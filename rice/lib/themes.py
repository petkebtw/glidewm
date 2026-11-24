"""Wallpaper themes: palette extraction, wallpaper sync and apply logic."""
import math
import os, json, random, hashlib, colorsys, subprocess
from PIL import Image, ImageDraw, ImageFilter

HOME = os.path.expanduser("~")
CACHE = f"{HOME}/.cache/theme"
THUMBS = f"{CACHE}/thumbs"
WALLS = f"{HOME}/Pictures/wallpapers"
EXT = (".png", ".jpg", ".jpeg", ".webp")
for d in (CACHE, THUMBS, WALLS):
    os.makedirs(d, exist_ok=True)

KEYS = ("bg", "bg2", "border", "fg", "dim", "accent", "accent2")
ONLINE = f"{WALLS}/online"
API = "https://api.github.com/repos/DenverCoder1/minimalistic-wallpaper-collection/contents/images"
RAW = "https://raw.githubusercontent.com/DenverCoder1/minimalistic-wallpaper-collection/main/images/"
SITE = "https://minimalistic-wallpaper.demolab.com/"
MAX_ONLINE, PER_RUN, MAX_BYTES = 150, 10, 6_000_000


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexc(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0, min(1, s)), max(0, min(1, v)))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


WH = "https://wallhaven.cc/api/v1/search?categories=110&purity=100&atleast=2560x1440&ratios=16x9&sorting=toplist&topRange=1y&page="
SOURCE_FILE = f"{HOME}/.cache/rice/source"
SOURCES = ("mono", "wallhaven", "minimal", "both")


def source():
    try:
        v = open(SOURCE_FILE).read().strip()
        return v if v in SOURCES else "mono"
    except OSError:
        return "mono"


def set_source(v):
    os.makedirs(os.path.dirname(SOURCE_FILE), exist_ok=True)
    open(SOURCE_FILE, "w").write(v)


def is_wh(path):
    return os.path.basename(path).startswith("wallhaven-")


def origin(path):
    """Which online source a download came from: 'mono', 'wallhaven' or 'minimal'."""
    b = os.path.basename(path)
    return "mono" if b.startswith("mono-") else "wallhaven" if b.startswith("wallhaven-") else "minimal"


def prune(keep):
    """Infinite feed: when the online folder is full, drop the oldest downloads (never the active wallpaper)."""
    try:
        cur = open(f"{CACHE}/wall").read().strip()
    except OSError:
        cur = ""
    keepf = {os.path.realpath(cur)}
    try:      # the picker pins the wallpaper it must revert to; a preview must never let sync delete it
        keepf.add(os.path.realpath(open(os.path.expanduser("~/.cache/rice/pinned")).read().strip()))
    except OSError:
        pass
    try:      # favourites are never pruned
        import favs
        keepf |= {os.path.realpath(p) for p in favs.load().get("themes", [])}
    except Exception:
        pass
    fs = sorted((os.path.join(ONLINE, f) for f in os.listdir(ONLINE) if not f.startswith(".")), key=os.path.getmtime)
    for f in fs[:max(len(fs) - keep, 0)]:
        if os.path.realpath(f) not in keepf:
            try: os.remove(f)
            except OSError: pass


def _save(tmpname, name, got_url, urlopen, cb=None, check=None):
    tmp = f"{ONLINE}/.{tmpname}.part"
    try:
        with urlopen(got_url) as r, open(tmp, "wb") as f:
            f.write(r.read())
        Image.open(tmp).verify()
        if check:              # quality gate on the real file (JPEG decoded at reduced scale)
            im = Image.open(tmp); im.draft("RGB", (256, 256))
            if not check(im):
                raise ValueError("rejected")
        os.replace(tmp, f"{ONLINE}/{name}")
        thumb(f"{ONLINE}/{name}"); palette(f"{ONLINE}/{name}")  # pre-extract the colours
        if cb: cb()
        return 1
    except Exception:
        try: os.remove(tmp)
        except OSError: pass
        return 0


