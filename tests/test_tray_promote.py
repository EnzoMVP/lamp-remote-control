from app.tray_promote import _same_exe


def test_same_exe_plain_path_case_insensitive():
    assert _same_exe(r"C:\Apps\LampRemote\LampRemote.exe", r"c:\apps\lampremote\LAMPREMOTE.EXE")


def test_same_exe_known_folder_guid_path():
    reg = r"{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}\Programs\LampRemote\LampRemote.exe"
    assert _same_exe(reg, r"C:\Users\x\AppData\Local\Programs\LampRemote\LampRemote.exe")


def test_different_exe():
    assert not _same_exe(r"C:\Other\LampRemote.exe", r"C:\Apps\LampRemote\LampRemote.exe")
