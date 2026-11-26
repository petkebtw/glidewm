#!/usr/bin/env bash
# Rebuild ~/.config/quickshell from the pristine reference copy in src/ with the X11/dwm changes applied.
set -e
D="$HOME/.local/share/dss"
# build next to the live config and swap at the end: a running qs (Settings, the desktop) reloads on file changes and
# crashed on the half-built tree ("Non-existent attached object" on an unpatched WlrLayershell line)
QB="$HOME/.config/quickshell.build"
rm -rf "$QB"
cp -rL "$D/src" "$QB"     # -L: src may be a link into the glidewm repo (install.sh); never patch the repo
cd "$QB"
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
rm -rf "$D/bin"; cp -rL "$D/bin-src" "$D/bin"
find "$D/bin" "$QB" -type f \( -path "$D/bin/*" -o -name '*.qml' -o -name '*.sh' -o -name '*.js' \) -print0 | xargs -0 perl -pi -e 's#\.local/bin(?!\w)#.local/share/dss/bin#g'
# desktop-set clock style only took the old names (digital|line|cookie|pixel): Settings > Desktop > Clock style
# Stacked, Shape and Analog were refused, so the clock fell back to Expressive (upstream bug, still in V6.10)
python3 - "$D/bin/desktop-set" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
a = '"style": ["digital", "line", "cookie", "pixel"]'
if a in s:
    s = s.replace(a, '"style": STYLES["clock"]', 1)
    open(p, "w").write(s)
PY
# our tools take over some shell actions (ours/rice-hotcorner: screenshot and record -> rice-shot, rice-record;
# ours/rice-lock: lock now -> our X11 lock). The shell's script stays as NAME.dss for everything else.
# wallpaper lists of the shell (Settings > Wallpaper, the picker, slideshow, random at login): only real wallpapers,
# no screenshots, icons or small/tall pictures (~/.local/lib/rice/wallcheck.py, the same check as theme-switch)
python3 - "$D/bin/rice-walls" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
a = "    return sorted(set(fs), key=lambda f: os.path.basename(f).lower())\n"
assert s.count(a) == 1
s = s.replace(a, "    fs = sorted(set(fs), key=lambda f: os.path.basename(f).lower())\n"
  "    try:\n"
  "        sys.path.insert(0, os.path.expanduser(\"~/.local/lib/rice\"))\n"
  "        import wallcheck\n"
  "        fs = wallcheck.filter(fs)\n"
  "    except ImportError:\n"
  "        pass\n"
  "    return fs\n", 1)
open(p, "w").write(s)
PY
grep -q 'wallcheck.filter' "$D/bin/rice-walls"
for n in rice-hotcorner rice-lock rice-wm; do
  [ -f "$D/bin/$n" ] && [ -f "$D/ours/$n" ] && mv "$D/bin/$n" "$D/bin/$n.dss"
done
find -L "$D/ours/" -maxdepth 1 -type f -exec cp -t "$D/bin/" {} +
# rice-cava, rice-busy, rice-wm-watch, rice-widget-fade and rice-toplevels are C programs (rice/lean, linked in ours/)
# since 2026-11-26: they end with the Quickshell that started it (PR_SET_PDEATHSIG) and replace the shell's scripts.
# rice-ws-watch listens to Hyprland or niri only; on X11 it waited for a socket forever (~6 MB of Python, 2026-11-26)
perl -0pi -e 's/(\ndef main\(\):\n)/$1    if not (os.environ.get("NIRI_SOCKET") or os.environ.get("WAYLAND_DISPLAY")):\n        sys.exit(0)  # X11 (glidewm): no compositor events to listen to\n/' "$D/bin/rice-ws-watch"
grep -q 'X11 (glidewm): no compositor events' "$D/bin/rice-ws-watch" || echo "port.sh: the rice-ws-watch X11 exit did not apply" >&2
# apps started from dwm keys have no QML_IMPORT_PATH: call qs through our wrapper (ours/qs)
for f in rice-settings rice-app rice-desktop rice-wallpaper rice-hotcorner; do
  [ -f "$D/bin/$f" ] && perl -pi -e 's#(?<![\w/.-])qs (-n|-p)#\$HOME/.local/share/dss/bin/qs $1#g' "$D/bin/$f"
