#!/usr/bin/env bash
# mwm all-in-one installer: checks every dependency, says what is missing, then installs
#   1. mwm itself (make, sudo make install -> /usr/local/bin/mwm: its own name, a system dwm is never touched)
#   2. the rice: helpers, Python library, configs (links into ~/.local/bin, ~/.local/lib/rice, ~/.config)
#   3. the Quickshell shell (DarkShadow's Shell, built for X11 by port.sh)
#   4. a login session "mwm" for SDDM, LightDM, GDM ... and app menu entries
#
#   ./install.sh              check, then install everything (asks before it starts)
#   ./install.sh --check      only check the dependencies and the existing setup
#   ./install.sh --yes        do not ask
#   ./install.sh --dry-run    show every step, change nothing
#   ./install.sh --no-build | --no-rice | --no-shell | --no-session | --no-apps     leave a part out
#
# Nothing of yours is overwritten: existing files are skipped or backed up (*.bak-DATE), and the script says which.
set -u
R="$(cd "$(dirname "$0")" && pwd)"
STAMP=$(date +%Y%m%d-%H%M%S)
YES=0 DRY=0 CHECK=0 BUILD=1 RICE=1 SHELL_=1 SESSION=1 APPS=1
for a in "$@"; do
  case "$a" in
    --yes|-y) YES=1 ;; --dry-run|-n) DRY=1 ;; --check) CHECK=1 ;;
    --no-build) BUILD=0 ;; --no-rice) RICE=0 ;; --no-shell) SHELL_=0 ;; --no-session) SESSION=0 ;; --no-apps) APPS=0 ;;
    -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $a (see --help)"; exit 2 ;;
  esac
done

if [ -t 1 ]; then B=$'\e[1m' G=$'\e[32m' Y=$'\e[33m' E=$'\e[31m' D=$'\e[2m' N=$'\e[0m'; else B= G= Y= E= D= N=; fi
ok()   { printf '  %s✔%s %s\n' "$G" "$N" "$*"; }
warn() { printf '  %s!%s %s\n' "$Y" "$N" "$*"; WARNS=$((WARNS + 1)); }
bad()  { printf '  %s✘%s %s\n' "$E" "$N" "$*"; }
head_() { printf '\n%s%s%s\n' "$B" "$*" "$N"; }
run()  { if [ "$DRY" = 1 ]; then printf '  %s$ %s%s\n' "$D" "$*" "$N"; else "$@"; fi; }
WARNS=0

# ---------- distro ----------
DISTRO=other
if command -v emerge >/dev/null; then DISTRO=gentoo
elif command -v pacman >/dev/null; then DISTRO=arch
elif command -v apt-get >/dev/null; then DISTRO=debian
elif command -v dnf >/dev/null; then DISTRO=fedora
fi

