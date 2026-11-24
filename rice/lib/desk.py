"""rice-desk daemon: desktop widgets that sit on the wallpaper below every window, plus an edit mode.

Every widget is its own small ARGB override-redirect window (Gtk POPUP, type hint DESKTOP, WM_CLASS
RiceDesk for bare widgets, RiceDeskGlass for glass cards) kept at the bottom of the stack with
XLowerWindow. Layout lives in ~/.cache/rice/desk.json (see load_layout / save).
Edit mode raises the widgets, adds an input-transparent overlay per monitor (class RiceDeskOverlay)
that draws outlines, handles, snap guides and the resize preview, and a hint pill that holds the
keyboard grab. Resizing only draws a preview in the overlay and resizes the real window on release
(a live window resize stalls on NVIDIA + picom while GL apps draw)."""
import os, sys, json, time, math, signal, random, subprocess, threading
import rice
from rice import Gtk, Gdk, GLib, cairo
import gi
gi.require_version("PangoCairo", "1.0")
import contextlib
from gi.repository import Pango, PangoCairo

STATE = os.environ.get("RICE_DESK_STATE") or os.path.expanduser("~/.cache/rice/desk.json")
MONO = "JetBrains Mono, Symbols Nerd Font"
SANS = "Inter Display, Inter, Symbols Nerd Font"
ICON = "Symbols Nerd Font"
import designs as _dsg
RADIUS = _dsg.geo()['desk']
SFX = _dsg.geo()['sfx']
GRID = 8
SNAP = 8
MARGIN = 24
TOP = getattr(rice, "BAR_BOTTOM", 37) + 16
C = rice.colors()
GA = [rice.glass_alpha()]
W_ = Pango.Weight


def G(hexcode):
    """Nerd Font glyph by code point (kept out of the source as literals on purpose)."""
    return chr(int(hexcode, 16))


# ---- motion ---------------------------------------------------------------
def mdur(s):
    f = getattr(rice, "mdur", None)
    if f:
        try:
            return float(f(s))
        except Exception:
            pass
    try:
        import settings
        if not settings.get("anim"):
            return 0.001
        m = settings.get("motion") or "calm"
        sp = float(settings.get("motion_speed") or 1.0)
    except Exception:
        m, sp = "calm", 1.0
    k = dict(calm=1.0, lively=0.9, bouncy=1.2, snappy=0.6, minimal=0.45).get(m, 1.0)
    return max(s * k / min(max(sp, 0.5), 2.0), 0.001)


def spring(t, preset=None):
    f = getattr(rice, "spring", None)
    if f:
        try:
            return float(f(t, preset))
        except Exception:
            pass
    if t <= 0: return 0.0
    if t >= 1: return 1.0
    z, w = 0.62, 9.0
    wd = w * math.sqrt(1 - z * z)
    tt = t * 1.0
    return 1 - math.exp(-z * w * tt) * (math.cos(wd * tt) + z * w / wd * math.sin(wd * tt))


def ease(t):
    return 1 - (1 - min(max(t, 0.0), 1.0)) ** 3


def tween(widget, dur, fn, done=None):
    """Run fn(t) for t 0..1 over dur seconds on the (display-rate) frame clock."""
    if dur <= 0.02 or widget is None:
        fn(1.0)
        if done: done()
        return
    st = [None]

    def tick(w, clock):
        now = clock.get_frame_time() / 1e6
        if st[0] is None:
            st[0] = now
        t = min((now - st[0]) / dur, 1.0)
        try:
            fn(t)
        except Exception:
            return False
        if t >= 1.0:
            if done: done()
            return False
        return True
    widget.add_tick_callback(tick)


@contextlib.contextmanager
def _skin(o):
    import designs
    saved = (dict(C), GA[0], rice.FONT, rice.SANS_FONT)
    try:
        dn = o.get("design")
        if dn:
            C["design"] = dn
        if dn and dn != "default":
            C.update(designs.palette(dict(C), dn, bool(C.get("light"))))
            rice.SANS_FONT, rice.FONT = designs.fonts(dn, rice.SANS_FONT, rice.FONT)
        if o.get("font"):
            rice.FONT = rice.SANS_FONT = o["font"]
        if o.get("accent"):
            C["accent"] = o["accent"]
        if o.get("bgalpha") is not None:
            GA[0] = float(o["bgalpha"])
        yield
    finally:
        C.clear(); C.update(saved[0]); GA[0] = saved[1]; rice.FONT, rice.SANS_FONT = saved[2], saved[3]


# ---- drawing helpers --------------------------------------------------------
def rgba(k, a=1.0):
    h = k if k.startswith("#") else C.get(k, "#ffffff")
    return rice.rgb(h, a)


def T(cr, s, x, y, size, color="fg", a=1.0, weight=W_.NORMAL, fam=MONO, align="l", valign="t",
      width=None, sx=1.0, ink=False, wrap=False):
    """Pango text at (x, y). align l/c/r, valign t/c/b; ink=True aligns on the glyphs' ink box.
    Returns (width, height) of the box used for alignment."""
    L = PangoCairo.create_layout(cr)
    fd = Pango.FontDescription()
    fd.set_family({MONO: rice.FONT + ", Symbols Nerd Font", SANS: rice.SANS_FONT + ", Symbols Nerd Font"}.get(fam, fam))
    fd.set_absolute_size(size * Pango.SCALE)
    fd.set_weight(weight)
    L.set_font_description(fd)
    if width:
        L.set_width(int(width * Pango.SCALE))
        if wrap:
            L.set_wrap(Pango.WrapMode.WORD_CHAR)
        else:
            L.set_ellipsize(Pango.EllipsizeMode.END)
    L.set_text(s, -1)
    ir, lr = L.get_pixel_extents()
    r = ir if ink else lr
    bw, bh = r.width * sx, r.height
    ox, oy = -r.x * sx, -r.y
    if align == "c": ox -= bw / 2
    elif align == "r": ox -= bw
    if valign == "c": oy -= bh / 2
    elif valign == "b": oy -= bh
    cr.save()
    cr.translate(x + ox, y + oy)
    cr.scale(sx, 1)
    cr.new_path()
    cr.move_to(0, 0)
    cr.set_source_rgba(*(rgba(color, a) if isinstance(color, str) else color))
    PangoCairo.show_layout(cr, L)
    cr.restore()
    return bw, bh


def DN():
    return C.get("design", "default")


def cookie_path(cr, cx, cy, r, lobes=10, amp=0.075, rot=-math.pi / 2, t0=0.0, t1=1.0, steps=160):
    """Scalloped 'cookie' outline (Material 3 shape). t0..t1 = fraction of the loop (0 = top, clockwise)."""
    cr.new_sub_path()
    n = max(int(steps * (t1 - t0)), 2)
    for i in range(n + 1):
        t = t0 + (t1 - t0) * i / n
        a = rot + 2 * math.pi * t
        rr = r * (1 - amp + amp * math.cos(lobes * 2 * math.pi * t))
        (cr.move_to if i == 0 and t0 == 0.0 or i == 0 else cr.line_to)(cx + rr * math.cos(a), cy + rr * math.sin(a))


def rect_loop(cr, cx, cy, r, t0, t1):
    """Square frame path of half-size r, from the top centre clockwise; t0..t1 = fraction of the perimeter."""
    pts = [(cx, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r), (cx - r, cy - r), (cx, cy - r)]
    seg = [r, 2 * r, 2 * r, 2 * r, r]
    tot = sum(seg)
    a, b = t0 * tot, t1 * tot
    pos = 0.0
    cr.new_sub_path()
    started = False
    for i, ln in enumerate(seg):
        s0, s1 = pos, pos + ln
        if b > s0 and a < s1:
            f0, f1 = max(a, s0) - s0, min(b, s1) - s0
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            ux, uy = (x1 - x0) / ln, (y1 - y0) / ln
            if not started:
                cr.move_to(x0 + ux * f0, y0 + uy * f0); started = True
            cr.line_to(x0 + ux * f1, y0 + uy * f1)
        pos = s1


def glass(cr, w, h, r=RADIUS):
    dn = DN()
    if dn == "brutal":                      # solid block, hard outline, no corners
        cr.rectangle(1.5, 1.5, w - 3, h - 3)
        cr.set_source_rgba(*rgba("bg", 1.0)); cr.fill_preserve()
        cr.set_source_rgba(*rgba("fg", 1.0)); cr.set_line_width(3); cr.stroke()
        return
    rice.rounded(cr, 0.5, 0.5, w - 1, h - 1, r)
    if dn == "material3":                   # tonal surface, no outline
        cr.set_source_rgba(*rgba("bg2", max(GA[0], 0.88) if C.get("glass", 1) else 1.0)); cr.fill()
        return
    cr.set_source_rgba(*rgba("bg", GA[0] if C.get("glass", 1) else 0.92))
    cr.fill_preserve()
    if dn == "macos":                       # hairline + top sheen like a macOS widget
        cr.set_source_rgba(*rgba("fg", 0.20)); cr.set_line_width(1); cr.stroke()
        rice.rounded(cr, 1.5, 1.5, w - 3, h - 3, max(r - 1, 0))
        g = cairo.LinearGradient(0, 0, 0, h)
        g.add_color_stop_rgba(0, *rgba("fg", 0.10)); g.add_color_stop_rgba(0.45, *rgba("fg", 0.0))
        cr.set_source(g); cr.fill()
        return
    cr.set_source_rgba(*rgba("accent", 0.45))
    cr.set_line_width(1.2)
    cr.stroke()


def shadowed(cr, w, h, fn, k=3, a=0.62):
    """fn(cr) drawn over a soft shadow of itself (bare widgets on the wallpaper). The shadow is fn drawn at
    1/k size, box-softened and scaled back up with a bilinear filter, tinted with the theme background."""
    p = 3
    sw, sh = int(w / k) + 2 * p, int(h / k) + 2 * p
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, sw, sh)
    c = cairo.Context(s)
    c.translate(p, p); c.scale(1.0 / k, 1.0 / k)
    fn(c)
    t = cairo.ImageSurface(cairo.FORMAT_ARGB32, sw, sh)
    tc = cairo.Context(t)
    for dx, dy, al in ((0, 0, 0.36), (1, 0, 0.16), (-1, 0, 0.16), (0, 1, 0.16), (0, -1, 0.16)):
        tc.set_source_surface(s, dx, dy); tc.paint_with_alpha(al)
    cr.save()
    cr.translate(-p * k, -p * k + 1.5)
    cr.scale(k, k)
    pat = cairo.SurfacePattern(t)
    pat.set_filter(cairo.FILTER_BILINEAR)
    cr.set_source_rgba(*rgba("bg", a))
    cr.mask(pat)
    cr.mask(pat)
    cr.restore()
    fn(cr)


def fit(cr, w, h, bw, bh):
    """Uniform scale of a bw x bh design into w x h, centred. Returns the scale."""
    s = min(w / bw, h / bh)
    cr.translate((w - bw * s) / 2, (h - bh * s) / 2)
    cr.scale(s, s)
    return s


def dashed_rrect(cr, x, y, w, h, r, color, a, lw=2.0, dash=(8, 6), off=0.0):
    cr.save()
    rice.rounded(cr, x, y, w, h, max(min(r, w / 2, h / 2), 1))
    cr.set_source_rgba(*rgba(color, a))
    cr.set_line_width(lw)
    cr.set_dash(list(dash), off)
    cr.stroke()
    cr.restore()


# ---- monitors ---------------------------------------------------------------
def monitors():
    d = Gdk.Display.get_default()
    out = []
    pm = d.get_primary_monitor()
    for i in range(d.get_n_monitors()):
        m = d.get_monitor(i)
        g = m.get_geometry()
        out.append(dict(name=m.get_model() or f"mon{i}", x=g.x, y=g.y, w=g.width, h=g.height,
                        primary=(m == pm) or (pm is None and i == 0)))
    if out and not any(m["primary"] for m in out):
        out[0]["primary"] = True
    return out