done

# X11: the mask is the window SHAPE, not only input. The holder animates (scale .92 + shift while fading in), so the shape
# froze smaller than the card and cut its top and left. Mask a static box that follows the final geometry instead.
perl -0pi -e 's/\Q(w.passive || w.editing) ? nothing : holder }\E/(w.passive || w.editing) ? nothing : maskBox }\n    Item { id: maskBox; x: w.px - w.mx; y: w.py - w.my; width: w.dispW; height: w.dispH }/' "$QB/rice-desktop/WidgetWindow.qml"
grep -q maskBox "$QB/rice-desktop/WidgetWindow.qml"

# widgets sit under windows. Quickshell read `aboveWindows: editing` once at creation (true), so every widget came up
# ABOVE and drew over windows and menus. Literal false = BELOW (dwm lowers those on map).
sed -i 's/^\(\s*\)aboveWindows: editing$/\1aboveWindows: false/' "$QB/rice-desktop/WidgetWindow.qml"
grep -q "aboveWindows: false" "$QB/rice-desktop/WidgetWindow.qml"

# tag switch to an empty desktop lagged: every widget window was unmapped when hidden and created again when shown
# (a new X window + GL surface each, about a dozen). Keep them mapped; hidden = opacity 0 and an empty input mask.
perl -0pi -e 's/visible: active && fk > 0\.01/visible: active/; s/\(w\.passive \|\| w\.editing\) \? nothing : maskBox/(w.passive || w.editing || w.hidden) ? nothing : maskBox/' "$QB/rice-desktop/WidgetWindow.qml"
grep -q "visible: active$" "$QB/rice-desktop/WidgetWindow.qml"

# small Images (app icons, tray, avatar, shapes) never left "Loading" with asynchronous: true on this X11 setup (all app icons blank).
# Icon-sized pictures load synchronously fine.
for f in AppIcon Bar RoundImage ShapeImage; do
  sed -i 's/asynchronous: true/asynchronous: false/' "$QB/rice-desktop/$f.qml"
done

# showing/hiding widgets: no fade (a dozen separate windows each re-rendered and re-composited ~20 frames while the tag slides in)
sed -i 's/Behavior on fk { NumberAnimation { duration: w.hidden ? 200 : 380;/Behavior on fk { enabled: false; NumberAnimation { duration: w.hidden ? 200 : 380;/' "$QB/rice-desktop/WidgetWindow.qml"
grep -q "Behavior on fk { enabled: false" "$QB/rice-desktop/WidgetWindow.qml"

# widgets are hidden by ours/rice-widget-fade (compositor opacity), never by re-rendering a dozen windows
sed -i 's/^    readonly property bool hideWidgets: .*/    readonly property bool hideWidgets: false/' "$QB/rice-desktop/shell.qml"
grep -q "hideWidgets: false" "$QB/rice-desktop/shell.qml"

# menus: closing a panel unmapped a fullscreen GL window, which cost X ~80 % CPU (the stutter on every close, worse when you
# open and close fast). Keep the window mapped for 60 s after it closes (empty input shape meanwhile), then let it go.
for f in ControlCenter Launcher ClipboardPanel GamePanel WallPicker Cheatsheet WifiMenu BluetoothMenu VolumeMenu PowerMenu TaskView; do
  perl -0pi -e 's/^    visible: (.+)$/    readonly property bool wmShown: $1\n    property bool wmWarm: false\n    visible: wmShown || wmWarm\n    onWmShownChanged: { if (wmShown) { wmWarm = true; wmWarmT.stop() } else wmWarmT.restart() }\n    Timer { id: wmWarmT; interval: 60000; onTriggered: if (!wmShown) wmWarm = false }\n    Item { id: wmAll; anchors.fill: parent }\n    Item { id: wmNone; width: 0; height: 0 }\n    mask: Region { item: wmShown ? wmAll : wmNone }/m' "$QB/rice-desktop/$f.qml"
  grep -q wmWarmT "$QB/rice-desktop/$f.qml"
