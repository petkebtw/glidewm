"""Shared helpers: theme colors + translucent rounded GTK3 popup window."""
import json, os, math, gi
try:
    import crashlog  # noqa: F401
except Exception:
    pass
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib
import cairo


# ---- display-rate frame driver -------------------------------------------
# GTK3's frame clock on X11 is fixed at 60 Hz, a third of a 165 Hz monitor, so every tick
# animation looked choppy. Replace add_tick_callback with a timer at the monitor's refresh rate
# that also paints synchronously (process_updates) instead of waiting for the 60 Hz clock.
import time as _time


class _Clock:
    def get_frame_time(self):
        return int(_time.monotonic() * 1e6)


_CLOCK = _Clock()
_TICKS = {}
_NEXT = [1]


def _interval(widget):
    try:
        d = Gdk.Display.get_default()
        gw = widget.get_window() if hasattr(widget, "get_window") else None
        m = d.get_monitor_at_window(gw) if gw is not None else None
        if m is None:
            _s, px, py = d.get_default_seat().get_pointer().get_position()
            m = d.get_monitor_at_point(px, py) or d.get_primary_monitor()
        hz = (m.get_refresh_rate() or 60000) / 1000.0
    except Exception:
        hz = 60.0
    return 5 if hz >= 120 else max(int(round(1000.0 / (min(max(hz, 30.0), 240.0) * 1.2))), 5)


def _fast_add_tick(self, cb, *data):
    tid = _NEXT[0]; _NEXT[0] += 1

    def run():
        if tid not in _TICKS:
            return False
        try:
            keep = cb(self, _CLOCK, *data)
        except Exception:
            keep = False
        if not keep:
            _TICKS.pop(tid, None)
            return False
        try:
            top = self.get_toplevel()
            gw = top.get_window() if top is not None else None
            if gw is not None and gw.is_visible():
                gw.process_updates(True)
        except Exception:
            pass
        return True
    _TICKS[tid] = GLib.timeout_add(_interval(self), run, priority=GLib.PRIORITY_HIGH_IDLE - 5)
    return tid


def _fast_remove_tick(self, tid):
    src = _TICKS.pop(tid, None)
    if src is not None:
        try: GLib.source_remove(src)
        except Exception: pass


Gtk.Widget.add_tick_callback = _fast_add_tick
Gtk.Widget.remove_tick_callback = _fast_remove_tick

COLORS_FILE = os.path.expanduser("~/.cache/theme/colors.json")
DEFAULT = dict(bg="#282a36", bg2="#343746", border="#44475a", fg="#f2f2f5", dim="#8a8ea8", accent="#bd93f9", accent2="#ff79c6")
FONT = "JetBrains Mono"
ICON_FONT = "Symbols Nerd Font"
SANS_FONT = "Inter Display"


CUR = {}          # colours of the newest Card; widgets read this at draw time


def colors():
    global FONT, SANS_FONT
    c = dict(DEFAULT)
    try:
        with open(COLORS_FILE) as f:
            c.update(json.load(f))
    except Exception:
        pass
    FONT = c.get("font_mono") or "JetBrains Mono"          # theme mood picks the fonts (themes.mood)
    SANS_FONT = c.get("font_sans") or "Inter Display"
    return c


