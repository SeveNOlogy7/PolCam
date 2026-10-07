"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

界面语言：Qt Linguist 工具链的运行时那一半。

代码里写的中文就是**源语言**，所以中文档不装 QTranslator —— 装一份 zh.qm 只会多出一个
会和代码脱节的副本。切到英文时装上 `polcam_en.qm`，Qt 在每次 `tr()` 求值时查表。

翻译目录（.ts/.qm）由 `tools/build_translations.py` 生成与校验，不在这儿管。
"""
import logging
import os

from qtpy import QtCore, QtWidgets

from ..core.language import Language

logger = logging.getLogger(__name__)

LANGUAGE_PROPERTY = "polcamLanguage"

__all__ = ("Language", "apply_language", "current_language", "retranslate_tree",
           "translate_source", "translations_dir", "invalidate_catalog_cache")


# 源语言没有目录：没有 zh.qm 这一项是设计，不是漏了。
CATALOGS = {Language.EN.value: "polcam_en"}


def translations_dir() -> str:
    """打包版在 sys._MEIPASS/polcam/translations，开发版在仓库里。"""
    return os.path.join(os.path.dirname(__file__), "..", "translations")


def current_language(app=None) -> Language:
    app = app if app is not None else QtWidgets.QApplication.instance()
    if app is None:
        return Language.ZH
    return Language.from_name(app.property(LANGUAGE_PROPERTY))


def apply_language(app, language: Language) -> Language:
    """装上/卸下翻译目录，返回**实际生效**的语言。

    目录加载不上时不会假装切换成功：界面继续说中文，按钮也就继续显示中文，
    否则用户会对着一个"已经切到 English"却满屏汉字的界面怀疑自己看错了。
    """
    language = Language.from_name(language)
    installed = app.property("_polcamTranslator")
    if isinstance(installed, QtCore.QTranslator):
        app.removeTranslator(installed)
        installed.deleteLater()
    app.setProperty("_polcamTranslator", None)

    wanted = CATALOGS.get(language.value)
    effective = language
    if wanted is not None:
        translator = QtCore.QTranslator(app)
        if translator.load(wanted, translations_dir()):
            app.installTranslator(translator)
            app.setProperty("_polcamTranslator", translator)
        else:
            translator.deleteLater()
            effective = Language.ZH
            logger.warning(f"翻译目录 {wanted}.qm 没能从 {translations_dir()} 加载，"
                           f"界面继续使用中文")
    app.setProperty(LANGUAGE_PROPERTY, effective.value)
    return effective


def retranslate_tree(window) -> int:
    """把已经上屏的文字按当前语言重取一遍，返回改动的控件数。

    Qt 对"运行时换语言"的官方答案是 retranslateUi()，那是 Designer 从 .ui 生成出来的函数；
    这里的界面是手写构造的，文字在 `__init__` 里就设进了控件。与其把十个类的构造代码各拆一遍，
    不如照着目录做一次树遍历：控件现在的文字要么是源字符串，要么是它的译文，两者都能映射回
    源字符串，再按当前语言取一次即可。

    只处理**能对上目录**的文字。读数、文件名、拼出来的句子不在目录里，原样留着 —— 那些本来
    就是运行时用 tr() 现算的，下次显示时自然是新语言。
    """
    display_to_source, _ = _catalogs()
    targets = [window] + window.findChildren(QtWidgets.QWidget)
    targets += [action for widget in targets for action in widget.actions()]
    changed = 0
    for target in targets:
        for getter, setter in ((target.text, target.setText),
                               (target.toolTip, target.setToolTip),
                               (target.accessibleName, target.setAccessibleName)):
            shown = getter()
            source = display_to_source.get(shown)
            if source is None:
                continue
            translated = translate_source(source)
            if translated != shown:
                setter(translated)
                changed += 1
    return changed


def translate_source(source: str) -> str:
    """按当前语言取一句。中文是源语言，直接回原文。

    同一句中文可能出现在几个类里；取第一个真能译出来的上下文。
    """
    if current_language() is Language.ZH:
        return source
    _, source_contexts = _catalogs()
    for context in source_contexts.get(source, ()):
        translated = QtCore.QCoreApplication.translate(context, source)
        if translated != source:
            return translated
    return source


_CATALOG_CACHE = None


def _catalogs():
    """`({显示文字: 源文字}, {源文字: [context, ...]})`。

    显示文字那一份把源文和译文都作为键，遍历才能双向还原；这份目录由
    tools/build_translations.py 从 .ts 导出成 sources.json 一起打包。没有它（还没跑过
    lrelease 之类）遍历就跳过，界面保持原样而不是猜。
    """
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE
    import json

    path = os.path.join(translations_dir(), "sources.json")
    display_to_source, source_contexts = {}, {}
    try:
        with open(path, encoding="utf-8") as handle:
            entries = json.load(handle)
    except (OSError, ValueError) as error:
        logger.warning(f"读不到翻译目录（{path}）：{error}；切换语言只重译运行时文字")
        entries = []
    for entry in entries:
        source = entry.get("source")
        context = entry.get("context")
        translation = entry.get("translation")
        if not source or not context:
            continue
        source_contexts.setdefault(source, [])
        if context not in source_contexts[source]:
            source_contexts[source].append(context)
        display_to_source.setdefault(source, source)
        if translation:
            display_to_source.setdefault(translation, source)
    _CATALOG_CACHE = (display_to_source, source_contexts)
    return _CATALOG_CACHE


def invalidate_catalog_cache():
    """重新生成目录后要让遍历读到新的那份。"""
    global _CATALOG_CACHE
    _CATALOG_CACHE = None
