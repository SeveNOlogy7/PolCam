"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

图库面板
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Iterable, List, Optional

import cv2
import numpy as np
from qtpy import QtCore, QtGui, QtWidgets

from ...core.gallery_service import GalleryItem
from ..styles import Styles

Signal = QtCore.Signal  # type: ignore[attr-defined]


class GalleryPanel(QtWidgets.QWidget):
    """展示自动保存图像的图库面板。"""

    imageActivated = Signal(str)
    deleteRequested = Signal(list)
    refreshRequested = Signal()

    VIEW_PREVIEW = 0
    VIEW_LIST = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items_by_id: dict[int, GalleryItem] = {}
        # 键是 (路径, mtime_ns)：同一次刷新之间条目没变就不必再解一遍全尺寸图
        self._thumbnails: dict[tuple[str, int], QtGui.QIcon] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)

        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(Styles.SPACING_MEDIUM)
        title_label = QtWidgets.QLabel("图库")
        title_label.setFont(Styles.get_bold_font(Styles.FONT_LARGE))
        header_layout.addWidget(title_label)

        header_layout.addStretch(1)

        self.count_label = QtWidgets.QLabel("0 项")
        header_layout.addWidget(self.count_label)

        self.view_mode_combo = QtWidgets.QComboBox()
        Styles.apply_combobox_style(self.view_mode_combo)
        self.view_mode_combo.addItem("预览图", self.VIEW_PREVIEW)
        self.view_mode_combo.addItem("列表", self.VIEW_LIST)
        self.view_mode_combo.currentIndexChanged.connect(self._on_view_mode_changed)
        header_layout.addWidget(self.view_mode_combo)

        self.open_button = QtWidgets.QPushButton("读取")
        self.open_button.setToolTip("在上方图像区中查看选中的图像")
        self.open_button.clicked.connect(self._open_selected_item)
        header_layout.addWidget(self.open_button)

        self.delete_button = QtWidgets.QPushButton("删除")
        self.delete_button.setToolTip("删除选中的图像文件及图库记录")
        self.delete_button.clicked.connect(self._delete_selected_item)
        header_layout.addWidget(self.delete_button)

        self.refresh_button = QtWidgets.QPushButton("刷新")
        self.refresh_button.setToolTip("重新扫描自动保存目录")
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        header_layout.addWidget(self.refresh_button)

        for button in (self.open_button, self.delete_button, self.refresh_button):
            Styles.apply_button_style(button)

        layout.addLayout(header_layout)

        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.preview_list = QtWidgets.QListWidget()
        self.preview_list.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.preview_list.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.preview_list.setMovement(QtWidgets.QListView.Movement.Static)
        self.preview_list.setIconSize(QtCore.QSize(120, 120))
        self.preview_list.setSpacing(8)
        self.preview_list.setWordWrap(True)
        self.preview_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.preview_list.itemDoubleClicked.connect(self._on_preview_item_activated)
        self.preview_list.itemSelectionChanged.connect(self._update_action_state)
        self.stack.addWidget(self.preview_list)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["文件名", "采集时间", "尺寸", "格式", "路径"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.cellDoubleClicked.connect(self._on_table_item_activated)
        self.table.itemSelectionChanged.connect(self._update_action_state)
        self.stack.addWidget(self.table)

        self.empty_label = QtWidgets.QLabel("暂无自动保存图像")
        self.empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        empty_palette = self.empty_label.palette()
        empty_palette.setColor(
            QtGui.QPalette.WindowText,
            empty_palette.color(QtGui.QPalette.PlaceholderText),
        )
        self.empty_label.setPalette(empty_palette)
        layout.addWidget(self.empty_label, 1)

        self._set_empty_state(True)
        self._update_action_state()

    def set_items(self, items: Iterable[GalleryItem]):
        items = list(items)
        # 清空之前先把选中的项记下来：每次自动保存后都会刷新一次，而 clear()/setRowCount(0)
        # 会把选区整个抹掉，用户那边表现为「刚点的项没了，读取/删除当场变灰」。
        kept_ids = set(self.selected_item_ids())
        self._items_by_id = {item.id: item for item in items}
        # 缓存随面板上还有没有这张图走，不然一个长会话里解过的缩略图会一直攒着
        live_paths = {item.file_path for item in items}
        self._thumbnails = {
            key: icon for key, icon in self._thumbnails.items() if key[0] in live_paths
        }
        self.preview_list.clear()
        self.table.setRowCount(0)

        for item in items:
            self._append_preview_item(item)
            self._append_table_row(item)

        self._restore_selection(kept_ids)
        self.count_label.setText(f"{len(items)} 项")
        self._set_empty_state(len(items) == 0)
        self._update_action_state()

    def _restore_selection(self, item_ids: set):
        """把刷新前选中的那些项重新选上；已经不存在的项自然落选。"""
        if not item_ids:
            return
        if self.stack.currentIndex() == self.VIEW_PREVIEW:
            for row in range(self.preview_list.count()):
                entry = self.preview_list.item(row)
                item_id = entry.data(QtCore.Qt.ItemDataRole.UserRole)
                if item_id is not None and int(item_id) in item_ids:
                    entry.setSelected(True)
            return

        selection_model = self.table.selectionModel()
        if selection_model is None:
            return
        flags = (QtCore.QItemSelectionModel.SelectionFlag.Select
                 | QtCore.QItemSelectionModel.SelectionFlag.Rows)
        for row in range(self.table.rowCount()):
            cell = self.table.item(row, 0)
            if cell is None:
                continue
            item_id = cell.data(QtCore.Qt.ItemDataRole.UserRole)
            if item_id is not None and int(item_id) in item_ids:
                # 逐行 select 天然是并集（Select 不带 Clear 时不会洗掉已选的行），
                # 这里要的就是把多选一项项叠回来
                selection_model.select(selection_model.model().index(row, 0), flags)

    def _append_preview_item(self, item: GalleryItem):
        list_item = QtWidgets.QListWidgetItem(self._create_thumbnail_icon(item.file_path), item.file_name)
        list_item.setData(QtCore.Qt.ItemDataRole.UserRole, item.id)
        tooltip = [
            f"文件: {item.file_name}",
            f"时间: {self._format_datetime(item.captured_at)}",
            f"尺寸: {item.width} x {item.height}",
            f"路径: {item.file_path}",
        ]
        list_item.setToolTip("\n".join(tooltip))
        self.preview_list.addItem(list_item)

    def _append_table_row(self, item: GalleryItem):
        row = self.table.rowCount()
        self.table.insertRow(row)

        values = [
            item.file_name,
            self._format_datetime(item.captured_at),
            f"{item.width} x {item.height}",
            item.file_format.upper(),
            item.file_path,
        ]
        for column, value in enumerate(values):
            table_item = QtWidgets.QTableWidgetItem(value)
            table_item.setData(QtCore.Qt.ItemDataRole.UserRole, item.id)
            self.table.setItem(row, column, table_item)

    def _create_thumbnail_icon(self, file_path: str) -> QtGui.QIcon:
        try:
            signature = (file_path, os.stat(file_path).st_mtime_ns)
        except OSError:
            # 文件已经不在了。图库行是按 captured_at DESC 排的，让这一行把异常抛出去
            # 就等于其后每次刷新都断在第一张图上，整个面板从此空白。
            return self._placeholder_icon()

        cached = self._thumbnails.get(signature)
        if cached is not None:
            return cached

        icon, cached = self._decode_thumbnail_icon(file_path)
        if cached:
            # 读失败的结果不进缓存：文件被别的进程占用、杀毒正在扫这类情况是会自愈的，
            # 按 (路径, mtime) 存住一个占位图标就等于永远显示占位图标
            self._thumbnails[signature] = icon
        return icon

    def _decode_thumbnail_icon(self, file_path: str) -> tuple[QtGui.QIcon, bool]:
        """返回 (图标, 是否值得缓存)。

        cv2.imdecode 抛的是 cv2.error，它不是 OSError 的子孙，只兜 OSError 会漏 ——
        而 set_items 是先清空视图再逐条填，异常一冒出来整个面板就剩 0 行。
        """
        # cv2.imread 按进程 ANSI 代码页解析路径，中文路径下读不出来，所以自己按字节读
        try:
            image = cv2.imdecode(np.fromfile(file_path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        except (OSError, cv2.error):
            return self._placeholder_icon(), False
        if image is None:
            # 预览读不出属于缺图而非错误，用中性文件图标，避免整排警告三角
            return self._placeholder_icon(), False

        height, width = image.shape
        qimage = QtGui.QImage(
            image.data,
            width,
            height,
            width,
            QtGui.QImage.Format.Format_Grayscale8,
        ).copy()
        pixmap = QtGui.QPixmap.fromImage(qimage)
        pixmap = pixmap.scaled(
            120,
            120,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        return QtGui.QIcon(pixmap), True

    def _placeholder_icon(self) -> QtGui.QIcon:
        return self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileIcon)

    def _format_datetime(self, timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

    def _set_empty_state(self, is_empty: bool):
        has_items = not is_empty
        self.stack.setVisible(has_items)
        self.empty_label.setVisible(is_empty)
        selected_count = len(self.selected_item_ids())
        self.open_button.setEnabled(has_items and selected_count == 1)
        self.delete_button.setEnabled(has_items and selected_count > 0)

    def _on_view_mode_changed(self):
        view_mode = self.view_mode_combo.currentData(QtCore.Qt.ItemDataRole.UserRole)
        self.stack.setCurrentIndex(int(view_mode))
        self._update_action_state()

    def current_item_id(self) -> Optional[int]:
        if self.stack.currentIndex() == self.VIEW_PREVIEW:
            current_item = self.preview_list.currentItem()
            if current_item is None:
                return None
            return current_item.data(QtCore.Qt.ItemDataRole.UserRole)

        current_row = self.table.currentRow()
        if current_row < 0:
            return None
        current_item = self.table.item(current_row, 0)
        if current_item is None:
            return None
        return current_item.data(QtCore.Qt.ItemDataRole.UserRole)

    def current_item(self) -> Optional[GalleryItem]:
        item_id = self.current_item_id()
        if item_id is None:
            return None
        return self._items_by_id.get(int(item_id))

    def selected_item_ids(self) -> List[int]:
        selected_ids: List[int] = []
        if self.stack.currentIndex() == self.VIEW_PREVIEW:
            for item in self.preview_list.selectedItems():
                item_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
                if item_id is not None:
                    selected_ids.append(int(item_id))
            return selected_ids

        selected_rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        for row in selected_rows:
            item = self.table.item(row, 0)
            if item is None:
                continue
            item_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if item_id is not None:
                selected_ids.append(int(item_id))
        return selected_ids

    def _open_selected_item(self):
        selected_ids = self.selected_item_ids()
        if len(selected_ids) != 1:
            return
        item = self._items_by_id.get(selected_ids[0])
        if item is not None:
            self.imageActivated.emit(item.file_path)

    def _delete_selected_item(self):
        selected_ids = self.selected_item_ids()
        if selected_ids:
            self.deleteRequested.emit(selected_ids)

    def _on_preview_item_activated(self, item: QtWidgets.QListWidgetItem):
        item_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
        gallery_item = self._items_by_id.get(int(item_id))
        if gallery_item is not None:
            self.imageActivated.emit(gallery_item.file_path)

    def _on_table_item_activated(self, row: int, _column: int):
        item = self.table.item(row, 0)
        if item is None:
            return
        item_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
        gallery_item = self._items_by_id.get(int(item_id))
        if gallery_item is not None:
            self.imageActivated.emit(gallery_item.file_path)

    def _update_action_state(self):
        selected_count = len(self.selected_item_ids())
        self.open_button.setEnabled(selected_count == 1)
        self.delete_button.setEnabled(selected_count > 0)
