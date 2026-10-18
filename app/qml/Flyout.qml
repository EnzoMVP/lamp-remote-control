import QtQuick
import QtQuick.Layouts
import QtQuick.Templates as T

// The tray flyout. Context properties from Python:
//   bulb    - BulbController (state + actions)
//   flyout  - FlyoutController (geometry, notch, open/close, helpers)
Item {
    id: root

    width: flyout.windowWidth
    height: flyout.windowHeight

    readonly property bool online: bulb.ready
    readonly property bool configured: bulb.status !== "unconfigured"
    readonly property bool whiteMode: bulb.mode === "white"
    readonly property bool bottomNotch: flyout.notchSide === "bottom"

    focus: true
    Keys.onEscapePressed: flyout.close()

    // Clicks on the transparent margin around the panel close it, like clicking outside.
    MouseArea { anchors.fill: parent; onClicked: flyout.close() }

    // Retry countdown shown in the footer while offline.
    property int secondsLeft: 0
    Connections {
        target: bulb
        function onConnectionChanged() { root.secondsLeft = bulb.retryIn }
    }
    Timer {
        interval: 1000; repeat: true
        running: root.secondsLeft > 0 && flyout.shown
        onTriggered: root.secondsLeft = Math.max(0, root.secondsLeft - 1)
    }

    Item {
        id: panel
        x: flyout.marginSide
        y: flyout.panelY
        width: flyout.panelWidth
        height: flyout.panelHeight

        // Open/close animation: fade + short slide from the taskbar side.
        opacity: flyout.shown ? 1 : 0
        transform: Translate { y: flyout.shown ? 0 : (root.bottomNotch ? 14 : -14) }
        Behavior on opacity { NumberAnimation { duration: flyout.shown ? 200 : 110; easing.type: Easing.OutCubic } }

        PanelBackground {
            panelWidth: panel.width
            panelHeight: panel.height
            notchSide: flyout.notchSide
            notchX: flyout.notchX
        }
        MouseArea { anchors.fill: parent }   // swallow clicks inside the panel

        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: 20; anchors.rightMargin: 20
            anchors.topMargin: 18; anchors.bottomMargin: 16
            spacing: 0

            // ---- Header ------------------------------------------------------------
            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: 44
                spacing: 8

                Icon { name: "bulb"; size: 20; color: Theme.text2; stroke: 1.7 }
                Text {
                    text: bulb.deviceName
                    color: Theme.text2
                    font.family: Theme.fontFamily; font.pixelSize: 15
                    elide: Text.ElideRight
                    Layout.maximumWidth: 150
                }
                Text {
                    text: !root.configured ? "Não configurada"
                        : bulb.status === "offline" ? "Offline"
                        : bulb.status === "connecting" && !root.online ? "Conectando…"
                        : bulb.on ? "Ligada" : "Desligada"
                    color: bulb.status === "offline" ? Theme.warning : Theme.text
                    font.family: Theme.fontFamily; font.pixelSize: 15; font.weight: Font.DemiBold
                }
                Item { Layout.fillWidth: true }
                CircleButton {
                    objectName: "powerButton"
                    iconName: "power"
                    iconSize: 22
                    implicitWidth: 46; implicitHeight: 46
                    lit: bulb.on && root.online
                    glowColor: bulb.color
                    enabled: root.online
                    onClicked: bulb.toggle()
                    Accessible.name: bulb.on ? "Desligar" : "Ligar"
                }
            }

            // ---- Hero: 3D bulb -------------------------------------------------------
            Bulb3D {
                Layout.fillWidth: true
                Layout.preferredHeight: 150
                lightColor: bulb.color
                intensity: bulb.brightness / 100
                lit: bulb.on && root.online
                dark: Theme.dark
                animate: flyout.shown
            }

            // ---- Everything below is the control surface ---------------------------
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                ColumnLayout {
                    id: controls
                    anchors.fill: parent
                    spacing: 0
                    visible: root.configured
                    enabled: root.online
                    opacity: root.online ? 1 : 0.42
                    Behavior on opacity { NumberAnimation { duration: Theme.animMed } }

                    // Big number + mode card
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 64
                        spacing: 12

                        Row {
                            Layout.alignment: Qt.AlignVCenter
                            spacing: 4
                            Text {
                                id: bigNumber
                                text: bulb.hasState ? bulb.brightness : "–"
                                color: bulb.on ? Theme.text : Theme.text2
                                font.family: Theme.fontFamily; font.pixelSize: 54; font.weight: Font.DemiBold
                                font.features: { "tnum": 1 }
                            }
                            Text {
                                text: "%"
                                color: Theme.text2
                                font.family: Theme.fontFamily; font.pixelSize: 22
                                anchors.baseline: bigNumber.baseline
                            }
                        }
                        Item { Layout.fillWidth: true }
                        Rectangle {   // mode card, like the reference's "Eco Mode" pill
                            Layout.preferredHeight: 54
                            Layout.preferredWidth: modeRow.implicitWidth + 22
                            Layout.minimumWidth: 0
                            Layout.maximumWidth: 200
                            radius: Theme.radiusCard
                            color: Theme.surface
                            border.width: 1; border.color: Theme.surfaceBorder
                            visible: bulb.hasColour

                            RowLayout {
                                id: modeRow
                                anchors.fill: parent
                                anchors.leftMargin: 14; anchors.rightMargin: 8
                                spacing: 8
                                Icon {
                                    name: root.whiteMode ? "sun" : "palette"
                                    size: 20; stroke: 1.6
                                    color: Theme.text2
                                }
                                Text {
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    text: "Luz branca"
                                    color: Theme.text
                                    font.family: Theme.fontFamily; font.pixelSize: 15; font.weight: Font.Medium
                                }
                                ToggleSwitch {
                                    objectName: "modeSwitch"
                                    implicitWidth: 56; implicitHeight: 30
                                    checked: root.whiteMode
                                    onToggled: bulb.setMode(checked ? "white" : "colour")
                                    Accessible.name: "Luz branca"
                                }
                            }
                        }
                    }

                    Item { Layout.preferredHeight: 10 }

                    // Brightness: − [slider] +
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        CircleButton {
                            iconName: "minus"
                            autoRepeat: true
                            onClicked: bulb.setBrightness(bulb.brightness - 5)
                            Accessible.name: "Diminuir brilho"
                        }
                        BigSlider {
                            id: brightnessSlider
                            objectName: "brightnessSlider"
                            Layout.fillWidth: true
                            from: 1; to: 100; stepSize: 1
                            externalValue: bulb.brightness
                            onMoved: bulb.setBrightness(value)
                            onCommitted: bulb.commit()
                            Accessible.name: "Brilho"
                        }
                        CircleButton {
                            iconName: "plus"
                            autoRepeat: true
                            onClicked: bulb.setBrightness(bulb.brightness + 5)
                            Accessible.name: "Aumentar brilho"
                        }
                    }
                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 22
                        Text {
                            x: brightnessSlider.x + 4; y: 6
                            text: "1%"; color: Theme.text2
                            font.family: Theme.fontFamily; font.pixelSize: 12
                        }
                        Text {
                            x: brightnessSlider.x + brightnessSlider.width - width - 4; y: 6
                            text: "100%"; color: Theme.text2
                            font.family: Theme.fontFamily; font.pixelSize: 12
                        }
                    }

                    Item { Layout.preferredHeight: 10 }

                    // Mode-specific section: temperature (white) or hue + saturation (colour)
                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 104

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 8
                            visible: opacity > 0
                            opacity: root.whiteMode ? 1 : 0
                            Behavior on opacity { NumberAnimation { duration: Theme.animMed } }

                            RowLayout {
                                Layout.fillWidth: true
                                Icon { name: "thermo"; size: 16; color: Theme.text2; stroke: 1.6 }
                                Text {
                                    text: "Temperatura"; color: Theme.text2
                                    font.family: Theme.fontFamily; font.pixelSize: 13
                                }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: bulb.hasState ? bulb.kelvin.toLocaleString(Qt.locale("pt_BR"), "f", 0) + " K" : "–"
                                    color: Theme.text
                                    font.family: Theme.fontFamily; font.pixelSize: 13; font.weight: Font.DemiBold
                                }
                            }
                            BigSlider {
                                Layout.fillWidth: true
                                trackHeight: 40
                                enabled: bulb.hasTemperature
                                from: 0; to: 100; stepSize: 1
                                externalValue: bulb.temperature
                                onMoved: bulb.setTemperature(value)
                                onCommitted: bulb.commit()
                                Accessible.name: "Temperatura de cor"
                                trackGradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0.0; color: "#FFA45A" }
                                    GradientStop { position: 0.45; color: "#FFE2C2" }
                                    GradientStop { position: 1.0; color: "#D5E5FF" }
                                }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                Text { text: "Quente"; color: Theme.text2; font.family: Theme.fontFamily; font.pixelSize: 12 }
                                Item { Layout.fillWidth: true }
                                Text { text: "Frio"; color: Theme.text2; font.family: Theme.fontFamily; font.pixelSize: 12 }
                            }
                        }

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 8
                            visible: opacity > 0
                            opacity: root.whiteMode ? 0 : 1
                            Behavior on opacity { NumberAnimation { duration: Theme.animMed } }

                            RowLayout {
                                Layout.fillWidth: true
                                Icon { name: "palette"; size: 16; color: Theme.text2; stroke: 1.6 }
                                Text {
                                    text: "Cor"; color: Theme.text2
                                    font.family: Theme.fontFamily; font.pixelSize: 13
                                }
                                Item { Layout.fillWidth: true }
                                Rectangle {
                                    width: 12; height: 12; radius: 6
                                    color: bulb.color
                                    border.width: 1; border.color: Theme.surfaceBorder
                                }
                                Text {
                                    text: bulb.color.toString().toUpperCase()
                                    color: Theme.text
                                    font.family: Theme.fontFamily; font.pixelSize: 13; font.weight: Font.DemiBold
                                }
                            }
                            BigSlider {
                                Layout.fillWidth: true
                                trackHeight: 34
                                from: 0; to: 359; stepSize: 1
                                externalValue: bulb.hue
                                thumbTint: Qt.hsva(bulb.hue / 360, 1, 1, 1)
                                onMoved: bulb.setHue(value)
                                onCommitted: bulb.commit()
                                Accessible.name: "Matiz"
                                trackGradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0 / 6; color: "#FF3B3B" }
                                    GradientStop { position: 1 / 6; color: "#FFE53B" }
                                    GradientStop { position: 2 / 6; color: "#4BFF3B" }
                                    GradientStop { position: 3 / 6; color: "#3BFFF2" }
                                    GradientStop { position: 4 / 6; color: "#3B5BFF" }
                                    GradientStop { position: 5 / 6; color: "#F23BFF" }
                                    GradientStop { position: 6 / 6; color: "#FF3B3B" }
                                }
                            }
                            BigSlider {
                                Layout.fillWidth: true
                                trackHeight: 34
                                from: 0; to: 100; stepSize: 1
                                externalValue: bulb.saturation
                                onMoved: bulb.setSaturation(value)
                                onCommitted: bulb.commit()
                                Accessible.name: "Saturação"
                                trackGradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0; color: "#F4F1EC" }
                                    GradientStop { position: 1; color: Qt.hsva(bulb.hue / 360, 1, 1, 1) }
                                }
                            }
                        }
                    }

                    Item { Layout.preferredHeight: 14 }

                    // Scene tiles: rows of 4, like the reference's Mode/Fan/Sleep/Airflow row
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 4
                        rowSpacing: 8
                        columnSpacing: 8
                        Repeater {
                            model: bulb.presets
                            delegate: PresetTile {
                                required property var modelData
                                objectName: "preset_" + modelData.id
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                text: modelData.name
                                caption: modelData.caption
                                iconName: modelData.icon
                                active: bulb.activePreset === modelData.id
                                onClicked: bulb.applyPreset(modelData.id)
                                Accessible.name: "Cena " + modelData.name
                            }
                        }
                    }
                }

                // Not configured yet: explain where the config goes.
                Rectangle {
                    anchors.left: parent.left; anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    height: setupColumn.implicitHeight + 36
                    visible: !root.configured
                    radius: Theme.radiusCard
                    color: Theme.surface
                    border.width: 1; border.color: Theme.surfaceBorder

                    ColumnLayout {
                        id: setupColumn
                        anchors.fill: parent; anchors.margins: 18
                        spacing: 10
                        Text {
                            text: "Configure sua lâmpada"
                            color: Theme.text
                            font.family: Theme.fontFamily; font.pixelSize: 18; font.weight: Font.DemiBold
                        }
                        Text {
                            Layout.fillWidth: true
                            text: bulb.message + ".\n\nCrie o arquivo config.json nesta pasta com o id, ip, "
                                  + "local_key e version da lâmpada (veja o README), ou rode:\n"
                                  + "python -m app.import_devices"
                            wrapMode: Text.Wrap
                            color: Theme.text2
                            font.family: Theme.fontFamily; font.pixelSize: 13
                            lineHeight: 1.15
                        }
                        T.Button {
                            id: openFolder
                            Layout.topMargin: 4
                            implicitHeight: 38
                            implicitWidth: openRow.implicitWidth + 28
                            hoverEnabled: true
                            onClicked: flyout.openConfigFolder()
                            background: Rectangle {
                                radius: 12
                                color: openFolder.down ? Qt.darker(Theme.accent, 1.1) : Theme.accent
                                border.width: 1; border.color: Theme.accentEdge
                            }
                            contentItem: Item {
                                Row {
                                    id: openRow
                                    anchors.centerIn: parent
                                    spacing: 8
                                    Icon { name: "folder"; size: 18; color: Theme.iconOnAccent; anchors.verticalCenter: parent.verticalCenter }
                                    Text {
                                        text: "Abrir pasta de configuração"
                                        color: Theme.iconOnAccent
                                        font.family: Theme.fontFamily; font.pixelSize: 14; font.weight: Font.DemiBold
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ---- Footer -----------------------------------------------------------------
            Item { Layout.preferredHeight: 12 }
            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: 26
                spacing: 8

                Icon {
                    name: bulb.status === "offline" ? "alert" : "shield"
                    size: 16; stroke: 1.6
                    color: bulb.status === "offline" ? Theme.warning : Theme.text2
                }
                Text {
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    color: bulb.status === "offline" ? Theme.warning : Theme.text2
                    font.family: Theme.fontFamily; font.pixelSize: 13
                    text: {
                        if (!root.configured) return "Sem configuração"
                        if (bulb.status === "online") return "Conectado · " + bulb.ipAddress
                        if (bulb.status === "connecting") return "Conectando a " + bulb.ipAddress + "…"
                        return bulb.message + (root.secondsLeft > 0 ? " · nova tentativa em " + root.secondsLeft + " s" : "")
                    }
                }
                T.Button {
                    id: retryButton
                    visible: bulb.status === "offline"
                    implicitHeight: 26
                    implicitWidth: retryText.implicitWidth + 16
                    hoverEnabled: true
                    onClicked: bulb.retry()
                    background: Rectangle {
                        radius: 8
                        color: retryButton.hovered ? Theme.warningBg : "transparent"
                    }
                    contentItem: Text {
                        id: retryText
                        text: "Tentar agora"
                        color: Theme.warning
                        font.family: Theme.fontFamily; font.pixelSize: 13; font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
                T.Button {
                    id: settingsButton
                    implicitWidth: 30; implicitHeight: 30
                    hoverEnabled: true
                    onClicked: flyout.openConfigFolder()
                    Accessible.name: "Abrir pasta de configuração"
                    background: Rectangle {
                        radius: 8
                        color: settingsButton.hovered ? Theme.surfaceHover : "transparent"
                    }
                    contentItem: Item {
                        Icon { anchors.centerIn: parent; name: "settings"; size: 18; color: Theme.text2; stroke: 1.6 }
                    }
                }
            }
        }
    }
}
