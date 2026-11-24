"""Design languages: palette roles + fonts + dock look. Chosen with settings 'design'.
   default = wallpaper palette + mood fonts; material3 = Material You tonal roles from the wallpaper seed;
   macos = system greys + blue, Inter, big magnify dock; brutal = black/white, hard edges, mono."""
import math

DESIGNS = {
    "default":  dict(label="Wallpaper"),
    "material3": dict(label="Material 3", sans="Roboto Flex", mono="Roboto Mono"),
    "macos":    dict(label="macOS", sans="Inter Display", mono="JetBrains Mono"),
    "brutal":   dict(label="Brutal", sans="Space Grotesk", mono="Space Mono"),
}
ORDER = ("default", "material3", "macos", "brutal")


def name():
    try:
        import settings
        d = settings.get("design")
        return d if d in DESIGNS else "default"
    except Exception:
        return "default"


def _seed(c):
    """(hue radians, chroma) of the wallpaper accent."""
    import themes
    L, a, b = themes._to_oklab(*themes.hexrgb(c["accent"]))
    return math.atan2(b, a), math.hypot(a, b)


def palette(c, design, light):
    """Return colours for a design, or c unchanged for 'default'."""
    if design == "default":
        return c
    import themes
    H = themes.oklch_hex
    if design == "material3":
        h, ch = _seed(c)
        k = min(ch, 0.16) if ch < 0.02 else max(0.035, min(ch, 0.16))   # seed strength; a grey wallpaper stays grey (no invented hue)
        t = lambda L, f: H(L, k * f, h)
        if light:
            return dict(c, bg=t(0.985, 0.10), bg2=t(0.94, 0.22), border=t(0.78, 0.30), fg=t(0.20, 0.12), dim=t(0.45, 0.25),
                        accent=t(0.48, 1.0), accent2=H(0.50, k * 0.8, h + 1.05))
        return dict(c, bg=t(0.18, 0.12), bg2=t(0.25, 0.20), border=t(0.42, 0.28), fg=t(0.92, 0.08), dim=t(0.76, 0.22),
                    accent=t(0.83, 1.0), accent2=H(0.82, k * 0.8, h + 1.05))
    if design == "macos":
        if light:
            return dict(c, bg="#f2f2f7", bg2="#ffffff", border="#d1d1d6", fg="#1c1c1e", dim="#6c6c70", accent="#007aff", accent2="#af52de")
        return dict(c, bg="#1c1c1e", bg2="#2c2c2e", border="#3a3a3c", fg="#f5f5f7", dim="#98989d", accent="#0a84ff", accent2="#bf5af2")
    if design == "brutal":
        h, ch = _seed(c)
        ac = H(0.88, max(ch, 0.16), h)
        if light:
            return dict(c, bg="#ffffff", bg2="#ededed", border="#000000", fg="#000000", dim="#444444", accent=H(0.55, max(ch, 0.18), h), accent2="#000000")
        return dict(c, bg="#000000", bg2="#141414", border="#ffffff", fg="#ffffff", dim="#bdbdbd", accent=ac, accent2="#ffffff")
    return c


def fonts(design, mood_sans, mood_mono):
    d = DESIGNS.get(design) or {}
    return d.get("sans", mood_sans), d.get("mono", mood_mono)


# Geometry per design language (corner radii in px, border width, picom class suffix). picom matches window classes,
# so a design that changes a radius needs its own class: RiceCard -> RiceCardM3 / RiceCardMac / RiceCardBr (see rice.conf).
GEO = {
    "default":   dict(card=26, dock=22, desk=22, bw=1.5, sfx=""),
    "material3": dict(card=34, dock=30, desk=30, bw=0.0, sfx="M3"),
    "macos":     dict(card=18, dock=15, desk=15, bw=1.0, sfx="Mac"),
    "brutal":    dict(card=0,  dock=0,  desk=0,  bw=3.0, sfx="Br"),
}


def geo(dn=None):
    """Geometry of the live design (read from colors.json, no settings import)."""
    if dn is None:
        try:
            import json, os
            dn = json.load(open(os.path.expanduser("~/.cache/theme/colors.json"))).get("design", "default")
        except Exception:
            dn = "default"
    return GEO.get(dn, GEO["default"])
