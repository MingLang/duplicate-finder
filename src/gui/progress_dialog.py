from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
)
from PySide6.QtCore import Qt, Signal


class ProgressDialog(QDialog):
    cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scanning...")
        self.setModal(False)
        self.setMinimumWidth(480)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint
        )
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.lbl_status = QLabel("Preparing scan...")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        self.lbl_detail = QLabel("")
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.lbl_detail)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)
        btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)

    def update_progress(self, done: int, total: int, current_path: str):
        if total > 0:
            pct = int(done * 100 / total)
            self.progress_bar.setValue(pct)
            self.lbl_status.setText(f"Processing files... {done:,} / {total:,}")
        else:
            self.progress_bar.setRange(0, 0)  # Indeterminate
            self.lbl_status.setText("Collecting files...")

        if current_path:
            # Truncate long paths for display
            if len(current_path) > 70:
                current_path = "..." + current_path[-67:]
            self.lbl_detail.setText(current_path)

    def set_phase(self, phase: str):
        self.lbl_status.setText(phase)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
