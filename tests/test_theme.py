"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

暗夜/浅色两套主题的取值、落地与图标跟随。
"""
import dataclasses

import pytest
from qtpy import QtCore, QtGui, QtWidgets

from polcam.core.theme import ThemeMode, tokens_for


def _contrast(first: QtGui.QColor, second: QtGui.QColor) -> float:
    """WCAG 2.x 对比度：只看亮度关系，正好是"文字压不压得住底色"的口径。"""
    def luminance(color):
        channels = []
        for raw in (color.redF(), color.greenF(), color.blueF()):
            channels.append(raw / 12.92 if raw <= 0.03928 else ((raw + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    high, low = max(luminance(first), luminance(second)), min(luminance(first), luminance(second))
    return (high + 0.05) / (low + 0.05)


def test_unknown_theme_name_falls_back_to_light():
    """认不出来的值回落到浅色：默认档变了要能被人看出来，静默换肤更糟。"""
    assert ThemeMode.from_name("circleshield") is ThemeMode.LIGHT
    assert ThemeMode.from_name(None) is ThemeMode.LIGHT
    assert ThemeMode.from_name("DARK") is ThemeMode.DARK


def test_theme_names_round_trip():
    for mode in ThemeMode:
        assert ThemeMode.from_name(mode.value) is mode


def test_toggling_is_an_involution():
    for mode in ThemeMode:
        assert mode.toggled().toggled() is mode
    assert ThemeMode.LIGHT.toggled() is ThemeMode.DARK


def test_both_modes_declare_the_same_roles():
    light = tokens_for(ThemeMode.LIGHT)
    dark = tokens_for(ThemeMode.DARK)
    assert {f.name for f in dataclasses.fields(light)} == {f.name for f in dataclasses.fields(dark)}


def test_every_token_is_a_hex_color():
    for mode in ThemeMode:
        tokens = tokens_for(mode)
        for field in dataclasses.fields(tokens):
            value = getattr(tokens, field.name)
            assert isinstance(value, str) and value.startswith("#"), field.name
            assert QtGui.QColor(value).isValid(), f"{mode}:{field.name}={value}"


def test_dark_text_has_readable_contrast_on_the_dark_surface():
    tokens = tokens_for(ThemeMode.DARK)
    window = QtGui.QColor(tokens.window)
    assert window.lightnessF() < 0.4, "底色不够暗"
    assert _contrast(window, QtGui.QColor(tokens.window_text)) >= 4.5
    assert _contrast(QtGui.QColor(tokens.base), QtGui.QColor(tokens.text)) >= 4.5
    assert _contrast(QtGui.QColor(tokens.highlight), QtGui.QColor(tokens.highlighted_text)) >= 4.5


def test_light_mode_keeps_the_look_it_already_has():
    """浅色档不许顺手换掉今天的配色：窗口浅灰、输入白底、高亮是系统蓝。"""
    tokens = tokens_for(ThemeMode.LIGHT)
    assert QtGui.QColor(tokens.window).lightnessF() > 0.85
    assert QtGui.QColor(tokens.base).name() == "#ffffff"
    assert QtGui.QColor(tokens.splitter_idle).name() == "#aeb6c1"
    assert QtGui.QColor(tokens.splitter_hover).name() == "#7f95ac"
    assert QtGui.QColor(tokens.splitter_pressed).name() == "#667c94"


def test_applying_a_theme_switches_to_fusion_and_sets_the_palette(qapp):
    from polcam.gui import app_theme

    app_theme.apply_theme(qapp, ThemeMode.DARK)
    try:
        assert qapp.style().objectName() == "fusion"
        palette = qapp.palette()
        tokens = tokens_for(ThemeMode.DARK)
        assert palette.color(QtGui.QPalette.Window).name() == QtGui.QColor(tokens.window).name()
        assert palette.color(QtGui.QPalette.Base).name() == QtGui.QColor(tokens.base).name()
        assert palette.color(QtGui.QPalette.Highlight).name() == QtGui.QColor(tokens.highlight).name()
        assert app_theme.current_mode(qapp) is ThemeMode.DARK
        # 禁用态要看得见但不是主角
        assert palette.color(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText).lightnessF() < 0.7
    finally:
        app_theme.apply_theme(qapp, ThemeMode.LIGHT)
    assert app_theme.current_mode(qapp) is ThemeMode.LIGHT


def test_the_splitter_border_follows_the_current_theme(qapp):
    """分割条描边以前是写死的 #aeb6c1，暗夜下贴在深色面板上等于没有边界。"""
    from polcam.gui import app_theme
    from polcam.gui.styles import Styles

    app_theme.apply_theme(qapp, ThemeMode.DARK)
    try:
        splitter = QtWidgets.QSplitter()
        Styles.apply_splitter_style(splitter)
        sheet = splitter.styleSheet()
        tokens = tokens_for(ThemeMode.DARK)
        assert tokens.splitter_idle in sheet
        assert tokens.splitter_hover in sheet
        assert tokens.splitter_pressed in sheet
        assert tokens_for(ThemeMode.LIGHT).splitter_idle not in sheet
    finally:
        app_theme.apply_theme(qapp, ThemeMode.LIGHT)


