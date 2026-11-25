#!/usr/bin/env bash
# glidewm all-in-one installer: checks every dependency, says what is missing, then installs
#   1. glidewm itself (make, sudo make install -> /usr/local/bin/glidewm: its own name, a system dwm is never touched)
#   2. the rice: helpers, Python library, configs (links into ~/.local/bin, ~/.local/lib/rice, ~/.config)
#   3. the Quickshell shell (DarkShadow's Shell, built for X11 by port.sh)
#   4. a login session "glidewm" for SDDM, LightDM, GDM ... and app menu entries
#
#   ./install.sh              check, then pick what to install from a menu (all parts are on at first)
#   ./install.sh --check      only check the dependencies and the existing setup
#   ./install.sh --yes        do not ask
#   ./install.sh --dry-run    show every step, change nothing
#   ./install.sh --only=rice,shell   install only these parts (build, rice, shell, session, apps), no menu
#   ./install.sh --no-build | --no-rice | --no-shell | --no-session | --no-apps     leave a part out
#   ./install.sh --verbose    also show what is fine and every step done (normally only warnings and errors)
#
# A part whose programs are missing is left out at first; choosing it anyway is an error that names what to install.
# Nothing of yours is overwritten: existing files are skipped or backed up (*.bak-DATE), and the script says which.
set -u
R="$(cd "$(dirname "$0")" && pwd)"
STAMP=$(date +%Y%m%d-%H%M%S)
YES=0 DRY=0 CHECK=0 ONLY=0 VERBOSE=0 BUILD=1 RICE=1 SHELL_=1 SESSION=1 APPS=1
for a in "$@"; do
  case "$a" in
    --yes|-y) YES=1 ;; --dry-run|-n) DRY=1 ;; --check) CHECK=1 ;; --verbose|-v) VERBOSE=1 ;;
    --only=*) BUILD=0 RICE=0 SHELL_=0 SESSION=0 APPS=0; ONLY=1
      for x in $(echo "${a#--only=}" | tr ',' ' '); do
        case $x in build|glidewm|mwm) BUILD=1 ;; rice) RICE=1 ;; shell) SHELL_=1 ;; session|login) SESSION=1 ;; apps|menu) APPS=1 ;;
          *) echo "unknown part: $x (build, rice, shell, session, apps)"; exit 2 ;; esac
      done ;;
    --no-build) BUILD=0 ;; --no-rice) RICE=0 ;; --no-shell) SHELL_=0 ;; --no-session) SESSION=0 ;; --no-apps) APPS=0 ;;
    -h|--help) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $a (see --help)"; exit 2 ;;
  esac
done

if [ -t 1 ]; then B=$'\e[1m' G=$'\e[32m' Y=$'\e[33m' E=$'\e[31m' D=$'\e[2m' N=$'\e[0m'; else B= G= Y= E= D= N=; fi
# only warnings and errors show (and a section header above the first one); --verbose shows the ✔ lines too
HEAD=""
flush_head() { [ -n "$HEAD" ] && printf '\n%s%s%s\n' "$B" "$HEAD" "$N"; HEAD=""; return 0; }
head_() { HEAD="$*"; [ "$VERBOSE" = 1 ] && flush_head; return 0; }
say()  { flush_head; printf '%s\n' "$*"; }
ok()   { [ "$VERBOSE" = 1 ] || return 0; flush_head; printf '  %s✔%s %s\n' "$G" "$N" "$*"; }
warn() { flush_head; printf '  %s!%s %s\n' "$Y" "$N" "$*"; WARNS=$((WARNS + 1)); }
bad()  { flush_head; printf '  %s✘%s %s\n' "$E" "$N" "$*"; }
run()  { if [ "$DRY" = 1 ]; then flush_head; printf '  %s$ %s%s\n' "$D" "$*" "$N"; else "$@"; fi; }
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
# level: build (needed for glidewm), core (the rice), shell (the Quickshell shell), opt (one feature)
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

MISS_build=() MISS_core=() MISS_shell=() MISS_opt=() PKGS=() PK_build=() PK_core=() PK_shell=() PK_opt=()
check_deps() {
  local lvl what how g a d f pk title
  for lvl in build core shell opt; do
    case $lvl in
      build) title="Build (needed for glidewm)" ;; core) title="Rice (needed for the desktop)" ;;
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
        case "$pk" in ""|\(*) ;; *) PKGS+=("${pk%% *}"); eval "PK_$lvl+=(\"\${pk%% *}\")" ;; esac
      fi
    done <<< "$DEPS"
  done
}

