"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.

设置对话框
"""

from __future__ import annotations

from pathlib import Path

from qtpy import QtCore, QtWidgets

from ..core.settings import AppSettings, ProcessingSettings, UISettings
from .image_display import COLOR_MODES, MODE_LABELS


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, current_settings: AppSettings, parent=None):
        super().__init__(parent)
        self._current_settings = current_settings
        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(520, 420)
        self._setup_ui()
        self._load_settings(current_settings)

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        app_group = QtWidgets.QGroupBox("应用偏好")
        app_form = QtWidgets.QFormLayout(app_group)

        self.display_mode_combo = QtWidgets.QComboBox()
        for mode in COLOR_MODES:
            self.display_mode_combo.addItem(MODE_LABELS[mode], mode)
        app_form.addRow("默认显示模式", self.display_mode_combo)

        dir_layout = QtWidgets.QHBoxLayout()
        self.directory_edit = QtWidgets.QLineEdit()
        self.directory_edit.setPlaceholderText("未设置时将使用用户主目录")
        browse_button = QtWidgets.QPushButton("浏览...")
        browse_button.clicked.connect(self._browse_directory)
        dir_layout.addWidget(self.directory_edit)
        dir_layout.addWidget(browse_button)
        app_form.addRow("默认文件目录", dir_layout)

        processing_group = QtWidgets.QGroupBox("处理参数")
        processing_form = QtWidgets.QFormLayout(processing_group)

        self.wb_auto_check = QtWidgets.QCheckBox("启用自动白平衡")
        processing_form.addRow("白平衡", self.wb_auto_check)

        self.angle_combo = QtWidgets.QComboBox()
        for angle in (0, 45, 90, 135):
            self.angle_combo.addItem(f"{angle}°", angle)
        processing_form.addRow("默认偏振角度", self.angle_combo)

        self.pol_color_mode_check = QtWidgets.QCheckBox("偏振分析默认使用彩色图像")
        processing_form.addRow("偏振模式", self.pol_color_mode_check)

        self.pol_wb_auto_check = QtWidgets.QCheckBox("偏振分析彩色图像启用自动白平衡")
        processing_form.addRow("偏振白平衡", self.pol_wb_auto_check)

        self.brightness_spin = self._create_double_spinbox(0.0, 2.0, 0.1)
        processing_form.addRow("亮度", self.brightness_spin)

        self.contrast_spin = self._create_double_spinbox(0.0, 2.0, 0.1)
        processing_form.addRow("对比度", self.contrast_spin)

        self.sharpness_spin = self._create_double_spinbox(0.0, 1.0, 0.1)
        processing_form.addRow("锐化", self.sharpness_spin)

        self.denoise_spin = self._create_double_spinbox(0.0, 1.0, 0.1)
        processing_form.addRow("降噪", self.denoise_spin)

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

        index = self.display_mode_combo.findData(ui_settings.display_mode)
        self.display_mode_combo.setCurrentIndex(index if index >= 0 else 0)
        self.directory_edit.setText(ui_settings.last_directory)

        self.wb_auto_check.setChecked(processing_settings.wb_auto)
        self._set_combo_value(self.angle_combo, processing_settings.selected_angle)
        self.pol_color_mode_check.setChecked(processing_settings.pol_color_mode)
        self.pol_wb_auto_check.setChecked(processing_settings.pol_wb_auto)
        self.brightness_spin.setValue(processing_settings.brightness)
        self.contrast_spin.setValue(processing_settings.contrast)
        self.sharpness_spin.setValue(processing_settings.sharpness)
        self.denoise_spin.setValue(processing_settings.denoise)

    def _restore_defaults(self):
        self._load_settings(AppSettings())

    def _browse_directory(self):
        start_dir = self.directory_edit.text().strip() or str(Path.home())
        selected = QtWidgets.QFileDialog.getExistingDirectory(self, "选择默认文件目录", start_dir)
        if selected:
            self.directory_edit.setText(selected)

    def get_settings(self) -> AppSettings:
        display_mode = self.display_mode_combo.currentData(QtCore.Qt.ItemDataRole.UserRole)
        directory = self.directory_edit.text().strip()
        return AppSettings(
            ui=UISettings(
                display_mode=display_mode,
                last_directory=directory,
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
            )
        )

    def _set_combo_value(self, combo: QtWidgets.QComboBox, value: int):
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)
