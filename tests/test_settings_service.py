"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

from pathlib import Path

from qtpy import QtCore

from polcam.core.preview import PreviewQuality
from polcam.core.settings import SettingsService
from polcam.core.theme import ThemeMode


def test_theme_mode_round_trips_by_name(tmp_path: Path):
    """主题存的也是名字：跟预览档一样，整数会跟着枚举顺序漂移。"""
    path = tmp_path / "settings.ini"
    service = SettingsService(ini_path=path)
    assert service.load_ui_settings().theme_mode is ThemeMode.LIGHT

    ui = service.load_ui_settings()
    ui.theme_mode = ThemeMode.DARK
    service.save_ui_settings(ui)

    assert SettingsService(ini_path=path).load_ui_settings().theme_mode is ThemeMode.DARK
    assert QtCore.QSettings(str(path), QtCore.QSettings.Format.IniFormat).value("ui/theme_mode") == "dark"


def test_unusable_theme_value_falls_back_to_light(tmp_path: Path):
    path = tmp_path / "settings.ini"
    raw = QtCore.QSettings(str(path), QtCore.QSettings.Format.IniFormat)
    raw.setValue("ui/theme_mode", "midnight")
    raw.sync()

    assert SettingsService(ini_path=path).load_ui_settings().theme_mode is ThemeMode.LIGHT


def test_preview_quality_round_trips_by_name(tmp_path: Path):
    """档位存的是名字：存整数会跟着枚举顺序漂移，老配置在新版本里读出别的档。"""
    path = tmp_path / "settings.ini"
    service = SettingsService(ini_path=path)
    assert service.load_ui_settings().preview_quality is PreviewQuality.BALANCED

    ui = service.load_ui_settings()
    ui.preview_quality = PreviewQuality.FLUID
    service.save_ui_settings(ui)

    assert SettingsService(ini_path=path).load_ui_settings().preview_quality is PreviewQuality.FLUID
    assert QtCore.QSettings(str(path), QtCore.QSettings.Format.IniFormat).value("ui/preview_quality") == "fluid"


def test_unusable_preview_quality_value_falls_back_to_balanced(tmp_path: Path):
    """坏值不能变成自动挡。

    自动档会随窗口大小改变屏上读数的口径，静默切过去等于悄悄改了测量条件；
    认不出来就回到均衡，至少行为是固定的、看得见的。
    """
    path = tmp_path / "settings.ini"
    raw = QtCore.QSettings(str(path), QtCore.QSettings.Format.IniFormat)
    raw.setValue("ui/preview_quality", "circleshield")
    raw.sync()

    assert SettingsService(ini_path=path).load_ui_settings().preview_quality is PreviewQuality.BALANCED


def test_settings_live_in_a_dedicated_file(tmp_path: Path):
    """配置要落在一个确定的文件里，跨进程、跨启动方式都还在。

    默认的 QSettings() 在 Windows 上取 registry 里的 organizationName/applicationName；
    没设过这两个时该存储是 invalid —— 实测 org='' app='python' 时 setValue 静默失败，
    读回来永远是默认值，等于用户选的目录白选。
    """
    ini = tmp_path / "PolCam" / "settings.ini"
    first = SettingsService(ini_path=ini)
    wanted = str(tmp_path / "shots")
    first.set_auto_save_directory(wanted)
    first.set_last_directory(str(tmp_path / "last"))

    assert ini.exists()
    second = SettingsService(ini_path=ini)
    assert second.get_auto_save_directory() == wanted
    assert second.get_last_directory() == str(tmp_path / "last")


def test_default_service_path_is_under_the_app_directory(tmp_path: Path, monkeypatch):
    """默认路径 = ~/PolCam/settings.ini，和日志、图库在同一个目录下。"""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    service = SettingsService()

    assert service.settings_path().endswith("settings.ini")
    assert "PolCam" in service.settings_path()


