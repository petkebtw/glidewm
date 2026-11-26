import QtQuick
import Quickshell
import Quickshell.Wayland

// glidewm (patches/TagPeek.qml, copied by port.sh): hover a tag on dwm's bar and a card under it shows what is on that
// tag, the apps and their titles (or "Empty"). dwm writes the hovered tag to root _RICE_HOVER, rice-toplevels passes it
// on (ToplevelManager.hover = [tag, x, y, monitor, window ids ...]).
// The window stays mapped and never takes input (an empty mask): mapping it on every hover made NVIDIA's first frame
// eat the fade, like the dock's slide. It stays under 300 px wide, so dwm's shellcheck() never gives it the focus.
Variants {
    model: Quickshell.screens
    delegate: PanelWindow {
        id: pw
        required property var modelData
        screen: modelData
        readonly property var h: ToplevelManager.hover
        // the hover is on this screen (root coordinates); a function: onHChanged runs before a binding would update
        function onThis(v) {
            return v.length >= 4 && v[1] >= modelData.x && v[1] < modelData.x + modelData.width
                   && v[2] - 1 >= modelData.y && v[2] - 1 < modelData.y + modelData.height
        }
        property bool shown: false
        property int tag: 0
        property var wins: []
        property real cx: 0
        property real cy: 0
        // a short wait before it shows (sweeping over the bar does not flash cards), none between tags once it is out
        Timer { id: showT; interval: 140; onTriggered: pw.take(true) }
        Timer { id: hideT; interval: 90; onTriggered: pw.shown = false }
        function take(show) {
            if (!onThis(h)) return
            tag = h[0]; cx = h[1] - modelData.x; cy = h[2] - modelData.y
            const l = []
            for (let i = 4; i < h.length; i++) { const t = ToplevelManager.byId[String(h[i])]; if (t) l.push(t) }
            wins = l
            if (show) shown = true
        }
        onHChanged: {
            if (onThis(h)) { hideT.stop(); if (shown) take(false); else showT.restart() }
            else { showT.stop(); hideT.restart() }
        }

        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        anchors { top: true; left: true }
        margins.left: Math.max(4, Math.min(modelData.width - width - 4, Math.round(cx - width / 2)))
        margins.top: Math.round(cy + 6)
        implicitWidth: 260
        implicitHeight: card.height + 12
        mask: Region { }

        NPal { id: pal; theme: "tinted"; alpha: 0.94 }

        Rectangle {
            id: card
            width: parent.width
            height: col.implicitHeight + 20
            radius: Look.sq ? 0 : 16
            color: pal.surface
            border.width: 1; border.color: pal.line
            opacity: pw.shown ? 1 : 0
            y: pw.shown ? 0 : -6
            Behavior on opacity { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
            Behavior on y { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

            Column {
                id: col
                x: 12; y: 10
                width: parent.width - 24
                spacing: 6
                T { text: "Tag " + pw.tag; font.pixelSize: 12; font.bold: true; color: pal.primary }
                T { visible: pw.wins.length === 0; text: "Empty"; font.pixelSize: 12; color: pal.dim }
                Repeater {
                    model: pw.wins.slice(0, 6)
                    delegate: Row {
                        id: row
                        required property var modelData
                        readonly property var entry: DesktopEntries.heuristicLookup(modelData.appId)
                        spacing: 8
                        width: col.width
                        AppIcon {
                            size: 22
                            anchors.verticalCenter: parent.verticalCenter
                            name: row.entry ? (row.entry.icon || "") : Icons.appKey(row.modelData.appId, row.modelData.title)
                            keys: [row.modelData.appId, row.entry ? row.entry.id : "", row.entry ? row.entry.name : ""]
                            look: "original"
                            colors: pal
                            active: row.modelData.activated
                        }
                        T {
                            anchors.verticalCenter: parent.verticalCenter
                            width: row.width - 30
                            elide: Text.ElideRight
                            font.pixelSize: 12
                            color: row.modelData.activated ? pal.fg : pal.dim
                            text: row.modelData.title || (row.entry ? row.entry.name : row.modelData.appId)
                        }
                    }
                }
                T { visible: pw.wins.length > 6; text: "+" + (pw.wins.length - 6) + " more"; font.pixelSize: 11; color: pal.dim }
            }
        }
    }
}
