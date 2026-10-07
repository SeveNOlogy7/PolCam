"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

设置对话框
"""

from __future__ import annotations

from pathlib import Path

from qtpy import QtCore, QtWidgets

from ..core.preview import PreviewQuality
from ..core.settings import (AppSettings, MAX_ZOOM_MAX, MAX_ZOOM_MIN,
                             ProcessingSettings, UISettings)
from .image_display import COLOR_MODES, mode_label


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, current_settings: AppSettings, parent=None, available_modes=None):
        super().__init__(parent)
        self._current_settings = current_settings
        # 默认显示模式只能从这台相机真能显示的模式里挑：黑白偏振机少了 3 个彩色模式，
        # 列出选不了的项只会让用户存下一个永远落不了地的偏好。
        self._available_modes = list(available_modes) if available_modes else list(COLOR_MODES)
        self.setWindowTitle(self.tr("设置"))
        self.setModal(True)
        self.resize(520, 420)
        self._setup_ui()
        self._load_settings(current_settings)

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        app_group = QtWidgets.QGroupBox(self.tr("应用偏好"))
        app_form = QtWidgets.QFormLayout(app_group)

        self.display_mode_combo = QtWidgets.QComboBox()
        for mode in self._available_modes:
            self.display_mode_combo.addItem(mode_label(mode), mode)
        app_form.addRow(self.tr("默认显示模式"), self.display_mode_combo)

        dir_layout = QtWidgets.QHBoxLayout()
        self.directory_edit = QtWidgets.QLineEdit()
        self.directory_edit.setPlaceholderText(self.tr("未设置时将使用用户目录/PolCam/capture"))
        browse_button = QtWidgets.QPushButton(self.tr("浏览..."))
        browse_button.clicked.connect(lambda: self._browse_directory(self.directory_edit, "选择默认文件目录"))
        dir_layout.addWidget(self.directory_edit)
        dir_layout.addWidget(browse_button)
        app_form.addRow(self.tr("默认文件目录"), dir_layout)

        auto_save_layout = QtWidgets.QHBoxLayout()
        self.auto_save_directory_edit = QtWidgets.QLineEdit()
        self.auto_save_directory_edit.setPlaceholderText(self.tr("未设置时将使用用户目录/PolCam/capture"))
        auto_save_browse_button = QtWidgets.QPushButton(self.tr("浏览..."))
        auto_save_browse_button.clicked.connect(
            lambda: self._browse_directory(self.auto_save_directory_edit, "选择自动保存目录")
        )
        auto_save_layout.addWidget(self.auto_save_directory_edit)
        auto_save_layout.addWidget(auto_save_browse_button)
        app_form.addRow(self.tr("自动保存目录"), auto_save_layout)

        # 范围就是合法域本身，不靠后台偷偷改：打不进非法值，用户看到的数字即存下的数字。
        self.max_zoom_spin = self._create_double_spinbox(MAX_ZOOM_MIN, MAX_ZOOM_MAX, 10.0)
        self.max_zoom_spin.setDecimals(1)
        app_form.addRow(self.tr("最大放大倍率"), self.max_zoom_spin)

        self.preview_quality_combo = QtWidgets.QComboBox()
        for quality in (PreviewQuality.AUTO, PreviewQuality.NATIVE,
                        PreviewQuality.BALANCED, PreviewQuality.FLUID):
            self.preview_quality_combo.addItem(quality.label, quality)
        # 这一项改的是屏幕上偏振读数的口径，必须把边界说清楚：只有连续流预览会被合并，
        # 单帧、图库、停止后的显示和一切保存都是全量。
        self.preview_quality_combo.setToolTip(
            self.tr("只影响连续采集时的实时预览：屏上一个像素是若干个 2x2 偏振超胞的平均，越流畅合并得越多。\n"
            "单帧拍摄、打开图库/文件、停止后的显示与所有保存、导出不受影响，始终按全分辨率解算。\n"
            "自动挡按窗口大小决定：放大到源图装得下就回到全分辨率。"))
        app_form.addRow(self.tr("实时预览质量"), self.preview_quality_combo)

        processing_group = QtWidgets.QGroupBox(self.tr("处理参数"))
        processing_form = QtWidgets.QFormLayout(processing_group)

        self.wb_auto_check = QtWidgets.QCheckBox(self.tr("启用自动白平衡"))
        processing_form.addRow(self.tr("白平衡"), self.wb_auto_check)

        self.angle_combo = QtWidgets.QComboBox()
        for angle in (0, 45, 90, 135):
            self.angle_combo.addItem(f"{angle}°", angle)
        processing_form.addRow(self.tr("默认偏振角度"), self.angle_combo)

        self.pol_color_mode_check = QtWidgets.QCheckBox(self.tr("偏振分析默认使用彩色图像"))
        processing_form.addRow(self.tr("偏振模式"), self.pol_color_mode_check)

        self.pol_wb_auto_check = QtWidgets.QCheckBox(self.tr("偏振分析彩色图像启用自动白平衡"))
        processing_form.addRow(self.tr("偏振白平衡"), self.pol_wb_auto_check)

        self.brightness_spin = self._create_double_spinbox(0.0, 2.0, 0.1)
        processing_form.addRow(self.tr("亮度"), self.brightness_spin)

        self.contrast_spin = self._create_double_spinbox(0.0, 2.0, 0.1)
        processing_form.addRow(self.tr("对比度"), self.contrast_spin)

        self.sharpness_spin = self._create_double_spinbox(0.0, 1.0, 0.1)
        processing_form.addRow(self.tr("锐化"), self.sharpness_spin)

        self.denoise_spin = self._create_double_spinbox(0.0, 1.0, 0.1)
        processing_form.addRow(self.tr("降噪"), self.denoise_spin)

        layout.addWidget(app_group)
        layout.addWidget(processing_group)

        standard_buttons = (
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel |
            QtWidgets.QDialogButtonBox.StandardButton.RestoreDefaults
        )
        self.button_box = QtWidgets.QDialogButtonBox(standard_buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        restore_button = self.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.RestoreDefaults)
        if restore_button is not None:
            restore_button.clicked.connect(self._restore_defaults)
        layout.addWidget(self.button_box)

    def _create_double_spinbox(self, minimum: float, maximum: float, step: float) -> QtWidgets.QDoubleSpinBox:
        spin_box = QtWidgets.QDoubleSpinBox()
        spin_box.setDecimals(1)
        spin_box.setRange(minimum, maximum)
        spin_box.setSingleStep(step)
        return spin_box

    def _load_settings(self, settings: AppSettings):
        ui_settings = settings.ui
        processing_settings = settings.processing
        # 波片状态不在本对话框里编辑，保存时要沿用当前生效的值，别把它重置回默认
        self._processing_baseline = processing_settings

        index = self.display_mode_combo.findData(ui_settings.display_mode)
        self.display_mode_combo.setCurrentIndex(index if index >= 0 else 0)
        self.directory_edit.setText(ui_settings.last_directory)
        self.auto_save_directory_edit.setText(ui_settings.auto_save_directory)
        self.max_zoom_spin.setValue(ui_settings.max_zoom)
        self._set_combo_value(self.preview_quality_combo, ui_settings.preview_quality)

        self.wb_auto_check.setChecked(processing_settings.wb_auto)
        self._set_combo_value(self.angle_combo, processing_settings.selected_angle)
        self.pol_color_mode_check.setChecked(processing_settings.pol_color_mode)
        self.pol_wb_auto_check.setChecked(processing_settings.pol_wb_auto)
        self.brightness_spin.setValue(processing_settings.brightness)
        self.contrast_spin.setValue(processing_settings.contrast)
        self.sharpness_spin.setValue(processing_settings.sharpness)
        self.denoise_spin.setValue(processing_settings.denoise)

    def _restore_defaults(self):
        """把偏好恢复到默认，但波片留在用户放好的位置。

        波片在不在光路、快轴多少度是光路里的物理状态，本页没有它的控件；把它一起
        重置回出厂值等于偷偷换了 Stokes 解算式（真机实测：设成"在光路/45°"后点一次
        恢复默认，参数就变成 False/0.0）。所以这两项沿用对话框打开时生效的值。
        """
        defaults = AppSettings()
        defaults.processing.retarder_in_path = self._processing_baseline.retarder_in_path
        defaults.processing.retarder_fast_axis_deg = (
            self._processing_baseline.retarder_fast_axis_deg)
        self._load_settings(defaults)

    def _browse_directory(self, target_edit: QtWidgets.QLineEdit, title: str):
        start_dir = target_edit.text().strip() or str(Path.home() / "PolCam" / "capture")
        selected = QtWidgets.QFileDialog.getExistingDirectory(self, title, start_dir)
        if selected:
            target_edit.setText(selected)

    def get_settings(self) -> AppSettings:
        display_mode = self.display_mode_combo.currentData(QtCore.Qt.ItemDataRole.UserRole)
        directory = self.directory_edit.text().strip()
        auto_save_directory = self.auto_save_directory_edit.text().strip()
        # findData 认不到值时返回 -1，currentData 会是 None：那不能让档位悄悄变成默认值，
        # 沿用打开时的值更诚实（这条路径只在枚举与下拉项不一致时到达，属于程序自己的错）。
        preview_quality = self.preview_quality_combo.currentData(QtCore.Qt.ItemDataRole.UserRole)
        if preview_quality is None:
            preview_quality = self._current_settings.ui.preview_quality
        return AppSettings(
            ui=UISettings(
                display_mode=display_mode,
                last_directory=directory,
                auto_save_directory=auto_save_directory,
                max_zoom=self.max_zoom_spin.value(),
                # 本页没有换肤控件：明暗档由右上角那个按钮管，保存设置时原样带回去，
                # 不许把用户当前的皮肤抹成默认值。
                theme_mode=self._current_settings.ui.theme_mode,
                preview_quality=preview_quality,
            ),
            processing=ProcessingSettings(
                wb_auto=self.wb_auto_check.isChecked(),
                brightness=self.brightness_spin.value(),
                contrast=self.contrast_spin.value(),
                sharpness=self.sharpness_spin.value(),
                denoise=self.denoise_spin.value(),
                selected_angle=int(self.angle_combo.currentData(QtCore.Qt.ItemDataRole.UserRole)),
                pol_color_mode=self.pol_color_mode_check.isChecked(),
                pol_wb_auto=self.pol_wb_auto_check.isChecked(),
                retarder_in_path=getattr(self._processing_baseline, 'retarder_in_path', False),
                retarder_fast_axis_deg=getattr(
                    self._processing_baseline, 'retarder_fast_axis_deg', 0.0),
            )
        )

    def _set_combo_value(self, combo: QtWidgets.QComboBox, value: int):
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)