done

# Qt's SVG renderer shows many icon SVGs (CSS <style>, currentColor: Dolphin, Konsole ...) as blank. Render every SVG icon to a PNG
# with rsvg-convert once (cached) and hand the PNG to the shell.
perl -0pi -e 's/^for a in "\$@"; do printf .%s\\t%s\\n. "\$a" "\$\(find_one "\$a"\)"; done\s*$/CACHE="\$HOME\/.cache\/rice\/svgicons"; mkdir -p "\$CACHE"\nfor a in "\$@"; do\n  f="\$(find_one "\$a")"\n  case "\$f" in\n    *.svg) o="\$CACHE\/\$(printf %s "\$f" | md5sum | cut -c1-16).png"\n           [ -s "\$o" ] || rsvg-convert -w 128 -h 128 -a "\$f" -o "\$o" 2>\/dev\/null || o=""\n           [ -n "\$o" ] && f="\$o" ;;\n  esac\n  printf "%s\\t%s\\n" "\$a" "\$f"\ndone\n/m' "$QB/rice-desktop/iconfile.sh"
tail -12 "$QB/rice-desktop/iconfile.sh"
bash -n "$QB/rice-desktop/iconfile.sh" && echo syntax-ok

# Icons.qml: a theme change (breeze-dark is set a moment after start) wipes `asked`/`pending` while a batch is in flight, so
# some names (Dolphin, Konsole ...) were marked asked but never looked up: blank icons for good. Re-queue anything asked and
# still unresolved every 2.5 s.
perl -0pi -e 's/\n\}\s*$/\n    Timer {\n        interval: 2500; running: true; repeat: true\n        onTriggered: {\n            if (look.running) return\n            const miss = Object.keys(ic.asked).filter(function(k) { return ic.files[k] === undefined && ic.pending.indexOf(k) < 0 })\n            if (miss.length > 0) { ic.pending = ic.pending.concat(miss); ic.next() }\n        }\n    }\n}\n/' "$QB/rice-desktop/Icons.qml"
grep -q "const miss" "$QB/rice-desktop/Icons.qml"

# an empty icon file (aonsoku.png is 0 bytes) is no icon: fall back to the default app icon
sed -i 's|\[ -f "\$n" \] && echo "\$n"; return 0|[ -s "$n" ] \&\& echo "$n"; return 0|' "$QB/rice-desktop/iconfile.sh"

# Quickshell's DesktopEntry.execute() ignores Terminal=true (btop, vim ... did nothing): run those in konsole.
perl -0pi -e 's/r\.entry\.execute\(\)/(r.entry.runInTerminal ? Quickshell.execDetached(["konsole", "-e"].concat(r.entry.command)) : r.entry.execute())/' "$QB/rice-desktop/Launcher.qml"
grep -q 'runInTerminal ? Quickshell.execDetached' "$QB/rice-desktop/Launcher.qml"

# theme colors: the shell menus were near-black grey with only the accent tinted. themes.apply writes bg/bg2 of the theme to
# waybar/colors.css; shell.qml hands them to Look, and the shell surface/cards (NPal) take them.
Q="$QB/rice-desktop"
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
python3 - "$QB/rice-settings/LookFeelPage.qml" "$D/patches" <<'PY'
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
grep -q "galRun" "$QB/rice-settings/LookFeelPage.qml"

# popups (launcher, control centre, clipboard, cheatsheet, power, wallpaper picker, game bar, task view) open on the screen
# under the pointer, not on the fixed main screen: Trigger asks xdotool for the pointer before it fires, Mon.pop holds the screen
python3 - "$QB/rice-desktop" <<'PY'
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
grep -q "Mon.pop" "$QB/rice-desktop/Launcher.qml"

