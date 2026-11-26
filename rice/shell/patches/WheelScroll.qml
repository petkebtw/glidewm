import QtQuick

// Scrolling a page with the mouse wheel or the touchpad. Put it inside the Flickable:
//   WheelScroll { id: wsc; flick: flick }                 (sideways: horizontal: true)
// and keep the page's own Behavior on contentY for jumps (search) with  enabled: ... && !wsc.active
// The mouse wheel glides to where the notches point; the touchpad moves the page with your fingers, as they go.
// glidewm (patches/WheelScroll.qml, copied by port.sh): the glide is a critically damped spring. The old glide covered
// a part of the way every frame, so each notch started at full speed and stopped short ("snip snap"); the spring
// speeds up and slows down softly, and a new notch only moves the goal, so the speed carries on without a kick.
// Website feel (2026-11-25): one notch is about 100 px at the default speed (was 216), the spring is softer, and the
// goal never runs more than 0.8 of a screen ahead of what you see, so a hard spin does not fling you somewhere unknown.
WheelHandler {
    id: ws
    property Flickable flick: null
    property bool horizontal: false
    property real k: Prefs.wheel * 100 / 216    // 100 px a notch at the default speed 1.8 (Home > Mouse wheel speed scales it)
    property real goal: 0
    property real vel: 0                          // px/s of the glide
    property real omega: 9.5                      // spring stiffness: most of the way in about 0.35 s, settled in 0.6 s
    property real lead: 0.8                       // how far the goal may run ahead of the glide, in screens
    property bool active: false                   // scrolled a moment ago (the page's Behavior stays out of the way)
    property var outer: null                      // a box inside a page: the page's WheelScroll, which scrolls on
                                                  // when the box is at its top or bottom
    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
    readonly property string prop: horizontal ? "contentX" : "contentY"
    function limit(v) {
        const max = horizontal ? Math.max(0, flick.contentWidth - flick.width) : Math.max(0, flick.contentHeight - flick.height)
        return Math.max(0, Math.min(max, v))
    }
    property real pos: 0                          // where the glide is (the Flickable may round what it is given)
    property FrameAnimation glide: FrameAnimation {
        onTriggered: {
            if (!ws.flick || ws.flick.dragging) { ws.vel = 0; stop(); return }
            let x = ws.pos, v = ws.vel
            let t = Math.min(0.05, frameTime)
            const w = ws.omega
            while (t > 0) {                       // small steps keep the spring stable on a slow frame
                const h = Math.min(t, 1 / 240)
                v += (w * w * (ws.goal - x) - 2 * w * v) * h
                x += v * h
                t -= h
            }
            const cx = ws.limit(x)
            if (cx !== x) { x = cx; v = 0 }       // never past the ends
            const done = Math.abs(ws.goal - x) < 0.3 && Math.abs(v) < 6
            if (done) x = ws.goal
            ws.flick[ws.prop] = x; ws.pos = x; ws.vel = v
            // done, or the Flickable kept it short of where we put it (its real end is nearer than limit() thinks):
            // stop, or the spring keeps pushing at the end forever
            if (done || Math.abs(ws.flick[ws.prop] - x) > 2) { ws.vel = 0; stop() }
        }
    }
    property Timer rest: Timer { interval: 260; onTriggered: ws.active = false }
    onWheel: function(e) { take(e) }
    function take(e) {
        if (!flick) return
        const cur = flick[prop]
        const touch = e.pixelDelta.x !== 0 || e.pixelDelta.y !== 0
        let to
        if (touch) {
            // a touchpad: follow the fingers
            const d = horizontal ? (e.pixelDelta.x !== 0 ? e.pixelDelta.x : e.pixelDelta.y) : e.pixelDelta.y
            to = limit(cur - d * 1.3 * Math.max(0.4, Prefs.scroll))
        } else {
            const a = horizontal ? (e.angleDelta.x !== 0 ? e.angleDelta.x : e.angleDelta.y) * 1.15 : e.angleDelta.y
            const base = glide.running ? goal : cur
            const span = (horizontal ? flick.width : flick.height) * lead
            const from = glide.running ? pos : cur
            to = limit(Math.max(from - span, Math.min(from + span, base - a * k)))
        }
        // a box inside a page at its end: the page scrolls instead
        if (outer && Math.abs(to - cur) < 0.5 && !glide.running) { outer.take(e); return }
        active = true
        rest.restart()
        goal = to
        if (touch) { glide.stop(); vel = 0; flick[prop] = goal; return }
        if (!glide.running) { vel = 0; pos = cur; glide.start() }
    }
}