# the command that installs packages $@ on this distro (empty when there are none)
install_cmd() {
  local pk; pk=$(printf '%s\n' "$@" | awk 'NF && !s[$0]++' | tr '\n' ' '); pk=${pk% }
  [ -n "$pk" ] || return 0
  case $DISTRO in
    gentoo) echo "sudo emerge -av $pk" ;; arch) echo "sudo pacman -S --needed $pk" ;;
    debian) echo "sudo apt install $pk" ;; fedora) echo "sudo dnf install $pk" ;; *) echo "the packages $pk" ;;
  esac
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
  if [ -n "$dm" ]; then ok "display manager at boot: $dm (it lists /usr/share/xsessions: pick \"glidewm\")"
  else
    warn "no display manager starts at boot: log in on a TTY and run startx (~/.xinitrc), or enable one:"
    case $INIT in
      systemd) say "      sudo systemctl enable sddm" ;;
      openrc)  say "      set DISPLAYMANAGER=\"sddm\" in /etc/conf.d/display-manager, then: sudo rc-update add display-manager default" ;;
      runit)   say "      sudo ln -s /etc/sv/sddm /var/service/   (Void; Artix: /etc/runit/sv/sddm -> /run/runit/service/)" ;;
      s6)      say "      sudo s6-rc-bundle-update add default sddm-srv" ;;
      dinit)   say "      sudo dinitctl enable sddm" ;;
    esac
  fi
  return 0
}

