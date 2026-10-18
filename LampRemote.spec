# PyInstaller spec — build with:  .venv\Scripts\pyinstaller LampRemote.spec --noconfirm
# Produces dist\LampRemote\LampRemote.exe (one-folder build: starts fast, unlike --onefile,
# which would unpack ~100 MB of Qt to a temp folder on every launch).

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ["LampRemote.pyw"],
    pathex=[],
    binaries=[],
    datas=[("app/qml", "app/qml")],
    hiddenimports=[
        "PySide6.QtQuick3D",
        "PySide6.QtQuickControls2",
        *collect_submodules("tinytuya"),
    ],
    excludes=[
        # Big Qt modules the app never uses.
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
        "PySide6.QtPdf", "PySide6.QtPdfQuick", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtGraphs", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
        "PySide6.QtLocation", "PySide6.QtPositioning", "PySide6.QtSql", "PySide6.QtTest",
        "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtBluetooth", "PySide6.QtNfc",
        "PySide6.QtSerialPort", "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSensors",
        "PySide6.QtTextToSpeech", "PySide6.QtVirtualKeyboard", "PySide6.Qt3DCore",
        "PySide6.Qt3DRender", "PySide6.Qt3DExtras", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
        "PySide6.Qt3DAnimation", "tkinter", "pytest",
    ],
    noarchive=False,
)

# PyInstaller collects every QML plugin, which drags in QtWebEngine (~200 MB) and friends.
# Drop everything this app doesn't load. Keep Quick3D + ShaderTools (runtime shader generation).
UNUSED = [
    "webengine", "webview", "webchannel", "qt6pdf", "qtpdf", "/pdf/", "opengl32sw",
    "quick3dphysics", "qt6graphs", "qtgraphs", "/qt3d", "qt63d", "multimedia", "spatialaudio",
    "location", "positioning", "virtualkeyboard", "charts", "datavisualization",
    "/material", "/universal", "/imagine", "fluentwinui3", "fusion", "stylekit",
    "texttospeech", "sensors", "scxml", "statemachine", "remoteobjects", "quicktest", "qt6test",
    "designer", "qt6help", "assetdownloader", "quickdialogs", "qt6quicktimeline", "/timeline",
    "quick3dxr", "qt6xr", "lottie", "qt6httpserver", "qt6serial", "bluetooth", "nfc",
]


def _used(entry):
    dest = entry[0].replace("\\", "/").lower()
    return not any(p in dest for p in UNUSED)


a.binaries = [b for b in a.binaries if _used(b)]
a.datas = [d for d in a.datas if _used(d)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LampRemote",
    console=False,           # tray app: no console window
    icon="assets/LampRemote.png",
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="LampRemote")
