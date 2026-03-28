import threading
from PySide6.QtCore import QThread, Signal

from core.scanner import scan_for_duplicates
from core.models import DuplicateGroup, ScanResult


class ScanConfig:
    def __init__(
        self,
        paths: list,
        min_size: int = 1024,
        algorithm: str = "sha256",
        skip_symlinks: bool = True,
        skip_hidden: bool = False,
        max_workers: int = 4,
    ):
        self.paths = paths
        self.min_size = min_size
        self.algorithm = algorithm
        self.skip_symlinks = skip_symlinks
        self.skip_hidden = skip_hidden
        self.max_workers = max_workers


class ScanWorker(QThread):
    progress_updated = Signal(int, int, str)   # done, total, current_path
    scan_complete = Signal(object)             # ScanResult
    error_occurred = Signal(str)

    def __init__(self, config: ScanConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def run(self):
        try:
            result = scan_for_duplicates(
                paths=self._config.paths,
                min_size=self._config.min_size,
                algorithm=self._config.algorithm,
                skip_symlinks=self._config.skip_symlinks,
                skip_hidden=self._config.skip_hidden,
                max_workers=self._config.max_workers,
                cancel_event=self._cancel_event,
                progress_callback=self._on_progress,
            )
            self.scan_complete.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _on_progress(self, done: int, total: int, current_path: str):
        self.progress_updated.emit(done, total, current_path)
