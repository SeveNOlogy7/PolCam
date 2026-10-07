"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtGui, QtCore
from .. import app_theme
from ..app_theme import themed_icon
from ..i18n import Language, current_language
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

        self.save_raw_action = self._add_action("save_raw.svg", self.tr("保存原始图像"))
        self.save_raw_action.setEnabled(False)

        self.save_result_action = self._add_action("save_result.svg", self.tr("保存处理结果"))
        self.save_result_action.setEnabled(False)

        self.open_raw_action = self._add_action("open_raw.svg", self.tr("打开原始图像"))

        self.addSeparator()

        self.settings_action = self._add_action("settings.svg", self.tr("设置"))
        self.about_action = self._add_action("about.svg", self.tr("关于"))
        self.help_action = self._add_action("help.svg", self.tr("帮助"))

        self.addSeparator()

        # 换肤与语言两个按钮：图标和提示说的都是"点下去会去哪"，不是"现在在哪"，
        # 所以它们显示的是当前档位的反面。
        self.theme_action = QtWidgets.QAction(self)
        self.addAction(self.theme_action)
        self.language_action = QtWidgets.QAction(self)
        self.addAction(self.language_action)
        self.refresh_texts()

    def _add_action(self, filename: str, text: str) -> QtWidgets.QAction:
        action = QtWidgets.QAction(self._load_icon(filename), text, self)
        self.addAction(action)
        self._themed_actions.append((filename, action, text))
        return action

    def refresh_texts(self):
        """把所有文字重取一遍。切换语言后必须由 MainWindow 调一次。

        每条提示都是**整句**进目录的，不用 "%1" 拼：Qt 的翻译表按整句查，拼出来的句子
        既查不到也容易被译成语序不通的英文。
        """
        for _, action, text in self._themed_actions:
            action.setText(self.tr(text))
        self._set_theme_text(app_theme.current_mode())
        self._set_language_text(current_language())

    def _set_theme_text(self, mode: ThemeMode):
        to_dark = mode is ThemeMode.LIGHT
        self.theme_action.setIcon(
            self._load_icon("theme_dark.svg" if to_dark else "theme_light.svg"))
        self.theme_action.setText(
            self.tr("切换到暗夜模式") if to_dark else self.tr("切换到浅色模式"))
        self.theme_action.setToolTip(
            self.tr("切换到暗夜模式（当前：浅色）") if to_dark
            else self.tr("切换到浅色模式（当前：暗夜）"))

    def set_theme_mode(self, mode: ThemeMode):
        """按当前档位重画换肤按钮。"""
        self._set_theme_text(mode)

    def _set_language_text(self, language: Language):
        """语言按钮只有一个图标：切换语言这件事本身与当前语言无关，翻转会让人以为点一次变两次。"""
        to_english = language is Language.ZH
        self.language_action.setIcon(self._load_icon("language.svg"))
        self.language_action.setText(
            self.tr("切换到英文界面") if to_english else self.tr("切换到中文界面"))
        self.language_action.setToolTip(
            self.tr("切换到英文界面（当前：中文）") if to_english
            else self.tr("切换到中文界面（当前：English）"))

    def set_language(self, language: Language):
        """按当前语言重画语言按钮（图标与提示都指向"切过去"的那个语言）。"""
        self._set_language_text(language)

    def refresh_theme(self):
        """换肤之后重画这一排：背景、每个图标的颜色、两个开关按钮自己。

        带 stylesheet 的控件在 polish 时把背景取色缓存下来了，只改应用调色板不会让它重画；
        图标更不会自己变 —— 它们是按当时调色板上色出来的位图。
        """
        Styles.apply_toolbar_style(self)
        for filename, action, _ in self._themed_actions:
            action.setIcon(self._load_icon(filename))
        self._set_theme_text(app_theme.current_mode())
        self._set_language_text(current_language())

    def _load_icon(self, filename: str) -> QtGui.QIcon:
        """加载图标，并按当前主题的 ButtonText 上色。"""
        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "resources", "icon", filename)
        return themed_icon(icon_path, Styles.TOOLBAR_ICON_SIZE)
