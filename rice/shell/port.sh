#!/usr/bin/env bash
# Rebuild ~/.config/quickshell from the pristine reference copy in src/ with the X11/dwm changes applied.
set -e
D="$HOME/.local/share/dss"
rm -rf "$HOME/.config/quickshell"
cp -r "$D/src" "$HOME/.config/quickshell"
cd "$HOME/.config/quickshell"
# layer-shell attached properties do not exist on X11 panels
# layer -> X11 stacking (PanelWindow.aboveWindows); namespace / keyboardFocus have no X11 meaning
find . -name '*.qml' -print0 | xargs -0 sed -i -E \
  -e 's/^(\s*)WlrLayershell\.layer:\s*editing \? WlrLayer\.Top : WlrLayer\.Bottom.*$/\1aboveWindows: editing/' \
  -e 's/^(\s*)WlrLayershell\.layer:\s*WlrLayer\.(Bottom|Background)\s*$/\1aboveWindows: false/' \
  -e '/^\s*WlrLayershell\.(layer|namespace|keyboardFocus)\s*:/d'
# window manager backend
cp "$D/Wm.dwm.qml" rice-desktop/Wm.qml
sed -i '/^import Quickshell.Hyprland/d' rice-desktop/Wm.qml

# every reference script and QML/sh file calls helpers as $HOME/.local/bin/NAME: point them at our private copy instead,
# so nothing of ~/.local/bin (rice-settings, rice-lock, rice-power ... are different programs there) is shadowed
rm -rf "$D/bin"; cp -r "$D/bin-src" "$D/bin"
find "$D/bin" "$HOME/.config/quickshell" -type f \( -path "$D/bin/*" -o -name '*.qml' -o -name '*.sh' -o -name '*.js' \) -print0 | xargs -0 perl -pi -e 's#\.local/bin(?!\w)#.local/share/dss/bin#g'
cp "$D/ours/"* "$D/bin/"
# apps started from dwm keys have no QML_IMPORT_PATH: call qs through our wrapper (ours/qs)
for f in rice-settings rice-app rice-desktop rice-wallpaper rice-hotcorner; do
  [ -f "$D/bin/$f" ] && perl -pi -e 's#(?<![\w/.-])qs (-n|-p)#\$HOME/.local/share/dss/bin/qs $1#g' "$D/bin/$f"
done

# X11: the mask is the window SHAPE, not only input. The holder animates (scale .92 + shift while fading in), so the shape
# froze smaller than the card and cut its top and left. Mask a static box that follows the final geometry instead.
perl -0pi -e 's/\Q(w.passive || w.editing) ? nothing : holder }\E/(w.passive || w.editing) ? nothing : maskBox }\n    Item { id: maskBox; x: w.px - w.mx; y: w.py - w.my; width: w.dispW; height: w.dispH }/' "$HOME/.config/quickshell/rice-desktop/WidgetWindow.qml"
grep -q maskBox "$HOME/.config/quickshell/rice-desktop/WidgetWindow.qml"

# widgets sit under windows. Quickshell read `aboveWindows: editing` once at creation (true), so every widget came up
# ABOVE and drew over windows and menus. Literal false = BELOW (dwm lowers those on map).
sed -i 's/^\(\s*\)aboveWindows: editing$/\1aboveWindows: false/' "$HOME/.config/quickshell/rice-desktop/WidgetWindow.qml"
grep -q "aboveWindows: false" "$HOME/.config/quickshell/rice-desktop/WidgetWindow.qml"

# tag switch to an empty desktop lagged: every widget window was unmapped when hidden and created again when shown
# (a new X window + GL surface each, about a dozen). Keep them mapped; hidden = opacity 0 and an empty input mask.
perl -0pi -e 's/visible: active && fk > 0\.01/visible: active/; s/\(w\.passive \|\| w\.editing\) \? nothing : maskBox/(w.passive || w.editing || w.hidden) ? nothing : maskBox/' "$HOME/.config/quickshell/rice-desktop/WidgetWindow.qml"
grep -q "visible: active$" "$HOME/.config/quickshell/rice-desktop/WidgetWindow.qml"