# ---------- what is already there (duplicates and conflicts) ----------
check_setup() {
  head_ "Your setup"
  # the binary: glidewm installs as /usr/local/bin/glidewm and never touches dwm
  if [ -e /usr/local/bin/glidewm ]; then
    if strings /usr/local/bin/glidewm 2>/dev/null | grep -q _RICE_CMD; then ok "/usr/local/bin/glidewm is installed (replaced by this build)"
    else warn "/usr/local/bin/glidewm is some other program: it is backed up to /usr/local/bin/glidewm.bak-$STAMP first"; fi
  fi
  # the old name of this window manager was mwm (renamed: Motif ships an mwm too)
  if [ -e /usr/local/bin/mwm ] && strings /usr/local/bin/mwm 2>/dev/null | grep -q _RICE_CMD; then
    warn "/usr/local/bin/mwm is this window manager under its old name: the glidewm part replaces it (a link while mwm still runs)"
  fi
  [ -f /usr/share/xsessions/mwm.desktop ] && grep -q 'mwm-session' /usr/share/xsessions/mwm.desktop && warn "old login entry mwm.desktop: the Login session part removes it"
  # an older glidewm install under the name dwm: it shadows a system dwm (Exec=dwm of a dwm login entry starts it)
  if [ -e /usr/local/bin/dwm ] && strings /usr/local/bin/dwm 2>/dev/null | grep -q _RICE_CMD; then
    warn "/usr/local/bin/dwm is an older glidewm install under the name dwm: it hides your system dwm. Once you log in with \"glidewm\": sudo rm /usr/local/bin/dwm"
  fi
  # login sessions
  local s n=0
  for s in /usr/share/xsessions/*.desktop; do
    [ -f "$s" ] || continue
    case "$(basename "$s")" in glidewm.desktop) continue ;; esac
    grep -qE '^Exec=.*(^|/| )glidewm(-session)?( |$)' "$s" && warn "login entry $(basename "$s") also starts glidewm: the menu will have two"
  done
  [ -f /usr/share/xsessions/glidewm.desktop ] && ok "login entry glidewm.desktop exists (updated if it differs)"
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
    grep -qE '^[^#]*(exec +)?(/usr/local/bin/)?(glidewm|glidewm-session)( |&|$)' "$HOME/.xprofile" && warn "~/.xprofile starts glidewm: the login entry starts it too (remove it from ~/.xprofile)"
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
[ ${#PKGS[@]} -gt 0 ] && say "  install:  $(install_cmd "${PKGS[@]}")"
[ "$CHECK" = 1 ] && exit 0

# ---------- what to install ----------
PART_VAR=(BUILD RICE SHELL_ SESSION APPS)
PART_NAME=("glidewm" "Rice" "Shell" "Login session" "App menu entries")
PART_DESC=("build, sudo make install -> /usr/local/bin/glidewm"
           "rice-* helpers, Python library, picom/rofi/keys configs, ~/.xprofile"
           "Quickshell: widgets, control centre, launcher, settings, lock (needs the rice once)"
           "\"glidewm\" at the SDDM / LightDM / GDM login, ~/.xinitrc for startx (sudo)"
           "Settings, Theme Switcher, Screenshot, Recorder ... in your app launcher")
# part I needs part J, unless J's result is already in place (then installing I alone is fine)
needs() {
  case $1 in
    2) [ -e "$HOME/.local/share/dss/src" ] || echo 1 ;;          # Shell: the rice links the shell files
    3) [ -x /usr/local/bin/glidewm ] || echo 0 ;;                     # Login session: runs /usr/local/bin/glidewm
    4) [ -x "$HOME/.local/bin/rice-settings" ] || echo 1 ;;       # App entries: start the rice helpers
  esac
}
# the programs part I needs that are not installed, and their packages
missing() { case $1 in 0) echo "${MISS_build[*]}" ;; 1) echo "${MISS_core[*]}" ;; 2) echo "${MISS_shell[*]}" ;; esac; }
part_pkgs() {
  case $1 in 0) printf '%s\n' ${PK_build[@]+"${PK_build[@]}"} ;; 1) printf '%s\n' ${PK_core[@]+"${PK_core[@]}"} ;;
             2) printf '%s\n' ${PK_shell[@]+"${PK_shell[@]}"} ;; esac
}
# the error for a chosen part whose programs are missing (empty when it can be installed)
part_err() {
  local m c; m=$(missing "$1"); [ -n "$m" ] || return 0
  mapfile -t _p < <(part_pkgs "$1"); c=$(install_cmd ${_p[@]+"${_p[@]}"})
  if [ -n "$c" ]; then echo "${PART_NAME[$1]} needs $m: install it first: $c"; else echo "${PART_NAME[$1]} needs $m: install it first"; fi
}
sel_errs() { local i; for i in 0 1 2 3 4; do [ "${!PART_VAR[i]}" = 1 ] && part_err "$i"; done; return 0; }
NOTE=""
note() { NOTE="${NOTE:+$NOTE; }$*"; }
part_on() {   # turn on part $1 and what it needs
  local j
  eval "${PART_VAR[$1]}=1"
  for j in $(needs "$1"); do
    [ "${!PART_VAR[j]}" = 1 ] && continue
    note "${PART_NAME[j]} turned on: ${PART_NAME[$1]} needs it"
    part_on "$j"
  done
}
part_off() {  # turn off part $1 and what needs it
  local i
  eval "${PART_VAR[$1]}=0"
  for i in 0 1 2 3 4; do
    [ "${!PART_VAR[i]}" = 1 ] || continue
    case " $(needs $i | tr '\n' ' ') " in *" $1 "*) note "${PART_NAME[i]} turned off: it needs ${PART_NAME[$1]}"; part_off "$i" ;; esac
  done
}
flush_notes() { [ -n "$NOTE" ] && { while read -r l; do warn "$l"; done < <(printf '%s\n' "$NOTE" | tr ';' '\n' | sed 's/^ *//'); NOTE=""; }; return 0; }
resolve() {   # add what the chosen parts need
  local i
  for i in 0 1 2 3 4; do [ "${!PART_VAR[i]}" = 1 ] && part_on "$i"; done
  flush_notes
}
# a chosen part that cannot be installed: say what to install, then stop
fail_errs() {
  local e; e=$(sel_errs); [ -n "$e" ] || return 0
  HEAD="Cannot install"
  while IFS= read -r l; do bad "$l"; done <<< "$e"
  say "  Install the missing programs and run ./install.sh again, or leave those parts out."
  exit 1
}

menu_plain() {
  local i v ans k m
  while :; do
    printf '\n%sChoose what to install%s  %s(numbers toggle, a = all, n = none, Enter = start, q = quit)%s\n' "$B" "$N" "$D" "$N"
    for i in 0 1 2 3 4; do
      v=${!PART_VAR[i]} m=$(missing $i)
      local mark="[ ]"; [ "$v" = 1 ] && mark="$G[x]$N"
      if [ -n "$m" ]; then printf '  %d  %s %-18s %smissing: %s%s\n' $((i + 1)) "$mark" "${PART_NAME[i]}" "$E" "$m" "$N"
      else printf '  %d  %s %-18s %s%s%s\n' $((i + 1)) "$mark" "${PART_NAME[i]}" "$D" "${PART_DESC[i]}" "$N"; fi
    done
    printf '  > '
    read -r ans || exit 0
    case "$ans" in
      "") break ;;
      q|Q) echo "Nothing changed."; exit 0 ;;
      a|A) for i in 0 1 2 3 4; do part_on $i; done; NOTE="" ;;
      n|N) for i in 0 1 2 3 4; do eval "${PART_VAR[i]}=0"; done ;;
      *) for k in $(echo "$ans" | tr ',' ' ' | grep -o '[0-9]'); do
           i=$((k - 1)); [ $i -ge 0 ] && [ $i -le 4 ] || continue
           if [ "${!PART_VAR[i]}" = 1 ]; then part_off $i; else part_on $i; fi
         done
         [ -n "$NOTE" ] && { echo "  $NOTE"; NOTE=""; }
         sel_errs | sed "s/^/  $E✘$N /" ;;
    esac
  done
  [ $((BUILD + RICE + SHELL_ + SESSION + APPS)) -eq 0 ] && { echo "Nothing chosen, nothing changed."; exit 0; }
  return 0
}