def primary():
    ms = monitors()
    return next(m for m in ms if m["primary"])


def mon_at(x, y):
    ms = monitors()
    for m in ms:
        if m["x"] <= x < m["x"] + m["w"] and m["y"] <= y < m["y"] + m["h"]:
            return m
    best = min(ms, key=lambda m: (max(m["x"] - x, 0, x - m["x"] - m["w"]) ** 2 + max(m["y"] - y, 0, y - m["y"] - m["h"]) ** 2))
    return best


def pointer():
    d = Gdk.Display.get_default()
    _s, x, y = d.get_default_seat().get_pointer().get_position()
    return x, y


def gdk_lower(win):
    try:
        gw = win.get_window()
        if gw is not None:
            gw.lower()
    except Exception:
        pass


def gdk_raise(win):
    try:
        gw = win.get_window()
        if gw is not None:
            gw.raise_()
    except Exception:
        pass


# ---- widget base ------------------------------------------------------------
class Item:
    kind, title, icon = "?", "?", G("f2d0")
    base = (300, 200)
    style0 = "glass"
    free = False          # True: content stretches to any aspect instead of a uniform fit

    def __init__(self, desk, d):
        self.desk, self.d = desk, d
        self.id = d.get("id") or f"{self.kind}-{random.randrange(16 ** 5):05x}"
        self.style = d.get("style") or self.style0
        self.opts = dict(d.get("opts") or {})
        self.w, self.h = int(d.get("w") or self.base[0]), int(d.get("h") or self.base[1])
        self.x, self.y = 0, 0
        self.win = None
        self.hidden = False       # media: nothing playing
        self.alive = True
        self._timers = []

    # geometry
    def rect(self):
        return (self.x, self.y, self.w, self.h)

    def min_size(self):
        return (max(int(self.base[0] * 0.45), 80), max(int(self.base[1] * 0.45), 60))

    def to_dict(self):
        cx, cy = self.x + self.w // 2, self.y + self.h // 2
        m = mon_at(cx, cy)
        return dict(id=self.id, kind=self.kind, mon=m["name"], origin=[m["x"], m["y"]],
                    x=self.x - m["x"], y=self.y - m["y"], w=self.w, h=self.h, style=self.style, opts=self.opts)

    # window
    def build(self):
        win = Gtk.Window(type=Gtk.WindowType.POPUP)
        win.set_wmclass("rice-desk", ("RiceDeskGlass" + SFX) if self.style == "glass" else "RiceDesk")
        win.set_title(f"rice-desk {self.kind}")
        win.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
        win.set_app_paintable(True)
        win.set_decorated(False)
        vis = win.get_screen().get_rgba_visual()
        if vis:
            win.set_visual(vis)
        win.set_default_size(self.w, self.h)
        win.set_size_request(self.w, self.h)
        win.move(self.x, self.y)
        win.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                       Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.SCROLL_MASK |
                       Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        win.connect("draw", self._draw)
        win.connect("button-press-event", lambda w, e: self.desk.on_press(self, e))
        win.connect("button-release-event", lambda w, e: self.desk.on_release(self, e))
        win.connect("motion-notify-event", lambda w, e: self.desk.on_motion(self, e))
        win.connect("scroll-event", lambda w, e: self.desk.on_scroll(self, e))
        win.connect("key-press-event", lambda w, e: self.desk.on_key(self, e))
        win.realize()
        win.get_window().set_background_rgba(Gdk.RGBA(0, 0, 0, 0))
        self.win = win
        return win

    def show(self, anim=True, delay=0.0, raised=False):
        if self.win is None:
            self.build()
        if self.hidden and not self.desk.editing:
            return
        win = self.win
        if not anim:
            win.set_opacity(1.0)
            win.move(self.x, self.y)
            win.show()
            (gdk_raise if raised else gdk_lower)(win)
            return
        win.set_opacity(0.0)
        win.move(self.x, self.y + 14)
        win.show()
        (gdk_raise if raised else gdk_lower)(win)

        def go():
            if self.win is not win:
                return False
            def f(t):
                win.set_opacity(min(t * 1.7, 1.0))
                win.move(self.x, self.y + int(round(14 * (1 - spring(t)))))
            tween(win, mdur(0.6), f)
            return False
        if delay > 0:
            GLib.timeout_add(int(delay * 1000), go)
        else:
            go()

    def hide_win(self, anim=True, done=None):
        win = self.win
        if win is None:
            if done: done()
            return
        if not anim:
            win.hide()
            if done: done()
            return

        def f(t):
            win.set_opacity(1 - ease(t))
        tween(win, mdur(0.28), f, lambda: (win.hide(), done and done()))

    def destroy(self):
        self.alive = False
        self.stop()
        if self.win is not None:
            self.win.destroy()
            self.win = None

    def rebuild(self, raised=False):
        old = self.win
        self.win = None
        self.build()
        if old is not None:
            old.destroy()
        self.show(anim=False, raised=raised)

    def redraw(self):
        if self.win is not None and self.win.get_mapped():
            self.win.queue_draw()

    def place(self):
        if self.win is not None:
            self.win.move(self.x, self.y)

    def commit_size(self, w, h):
        self.w, self.h = int(w), int(h)
        if self.win is not None:
            self.win.set_size_request(self.w, self.h)
            self.win.resize(self.w, self.h)

    def _draw(self, win, cr):
        a = win.get_allocation()
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        try:
            self.render(cr, a.width, a.height)
        except Exception as ex:
            print("rice-desk draw", self.kind, ex, file=sys.stderr)
        return True

    def skin(self):
        """Per-widget look from opts (font, design, accent, bgalpha): swaps the module palette/fonts while drawing."""
        o = self.opts
        if not any(k in o for k in ("font", "design", "accent", "bgalpha")):
            return contextlib.nullcontext()
        return _skin(o)

    def render(self, cr, w, h, preview=False):
        with self.skin():
            self._render(cr, w, h, preview)

    def _render(self, cr, w, h, preview=False):
        if self.style == "glass":
            glass(cr, w, h)
            cr.save(); self.paint(cr, w, h, preview); cr.restore()
        else:
            shadowed(cr, w, h, lambda c: (c.save(), self.paint(c, w, h, preview), c.restore()))

    def fg_shadowless(self):
        return self.style == "glass"

    # content + behaviour (override)
    def paint(self, cr, w, h, preview=False):
        pass

    def start(self):
        pass

    def stop(self):
        for t in self._timers:
            try: GLib.source_remove(t)
            except Exception: pass
        self._timers = []

    def every(self, ms, fn):
        def run():
            if not self.alive:
                return False
            fn()
            return True
        self._timers.append(GLib.timeout_add(ms, run))

    def extra_menu(self, menu, setopt):
        pass

    def click(self, x, y, e):
        return False

    def scroll(self, up):
        return False

    def local(self, x, y):
        """Window coords -> design coords (for fitted widgets)."""
        bw, bh = self.base
        s = min(self.w / bw, self.h / bh)
        return (x - (self.w - bw * s) / 2) / s, (y - (self.h - bh * s) / 2) / s


# ---- clock ------------------------------------------------------------------
class Clock(Item):
    kind, title, icon = "clock", "Clock", G("f017")
    base = (300, 400)
    style0 = "bare"

    def extra_menu(self, menu, setopt):
        for key, label, dflt in (("h24", "24-hour time", True), ("greeting", "Show greeting", True)):
            m = Gtk.CheckMenuItem(label=label); m.set_active(self.opts.get(key, dflt))
            m.connect("toggled", lambda w, k=key: (self.opts.__setitem__(k, w.get_active()), self.redraw(), self.desk.save()))
            menu.append(m)

    def start(self):
        self._tick()

    def _tick(self):
        if not self.alive:
            return False
        self.redraw()
        now = time.time()
        ms = int((60 - (now % 60)) * 1000) + 40          # next minute boundary
        self._ct = GLib.timeout_add(ms, self._tick)
        return False

    def stop(self):
        super().stop()
        if getattr(self, "_ct", None):
            GLib.source_remove(self._ct)
            self._ct = None

    def paint(self, cr, w, h, preview=False):
        fit(cr, w, h, *self.base)
        bw, bh = self.base
        lt = time.localtime()
        h24 = self.opts.get("h24", True)
        hh = lt.tm_hour if h24 else (lt.tm_hour % 12 or 12)
        cx = bw / 2
        dn = DN()
        if dn == "macos":                               # one light line, date above (iOS style)
            T(cr, time.strftime("%A, %B %-d", lt), cx, 96, 18, "accent", 1.0, W_.MEDIUM, SANS, "c")
            T(cr, f"{hh:02d}:{lt.tm_min:02d}", cx, 128, 104, "fg", 1.0, W_.LIGHT, SANS, "c", ink=True)
        elif dn == "brutal":                            # two boxed mono blocks with hard shadows
            for k, (txt, ay) in enumerate(((f"{hh:02d}", 46), (f"{lt.tm_min:02d}", 206))):
                cr.rectangle(cx - 100 + 7, ay + 7, 200, 140); cr.set_source_rgba(*rgba("fg", 1.0)); cr.fill()
                cr.rectangle(cx - 100, ay, 200, 140); cr.set_source_rgba(*rgba("accent" if k else "bg", 1.0)); cr.fill()
                cr.rectangle(cx - 100, ay, 200, 140); cr.set_source_rgba(*rgba("fg", 1.0)); cr.set_line_width(4); cr.stroke()
                T(cr, txt, cx, ay + 70, 118, "bg" if k else "fg", 1.0, W_.HEAVY, MONO, "c", "c", ink=True)
            T(cr, time.strftime("%a %-d %b", lt).upper(), cx, 22, 16, "fg", 1.0, W_.HEAVY, MONO, "c")
        else:
            T(cr, time.strftime("%A, %B %-d", lt), cx, 16, 17, "fg", 0.78, W_.MEDIUM, SANS, "c")
            T(cr, f"{hh:02d}", cx, 52, 178, "fg", 1.0, W_.HEAVY, SANS, "c", ink=True, sx=0.74)
            T(cr, f"{lt.tm_min:02d}", cx, 52 + 132 + 16, 178, "accent", 1.0, W_.HEAVY, SANS, "c", ink=True, sx=0.74)
        if self.opts.get("greeting", True):
            hr = lt.tm_hour
            part = "morning" if 5 <= hr < 12 else "afternoon" if 12 <= hr < 17 else "evening" if 17 <= hr < 22 else "night"
            T(cr, f"Good {part}, {self.desk.user}", cx, bh - 16, 16, "fg", 0.85, W_.MEDIUM, SANS, "c", "b")


