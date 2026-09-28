"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
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
    auto_save_directory: str = ""
    max_zoom: float = 1000.0


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
    retarder_in_path: bool = bool(DEFAULT_PROCESSING_PARAMS["retarder_in_path"])
    # 单个角度（float）或角度序列（拨片一次给多个 α）都要能原样装回去
    retarder_fast_axis_deg: Any = DEFAULT_PROCESSING_PARAMS["retarder_fast_axis_deg"]

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
            "retarder_in_path": self.retarder_in_path,
            "retarder_fast_axis_deg": self.retarder_fast_axis_deg,
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
            retarder_in_path=bool(defaults["retarder_in_path"]),
            retarder_fast_axis_deg=defaults["retarder_fast_axis_deg"],
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
        last_directory = self._settings.value("ui/last_directory", self.get_default_capture_directory())
        auto_save_directory = self._settings.value("ui/auto_save_directory", self.get_default_capture_directory())
        return UISettings(
            display_mode=self._parse_processing_mode(display_mode_name),
            last_directory=str(last_directory or ""),
            auto_save_directory=str(auto_save_directory or ""),
            max_zoom=self._to_float(self._settings.value("ui/max_zoom", UISettings().max_zoom), UISettings().max_zoom),
        )

    def save_ui_settings(self, ui_settings: UISettings):
        self._settings.setValue("ui/display_mode", ui_settings.display_mode.name)
        self._settings.setValue("ui/last_directory", self._normalize_directory(ui_settings.last_directory))
        self._settings.setValue("ui/auto_save_directory", self._normalize_directory(ui_settings.auto_save_directory))
        self._settings.setValue("ui/max_zoom", max(1.0, float(ui_settings.max_zoom)))

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
            retarder_in_path=self._to_bool(self._settings.value("processing/retarder_in_path", defaults.retarder_in_path)),
            retarder_fast_axis_deg=self._to_angles(
                self._settings.value("processing/retarder_fast_axis_deg", defaults.retarder_fast_axis_deg),
                defaults.retarder_fast_axis_deg),
        )

    def _to_angles(self, value: Any, default: Any) -> Any:
        """快轴角度：可能是单个数，也可能是自动拨片给的一串角度。

        QSettings 把列表读回成字符串列表，所以逐项转 float；转不动就退回默认值，
        别让一个坏条目把整个设置加载搞崩。
        """
        if value is None:
            return default
        if isinstance(value, (list, tuple)):
            try:
                return [float(item) for item in value]
            except (TypeError, ValueError):
                return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

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
        directory = self._settings.value("ui/last_directory", self.get_default_capture_directory())
        directory = self._normalize_directory(directory)
        return directory or self.get_default_capture_directory()

    def set_last_directory(self, directory: str):
        normalized = self._normalize_directory(directory)
        if normalized:
            self._settings.setValue("ui/last_directory", normalized)
            self._settings.sync()

    def get_app_data_directory(self) -> str:
        return str((Path.home() / "PolCam").expanduser())

    def get_default_capture_directory(self) -> str:
        return str((Path(self.get_app_data_directory()) / "capture").expanduser())

    def get_auto_save_directory(self) -> str:
        directory = self._settings.value("ui/auto_save_directory", self.get_default_capture_directory())
        directory = self._normalize_directory(directory)
        return directory or self.get_default_capture_directory()

    def set_auto_save_directory(self, directory: str):
        normalized = self._normalize_directory(directory)
        if normalized:
            self._settings.setValue("ui/auto_save_directory", normalized)
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