# arrow-key picker (like Claude Code): up/down or j/k move, Space toggles, Enter toggles a part or submits on Submit,
# a = all, n = none, Esc / q quits
menu() {
  case "${TERM:-dumb}" in dumb|"") menu_plain; return ;; esac
  local cur=0 key rest i v m msg="" mcol="" first=1 rows=9 cols
  cols=$(tput cols 2>/dev/null || echo 80)
  printf '\e[?25l'; trap 'printf "\e[?25h"' EXIT
  trap 'printf "\e[?25h\n"; echo "Nothing changed."; exit 130' INT
  # after a change: the first error of a chosen part (red), else what was turned on or off (yellow)
  status() {
    local e; e=$(sel_errs | head -1)
    if [ -n "$e" ]; then msg="✘ $e" mcol=$E; else msg=$NOTE mcol=$Y; fi
    NOTE=""
  }
  toggle() { if [ "${!PART_VAR[$1]}" = 1 ]; then part_off "$1"; else part_on "$1"; fi; status; }
  while :; do
    [ $first = 1 ] || printf '\e[%dA' $rows; first=0
    printf '\e[2K%sChoose what to install%s\n' "$B" "$N"
    for i in 0 1 2 3 4; do
      v=${!PART_VAR[i]} m=$(missing $i)
      local mark="[ ]" col="" ptr="  " name="${PART_NAME[i]}" desc="$D${PART_DESC[i]}$N"
      [ "$v" = 1 ] && mark="[x]" col=$G
      [ $i = $cur ] && ptr="${B}❯${N} "
      [ -n "$m" ] && desc="${E}missing: $m$N"
      if [ $i = $cur ]; then printf '\e[2K %s%s%s%s %s%-17s%s %s\n' "$ptr" "$col" "$mark" "$N" "$B" "$name" "$N" "$desc"
      else printf '\e[2K %s%s%s%s %-17s %s\n' "$ptr" "$col" "$mark" "$N" "$name" "$desc"; fi
    done
    printf '\e[2K\n'
    if [ $cur = 5 ]; then printf '\e[2K %s❯ %sSubmit%s\n' "$B" "$G" "$N"; else printf '\e[2K   Submit\n'; fi
    # one line only (the redraw moves up a fixed number of rows): cut to the terminal width
    if [ -n "$msg" ]; then printf '\e[2K %s%s%s\n' "$mcol" "${msg:0:$((cols - 2))}" "$N"; msg=""
    else printf '\e[2K %s↑/↓ move · Space toggle · Enter select · a all · n none · Esc quit%s\n' "$D" "$N"; fi
    IFS= read -rsn1 key || { printf '\e[?25h'; exit 0; }
    case "$key" in
      $'\e')
        rest=""; IFS= read -rsn2 -t 0.05 rest
        case "$rest" in
          '[A'|'OA') cur=$(( (cur + 5) % 6 )) ;;
          '[B'|'OB') cur=$(( (cur + 1) % 6 )) ;;
          '') printf '\e[?25h'; echo "Nothing changed."; exit 0 ;;
        esac ;;
      k) cur=$(( (cur + 5) % 6 )) ;;
      j|$'\t') cur=$(( (cur + 1) % 6 )) ;;
      ' ') [ $cur -lt 5 ] && toggle $cur ;;
      '') if [ $cur = 5 ]; then break; else toggle $cur; fi ;;
      a|A) for i in 0 1 2 3 4; do part_on $i; done; NOTE=""; status ;;
      n|N) for i in 0 1 2 3 4; do eval "${PART_VAR[i]}=0"; done ;;
      q|Q) printf '\e[?25h'; echo "Nothing changed."; exit 0 ;;
    esac
  done
  printf '\e[?25h'; trap - INT
  [ $((BUILD + RICE + SHELL_ + SESSION + APPS)) -eq 0 ] && { echo "Nothing chosen, nothing changed."; exit 0; }
  return 0
}

