"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

偏振分析控制组组件
"""

from qtpy import QtWidgets, QtCore
from .control_group import ControlGroup
from .white_balance import WhiteBalance
from ..styles import Styles

class PolarizationControl(ControlGroup):
    color_mode_changed = QtCore.Signal(bool)
    wb_auto_changed = QtCore.Signal(bool)
    wb_once_clicked = QtCore.Signal()
    retarder_changed = QtCore.Signal(bool)
    retarder_angle_changed = QtCore.Signal(float)
    
    def __init__(self, parent=None):
        super().__init__("合成图像设置", parent)
        self._setup_pol_ui()
        self._setup_connections()
        
    def _setup_pol_ui(self):
        # 添加彩色/灰度选择
        self.color_mode_combo = QtWidgets.QComboBox()
        self.color_mode_combo.addItems(["灰度图像", "彩色图像"])
        self.color_mode_combo.setToolTip("选择偏振分析结果的合成方式")
        Styles.apply_combobox_style(self.color_mode_combo)
        self.layout.addWidget(self.color_mode_combo)
        
        # 添加白平衡控制
        self.wb_control = WhiteBalance("白平衡设置", self)
        self.wb_control.setVisible(False)  # 初始时隐藏白平衡控制
        self.layout.addWidget(self.wb_control)

        # 波片状态 + 快轴角度：解算式按这两项切换，自动转角的拨片到位后写的也是这两项
        self.retarder_check = QtWidgets.QCheckBox("1/4 波片在光路中")
        self.retarder_check.setToolTip(
            "放进去之后 DoCP 才有可用的旋向符号；单个快轴角度只能定住三个 Stokes 分量")
        self.layout.addWidget(self.retarder_check)

        self.retarder_angle_spin = QtWidgets.QDoubleSpinBox()
        self.retarder_angle_spin.setDecimals(1)
        self.retarder_angle_spin.setRange(0.0, 180.0)
        self.retarder_angle_spin.setSingleStep(1.0)
        self.retarder_angle_spin.setSuffix(" °")
        self.retarder_angle_spin.setToolTip("波片快轴角度（手动读数或拨片上报）")
        self.retarder_angle_spin.setEnabled(False)
        self.layout.addWidget(self.retarder_angle_spin)
        
    def _setup_connections(self):
        self.color_mode_combo.currentIndexChanged.connect(
            lambda idx: self._handle_color_mode_changed(idx == 1)
        )
        self.wb_control.auto_changed.connect(self.wb_auto_changed)
        self.wb_control.once_clicked.connect(self.wb_once_clicked)
        self.retarder_check.toggled.connect(self._handle_retarder_toggled)
        self.retarder_angle_spin.valueChanged.connect(self.retarder_angle_changed)

    def _handle_retarder_toggled(self, enabled: bool):
        self.retarder_angle_spin.setEnabled(enabled)
        self.retarder_changed.emit(enabled)

    def set_retarder_state(self, enabled: bool, angle_deg: float):
        """回填设置时不要反过来触发一次参数变更。"""
        for widget in (self.retarder_check, self.retarder_angle_spin):
            widget.blockSignals(True)
        self.retarder_check.setChecked(bool(enabled))
        self.retarder_angle_spin.setValue(float(angle_deg))
        self.retarder_angle_spin.setEnabled(bool(enabled))
        for widget in (self.retarder_check, self.retarder_angle_spin):
            widget.blockSignals(False)
        
    def _handle_color_mode_changed(self, is_color: bool):
        self.wb_control.setVisible(is_color)
        self.color_mode_changed.emit(is_color)
        
    def is_color_mode(self) -> bool:
        return self.color_mode_combo.currentIndex() == 1

    def set_mono_locked(self, locked: bool):
        """黑白相机时锁定为灰度模式"""
        if locked:
            self.color_mode_combo.setCurrentIndex(0)  # 强制灰度
            self.color_mode_combo.setEnabled(False)
            self.wb_control.setVisible(False)
        else:
            self.color_mode_combo.setEnabled(True)
