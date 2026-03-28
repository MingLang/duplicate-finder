import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QMenu, QAbstractItemView, QHeaderView,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QBrush

from utils.format import human_size


# Column indices
COL_NAME = 0
COL_HASH = 1
COL_SIZE = 2
COL_PATH = 3

GROUP_BG = QColor(255, 243, 205)   # light amber
GROUP_BG_ALT = QColor(232, 245, 233)  # light green alternate


class ResultsTable(QWidget):
    delete_requested = Signal(list)   # list of file paths to delete
    open_requested = Signal(str)      # single file path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._groups = []
        self._group_items = []   # parallel list of QTreeWidgetItem (group headers)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Name / Path", "Hash (short)", "Size", "Full Path"])
        self.tree.setAlternatingRowColors(False)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.setUniformRowHeights(False)
        self.tree.setSortingEnabled(False)

        header = self.tree.header()
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_HASH, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_SIZE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_PATH, QHeaderView.ResizeMode.ResizeToContents)
        header.setMinimumSectionSize(80)

        layout.addWidget(self.tree)

        # Bulk action buttons
        btn_row = QHBoxLayout()
        self.btn_select_all = QPushButton("Check All Dupes")
        self.btn_select_all.setToolTip("Check all files except the first in each group")
        self.btn_select_none = QPushButton("Uncheck All")
        self.btn_keep_newest = QPushButton("Auto-Keep Newest")
        self.btn_keep_newest.setToolTip("Keep the most recently modified file in each group")
        self.btn_keep_oldest = QPushButton("Auto-Keep Oldest")
        self.btn_keep_oldest.setToolTip("Keep the oldest file in each group")
        for btn in (self.btn_select_all, self.btn_select_none, self.btn_keep_newest, self.btn_keep_oldest):
            btn_row.addWidget(btn)
        btn_row.addStretch()

        self.lbl_checked = QLabel("0 files checked")
        btn_row.addWidget(self.lbl_checked)
        layout.addLayout(btn_row)

        # Bottom action bar
        action_row = QHBoxLayout()
        self.btn_delete = QPushButton("Delete Checked to Recycle Bin")
        self.btn_delete.setObjectName("btnDelete")
        self.btn_delete.setMinimumHeight(32)
        self.btn_open_explorer = QPushButton("Open in Explorer")
        self.btn_export = QPushButton("Export CSV")
        action_row.addWidget(self.btn_delete)
        action_row.addWidget(self.btn_open_explorer)
        action_row.addWidget(self.btn_export)
        action_row.addStretch()
        layout.addLayout(action_row)

        # Connections
        self.btn_select_all.clicked.connect(self._select_all_dupes)
        self.btn_select_none.clicked.connect(self._select_none)
        self.btn_keep_newest.clicked.connect(self._auto_keep_newest)
        self.btn_keep_oldest.clicked.connect(self._auto_keep_oldest)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_open_explorer.clicked.connect(self._on_open_explorer)
        self.btn_export.clicked.connect(self._on_export)
        self.tree.itemChanged.connect(self._update_checked_label)

    def load_results(self, groups: list):
        self.tree.blockSignals(True)
        self.tree.clear()
        self._groups = groups
        self._group_items = []

        for idx, group in enumerate(groups):
            bg = GROUP_BG if idx % 2 == 0 else GROUP_BG_ALT
            # Group header item
            header_item = QTreeWidgetItem()
            short_hash = group.hash[:12] + "..."
            header_item.setText(COL_NAME, f"[{group.count} files]  Wasted: {human_size(group.wasted_bytes)}")
            header_item.setText(COL_HASH, short_hash)
            header_item.setText(COL_SIZE, human_size(group.size))
            header_item.setText(COL_PATH, "")
            header_item.setToolTip(COL_HASH, group.hash)
            header_item.setData(0, Qt.ItemDataRole.UserRole, ("group", idx))

            bold = QFont()
            bold.setBold(True)
            header_item.setFont(COL_NAME, bold)
            for col in range(4):
                header_item.setBackground(col, QBrush(bg))

            # File children
            for fi in group.files:
                child = QTreeWidgetItem(header_item)
                fname = os.path.basename(fi.path)
                child.setText(COL_NAME, fname)
                child.setText(COL_HASH, "")
                child.setText(COL_SIZE, human_size(fi.size))
                child.setText(COL_PATH, fi.path)
                child.setToolTip(COL_PATH, fi.path)
                child.setToolTip(COL_NAME, fi.path)
                child.setCheckState(COL_NAME, Qt.CheckState.Unchecked)
                child.setData(0, Qt.ItemDataRole.UserRole, ("file", fi.path, fi.modified))

            self.tree.addTopLevelItem(header_item)
            header_item.setExpanded(True)
            self._group_items.append(header_item)

        self.tree.blockSignals(False)
        self._update_checked_label()

    def add_group(self, group, idx: int):
        """Add a single group (for streaming results)."""
        self._groups.append(group)
        real_idx = len(self._groups) - 1
        bg = GROUP_BG if real_idx % 2 == 0 else GROUP_BG_ALT

        self.tree.blockSignals(True)
        header_item = QTreeWidgetItem()
        short_hash = group.hash[:12] + "..."
        header_item.setText(COL_NAME, f"[{group.count} files]  Wasted: {human_size(group.wasted_bytes)}")
        header_item.setText(COL_HASH, short_hash)
        header_item.setText(COL_SIZE, human_size(group.size))
        header_item.setToolTip(COL_HASH, group.hash)
        header_item.setData(0, Qt.ItemDataRole.UserRole, ("group", real_idx))

        bold = QFont()
        bold.setBold(True)
        header_item.setFont(COL_NAME, bold)
        for col in range(4):
            header_item.setBackground(col, QBrush(bg))

        for fi in group.files:
            child = QTreeWidgetItem(header_item)
            fname = os.path.basename(fi.path)
            child.setText(COL_NAME, fname)
            child.setText(COL_SIZE, human_size(fi.size))
            child.setText(COL_PATH, fi.path)
            child.setToolTip(COL_PATH, fi.path)
            child.setToolTip(COL_NAME, fi.path)
            child.setCheckState(COL_NAME, Qt.CheckState.Unchecked)
            child.setData(0, Qt.ItemDataRole.UserRole, ("file", fi.path, fi.modified))

        self.tree.addTopLevelItem(header_item)
        header_item.setExpanded(True)
        self._group_items.append(header_item)
        self.tree.blockSignals(False)
        self._update_checked_label()

    def clear(self):
        self.tree.clear()
        self._groups = []
        self._group_items = []
        self._update_checked_label()

    def _iter_file_children(self):
        """Yield all file-level child items."""
        for i in range(self.tree.topLevelItemCount()):
            group_item = self.tree.topLevelItem(i)
            for j in range(group_item.childCount()):
                yield group_item, group_item.child(j)

    def _select_all_dupes(self):
        """Check all files except the first in each group."""
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            group_item = self.tree.topLevelItem(i)
            for j in range(group_item.childCount()):
                state = Qt.CheckState.Checked if j > 0 else Qt.CheckState.Unchecked
                group_item.child(j).setCheckState(COL_NAME, state)
        self.tree.blockSignals(False)
        self._update_checked_label()

    def _select_none(self):
        self.tree.blockSignals(True)
        for _, child in self._iter_file_children():
            child.setCheckState(COL_NAME, Qt.CheckState.Unchecked)
        self.tree.blockSignals(False)
        self._update_checked_label()

    def _auto_keep_newest(self):
        """Keep the most recently modified file; check the rest."""
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            group_item = self.tree.topLevelItem(i)
            children = [group_item.child(j) for j in range(group_item.childCount())]
            if not children:
                continue
            # Find newest by mtime
            newest_idx = max(
                range(len(children)),
                key=lambda k: children[k].data(0, Qt.ItemDataRole.UserRole)[2]
            )
            for j, child in enumerate(children):
                state = Qt.CheckState.Unchecked if j == newest_idx else Qt.CheckState.Checked
                child.setCheckState(COL_NAME, state)
        self.tree.blockSignals(False)
        self._update_checked_label()

    def _auto_keep_oldest(self):
        """Keep the oldest file; check the rest."""
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            group_item = self.tree.topLevelItem(i)
            children = [group_item.child(j) for j in range(group_item.childCount())]
            if not children:
                continue
            oldest_idx = min(
                range(len(children)),
                key=lambda k: children[k].data(0, Qt.ItemDataRole.UserRole)[2]
            )
            for j, child in enumerate(children):
                state = Qt.CheckState.Unchecked if j == oldest_idx else Qt.CheckState.Checked
                child.setCheckState(COL_NAME, state)
        self.tree.blockSignals(False)
        self._update_checked_label()

    def get_checked_paths(self) -> list:
        paths = []
        for _, child in self._iter_file_children():
            if child.checkState(COL_NAME) == Qt.CheckState.Checked:
                paths.append(child.text(COL_PATH))
        return paths

    def _update_checked_label(self, *args):
        count = len(self.get_checked_paths())
        self.lbl_checked.setText(f"{count} file{'s' if count != 1 else ''} checked")

    def remove_paths(self, deleted_paths: set):
        """Remove deleted files from tree; remove groups with < 2 files left."""
        self.tree.blockSignals(True)
        to_remove_groups = []
        for i in range(self.tree.topLevelItemCount()):
            group_item = self.tree.topLevelItem(i)
            to_remove_children = []
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                if child.text(COL_PATH) in deleted_paths:
                    to_remove_children.append(j)
            # Remove in reverse order to preserve indices
            for j in reversed(to_remove_children):
                group_item.takeChild(j)
            if group_item.childCount() < 2:
                to_remove_groups.append(i)
        for i in reversed(to_remove_groups):
            self.tree.takeTopLevelItem(i)
        self.tree.blockSignals(False)
        self._update_checked_label()

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        menu = QMenu(self)
        if data[0] == "file":
            path = data[1]
            menu.addAction("Open file", lambda: self.open_requested.emit(path))
            menu.addAction("Open containing folder", lambda: self._open_folder(path))
            menu.addAction("Keep this, delete others in group", lambda: self._keep_this(item))
            menu.addSeparator()
            check_state = item.checkState(COL_NAME)
            if check_state == Qt.CheckState.Checked:
                menu.addAction("Uncheck", lambda: item.setCheckState(COL_NAME, Qt.CheckState.Unchecked))
            else:
                menu.addAction("Check for deletion", lambda: item.setCheckState(COL_NAME, Qt.CheckState.Checked))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _open_folder(self, path: str):
        import subprocess
        folder = os.path.dirname(path)
        subprocess.Popen(["explorer", "/select,", path])

    def _keep_this(self, item):
        """Uncheck this item, check all siblings."""
        parent = item.parent()
        if not parent:
            return
        self.tree.blockSignals(True)
        for j in range(parent.childCount()):
            child = parent.child(j)
            state = Qt.CheckState.Unchecked if child is item else Qt.CheckState.Checked
            child.setCheckState(COL_NAME, state)
        self.tree.blockSignals(False)
        self._update_checked_label()

    def _on_delete(self):
        paths = self.get_checked_paths()
        if paths:
            self.delete_requested.emit(paths)

    def _on_open_explorer(self):
        selected = self.tree.selectedItems()
        for item in selected:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data[0] == "file":
                self._open_folder(data[1])
                break

    def _on_export(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "duplicate_files.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write("Group,Hash,Size,File Path\n")
                for i in range(self.tree.topLevelItemCount()):
                    group_item = self.tree.topLevelItem(i)
                    group_hash = group_item.toolTip(COL_HASH)
                    size = group_item.text(COL_SIZE)
                    for j in range(group_item.childCount()):
                        child = group_item.child(j)
                        fpath = child.text(COL_PATH)
                        f.write(f"{i+1},{group_hash},{size},{fpath}\n")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Export Error", str(e))