if [ "$ONLY" = 0 ]; then
  # default choice: leave out parts whose programs are missing (and what needs them); choosing one again is an error
  for i in 0 1 2 3 4; do
    [ "${!PART_VAR[i]}" = 1 ] && [ -n "$(missing $i)" ] && { warn "${PART_NAME[i]} left out: missing $(missing $i)"; part_off "$i"; }
  done
  flush_notes
fi
resolve
[ "$YES" = 0 ] && [ "$ONLY" = 0 ] && [ -t 0 ] && menu
fail_errs
if [ "$VERBOSE" = 1 ]; then
  printf '\n%sInstalling:%s' "$B" "$N"
  for i in 0 1 2 3 4; do [ "${!PART_VAR[i]}" = 1 ] && printf ' %s,' "${PART_NAME[i]}"; done | sed 's/,$//'
  echo
fi

SUDO=sudo; [ "$(id -u)" = 0 ] && SUDO=
rootwrite() { # dst  (content on stdin): write a root-owned file only when it differs; back up an old one
  local dst=$1 tmp; tmp=$(mktemp); cat > "$tmp"
  if [ -f "$dst" ] && cmp -s "$tmp" "$dst"; then ok "$dst is up to date"; rm -f "$tmp"; return; fi
  [ -f "$dst" ] && run $SUDO cp "$dst" "$dst.bak-$STAMP" && warn "backup: $dst.bak-$STAMP"
  run $SUDO install -Dm "${MODE:-644}" "$tmp" "$dst" && ok "wrote $dst"
  rm -f "$tmp"
}

# ---------- 1. glidewm ----------
if [ $BUILD = 1 ]; then
  head_ "1. glidewm"
  cd "$R" || exit 1
  if [ -f config.h ]; then ok "config.h exists: your config is kept (config.def.h is the default)"
  else run cp config.def.h config.h && ok "config.h made from config.def.h"; fi
  if [ "$DRY" = 1 ]; then run make
  else log=$(mktemp) || exit 1
       make >"$log" 2>&1 || { bad "make failed:"; tail -20 "$log"; rm -f "$log"; exit 1; }
       rm -f "$log"; ok "built ./glidewm"; fi
  if [ -e /usr/local/bin/glidewm ] && ! strings /usr/local/bin/glidewm 2>/dev/null | grep -q _RICE_CMD; then
    run $SUDO cp /usr/local/bin/glidewm "/usr/local/bin/glidewm.bak-$STAMP" && warn "backup: /usr/local/bin/glidewm.bak-$STAMP"
  fi
  if [ "$DRY" = 1 ]; then run $SUDO make install; else $SUDO make install >/dev/null && ok "installed /usr/local/bin/glidewm"; fi
  # the old name mwm: remove it, or link it to glidewm while a session still runs it (a restart re-runs /usr/local/bin/mwm)
  if [ -f /usr/local/bin/mwm ] && [ ! -L /usr/local/bin/mwm ] && strings /usr/local/bin/mwm 2>/dev/null | grep -q _RICE_CMD; then
    if pgrep -x mwm >/dev/null; then
      run $SUDO ln -sf glidewm /usr/local/bin/mwm && warn "/usr/local/bin/mwm is now a link to glidewm (mwm is running). After you log in with \"glidewm\": sudo rm /usr/local/bin/mwm"
    else run $SUDO rm -f /usr/local/bin/mwm && ok "removed the old /usr/local/bin/mwm"; fi
  fi
  [ -f /usr/local/share/man/man1/mwm.1 ] && run $SUDO rm -f /usr/local/share/man/man1/mwm.1
  if pgrep -x mwm >/dev/null; then warn "the running session is glidewm under its old name mwm: log out and pick \"glidewm\" to use the new build"
  elif pgrep -x glidewm >/dev/null; then warn "glidewm is running: Mod+Ctrl+Shift+q restarts it into the new build (windows and tags stay)"
  elif pgrep -x dwm >/dev/null && [ "$(readlink -f /proc/$(pgrep -x dwm | head -1)/exe 2>/dev/null)" = /usr/local/bin/dwm ]; then
    warn "the running session is the older glidewm under the name dwm: log out and pick \"glidewm\" to use the new build"
  fi
