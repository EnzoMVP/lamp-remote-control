import QtQuick
import QtQuick.Effects
import QtQuick.Templates as T

// Thick slider with a cream thumb, as in the reference.
// Progress mode (default): the filled part fades from dim to bright up to the thumb.
// Gradient mode: set `trackGradient` to paint the whole track (temperature, hue...).
T.Slider {
    id: control

    property real externalValue: 0          // value from the bulb; ignored while dragging
    property Gradient trackGradient: null
    property real trackHeight: 46
    property color thumbTint: "transparent" // small colour dot inside the thumb
    signal committed()                       // drag released

    implicitWidth: 240
    implicitHeight: trackHeight
    focusPolicy: Qt.TabFocus
    wheelEnabled: true
    live: true

    Binding {
        control.value: control.externalValue
        when: !control.pressed
        restoreMode: Binding.RestoreNone
    }
    onPressedChanged: if (!pressed) committed()

    background: Rectangle {
        id: track
        x: control.leftPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        width: control.availableWidth
        height: control.trackHeight
        radius: Math.min(14, height / 2)
        color: control.trackGradient ? "transparent" : Theme.track
        gradient: control.trackGradient
        opacity: control.trackGradient && Theme.dark ? 0.88 : 1
        border.width: 1
        border.color: Theme.trackBorder

        Rectangle {   // progress fill
            visible: !control.trackGradient
            x: 0; y: 0
            height: parent.height
            width: thumb.x - control.leftPadding + thumb.width
            radius: parent.radius
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Theme.fillStart }
                GradientStop { position: 1; color: Theme.fillEnd }
            }
        }
    }

    handle: Item {
        id: thumb
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        y: control.topPadding + (control.availableHeight - height) / 2
        width: Math.round(control.trackHeight * 0.7)
        height: control.trackHeight - 6

        RectangularShadow {
            anchors.fill: knob
            radius: knob.radius
            blur: 10
            offset.y: 2
            color: Qt.rgba(0, 0, 0, Theme.dark ? 0.55 : 0.22)
        }
        Rectangle {
            id: knob
            anchors.fill: parent
            radius: Math.min(10, height / 3)
            color: Theme.accent
            border.width: 1
            border.color: Theme.accentEdge
            scale: control.pressed ? 0.94 : 1
            Behavior on scale { NumberAnimation { duration: 100 } }

            Rectangle {   // colour dot for gradient tracks
                anchors.centerIn: parent
                width: 12; height: 12; radius: 6
                visible: control.thumbTint.a > 0
                color: control.thumbTint
                border.width: 1
                border.color: Qt.rgba(0, 0, 0, 0.15)
            }
        }
        Rectangle {   // keyboard focus ring
            anchors.fill: parent; anchors.margins: -3
            radius: knob.radius + 3
            color: "transparent"
            border.width: 2; border.color: Theme.text
            visible: control.visualFocus
        }
    }
}
