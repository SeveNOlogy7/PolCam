"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

把 core.theme 的取值落到 QApplication 上：风格、调色板、以及跟着调色板走色的图标。

刻意用 Fusion：两套配色要在 Windows 与 Linux 上长成同一个样子，而原生风格各有自己的
取色逻辑（Windows 读系统注册表，Linux 跟桌面主题），只有 Fusion 完整听 QPalette 的话。
代价是浅色档也得自带一套取值，不能再指望系统给 —— 所以 core/theme.py 里浅色那组
照今天的外观写死。
"""
import os

from qtpy import QtCore, QtGui, QtWidgets

from ..core.theme import ThemeMode, tokens_for

MODE_PROPERTY = "polcamThemeMode"

_ICON_CACHE = {}


def current_mode(app=None) -> ThemeMode:
    """当前档位。没应用过主题时是浅色，与改造前的外观一致。"""
    app = app or QtWidgets.QApplication.instance()
    if app is None:
        return ThemeMode.LIGHT
    return ThemeMode.from_name(app.property(MODE_PROPERTY))


def palette_for(mode: ThemeMode) -> QtGui.QPalette:
    tokens = tokens_for(mode)

    def color(role):
        return QtGui.QColor(getattr(tokens, role))

    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, color('window'))
    palette.setColor(QtGui.QPalette.WindowText, color('window_text'))
    palette.setColor(QtGui.QPalette.Base, color('base'))
    palette.setColor(QtGui.QPalette.AlternateBase, color('window'))
    palette.setColor(QtGui.QPalette.Text, color('text'))
    palette.setColor(QtGui.QPalette.Button, color('button'))
    palette.setColor(QtGui.QPalette.ButtonText, color('button_text'))
    palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor("#ff5555"))
    palette.setColor(QtGui.QPalette.Highlight, color('highlight'))
    palette.setColor(QtGui.QPalette.HighlightedText, color('highlighted_text'))
    palette.setColor(QtGui.QPalette.ToolTipBase, color('tooltip_base'))
    palette.setColor(QtGui.QPalette.ToolTipText, color('tooltip_text'))
    palette.setColor(QtGui.QPalette.PlaceholderText, color('placeholder_text'))
    # 禁用态要显式给：不给的话 Qt 沿用同组的颜色，深色档下"禁用"和"可用"看着一样。
    for group in (QtGui.QPalette.Disabled,):
        palette.setColor(group, QtGui.QPalette.WindowText, color('disabled_text'))
        palette.setColor(group, QtGui.QPalette.Text, color('disabled_text'))
        palette.setColor(group, QtGui.QPalette.ButtonText, color('disabled_text'))
    return palette


def apply_theme(app, mode: ThemeMode) -> ThemeMode:
    """换肤。已经在屏幕上的控件会跟着收到 PaletteChange。"""
    app.setStyle("Fusion")
    app.setPalette(palette_for(mode))
    app.setProperty(MODE_PROPERTY, mode.value)
    _ICON_CACHE.clear()
    return mode


def themed_icon(path: str, size: QtCore.QSize = None) -> QtGui.QIcon:
    """按当前调色板给单色 SVG 上色。

    资源里的图标是 #333 或 currentColor 的图形，贴在深色工具栏上等于没有；与其为两个
    档各存一份 svg，不如在这里跟着 ButtonText 上一次色。缓存键带上档位与尺寸，换肤
    之后不会继续发旧颜色的图。
    """
    mode = current_mode()
    size = size or QtCore.QSize(32, 32)
    key = (path, mode.value, size.width(), size.height())
    cached = _ICON_CACHE.get(key)
    if cached is not None:
        return cached

    color = QtWidgets.QApplication.instance().palette().color(QtGui.QPalette.ButtonText)
    icon = QtGui.QIcon(path)
    renderer = None
    try:
        from qtpy import QtSvg

        renderer = QtSvg.QSvgRenderer(path)
    except Exception:
        renderer = None
    if renderer is not None and renderer.isValid():
        pixmap = QtGui.QPixmap(size)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        renderer.render(painter)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), color)
        painter.end()
        icon = QtGui.QIcon(pixmap)
    _ICON_CACHE[key] = icon
    return icon


def icon_path(filename: str) -> str:
    return os.path.join(os.path.dirname(__file__), "..", "resources", "icon", filename)
