"""Synced lyrics from lrclib.net (no key). get(artist, title, seconds) -> [(sec, text)] or None. Cached on disk."""
import os, re, json, hashlib, urllib.request, urllib.parse

CACHE = os.path.expanduser("~/.cache/rice/lyrics")
UA = {"User-Agent": "rice-media/1.0"}


def _fetch(url, timeout):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def parse(lrc):
    out = []
    for ln in lrc.splitlines():
        m = re.match(r"^((?:\[\d+:\d+(?:[.:]\d+)?\])+)\s*(.*)$", ln)
        if not m:
            continue
        for mm, ss in re.findall(r"\[(\d+):(\d+(?:[.:]\d+)?)\]", m.group(1)):
            out.append((int(mm) * 60 + float(ss.replace(":", ".")), re.sub(r"<[^>]*>", "", m.group(2)).strip()))
    out.sort(key=lambda x: x[0])
    return out or None


def clean(s):
    s = re.sub(r"[\(\[][^)\]]*(speed|slowed|reverb|nightcore|official|lyric|audio|video|remix)[^)\]]*[\)\]]", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip(" -")


def get(artist, title, secs, timeout=3.0):
    key = hashlib.md5(f"{artist}|{title}".encode()).hexdigest()
    path = os.path.join(CACHE, key + ".json")
    try:
        with open(path) as f:
            d = json.load(f)
        return [tuple(x) for x in d] if d else None
    except Exception:
        pass
    res = None
    try:
        t = clean(title)
        q = [dict(track_name=t, artist_name=artist, duration=int(secs))] if artist else []
        for p in q:
            try:
                res = _fetch("https://lrclib.net/api/get?" + urllib.parse.urlencode(p), timeout).get("syncedLyrics")
            except Exception:
                res = None
            if res:
                break
        if not res:
            for qs in ([f"{artist} {t}"] if artist else []) + [t]:
                items = _fetch("https://lrclib.net/api/search?" + urllib.parse.urlencode(dict(q=qs)), timeout)
                items = [i for i in items if i.get("syncedLyrics")]
                items.sort(key=lambda i: abs((i.get("duration") or 0) - secs))
                if items and abs((items[0].get("duration") or 0) - secs) < 8:
                    res = items[0]["syncedLyrics"]
                    break
        lines = parse(res) if res else None
    except Exception:
        return None  # network error: do not cache
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w") as f:
        json.dump(lines or [], f)
    return lines