def _icon_pixels(icon) -> list:
    """图标里"确实画了东西"的那些像素，取还原后的真颜色。

    两个坑：`QColor(image.pixel(...))` 会把打包值里的 alpha 丢掉（一个透明像素读出来是
    不透明的黑），要用 `pixelColor`；而 ARGB32 的存储是预乘的，边缘反锯齿像素的颜色被
    alpha 缩过，所以只取接近不透明的部分。
    """
    pixmap = icon.pixmap(QtCore.QSize(24, 24))
    assert not pixmap.isNull()
    image = pixmap.toImage().convertToFormat(QtGui.QImage.Format.Format_ARGB32)
    found = []
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() >= 200:
                found.append(color)
    return found


@pytest.mark.parametrize("mode", list(ThemeMode))
def test_toolbar_icons_follow_the_palette_instead_of_their_baked_fill(qapp, mode):
    """图标是单色 SVG（#333 或 currentColor），贴到深色工具栏上必须跟着调色板换色。

    否则 #333 的图形压在 #31363b 的工具栏上，用户只会看见一排空白格子。
    """
    import os
    from polcam.gui import app_theme

    svg = os.path.join(os.path.dirname(app_theme.__file__), "..", "resources", "icon", "settings.svg")
    app_theme.apply_theme(qapp, mode)
    try:
        pixels = _icon_pixels(app_theme.themed_icon(svg))
        assert pixels, "图标整个是透明的"
        average = QtGui.QColor(
            int(sum(p.red() for p in pixels) / len(pixels)),
            int(sum(p.green() for p in pixels) / len(pixels)),
            int(sum(p.blue() for p in pixels) / len(pixels)),
        )
        expected = qapp.palette().color(QtGui.QPalette.ButtonText)
        assert _contrast(average, QtGui.QColor(tokens_for(mode).window)) >= 3.0, (
            f"{mode} 档下图标和工具栏底色对比不足：{average.name()} vs {tokens_for(mode).window}")
        assert _contrast(average, expected) < 1.5, "图标没跟着 ButtonText 走"
    finally:
        app_theme.apply_theme(qapp, ThemeMode.LIGHT)


def test_the_toolbar_toggle_changes_the_theme_and_remembers_it(main_window):
    """右上角一键换肤：点了立刻生效，并且把"当前档的另一档"写进设置。"""
    from qtpy import QtWidgets

    from polcam.gui import app_theme

    app = QtWidgets.QApplication.instance()
    app_theme.apply_theme(app, ThemeMode.LIGHT)
    action = main_window.toolbar.theme_action
    try:
        assert "暗夜" in action.toolTip(), action.toolTip()

        action.trigger()
        assert app_theme.current_mode(app) is ThemeMode.DARK
        assert main_window.build_current_settings().ui.theme_mode is ThemeMode.DARK
        assert "浅色" in action.toolTip(), "提示还写着上一个档"
        # 换肤之后分割条要跟着重描，不然还是那条浅色描边
        assert tokens_for(ThemeMode.DARK).splitter_idle in main_window.top_splitter.styleSheet()

        action.trigger()
        assert app_theme.current_mode(app) is ThemeMode.LIGHT
        assert main_window.build_current_settings().ui.theme_mode is ThemeMode.LIGHT
    finally:
        app_theme.apply_theme(app, ThemeMode.LIGHT)


