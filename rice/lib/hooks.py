"""Theme hooks: push the active palette into fastfetch, btop, cava, the konsole 'rice' profile and SDDM."""
import os, re, subprocess, shutil, json

HOME = os.path.expanduser("~")
SDDM_DIR = "/var/lib/rice-sddm"            # created once by rice-sddm (pkexec), owned by the user
SDDM_BASE = "/usr/share/sddm/themes/silent/configs/default.conf"


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ansi(h):
    return "38;2;%d;%d;%d" % rgb(h)


def mix(a, b, f):
    ra, rb = rgb(a), rgb(b)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * f) for x, y in zip(ra, rb))


def ensure(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    open(tmp, "w").write(text)
    os.replace(tmp, path)


# ---------------------------------------------------------------- fastfetch
# the logo picked in Settings > Look & Feel > Logo gallery (~/.config/rice/fflogo.json: {"logo": ID, "mode": "image"|"ascii"});
# art lives in ~/.local/share/rice/fflogos (catalog.json). No choice saved: the template's own logo stays.
FFLOGOS = f"{HOME}/.local/share/rice/fflogos"
FFSTATE = f"{HOME}/.config/rice/fflogo.json"


def fflogo(s, c):
    try:
        st = json.load(open(FFSTATE))
        item = next(i for i in json.load(open(f"{FFLOGOS}/catalog.json")) if i["id"] == st.get("logo"))
    except Exception:
        return s
    acc, acc2 = ansi(c["accent"]), ansi(c["accent2"])
    mode = st.get("mode", "image")
    m = re.search(r'"logo":\s*\{.*?\n  \},', s, flags=re.S)
    if not m:
        return s
    old = m.group(0)
    if item.get("image") and (mode == "image" or not item.get("ascii")):
        new = re.sub(r'"source":\s*"[^"]*"', '"source": "%s"' % f"{FFLOGOS}/{item['image']}", old, count=1)
        if '"type": "kitty-icat"' not in new and '"type"' not in new:
            new = new.replace('{', '{"type": "kitty-icat", ', 1)
    elif item.get("ascii"):
        new = '"logo": {"type": "file", "source": "%s", "color": {"1": "%s"}, "padding": {"right": 4, "left": 0, "top": 0, "bottom": 1}},' % (f"{FFLOGOS}/{item['ascii']}", acc)
    else:
        new = '"logo": {"type": "builtin", "source": "%s", "color": {"1": "%s", "2": "%s"}, "padding": {"right": 4}},' % (item.get("builtin", "gentoo"), acc, acc2)
    return s.replace(old, new, 1)


def fflayout(s, c):
    """layout "classic" (Settings > Look & Feel > Logo gallery): user@host, a rule, then bold  OS: value  lines, no icons."""
    try:
        st = json.load(open(FFSTATE))
    except Exception:
        return s
    if st.get("layout") != "classic":
        return s
    acc = ansi(c["accent"])
    disp = '"display": {"separator": ": ", "color": {"keys": "1;%s", "title": "1;%s"}},' % (acc, acc)
    mods = ('"modules": [\n    {"type": "title"},\n    {"type": "separator"},\n    {"type": "os", "key": "OS"},\n    {"type": "kernel", "key": "Kernel"},\n'
            '    {"type": "uptime", "key": "Uptime"},\n    {"type": "packages", "key": "Packages"},\n    {"type": "wm", "key": "WM"},\n'
            '    {"type": "cpu", "key": "CPU"},\n    {"type": "gpu", "key": "GPU"},\n    {"type": "memory", "key": "Memory"}\n  ]')
    s = re.sub(r'"display":\s*\{.*?\n  \},', lambda m: disp, s, count=1, flags=re.S)
    s = re.sub(r'"modules":\s*\[.*\n  \]', lambda m: mods, s, count=1, flags=re.S)
    return s


def fastfetch(c):
    cfg = f"{HOME}/.config/fastfetch/config.jsonc"
    tmpl = cfg + ".tmpl"
    if not os.path.exists(tmpl):
        if not os.path.exists(cfg):
            return
        shutil.copy(cfg, tmpl)               # untouched original, we always derive from it
    s = open(tmpl).read()
    acc, fg, dim = ansi(c["accent"]), ansi(c["fg"]), ansi(c["dim"])
    sw = [ansi(c["accent"]), ansi(c["accent2"]), ansi(c["fg"]), ansi(c["dim"])]
    s = s.replace('"keyColor": "37"', f'"keyColor": "{acc}"')
    s = s.replace('"keyColor": "90"', f'"keyColor": "{dim}"')
    s = re.sub(r'"format": "(?:\\u001b\[(?:90|37)m[^"\\]*?)+"',
               lambda m: '"format": "' + "".join(f"\\u001b[{sw[i % 4]}m  " for i in range(8)) + '"', s)
    s = fflayout(fflogo(s, c), c)
    ensure(cfg, s)
    # compact ASCII variant for the rice scene (terminals without image support)
    r = re.sub(r'"logo":\s*\{.*?\n  \},', '"logo": {"type": "builtin", "source": "gentoo_small", "color": {"1": "%s", "2": "%s"}, "padding": {"right": 3}},' % (acc, ansi(c["accent2"])), s, count=1, flags=re.S)
    ensure(f"{HOME}/.config/fastfetch/rice.jsonc", r)


# ---------------------------------------------------------------- btop
BTOP_THEME = f"{HOME}/.config/btop/themes/rice.theme"


def btop(c):
    ensure(BTOP_THEME, btop_text(c))
    subprocess.run(["pkill", "-USR2", "-x", "btop"], stderr=subprocess.DEVNULL)   # live theme reload


def btop_text(c):
    th = {
        "main_bg": c["bg"], "main_fg": c["fg"], "title": c["fg"], "hi_fg": c["accent"],
        "selected_bg": c["border"], "selected_fg": c["fg"], "inactive_fg": c["dim"],
        "graph_text": c["dim"], "meter_bg": c["border"], "proc_misc": c["accent2"],
        "cpu_box": c["border"], "mem_box": c["border"], "net_box": c["border"], "proc_box": c["border"],
        "div_line": c["border"],
    }
    grads = {"temp": (c["accent"], c["accent2"], c["fg"]), "cpu": (c["accent"], c["accent2"], c["fg"]),
             "free": (c["dim"], c["accent"], c["fg"]), "cached": (c["dim"], c["accent2"], c["fg"]),
             "available": (c["dim"], c["accent"], c["fg"]), "used": (c["accent"], c["accent2"], c["fg"]),
             "download": (c["dim"], c["accent"], c["fg"]), "upload": (c["dim"], c["accent2"], c["fg"])}
    out = [f'theme[{k}]="{v}"' for k, v in th.items()]
    for k, (a, b, d) in grads.items():
        out += [f'theme[{k}_start]="{a}"', f'theme[{k}_mid]="{b}"', f'theme[{k}_end]="{d}"']
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- cava
def cava_cols(c):
    return [mix(c["accent"], c["bg"], 0.35), c["accent"], mix(c["accent"], c["accent2"], 0.5), c["accent2"],
            mix(c["accent2"], c["fg"], 0.5), c["fg"]]


def cava(c):
    conf = f"{HOME}/.config/cava/config"
    if not os.path.exists(conf):
        return
    cols = cava_cols(c)
    block = "\n".join(["; RICE-THEME-START", "gradient = 1"] +
                      [f"gradient_color_{i + 1} = '{col}'" for i, col in enumerate(cols)] + ["; RICE-THEME-END"])
    t = open(conf).read()
    if "RICE-THEME-START" in t:
        t = re.sub(r"; RICE-THEME-START.*?; RICE-THEME-END", block, t, flags=re.S)
    else:
        t = re.sub(r"^\[color\]\s*\n", "[color]\n" + block + "\n", t, count=1, flags=re.M)
    ensure(conf, t)
    subprocess.run(["pkill", "-USR1", "-x", "cava"], stderr=subprocess.DEVNULL)    # live colour reload


# ---------------------------------------------------------------- konsole "rice" profile
def ansi_colors(c):
    """The 8 normal + 8 bright terminal colours, made in OKLCH so red stays red and yellow stays yellow
       whatever the accent is (sRGB mixing with the accent used to turn red into olive or purple and
       yellow into grey). Each of those leans a little toward the accent. Blue and magenta are the theme's
       accent and accent2 (a fixed blue looked foreign on a green wallpaper)."""
    import math, themes
    L_bg = themes._to_oklab(*rgb(c["bg"]))[0]
    dark = L_bg < 0.55
    _, aa, ab = themes._to_oklab(*rgb(c["accent"]))
    ha, ca = math.atan2(ab, aa), math.hypot(aa, ab)
    chroma = max(0.10, min(0.15, ca * 0.85)) if ca > 0.03 else 0.11
    # slot: (hue deg, lightness on dark bg, lightness on light bg)
    slots = {1: (27, 0.72, 0.52), 2: (145, 0.78, 0.50), 3: (100, 0.84, 0.50),
             4: (260, 0.72, 0.50), 5: (330, 0.74, 0.52), 6: (200, 0.80, 0.50)}
    norm, bright = [None] * 8, [None] * 8
    for i, (hd, ld, ll) in slots.items():
        h = math.radians(hd)
        d = math.atan2(math.sin(ha - h), math.cos(ha - h))      # signed distance to the accent hue
        if ca > 0.03:
            h += max(-math.radians(10), min(math.radians(10), d * 0.15))
        L = ld if dark else ll
        norm[i] = themes.oklch_hex(L, chroma, h)
        bright[i] = themes.oklch_hex(L + (0.08 if dark else -0.08), chroma * 1.08, h)
    # blue and magenta carry the theme (bash paints the prompt path in blue, ls the directories):
    # the accents, lifted or darkened until they read on bg
    for i, key in ((4, "accent"), (5, "accent2")):
        L, a, b = themes._to_oklab(*rgb(c[key]))
        C, h = math.hypot(a, b), math.atan2(b, a)
        L = max(L, 0.70) if dark else min(L, 0.50)
        norm[i] = themes.oklch_hex(L, C, h)
        bright[i] = themes.oklch_hex(L + (0.08 if dark else -0.08), C * 1.05, h)
    if dark:
        norm[0], bright[0] = c["border"], mix(c["border"], c["dim"], 0.45)   # bright black = comments, autosuggestions: must stay readable
        norm[7], bright[7] = c["dim"], c["fg"]
    else:
        norm[0], bright[0] = c["fg"], c["dim"]
        norm[7], bright[7] = c["border"], c["bg2"]
    return norm, bright


KONSOLE_DIR = f"{HOME}/.local/share/konsole"
KONSOLE_PROFILE = ("[Appearance]\nColorScheme=Rice\nFont=%s,11,-1,5,50,0,0,0,0,0\n\n"
                   "[General]\nName=rice\nParent=FALLBACK/\nTerminalMargin=14\nTerminalCenter=false\n\n[Scrolling]\nScrollBarPosition=2\n")


def konsole(c, look=None, glass=True):
    ensure(f"{KONSOLE_DIR}/Rice.colorscheme", konsole_text(c, look, glass))
    ensure(f"{KONSOLE_DIR}/rice.profile", KONSOLE_PROFILE % c.get("font_mono", "JetBrains Mono"))


def konsole_text(c, look=None, glass=True):
    bg, fg = c["bg"], c["fg"]
    norm, bright = ansi_colors(c)
    parts = [f"[Background]\nColor={','.join(map(str, rgb(bg)))}\n", f"[Foreground]\nColor={','.join(map(str, rgb(fg)))}\n"]
    for i in range(8):
        parts.append(f"[Color{i}]\nColor={','.join(map(str, rgb(norm[i])))}\n")
        parts.append(f"[Color{i}Intense]\nColor={','.join(map(str, rgb(bright[i])))}\n")
    parts.append(f"[General]\nDescription=Rice\nOpacity={(look or {}).get('opacity', 0.6):.2f}\nBlur={'true' if glass else 'false'}\n")
    return "\n".join(parts)


# ---------------------------------------------------------------- kitty (test run beside Konsole)
KITTY_THEME = f"{HOME}/.cache/theme/kitty.conf"


def kitty_text(c, look=None, glass=True):
    norm, bright = ansi_colors(c)
    op = (look or {}).get("opacity", 0.6) if glass else 1.0
    lines = [f"background {c['bg']}", f"foreground {c['fg']}", f"background_opacity {op:.2f}",
             f"cursor {c['fg']}", f"cursor_text_color {c['bg']}",
             f"selection_background {mix(c['bg'], c['accent'], 0.45)}", f"selection_foreground {c['fg']}",
             f"url_color {c['accent']}",
             f"active_border_color {c['accent']}", f"inactive_border_color {c['border']}",
             f"active_tab_background {c['accent']}", f"active_tab_foreground {c['bg']}",
             f"inactive_tab_background {c['bg2']}", f"inactive_tab_foreground {c['dim']}",
             f"tab_bar_background {c['bg']}"]
    lines += [f"color{i} {norm[i]}" for i in range(8)] + [f"color{i + 8} {bright[i]}" for i in range(8)]
    return "# written by ~/.local/lib/rice/hooks.py on every theme apply\n" + "\n".join(lines) + "\n"


def kitty(c, look=None, glass=True):
    t = kitty_text(c, look, glass)
    try:
        if open(KITTY_THEME).read() == t:
            return
    except OSError:
        pass
    ensure(KITTY_THEME, t)
    subprocess.run(["pkill", "-USR1", "-x", "kitty"], stderr=subprocess.DEVNULL)   # every kitty reloads kitty.conf


# ---------------------------------------------------------------- SDDM (needs `rice-sddm` once)
def sddm_theme_conf(c, bg=SDDM_DIR + "/rice-bg.jpg"):
    """theme.conf for the own "rice" SDDM theme (~/.local/share/rice/sddm-theme). Values quoted: QSettings ini."""
    import time
    return ("[General]\n"
            f'background="{bg}"\n'
            + "".join(f'{k}="{c[k]}"\n' for k in ("bg", "bg2", "fg", "dim", "accent", "accent2") if k in c)
            + 'error="#ee5d66"\n'
            + f'light="{1 if c.get("light") else 0}"\n'
            + 'preview="false"\n'
            + f'synced="{time.strftime("%Y-%m-%d %H:%M:%S")}"\n')


def sddm(c, wall):
    """Final apply only: blurred wallpaper + colours into /var/lib/rice-sddm (user-owned, made by `rice-sddm`).
    Feeds the own "rice" theme (theme.conf) and, if installed, the old "silent" theme (rice.conf)."""
    if not (os.path.isdir(SDDM_DIR) and os.access(SDDM_DIR, os.W_OK)):
        return False
    try:
        from PIL import Image, ImageOps, ImageFilter          # ImageMagick here has no JPEG decoder
        im = ImageOps.fit(Image.open(wall).convert("RGB"), (2560, 1440), Image.LANCZOS)
        # blur only: light blur (shapes stay) mixed with a heavy one (colours melt together)
        base = im.resize((1280, 720), Image.LANCZOS)
        im = Image.blend(base.filter(ImageFilter.GaussianBlur(7)), base.filter(ImageFilter.GaussianBlur(30)), 0.5)
        im = im.resize((2560, 1440), Image.BICUBIC)
        im.save(f"{SDDM_DIR}/rice-bg.jpg.tmp.jpg", "JPEG", quality=88)
        os.replace(f"{SDDM_DIR}/rice-bg.jpg.tmp.jpg", f"{SDDM_DIR}/rice-bg.jpg")
        os.chmod(f"{SDDM_DIR}/rice-bg.jpg", 0o644)
        ensure(f"{SDDM_DIR}/theme.conf", sddm_theme_conf(c))
        os.chmod(f"{SDDM_DIR}/theme.conf", 0o644)
        if os.path.exists(SDDM_BASE):
            sddm_silent(c)
        return True
    except Exception as e:
        try:
            open(f"{HOME}/.cache/rice/sddm.log", "a").write(f"sddm hook failed: {e!r}\n")
        except OSError:
            pass
        return False


def sddm_silent(c):
    t = open(SDDM_BASE).read()
    sect = [None]
    out = []
    for ln in t.splitlines():
        m = re.match(r"\s*\[(.+)\]", ln)
        if m:
            sect[0] = m.group(1)
        k = re.match(r"\s*([\w-]+)\s*=", ln)
        key = k.group(1) if k else ""
        if re.search(r'"#[0-9a-fA-F]{3,8}"', ln) and key.endswith("color"):
            accent = key.startswith("active-border") or key in ("warning-color", "error-color", "primary-color") or \
                     (key == "border-color" and "Input" in (sect[0] or ""))
            col = c["accent"] if accent else c["fg"]
            if key in ("background-color", "active-background-color", "active-option-background-color") or key == "key-active-background-color":
                col = c["accent"] if key.startswith("active") else c["fg"]
            if key == "border-color" and "VirtualKeyboard" in (sect[0] or ""):
                col = c["bg"]
            ln = re.sub(r'"#[0-9a-fA-F]{3,8}"', f'"{col}"', ln, count=1)
        if key in ("background",) and sect[0] in ("LockScreen", "LoginScreen"):
            ln = 'background = "rice-bg.jpg"'
        if key == "use-background-color" and sect[0] in ("LockScreen", "LoginScreen"):
            ln = "use-background-color = false"
        if key == "blur" and sect[0] in ("LockScreen", "LoginScreen"):
            ln = "blur = 0"   # the image itself is already blurred
        if key == "brightness" and sect[0] in ("LockScreen", "LoginScreen"):
            ln = "brightness = 0.0"
        out.append(ln)
    ensure(f"{SDDM_DIR}/rice.conf", "\n".join(out) + "\n")
    os.chmod(f"{SDDM_DIR}/rice.conf", 0o644)


def picom(look):
    """Blur strength from the wallpaper; picom reloads its config on SIGUSR1."""
    conf = f"{HOME}/.config/picom/rice.conf"
    try:
        t = open(conf).read()
        n = re.sub(r"^blur-strength = \d+;", f"blur-strength = {look['blur']};", t, count=1, flags=re.M)
        if n != t:
            ensure(conf, n)
            subprocess.run(["pkill", "-USR1", "-x", "picom"], stderr=subprocess.DEVNULL)
    except OSError:
        pass


# ---------------------------------------------------------------- Qt / Dolphin
def qt(c):
    """KDE colour scheme from the wallpaper palette; Dolphin and other Qt apps read it at start."""
    def t(h):
        return "%d,%d,%d" % rgb(h)
    light = bool(c.get("light"))
    bg, bg2, bd, fg, dim, ac, ac2 = (t(c[k]) for k in ("bg", "bg2", "border", "fg", "dim", "accent", "accent2"))
    onacc = t(c["bg"])
    def sec(n, b, alt, f, dec):
        return (f"[Colors:{n}]\nBackgroundNormal={b}\nBackgroundAlternate={alt}\nForegroundNormal={f}\n"
                f"ForegroundInactive={dim}\nForegroundActive={ac}\nForegroundLink={ac2}\nForegroundVisited={dim}\n"
                "ForegroundNegative=224,108,117\nForegroundNeutral=229,192,123\nForegroundPositive=152,195,121\n"
                f"DecorationFocus={dec}\nDecorationHover={ac}\n\n")
    s = "[General]\nColorScheme=RiceWall\nName=Rice Wall\n\n"
    s += sec("View", bg, bg2, fg, ac) + sec("Window", bg2, bg, fg, ac) + sec("Button", bd, bg2, fg, ac)
    s += sec("Selection", ac, ac2, onacc, ac) + sec("Tooltip", bg2, bg, fg, ac)
    s += sec("Complementary", bg, bg2, fg, ac) + sec("Header", bg2, bg, fg, ac)
    s += f"[WM]\nactiveBackground={bg}\nactiveForeground={fg}\ninactiveBackground={bg2}\ninactiveForeground={dim}\n"
    ensure(f"{HOME}/.local/share/color-schemes/RiceWall.colors", s)
    kg = f"{HOME}/.config/kdeglobals"
    txt = open(kg).read() if os.path.exists(kg) else ""
    txt = re.sub(r"^ColorScheme=.*$", "ColorScheme=RiceWall", txt, flags=re.M)
    txt = re.sub(r"^AccentColor=.*$", "AccentColor=" + ac, txt, flags=re.M)
    ensure(kg, txt)
    dr = f"{HOME}/.config/dolphinrc"
    if os.path.exists(dr):
        ensure(dr, re.sub(r"^ColorScheme=.*$", "ColorScheme=RiceWall", open(dr).read(), flags=re.M))

    qss = f"""
* {{ font-family: "{c.get('font_sans', 'Inter')}", "Inter", "JetBrains Mono"; color: {c['fg']}; }}
QMainWindow, QDialog, QMenu, QToolBar, QStatusBar, QDockWidget {{ background: {c['bg2']}; }}
QAbstractItemView, QListView, QTreeView, QScrollArea {{ background: {c['bg']}; color: {c['fg']}; border: none;
  outline: 0; selection-background-color: {c['accent']}; selection-color: {c['bg']}; }}
QAbstractItemView::item {{ color: {c['fg']}; border-radius: 8px; padding: 3px; }}
QAbstractItemView::item:hover {{ background: {mix(c['bg'], c['fg'], 0.08)}; }}
QAbstractItemView::item:selected {{ background: {c['accent']}; color: {c['bg']}; }}
QLabel, QCheckBox, QRadioButton, QToolButton {{ color: {c['fg']}; background: transparent; }}
QToolButton {{ border-radius: 7px; padding: 4px; }}
QToolButton:hover {{ background: {mix(c['bg2'], c['fg'], 0.10)}; }}
QToolButton:pressed, QToolButton:checked {{ background: {mix(c['bg2'], c['fg'], 0.18)}; }}
QPushButton {{ background: {c['border']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 5px 14px; }}
QPushButton:hover {{ background: {mix(c['border'], c['fg'], 0.12)}; }}
QPushButton:default {{ background: {c['accent']}; color: {c['bg']}; }}
QLineEdit, QComboBox, QSpinBox {{ background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 4px 8px;
  selection-background-color: {c['accent']}; selection-color: {c['bg']}; }}
QLineEdit:focus {{ border: 1px solid {c['accent']}; }}
QMenu {{ background: {c['bg2']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['accent']}; color: {c['bg']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 5px 8px; }}
QTabBar::tab {{ background: transparent; color: {c['dim']}; padding: 6px 14px; margin: 3px 2px; border-radius: 8px; }}
QTabBar::tab:selected {{ background: {mix(c['bg2'], c['fg'], 0.12)}; color: {c['fg']}; }}
QTabBar::tab:hover:!selected {{ background: {mix(c['bg2'], c['fg'], 0.06)}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {mix(c['bg'], c['fg'], 0.22)}; border-radius: 3px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {mix(c['bg'], c['fg'], 0.22)}; border-radius: 3px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; border: none; width: 0; height: 0; }}
QSplitter::handle {{ background: transparent; }}
QToolTip {{ background: {c['bg2']}; color: {c['fg']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 4px; }}
"""
    ensure(f"{HOME}/.cache/theme/dolphin.qss", qss)


def _fail(name, e):
    """A hook failure used to vanish; log it so rice-themecheck and a human can see it."""
    try:
        import time
        with open(f"{HOME}/.cache/rice/theme-switch.log", "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} HOOK {name} FAILED: {type(e).__name__}: {e}\n")
    except OSError:
        pass


def run_all(c, wall, final=True, look=None, glass=True):
    """Cheap hooks run on every live preview step; SDDM (image convert) only when the choice is final."""
    for fn, args in ((fastfetch, (c,)), (btop, (c,)), (cava, (c,)), (qt, (c,)), (konsole, (c, look, glass)), (kitty, (c, look, glass))):
        try:
            fn(*args)
        except Exception as e:
            _fail(fn.__name__, e)
    if final:
        if look:
            picom(look)
        try:
            sddm(c, wall)
        except Exception as e:
            _fail("sddm", e)