def sync_wallhaven(n, cb=None):
    """Wallhaven yearly toplist: SFW only, 16:9, >=1440p, well-liked (>=80 favourites)."""
    import urllib.request
    have = set(os.listdir(ONLINE))
    hdr = {"User-Agent": "rice-themes/1.0"}
    data, seen = [], set()
    for page in random.sample(range(1, 41), 6):          # random pages until enough fresh, good ones turn up
        try:
            with urllib.request.urlopen(urllib.request.Request(WH + str(page), headers=hdr), timeout=10) as r:
                got = json.load(r)["data"]
        except Exception:
            if not data: return 0                          # offline
            break
        for d in got:
            nm = os.path.basename(d["path"])
            if d.get("purity") == "sfw" and d.get("favorites", 0) >= 80 and d.get("file_size", 0) <= 8_000_000 \
                    and nm not in have and nm not in seen:
                seen.add(nm); data.append(d)
        if len(data) >= n: break
    random.shuffle(data)
    uo = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=hdr), timeout=40)
    return sum(_save(os.path.basename(d["path"]), os.path.basename(d["path"]), d["path"], uo, cb) for d in data[:n])


def sync_minimal(n, cb=None):
    import urllib.request, re
    have = set(os.listdir(ONLINE))
    names = []
    try:
        with urllib.request.urlopen(API, timeout=8) as r:
            names = [(d["name"], d["size"]) for d in json.load(r) if d["name"].lower().endswith(EXT)]
    except Exception:
        try:
            with urllib.request.urlopen(SITE, timeout=8) as r:
                html = r.read().decode("utf8", "ignore")
            names = [(x, 0) for x in re.findall(r'raw\.githubusercontent\.com/[^"]+/images/([^"]+)"', html)]
        except Exception:
            return 0  # offline
    local = {x.lower() for x in have}
    new = [x for x in names if x[0].lower() not in local and (x[1] == 0 or x[1] <= MAX_BYTES)]
    random.shuffle(new)
    uo = lambda u: urllib.request.urlopen(u, timeout=30)
    return sum(_save(x[0], x[0], RAW + urllib.request.quote(x[0]), uo, cb) for x in new[:n])


# ---- mono: calm monochrome / muted photos and ink-on-black art from Wallhaven ----------------
# Three groups -- black-and-white photos, muted/faded colour photos, ink or line art on black -- and
# every sync draws from each, so a batch is varied. (query, categories); categories bits: general,
# anime, people. MONO_NOT drops tags that bring graphics, memes and logos; the gate below throws out
# whatever colourful stuff still slips in.
MONO_Q = (
    (("monochrome clouds", "100"), ("monochrome nature", "100"), ("monochrome landscape", "100"),
     ("fog monochrome", "100"), ("black and white photography", "100"), ("monochrome flowers", "100"),
     ("monochrome sea", "100"), ("grayscale", "100"), ("monochrome minimalism", "100"), ("minimalism dark", "100")),
    (("blossom", "100"), ("cherry blossom", "100"), ("film photography", "100"), ("mist", "100"),
     ("forest fog", "100"), ("winter dark", "100"), ("nature photography dark", "100"), ("desaturated", "100"),
     ("muted", "100"), ("film grain", "100")),
    (("monochrome drawing", "101"), ("drawing black background", "100"), ("ink monochrome", "101"),
     ("line art monochrome", "101"), ("monochrome portrait", "101")),
)
MONO_URL = ("https://wallhaven.cc/api/v1/search?categories=%s&purity=100&atleast=1920x1080&ratios=16x9,16x10"
            "&sorting=favorites&page=%d&q=%s")
MONO_NOT = " -abstract -pattern -typography -text -3D -meme -logo -anime -cartoon -fractal"
MONO_MAX = dict(c=0.028, p90=0.050, hi=0.03, s90=0.10, l=0.62)