# ---- pomodoro ---------------------------------------------------------------
class Pomodoro(Item):
    kind, title, icon = "pomodoro", "Pomodoro", G("f2f2")
    base = (260, 280)
    style0 = "glass"

    def __init__(self, desk, d):
        super().__init__(desk, d)
        self.work = int(self.opts.get("work", 25)) * 60
        self.brk = int(self.opts.get("break", 5)) * 60
        self.phase = "focus"
        self.left = self.work
        self.end = None           # monotonic end time while running
        self._run = None

    def total(self):
        return self.work if self.phase == "focus" else self.brk

    def remaining(self):
        if self.end is None:
            return self.left
        return max(self.end - time.monotonic(), 0)

    def toggle(self):
        if self.end is None:
            self.end = time.monotonic() + self.left
            self._run = GLib.timeout_add(250, self._step)
        else:
            self.left = self.remaining()
            self.end = None
        self.redraw()

    def reset(self):
        self.end = None
        self.phase = "focus"
        self.left = self.work
        self.redraw()

    def _step(self):
        if not self.alive or self.end is None:
            self._run = None
            return False
        if self.remaining() <= 0:
            done = self.phase
            self.phase = "break" if self.phase == "focus" else "focus"
            self.left = self.total()
            self.end = time.monotonic() + self.left
            try:
                subprocess.Popen(["notify-send", "-a", "rice-desk", "Pomodoro",
                                  "Focus done, take a break" if done == "focus" else "Break over, back to focus"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        self.redraw()
        return True

    def stop(self):
        super().stop()
        if self._run:
            try: GLib.source_remove(self._run)
            except Exception: pass
            self._run = None

    def geom(self):
        return 130, 128, 98       # cx, cy, R in design coords

    def paint(self, cr, w, h, preview=False):
        fit(cr, w, h, *self.base)
        cx, cy, R = self.geom()
        rem = self.remaining()
        frac = rem / max(self.total(), 1)
        running = self.end is not None
        dn = DN()
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        if dn == "material3":                           # scalloped cookie track, progress runs round it
            cr.set_line_width(9)
            cookie_path(cr, cx, cy, R, 12, 0.05)
            cr.set_source_rgba(*rgba("fg", 0.13)); cr.stroke()
            if frac > 0.001:
                cookie_path(cr, cx, cy, R, 12, 0.05, t1=frac)
                cr.set_source_rgba(*rgba("accent2" if self.phase == "break" else "accent", 1.0)); cr.stroke()
        elif dn == "macos":                             # thin smooth ring
            cr.set_line_width(6)
            cr.set_source_rgba(*rgba("fg", 0.14)); cr.arc(cx, cy, R, 0, 2 * math.pi); cr.stroke()
            if frac > 0.001:
                cr.set_source_rgba(*rgba("accent2" if self.phase == "break" else "accent", 1.0))
                cr.arc(cx, cy, R, -math.pi / 2, -math.pi / 2 + 2 * math.pi * frac); cr.stroke()
        elif dn == "brutal":                            # square frame
            cr.set_line_cap(cairo.LINE_CAP_BUTT); cr.set_line_width(10)
            rect_loop(cr, cx, cy, R - 4, 0.0, 1.0); cr.set_source_rgba(*rgba("fg", 0.18)); cr.stroke()
            if frac > 0.001:
                rect_loop(cr, cx, cy, R - 4, 0.0, frac)
                cr.set_source_rgba(*rgba("accent2" if self.phase == "break" else "accent", 1.0)); cr.stroke()
            cr.set_line_width(3); cr.rectangle(cx - R - 3, cy - R - 3, 2 * R + 6, 2 * R + 6)
            cr.set_source_rgba(*rgba("fg", 1.0)); cr.stroke()
        else:
            cr.set_line_width(9)
            cr.set_source_rgba(*rgba("fg", 0.13))
            cr.arc(cx, cy, R, 0, 2 * math.pi); cr.stroke()
        if dn == "default" and frac > 0.001:
            amp = 3.2 if running else 1.6
            ph = (time.monotonic() * 2.0) if running else 0.0
            a0 = -math.pi / 2
            n = max(int(180 * frac), 2)
            for i in range(n + 1):
                th = a0 + 2 * math.pi * frac * i / n
                r = R + amp * math.sin(th * 14 + ph)
                (cr.move_to if i == 0 else cr.line_to)(cx + r * math.cos(th), cy + r * math.sin(th))
            cr.set_source_rgba(*rgba("accent2" if self.phase == "break" else "accent", 1.0))
            cr.stroke()
        m, s = divmod(int(math.ceil(rem)), 60)
        T(cr, "BREAK" if self.phase == "break" else "FOCUS", cx, cy - 34, 12, "fg", 0.6, W_.BOLD, MONO, "c", "c")
        T(cr, f"{m:02d}:{s:02d}", cx, cy + 2, 44, "fg", 1.0, W_.BOLD, SANS, "c", "c", ink=True)
        # controls: reset (left) and play/pause (right), inside the ring
        for (bx, glyph) in ((cx - 24, G("f0e2")), (cx + 24, G("f04c") if running else G("f04b"))):
            cr.arc(bx, cy + 44, 15, 0, 2 * math.pi)
            cr.set_source_rgba(*rgba("fg", 0.12)); cr.fill()
            T(cr, glyph, bx, cy + 44, 13, "fg", 0.95, W_.NORMAL, ICON, "c", "c", ink=True)
        T(cr, "click to start" if not running and rem >= self.total() else ("running" if running else "paused"),
          cx, self.base[1] - 14, 12, "fg", 0.55, W_.NORMAL, MONO, "c", "b")

    def click(self, x, y, e):
        if e.button != 1:
            return False
        lx, ly = self.local(x, y)
        cx, cy, R = self.geom()
        if math.hypot(lx - (cx - 24), ly - (cy + 44)) < 18:
            self.reset(); return True
        if math.hypot(lx - cx, ly - cy) < R + 14:
            self.toggle(); return True
        return False


# ---- system -----------------------------------------------------------------
class System(Item):
    kind, title, icon = "system", "System", G("f4bc")
    base = (380, 150)
    style0 = "glass"

    def __init__(self, desk, d):
        super().__init__(desk, d)
        self.vals = [0.0, 0.0, 0.0]
        self._cpu = None

    def start(self):
        self._sample()
        self.every(2000, self._sample)

    def _sample(self):
        try:
            with open("/proc/stat") as f:
                v = [int(x) for x in f.readline().split()[1:9]]
            idle, tot = v[3] + v[4], sum(v)
            if self._cpu:
                di, dt = idle - self._cpu[0], tot - self._cpu[1]
                self.vals[0] = 1 - di / dt if dt > 0 else 0
            self._cpu = (idle, tot)
            mi = {}
            with open("/proc/meminfo") as f:
                for ln in f:
                    k, val = ln.split(":", 1)
                    mi[k] = int(val.split()[0])
                    if len(mi) > 4 and "MemAvailable" in mi:
                        break
            self.vals[1] = 1 - mi["MemAvailable"] / mi["MemTotal"]
            st = os.statvfs("/")
            used = st.f_blocks - st.f_bfree
            self.vals[2] = used / max(used + st.f_bavail, 1)
        except Exception:
            pass
        self.redraw()

    def paint(self, cr, w, h, preview=False):
        fit(cr, w, h, *self.base)
        labels = (("CPU", G("f4bc")), ("RAM", G("efc5")), ("DISK", G("f0a0")))
        vals = (0.34, 0.52, 0.61) if preview else self.vals
        dn = DN()
        hi = max(range(3), key=lambda k: vals[k])
        for i, ((lab, _ic), v) in enumerate(zip(labels, vals)):
            cx, cy, R = 70 + i * 120, 66, 42
            v = min(max(v, 0.0), 1.0)
            cr.new_path()                                  # T() leaves a current point: it drew a line to the next arc
            if dn == "material3":                      # scalloped cookie, the busiest one filled with the accent
                cookie_path(cr, cx, cy, R + 4, 10, 0.07)
                if i == hi:
                    cr.set_source_rgba(*rgba("accent", 1.0)); cr.fill()
                    ink = "bg"
                else:
                    cr.set_source_rgba(*rgba("fg", 0.10)); cr.fill()
                    ink = "fg"
                    if v > 0.01:
                        cr.set_line_width(3.5); cr.set_line_cap(cairo.LINE_CAP_ROUND)
                        cookie_path(cr, cx, cy, R + 1, 10, 0.07, t1=v)
                        cr.set_source_rgba(*rgba("accent", 1.0)); cr.stroke()
                T(cr, f"{int(round(v * 100))}%", cx, cy - 2, 22, ink, 1.0, W_.BOLD, SANS, "c", "c", ink=True)
                T(cr, lab, cx, cy + 17, 11, ink, 0.75, W_.MEDIUM, SANS, "c", "c")
                continue
            if dn == "macos":                          # thin full rings (Activity-ring style)
                cr.set_line_width(6); cr.set_line_cap(cairo.LINE_CAP_ROUND)
                cr.set_source_rgba(*rgba("fg", 0.14)); cr.arc(cx, cy, R, 0, 2 * math.pi); cr.stroke()
                if v > 0.005:
                    cr.set_source_rgba(*rgba("accent" if i != 1 else "accent2", 1.0))
                    cr.arc(cx, cy, R, -math.pi / 2, -math.pi / 2 + 2 * math.pi * v); cr.stroke()
                T(cr, f"{int(round(v * 100))}", cx, cy - 2, 26, "fg", 1.0, W_.LIGHT, SANS, "c", "c", ink=True)
                T(cr, lab, cx, cy + 20, 10, "fg", 0.6, W_.MEDIUM, SANS, "c", "c")
                continue
            if dn == "brutal":                         # boxed level meters
                bx, by, bs = cx - 40, cy - 46, 80
                cr.rectangle(bx + 5, by + 5, bs, bs); cr.set_source_rgba(*rgba("fg", 1.0)); cr.fill()
                cr.rectangle(bx, by, bs, bs); cr.set_source_rgba(*rgba("bg", 1.0)); cr.fill()
                cr.rectangle(bx, by + bs * (1 - v), bs, bs * v); cr.set_source_rgba(*rgba("accent", 1.0)); cr.fill()
                cr.rectangle(bx, by, bs, bs); cr.set_source_rgba(*rgba("fg", 1.0)); cr.set_line_width(3); cr.stroke()
                T(cr, f"{int(round(v * 100))}", cx, cy - 6, 28, "fg", 1.0, W_.HEAVY, MONO, "c", "c", ink=True)
                T(cr, lab, cx, 132, 12, "fg", 1.0, W_.HEAVY, MONO, "c", "c")
                continue
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_line_width(8)
            cr.set_source_rgba(*rgba("fg", 0.13))
            cr.arc(cx, cy, R, math.radians(135), math.radians(405)); cr.stroke()
            if v > 0.005:
                cr.set_source_rgba(*rgba("accent" if v < 0.85 else "accent2", 1.0))
                cr.arc(cx, cy, R, math.radians(135), math.radians(135 + 270 * min(v, 1.0))); cr.stroke()
            T(cr, f"{int(round(v * 100))}", cx, cy, 24, "fg", 1.0, W_.BOLD, SANS, "c", "c", ink=True)
            T(cr, "%", cx + 1, cy + 22, 10, "fg", 0.6, W_.NORMAL, MONO, "c", "c")
            T(cr, lab, cx, 132, 12, "fg", 0.75, W_.BOLD, MONO, "c", "c")


# ---- calendar ---------------------------------------------------------------
class Calendar(Item):
    kind, title, icon = "calendar", "Calendar", G("f073")
    base = (300, 290)
    style0 = "glass"

    def __init__(self, desk, d):
        super().__init__(desk, d)
        self.off = 0
        self._day = None
        self._scrolled = 0

    def start(self):
        self._day = time.localtime().tm_yday
        self.every(30000, self._check)

    def _check(self):
        lt = time.localtime()
        if self.off and time.monotonic() - self._scrolled > 45:
            self.off = 0; self.redraw()
        if lt.tm_yday != self._day:
            self._day = lt.tm_yday; self.redraw()

    def scroll(self, up):
        self.off += -1 if up else 1
        self._scrolled = time.monotonic()
        self.redraw()
        return True

    def paint(self, cr, w, h, preview=False):
        import calendar
        fit(cr, w, h, *self.base)
        lt = time.localtime()
        y, m = lt.tm_year, lt.tm_mon + self.off
        while m < 1: m += 12; y -= 1
        while m > 12: m -= 12; y += 1
        T(cr, f"{calendar.month_name[m]}", 22, 20, 20, "fg", 1.0, W_.BOLD, SANS)
        T(cr, f"{y}", self.base[0] - 22, 22, 15, "accent", 1.0, W_.MEDIUM, SANS, "r")
        cw, top = 36.6, 66
        for i, dn in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            T(cr, dn, 22 + cw * i + cw / 2 - 2, top, 11, "fg", 0.5 if i < 5 else 0.7, W_.BOLD, MONO, "c")
        weeks = calendar.Calendar(0).monthdatescalendar(y, m)
        for r, wk in enumerate(weeks):
            for i, dt in enumerate(wk):
                x = 22 + cw * i + cw / 2 - 2
                yy = top + 34 + r * 31
                today = (dt.year, dt.month, dt.day) == (lt.tm_year, lt.tm_mon, lt.tm_mday)
                if today:
                    dn_ = DN()
                    cr.new_path()
                    if dn_ == "material3":
                        cookie_path(cr, x, yy, 15, 8, 0.07)
                    elif dn_ == "brutal":
                        cr.rectangle(x - 14, yy - 14, 28, 28)
                    elif dn_ == "macos":
                        cr.arc(x, yy, 13, 0, 2 * math.pi)
                    else:
                        cr.arc(x, yy, 14, 0, 2 * math.pi)
                    cr.set_source_rgba(*rgba("accent", 1.0)); cr.fill()
                a = 1.0 if dt.month == m else 0.28
                T(cr, str(dt.day), x, yy, 13, "bg" if today else "fg", a, W_.BOLD if today else W_.NORMAL, MONO, "c", "c")


# ---- media (MPRIS) ----------------------------------------------------------
class Media(Item):
    kind, title, icon = "media", "Media", G("f001")
    base = (400, 140)
    style0 = "glass"

    def __init__(self, desk, d):
        super().__init__(desk, d)
        self.info = None
        self.player = None
        self.cover = None
        self._cover_url = None
        self._pend = None
        self._prog = None
        self._subs = []
        self.hidden = True

    def start(self):
        try:
            import mpris
            from gi.repository import Gio
            self.mp = mpris
            bus = mpris.BUS
            self._subs.append(bus.signal_subscribe(None, "org.freedesktop.DBus.Properties", "PropertiesChanged",
                                                   "/org/mpris/MediaPlayer2", None, Gio.DBusSignalFlags.NONE,
                                                   lambda *a: self.soon(), None))
            self._subs.append(bus.signal_subscribe("org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged",
                                                   "/org/freedesktop/DBus", "org.mpris.MediaPlayer2", Gio.DBusSignalFlags.MATCH_ARG0_NAMESPACE,
                                                   lambda *a: self.soon(), None))
        except Exception as ex:
            print("rice-desk media", ex, file=sys.stderr)
            self.mp = None
        self.refresh()
        self.every(10000, self.refresh)

    def stop(self):
        super().stop()
        try:
            for s in self._subs:
                self.mp.BUS.signal_unsubscribe(s)
        except Exception:
            pass
        self._subs = []
        if self._prog:
            GLib.source_remove(self._prog); self._prog = None

    def soon(self):
        if self._pend is None:
            self._pend = GLib.timeout_add(150, self._soon)

    def _soon(self):
        self._pend = None
        self.refresh()
        return False

    def refresh(self):
        if not self.alive or self.mp is None:
            return
        mp = self.mp
        info = None
        try:
            p = mp.active()
            if p:
                md = mp.get(p, "Metadata")
                ar = md.get("xesam:artist", [])
                st = mp.get(p, "PlaybackStatus")
                try: pos = int(mp.get(p, "Position"))
                except Exception: pos = 0
                info = dict(title=str(md.get("xesam:title", "") or "Unknown"),
                            artist=", ".join(ar) if isinstance(ar, list) else str(ar),
                            length=max(int(md.get("mpris:length", 0) or 0), 0), pos=pos, t=time.monotonic(),
                            playing=st == "Playing", status=st, url=str(md.get("mpris:artUrl", "") or ""))
                self.player = p
                if info["status"] == "Stopped" and not info["title"]:
                    info = None
        except Exception:
            info = None
        self.info = info
        if info and info["url"] != self._cover_url:
            self._cover_url = info["url"]
            self.cover = None
            self._load_cover(info["url"])
        want_hidden = info is None
        if want_hidden != self.hidden:
            self.hidden = want_hidden
            if not self.desk.editing:
                if want_hidden:
                    self.hide_win()
                else:
                    self.show()
        if info and info["playing"] and self._prog is None:
            self._prog = GLib.timeout_add(1000, self._progress)
        self.redraw()

    def _progress(self):
        if not self.alive or not self.info or not self.info["playing"]:
            self._prog = None
            return False
        self.redraw()
        return True

    def _load_cover(self, url):
        mp = self.mp

        def done(path):
            if path and url == self._cover_url:
                try:
                    from gi.repository import GdkPixbuf
                    self.cover = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 220, 220, True)
                except Exception:
                    self.cover = None
                self.redraw()
            return False
        p = mp.art_path(url, net=False)
        if p or not url.startswith("http"):
            done(p)
            return
        threading.Thread(target=lambda: GLib.idle_add(done, mp.art_path(url, net=True)), daemon=True).start()

    def btns(self):
        return ((174, G("f04a"), "Previous"), (214, "pp", "PlayPause"), (254, G("f04e"), "Next"))

    def paint(self, cr, w, h, preview=False):
        fit(cr, w, h, *self.base)
        info = self.info
        if preview and not info:
            info = dict(title="Midnight City", artist="M83", length=240e6, pos=90e6, t=time.monotonic(), playing=True)
        x0, y0, cs = 20, 20, 100
        dn = DN()
        if dn == "material3":
            cookie_path(cr, x0 + cs / 2, y0 + cs / 2, cs / 2, 8, 0.06)
        elif dn == "brutal":
            cr.rectangle(x0, y0, cs, cs)
        else:
            rice.rounded(cr, x0, y0, cs, cs, 24 if dn == "macos" else 16)
        if self.cover is not None and not preview:
            cr.save(); cr.clip()
            pw, ph = self.cover.get_width(), self.cover.get_height()
            sc = cs / min(pw, ph)
            cr.translate(x0 + (cs - pw * sc) / 2, y0 + (cs - ph * sc) / 2); cr.scale(sc, sc)
            Gdk.cairo_set_source_pixbuf(cr, self.cover, 0, 0); cr.paint()
            cr.restore()
        else:
            g = cairo.LinearGradient(x0, y0, x0 + cs, y0 + cs)
            g.add_color_stop_rgba(0, *rgba("accent", 0.9)); g.add_color_stop_rgba(1, *rgba("accent2", 0.9))
            cr.set_source(g); cr.fill()
            T(cr, G("f001"), x0 + cs / 2, y0 + cs / 2, 34, "bg", 0.9, W_.NORMAL, ICON, "c", "c", ink=True)
        if dn == "brutal":
            cr.rectangle(x0, y0, cs, cs); cr.set_source_rgba(*rgba("fg", 1.0)); cr.set_line_width(3); cr.stroke()
        tx = 140
        if not info:
            T(cr, "Nothing playing", tx, 40, 17, "fg", 0.9, W_.BOLD, SANS)
            T(cr, "media widget hides itself", tx, 66, 12, "fg", 0.55, W_.NORMAL, MONO)
            return
        T(cr, info["title"], tx, 22, 17, "fg", 1.0, W_.BOLD, SANS, width=self.base[0] - tx - 18)
        T(cr, info["artist"] or " ", tx, 47, 13, "fg", 0.65, W_.NORMAL, SANS, width=self.base[0] - tx - 18)
        L = info["length"]
        if L > 0:
            pos = info["pos"] + ((time.monotonic() - info["t"]) * 1e6 if info["playing"] else 0)
            f = min(max(pos / L, 0), 1)
            bw = self.base[0] - tx - 22
            if dn == "material3":                       # wavy played part, straight rest
                xe = tx + bw * f
                cr.set_line_width(3); cr.set_line_cap(cairo.LINE_CAP_ROUND)
                cr.set_source_rgba(*rgba("fg", 0.18)); cr.move_to(xe, 78); cr.line_to(tx + bw, 78); cr.stroke()
                ph0 = time.monotonic() * 3 if info["playing"] else 0.0
                cr.new_path()
                for k in range(int(max(xe - tx, 1)) + 1):
                    (cr.move_to if k == 0 else cr.line_to)(tx + k, 78 + 2.6 * math.sin(k * 0.42 - ph0))
                cr.set_source_rgba(*rgba("accent", 1)); cr.stroke()
            elif dn == "brutal":
                cr.rectangle(tx, 72, bw, 10); cr.set_source_rgba(*rgba("bg", 1)); cr.fill_preserve()
                cr.set_source_rgba(*rgba("fg", 1)); cr.set_line_width(3); cr.stroke()
                cr.rectangle(tx, 72, max(bw * f, 2), 10); cr.set_source_rgba(*rgba("accent", 1)); cr.fill()
            else:
                th = 6 if dn == "macos" else 4
                rice.rounded(cr, tx, 78 - th / 2, bw, th, th / 2); cr.set_source_rgba(*rgba("fg", 0.15)); cr.fill()
                if f > 0:
                    rice.rounded(cr, tx, 78 - th / 2, max(bw * f, th), th, th / 2); cr.set_source_rgba(*rgba("accent", 1)); cr.fill()
        for bx, g_, _m in self.btns():
            glyph = (G("f04c") if info["playing"] else G("f04b")) if g_ == "pp" else g_
            if g_ == "pp":
                cr.arc(bx, 108, 17, 0, 2 * math.pi); cr.set_source_rgba(*rgba("fg", 0.92)); cr.fill()
                T(cr, glyph, bx + (0 if info["playing"] else 1), 108, 13, "bg", 1.0, W_.NORMAL, ICON, "c", "c", ink=True)
            else:
                T(cr, glyph, bx, 108, 14, "fg", 0.85, W_.NORMAL, ICON, "c", "c", ink=True)

    def click(self, x, y, e):
        if e.button != 1 or not self.info or not self.player:
            return False
        lx, ly = self.local(x, y)
        for bx, _g, m in self.btns():
            if abs(lx - bx) < 18 and abs(ly - 108) < 18:
                self.mp.call(self.player, m)
                GLib.timeout_add(200, lambda: (self.refresh(), False)[1])
                return True
        return False


# ---- visualizer (cava) ------------------------------------------------------
class Visualizer(Item):
    kind, title, icon = "visualizer", "Visualizer", G("f0a1")
    base = (600, 160)
    style0 = "bare"
    free = True
    N = 24

    def __init__(self, desk, d):
        super().__init__(desk, d)
        self.vals = [0] * self.N

    def feed(self, vals):
        if vals != self.vals:
            self.vals = vals
            self.redraw()

    def start(self):
        self.desk.cava_need()

    def render(self, cr, w, h, preview=False):
        if self.style == "glass":
            glass(cr, w, h)
            self.paint(cr, w, h, preview)
        else:
            shadowed(cr, w, h, lambda c: self.paint(c, w, h, preview), k=4, a=0.45)

    def paint(self, cr, w, h, preview=False):
        n = self.N
        vals = self.vals
        if preview or (not self.desk.cava_ok and not any(vals)):
            vals = [int(1000 * (0.18 + 0.5 * abs(math.sin(i * 0.55 + 0.7)) * (1 - abs(i - n / 2) / n))) for i in range(n)] if preview else vals
        pad = 16 if self.style == "glass" else 4
        slot = (w - 2 * pad) / n
        bw = max(slot * 0.58, 2)
        col = rgba("fg", 0.95) if self.style == "glass" else (1, 1, 1, 0.92)
        cr.set_source_rgba(*col)
        H = h - 2 * pad
        dn = DN()
        if dn == "macos":
            bw = max(slot * 0.34, 2)
        elif dn == "brutal":
            bw = max(slot * 0.82, 3)
        for i, v in enumerate(vals[:n]):
            bh = max(bw, H * min(v, 1000) / 1000.0)
            x = pad + slot * i + (slot - bw) / 2
            if dn == "brutal":
                cr.rectangle(x, pad + H - bh, bw, bh)
            else:
                rice.rounded(cr, x, pad + H - bh, bw, bh, bw / 2)
        cr.fill()


class Cava:
    """One cava process (raw ascii on stdout) shared by all visualizer widgets."""

    def __init__(self, desk):
        self.desk = desk
        self.p = None
        self.buf = b""
        self.watch = None
        self.fails = 0

    def start(self):
        if self.p is not None:
            return True
        exe = GLib.find_program_in_path("cava")
        if not exe:
            return False
        run = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
        cfg = os.path.join(run, f"rice-desk-cava-{os.getpid()}.conf")
        with open(cfg, "w") as f:
            f.write(f"""[general]
bars = {Visualizer.N}
framerate = 60
sleep_timer = 2
[output]
method = raw
raw_target = /dev/stdout
data_format = ascii
ascii_max_range = 1000
bar_delimiter = 59
frame_delimiter = 10
channels = mono
mono_option = average
[smoothing]
noise_reduction = 77
""")
        self.cfg = cfg

        def pdeath():
            try:
                import ctypes
                ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM)
            except Exception:
                pass
        try:
            self.p = subprocess.Popen([exe, "-p", cfg], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                      stdin=subprocess.DEVNULL, preexec_fn=pdeath)
        except Exception:
            self.p = None
            return False
        fd = self.p.stdout.fileno()
        os.set_blocking(fd, False)
        ch = GLib.IOChannel.unix_new(fd)
        self.watch = GLib.io_add_watch(ch, GLib.PRIORITY_DEFAULT, GLib.IOCondition.IN | GLib.IOCondition.HUP | GLib.IOCondition.ERR, self._read)
        return True

    def _read(self, ch, cond):
        try:
            data = os.read(self.p.stdout.fileno(), 65536)
        except BlockingIOError:
            return True
        except Exception:
            data = b""
        if not data:
            self._died()
            return False
        self.buf += data
        if b"\n" not in self.buf:
            return True
        lines = self.buf.split(b"\n")
        self.buf = lines[-1]
        last = lines[-2]
        try:
            vals = [int(x) for x in last.decode().strip().rstrip(";").split(";") if x != ""]
        except Exception:
            return True
        if len(vals) >= Visualizer.N:
            for it in self.desk.items:
                if isinstance(it, Visualizer) and not it.hidden:
                    it.feed(vals[:Visualizer.N])
        return True

    def _died(self):
        self.stop()
        self.fails += 1
        if self.fails < 6 and any(isinstance(i, Visualizer) for i in self.desk.items):
            GLib.timeout_add(2000 * self.fails, lambda: (self.start(), False)[1])

    def stop(self):
        if self.watch:
            try: GLib.source_remove(self.watch)
            except Exception: pass
            self.watch = None
        if self.p is not None:
            try:
                self.p.terminate(); self.p.wait(timeout=1)
            except Exception:
                try: self.p.kill()
                except Exception: pass
            self.p = None
        try: os.remove(self.cfg)
        except Exception: pass


