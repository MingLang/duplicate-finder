import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLabel, QHeaderView, QAbstractItemView, QMenu,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont

from utils.format import human_size

COL_NAME     = 0
COL_SIZE     = 1
COL_FILES    = 2
COL_DUP      = 3
COL_DUP_PCT  = 4
COL_COMMENT  = 5

# Colour gradient stops: (ratio, (R, G, B))
_STOPS = [
    (0.00, (255, 255, 255)),  # white  — no duplicates
    (0.05, (255, 252, 200)),  # cream
    (0.20, (255, 235, 120)),  # yellow
    (0.50, (255, 190, 100)),  # orange
    (1.00, (255, 140, 140)),  # salmon-red
]

_COLOR_EMPTY   = QColor(248, 248, 248)
_COLOR_RED     = QColor(180,  30,  30)   # comment text: delete candidate
_COLOR_ORANGE  = QColor(180,  90,   0)   # comment text: worth reviewing
_COLOR_GRAY    = QColor(100, 100, 100)   # comment text: informational

# Folder names (case-insensitive) that are clearly regeneratable / temporary
_CACHE_NAMES = {
    '__pycache__', '.cache', 'cache', 'caches',
    'temp', 'tmp', 'temporary',
    'node_modules', '.npm', '.yarn', '.pnpm-store',
    '.gradle', '.m2', '.ivy2',
    'obj', 'debug', 'release',          # build output
    'logs', 'log',
    '.mypy_cache', '.pytest_cache', '.ruff_cache', '.tox',
    'dist-info', '__MACOSX',
}

# Keywords in folder name that suggest it's a backup / copy
_BACKUP_KEYWORDS = ('backup', 'bak', ' bak', '_bak', 'old', '_old',
                    'copy', 'copies', 'archive', 'archived')


def _dup_color(ratio: float, has_files: bool) -> QColor:
    if not has_files or ratio <= 0:
        return _COLOR_EMPTY
    for i in range(len(_STOPS) - 1):
        r0, c0 = _STOPS[i]
        r1, c1 = _STOPS[i + 1]
        if ratio <= r1:
            t = (ratio - r0) / (r1 - r0)
            r = int(c0[0] + t * (c1[0] - c0[0]))
            g = int(c0[1] + t * (c1[1] - c0[1]))
            b = int(c0[2] + t * (c1[2] - c0[2]))
            return QColor(r, g, b)
    return QColor(*_STOPS[-1][1])


def _make_comment(node) -> tuple:
    """
    Return (comment_text, text_color) for the Comments column.

    Priority (highest first):
      1. All files are duplicates                  → red,    delete candidate
      2. Known regeneratable cache folder           → orange, safe to clean
      3. Backup-named folder with ≥50 % duplicates → orange, worth reviewing
      4. ≥80 % duplicate content                   → orange, likely redundant
      5. ≥30 % duplicate content                   → gray,   informational
      6. No notable pattern                         → ("", None)
    """
    if node.total_files == 0:
        return ("", None)

    ratio = node.dup_ratio
    name_lower = node.name.lower().strip()

    # 1. Known regeneratable cache / build-artifact folder (checked first —
    #    these are always safe to delete regardless of dup ratio)
    if name_lower in _CACHE_NAMES:
        if ratio > 0:
            return (f"Regeneratable cache — {ratio:.0%} duplicates, safe to delete", _COLOR_ORANGE)
        return ("Regeneratable cache — safe to delete", _COLOR_ORANGE)

    # 2. Fully duplicated folder (not a known cache)
    if ratio == 1.0:
        return ("All files exist elsewhere — redundant copy", _COLOR_RED)

    # 3. Backup / copy folder with meaningful duplicate content
    is_backup = any(kw in name_lower for kw in _BACKUP_KEYWORDS)
    if is_backup and ratio >= 0.5:
        return (f"Backup folder — {ratio:.0%} of files are duplicates", _COLOR_ORANGE)

    # 4. Very high duplicate ratio
    if ratio >= 0.8:
        return (f"{ratio:.0%} duplicate content — likely a redundant copy", _COLOR_ORANGE)

    # 5. Moderate duplicate ratio
    if ratio >= 0.3:
        return (f"{ratio:.0%} of files are duplicated elsewhere", _COLOR_GRAY)

    return ("", None)


# Sentinel for lazy-loaded dummy children
_DUMMY = object()


