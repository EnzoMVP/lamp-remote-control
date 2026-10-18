import QtQuick
import QtQuick.Shapes
import QtQuick3D
import QtQuick3D.Helpers
import LampRemote

// Hero: a real-time 3D bulb that glows in the bulb's current colour, with a halo behind it.
Item {
    id: root

    property color lightColor: "#ffd59a"
    property real intensity: 1.0        // brightness 0..1
    property bool lit: true
    property bool dark: true
    property bool animate: true         // pause the idle float when hidden

    // 0 = off, ~0.35 = dim, 1 = full. Brightness maps non-linearly so 1% still reads as "on".
    readonly property real targetGlow: lit ? 0.35 + 0.65 * Math.sqrt(intensity) : 0
    property real glow: targetGlow
    Behavior on glow { NumberAnimation { duration: 420; easing.type: Easing.OutCubic } }

    property color shownColor: lightColor
    Behavior on shownColor { ColorAnimation { duration: 260 } }

    // Mouse parallax (degrees), eased.
    property real tiltX: 0
    property real tiltY: 0
    Behavior on tiltX { NumberAnimation { duration: 500; easing.type: Easing.OutCubic } }
    Behavior on tiltY { NumberAnimation { duration: 500; easing.type: Easing.OutCubic } }

    property real floatPhase: 0
    NumberAnimation on floatPhase {
        from: 0; to: Math.PI * 2; duration: 6000
        loops: Animation.Infinite; running: root.animate && root.visible
    }

    readonly property color frostedColor: "#ece9e3"   // unlit milky glass

    function mixColor(a, b, t) {
        return Qt.rgba(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t, 1)
    }

    // --- Halo ----------------------------------------------------------------
    Shape {
        id: halo
        width: Math.min(root.width * 1.2, root.height * 1.6)
        height: width
        x: (root.width - width) / 2
        y: root.height * 0.36 - height / 2 + Math.sin(root.floatPhase) * 2
        opacity: root.glow
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeWidth: -1
            fillGradient: RadialGradient {
                centerX: halo.width / 2; centerY: halo.height / 2
                focalX: centerX; focalY: centerY
                centerRadius: halo.width / 2; focalRadius: 0
                GradientStop { position: 0.0; color: Qt.rgba(root.shownColor.r, root.shownColor.g, root.shownColor.b, root.dark ? 0.85 : 0.7) }
                GradientStop { position: 0.2; color: Qt.rgba(root.shownColor.r, root.shownColor.g, root.shownColor.b, root.dark ? 0.45 : 0.36) }
                GradientStop { position: 0.45; color: Qt.rgba(root.shownColor.r, root.shownColor.g, root.shownColor.b, root.dark ? 0.14 : 0.1) }
                GradientStop { position: 1.0; color: Qt.rgba(root.shownColor.r, root.shownColor.g, root.shownColor.b, 0) }
            }
            PathRectangle { x: 0; y: 0; width: halo.width; height: halo.height }
        }
    }

    // --- 3D scene ---------------------------------------------------------------
    View3D {
        id: view
        anchors.fill: parent
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.VeryHigh
            tonemapMode: SceneEnvironment.TonemapModeLinear
            lightProbe: Texture {
                textureData: ProceduralSkyTextureData {
                    skyTopColor: "#cfd6e0"; skyHorizonColor: "#f2ece2"
                    groundHorizonColor: "#8a847c"; groundBottomColor: "#2a2826"
                    sunColor: "#ffffff"; sunLatitude: 40; sunLongitude: 220
                }
            }
            probeExposure: 0.55
        }

        PerspectiveCamera {
            position: Qt.vector3d(0, 0, 300)
            fieldOfView: 30
            clipNear: 10
            clipFar: 1000
        }

        DirectionalLight {   // key light, upper left
            eulerRotation: Qt.vector3d(-35, -35, 0)
            brightness: 1.15
            color: "#fff8ee"
        }
        DirectionalLight {   // cool rim from behind right
            eulerRotation: Qt.vector3d(-10, 150, 0)
            brightness: 0.55
            color: "#dfe8ff"
        }
        DirectionalLight {   // bulb's own light spilling down onto the body
            eulerRotation: Qt.vector3d(-90, 0, 0)
            brightness: 0.9 * root.glow
            color: root.shownColor
        }

        Node {
            id: bulb
            y: Math.sin(root.floatPhase) * 2.2
            eulerRotation: Qt.vector3d(14 + root.tiltX, root.tiltY, -9 + Math.sin(root.floatPhase + 1) * 1.5)
            scale: Qt.vector3d(view.height / 138, view.height / 138, view.height / 138)

            Node {
                y: -58

                Model {
                    geometry: BulbPart { part: "glass" }
                    materials: PrincipledMaterial {
                        // Lit: the diffuse part fades out so the emissive colour stays saturated.
                        baseColor: root.mixColor(root.frostedColor,
                                                 Qt.rgba(root.shownColor.r * 0.12, root.shownColor.g * 0.12, root.shownColor.b * 0.12, 1),
                                                 Math.min(1, root.glow * 1.25))
                        emissiveFactor: Qt.vector3d(root.shownColor.r * root.glow * 1.1,
                                                    root.shownColor.g * root.glow * 1.1,
                                                    root.shownColor.b * root.glow * 1.1)
                        roughness: 0.6
                        metalness: 0
                        specularAmount: 0.25 * (1 - root.glow)
                    }
                }
                Model {
                    geometry: BulbPart { part: "body" }
                    materials: PrincipledMaterial {
                        baseColor: "#f4f2ee"
                        roughness: 0.42
                        metalness: 0
                        emissiveFactor: Qt.vector3d(root.shownColor.r * root.glow * 0.06,
                                                    root.shownColor.g * root.glow * 0.06,
                                                    root.shownColor.b * root.glow * 0.06)
                    }
                }
                Model {
                    geometry: BulbPart { part: "screw" }
                    materials: PrincipledMaterial {
                        baseColor: "#e4e4e0"
                        roughness: 0.3
                        metalness: 1
                        specularAmount: 1
                    }
                }
                Model {
                    geometry: BulbPart { part: "insulator" }
                    materials: PrincipledMaterial { baseColor: "#1d1d1f"; roughness: 0.3 }
                }
                Model {
                    geometry: BulbPart { part: "tip" }
                    materials: PrincipledMaterial { baseColor: "#c9a86a"; roughness: 0.3; metalness: 0.9 }
                }
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        onPositionChanged: (mouse) => {
            root.tiltY = (mouse.x / width - 0.5) * 30
            root.tiltX = (mouse.y / height - 0.5) * 16
        }
        onExited: { root.tiltX = 0; root.tiltY = 0 }
    }
}
