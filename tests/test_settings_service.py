"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

from pathlib import Path

from qtpy import QtCore

from polcam.core.settings import SettingsService


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
