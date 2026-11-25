import Quickshell
import Quickshell.Io
import QtQuick

// Settings > Desktop > glidewm (port.sh puts it in place of the Hyprland / niri page): glidewm's own settings live in the
// glidewm settings app (~/.local/bin/rice-settings PAGE) and the tools in ~/.local/bin; this page opens them.
Item {
    id: page
    property var ctl
    property string ver: ""
    Process {
        command: ["bash", "-c", "\"$HOME/.local/share/dss/bin/rice-wm\" version"]
        running: true
        stdout: StdioCollector { onStreamFinished: page.ver = text.trim() }
    }
    function run(cmd, args, msg) {
        Quickshell.execDetached(["bash", "-c", "exec \"$HOME/.local/bin/$1\" \"${@:2}\"", "_", cmd].concat(args || []))
        page.ctl.status = msg
    }
    readonly property var apps: [
        { l: "Display", d: "Monitors, resolution, refresh rate, rotation, brightness, night light", g: "\uf108", p: "display" },
        { l: "Keyboard & mouse", d: "Layout, key repeat, mouse speed and acceleration", g: "\uf11c", p: "input" },
        { l: "Windows & bar", d: "Gaps, bar padding, tiling", g: "\uf2d0", p: "windows" },
        { l: "Shortcuts", d: "Every glidewm key (writes ~/.config/rice/binds.conf)", g: "\uf084", p: "keys" },
        { l: "Network", d: "Interfaces, DNS, MTU, DHCP renew, tests", g: "\uf1eb", p: "net" },
        { l: "Sound devices", d: "Output and input devices, the audio fix", g: "\uf028", p: "sound" }
    ]
    readonly property var tools: [
        { l: "Screenshot", d: "Frozen screen, region, annotate, OCR (Mod+Shift+S)", g: "\uf030", c: "rice-shot", a: [] },
        { l: "Screen recorder", d: "Desktop, one monitor or a region, with sound (Mod+Shift+R)", g: "\uf03d", c: "rice-record", a: [] },
        { l: "Lock screen", d: "Lock now (Mod+Shift+L)", g: "\uf023", c: "rice-lock", a: [] },
        { l: "Theme switcher", d: "Arrows preview a wallpaper theme, Enter keeps it (Mod+Shift+T)", g: "\uf1fc", c: "theme-switch", a: [] },
        { l: "Monitor overview", d: "Every monitor zoomable, drag windows between them (Mod+Z)", g: "\uf00a", c: "rice-map", a: [] },
        { l: "Check the theme", d: "Repair colours, blur and the terminal if they do not match the wallpaper", g: "\uf0ad", c: "rice-themecheck", a: ["--fix"] }
    ]

    PageScroll {
        anchors.fill: parent

        SectionTitle { text: "glidewm"; sub: (page.ver || "glidewm") + I18n.t("  ·  the window manager. Its own settings open in the glidewm settings app.") }
        Repeater {
            model: page.apps
            SettingRow {
                required property var modelData
                label: I18n.t(modelData.l); desc: I18n.t(modelData.d); icon: modelData.g; reserved: 110
                Btn { anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
                      text: I18n.t("Open"); variant: "tonal"
                      onClicked: page.run("rice-settings", [modelData.p], I18n.t("Opening ") + I18n.t(modelData.l)) }
            }
        }

        SectionTitle { text: I18n.t("Tools"); sub: I18n.t("The glidewm tools. The control centre, game bar and island use the same ones.") }
        Repeater {
            model: page.tools
            SettingRow {
                required property var modelData
                label: I18n.t(modelData.l); desc: I18n.t(modelData.d); icon: modelData.g; reserved: 110
                Btn { anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
                      text: I18n.t("Start"); variant: "tonal"
                      onClicked: page.run(modelData.c, modelData.a, I18n.t(modelData.l)) }
            }
        }
    }
}
