"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.

应用设置持久化服务
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from qtpy import QtCore

from .processing_module import DEFAULT_PROCESSING_PARAMS, ProcessingMode


@dataclass
class UISettings:
    display_mode: ProcessingMode = ProcessingMode.RAW
    last_directory: str = ""


@dataclass
class ProcessingSettings:
    wb_auto: bool = bool(DEFAULT_PROCESSING_PARAMS["wb_auto"])
    brightness: float = float(DEFAULT_PROCESSING_PARAMS["brightness"])
    contrast: float = float(DEFAULT_PROCESSING_PARAMS["contrast"])
    sharpness: float = float(DEFAULT_PROCESSING_PARAMS["sharpness"])
    denoise: float = float(DEFAULT_PROCESSING_PARAMS["denoise"])
    selected_angle: int = int(DEFAULT_PROCESSING_PARAMS["selected_angle"])
    pol_color_mode: bool = bool(DEFAULT_PROCESSING_PARAMS["pol_color_mode"])
    pol_wb_auto: bool = bool(DEFAULT_PROCESSING_PARAMS["pol_wb_auto"])

    def to_params(self) -> Dict[str, Any]:
        return {
            "wb_auto": self.wb_auto,
            "brightness": self.brightness,
            "contrast": self.contrast,
            "sharpness": self.sharpness,
            "denoise": self.denoise,
            "selected_angle": self.selected_angle,
            "pol_color_mode": self.pol_color_mode,
            "pol_wb_auto": self.pol_wb_auto,
        }

    @classmethod
    def from_params(cls, params: Dict[str, Any]) -> "ProcessingSettings":
        defaults = DEFAULT_PROCESSING_PARAMS.copy()
        defaults.update({key: value for key, value in params.items() if key in defaults})
        return cls(
            wb_auto=bool(defaults["wb_auto"]),
            brightness=float(defaults["brightness"]),
            contrast=float(defaults["contrast"]),
            sharpness=float(defaults["sharpness"]),
            denoise=float(defaults["denoise"]),
            selected_angle=int(defaults["selected_angle"]),
            pol_color_mode=bool(defaults["pol_color_mode"]),
            pol_wb_auto=bool(defaults["pol_wb_auto"]),
        )


@dataclass
class AppSettings:
    ui: UISettings = field(default_factory=UISettings)
    processing: ProcessingSettings = field(default_factory=ProcessingSettings)


class SettingsService:
    """基于 QSettings 的轻量配置服务。"""

    def __init__(self, settings: Optional[QtCore.QSettings] = None):
        self._settings = settings or QtCore.QSettings()

    def load(self) -> AppSettings:
        return AppSettings(
            ui=self.load_ui_settings(),
            processing=self.load_processing_settings(),
        )

    def save(self, app_settings: AppSettings):
        self.save_ui_settings(app_settings.ui)
        self.save_processing_settings(app_settings.processing)
        self._settings.sync()

    def load_ui_settings(self) -> UISettings:
        display_mode_name = self._settings.value("ui/display_mode", ProcessingMode.RAW.name)
        last_directory = self._settings.value("ui/last_directory", "")
        return UISettings(
            display_mode=self._parse_processing_mode(display_mode_name),
            last_directory=str(last_directory or ""),
        )

    def save_ui_settings(self, ui_settings: UISettings):
        self._settings.setValue("ui/display_mode", ui_settings.display_mode.name)
        self._settings.setValue("ui/last_directory", self._normalize_directory(ui_settings.last_directory))

    def load_processing_settings(self) -> ProcessingSettings:
        defaults = ProcessingSettings()
        return ProcessingSettings(
            wb_auto=self._to_bool(self._settings.value("processing/wb_auto", defaults.wb_auto)),
            brightness=self._to_float(self._settings.value("processing/brightness", defaults.brightness), defaults.brightness),
            contrast=self._to_float(self._settings.value("processing/contrast", defaults.contrast), defaults.contrast),
            sharpness=self._to_float(self._settings.value("processing/sharpness", defaults.sharpness), defaults.sharpness),
            denoise=self._to_float(self._settings.value("processing/denoise", defaults.denoise), defaults.denoise),
            selected_angle=self._to_int(self._settings.value("processing/selected_angle", defaults.selected_angle), defaults.selected_angle),
            pol_color_mode=self._to_bool(self._settings.value("processing/pol_color_mode", defaults.pol_color_mode)),
            pol_wb_auto=self._to_bool(self._settings.value("processing/pol_wb_auto", defaults.pol_wb_auto)),
        )

    def save_processing_settings(self, processing_settings: ProcessingSettings):
        params = processing_settings.to_params()
        for key, value in params.items():
            self._settings.setValue(f"processing/{key}", value)

    def load_window_geometry(self) -> Optional[QtCore.QByteArray]:
        geometry = self._settings.value("ui/window_geometry")
        if isinstance(geometry, QtCore.QByteArray) and not geometry.isEmpty():
            return geometry
        if isinstance(geometry, (bytes, bytearray)):
            return QtCore.QByteArray(bytes(geometry))
        return None

    def save_window_geometry(self, geometry: QtCore.QByteArray):
        if geometry is not None:
            self._settings.setValue("ui/window_geometry", geometry)
            self._settings.sync()

    def get_last_directory(self) -> str:
        directory = self._settings.value("ui/last_directory", "")
        directory = self._normalize_directory(directory)
        return directory or str(Path.home())

    def set_last_directory(self, directory: str):
        normalized = self._normalize_directory(directory)
        if normalized:
            self._settings.setValue("ui/last_directory", normalized)
            self._settings.sync()

    def _parse_processing_mode(self, value: Any) -> ProcessingMode:
        if isinstance(value, ProcessingMode):
            return value
        try:
            return ProcessingMode[str(value)]
        except (KeyError, TypeError):
            return ProcessingMode.RAW

    def _normalize_directory(self, directory: Any) -> str:
        if not directory:
            return ""
        return str(Path(str(directory)).expanduser())

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @staticmethod
    def _to_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