# small Images (app icons, tray, avatar, shapes) never left "Loading" with asynchronous: true on this X11 setup (all app icons blank).
# Icon-sized pictures load synchronously fine.
for f in AppIcon Bar RoundImage ShapeImage; do
  sed -i 's/asynchronous: true/asynchronous: false/' "$HOME/.config/quickshell/rice-desktop/$f.qml"
done

# showing/hiding widgets: no fade (a dozen separate windows each re-rendered and re-composited ~20 frames while the tag slides in)
sed -i 's/Behavior on fk { NumberAnimation { duration: w.hidden ? 200 : 380;/Behavior on fk { enabled: false; NumberAnimation { duration: w.hidden ? 200 : 380;/' "$HOME/.config/quickshell/rice-desktop/WidgetWindow.qml"
grep -q "Behavior on fk { enabled: false" "$HOME/.config/quickshell/rice-desktop/WidgetWindow.qml"

# widgets are hidden by ours/rice-widget-fade (compositor opacity), never by re-rendering a dozen windows
sed -i 's/^    readonly property bool hideWidgets: .*/    readonly property bool hideWidgets: false/' "$HOME/.config/quickshell/rice-desktop/shell.qml"
grep -q "hideWidgets: false" "$HOME/.config/quickshell/rice-desktop/shell.qml"

# menus: closing a panel unmapped a fullscreen GL window, which cost X ~80 % CPU (the stutter on every close, worse when you
# open and close fast). Keep the window mapped for 60 s after it closes (empty input shape meanwhile), then let it go.
for f in ControlCenter Launcher ClipboardPanel GamePanel WallPicker Cheatsheet WifiMenu BluetoothMenu VolumeMenu PowerMenu TaskView; do
  perl -0pi -e 's/^    visible: (.+)$/    readonly property bool wmShown: $1\n    property bool wmWarm: false\n    visible: wmShown || wmWarm\n    onWmShownChanged: { if (wmShown) { wmWarm = true; wmWarmT.stop() } else wmWarmT.restart() }\n    Timer { id: wmWarmT; interval: 60000; onTriggered: if (!wmShown) wmWarm = false }\n    Item { id: wmAll; anchors.fill: parent }\n    Item { id: wmNone; width: 0; height: 0 }\n    mask: Region { item: wmShown ? wmAll : wmNone }/m' "$HOME/.config/quickshell/rice-desktop/$f.qml"
  grep -q wmWarmT "$HOME/.config/quickshell/rice-desktop/$f.qml"
done

# Qt's SVG renderer shows many icon SVGs (CSS <style>, currentColor: Dolphin, Konsole ...) as blank. Render every SVG icon to a PNG
# with rsvg-convert once (cached) and hand the PNG to the shell.
perl -0pi -e 's/^for a in "\$@"; do printf .%s\\t%s\\n. "\$a" "\$\(find_one "\$a"\)"; done\s*$/CACHE="\$HOME\/.cache\/rice\/svgicons"; mkdir -p "\$CACHE"\nfor a in "\$@"; do\n  f="\$(find_one "\$a")"\n  case "\$f" in\n    *.svg) o="\$CACHE\/\$(printf %s "\$f" | md5sum | cut -c1-16).png"\n           [ -s "\$o" ] || rsvg-convert -w 128 -h 128 -a "\$f" -o "\$o" 2>\/dev\/null || o=""\n           [ -n "\$o" ] && f="\$o" ;;\n  esac\n  printf "%s\\t%s\\n" "\$a" "\$f"\ndone\n/m' "$HOME/.config/quickshell/rice-desktop/iconfile.sh"
tail -12 "$HOME/.config/quickshell/rice-desktop/iconfile.sh"
bash -n "$HOME/.config/quickshell/rice-desktop/iconfile.sh" && echo syntax-ok

