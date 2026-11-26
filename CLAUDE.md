# dwm rice (Gentoo, X11)

Personal dwm 6.8 build on Gentoo. Upstream suckless source with the systray patch applied, plus hand-edited rice features. Uncommitted changes in `dwm.c`, `config.def.h`, `config.mk`, `drw.c`, `drw.h`; `config.h` and `*.o` are untracked. Do not commit unless asked. History per session is in `TODO.txt`, `handoff.md`, `RICE.md` (user-facing summary, update together with this file) and the `*.pre-*` backups.

## Build and install

- Build: `make` (clean with `-Wall -pedantic`). Only `config.h` is built; `config.def.h` is out of sync.
- Name: glidewm (renamed from mwm on 2026-11-25: Motif ships an `mwm`). Logo in `logo/`, dwm style: `make.py` draws the lowercase wordmark on a unit grid (strokes one unit, x-height 5, w and m share a stem) into `glidewm.svg` (black), `glidewm-light.svg` (white; README `<picture>`, GitHub wraps it in `<themed-picture>` so it follows the GitHub theme), `glidewm-icon.svg` + `icon-*.png` (the g on a dark rounded square, installed as the `glidewm` icon). Edit `make.py`, not the SVGs. The first glass logo is gone from the repo. GitHub repo renamed to `petkebtw/glidewm` (remote updated). Binary is `glidewm` (Makefile builds `./glidewm`, `sudo make install` to `/usr/local/bin/glidewm`; login entry `glidewm.desktop` runs `/usr/local/bin/glidewm-session`, made by `./install.sh`). The running session may still be `/usr/local/bin/mwm` (old name) until the user logs in with "glidewm"; install.sh links the old mwm to glidewm while it runs (restart re-execs argv[0]).
- Install: `sudo make install` to `/usr/local/bin/glidewm`. Claude cannot run it (no TTY for sudo). Ask the user, then restart dwm with `Mod+Shift+q` (`Mod+Ctrl+Shift+q` restarts keeping windows and tags).
- `Mod` = Alt. Terminal `konsole` (kitty is a test setup only), launcher `Mod+p` = `rofi-launcher` = `exec rice-search`.
- Test without installing: `Xvfb :7 -screen 0 1280x720x24 &`, `DISPLAY=:7 ./glidewm`. Start dwm first, then `xrdb -merge` (Xvfb resets resources when the last client exits).
- Edit `dwm.c` by hand. Never apply `.diff` patches (`dwm-systray-*.diff` are reference only).
- Backup before big edits: `cp file file.pre-NAME`.

- All-in-one installer: `./install.sh` (`--check`, `--dry-run`, `--only=PARTS`, `--yes`, `--no-*`, `--verbose`; quiet by default: `ok()` prints only with `--verbose`, `head_` is lazy; a chosen part with missing deps fails in `fail_errs`). Checks deps (build/core/shell/opt with
  Gentoo/Arch/Debian/Fedora package names), the init system (runit here: elogind, polkit, D-Bus, PipeWire from ~/.xprofile, SDDM),
  duplicates; arrow-key picker; part dependencies in `needs()` (Shell and Apps need Rice, Session needs glidewm, unless already in place).
  Test it with `--dry-run` and a scratch `HOME`; the picker needs a pty (`printf KEYS | script -qc "./install.sh --dry-run" /dev/null`,
  end the keys on Submit or it waits forever). Never run its sudo parts here.

## Detail docs (read on demand, not auto-loaded)

- `docs/dwm-features.md`: dwm.c/config.h features, keys, canvas mode, IPC commands. Read before editing `dwm.c`.
- `docs/rice-scripts.md`: scripts in `~/.local/bin`, theme pipeline, popups, kitty, the fastfetch logo gallery (`~/.local/share/rice/fflogos/make.py`, not in the repo). Read before touching a rice script.
- README: screenshots live in `screenshots/` as JPEG q90 (user sends PNGs; convert, place between sections, not only at the top; now: `clock-visualiser.jpg` after Features, `fetch-cava.jpg` after Themes, `dock-music.jpg` after Shell); the Patches table lists every suckless patch in `dwm.c` (only systray applied from its diff).
- `docs/menu-animation.md`: card/panel animation design, picom rules, what failed. Read before touching `rice.py` animation.
- `handoff-dss.md` (its "Updates" section lists everything port.sh changes: rice-update, routing wrappers, GlidewmPage, hide-dead.py, wallcheck, vsync): brief of the DarkShadow's Shell (real QML, Quickshell on X11) port, what is live, rollback, open items, the lag measuring recipe. Read first when touching `~/.config/quickshell`, `~/.local/share/dss`, `_RICE_TAGS`/`_RICE_MONS`, shell focus or the quickshell picom rule. Edit `~/.local/share/dss/port.sh`, not `~/.config/quickshell`.
- `docs/history.md`: full per-session log (old CLAUDE.md, about 80 KB). Grep it for the why behind a decision; do not read whole.

