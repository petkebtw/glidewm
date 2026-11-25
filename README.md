<div align="center">

# 🪟 mwm

**muxy window manager**

A tiling window manager for X11, forked from [dwm](https://dwm.suckless.org) 6.8.<br>
Glass bar · smooth animations · infinite canvas · tiny IPC · one C file.

<br>

[![License](https://img.shields.io/badge/license-MIT%2FX-8ad7eb?style=for-the-badge&labelColor=1e202b)](LICENSE)
[![Language](https://img.shields.io/badge/C99-single%20file-86dbd7?style=for-the-badge&logo=c&logoColor=white&labelColor=1e202b)](dwm.c)
[![Base](https://img.shields.io/badge/based%20on-dwm%206.8-f2b8a0?style=for-the-badge&labelColor=1e202b)](https://git.suckless.org/dwm)
[![Last commit](https://img.shields.io/github/last-commit/petkebtw/mwm?style=for-the-badge&color=c6b6f2&labelColor=1e202b)](https://github.com/petkebtw/mwm/commits/main)
[![Stars](https://img.shields.io/github/stars/petkebtw/mwm?style=for-the-badge&color=f2e0a0&labelColor=1e202b)](https://github.com/petkebtw/mwm/stargazers)

<br>

[✨ Features](#-features) · [🎨 Rice](#-the-rice) · [📦 Install](#-install) · [⌨️ Keys](#️-keys) · [🔧 Setup](#-session-setup) · [🛠️ Troubleshooting](#️-troubleshooting) · [❓ FAQ](#-faq)

<br>

<img src="screenshots/desktop.png" alt="mwm desktop: floating bar, clock and visualizer widgets" width="49%"> <img src="screenshots/windows.png" alt="mwm tiled windows: fastfetch, cava, btop" width="49%">

</div>

> [!NOTE]
> mwm is a personal fork of dwm. It is not an official suckless project.

## ✨ Features

**🎞️ Look and motion**
- Floating rounded bar. Padding drops when a tag holds one window.
- Tags are dots that ease into a pill.
- Windows move on a bezier curve (0.22 s). New windows are not animated.
- Border on the focused window only, with a crossfade.
- Colours from X resources (`dwm.normbgcolor` ...). Reload: `Mod+F5`.

**📐 Layouts** · `Mod+space` cycles, `Mod+Ctrl+space` resets

| | Layout | |
| :---: | --- | --- |
| `[]=` | tile | master and stack |
| `[B]` | bento | big window left, uneven grid right |
| `[D]` | dock | sidebar, main area, widget column |
| `[#]` | mosaic | staggered brick rows |

**🌌 Canvas mode**
- `Mod+Shift+g` turns a tag into an infinite plane.
- Drag the background to pan. `Mod+scroll` zooms. `Mod+Ctrl+0` resets.

**🖥️ Multi-monitor**
- Systray mirrored on every bar, clicks included.
- New windows, popups and screenshots follow the pointer.
- Tag state published for external shells.

**🔌 Rice hooks**
- `~/.config/rice/binds.conf` replaces compiled keys at runtime.
- Quickshell panels are mapped but never tiled.
- Root-property [IPC](#-ipc).

📖 Full reference: [docs/dwm-features.md](docs/dwm-features.md)

## 🎨 The rice

The screenshots show mwm with a full desktop shell on top. It lives in [`rice/`](rice). mwm runs fine without it.

**🖌️ Themes from the wallpaper**
- Accent colour picked from the wallpaper. Grey pictures stay grey.
- One apply themes the bar, rofi, Konsole, kitty, btop, cava, fastfetch, Qt, SDDM and the shell.
- Contrast guard keeps text readable (WCAG).
- Fonts and styles follow the palette mood: Material 3, macOS, Brutal, Wallpaper.
- `theme-switch` (`Mod+Shift+t`): arrows to preview, Enter keeps, Esc reverts.

**🧩 Shell (Quickshell QML)**
- Bar, dock, control centre (`Mod+n`) and dynamic island.
- Desktop widgets: clock, visualiser, weather, battery, lyrics. `Mod+e` edits them.
- Game bar (`Mod+g`), hot corner, welcome screen, wallpaper picker.
- Menus grow out of the bar as glass shapes.

**🔎 Launcher and tools**
- Search apps, files, settings, math. Prefixes: `>` terminal, `?` web, `=` math, `/` paths.
- Clipboard history (`Mod+v`) and media card (`Mod+Shift+m`).
- Tools menu: convert, download, record, screenshot, colour picker, QR code.
- Screenshot editor with OCR. Screen recorder with per-app audio.
- Lock screen, power menu, polkit prompt, SDDM theme.

**⚙️ Settings app** (`Mod+o`)
- Appearance, wallpapers, sound, display, keyboard, mouse, gaps, network, shortcuts.

**🪄 Compositor**
- [picom](https://github.com/yshui/picom) 13 rules: clean menus, no blur on widgets, light blur on moving windows.

## 📦 Install

### ⚡ One command

```sh
git clone https://github.com/petkebtw/mwm.git && cd mwm
./install.sh --check     # what is installed, what is missing (with the package names for your distro)
./install.sh             # mwm, the rice, the shell, the "mwm" login session and app menu entries
```

- Never overwrites your files: existing ones are kept or backed up (`*.bak-DATE`).
- Checks the init system (systemd, OpenRC, runit, s6, dinit): logind/elogind, polkit, D-Bus, how PipeWire starts, the display manager at boot.
- Warns about duplicates: a second mwm login entry, an old install under the name `dwm`, helpers shadowed in `PATH`, things `~/.xprofile` starts twice.
- `--dry-run` shows every step. `--no-build`, `--no-rice`, `--no-shell`, `--no-session`, `--no-apps` skip a part.
- Pick **mwm** at the login screen (SDDM, LightDM, GDM), or `startx`.

The manual steps follow.

### 1. Dependencies

| Distro | Command |
| --- | --- |
| 🐧 Gentoo | `emerge x11-libs/libX11 x11-libs/libXft x11-libs/libXinerama x11-libs/libXtst x11-libs/libXext x11-libs/cairo media-libs/fontconfig` |
| 🌀 Debian / Ubuntu | `apt install build-essential pkg-config libx11-dev libxft-dev libxinerama-dev libxtst-dev libxext-dev libcairo2-dev libfontconfig1-dev` |
| 🏔️ Arch | `pacman -S base-devel libx11 libxft libxinerama libxtst libxext cairo fontconfig` |

Required at runtime: `xrdb` and a terminal (default `konsole`, change `termcmd` in `config.h`).

<details>
<summary>Optional runtime tools</summary>

| Tool | For |
| --- | --- |
| `picom` | blur, shadows, rounded corners |
| `feh` | wallpaper |
| `pipewire`, `wireplumber` | audio |
| `quickshell` (X11 build) | widgets, dock, launcher |
| `xdotool`, `maim`, `xclip` | scripting, screenshots, clipboard |
| a polkit agent | auth prompts |
| JetBrains Mono, Symbols Nerd Font | bar font |

</details>

### 2. Build mwm

```sh
git clone https://github.com/petkebtw/mwm.git
cd mwm
cp config.def.h config.h     # edit to taste
make
sudo make install            # installs /usr/local/bin/mwm (a system dwm is not touched)
```

Add `exec mwm` to `~/.xinitrc`, or pick the session in your display manager (`install.sh` adds the "mwm" entry).

> [!IMPORTANT]
> Default binds call the `rice/` helpers (`rice-search`, `rice-center`, `dwm-volume` ...).
> Install the rice, or change the binds in `config.h` or `~/.config/rice/binds.conf`.

### 3. Install the rice (optional)

```sh
cd rice && ./install.sh                  # symlinks, never overwrites
cp config/xprofile.example ~/.xprofile   # edit monitors, wallpaper, layout
~/.local/share/dss/port.sh               # build the Quickshell shell
~/.local/share/dss/dss-start             # start it
```

- Needs Python 3, PyGObject (GTK 3), Pillow, `rofi`, `picom`, `feh`, `xdotool`, `maim`, `xclip`, `tesseract`, `ffmpeg`.
- Quickshell must be built for X11 (Gentoo: `gui-apps/quickshell` with `X`, without `layer-shell`).
- `rice-dl` needs a [cobalt](https://github.com/imputnet/cobalt) URL in `~/.cache/rice/cobalt_url`.

<details>
<summary>📁 What is in <code>rice/</code></summary>

| Path | Contents |
| --- | --- |
| `bin/` | 50 commands: `rice-*`, `theme-switch`, `scglass`, `dwm-status`, `dwm-volume`, `rofi-launcher` ... |
| `lib/` | shared Python: themes, designs, per-app hooks, widgets, settings |
| `shell/` | `port.sh`, `dss-start`, X11 patches for the shell |
| `shell/dss/` | the QML shell: desktop, apps, settings, lock screen, welcome, sounds |
| `config/` | picom `rice.conf`, `binds.conf`, rofi themes, `xprofile.example` |

</details>

## ⌨️ Keys

`Mod` = `Alt`

<table>
<tr><td valign="top">

**🚀 Apps**

| Keys | Action |
| --- | --- |
| `Mod+Shift+Return` | terminal |
| `Mod+p` | launcher |
| `Mod+s` | search |
| `Mod+n` | control centre |
| `Mod+o` | settings |
| `Mod+v` | clipboard |
| `Mod+z` | monitor overview |
| `Mod+g` | game bar |
| `Mod+Shift+t` | themes |
| `Mod+Shift+o` | tools |
| `Mod+Shift+m` | media |
| `Mod+Shift+r` | recorder |
| `Mod+Shift+s` / `Print` | screenshot |
| `Mod+Shift+l` | lock |
| `Mod+e` / `Mod+Shift+e` | edit / add widgets |

</td><td valign="top">

**🪟 Windows**

| Keys | Action |
| --- | --- |
| `Mod+j` / `k` | focus next / prev |
| `Mod+Shift+j` / `k` | move down / up |
| `Mod+Return` | to master |
| `Mod+h` / `l` | master size |
| `Mod+i` / `d` | master count |
| `Mod+Shift+space` | float |
| `Mod+Arrows` | snap |
| `Mod+Shift+Arrows` | nudge |
| `Mod+Ctrl+Arrows` | resize |
| `Mod+Shift+c` | close |
| `Mod+space` | next layout |
| `Mod+t` | tile |
| `Mod+-` / `=` | gaps |
| `Mod+b` | toggle bar |

</td><td valign="top">

**🏷️ Tags and session**

| Keys | Action |
| --- | --- |
| `Mod+1..9` | view tag |
| `Mod+Shift+1..9` | send to tag |
| `Mod+0` | all tags |
| `Mod+Shift+0` | sticky window |
| `Mod+,` / `.` | focus monitor |
| `Mod+Shift+,` / `.` | send to monitor |
| `Mod+Shift+g` | canvas mode |
| `Mod+scroll` | canvas zoom |
| `Mod+Ctrl+0` | reset zoom |
| `Mod+F5` | reload colours |
| volume keys | volume |
| `Mod+Shift+q` | quit |
| `Mod+Ctrl+Shift+q` | restart, keep windows |

</td></tr>
</table>

## 🔧 Session setup

Put this in `~/.xprofile` (SDDM, GDM, LightDM) or at the top of `~/.xinitrc`:

```sh
export PATH="$HOME/.local/bin:$PATH"
xrandr --output DP-1 --primary --mode 1920x1080 --pos 0x1080 \
       --output HDMI-1 --mode 1920x1080 --pos 0x0
xrdb -merge ~/.Xresources
feh --bg-fill ~/Pictures/wall.jpg &
picom --config ~/.config/picom/picom.conf &
setxkbmap us
xset s off; xset s noblank; xset -dpms
(sleep 2; pipewire-pulse) &
```

- 💡 Start `picom` before `quickshell`, so panels get blur.
- 💡 Two NVIDIA monitors with different refresh rates: `__GL_SYNC_DISPLAY_DEVICE=<fast output> picom ...`

## 📡 IPC

```sh
xprop -root -f _RICE_CMD 32c -set _RICE_CMD "2, 12"    # set the gap to 12 px
```

- Wait about 40 ms between writes, or the second is lost.
- State is published on `_RICE_TAGS` and `_RICE_MONS`.
- Command list: [docs/dwm-features.md](docs/dwm-features.md).

## 🛠️ Troubleshooting

| Problem | Fix |
| --- | --- |
| Wrong colours or blur | `rice-themecheck --fix` |
| A script crashed | see `~/.cache/rice/crash.log` |
| Menu leaves a ghost | reload picom: `kill -USR1 <picom pid>` |
| Animations feel heavy | Settings > Appearance, or lighter blur |
| Tray on wrong monitor | set `systraypinning` in `config.h`, rebuild |
| `Mod+z`: "no data from dwm" | `sudo make install`, restart mwm |
| Key edits do nothing | delete `~/.config/rice/binds.conf` |
| Audio hangs | restart PipeWire |
| Stutter with a game | GPU load, not mwm |

## ❓ FAQ

<details>
<summary><b>Do I need the rice or Quickshell?</b></summary>

No. mwm runs without them.
</details>

<details>
<summary><b>Does it replace my dwm?</b></summary>

No. The binary is `mwm` (`/usr/local/bin/mwm`) and the login entry is "mwm", so a system `dwm` keeps working next to it.
Colours are still read from `dwm.*` X resources, so existing `~/.Xresources` work.
</details>

<details>
<summary><b>How do I follow upstream dwm?</b></summary>

```sh
git remote add upstream https://git.suckless.org/dwm
git fetch upstream
```

Expect conflicts: `dwm.c` has diverged a lot.
</details>

## 🙏 Credits

- [dwm](https://dwm.suckless.org) by suckless.org: the base.
- [systray patch](https://dwm.suckless.org/patches/systray/): extended to mirror on every bar.
- [DarkShadow's Shell](https://github.com/shadowww-dev/DarkShadowShell) (MIT): the QML shell, ported to X11.
- [Quickshell](https://quickshell.org), [picom](https://github.com/yshui/picom), [cairo](https://www.cairographics.org).

## 📄 License

MIT/X, same as dwm. See [LICENSE](LICENSE). The shell in `rice/shell/dss` keeps its own MIT `LICENSE`.
