from dataclasses import dataclass, field


@dataclass
class FileInfo:
    path: str
    size: int        # bytes
    modified: float  # os.stat mtime
    hash: str = ""


@dataclass
class DuplicateGroup:
    hash: str
    size: int                   # bytes per file
    files: list = field(default_factory=list)  # list[FileInfo]

    @property
    def count(self) -> int:
        return len(self.files)

    @property
    def wasted_bytes(self) -> int:
        return self.size * (self.count - 1)


@dataclass
class ScanResult:
    total_files_scanned: int = 0
    total_groups: int = 0
    total_wasted_bytes: int = 0
    duration_seconds: float = 0.0
    groups: list = field(default_factory=list)  # list[DuplicateGroup]
