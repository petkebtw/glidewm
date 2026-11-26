## Menu animation (rice.py)

- Style in `settings.json` `anim_style`: `"ghost"` (default), `"bar"` (card hangs from the bar), `"picom"` (picom-only, user found it too subtle). Cards dock under the bar (`BAR_BOTTOM = 37`, `BAR_GAP = 8` must match the real bar); cards with `origin` keep their place.
- Default ghost (`Card._ghost_fixed`): a `RiceGrow` window mapped once at its biggest size that only repaints (shape, shadow, own blurred backdrop via `backdrop()`), contents snapshot fades in and rises 10 px while the shape grows with a slight overshoot, real card takes over at the end (real card has an empty shape until then; `_unhide_shape()` at handoff). Open about 0.4-0.5 s, close fold 0.24 s. The old per-frame-resizing ghost is `settings.put('ghost_resize', True)`.
- Why not resize per frame: on NVIDIA + picom GLX a real window RESIZE or SHAPE change stalls while any other app draws vsynced OpenGL (Steam views, games); moves and repaints do not. Do not retry resize-based or clip-based reveals (the settings clip reveal failed: only newly exposed parts paint).
- Frame driver: `rice.py` replaces GTK's 60 Hz frame clock with a GLib timer (5 ms ticks when the monitor is at least 120 Hz) because DP-4 is 165 Hz.
- picom: `RiceGhost`, `RiceCard`, `RicePanel` rules have `blur-strength = 18`, radius 26 (every card and rasi must use 26), no fade; `RiceGrow` has no blur/shadow/rounding; `RiceLock` is excluded from rounding and blur; `RiceAuth` (polkit) grows via picom animation. Normal windows get the picom `appear` open animation. `use-damage = true`.
- Panel (settings): window moves in from beyond the right screen edge (0.5 s), close 0.32 s, move only. Not done: bar-attached circle icons with a dropdown per settings page.
- A card's contents snapshot is taken before async content arrives; `_ghost` re-snaps every 60 ms for the first 0.45 s on cards under 400k px (theme-switcher thumbnails).

