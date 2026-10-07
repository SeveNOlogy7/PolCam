"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

界面主题档位与配色取值。

这里只有**数据**，不碰 Qt：一套档位的颜色要能脱离 QApplication 被检查（两个档必须
声明同样的角色、深色档的文字要压得住深色底），落到 QPalette 是 gui/app_theme.py 的事。
"""
from dataclasses import dataclass
from enum import Enum


class ThemeMode(Enum):
    """用户在右上角切换的界面明暗。"""

    LIGHT = "light"
    DARK = "dark"

    @property
    def label(self) -> str:
        return {ThemeMode.LIGHT: "浅色", ThemeMode.DARK: "暗夜"}[self]

    @staticmethod
    def from_name(name) -> "ThemeMode":
        """把 settings.ini 里存的字符串装回来。

        存名字不存整数（顺序会变），认不出来的值回落到浅色而不是暗夜：默认档变了要能
        被人看出来，静默换肤更糟。
        """
        if isinstance(name, str):
            try:
                return ThemeMode(name.strip().lower())
            except ValueError:
                return ThemeMode.LIGHT
        return ThemeMode.LIGHT

    def toggled(self) -> "ThemeMode":
        return ThemeMode.DARK if self is ThemeMode.LIGHT else ThemeMode.LIGHT


@dataclass(frozen=True)
class ThemeTokens:
    """一个档位的全部颜色。全部写成 #rrggbb，好让测试能逐条解析。"""

    window: str
    window_text: str
    base: str
    text: str
    button: str
    button_text: str
    highlight: str
    highlighted_text: str
    tooltip_base: str
    tooltip_text: str
    placeholder_text: str
    disabled_text: str
    # 分割条描边。浅色档沿用改造前的三个值，深色档按"越靠近越亮"反过来：
    # 深色面板上一条 #aeb6c1 的亮线会把边界糊成一片白。
    splitter_idle: str
    splitter_hover: str
    splitter_pressed: str


LIGHT = ThemeTokens(
    window="#f0f0f0",
    window_text="#1e1e1e",
    base="#ffffff",
    text="#1e1e1e",
    button="#e1e1e1",
    button_text="#1e1e1e",
    highlight="#0078d7",
    highlighted_text="#ffffff",
    tooltip_base="#ffffe1",
    tooltip_text="#1e1e1e",
    placeholder_text="#9a9a9a",
    disabled_text="#6d6d6d",
    splitter_idle="#aeb6c1",
    splitter_hover="#7f95ac",
    splitter_pressed="#667c94",
)

DARK = ThemeTokens(
    window="#31363b",
    window_text="#eff0f1",
    base="#232627",
    text="#fcfcfc",
    button="#31363b",
    button_text="#eff0f1",
    highlight="#3daee9",
    highlighted_text="#1e1e1e",
    tooltip_base="#31363b",
    tooltip_text="#eff0f1",
    placeholder_text="#a0a0a0",
    disabled_text="#8f9498",
    splitter_idle="#4b4f52",
    splitter_hover="#6d7a86",
    splitter_pressed="#8fa3b8",
)

TOKENS = {ThemeMode.LIGHT: LIGHT, ThemeMode.DARK: DARK}


def tokens_for(mode: ThemeMode) -> ThemeTokens:
    """档位对应的取值；传进来的是配置文件里的字符串时也认。"""
    resolved = mode if isinstance(mode, ThemeMode) else ThemeMode.from_name(mode)
    return TOKENS[resolved]
