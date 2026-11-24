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

## Upstream

mwm is built on dwm 6.8 from `git.suckless.org/dwm`, with the systray patch applied by hand.
The suckless history is kept in this repository; `git remote add upstream https://git.suckless.org/dwm`
to follow it.

## License

MIT/X Consortium, same as dwm. See [LICENSE](LICENSE). Copyright of the original dwm authors is kept.
