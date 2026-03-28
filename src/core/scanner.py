import os
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Generator, Optional

from .hasher import hash_partial, hash_full
from .models import FileInfo, DuplicateGroup, ScanResult


def _walk_paths(
    paths: list,
    skip_symlinks: bool,
    skip_hidden: bool,
) -> list:
    """Iterative directory walk using os.scandir(). Returns list of FileInfo."""
    results = []
    for root_path in paths:
        stack = [os.path.normpath(root_path)]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as it:
                    for entry in it:
                        try:
                            if skip_symlinks and entry.is_symlink():
                                continue
                            if skip_hidden and entry.name.startswith("."):
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                # Skip hidden dirs on Windows (system attribute)
                                if skip_hidden:
                                    try:
                                        import stat as stat_mod
                                        s = entry.stat()
                                        # FILE_ATTRIBUTE_HIDDEN = 2
                                        if hasattr(s, 'st_file_attributes') and (s.st_file_attributes & 2):
                                            continue
                                    except (OSError, AttributeError):
                                        pass
                                stack.append(os.path.normpath(entry.path))
                            elif entry.is_file(follow_symlinks=False):
                                try:
                                    st = entry.stat()
                                    if st.st_size > 0:
                                        results.append(FileInfo(
                                            path=os.path.normpath(entry.path),
                                            size=st.st_size,
                                            modified=st.st_mtime,
                                        ))
                                except (OSError, PermissionError):
                                    pass
                        except (OSError, PermissionError):
                            pass
            except (OSError, PermissionError):
                pass
    return results


def _group_by_size(files: list, min_size: int) -> dict:
    """Group FileInfo objects by size, discard unique sizes and below min_size."""
    by_size = defaultdict(list)
    for fi in files:
        if fi.size >= min_size:
            by_size[fi.size].append(fi)
    return {size: group for size, group in by_size.items() if len(group) > 1}


def _partial_hash_filter(
    by_size: dict,
    algorithm: str,
    max_workers: int,
    cancel_event: threading.Event,
    progress_callback: Optional[Callable] = None,
    progress_offset: int = 0,
    total_files: int = 0,
) -> dict:
    """Apply partial-hash pre-filter. Returns dict keyed by (size, partial_hash)."""
    candidates = []
    for size, group in by_size.items():
        for fi in group:
            candidates.append((size, fi))

    by_partial = defaultdict(list)
    done = progress_offset

    def _hash_one(item):
        size, fi = item
        ph = hash_partial(fi.path, algorithm)
        return size, fi, ph

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_hash_one, item): item for item in candidates}
        for future in as_completed(futures):
            if cancel_event.is_set():
                break
            try:
                size, fi, ph = future.result()
                if ph:
                    by_partial[(size, ph)].append(fi)
            except Exception:
                pass
            done += 1
            if progress_callback:
                progress_callback(done, total_files, "")

    return {key: group for key, group in by_partial.items() if len(group) > 1}


def scan_for_duplicates(
    paths: list,
    min_size: int,
    algorithm: str,
    skip_symlinks: bool,
    skip_hidden: bool,
    max_workers: int,
    cancel_event: threading.Event,
    progress_callback: Optional[Callable] = None,
) -> ScanResult:
    """
    Full scan pipeline. Returns ScanResult with all duplicate groups.
    progress_callback(done: int, total: int, current_path: str)
    """
    start = time.time()

    # Stage 1: collect all files
    if progress_callback:
        progress_callback(0, 0, "Collecting files...")
    all_files = _walk_paths(paths, skip_symlinks, skip_hidden)
    total_scanned = len(all_files)

    if cancel_event.is_set():
        return ScanResult(total_files_scanned=total_scanned)

    # Stage 2: group by size
    if progress_callback:
        progress_callback(0, total_scanned, "Grouping by size...")
    by_size = _group_by_size(all_files, min_size)
    size_candidates = sum(len(v) for v in by_size.values())

    if not by_size or cancel_event.is_set():
        return ScanResult(total_files_scanned=total_scanned)

    # Stage 3: partial hash pre-filter
    if progress_callback:
        progress_callback(0, size_candidates, "Pre-filtering with partial hash...")
    by_partial = _partial_hash_filter(
        by_size, algorithm, max_workers, cancel_event,
        progress_callback, 0, size_candidates
    )
    partial_candidates = sum(len(v) for v in by_partial.values())

    if not by_partial or cancel_event.is_set():
        return ScanResult(total_files_scanned=total_scanned)

    # Stage 4: full hash
    if progress_callback:
        progress_callback(0, partial_candidates, "Computing full hashes...")

    groups = []
    done = 0
    by_full = defaultdict(list)

    def _full_hash_one(item):
        key, fi = item
        fh = hash_full(fi.path, algorithm)
        return key, fi, fh

    items = [(key, fi) for key, group in by_partial.items() for fi in group]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_full_hash_one, item): item for item in items}
        for future in as_completed(futures):
            if cancel_event.is_set():
                break
            try:
                key, fi, fh = future.result()
                if fh:
                    fi.hash = fh
                    by_full[fh].append(fi)
            except Exception:
                pass
            done += 1
            if progress_callback:
                progress_callback(done, partial_candidates, "")

    for fh, file_list in by_full.items():
        if len(file_list) > 1 and not cancel_event.is_set():
            # All files in a group have same size (guaranteed by size pre-filter)
            size = file_list[0].size
            group = DuplicateGroup(hash=fh, size=size, files=file_list)
            groups.append(group)

    # Sort groups by wasted space descending
    groups.sort(key=lambda g: g.wasted_bytes, reverse=True)

    elapsed = time.time() - start
    total_wasted = sum(g.wasted_bytes for g in groups)

    return ScanResult(
        total_files_scanned=total_scanned,
        total_groups=len(groups),
        total_wasted_bytes=total_wasted,
        duration_seconds=elapsed,
        groups=groups,
    )