def test_retarder_settings_survive_a_restart(tmp_path: Path):
    """波片状态和角度存进去要能原样读回来，多个 α 的列表也不行。

    save_processing_settings 是遍历 to_params 写的，而 load 是逐字段拼的——只补一半的
    话，设置里看着存了，重启后被默认值悄悄覆盖。
    而且必须换一份文件来读：IniFormat 把 list 写成同一行的 `0, 45`，读回来是字符串，
    同一个 QSettings 实例读自己刚写的却还是 list，用例就假装通过了（真机实测：
    settings.ini 里躺着 retarder_fast_axis_deg=0, 45，重启后角度静默退回 0.0）。
    """
    from polcam.core.settings import ProcessingSettings

    ini_format = QtCore.QSettings.Format.IniFormat
    written_path = tmp_path / "written.ini"
    written = QtCore.QSettings(str(written_path), ini_format)
    SettingsService(written).save_processing_settings(ProcessingSettings(
        retarder_in_path=True, retarder_fast_axis_deg=[0.0, 45.0]))
    written.sync()

    # 换文件等于换实例，绕开进程内缓存，这才是用户重启应用时看到的那份内容
    restart_path = tmp_path / "restart.ini"
    restart_path.write_text(written_path.read_text(encoding="utf-8"), encoding="utf-8")
    loaded = SettingsService(QtCore.QSettings(str(restart_path), ini_format)) \
        .load_processing_settings()
    assert loaded.retarder_in_path is True
    assert loaded.retarder_fast_axis_deg == [0.0, 45.0], \
        f"多角度没能原样读回：{loaded.retarder_fast_axis_deg!r}"

    single_path = tmp_path / "single.ini"
    single_path.write_text(
        "[processing]\nretarder_in_path=true\nretarder_fast_axis_deg=30\n", encoding="utf-8")
    single = SettingsService(QtCore.QSettings(str(single_path), ini_format)) \
        .load_processing_settings()
    assert single.retarder_fast_axis_deg == 30.0, \
        f"单个角度不该被读成列表：{single.retarder_fast_axis_deg!r}"


def test_unparsable_angle_falls_back_to_the_default(tmp_path: Path):
    """坏角度退回默认值，别让设置加载整个抛出去。"""
    ini_format = QtCore.QSettings.Format.IniFormat
    path = tmp_path / "broken.ini"
    path.write_text("[processing]\nretarder_fast_axis_deg=abc\n", encoding="utf-8")

    loaded = SettingsService(QtCore.QSettings(str(path), ini_format)).load_processing_settings()
    assert loaded.retarder_fast_axis_deg == 0.0


def test_default_directories_are_under_user_polcam(tmp_path: Path):
    settings = QtCore.QSettings(str(tmp_path / "settings.ini"), QtCore.QSettings.Format.IniFormat)
    service = SettingsService(settings)

    expected_app_dir = Path.home() / "PolCam"
    expected_capture_dir = expected_app_dir / "capture"

    assert Path(service.get_app_data_directory()) == expected_app_dir
    assert Path(service.get_default_capture_directory()) == expected_capture_dir
    assert Path(service.get_auto_save_directory()) == expected_capture_dir
    assert Path(service.get_last_directory()) == expected_capture_dir


def test_auto_save_directory_is_independent_from_manual_directory(tmp_path: Path):
    settings = QtCore.QSettings(str(tmp_path / "settings.ini"), QtCore.QSettings.Format.IniFormat)
    service = SettingsService(settings)

    manual_dir = tmp_path / "manual"
    auto_dir = tmp_path / "auto"

    service.set_auto_save_directory(str(auto_dir))
    service.set_last_directory(str(manual_dir))

    assert Path(service.get_auto_save_directory()) == auto_dir
    assert Path(service.get_last_directory()) == manual_dir


def test_max_zoom_setting_round_trips(tmp_path: Path):
    settings = QtCore.QSettings(str(tmp_path / "settings.ini"), QtCore.QSettings.Format.IniFormat)
    service = SettingsService(settings)

    app_settings = service.load()
    app_settings.ui.max_zoom = 450.0
    service.save(app_settings)

    loaded = service.load()
    assert loaded.ui.max_zoom == 450.0