# clock hours tone: a grey theme colour has no hue; forcing saturation 0.25 on hue 0 made it pink
python3 - "$QB/rice-desktop/ClockWidget.qml" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
a = "Math.min(0.7, Math.max(0.25, hand.hslSaturation))"
assert s.count(a) == 1
s = s.replace(a, "(hand.hslSaturation < 0.08 ? hand.hslSaturation : Math.min(0.7, Math.max(0.25, hand.hslSaturation)))")
open(p, "w").write(s)
PY
grep -q "hand.hslSaturation < 0.08" "$QB/rice-desktop/ClockWidget.qml"

# launcher (M3): hovering moved the selection and scrolled the list under the pointer; only typing, arrows and clicks select
perl -0pi -e 's/^\s*onPositionChanged: \{ ln\.noScroll = true; ln\.cur = (cell|row)\.index; ln\.noScroll = false \}\n//mg' "$QB/rice-desktop/LauncherM3.qml"
if grep -q 'onPositionChanged: { ln.noScroll = true' "$QB/rice-desktop/LauncherM3.qml"; then echo "LauncherM3 hover patch did not apply"; exit 1; fi

# Settings on glidewm: hide the pages that only work on Hyprland / niri or with the QML bar (it is off: the dwm bar is used),
# put an glidewm page (patches/GlidewmPage.qml: opens the glidewm settings app and tools) where the Hyprland page was, name glidewm.
#   gone: 2 bar, 3 bar layout, 5 recorder (rice-record is used), 6 island (lives in the QML bar), 11 idle & lock
#   (hypridle, Wayland lock), 23 keyboard (Hyprland input), 28 monitors (hypr-set), 30 keybinds (Hyprland/niri),
#   33 infinite desktop (Hyprland plugin), 36 window rules (Hyprland). A link to one of them lands on the glidewm page.
cp "$D/patches/GlidewmPage.qml" "$QB/rice-settings/GlidewmPage.qml"
python3 - "$QB/rice-settings" <<'PY'
import sys, re
q = sys.argv[1]
p = q + "/shell.qml"; s = open(p).read()
def sub(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)
sub('readonly property string wmLabel: niri ? "niri" : "Hyprland"', 'readonly property string wmLabel: "glidewm"')
sub('pages: niri ? [29, 12, 25, 36, 4, 11] : [29, 33, 12, 25, 36, 4, 11]', 'pages: [4, 29, 12, 25]')
sub('pages: [2, 3, 6, 7]', 'pages: [7]')
# the other groups (System gained 41 Care in V6.00 ...): drop the gone pages from whatever list upstream has now
def keep(m):
    ids = [i for i in re.findall(r"\d+", m.group(1)) if int(i) not in {2, 3, 5, 6, 11, 23, 28, 30, 33, 36}]
    return "pages: [" + ", ".join(ids) + "]"
s, k = re.subn(r'(?m)(?<=sym: "settings", )pages: \[([\d, ]+)\]', keep, s)
assert k == 1, "System group pages"
sub('onPageChanged: {', 'readonly property var gone: [2, 3, 5, 6, 11, 23, 28, 30, 33, 36]\n    onPageChanged: { if (gone.indexOf(page) >= 0) { page = 4; return }')
sub('HyprlandPage { anchors.fill: parent; ctl: win }', 'GlidewmPage { anchors.fill: parent; ctl: win }')
gone = {2, 3, 5, 6, 11, 23, 28, 30, 33, 36}
n = 0
def drop(m):
    global n
    if int(m.group(2)) in gone:
        n += 1
        return ""
    return m.group(0)
s = re.sub(r"(?m)^(\s*PageSlot \{ nav: win; idx: (\d+);.*\n)", drop, s)
assert n == len(gone), n
open(p, "w").write(s)
p = q + "/AboutPage.qml"; s = open(p).read()
sub('{ n: "Hyprland", u: "https://hypr.land" }, { n: "niri", u: "https://github.com/niri-wm/niri" }',
    '{ n: "glidewm", u: "https://github.com/petkebtw/glidewm" }, { n: "dwm", u: "https://dwm.suckless.org" }')
