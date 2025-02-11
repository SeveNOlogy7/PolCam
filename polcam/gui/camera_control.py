"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtCore
from qtpy import QtGui
from .styles import Styles

class CameraControl(QtWidgets.QWidget):
    # 扩展信号定义
    connect_clicked = QtCore.Signal(bool)
    capture_clicked = QtCore.Signal()
    stream_clicked = QtCore.Signal(bool)
    exposure_changed = QtCore.Signal(float)
    exposure_auto_changed = QtCore.Signal(bool)
    exposure_once_clicked = QtCore.Signal()
    gain_changed = QtCore.Signal(float)
    gain_auto_changed = QtCore.Signal(bool)
    gain_once_clicked = QtCore.Signal()
    wb_auto_changed = QtCore.Signal(bool)
    wb_once_clicked = QtCore.Signal()
    angle_changed = QtCore.Signal(int)
    color_mode_changed = QtCore.Signal(bool)  # True为彩色，False为灰度
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 连接和采集控制
        self.connect_btn = QtWidgets.QPushButton("连接相机")
        self.connect_btn.setCheckable(True)
        layout.addWidget(self.connect_btn)
        
        self.capture_btn = QtWidgets.QPushButton("单帧采集")
        self.stream_btn = QtWidgets.QPushButton("连续采集")
        self.stream_btn.setCheckable(True)
        layout.addWidget(self.capture_btn)
        layout.addWidget(self.stream_btn)
        
        # 曝光控制组
        exposure_group = QtWidgets.QGroupBox("曝光控制")
        Styles.apply_group_title_style(exposure_group)
        exposure_layout = QtWidgets.QVBoxLayout(exposure_group)
        
        # 曝光时间设置
        exposure_value_layout = QtWidgets.QHBoxLayout()
        exposure_value_layout.addWidget(QtWidgets.QLabel("曝光时间:"))
        self.exposure_spin = QtWidgets.QDoubleSpinBox()
        self.exposure_spin.setDecimals(1)
        self.exposure_spin.setFont(QtGui.QFont("", 11))
        self.exposure_spin.setMinimumHeight(30)
        exposure_value_layout.addWidget(self.exposure_spin)
        exposure_layout.addLayout(exposure_value_layout)
        
        # 曝光自动控制
        exposure_auto_layout = QtWidgets.QHBoxLayout()
        self.exposure_auto = QtWidgets.QCheckBox("自动")
        self.exposure_auto.setFont(QtGui.QFont("", 11))
        self.exposure_once = QtWidgets.QPushButton("单次")
        self.exposure_once.setFont(QtGui.QFont("", 11))
        self.exposure_once.setMinimumHeight(30)
        exposure_auto_layout.addWidget(self.exposure_auto)
        exposure_auto_layout.addWidget(self.exposure_once)
        exposure_layout.addLayout(exposure_auto_layout)
        
        layout.addWidget(exposure_group)
        
        # 增益控制组
        gain_group = QtWidgets.QGroupBox("增益控制")
        Styles.apply_group_title_style(gain_group)
        gain_layout = QtWidgets.QVBoxLayout(gain_group)
        
        # 增益值设置
        gain_value_layout = QtWidgets.QHBoxLayout()
        gain_value_layout.addWidget(QtWidgets.QLabel("增益:"))
        self.gain_spin = QtWidgets.QDoubleSpinBox()
        self.gain_spin.setDecimals(1)
        self.gain_spin.setFont(QtGui.QFont("", 11))
        self.gain_spin.setMinimumHeight(30)
        gain_value_layout.addWidget(self.gain_spin)
        gain_layout.addLayout(gain_value_layout)
        
        # 增益自动控制
        gain_auto_layout = QtWidgets.QHBoxLayout()
        self.gain_auto = QtWidgets.QCheckBox("自动")
        self.gain_auto.setFont(QtGui.QFont("", 11))
        self.gain_once = QtWidgets.QPushButton("单次")
        self.gain_once.setFont(QtGui.QFont("", 11))
        self.gain_once.setMinimumHeight(30)
        gain_auto_layout.addWidget(self.gain_auto)
        gain_auto_layout.addWidget(self.gain_once)
        gain_layout.addLayout(gain_auto_layout)
        
        layout.addWidget(gain_group)
        
        # 角度选择控制组 - 确保添加在参数布局中的正确位置
        self.angle_group = QtWidgets.QGroupBox("角度选择")
        Styles.apply_group_title_style(self.angle_group)
        angle_layout = QtWidgets.QHBoxLayout(self.angle_group)
        
        angle_label = QtWidgets.QLabel("偏振角度:")
        angle_label.setFont(QtGui.QFont("", 11))
        angle_layout.addWidget(angle_label)
        
        self.angle_combo = QtWidgets.QComboBox()
        self.angle_combo.setFont(QtGui.QFont("", 11))
        self.angle_combo.setMinimumHeight(30)
        self.angle_combo.addItems(["0°", "45°", "90°", "135°"])
        Styles.apply_combobox_style(self.angle_combo)
        angle_layout.addWidget(self.angle_combo)
        
        layout.addWidget(self.angle_group)
        self.angle_group.setVisible(False)  # 初始时隐藏
        
        # 白平衡控制组
        self.wb_group = QtWidgets.QGroupBox("白平衡控制")  # 修改变量名以便访问
        Styles.apply_group_title_style(self.wb_group)
        wb_layout = QtWidgets.QHBoxLayout(self.wb_group)
        
        self.wb_auto = QtWidgets.QCheckBox("自动")
        self.wb_auto.setFont(QtGui.QFont("", 11))
        self.wb_once = QtWidgets.QPushButton("单次")
        self.wb_once.setFont(QtGui.QFont("", 11))
        self.wb_once.setMinimumHeight(30)
        wb_layout.addWidget(self.wb_auto)
        wb_layout.addWidget(self.wb_once)
        layout.addWidget(self.wb_group)
        
        # 添加偏振分析模式的颜色设置组
        self.pol_color_group = QtWidgets.QGroupBox("合成图像设置")
        Styles.apply_group_title_style(self.pol_color_group)
        pol_color_layout = QtWidgets.QVBoxLayout(self.pol_color_group)
        
        # 添加彩色/灰度选择
        self.color_mode_combo = QtWidgets.QComboBox()
        self.color_mode_combo.addItems(["灰度图像", "彩色图像"])
        self.color_mode_combo.setFont(QtGui.QFont("", 11))
        self.color_mode_combo.setMinimumHeight(30)
        Styles.apply_combobox_style(self.color_mode_combo)
        pol_color_layout.addWidget(self.color_mode_combo)
        
        # 添加白平衡控制（初始隐藏）
        self.pol_wb_auto = QtWidgets.QCheckBox("自动白平衡")
        self.pol_wb_once = QtWidgets.QPushButton("单次白平衡")
        self.pol_wb_auto.setFont(QtGui.QFont("", 11))
        self.pol_wb_once.setFont(QtGui.QFont("", 11))
        self.pol_wb_once.setMinimumHeight(30)
        
        wb_layout = QtWidgets.QHBoxLayout()
        wb_layout.addWidget(self.pol_wb_auto)
        wb_layout.addWidget(self.pol_wb_once)
        pol_color_layout.addLayout(wb_layout)
        
        layout.addWidget(self.pol_color_group)
        self.pol_color_group.setVisible(False)  # 初始隐藏
        
        layout.addStretch()
        
        # 初始状态设置
        self.capture_btn.setEnabled(False)
        self.stream_btn.setEnabled(False)
        
        # 设置固定的尺寸策略
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.Preferred
        )
        
        # 应用样式到所有按钮
        for btn in [self.connect_btn, self.capture_btn, self.stream_btn,
                   self.exposure_once, self.gain_once, self.wb_once]:
            Styles.apply_button_style(btn)
        
        # 应用样式到所有数值框
        for spinbox in [self.exposure_spin, self.gain_spin]:
            Styles.apply_spinbox_style(spinbox)
        
        # 应用样式到所有复选框
        for checkbox in [self.exposure_auto, self.gain_auto, self.wb_auto]:
            Styles.apply_checkbox_style(checkbox)
        
    def setup_connections(self):
        # 设置参数范围
        self.exposure_spin.setRange(1.0, 1000000.0)  # 1us - 1s，使用浮点数
        self.exposure_spin.setValue(10000.0)  # 默认10ms，使用浮点数
        self.gain_spin.setRange(0.0, 24.0)  # 0-24dB，使用浮点数
        self.gain_spin.setValue(0.0)  # 默认0dB，使用浮点数
        
        # 连接按钮信号
        self.connect_btn.clicked.connect(self.connect_clicked)
        self.capture_btn.clicked.connect(self.capture_clicked)
        self.stream_btn.clicked.connect(self.stream_clicked)
        
        # 连接参数信号
        self.exposure_spin.valueChanged.connect(lambda v: self.exposure_changed.emit(float(v)))
        self.exposure_auto.toggled.connect(self._handle_exposure_auto)
        self.gain_spin.valueChanged.connect(lambda v: self.gain_changed.emit(float(v)))
        self.gain_auto.toggled.connect(self._handle_gain_auto)
        self.wb_auto.toggled.connect(self.wb_auto_changed)
        
        # 添加单次按钮的信号连接
        self.exposure_once.clicked.connect(self.exposure_once_clicked)
        self.gain_once.clicked.connect(self.gain_once_clicked)
        self.wb_once.clicked.connect(self.wb_once_clicked)

        self.exposure_auto.toggled.connect(
            lambda checked: self.exposure_once.setEnabled(not checked)
        )
        
        self.gain_auto.toggled.connect(
            lambda checked: self.gain_once.setEnabled(not checked)
        )
        
        self.wb_auto.toggled.connect(
            lambda checked: self.wb_once.setEnabled(not checked)
        )
        
        # 添加角度选择信号连接
        self.angle_combo.currentIndexChanged.connect(
            lambda idx: self.angle_changed.emit(idx * 45)  # 转换为实际角度值
        )
        
        # 添加颜色模式切换信号
        self.color_mode_combo.currentIndexChanged.connect(
            lambda idx: self._handle_color_mode_changed(idx == 1)
        )

    def _handle_exposure_auto(self, checked: bool):
        """处理曝光自动模式切换"""
        self.exposure_spin.setReadOnly(checked)  # 只读而不是禁用
        self.exposure_spin.setEnabled(True)      # 保持启用状态以显示数值
        self.exposure_auto_changed.emit(checked)
        
    def _handle_gain_auto(self, checked: bool):
        """处理增益自动模式切换"""
        self.gain_spin.setReadOnly(checked)      # 只读而不是禁用
        self.gain_spin.setEnabled(True)          # 保持启用状态以显示数值
        self.gain_auto_changed.emit(checked)
        
    def _handle_color_mode_changed(self, is_color: bool):
        """处理颜色模式改变"""
        self.pol_wb_auto.setVisible(is_color)
        self.pol_wb_once.setVisible(is_color)
        self.color_mode_changed.emit(is_color)

    def update_exposure_value(self, value: float):
        """更新曝光值（不触发信号）"""
        self.exposure_spin.blockSignals(True)
        self.exposure_spin.setValue(value)
        self.exposure_spin.blockSignals(False)
        
    def update_gain_value(self, value: float):
        """更新增益值（不触发信号）"""
        self.gain_spin.blockSignals(True)
        self.gain_spin.setValue(value)
        self.gain_spin.blockSignals(False)
        
    def set_connected(self, connected: bool):
        self.capture_btn.setEnabled(connected)
        self.stream_btn.setEnabled(connected)
        self.exposure_spin.setEnabled(connected and not self.exposure_auto.isChecked())
        self.exposure_auto.setEnabled(connected)
        self.gain_spin.setEnabled(connected and not self.gain_auto.isChecked())
        self.gain_auto.setEnabled(connected)
        self.wb_auto.setEnabled(connected)
        self.connect_btn.setText("断开相机" if connected else "连接相机")
        # 更新单次按钮状态
        self.exposure_once.setEnabled(connected and not self.exposure_auto.isChecked())
        self.gain_once.setEnabled(connected and not self.gain_auto.isChecked())
        self.wb_once.setEnabled(connected and not self.wb_auto.isChecked())

    def enable_exposure_controls(self, enabled: bool):
        """设置曝光相关控件的启用状态"""
        self.exposure_spin.setEnabled(enabled)
        self.exposure_auto.setEnabled(enabled)
        self.exposure_once.setEnabled(enabled and not self.exposure_auto.isChecked())
        
    def enable_gain_controls(self, enabled: bool):
        """设置增益相关控件的启用状态"""
        self.gain_spin.setEnabled(enabled)
        self.gain_auto.setEnabled(enabled)
        self.gain_once.setEnabled(enabled and not self.gain_auto.isChecked())
        
    def enable_wb_controls(self, enabled: bool):
        """设置白平衡相关控件的启用状态"""
        self.wb_auto.setEnabled(enabled)
        self.wb_once.setEnabled(enabled and not self.wb_auto.isChecked())

    def set_wb_controls_visible(self, visible: bool):
        """设置白平衡控制组的可见性"""
        if self.wb_group.isVisible() != visible:  # 只在状态不同时才更新
            self.wb_group.setVisible(visible)
            # 立即重新计算布局
            self.updateGeometry()
            self.parentWidget().updateGeometry()

    def set_angle_controls_visible(self, visible: bool):
        """设置角度选择控制组的可见性"""
        if self.angle_group.isVisible() != visible:  # 只在状态不同时才更新
            self.angle_group.setVisible(visible)
            # 立即重新计算布局
            self.updateGeometry()
            self.parentWidget().updateGeometry()
            
    def set_pol_controls_visible(self, visible: bool):
        """设置偏振分析相关控件的可见性"""
        if self.pol_color_group.isVisible() != visible:
            self.pol_color_group.setVisible(visible)
            self.updateGeometry()
            if self.parentWidget():
                self.parentWidget().adjustSize()

    def get_selected_angle(self) -> int:
        """获取当前选择的角度值"""
        return self.angle_combo.currentIndex() * 45

    def is_pol_color_mode(self) -> bool:
        """返回当前是否为彩色模式"""
        return self.color_mode_combo.currentIndex() == 1

    def _update_current_values(self):
        """更新当前显示的参数值"""
        if hasattr(self.parent(), 'camera') and self.parent().camera:
            camera = self.parent().camera
            # 更新曝光值显示
            self.update_exposure_value(camera.get_exposure_time())
            # 更新增益值显示
            self.update_gain_value(camera.get_gain())
