# Handoff: DarkShadow's Shell on dwm (2026-11-24)

Short brief for the next session. Detail lives in `docs/rice-scripts.md` (bottom sections) and the `*.pre-*` backups.

## What the user wanted
A copy of https://github.com/shadowww-dev/DarkShadowShell (Hyprland + Quickshell, QML) on this dwm/X11 box. Earlier in the session I built Python look-alikes (island, game bar, wallpaper picker, welcome, notifications, design-language shapes). The user said "just copy this", so the real QML now runs and the Python island/dock/desk are retired.

## State right now (live session)
- Quickshell 0.3.1 built X11-only (`docs/install-quickshell.sh`; USE `-wayland -hyprland -layer-shell ...`, guru overlay, `~amd64`). `qs` is `/usr/bin/qs`.
- The shell runs from `~/.config/quickshell/rice-desktop` via `~/.local/share/dss/dss-start` (started from `~/.xprofile`, backup `~/.xprofile.pre-dss`).
- Live and checked on screen: desktop widgets (clock, focus timer, user card, CPU/RAM/GPU gauges, music card), control centre (`rice-cc`), notifications (shell owns them, `rice-cc engine shell`), widgets auto-hide while the viewed tag has a window.
- Turned off at the user's request: the QML bottom bar (`rice-bar set enabled off`, `~/.config/rice/bar.json`) and the visualizer widget. The dwm text bar at the top is still there (tray lives in it).
- Retired (processes stopped, autostart lines removed): `rice-island`, `rice-dock`, `rice-desk` (Python, still in `~/.local/bin` and `~/.local/lib/rice`). `rice-hotcorner` (Python) still autostarts.

