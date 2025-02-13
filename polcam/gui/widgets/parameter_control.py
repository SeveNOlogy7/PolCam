"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.

参数控制组组件
"""

from qtpy import QtWidgets, QtCore, QtGui
from .control_group import ControlGroup
from ..styles import Styles

class ParameterControl(ControlGroup):
    # 定义信号
    value_changed = QtCore.Signal(float)
    auto_changed = QtCore.Signal(bool)
    once_clicked = QtCore.Signal()
    
    def __init__(self, title: str, param_name: str, unit: str = "", parent=None):
        super().__init__(title, parent)
        self.param_name = param_name
        self.unit = unit
        self._setup_parameter_ui()
        self._setup_connections()
        
    def _setup_parameter_ui(self):
        # 参数值控制
        value_layout = QtWidgets.QHBoxLayout()
        value_layout.addWidget(QtWidgets.QLabel(f"{self.param_name} ({self.unit}):" if self.unit else f"{self.param_name}:"))
        
        self.value_spin = QtWidgets.QDoubleSpinBox()
        self.value_spin.setDecimals(1)
        self.value_spin.setRange(0.0, 1000000.0)
        Styles.apply_spinbox_style(self.value_spin)
        value_layout.addWidget(self.value_spin)
        
        self.layout.addLayout(value_layout)
        
        # 自动控制
        auto_layout = QtWidgets.QHBoxLayout()
        self.auto_check = QtWidgets.QCheckBox("自动")
        Styles.apply_checkbox_style(self.auto_check)
        
        self.once_btn = QtWidgets.QPushButton("单次")
        Styles.apply_button_style(self.once_btn)
        
        auto_layout.addWidget(self.auto_check)
        auto_layout.addWidget(self.once_btn)
        self.layout.addLayout(auto_layout)
        
    def _setup_connections(self):
        self.value_spin.valueChanged.connect(
            lambda v: self.value_changed.emit(float(v))
        )
        self.auto_check.toggled.connect(self._handle_auto_changed)
        self.once_btn.clicked.connect(self.once_clicked)
        
    def _handle_auto_changed(self, checked: bool):
        self.value_spin.setReadOnly(checked)
        self.value_spin.setEnabled(True)
        self.once_btn.setEnabled(not checked)
        self.auto_changed.emit(checked)
        
    def set_range(self, min_val: float, max_val: float):
        self.value_spin.setRange(min_val, max_val)
        
    def set_value(self, value: float):
        """设置参数值（不触发信号）"""
        self.value_spin.blockSignals(True)
        self.value_spin.setValue(value)
        self.value_spin.blockSignals(False)
        
    def is_auto(self) -> bool:
        """返回是否处于自动模式"""
        return self.auto_check.isChecked()

    def set_enabled(self, enabled: bool):
        self.value_spin.setEnabled(enabled)
        self.auto_check.setEnabled(enabled)
        self.once_btn.setEnabled(enabled and not self.auto_check.isChecked())
