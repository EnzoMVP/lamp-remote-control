import QtQuick
import QtQuick.Shapes

// Stroke icon drawn from SVG path data on a 24x24 grid, so it can take any colour.
Shape {
    id: root

    property string name: ""
    property color color: "white"
    property real size: 20
    property real stroke: 1.8

    width: size
    height: size
    preferredRendererType: Shape.CurveRenderer

    readonly property var paths: ({
        power: ["M12 3v8", "M7.05 6.05a7.5 7.5 0 1 0 9.9 0"],
        bulb: ["M9 18h6", "M10 21h4", "M12 3a6 6 0 0 0-3.6 10.8c.7.5 1.1 1.3 1.1 2.2h5c0-.9.4-1.7 1.1-2.2A6 6 0 0 0 12 3z"],
        minus: ["M6 12h12"],
        plus: ["M12 6v12", "M6 12h12"],
        sun: ["M12 8.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7z", "M12 2.5v2", "M12 19.5v2", "M4.6 4.6l1.4 1.4", "M18 18l1.4 1.4", "M2.5 12h2", "M19.5 12h2", "M4.6 19.4L6 18", "M18 6l1.4-1.4"],
        palette: ["M12 3a9 9 0 0 0 0 18c1.2 0 1.8-.8 1.8-1.7 0-.5-.2-.9-.5-1.2-.3-.3-.5-.7-.5-1.2 0-.9.8-1.7 1.7-1.7H16a5 5 0 0 0 5-5c0-4-4-7.2-9-7.2z",
                  "M7.5 11.5h.01", "M9.5 7.5h.01", "M14.5 7.5h.01"],
        book: ["M4 5.5A2.5 2.5 0 0 1 6.5 3H12v16H6.5A2.5 2.5 0 0 0 4 21.5z", "M20 5.5A2.5 2.5 0 0 0 17.5 3H12v16h5.5a2.5 2.5 0 0 1 2.5 2.5z"],
        sofa: ["M4 11V8a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v3", "M2.5 13.5a2 2 0 0 1 4 0V15h11v-1.5a2 2 0 0 1 4 0V18H2.5z", "M5 18v2", "M19 18v2"],
        target: ["M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18z", "M12 7.5a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9z", "M12 11.2a.8.8 0 1 1 0 1.6.8.8 0 0 1 0-1.6z"],
        moon: ["M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"],
        shield: ["M12 3l7 3v5.5c0 4.4-3 8-7 9.5-4-1.5-7-5.1-7-9.5V6z", "M9 12l2.2 2.2L15.5 10"],
        alert: ["M12 3.5l9.5 16.5h-19z", "M12 10v4", "M12 17.2h.01"],
        settings: ["M4 7h9", "M17 7h3", "M15 5v4", "M4 17h3", "M11 17h9", "M9 15v4"],
        refresh: ["M20 12a8 8 0 1 1-2.3-5.6", "M20 4v5h-5"],
        thermo: ["M12 14.5V5.5a2 2 0 0 0-4 0v9a3.5 3.5 0 1 0 4 0z"],
        folder: ["M3.5 6.5a2 2 0 0 1 2-2H10l2 2.5h6.5a2 2 0 0 1 2 2v8.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"]
    })

    ShapePath {
        strokeColor: root.color
        strokeWidth: root.stroke * 24 / root.size   // stroke is scaled along with the path
        fillColor: "transparent"
        capStyle: ShapePath.RoundCap
        joinStyle: ShapePath.RoundJoin
        scale: Qt.size(root.size / 24, root.size / 24)
        PathSvg { path: (root.paths[root.name] || []).join(" ") }
    }
}
