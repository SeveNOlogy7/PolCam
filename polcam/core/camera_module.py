"""
相机模块实现
提供相机控制和图像采集功能
"""

import gxipy as gx
import numpy as np
import threading
from typing import Optional, Tuple, Dict, Any
import queue
import time
from .base_module import BaseModule
from .events import EventType, Event

class CameraModule(BaseModule):
    """相机控制模块
    
    负责:
    1. 相机的连接和断开
    2. 图像采集
    3. 相机参数控制
    4. 状态管理和错误处理
    """
    
    def __init__(self):
        super().__init__("Camera")
        self.device_manager = gx.DeviceManager()
        self._camera = None
        self._remote_feature = None
        self._is_streaming = False
        self._stream_thread: Optional[threading.Thread] = None
        self._frame_queue = queue.Queue(maxsize=2)  # 图像缓冲队列
        self._stop_flag = False
        
        # 缓存最后设置的参数值
        self._last_params = {
            'exposure': 10000.0,
            'gain': 0.0,
            'wb_auto': False
        }

    def _do_initialize(self) -> bool:
        """初始化相机设备管理器"""
        try:
            device_count, device_list = self.device_manager.update_all_device_list()
            if device_count == 0:
                self._logger.error("未找到相机设备")
                return False
            return True
        except Exception as e:
            self._logger.error(f"初始化相机管理器失败: {str(e)}")
            return False

    def _do_start(self) -> bool:
        """启动相机模块"""
        try:
            return self.connect()
        except Exception as e:
            self._logger.error(f"启动相机模块失败: {str(e)}")
            return False

    def _do_stop(self) -> bool:
        """停止相机模块"""
        try:
            if self._is_streaming:
                self.stop_streaming()
            return True
        except Exception as e:
            self._logger.error(f"停止相机模块失败: {str(e)}")
            return False

    def _do_destroy(self) -> bool:
        """销毁相机模块"""
        try:
            self.disconnect()
            return True
        except Exception as e:
            self._logger.error(f"销毁相机模块失败: {str(e)}")
            return False

    def connect(self) -> bool:
        """连接相机"""
        try:
            # 检查设备列表
            device_count, _ = self.device_manager.update_all_device_list()
            if device_count == 0:
                self._logger.error("未找到相机设备")
                return False

            # 打开第一个设备
            self._camera = self.device_manager.open_device_by_index(1)
            self._remote_feature = self._camera.get_remote_device_feature_control()
            
            # 初始化相机参数
            self._init_camera_parameters()
            
            # 发布连接成功事件
            self.publish_event(EventType.CAMERA_CONNECTED, {
                "device_info": "MER2-503-23GC-POL"
            })
            
            return True
            
        except Exception as e:
            self._logger.error(f"连接相机失败: {str(e)}")
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })
            return False

    def disconnect(self):
        """断开相机连接"""
        try:
            if self._is_streaming:
                self.stop_streaming()
                
            if self._camera:
                self._camera.close_device()
                self._camera = None
                self._remote_feature = None
                
            self.publish_event(EventType.CAMERA_DISCONNECTED)
            
        except Exception as e:
            self._logger.error(f"断开相机连接失败: {str(e)}")
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })

    def start_streaming(self):
        """开始图像采集"""
        if not self._camera or self._is_streaming:
            return
            
        try:
            # 先发送处理开始事件
            self.publish_event(EventType.PROCESSING_STARTED)
            # 确保事件被处理
            time.sleep(0.1)
            
            self._stop_flag = False
            self._camera.stream_on()
            self._is_streaming = True
            
            # 启动采集线程
            self._stream_thread = threading.Thread(
                target=self._streaming_task,
                daemon=True
            )
            self._stream_thread.start()
            
        except Exception as e:
            self._logger.error(f"启动图像采集失败: {str(e)}")
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })

    def stop_streaming(self):
        """停止图像采集"""
        if not self._is_streaming:
            return
            
        try:
            self._stop_flag = True
            if self._stream_thread:
                self._stream_thread.join(timeout=1.0)
            self._camera.stream_off()
            self._is_streaming = False
            
            # 清空图像队列
            while not self._frame_queue.empty():
                self._frame_queue.get_nowait()
                
            # 确保在最后发送处理完成事件
            self.publish_event(EventType.PROCESSING_COMPLETED)
            # 给事件处理一些时间
            time.sleep(0.1)
            
        except Exception as e:
            self._logger.error(f"停止图像采集失败: {str(e)}")
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })

    def _streaming_task(self):
        """图像采集线程任务"""
        while not self._stop_flag:
            try:
                # 获取图像
                frame = self._get_frame()
                if frame is not None:
                    # 将旧帧从队列中移除（如果队列满）
                    if self._frame_queue.full():
                        try:
                            self._frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                    
                    # 将新帧放入队列
                    self._frame_queue.put(frame)
                    
                    # 发布帧捕获事件
                    self.publish_event(EventType.FRAME_CAPTURED, {
                        "frame": frame,
                        "timestamp": time.time()
                    })
                    
            except Exception as e:
                self._logger.error(f"图像采集错误: {str(e)}")
                self.publish_event(EventType.ERROR_OCCURRED, {
                    "source": "camera",
                    "error": str(e)
                })
                time.sleep(0.1)  # 错误发生时短暂暂停

    def _get_frame(self) -> Optional[np.ndarray]:
        """获取单帧图像"""
        try:
            raw_image = self._camera.data_stream[0].get_image()
            if raw_image:
                frame = raw_image.get_numpy_array()
                return frame
        except Exception as e:
            self._logger.error(f"获取图像失败: {str(e)}")
        return None

    def get_frame(self) -> Optional[np.ndarray]:
        """获取最新图像帧"""
        try:
            return self._frame_queue.get_nowait()
        except queue.Empty:
            return None

    def _init_camera_parameters(self):
        """初始化相机参数"""
        if not self._remote_feature:
            return
            
        try:
            # 设置触发模式为关闭
            self._remote_feature.get_enum_feature("TriggerMode").set("Off")
            
            # 设置自动曝光为关闭
            self._remote_feature.get_enum_feature("ExposureAuto").set("Off")
            self.set_exposure_time(self._last_params['exposure'])
            
            # 设置自动增益为关闭
            self._remote_feature.get_enum_feature("GainAuto").set("Off")
            self.set_gain(self._last_params['gain'])
            
            # 设置白平衡模式
            self._remote_feature.get_enum_feature("BalanceWhiteAuto").set(
                "Continuous" if self._last_params['wb_auto'] else "Off"
            )
            
        except Exception as e:
            self._logger.error(f"初始化相机参数失败: {str(e)}")
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })

    def set_exposure_time(self, exposure: float):
        """设置曝光时间"""
        if not self._remote_feature:
            return
            
        try:
            self._remote_feature.get_float_feature("ExposureTime").set(exposure)
            self._last_params['exposure'] = exposure
            self.publish_event(EventType.PARAMETER_CHANGED, {
                "parameter": "exposure",
                "value": exposure
            })
        except Exception as e:
            error_msg = f"设置曝光时间失败: {str(e)}"
            self._logger.error(error_msg)
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": error_msg
            })

    def set_gain(self, gain: float):
        """设置增益值"""
        if not self._remote_feature:
            return
            
        try:
            self._remote_feature.get_float_feature("Gain").set(gain)
            self._last_params['gain'] = gain
            self.publish_event(EventType.PARAMETER_CHANGED, {
                "parameter": "gain",
                "value": gain
            })
        except Exception as e:
            self._logger.error(f"设置增益值失败: {str(e)}")

    def set_white_balance_auto(self, auto: bool):
        """设置白平衡模式"""
        if not self._remote_feature:
            return
            
        try:
            mode = "Continuous" if auto else "Off"
            self._remote_feature.get_enum_feature("BalanceWhiteAuto").set(mode)
            self._last_params['wb_auto'] = auto
            self.publish_event(EventType.PARAMETER_CHANGED, {
                "parameter": "white_balance_auto",
                "value": auto
            })
        except Exception as e:
            self._logger.error(f"设置白平衡模式失败: {str(e)}")

    def set_exposure_auto(self, auto: bool):
        """设置自动曝光模式"""
        if not self._remote_feature:
            return
            
        try:
            mode = "Continuous" if auto else "Off"
            self._remote_feature.get_enum_feature("ExposureAuto").set(mode)
            self.publish_event(EventType.PARAMETER_CHANGED, {
                "parameter": "exposure_auto",
                "value": auto
            })
        except Exception as e:
            self._logger.error(f"设置自动曝光模式失败: {str(e)}")
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })

    def set_exposure_once(self):
        """执行单次自动曝光"""
        if not self._remote_feature:
            return
            
        try:
            self._remote_feature.get_enum_feature("ExposureAuto").set("Once")
            # 等待自动曝光完成
            max_wait_time = 5  # 最大等待时间（秒）
            start_time = time.time()
            while (time.time() - start_time) < max_wait_time:
                if self._remote_feature.get_enum_feature("ExposureAuto").get() == "Off":
                    break
                time.sleep(0.1)
            else:
                self._logger.warning("单次自动曝光超时")
                
            # 更新最后的曝光值
            self._last_params['exposure'] = self.get_exposure_time()
            self.publish_event(EventType.PARAMETER_CHANGED, {
                "parameter": "exposure",
                "value": self._last_params['exposure']
            })
        except Exception as e:
            self._logger.error(f"单次自动曝光失败: {str(e)}")
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })
            raise

    def set_gain_auto(self, auto: bool):
        """设置自动增益模式"""
        if not self._remote_feature:
            return
            
        try:
            mode = "Continuous" if auto else "Off"
            self._remote_feature.get_enum_feature("GainAuto").set(mode)
            self.publish_event(EventType.PARAMETER_CHANGED, {
                "parameter": "gain_auto",
                "value": auto
            })
        except Exception as e:
            self._logger.error(f"设置自动增益模式失败: {str(e)}")
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })

    def set_gain_once(self):
        """执行单次自动增益"""
        if not self._remote_feature:
            return
            
        try:
            self._remote_feature.get_enum_feature("GainAuto").set("Once")
            # 等待自动增益完成
            max_wait_time = 5  # 最大等待时间（秒）
            start_time = time.time()
            while (time.time() - start_time) < max_wait_time:
                if self._remote_feature.get_enum_feature("GainAuto").get() == "Off":
                    break
                time.sleep(0.1)
            else:
                self._logger.warning("单次自动增益超时")
                
            # 更新最后的增益值
            self._last_params['gain'] = self.get_gain()
            self.publish_event(EventType.PARAMETER_CHANGED, {
                "parameter": "gain",
                "value": self._last_params['gain']
            })
        except Exception as e:
            self._logger.error(f"单次自动增益失败: {str(e)}")
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })
            raise

    def set_balance_white_once(self):
        """执行单次白平衡"""
        if not self._remote_feature:
            return
            
        try:
            self._remote_feature.get_enum_feature("BalanceWhiteAuto").set("Once")
            # 等待白平衡完成
            max_wait_time = 5  # 最大等待时间（秒）
            start_time = time.time()
            while (time.time() - start_time) < max_wait_time:
                if self._remote_feature.get_enum_feature("BalanceWhiteAuto").get() == "Off":
                    break
                time.sleep(0.1)
            else:
                self._logger.warning("单次白平衡超时")
                
            self.publish_event(EventType.PARAMETER_CHANGED, {
                "parameter": "white_balance",
                "value": "once_completed"
            })
        except Exception as e:
            self._logger.error(f"单次白平衡失败: {str(e)}")
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })
            raise

    def get_exposure_time(self) -> float:
        """获取当前曝光时间"""
        if not self._remote_feature:
            return 0.0
            
        try:
            return self._remote_feature.get_float_feature("ExposureTime").get()
        except Exception as e:
            self._logger.error(f"获取曝光时间失败: {str(e)}")
            return 0.0

    def get_gain(self) -> float:
        """获取当前增益值"""
        if not self._remote_feature:
            return 0.0
            
        try:
            return self._remote_feature.get_float_feature("Gain").get()
        except Exception as e:
            self._logger.error(f"获取增益值失败: {str(e)}")
            return 0.0

    def is_connected(self) -> bool:
        """返回相机是否已连接"""
        return self._camera is not None

    def is_streaming(self) -> bool:
        """返回是否正在采集图像"""
        return self._is_streaming

    def get_last_exposure(self) -> float:
        """获取最后设置的曝光值"""
        return self._last_params['exposure']

    def get_last_gain(self) -> float:
        """获取最后设置的增益值"""
        return self._last_params['gain']

    def is_wb_auto(self) -> bool:
        """获取白平衡是否为自动模式"""
        return self._last_params['wb_auto']
