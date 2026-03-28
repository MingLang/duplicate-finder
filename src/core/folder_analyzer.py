import os
from collections import defaultdict

from .models import ScanResult, FolderMatch


def analyze_folder_duplicates(
    scan_result: ScanResult,
    min_shared_files: int = 1,
) -> list:
    """
    Produce a pairwise list of FolderMatch objects.

    For every pair of folders (A, B) that share >= min_shared_files duplicate
    file hashes, one FolderMatch(folders=[A, B], ...) is created.
    Results are sorted by wasted_bytes descending.
    """
    if not scan_result.groups:
        return []

    # folder -> set of hashes whose files live there
    folder_hashes: dict = defaultdict(set)
    # folder -> {hash: FileInfo}
    folder_file_map: dict = defaultdict(dict)
    hash_size: dict = {}

    for group in scan_result.groups:
        hash_size[group.hash] = group.size
        for fi in group.files:
            folder = os.path.normpath(os.path.dirname(fi.path))
            folder_hashes[folder].add(group.hash)
            folder_file_map[folder][group.hash] = fi

    folders = list(folder_hashes.keys())
    if len(folders) < 2:
        return []

    pairs = []
    for i in range(len(folders)):
        for j in range(i + 1, len(folders)):
            fa, fb = folders[i], folders[j]
            shared = folder_hashes[fa] & folder_hashes[fb]
            if len(shared) < min_shared_files:
                continue
            pairs.append(FolderMatch(
                folders=[fa, fb],
                shared_hashes=shared,
                folder_hashes={fa: folder_hashes[fa], fb: folder_hashes[fb]},
                folder_file_map={
                    fa: dict(folder_file_map[fa]),
                    fb: dict(folder_file_map[fb]),
                },
                hash_size=hash_size,
            ))

    pairs.sort(key=lambda m: m.wasted_bytes, reverse=True)
    return pairs
