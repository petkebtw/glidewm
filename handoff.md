# Handoff: window animations like reference4.mp4, and where the rice stands (2026-11-17)

Read `CLAUDE.md` first (build, install, working rules). This file is the short version for whoever continues the
animation work, plus the open items from the last session.

## 1. What reference4.mp4 shows

`reference4.mp4` is a 1024x576, 36 s screen recording of a tiling desktop (dwm/Hyprland style) over a dark blue
night-sky wallpaper. It is low resolution, so timings below are estimates from frame sampling (10-15 fps tiles
extracted with ffmpeg), not measurements.

What the motion looks like:

- **Windows are transparent.** The terminals (btop, cava, a big clock, a lyrics-like window) have no visible
  background. Only a 1 px outline shows each window's rectangle, and the focused window's outline is bright white
  while the others are dim.
- **The outlines are the animation.** When a window opens, a split line appears and slides to its place; the
  focused window's bright edge sweeps across the screen as the layout rearranges. The frames around 12-16 s show a
  bright vertical edge moving while a box fills in next to it. Around 17-19 s a column of many small windows grows
  in from the left screen edge and splits into nested rectangles (dwindle-like).
- **Real resizing, no scaling.** Window contents reflow as the rectangles move; there is no zoom, no fade-in of the
  whole window and no bounce. Easing is a fast start with a long soft end (ease-out), about 0.25-0.35 s.
- **Siblings move at the same time** as the new window grows, so the layout always looks like one continuous
  motion.
- **Theme change** (around 12 s) is a full-screen blur and crossfade to a new wallpaper, after which the windows
  re-open.
- Menus in `reference.mp4` (not 4) are separate: glass cards that fade/scale in. That study (app menu, volume,
  media, clipboard) was started and interrupted, and is not done.

## 2. What is implemented, and what is not

In `dwm.c` (installed only after `sudo make install` and `Mod+Shift+q`):

- `companim = 0`: dwm animates real window geometry itself (`resizeclient` sets a target, `animstep()` eases it).
  Easing is `easeg` = cubic-bezier(0.22, 1, 0.36, 1) (no overshoot), `GEODUR` = 0.22 s.
- Siblings of a new or closed window glide to their new rectangles. Workspace switch slides windows out and in
  (`park` / `swipedir`). The focused window has the bright outline, unfocused ones have none, and the outline
  crossfades (`bm` / `bt`).
- A NEW window is not animated: it opens at its final geometry and picom fades it in (`appear`, scale 0.93, 0.2 s).

What is deliberately different from the reference, and why:

- The first version grew a new window from a thin strip at the screen edge, which looks like the reference. It was
  removed because the shell inside a new Konsole then saw a 2-column terminal, got four SIGWINCH signals
  (2, 159, 176, 177 columns) and garbled its prompt (typed text landed behind `petke@gentoo`). Verified with a
  script that traps WINCH and prints `stty size`: old build 2, 159, 176, 177; new build 177 only.
- So the reference's "window grows out of an edge" look is currently missing for NEW windows. Siblings still
  resize live, which also sends SIGWINCH to their shells, but only between normal sizes, and has not garbled
  anything.

## 3. Suggested next step: get the reference look without resizing the new window

Keep the new window at its final size and reveal it with an X shape instead of resizing it:

1. Map the new window at its final geometry (as now).
2. Set a bounding shape (`XShapeCombineRectangles`, `ShapeBounding`) that starts as a thin strip at the nearest
   screen edge and grows to the full rectangle over `GEODUR`, using `easeg`. dwm already links `-lXext` and has
   `clipcanvas()` that uses XShape per client, so the plumbing exists.
3. Remove the shape at the end (`ShapeSet` with the full rectangle or `ShapeBounding` reset).
4. Leave the picom `appear` fade off for these windows, or keep it very short, because the shape reveal replaces it.

Expected result: the strip-growing look of reference4 with the shell seeing its final size the whole time.
Things to check: the focused outline must grow with the shape (the border is part of the window, so it is clipped
too), and `clipcanvas()` also sets shapes in canvas mode, so the two must not overwrite each other.

Alternative if XShape is awkward: let picom animate only the open (`geometry` trigger scoped to a short window
after map), but picom's geometry animation stretches the old image, which was ugly when a neighbour closed.

How to verify any change: run a test dwm in Xvfb (`Xvfb :7 -screen 0 1280x720x24 &`, `DISPLAY=:7 ./dwm`), open a
Konsole that runs a script trapping WINCH, and check the logged sizes. Poll window geometry with
`xdotool search --class konsole` and `getwindowgeometry` in a loop to see the motion. Take screenshots with
`maim -g` crops only.

## 4. Re-studying the reference

```
ffprobe -v error -show_entries format=duration:stream=width,height reference4.mp4
ffmpeg -y -ss 13 -t 1.2 -i reference4.mp4 -vf "fps=15,crop=1024:500:0:76,scale=340:-1,tile=3x6" -frames:v 1 sheet.png
ffmpeg -y -ss 17.2 -t 1.2 -i reference4.mp4 -vf "fps=15,crop=1024:500:0:76,scale=340:-1,tile=3x6" -frames:v 1 sheet2.png
```

The two segments above (13 s and 17.2 s) are the most useful: window open and nested-split growth.

## 5. State of the rest (so nobody repeats work)

Done in the last session, in files outside this repo unless noted:

- Popup menus pop out of the bar (or the clicked icon) and shrink back; 190 ms open, 120 ms close, no overshoot
  (`~/.local/lib/rice/rice.py`). Start-up of every tool was measured at 0.11-0.33 s. A bug that put the animation
  window at the top-left (the "invisible transparent window") is fixed.
- Colour extractor rewritten in OKLab (`~/.local/lib/rice/themes.py`); the login screen background is the
  wallpaper, heavily blurred.
- In `dwm.c`: layouts are tile, bento, dock, mosaic, pinwheel; the right bar cluster is on every monitor; the
  systray is pinned to monitor 1 and mirrored on the other bar with working left and right click (XTest); new
  windows and keybinds follow the monitor under the cursor.
- picom `rice.conf` uses only `rules`; `RiceCard` has `fade = false`; the systray has class `dwmtray` so picom
  skips it.

Not verified on the real two-monitor setup (tested only in Xvfb with one monitor): the tray mirror and its clicks,
the new layouts, the no-strip open, and the pointer-monitor sync.

Open items:

- `sudo make install` + `Mod+Shift+q` has not been run for the latest `dwm.c` (the user must do it; there is no TTY
  for sudo here).
- A stale second picom (pid 30252, parent 1) may still be running.
- The user's report "typing goes behind `petke@gentoo` and a little strip is there" was explained by the strip start;
  the fix is built but not confirmed on the user's screen.
- The `reference.mp4` menu-animation study was interrupted.
- `config.def.h` is still out of sync with `config.h`.

## 6. Pitfalls

- Never `pkill -x konsole` or `pkill -x picom`: they hit the user's live processes. Use PIDs from `$!` and check
  `/proc/PID/cmdline`.
- Do not send xdotool input to the live display (`:0`) unless the target is confirmed; use `DISPLAY=:7`.
- Do not restart dwm, picom or PipeWire without saying so first. `kill -USR1 <main picom pid>` reloads picom; get
  the PID from `ps -o pid,ppid,args -C picom` (a USR1 to an orphan picom killed it).
- Do not commit unless asked.