# ---------- dependencies ----------
# level|what|how to check|gentoo|arch|debian|fedora
# level: build (needed for mwm), core (the rice), shell (the Quickshell shell), opt (one feature)
# how: a command name, py:MODULE, pc:PKGCONFIG, font:NAME
DEPS='
build|C compiler|cc|sys-devel/gcc|base-devel|build-essential|gcc
build|make|make|dev-build/make|base-devel|build-essential|make
build|pkg-config|pkg-config|dev-util/pkgconf|pkgconf|pkg-config|pkgconf
build|Xlib headers|pc:x11|x11-libs/libX11|libx11|libx11-dev|libX11-devel
build|Xft headers|pc:xft|x11-libs/libXft|libxft|libxft-dev|libXft-devel
build|Xinerama headers|pc:xinerama|x11-libs/libXinerama|libxinerama|libxinerama-dev|libXinerama-devel
build|XTest headers|pc:xtst|x11-libs/libXtst|libxtst|libxtst-dev|libXtst-devel
build|Xext headers|pc:xext|x11-libs/libXext|libxext|libxext-dev|libXext-devel
build|cairo (xlib)|pc:cairo-xlib|x11-libs/cairo|cairo|libcairo2-dev|cairo-devel
build|fontconfig|pc:fontconfig|media-libs/fontconfig|fontconfig|libfontconfig1-dev|fontconfig-devel
build|freetype|pc:freetype2|media-libs/freetype|freetype2|libfreetype-dev|freetype-devel
core|xrdb (colours)|xrdb|x11-apps/xrdb|xorg-xrdb|x11-xserver-utils|xrdb
core|xrandr|xrandr|x11-apps/xrandr|xorg-xrandr|x11-xserver-utils|xrandr
core|xset|xset|x11-apps/xset|xorg-xset|x11-xserver-utils|xset
core|setxkbmap|setxkbmap|x11-apps/setxkbmap|xorg-setxkbmap|x11-xkb-utils|setxkbmap
core|xprop|xprop|x11-apps/xprop|xorg-xprop|x11-utils|xprop
core|xinput|xinput|x11-apps/xinput|xorg-xinput|xinput|xinput
core|Python 3|python3|dev-lang/python|python|python3|python3
core|PyGObject (GTK 3)|py:gi|dev-python/pygobject|python-gobject|python3-gi|python3-gobject
core|GTK 3|py:gtk3|x11-libs/gtk+:3|gtk3|gir1.2-gtk-3.0|gtk3
core|pycairo|py:cairo|dev-python/pycairo|python-cairo|python3-gi-cairo|python3-cairo
core|Pillow|py:PIL|dev-python/pillow|python-pillow|python3-pil|python3-pillow
core|picom (blur, shadows)|picom|x11-misc/picom|picom|picom|picom
core|rofi|rofi|x11-misc/rofi|rofi|rofi|rofi
core|feh (wallpaper)|feh|media-gfx/feh|feh|feh|feh
core|xdotool|xdotool|x11-misc/xdotool|xdotool|xdotool|xdotool
core|xclip|xclip|x11-misc/xclip|xclip|xclip|xclip
core|maim (screenshots)|maim|media-gfx/maim|maim|maim|maim
core|slop|slop|x11-misc/slop|slop|slop|slop
core|ImageMagick|magick|media-gfx/imagemagick|imagemagick|imagemagick|ImageMagick
core|PipeWire|pipewire|media-video/pipewire|pipewire|pipewire|pipewire
core|WirePlumber (wpctl)|wpctl|media-video/wireplumber|wireplumber|wireplumber|wireplumber
core|pactl|pactl|media-sound/pulseaudio-utils|libpulse|pulseaudio-utils|pulseaudio-utils
core|notify-send|notify-send|x11-libs/libnotify|libnotify|libnotify-bin|libnotify
core|dunst (notifications)|dunst|x11-misc/dunst|dunst|dunst|dunst
core|curl|curl|net-misc/curl|curl|curl|curl
core|git (updates)|git|dev-vcs/git|git|git|git
core|jq|jq|app-misc/jq|jq|jq|jq
core|fontconfig tools|fc-list|media-libs/fontconfig|fontconfig|fontconfig|fontconfig
core|JetBrains Mono|font:JetBrains Mono|media-fonts/jetbrains-mono|ttf-jetbrains-mono|fonts-jetbrains-mono|jetbrains-mono-fonts
core|Symbols Nerd Font|font:Symbols Nerd Font|media-fonts/nerdfonts|ttf-nerd-fonts-symbols|(nerd-fonts release)|(nerd-fonts release)
core|a terminal (konsole)|konsole|kde-apps/konsole|konsole|konsole|konsole
shell|Quickshell (X11 build)|qs|gui-apps/quickshell (USE=X -layer-shell)|quickshell|(build from source)|(copr)
opt|Qt 6 SVG (some shell icons)|qt:svg|dev-qt/qtsvg:6|qt6-svg|qt6-svg-dev|qt6-qtsvg
opt|tesseract (OCR in screenshots)|tesseract|app-text/tesseract|tesseract|tesseract-ocr|tesseract
opt|ffmpeg (recorder, converter)|ffmpeg|media-video/ffmpeg|ffmpeg|ffmpeg|ffmpeg
opt|qrencode (QR codes)|qrencode|media-gfx/qrencode|qrencode|qrencode|qrencode
opt|rsvg-convert (icons)|rsvg-convert|gnome-base/librsvg|librsvg|librsvg2-bin|librsvg2-tools
opt|playerctl (media keys)|playerctl|media-sound/playerctl|playerctl|playerctl|playerctl
opt|mpv (live wallpapers)|mpv|media-video/mpv|mpv|mpv|mpv
opt|NetworkManager (Wi-Fi toggle)|nmcli|net-misc/networkmanager|networkmanager|network-manager|NetworkManager
opt|bluetoothctl|bluetoothctl|net-wireless/bluez|bluez-utils|bluez|bluez
opt|brightnessctl|brightnessctl|app-misc/brightnessctl|brightnessctl|brightnessctl|brightnessctl
opt|power-profiles-daemon|powerprofilesctl|sys-power/power-profiles-daemon|power-profiles-daemon|power-profiles-daemon|power-profiles-daemon
opt|a polkit agent|polkit-agent-any|sys-auth/polkit-kde-agent|polkit-kde-agent|polkit-kde-agent-1|polkit-kde
opt|fastfetch|fastfetch|app-misc/fastfetch|fastfetch|fastfetch|fastfetch
opt|btop|btop|sys-process/btop|btop|btop|btop
opt|cava (visualiser)|cava|media-sound/cava|cava|cava|cava
opt|kitty|kitty|x11-terms/kitty|kitty|kitty|kitty
opt|dolphin (files)|dolphin|kde-apps/dolphin|dolphin|dolphin|dolphin
opt|ClamAV (security page)|clamscan|app-antivirus/clamav|clamav|clamav|clamav
opt|zenity (dialogs)|zenity|gnome-extra/zenity|zenity|zenity|zenity
'

