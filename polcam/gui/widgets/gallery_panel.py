"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

图库面板
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Optional

import cv2
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
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)

        header_layout = QtWidgets.QHBoxLayout()
        title_label = QtWidgets.QLabel("图库")
        title_font = title_label.font()
        title_font.setBold(True)
        title_label.setFont(title_font)
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
        self.open_button.clicked.connect(self._open_selected_item)
        header_layout.addWidget(self.open_button)

        self.delete_button = QtWidgets.QPushButton("删除")
        self.delete_button.clicked.connect(self._delete_selected_item)
        header_layout.addWidget(self.delete_button)

        self.refresh_button = QtWidgets.QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        header_layout.addWidget(self.refresh_button)

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
        self.empty_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.empty_label)

        self._set_empty_state(True)
        self._update_action_state()

    def set_items(self, items: Iterable[GalleryItem]):
        items = list(items)
        self._items_by_id = {item.id: item for item in items}
        self.preview_list.clear()
        self.table.setRowCount(0)

        for item in items:
            self._append_preview_item(item)
            self._append_table_row(item)

        self.count_label.setText(f"{len(items)} 项")
        self._set_empty_state(len(items) == 0)
        self._update_action_state()

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
        image = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            return self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxWarning)

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
        return QtGui.QIcon(pixmap)

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
