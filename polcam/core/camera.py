"""
MIT License
Copyright (c) 2024 PolCam Contributors
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

    def connect(self, device_index: int = 1) -> bool:
        try:
            dev_num, _ = self.device_manager.update_all_device_list()
            if dev_num == 0:
                self.logger.error("未找到相机设备")
                return False

            self.camera = self.device_manager.open_device_by_index(device_index)
            self.remote_feature = self.camera.get_remote_device_feature_control()

            # 设置触发模式为关闭
            try:
                trigger_mode = self.remote_feature.get_enum_feature("TriggerMode")
                trigger_mode.set("Off")
            except Exception as e:
                self.logger.warning(f"设置触发模式失败: {e}")

            return True
        except Exception as e:
            self.logger.error(f"连接相机失败: {e}")
            return False

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
                # 确保时间参数为浮点数类型
                exposure_time = float(time_us)
                self.remote_feature.get_float_feature("ExposureTime").set(exposure_time)
            except Exception as e:
                self.logger.error(f"设置曝光时间失败: {e}")

    def set_exposure_auto(self, auto: bool):
        if self.camera:
            self.remote_feature.get_enum_feature("ExposureAuto").set(
                "Continuous" if auto else "Off"
            )

    def set_gain(self, gain: float):
        if self.camera:
            self.remote_feature.get_float_feature("Gain").set(gain)

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