## Environment gotchas

- Two monitors: DP-4 (primary, 1920x1080 at 0,1080, 165 Hz) and HDMI-0 (above, rotated inverted, 75 Hz). Popups open on the monitor under the pointer.
- NVIDIA syncs GL swaps to HDMI-0 (75 Hz) by default: `~/.xprofile` exports `__GL_SYNC_DISPLAY_DEVICE=DP-4` since 2026-11-25 (a vsynced GL test window swapped 75/s without it, 165/s with it). picom with `vsync = true` presented every 2nd-3rd vblank (~80 fps: its sgi_video_sync pacing plus a vsynced swap = 2 vblanks a frame); `rice.conf` has `vsync = false` since 2026-11-25 (backup `rice.conf.pre-novsync`): 165 fps, frame pacing still times frames. Not the cause: GPU clocks, blur, damage, `frame-pacing`, `--realtime`; `PICOM_DEBUG=force_vblank_sched=present` is worse (~77 fps). Measure with `cap` + `gl` (scratchpad). `GPUPowerMizerMode=1` does not stick on driver 615 (set, reads back 0). NVIDIA syncs GL swaps to one display. picom is started as `__GL_SYNC_DISPLAY_DEVICE=DP-4 picom --config ~/.config/picom/rice.conf` from `~/.xprofile` (so HDMI-0 can tear or look choppier). The root-owned `~/.config/picom/picom.conf` is untouched.
- picom rules live in `rice.conf` (`rules = (...)`, picom 13, every `match` exclusive, top-level `animations` ignores `match`). Reload with `kill -USR1 <main picom pid>` (`ps -o pid,ppid,args -C picom`; a USR1 to an orphan picom killed it). A broken `rice.conf` KILLS picom on reload: edit a copy, `diff`, copy over, then reload. If it dies: `__GL_SYNC_DISPLAY_DEVICE=DP-4 setsid picom --config ~/.config/picom/rice.conf &`. A stale second picom may exist.
- Games/Steam lag: `~/.local/bin/steam` wrapper adds `-cef-disable-gpu` (restart Steam to apply). A fullscreen game that saturates the GPU still slows cards; that is GPU load, not fixable here. Do NOT cap or throttle game FPS. Untried: iconify games on hidden tags.
- Audio: after re-login PipeWire can be stale; `audio-fix` restarts it and sets the HyperX profile `output:analog-stereo+input:mono-fallback` (`dwm-volume` calls it). A hung PipeWire makes `wpctl` block forever: wrap every `wpctl`, `pactl`, `audio-fix` call in `timeout`. `dwm-volume` serializes with `flock` on `$XDG_RUNTIME_DIR/dwm-volume.lock` and starts `rice-volume` with `9>&-`; `audio-fix` has its own `flock`.
- `dwm-status` is event-driven (`pactl subscribe` sends `SIGRTMIN+10`).
- Measuring tools (rebuild in scratchpad if gone): `cap` (XGetImage change timer = real frame cadence), `gl` (vsynced GL load), `rz` (move/resize/shape/repaint test window).
- Performance rule: never change (map, unmap, fade, move) the Quickshell widget windows at tag-switch time; hide them with `_NET_WM_WINDOW_OPACITY` (`rice-widget-fade`). Measure lag with x11grab + ffmpeg `mpdecimate` and `top` before and after (recipe in `handoff-dss.md`). picom blur and shadows on moving windows are the big cost.
- A dwm change is live only after install and a dwm restart: compare `stat -L -c %i /proc/$(pgrep -x glidewm)/exe /usr/local/bin/glidewm` (old session: `pgrep -x dwm`, `/usr/local/bin/dwm`).
- Known unfixed: session restore saves Steam as `./steamwebhelper ...`, which cannot start.

