#!/bin/sh
# Quickshell for X11 only (no Wayland, no Hyprland). Needs root. Pulls 2 packages: dev-cpp/cli11 + gui-apps/quickshell (guru).
set -e
echo 'gui-apps/quickshell ~amd64' | sudo tee /etc/portage/package.accept_keywords/quickshell
echo 'gui-apps/quickshell X jemalloc mpris notifications pam pipewire policykit sockets tray upower -bluetooth -crash-handler -greetd -hyprland -i3 -layer-shell -networkmanager -screencopy -session-lock -toplevel-management -wayland' | sudo tee /etc/portage/package.use/quickshell
sudo emerge -av gui-apps/quickshell
