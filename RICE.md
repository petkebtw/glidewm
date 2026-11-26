# Rice cheat sheet

dwm 6.8 on Gentoo, with a set of Python/GTK helpers in `~/.local/bin`. `Mod` is Alt. Every key below can be changed in
Settings > Shortcuts (stored in `~/.config/rice/binds.conf`, needs the rebuilt dwm).

## Keys

| Key | Action |
|---|---|
| `Mod+Shift+Return` | terminal (konsole) |
| `Mod+p` | app launcher (the search card, same as `Mod+s`) |
| `Mod+s` | universal search (apps, files, settings, commands, math; `>` run, `?` web, `=` calc) |
| `Mod+o` | settings (the Quickshell Settings app; `Mod+Shift+o` the same, `Mod+Shift+t` opens its Theme page) |
| `Mod+n` | control centre (Control / Today / System / Style tabs; Style = motion presets, dock options) |
| `Mod+e` | edit desktop widgets (goes to the first empty tag of the widget monitor first; drag, corner resize, arrows nudge, Delete, `b` glass/bare, `a` add, Esc save) |
| `Mod+Shift+e` | add a desktop widget |
| `Mod+Shift+o` | tools menu |
| `Mod+Shift+t` | theme switcher (arrows, `o` online/offline, `g` glass, `r` rice mode, `s` source, Enter keep, Esc revert) |
| `Mod+v` | clipboard history (filter, Up/Down, Enter copies, Esc closes) |
| `Mod+Shift+m` | media card (space, arrows, n, p, Esc) |
| `Print` / `Mod+Shift+s` | screenshot (Print = the monitor under the pointer; `f` desktop, `m` monitor). In the editor: scroll zooms, middle drag pans, `0` resets, `x` or the Copy text button reads the text (OCR: English, German, French, Spanish, Hungarian, Russian) |
| `Mod+Shift+r` | screen recorder (audio output, per-app audio, mic) |
| `Mod+Shift+l` | lock |
| `Mod+space` | next layout (tile, bento, dock, mosaic) |
| `Mod+Ctrl+space` | default layout (tile) |
| `Mod+t` | tile |
| `Mod+Shift+space` | float / unfloat the focused window |
| `Mod+j` / `Mod+k` | focus next / previous |
| `Mod+Shift+j` / `Mod+Shift+k` | move window down / up the stack |
| `Mod+Return` | make master |
| `Mod+h` / `Mod+l` | master size, `Mod+i` / `Mod+d` master count |
| `Mod+1..9` | workspace, `Mod+Shift+1..9` move window there |
| `Mod+arrows` | snap half / quarter, `+Shift` nudge, `+Ctrl` resize |
| `Mod+-` / `Mod+=` / `Mod+Shift+=` | gaps smaller / bigger / reset |
| `Mod+b` | toggle bar |
| `Mod+Shift+g` | canvas mode (drag background to pan) |
| `Mod+scroll` | zoom the canvas in place (canvas mode): every window moves and resizes about the pointer, the bar shows the percentage. `Mod+Ctrl+0` back to 100% |
| `Mod+z` | canvas zoom: a camera over the canvas on every monitor (scroll zoom, drag pan, drag a window to move it, click a window to fly there, middle click closes, arrows next, `f` fit, `0` 100%, Esc). Needs canvas mode for panning |
| `Mod+Shift+c` | close window |
| `Mod+Shift+q` | quit dwm |
| `Mod+Shift+Ctrl+q` | restart dwm, windows stay |

## Layouts

- **tile** master left, stack right.
- **bento** big window left, a big tile top right, smaller tiles in two uneven columns below.
- **dock** window 1 in the middle, window 2 as a narrow sidebar on the left, the rest stacked on the right.
- **mosaic** staggered brick rows with uneven widths.

Nothing overlaps. `Mod+h` / `Mod+l` change the main window size in every layout.

## Dock, widgets, login screen

- Dock: touch the bottom screen edge. Click = open or focus, middle = new window, right = pin/unpin. Options in `Mod+n` > Style.
- Shell dock (Quickshell): slides up from the bottom edge; a dot under every open app (a line under the focused one);
  clicking an open app slides to its tag and focuses it; right click > Close asks the app to close.
- Hover a tag dot on the bar: a card under it lists the apps on that tag (or "Empty"). Needs the newest glidewm.
- Wallpapers: source `mono` (black and white, muted, ink on black) is the default; `s` in the theme switcher cycles sources.
- Login screen: `rice-sddm --preview` to look, `rice-sddm` to install (asks password once), `rice-sddm --revert` to undo.

## Two monitors

The bar looks the same on both: the volume icon, clock and avatar show on each. The systray lives on one bar and is
mirrored on the other (a click on a mirrored icon works, left and right). New windows and workspace keys act on
the monitor under the cursor.

## Look and feel

