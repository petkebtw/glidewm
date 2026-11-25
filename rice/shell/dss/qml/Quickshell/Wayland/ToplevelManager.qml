pragma Singleton
import QtQuick
// X11 stand-in for Quickshell.Wayland's ToplevelManager: no toplevel list here (the dwm port fills Wm.qml instead)
QtObject {
    property var toplevels: ({ values: [] })
    property var activeToplevel: null
}