# ---- note -------------------------------------------------------------------
class Note(Item):
    kind, title, icon = "note", "Note", G("f249")
    base = (260, 200)
    style0 = "glass"
    free = True

    def __init__(self, desk, d):
        super().__init__(desk, d)
        self.editing = False
        self._blink = None
        self.caret = True

    def paint(self, cr, w, h, preview=False):
        text = self.opts.get("text", "")
        if preview and not text:
            text = "buy milk\nrender the donut\ncall mum"
        T(cr, G("f249"), 20, 18, 13, "accent", 1.0, W_.NORMAL, ICON)
        T(cr, "note", 40, 17, 12, "fg", 0.55, W_.BOLD, MONO)
        if self.editing:
            T(cr, "Esc to save", w - 18, 17, 11, "accent", 0.9, W_.NORMAL, MONO, "r")
        shown = text + ("▏" if self.editing and self.caret else ("" if self.editing else ""))
        if not text and not self.editing:
            T(cr, "Double-click to write…", 20, 46, 14, "fg", 0.45, W_.NORMAL, MONO, width=w - 40, wrap=True)
        else:
            cr.save()
            cr.rectangle(0, 40, w, h - 54); cr.clip()
            T(cr, shown or " ", 20, 46, 14, "fg", 0.95, W_.NORMAL, MONO, width=w - 40, wrap=True)
            cr.restore()
        if self.editing:
            rice.rounded(cr, 6, 6, w - 12, h - 12, RADIUS - 6)
            cr.set_source_rgba(*rgba("accent", 0.55)); cr.set_line_width(1.5); cr.stroke()

    def click(self, x, y, e):
        if self.editing:
            if not (0 <= x <= self.w and 0 <= y <= self.h):
                self.finish()
            return True
        if e.button == 1 and e.type == Gdk.EventType._2BUTTON_PRESS:
            self.begin()
            return True
        return False

    def begin(self):
        if self.editing or self.win is None:
            return
        self.editing = True
        gdk_raise(self.win)
        self._grab(0)
        self._blink = GLib.timeout_add(530, self._blinkf)
        self.redraw()

    def _grab(self, n):
        seat = Gdk.Display.get_default().get_default_seat()
        ok = seat.grab(self.win.get_window(), Gdk.SeatCapabilities.ALL, True, None, None, None) == Gdk.GrabStatus.SUCCESS
        if not ok and n < 20:
            GLib.timeout_add(50, lambda: (self._grab(n + 1), False)[1])

    def _blinkf(self):
        if not self.editing:
            self._blink = None
            return False
        self.caret = not self.caret
        self.redraw()
        return True

    def finish(self):
        if not self.editing:
            return
        self.editing = False
        Gdk.Display.get_default().get_default_seat().ungrab()
        if self._blink:
            GLib.source_remove(self._blink); self._blink = None
        if not self.desk.editing:
            gdk_lower(self.win)
        self.desk.save()
        self.redraw()

    def key(self, e):
        if not self.editing:
            return False
        k = e.keyval
        ctrl = e.state & Gdk.ModifierType.CONTROL_MASK
        t = self.opts.get("text", "")
        if k == Gdk.KEY_Escape or (ctrl and k in (Gdk.KEY_Return, Gdk.KEY_KP_Enter)):
            self.finish(); return True
        if k == Gdk.KEY_BackSpace:
            t = t[:-1]
        elif k in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            t += "\n"
        elif ctrl and k in (Gdk.KEY_v, Gdk.KEY_V):
            s = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text() or ""
            t += s
        elif ctrl and k in (Gdk.KEY_u, Gdk.KEY_U):
            t = ""
        else:
            u = Gdk.keyval_to_unicode(k)
            if u and u >= 32 and not ctrl:
                t += chr(u)
            else:
                return True
        self.opts["text"] = t[:2000]
        self.caret = True
        self.redraw()
        return True