def mono_stats(im):
    """Colourfulness of a picture on a 64x64 copy: c = mean OKLab chroma, p90 = its 90th percentile,
       hi = share of clearly coloured pixels (C > 0.05), s90 = 90th percentile of C/L over the pixels
       that are not dark (dark pixels have little chroma whatever their hue), l = mean grey 0..1."""
    if im.mode != "RGB":
        im = im.convert("RGB")
    im = im.copy(); im.thumbnail((64, 64))
    cs, sat, ls = [], [], 0
    for r, g, b in im.getdata():
        ls += r * 0.299 + g * 0.587 + b * 0.114
        if abs(r - g) < 3 and abs(g - b) < 3:      # neutral pixel: skip the cube roots
            cs.append(0.0)
            if r > 70: sat.append(0.0)
            continue
        L, a, bb = _to_oklab(r, g, b)
        C = math.hypot(a, bb)
        cs.append(C)
        if L > 0.3: sat.append(C / L)
    cs.sort(); sat.sort()
    n = len(cs)
    return dict(c=sum(cs) / n, p90=cs[int(n * 0.9)], hi=sum(x > 0.05 for x in cs) / n,
                s90=sat[int(len(sat) * 0.9)] if sat else 0.0, l=ls / n / 255)


def mono_ok(im):
    """Quality gate of the mono source: near-monochrome or muted, no big colourful subject,
       and not a mostly white picture."""
    st = mono_stats(im)
    return all(st[k] <= v for k, v in MONO_MAX.items())


def _neutral_hex(h):
    r, g, b = hexrgb(h)
    _L, a, bb = _to_oklab(r, g, b)
    return math.hypot(a, bb) < 0.04


def sync_mono(n, cb=None):
    """Calm monochrome wallpapers: a few random queries from MONO_Q (random early page, by favourites),
       Wallhaven's own colour list as a pre-filter, then the chroma gate on the thumbnail and again on
       the downloaded file. Rejects are deleted and do not count."""
    import urllib.request, urllib.parse, io
    have = {f.split("-", 1)[-1] for f in os.listdir(ONLINE)}   # wallhaven ids, mono- or wallhaven- prefixed
    hdr = {"User-Agent": "rice-themes/1.0"}
    get = lambda u, t=15: urllib.request.urlopen(urllib.request.Request(u, headers=hdr), timeout=t)
    qs = [random.choice(g) for g in MONO_Q] + [random.choice(random.choice(MONO_Q))]
    pool, seen = [], set()
    for q, cat in qs:
        try:
            with get(MONO_URL % (cat, random.randint(1, 3), urllib.parse.quote(q + MONO_NOT)), 10) as r:
                data = json.load(r)["data"]
            if not data:      # few hits: page 1 always has them
                with get(MONO_URL % (cat, 1, urllib.parse.quote(q + MONO_NOT)), 10) as r:
                    data = json.load(r)["data"]
        except Exception:      # offline or rate limited: the pool just stays small
            continue
        for d in data:
            nm = os.path.basename(d["path"]).split("-", 1)[-1]
            cols = d.get("colors") or []
            if d.get("purity") != "sfw" or d.get("file_size", 0) > 8_000_000 or d.get("favorites", 0) < 10 \
                    or nm in have or nm in seen:
                continue
            if cols and sum(map(_neutral_hex, cols)) < 0.6 * len(cols):
                continue
            seen.add(nm); pool.append(d)
    random.shuffle(pool)
    got = 0
    for d in pool:
        if got >= n:
            break
        try:
            with get(d["thumbs"]["small"]) as r:
                if not mono_ok(Image.open(io.BytesIO(r.read()))):
                    continue
        except Exception:
            continue
        nm = os.path.basename(d["path"]).split("-", 1)[-1]
        if _save(nm, "mono-" + nm, d["path"], lambda u: get(u, 40), cb, check=mono_ok):
            got += 1
    return got


def item_for(path):
    name = os.path.splitext(os.path.basename(path))[0]
    isonl = os.path.dirname(path) == ONLINE
    name = name.split("-", 1)[1] if isonl and "-" in name else name
    return dict(name=name.replace("_", " ")[:28], wall=path, colors=None, online=isonl)


