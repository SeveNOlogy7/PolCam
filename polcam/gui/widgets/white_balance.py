"""白平衡控制组组件"""

from qtpy import QtWidgets, QtCore, QtGui
from .control_group import ControlGroup
from ..styles import Styles

class WhiteBalance(ControlGroup):
    auto_changed = QtCore.Signal(bool)
    once_clicked = QtCore.Signal()
    
    def __init__(self, title="白平衡控制", parent=None):
        super().__init__(title, parent)
        self._setup_wb_ui()
        self._setup_connections()
        
    def _setup_wb_ui(self):
        wb_layout = QtWidgets.QHBoxLayout()
        
        self.auto_check = QtWidgets.QCheckBox("自动")
        self.auto_check.setFont(QtGui.QFont("", 11))
        Styles.apply_checkbox_style(self.auto_check)
        
        self.once_btn = QtWidgets.QPushButton("单次")
        self.once_btn.setFont(QtGui.QFont("", 11))
        self.once_btn.setMinimumHeight(30)
        Styles.apply_button_style(self.once_btn)
        
        wb_layout.addWidget(self.auto_check)
        wb_layout.addWidget(self.once_btn)
        self.layout.addLayout(wb_layout)
        
    def _setup_connections(self):
        self.auto_check.toggled.connect(self._handle_auto_changed)
        self.once_btn.clicked.connect(self.once_clicked)
        
    def _handle_auto_changed(self, checked: bool):
        self.once_btn.setEnabled(not checked)
        self.auto_changed.emit(checked)
        
    def set_enabled(self, enabled: bool):
        self.auto_check.setEnabled(enabled)
        self.once_btn.setEnabled(enabled and not self.auto_check.isChecked())