sub('n: page.info.wm || "Hyprland"', 'n: page.info.wm || "glidewm"')
open(p, "w").write(s)
PY
grep -q 'GlidewmPage { anchors.fill' "$QB/rice-settings/shell.qml"

# Settings rows that cannot work on glidewm/X11 (Hyprland blur, animations, input, gaming mode, Minimal mode, night light,
# Light mode ...) are hidden: patches/hide-dead.py (list and rules in it)
python3 "$D/patches/hide-dead.py" "$QB/rice-settings" >/dev/null
grep -q 'visible: false' "$QB/rice-settings/HomePage.qml"

# the dock's panel: the "tinted" surface (a dark shade of the wallpaper color) instead of the theme's near-black bg;
# at a low opacity over picom's blur the near-black read as flat grey
perl -pi -e 's/NPal \{ id: pal; theme: "shell"; alpha: dock\.alpha \}/NPal { id: pal; theme: "tinted"; alpha: dock.alpha }/' "$QB/rice-desktop/Dock.qml"
grep -q 'NPal { id: pal; theme: "tinted"; alpha: dock.alpha }' "$QB/rice-desktop/Dock.qml"

# the dock slides in without a map: its window stays mapped and, while hidden, takes no input (an empty mask; the 3 px
# strip below brings it back). Mapped on every reveal, NVIDIA's first frame of the new window ate most of the 260 ms
# slide, so the dock just popped up.
python3 - "$QB/rice-desktop/Dock.qml" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
def sub(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)
sub("visible: dock.on && (dock.reveal || dock.t > 0.01)", "visible: dock.on")
sub("mask: dock.mag > 0 ? magRegion : null\n        Region { id: magRegion; item: panel }",
    "mask: !dock.reveal && dock.t < 0.01 ? noInput : (dock.mag > 0 ? magRegion : null)\n"
    "        Region { id: magRegion; item: panel }\n"
    "        Region { id: noInput }")
# the Grid's add transition (opacity 0 -> 1, scale 0.3 -> 1) left every part at opacity 0 on X11: the dock showed as
# an empty bar. Without it the parts are simply there (seen in Xvfb: empty with it, icons and song without it)
i = s.find("                add: Transition {")
j = s.find("                Repeater {", i)
assert i > 0 and j > i and s[i:j].count("Transition") == 1, "dock add transition"
s = s[:i] + s[j:]
# the song's picture: a player that sends no art (Mullvad Browser / SoundCloud: no mpris:artUrl) left an empty grey
# square; a music note in the theme colour stands there now
sub("""                        source: dock.player && dock.player.trackArtUrl ? dock.player.trackArtUrl : ""
                    }""", """                        source: dock.player && dock.player.trackArtUrl ? dock.player.trackArtUrl : ""
                        Rectangle { anchors.fill: parent; radius: Look.sq ? 0 : 12; color: pal.container
                            visible: !(dock.player && dock.player.trackArtUrl)
                            MIcon { anchors.centerIn: parent; size: 20; name: "music_note"; glyph: String.fromCodePoint(0xF075A); color: pal.inkContainer } }
                    }""")
open(p, "w").write(s)
PY

# hover a tag on dwm's bar: a card under it lists the apps on that tag (patches/TagPeek.qml; dwm writes _RICE_HOVER,
# rice-toplevels passes it to ToplevelManager.hover)
cp "$D/patches/TagPeek.qml" "$QB/rice-desktop/TagPeek.qml"
python3 - "$QB/rice-desktop/shell.qml" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
a = "    Dock { id: dockObj;"
assert s.count(a) == 1, "shell.qml Dock line"
s = s.replace(a, "    TagPeek { }\n" + a)
open(p, "w").write(s)
PY

