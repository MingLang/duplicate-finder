import os
from collections import defaultdict

from .models import ScanResult, FolderNode


def build_folder_tree(scan_result: ScanResult, root_paths: list) -> list:
    """
    Build a list of FolderNode trees (one per root_path) with cumulative size,
    file count, and duplicate statistics derived from scan_result.

    Returns list[FolderNode], one per root path that contained scanned files.
    """
    if not scan_result.all_files:
        return []

    # Build set of every path that is a duplicate (has at least one other copy)
    dup_paths: set = set()
    for group in scan_result.groups:
        for fi in group.files:
            dup_paths.add(os.path.normpath(fi.path))

    # Per-folder own stats (files directly inside, not children)
    own: dict = defaultdict(lambda: {'size': 0, 'files': 0, 'dup_files': 0, 'dup_size': 0})
    for fi in scan_result.all_files:
        folder = os.path.normpath(os.path.dirname(fi.path))
        own[folder]['size'] += fi.size
        own[folder]['files'] += 1
        if os.path.normpath(fi.path) in dup_paths:
            own[folder]['dup_files'] += 1
            own[folder]['dup_size'] += fi.size

    # Map: parent folder → list of direct child folders
    all_folders = set(own.keys())
    by_parent: dict = defaultdict(list)
    for path in all_folders:
        parent = os.path.normpath(os.path.dirname(path))
        if parent != path:  # drive root (e.g. C:\) points to itself — stop there
            by_parent[parent].append(path)

    def build_node(path: str, display_name: str) -> FolderNode:
        node = FolderNode(path=path, name=display_name)
        s = own.get(path, {})
        node.total_size = s.get('size', 0)
        node.total_files = s.get('files', 0)
        node.total_dup_files = s.get('dup_files', 0)
        node.total_dup_size = s.get('dup_size', 0)

        for child_path in sorted(by_parent.get(path, [])):
            child = build_node(child_path, os.path.basename(child_path) or child_path)
            node.children.append(child)
            node.total_size += child.total_size
            node.total_files += child.total_files
            node.total_dup_files += child.total_dup_files
            node.total_dup_size += child.total_dup_size

        return node

    roots = []
    for rp in root_paths:
        norm = os.path.normpath(rp)
        if norm in all_folders or norm in by_parent:
            roots.append(build_node(norm, norm))  # show full path at root level

    return roots
