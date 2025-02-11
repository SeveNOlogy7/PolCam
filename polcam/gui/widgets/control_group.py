"""基础控制组组件"""

from qtpy import QtWidgets, QtGui
from ..styles import Styles

class ControlGroup(QtWidgets.QGroupBox):
    """基础控制组组件"""
    
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        Styles.apply_group_title_style(self)
        self.setup_ui()
        
    def setup_ui(self):
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(5)