have() {
  local how="$1"
  case "$how" in
    pc:*) pkg-config --exists "${how#pc:}" 2>/dev/null ;;
    qt:svg) ls /usr/lib*/qt6/plugins/imageformats/libqsvg.so /usr/lib/*/qt6/plugins/imageformats/libqsvg.so >/dev/null 2>&1 ;;
    py:gtk3) python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" 2>/dev/null ;;
    py:*) python3 -c "import ${how#py:}" 2>/dev/null ;;
    font:*) fc-list 2>/dev/null | grep -qi "${how#font:}" ;;
    polkit-agent-any)
      for p in /usr/lib*/polkit-kde-authentication-agent-1 /usr/libexec/polkit-kde-authentication-agent-1 \
               /usr/lib*/polkit-gnome/polkit-gnome-authentication-agent-1 /usr/libexec/polkit-gnome-authentication-agent-1; do
        [ -x "$p" ] && return 0
      done
      command -v lxpolkit >/dev/null || command -v mate-polkit >/dev/null ;;
    *) command -v "$how" >/dev/null ;;
  esac
}

MISS_build=() MISS_core=() MISS_shell=() MISS_opt=() PKGS=()
check_deps() {
  local lvl what how g a d f pk title
  for lvl in build core shell opt; do
    case $lvl in
      build) title="Build (needed for mwm)" ;; core) title="Rice (needed for the desktop)" ;;
      shell) title="Shell (Quickshell widgets, menus, settings)" ;; opt) title="Optional (one feature each)" ;;
    esac
    head_ "$title"
    while IFS='|' read -r l what how g a d f; do
      [ "$l" = "$lvl" ] || continue
      case $DISTRO in gentoo) pk=$g ;; arch) pk=$a ;; debian) pk=$d ;; fedora) pk=$f ;; *) pk="" ;; esac
      if have "$how"; then ok "$what"
      else
        if [ "$lvl" = opt ]; then warn "$what  ${D}($pk)${N}"; else bad "$what  ${D}($pk)${N}"; fi
        eval "MISS_$lvl+=(\"\$what\")"
        case "$pk" in ""|\(*) ;; *) PKGS+=("${pk%% *}") ;; esac
      fi
    done <<< "$DEPS"
  done
}

