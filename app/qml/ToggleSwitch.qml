import QtQuick
import QtQuick.Templates as T

// Pill switch, as in the reference's "Eco Mode" card.
T.Switch {
    id: control

    implicitWidth: 64
    implicitHeight: 34
    focusPolicy: Qt.TabFocus

    indicator: Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: control.checked ? Theme.toggleOn : Theme.toggleOff
        border.width: 1
        border.color: Theme.surfaceBorder
        Behavior on color { ColorAnimation { duration: Theme.animMed } }

        Rectangle {
            width: parent.height - 6
            height: width
            radius: width / 2
            y: 3
            x: control.checked ? parent.width - width - 3 : 3
            color: control.checked ? (Theme.dark ? "#FFFFFF" : "#FFFFFF") : Theme.accent
            Behavior on x { NumberAnimation { duration: Theme.animMed; easing.type: Easing.OutCubic } }
        }
        Rectangle {
            anchors.fill: parent; anchors.margins: -3
            radius: height / 2
            color: "transparent"
            border.width: 2; border.color: Theme.text
            visible: control.visualFocus
        }
    }
    contentItem: Item {}
}
