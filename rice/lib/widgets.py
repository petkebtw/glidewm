"""Cairo widgets shared by rice-settings, rice-tools and friends. All read rice.CUR at draw time, so a
   theme change recolours them live."""
import math, time
import rice
from rice import Gtk, Gdk, GLib, cairo


def col(k, a=1.0):
    return rice.rgb(rice.CUR.get(k, "#ffffff"), a)


def text(cr, s, x, y, size=12, bold=False, color="fg", a=1.0, align="l", font=None):
    cr.select_font_face(font or rice.FONT, 0, 1 if bold else 0)
    cr.set_font_size(size)
    e = cr.text_extents(s)
    if align == "c": x -= e.width / 2 + e.x_bearing
    elif align == "r": x -= e.width + e.x_bearing
    cr.set_source_rgba(*col(color, a))
    cr.move_to(x, y); cr.show_text(s)
    return e.x_advance


def icon(cr, glyph, x, y, size=18, color="fg", a=1.0):
    return text(cr, glyph, x, y, size, False, color, a, "c", rice.ICON_FONT)


class Anim(Gtk.DrawingArea):
    """DrawingArea with a 0..1 value that eases toward a target on the frame clock."""

    def __init__(self, v=0.0, speed=0.3):
        super().__init__()
        self.v, self.t, self.speed, self._tk = v, v, speed, None

    def go(self, t):
        self.t = t
        if self._tk is None:
            self._tk = self.add_tick_callback(self._step)

    def _step(self, w, clock):
        d = self.t - self.v
        self.v += d * self.speed
        self.queue_draw()
        if abs(d) < 0.004:
            self.v = self.t; self._tk = None
            return False
        return True


class Switch(Anim):
    def __init__(self, on=False, cb=None):
        super().__init__(1.0 if on else 0.0)
        self.on, self.cb = on, cb
        self.set_size_request(46, 26)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("draw", self._draw)
        self.connect("button-press-event", self._press)

    def set(self, on):
        self.on = on; self.go(1.0 if on else 0.0)

    def _press(self, w, e):
        self.set(not self.on)
        if self.cb: self.cb(self.on)
        return True

    def _draw(self, w, cr):
        r = 13
        rice.rounded(cr, 1, 1, 44, 24, r - 1)
        ac, bd = col("accent"), col("border")
        cr.set_source_rgba(*(bd[i] + (ac[i] - bd[i]) * self.v for i in range(3)), 1); cr.fill()
        kx = 13 + 20 * self.v
        cr.arc(kx + 1, 14, 9.5, 0, 6.2832)
        bg = col("bg") if self.v > 0.5 else col("fg")
        cr.set_source_rgba(*bg[:3], 1); cr.fill()
        return False


class Seg(Anim):
    """Segmented control with a sliding highlight."""

    def __init__(self, opts, sel=0, cb=None, w=200):
        super().__init__(float(sel), 0.28)
        self.opts, self.sel, self.cb = opts, sel, cb
        self.set_size_request(w, 30)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("draw", self._draw)
        self.connect("button-press-event", self._press)

    def set(self, i):
        self.sel = i; self.go(float(i))

    def _press(self, w, e):
        n = len(self.opts)
        i = max(0, min(n - 1, int(e.x / (self.get_allocated_width() / n))))
        if i != self.sel:
            self.set(i)
            if self.cb: self.cb(i)
        return True

    def _draw(self, w, cr):
        W, H = self.get_allocated_width(), self.get_allocated_height()
        n = len(self.opts); sw = (W - 4) / n
        rice.rounded(cr, 0.5, 0.5, W - 1, H - 1, H / 2)
        cr.set_source_rgba(*col("fg", 0.08)); cr.fill()
        rice.rounded(cr, 2 + self.v * sw, 2, sw, H - 4, (H - 4) / 2)
        cr.set_source_rgba(*col("accent")); cr.fill()
        for i, o in enumerate(self.opts):
            on = abs(i - self.v) < 0.5
            text(cr, o, 2 + sw * (i + 0.5), H / 2 + 4, 11, on, "bg" if on else "dim", 1, "c")
        return False


class Slider(Anim):
    def __init__(self, v=0.0, cb=None, w=200):
        super().__init__(v, 0.35)
        self.cb, self.drag = cb, False
        self.set_size_request(w, 26)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
        self.connect("draw", self._draw)
        self.connect("button-press-event", self._p)
        self.connect("button-release-event", lambda *a: setattr(self, "drag", False))
        self.connect("motion-notify-event", self._m)

    def _set(self, x):
        v = max(0.0, min(1.0, (x - 8) / max(1, self.get_allocated_width() - 16)))
        self.v = self.t = v; self.queue_draw()
        if self.cb: self.cb(v)

    def _p(self, w, e):
        self.drag = True; self._set(e.x); return True

    def _m(self, w, e):
        if self.drag: self._set(e.x)
        return True

    def _draw(self, w, cr):
        W, H = self.get_allocated_width(), self.get_allocated_height()
        rice.rounded(cr, 8, H / 2 - 4, W - 16, 8, 4); cr.set_source_rgba(*col("fg", 0.1)); cr.fill()
        x = 8 + self.v * (W - 16)
        rice.rounded(cr, 8, H / 2 - 4, max(8, x - 8), 8, 4); cr.set_source_rgba(*col("accent")); cr.fill()
        cr.arc(x, H / 2, 9, 0, 6.2832); cr.set_source_rgba(*col("fg")); cr.fill()
        return False


