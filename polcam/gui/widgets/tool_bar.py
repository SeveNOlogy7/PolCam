from qtpy import QtWidgets, QtGui, QtCore
from ..styles import Styles
import os

class ToolBar(QtWidgets.QToolBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(False)
        # 应用样式
        Styles.apply_toolbar_style(self)
        self.setIconSize(QtCore.QSize(24, 24))
        self.setup_actions()

    def setup_actions(self):
        # 创建并添加动作
        self.save_raw_action = QtWidgets.QAction(self._load_icon("save_raw.svg"), "保存原始图像", self)
        self.save_raw_action.setEnabled(False)
        self.addAction(self.save_raw_action)

        self.save_result_action = QtWidgets.QAction(self._load_icon("save_result.svg"), "保存处理结果", self)
        self.save_result_action.setEnabled(False)
        self.addAction(self.save_result_action)

        # 添加打开原始图像按钮
        self.open_raw_action = QtWidgets.QAction(self._load_icon("open_raw.svg"), "打开原始图像", self)
        self.addAction(self.open_raw_action)

        self.addSeparator()

        self.settings_action = QtWidgets.QAction(self._load_icon("settings.svg"), "设置", self)
        self.addAction(self.settings_action)

        self.about_action = QtWidgets.QAction(self._load_icon("about.svg"), "关于", self)
        self.addAction(self.about_action)

        self.help_action = QtWidgets.QAction(self._load_icon("help.svg"), "帮助", self)
        self.addAction(self.help_action)

    def _load_icon(self, filename: str) -> QtGui.QIcon:
        """加载图标"""
        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "resources", "icon", filename)
        if os.path.exists(icon_path):
            return QtGui.QIcon(icon_path)
        return QtGui.QIcon()
