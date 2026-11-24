"""Favorites for apps and themes (~/.cache/rice/favs.json: {"apps": [...], "themes": [...]})."""
import os, json

PATH = os.path.expanduser("~/.cache/rice/favs.json")


def load():
    try:
        return json.load(open(PATH))
    except Exception:
        return {}


def has(kind, key):
    return key in load().get(kind, [])


def toggle(kind, key):
    d = load()
    l = d.setdefault(kind, [])
    if key in l:
        l.remove(key)
    else:
        l.append(key)
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    json.dump(d, open(PATH + ".tmp", "w"))
    os.replace(PATH + ".tmp", PATH)
    return key in l