# ---------- init system, session services ----------
INIT=unknown
check_init() {
  head_ "Init system and session services"
  local p1; p1=$(ps -p 1 -o comm= 2>/dev/null)
  if [ -d /run/systemd/system ]; then INIT=systemd
  elif [ "$p1" = runit ] || [ -d /run/runit ]; then INIT=runit
  elif command -v openrc >/dev/null || [ -d /run/openrc ]; then INIT=openrc
  elif [ "$p1" = s6-svscan ] || command -v s6-rc >/dev/null; then INIT=s6
  elif [ "$p1" = dinit ] || command -v dinitctl >/dev/null; then INIT=dinit
  elif [ "$p1" = init ]; then INIT=sysvinit
  fi
  ok "init: $INIT${p1:+ (PID 1: $p1)}"
  # login and seat manager: loginctl (power menu, lock, session restore) needs logind or elogind
  if [ "$INIT" = systemd ]; then ok "logind: systemd-logind"
  elif pgrep -x elogind >/dev/null || pgrep -x elogind-daemon >/dev/null; then ok "logind: elogind is running"
  else warn "no elogind running: reboot, power off and suspend in the power menu need it (or a seatd + sudo setup). Install and enable elogind"; fi
  # polkit: the auth prompts, DNS/MTU changes in settings
  if pgrep -x polkitd >/dev/null; then ok "polkit is running"; else warn "polkitd is not running: pkexec prompts (settings, power) fail"; fi
  # D-Bus: notifications, the tray, MPRIS
  if pgrep -x dbus-daemon >/dev/null || pgrep -x dbus-broker >/dev/null; then ok "D-Bus system bus is running"
  else warn "no D-Bus system bus: start the dbus service"; fi
  command -v dbus-run-session >/dev/null || warn "dbus-run-session is missing: startx gets no session bus"
  # PipeWire: systemd starts it per user; other inits need it in ~/.xprofile
  if [ "$INIT" = systemd ]; then
    if systemctl --user is-enabled pipewire.socket >/dev/null 2>&1 || systemctl --user is-active pipewire >/dev/null 2>&1; then ok "PipeWire: started by systemd --user"
    else warn "PipeWire is not enabled: systemctl --user enable --now pipewire pipewire-pulse wireplumber"; fi
  else
    if grep -qE '^[^#]*(pipewire|gentoo-pipewire-launcher)' "$HOME/.xprofile" 2>/dev/null; then ok "PipeWire: started from ~/.xprofile ($INIT has no user services)"
    else warn "$INIT does not start PipeWire per user: ~/.xprofile has to (the example has it: gentoo-pipewire-launcher or pipewire &, wireplumber &, pipewire-pulse &)"; fi
  fi
  # a display manager that starts at boot
  local dm="" d
  case $INIT in
    systemd) dm=$(systemctl is-enabled display-manager.service >/dev/null 2>&1 && readlink -f /etc/systemd/system/display-manager.service | xargs -r basename | sed 's/\.service$//') ;;
    openrc)  dm=$(rc-update show default 2>/dev/null | awk '{print $1}' | grep -E '^(display-manager|xdm|sddm|lightdm|gdm|lxdm|greetd|ly)$' | head -1)
             [ "$dm" = display-manager ] && dm="display-manager ($(sed -n 's/^DISPLAYMANAGER="\{0,1\}\([^"]*\)"\{0,1\}/\1/p' /etc/conf.d/display-manager 2>/dev/null))" ;;
    runit)   for d in /var/service /etc/runit/runsvdir/default /etc/runit/runsvdir/current /run/runit/service; do
               [ -d "$d" ] || continue
               dm=$(ls "$d" 2>/dev/null | grep -E '^(sddm|lightdm|gdm|lxdm|greetd|ly|xdm)$' | head -1); [ -n "$dm" ] && break
             done ;;
    s6)      dm=$(s6-rc -a list 2>/dev/null | grep -E '^(sddm|lightdm|gdm|greetd|ly)' | head -1) ;;
    dinit)   dm=$(dinitctl list 2>/dev/null | grep -oE '\b(sddm|lightdm|gdm|greetd|ly)\b' | head -1) ;;
  esac
  if [ -n "$dm" ]; then ok "display manager at boot: $dm (it lists /usr/share/xsessions: pick \"mwm\")"
  else
    warn "no display manager starts at boot: log in on a TTY and run startx (~/.xinitrc), or enable one:"
    case $INIT in
      systemd) echo "      sudo systemctl enable sddm" ;;
      openrc)  echo "      set DISPLAYMANAGER=\"sddm\" in /etc/conf.d/display-manager, then: sudo rc-update add display-manager default" ;;
      runit)   echo "      sudo ln -s /etc/sv/sddm /var/service/   (Void; Artix: /etc/runit/sv/sddm -> /run/runit/service/)" ;;
      s6)      echo "      sudo s6-rc-bundle-update add default sddm-srv" ;;
      dinit)   echo "      sudo dinitctl enable sddm" ;;
    esac
  fi
  return 0
}

