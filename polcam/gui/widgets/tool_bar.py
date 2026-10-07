"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtGui, QtCore
from .. import app_theme
from ..app_theme import themed_icon
from ..styles import Styles
from ...core.theme import ThemeMode
import os

class ToolBar(QtWidgets.QToolBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(False)
        # 应用样式
        Styles.apply_toolbar_style(self)
        self.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setIconSize(Styles.TOOLBAR_ICON_SIZE)
        self.setup_actions()

    def setup_actions(self):
        # 每个动作记住自己的 svg 文件名，换肤时按新的调色板重取一次图标
        self._themed_actions = []

        self.save_raw_action = self._add_action("save_raw.svg", "保存原始图像")
        self.save_raw_action.setEnabled(False)

        self.save_result_action = self._add_action("save_result.svg", "保存处理结果")
        self.save_result_action.setEnabled(False)

        self.open_raw_action = self._add_action("open_raw.svg", "打开原始图像")

        self.addSeparator()

        self.settings_action = self._add_action("settings.svg", "设置")
        self.about_action = self._add_action("about.svg", "关于")
        self.help_action = self._add_action("help.svg", "帮助")

        self.addSeparator()

        # 换肤按钮：图标与提示说的都是"点下去会去哪"，不是"现在在哪"，所以它自己
        # 就是当前档的反面。
        self.theme_action = QtWidgets.QAction(self)
        self.addAction(self.theme_action)
        self.set_theme_mode(ThemeMode.LIGHT)

    def _add_action(self, filename: str, text: str) -> QtWidgets.QAction:
        action = QtWidgets.QAction(self._load_icon(filename), text, self)
        self.addAction(action)
        self._themed_actions.append((filename, action))
        return action

    def set_theme_mode(self, mode: ThemeMode):
        """按当前档位重画换肤按钮。"""
        target = mode.toggled()
        self.theme_action.setIcon(
            self._load_icon("theme_dark.svg" if target is ThemeMode.DARK else "theme_light.svg"))
        self.theme_action.setText(f"切换到{target.label}模式")
        self.theme_action.setToolTip(f"切换到{target.label}模式（当前：{mode.label}）")

    def refresh_theme(self):
        """换肤之后重画这一排：背景、每个图标的颜色、换肤按钮自己的图标。

        带 stylesheet 的控件在 polish 时把背景取色缓存下来了，只改应用调色板不会让它重画；
        图标更不会自己变 —— 它们是按当时调色板上色出来的位图。
        """
        Styles.apply_toolbar_style(self)
        for filename, action in self._themed_actions:
            action.setIcon(self._load_icon(filename))
        self.set_theme_mode(app_theme.current_mode())

    def _load_icon(self, filename: str) -> QtGui.QIcon:
        """加载图标，并按当前主题的 ButtonText 上色。"""
        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "resources", "icon", filename)
        return themed_icon(icon_path, Styles.TOOLBAR_ICON_SIZE)

