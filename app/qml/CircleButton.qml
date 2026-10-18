import QtQuick
import QtQuick.Templates as T

// Round icon button (power, − / +), as in the reference.
T.Button {
    id: control

    property string iconName: ""
    property real iconSize: 20
    property bool lit: false   // e.g. power button while the bulb is on
    property color glowColor: "transparent" // soft ring in the bulb colour

    implicitWidth: 44
    implicitHeight: 44
    focusPolicy: Qt.TabFocus
    hoverEnabled: true

    background: Item {
        Rectangle {   // colour ring, only when highlighted
            anchors.centerIn: parent
            width: parent.width + 6; height: width; radius: width / 2
            color: "transparent"
            border.width: 1.5
            border.color: Qt.rgba(control.glowColor.r, control.glowColor.g, control.glowColor.b, 0.55)
            opacity: control.lit ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.animMed } }
        }
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: control.lit ? Theme.accent
                 : control.down ? Theme.surfacePressed
                 : control.hovered ? Theme.surfaceHover : Theme.surface
            border.width: 1
            border.color: control.lit ? Theme.accentEdge : Theme.surfaceBorder
            Behavior on color { ColorAnimation { duration: Theme.animFast } }
        }
        Rectangle {   // keyboard focus ring
            anchors.fill: parent; anchors.margins: -3
            radius: width / 2
            color: "transparent"
            border.width: 2; border.color: Theme.text
            visible: control.visualFocus
        }
    }

    contentItem: Item {
        Icon {
            anchors.centerIn: parent
            name: control.iconName
            size: control.iconSize
            color: control.lit ? Theme.iconOnAccent : Theme.text
            opacity: control.enabled ? 1 : 0.4
        }
    }

    scale: down ? 0.94 : 1
    Behavior on scale { NumberAnimation { duration: 90 } }
}