class Tile(Anim):
    """Big rounded launcher tile: glyph + label; lifts on hover."""

    def __init__(self, glyph, label, cb, w=104, h=92, sub=None):
        super().__init__(0.0, 0.3)
        self.glyph, self.label, self.cb, self.sub = glyph, label, cb, sub
        self.set_size_request(w, h)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("draw", self._draw)
        self.connect("enter-notify-event", lambda *a: self.go(1.0))
        self.connect("leave-notify-event", lambda *a: self.go(0.0))
        self.connect("button-press-event", lambda w, e: (self.cb(), True)[1] if e.button == 1 else False)

    def _draw(self, w, cr):
        W, H = self.get_allocated_width(), self.get_allocated_height()
        rice.rounded(cr, 3, 3, W - 6, H - 6, 20)
        ac = col("accent"); f = col("fg")
        k = self.v
        cr.set_source_rgba(*(f[i] * (1 - k) + ac[i] * k for i in range(3)), 0.07 + 0.78 * k); cr.fill()
        on = "bg" if k > 0.6 else "accent"
        icon(cr, self.glyph, W / 2, H / 2 - 4 - 2 * k, 26, on)
        text(cr, self.label, W / 2, H - 17, 11, True, "bg" if k > 0.6 else "fg", 1, "c")
        return False


def heading(s):
    l = Gtk.Label(xalign=0)
    l.set_markup(f'<span size="9500" weight="bold" letter_spacing="1500" alpha="60%">{GLib.markup_escape_text(s.upper())}</span>')
    return l


def row(label, ctl, sub=None):
    b = Gtk.Box(spacing=10)
    v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    l = Gtk.Label(xalign=0); l.set_markup(f'<span size="11500">{GLib.markup_escape_text(label)}</span>'); l.set_ellipsize(3); l.set_max_width_chars(16)
    v.pack_start(l, False, False, 0)
    if sub:
        d = Gtk.Label(xalign=0); d.set_markup(f'<span size="9000" alpha="55%">{GLib.markup_escape_text(sub)}</span>'); d.set_ellipsize(3); d.set_max_width_chars(20)
        v.pack_start(d, False, False, 0)
    b.pack_start(v, True, True, 0)
    b.pack_end(ctl, False, False, 0)
    ctl.set_valign(Gtk.Align.CENTER)
    return b


class Btn(Anim):
    """Pill button. primary = accent fill."""

    def __init__(self, label, cb, primary=True, w=120, h=36):
        super().__init__(0.0, 0.3)
        self.label, self.cb, self.primary, self.enabled = label, cb, primary, True
        self.set_size_request(w, h)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("draw", self._draw)
        self.connect("enter-notify-event", lambda *a: self.go(1.0))
        self.connect("leave-notify-event", lambda *a: self.go(0.0))
        self.connect("button-press-event", lambda w, e: (self.cb() if self.enabled else None, True)[1] if e.button == 1 else False)

    def _draw(self, w, cr):
        W, H = self.get_allocated_width(), self.get_allocated_height()
        rice.rounded(cr, 1, 1, W - 2, H - 2, (H - 2) / 2)
        a = (1.0 if self.enabled else 0.35)
        if self.primary:
            cr.set_source_rgba(*col("accent")[:3], a * (0.85 + 0.15 * self.v))
        else:
            cr.set_source_rgba(*col("fg")[:3], a * (0.08 + 0.1 * self.v))
        cr.fill()
        text(cr, self.label, W / 2, H / 2 + 4.5, 12, True, "bg" if self.primary else "fg", a, "c")
        return False


class Bar(Anim):
    """Progress bar; value None = indeterminate shimmer."""

    def __init__(self, h=8):
        super().__init__(0.0, 0.4)
        self.val = 0.0
        self.set_size_request(-1, h)
        self.connect("draw", self._draw)
        self._tick = self.add_tick_callback(lambda w, c: (self.queue_draw(), True)[1])

    def _draw(self, w, cr):
        W, H = self.get_allocated_width(), self.get_allocated_height()
        rice.rounded(cr, 0, 0, W, H, H / 2); cr.set_source_rgba(*col("fg", 0.1)); cr.fill()
        if self.val is None:
            x = ((time.time() * 0.9) % 1.4 - 0.2) * W
            cr.save(); rice.rounded(cr, 0, 0, W, H, H / 2); cr.clip()
            rice.rounded(cr, x, 0, W * 0.25, H, H / 2); cr.set_source_rgba(*col("accent")); cr.fill(); cr.restore()
        else:
            self.v += (self.val - self.v) * 0.25
            rice.rounded(cr, 0, 0, max(H, W * self.v), H, H / 2); cr.set_source_rgba(*col("accent")); cr.fill()
        return False