# fewer shell windows (2026-11-26): every mapped Quickshell window has its own render thread and GL context (~6 MB
# on NVIDIA). WallLum (wallpaper brightness, a 2 x 2 window) and VibeCover (the song cover's colours) exist only while
# they measure: Look.lumGrid / Vibe.tint* keep the result. The dock's 3 px reveal strip is no window of its own: while
# the dock is away, the dock window (always mapped) takes input only on that strip.
python3 - "$QB/rice-desktop" <<'PY'
import sys
q = sys.argv[1]
def sub(f, a, b):
    p = q + "/" + f; s = open(p).read()
    assert s.count(a) == 1, (f, a)
    open(p, "w").write(s.replace(a, b))
sub("shell.qml", "    WallLum { path: root.wallpaper; sw: root.sw; sh: root.sh }\n",
    "    // made only while it measures a new wallpaper (or screen size); Look.lumGrid keeps the result\n"
    "    property string lumKey: \"\"\n"
    "    LazyLoader {\n"
    "        active: Look.adapt && root.wallpaper !== \"\" && root.lumKey !== root.wallpaper + \"|\" + root.sw + \"x\" + root.sh\n"
    "        WallLum { path: root.wallpaper; sw: root.sw; sh: root.sh; onMeasured: root.lumKey = path + \"|\" + sw + \"x\" + sh }\n"
    "    }\n")
sub("shell.qml", "    VibeCover { }\n",
    "    // made only while it reads a new cover; Vibe.tint, tint2 and tintOf keep the result\n"
    "    LazyLoader { active: Vibe.cover && Player.art !== \"\" && Vibe.tintOf !== Player.art; VibeCover { } }\n")
# WallLum says when it is done: painted with the picture's real shape (the probe has its size, or failed)
sub("WallLum.qml", "    property real ratio: 16 / 9      // width / height of the wallpaper picture\n",
    "    property real ratio: 16 / 9      // width / height of the wallpaper picture\n"
    "    signal measured()\n"
    "    readonly property bool probed: probe.status === Image.Ready || probe.status === Image.Error\n")
sub("WallLum.qml", "        onStatusChanged: if (status === Image.Ready && implicitHeight > 0) { wl.ratio = implicitWidth / implicitHeight; cv.requestPaint() }",
    "        onStatusChanged: { if (status === Image.Ready && implicitHeight > 0) { wl.ratio = implicitWidth / implicitHeight; cv.requestPaint() }\n"
    "                           else if (status === Image.Error) cv.requestPaint() }")
sub("WallLum.qml", "            Look.lumGrid = g\n", "            Look.lumGrid = g\n            if (wl.probed) wl.measured()\n")
# the dock: the strip window goes, the dock window takes its place
p = q + "/Dock.qml"; s = open(p).read()
i = s.find("    // ---------------- the strip that brings the dock back ----------------\n")
j = s.find("    // ---------------- the dock ----------------\n")
assert i > 0 and j > i and s[i:j].count("PanelWindow") == 1, "dock strip window"
s = s[:i] + s[j:]
open(p, "w").write(s)
sub("Dock.qml", "        mask: !dock.reveal && dock.t < 0.01 ? noInput : (dock.mag > 0 ? magRegion : null)\n",
    "        mask: !dock.reveal && dock.t < 0.01 ? (dock.autoHide ? edgeRegion : noInput) : (dock.mag > 0 ? magRegion : null)\n"
    "        Region { id: edgeRegion; item: edgeStrip }\n")