# Icons.qml: a theme change (breeze-dark is set a moment after start) wipes `asked`/`pending` while a batch is in flight, so
# some names (Dolphin, Konsole ...) were marked asked but never looked up: blank icons for good. Re-queue anything asked and
# still unresolved every 2.5 s.
perl -0pi -e 's/\n\}\s*$/\n    Timer {\n        interval: 2500; running: true; repeat: true\n        onTriggered: {\n            if (look.running) return\n            const miss = Object.keys(ic.asked).filter(function(k) { return ic.files[k] === undefined && ic.pending.indexOf(k) < 0 })\n            if (miss.length > 0) { ic.pending = ic.pending.concat(miss); ic.next() }\n        }\n    }\n}\n/' "$HOME/.config/quickshell/rice-desktop/Icons.qml"
grep -q "const miss" "$HOME/.config/quickshell/rice-desktop/Icons.qml"

# an empty icon file (aonsoku.png is 0 bytes) is no icon: fall back to the default app icon
sed -i 's|\[ -f "\$n" \] && echo "\$n"; return 0|[ -s "$n" ] \&\& echo "$n"; return 0|' "$HOME/.config/quickshell/rice-desktop/iconfile.sh"

# Quickshell's DesktopEntry.execute() ignores Terminal=true (btop, vim ... did nothing): run those in konsole.
perl -0pi -e 's/r\.entry\.execute\(\)/(r.entry.runInTerminal ? Quickshell.execDetached(["konsole", "-e"].concat(r.entry.command)) : r.entry.execute())/' "$HOME/.config/quickshell/rice-desktop/Launcher.qml"
grep -q 'runInTerminal ? Quickshell.execDetached' "$HOME/.config/quickshell/rice-desktop/Launcher.qml"

# theme colors: the shell menus were near-black grey with only the accent tinted. themes.apply writes bg/bg2 of the theme to
# waybar/colors.css; shell.qml hands them to Look, and the shell surface/cards (NPal) take them.
Q="$HOME/.config/quickshell/rice-desktop"
perl -0pi -e 's/(    property color accent: "#9ec9bd"\n)/$1    property color themeBg: "transparent"\n    property color themeBg2: "transparent"\n/' "$Q/Look.qml"
grep -q "themeBg2" "$Q/Look.qml"
perl -0pi -e 's|onContent: function\(t\) \{ const r = /\@define-color accent \*\(#\[0-9a-fA-F\]\{6\}\)/\.exec\(t\); if \(r\) root\.setAccent\(r\[1\]\) \}|onContent: function(t) { const r = /\@define-color accent *(#[0-9a-fA-F]{6})/.exec(t); if (r) root.setAccent(r[1]); const b = /\@define-color bg *(#[0-9a-fA-F]{6})/.exec(t); if (b) Look.themeBg = b[1]; const b2 = /\@define-color bg2 *(#[0-9a-fA-F]{6})/.exec(t); if (b2) Look.themeBg2 = b2[1] }|' "$Q/shell.qml"
grep -q "Look.themeBg2" "$Q/shell.qml"
perl -0pi -e 's|default: return Qt\.hsla\(hue, mono \? 0 : 0\.12, 0\.1, a\)|default: return Look.themeBg.a > 0 ? Qt.rgba(Look.themeBg.r, Look.themeBg.g, Look.themeBg.b, a) : Qt.hsla(hue, mono ? 0 : 0.12, 0.1, a)|; s|(readonly property color cardBase: light \? Qt\.rgba\(1, 1, 1, 1\) : )|$1(theme === "shell" \&\& Look.themeBg2.a > 0 ? Look.themeBg2 : |; s|(theme === "black" \? 2\.6 : 1\.75\))(\n)|$1)$2|' "$Q/NPal.qml"
grep -q "Look.themeBg2" "$Q/NPal.qml"

# clock: the wallpaper is bright in the file but sits under dark text on screen, so the adaptive dark ink blended in. Always light ink,
# and the hours / date pill take the bright theme accent.
perl -0pi -e 's/readonly property bool lightBg: pal \? pal\.light : false/readonly property bool lightBg: false/; s/readonly property color hand: pal \? pal\.primary : "#F6F5F4"/readonly property color hand: Look.accentHi/; s/color: ck\.pal \? ck\.pal\.primary : "#33ffffff"/color: Look.accentHi/; s/color: ck\.pal \? ck\.pal\.inkOn : "white"/color: "#10131a"/; s/readonly property color ink: pal \? pal\.fg : "#F6F5F4"/readonly property color ink: "#F6F5F4"/' "$Q/ClockWidget.qml"
grep -q 'lightBg: false' "$Q/ClockWidget.qml"
grep -q 'hand: Look.accentHi' "$Q/ClockWidget.qml"

