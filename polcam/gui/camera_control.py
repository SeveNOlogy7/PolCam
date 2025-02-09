"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtCore

class CameraControl(QtWidgets.QWidget):
    # 定义所有信号
    connect_clicked = QtCore.Signal(bool)
    capture_clicked = QtCore.Signal()
    stream_clicked = QtCore.Signal(bool)
    exposure_changed = QtCore.Signal(float)
    exposure_auto_changed = QtCore.Signal(bool)
    gain_changed = QtCore.Signal(float)
    gain_auto_changed = QtCore.Signal(bool)
    wb_auto_changed = QtCore.Signal(bool)
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)  # 设置内边距
        
        # 顶部控制区域
        top_layout = QtWidgets.QHBoxLayout()
        
        # 连接控制
        self.connect_btn = QtWidgets.QPushButton("连接相机")
        self.connect_btn.setCheckable(True)
        layout.addWidget(self.connect_btn)
        
        # 采集控制
        self.capture_btn = QtWidgets.QPushButton("单帧采集")
        self.stream_btn = QtWidgets.QPushButton("连续采集")
        self.stream_btn.setCheckable(True)
        layout.addWidget(self.capture_btn)
        layout.addWidget(self.stream_btn)
        
        # 参数控制组
        param_group = QtWidgets.QGroupBox("参数设置")
        param_layout = QtWidgets.QFormLayout(param_group)
        
        # 曝光控制
        self.exposure_spin = QtWidgets.QDoubleSpinBox()
        self.exposure_spin.setDecimals(1)  # 设置小数位数
        self.exposure_auto = QtWidgets.QCheckBox("自动")
        exposure_layout = QtWidgets.QHBoxLayout()
        exposure_layout.addWidget(self.exposure_spin)
        exposure_layout.addWidget(self.exposure_auto)
        param_layout.addRow("曝光时间:", exposure_layout)
        
        # 增益控制
        self.gain_spin = QtWidgets.QDoubleSpinBox()
        self.gain_spin.setDecimals(1)  # 设置小数位数
        self.gain_auto = QtWidgets.QCheckBox("自动")
        gain_layout = QtWidgets.QHBoxLayout()
        gain_layout.addWidget(self.gain_spin)
        gain_layout.addWidget(self.gain_auto)
        param_layout.addRow("增益:", gain_layout)
        
        # 白平衡控制
        self.wb_auto = QtWidgets.QCheckBox("自动白平衡")
        param_layout.addRow("", self.wb_auto)
        
        layout.addWidget(param_group)
        layout.addStretch()
        
        # 修改连接信号部分，移除到 setup_connections
        self.capture_btn.setEnabled(False)
        self.stream_btn.setEnabled(False)
        
        # 设置固定的尺寸策略
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.Preferred
        )
        
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
