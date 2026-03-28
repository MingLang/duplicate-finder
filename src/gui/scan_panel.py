import os
import string
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QGroupBox, QLabel, QComboBox, QSpinBox, QCheckBox, QFileDialog,
    QAbstractItemView, QSizePolicy, QMenu,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDropEvent, QDragEnterEvent


def _get_drives() -> list:
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            drives.append(drive)
    return drives


class PathListWidget(QListWidget):
    """QListWidget that accepts drag-and-drop of folders."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isdir(path):
                    self._add_path(path)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def _add_path(self, path: str):
        # Avoid duplicates
        existing = [self.item(i).text() for i in range(self.count())]
        if path not in existing:
            self.addItem(path)


class ScanPanel(QWidget):
    scan_requested = Signal(list, dict)  # paths, options

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(240)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- Scan Targets ---
        targets_box = QGroupBox("Scan Targets")
        targets_layout = QVBoxLayout(targets_box)
        targets_layout.setSpacing(4)

        self.path_list = PathListWidget()
        self.path_list.setToolTip("Drag folders here, or use the buttons below")
        targets_layout.addWidget(self.path_list)

        btn_row = QHBoxLayout()
        self.btn_add_folder = QPushButton("+ Folder")
        self.btn_add_folder.setToolTip("Add a folder to scan")
        self.btn_add_drive = QPushButton("+ Drive")
        self.btn_add_drive.setToolTip("Add an entire drive to scan")
        self.btn_remove = QPushButton("Remove")
        self.btn_remove.setToolTip("Remove selected paths")
        btn_row.addWidget(self.btn_add_folder)
        btn_row.addWidget(self.btn_add_drive)
        btn_row.addWidget(self.btn_remove)
        targets_layout.addLayout(btn_row)

        layout.addWidget(targets_box)

        # --- Options ---
        opts_box = QGroupBox("Options")
        opts_layout = QVBoxLayout(opts_box)
        opts_layout.setSpacing(6)

        # Hash algorithm
        alg_row = QHBoxLayout()
        alg_row.addWidget(QLabel("Algorithm:"))
        self.combo_algorithm = QComboBox()
        self.combo_algorithm.addItems(["sha256", "md5"])
        alg_row.addWidget(self.combo_algorithm)
        opts_layout.addLayout(alg_row)

        # Min file size
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Min size:"))
        self.spin_min_size = QSpinBox()
        self.spin_min_size.setRange(0, 999999)
        self.spin_min_size.setValue(1)
        size_row.addWidget(self.spin_min_size)
        self.combo_size_unit = QComboBox()
        self.combo_size_unit.addItems(["KB", "MB", "Bytes"])
        size_row.addWidget(self.combo_size_unit)
        opts_layout.addLayout(size_row)

        # Thread count
        thread_row = QHBoxLayout()
        thread_row.addWidget(QLabel("Threads:"))
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 32)
        self.spin_threads.setValue(4)
        thread_row.addWidget(self.spin_threads)
        opts_layout.addLayout(thread_row)

        self.chk_skip_symlinks = QCheckBox("Skip symlinks")
        self.chk_skip_symlinks.setChecked(True)
        self.chk_skip_hidden = QCheckBox("Skip hidden files")
        self.chk_skip_hidden.setChecked(False)
        opts_layout.addWidget(self.chk_skip_symlinks)
        opts_layout.addWidget(self.chk_skip_hidden)

        layout.addWidget(opts_box)

        # --- Summary ---
        self.summary_box = QGroupBox("Summary")
        summary_layout = QVBoxLayout(self.summary_box)
        self.lbl_files = QLabel("Files scanned: —")
        self.lbl_groups = QLabel("Duplicate groups: —")
        self.lbl_wasted = QLabel("Wasted space: —")
        self.lbl_time = QLabel("Scan time: —")
        for lbl in (self.lbl_files, self.lbl_groups, self.lbl_wasted, self.lbl_time):
            lbl.setWordWrap(True)
            summary_layout.addWidget(lbl)
        layout.addWidget(self.summary_box)

        layout.addStretch()

        # --- Scan Button ---
        self.btn_scan = QPushButton("Scan")
        self.btn_scan.setObjectName("btnScan")
        self.btn_scan.setMinimumHeight(36)
        self.btn_scan.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.btn_scan)

        # --- Connections ---
        self.btn_add_folder.clicked.connect(self._add_folder)
        self.btn_add_drive.clicked.connect(self._add_drive)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_scan.clicked.connect(self._on_scan_clicked)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.path_list._add_path(folder)

    def _add_drive(self):
        drives = _get_drives()
        if not drives:
            return
        menu = QMenu(self)
        for drive in drives:
            menu.addAction(drive, lambda d=drive: self.path_list._add_path(d))
        menu.exec(self.btn_add_drive.mapToGlobal(self.btn_add_drive.rect().bottomLeft()))

    def _remove_selected(self):
        for item in self.path_list.selectedItems():
            self.path_list.takeItem(self.path_list.row(item))

    def _on_scan_clicked(self):
        paths = [self.path_list.item(i).text() for i in range(self.path_list.count())]
        if not paths:
            return
        unit = self.combo_size_unit.currentText()
        val = self.spin_min_size.value()
        multipliers = {"Bytes": 1, "KB": 1024, "MB": 1024 * 1024}
        min_size = val * multipliers.get(unit, 1024)

        options = {
            "min_size": min_size,
            "algorithm": self.combo_algorithm.currentText(),
            "skip_symlinks": self.chk_skip_symlinks.isChecked(),
            "skip_hidden": self.chk_skip_hidden.isChecked(),
            "max_workers": self.spin_threads.value(),
        }
        self.scan_requested.emit(paths, options)

    def update_summary(self, result):
        from utils.format import human_size
        self.lbl_files.setText(f"Files scanned: {result.total_files_scanned:,}")
        self.lbl_groups.setText(f"Duplicate groups: {result.total_groups:,}")
        self.lbl_wasted.setText(f"Wasted space: {human_size(result.total_wasted_bytes)}")
        self.lbl_time.setText(f"Scan time: {result.duration_seconds:.1f}s")

    def set_scanning(self, scanning: bool):
        self.btn_scan.setEnabled(not scanning)
        self.btn_add_folder.setEnabled(not scanning)
        self.btn_add_drive.setEnabled(not scanning)
        self.btn_remove.setEnabled(not scanning)
