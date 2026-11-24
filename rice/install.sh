#!/bin/sh
# Link the rice helpers into your home. Nothing is overwritten: existing files are skipped.
# Usage: ./install.sh        (run from the rice/ directory)
set -e
R="$(cd "$(dirname "$0")" && pwd)"
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
link "$R/config/rice.conf"    "$HOME/.config/picom/rice.conf"
link "$R/config/binds.conf"   "$HOME/.config/rice/binds.conf"
echo
echo "Done. Copy config/xprofile.example to ~/.xprofile (or merge it), then see the README."
echo "The Quickshell shell needs DarkShadow's Shell in ~/.local/share/dss/src first, then run port.sh."