# ---------- what is already there (duplicates and conflicts) ----------
check_setup() {
  head_ "Your setup"
  # the binary: mwm installs as /usr/local/bin/mwm and never touches dwm
  if [ -e /usr/local/bin/mwm ]; then
    if strings /usr/local/bin/mwm 2>/dev/null | grep -q _RICE_CMD; then ok "/usr/local/bin/mwm is installed (replaced by this build)"
    else warn "/usr/local/bin/mwm is some other program: it is backed up to /usr/local/bin/mwm.bak-$STAMP first"; fi
  fi
  # an older mwm install under the name dwm: it shadows a system dwm (Exec=dwm of a dwm login entry starts it)
  if [ -e /usr/local/bin/dwm ] && strings /usr/local/bin/dwm 2>/dev/null | grep -q _RICE_CMD; then
    warn "/usr/local/bin/dwm is an older mwm install under the name dwm: it hides your system dwm. Once you log in with \"mwm\": sudo rm /usr/local/bin/dwm"
  fi
  # login sessions
  local s n=0
  for s in /usr/share/xsessions/*.desktop; do
    [ -f "$s" ] || continue
    case "$(basename "$s")" in mwm.desktop) continue ;; esac
    grep -qE '^Exec=.*(^|/| )mwm(-session)?( |$)' "$s" && warn "login entry $(basename "$s") also starts mwm: the menu will have two"
  done
  [ -f /usr/share/xsessions/mwm.desktop ] && ok "login entry mwm.desktop exists (updated if it differs)"
  # PATH
  case ":$PATH:" in *":$HOME/.local/bin:"*) ok "~/.local/bin is in PATH" ;;
    *) warn "~/.local/bin is not in PATH: add  export PATH=\"\$HOME/.local/bin:\$PATH\"  to ~/.xprofile (the example has it)" ;; esac
  # helpers shadowed by other programs of the same name
  local f p
  for f in "$R"/rice/bin/*; do
    p=$(type -ap "$(basename "$f")" 2>/dev/null | grep -v "^$HOME/.local/bin/" | head -1)
    [ -n "$p" ] && warn "$(basename "$f") also exists as $p"
  done
  # ~/.xprofile: started twice?
  if [ -f "$HOME/.xprofile" ]; then
    local c
    for c in picom dss-start dunst rice-hotcorner theme-switch; do
      n=$(grep -cE "^[^#]*\b$c\b" "$HOME/.xprofile" 2>/dev/null)
      [ "${n:-0}" -gt 1 ] && warn "~/.xprofile starts $c $n times"
    done
    grep -qE '^[^#]*(exec +)?(/usr/local/bin/)?(mwm|mwm-session)( |&|$)' "$HOME/.xprofile" && warn "~/.xprofile starts mwm: the login entry starts it too (remove it from ~/.xprofile)"
    ok "~/.xprofile exists (kept; compare with rice/config/xprofile.example)"
  fi
  if [ -f "$HOME/.xinitrc" ]; then
    n=$(grep -cE '^[^#]*\bexec\b' "$HOME/.xinitrc")
    [ "${n:-0}" -gt 1 ] && warn "~/.xinitrc has $n exec lines: only the first one runs"
  fi
  # running twice right now
  for c in picom dunst; do
    n=$(pgrep -cx "$c" 2>/dev/null); [ "${n:-0}" -gt 1 ] && warn "$n $c processes are running"
  done
  n=$(pgrep -fc 'quickshell/rice-desktop' 2>/dev/null); [ "${n:-0}" -gt 1 ] && warn "$n desktop shells are running"
  # files in the way of the rice links (real files, not links: install.sh skips them)
  n=0
  for f in "$R"/rice/bin/*; do [ -e "$HOME/.local/bin/$(basename "$f")" ] && [ ! -L "$HOME/.local/bin/$(basename "$f")" ] && n=$((n + 1)); done
  [ $n -gt 0 ] && warn "$n helpers in ~/.local/bin are your own files, not links to this repo: they are kept (delete one to use the repo's)"
  return 0
}

check_deps
check_init
check_setup

head_ "Summary"
nb=${#MISS_build[@]} nc=${#MISS_core[@]} ns=${#MISS_shell[@]} no=${#MISS_opt[@]}
[ $nb -eq 0 ] && ok "build: all there" || bad "build: $nb missing: ${MISS_build[*]}"
[ $nc -eq 0 ] && ok "rice: all there" || bad "rice: $nc missing: ${MISS_core[*]}"
[ $ns -eq 0 ] && ok "shell: all there" || bad "shell: $ns missing: ${MISS_shell[*]}"
[ $no -eq 0 ] && ok "optional: all there" || warn "optional: $no missing: ${MISS_opt[*]}"
if [ ${#PKGS[@]} -gt 0 ]; then
  pk=$(printf '%s\n' "${PKGS[@]}" | awk '!s[$0]++' | tr '\n' ' ')
  case $DISTRO in
    gentoo) echo "  install:  sudo emerge -av $pk" ;; arch) echo "  install:  sudo pacman -S --needed $pk" ;;
    debian) echo "  install:  sudo apt install $pk" ;; fedora) echo "  install:  sudo dnf install $pk" ;;
    *) echo "  packages: $pk" ;;
  esac
fi
[ "$CHECK" = 1 ] && exit 0

[ $nb -gt 0 ] && [ "$BUILD" = 1 ] && { bad "mwm cannot be built without the build dependencies. Install them, or run with --no-build."; exit 1; }
[ $ns -gt 0 ] && [ "$SHELL_" = 1 ] && { warn "Quickshell is missing: the shell part is left out (--no-shell)"; SHELL_=0; }
[ $nc -gt 0 ] && warn "the rice is installed, but the parts that need the missing programs will not work until you install them"

if [ "$YES" = 0 ] && [ "$DRY" = 0 ]; then
  echo
  printf '%sInstall%s:' "$B" "$N"
  [ $BUILD = 1 ] && printf ' mwm'; [ $RICE = 1 ] && printf ' rice'; [ $SHELL_ = 1 ] && printf ' shell'
  [ $SESSION = 1 ] && printf ' login-session'; [ $APPS = 1 ] && printf ' app-entries'
  printf '  [Y/n] '
  read -r ans; case "$ans" in ""|y|Y|yes) ;; *) echo "Nothing changed."; exit 0 ;; esac
fi

SUDO=sudo; [ "$(id -u)" = 0 ] && SUDO=
rootwrite() { # dst  (content on stdin): write a root-owned file only when it differs; back up an old one
  local dst=$1 tmp; tmp=$(mktemp); cat > "$tmp"
  if [ -f "$dst" ] && cmp -s "$tmp" "$dst"; then ok "$dst is up to date"; rm -f "$tmp"; return; fi
  [ -f "$dst" ] && run $SUDO cp "$dst" "$dst.bak-$STAMP" && echo "  backup: $dst.bak-$STAMP"
  run $SUDO install -Dm "${MODE:-644}" "$tmp" "$dst" && ok "wrote $dst"
  rm -f "$tmp"
}

# ---------- 1. mwm ----------
if [ $BUILD = 1 ]; then
  head_ "1. mwm"
  cd "$R" || exit 1
  if [ -f config.h ]; then ok "config.h exists: your config is kept (config.def.h is the default)"
  else run cp config.def.h config.h && ok "config.h made from config.def.h"; fi
  if [ "$DRY" = 1 ]; then run make
  else make >/tmp/mwm-build.$$ 2>&1 || { bad "make failed:"; tail -20 /tmp/mwm-build.$$; rm -f /tmp/mwm-build.$$; exit 1; }
       rm -f /tmp/mwm-build.$$; ok "built ./mwm"; fi
  if [ -e /usr/local/bin/mwm ] && ! strings /usr/local/bin/mwm 2>/dev/null | grep -q _RICE_CMD; then
    run $SUDO cp /usr/local/bin/mwm "/usr/local/bin/mwm.bak-$STAMP" && echo "  backup: /usr/local/bin/mwm.bak-$STAMP"
  fi
  if [ "$DRY" = 1 ]; then run $SUDO make install; else $SUDO make install >/dev/null && ok "installed /usr/local/bin/mwm"; fi
  if pgrep -x mwm >/dev/null; then echo "  mwm is running: Mod+Ctrl+Shift+q restarts it into the new build (windows and tags stay)"
  elif pgrep -x dwm >/dev/null && [ "$(readlink -f /proc/$(pgrep -x dwm | head -1)/exe 2>/dev/null)" = /usr/local/bin/dwm ]; then
    echo "  the running session is the older mwm under the name dwm: log out and pick \"mwm\" to use the new build"
  fi
fi

# ---------- 2. the rice ----------
if [ $RICE = 1 ]; then
  head_ "2. Rice (helpers, library, configs)"
  if [ "$DRY" = 1 ]; then run "$R/rice/install.sh"
  else (cd "$R/rice" && ./install.sh) | grep -v "^$\|^Done\. Copy\|^Then build" | sed "s/^/  /"; fi
  if [ -f "$HOME/.xprofile" ]; then ok "~/.xprofile kept"
  else run cp "$R/rice/config/xprofile.example" "$HOME/.xprofile" && ok "~/.xprofile made from the example: edit the monitors and wallpaper"; fi
  mkdir -p "$HOME/.config/rice" "$HOME/Pictures/wallpapers" 2>/dev/null
fi

# ---------- 3. the shell ----------
if [ $SHELL_ = 1 ]; then
  head_ "3. Shell (Quickshell)"
  S="$HOME/.local/share/dss"
  if [ ! -e "$S/src" ]; then
    bad "$S/src is missing: the rice part links it (run without --no-rice)"
  else
    [ -f "$S/upstream.rev" ] || { run cp "$R/rice/shell/dss/UPSTREAM" "$S/upstream.rev" && ok "shell version recorded (updates start from it)"; }
    if [ "$DRY" = 1 ]; then run bash "$S/port.sh"
    elif bash "$S/port.sh" >/tmp/mwm-port.$$ 2>&1; then ok "built ~/.config/quickshell"
    else bad "port.sh failed:"; tail -15 /tmp/mwm-port.$$; fi
    rm -f /tmp/mwm-port.$$
    grep -q 'dss-start' "$HOME/.xprofile" 2>/dev/null && ok "~/.xprofile starts the shell" \
      || warn "add to ~/.xprofile, after picom:  (sleep 1; ~/.local/share/dss/dss-start) &"
  fi
fi

# ---------- 4a. login session ----------
if [ $SESSION = 1 ]; then
  head_ "4. Login session (SDDM, LightDM, GDM, startx)"
  MODE=755 rootwrite /usr/local/bin/mwm-session <<'EOF'
#!/bin/sh
# mwm session: what the display manager runs (it has already read ~/.xprofile) and what ~/.xinitrc can exec.
# A session D-Bus when there is none (startx), so notifications, the tray and portals work.
if [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ] && command -v dbus-run-session >/dev/null; then
  exec dbus-run-session /usr/local/bin/mwm
fi
exec /usr/local/bin/mwm
EOF
  rootwrite /usr/share/xsessions/mwm.desktop <<'EOF'
[Desktop Entry]
Name=mwm
Comment=muxy window manager (dwm fork) with the rice shell
Exec=/usr/local/bin/mwm-session
TryExec=/usr/local/bin/mwm
Type=XSession
DesktopNames=mwm
EOF
  for dm in sddm lightdm gdm lxdm ly greetd; do command -v "$dm" >/dev/null && ok "$dm reads /usr/share/xsessions: pick \"mwm\" at the login screen"; done
  if [ -f "$HOME/.xinitrc" ]; then
    if grep -q 'mwm-session\|exec .*\bmwm\b' "$HOME/.xinitrc"; then ok "~/.xinitrc starts mwm"
    else echo "  startx: ~/.xinitrc starts something else ($(grep -m1 -E '^[^#]*\bexec\b' "$HOME/.xinitrc" | sed 's/^ *//')): put  exec /usr/local/bin/mwm-session  there instead"; fi
  else
    run sh -c "printf '%s\n' '#!/bin/sh' '[ -f \"\$HOME/.xprofile\" ] && . \"\$HOME/.xprofile\"' 'exec /usr/local/bin/mwm-session' > \"\$HOME/.xinitrc\"" \
      && ok "~/.xinitrc made (startx starts mwm)"
  fi
fi

# ---------- 4b. app entries ----------
if [ $APPS = 1 ]; then
  head_ "5. App menu entries"
  A="$HOME/.local/share/applications"; L="$HOME/.local/bin"
  mkdir -p "$A"
  # file|Name|Comment|Exec|Icon|Keywords|Categories
  ENTRIES="
mwm-settings|mwm Settings|Display, keyboard, gaps, network, shortcuts|$L/rice-settings|preferences-system|settings;display;keyboard;network;shortcuts;|Settings;DesktopSettings;
mwm-shell-settings|Shell Settings|Widgets, look, notifications, wallpapers, updates|$HOME/.local/share/dss/bin/rice-settings|preferences-desktop|shell;widgets;theme;update;|Settings;DesktopSettings;
mwm-themes|Theme Switcher|Pick a wallpaper theme, colours follow|$L/theme-switch|preferences-desktop-theme|theme;wallpaper;colors;|Settings;DesktopSettings;
mwm-wallpapers|Wallpapers|Wallpaper picker|$L/rice-wall|preferences-desktop-wallpaper|wallpaper;background;|Settings;DesktopSettings;
mwm-screenshot|Screenshot|Region, annotate, OCR|$L/rice-shot|applets-screenshooter|screenshot;capture;ocr;|Utility;Graphics;
mwm-recorder|Screen Recorder|Record the desktop, a monitor or a region|$L/rice-record|media-record|record;video;screencast;|Utility;AudioVideo;
mwm-overview|Monitor Overview|Every monitor, drag windows between them|$L/rice-map|video-display|monitors;overview;|Utility;
mwm-tools|Tools|Convert, download, colour picker, QR code|$L/rice-tools|applications-utilities|tools;convert;qr;color;|Utility;
mwm-lock|Lock Screen|Lock now|$L/rice-lock|system-lock-screen|lock;|System;
"
  while IFS='|' read -r file name cmt exe icon kw cat; do
    [ -n "$file" ] || continue
    [ -x "$exe" ] || [ "$DRY" = 1 ] || { warn "$name: $exe is missing, no entry"; continue; }
    dst="$A/$file.desktop"
    new="[Desktop Entry]
Type=Application
Name=$name
Comment=$cmt
Exec=$exe
Icon=$icon
Keywords=$kw
Categories=$cat
X-mwm=1"
    # an entry of the same name that is not ours: a duplicate in the menu
    dup=$(grep -lx "Name=$name" "$A"/*.desktop /usr/share/applications/*.desktop 2>/dev/null | grep -v "^$dst$" | head -1)
    [ -n "$dup" ] && warn "\"$name\" is also in $dup: the menu shows it twice"
    if [ -f "$dst" ] && ! grep -q '^X-mwm=1' "$dst"; then warn "$dst is yours (not made by this script): kept"; continue; fi
    if [ -f "$dst" ] && [ "$(cat "$dst")" = "$new" ]; then ok "$name"; continue; fi
    if [ "$DRY" = 1 ]; then run "write $dst"; else printf '%s\n' "$new" > "$dst" && ok "$name"; fi
  done <<< "$ENTRIES"
  command -v update-desktop-database >/dev/null && run update-desktop-database "$A" 2>/dev/null
fi

head_ "Done"
[ $WARNS -gt 0 ] && echo "  $WARNS notes above (${Y}!${N})."
echo "  Log out and pick \"mwm\" at the login screen, or: startx. Keys: README.md. Updates: Shell Settings > Update Center."
