"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

import gxipy as gx
import numpy as np
import logging
from typing import Optional, Tuple

class Camera:
    def __init__(self):
        self.device_manager = gx.DeviceManager()
        self.camera = None
        self.is_streaming = False
        self.logger = logging.getLogger(__name__)
        self._last_exposure = 10000.0  # 默认曝光时间
        self._last_gain = 0.0         # 默认增益值

    def connect(self, device_index: int = 1) -> tuple[bool, str]:
        try:
            dev_num, _ = self.device_manager.update_all_device_list()
            if dev_num == 0:
                self.logger.error("未找到相机设备")
                return False, "未找到相机设备"

            self.camera = self.device_manager.open_device_by_index(device_index)
            self.remote_feature = self.camera.get_remote_device_feature_control()

            # 设置触发模式为关闭
            try:
                trigger_mode = self.remote_feature.get_enum_feature("TriggerMode")
                trigger_mode.set("Off")
            except Exception as e:
                self.logger.warning(f"设置触发模式失败: {e}")

            # 获取相机当前参数
            try:
                self._last_exposure = self.get_exposure_time()
                self._last_gain = self.get_gain()
                self.logger.info(f"读取相机参数: 曝光时间={self._last_exposure}us, 增益={self._last_gain}dB")
            except Exception as e:
                self.logger.warning(f"读取相机参数失败: {e}")

            return True, ""
        except Exception as e:
            error_msg = f"连接相机失败: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg

    def disconnect(self):
        if self.camera:
            if self.is_streaming:
                self.stop_streaming()
            self.camera.close_device()
            self.camera = None

    def start_streaming(self):
        if self.camera and not self.is_streaming:
            self.camera.stream_on()
            self.is_streaming = True

    def stop_streaming(self):
        if self.camera and self.is_streaming:
            self.camera.stream_off()
            self.is_streaming = False

    def get_frame(self) -> Optional[np.ndarray]:
        try:
            if not self.is_streaming:
                self.start_streaming()
                raw_image = self.camera.data_stream[0].get_image()
                self.stop_streaming()
            else:
                raw_image = self.camera.data_stream[0].get_image()
                
            if raw_image is not None:
                return raw_image.get_numpy_array()
            return None
        except Exception as e:
            self.logger.error(f"获取图像失败: {e}")
            return None

    def set_exposure_time(self, time_us: float):
        if self.camera:
            try:
                exposure_time = float(time_us)
                self.remote_feature.get_float_feature("ExposureTime").set(exposure_time)
                self._last_exposure = exposure_time
            except Exception as e:
                self.logger.error(f"设置曝光时间失败: {e}")

    def set_exposure_auto(self, auto: bool):
        if self.camera:
            self.remote_feature.get_enum_feature("ExposureAuto").set(
                "Continuous" if auto else "Off"
            )

    def set_gain(self, gain: float):
        if self.camera:
            try:
                self.remote_feature.get_float_feature("Gain").set(gain)
                self._last_gain = gain
            except Exception as e:
                self.logger.error(f"设置增益失败: {e}")

    def set_gain_auto(self, auto: bool):
        if self.camera:
            self.remote_feature.get_enum_feature("GainAuto").set(
                "Continuous" if auto else "Off"
            )

    def set_balance_white_auto(self, auto: bool):
        if self.camera:
            self.remote_feature.get_enum_feature("BalanceWhiteAuto").set(
                "Continuous" if auto else "Off"
            )

    def get_exposure_time(self) -> float:
        """获取当前曝光时间"""
        if self.camera:
            try:
                return self.remote_feature.get_float_feature("ExposureTime").get()
            except Exception as e:
                self.logger.error(f"获取曝光时间失败: {e}")
        return 0.0

    def get_gain(self) -> float:
        """获取当前增益值"""
        if self.camera:
            try:
                return self.remote_feature.get_float_feature("Gain").get()
            except Exception as e:
                self.logger.error(f"获取增益值失败: {e}")
        return 0.0

    def get_last_exposure(self) -> float:
        """获取上次的曝光时间"""
        return self._last_exposure

    def get_last_gain(self) -> float:
        """获取上次的增益值"""
        return self._last_gain