Menus open right under the bar: a blank glass shape grows out of the bar (wide first, then downward), then the contents fade in. Closing fades the contents out and folds the shape back up. The volume and avatar menus keep their place under the icon you clicked. Colours come from
the wallpaper (OKLab extraction: the accent follows the picture, muted pictures give muted accents). The login screen
uses the wallpaper, heavily blurred. New terminals open at their final size and fade in; neighbours glide.

## Tools (`Mod+Shift+o`)

Search, Convert (images, video, audio, archives), Download (cobalt API at `https://cobalt-api.petke.org/`),
Clipboard, Record, Screenshot, Colour picker, QR code, Themes, Settings, Media, Volume.

## Settings (`Mod+o`)

Appearance (glass mode, solid scheme, animations, terminal opacity, blur, shadows, fading), Wallpapers (online mode,
source, storage), Sound (volume, devices, media card auto-close), Display (resolution, refresh, orientation,
brightness, night light, screen-off timer), Keyboard & Mouse (layout, Caps Lock, repeat, acceleration, speed),
Windows & Bar (gaps), Network (interfaces, DNS, MTU, DHCP renew, ping/DNS tests), Shortcuts, About.

Only values you change are saved (`~/.cache/rice/settings.json`) and applied at login by `rice-apply`.

## Glass mode

On: translucent, blurred menus tinted by the wallpaper. Off: solid menus, near black (near white for bright
wallpapers; override with Solid scheme).

## Install and update

```
cd ~/dwm && ./install.sh --check          # what is there, what is missing (packages for your distro), init system
cd ~/dwm && ./install.sh                  # arrow-key picker: glidewm, Rice, Shell, Login session, App menu entries
cd ~/dwm && make && sudo make install     # only glidewm: builds ./glidewm, installs /usr/local/bin/glidewm
```

- Renamed mwm → glidewm (Motif already ships an `mwm`); logo in `logo/`. The binary is `glidewm` now, and the login entry is "glidewm" (runs `/usr/local/bin/glidewm-session`). Log out and pick "glidewm" once;
  after that `sudo rm /usr/local/bin/dwm` (the old build under the dwm name). `Mod+Shift+Ctrl+q` restarts into a new build.
- Picker: Up/Down move, Space or Enter toggles, Enter on Submit installs, Esc quits. Parts that need each other switch
  together (Shell and App entries need Rice, Login session needs glidewm). `--only=rice,shell` skips the picker.
- The installer prints only warnings and errors (`--verbose` for everything). A part whose programs are missing starts
  unselected; choosing it anyway (picker, `--only`) is an error naming the install command.
- Shell updates: Shell Settings > Update Center pulls glidewm and the newest DarkShadow's Shell, rebuilds it for X11 and
  rolls back if a patch no longer fits.
- Python helpers need no install: they are used as soon as they are saved.

## When something breaks

- Colours, blur or the terminal look wrong: run `rice-themecheck` (`--fix` repairs it). It also runs by itself after every theme change and at login, and notifies you only when it cannot fix something. Log: `~/.cache/rice/themecheck.log`.

- `~/.cache/rice/crash.log`: tracebacks and hard crashes of every rice script. Look here first.
- `~/.cache/rice/media.log`: every media key that reached `rice-media`.
- A menu looks wrong or leaves a see-through ghost: check `~/.config/picom/rice.conf` (rules `RiceCard`, `RicePanel`, `RiceGhost`: no animations, `fade = false`) and reload picom with `SIGUSR1`. Menus sit under the bar by `BAR_BOTTOM` + `BAR_GAP` in `~/.local/lib/rice/rice.py`; change them if the bar height changes.
- Animations off: Settings > Appearance > Animations (menus then just appear).
- The tray lands on the wrong monitor: set `systraypinning` in `config.h` (1 = first monitor, 2 = second) and rebuild.
- `rice-supervise` restarts `dwm-status`, `clip-daemon` and `polkit-agent` if they die.
- Reset all keybinds: Settings > Shortcuts > Reset (or delete `~/.config/rice/binds.conf`).
- Backups of edited files sit next to them as `*.pre-*` / `.v1` / `.v2`.
- `Mod+z` shows "no data from dwm": the running dwm is older than the map commands. `sudo make install`, then `Mod+Shift+q`.
- OCR ("Copy text" in the screenshot editor) says "tesseract missing" or finds nothing: tesseract is installed, but its leptonica cannot read PNG, so `rice-shot` feeds it PPM. Language data lives in `~/.local/share/rice/tessdata` (eng, deu, fra, spa, hun, rus); add a `.traineddata` file there to add a language.
- The folder chooser is the standard GTK dialog (`rice-folder`, dark Adwaita); it asks for its own window size on first run only.

- Wallpaper lists (theme switcher, picker, Shell Settings) skip screenshots, small or tall pictures and duplicates (the
  best quality copy stays). List the duplicates: `python3 ~/.local/lib/rice/wallcheck.py --dupes ~/Pictures/wallpapers`.
