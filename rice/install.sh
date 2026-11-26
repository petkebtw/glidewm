#!/bin/sh
# Link the rice helpers into your home. Nothing is overwritten: existing files are skipped.
# Usage: ./install.sh        (run from the rice/ directory)
set -e
R="$(cd "$(dirname "$0")" && pwd)"
# the C helpers (lean/: nothp and the resident daemons clip-daemon, polkit-agent, rice-toplevels) first: bin/ and
# shell/ours link to them
if command -v cc >/dev/null 2>&1 && command -v make >/dev/null 2>&1; then
  make -s -C "$R/lean" || echo "warn   lean/ did not build (needs libX11, libXfixes, polkit-agent-1 headers)"
else
  echo "warn   no C compiler: lean/ (clip-daemon, polkit-agent, rice-toplevels, nothp) is not built"
fi
link() { # src dst
  mkdir -p "$(dirname "$2")"
  if [ -e "$2" ] || [ -L "$2" ]; then echo "skip   $2 (exists)"; else ln -s "$1" "$2"; echo "link   $2"; fi
}
for f in "$R"/bin/*; do link "$f" "$HOME/.local/bin/$(basename "$f")"; done
mkdir -p "$HOME/.local/lib/rice"
for f in "$R"/lib/*.py; do link "$f" "$HOME/.local/lib/rice/$(basename "$f")"; done
mkdir -p "$HOME/.local/share/dss"
link "$R/shell/port.sh"       "$HOME/.local/share/dss/port.sh"
link "$R/shell/dss-start"     "$HOME/.local/share/dss/dss-start"
link "$R/shell/Wm.dwm.qml"    "$HOME/.local/share/dss/Wm.dwm.qml"
link "$R/shell/ours"          "$HOME/.local/share/dss/ours"
link "$R/shell/patches"       "$HOME/.local/share/dss/patches"
link "$R/shell/dss/quickshell" "$HOME/.local/share/dss/src"
link "$R/shell/dss/bin"       "$HOME/.local/share/dss/bin-src"
link "$R/shell/dss/qml"       "$HOME/.local/share/dss/qml"
link "$R/shell/dss/sounds"    "$HOME/.local/share/dss/sounds"
for f in "$R"/config/rofi/*.rasi; do link "$f" "$HOME/.config/rofi/$(basename "$f")"; done
link "$R/config/rice.conf"    "$HOME/.config/picom/rice.conf"
link "$R/config/binds.conf"   "$HOME/.config/rice/binds.conf"
echo
echo "Done. Copy config/xprofile.example to ~/.xprofile (or merge it), then see the README."
echo "Then build the Quickshell shell: ~/.local/share/dss/port.sh (writes ~/.config/quickshell), start it with dss-start."