# ---- fetch ------------------------------------------------------------------
ART = r""" _-----_
(       \
\    0   \
 \        )
 /      _/
(     _-
\____-"""


class Fetch(Item):
    kind, title, icon = "fetch", "Fetch", G("f120")
    base = (470, 224)
    style0 = "glass"

    def __init__(self, desk, d):
        super().__init__(desk, d)
        self.lines = []
        self._static = None

    def start(self):
        self._collect()
        self.every(60000, self._collect)

    def _static_info(self):
        if self._static:
            return self._static
        osn = "Linux"
        try:
            for ln in open("/etc/os-release"):
                if ln.startswith("PRETTY_NAME="):
                    osn = ln.split("=", 1)[1].strip().strip("\"'"); break
        except Exception:
            pass
        cpu = "?"
        try:
            for ln in open("/proc/cpuinfo"):
                if ln.startswith("model name"):
                    cpu = ln.split(":", 1)[1].strip()
                    for junk in ("(R)", "(TM)", " CPU", " Processor"):
                        cpu = cpu.replace(junk, "")
                    cpu = " ".join(cpu.split()).split(" @")[0]
                    break
        except Exception:
            pass
        self._static = dict(os=osn, cpu=cpu, kernel=os.uname().release, host=os.uname().nodename,
                            shell=os.path.basename(os.environ.get("SHELL", "sh")))
        return self._static

    def _pkgs(self):
        n = 0
        try:
            with os.scandir("/var/db/pkg") as cats:
                for c in cats:
                    if c.is_dir():
                        n += sum(1 for _ in os.scandir(c.path))
        except Exception:
            return None
        return n

    def _collect(self):
        s = self._static_info()
        try:
            up = int(float(open("/proc/uptime").read().split()[0]))
        except Exception:
            up = 0
        d, r = divmod(up, 86400); hh, r = divmod(r, 3600); mm = r // 60
        upt = (f"{d}d " if d else "") + (f"{hh}h " if hh or d else "") + f"{mm}m"
        mem = "?"
        try:
            mi = {}
            for ln in open("/proc/meminfo"):
                k, v = ln.split(":", 1); mi[k] = int(v.split()[0])
                if "MemAvailable" in mi and "MemTotal" in mi: break
            mem = f"{(mi['MemTotal'] - mi['MemAvailable']) / 1048576:.1f} / {mi['MemTotal'] / 1048576:.1f} GiB"
        except Exception:
            pass
        pk = self._pkgs()
        self.lines = [("os", s["os"]), ("kernel", s["kernel"]), ("uptime", upt),
                      ("pkgs", f"{pk} (emerge)" if pk is not None else "?"), ("wm", "dwm"),
                      ("shell", s["shell"]), ("cpu", s["cpu"]), ("mem", mem)]
        self.redraw()

    def paint(self, cr, w, h, preview=False):
        fit(cr, w, h, *self.base)
        s = self._static_info()
        if not self.lines:
            self._collect()
        T(cr, f"{self.desk.user}@{s['host']}", 20, 16, 13, "accent", 1.0, W_.BOLD, MONO)
        T(cr, " ~ $ fetch", 20 + T(cr, f"{self.desk.user}@{s['host']}", -9999, 0, 13, "accent", 0, W_.BOLD, MONO)[0], 16, 13, "fg", 0.7, W_.NORMAL, MONO)
        for i, ln in enumerate(ART.split("\n")):
            T(cr, ln, 22, 50 + i * 17, 13, "accent2", 1.0, W_.BOLD, MONO)
        kx = 160
        for i, (k, v) in enumerate(self.lines):
            y = 44 + i * 18
            T(cr, k, kx, y, 12.5, "accent", 1.0, W_.BOLD, MONO)
            T(cr, v, kx + 62, y, 12.5, "fg", 0.92, W_.NORMAL, MONO, width=self.base[0] - kx - 62 - 16)
        for i, k in enumerate(("bg2", "border", "dim", "fg", "accent", "accent2")):
            rice.rounded(cr, 22 + i * 20, self.base[1] - 34, 16, 16, 5)
            cr.set_source_rgba(*rgba(k, 1.0)); cr.fill()


KINDS = dict(clock=Clock, pomodoro=Pomodoro, system=System, calendar=Calendar, media=Media,
             visualizer=Visualizer, note=Note, fetch=Fetch)
ORDER = ("clock", "visualizer", "system", "calendar", "media", "pomodoro", "note", "fetch")