def rgb(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def rounded(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def bezier(x1, y1, x2, y2):
    """CSS-style cubic-bezier easing, like Hyprland's `bezier = name, x1, y1, x2, y2`."""
    def f(t):
        if t <= 0: return 0.0
        if t >= 1: return 1.0
        lo, hi, u = 0.0, 1.0, t
        for _ in range(24):
            x = 3 * (1 - u) ** 2 * u * x1 + 3 * (1 - u) * u * u * x2 + u ** 3
            if abs(x - t) < 1e-5: break
            if x < t: lo = u
            else: hi = u
            u = (lo + hi) / 2
        return 3 * (1 - u) ** 2 * u * y1 + 3 * (1 - u) * u * u * y2 + u ** 3
    return f


EASE_OUT = bezier(0.05, 0.9, 0.1, 1.05)      # Hyprland "default": fast start, slight overshoot, soft landing
EASE_IN = bezier(0.3, 0.0, 0.8, 0.15)
EASE_SNAP = bezier(0.16, 1.0, 0.3, 1.0)      # fast out, long soft end, no overshoot (menus, panels)
EASE_AWAY = bezier(0.4, 0.0, 1.0, 1.0)       # closing: starts slow, leaves fast


def anim_on():
    try:
        import settings
        return bool(settings.get("anim"))
    except Exception:
        return True


def glass_alpha(default=0.66):
    """Menu glass opacity: like the terminal (Rice.colorscheme Opacity) plus a little for legibility; the extra blur comes from picom."""
    try:
        op = None
        with open(os.path.expanduser("~/.local/share/konsole/Rice.colorscheme")) as f:
            for ln in f:
                if ln.startswith("Opacity="):
                    op = float(ln.split("=", 1)[1]); break
        if op is None:
            return default
        return min(max(op + 0.06, 0.30), 0.55)
    except Exception:
        return default


def use_ghost():
    """Pop style: True (default) = the shape-growing ghost; False (settings anim_style = "picom") = picom's own open/close animation like terminals."""
    try:
        import settings
        return settings.get("anim_style") != "picom"
    except Exception:
        return True


def fixed_grow():
    """True (default): the grow/fold ghost is one full-size window that only repaints (see Card._ghost_fixed).
    settings ghost_resize = true brings back the old ghost that is resized every frame."""
    try:
        import settings
        return not settings.get("ghost_resize")
    except Exception:
        return True


def backdrop(x, y, w, h, k=8):
    """Blurred copy of the screen at (x, y, w, h) as a cairo surface, or None.
    Matches picom's dual_kawase blur-strength 18 (fitted on live captures: downscale 1/8 box-filtered,
    one soften pass, bilinear upscale; mean error about 1/255). Returns (surface, sx, sy): where its
    top-left sits on screen (the capture is clamped to the root window)."""
    try:
        root = Gdk.get_default_root_window()
        rw, rh = root.get_width(), root.get_height()
        m = 24                                   # extra margin so the blur near the edges sees real neighbours
        x0, y0 = max(x - m, 0), max(y - m, 0)
        x1, y1 = min(x + w + m, rw), min(y + h + m, rh)
        if x1 - x0 < 8 or y1 - y0 < 8:
            return None
        pb = Gdk.pixbuf_get_from_window(root, x0, y0, x1 - x0, y1 - y0)
        if pb is None:
            return None
        W, H = x1 - x0, y1 - y0
        sw, sh = max(W // k, 2), max(H // k, 2)
        s = cairo.ImageSurface(cairo.FORMAT_RGB24, sw, sh)
        c = cairo.Context(s)
        c.scale(sw / W, sh / H)
        Gdk.cairo_set_source_pixbuf(c, pb, 0, 0)
        c.get_source().set_filter(cairo.FILTER_GOOD)
        c.paint()
        t = cairo.ImageSurface(cairo.FORMAT_RGB24, sw, sh)
        tc = cairo.Context(t)
        tc.set_source_surface(s, 0, 0); tc.paint()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            tc.set_source_surface(s, dx, dy); tc.get_source().set_extend(cairo.EXTEND_PAD); tc.paint_with_alpha(0.2)
        o = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
        oc = cairo.Context(o)
        oc.scale(W / sw, H / sh)
        oc.set_source_surface(t, 0, 0)
        p = oc.get_source(); p.set_filter(cairo.FILTER_BILINEAR); p.set_extend(cairo.EXTEND_PAD)
        oc.paint()
        return o, x0, y0
    except Exception:
        return None


TUCK = 26   # bar style: the card reaches this far up under the bar, so its rounded top corners are hidden and it looks attached


def bar_style():
    try:
        import settings
        return settings.get("anim_style") == "bar"
    except Exception:
        return False


def find_bar(px, py):
    """(xid, x, y, w, h) of the dwm bar window on the monitor under (px, py), or None."""
    try:
        import subprocess
        d = Gdk.Display.get_default()
        m = (d.get_monitor_at_point(px, py) or d.get_primary_monitor()).get_geometry()
        out = subprocess.run(["xdotool", "search", "--class", "dwm", "getwindowgeometry", "--shell", "%@"],
                             capture_output=True, text=True, timeout=1).stdout
        best = None
        for blk in out.split("WINDOW=")[1:]:
            kv = dict(l.split("=", 1) for l in ("WINDOW=" + blk).splitlines() if "=" in l)
            x, y, w, h = (int(kv[k]) for k in ("X", "Y", "WIDTH", "HEIGHT"))
            if w < 200 or h > 60 or h < 10:
                continue
            if m.x <= x < m.x + m.width and m.y <= y < m.y + 60:
                best = (int(kv["WINDOW"]), x, y, w, h)
        return best
    except Exception:
        return None


def below_bar(win, bar):
    """Stack a mapped Gtk popup directly under the bar window, so what sticks out under the bar is hidden."""
    try:
        if not bar or win.get_window() is None:
            return
        gi.require_version("GdkX11", "3.0")
        from gi.repository import GdkX11
        sib = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), bar[0])
        win.get_window().restack(sib, False)
    except Exception:
        pass


def primary_geometry():
    d = Gdk.Display.get_default()
    m = d.get_primary_monitor() or d.get_monitor(0)
    return m.get_geometry()


BAR_BOTTOM = 37   # bar's bottom edge below the monitor top; keep equal to the 37 in picom rice.conf
BAR_GAP = 8
S0 = 0.55      # how small a card is at the origin point (bigger = shorter, snappier travel)


def fade_child(win, to, delay_ms, dur_ms, done=None):
    """Fade a window's contents (not the glass) with the frame clock."""
    ch = win.get_child()
    if ch is None:
        if done: done()
        return
    t0 = [None]
    frm = ch.get_opacity()

    def tick(wd, clock):
        now = clock.get_frame_time() / 1000.0
        if t0[0] is None:
            t0[0] = now + delay_ms
        t = (now - t0[0]) / float(max(dur_ms, 1))
        if t < 0:
            return True
        t = min(t, 1.0)
        ch.set_opacity(frm + (to - frm) * (1 - (1 - t) ** 3))
        if t >= 1.0:
            if done: done()
            return False
        return True
    win.add_tick_callback(tick)


class Card(Gtk.Window):
    """Override-redirect translucent rounded window (picom adds blur + shadow)."""

    def __init__(self, w, h, radius=26, popup=True, alpha=0.66):
        super().__init__(type=Gtk.WindowType.POPUP if popup else Gtk.WindowType.TOPLEVEL)
        self.c = colors()
        import designs
        self.geo = designs.geo(self.c.get("design", "default"))
        self.set_wmclass("rice", "RiceCard" + self.geo["sfx"])
        radius = round(radius * self.geo["card"] / 26) if radius else 0
        CUR.clear(); CUR.update(self.c)
        self.glass = bool(self.c.get("glass", 1))
        self.radius, self.alpha = radius, (glass_alpha(alpha) if self.glass else 1.0)   # glass off: solid card
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_default_size(w, h)
        self.set_size_request(w, h)
        vis = self.get_screen().get_rgba_visual()
        if vis:
            self.set_visual(vis)
        self.connect("draw", self._draw)
        self._css = None
        self.origin = None          # (x, y) the card pops out of; None = the bar's top centre
        self._style()

    def _anchor(self):
        """Point the pop animation grows from / shrinks into."""
        if self.origin:
            return self.origin
        try:
            d = Gdk.Display.get_default()
            _scr, px, py = d.get_default_seat().get_pointer().get_position()
            g = (d.get_monitor_at_point(px, py) or d.get_primary_monitor()).get_geometry()
        except Exception:
            g = primary_geometry()
        return (g.x + g.width // 2, g.y + 24)   # middle of the bar, top centre

    def _style(self):
        css = Gtk.CssProvider()
        c = self.c
        css.load_from_data(f"""
        * {{ font-family: '{FONT}', '{ICON_FONT}'; color: {c['fg']}; }}
        window {{ background: transparent; }}
        button {{ background: transparent; border: none; box-shadow: none; padding: 4px 10px; border-radius: 12px; }}
        button:hover {{ background: alpha({c['accent']}, 0.25); }}
        entry {{ background: alpha({c['bg2']}, 0.9); border: 1px solid {c['border']}; border-radius: 10px; padding: 8px 10px; color: {c['fg']}; }}
        list, row, scrolledwindow, viewport, scrolledwindow undershoot, scrolledwindow overshoot {{ background: transparent; background-image: none; border: none; box-shadow: none; }}
        row:hover {{ background: alpha({c['fg']}, 0.07); border-radius: 10px; }}
        row:selected, row.sel {{ background: {c['accent']}; border-radius: 12px; }}
        row:selected *, row.sel * {{ color: {c['bg']}; }}
        scrollbar {{ opacity: 0; min-width: 0; }}
        button.pill {{ background: alpha({c['fg']}, 0.08); padding: 8px 10px; }}
        button.pill:hover {{ background: alpha({c['accent']}, 0.35); }}
        entry:focus {{ border-color: {c['accent']}; box-shadow: none; outline: none; }}
        entry selection {{ background: {c['accent']}; color: {c['bg']}; }}
        .dim {{ color: {c['dim']}; }}
        .accent {{ color: {c['accent']}; }}
        """.encode())
        if self._css is not None:
            Gtk.StyleContext.remove_provider_for_screen(Gdk.Screen.get_default(), self._css)
        self._css = css
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def restyle(self):
        """Reload colours + glass setting after a theme change, live."""
        self.c = colors()
        CUR.clear(); CUR.update(self.c)
        self.glass = bool(self.c.get("glass", 1))
        self.alpha = glass_alpha(0.72) if self.glass else 1.0
        self._style()
        self.queue_draw()

    def _draw(self, w, cr):
        if getattr(self, "_snapping", False):
            return False
        a = self.get_allocation()
        cr.set_operator(cairo.OPERATOR_SOURCE)
        rounded(cr, 0.5, 0.5, a.width - 1, a.height - 1, self.radius)
        cr.set_source_rgba(*rgb(self.c["bg"], self.alpha))
        cr.fill_preserve()
        cr.set_operator(cairo.OPERATOR_OVER)
        bw = self.geo["bw"]
        if bw:
            cr.set_source_rgba(*rgb(self.c["fg"] if bw >= 3 else self.c["accent"], 1.0 if bw >= 3 else (0.55 if self.glass else 0.35)))
            cr.set_line_width(bw)
            cr.stroke()
        else:
            cr.new_path()
        return False

    def _dock_y(self):
        ax, ay = self._anchor()
        if bar_style() and getattr(self, "_tucked", False) and getattr(self, "_bar", None):
            return int(self._bar[2] + self._bar[4] - TUCK)
        return int(ay - 24 + BAR_BOTTOM + BAR_GAP)

    def move(self, x, y):
        # menus stay docked under the bar, even when a script moves them after show_all()
        if getattr(self, "_docked", False):
            try:
                y = self._dock_y()
            except Exception:
                pass
        super().move(x, y)

    def place(self, x, y):
        self.move(x, y)

    def top_center(self, y=64):
        g = primary_geometry()
        w, _ = self.get_size_request()
        self.move(g.x + (g.width - w) // 2, g.y + y)

    # ---- pop animation -------------------------------------------------
    # The real window never resizes. A "ghost" popup (same WM class, so picom
    # blurs/rounds/shadows it) draws a snapshot of the card scaled around its
    # centre, so blur and shadow follow the animated size.
    def _snapshot(self):
        w, h = self.get_size_request()
        a = self.get_allocation()
        if a.width > 1 and a.height > 1:
            w, h = a.width, a.height
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(surf)
        self.draw(cr)
        return surf, w, h

    def _real_visible(self, on):
        """Hide the real card (shape + opacity) while the ghost animates, so picom
        draws one blur/shadow only, not two stacked ones."""
        win = self.get_window()
        if win is None:
            return
        win.shape_combine_region(None if on else cairo.Region(), 0, 0)
        self.set_opacity(1.0 if on else 0.0)

    def _ghost_run(self, dur, curve, done, anchor=None):
        surf, w, h = self._snapshot()
        bare = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)       # glass only, no contents
        self._draw(self, cairo.Context(bare))
        x, y = self._pos
        if anchor is None:
            anchor = (x + w / 2.0, y + h / 2.0)       # scale around the centre
        ax, ay = anchor
        gh = Gtk.Window(type=Gtk.WindowType.POPUP)
        gh.set_wmclass("rice", "RiceCard" + self.geo["sfx"])
        gh.set_app_paintable(True)
        vis = gh.get_screen().get_rgba_visual()
        if vis:
            gh.set_visual(vis)
        st = dict(s=1.0, a=0.0, c=1.0, dy=0.0, sx=1.0, sy=1.0)

        def place():
            # one ConfigureWindow per frame: separate resize() and move() tear (two X requests, two repaints)
            gw, gh_ = max(int(round(w * st["sx"])) & ~1, 2), max(int(round(h * st["sy"])) & ~1, 2)
            px, py = int(round(x + (w - gw) / 2.0)), int(round(y + st["dy"]))
            gdk = gh.get_window()
            if gdk is not None:
                gdk.move_resize(px, py, gw, gh_)
            else:
                gh.resize(gw, gh_); gh.move(px, py)

        def draw(wd, cr):
            cr.set_operator(cairo.OPERATOR_SOURCE)
            cr.set_source_rgba(0, 0, 0, 0)
            cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER)
            cr.scale(wd.get_allocated_width() / w, wd.get_allocated_height() / h)
            g, c = max(0.0, min(1.0, st["a"])), max(0.0, min(1.0, st["c"]))
            if c < 1.0:
                cr.set_source_surface(bare, 0, 0)
                cr.paint_with_alpha(g * (1.0 - c))
            cr.set_source_surface(surf, 0, 0)
            cr.paint_with_alpha(g * c)
            return True

        gh.connect("draw", draw)
        curve(0.0, st)
        gh.set_default_size(max(int(w * st["sx"]), 2), max(int(h * st["sy"]), 2))
        place()
        gh.show_all()
        gh.get_window().set_pass_through(True)
        t0 = [None]
        fin = [False]

        def finish():
            if fin[0]:
                return
            fin[0] = True
            try:
                done()
            finally:
                gh.hide()            # unmap + destroy right now: nothing may outlive the animation
                gh.destroy()

        def tick(wd, clock):
            if fin[0]:
                return False
            now = clock.get_frame_time()
            if t0[0] is None:
                t0[0] = now
            t = min((now - t0[0]) / (dur * 1000.0), 1.0)
            curve(t, st)
            place()
            gh.queue_draw()
            if t >= 1.0:
                finish()
                return False
            return True
        gh.add_tick_callback(tick)
        # watchdog: if the frame clock stalls the ghost must not stay on screen
        GLib.timeout_add(int(dur) + 250, lambda: (finish(), False)[1])

    def _dock_under_bar(self):
        """Menus open right under the bar (top edge on it) and unfold downward; picom does the motion.
        Cards that pop out of a clicked icon (origin set) keep their own place."""
        try:
            if self.origin or isinstance(self, Panel):
                return
            self._docked = True
            x = self.get_position()[0]
            self.move(x, self._dock_y())
        except Exception:
            pass

    def _fade_alpha(self, to, delay_ms, dur_ms):
        """Animate the glass alpha: opaque while the shape grows/folds (nothing from behind shows through), glass when settled."""
        t0 = [None]
        frm = self.alpha

        def tick(wd, clock):
            now = clock.get_frame_time() / 1000.0
            if t0[0] is None:
                t0[0] = now + delay_ms
            t = (now - t0[0]) / float(max(dur_ms, 1))
            if t < 0:
                return True
            t = min(t, 1.0)
            self.alpha = frm + (to - frm) * (1 - (1 - t) ** 3)
            self.queue_draw()
            return t < 1.0
        self.add_tick_callback(tick)

    def _fade_child(self, to, delay_ms, dur_ms, done=None):
        """Fade the card's contents (not the glass): contents arrive after the shape has grown, leave before it folds."""
        ch = self.get_child()
        if ch is None:
            if done: done()
            return
        t0 = [None]
        frm = ch.get_opacity()

        def tick(wd, clock):
            now = clock.get_frame_time() / 1000.0
            if t0[0] is None:
                t0[0] = now + delay_ms
            t = (now - t0[0]) / float(max(dur_ms, 1))
            if t < 0:
                return True
            t = min(t, 1.0)
            ch.set_opacity(frm + (to - frm) * (1 - (1 - t) ** 3))
            if t >= 1.0:
                if done: done()
                return False
            return True
        self.add_tick_callback(tick)

    def _unhide_shape(self):
        if getattr(self, "_shape_hidden", False):
            self._shape_hidden = False
            try:
                self.get_window().shape_combine_region(None, 0, 0)
                self.queue_draw()
                self.get_window().process_updates(True)
            except Exception:
                pass

    def _lift_child(self, off, dur_ms):
        """Contents rise `off` px into place while they fade in (child margin, eased out). Not for big panels."""
        ch = self.get_child()
        if ch is None or isinstance(self, Panel):
            return
        base = ch.get_margin_top()
        t0 = [None]
        ease = bezier(0.2, 1.0, 0.3, 1.0)

        def tick(wd, clock):
            now = clock.get_frame_time() / 1000.0
            if t0[0] is None:
                t0[0] = now
            t = min((now - t0[0]) / float(max(dur_ms, 1)), 1.0)
            ch.set_margin_top(base + int(round(off * (1.0 - ease(t)))))
            return t < 1.0
        ch.set_margin_top(base + off)
        self.add_tick_callback(tick)

    # ---- grow / fold shape ---------------------------------------------------
    # A "RiceGhost" popup (own picom rule: blur + shadow, no animation) is really resized each frame (one
    # move_resize call) and draws only the blank glass shape. The real card sits invisible (opacity 0)
    # at its final place and takes over when the ghost is full size; then its contents fade in.
    def _ghost(self, grow, done, wait=False):
        if fixed_grow() and not getattr(self, "_tucked", False):
            r = self._ghost_fixed(grow, done, wait)
            if r is not None:
                return r
        x, y = self._pos
        w, h = self.get_size_request()
        a = self.get_allocation()
        if a.width > 1 and a.height > 1:
            w, h = a.width, a.height
        right = isinstance(self, Panel)
        gh = Gtk.Window(type=Gtk.WindowType.POPUP)
        gh.set_wmclass("rice", "RiceGhost" + self.geo["sfx"])
        gh.set_app_paintable(True)
        vis = gh.get_screen().get_rgba_visual()
        if vis:
            gh.set_visual(vis)
        goal = self._goal_alpha
        csurf = None
        ch0 = self.get_child()

        def snap():
            """Render the contents once at final layout (the ghost paints them clipped by the growing shape)."""
            try:
                self.check_resize()                # finish any pending relayout first (rows added right after show)
                surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
                o = ch0.get_opacity(); ch0.set_opacity(1.0)
                cc = cairo.Context(surf)
                a0 = ch0.get_allocation()
                cc.translate(a0.x, a0.y)           # child.draw() draws relative to its own allocation
                ch0.draw(cc)
                ch0.set_opacity(o)
                return surf
            except Exception:
                return None
        if grow and ch0 is not None:
            csurf = snap()
        fill = getattr(self, "fill_rgba", None) or rgb(self.c["bg"], goal)
        edge = rgb(self.c["accent"], 0.55 if self.glass else 0.35)
        st = dict(sx=0.2, sy=0.08, ca=0.0, lift=0.0)
        if not grow:
            st = dict(sx=1.0, sy=1.0)
        fx = bezier(0.2, 1.25, 0.3, 1.0)        # overshoot, then settle (spring feel)
        fy = bezier(0.25, 1.5, 0.3, 1.0)
        ex = bezier(0.3, 0.0, 0.6, 0.85)
        fl = bezier(0.2, 1.0, 0.3, 1.0)

        def geom():
            gw = max(int(round(w * st["sx"])) & ~1, 6)
            gh_ = max(int(round(h * st["sy"])) & ~1, 6)
            px = x + (w - gw) if right else x + (w - gw) // 2
            return px, y, gw, gh_

        def draw(wd, cr):
            # the GDK window size is what move_resize just set; the GTK allocation lags a frame behind, which drew
            # the rim smaller than the window and left a lighter blurred rectangle sticking out of the shape
            gw_ = wd.get_window()
            al = Gdk.Rectangle()
            al.width, al.height = (gw_.get_width(), gw_.get_height()) if gw_ is not None else (wd.get_allocated_width(), wd.get_allocated_height())
            cr.set_operator(cairo.OPERATOR_SOURCE)
            cr.set_source_rgba(0, 0, 0, 0); cr.paint()
            rounded(cr, 0.5, 0.5, al.width - 1, al.height - 1, min(self.radius, al.height / 2.0))
            cr.set_source_rgba(*fill); cr.fill_preserve()
            cr.set_operator(cairo.OPERATOR_OVER)
            cr.set_source_rgba(*edge); cr.set_line_width(1.5); cr.stroke()
            if csurf is not None and st["ca"] > 0.01:
                px_, _py, _gw, _gh = geom()
                rounded(cr, 0.5, 0.5, al.width - 1, al.height - 1, min(self.radius, al.height / 2.0))
                cr.clip()
                cr.set_source_surface(st.get("cs") or csurf, -(px_ - x), st["lift"])
                cr.paint_with_alpha(st["ca"])
            return True
        gh.connect("draw", draw)
        px, py, gw, gh_ = geom()
        gh.set_default_size(gw, gh_)
        gh.move(px, py)
        if wait:
            gh.set_opacity(0.0)           # pre-mapped invisible at full size; start() reveals it with no latency
        gh.show_all()
        gh.get_window().set_pass_through(True)
        try:
            # when the window grows, the X server fills the new area with this colour at once (premultiplied ARGB),
            # so the compositor never sees a transparent strip before our own paint arrives
            gh.get_window().set_background_rgba(Gdk.RGBA(fill[0], fill[1], fill[2], fill[3]))
        except Exception:
            pass
        if getattr(self, "_tucked", False):
            below_bar(gh, self._bar)
        t0 = [None]
        fin = [False]
        go = [not wait]
        handed = [False]
        dur = getattr(self, "grow_dur", 0.52) if grow else 0.24

        def finish():
            if fin[0]:
                return
            fin[0] = True
            try:
                if not handed[0]:
                    handed[0] = True
                    done()
            finally:
                gh.hide()                    # same flush as the card showing up: no frame with both layers (looked darker)
                GLib.idle_add(lambda: (gh.destroy(), False)[1])

        def tick(wd, clock):
            if fin[0]:
                return False
            if not go[0]:
                return True
            now = clock.get_frame_time() / 1e6
            if t0[0] is None:
                t0[0] = now
            t = now - t0[0]
            if grow:
                if csurf is not None and w * h < 600000 and t - st.get("rs", -1.0) > 0.03 and t < 0.6:
                    st["rs"] = t                       # contents that load while the shape grows (thumbnails) show up too
                    ns = snap()
                    if ns is not None:
                        st["cs"] = ns
                st["sx"] = 0.2 + 0.8 * fx(min(t / 0.40, 1))
                st["sy"] = 0.08 + 0.92 * fy(min(t / 0.52, 1))
                u = min(max((t - 0.09) / 0.24, 0.0), 1.0)
                st["ca"] = u * u * (3 - 2 * u)                      # contents appear while the shape is still growing
                st["lift"] = 10.0 * (1.0 - fl(min(max((t - 0.05) / 0.38, 0.0), 1.0)))
            else:
                st["sx"] = 1.0 - 0.8 * ex(min(t / 0.24, 1))
                st["sy"] = 1.0 - 0.92 * ex(min(t / 0.24, 1))
            px, py, gw, gh_ = geom()
            g = gh.get_window()
            if g is not None:
                g.move_resize(px, py, gw, gh_)
            gh.queue_draw()
            if t >= dur:
                finish()
                return False
            return True
        gh.add_tick_callback(tick)

        def start():
            go[0] = True
            gh.set_opacity(1.0)
            GLib.timeout_add(int(dur * 1000) + 300, lambda: (finish(), False)[1])
        if not wait:
            start()
        return start

    # ---- grow / fold without resizing --------------------------------------------
    # Measured 2026-11-21: on NVIDIA, while any other app draws with OpenGL + vsync (Steam's GPU web view, games),
    # every window RESIZE or SHAPE change stalls picom (it rebinds the window pixmap and waits behind that app's
    # vsync): the resized ghost fell from ~80 to ~15 frames/s. Moves and plain repaints are not affected.
    # So this ghost is mapped once at its biggest size (overshoot + shadow margin included) and only repaints:
    # it draws the shape, a soft shadow and the glass itself. picom gives the class RiceGrow no blur, shadow
    # or rounding (it would blur the whole rectangle), so the ghost paints its own blurred backdrop
    # (backdrop(), fitted to picom's blur) and the handoff to the real card looks the same.
    def _ghost_fixed(self, grow, done, wait=False):
        x, y = self._pos
        w, h = self.get_size_request()
        a = self.get_allocation()
        if a.width > 1 and a.height > 1:
            w, h = a.width, a.height
        right = isinstance(self, Panel)
        SM, ST, SB = 34, 22, 46                     # shadow margins: sides, top, bottom (picom: radius 30, offset y 10)
        W = int(w * 1.03) + 2 + 2 * SM              # overshoot: width up to +1.6 %, height up to +7.4 %
        H = int(h * 1.09) + 2 + ST + SB
        x0 = (x + w + SM - W) if right else (x + w // 2 - W // 2)
        y0 = y - ST
        if grow:
            bd = backdrop(x0, y0, W, H)                 # the real card is still shaped away: this is what is behind it
            self._backdrop = (bd, x0, y0, W, H)
        else:
            sv = getattr(self, "_backdrop", None)       # the card covers its place now: reuse the capture from opening
            bd = sv[0] if sv and sv[1:] == (x0, y0, W, H) else None
        if bd is None:
            return None
        bsurf, bx, by = bd
        gh = Gtk.Window(type=Gtk.WindowType.POPUP)
        gh.set_wmclass("rice", "RiceGrow")
        gh.set_app_paintable(True)
        vis = gh.get_screen().get_rgba_visual()
        if vis:
            gh.set_visual(vis)
        goal = self._goal_alpha
        csurf = None
        ch0 = self.get_child()

        def snap():
            """Render the contents once at final layout (the ghost paints them clipped by the growing shape)."""
            try:
                self.check_resize()
                surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
                o = ch0.get_opacity(); ch0.set_opacity(1.0)
                cc = cairo.Context(surf)
                a0 = ch0.get_allocation()
                cc.translate(a0.x, a0.y)
                ch0.draw(cc)
                ch0.set_opacity(o)
                return surf
            except Exception:
                return None
        if grow and ch0 is not None:
            csurf = snap()
        fill = getattr(self, "fill_rgba", None) or rgb(self.c["bg"], goal)
        edge = rgb(self.c["accent"], 0.55 if self.glass else 0.35)
        st = dict(sx=0.2, sy=0.08, ca=0.0, lift=0.0) if grow else dict(sx=1.0, sy=1.0)
        fx = bezier(0.2, 1.25, 0.3, 1.0)
        fy = bezier(0.25, 1.5, 0.3, 1.0)
        ex = bezier(0.3, 0.0, 0.6, 0.85)
        fl = bezier(0.2, 1.0, 0.3, 1.0)

        def geom():                                    # shape rectangle in ghost-window coordinates
            gw = max(int(round(w * st["sx"])) & ~1, 6)
            gh_ = max(int(round(h * st["sy"])) & ~1, 6)
            px = (x + (w - gw)) if right else (x + (w - gw) // 2)
            return px - x0, ST, gw, gh_

        def draw(wd, cr):
            ox, oy, gw, gh_ = geom()
            r = min(self.radius, gh_ / 2.0)
            cr.set_operator(cairo.OPERATOR_SOURCE)
            cr.set_source_rgba(0, 0, 0, 0); cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER)
            ga = st.get("ga", 1.0)                     # motion preset "minimal": the whole ghost fades
            if ga < 0.999:
                cr.push_group()
            for i in range(8):                         # soft shadow like picom's (radius 30, opacity .5, 10 px down)
                e = 30.0 * (1.0 - i / 8.0)
                rounded(cr, ox - e, oy + 10 - e, gw + 2 * e, gh_ + 2 * e, r + e)
                cr.set_source_rgba(0, 0, 0, 0.065); cr.fill()
            rounded(cr, ox + 0.5, oy + 0.5, gw - 1, gh_ - 1, r)
            cr.save()
            cr.clip_preserve()
            cr.set_source_surface(bsurf, bx - x0, by - y0); cr.paint()      # the blur picom would put behind it
            cr.restore()
            cr.set_source_rgba(*fill); cr.fill_preserve()
            cr.set_source_rgba(*edge); cr.set_line_width(1.5); cr.stroke()
            if csurf is not None and st.get("ca", 0) > 0.01:
                rounded(cr, ox + 0.5, oy + 0.5, gw - 1, gh_ - 1, r)
                cr.clip()
                cr.set_source_surface(st.get("cs") or csurf, x - x0, oy + st["lift"])
                cr.paint_with_alpha(st["ca"])
            if ga < 0.999:
                cr.reset_clip()
                cr.pop_group_to_source(); cr.paint_with_alpha(max(ga, 0.0))
            return True
        gh.connect("draw", draw)
        gh.set_default_size(W, H)
        gh.set_size_request(W, H)
        gh.move(x0, y0)
        try:
            gh.realize()
            gh.get_window().set_background_rgba(Gdk.RGBA(0, 0, 0, 0))   # no leftover pixels before the first paint
        except Exception:
            pass
        if wait:
            gh.set_opacity(0.0)
        gh.show_all()
        gh.get_window().set_pass_through(True)
        t0 = [None]
        fin = [False]
        go = [not wait]
        handed = [False]
        dur = getattr(self, "grow_dur", 0.52) if grow else 0.24
        MP = motion()                                  # motion preset; calm = the original timings and curves
        mk = mdur(1.0)
        dur *= mk                                      # real seconds; tick() works on the calm timeline (t / mk)
        mname = MP["name"]

        def finish():
            if fin[0]:
                return
            fin[0] = True
            try:
                if not handed[0]:
                    handed[0] = True
                    done()
            finally:
                gh.hide()
                GLib.idle_add(lambda: (gh.destroy(), False)[1])

        def tick(wd, clock):
            if fin[0]:
                return False
            if not go[0]:
                return True
            now = clock.get_frame_time() / 1e6
            if t0[0] is None:
                t0[0] = now
            rt = now - t0[0]                           # real seconds
            t = rt / mk                                # calm-timeline seconds
            if grow:
                if csurf is not None and w * h < 600000 and rt - st.get("rs", -1.0) > 0.03 and rt < 0.6:
                    st["rs"] = rt
                    ns = snap()
                    if ns is not None:
                        st["cs"] = ns
                if mname == "minimal":                 # no shape motion: the card fades in where it lands
                    st["sx"] = st["sy"] = 1.0
                    u = min(t / 0.52, 1.0)
                    st["ga"] = u
                    st["ca"] = u
                    st["lift"] = 4.0 * (1.0 - u)
                elif mname == "calm":
                    st["sx"] = 0.2 + 0.8 * fx(min(t / 0.40, 1))
                    st["sy"] = 0.08 + 0.92 * fy(min(t / 0.52, 1))
                else:                                  # spring presets; overshoot scaled to fit the ghost window
                    vx, vy = spring(min(t / 0.40, 1), MP), spring(min(t / 0.52, 1), MP)
                    vx = vx if vx <= 1 else 1 + (vx - 1) * 0.1
                    vy = vy if vy <= 1 else 1 + (vy - 1) * 0.3
                    st["sx"] = min(0.2 + 0.8 * vx, 1.03)
                    st["sy"] = min(0.08 + 0.92 * vy, 1.085)
                if mname != "minimal":
                    u = min(max((t - 0.09) / 0.24, 0.0), 1.0)
                    st["ca"] = u * u * (3 - 2 * u)
                    st["lift"] = 10.0 * (1.0 - fl(min(max((t - 0.05) / 0.38, 0.0), 1.0)))
            elif mname == "minimal":
                u = min(t / 0.24, 1)
                st["sx"] = st["sy"] = 1.0 - 0.04 * u
                st["ga"] = 1.0 - u
            else:
                st["sx"] = 1.0 - 0.8 * ex(min(t / 0.24, 1))
                st["sy"] = 1.0 - 0.92 * ex(min(t / 0.24, 1))
            gh.queue_draw()                            # repaint only: the window never changes size or shape
            if rt >= dur:
                finish()
                return False
            return True
        gh.add_tick_callback(tick)

        def start():
            go[0] = True
            gh.set_opacity(1.0)
            GLib.timeout_add(int(dur * 1000) + 300, lambda: (finish(), False)[1])
        if not wait:
            start()
        return start

    def show_all(self):
        """Real card mapped invisible at its place; a ghost shape grows from the bar, then the card takes over."""
        self._leaving = False
        ch = self.get_child()
        anim = anim_on() and ch is not None and use_ghost() and not getattr(self, "fast", False)
        self._goal_alpha = self.alpha
        if not (self.origin or isinstance(self, Panel)):
            self._docked = True
            if bar_style() and ch is not None and not getattr(self, "_tucked", False):
                try:
                    ax_, ay_ = self._anchor()
                    self._bar = find_bar(int(ax_), int(ay_))
                    if self._bar:
                        w_, h_ = self.get_size_request()
                        self.set_size_request(w_, h_ + TUCK)
                        self.resize(w_, h_ + TUCK)
                        ch.set_margin_top(ch.get_margin_top() + TUCK)
                        self._tucked = True
                except Exception:
                    self._tucked = False
        if anim:
            ch.set_opacity(0.0)
            try:
                self.realize()
                # picom still blurs and shadows a window that has opacity 0, which showed as a ghost rectangle at the
                # final place before the shape grew; an empty bounding shape makes the real card truly invisible
                self.get_window().shape_combine_region(cairo.Region(), 0, 0)
                self._shape_hidden = True
            except Exception:
                pass
            self.set_opacity(0.0)
        else:
            self.set_opacity(1.0)
        if isinstance(self, Panel):
            self.move(self.fx, self.fy)
        if not anim:
            try:                                  # a fresh ARGB window must start transparent, not with leftover pixels
                self.realize()
                self.get_window().set_background_rgba(Gdk.RGBA(0, 0, 0, 0))
            except Exception:
                pass
        Gtk.Window.show_all(self)
        self._dock_under_bar()
        if getattr(self, "_tucked", False):
            below_bar(self, self._bar)
        self._pos = tuple(self.get_position())
        if not anim:
            GLib.idle_add(lambda: (setattr(self, "_pos", tuple(self.get_position())), False)[1])
            return
        state = dict(started=False)

        def start():
            if state["started"]:
                return False
            state["started"] = True
            self._pos = tuple(self.get_position())      # scripts may move() after show_all

            def handoff():
                ch_ = self.get_child()
                if ch_ is not None:
                    ch_.set_opacity(1.0)             # the ghost already showed the contents at full strength
                self.set_opacity(1.0)
                self._unhide_shape()                 # shows the card and paints it at once, before the ghost goes away
            self._ghost(True, handoff)
            return False
        GLib.timeout_add(40, start)        # layout is forced by snap(); the hidden real card never paints

    def quit_anim(self, *_):
        """Contents fade out, then a ghost shape folds back into the bar, then leave the main loop."""
        if getattr(self, "_leaving", False):
            return False
        self._leaving = True

        def quit_():
            self.hide()
            GLib.timeout_add(20, lambda: (Gtk.main_quit(), False)[1])

        def fold():
            if not anim_on() or not self._pos:
                quit_(); return

            def after():
                quit_()
            go = self._ghost(False, after, wait=True)        # mapped invisible now, while the contents fade
            def swap():
                ch_ = self.get_child()
                if ch_ is not None:
                    ch_.hide()                               # contents truly gone: nothing of them can blur through the ghost
                self.queue_draw()
                go()                                         # reveal the ghost ...
                self.set_opacity(0.0); (self.get_window() or self).hide()      # ... and hide the real card now (a still-mapped card shows blurred through the ghost)
            swap_fn[0] = swap
        swap_fn = [None]
        if anim_on() and use_ghost() and not getattr(self, "fast", False):
            self._pos = tuple(self.get_position())
            if self._pos:
                fold()
            self._fade_child(0.0, 0, 110, lambda: swap_fn[0]() if swap_fn[0] else quit_())
        else:
            quit_()
        return False


class Panel(Card):
    """Side panel that slides out from the right screen edge (real window moves; blur and shadow follow).
       Close with quit_anim: it slides back out."""

    def __init__(self, w, margin=14, top=BAR_BOTTOM + BAR_GAP, popup=True):
        g = self.mon()
        h = g.height - top - margin
        super().__init__(w, h, radius=26, popup=popup, alpha=0.72)
        self.pw, self.ph, self.margin, self.top = w, h, margin, top
        self.gx, self.gy, self.gw = g.x, g.y, g.width
        self.fx = g.x + g.width - w - margin
        self.fy = g.y + top
        self.set_wmclass("rice", "RicePanel" + self.geo["sfx"])      # own class: picom grows it from its top-right corner

    @staticmethod
    def mon():
        d = Gdk.Display.get_default()
        _, px, py = d.get_default_seat().get_pointer().get_position()
        m = d.get_monitor_at_point(px, py) or d.get_primary_monitor()
        return m.get_geometry()

    # A big window must not be resized every frame (each resize reallocates the texture and re-blurs ~1 MP in picom,
    # that made the settings panel choppy). The panel keeps its size and only slides in from the right and fades.
    def _slide(self, opening, done=None):
        """The panel comes in from beyond the right screen edge and leaves the same way (move only: no resize,
        no fade, so it reads as a real slide)."""
        t0 = [None]
        dur = mdur(0.5 if opening else 0.32)              # motion preset + speed (calm at 1.0 = 0.5 / 0.32 s)
        MP = motion()
        dist = (self.gx + self.gw) - self.fx + 24         # until it is fully outside the monitor
        if not opening:
            curve = EASE_AWAY
        elif MP["name"] == "calm":
            curve = EASE_SNAP
        else:
            lim = 28.0 / max(dist, 1.0)                   # a spring may pass its place by at most 28 px

            def curve(u):
                v = spring(u, MP)
                return v if v <= 1.0 else 1.0 + min((v - 1.0) * 0.35, lim)

        def tick(wd, clock):
            now = clock.get_frame_time() / 1e6
            if t0[0] is None:
                t0[0] = now
            t = min((now - t0[0]) / dur, 1.0)
            e = curve(t)
            if not opening:
                e = 1.0 - e
            self.move(int(self.fx + dist * (1.0 - e)), self.fy)
            if t >= 1.0:
                if done:
                    done()
                return False
            return True
        self.add_tick_callback(tick)

    def show_all(self):
        self._leaving = False
        if not (anim_on() and self.get_child() is not None):
            return Card.show_all(self)
        self._goal_alpha = self.alpha
        self.set_opacity(1.0)
        self.move(self.gx + self.gw + 24, self.fy)       # starts outside the monitor, painted there first
        try:
            self.realize()
            self.get_window().set_background_rgba(Gdk.RGBA(0, 0, 0, 0))
        except Exception:
            pass
        Gtk.Window.show_all(self)
        self._pos = (self.fx, self.fy)
        state = dict(started=False)

        def start():
            if state["started"]:
                return False
            state["started"] = True
            self._slide(True)
            return False
        hid = []

        def painted(wd, cr):
            wd.disconnect(hid[0])
            GLib.idle_add(start)
            return False
        hid.append(self.connect_after("draw", painted))
        GLib.timeout_add(400, start)

    def quit_anim(self, *_):
        if getattr(self, "_leaving", False):
            return False
        self._leaving = True

        def quit_():
            self.hide()
            GLib.timeout_add(20, lambda: (Gtk.main_quit(), False)[1])
        if anim_on():
            self._slide(False, quit_)
        else:
            quit_()
        return False


# ==== motion presets ==========================================================================
# Settings "Motion" page (rice-center Customize tab): a preset (settings `motion`), a speed factor
# (settings `motion_speed`, 0.5-2.0, higher = faster) and the old `anim` on/off switch.
# "calm" is the original look: Card grow/fold and the Panel slide are unchanged with it at speed 1.0.
# Public API, also used by other scripts through getattr(rice, ...):
#   motion(name=None) -> preset dict (name, label, desc, curve, zeta, omega, k)
#   spring(t, preset=None) -> eased 0..1 (t clamped to 0..1; lively/bouncy overshoot above 1, ends exactly at 1)
#   mdur(base_s) -> base duration scaled by the preset and the speed (>= 0.001 s; 0.001 when animations are off)
MOTION_PRESETS = {
    "calm":    dict(label="Calm", desc="smooth glide, no overshoot", curve="snap", zeta=1.0, omega=8.0, k=1.0),
    "lively":  dict(label="Lively", desc="quick with a little spring", curve="spring", zeta=0.62, omega=9.0, k=0.9),
    "bouncy":  dict(label="Bouncy", desc="playful springs that wobble", curve="spring", zeta=0.38, omega=13.0, k=1.2),
    "snappy":  dict(label="Snappy", desc="fast and crisp, no wobble", curve="spring", zeta=1.0, omega=9.0, k=0.6),
    "minimal": dict(label="Minimal", desc="short plain fades", curve="linear", zeta=1.0, omega=8.0, k=0.45),
}
MOTION_ORDER = ("calm", "lively", "bouncy", "snappy", "minimal")
_MCACHE = [0.0, None, 1.0]          # read time, preset name, speed


def _motion_read():
    now = _time.monotonic()
    if _MCACHE[1] is None or now - _MCACHE[0] > 0.5:
        name, sp = "calm", 1.0
        try:
            import settings
            d = settings.load()
            name = d.get("motion") or "calm"
            sp = float(d.get("motion_speed") or 1.0)
        except Exception:
            pass
        _MCACHE[:] = [now, name if name in MOTION_PRESETS else "calm", min(max(sp, 0.5), 2.0)]
    return _MCACHE[1], _MCACHE[2]


def motion(name=None):
    """Active (or named) motion preset as a dict; `speed` is the user's speed factor."""
    cur, sp = _motion_read()
    n = name if name in MOTION_PRESETS else cur
    p = dict(MOTION_PRESETS[n]); p["name"] = n; p["speed"] = sp
    return p


def spring(t, preset=None):
    """Motion-preset easing. preset: None (active), a preset name or a motion() dict."""
    p = preset if isinstance(preset, dict) else motion(preset)
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    kind = p.get("curve", "snap")
    if kind == "snap":
        return EASE_SNAP(t)
    if kind == "linear":
        return 1.0 - (1.0 - t) ** 2
    z, w = p.get("zeta", 1.0), p.get("omega", 8.0)
    if z < 1.0:
        wd = w * math.sqrt(1.0 - z * z)
        v = 1.0 - math.exp(-z * w * t) * (math.cos(wd * t) + z * w / wd * math.sin(wd * t))
    else:
        v = 1.0 - math.exp(-w * t) * (1.0 + w * t)
    return 1.0 - (1.0 - v) * (1.0 - t ** 6)       # the tiny leftover fades out, so t = 1 lands exactly on 1


def mdur(base_s):
    """Duration for an animation whose calm length is base_s seconds."""
    if not anim_on():
        return 0.001
    n, sp = _motion_read()
    return max(base_s * MOTION_PRESETS[n]["k"] / sp, 0.001)
