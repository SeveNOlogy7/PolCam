"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

界面语言档位。只有**数据**，不碰 Qt —— 与 core/theme.py 同一个理由：设置层要能存它，
而设置层不许依赖 gui。Qt 那一半（QTranslator、遍历重译）在 gui/i18n.py。
"""
from enum import Enum


class Language(Enum):
    """用户在右上角切换的界面语言。"""

    ZH = "zh"   # 源语言：屏幕上就是代码里的那些中文字面量
    EN = "en"

    @property
    def label(self) -> str:
        """这个语言自称什么。名字本身不译 —— 中文界面写"中文"，英文界面写 "English"。"""
        return {Language.ZH: "中文", Language.EN: "English"}[self]

    @staticmethod
    def from_name(name) -> "Language":
        """把 settings.ini 里存的字符串装回来；认不出来的回落到中文（源语言）。"""
        if isinstance(name, str):
            try:
                return Language(name.strip().lower())
            except ValueError:
                return Language.ZH
        return Language.ZH

    def toggled(self) -> "Language":
        return Language.EN if self is Language.ZH else Language.ZH