def entry(placeholder="", w=-1):
    e = Gtk.Entry()
    e.set_placeholder_text(placeholder)
    e.set_size_request(w, 40)
    e.set_has_frame(False)
    return e


def toast(text_, secs=2.4):
    """Small centred-top card; does not touch the caller's main loop."""
    t = rice.Card(max(240, 11 * len(text_) + 56), 52, radius=26)
    lab = Gtk.Label(); lab.set_markup(f'<span size="11500" weight="bold">{GLib.markup_escape_text(text_)}</span>')
    t.add(lab)
    g = rice.primary_geometry()
    ww, _ = t.get_size_request()
    t.move(g.x + (g.width - ww) // 2, g.y + 70)
    t.show_all()

    def gone():
        t._leaving = False
        t.hide(); t.destroy()
        return False
    GLib.timeout_add(int(secs * 1000), lambda: (t.hide(), t.destroy(), False)[2])
    return t


def mon_center(w, h):
    d = Gdk.Display.get_default()
    _, px, py = d.get_default_seat().get_pointer().get_position()
    m = d.get_monitor_at_point(px, py) or d.get_primary_monitor()
    g = m.get_geometry()
    return g.x + (g.width - w) // 2, g.y + (g.height - h) // 2, g


def grab_keys(win, tries=30):
    def go():
        seat = Gdk.Display.get_default().get_default_seat()
        if seat.grab(win.get_window(), Gdk.SeatCapabilities.ALL, True, None, None, None) == Gdk.GrabStatus.SUCCESS:
            return False
        go.n += 1
        return go.n < tries
    go.n = 0
    GLib.timeout_add(60, go)


def close_on_outside(win):
    """Esc, right click or a click outside closes a grabbing card."""
    def key(wd, e):
        if e.keyval == Gdk.KEY_Escape:
            win.quit_anim(); return True
        return False

    def press(wd, e):
        a = win.get_allocation()
        if e.button == 3 or not (0 <= e.x <= a.width and 0 <= e.y <= a.height):
            win.quit_anim(); return True
        return False
    win.add_events(Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.BUTTON_PRESS_MASK)
    win.connect("key-press-event", key)
    win.connect("button-press-event", press)


def dropdown(label, sub, options, current, cb, maxh=None):
    """KDE-style combo row: shows the current value; click expands the option list below (animated)."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    st = dict(v=current)

    def text_of(v):
        return next((l for l, x in options if x == v), str(v))
    btn = Gtk.Button(); btn.get_style_context().add_class("pill")
    rv = Gtk.Revealer(); rv.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN); rv.set_transition_duration(180)
    lst = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
    lst.set_margin_start(14)
    btns = []

    def paint():
        btn.set_label(text_of(st["v"]) + "   ▾")
        for b, (l, x) in zip(btns, options):
            b.set_label(("●  " if x == st["v"] else "○  ") + l)

    def pick(x):
        st["v"] = x; paint(); rv.set_reveal_child(False); cb(x)
    for l, x in options:
        b = Gtk.Button(); b.get_style_context().add_class("pill"); b.connect("clicked", lambda _b, x=x: pick(x))
        b.get_child() if False else None
        btns.append(b); lst.pack_start(b, False, False, 0)
    if maxh:
        sc = Gtk.ScrolledWindow(); sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.set_min_content_height(maxh); sc.set_max_content_height(maxh); sc.add(lst); rv.add(sc)
    else:
        rv.add(lst)
    btn.connect("clicked", lambda *_: rv.set_reveal_child(not rv.get_reveal_child()))
    paint()
    box.pack_start(row(label, btn, sub), False, False, 0)
    box.pack_start(rv, False, False, 0)
    box.set = lambda v: (st.__setitem__("v", v), paint())
    return box


def vslider(label, sub, lo, hi, cur, fmt, cb, step=1, wd=260, delay=200):
    """Slider row with a live value label; cb fires (debounced) with the number."""
    sl = Slider((cur - lo) / float(hi - lo), None, wd)
    val = Gtk.Label(); val.set_size_request(64, -1); val.set_xalign(1)
    tm = [None]

    def show(v):
        val.set_markup(f'<span size="10500" alpha="70%">{GLib.markup_escape_text(fmt(v))}</span>')
    show(cur)

    def changed(f):
        v = lo + f * (hi - lo)
        v = round(v / step) * step
        v = max(lo, min(hi, v))
        show(v)
        if tm[0]: GLib.source_remove(tm[0])
        tm[0] = GLib.timeout_add(delay, lambda: (cb(v), tm.__setitem__(0, None), False)[2])
    sl.cb = changed
    h = Gtk.Box(spacing=8)
    h.pack_start(sl, False, False, 0); h.pack_start(val, False, False, 0)
    return row(label, h, sub)