sub("Dock.qml", "        MouseArea {\n            id: dockMouse\n",
    "        // the strip along the edge that brings the dock back (its own 3 px window before: one render thread and\n"
    "        // GL context less); while the dock is away it is the only part of this window that takes input\n"
    "        MouseArea {\n"
    "            id: edgeStrip\n"
    "            z: 10\n"
    "            enabled: dock.on && dock.autoHide && !dock.reveal && dock.t < 0.05\n"
    "            hoverEnabled: true\n"
    "            width: dock.vert ? 3 : Math.min(parent.width, Math.max(200, panel.width))\n"
    "            height: dock.vert ? Math.min(parent.height, Math.max(200, panel.height)) : 3\n"
    "            x: dock.edge === \"left\" ? 0 : (dock.edge === \"right\" ? parent.width - width : (parent.width - width) / 2)\n"
    "            y: dock.vert ? (parent.height - height) / 2 : parent.height - height\n"
    "            onEntered: { hideTimer.stop(); dock.hovering = true }\n"
    "        }\n"
    "        MouseArea {\n            id: dockMouse\n")
PY
grep -q 'id: edgeStrip' "$QB/rice-desktop/Dock.qml"
grep -q 'onMeasured: root.lumKey' "$QB/rice-desktop/shell.qml"

# smooth wheel scrolling in Settings: patches/WheelScroll.qml glides on a critically damped spring (no kick and
# sudden stop on every notch), and the boxes that scrolled with Qt's plain wheel jumps get it too: the side menu,
# the search results and What's new; over the fastfetch output on Look & Feel the page scrolls
cp "$D/patches/WheelScroll.qml" "$QB/rice-settings/WheelScroll.qml"
python3 - "$QB/rice-settings" <<'PY2'
import sys
q = sys.argv[1]
def sub(f, a, b):
    p = q + "/" + f; s = open(p).read()
    assert s.count(a) == 1, (f, a)
    open(p, "w").write(s.replace(a, b))
sub("PageScroll.qml", "property alias body: flick", "property alias body: flick\n    property alias wheel: flickWheel")
sub("LookFeelPage.qml", "    PageScroll {\n        anchors.fill: parent", "    PageScroll {\n        id: pageScroll\n        anchors.fill: parent")
# the fastfetch output box claims more height than its text (it would scroll into blank space): the page scrolls there
sub("LookFeelPage.qml", "id: out\n", "id: out\n                        WheelHandler { acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad; onWheel: function(e) { pageScroll.wheel.take(e) } }\n")
sub("shell.qml", "id: navFlick\n", "id: navFlick\n            WheelScroll { flick: navFlick }\n")
sub("shell.qml", "id: resultList\n", "id: resultList\n            WheelScroll { flick: resultList }\n")
sub("WhatsNew.qml", "id: list\n", "id: list\n            WheelScroll { flick: list }\n")
PY2
grep -q 'critically damped' "$QB/rice-settings/WheelScroll.qml"

# wallpapers picked in the shell (Wallpaper page, themes, presets, the picker) go through the glidewm theme pipeline
# (feh, colours for dwm, rofi, terminals and the shell): awww and matugen do not exist here, nothing changed before
python3 - "$QB/hyprquickpaper/commands.sh" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
a = 'esac\n\nmkdir -p "$HOME/.cache/rice" "$HOME/.config/waybar"\n'
assert s.count(a) == 1
s = s.replace(a, 'esac\n\n# glidewm: the picture goes through the glidewm theme pipeline (themes.apply)\n'
  'if [ -f "$HOME/.local/lib/rice/themes.py" ]; then\n'
  '  echo "$img" > "$HOME/.cache/hyprquickpaper-current"\n'
  '  exec python3 -c \'import os, sys; sys.path.insert(0, os.path.expanduser("~/.local/lib/rice")); import themes; themes.apply(themes.item_for(sys.argv[1]))\' "$img"\n'
  'fi\n\n' + a, 1)
open(p, "w").write(s)
PY
grep -q 'themes.apply(themes.item_for' "$QB/hyprquickpaper/commands.sh"

# swap in the finished tree in one step (the old one goes away after)
cd "$HOME/.config"
rm -rf "$HOME/.config/quickshell.old"
[ -e "$HOME/.config/quickshell" ] && mv "$HOME/.config/quickshell" "$HOME/.config/quickshell.old"
mv "$QB" "$HOME/.config/quickshell"
rm -rf "$HOME/.config/quickshell.old"
