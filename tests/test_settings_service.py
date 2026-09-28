"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

from pathlib import Path

from qtpy import QtCore

from polcam.core.settings import SettingsService


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


def test_retarder_settings_survive_the_round_trip(tmp_path: Path):
    """波片状态和角度存进去要能原样读回来，多个 α 的列表也不行。

    save_processing_settings 是遍历 to_params 写的，而 load 是逐字段拼的——只补一半的
    话，设置里看着存了，重启后被默认值悄悄覆盖。
    """
    from polcam.core.settings import ProcessingSettings

    settings = QtCore.QSettings(str(tmp_path / "settings.ini"), QtCore.QSettings.Format.IniFormat)
    service = SettingsService(settings)
    service.save_processing_settings(ProcessingSettings(
        retarder_in_path=True, retarder_fast_axis_deg=[0.0, 45.0]))

    loaded = service.load_processing_settings()
    assert loaded.retarder_in_path is True
    assert [float(angle) for angle in loaded.retarder_fast_axis_deg] == [0.0, 45.0]

    service.save_processing_settings(ProcessingSettings(
        retarder_in_path=True, retarder_fast_axis_deg=30.0))
    single = service.load_processing_settings()
    assert single.retarder_fast_axis_deg == 30.0


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
    app_settings.ui.max_zoom = 2500.0
    service.save(app_settings)

    loaded = service.load()
    assert loaded.ui.max_zoom == 2500.0
