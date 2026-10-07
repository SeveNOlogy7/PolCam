"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

中英切换：立即重刷、记住档位、目录缺失时不撒谎，以及目录完整性门本身。
"""
import subprocess
import sys

import pytest
from qtpy import QtGui, QtWidgets

from polcam.core.language import Language
from polcam.gui import i18n


@pytest.fixture(autouse=True)
def _leave_the_app_as_found(qapp):
    """语言档改的是 QApplication 与设置文件，同进程后来的测试不能继承它。"""
    from polcam.core.settings import SettingsService

    palette = qapp.palette()
    style_name = qapp.style().objectName()
    language = i18n.current_language(qapp)
    settings = SettingsService()
    saved = settings.load()
    yield
    i18n.apply_language(qapp, language)
    qapp.setPalette(palette)
    qapp.setStyle(style_name)
    restored = settings.load()
    restored.ui.language = saved.ui.language
    settings.save(restored)


def test_unknown_language_name_falls_back_to_the_source_language():
    assert Language.from_name("klingon") is Language.ZH
    assert Language.from_name(None) is Language.ZH
    assert Language.from_name("EN") is Language.EN
    # 已经是枚举就原样通过：apply_language 在入口上调它，返回默认档会让英文永远装不上
    assert Language.from_name(Language.EN) is Language.EN


def test_toggling_the_button_switches_every_visible_text_at_once(main_window):
    """点一次就全变了 —— 不重启、不重开窗口。

    构造期设进控件的文字不会自己跟着 QTranslator 变，所以这里验的是重译那条路真的走到了
    每一类控件：按钮、工具栏动作、分组标题、下拉框条目、状态栏。
    """
    action = main_window.toolbar.language_action
    assert "英文" in action.toolTip()

    action.trigger()

    assert i18n.current_language(QtWidgets.QApplication.instance()) is Language.EN
    assert main_window.camera_control.connect_btn.text() == "Connect Camera"
    assert main_window.toolbar.save_raw_action.text() == "Save Raw Image"
    assert main_window.gallery_panel.open_button.text() == "Open"
    assert main_window.image_display.display_mode.itemText(0) == "Raw Image"
    assert main_window.windowTitle() == "Polarization Camera Control"
    assert "Chinese" in action.toolTip(), "提示还写着上一个语言"

    action.trigger()
    assert main_window.camera_control.connect_btn.text() == "连接相机"
    assert main_window.image_display.display_mode.itemText(0) == "原始图像"
    assert "英文" in action.toolTip()


def test_runtime_messages_are_computed_in_the_current_language(main_window):
    """运行时文案是现算的：切完语言之后再生成一条，就该是新语言。

    这里直接收控制器要发出去的那句，而不是状态栏上的字 —— 状态栏还会被处理完成、
    采集状态这些事件覆盖，那样测的就不是语言了。
    """
    controller = main_window.image_display.toolbar_controller
    sent = []
    controller._show_status_message = sent.append

    main_window.toolbar.language_action.trigger()
    controller._handle_cursor_mode(True)
    assert sent == ["Cursor mode on"], sent

    sent.clear()
    main_window.toolbar.language_action.trigger()
    controller._handle_cursor_mode(True)
    assert sent == ["游标模式已开启"], sent


def test_the_chosen_language_survives_a_restart(qapp):
    import shiboken6

    from polcam.core.settings import SettingsService
    from polcam.gui.main_window import MainWindow

    service = SettingsService()
    settings = service.load()
    settings.ui.language = Language.EN
    service.save(settings)

    window = MainWindow()
    try:
        assert i18n.current_language(qapp) is Language.EN
        assert window.camera_control.capture_btn.text() == "Single Frame"
    finally:
        window.close()
        shiboken6.delete(window)


def test_a_missing_catalog_does_not_claim_to_have_switched(qapp, tmp_path, caplog, monkeypatch):
    """目录装不上就老实说还是中文。

    否则用户按下按钮、界面满屏汉字、按钮却写着"当前：English" —— 那比没有这个功能更糟。
    """
    import logging

    monkeypatch.setattr(i18n, "translations_dir", lambda: str(tmp_path))
    with caplog.at_level(logging.WARNING, logger="polcam.gui.i18n"):
        effective = i18n.apply_language(qapp, Language.EN)
    assert effective is Language.ZH
    assert i18n.current_language(qapp) is Language.ZH
    assert "polcam_en" in caplog.text


def test_the_language_round_trips_through_the_ini(tmp_path):
    from qtpy import QtCore

    from polcam.core.settings import SettingsService

    path = tmp_path / "settings.ini"
    service = SettingsService(ini_path=path)
    ui = service.load_ui_settings()
    ui.language = Language.EN
    service.save_ui_settings(ui)

    assert QtCore.QSettings(str(path), QtCore.QSettings.Format.IniFormat).value("ui/language") == "en"
    assert SettingsService(ini_path=path).load_ui_settings().language is Language.EN


def test_guide_page_lines_wrap_so_english_is_not_cut_off(main_window, qapp):
    """引导页的正文必须能换行 —— 内容列被限到 460px，英文同一句要长两三成。

    真平台英文截图抓到过 `... reads “Connect Camer`：后半句直接没了。中文刚好塞得下，
    所以这个缺陷只在换语言之后才露头。
    """
    display = main_window.image_display
    main_window.toolbar.language_action.trigger()
    display.show_help_view()
    main_window.resize(1200, 800)
    qapp.processEvents()

    bodies = [label for label in display.help_view.findChildren(QtWidgets.QLabel)
              if label.text().startswith("·")]
    assert bodies, "引导页没找到正文行"
    for label in bodies:
        assert label.wordWrap(), f"这一行没开换行：{label.text()[:40]}"
    # 有牙：内容列的最大宽度写死在 460，至少有一行单排着放不下 —— 否则这条测试
    # 什么都没保证（真平台英文截图里被裁掉的正是这种行）。
    metrics = QtGui.QFontMetrics(bodies[0].font())
    widest = max(metrics.horizontalAdvance(label.text()) for label in bodies)
    assert widest > 460, f"最长的一行只有 {widest}px，测不出换行这件事"


def test_english_mode_leaves_no_chinese_on_screen(main_window):
    """英文档下，界面上不该还有汉字。

    判据是"文字里有汉字"而不是"文字等于某条源文" —— 后者会放过压根没进目录的漏网字面量。
    真平台探针抓到过 StatusIndicator 的悬停提示就是这么漏掉的。
    """
    from polcam.gui.settings_dialog import SettingsDialog

    def has_cjk(text):
        return any("\u4e00" <= ch <= "\u9fff" for ch in text or "")

    main_window.toolbar.language_action.trigger()
    targets = [main_window] + main_window.findChildren(QtWidgets.QWidget)
    targets += [a for w in targets for a in w.actions()]
    stuck = []
    for target in targets:
        for reader in ("text", "toolTip"):
            shown = getattr(target, reader, lambda: "")()
            if has_cjk(shown):
                stuck.append(f"{type(target).__name__}.{reader}={shown[:50]}")
    for combo in main_window.findChildren(QtWidgets.QComboBox):
        for index in range(combo.count()):
            if has_cjk(combo.itemText(index)):
                stuck.append(f"QComboBox.item[{index}]={combo.itemText(index)}")
    dialog = SettingsDialog(main_window.build_current_settings(), main_window)
    for target in [dialog] + dialog.findChildren(QtWidgets.QWidget):
        for reader in ("text", "toolTip"):
            shown = getattr(target, reader, lambda: "")()
            if has_cjk(shown):
                stuck.append(f"Settings {type(target).__name__}.{reader}={shown[:50]}")
    assert not stuck, "英文档下还有中文：\n" + "\n".join(sorted(set(stuck)))


def test_the_catalog_is_complete_and_up_to_date():
    """把 CI 那道门也在测试里跑一遍。

    否则有人在 setText 里塞了没包 tr() 的中文、或者改了 .ts 忘了重新生成 .qm，
    只有推到 CI 才会发现 —— 而本地跑测试的人看不到任何异常。
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "build_translations.py"), "--check"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert result.returncode == 0, result.stdout + result.stderr
