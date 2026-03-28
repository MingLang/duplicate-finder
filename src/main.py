import sys
import os

# Add src directory to path so imports work both in dev and PyInstaller
if getattr(sys, "frozen", False):
    # PyInstaller bundle: sys._MEIPASS is the temp extraction dir
    src_dir = os.path.dirname(sys.executable)
    bundle_dir = sys._MEIPASS
    sys.path.insert(0, bundle_dir)
else:
    src_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, src_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from gui.main_window import MainWindow, _resource_path


def main():
    # Enable high-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Duplicate File Finder")
    app.setApplicationVersion("1.0")

    # App icon
    icon_path = _resource_path("resources/app.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
