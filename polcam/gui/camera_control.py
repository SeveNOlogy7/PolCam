"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtCore

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
        
        # 参数控制区域
        param_group = QtWidgets.QGroupBox("参数设置")
        param_layout = QtWidgets.QVBoxLayout(param_group)
        
        # 曝光控制组
        exposure_group = QtWidgets.QGroupBox("曝光控制")
        exposure_layout = QtWidgets.QVBoxLayout(exposure_group)
        
        # 曝光时间设置
        exposure_value_layout = QtWidgets.QHBoxLayout()
        exposure_value_layout.addWidget(QtWidgets.QLabel("曝光时间:"))
        self.exposure_spin = QtWidgets.QDoubleSpinBox()
        self.exposure_spin.setDecimals(1)
        exposure_value_layout.addWidget(self.exposure_spin)
        exposure_layout.addLayout(exposure_value_layout)
        
        # 曝光自动控制
        exposure_auto_layout = QtWidgets.QHBoxLayout()
        self.exposure_auto = QtWidgets.QCheckBox("自动")
        self.exposure_once = QtWidgets.QPushButton("单次") 
        exposure_auto_layout.addWidget(self.exposure_auto)
        exposure_auto_layout.addWidget(self.exposure_once)
        exposure_layout.addLayout(exposure_auto_layout)
        
        param_layout.addWidget(exposure_group)
        
        # 增益控制组
        gain_group = QtWidgets.QGroupBox("增益控制")
        gain_layout = QtWidgets.QVBoxLayout(gain_group)
        
        # 增益值设置
        gain_value_layout = QtWidgets.QHBoxLayout()
        gain_value_layout.addWidget(QtWidgets.QLabel("增益:"))
        self.gain_spin = QtWidgets.QDoubleSpinBox()
        self.gain_spin.setDecimals(1)
        gain_value_layout.addWidget(self.gain_spin)
        gain_layout.addLayout(gain_value_layout)
        
        # 增益自动控制
        gain_auto_layout = QtWidgets.QHBoxLayout()
        self.gain_auto = QtWidgets.QCheckBox("自动")
        self.gain_once = QtWidgets.QPushButton("单次")
        gain_auto_layout.addWidget(self.gain_auto)
        gain_auto_layout.addWidget(self.gain_once)
        gain_layout.addLayout(gain_auto_layout)
        
        param_layout.addWidget(gain_group)
        
        # 白平衡控制组
        wb_group = QtWidgets.QGroupBox("白平衡控制")
        wb_layout = QtWidgets.QHBoxLayout(wb_group)
        
        self.wb_auto = QtWidgets.QCheckBox("自动")
        self.wb_once = QtWidgets.QPushButton("单次")
        wb_layout.addWidget(self.wb_auto)
        wb_layout.addWidget(self.wb_once)
        param_layout.addWidget(wb_group)
        
        layout.addWidget(param_group)
        layout.addStretch()
        
        # 初始状态设置
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
