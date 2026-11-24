"""Tiny MPRIS client shared by cards and the lock screen."""
import os, hashlib, urllib.request
from gi.repository import Gio, GLib

BUS = Gio.bus_get_sync(Gio.BusType.SESSION, None)
IFACE = "org.mpris.MediaPlayer2.Player"


def players():
    r = BUS.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListNames",
                      None, GLib.VariantType("(as)"), 0, 500, None)
    return [n for n in r[0] if n.startswith("org.mpris.MediaPlayer2.")]


def get(name, prop):
    r = BUS.call_sync(name, "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties", "Get",
                      GLib.Variant("(ss)", (IFACE, prop)), GLib.VariantType("(v)"), 0, 500, None)
    return r[0]


def call(name, method):
    try:
        BUS.call_sync(name, "/org/mpris/MediaPlayer2", IFACE, method, None, None, 0, 500, None)
    except Exception:
        pass


def active():
    ps = players()
    for p in ps:
        try:
            if get(p, "PlaybackStatus") == "Playing":
                return p
        except Exception:
            pass
    return ps[0] if ps else None


def art_path(url, net=True):
    try:
        if url.startswith("file://"):
            return url[7:]
        if not url:
            return None
        path = os.path.expanduser("~/.cache/rice/art_" + hashlib.md5(url.encode()).hexdigest())
        if not os.path.exists(path):
            if not net:
                return None
            with urllib.request.urlopen(url, timeout=4) as r, open(path + ".part", "wb") as f:
                f.write(r.read())
            os.replace(path + ".part", path)
            _prune_art()
        return path
    except Exception:
        return None


def _prune_art(keep=40):
    d = os.path.expanduser("~/.cache/rice")
    fs = sorted((os.path.join(d, f) for f in os.listdir(d) if f.startswith("art_") and not f.endswith(".part")), key=os.path.getmtime)
    for f in fs[:-keep]:
        try: os.remove(f)
        except OSError: pass


def info(name):
    """-> dict(title, artist, length, pos, playing, art) or None"""
    try:
        md = get(name, "Metadata")
        ar = md.get("xesam:artist", [])
        return dict(title=str(md.get("xesam:title", "Unknown")),
                    artist=", ".join(ar) if isinstance(ar, list) else str(ar),
                    length=max(int(md.get("mpris:length", 1)), 1),
                    pos=int(get(name, "Position")),
                    playing=get(name, "PlaybackStatus") == "Playing",
                    art=art_path(str(md.get("mpris:artUrl", ""))))
    except Exception:
        return None
