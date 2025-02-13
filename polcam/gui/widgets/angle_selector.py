"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.

角度选择控制组组件
"""

from qtpy import QtWidgets, QtCore, QtGui
from .control_group import ControlGroup
from ..styles import Styles

class AngleSelector(ControlGroup):
    angle_changed = QtCore.Signal(int)
    
    def __init__(self, parent=None):
        super().__init__("角度选择", parent)
        self._setup_angle_ui()
        self._setup_connections()
        
    def _setup_angle_ui(self):
        angle_layout = QtWidgets.QHBoxLayout()
        
        angle_label = QtWidgets.QLabel("偏振角度:")
        angle_label.setFont(QtGui.QFont("", 11))
        angle_layout.addWidget(angle_label)
        
        self.angle_combo = QtWidgets.QComboBox()
        self.angle_combo.setFont(QtGui.QFont("", 11))
        self.angle_combo.setMinimumHeight(30)
        self.angle_combo.addItems(["0°", "45°", "90°", "135°"])
        Styles.apply_combobox_style(self.angle_combo)
        angle_layout.addWidget(self.angle_combo)
        
        self.layout.addLayout(angle_layout)
        
    def _setup_connections(self):
        self.angle_combo.currentIndexChanged.connect(
            lambda idx: self.angle_changed.emit(idx * 45)
        )
        
    def get_angle(self) -> int:
        return self.angle_combo.currentIndex() * 45
