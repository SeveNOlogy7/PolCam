"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.

相机选择对话框
提供多相机场景下的设备选择功能
"""

from qtpy import QtWidgets, QtCore, QtGui
from .styles import Styles
from ..core.camera_module import CameraModule
import logging


class CameraSelectDialog(QtWidgets.QDialog):
    """相机选择对话框

    当检测到多个相机时显示，允许用户:
    1. 查看可用相机列表
    2. 选择并连接/断开相机
    3. 刷新设备列表
    """

    def __init__(self, camera: CameraModule, device_list: list, parent=None):
        super().__init__(parent)
        self._logger = logging.getLogger("polcam.gui.CameraSelectDialog")
        self._camera = camera
        self._device_list = device_list
        self._connected_index = None  # 当前对话框内连接的设备索引

        self.setWindowTitle("选择相机")
        self.setMinimumSize(600, 400)
        self.setModal(True)

        self._setup_ui()
        self._setup_connections()
        self._populate_table()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 信息标签
        self._info_label = QtWidgets.QLabel(
            f"检测到 {len(self._device_list)} 个相机设备，请选择要连接的相机："
        )
        self._info_label.setFont(Styles.get_font(Styles.FONT_MEDIUM))
        layout.addWidget(self._info_label)

        # 相机列表表格
        self._table = QtWidgets.QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["序号", "型号", "序列号", "IP地址", "状态"])
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setFont(Styles.get_font(Styles.FONT_MEDIUM))
        self._table.horizontalHeader().setFont(Styles.get_font(Styles.FONT_MEDIUM))
        layout.addWidget(self._table)

        # 按钮行
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        self._connect_btn = QtWidgets.QPushButton("连接")
        self._refresh_btn = QtWidgets.QPushButton("刷新")
        self._return_btn = QtWidgets.QPushButton("返回")

        for btn in [self._connect_btn, self._refresh_btn, self._return_btn]:
            Styles.apply_button_style(btn)
            btn.setMinimumWidth(80)
            btn_layout.addWidget(btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _setup_connections(self):
        self._connect_btn.clicked.connect(self._handle_connect)
        self._refresh_btn.clicked.connect(self._handle_refresh)
        self._return_btn.clicked.connect(self._handle_return)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def _populate_table(self):
        """用设备列表填充表格"""
        self._table.setRowCount(len(self._device_list))
        for row, info in enumerate(self._device_list):
            self._table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(info.get('index', row + 1))))
            self._table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(info.get('model_name', ''))))
            self._table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(info.get('sn', ''))))
            self._table.setItem(row, 3, QtWidgets.QTableWidgetItem(str(info.get('ip', ''))))

            access = info.get('access_status', 0)
            status_text = self._access_status_text(access)
            self._table.setItem(row, 4, QtWidgets.QTableWidgetItem(status_text))

        self._table.resizeColumnsToContents()
        self._update_button_states()

    @staticmethod
    def _access_status_text(access_status) -> str:
        """将 GxAccessStatus 转为中文显示"""
        mapping = {0: "未知", 1: "可用", 2: "只读", 3: "不可访问"}
        return mapping.get(access_status, "未知")

    def _on_selection_changed(self):
        self._update_button_states()

    def _get_selected_device_index(self):
        """获取当前选中行对应的设备索引，无选中返回 None"""
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        if row < 0 or row >= len(self._device_list):
            return None
        return self._device_list[row].get('index', row + 1)

    def _update_button_states(self):
        """根据选择和连接状态更新按钮"""
        selected_index = self._get_selected_device_index()
        has_selection = selected_index is not None
        is_connected = self._camera.is_connected()

        if is_connected and has_selection and selected_index == self._connected_index:
            # 选中的是已连接的设备 → 显示"断开"
            self._connect_btn.setText("断开")
            self._connect_btn.setEnabled(True)
        elif is_connected:
            # 已连接但选中的是其他设备 → 禁用（需先断开）
            self._connect_btn.setText("连接")
            self._connect_btn.setEnabled(False)
        else:
            # 未连接 → 有选中则启用"连接"
            self._connect_btn.setText("连接")
            self._connect_btn.setEnabled(has_selection)

    def _handle_connect(self):
        """连接到或断开所选相机"""
        if self._camera.is_connected():
            # 断开当前连接
            self._camera.stop()
            self._connected_index = None
            self._logger.info("已在对话框中断开相机")
            self._handle_refresh()  # 断开后刷新列表
            return

        selected_index = self._get_selected_device_index()
        if selected_index is None:
            return

        # 查找选中行的设备信息用于日志
        selected = self._table.selectionModel().selectedRows()
        row = selected[0].row()
        device_info = self._device_list[row]

        try:
            self._camera.set_target_device_index(selected_index)
            success = self._camera.start()
            if success:
                self._connected_index = selected_index
                model = device_info.get('model_name', '')
                sn = device_info.get('sn', '')
                self._info_label.setText(f"已连接: {model} (SN: {sn})")
                self._logger.info(f"在对话框中连接相机成功: index={selected_index}")
            else:
                QtWidgets.QMessageBox.warning(self, "连接失败", "无法连接到所选相机")
        except Exception as e:
            self._logger.error(f"连接相机时发生错误: {str(e)}")
            QtWidgets.QMessageBox.warning(self, "连接错误", f"连接相机时发生错误: {str(e)}")

        self._update_button_states()

    def _handle_refresh(self):
        """重新枚举相机并刷新表格"""
        try:
            count, device_list = self._camera.enumerate_devices()
            if device_list is None:
                device_list = []
            self._device_list = device_list
            self._populate_table()

            if count == 0:
                self._info_label.setText("未检测到相机设备")
            elif not self._camera.is_connected():
                self._info_label.setText(f"检测到 {count} 个相机设备，请选择要连接的相机：")
        except Exception as e:
            self._logger.error(f"刷新设备列表失败: {str(e)}")
            QtWidgets.QMessageBox.warning(self, "刷新失败", f"刷新设备列表失败: {str(e)}")

    def _handle_return(self):
        """关闭对话框，根据连接状态返回 accept/reject"""
        if self._camera.is_connected():
            self.accept()
        else:
            self.reject()

    def closeEvent(self, event: QtGui.QCloseEvent):
        """处理窗口关闭（X 按钮），与"返回"行为一致"""
        if self._camera.is_connected():
            self.accept()
        else:
            self.reject()
