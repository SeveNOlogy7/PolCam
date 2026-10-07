"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

应用设置持久化服务
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union

from qtpy import QtCore

from .preview import PreviewQuality
from .processing_module import DEFAULT_PROCESSING_PARAMS, ProcessingMode
from .theme import ThemeMode

logger = logging.getLogger(__name__)

# 最大放大倍率的合法域。上限 10000 要点几十次才到顶，而放大到那种程度的 ROI 已经不足
# 一格偏振超胞，屏上给不出可解释的四格读数；低于 100 则等于把这个限制关掉了。
MAX_ZOOM_MIN = 100.0
MAX_ZOOM_MAX = 1000.0


def clamp_max_zoom(value: float) -> float:
    """把最大放大倍率夹进合法域。合法值原样通过，不做四舍五入。"""
    return min(MAX_ZOOM_MAX, max(MAX_ZOOM_MIN, float(value)))


@dataclass
class UISettings:
    display_mode: ProcessingMode = ProcessingMode.RAW
    last_directory: str = ""
    auto_save_directory: str = ""
    max_zoom: float = 1000.0
    # 界面明暗。存名字（同 preview_quality）：整数会跟着枚举顺序漂移。
    theme_mode: ThemeMode = ThemeMode.LIGHT
    # 连续流预览的合并档位。默认均衡（2x2 超胞合并）：装上就吃到约 3x 预览帧率，
    # 代价是屏幕上的 DoLP/AoLP 是按区域平均算的 —— 只有预览如此，保存与单帧仍走原始档。
    preview_quality: PreviewQuality = PreviewQuality.BALANCED


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
    """基于 QSettings 的轻量配置服务。

    默认写到 ~/PolCam/settings.ini，而不是靠进程元数据的 `QSettings()`。默认的
    QSettings 在 Windows 上取 registry 的 organizationName/applicationName，两者没设过
    时这个存储是 invalid —— setValue 静默失败、读出来永远是默认值，而日志和图库都已经在
    ~/PolCam 下面了，配置也该在同一处才能被用户找到。
    """

    SETTINGS_FILE = "settings.ini"

    def __init__(self, settings: Optional[QtCore.QSettings] = None,
                 ini_path: Optional[Union[str, Path]] = None):
        if settings is not None:
            self._settings = settings
            return
        path = Path(ini_path) if ini_path is not None else \
            Path(self.get_app_data_directory()) / self.SETTINGS_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        self._settings = QtCore.QSettings(str(path), QtCore.QSettings.Format.IniFormat)
        self._migrate_legacy_settings(path)

    @staticmethod
    def _migrate_legacy_settings(target_path: Path):
        """把老版本存在 registry（organizationName/applicationName）里的配置搬过来一次。

        1.0.x 的用户配好过目录和参数，换了存储位置不能让他们以为设置被清了。
        """
        if target_path.exists():
            return
        legacy = QtCore.QSettings()
        if legacy.status() != QtCore.QSettings.Status.NoError or not legacy.allKeys():
            return
        target = QtCore.QSettings(str(target_path), QtCore.QSettings.Format.IniFormat)
        for key in legacy.allKeys():
            value = legacy.value(key)
            if value is not None:
                target.setValue(key, value)
        target.sync()

    def settings_path(self) -> str:
        """当前配置文件的位置（诊断用，也让设置对话框能告诉用户去哪儿找）。"""
        return self._settings.fileName()

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
        max_zoom = self._to_float(self._settings.value("ui/max_zoom", UISettings().max_zoom),
                                  UISettings().max_zoom)
        clamped_max_zoom = clamp_max_zoom(max_zoom)
        if clamped_max_zoom != max_zoom:
            # 键名一起写出来：用户手改过配置文件，只说"1000"他不知道去哪儿找那一行。
            logger.warning(f"ui/max_zoom={max_zoom:g} 超出允许范围 "
                           f"{MAX_ZOOM_MIN:g}–{MAX_ZOOM_MAX:g}，已夹到 {clamped_max_zoom:g}")
        return UISettings(
            display_mode=self._parse_processing_mode(display_mode_name),
            last_directory=str(last_directory or ""),
            auto_save_directory=str(auto_save_directory or ""),
            max_zoom=clamped_max_zoom,
            theme_mode=ThemeMode.from_name(self._settings.value("ui/theme_mode",
                                                                UISettings().theme_mode.value)),
            preview_quality=PreviewQuality.from_name(self._settings.value("ui/preview_quality",
                                                                          UISettings().preview_quality.value)),
        )

    def save_ui_settings(self, ui_settings: UISettings):
        self._settings.setValue("ui/display_mode", ui_settings.display_mode.name)
        self._settings.setValue("ui/last_directory", self._normalize_directory(ui_settings.last_directory))
        self._settings.setValue("ui/auto_save_directory", self._normalize_directory(ui_settings.auto_save_directory))
        self._settings.setValue("ui/max_zoom", clamp_max_zoom(ui_settings.max_zoom))
        self._settings.setValue("ui/theme_mode", ui_settings.theme_mode.value)
        self._settings.setValue("ui/preview_quality", ui_settings.preview_quality.value)

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

        IniFormat 把 list 写成同一行里的 `0, 45`，读回来是**字符串**，逐项转 float 之前
        得先按逗号拆开（实测：写进去 [0.0, 45.0]，重启后 float("0, 45") 抛 ValueError,
        角度被静默退回默认 0.0，用户以为波片还按两个角度解算）。转不动就退回默认值，
        别让一个坏条目把整个设置加载搞崩。
        """
        if value is None:
            return default
        if isinstance(value, (list, tuple)):
            items = list(value)
        elif isinstance(value, str) and "," in value:
            items = value.split(",")
        else:
            items = [value]
        try:
            numbers = [float(item) for item in items if str(item).strip() != ""]
        except (TypeError, ValueError):
            return default
        if not numbers:
            return default
        return numbers[0] if len(numbers) == 1 else numbers

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
        path = Path(str(directory)).expanduser()
        if not path.is_absolute():
            # 相对值当场定成绝对路径：设置里那是个自由输入框，打 `capture` 是合法的，
            # 而采集写盘时 `mkdir` 落在**当时的 CWD**——换个文件夹（或改过"起始位置"的快捷
            # 方式）启动，旧图库记录就指不到文件、新采集又另开一个同名目录。
            path = Path.cwd() / path
        return str(path)

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