def test_every_top_bar_icon_follows_the_theme(main_window):
    """换肤之后，顶栏那排图标也得跟着换颜色。

    它们是启动时按当时的调色板渲出来的位图，不会自己跟着 palette 变 —— 真平台截图抓到
    深色工具栏上留着一排 #1e1e1e 的图形。
    """
    from qtpy import QtWidgets

    from polcam.gui import app_theme

    app = QtWidgets.QApplication.instance()
    toolbar = main_window.toolbar
    actions = [toolbar.save_raw_action, toolbar.save_result_action, toolbar.open_raw_action,
               toolbar.settings_action, toolbar.about_action, toolbar.help_action,
               toolbar.theme_action]
    try:
        app_theme.apply_theme(app, ThemeMode.DARK)
        toolbar.refresh_theme()
        for action in actions:
            pixels = _icon_pixels(action.icon())
            assert pixels, f"{action.text()} 的图标是空的"
            light = sum(1 for p in pixels if p.lightnessF() > 0.7) / len(pixels)
            assert light > 0.9, f"{action.text()} 在暗夜档下还是深色图形（亮像素 {light:.0%}）"

        app_theme.apply_theme(app, ThemeMode.LIGHT)
        toolbar.refresh_theme()
        for action in actions:
            pixels = _icon_pixels(action.icon())
            dark = sum(1 for p in pixels if p.lightnessF() < 0.3) / len(pixels)
            assert dark > 0.9, f"{action.text()} 在浅色档下变成了浅色图形（暗像素 {dark:.0%}）"
    finally:
        app_theme.apply_theme(app, ThemeMode.LIGHT)


def test_saving_settings_leaves_the_skin_alone(main_window):
    """设置页没有换肤控件，保存与"恢复默认"都不许把皮肤抹回浅色。

    和波片同一条规矩：本页管不着的东西，就沿用外面生效的那个值。
    """
    from qtpy import QtWidgets

    from polcam.gui import app_theme
    from polcam.gui.settings_dialog import SettingsDialog

    app = QtWidgets.QApplication.instance()
    app_theme.apply_theme(app, ThemeMode.DARK)
    main_window._theme_mode = ThemeMode.DARK
    try:
        dialog = SettingsDialog(main_window.build_current_settings(), main_window)
        assert dialog.get_settings().ui.theme_mode is ThemeMode.DARK
        dialog._restore_defaults()
        assert dialog.get_settings().ui.theme_mode is ThemeMode.DARK, \
            "恢复默认把用户的皮肤换了，而这一页根本没有那个开关"
    finally:
        app_theme.apply_theme(app, ThemeMode.LIGHT)


def test_the_window_comes_up_in_the_saved_theme(qapp):
    """重启后要回到用户离开时的那个档，不能每次都回浅色。"""
    import shiboken6

    from polcam.core.settings import SettingsService
    from polcam.gui import app_theme
    from polcam.gui.main_window import MainWindow

    service = SettingsService()
    settings = service.load()
    settings.ui.theme_mode = ThemeMode.DARK
    service.save(settings)

    window = MainWindow()
    try:
        assert app_theme.current_mode(qapp) is ThemeMode.DARK
        assert window.image_display.palette().color(QtGui.QPalette.Base).name() == \
            QtGui.QColor(tokens_for(ThemeMode.DARK).base).name()
    finally:
        window.close()
        shiboken6.delete(window)
        app_theme.apply_theme(qapp, ThemeMode.LIGHT)
        fresh = SettingsService()
        restored = fresh.load()
        restored.ui.theme_mode = ThemeMode.LIGHT
        fresh.save(restored)