## How the port works
- Pristine reference: `~/.local/share/dss/src` (QML) and `~/.local/share/dss/bin-src` (helper scripts). `~/.local/share/dss/port.sh` rebuilds `~/.config/quickshell` and `~/.local/share/dss/bin` from them. Re-run it after any edit, then restart the shell (`kill` the `qs` pid; `dss-start` again, `setsid`).
- port.sh transforms: deletes `WlrLayershell.layer/namespace/keyboardFocus` lines; maps `WlrLayer.Bottom/Background` to `aboveWindows: false` (`editing ? Top : Bottom` becomes `aboveWindows: editing`); installs `Wm.dwm.qml` as `rice-desktop/Wm.qml`; rewrites every `.local/bin` path in QML, `.sh`, `.js` and the helper scripts to `.local/share/dss/bin`, so nothing in `~/.local/bin` is shadowed (10 names clash: rice-gamebar, rice-hotcorner, rice-lock, rice-lyrics, rice-media, rice-power, rice-sddm, rice-settings, rice-volume, rice-welcome).
- Our own helpers live in `~/.local/share/dss/ours/` (copied into `bin/` by port.sh): `rice-wm-watch` (JSON lines from dwm's `_RICE_TAGS` + active window), `ws-go` (`xdotool key alt+N`), `rice-busy` (1 when the viewed tag has windows).
- Shim QML modules `Quickshell.Wayland` (empty `ToplevelManager`) and `Quickshell.Hyprland` in `~/.local/share/dss/qml`; `dss-start` sets `QML_IMPORT_PATH` and `PATH`.
- Reference settings were copied with `cp -n` into `~/.config/rice/` and `~/.config/waybar/ui.json`. Widgets are driven with `~/.local/share/dss/bin/desktop-set widget NAME on|off`, `clock style digital|line|cookie|pixel`, `dock KEY on|off`.

## dwm changes (installed, running)
- `drawbar()` publishes `_RICE_TAGS` = {viewed mask, occupied mask, urgent mask, monitor} on the root window.
- `isshellwin()` in `maprequest()` maps windows of type `_NET_WM_WINDOW_TYPE_DOCK` or `_KDE_NET_WM_WINDOW_TYPE_OVERRIDE` without managing them. Without it Quickshell panels get tiled.
- Backups `dwm.c.pre-tags`, `dwm.c.pre-dockpass`. Any dwm change needs `sudo make install` then `Mod+Ctrl+Shift+q` (an exec restart keeps the pid, so `ps` start time does not change).

## picom
- `~/.config/picom/rice.conf` got rules for `name = 'quickshell'` (no blur, shadow or rounding: blur turned every transparent widget window into a block) and for the design-language classes (`RiceCardM3/Mac/Br`, `RicePanel*`, `RiceGhost*`, `RiceDock*`, `RiceDeskGlass*`) plus `RiceIsland`. Reload: `kill -USR1 <main picom pid>` (`ps -o pid,ppid,args -C picom`). Validate a copy on Xvfb first: `DISPLAY=:7 timeout 3 picom --config COPY --backend glx` (rc 124 = parsed).

## Keybinds (dwm runtime file `~/.config/rice/binds.conf`, backup `.pre-dss`; Mod = Alt)
`Mod+p` launcher, `Mod+n` control centre, `Mod+e` widget edit, `Mod+g` game bar, `Mod+w` wallpaper picker, `Mod+v` clipboard, `Mod+slash` cheat sheet, `Mod+Shift+n` dashboard. binds.conf replaces the compiled `keys[]`; reload with `xprop -root -f _RICE_CMD 32c -set _RICE_CMD "5, 0"`. None of these keys were pressed by me; I called the scripts directly.

## Not verified / open
- Dock (`desktop-set dock enabled on`, apps konsole/firefox/dolphin/steam) is enabled but was never seen; its open-apps list needs `ToplevelManager`, which does not exist on X11 (a window list from `_NET_CLIENT_LIST` would have to be added to the shim).
- QML Settings, Welcome, apps, wallpaper picker, game bar, clipboard, task view, snip: not opened. The QML lock screen needs `WlSessionLock` (Wayland): keep `~/.local/bin/rice-lock`.
- PipeWire in Quickshell logs "Failed to connect pipewire context. Errno: 112"; volume widgets that use the Quickshell Pipewire module may be dead. Volume keys still use the user's `dwm-volume`.
- Lag: idle CPU 0 %, control centre animation about 83 fps, memory 415 MB after removing bar and visualizer. The user still felt lag earlier; unknown where. The shell keeps one fullscreen transparent window and one 1920x514 widget window. Next step if needed: reference lite mode (`~/.config/rice/effects.json` `"lite": true`).
- Widget auto-hide only looks at the viewed tag of the selected monitor.
- Two monitors untested with the QML shell (HDMI-0 above DP-4).
- Real blur behind widgets is gone (picom rule); a fix would need a per-window shape.

## Rollback
Restore `~/.xprofile.pre-dss` and `~/.config/rice/binds.conf.pre-dss`, delete `~/.local/share/dbus-1/services/org.knopwob.dunst.service` (it makes D-Bus start `dss-start` for notifications), `kill` the `qs` pid, `rice-cc engine swaync` if swaync is wanted back, then start the old Python helpers via `rice-supervise rice-island|rice-dock|rice-desk`.

## Gotchas learned
- Never `kill $(cat ~/.cache/rice/dock-0.pid)` to test: SIGTERM ends `rice-supervise` (stops the live dock). Use `kill -9` on the child if a restart is wanted. Same for any supervised helper.
- `pkill -f` is banned here (kills the calling shell). The auto-mode classifier also blocks running `themes.apply` against the live session.
- Xvfb tests: use a fake `HOME` (symlink `.config/quickshell`, `.local/lib`), set `DISPLAY=:7` on every command, run `./dwm` on `:7` too; picom on Xvfb dims windows without a focused client.
- Python rice scripts still present and working (settings, lock, power, search, shot, record, volume ...); the earlier Python polish (spam-safe launchers via `once-*.lock`, design-language geometry `designs.GEO`, Material 3 settings cards, `rice-gamebar`, `rice-wall`, `rice-welcome`) stays in `~/.local/bin` and `~/.local/lib/rice` and is documented in `docs/rice-scripts.md`.

## Session 2026-11-24 (later): performance, menus, keyboard, icons

State at the end of the session. Everything is regenerated by `~/.local/share/dss/port.sh` (it patches the QML after copying `src/`), so edit port.sh, not `~/.config/quickshell`.

### dwm.c changes (backups `dwm.c.pre-monbusy`, `.pre-shellfocus`, `.pre-noslide`, `.pre-shapefocus`)
- `publishmons()` (called from `drawbar()`): root property `_RICE_MONS` = per monitor {x, y, viewed mask, occupied mask}. `ours/rice-busy NAME` and `ours/rice-widget-fade` read it. `_RICE_TAGS` is unchanged (selected monitor only).
- `maprequest()`: shell windows (`isshellwin()`) are mapped unmanaged; a window with `_NET_WM_STATE_BELOW` is lowered on every map. `scan()` no longer manages already-mapped shell windows after a dwm restart.
- Keyboard for shell menus: Qt on X11 never asks for the keyboard (no `_NET_ACTIVE_WINDOW`), so nothing got Esc or typing. `shellcheck()` + ShapeNotify: an unmanaged ABOVE quickshell window whose bounding shape is at least 300x300 gets `XSetInputFocus` (`shellfocus`); when the shape goes away focus returns to the client (`focus(NULL)`). The shell masks a menu to its card while open and to nothing while closed (see `wmShown` below), which drives this. `focusin()` ignores `shellfocus`. A `_NET_ACTIVE_WINDOW` client message from a shell window is also honoured, but Qt never sends one.
- `noslide()`: if `~/.config/rice/noslide` exists, tag switches snap instead of sliding. The file does not exist (the user wants the slide).
- A dwm change is live only after `sudo make install` and a restart of the running binary. Check `stat -L -c %i /proc/$(pgrep -x dwm)/exe /usr/local/bin/dwm`: equal inodes mean the new binary runs. Last state seen: the shapecheck build (18:39) was built, not yet confirmed installed. Verify with `xdotool getwindowfocus` while `rice-launch` has the launcher open (it must not stay on the Konsole window id).

### port.sh patches (all in `~/.local/share/dss/port.sh`, backup `port.sh.pre-mask`)
- `WidgetWindow.qml`: mask a static `maskBox` (the animated holder froze the X shape small and cut the gauges); `aboveWindows: false` (Quickshell read `aboveWindows: editing` once at creation, so widgets came up ABOVE and drew over windows); `visible: active` (windows stay mapped); fade disabled; `shell.qml` `hideWidgets: false`.
- Menus (ControlCenter, Launcher, ClipboardPanel, GamePanel, WallPicker, Cheatsheet, Wifi/Bluetooth/Volume/PowerMenu, TaskView): `visible: wmShown || wmWarm`, mask `wmShown ? full : none`, kept mapped 60 s after closing. Reason: Qt hiding a fullscreen GL window cost X 73-93 % CPU on every close. Trade-off: an invisible fullscreen window stays above everything for up to 60 s and may stop picom unredirecting a fullscreen game right after menu use.
- Images: `AppIcon`, `Bar`, `RoundImage`, `ShapeImage` load synchronously (`asynchronous: true` never left Loading, all icons blank).
- `iconfile.sh`: SVG icons are rendered once to PNG with `rsvg-convert` into `~/.cache/rice/svgicons` (Qt shows CSS-styled SVGs such as Dolphin and Konsole blank); an empty icon file is no icon. `Icons.qml`: a 2.5 s timer re-queues names that were asked but never resolved (a theme change during start wiped `pending`).
- `Launcher.qml`: `Terminal=true` entries (btop, vim) run as `konsole -e` (Quickshell `execute()` ignores `runInTerminal`). `LauncherM3.qml` (edited in `src/`, backup `~/.local/share/dss/LauncherM3.qml.pre-hover`): hovering no longer moves the selection, only typing, arrows and clicks.

### Helpers in `~/.local/share/dss/ours/` (copied to `bin/`)
- `rice-busy NAME`: per-screen "windows on the viewed tags" (reads `_RICE_MONS`); the shell uses it only to pause decorative widget motion (`Look.covered`).
- `rice-widget-fade`: started 6 s after `qs` by `dss-start`, flock'd (`$XDG_RUNTIME_DIR/rice-widget-fade.lock`). Hides widgets by setting `_NET_WM_WINDOW_OPACITY` 0 on the BELOW widget windows of every monitor that has windows on its viewed tags, so picom hides them and nothing re-renders. Changing a dozen GL windows at once (opacity in QML, unmap, move) stalled X for about 150 ms per tag switch. Exits when `qs` is gone. Its `xprop -spy` is started with `9>&-` (it used to leak and hold the lock).
- `rice-edit` (Mod+e): widgets sit under windows, so it first views the first empty tag of the widget monitor, then toggles edit mode.

### Config and keys
- `~/.config/rice/binds.conf` (backup `.pre-menus`): `Mod+o` and `Mod+Shift+o` = QML `rice-settings`, `Mod+Shift+t` = `rice-settings 8` (Theme), `Mod+s` = `rice-launch`, `Mod+e` = `rice-edit`. Still Python: `Mod+z` map, `Mod+Shift+l` lock, `Mod+Shift+r` record, `Mod+Shift+m` media, screenshots.
- picom `~/.config/picom/rice.conf` (original `rice.conf.pre-lag`): `blur-strength = 2`, global `shadow = false`. Blur and shadow on moving windows were the largest compositing cost.
- Hot corner removed: `rice-supervise rice-hotcorner` commented out in `~/.xprofile` (backup `.xprofile.pre-corner`), `hotcorner.json` `"enabled": false`.
- `~/.config/rice/rofi.json` (backup `.pre-opaque`): launcher `"transparency": false` (it blended windows behind it into the panel).
- `~/.local/share/applications/start-mullvad-browser.desktop`: its `Exec=sh -c '...' dummy %k` uses single quotes, which the desktop-entry spec (and Quickshell) do not parse. Replaced by `Exec="/home/petke/Downloads/mullvad-browser/Browser/start-mullvad-browser" %u`. Re-running `--register-app` rewrites it.
- NVIDIA sat in P5 (555-1500 MHz of 3090) during switches. `nvidia-settings -a "[gpu:0]/GPUPowerMizerMode=1"` was set for the running session only; the `.xprofile` edit was denied, so it is not persistent.
- `dss-start` exports `__GL_SYNC_TO_VBLANK=0 __GL_YIELD=USLEEP` (backup `dss-start.pre-gl`): no measurable effect, and every app started from the launcher inherits it. Remove it if it causes tearing.

### How lag was measured (repeat this, do not guess)
- Frame cadence: `ffmpeg -f x11grab -framerate 60 -video_size 1920x1080 -i :0.0+0,1080 -t 4 x.mkv` during `xprop -root -f _RICE_CMD 32c -set _RICE_CMD "1,0,1080"` (view the first empty tag) and `ws-go 1`; then `ffmpeg -i x.mkv -vf "mpdecimate=hi=200:lo=100:frac=0.1,showinfo" -f null -` and count `pts_time` per 0.25 s (15 = full rate).
- CPU: `top -b -d 0.2 -o %CPU` during the action, look at `X` and `qs`. With the shell off X stays under 12 % in a switch.
- Results: tag switch to the empty desktop 4-7 frames per bucket before, 9-15 after the picom change; widget hide stall X 70 %/qs 55 % before, X 27 %/qs idle after `rice-widget-fade`; menu close X 73-93 % before, 5-39 % after.
- `perf record -p <qs pid>` works (the hot spot was a spin in `libnvidia-glcore`); `perf` on the X server is not permitted.

### Open
- Rapid toggling (8 times in 0.7 s) of clipboard, game bar, wallpaper picker and power menu still spikes X to about 93 % and qs to 60-73 %: the panels' own open animation.
- Keyboard focus for shell menus (above) is built but unconfirmed live. Panels without a mask (Snip, EditPanel, DeskMenu) get no keys.
- Menus in the original repo's design (the Python menus were replaced by the QML ones where they exist); the user can describe the design if more are wanted.
- Aonsoku has a 0-byte icon (default icon now). The dock's open-apps list still needs a window list on the `ToplevelManager` shim.
- `PulseAudioService: Connection refused` repeats in `~/.cache/rice/desktop.log` (PipeWire stale; `audio-fix`).
- `rice-busy` and `rice-wm-watch` leave their `xprop -spy` child behind (ppid 1) when `qs` is killed; kill strays by hand.
- The widgets' decorative motion still redraws the idle desktop about 29 times a second; `touch ~/.cache/rice/lite` cuts that to about 8 (Look.lite, also pauses the visualizer).

## Updates (2026-11-25)

- `ours/rice-update` replaces the upstream updater (which wanted `~/shadows-shell` + its Hyprland `install.sh`).
  One update: `git pull --ff-only` of the mwm repo, `rice/install.sh` (new links only), then DarkShadow's Shell:
  private clone in `~/.local/share/dss/upstream`, its `quickshell/ bin/ sounds/` copied to `src/ bin-src/ sounds/`,
  then `port.sh`. If `port.sh` fails on the new version, the old `src/` etc. are put back and rebuilt.
- Shell commit in use: `~/.local/share/dss/upstream.rev` (seed in the repo: `rice/shell/dss/UPSTREAM`).
- Only the desktop `qs` (cmdline has `~/.config/quickshell/rice-desktop`) is restarted; Settings stays open.
- Local edits to the shell must be `port.sh` patches: `src/` is replaced on every shell update. The LauncherM3
  hover change moved into `port.sh` for this reason. `ours/` must hold files only (`port.sh` copies plain files).
- `port.sh` builds in `~/.config/quickshell.build` and swaps it in at the end. Rebuilding in place crashed a running
  Settings: qs live-reloads and saw an unpatched `WlrLayershell` line ("Non-existent attached object").
- V5.06 Settings calls `rice-update whatsnew` / `whatsnew-seen`; ours implements them (CHANGELOG from the upstream
  clone). Unknown subcommands exit 2. They used to fall through to a full update, which caused that crash.
- Our tools take over shell actions: `ours/rice-hotcorner` sends `shot *` to `~/.local/bin/rice-shot` and
  `record full|region` to `rice-record` (`record stop` kills ours if it runs); `ours/rice-lock` sends `now|test` to our
  X11 lock. `port.sh` renames the shell's scripts to `rice-hotcorner.dss` / `rice-lock.dss`; all other commands go there.
  The control centre's Record tile does not show our recording state (it reads `record.json`, ours writes `record.pid`).
- Settings on mwm (port.sh block before the swap): wmLabel "mwm"; pages 2 3 5 6 11 23 28 30 33 36 (QML bar, bar
  layout, recorder, island, idle/lock, keyboard, monitors, keybinds, infinite desktop, window rules) have no PageSlot
  and are out of the nav; `gone` redirects links to them to page 4. Page 4 is `patches/MwmPage.qml`: buttons open
  `~/.local/bin/rice-settings display|input|windows|keys|net|sound` and the tools (rice-shot, rice-record, rice-lock,
  theme-switch, rice-map, rice-themecheck --fix). About credits mwm + dwm. `ours/rice-wm` answers label/version as mwm.
- Dead Settings rows are hidden by `patches/hide-dead.py` (run from port.sh): rows whose block calls hypr-set
  (`ctl.hset/hv/ha/setAnim`), rice-minimal, rice-effects lite/gaming, night light, plus an explicit list (Light mode,
  blur toggles, Hyprland input, gaming-mode keeps, power mode without power-profiles-daemon, Minimal mode, Hyprland
  borders/shadows/animations). `--report` lists what it hides. Its pattern misses print to stderr.
- Wallpapers picked in the shell: port.sh makes `hyprquickpaper/commands.sh` exec `themes.apply(themes.item_for(img))`
  (feh + the mwm theme pipeline); awww and matugen are not installed, so before nothing changed.
- Scrolling: `ours/qs` sets `__GL_SYNC_TO_VBLANK=1` for everything but rice-desktop (Settings inherited 0 from
  dss-start and its frames came unevenly); WheelScroll glide time constant 0.09 s -> 0.14 s.
- rice-widget-fade reads "autoHide" from ~/.config/rice/desktop.json (Settings > Auto-hide widgets); off = never hides.
- Wallpaper lists skip non-wallpapers: `~/.local/lib/rice/wallcheck.py` (>= 1600x900, aspect 1.25-2.7, not screenshot-named or in a Screenshots dir; sizes cached in ~/.cache/rice/wallcheck.json). Used by themes.items() and, via port.sh, by rice-walls all_files().
  Duplicates too: `wallcheck.dedupe()` (256-bit dHash <= 24 bits, 4x4 colour grid <= 14, contrast-stretched 16x16 grey: <= 1 cell differs by > 24); keeps the current, else the biggest, else not under online/. `python3 wallcheck.py --dupes DIR` lists them.

## Lag measurements (2026-11-25, evening)
- Menus (cc, launcher, clipboard, game bar, power) and the tag slide: 15-20 new frames per 0.25 s (60-80 fps) on the
  165 Hz DP-4; qs CPU under 25 %, X up to 83 % on cc close. Tools: scratchpad `meas.sh` (x11grab + mpdecimate + top).
- Cause 1: GL clients sync to HDMI-0 (75 Hz) unless `__GL_SYNC_DISPLAY_DEVICE=DP-4`; now exported in `~/.xprofile`
  (backup `.xprofile.pre-glsync`). Live after the next login.
- Cause 2 (fixed): picom `vsync = true` = 2 vblanks per frame (sgi_video_sync pacing + vsynced swap). `vsync = false`
  in `~/.config/picom/rice.conf` (backup `.pre-novsync`) gives 6 ms frames (165 fps); default scheduler is already
  sgi_video_sync, forcing `present` is worse. After it: cc open 31/20 frames per 0.25 s, launcher 23. Watch for tearing.
- Cause 3 (fixed): desktop qs ran `__GL_SYNC_TO_VBLANK=0`. With `=1` + DP-4 sync every menu (cc, launcher, clipboard,
  game bar) opens and closes at 41 frames per 0.25 s = 165 fps. `dss-start` (backup `.pre-vsync1`) and `ours/qs` now
  export `__GL_SYNC_TO_VBLANK=1`; the DP-4 device comes from `~/.xprofile`. Repo copies in `rice/shell/` updated.
- Cause 4 (fixed, live in mwm since the 2026-11-25 re-login): dwm's slide stepped every 8 ms (`run()` select timeout) = 125 fps max, tag slide
  measured 31 frames per 0.25 s. Now 5 ms (`dwm.c.pre-165`), `config.h` refreshrate 120 -> 165 (drag/resize).
  After: slide 36-38 frames per 0.25 s; menus still 41 after the re-login (env from `~/.xprofile` reaches qs).
- rice-media waited up to 1.6 s for lyrics of a new song before opening; now 0.4 s (fetch continues and caches).

## Rename (2026-11-25)
- mwm is now glidewm (Motif ships an `mwm`). `patches/MwmPage.qml` is `patches/GlidewmPage.qml`; `rice-wm` answers glidewm and parses `glidewm-`/`mwm-`/`dwm-` versions; `rice-update` looks for clones in `~/glidewm`, `~/mwm`, `~/dwm`. GitHub URL unchanged (`petkebtw/mwm`). Older entries above say mwm.

## Fixes (2026-11-25, late)
- Update to V6.10 failed: port.sh matched the System nav list exactly; V6.00 added page 41 (Care). Now it drops the gone pages from whatever the list is (`port.sh.pre-v610`). V6.10 builds and loads in Xvfb with every patch (scratch HOME).
- Clock style Stacked/Shape/Analog fell back to Expressive: upstream `desktop-set` CHOICES only allowed digital|line|cookie|pixel, so `desktop-set clock style stacked` exited 1 and Settings re-read the old value. port.sh makes CHOICES use `STYLES["clock"]` (still broken upstream in V6.10).
- Settings wheel: about 100 px a notch at the default speed (was 216), spring omega 13 -> 9.5, goal capped 0.8 screen ahead of the glide (`patches/WheelScroll.qml`).
- Dock looked grey: icons were 62% recoloured toward the pale accent (`shade: true`, "Match the wallpaper"); set `desktop-set dock shade off` (backup `~/.config/rice/desktop.json.pre-dockcolor`). port.sh now gives the dock panel NPal theme "tinted" instead of "shell" (theme bg #0c1218 at opacity 0.36 read as flat grey over blur); backup `port.sh.pre-docktint`.
- Dock running dots + click-to-go: `Quickshell.Wayland.ToplevelManager` was an empty stub. Now `dss/qml/.../ToplevelManager.qml` is filled by `ours/rice-toplevels` (xprop -spy on _NET_CLIENT_LIST/_NET_ACTIVE_WINDOW, JSON lines, PDEATHSIG so no orphan xprop). `activate()` = dwm IPC `9,win` (views its tag with the slide, focuses); `close()` = WM_DELETE_WINDOW via ctypes (`rice-toplevels close ID`). Tested in Xvfb: click on a running app's icon moved view 4 -> 1 and focused it. TaskView also gets the list (its ScreencopyView is Wayland-only, caught by its try). Backup of the stub: `ToplevelManager.qml.pre-x11`.
- Dock popped up without its slide: its window was mapped on every reveal (NVIDIA's first frame ate the 260 ms). port.sh keeps it mapped; hidden it has an empty input mask (Region noInput). Xvfb: pointer passes through while hidden, strip reveals, dock takes input. Backup port.sh.pre-dockmap.
- Dock was an empty bar: the Grid add transition (opacity 0->1) left all parts at opacity 0. port.sh removes it (Xvfb: empty with, full without). Backup port.sh.pre-dockadd.
- Dock music art: no mpris:artUrl (Mullvad/SoundCloud) left an empty square; port.sh puts a music-note glyph there. ToplevelManager now reassigns toplevels only when the window set changes (focus changes rebuilt the dock row twice per tag switch). Backup port.sh.pre-musicart.
- Tag hover card (TagPeek): dwm's bars select PointerMotion/LeaveWindow; `taghover()` writes root `_RICE_HOVER` = {tag 1-9, tag middle x, bar bottom y, monitor, window ids on that tag} or {0}. `rice-toplevels` spies it too ({"hover": [...]}), `ToplevelManager.hover` holds it, `patches/TagPeek.qml` (port.sh adds `TagPeek { }` to shell.qml) shows a 260 px card under the tag: app icons + titles or "Empty", 140 ms delay, fade. Window always mapped, empty mask, < 300 px wide (shellcheck never focuses it). Xvfb-tested. Needs the new dwm (`sudo make install`).
- run(): animstep() now also runs when >= 6 ms passed even while events keep coming (pointer motion over the bar would starve it). Dock-click vs key tag slide in Xvfb: 82 vs 81 steps over 425 ms, same events: the live dock-click lag is not dwm's event loop. Not measured live yet.
- Cover art: Mullvad Browser sends no mpris:artUrl. SoundCloud's unofficial api-v2 (scraped client_id) was refused by the permission check; open: user choice of source.

## Memory (2026-11-26)

- Boot use ~1.4 GiB with only konsole open: qs rice-desktop ~400 MB fresh (grew to 670 MB over a session), Xorg 210 MB,
  picom 110 MB, kernel/NVIDIA ~300 MB, konsole 90 MB, daemons ~200 MB. dwm itself 12 MB.
- Orphan fix: rice-busy, rice-wm-watch (ours/, watchdog line after the header: exits with its parent qs, kills its
  xprop -spy) and rice-cava (port.sh perl patch after the ours/ copy: `kill -0 "$PPID"` in its wait loop) outlived
  every qs restart; a silent cava never notices the dead pipe, and with music it re-spawned every second.
  Verified: after `rice-desktop restart` every helper of the old instance is gone within 3 s. Backups `*.pre-orphan`.
- ours/qs exports `MALLOC_ARENA_MAX=2 MALLOC_TRIM_THRESHOLD_=4194304` (backup `rice/shell/qs.pre-malloc`): no change
  at start (396 vs 397 MB), meant for the growth over a session; not yet measured over hours.
- Not done (would cost looks or smoothness): `QSG_RENDER_LOOP=basic` (11 vsynced windows on one thread), picom xrender.
- Goal set 2026-11-26: under 1 GiB in fastfetch at boot (konsole + fastfetch only), no feature/look loss.
  fastfetch "used" = MemTotal - MemAvailable, which also subtracts kernel reserves (~450 MB here).
  Done, user side (all live and measured):
  - `rice/lean/nothp` (prctl PR_SET_THP_DISABLE, inherited): THP "always" filled heaps with 2 MB pages.
    qs anon 230 -> 113 MB, picom 61 -> 14 MB. ~/.xprofile runs every session daemon through it (backup
    `~/.xprofile.pre-nothp`), ours/qs too. Apps started from glidewm keep THP.
  - C rewrites in `rice/lean` (Makefile; rice/install.sh builds; rice/bin + shell/ours link there):
    clip-daemon 18 -> 0.3 MB (XFixes; image/png as is, other image types converted once by GdkPixbuf;
    INCR, dedupe, prune tested on Xvfb), polkit-agent 18.5 -> 0.5 MB (C listener; the GTK window is
    `rice/bin/polkit-dialog`, started per request; wrong-password and cancel tested live, rc 126;
    the correct-password path is NOT tested), rice-toplevels 6.3 -> 0.2 MB (same JSON, diffed).
  - rice-update watch: sh sleep loop holding the lock, Python only for a due check (8 -> 0.35 MB).
  - rice-ws-watch exits on X11 (port.sh patch; it waited for a Hyprland socket forever).
  Root side, prepared, needs the user: `sudo ~/dwm/rice/memory/apply-root.sh` (`--undo`):
  runit stage 1 never ran `sysctl --system` (swappiness 10 and the game max_map_count were not applied:
  live 100 and 65530); min_free_kbytes 22528 and lowmem_reserve_ratio 32768 2048 32 (~240 MB of reserves);
  Xorg via sddm `[X11] ServerPath=/usr/local/bin/X-nothp`. `rice/memory/diag.sh` (sudo, read-only) shows X's
  heap and slab. Estimate before the root part: ~1.30 GiB at boot; after: ~1.05 GiB (not measured).
  Measured after `apply-root.sh` + reboot (2026-11-26): fastfetch 781.77 MiB at 3 min (was 1.42 GiB). All
  daemons up with THP off (X via X-nothp, qs 91 MB anon, picom 13, pipewire 5, pipewire-pulse 7, clip-daemon
  and polkit-agent under 1 MB). at-spi still starts (Qt activates it, not GTK): ~5 MB, left alone.
- Xorg AutoAddGPU off (apply-root.sh step 4, `/etc/X11/xorg.conf.d/10-glidewm-noautogpu.conf`): Xorg added the
  RTX card again as a modesetting GPU screen 3x per start (glamor GL context each time, drmSetMaster failed).
  Applied by the user, not yet seen at a login.
- Kernel 7.2.9-optimized (2026-11-26; built as -glide first, renamed by request), built in ~/src/linux-glide (clean copy of /usr/src/linux-7.2.9-cachyos-r1),
  config = /boot/config-7.2.9-eclipse + localmodconfig (lsmod + ~/src/lsmod.glide extras) + NR_CPUS 16, no
  MAXSMP/NUMA/debug info/BTF/sched_ext/ftrace/kprobes/kexec/crash dump/KALLSYMS_ALL. Kept: clang ThinLTO,
  native, O3, BORE, BBRv3, MGLRU, PREEMPT, 1000 Hz, hibernation, IA32, NTSYNC. amdgpu stays a module: it is
  what selects ttm/drm_ttm_helper/drm_display_helper/cec, which nvidia-drm's fbdev (TTY console) needs.
  252 modules, bzImage 12.1 MB (eclipse 17.2 MB). NVIDIA 615.78.08 open modules built by hand in
  ~/src/nvidia-glide (from distfiles .run, LLVM=1, signed with the kernel key) so portage keeps eclipse's.
  Install: `sudo rice/memory/install-kernel.sh` (`--remove`, `--grub` = menu only). The boot menu is Void's grub (/mnt/void, `/etc/grub.d/15_gentoo` = "Gentoo Linux (runit)", newest kernel, `rw init=/sbin/runit-init`); Gentoo's own grub.cfg is unused, so the script regenerates Void's via chroot. Newer cachyos-sources (7.2.11, 7.3.0) not taken: no 10%+ gain. Gotcha: an rsync exclude of `vmlinux*` dropped
  vmlinux.lds.S sources (restored from ~/src/restored.txt). Not booted yet.
- 2026-11-26 (later), "10+ MB more", both parts live and tested:
  1. C rewrites in rice/lean (links: shell/ours/rice-{busy,wm-watch,widget-fade,cava}, bin/{dwm-status,rice-supervise};
     bash originals as `*.pre-lean`): same outputs (busy/wm-watch diffed live, fade window selection diffed live and
     its hide/show/autoHide/exit cycle tested on Xvfb with a fake qs, cava config byte-identical + fps restart +
     parent exit, dwm-status format/RTMIN+10/pactl restart, supervise exit codes and crash-loop). Differences:
     rice-wm-watch writes titles as real JSON (bash passed xprop's \" through); rice-widget-fade fades the windows of
     the newest qs running quickshell/rice-desktop (bash: lowest qs pid, a Settings qs if older). port.sh's
     rice-cava perl patch is gone (ours/rice-cava replaces the script). Helpers ~18 -> ~11 MB PSS.
  2. port.sh "fewer shell windows": WallLum and VibeCover in LazyLoaders (exist only while measuring; Look.lumGrid,
     Vibe.tint* keep the result; tested on Xvfb with debug logs and a fake MPRIS player on a private bus), the dock's
     3 px reveal strip is a MouseArea + input mask of the always-mapped dock window (Xvfb: edge -> reveal, away ->
     hide, edge again -> reveal). Render threads 9 -> 7, qs anon 110 -> 103 MB. Live hover not tried (pointer).
  Found and fixed: the rejected QSG_RENDER_LOOP=basic test had stayed in the live dss/bin/qs (not repo/ours) since
  before the 781 MiB reboot; reverted, so that figure is ~20 MB low.

## Tag slide lag (2026-11-26)
- Cause: the hidden dock (always mapped, empty mask) animated its focus dot and icon colours (Behaviors 160-400 ms) on
  the focus change of every tag switch, so qs re-rendered the dock window at 165 Hz under the slide: X 90 %, qs 50-60 %,
  dwm moved windows only every 30-45 ms (9 ConfigureNotify per slide; 25 with qs SIGSTOPped). The visualizer widget
  also painted ~42/s while auto-hide had it at opacity 0.
- Fix (port.sh, backup `port.sh.pre-dockidle`): Dock.qml `live: reveal || t > 0.02`, every row Behavior and AppIcon
  (`anim`) Behavior `enabled` only while live (t/hovK keep animating); VizWidget `paused: root.autoHide && Look.covered`
  skips painting (cava keeps running). Live since 2026-11-26, Xvfb load clean.
- Result (10 switches DP-4, empty tag <-> tag 1, dwm 22-25 moves per slide): unique frames in 300 ms 8.1 -> 18.3, max
  gap ~100 -> 18-42 ms, X max 90 -> 50 %, qs max 60 -> 16 %. Visualizer: 60 paints/s on an empty tag, 0 covered.
- Tools (scratchpad, rebuild if gone): `cw WIN END` logs ConfigureNotify (dwm step cadence), `dmg END WIN...` XDamage
  per window, `ab.sh LABEL` drives 10 switches (`_RICE_CMD 1,0,1080` / `xdotool key alt+1`) and counts unique frames
  from a live `x11grab -copyts` strip at y 1200 (wallclock pts; `-t` breaks with -copyts, use `timeout -s INT`).
- The X server is `X` (not Xorg) for `pgrep`. Left: first 40 ms of a slide still has 1-4 frames (map + texture bind).

## Vibe removed (2026-11-26)
- Why: Vibe "Colors from the cover" (default on) made the accent the playing media's cover colour: a magenta YouTube
  thumbnail in Mullvad turned every widget purple over the blue wallpaper (accent `#98cdfe`).
- port.sh (backup `port.sh.pre-novibe`): Vibe.qml defaults and `apply()` force cover, borders, island, edge, weather,
  lyrics off and `fall: ""` (no Try); Settings > Appearance loses page 42 (Vibe). port.sh writes
  `~/.config/rice/vibe.json` all off (rice-scene beat, lock ring read it). Bar visualizer style keys kept (QML bar is
  unused on dwm). Desktop and Settings load clean on Xvfb; live desktop qs restarted.
