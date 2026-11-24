pragma Singleton
import Quickshell
import Quickshell.Io
import QtQuick

// dwm backend (X11 port of DarkShadow's Shell). Same API as the Hyprland/niri Wm: focusedId, occupied(n), maxWs(min),
// focusedWindow, goWs(n). State comes from dwm's _RICE_TAGS root property through rice-wm-watch (JSON lines).
Singleton {
    id: wm
    readonly property bool niri: false
    readonly property bool hypr: true          // the shell treats "not niri" as Hyprland: keep that path, data is ours
    readonly property string name: "dwm"
    property int tick: 0
    property int titleTick: 0
    property int view: 1
    property int occ: 0
    property int urg: 0
    property string title: ""
    property string cls: ""

    Process {
        id: watch
        running: true
        command: ["rice-wm-watch"]
        stdout: SplitParser {
            onRead: function(line) {
                let o
                try { o = JSON.parse(line) } catch (e) { return }
                const tags = o.view !== wm.view || o.occ !== wm.occ || o.urg !== wm.urg
                wm.view = o.view; wm.occ = o.occ; wm.urg = o.urg
                if (o.title !== wm.title || o["class"] !== wm.cls) { wm.title = o.title; wm.cls = o["class"]; wm.titleTick++ }
                if (tags) wm.tick++
            }
        }
        onExited: restart.restart()
    }
    Timer { id: restart; interval: 1500; onTriggered: watch.running = true }

    readonly property string focusedOutput: ""
    readonly property int focusedId: {
        tick
        for (let i = 1; i <= 9; i++) if ((view >> (i - 1)) & 1) return i
        return 1
    }
    function occupied(n) { return ((occ >> (n - 1)) & 1) === 1 }
    function maxWs(min) {
        let m = min || 1
        for (let i = 9; i > m; i--) if (occupied(i) || ((view >> (i - 1)) & 1)) { m = i; break }
        return m
    }
    readonly property var focusedWindow: {
        tick; titleTick
        return title !== "" || cls !== "" ? { title: title, appId: cls, floating: false } : null
    }
    readonly property string activeTitle: focusedWindow ? focusedWindow.title : ""
    readonly property string activeApp: focusedWindow ? focusedWindow.appId : ""

    property real lastGo: 0
    function goWs(n) {
        const s = String(n)
        if (s.indexOf("e") === 0) {
            const now = Date.now()
            if (now - lastGo < 220) return
            lastGo = now
        }
        Quickshell.execDetached(["ws-go", s])
    }
}
