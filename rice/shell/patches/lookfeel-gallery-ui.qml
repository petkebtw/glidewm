        // ---------- fastfetch logo gallery ----------
        SectionTitle { text: I18n.t("Logo gallery"); sub: I18n.t("Pick the logo fastfetch shows, as a picture or as ASCII art.") }
        SegRow {
            label: I18n.t("Show it as")
            desc: I18n.t("Picture needs a terminal that shows images (Kitty protocol). ASCII works everywhere and takes your theme color")
            options: [{ label: I18n.t("Picture"), value: "image" }, { label: "ASCII", value: "ascii" }]
            current: page.gal.mode || "image"
            onChosen: function(v) { page.galRun(["mode", v]) }
        }
        SegRow {
            label: I18n.t("Info layout")
            desc: I18n.t("Classic: user@host, a rule, then bold OS / Kernel / Uptime lines without icons")
            options: [{ label: I18n.t("Mine"), value: "own" }, { label: I18n.t("Classic"), value: "classic" }]
            current: page.gal.layout || "own"
            onChosen: function(v) { page.galRun(["layout", v]) }
        }
        Flow {
            width: parent.width
            spacing: 10
            Repeater {
                model: page.gal.items || []
                delegate: Rectangle {
                    id: gcard
                    readonly property bool sel: page.gal.logo === modelData.id
                    readonly property bool pic: modelData.image !== "" && (page.gal.mode !== "ascii" || modelData.ascii === "")
                    width: 168; height: 196
                    radius: M3.sq ? 0 : M3.rL
                    color: sel ? M3.primaryContainer : (gm.containsMouse ? M3.surfaceHigh : M3.surfaceC)
                    border.width: sel ? 2 : 0; border.color: M3.primary
                    Item {
                        x: 10; y: 10; width: parent.width - 20; height: 140; clip: true
                        Image { anchors.fill: parent; visible: gcard.pic; source: gcard.pic ? "file://" + modelData.image : ""
                            fillMode: Image.PreserveAspectFit; sourceSize.width: 280; sourceSize.height: 280; smooth: true }
                        Text { anchors.centerIn: parent; visible: !gcard.pic; text: modelData.art !== "" ? modelData.art : modelData.name
                            font.family: "monospace"; font.pixelSize: 6; lineHeight: 0.95; color: M3.primary; textFormat: Text.PlainText }
                    }
                    T { x: 12; y: 154; width: parent.width - 24; text: modelData.name; font.pixelSize: 14; elide: Text.ElideRight }
                    T { x: 12; y: 174; width: parent.width - 24; text: modelData.desc; font.pixelSize: 10; color: M3.inkDim; elide: Text.ElideRight }
                    MouseArea { id: gm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: page.galRun(["set", modelData.id]) }
                }
            }
        }
        Btn {
            visible: page.gal.logo !== ""
            text: I18n.t("Back to my own logo"); sym: "restart_alt"; icon: ""; variant: "tonal"
            onClicked: page.galRun(["reset"])
        }

