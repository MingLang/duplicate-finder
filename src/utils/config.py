import os
import sys
from PySide6.QtCore import QSettings


def get_settings() -> QSettings:
    """
    Return a QSettings instance backed by an INI file next to the executable.
    This makes the app fully portable — no registry writes.
    """
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle
        base = os.path.dirname(sys.executable)
    else:
        # Running from source
        base = os.path.dirname(os.path.abspath(__file__))
        base = os.path.join(base, "..", "..")
    base = os.path.normpath(base)
    ini_path = os.path.join(base, "duplicate_finder_config.ini")
    return QSettings(ini_path, QSettings.Format.IniFormat)
