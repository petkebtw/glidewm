"""Persistent rice settings (~/.cache/rice/settings.json)."""
import os, json

PATH = os.path.expanduser("~/.cache/rice/settings.json")
DEFAULTS = dict(glass=True, online=False, source="mono", scheme="auto", anim=True, anim_style="ghost", ricemode=False, sys={})
# motion presets (rice.motion()), control centre (rice-center), dock options (rice-dock); setdefault so other additions win
for _k, _v in (("motion", "calm"), ("motion_speed", 1.0), ("dnd", False), ("dock", {}), ("design", "default")):
    DEFAULTS.setdefault(_k, _v)


def load():
    d = dict(DEFAULTS)
    try:
        d.update(json.load(open(PATH)))
    except Exception:
        pass
    # legacy files from before settings.json
    try:
        if "source" not in json.load(open(PATH)):
            d["source"] = open(os.path.expanduser("~/.cache/rice/source")).read().strip() or d["source"]
    except Exception:
        pass
    d["ricemode"] = os.path.exists(os.path.expanduser("~/.cache/rice/ricemode"))
    return d


def get(k):
    return load().get(k, DEFAULTS.get(k))


def put(k, v):
    d = load()
    d[k] = v
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    tmp = PATH + ".tmp"
    json.dump({x: d[x] for x in DEFAULTS if x != "ricemode"}, open(tmp, "w"))
    os.replace(tmp, PATH)
    if k == "source":
        open(os.path.expanduser("~/.cache/rice/source"), "w").write(v)
    if k == "ricemode":
        f = os.path.expanduser("~/.cache/rice/ricemode")
        if v:
            open(f, "w").close()
        elif os.path.exists(f):
            os.remove(f)
    return d


def sget(k, default=None):
    """System-level settings (keyboard, mouse, night light, gaps ...): only keys the user changed are present."""
    return (load().get("sys") or {}).get(k, default)


def sput(k, v):
    d = dict(load().get("sys") or {})
    if v is None:
        d.pop(k, None)
    else:
        d[k] = v
    return put("sys", d)
