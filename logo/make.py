#!/usr/bin/env python3
"""glidewm logo, dwm style: lowercase letters on a unit grid, strokes one unit thick, square corners.
x-height 5 units (rows 2-6), ascenders rows 0-1, descender rows 7-8; w and m share a stem like dwm's d, w, m.
Writes glidewm.svg (dark ink), glidewm-light.svg (light ink, for dark backgrounds), glidewm-icon.svg (the g on a
rounded square) and PNGs. Run: python3 make.py"""
import subprocess

U = 8                     # px per grid unit in the SVG (scales freely)
X0, X1 = 2, 6             # x-height rows
cells = set()


def box(c0, c1, r0, r1):
    for c in range(c0, c1 + 1):
        for r in range(r0, r1 + 1):
            cells.add((c, r))


def ring(c0, c1, r0, r1):          # a square letter bowl, one unit thick
    box(c0, c1, r0, r0); box(c0, c1, r1, r1); box(c0, c0, r0, r1); box(c1, c1, r0, r1)


def glyphs():
    ring(0, 3, X0, X1); box(3, 3, X1, 8); box(0, 3, 8, 8)              # g
    box(5, 5, 0, X1)                                                     # l
    box(7, 7, 0, 0); box(7, 7, X0, X1)                                   # i
    ring(9, 12, X0, X1); box(12, 12, 0, X1)                              # d
    box(14, 17, X0, X0); box(14, 14, X0, X1); box(14, 17, 4, 4); box(17, 17, X0, 4); box(14, 17, X1, X1)   # e
    for c in (19, 21, 23): box(c, c, X0, X1)                             # w: three stems on a floor
    box(19, 23, X1, X1)
    box(23, 27, X0, X0)                                                  # m: roof from the shared stem
    for c in (25, 27): box(c, c, X0, X1)


def runs(cs):
    """merge cells into horizontal runs -> fewer rects"""
    out = []
    for r in sorted({r for _, r in cs}):
        row = sorted(c for c, rr in cs if rr == r)
        s = p = row[0]
        for c in row[1:] + [None]:
            if c is not None and c == p + 1:
                p = c; continue
            out.append((s, r, p - s + 1)); 
            if c is not None: s = p = c
    return out


def svg(cs, ink, w, h, pad=0, bg=None, rx=0, scale=U, title="glidewm"):
    W, H = (w + 2 * pad) * scale, (h + 2 * pad) * scale
    rects = "".join(f'<rect x="{(c + pad) * scale}" y="{(r + pad) * scale}" width="{n * scale}" height="{scale}"/>' for c, r, n in runs(cs))
    back = f'<rect width="{W}" height="{H}" rx="{rx}" fill="{bg}"/>' if bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" shape-rendering="crispEdges">'
            f'<title>{title}</title>{back}<g fill="{ink}">{rects}</g></svg>\n')


glyphs()
W = max(c for c, _ in cells) + 1; H = 9
open("glidewm.svg", "w").write(svg(cells, "#222222", W, H))
open("glidewm-light.svg", "w").write(svg(cells, "#eeeeee", W, H))
g = {(c, r) for c, r in cells if c <= 3}                                 # the g alone, centred in a square
# icon: 13x13 units, g (4x9) centred, dark rounded square
gi = {(c + 3, r - 2 + 1.5) for c, r in g}                               # g is 4x7 (rows 2-8): centred in 10x10
open("glidewm-icon.svg", "w").write(svg(gi, "#eeeeee", 10, 10, bg="#222222", rx=2.5 * U, title="glidewm icon"))
for name, w in (("glidewm", 896), ("glidewm-light", 896)):
    subprocess.run(["rsvg-convert", "-w", str(w), f"{name}.svg", "-o", f"{name}.png"], check=True)
for s in (16, 32, 48, 64, 128, 256):
    subprocess.run(["rsvg-convert", "-w", str(s), "-h", str(s), "glidewm-icon.svg", "-o", f"icon-{s}.png"], check=True)
print(f"{W}x{H} units, {len(cells)} cells")
