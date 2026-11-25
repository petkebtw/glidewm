"""Is a picture a wallpaper? Screenshots, icons and other small or tall pictures are not.
   is_wallpaper(path) -> bool; dedupe(paths, keep=()) -> the paths without duplicates (the same picture under another
   name, folder or size: perceptual hash). Used by themes.items() and the shell's rice-walls (port.sh hooks it in).
   A wallpaper: at least MIN_W x MIN_H, landscape (aspect MIN_AR .. MAX_AR), not named or filed like a screenshot.
   Sizes are read from the file header and cached by mtime in ~/.cache/rice/wallcheck.json."""
import json
import os
import re
import struct
import sys

MIN_W, MIN_H = 1600, 900
MIN_AR, MAX_AR = 1.25, 2.7
SHOT = re.compile(r"(^|[^a-z])(screenshot|screen[ _-]?shot|scrot|snip|capture|bildschirmfoto|zrzut)", re.I)
SHOT_DIRS = {"screenshots", "screenshot", "screen shots", "captures"}
VIDEOS = (".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v", ".gif")
CACHE = os.path.expanduser("~/.cache/rice/wallcheck.json")
_cache = None
_dirty = False


def _size(path):
    """(w, h) from the header of a PNG, JPEG, WebP, BMP; Pillow for anything else; None when unknown"""
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", head[16:24])
            if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                f.seek(12)
                kind = f.read(4)
                if kind == b"VP8X":
                    f.seek(24)
                    b = f.read(6)
                    return (int.from_bytes(b[0:3], "little") + 1, int.from_bytes(b[3:6], "little") + 1)
                if kind == b"VP8 ":
                    f.seek(26)
                    w, h = struct.unpack("<HH", f.read(4))
                    return (w & 0x3FFF, h & 0x3FFF)
                if kind == b"VP8L":
                    f.seek(21)
                    b = f.read(4)
                    bits = int.from_bytes(b, "little")
                    return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
            if head[:2] == b"BM":
                w, h = struct.unpack("<ii", head[18:26])
                return (w, abs(h))
            if head[:2] == b"\xff\xd8":
                f.seek(2)
                while True:
                    m = f.read(2)
                    if len(m) < 2 or m[0] != 0xFF:
                        break
                    if m[1] in (0xD8, 0x01) or 0xD0 <= m[1] <= 0xD7:
                        continue
                    ln = struct.unpack(">H", f.read(2))[0]
                    if m[1] in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        h, w = struct.unpack(">HH", f.read(5)[1:5])
                        return (w, h)
                    f.seek(ln - 2, 1)
    except (OSError, struct.error):
        return None
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


def _load():
    global _cache
    if _cache is None:
        try:
            _cache = json.load(open(CACHE))
        except (OSError, ValueError):
            _cache = {}
    return _cache


def save():
    global _dirty
    if not _dirty:
        return
    try:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        tmp = CACHE + ".tmp"
        json.dump(_cache, open(tmp, "w"))
        os.replace(tmp, CACHE)
        _dirty = False
    except OSError:
        pass


def size(path):
    global _dirty
    c = _load()
    try:
        m = os.path.getmtime(path)
    except OSError:
        return None
    e = c.get(path)
    if e and e[0] == m:
        return tuple(e[1]) if e[1] else None
    s = _size(path)
    c[path] = [m, list(s) if s else None]
    _dirty = True
    return s


