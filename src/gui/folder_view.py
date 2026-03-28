import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QMenu, QAbstractItemView, QHeaderView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QBrush

from utils.format import human_size

COL_NAME = 0   # folder/file name, or pair header
COL_INFO = 1   # shared-file count / file size / similarity
COL_PATH = 2   # full path

# Alternating colour pairs: (pair-header bg, folder-A bg, folder-B bg)
_PALETTE = [
    (QColor(200, 220, 255), QColor(225, 235, 255), QColor(235, 242, 255)),  # blue
    (QColor(195, 240, 210), QColor(220, 248, 228), QColor(232, 252, 238)),  # green
    (QColor(255, 225, 195), QColor(255, 240, 220), QColor(255, 247, 235)),  # orange
    (QColor(235, 210, 255), QColor(245, 228, 255), QColor(250, 240, 255)),  # purple
]


class FolderView(QWidget):
    """
    Pairwise folder duplicate comparison view.

    Tree layout:
      [Pair N]  FolderA-name  ↔  FolderB-name   X files — identical/Y% — Z GB wasted
        ├── C:\\path\\to\\FolderA\\            X / total files shared
        │     ☑ filename.ext    size
        │     ☑ ...
        └── C:\\path\\to\\FolderB\\            X / total files shared
              ☑ filename.ext    size
              ☑ ...
    """

    delete_requested = Signal(list)  # list[str] file paths
    open_requested = Signal(str)     # folder path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pairs = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.lbl_summary = QLabel(
            "Run a scan, then switch to this tab to see folder-level comparison."
        )
        self.lbl_summary.setContentsMargins(6, 4, 6, 0)
        layout.addWidget(self.lbl_summary)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Folder / File", "Info", "Full Path"])
        self.tree.setAlternatingRowColors(False)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.setUniformRowHeights(False)

        hdr = self.tree.header()
        hdr.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(COL_INFO, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(COL_PATH, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setMinimumSectionSize(80)

        layout.addWidget(self.tree)

        btn_row = QHBoxLayout()
        self.btn_uncheck_all = QPushButton("Uncheck All")
        self.btn_expand_all = QPushButton("Expand All")
        self.btn_collapse_all = QPushButton("Collapse Pairs")
        for b in (self.btn_uncheck_all, self.btn_expand_all, self.btn_collapse_all):
            btn_row.addWidget(b)
        btn_row.addStretch()
        self.lbl_checked = QLabel("0 files checked")
        btn_row.addWidget(self.lbl_checked)
        layout.addLayout(btn_row)

        action_row = QHBoxLayout()
        self.btn_delete = QPushButton("Delete Checked to Recycle Bin")
        self.btn_delete.setObjectName("btnDelete")
        self.btn_delete.setMinimumHeight(32)
        action_row.addWidget(self.btn_delete)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.btn_uncheck_all.clicked.connect(self._uncheck_all)
        self.btn_expand_all.clicked.connect(self.tree.expandAll)
        self.btn_collapse_all.clicked.connect(self._collapse_to_pairs)
        self.btn_delete.clicked.connect(self._on_delete)
        self.tree.itemChanged.connect(self._on_item_changed)

    # ------------------------------------------------------------------
    # Load / clear
    # ------------------------------------------------------------------

    def load_matches(self, matches: list):
        self.tree.blockSignals(True)
        self.tree.clear()
        self._pairs = matches

        for idx, match in enumerate(matches):
            pal = _PALETTE[idx % len(_PALETTE)]
            pair_bg, bg_a, bg_b = pal[0], pal[1], pal[2]
            folder_bgs = [bg_a, bg_b]

            fa, fb = match.folders[0], match.folders[1]
            name_a = os.path.basename(fa) or fa
            name_b = os.path.basename(fb) or fb

            sim_text = "identical" if match.is_identical else f"{match.similarity:.0%} similar"
            wasted_text = human_size(match.wasted_bytes)

            pair_item = QTreeWidgetItem()
            pair_item.setText(
                COL_NAME,
                f"Pair {idx + 1}    {name_a}  ↔  {name_b}",
            )
            pair_item.setText(
                COL_INFO,
                f"{match.shared_file_count} files — {sim_text} — {wasted_text} wasted",
            )
            pair_item.setText(COL_PATH, "")
            pair_item.setToolTip(COL_NAME, f"{fa}\n↔\n{fb}")
            pair_item.setData(0, Qt.ItemDataRole.UserRole, ("pair", idx))

            bold = QFont()
            bold.setBold(True)
            bold.setPointSize(bold.pointSize() + 1)
            pair_item.setFont(COL_NAME, bold)
            for col in range(3):
                pair_item.setBackground(col, QBrush(pair_bg))

            for folder_idx, folder in enumerate(match.folders):
                folder_item = self._make_folder_item(
                    match, folder, folder_bgs[folder_idx]
                )
                pair_item.addChild(folder_item)

            self.tree.addTopLevelItem(pair_item)
            pair_item.setExpanded(True)
            for j in range(pair_item.childCount()):
                pair_item.child(j).setExpanded(True)

        self.tree.blockSignals(False)
        self._update_summary()
        self._update_checked_label()

    def _make_folder_item(self, match, folder: str, bg: QColor) -> QTreeWidgetItem:
        hashes_here = match.folder_hashes[folder]
        shared_count = len(hashes_here & match.shared_hashes)
        total_count = len(hashes_here)

        folder_item = QTreeWidgetItem()
        folder_item.setText(COL_NAME, folder)
        folder_item.setText(COL_INFO, f"{shared_count} / {total_count} files duplicated")
        folder_item.setText(COL_PATH, folder)
        folder_item.setToolTip(COL_NAME, folder)
        folder_item.setData(0, Qt.ItemDataRole.UserRole, ("folder", folder))
        folder_item.setCheckState(COL_NAME, Qt.CheckState.Checked)
        folder_item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )

        fld_font = QFont()
        fld_font.setBold(True)
        folder_item.setFont(COL_NAME, fld_font)
        for col in range(3):
            folder_item.setBackground(col, QBrush(bg))

        # File children — only shared files (appear in the other folder too)
        shared_here = match.shared_hashes & hashes_here
        for h in sorted(shared_here):
            fi = match.folder_file_map[folder].get(h)
            if not fi:
                continue
            file_item = QTreeWidgetItem(folder_item)
            file_item.setText(COL_NAME, os.path.basename(fi.path))
            file_item.setText(COL_INFO, human_size(fi.size))
            file_item.setText(COL_PATH, fi.path)
            file_item.setToolTip(COL_NAME, fi.path)
            file_item.setToolTip(COL_PATH, fi.path)
            file_item.setCheckState(COL_NAME, Qt.CheckState.Checked)
            file_item.setData(0, Qt.ItemDataRole.UserRole, ("file", fi.path, fi.modified))

        return folder_item

    def clear(self):
        self.tree.clear()
        self._pairs = []
        self.lbl_summary.setText(
            "Run a scan, then switch to this tab to see folder-level comparison."
        )
        self._update_checked_label()

    # ------------------------------------------------------------------
    # Checkbox propagation
    # ------------------------------------------------------------------

    def _on_item_changed(self, item, column):
        if column != COL_NAME:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        self.tree.blockSignals(True)
        if data[0] == "folder":
            state = item.checkState(COL_NAME)
            if state != Qt.CheckState.PartiallyChecked:
                for k in range(item.childCount()):
                    item.child(k).setCheckState(COL_NAME, state)
        elif data[0] == "file":
            parent = item.parent()
            if parent:
                self._sync_folder_tristate(parent)
        self.tree.blockSignals(False)
        self._update_checked_label()

    def _sync_folder_tristate(self, folder_item):
        n = folder_item.childCount()
        if n == 0:
            return
        checked = sum(
            1 for k in range(n)
            if folder_item.child(k).checkState(COL_NAME) == Qt.CheckState.Checked
        )
        if checked == 0:
            folder_item.setCheckState(COL_NAME, Qt.CheckState.Unchecked)
        elif checked == n:
            folder_item.setCheckState(COL_NAME, Qt.CheckState.Checked)
        else:
            folder_item.setCheckState(COL_NAME, Qt.CheckState.PartiallyChecked)

    # ------------------------------------------------------------------
    # Bulk actions
    # ------------------------------------------------------------------

    def _uncheck_all(self):
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            pair_item = self.tree.topLevelItem(i)
            for j in range(pair_item.childCount()):
                folder_item = pair_item.child(j)
                folder_item.setCheckState(COL_NAME, Qt.CheckState.Unchecked)
                for k in range(folder_item.childCount()):
                    folder_item.child(k).setCheckState(COL_NAME, Qt.CheckState.Unchecked)
        self.tree.blockSignals(False)
        self._update_checked_label()

    def _set_folder_check(self, folder_item, state):
        self.tree.blockSignals(True)
        folder_item.setCheckState(COL_NAME, state)
        for k in range(folder_item.childCount()):
            folder_item.child(k).setCheckState(COL_NAME, state)
        self.tree.blockSignals(False)
        self._update_checked_label()

    def _collapse_to_pairs(self):
        self.tree.collapseAll()
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setExpanded(True)

    # ------------------------------------------------------------------
    # Checked paths
    # ------------------------------------------------------------------

    def get_checked_paths(self) -> list:
        seen = set()
        paths = []
        for i in range(self.tree.topLevelItemCount()):
            pair_item = self.tree.topLevelItem(i)
            for j in range(pair_item.childCount()):
                folder_item = pair_item.child(j)
                for k in range(folder_item.childCount()):
                    file_item = folder_item.child(k)
                    if file_item.checkState(COL_NAME) == Qt.CheckState.Checked:
                        p = file_item.text(COL_PATH)
                        if p not in seen:
                            seen.add(p)
                            paths.append(p)
        return paths

    def _update_checked_label(self, *args):
        count = len(self.get_checked_paths())
        self.lbl_checked.setText(f"{count} file{'s' if count != 1 else ''} checked")

    def _update_summary(self):
        if not self._pairs:
            self.lbl_summary.setText("No folder pairs found.")
            return
        total_wasted = sum(m.wasted_bytes for m in self._pairs)
        self.lbl_summary.setText(
            f"{len(self._pairs)} folder pair(s) with duplicate files — "
            f"{human_size(total_wasted)} could be freed.   "
            f"Uncheck the folder you want to KEEP, then click Delete."
        )

    # ------------------------------------------------------------------
    # Remove deleted files from tree
    # ------------------------------------------------------------------

    def remove_paths(self, deleted_paths: set):
        self.tree.blockSignals(True)
        pairs_to_remove = []
        for i in range(self.tree.topLevelItemCount()):
            pair_item = self.tree.topLevelItem(i)
            for j in range(pair_item.childCount()):
                folder_item = pair_item.child(j)
                to_remove = [
                    k for k in range(folder_item.childCount())
                    if folder_item.child(k).text(COL_PATH) in deleted_paths
                ]
                for k in reversed(to_remove):
                    folder_item.takeChild(k)
            # Remove pair if either folder has no shared files left
            active_folders = sum(
                1 for j in range(pair_item.childCount())
                if pair_item.child(j).childCount() > 0
            )
            if active_folders < 2:
                pairs_to_remove.append(i)
        for i in reversed(pairs_to_remove):
            self.tree.takeTopLevelItem(i)
        self.tree.blockSignals(False)
        self._update_checked_label()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        menu = QMenu(self)
        if data[0] == "folder":
            folder = data[1]
            menu.addAction(
                "Check all  (mark this folder for deletion)",
                lambda: self._set_folder_check(item, Qt.CheckState.Checked),
            )
            menu.addAction(
                "Uncheck all  (keep this folder)",
                lambda: self._set_folder_check(item, Qt.CheckState.Unchecked),
            )
            menu.addSeparator()
            menu.addAction(
                "Open in Explorer",
                lambda: self.open_requested.emit(folder),
            )
        elif data[0] == "file":
            path = data[1]
            if item.checkState(COL_NAME) == Qt.CheckState.Checked:
                menu.addAction(
                    "Uncheck  (keep this file)",
                    lambda: item.setCheckState(COL_NAME, Qt.CheckState.Unchecked),
                )
            else:
                menu.addAction(
                    "Check for deletion",
                    lambda: item.setCheckState(COL_NAME, Qt.CheckState.Checked),
                )
            menu.addSeparator()
            menu.addAction(
                "Open containing folder in Explorer",
                lambda: self.open_requested.emit(os.path.dirname(path)),
            )
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def _on_delete(self):
        paths = self.get_checked_paths()
        if paths:
            self.delete_requested.emit(paths)
