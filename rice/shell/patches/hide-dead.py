#!/usr/bin/env python3
"""Hide Settings rows that cannot work on glidewm/X11 (port.sh runs it on the built rice-settings).
  hide-dead.py DIR [--report]
A row (an element with a `label:`) is dead when its block calls a Hyprland/niri-only backend (DEAD), or when it is
listed in EXTRA (file, label) / SECTIONS (file, section title). Dead elements get `visible: false` (an existing
`visible:` of the element is replaced)."""
import os, re, sys

DEAD = re.compile(r"ctl\.(hset|hv|ha|setAnim)\b|hypr-set|rice-minimal|rice-effects\\?\"? (lite|gaming)|"
                  r"\"rice-effects\", \"(lite|gaming)\"|effects\.(lite|gaming)|setLite|setGaming|hyprsunset|nightlight|rice-taskview")
# rows the regex cannot see (their backend is reached through a helper function)
EXTRA = {
    ("HomePage.qml", "Light mode"), ("HomePage.qml", "Window blur"), ("HomePage.qml", "Animations"),
    ("HomePage.qml", "Bar transparency"),
    ("HomePage.qml", "Mouse wheel speed"), ("HomePage.qml", "Touchpad scroll speed"), ("HomePage.qml", "Natural scrolling"),
    ("HomePage.qml", "Tap to click"), ("HomePage.qml", "Pointer speed"),
    ("GamingPage.qml", "Light mode"), ("GamingPage.qml", "Keep blur & transparency"), ("GamingPage.qml", "Keep animations"),
    ("GamingPage.qml", "Keep shadows"), ("GamingPage.qml", "Power mode"), ("GamingPage.qml", "Keep gaps"), ("GamingPage.qml", "Blur behind the game bar"),
    ("ServicesPage.qml", "Gaming mode"), ("ServicesPage.qml", "Night light warmth"),
    ("DesktopPage.qml", "Light mode"), ("DesktopPage.qml", "Blur behind widgets"), ("DesktopPage.qml", "Super alone opens it"),
    ("DesktopPage.qml", "Live pictures of the windows"), ("DesktopPage.qml", "Empty workspaces too"),
    ("InterfacePage.qml", "Blur"),
    ("NotificationsPage.qml", "Blur behind pop-ups"), ("NotificationsPage.qml", "Blur behind the control center"),
    ("WindowsPage.qml", "Border thickness"), ("WindowsPage.qml", "Corner rounding"),
    ("WindowsPage.qml", "Shadows@1"), ("WindowsPage.qml", "Thickness@1"), ("WindowsPage.qml", "Intensity@1"),
    ("MotionPage.qml", "Animations"), ("MotionPage.qml", "Speed@1"),
    ("LookFeelPage.qml", "Minimal mode"), ("LookFeelPage.qml", "Window frame"), ("LookFeelPage.qml", "Frame width"),
    ("LookFeelPage.qml", "Solid windows"), ("LookFeelPage.qml", "Flat bar"),
}
SECTIONS = {("HomePage.qml", "Mouse & touchpad"), ("LookFeelPage.qml", "Minimal mode"), ("MotionPage.qml", "Windows")}
# whole elements found by the text that starts them (the `{` ends the pattern)
PATTERNS = [
    ("WindowsPage.qml", r"// ---------- a live sample ----------\s*Rectangle \{"),      # a Hyprland window preview
    ("WindowsPage.qml", r"Head \{ icon: \"rounded_corner\""),
    ("WindowsPage.qml", r"Head \{ icon: \"shadow\""),
    ("MotionPage.qml", r"Flow \{\s*id: flow\b"),                                          # Hyprland animation styles
]


def block(s, i):
    """the element around position i: (start of its `{`, end after its `}`)"""
    depth, j = 0, i
    while j > 0:
        j -= 1
        c = s[j]
        if c == "}":
            depth += 1
        elif c == "{":
            if depth == 0:
                break
            depth -= 1
    start, depth, k, q = j, 0, j, None
    while k < len(s):
        c = s[k]
        if q:
            if c == "\\":
                k += 2
                continue
            if c == q:
                q = None
        elif c in "\"'":
            q = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return start, k + 1
        k += 1
    return start, len(s)


def top_visible(s, a, b):
    """position of the element's own `visible:` (depth 1 inside its braces), or -1"""
    depth, k, q = 0, a, None
    while k < b:
        c = s[k]
        if q:
            if c == "\\":
                k += 2
                continue
            if c == q:
                q = None
        elif c in "\"'":
            q = c
        elif c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
        elif depth == 1 and s.startswith("visible:", k) and (k == 0 or not (s[k - 1].isalnum() or s[k - 1] in "._")):
            return k
        k += 1
    return -1


def hide(s, a, b):
    v = top_visible(s, a, b)
    if v >= 0:
        e = v + len("visible:")
        # the value runs to the end of the line or a `;` at depth 0
        depth, k = 0, e
        while k < b:
            c = s[k]
            if c in "([{":
                depth += 1
            elif c in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and c in ";\n":
                break
            k += 1
        return s[:v] + "visible: false" + s[k:]
    return s[:a + 1] + " visible: false;" + s[a + 1:]


def run(d, report):
    out = []
    for f in sorted(os.listdir(d)):
        if not f.endswith("Page.qml"):
            continue
        p = os.path.join(d, f)
        s = open(p).read()
        seen, hits = {}, []
        for m in re.finditer(r'label: I18n\.t\("([^"]+)"\)', s):
            lab = m.group(1)
            seen[lab] = seen.get(lab, 0) + 1
            a, b = block(s, m.start())
            if s[max(0, a - 120):a].rstrip().endswith(("options: [", ",")) and "options" in s[max(0, a - 300):a]:
                continue   # a choice inside a SegRow's options list, not a row
            body = s[a:b]
            key = lab + ("@%d" % seen[lab] if seen[lab] > 1 or (f, lab + "@1") in EXTRA else "")
            if (f, lab) in EXTRA or (f, key) in EXTRA or DEAD.search(body):
                hits.append((a, b, lab))
        for m in re.finditer(r'SectionTitle \{ text: I18n\.t\("([^"]+)"\)', s):
            if (f, m.group(1)) in SECTIONS:
                a, b = block(s, m.start() + len("SectionTitle {"))
                hits.append((a, b, "§" + m.group(1)))
        for pf, pat in PATTERNS:
            if pf != f:
                continue
            m = re.search(pat, s)
            if not m:
                print("hide-dead: pattern not found in %s: %s" % (f, pat), file=sys.stderr)
                continue
            br = s.rfind("{", m.start(), m.end())
            if br < 0:
                br = s.find("{", m.end())
            a2, b2 = block(s, br + 1)
            hits.append((a2, b2, "~" + pat[:24]))
        # outermost first, no nested duplicates; apply from the end so positions stay valid
        hits.sort()
        keep = []
        for h in hits:
            if keep and h[0] >= keep[-1][0] and h[1] <= keep[-1][1]:
                continue
            keep.append(h)
        for a, b, lab in sorted(keep, reverse=True):
            s = hide(s, a, b)
        if keep:
            out.append("%s: %s" % (f, ", ".join(l for _, _, l in keep)))
            if not report:
                open(p, "w").write(s)
    print("\n".join(out))


if __name__ == "__main__":
    run(sys.argv[1], "--report" in sys.argv)