class FolderTreeView(QWidget):
    """
    Explorer-style folder size / duplicate heatmap with junk-file suggestions.

    Columns: Folder | Total Size | Files | Dup Files | Dup % | Comments
    Row background is colour-scaled by duplicate ratio (white → red).
    The Comments column suggests whether a folder contains disposable content.
    """

    open_requested = Signal(str)  # folder path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._roots = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.lbl_summary = QLabel(
            "Run a scan, then switch to this tab to view the folder size map."
        )
        self.lbl_summary.setContentsMargins(6, 4, 6, 4)
        layout.addWidget(self.lbl_summary)

        # Colour legend
        legend_row = QHBoxLayout()
        legend_row.setContentsMargins(6, 0, 6, 2)
        legend_row.addWidget(QLabel("Dup ratio:"))
        for label, ratio in [("0 %", 0.0), ("5 %", 0.05), ("20 %", 0.20),
                              ("50 %", 0.50), ("100 %", 1.0)]:
            swatch = QLabel(f"  {label}  ")
            swatch.setAutoFillBackground(True)
            pal = swatch.palette()
            pal.setColor(swatch.backgroundRole(), _dup_color(ratio, True))
            swatch.setPalette(pal)
            legend_row.addWidget(swatch)
        legend_row.addStretch()
        layout.addLayout(legend_row)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels(
            ["Folder", "Total Size", "Files", "Dup Files", "Dup %", "Comments"]
        )
        self.tree.setAlternatingRowColors(False)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.setUniformRowHeights(True)

        hdr = self.tree.header()
        hdr.setSectionResizeMode(COL_NAME,    QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(COL_SIZE,    QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(COL_FILES,   QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(COL_DUP,     QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(COL_DUP_PCT, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(COL_COMMENT, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setMinimumSectionSize(60)

        self.tree.itemExpanded.connect(self._on_item_expanded)
        layout.addWidget(self.tree)

    # ------------------------------------------------------------------
    # Load / clear
    # ------------------------------------------------------------------

    def load_tree(self, roots: list):
        self.tree.clear()
        self._roots = roots
        for node in roots:
            item = self._make_item(node)
            self.tree.addTopLevelItem(item)
            item.setExpanded(True)
        self._update_summary()

    def clear(self):
        self.tree.clear()
        self._roots = []
        self.lbl_summary.setText(
            "Run a scan, then switch to this tab to view the folder size map."
        )

    # ------------------------------------------------------------------
    # Item creation (lazy)
    # ------------------------------------------------------------------

    def _make_item(self, node) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        self._populate_item(item, node)
        if node.children:
            dummy = QTreeWidgetItem(item)
            dummy.setData(0, Qt.ItemDataRole.UserRole, _DUMMY)
        return item

    def _populate_item(self, item: QTreeWidgetItem, node):
        item.setText(COL_NAME,  node.name)
        item.setText(COL_SIZE,  human_size(node.total_size))
        item.setText(COL_FILES, f"{node.total_files:,}" if node.total_files else "—")

        if node.total_dup_files:
            item.setText(COL_DUP,     f"{node.total_dup_files:,}")
            item.setText(COL_DUP_PCT, f"{node.dup_ratio:.1%}")
        else:
            item.setText(COL_DUP,     "—")
            item.setText(COL_DUP_PCT, "—")

        item.setToolTip(COL_NAME, node.path)

        # Row background: duplicate heat
        bg = _dup_color(node.dup_ratio, node.total_files > 0)
        brush = QBrush(bg)
        for col in range(6):
            item.setBackground(col, brush)

        # Bold Dup % when notable
        if node.dup_ratio >= 0.5:
            bold = QFont()
            bold.setBold(True)
            item.setFont(COL_DUP_PCT, bold)

        # Comment
        comment_text, comment_color = _make_comment(node)
        if comment_text:
            item.setText(COL_COMMENT, comment_text)
            if comment_color:
                item.setForeground(COL_COMMENT, QBrush(comment_color))
            italic = QFont()
            italic.setItalic(True)
            item.setFont(COL_COMMENT, italic)

        item.setData(0, Qt.ItemDataRole.UserRole, node)

    def _on_item_expanded(self, item: QTreeWidgetItem):
        if item.childCount() == 1:
            dummy = item.child(0)
            if dummy.data(0, Qt.ItemDataRole.UserRole) is _DUMMY:
                node = item.data(0, Qt.ItemDataRole.UserRole)
                item.takeChild(0)
                for child_node in node.children:
                    item.addChild(self._make_item(child_node))

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _update_summary(self):
        if not self._roots:
            self.lbl_summary.setText("No folders to display.")
            return
        total_size  = sum(n.total_size     for n in self._roots)
        total_files = sum(n.total_files    for n in self._roots)
        total_dup   = sum(n.total_dup_files for n in self._roots)
        ratio = total_dup / total_files if total_files else 0
        self.lbl_summary.setText(
            f"{human_size(total_size)} across {total_files:,} files — "
            f"{total_dup:,} duplicate files ({ratio:.1%})   "
            "| Row colour = duplicate ratio   | Comments = cleanup suggestions"
        )

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        node = item.data(0, Qt.ItemDataRole.UserRole)
        if not node or node is _DUMMY:
            return
        menu = QMenu(self)
        menu.addAction(
            "Open in Explorer",
            lambda: self.open_requested.emit(node.path),
        )
        menu.exec(self.tree.viewport().mapToGlobal(pos))
