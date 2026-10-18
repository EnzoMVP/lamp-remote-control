pragma Singleton
import QtQuick

// Palette derived from the reference: warm near-black panel, warm-grey surfaces, cream accents.
// Follows the Windows app theme (Settings > Personalization > Colors) live.
QtObject {
    // `themeOverride` ("", "dark", "light") is a context property set from Python (for testing).
    readonly property bool dark: themeOverride === "dark" ? true
                               : themeOverride === "light" ? false
                               : Application.styleHints.colorScheme !== Qt.ColorScheme.Light

    readonly property string fontFamily: "Bahnschrift"   // Windows' built-in DIN

    readonly property color panelTop:     dark ? "#171614" : "#FCFBF8"
    readonly property color panelBottom:  dark ? "#0C0B0A" : "#F2EFE9"
    readonly property color panelBorder:  dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.09)
    readonly property color shadow:       dark ? Qt.rgba(0, 0, 0, 0.75) : Qt.rgba(0.2, 0.15, 0.1, 0.28)

    readonly property color surface:        dark ? "#1C1B18" : "#ECE8E1"
    readonly property color surfaceHover:   dark ? "#24221F" : "#E5E0D7"
    readonly property color surfacePressed: dark ? "#2B2925" : "#DCD6CC"
    readonly property color surfaceBorder:  dark ? Qt.rgba(1, 1, 1, 0.045) : Qt.rgba(0, 0, 0, 0.05)
    readonly property color surfaceActive:  dark ? "#2A2824" : "#E2DACB"
    readonly property color activeBorder:   dark ? "#6B6255" : "#A99C86"

    readonly property color text:      dark ? "#F3EFE8" : "#1C1A17"
    readonly property color text2:     dark ? "#9C968C" : "#6C665D"
    readonly property color text3:     dark ? "#6A655D" : "#9C968C"

    readonly property color accent:     dark ? "#ECE5D6" : "#FFFFFF"   // thumbs, knobs
    readonly property color accentEdge: dark ? Qt.rgba(0, 0, 0, 0.25) : Qt.rgba(0, 0, 0, 0.14)
    readonly property color iconOnAccent: dark ? "#1A1815" : "#1C1A17"

    readonly property color track:       dark ? "#090808" : "#E4DFD6"
    readonly property color trackBorder: dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(0, 0, 0, 0.05)
    readonly property color fillStart:   dark ? Qt.rgba(0.93, 0.90, 0.84, 0.10) : Qt.rgba(0.42, 0.37, 0.30, 0.10)
    readonly property color fillEnd:     dark ? Qt.rgba(0.93, 0.90, 0.84, 0.42) : Qt.rgba(0.42, 0.37, 0.30, 0.38)

    readonly property color toggleOn:   dark ? "#C9BFAE" : "#3A3530"
    readonly property color toggleOff:  dark ? "#2D2B27" : "#D6D0C6"

    readonly property color warning:     dark ? "#F0A57E" : "#B4532A"
    readonly property color warningBg:   dark ? Qt.rgba(0.94, 0.65, 0.49, 0.10) : Qt.rgba(0.70, 0.32, 0.16, 0.08)
    readonly property color success:     dark ? "#9C968C" : "#6C665D"

    readonly property int radiusPanel: 26
    readonly property int radiusCard: 16
    readonly property int animFast: 140
    readonly property int animMed: 220
}