fi

# ---------- 2. the rice ----------
if [ $RICE = 1 ]; then
  head_ "2. Rice (helpers, library, configs)"
  if [ "$DRY" = 1 ]; then run "$R/rice/install.sh"
  elif [ "$VERBOSE" = 1 ]; then (cd "$R/rice" && ./install.sh) | grep -v "^$\|^Done\. Copy\|^Then build" | sed "s/^/  /"
  else (cd "$R/rice" && ./install.sh) >/dev/null; fi
  if [ -f "$HOME/.xprofile" ]; then ok "~/.xprofile kept"
  else run cp "$R/rice/config/xprofile.example" "$HOME/.xprofile" && warn "~/.xprofile made from the example: edit the monitors and wallpaper"; fi
  mkdir -p "$HOME/.config/rice" "$HOME/Pictures/wallpapers" 2>/dev/null
fi

# ---------- 3. the shell ----------
if [ $SHELL_ = 1 ]; then
  head_ "3. Shell (Quickshell)"
  S="$HOME/.local/share/dss"
  if [ ! -e "$S/src" ] && ! { [ "$DRY" = 1 ] && [ $RICE = 1 ]; }; then
    bad "$S/src is missing: the rice part links it (run without --no-rice)"
  else
    [ -f "$S/upstream.rev" ] || { run cp "$R/rice/shell/dss/UPSTREAM" "$S/upstream.rev" && ok "shell version recorded (updates start from it)"; }
    if [ "$DRY" = 1 ]; then run bash "$S/port.sh"
    else
      log=$(mktemp) || exit 1
      if bash "$S/port.sh" >"$log" 2>&1; then ok "built ~/.config/quickshell"
      else bad "port.sh failed:"; tail -15 "$log"; fi
      rm -f "$log"
    fi
    grep -q 'dss-start' "$HOME/.xprofile" 2>/dev/null && ok "~/.xprofile starts the shell" \
      || warn "add to ~/.xprofile, after picom:  (sleep 1; ~/.local/share/dss/dss-start) &"
  fi
fi

# ---------- 4a. login session ----------
if [ $SESSION = 1 ]; then
  head_ "4. Login session (SDDM, LightDM, GDM, startx)"
  MODE=755 rootwrite /usr/local/bin/glidewm-session <<'EOF'
#!/bin/sh
# glidewm session: what the display manager runs (it has already read ~/.xprofile) and what ~/.xinitrc can exec.
# A session D-Bus when there is none (startx), so notifications, the tray and portals work.
if [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ] && command -v dbus-run-session >/dev/null; then
  exec dbus-run-session /usr/local/bin/glidewm
fi
exec /usr/local/bin/glidewm
EOF
  rootwrite /usr/share/xsessions/glidewm.desktop <<'EOF'
[Desktop Entry]
Name=glidewm
Comment=glide window manager (dwm fork) with the rice shell
Exec=/usr/local/bin/glidewm-session
TryExec=/usr/local/bin/glidewm
Type=XSession
DesktopNames=glidewm
EOF
  for f in /usr/share/xsessions/mwm.desktop /usr/local/bin/mwm-session; do   # the old name, made by this script
    [ -f "$f" ] && grep -q 'mwm-session\|/usr/local/bin/mwm' "$f" && run $SUDO rm -f "$f" && ok "removed the old $f"
  done
  for dm in sddm lightdm gdm lxdm ly greetd; do command -v "$dm" >/dev/null && ok "$dm reads /usr/share/xsessions: pick \"glidewm\" at the login screen"; done
  if [ -f "$HOME/.xinitrc" ]; then
    if grep -q 'glidewm-session\|exec .*\bglidewm\b' "$HOME/.xinitrc"; then ok "~/.xinitrc starts glidewm"
    else warn "startx: ~/.xinitrc starts something else ($(grep -m1 -E '^[^#]*\bexec\b' "$HOME/.xinitrc" | sed 's/^ *//')): put  exec /usr/local/bin/glidewm-session  there instead"; fi
  else
    run sh -c "printf '%s\n' '#!/bin/sh' '[ -f \"\$HOME/.xprofile\" ] && . \"\$HOME/.xprofile\"' 'exec /usr/local/bin/glidewm-session' > \"\$HOME/.xinitrc\"" \
      && ok "~/.xinitrc made (startx starts glidewm)"
  fi