## Working rules for Claude here

- Never send `xdotool` key or mouse input to the live session unless the target window is confirmed up (for example `xdotool search --class RiceShot`). Add `sleep` between synthetic mouse events.
- `pkill -f` and `pgrep -f` match the calling shell and can kill it. Use PIDs (`./dwm & DP=$!`, `kill $DP`) or `pkill -x` with an exact name. Never `pkill -x dwm`, `konsole` or `picom` on the live session; check `/proc/PID/cmdline`.
- In Xvfb tests set `DISPLAY=:7` on every command, including `xdotool`.
- `pkexec` needs a live parent shell (`sh -c 'pkexec ...' &`).
- Screenshots of the root include the user's other windows: crop with `maim -g WxH+X+Y`, capture sequentially (parallel `maim` races), delete them after looking.
- Do not restart or replace dwm, PipeWire or picom without saying so first.
- Do not cap game FPS. Pitch ambitious ideas but build exactly what was named. Test the real path before claiming it works.
- Keep rice script start-up fast: no heavy imports at the top.

## Unverified / open

- Not seen live: `rice-lock` correct-password path, `rice-session logout/reboot/poweroff/restore`, the `rice` SDDM theme at a real login (needs the user to run `rice-sddm`), passwordless runit power, the DNS/MTU pkexec paths in settings, `rice-record` per-app routing with a real recording, `rice-map` and the tray mirror on two real monitors, a real game with the game-move rule, `rice-scene` monitor detection.
- New shell (2026-11-23, see `docs/rice-scripts.md`): `rice-dock`, `rice-desk`, `rice-center` live blur look, two-monitor behaviour, control-centre toggles, non-calm motion presets on the real picom. Dock focus to a hidden tag needs `sudo make install`.
- Mic test in `rice-volume` needs the HyperX input profile active.
- Open Konsole windows keep old colours/opacity until the next theme apply.
- tesseract data system-wide would need `L10N` + `app-text/tessdata_fast`; leptonica lacks png/jpeg/tiff.
- Theme switcher "background changes after a few secs" could not be reproduced; needs a description from the user.
- dwm changes always need `sudo make install` + `Mod+Shift+q` before they are live.
- 2026-11-25 late (details in `handoff-dss.md` "Fixes" and the lines after it): `dwm.c` tag hover (`_RICE_HOVER`, `taghover()`, backup `dwm.c.pre-tagpeek`) and the 6 ms animstep guard in `run()` are built but not installed; the live session runs `/usr/local/bin/mwm`, so install with `sudo make install && sudo ln -sf /usr/local/bin/glidewm /usr/local/bin/mwm`, then `Mod+Ctrl+Shift+q`. Tag slide after a dock click is laggier than after a key on the real screen; Xvfb shows the same dwm steps (81 vs 82 over 425 ms), so measure live (ask first). Real cover art from Mullvad Browser (no `mpris:artUrl`): scraping SoundCloud's api-v2 `client_id` was refused by the permission check; the user picks a source (iTunes/Deezer, scglass, placeholder).
- Shell patches in `port.sh` since then (each with a `port.sh.pre-*` backup): nav pages by filter (V6.10), `desktop-set` clock styles, `patches/WheelScroll.qml` (100 px a notch, omega 9.5, lead 0.8 screen), dock panel NPal "tinted", dock window always mapped with an empty mask while hidden, dock Grid add transition removed (it left parts at opacity 0), music art note, `TagPeek { }`. Dock icons: `desktop-set dock shade off` (backup `desktop.json.pre-dockcolor`).
- Xvfb tests of the shell: scratch HOME with a copy of `~/.local/share/dss`, run that `port.sh`, `QML_IMPORT_PATH=$D/qml PATH=$D/bin:$PATH qs -n -p ...`; start Xvfb with `-noreset`. Without a compositor translucent windows render black. `grep -q` on `/proc/PID/cmdline` does not match (NUL bytes): `tr '\0' ' '` first.
