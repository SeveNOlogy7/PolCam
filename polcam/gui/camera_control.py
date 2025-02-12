"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtCore
from .styles import Styles
from .widgets.parameter_control import ParameterControl
from .widgets.angle_selector import AngleSelector
from .widgets.white_balance import WhiteBalance
from .widgets.polarization_control import PolarizationControl

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
        
        # 连接和采集控制按钮
        self.connect_btn = QtWidgets.QPushButton("连接相机")
        self.connect_btn.setCheckable(True)
        layout.addWidget(self.connect_btn)
        
        self.capture_btn = QtWidgets.QPushButton("单帧采集")
        self.stream_btn = QtWidgets.QPushButton("连续采集")
        self.stream_btn.setCheckable(True)
        layout.addWidget(self.capture_btn)
        layout.addWidget(self.stream_btn)
        
        # 添加参数控制组
        self.exposure_control = ParameterControl("曝光控制", "曝光时间", "us")
        self.gain_control = ParameterControl("增益控制", "增益", "dB")
        layout.addWidget(self.exposure_control)
        layout.addWidget(self.gain_control)
        
        # 添加角度选择控制组
        self.angle_selector = AngleSelector()
        layout.addWidget(self.angle_selector)
        self.angle_selector.setVisible(False)
        
        # 添加偏振分析控制组
        self.pol_control = PolarizationControl()
        layout.addWidget(self.pol_control)
        self.pol_control.setVisible(False)
        
        # 添加白平衡控制组
        self.wb_control = WhiteBalance()
        layout.addWidget(self.wb_control)
        self.wb_control.setVisible(False)
        
        layout.addStretch()
        
        # 初始状态设置
        self.capture_btn.setEnabled(False)
        self.stream_btn.setEnabled(False)
        
        # 应用样式
        for btn in [self.connect_btn, self.capture_btn, self.stream_btn]:
            Styles.apply_button_style(btn)
            
    def setup_connections(self):
        # 设置参数范围
        self.exposure_control.set_range(20.0, 1000000.0)  # 20us - 1s
        self.exposure_control.set_value(10000.0)         # 默认10ms
        self.gain_control.set_range(0.0, 24.0)          # 0-24dB
        self.gain_control.set_value(0.0)                # 默认0dB
        
        # 连接按钮信号
        self.connect_btn.clicked.connect(self.connect_clicked)
        self.capture_btn.clicked.connect(self.capture_clicked)
        self.stream_btn.clicked.connect(self.stream_clicked)
        
        # 连接参数控制信号
        self.exposure_control.value_changed.connect(self.exposure_changed)
        self.exposure_control.auto_changed.connect(self.exposure_auto_changed)
        self.exposure_control.once_clicked.connect(self.exposure_once_clicked)
        
        self.gain_control.value_changed.connect(self.gain_changed)
        self.gain_control.auto_changed.connect(self.gain_auto_changed)
        self.gain_control.once_clicked.connect(self.gain_once_clicked)
        
        # 连接白平衡信号
        self.wb_control.auto_changed.connect(self.wb_auto_changed)
        self.wb_control.once_clicked.connect(self.wb_once_clicked)
        
        # 角度选择信号
        self.angle_selector.angle_changed.connect(self.angle_changed)
        
        # 偏振分析颜色模式信号
        self.pol_control.color_mode_changed.connect(self._handle_color_mode_changed)

    def _handle_color_mode_changed(self, is_color: bool):
        """处理颜色模式改变"""
        # 修正：使用 wb_control 而不是直接访问 checkbox 和 button
        self.pol_control.wb_control.setVisible(is_color)
        self.color_mode_changed.emit(is_color)

    def update_exposure_value(self, value: float):
        """更新曝光值（不触发信号）"""
        self.exposure_control.set_value(value)
        
    def update_gain_value(self, value: float):
        """更新增益值（不触发信号）"""
        self.gain_control.set_value(value)
        
    def set_connected(self, connected: bool):
        """设置连接状态时的控件启用状态"""
        self.capture_btn.setEnabled(connected)
        self.stream_btn.setEnabled(connected)
        self.exposure_control.set_enabled(connected)
        self.gain_control.set_enabled(connected)
        self.connect_btn.setText("断开相机" if connected else "连接相机")

    def enable_exposure_controls(self, enabled: bool):
        """设置曝光相关控件的启用状态"""
        self.exposure_control.set_enabled(enabled)
        
    def enable_gain_controls(self, enabled: bool):
        """设置增益相关控件的启用状态"""
        self.gain_control.set_enabled(enabled)
        
    def enable_wb_controls(self, enabled: bool):
        """设置白平衡相关控件的启用状态
        注：只影响单次白平衡按钮，不影响自动模式开关"""
        self.wb_control.once_btn.setEnabled(enabled)

    def set_wb_controls_visible(self, visible: bool):
        """设置白平衡控制组的可见性"""
        if self.wb_control.isVisible() != visible:  # 只在状态不同时才更新
            self.wb_control.setVisible(visible)
            # 立即重新计算布局
            self.updateGeometry()
            self.parentWidget().updateGeometry()

    def set_angle_controls_visible(self, visible: bool):
        """设置角度选择控制组的可见性"""
        if self.angle_selector.isVisible() != visible:  # 只在状态不同时才更新
            self.angle_selector.setVisible(visible)
            # 立即重新计算布局
            self.updateGeometry()
            self.parentWidget().updateGeometry()
            
    def set_pol_controls_visible(self, visible: bool):
        """设置偏振分析相关控件的可见性"""
        if self.pol_control.isVisible() != visible:
            self.pol_control.setVisible(visible)
            self.updateGeometry()
            if self.parentWidget():
                self.parentWidget().adjustSize()

    def get_selected_angle(self) -> int:
        """获取当前选择的角度值"""
        return self.angle_selector.combo.currentIndex() * 45

    def is_pol_color_mode(self) -> bool:
        """返回当前是否为彩色模式"""
        return self.pol_control.combo.currentIndex() == 1

    def handle_one_shot_auto(self, control_type: str):
        """处理单次自动调整
        
        Args:
            control_type: 'exposure', 'gain' 或 'wb'
        """
        if control_type == 'exposure':
            self.exposure_control.set_enabled(False)
        elif control_type == 'gain':
            self.gain_control.set_enabled(False)
        elif control_type == 'wb':
            self.wb_control.set_enabled(False)

    def handle_one_shot_complete(self, control_type: str, value: float = None):
        """处理单次自动调整完成
        
        Args:
            control_type: 'exposure', 'gain' 或 'wb'
            value: 新的参数值(可选)
        """
        if control_type == 'exposure':
            self.exposure_control.set_enabled(True)
            if value is not None:
                self.update_exposure_value(value)
        elif control_type == 'gain':
            self.gain_control.set_enabled(True)
            if value is not None:
                self.update_gain_value(value)
        elif control_type == 'wb':
            self.wb_control.set_enabled(True)
            self.wb_control.once_button.setChecked(False)

    def handle_parameter_change(self, param_name: str, value: float):
        """处理参数变化
        
        Args:
            param_name: 'exposure' 或 'gain'
            value: 新的参数值
        """
        if param_name == 'exposure':
            self.update_exposure_value(value)
        elif param_name == 'gain':
            self.update_gain_value(value)

    def update_auto_parameters(self, exposure: float = None, gain: float = None):
        """更新自动参数显示值"""
        if exposure is not None and self.exposure_control.is_auto():
            self.update_exposure_value(exposure)
            
        if gain is not None and self.gain_control.is_auto():
            self.update_gain_value(gain)

    def handle_stream_state(self, streaming: bool):
        """处理连续采集状态改变"""
        self.capture_btn.setEnabled(not streaming)
        self.stream_btn.setText("停止采集" if streaming else "连续采集")