- A Shell Settings option does nothing: options that only work on Hyprland or niri are hidden by
  `~/.local/share/dss/patches/hide-dead.py` (run by `port.sh`); add the row there.
- Fonts follow the theme mood: grey/B&W themes use IBM Plex (serious), loud warm ones Fredoka/Space Mono (playful), cool saturated ones Space Grotesk. Applies to cards, dock, desktop widgets, rofi, Konsole, Qt. Bar font stays JetBrains Mono.
- Design styles: `Mod+n` > Style > Design picks Wallpaper / Material 3 / macOS / Brutal (colours, fonts, dock look).
- Right-click any desktop widget: font, design, accent, glass opacity per widget. Bar: Mod+n > Style > Bar (workspace marks, title, layout label; needs sudo make install).

## Notes from 2026-11-24 (later)
- The corner action panel (hot corner) is gone. To get it back, uncomment `rice-supervise rice-hotcorner &` in `~/.xprofile` and set `"enabled": true` in `~/.config/rice/hotcorner.json`.
- Windows lost their drop shadow and the blur is lighter (`~/.config/picom/rice.conf`, original in `rice.conf.pre-lag`): that removed most of the tag-switch and menu stutter.
- Widgets hide while windows are open on their own monitor (per monitor now) and are hidden through the compositor, so switching tags does not redraw them.
- The launcher is solid (no see-through), hovering does not change the selection, terminal apps (btop, vim) open in Konsole. Esc and typing in menus need the newest dwm (`sudo make install`, then `Mod+Ctrl+Shift+q`).
- NVIDIA clocks: for smoother compositing run `nvidia-settings -a "[gpu:0]/GPUPowerMizerMode=1"` (uses more idle power; add it to `~/.xprofile` to keep it).

## Notes from 2026-11-25
- Shell Settings: dead pages and options are gone (bar, island, Hyprland window options, input, keybinds, monitors, idle,
  gaming mode, Light mode, blur toggles, night light, Minimal mode). Desktop > glidewm opens the glidewm settings app and tools.
- The shell's screenshot, record and lock buttons run `rice-shot`, `rice-record`, `rice-lock`.
- Picking a wallpaper in the shell themes the whole desktop (it used to do nothing: no awww or matugen here).
- Auto-hide widgets off now really keeps them visible.
- Settings scrolls evenly (synced to the screen).

## 2026-11-25 (evening)
- Restart keeps windows on their monitor and tag (preserveonrestart, by hand). Needs `./install.sh --only=build,session` and a glidewm login.
- README: Patches table and credits, three new screenshots between sections (clock + visualiser, fastfetch + cava terminals, dock + music).
- Fastfetch logo gallery v2: softer portraits, ASCII for every portrait, 10 new logos (8 portraits, glidewm, Tux), 23 in all.
- New minimal logo in the dwm style (`logo/make.py`); repo renamed to github.com/petkebtw/glidewm.

## 2026-11-25 (late)
- Shell update to V6.10 works again (the System menu had gained a page, the X11 patch did not apply).
- Clock style Stacked, Shape and Analog stick (the shell's own tool refused them and fell back to Expressive).
- Settings scrolls like a website: about 100 px a wheel notch, a soft glide, never more than most of a screen ahead.
- Dock: not empty any more, icons in their own colours, panel tinted with the wallpaper colour, slides in, running-app
  dots, click goes to the app's tag. Music card shows a note when the player sends no cover (Mullvad Browser never does).
- Tag hover card (see Dock, widgets). dwm part needs `sudo make install` and a restart:
  `sudo make install && sudo ln -sf /usr/local/bin/glidewm /usr/local/bin/mwm`, then `Mod+Ctrl+Shift+q`.
- Open: the tag slide after a dock click is laggier than after a key (dwm runs it the same; needs a live measurement);
  a source for real cover art from Mullvad Browser.

## 2026-11-26

- Memory: helper scripts of the desktop shell (rice-busy, rice-wm-watch, rice-cava with its cava) no longer stay
  running after a shell restart or update. The shell starts with a leaner memory allocator setting. Details in
  `handoff-dss.md` "Memory".
- Memory at login (goal: under 1 GiB): the session daemons run without transparent huge pages (`nothp`), and
  clip-daemon, polkit-agent (same password window) and rice-toplevels are small C programs now (`rice/lean`).
  The root part (kernel reserves, Xorg, and a runit fix: `/etc/sysctl.d` was never applied) is
  `sudo rice/memory/apply-root.sh`. Result: 781 MiB in fastfetch after login (was 1.42 GiB; ~20 MB of that came from
  a render-loop test left on by mistake, reverted). Later: more helpers in C (rice-busy, rice-wm-watch,
  rice-widget-fade, rice-cava, dwm-status, rice-supervise) and two fewer shell windows (~15-20 MB).