# fastfetch logo gallery in Settings > Look & Feel (ff-logo in ours/, art in ~/.local/share/rice/fflogos, hook in ~/.local/lib/rice/hooks.py)
python3 - "$HOME/.config/quickshell/rice-settings/LookFeelPage.qml" "$D/patches" <<'PY'
import sys
p, d = sys.argv[1], sys.argv[2]
s = open(p).read()
a = '    property string busy: ""'
b = '        // ---------- shell ----------'
assert s.count(a) == 1 and s.count(b) == 1
s = s.replace(a, open(d + "/lookfeel-gallery-props.qml").read() + a, 1)
s = s.replace(b, open(d + "/lookfeel-gallery-ui.qml").read() + b, 1)
open(p, "w").write(s)
PY
grep -q "galRun" "$HOME/.config/quickshell/rice-settings/LookFeelPage.qml"

# popups (launcher, control centre, clipboard, cheatsheet, power, wallpaper picker, game bar, task view) open on the screen
# under the pointer, not on the fixed main screen: Trigger asks xdotool for the pointer before it fires, Mon.pop holds the screen
python3 - "$HOME/.config/quickshell/rice-desktop" <<'PY'
import sys, re
q = sys.argv[1]
p = q + "/Mon.qml"; s = open(p).read()
a = "    readonly property var widgetScreen:"
assert s.count(a) == 1
s = s.replace(a, '    property string popName: ""\n    readonly property var pop: popName !== "" ? pick(Quickshell.screens, popName) : screen\n' + a, 1)
open(p, "w").write(s)
p = q + "/Trigger.qml"; s = open(p).read()
assert s.count("tr.fired(o)") == 2
s = s.replace("tr.fired(o)", "tr.emit(o)")
a = "    FileView {\n        id: fv"
assert s.count(a) == 1
add = '''    property string pend: ""
    function emit(line) { pend = line; pp.running = false; pp.running = true }
    Process {
        id: pp
        command: ["xdotool", "getmouselocation"]
        stdout: StdioCollector { onStreamFinished: {
            const m = /x:(-?\\d+) y:(-?\\d+)/.exec(text)
            if (m) {
                const x = parseInt(m[1]), y = parseInt(m[2]), l = Quickshell.screens
                for (let i = 0; i < l.length; i++)
                    if (x >= l[i].x && x < l[i].x + l[i].width && y >= l[i].y && y < l[i].y + l[i].height) { Mon.popName = String(l[i].name); break }
            }
            tr.fired(tr.pend)
        } }
        onExited: function(c) { if (c !== 0) tr.fired(tr.pend) }
    }
'''
s = s.replace(a, add + a, 1)
open(p, "w").write(s)
for f in "Launcher ControlCenter ClipboardPanel Cheatsheet PowerMenu WallPicker GamePanel TaskView".split():
    p = q + "/" + f + ".qml"; s = open(p).read()
    assert s.count("screen: Mon.screen") == 1, f
    open(p, "w").write(s.replace("screen: Mon.screen", "screen: Mon.pop"))
PY
grep -q "Mon.pop" "$HOME/.config/quickshell/rice-desktop/Launcher.qml"

# clock hours tone: a grey theme colour has no hue; forcing saturation 0.25 on hue 0 made it pink
python3 - "$HOME/.config/quickshell/rice-desktop/ClockWidget.qml" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
a = "Math.min(0.7, Math.max(0.25, hand.hslSaturation))"
assert s.count(a) == 1
s = s.replace(a, "(hand.hslSaturation < 0.08 ? hand.hslSaturation : Math.min(0.7, Math.max(0.25, hand.hslSaturation)))")
open(p, "w").write(s)
PY
grep -q "hand.hslSaturation < 0.08" "$HOME/.config/quickshell/rice-desktop/ClockWidget.qml"
