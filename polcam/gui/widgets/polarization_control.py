"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.

偏振分析控制组组件
"""

from qtpy import QtWidgets, QtCore, QtGui
from .control_group import ControlGroup
from .white_balance import WhiteBalance
from ..styles import Styles

class PolarizationControl(ControlGroup):
    color_mode_changed = QtCore.Signal(bool)
    wb_auto_changed = QtCore.Signal(bool)
    wb_once_clicked = QtCore.Signal()
    
    def __init__(self, parent=None):
        super().__init__("合成图像设置", parent)
        self._setup_pol_ui()
        self._setup_connections()
        
    def _setup_pol_ui(self):
        # 添加彩色/灰度选择
        self.color_mode_combo = QtWidgets.QComboBox()
        self.color_mode_combo.addItems(["灰度图像", "彩色图像"])
        self.color_mode_combo.setFont(QtGui.QFont("", 11))
        self.color_mode_combo.setMinimumHeight(30)
        Styles.apply_combobox_style(self.color_mode_combo)
        self.layout.addWidget(self.color_mode_combo)
        
        # 添加白平衡控制
        self.wb_control = WhiteBalance("白平衡设置", self)
        self.wb_control.setVisible(False)  # 初始时隐藏白平衡控制
        self.layout.addWidget(self.wb_control)
        
    def _setup_connections(self):
        self.color_mode_combo.currentIndexChanged.connect(
            lambda idx: self._handle_color_mode_changed(idx == 1)
        )
        self.wb_control.auto_changed.connect(self.wb_auto_changed)
        self.wb_control.once_clicked.connect(self.wb_once_clicked)
        
    def _handle_color_mode_changed(self, is_color: bool):
        self.wb_control.setVisible(is_color)
        self.color_mode_changed.emit(is_color)
        
    def is_color_mode(self) -> bool:
        return self.color_mode_combo.currentIndex() == 1
