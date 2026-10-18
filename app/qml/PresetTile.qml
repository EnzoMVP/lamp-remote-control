import QtQuick
import QtQuick.Templates as T

// Scene tile: icon + small caption + name, like the reference's Mode/Fan/Sleep/Airflow tiles.
T.Button {
    id: control

    property string iconName: ""
    property string caption: ""
    property bool active: false

    implicitHeight: 84
    hoverEnabled: true
    focusPolicy: Qt.TabFocus

    background: Rectangle {
        radius: Theme.radiusCard
        color: control.active ? Theme.surfaceActive
             : control.down ? Theme.surfacePressed
             : control.hovered ? Theme.surfaceHover : Theme.surface
        border.width: 1
        border.color: control.visualFocus ? Theme.text
                    : control.active ? Theme.activeBorder : Theme.surfaceBorder
        Behavior on color { ColorAnimation { duration: Theme.animFast } }
    }

    contentItem: Item {
        Icon {
            x: 2; y: 2
            name: control.iconName
            size: 22
            stroke: 1.6
            color: Theme.text
        }
        Rectangle {   // "active" dot, like the reference's Sleep tile
            anchors.right: parent.right; anchors.top: parent.top
            anchors.margins: 6
            width: 6; height: 6; radius: 3
            color: Theme.text
            opacity: control.active ? 0.9 : 0.18
        }
        Column {
            anchors.left: parent.left; anchors.bottom: parent.bottom
            anchors.leftMargin: 2
            spacing: 1
            Text {
                text: control.caption
                color: Theme.text2
                font.family: Theme.fontFamily
                font.pixelSize: 11
            }
            Text {
                text: control.text
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 15
                font.weight: Font.DemiBold
            }
        }
    }
    padding: 12
    scale: down ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: 90 } }
}
