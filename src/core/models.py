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
    groups: list = field(default_factory=list)   # list[DuplicateGroup]
    all_files: list = field(default_factory=list)  # list[FileInfo] — all scanned files


@dataclass
class FolderNode:
    """A node in the folder size/duplicate tree."""
    path: str
    name: str
    total_size: int = 0       # bytes, includes all descendants
    total_files: int = 0      # file count, includes all descendants
    total_dup_files: int = 0  # files that have a duplicate somewhere
    total_dup_size: int = 0   # bytes of those duplicate files
    children: list = field(default_factory=list)  # list[FolderNode], sorted by name

    @property
    def dup_ratio(self) -> float:
        return self.total_dup_files / self.total_files if self.total_files > 0 else 0.0


@dataclass
class FolderMatch:
    """A group of folders that share duplicate files with each other."""
    folders: list        # list[str] — sorted folder paths in this group
    shared_hashes: set   # set[str] — file hashes present in >= 2 folders
    folder_hashes: dict  # dict[str, set[str]] — folder -> all dup-file hashes in it
    folder_file_map: dict  # dict[str, dict[str, FileInfo]] — folder -> {hash: FileInfo}
    hash_size: dict      # dict[str, int] — hash -> bytes per file

    @property
    def shared_file_count(self) -> int:
        return len(self.shared_hashes)

    @property
    def shared_bytes(self) -> int:
        """Total bytes of one copy of every shared file."""
        return sum(self.hash_size.get(h, 0) for h in self.shared_hashes)

    @property
    def wasted_bytes(self) -> int:
        """Space that could be freed by keeping only one folder's copy."""
        return self.shared_bytes * (len(self.folders) - 1)

    @property
    def similarity(self) -> float:
        """Fraction of shared files vs the largest folder's dup-file count (0–1)."""
        if not self.folder_hashes:
            return 0.0
        max_count = max(len(v) for v in self.folder_hashes.values())
        return len(self.shared_hashes) / max_count if max_count > 0 else 0.0

    @property
    def is_identical(self) -> bool:
        """True when every folder contains exactly the same set of files."""
        if len(self.folders) < 2:
            return False
        first = self.folder_hashes[self.folders[0]]
        return all(self.folder_hashes[f] == first for f in self.folders[1:])