def test_clamp_max_zoom_only_moves_illegal_values():
    from polcam.core.settings import clamp_max_zoom

    assert clamp_max_zoom(99.0) == 100.0
    assert clamp_max_zoom(100.0) == 100.0
    assert clamp_max_zoom(450.0) == 450.0
    assert clamp_max_zoom(1000.0) == 1000.0
    assert clamp_max_zoom(1001.0) == 1000.0


def test_an_out_of_range_max_zoom_is_clamped_on_load(tmp_path: Path):
    """老配置或手改过的非法上限要在读的时候夹回来，不是等到用的人被咬。

    上限 10000 时点击放大要按几十次才到顶，而放大到那种程度的 ROI 已经不足一格偏振
    超胞，四格读数根本没有可解释的内容；下限以下则等于关掉了这个限制。
    """
    path = tmp_path / "settings.ini"
    raw = QtCore.QSettings(str(path), QtCore.QSettings.Format.IniFormat)
    raw.setValue("ui/max_zoom", 5000.0)
    raw.sync()

    assert SettingsService(ini_path=path).load_ui_settings().max_zoom == 1000.0

    raw.setValue("ui/max_zoom", 3.0)
    raw.sync()
    assert SettingsService(ini_path=path).load_ui_settings().max_zoom == 100.0


def test_a_clamped_max_zoom_is_said_out_loud(tmp_path: Path, caplog):
    """夹过了要在日志里留一句：用户的 5000 是被改掉的，不是软件自己挑的 1000。"""
    import logging

    path = tmp_path / "settings.ini"
    raw = QtCore.QSettings(str(path), QtCore.QSettings.Format.IniFormat)
    raw.setValue("ui/max_zoom", 5000.0)
    raw.sync()

    with caplog.at_level(logging.WARNING, logger="polcam.core.settings"):
        SettingsService(ini_path=path).load_ui_settings()

    assert "ui/max_zoom=5000" in caplog.text, caplog.text
    assert "1000" in caplog.text, caplog.text


def test_saving_an_illegal_max_zoom_writes_a_legal_one(tmp_path: Path):
    """写出去的值也要合法 —— 否则下次读的是同一份非法配置，日志再报一遍。"""
    path = tmp_path / "settings.ini"
    service = SettingsService(ini_path=path)

    ui = service.load_ui_settings()
    ui.max_zoom = 7.0
    service.save_ui_settings(ui)

    assert float(QtCore.QSettings(str(path), QtCore.QSettings.Format.IniFormat)
                 .value("ui/max_zoom")) == 100.0


def test_relative_directories_are_stored_absolute(tmp_path: Path, monkeypatch):
    """在设置里手打的相对目录要当场定成绝对路径，不能跟着进程的工作目录漂。

    「自动保存目录」是个自由输入框，打 `capture` 这种相对值是合法的。以前
    `_normalize_directory` 只 expanduser，于是这个值原样进了 settings.ini，采集时
    `Path('capture').mkdir()` 落在**当时的 CWD** 下：从别的文件夹（或改过"起始位置"的
    快捷方式）再启动，旧记录全指不到文件、图库一片占位图，而新的采集又开出一个同名
    不同地的目录。
    """
    ini = tmp_path / "PolCam" / "settings.ini"
    service = SettingsService(ini_path=ini)

    cwd = tmp_path / "launch_dir"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    service.set_auto_save_directory("capture")
    service.set_last_directory("last")

    saved = service.get_auto_save_directory()
    assert Path(saved).is_absolute(), f"相对路径被原样存下来了: {saved!r}"
    assert saved == str(cwd / "capture"), f"没有按设定时的工作目录定死: {saved!r}"
    assert Path(service.get_last_directory()).is_absolute()

    # 换个 CWD 再读：值不该跟着变，否则旧记录就指不到文件了
    other = tmp_path / "another_dir"
    other.mkdir()
    monkeypatch.chdir(other)
    assert service.get_auto_save_directory() == saved, "同一个设置随 CWD 变了目标目录"
