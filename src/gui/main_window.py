import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter, QStatusBar,
    QProgressBar, QLabel, QMessageBox, QApplication, QTabWidget,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QAction

from gui.scan_panel import ScanPanel
from gui.results_table import ResultsTable
from gui.folder_view import FolderView
from gui.progress_dialog import ProgressDialog
from workers.scan_worker import ScanWorker, ScanConfig
from utils.file_ops import delete_files_to_trash
from utils.format import human_size
from utils.config import get_settings
from core.folder_analyzer import analyze_folder_duplicates


def _resource_path(relative: str) -> str:
    """Return absolute path to a resource, works for dev and PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    return os.path.join(base, relative)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Duplicate File Finder")
        self.setMinimumSize(900, 600)
        self._worker = None
        self._progress_dlg = None
        self._settings = get_settings()
        self._build_ui()
        self._load_stylesheet()
        self._restore_geometry()

    def _build_ui(self):
        # Central widget with splitter
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)

        self.scan_panel = ScanPanel()
        self.results_table = ResultsTable()
        self.folder_view = FolderView()

        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.results_table, "File Duplicates")
        self.tab_widget.addTab(self.folder_view, "Folder Analysis")

        self.splitter.addWidget(self.scan_panel)
        self.splitter.addWidget(self.tab_widget)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([240, 900])

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.lbl_status = QLabel("Ready")
        self.status_bar.addWidget(self.lbl_status, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # Connections
        self.scan_panel.scan_requested.connect(self._on_scan_requested)
        self.results_table.delete_requested.connect(self._on_delete_requested)
        self.results_table.open_requested.connect(self._on_open_requested)
        self.folder_view.delete_requested.connect(self._on_delete_requested)
        self.folder_view.open_requested.connect(self._on_open_folder)

    def _load_stylesheet(self):
        qss_path = _resource_path("resources/styles.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r") as f:
                self.setStyleSheet(f.read())

    def _restore_geometry(self):
        geom = self._settings.value("window/geometry")
        if geom:
            self.restoreGeometry(geom)
        else:
            self.resize(1100, 700)
            # Center on screen
            screen = QApplication.primaryScreen().availableGeometry()
            x = (screen.width() - self.width()) // 2
            y = (screen.height() - self.height()) // 2
            self.move(x, y)

    def closeEvent(self, event):
        self._settings.setValue("window/geometry", self.saveGeometry())
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        event.accept()

    # --- Scan ---

    def _on_scan_requested(self, paths: list, options: dict):
        if self._worker and self._worker.isRunning():
            return

        self.results_table.clear()
        self.folder_view.clear()
        self.scan_panel.set_scanning(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.lbl_status.setText("Starting scan...")

        self._progress_dlg = ProgressDialog(self)
        self._progress_dlg.cancel_requested.connect(self._on_cancel)
        self._progress_dlg.show()

        config = ScanConfig(
            paths=paths,
            min_size=options["min_size"],
            algorithm=options["algorithm"],
            skip_symlinks=options["skip_symlinks"],
            skip_hidden=options["skip_hidden"],
            max_workers=options["max_workers"],
        )

        self._worker = ScanWorker(config, self)
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.scan_complete.connect(self._on_scan_complete)
        self._worker.error_occurred.connect(self._on_scan_error)
        self._worker.start()

    def _on_cancel(self):
        if self._worker:
            self._worker.cancel()
            self.lbl_status.setText("Cancelling...")

    def _on_progress(self, done: int, total: int, current_path: str):
        if self._progress_dlg:
            self._progress_dlg.update_progress(done, total, current_path)
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(done)
        else:
            self.progress_bar.setRange(0, 0)
        if done > 0 and total > 0:
            self.lbl_status.setText(f"Scanning... {done:,} / {total:,} files")

    def _on_scan_complete(self, result):
        if self._progress_dlg:
            self._progress_dlg.close()
            self._progress_dlg = None

        self.scan_panel.set_scanning(False)
        self.scan_panel.update_summary(result)
        self.progress_bar.setVisible(False)

        if result.total_groups == 0:
            self.lbl_status.setText(
                f"Scan complete — no duplicates found ({result.total_files_scanned:,} files scanned in {result.duration_seconds:.1f}s)"
            )
        else:
            self.lbl_status.setText(
                f"Found {result.total_groups:,} duplicate groups — {human_size(result.total_wasted_bytes)} wasted "
                f"({result.total_files_scanned:,} files in {result.duration_seconds:.1f}s)"
            )
            self.results_table.load_results(result.groups)

            # Folder analysis (fast — runs on already-computed data)
            folder_matches = analyze_folder_duplicates(result)
            if folder_matches:
                self.folder_view.load_matches(folder_matches)
                self.tab_widget.setTabText(
                    1, f"Folder Analysis ({len(folder_matches)} groups)"
                )
            else:
                self.tab_widget.setTabText(1, "Folder Analysis")

    def _on_scan_error(self, error_msg: str):
        if self._progress_dlg:
            self._progress_dlg.close()
            self._progress_dlg = None
        self.scan_panel.set_scanning(False)
        self.progress_bar.setVisible(False)
        self.lbl_status.setText("Scan failed")
        QMessageBox.critical(self, "Scan Error", f"An error occurred during scanning:\n\n{error_msg}")

    # --- Delete ---

    def _on_delete_requested(self, paths: list):
        if not paths:
            return

        from utils.format import human_size
        total_size = 0
        # Try to calculate total size of files to delete
        for p in paths:
            try:
                total_size += os.path.getsize(p)
            except OSError:
                pass

        msg = (
            f"Move {len(paths)} file(s) to the Recycle Bin?\n\n"
            f"Total size: {human_size(total_size)}\n\n"
            f"This action is reversible — files will go to the Recycle Bin."
        )
        if len(paths) <= 10:
            msg += "\n\nFiles to delete:\n" + "\n".join(f"  • {p}" for p in paths)

        reply = QMessageBox.question(
            self, "Confirm Deletion", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        succeeded, failed = delete_files_to_trash(paths)

        if succeeded:
            deleted = set(succeeded)
            self.results_table.remove_paths(deleted)
            self.folder_view.remove_paths(deleted)
            self.lbl_status.setText(f"Moved {len(succeeded)} file(s) to Recycle Bin.")

        if failed:
            fail_msg = "\n".join(f"  • {p}: {err}" for p, err in failed)
            QMessageBox.warning(
                self, "Some Deletions Failed",
                f"{len(failed)} file(s) could not be deleted:\n\n{fail_msg}"
            )

    # --- Open ---

    def _on_open_requested(self, path: str):
        import subprocess
        try:
            subprocess.Popen(["explorer", "/select,", path])
        except Exception:
            pass

    def _on_open_folder(self, folder: str):
        import subprocess
        try:
            subprocess.Popen(["explorer", folder])
        except Exception:
            pass
