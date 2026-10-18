import QtQuick
import QtQuick.Effects
import QtQuick.Shapes

// Rounded panel with a soft notch pointing at the tray icon, plus drop shadow.
// Place it over the panel rect; it extends itself by `notchHeight` on the notch side.
Item {
    id: root

    property real panelWidth: 0
    property real panelHeight: 0
    property real radius: Theme.radiusPanel
    property string notchSide: "bottom"   // "bottom" | "top" | "none"
    property real notchX: panelWidth / 2  // notch tip, in panel coordinates
    property real notchHeight: 10
    property real notchHalfWidth: 17

    readonly property real topExtra: notchSide === "top" ? notchHeight : 0
    readonly property real bottomExtra: notchSide === "bottom" ? notchHeight : 0

    x: 0
    y: -topExtra
    width: panelWidth
    height: panelHeight + topExtra + bottomExtra

    function buildPath(w, h, r, side, nx, nh, nw, oy) {
        nx = Math.max(r + nw, Math.min(w - r - nw, nx))
        const Y = (v) => v + oy
        let p = `M ${r} ${Y(0)} `
        if (side === "top")
            p += `H ${nx - nw} C ${nx - nw * 0.53} ${Y(0)} ${nx - nw * 0.24} ${Y(-nh)} ${nx} ${Y(-nh)} `
               + `C ${nx + nw * 0.24} ${Y(-nh)} ${nx + nw * 0.53} ${Y(0)} ${nx + nw} ${Y(0)} `
        p += `H ${w - r} A ${r} ${r} 0 0 1 ${w} ${Y(r)} V ${Y(h - r)} A ${r} ${r} 0 0 1 ${w - r} ${Y(h)} `
        if (side === "bottom")
            p += `H ${nx + nw} C ${nx + nw * 0.53} ${Y(h)} ${nx + nw * 0.24} ${Y(h + nh)} ${nx} ${Y(h + nh)} `
               + `C ${nx - nw * 0.24} ${Y(h + nh)} ${nx - nw * 0.53} ${Y(h)} ${nx - nw} ${Y(h)} `
        p += `H ${r} A ${r} ${r} 0 0 1 0 ${Y(h - r)} V ${Y(r)} A ${r} ${r} 0 0 1 ${r} ${Y(0)} Z`
        return p
    }

    Shape {
        id: shape
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        visible: false   // drawn through the shadow effect below
        ShapePath {
            strokeColor: Theme.panelBorder
            strokeWidth: 1
            fillGradient: LinearGradient {
                x1: 0; y1: 0; x2: 0; y2: root.height
                GradientStop { position: 0; color: Theme.panelTop }
                GradientStop { position: 1; color: Theme.panelBottom }
            }
            PathSvg {
                path: root.buildPath(root.width, root.panelHeight, root.radius, root.notchSide,
                                     root.notchX, root.notchHeight, root.notchHalfWidth, root.topExtra)
            }
        }
    }

    MultiEffect {
        source: shape
        anchors.fill: shape
        autoPaddingEnabled: true
        shadowEnabled: true
        shadowColor: Theme.shadow
        shadowBlur: 1.0
        shadowVerticalOffset: 8
        blurMax: 48
    }
}