def sig(path):
    """(256-bit difference hash as int, 4x4 RGB grid, 16x16 contrast-stretched grey) of the picture, cached by mtime; None when unreadable"""
    global _dirty
    c = _load()
    try:
        m = os.path.getmtime(path)
    except OSError:
        return None
    e = c.get("#3" + path)
    if e and e[0] == m:
        return (int(e[1][0], 16), e[1][1], e[1][2]) if e[1] else None
    v = None
    try:
        import warnings
        from PIL import Image
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with Image.open(path) as im:
                im.draft("RGB", (320, 180))          # JPEG: decode at a fraction of the size, much faster
                rgb = im.convert("RGB")
                g = rgb.convert("L").resize((17, 16), Image.BILINEAR).tobytes()
                grid = list(rgb.resize((4, 4), Image.BILINEAR).tobytes())
                from PIL import ImageOps
                thumb = list(ImageOps.autocontrast(rgb.convert("L").resize((16, 16), Image.BILINEAR), cutoff=1).tobytes())
        h = 0
        for y in range(16):
            for x in range(16):
                h = (h << 1) | (g[y * 17 + x] > g[y * 17 + x + 1])
        v = (h, grid, thumb)
    except Exception:
        v = None
    c["#3" + path] = [m, ["%x" % v[0], v[1], v[2]] if v else None]
    _dirty = True
    return v


DUP_BITS = 24    # of 256: hashes this close have the same shapes
DUP_COLOR = 14   # mean difference of the 4x4 colour grid (0-255): and the same colours
DUP_THUMB = 1    # cells (of 256) of the contrast-stretched 16x16 grey picture that may differ (> 24): and the same
                 # subject. Copies differ by at most 5 anywhere; dark minimal wallpapers (a small figure on black) hash
                 # alike, but 6+ of their stretched cells differ


def same(a, b):
    if bin(a[0] ^ b[0]).count("1") > DUP_BITS:
        return False
    if sum(abs(x - y) for x, y in zip(a[1], b[1])) / len(a[1]) > DUP_COLOR:
        return False
    return sum(abs(x - y) > 24 for x, y in zip(a[2], b[2])) <= DUP_THUMB


def dedupe(paths, keep=()):
    """one path per picture, the best copy: the most pixels, then lossless (PNG, WebP lossless ...) over JPEG, then
       the bigger file (less compression); ties: the one in `keep` (the current wallpaper), not a download, the
       shortest path"""
    keep = set(keep)
    def rank(p):
        s = size(p) or (0, 0)
        try:
            b = os.path.getsize(p)
        except OSError:
            b = 0
        lossless = not p.lower().endswith((".jpg", ".jpeg"))
        return (s[0] * s[1], lossless, b, p in keep, "/online/" not in p, -len(p))
    kept, sigs = [], []
    for p in sorted(paths, key=rank, reverse=True):
        if p.lower().endswith(VIDEOS):
            kept.append(p)
            continue
        v = sig(p)
        if v is not None and any(same(v, w) for w in sigs):
            continue
        kept.append(p)
        if v is not None:
            sigs.append(v)
    save()
    order = {p: i for i, p in enumerate(paths)}
    return sorted(kept, key=order.get)


def is_wallpaper(path):
    low = path.lower()
    if low.endswith(VIDEOS):
        return True                      # live wallpapers: judged by the shell
    if SHOT.search(os.path.basename(path)):
        return False
    if any(p.lower() in SHOT_DIRS for p in os.path.dirname(path).split(os.sep)):
        return False
    s = size(path)
    if not s:
        return True                      # unknown size: do not hide it
    w, h = s
    if w < MIN_W or h < MIN_H:
        return False
    return MIN_AR <= w / h <= MAX_AR


def filter(paths, keep=()):
    """wallpapers only, one copy of each"""
    return dedupe([p for p in paths if is_wallpaper(p)], keep)


if __name__ == "__main__" and sys.argv[1:2] == ["--dupes"]:
    import sys
    ps = [os.path.join(r, f) for d in sys.argv[2:] for r, _, fs in os.walk(d) for f in fs if not f.startswith(".")]
    ps = [p for p in ps if is_wallpaper(p)]
    k = set(dedupe(ps))
    for p in sorted(set(ps) - k):
        print("dup\t" + p)
    print("%d pictures, %d duplicates" % (len(ps), len(ps) - len(k)))
    raise SystemExit
if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        print("%s\t%s\t%s" % ("yes" if is_wallpaper(p) else "no", size(p), p))
    save()