fi

# ---------- 4b. app entries ----------
if [ $APPS = 1 ]; then
  head_ "5. App menu entries"
  A="$HOME/.local/share/applications"; L="$HOME/.local/bin"
  mkdir -p "$A"
  # the glidewm logo as an icon (the Settings entry uses it)
  for sz in 16 32 48 64 128 256; do
    run install -Dm644 "$R/logo/icon-$sz.png" "$HOME/.local/share/icons/hicolor/${sz}x${sz}/apps/glidewm.png"
  done
  run install -Dm644 "$R/logo/glidewm-icon.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/glidewm.svg"
  # file|Name|Comment|Exec|Icon|Keywords|Categories
  ENTRIES="
glidewm-settings|glidewm Settings|Display, keyboard, gaps, network, shortcuts|$L/rice-settings|glidewm|settings;display;keyboard;network;shortcuts;|Settings;DesktopSettings;
glidewm-shell-settings|Shell Settings|Widgets, look, notifications, wallpapers, updates|$HOME/.local/share/dss/bin/rice-settings|preferences-desktop|shell;widgets;theme;update;|Settings;DesktopSettings;
glidewm-themes|Theme Switcher|Pick a wallpaper theme, colours follow|$L/theme-switch|preferences-desktop-theme|theme;wallpaper;colors;|Settings;DesktopSettings;
glidewm-wallpapers|Wallpapers|Wallpaper picker|$L/rice-wall|preferences-desktop-wallpaper|wallpaper;background;|Settings;DesktopSettings;
glidewm-screenshot|Screenshot|Region, annotate, OCR|$L/rice-shot|applets-screenshooter|screenshot;capture;ocr;|Utility;Graphics;
glidewm-recorder|Screen Recorder|Record the desktop, a monitor or a region|$L/rice-record|media-record|record;video;screencast;|Utility;AudioVideo;
glidewm-overview|Monitor Overview|Every monitor, drag windows between them|$L/rice-map|video-display|monitors;overview;|Utility;
glidewm-tools|Tools|Convert, download, colour picker, QR code|$L/rice-tools|applications-utilities|tools;convert;qr;color;|Utility;
glidewm-lock|Lock Screen|Lock now|$L/rice-lock|system-lock-screen|lock;|System;
"
  for f in "$A"/mwm-*.desktop; do [ -f "$f" ] && grep -q '^X-mwm=1' "$f" && run rm -f "$f"; done   # the old name
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
X-glidewm=1"
    # an entry of the same name that is not ours: a duplicate in the menu
    dup=$(grep -lx "Name=$name" "$A"/*.desktop /usr/share/applications/*.desktop 2>/dev/null | grep -v "^$dst$" | head -1)
    [ -n "$dup" ] && warn "\"$name\" is also in $dup: the menu shows it twice"
    if [ -f "$dst" ] && ! grep -q '^X-glidewm=1' "$dst"; then warn "$dst is yours (not made by this script): kept"; continue; fi
    if [ -f "$dst" ] && [ "$(cat "$dst")" = "$new" ]; then ok "$name"; continue; fi
    if [ "$DRY" = 1 ]; then run "write $dst"; else printf '%s\n' "$new" > "$dst" && ok "$name"; fi
  done <<< "$ENTRIES"
  command -v update-desktop-database >/dev/null && run update-desktop-database "$A" 2>/dev/null
fi

HEAD=""
echo
[ $WARNS -gt 0 ] && echo "Done, $WARNS notes above (${Y}!${N})." || echo "Done."
echo "Log out and pick \"glidewm\" at the login screen, or: startx. Keys: README.md. Updates: Shell Settings > Update Center."
