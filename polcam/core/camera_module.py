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
        self._frame_queue = queue.Queue(maxsize=4)  # 增加队列大小
        self._stop_flag = False
        
        # 修改软件白平衡相关的标志
        self._use_software_wb = True  # 默认使用软件白平衡
        self._wb_auto = False        # 白平衡自动模式标志
        
        # 缓存最后设置的参数值
        self._last_params = {
            'exposure': 10000.0,
            'gain': 0.0,
            'wb_auto': False,
            'software_wb_auto': False  # 添加软件白平衡状态
        }
        self._connected = False  # 添加连接状态标志
        self._device_indices = []  # 添加已打开设备的索引列表

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
            # 确保相机被正确关闭
            self.disconnect()
            # 清空设备列表
            self._device_indices = []
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

            # 查找可用的设备索引
            device_index = 1
            while device_index in self._device_indices:
                device_index += 1
            
            # 打开设备
            try:
                self._camera = self.device_manager.open_device_by_index(device_index)
            except Exception as e:
                    raise e

            if self._camera is None:
                self._logger.error("打开相机失败")
                return False
                
            self._device_indices.append(device_index)
            self._remote_feature = self._camera.get_remote_device_feature_control()
            
            # 初始化相机参数
            self._init_camera_parameters()
            
            # 设置连接状态
            self._connected = True
            
            # 发布连接成功事件
            self.publish_event(EventType.CAMERA_CONNECTED, {
                "device_info": "MER2-503-23GC-POL"
            })
            
            self._logger.info("相机连接成功")
            return True
            
        except Exception as e:
            self._logger.error(f"连接相机失败: {str(e)}")
            self._camera = None
            self._remote_feature = None
            self._connected = False
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
                
            self._connected = False
            self._device_indices.clear()  # 清空设备索引列表
            
            # 等待资源释放
            time.sleep(0.1)
            
            self.publish_event(EventType.CAMERA_DISCONNECTED)
            
        except Exception as e:
            self._logger.error(f"断开相机连接失败: {str(e)}")
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })
        finally:
            # 确保状态被重置
            self._camera = None
            self._remote_feature = None
            self._connected = False
            self._device_indices.clear()

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
            
            # 确保数据流关闭
            self._camera.stream_off()
            time.sleep(0.1)  # 等待数据流完全关闭
            
            # 清空图像队列
            while not self._frame_queue.empty():
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    break
                    
            self._is_streaming = False
            
            # 确保在最后发送处理完成事件
            self.publish_event(EventType.PROCESSING_COMPLETED)
            
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
                raw_image = self._camera.data_stream[0].get_image()
                if raw_image:
                    frame = raw_image.get_numpy_array()
                    if frame is not None:
                        # 当队列满时，移除最旧的帧
                        try:
                            if self._frame_queue.full():
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
                else:
                    time.sleep(0.001)  # 短暂暂停避免空转
                    
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
            if not self._is_streaming:
                # 单帧采集时，临时开启数据流
                self._camera.stream_on()
                time.sleep(0.1)  # 等待数据流启动
                
                try:
                    raw_image = self._camera.data_stream[0].get_image()
                    if raw_image:
                        frame = raw_image.get_numpy_array()
                        return frame
                finally:
                    # 确保数据流被关闭
                    self._camera.stream_off()
                    time.sleep(0.1)  # 等待数据流关闭
            else:
                # 连续采集模式下增加等待时间
                try:
                    return self._frame_queue.get(timeout=0.1)  # 等待最多100ms
                except queue.Empty:
                    self._logger.error("图像队列为空")
                    return None
                    
        except Exception as e:
            self._logger.error(f"获取图像失败: {str(e)}")
            raise  # 抛出异常以便上层处理
            
        return None

    def _init_camera_parameters(self):
        """初始化相机参数"""
        if not self._remote_feature:
            return
            
        try:
            # 设置触发模式为关闭
            self._remote_feature.get_enum_feature("TriggerMode").set("Off")
            
            # 读取并设置曝光参数
            try:
                current_exposure = self._remote_feature.get_float_feature("ExposureTime").get()
                self._last_params['exposure'] = current_exposure
                self._remote_feature.get_enum_feature("ExposureAuto").set("Off")
                self.publish_event(EventType.PARAMETER_CHANGED, {
                    "parameter": "exposure",
                    "value": current_exposure
                })
            except Exception as e:
                self._logger.error(f"读取曝光参数失败: {str(e)}")
            
            # 读取并设置增益参数
            try:
                current_gain = self._remote_feature.get_float_feature("Gain").get()
                self._last_params['gain'] = current_gain
                self._remote_feature.get_enum_feature("GainAuto").set("Off")
                self.publish_event(EventType.PARAMETER_CHANGED, {
                    "parameter": "gain",
                    "value": current_gain
                })
            except Exception as e:
                self._logger.error(f"读取增益参数失败: {str(e)}")
            
            # 尝试设置硬件白平衡模式
            try:
                self._remote_feature.get_enum_feature("BalanceWhiteAuto")
                self._use_software_wb = False  # 硬件支持白平衡
            except Exception as e:
                self._logger.info("硬件不支持白平衡，将使用软件白平衡")
                self._use_software_wb = True
                
            # 如果需要打开白平衡，根据是否支持硬件白平衡选择处理方式
            if self._last_params['wb_auto']:
                if not self._use_software_wb:
                    self._remote_feature.get_enum_feature("BalanceWhiteAuto").set("Continuous")
                else:
                    self._last_params['software_wb_auto'] = True
            
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
        try:
            if not self._use_software_wb:
                # 尝试使用硬件白平衡
                self._remote_feature.get_enum_feature("BalanceWhiteAuto").set(
                    "Continuous" if auto else "Off"
                )
            else:
                # 仅更新软件白平衡标志
                self._wb_auto = auto
                self._logger.info(f"使用软件白平衡，自动模式: {auto}")
            
            # 发布参数改变事件
            self.publish_event(EventType.PARAMETER_CHANGED, {
                "parameter": "white_balance_auto",
                "value": auto,
                "is_software": self._use_software_wb
            })
        except Exception as e:
            self._logger.error(f"设置白平衡模式失败: {str(e)}")
            # 出错时切换到软件白平衡
            self._use_software_wb = True
            self._wb_auto = auto

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
        try:
            if not self._use_software_wb:
                # 尝试使用硬件白平衡
                self._remote_feature.get_enum_feature("BalanceWhiteAuto").set("Once")
                # 等待白平衡完成
                max_wait_time = 5
                start_time = time.time()
                while (time.time() - start_time) < max_wait_time:
                    if self._remote_feature.get_enum_feature("BalanceWhiteAuto").get() == "Off":
                        break
                    time.sleep(0.1)
                else:
                    self._logger.warning("单次白平衡超时")
            else:
                # 软件白平衡逻辑
                self._logger.info("执行软件单次白平衡")
                # 这里可以触发一个事件，让图像处理模块执行一次软件白平衡
                self.publish_event(EventType.PARAMETER_CHANGED, {
                    "parameter": "white_balance",
                    "value": "once_requested"
                })
                
            self.publish_event(EventType.PARAMETER_CHANGED, {
                "parameter": "white_balance",
                "value": "once_completed"
            })
        except Exception as e:
            self._logger.error(f"单次白平衡失败: {str(e)}")
            # 出错时切换到软件白平衡
            self._use_software_wb = True
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
        # 修改连接状态的判断逻辑
        return (self._camera is not None and 
                self._remote_feature is not None and 
                self._connected)

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
        if self._use_software_wb:
            return self._wb_auto
        try:
            return self._remote_feature.get_enum_feature("BalanceWhiteAuto").get() == "Continuous"
        except:
            self._use_software_wb = True
            return self._wb_auto

    def is_using_software_wb(self) -> bool:
        """获取是否使用软件白平衡"""
        return self._use_software_wb