# ---- edit mode overlay + hint pill -----------------------------------------
class Overlay(Gtk.Window):
    """Full-monitor, input-transparent, only partly repainted (queue_draw_area) layer for edit mode."""

    def __init__(self, desk, m):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.desk, self.m = desk, m
        self.set_wmclass("rice-desk", "RiceDeskOverlay")
        self.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
        self.set_app_paintable(True)
        vis = self.get_screen().get_rgba_visual()
        if vis:
            self.set_visual(vis)
        self.set_default_size(m["w"], m["h"])
        self.set_size_request(m["w"], m["h"])
        self.move(m["x"], m["y"])
        self.connect("draw", self._draw)
        self.realize()
        self.get_window().set_background_rgba(Gdk.RGBA(0, 0, 0, 0))
        self.input_shape_combine_region(cairo.Region())
        self.show()

    def _draw(self, w, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.translate(-self.m["x"], -self.m["y"])
        try:
            self.desk.draw_overlay(cr, self.m)
        except Exception as ex:
            print("rice-desk overlay", ex, file=sys.stderr)
        return True

    def damage(self, r):
        x, y, w, h = r
        m = self.m
        x0, y0 = max(int(x) - m["x"], 0), max(int(y) - m["y"], 0)
        x1, y1 = min(int(math.ceil(x + w)) - m["x"], m["w"]), min(int(math.ceil(y + h)) - m["y"], m["h"])
        if x1 > x0 and y1 > y0:
            self.queue_draw_area(x0, y0, x1 - x0, y1 - y0)


HINT = "Drag to move · pull a corner to resize · arrows nudge · Delete removes · Esc to finish"
HINT2 = "Tab next · b bare/glass · a add"


class Pill(Gtk.Window):
    def __init__(self, desk):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.desk = desk
        self.set_wmclass("rice-desk", "RiceDeskGlass" + SFX)
        self.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
        self.set_app_paintable(True)
        vis = self.get_screen().get_rgba_visual()
        if vis:
            self.set_visual(vis)
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4)
        c = cairo.Context(s)
        w1 = T(c, HINT, 0, 0, 13, "fg", 0, W_.MEDIUM, MONO)[0]
        w2 = T(c, HINT2, 0, 0, 12, "fg", 0, W_.NORMAL, MONO)[0]
        self.w1, self.w2 = w1, w2
        self.W, self.H = int(w1 + w2 + 26 + 30 * 2 + 30), 44
        self.set_default_size(self.W, self.H)
        self.set_size_request(self.W, self.H)
        self.add_events(Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("draw", self._draw)
        self.connect("key-press-event", lambda w, e: desk.on_key(None, e))
        self.realize()
        self.get_window().set_background_rgba(Gdk.RGBA(0, 0, 0, 0))

    def place(self):
        px, py = pointer()
        m = mon_at(px, py)
        self.x = m["x"] + (m["w"] - self.W) // 2
        self.y = m["y"] + m["h"] - self.H - 28
        return self.x, self.y

    def _draw(self, w, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0); cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        glass(cr, self.W, self.H, self.H / 2)
        x = 30
        T(cr, G("f044"), x - 4, self.H / 2, 14, "accent", 1.0, W_.NORMAL, ICON, "c", "c", ink=True)
        x += 18
        T(cr, HINT, x, self.H / 2, 13, "fg", 0.95, W_.MEDIUM, MONO, "l", "c")
        x += self.w1 + 26
        cr.set_source_rgba(*rgba("fg", 0.25)); cr.rectangle(x - 13, 13, 1, self.H - 26); cr.fill()
        T(cr, HINT2, x, self.H / 2, 12, "fg", 0.6, W_.NORMAL, MONO, "l", "c")
        return True


# ---- add picker -------------------------------------------------------------
def pick_kind(desk):
    """Glass card with a preview tile per widget kind. Runs a nested main loop; returns a kind or None."""
    import widgets
    cols, tw, th = 4, 200, 132
    W = cols * (tw + 14) + 34
    rows = (len(ORDER) + cols - 1) // cols
    H = 78 + rows * (th + 36) + 14
    card = rice.Card(W, H)
    sel = [0]
    res = [None]
    fakes = {k: KINDS[k](desk, dict(id="preview", kind=k)) for k in ORDER}
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.set_margin_top(20); box.set_margin_start(17); box.set_margin_end(17)
    t = Gtk.Label(xalign=0)
    t.set_markup('<span size="15000" weight="bold">Add a widget</span>   <span size="10500" alpha="60%">click, or arrows + Enter</span>')
    box.pack_start(t, False, False, 0)
    grid = Gtk.Grid(column_spacing=14, row_spacing=8)
    grid.set_margin_top(16)
    box.pack_start(grid, False, False, 0)
    tiles = []

    def choose(i):
        if res[0] is None:
            res[0] = ORDER[i]
            card.quit_anim()

    for i, k in enumerate(ORDER):
        da = Gtk.DrawingArea()
        da.set_size_request(tw, th + 28)
        da.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.ENTER_NOTIFY_MASK)

        def draw(w, cr, i=i, k=k):
            it = fakes[k]
            on = sel[0] == i
            rice.rounded(cr, 1, 1, tw - 2, th - 2, 16)
            cr.set_source_rgba(*rgba("fg", 0.10 if on else 0.05)); cr.fill_preserve()
            cr.set_source_rgba(*rgba("accent", 0.9 if on else 0.18)); cr.set_line_width(2 if on else 1); cr.stroke()
            bw, bh = it.base
            pad = 12
            sc = min((tw - 2 * pad) / bw, (th - 2 * pad) / bh)
            pw, ph = bw * sc, bh * sc
            cr.save()
            cr.translate((tw - pw) / 2, (th - ph) / 2)
            cr.scale(sc, sc)
            if it.style0 == "glass":
                glass(cr, bw, bh)
            it.paint(cr, bw, bh, preview=True)
            cr.restore()
            T(cr, it.icon, 10, th + 14, 12, "accent", 1.0, W_.NORMAL, ICON, "l", "c", ink=True)
            T(cr, it.title, 30, th + 14, 13, "fg", 0.95 if on else 0.7, W_.BOLD, MONO, "l", "c")
            return False
        da.connect("draw", draw)
        da.connect("button-press-event", lambda w, e, i=i: (choose(i), True)[1])

        def enter(w, e, i=i):
            sel[0] = i
            for t_ in tiles: t_.queue_draw()
        da.connect("enter-notify-event", enter)
        grid.attach(da, i % cols, i // cols, 1, 1)
        tiles.append(da)
    card.add(box)

    def key(w, e):
        k = e.keyval
        n = len(ORDER)
        if k in (Gdk.KEY_Right, Gdk.KEY_l): sel[0] = (sel[0] + 1) % n
        elif k in (Gdk.KEY_Left, Gdk.KEY_h): sel[0] = (sel[0] - 1) % n
        elif k in (Gdk.KEY_Down, Gdk.KEY_j): sel[0] = min(sel[0] + cols, n - 1)
        elif k in (Gdk.KEY_Up, Gdk.KEY_k): sel[0] = max(sel[0] - cols, 0)
        elif k in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space): choose(sel[0]); return True
        else: return False
        for t_ in tiles: t_.queue_draw()
        return True
    card.add_events(Gdk.EventMask.KEY_PRESS_MASK)
    card.connect("key-press-event", key)
    widgets.close_on_outside(card)
    x, y, _g = widgets.mon_center(W, H)
    card.origin = (x + W // 2, y + H // 2)
    card.move(x, y)
    card.show_all()
    widgets.grab_keys(card)
    loop = GLib.MainLoop()
    _LOOPS.append(loop)
    try:
        loop.run()                   # Card.quit_anim -> Gtk.main_quit (patched in run()) ends this nested loop
    finally:
        _LOOPS.remove(loop)
    try:
        Gdk.Display.get_default().get_default_seat().ungrab()
        card.destroy()
    except Exception:
        pass
    return res[0]


# ---- the desk -----------------------------------------------------------------
class Desk:
    def __init__(self):
        import pwd
        try:
            g = pwd.getpwuid(os.getuid())
            self.user = (g.pw_gecos.split(",")[0].split()[0] if g.pw_gecos.strip(", ") else g.pw_name)
        except Exception:
            self.user = os.environ.get("USER", "you")
        self.items = []
        self.editing = False
        self.sel = None
        self.drag = None
        self.overlays = []
        self.pill = None
        self.guides = []
        self.preview = None       # (item, x, y, w, h) while resizing
        self._dmg = []
        self.sel_anim = None
        self.cava = Cava(self)
        self.cava_ok = False
        self.picking = False
        self._cmtime = self._colors_mtime()
        self.cursors = {}

    # -- layout
    def load_layout(self):
        try:
            data = json.load(open(STATE))
            ws = data.get("widgets", data) if isinstance(data, dict) else data
        except Exception:
            ws = None
        if not ws:
            ws = self.default_layout()
        return [w for w in ws if isinstance(w, dict) and w.get("kind") in KINDS]

    def default_layout(self):
        m = primary()
        def at(kind, x, y, w, h, style):
            return dict(id=f"{kind}-1", kind=kind, mon=m["name"], origin=[m["x"], m["y"]], x=x, y=y, w=w, h=h, style=style, opts={})
        return [at("clock", 90, max((m["h"] - 400) // 2 - 30, TOP), 300, 400, "bare"),
                at("system", m["w"] - 380 - 90, TOP + 40, 380, 150, "glass"),
                at("visualizer", (m["w"] - 600) // 2, m["h"] - 160 - 96, 600, 160, "bare")]

    def resolve(self, d):
        ms = monitors()
        mon = d.get("mon")
        m = None
        if isinstance(mon, str):
            m = next((x for x in ms if x["name"] == mon), None)
        if m is None:
            org = d.get("origin") or (mon if isinstance(mon, list) else None)
            if org:
                m = next((x for x in ms if [x["x"], x["y"]] == list(org)), None)
        if m is None:
            m = next(x for x in ms if x["primary"])
        x = m["x"] + int(d.get("x", 100))
        y = m["y"] + int(d.get("y", 100))
        return self.clamp(x, y, int(d.get("w", 200)), int(d.get("h", 200)), m)

    def clamp(self, x, y, w, h, m=None):
        m = m or mon_at(x + w // 2, y + h // 2)
        x = min(max(x, m["x"]), m["x"] + m["w"] - min(w, m["w"]))
        y = min(max(y, m["y"]), m["y"] + m["h"] - min(h, m["h"]))
        return x, y

    def save(self):
        ws = []
        for it in self.items:
            it.d = it.to_dict()
            ws.append(it.d)
        data = dict(version=1, widgets=ws)
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        tmp = STATE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, STATE)

    def make(self, d):
        it = KINDS[d["kind"]](self, d)
        it.x, it.y = self.resolve(d)
        return it

    def start(self, initial=None):
        for i, d in enumerate(self.load_layout()):
            it = self.make(d)
            self.items.append(it)
            it.build()
            it.start()
            it.show(anim=True, delay=0.07 * i)
        if not os.path.exists(STATE):
            self.save()
        GLib.timeout_add(2000, self._watch_colors)
        Gdk.Screen.get_default().connect("monitors-changed", lambda *a: GLib.timeout_add(500, self._remonitor))
        if initial:
            GLib.timeout_add(500, lambda: (self.command(initial), False)[1])

    def _remonitor(self):
        if self.editing:
            self.finish_edit()
        for it in self.items:
            it.x, it.y = self.resolve(it.d)
            it.place()
        return False

    def reload(self):
        if self.editing:
            self.finish_edit(save=False)
        for it in self.items:
            it.destroy()
        self.items = []
        self.cava.stop()
        self.recolor()
        for i, d in enumerate(self.load_layout()):
            it = self.make(d)
            self.items.append(it)
            it.build(); it.start(); it.show(anim=True, delay=0.05 * i)

    def quit(self):
        if self.editing:
            self.finish_edit()
        n = [len(self.items)]
        self.cava.stop()
        if not n[0] or not rice.anim_on():
            _REAL_QUIT(); return
        for it in self.items:
            it.hide_win(True)
        GLib.timeout_add(int(mdur(0.28) * 1000) + 120, lambda: (_REAL_QUIT(), False)[1])

    # -- theme
    def _colors_mtime(self):
        try:
            return os.stat(rice.COLORS_FILE).st_mtime
        except Exception:
            return 0

    def _watch_colors(self):
        mt = self._colors_mtime()
        if mt != self._cmtime:
            self._cmtime = mt
            GLib.timeout_add(300, lambda: (self.recolor(), False)[1])     # let the theme finish writing
        return True

    def recolor(self):
        if _dsg.geo()["sfx"] != SFX:            # design language changed shape: restart (rice-supervise brings us back)
            log("design geometry changed, restarting"); os._exit(1)
        C.clear(); C.update(rice.colors())
        rice.CUR.clear(); rice.CUR.update(C)
        GA[0] = rice.glass_alpha()
        for it in self.items:
            it.redraw()
        if self.pill: self.pill.queue_draw()
        for o in self.overlays: o.queue_draw()

    # -- cava
    def cava_need(self):
        self.cava_ok = self.cava.start()

    # -- commands (FIFO / signals)
    def command(self, c):
        c = c.strip()
        log(f"command {c}")
        if c == "edit":
            if self.editing: self.finish_edit()
            else: self.begin_edit()
        elif c == "edit-on":
            self.begin_edit()
        elif c == "add":
            GLib.idle_add(lambda: (self.add_picker(), False)[1])
        elif c == "reload":
            self.reload()
        elif c == "stop":
            self.quit()
        elif c == "save":
            self.save()

    # -- adding / removing
    def add_kind(self, kind, at=None):
        cls = KINDS[kind]
        bw, bh = cls.base
        px, py = at or pointer()
        m = mon_at(px, py)
        x, y = self.clamp(px - bw // 2, py - bh // 2, bw, bh, m)
        d = dict(kind=kind, w=bw, h=bh, style=cls.style0, opts={})
        it = cls(self, d)
        it.x, it.y = x, y
        self.items.append(it)
        it.build(); it.start()
        it.show(anim=True, raised=True)
        return it

    def add_picker(self):
        if self.picking:
            return
        self.picking = True
        was = self.editing
        if was:
            self.ungrab()
        try:
            kind = pick_kind(self)
        finally:
            self.picking = False
        if kind:
            px, py = pointer()
            if not was:
                self.begin_edit()
            it = self.add_kind(kind, (px, py))
            self.select(it)
            self.save()
            for o in self.overlays: o.queue_draw()
        if self.editing:
            self.grab()

    def remove(self, it):
        if it not in self.items:
            return
        idx = self.items.index(it)
        self.items.remove(it)
        nxt = self.items[min(idx, len(self.items) - 1)] if self.items else None
        if self.sel is it:
            self.select(nxt)
        if isinstance(it, Note) and it.editing:
            it.finish()

        def gone():
            it.destroy()
            if not any(isinstance(i, Visualizer) for i in self.items):
                self.cava.stop()
        win = it.win
        if win is None:
            gone(); return
        x0, y0 = it.x, it.y

        def f(t):
            e = ease(t)
            win.set_opacity(1 - e)
            win.move(x0, y0 + int(10 * e))
        tween(win, mdur(0.3), f, gone)
        for o in self.overlays: o.queue_draw()

    # -- edit mode
    def begin_edit(self):
        if self.editing:
            return
        self.editing = True
        for it in self.items:
            if it.hidden:
                it.show(anim=True, raised=True)
            else:
                gdk_raise(it.win)
        self.overlays = [Overlay(self, m) for m in monitors()]
        self.pill = Pill(self)
        x, y = self.pill.place()
        self.pill.set_opacity(0.0)
        self.pill.move(x, y + 20)
        self.pill.show()
        pill = self.pill

        def f(t):
            pill.set_opacity(min(t * 1.6, 1.0))
            pill.move(x, y + int(round(20 * (1 - spring(t)))))
        tween(pill, mdur(0.5), f)
        self.grab()
        if self.items:
            px, py = pointer()
            under = next((i for i in self.items if i.x <= px < i.x + i.w and i.y <= py < i.y + i.h), None)
            self.select(under or self.items[0])

    def grab(self, n=0):
        if not self.editing or self.pill is None:
            return False
        seat = Gdk.Display.get_default().get_default_seat()
        gw = self.pill.get_window()
        ok = gw is not None and seat.grab(gw, Gdk.SeatCapabilities.KEYBOARD, False, None, None, None) == Gdk.GrabStatus.SUCCESS
        if not ok and n < 30:
            GLib.timeout_add(60, lambda: (self.grab(n + 1), False)[1])
        return False

    def ungrab(self):
        try:
            Gdk.Display.get_default().get_default_seat().ungrab()
        except Exception:
            pass

    def finish_edit(self, save=True):
        if not self.editing:
            return
        self.editing = False
        self.drag = None
        self.preview = None
        self.guides = []
        self.sel = None
        self.sel_anim = None
        self.ungrab()
        for o in self.overlays:
            o.destroy()
        self.overlays = []
        pill = self.pill
        self.pill = None
        if pill is not None:
            x, y = pill.get_position()

            def f(t):
                e = ease(t)
                pill.set_opacity(1 - e)
                pill.move(x, y + int(16 * e))
            tween(pill, mdur(0.26), f, pill.destroy)
        for it in self.items:
            if it.win is not None:
                it.win.set_opacity(1.0)
                it.win.get_window().set_cursor(None) if it.win.get_window() else None
            if it.hidden:
                it.hide_win()
            elif it.win is not None:
                gdk_lower(it.win)
        if save:
            self.save()

    def select(self, it):
        old = self.sel
        prev = self.cur_sel_rect()
        self.sel = it
        if it is not None:
            if old is None or prev is None:
                x, y, w, h = it.rect()
                prev = (x + w * 0.06, y + h * 0.06, w * 0.88, h * 0.88)
            self.sel_anim = dict(frm=prev, t0=time.monotonic(), dur=mdur(0.45))
            self._run_sel_anim()
        self.refresh(full=True)

    def _run_sel_anim(self):
        if self.pill is None:
            return

        def tick(w, clock):
            a = self.sel_anim
            if a is None or not self.editing:
                return False
            self.refresh()
            if time.monotonic() - a["t0"] >= a["dur"]:
                self.sel_anim = None
                self.refresh()
                return False
            return True
        self.pill.add_tick_callback(tick)

    def cur_sel_rect(self):
        it = self.sel
        if it is None:
            return None
        if self.preview and self.preview[0] is it:
            tgt = self.preview[1:]
        else:
            tgt = it.rect()
        a = self.sel_anim
        if a is None or self.drag:
            return tgt
        t = min((time.monotonic() - a["t0"]) / max(a["dur"], 1e-3), 1.0)
        k = spring(t)
        return tuple(f + (g - f) * k for f, g in zip(a["frm"], tgt))

    def dyn_rects(self):
        rs = []
        r = self.cur_sel_rect()
        if r:
            x, y, w, h = r
            rs.append((x - 16, y - 44, w + 32, h + 60))
        for g in self.guides:
            if g[0] == "v":
                rs.append((g[1] - 3, g[2], 6, g[3] - g[2]))
            else:
                rs.append((g[2], g[1] - 3, g[3] - g[2], 6))
        if self.preview:
            _it, x, y, w, h = self.preview
            rs.append((x - 16, y - 44, w + 32, h + 60))
        if self.drag:
            x, y, w, h = self.drag["it"].rect()
            rs.append((x - 16, y - 44, w + 32, h + 60))
        return rs

    def refresh(self, full=False):
        new = self.dyn_rects()
        for o in self.overlays:
            if full:
                o.queue_draw()
            else:
                for r in self._dmg + new:
                    o.damage(r)
        self._dmg = new

    def draw_overlay(self, cr, m):
        for it in self.items:
            if it is self.sel or it.win is None or not it.win.get_mapped():
                continue
            x, y, w, h = it.rect()
            dashed_rrect(cr, x - 4, y - 4, w + 8, h + 8, RADIUS + 4, "fg", 0.35, 1.2, (5, 6))
        cr.set_line_width(1)
        for g in self.guides:
            cr.set_source_rgba(*rgba("accent", 0.85))
            if g[0] == "v":
                cr.rectangle(g[1] - 0.5, g[2], 1, g[3] - g[2])
            else:
                cr.rectangle(g[2], g[1] - 0.5, g[3] - g[2], 1)
            cr.fill()
        if self.preview:
            it, x, y, w, h = self.preview
            cr.save()
            cr.translate(x, y)
            it.render(cr, w, h, preview=False)
            cr.restore()
        r = self.cur_sel_rect()
        if r and self.sel is not None:
            x, y, w, h = r
            it = self.sel
            dashed_rrect(cr, x - 5, y - 5, w + 10, h + 10, RADIUS + 5, "accent", 1.0, 2.0, (9, 6))
            for hx, hy in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
                cr.arc(hx, hy, 6.5, 0, 2 * math.pi)
                cr.set_source_rgba(*rgba("bg", 1.0)); cr.fill_preserve()
                cr.set_source_rgba(*rgba("accent", 1.0)); cr.set_line_width(2.5); cr.stroke()
            lab = f"{it.title.lower()} · {int(w)}×{int(h)} · {it.style}"
            s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 2, 2)
            tw = T(cairo.Context(s), lab, 0, 0, 11.5, "fg", 0, W_.BOLD, MONO)[0]
            rice.rounded(cr, x, y - 36, tw + 20, 24, 12)
            cr.set_source_rgba(*rgba("accent", 0.95)); cr.fill()
            T(cr, lab, x + 10, y - 24, 11.5, "bg", 1.0, W_.BOLD, MONO, "l", "c")

    # -- snapping
    def snap(self, it, nx, ny, w, h, free=False):
        self.guides = []
        if free:
            return int(nx), int(ny)
        m = mon_at(nx + w // 2, ny + h // 2)
        xs = [(m["x"] + MARGIN, (0,)), (m["x"] + m["w"] - MARGIN, (w,)), (m["x"] + m["w"] / 2, (w / 2,))]
        ys = [(m["y"] + TOP, (0,)), (m["y"] + m["h"] - MARGIN, (h,)), (m["y"] + m["h"] / 2, (h / 2,))]
        for o in self.items:
            if o is it or o.win is None or not o.win.get_mapped():
                continue
            ox, oy, ow, oh = o.rect()
            xs += [(ox, (0, w)), (ox + ow, (0, w)), (ox + ow / 2, (w / 2,)), (ox + ow + 16, (0,)), (ox - 16, (w,))]
            ys += [(oy, (0, h)), (oy + oh, (0, h)), (oy + oh / 2, (h / 2,)), (oy + oh + 16, (0,)), (oy - 16, (h,))]

        def best(pos, cands):
            b = None
            for T_, offs in cands:
                for off in offs:
                    d = abs(pos + off - T_)
                    if d <= SNAP and (b is None or d < b[0]):
                        b = (d, T_ - off, T_)
            return b
        bx, by = best(nx, xs), best(ny, ys)
        if bx:
            nx = bx[1]
            self.guides.append(("v", bx[2], m["y"], m["y"] + m["h"]))
        else:
            nx = m["x"] + round((nx - m["x"]) / GRID) * GRID
        if by:
            ny = by[1]
            self.guides.append(("h", by[2], m["x"], m["x"] + m["w"]))
        else:
            ny = m["y"] + round((ny - m["y"]) / GRID) * GRID
        return int(nx), int(ny)

    # -- input
    def corner(self, it, x, y):
        z = 22
        l, t = x < z, y < z
        r, b = x > it.w - z, y > it.h - z
        if l and t: return "nw"
        if r and t: return "ne"
        if l and b: return "sw"
        if r and b: return "se"
        return None

    def cursor(self, name):
        c = self.cursors.get(name)
        if c is None:
            c = self.cursors[name] = Gdk.Cursor.new_from_name(Gdk.Display.get_default(), name)
        return c

    def on_press(self, it, e):
        if e.type == Gdk.EventType.BUTTON_PRESS and e.button == 3 and not (isinstance(it, Note) and it.editing):
            return self.context_menu(it, e)
        if isinstance(it, Note) and it.editing:
            return it.click(e.x, e.y, e)
        if not self.editing:
            return it.click(e.x, e.y, e)
        if e.type != Gdk.EventType.BUTTON_PRESS or e.button != 1:
            return True
        if self.sel is not it:
            self.select(it)
        c = self.corner(it, e.x, e.y)
        self.drag = dict(it=it, mode=("resize", c) if c else ("move", None), rx=e.x_root, ry=e.y_root,
                         g=it.rect(), moved=False)
        if c:
            self.preview = (it, *it.rect())
            it.win.set_opacity(0.0)
        self.refresh()
        return True

    FONTS = ("Roboto Flex", "Inter Display", "Red Hat Display", "Nunito", "Fredoka", "Space Grotesk", "IBM Plex Sans",
             "Fraunces", "JetBrains Mono", "Space Mono", "IBM Plex Mono", "Roboto Mono")
    ACCENTS = (("Rose", "#ff6b81"), ("Orange", "#ff9f43"), ("Yellow", "#ffd166"), ("Green", "#7bd88f"),
               ("Teal", "#4fd1c5"), ("Blue", "#5aa9ff"), ("Purple", "#b388ff"), ("White", "#f2f2f2"))
    ALPHAS = (("Clear", 0.25), ("Light", 0.45), ("Medium", 0.7), ("Solid", 0.96))

    def context_menu(self, it, e):
        import designs
        menu = Gtk.Menu()
        self._menu_css()

        def setopt(k, v):
            if v is None:
                it.opts.pop(k, None)
            else:
                it.opts[k] = v
            it.redraw(); self.save()

        def radio(parent, label, on, cb, group=[None]):
            m = Gtk.CheckMenuItem(label=label); m.set_draw_as_radio(True); m.set_active(on)
            m.connect("activate", lambda w: w.get_active() and cb())
            parent.append(m)

        def sub(label, items):
            m = Gtk.MenuItem(label=label); sm = Gtk.Menu(); m.set_submenu(sm); menu.append(m)
            for lab, on, cb in items:
                radio(sm, lab, on, cb)
            return sm

        o = it.opts
        sub("Font", [("Follow theme", "font" not in o, lambda: setopt("font", None))] +
            [(f, o.get("font") == f, (lambda f=f: setopt("font", f))) for f in self.FONTS])
        sub("Design language", [("Follow theme", "design" not in o, lambda: setopt("design", None))] +
            [(designs.DESIGNS[k]["label"], o.get("design") == k, (lambda k=k: setopt("design", k))) for k in designs.ORDER[1:]])
        sub("Accent colour", [("Follow theme", "accent" not in o, lambda: setopt("accent", None))] +
            [(n, o.get("accent") == h, (lambda h=h: setopt("accent", h))) for n, h in self.ACCENTS])

        def restyle(st):
            if it.style != st:
                it.style = st; it.rebuild(raised=self.editing)
                self.refresh(full=True); self.save()
        sub("Background", [("Glass card", it.style == "glass", lambda: restyle("glass")),
                           ("Bare (no card)", it.style != "glass", lambda: restyle("bare"))])
        if it.style == "glass":
            sub("Glass opacity", [("Follow theme", "bgalpha" not in o, lambda: setopt("bgalpha", None))] +
                [(n, o.get("bgalpha") == a, (lambda a=a: setopt("bgalpha", a))) for n, a in self.ALPHAS])
        it.extra_menu(menu, setopt)
        menu.append(Gtk.SeparatorMenuItem())

        def item(label, cb):
            m = Gtk.MenuItem(label=label); m.connect("activate", lambda w: cb()); menu.append(m)
        item("Reset appearance", lambda: ([it.opts.pop(k, None) for k in ("font", "design", "accent", "bgalpha")], it.redraw(), self.save()))
        item("Move / resize widgets…", lambda: self.begin_edit() if not self.editing else None)
        item("Remove widget", lambda: self.remove(it))
        menu.show_all()
        menu.popup_at_pointer(e)
        return True

    def _menu_css(self):
        css = Gtk.CssProvider()
        c = C
        css.load_from_data(f"""
        menu, .popup {{ background: {c['bg2']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 4px; color: {c['fg']}; }}
        menuitem {{ color: {c['fg']}; padding: 5px 12px; border-radius: 7px; font-family: '{rice.SANS_FONT}'; font-size: 13px; }}
        menuitem:hover {{ background: {c['accent']}; color: {c['bg']}; }}
        menuitem label {{ color: inherit; }}
        separator {{ background: {c['border']}; min-height: 1px; margin: 4px 6px; }}
        """.encode())
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def on_motion(self, it, e):
        if not self.editing:
            return False
        dr = self.drag
        if dr is None:
            gw = it.win.get_window() if it.win else None
            if gw is not None:
                c = self.corner(it, e.x, e.y)
                gw.set_cursor(self.cursor({"nw": "nwse-resize", "se": "nwse-resize", "ne": "nesw-resize", "sw": "nesw-resize"}.get(c, "move")))
            return True
        dx, dy = e.x_root - dr["rx"], e.y_root - dr["ry"]
        if abs(dx) + abs(dy) > 2:
            dr["moved"] = True
        free = bool(e.state & Gdk.ModifierType.SHIFT_MASK)
        x0, y0, w0, h0 = dr["g"]
        o = dr["it"]
        if dr["mode"][0] == "move":
            nx, ny = self.snap(o, x0 + dx, y0 + dy, w0, h0, free)
            o.x, o.y = nx, ny
            o.place()
        else:
            c = dr["mode"][1]
            mw, mh = o.min_size()
            l, t, r, b = x0, y0, x0 + w0, y0 + h0
            if "w" in c: l = min(x0 + dx, r - mw)
            if "e" in c: r = max(r + dx, l + mw)
            if "n" in c: t = min(y0 + dy, b - mh)
            if "s" in c: b = max(b + dy, t + mh)
            if not o.free and not free:          # keep the aspect of fitted widgets
                ar = w0 / h0
                nw, nh = r - l, b - t
                if nw / nh > ar: nw = nh * ar
                else: nh = nw / ar
                if "w" in c: l = r - nw
                else: r = l + nw
                if "n" in c: t = b - nh
                else: b = t + nh
            if not free:
                g = lambda v: round(v / GRID) * GRID
                l, t, r, b = (g(l) if "w" in c else l), (g(t) if "n" in c else t), (g(r) if "e" in c else r), (g(b) if "s" in c else b)
            self.guides = []
            self.preview = (o, int(l), int(t), int(r - l), int(b - t))
        self.refresh()
        return True

    def on_release(self, it, e):
        dr = self.drag
        if not self.editing or dr is None:
            return False
        self.drag = None
        o = dr["it"]
        if dr["mode"][0] == "resize" and self.preview:
            _i, x, y, w, h = self.preview
            o.x, o.y = x, y
            o.commit_size(w, h)
            o.place()
            win = o.win

            def show_again():
                self.preview = None
                if win is not None:
                    win.set_opacity(1.0)
                self.refresh(full=True)
                return False
            GLib.timeout_add(70, show_again)       # let the resized window paint before the preview goes
        self.guides = []
        self.refresh(full=True)
        return True

    def on_scroll(self, it, e):
        if self.editing:
            return True
        up = e.direction == Gdk.ScrollDirection.UP or (e.direction == Gdk.ScrollDirection.SMOOTH and e.get_scroll_deltas()[2] < 0)
        return it.scroll(up)

    def on_key(self, it, e):
        if it is not None and isinstance(it, Note) and it.editing:
            return it.key(e)
        for n in self.items:
            if isinstance(n, Note) and n.editing:
                return n.key(e)
        if not self.editing:
            return False
        k = e.keyval
        shift = e.state & Gdk.ModifierType.SHIFT_MASK
        s = self.sel
        if k == Gdk.KEY_Escape:
            self.finish_edit(); return True
        if k in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab) and self.items:
            i = self.items.index(s) if s in self.items else -1
            i = (i + (-1 if shift or k == Gdk.KEY_ISO_Left_Tab else 1)) % len(self.items)
            self.select(self.items[i]); return True
        if k in (Gdk.KEY_a, Gdk.KEY_A):
            GLib.idle_add(lambda: (self.add_picker(), False)[1]); return True
        if s is None:
            return True
        step = 10 if shift else 1
        mv = {Gdk.KEY_Left: (-step, 0), Gdk.KEY_Right: (step, 0), Gdk.KEY_Up: (0, -step), Gdk.KEY_Down: (0, step)}
        if k in mv:
            dx, dy = mv[k]
            s.x += dx; s.y += dy
            s.place(); self.refresh(); return True
        if k in (Gdk.KEY_Delete, Gdk.KEY_BackSpace, Gdk.KEY_KP_Delete):
            self.remove(s); return True
        if k in (Gdk.KEY_b, Gdk.KEY_B):
            s.style = "bare" if s.style == "glass" else "glass"
            s.rebuild(raised=True)
            for o in self.overlays:      # keep the overlays above the rebuilt widget
                gdk_raise(o)
            if self.pill: gdk_raise(self.pill)
            self.refresh(full=True); return True
        return True


_LOOPS = []
_REAL_QUIT = Gtk.main_quit


LOG = os.environ.get("RICE_DESK_LOG") or os.path.expanduser("~/.cache/rice/desk.log")


def log(msg):
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 200000:
            os.replace(LOG, LOG + ".old")
        with open(LOG, "a") as f:
            f.write(f"{time.strftime('%m-%d %H:%M:%S')} [{os.getpid()}] {msg}\n")
    except Exception:
        pass


def _quit_nested(*_a):
    """rice.Card.quit_anim calls Gtk.main_quit when a card closes; in the daemon that may only end the
    picker's nested loop, never the daemon (a late second call would otherwise stop all widgets)."""
    if _LOOPS:
        _LOOPS[-1].quit()


def run(fifo, initial=None):
    Gtk.main_quit = _quit_nested
    desk = Desk()

    def on_fifo(ch, cond):
        try:
            data = os.read(fd, 4096).decode(errors="ignore")
        except BlockingIOError:
            return True
        except Exception:
            return True
        for ln in data.splitlines():
            if ln.strip():
                GLib.idle_add(lambda c=ln: (desk.command(c), False)[1])
        return True
    fd = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
    GLib.io_add_watch(GLib.IOChannel.unix_new(fd), GLib.PRIORITY_DEFAULT, GLib.IOCondition.IN, on_fifo)
    for sig, c in ((signal.SIGUSR1, "edit"), (signal.SIGUSR2, "add"), (signal.SIGHUP, "reload")):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda c=c: (desk.command(c), True)[1])
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: (log("SIGTERM"), desk.quit(), False)[2])
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: (log("SIGINT"), desk.quit(), False)[2])
    try:
        import faulthandler
        faulthandler.enable(file=open(LOG, "a"))
    except Exception:
        pass
    log(f"start display={os.environ.get('DISPLAY')} state={STATE}")
    desk.start(initial)
    try:
        Gtk.main()
    finally:
        desk.cava.stop()
        log("exit")