def search_wallhaven(q, n, cb, page=1):
    """Keyword search on Wallhaven (SFW, 16:9, >=1080p). cb(path) fires for every hit: at once for files we
       already have, after the download for new ones. Returns how many hits were delivered."""
    import urllib.request, urllib.parse
    os.makedirs(ONLINE, exist_ok=True)
    hdr = {"User-Agent": "rice-themes/1.0"}
    url = ("https://wallhaven.cc/api/v1/search?categories=110&purity=100&atleast=1920x1080&ratios=16x9"
           "&sorting=relevance&page=%d&q=" % page + urllib.parse.quote(q))
    with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=10) as r:
        data = json.load(r)["data"]
        hits = [d for d in data if d.get("purity") == "sfw" and d.get("file_size", 0) <= 8_000_000][:n]
    if not data:
        return -1                      # past the last page
    uo = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=hdr), timeout=40)
    got = 0
    for d in hits:
        nm = os.path.basename(d["path"])
        path = os.path.join(ONLINE, nm)
        if os.path.exists(path):
            cb(path); got += 1
        else:
            got += _save(nm, nm, d["path"], uo, lambda p=path: cb(p))
    if got:
        prune(MAX_ONLINE)
    return got


def sync(n=PER_RUN, cb=None):
    """Pull n new wallpapers from the chosen source(s); the oldest downloads rotate out, so it never runs dry."""
    os.makedirs(ONLINE, exist_ok=True)
    src = source()
    got = 0
    if src == "mono":
        got = sync_mono(n, cb)
    elif src == "wallhaven":
        got = sync_wallhaven(n, cb)
    elif src == "minimal":
        got = sync_minimal(n, cb)
    else:
        got = sync_wallhaven((n + 1) // 2, cb) + sync_minimal(n // 2, cb)
    if got:
        prune(MAX_ONLINE)
    return got


_PAL = {}
PAL_DIR = f"{CACHE}/pal"
PAL_VER = 4          # bump when _palette changes, old cache files are then ignored


def _pal_file(path, light):
    st = os.stat(path)
    k = f"{os.path.realpath(path)}|{st.st_mtime_ns}|{st.st_size}|{int(light)}|{PAL_VER}"
    return f"{PAL_DIR}/{hashlib.md5(k.encode()).hexdigest()}.json"


def palette(path, light=False):
    """Palette for a wallpaper. Memory cache, then a disk cache (~/.cache/theme/pal, keyed by path, mtime,
       size and PAL_VER) so a fresh theme-switch does not re-extract every picture it shows."""
    k = (path, light)
    if k not in _PAL:
        try:
            f = _pal_file(path, light)
            try:
                c = json.load(open(f))
                if not all(isinstance(c.get(x), str) for x in KEYS):
                    raise ValueError
            except (OSError, ValueError):
                c = _palette(path, light)
                os.makedirs(PAL_DIR, exist_ok=True)
                _write(f, json.dumps(c))
            _PAL[k] = c
        except (FileNotFoundError, OSError):     # an online wallpaper pruned while it was being read: neutral, not cached
            return dict(bg="#f4f4f4", bg2="#e6e6e6", border="#c8c8c8", fg="#161616", dim="#5c5c5c", accent="#262626", accent2="#555555") if light \
                else dict(bg="#101010", bg2="#1b1b1b", border="#303030", fg="#f2f2f2", dim="#9a9a9a", accent="#e6e6e6", accent2="#b8b8b8")
    return _PAL[k]


# ---- colour extraction (OKLab) ------------------------------------------------------------
def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _to_oklab(r, g, b):
    r, g, b = _lin(r), _lin(g), _lin(b)
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def _from_oklab(L, a, b):
    """-> linear-light (r, g, b), not clipped"""
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def oklch_hex(L, C, h):
    """OKLCH -> '#rrggbb'. Chroma is reduced until the colour fits in sRGB, so lightness and hue hold."""
    L = max(0.0, min(1.0, L))
    for _ in range(24):
        rgb = _from_oklab(L, C * math.cos(h), C * math.sin(h))
        if all(-0.0005 <= x <= 1.0005 for x in rgb):
            break
        C *= 0.92
    out = []
    for x in rgb:
        x = max(0.0, min(1.0, x))
        x = 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
        out.append(round(x * 255))
    return "#%02x%02x%02x" % tuple(out)


def _pixels(path):
    """64x64 copy of the picture as [(r, g, b, count)]: pixels binned at 4 bits per channel, each bin keeps its mean colour."""
    im = Image.open(path)
    im.draft("RGB", (256, 256))               # JPEG: decode at 1/2..1/8 scale, most of the old cost was the full 4K decode
    if im.mode == "P" and "transparency" in im.info:
        im = im.convert("RGBA")
    im = im.convert("RGB")
    im.thumbnail((64, 64))
    bins = {}
    for r, g, b in im.getdata():
        k = (r >> 4, g >> 4, b >> 4)
        a = bins.get(k)
        if a is None:
            bins[k] = [r, g, b, 1]
        else:
            a[0] += r; a[1] += g; a[2] += b; a[3] += 1
    return [(a[0] / a[3], a[1] / a[3], a[2] / a[3], a[3]) for a in bins.values()]


def _hdiff(a, b):
    d = abs(a - b) % (2 * math.pi)
    return min(d, 2 * math.pi - d)


def _families(path):
    """Hue families of the picture, measured on its pixels (no clustering, so no random seed):
       for 72 hues around the circle, the coloured pixels within +-26 deg. Returns (fams, meanL, rel);
       fams = [(C, h, share)] where C and h are the weighted mean colour of the family and share its
       part of the picture. A sky in light and dark blue is one blue family. rel = mean chroma relative
       to lightness (C / max(L, 0.2)): how colourful the picture looks, fair to dark pictures too."""
    px = []
    for r, g, b, w in _pixels(path):
        L, a, bb = _to_oklab(r, g, b)
        px.append((L, a, bb, math.hypot(a, bb), math.atan2(bb, a) % (2 * math.pi), w))
    n = float(sum(p[5] for p in px))
    meanL = sum(p[0] * p[5] for p in px) / n
    rel = sum(p[3] / max(p[0], 0.2) * p[5] for p in px) / n
    col = [p for p in px if p[3] >= 0.010 and p[0] > 0.10]
    fams = []
    for i in range(72):
        hc = i * 2 * math.pi / 72
        sa = sb = sw = 0.0
        for L, a, bb, C, h, w in col:
            if _hdiff(h, hc) < 0.45:
                sa += a * w; sb += bb * w; sw += w
        if sw:
            fams.append((math.hypot(sa, sb) / sw, math.atan2(sb, sa) % (2 * math.pi), sw / n))
    return fams, meanL, rel


def _score(f):
    return f[2] ** 0.45 * f[0] ** 1.3


def _palette(path, light=False):
    fams, meanL, rel = _families(path)
    # the characteristic colour: present in the picture AND colourful (a dull dominant tone loses)
    cand = [f for f in fams if f[0] >= 0.010 and f[2] >= 0.01]
    best = max(cand, key=_score) if cand else None
    if not best:
        # white / black / grey picture: neutral instead of an invented colour
        if light:
            return dict(bg="#f4f4f4", bg2="#e6e6e6", border="#c8c8c8", fg="#161616", dim="#5c5c5c", accent="#262626", accent2="#555555")
        return dict(bg="#101010", bg2="#1b1b1b", border="#303030", fg="#f2f2f2", dim="#9a9a9a", accent="#e6e6e6", accent2="#b8b8b8")
    C0, h, _share = best
    # a dull olive reads as green to the eye once the context is dark; its numeric hue is yellower
    if C0 < 0.04 and 1.65 < h < 2.2:
        h += 0.32
    # a second, different colour that really exists in the picture, else a gentle neighbour hue
    others = [f for f in cand if _hdiff(f[1], h) > 0.6 and f[0] >= 0.03]
    h2 = max(others, key=_score)[1] if others else h + 0.5
    # follow the picture: a dark picture gets a mid-light accent (not neon), a bright one a light one;
    # muted pictures give a muted accent, vivid ones a vivid one
    LA = max(0.64, min(0.75, 0.50 + meanL * 0.55))
    C = max(0.058, min(C0 * 2.2, 0.19))
    f = min(1.0, C0 / 0.05)                    # how colourful the picture is -> tint of the surfaces
    # near-grey pictures (black-and-white photos, faded film, ink): the faint tint is JPEG/film cast, not
    # a colour; boosting it to C 0.058 invents a hue. Fade towards an off-white (dark) / charcoal (light)
    # accent that keeps only a breath of the tint. Full colour once the chosen family is clearly coloured
    # (C0 >= 0.042, e.g. a small logo on grey) or the picture as a whole is (rel >= 0.06, e.g. a dark
    # moody forest whose pixels are all faintly green); neutral below C0 0.012 and rel 0.03.
    t = max(0.0, min(1.0, max((C0 - 0.012) / 0.03, (rel - 0.03) / 0.03))) ** 2
    Cn = min(C0, 0.012)
    C = Cn + (C - Cn) * t
    C2 = C * 0.9 if t > 0.3 else Cn * 0.7      # no invented second hue on a grey picture
    if light:
        return dict(bg=oklch_hex(0.97, 0.012 * f, h), bg2=oklch_hex(0.93, 0.018 * f, h), border=oklch_hex(0.83, 0.025 * f, h),
                    fg=oklch_hex(0.20, 0.03 * f, h), dim=oklch_hex(0.45, 0.03 * f, h),
                    accent=oklch_hex(0.30 + 0.20 * t, C, h), accent2=oklch_hex(0.42 + 0.06 * t, C2, h2))
    LA = 0.86 + (LA - 0.86) * t
    return dict(bg=oklch_hex(0.17, 0.030 * f, h), bg2=oklch_hex(0.23, 0.036 * f, h), border=oklch_hex(0.34, 0.040 * f, h),
                fg=oklch_hex(0.95, 0.010 * f, h), dim=oklch_hex(0.70, 0.024 * f, h),
                accent=oklch_hex(LA, C, h), accent2=oklch_hex(LA - 0.04 - 0.10 * (1 - t), C2, h2))


_LUM = {}


def luminance(wall):
    if wall not in _LUM:
        try:
            im = Image.open(wall); im.draft("L", (200, 120))
            g = im.convert("L").resize((48, 27))
            px = list(g.getdata())
            _LUM[wall] = sum(px) / len(px) / 255
        except Exception:
            _LUM[wall] = 0.2
    return _LUM[wall]


def scheme(wall):
    """'dark' or 'light' for the solid (glass off) look: user override, else from the wallpaper."""
    import settings
    s = settings.get("scheme")
    if s in ("dark", "light"):
        return s
    return "light" if luminance(wall) > 0.55 else "dark"


def thumb(path):
    t = f"{THUMBS}/{hashlib.md5(path.encode()).hexdigest()}.png"
    if not os.path.exists(t):
        im = Image.open(path).convert("RGB")
        im.thumbnail((360, 220))
        im.save(t)
    return t


def _cur():
    try:
        return os.path.realpath(open(f"{CACHE}/wall").read().strip())
    except OSError:
        return ""


def items(online=None, cur=None):
    """Offline: the wallpapers on this machine (online downloads that are the current one still show).
       Online: the current wallpaper plus the downloaded ones, no other local ones."""
    import settings
    if online is None:
        online = settings.get("online")
    cur = cur or _cur()
    src = source()
    out = []
    for root, dirs, files in os.walk(WALLS):
        dirs.sort()
        for f in sorted(files):
            if f.lower().endswith(EXT) and not f.startswith("."):
                p = os.path.realpath(os.path.join(root, f))
                isonl = root == ONLINE
                if isonl and src != "both" and origin(p) != src and p != cur:
                    continue
                if online and not isonl and p != cur:
                    continue
                if not online and isonl and p != cur:
                    continue
                name = os.path.splitext(f)[0]
                name = name.split("-", 1)[1] if isonl and "-" in name else name
                out.append(dict(name=name.replace("_", " ")[:28], wall=p, colors=None, online=isonl))
    def _mt(path):
        try:
            return os.path.getmtime(path)
        except OSError:      # pruned or still downloading while the list is built
            return 0
    out = [i for i in out if os.path.exists(i["wall"])]
    out.sort(key=lambda i: (i["online"], _mt(i["wall"]) if i["online"] else 0, i["name"].lower()))
    if online:    # the current one first, then the feed
        out.sort(key=lambda i: i["wall"] != cur)
    return out


_LOOK = {}


def look(wall):
    """Terminal translucency from the wallpaper: bright or busy pictures get a more opaque, blurrier terminal."""
    if wall in _LOOK:
        return _LOOK[wall]
    try:
        from PIL import Image
        im = Image.open(wall); im.draft("L", (400, 300))
        g = im.convert("L").resize((96, 54))
        px = list(g.getdata()); w, h = 96, 54
        L = sum(px) / len(px) / 255
        gx = sum(abs(px[y * w + x] - px[y * w + x + 1]) for y in range(h) for x in range(w - 1))
        gy = sum(abs(px[y * w + x] - px[(y + 1) * w + x]) for y in range(h - 1) for x in range(w))
        busy = (gx + gy) / (2 * w * h * 255)
        r = dict(opacity=min(max(0.30 + 0.55 * max(0.0, L - 0.25) + 1.2 * busy, 0.30), 0.85),
                 blur=int(min(max(round(2 + busy * 40), 2), 6)))
    except Exception:
        r = dict(opacity=0.6, blur=3)
    _LOOK[wall] = r
    return r


def colors_for(item):
    """Palette for an item under the current glass setting. Returns (colors, glass, light)."""
    import settings
    glass = settings.get("glass")
    light = (not glass) and scheme(item["wall"]) == "light"
    c = item["colors"] or palette(item["wall"], light)
    import designs
    c = designs.palette(c, designs.name(), light)
    if not glass and not light and designs.name() == "default":          # solid dark menus: near black, only a breath of the wallpaper colour
        c = dict(c, bg=mixhex(c["bg"], "#050505", 0.6), bg2=mixhex(c["bg2"], "#0c0c0c", 0.5))
    return contrast_fix(c, light), glass, light


def _rl(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def cr(a, b):
    """WCAG contrast ratio of two #rrggbb colours (1 = identical, 21 = black on white)."""
    la, lb = _rl(a), _rl(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def contrast_fix(c, light):
    """Nothing in a theme may blend into its background: push text, accents and borders away from bg (and bg2, the
       cards) until they pass a minimum contrast. Colours keep their hue; they only get lighter (dark theme) or darker."""
    far = "#000000" if light else "#ffffff"
    need = (("fg", 9.0), ("dim", 5.0), ("accent", 5.0), ("accent2", 4.0), ("border", 1.8))
    c = dict(c)
    for k, mn in need:
        if k not in c:
            continue
        for bgk in ("bg", "bg2"):
            if bgk not in c:
                continue
            v, i = c[k], 0
            while cr(v, c[bgk]) < mn and i < 20:
                v = mixhex(v, far, 0.1); i += 1
            c[k] = v
    return c


HOME_CACHE = os.path.expanduser('~/.cache/rice')
import threading as _th
_APPLY_LOCK = _th.RLock()      # one apply at a time: a slow preview can never finish after (and undo) the revert


def _log(msg):
    try:
        import time
        open(f"{HOME_CACHE}/theme-switch.log", "a").write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass


def apply(item, final=True):
    with _APPLY_LOCK:
        _log(f"apply final={final} {os.path.basename(item['wall'])}")
        _apply(item, final)
    if final:
        autocheck(2)


def autocheck(delay):
    """Run rice-themecheck --fix in the background (after a final apply and at login). Skipped while the
       checker itself re-applies, so it can never loop."""
    if os.environ.get("RICE_THEMECHECK"):
        return
    subprocess.Popen(["sh", "-c", f"sleep {delay}; exec {HOME}/.local/bin/rice-themecheck --fix -q"],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, close_fds=True)


def rasi_text(c, glass):
    a1, a2 = ("b8", "cc") if glass else ("ff", "ff")
    return ("* {\n" + "".join(f"    {k}: {c[k]};\n" for k in KEYS) + f'    font: "{c.get("font_mono") or mood(c)[2]} 11";\n' +
            f"    bga: {c['bg']}{a1};\n    bgb: {c['bg2']}{a2};\n}}\n")


XRES = (("normbgcolor", "bg"), ("normbordercolor", "border"), ("normfgcolor", "dim"),
        ("selbgcolor", "accent"), ("selbordercolor", "accent"), ("selfgcolor", "bg"))


def xres_text(c):
    return "".join(f"dwm.{r}: {c[k]}\n" for r, k in XRES)


def look_for(wall, glass):
    """Terminal opacity + picom blur that apply() uses: from the wallpaper, then the user's overrides."""
    import settings
    lk = dict(look(wall))
    if not glass:
        lk["opacity"] = 1.0
    else:
        to = settings.sget("term_opacity")
        if to is not None:
            lk["opacity"] = float(to)
    bl = settings.sget("blur")
    if bl is not None:
        lk["blur"] = int(bl)
    return lk


# Font personality from the palette: grey themes read serious, loud warm ones playful, cool saturated ones techy.
# fonts: (sans UI/clock, mono UI/terminal). Mono must be fixed-width (Konsole).
MOODS = {
    "serious": ("IBM Plex Sans", "IBM Plex Mono"),
    "calm":    ("Inter Display", "JetBrains Mono"),
    "soft":    ("Nunito", "JetBrains Mono"),
    "elegant": ("Fraunces", "IBM Plex Mono"),
    "techy":   ("Space Grotesk", "Space Mono"),
    "playful": ("Fredoka", "Space Mono"),
}


def mood(c):
    """-> (mood name, sans, mono) from accent chroma and hue, plus how bright the background is."""
    try:
        ch, hs, n = 0.0, [], 0
        for k in ("accent", "accent2"):
            L, a, b = _to_oklab(*hexrgb(c[k]))
            ch += math.hypot(a, b); hs.append(math.degrees(math.atan2(b, a)) % 360)
        ch /= 2
        bgL = _to_oklab(*hexrgb(c["bg"]))[0]
        h = hs[0]
    except Exception:
        return ("calm",) + MOODS["calm"]
    if ch < 0.035:
        m = "serious"
    elif ch < 0.075:
        m = "elegant" if (bgL > 0.6 or 20 < h < 110) else "calm"
    elif ch < 0.13:
        m = "soft" if (h < 200 or h > 330) else "techy"
    else:
        m = "playful" if (h > 300 or h < 120) else "techy"
    return (m,) + MOODS[m]


def _write(path, text):
    """Atomic write: cards, rice-lyrics and the bar read these files live and must never see half a file."""
    tmp = f"{path}.{os.getpid()}.{_th.get_ident()}.tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def _apply(item, final=True):
    c, glass, light = colors_for(item)
    import designs
    mo, sans, mono = mood(c)
    dn = designs.name()
    sans, mono = designs.fonts(dn, sans, mono)
    c = dict(c, mood=mo if dn == "default" else dn, font_sans=sans, font_mono=mono, design=dn)
    _write(f"{CACHE}/colors.json", json.dumps(dict(c, glass=1 if glass else 0, light=1 if light else 0), indent=1))
    _write(f"{CACHE}/wall", item["wall"])
    _write(f"{CACHE}/current", item["name"])
    # the QML shell measures the wallpaper's brightness (to pick light or dark widget text) from this file; it used to be
    # left on an old wallpaper, so widgets got text for the wrong picture
    try:
        _write(os.path.expanduser("~/.cache/hyprquickpaper-current"), item["wall"] + "\n")
    except Exception:
        pass
    _write(f"{CACHE}/colors.rasi", rasi_text(c, glass))
    _write(f"{CACHE}/dwm.Xresources", xres_text(c))
    # the QML shell (widgets, menus, visualizer) follows @define-color accent in this file (it re-reads it every 2 s)
    try:
        _write(os.path.expanduser("~/.config/waybar/colors.css"), "".join(
            f"@define-color {k} {c[k]};\n" for k in ("accent", "accent2", "bg", "bg2", "fg", "dim", "border") if k in c))
    except Exception:
        pass
    subprocess.run(["feh", "--bg-fill", item["wall"]], timeout=10)   # wait: a late preview feh must not overwrite the revert
    subprocess.run(["xrdb", "-merge", f"{CACHE}/dwm.Xresources"])  # dwm reloads on property change
    try:
        import hooks
        hooks.run_all(c, item["wall"], final, look_for(item["wall"], glass), glass)
    except Exception:
        import traceback
        _log("HOOKS FAILED: " + traceback.format_exc().strip().splitlines()[-1])


def mixhex(a, b, f):
    ra, rb = hexrgb(a), hexrgb(b)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * f) for x, y in zip(ra, rb))


def current_item():
    try:
        name = open(f"{CACHE}/current").read().strip()
        for it in items():
            if it["name"] == name:
                return it
    except Exception:
        pass
    return None
