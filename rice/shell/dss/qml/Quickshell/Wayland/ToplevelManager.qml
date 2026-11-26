pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
// X11 stand-in for Quickshell.Wayland's ToplevelManager, filled from dwm's _NET_CLIENT_LIST by rice-toplevels
// (JSON lines, xprop -spy: no polling). Each toplevel has appId (WM_CLASS class), title, activated, activate(), close().
// activate() is dwm IPC 9: dwm goes to the window's tag (with the tag slide) and focuses it. close() asks the window to
// close (WM_DELETE_WINDOW). The dock shows a dot under open apps from this; before it was an empty list.
Singleton {
    id: tm
    property var toplevels: ({ values: [] })
    property var activeToplevel: null
    property var byId: ({})
    // glidewm only (not in Quickshell): the tag under the pointer on dwm's bar, [tag, x, y, monitor, window ids ...]
    // ([] when none); TagPeek.qml shows what is on it
    property var hover: []

    property Component tlComp: Component {
        QtObject {
            property real wid: 0
            property string appId: ""
            property string title: ""
            property bool activated: false
            function activate() {
                Quickshell.execDetached(["xprop", "-root", "-f", "_RICE_CMD", "32c", "-set", "_RICE_CMD", "9, " + wid])
            }
            function close() {
                Quickshell.execDetached(["bash", "-c", "\"$HOME/.local/share/dss/bin/rice-toplevels\" close \"$1\"", "_", String(wid)])
            }
        }
    }

    property Process watch: Process {
        running: true
        command: ["bash", "-c", "exec \"$HOME/.local/share/dss/bin/rice-toplevels\""]
        stdout: SplitParser {
            onRead: function(line) {
                let d
                try { d = JSON.parse(line) } catch (e) { return }
                if (d.hover !== undefined) { tm.hover = d.hover; return }
                const old = tm.byId, now = {}, list = []
                let act = null
                for (let i = 0; i < d.wins.length; i++) {
                    const r = d.wins[i], k = String(r[0])
                    const t = old[k] || tm.tlComp.createObject(tm, { wid: r[0] })
                    if (t.appId !== r[1]) t.appId = r[1]
                    if (t.title !== r[2]) t.title = r[2]
                    const a = r[0] === d.active
                    if (t.activated !== a) t.activated = a
                    if (a) act = t
                    now[k] = t
                    list.push(t)
                }
                // a new list only when windows came, went or moved: focus and title changes go through the objects
                // (a new list rebuilds the whole dock row, twice on every tag switch: it made the slide stutter)
                const prev = tm.toplevels.values
                let same = prev.length === list.length
                for (let i = 0; same && i < list.length; i++) same = prev[i] === list[i]
                for (const k in old) if (!now[k]) old[k].destroy(1000)
                tm.byId = now
                if (!same) tm.toplevels = { values: list }
                if (tm.activeToplevel !== act) tm.activeToplevel = act
            }
        }
    }
    // the watcher ended (xprop or the X connection went away): start it again after a moment
    property Timer again: Timer { interval: 2000; running: !tm.watch.running; onTriggered: tm.watch.running = true }
}
