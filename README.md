<div align="center">

# mwm

### muxy window manager

A fast, floating-bar, animated fork of [suckless dwm](https://dwm.suckless.org) 6.8 for X11.

![language](https://img.shields.io/badge/language-C99-blue) ![license](https://img.shields.io/badge/license-MIT%2FX-green) ![base](https://img.shields.io/badge/based%20on-dwm%206.8-orange)

</div>

mwm keeps dwm's tiny, fast core and adds the things you usually patch in by hand:
a rounded floating bar, eased animations, a system tray on every monitor, an infinite
canvas mode and a small IPC. It is not an official suckless project.

## Features

- **Floating bar** with padding and gaps. It drops its padding when a tag has one window.
- **Dot and pill tags** drawn with cairo, eased between states.
- **Window animation** (cubic bezier, 0.22 s). New windows are not animated, so terminals see their final size.
- **Focused-only borders** with a crossfade between windows.
- **Layouts:** tile, bento, dock, mosaic, monocle, floating. `Mod+space` cycles.
- **Canvas mode:** an infinite plane. Drag to pan, `Mod+scroll` to zoom.
- **Systray on every bar.** The real tray lives on one monitor, the others mirror it.
- **Multi-monitor aware:** popups and spawns follow the pointer.
- **Colours from X resources** (`dwm.normbgcolor`, `dwm.selbgcolor` ...). Reload with `Mod+F5`.
- **Runtime key binds** from `~/.config/rice/binds.conf` replace the compiled `keys[]` when that file exists.
- **IPC** over a root window property: `xprop -root -f _RICE_CMD 32c -set _RICE_CMD "N, ..."`.
- **Shell-window support** so a Quickshell panel set is not tiled.

Full list and key reference: [docs/dwm-features.md](docs/dwm-features.md).

## Build

Needs Xlib, Xft, fontconfig, Xinerama, Xext, XTest and cairo (with xlib).

```sh
# Gentoo
emerge x11-libs/libX11 x11-libs/libXft x11-libs/libXinerama x11-libs/libXtst x11-libs/cairo
# Debian / Ubuntu
apt install build-essential libx11-dev libxft-dev libxinerama-dev libxtst-dev libxext-dev libcairo2-dev

git clone https://github.com/petkebtw/mwm.git
cd mwm
cp config.def.h config.h    # edit to taste
make
sudo make install           # installs the dwm binary to /usr/local/bin
```

`Mod` is `Alt`. Default terminal is `konsole`, launcher `Mod+p`. Change both in `config.h`.

Add `exec dwm` to `~/.xinitrc`, or a session entry for your display manager.

## Dependencies

**Build:** a C99 compiler, `make`, `pkg-config`, and the dev headers for Xlib, Xft, fontconfig, Xinerama, Xext, XTest and cairo (xlib backend).

| Distro | Packages |
| --- | --- |
| Gentoo | `x11-libs/libX11 x11-libs/libXft x11-libs/libXinerama x11-libs/libXtst x11-libs/libXext x11-libs/cairo media-libs/fontconfig` |
| Debian / Ubuntu | `build-essential pkg-config libx11-dev libxft-dev libxinerama-dev libxtst-dev libxext-dev libcairo2-dev libfontconfig1-dev` |
| Arch | `base-devel libx11 libxft libxinerama libxtst libxext cairo fontconfig` |

**Runtime, required:** `xrdb` (colours are read from X resources) and a terminal. The default is `konsole`; edit `termcmd` in `config.h`.

**Runtime, optional.** mwm itself does not start these, your `~/.xprofile` does:

| Tool | Used for |
| --- | --- |
| `picom` | compositing: blur, shadows, rounded corners. The bar is ARGB and wants a compositor. |
| `feh` | wallpaper |
| `pipewire`, `pipewire-pulse`, `wireplumber` | audio (`wpctl`, `pactl`) |
| `quickshell` (X11 build) | the widget, dock and launcher shell |
| `xrandr`, `setxkbmap`, `xset` | monitor layout, keyboard, screen blanking |
| `xdotool`, `maim`, `xclip` | scripting, screenshots, clipboard |
| a polkit agent | auth prompts |
| JetBrains Mono and Symbols Nerd Font | bar font |

The key binds in the default `config.h` call helper scripts that are **not** in this repo: `rice-search`, `rice-center`, `rice-map`, `rice-lock`, `rice-power`, `rice-media`, `rice-record`, `rice-settings`, `rice-gamebar` and `dwm-volume`. Without them those keys do nothing. Point them at your own commands in `config.h`, or in `~/.config/rice/binds.conf`.

## Session setup (`~/.xprofile`)

mwm is started by your login manager or `~/.xinitrc`. Put session setup in `~/.xprofile` (SDDM, GDM and LightDM source it) or at the top of `~/.xinitrc`. A minimal one:

```sh
export PATH="$HOME/.local/bin:$PATH"

# monitors (check names with `xrandr`)
xrandr --output DP-1 --primary --mode 1920x1080 --pos 0x1080 \
       --output HDMI-1 --mode 1920x1080 --pos 0x0

xrdb -merge ~/.Xresources            # colours: dwm.normbgcolor, dwm.selbgcolor ...
feh --bg-fill ~/Pictures/wall.jpg &
picom --config ~/.config/picom/picom.conf &

setxkbmap us                         # your layout
xset s off; xset s noblank; xset -dpms

export XCURSOR_THEME=Adwaita XCURSOR_SIZE=24
export NO_AT_BRIDGE=1

# audio: start once, after the session bus is up
(sleep 2; pipewire-pulse) &
```

Notes:
- `xrdb -merge` must run before mwm starts, or after it followed by `Mod+F5`. mwm reloads colours on `RESOURCE_MANAGER` changes.
- Start `picom` before `quickshell`, so the panels get blur.
- On NVIDIA with two monitors of different refresh rates, `__GL_SYNC_DISPLAY_DEVICE=<fast output> picom ...` keeps the fast one smooth.
- `exec mwm` or `exec dwm` goes last in `~/.xinitrc`. Display managers start it from the session entry instead.

## Upstream

mwm is built on dwm 6.8 from `git.suckless.org/dwm`, with the systray patch applied by hand.
The suckless history is kept in this repository; `git remote add upstream https://git.suckless.org/dwm`
to follow it.

## License

MIT/X Consortium, same as dwm. See [LICENSE](LICENSE). Copyright of the original dwm authors is kept.
