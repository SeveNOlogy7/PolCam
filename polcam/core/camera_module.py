"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

相机模块实现
提供相机控制和图像采集功能
"""

try:
    import gxipy as gx
except Exception as _gxipy_error:
    # 未安装大恒 Galaxy 驱动时 gxipy 在 import 阶段就会抛错（GALAXY_GENICAM_ROOT
    # 缺失是 KeyError，不是它只捕获的 OSError）。此时相机功能整体降级，但应用
    # 仍应能启动并读取已保存的原始图像。
    gx = None
    GXIPY_IMPORT_ERROR = str(_gxipy_error)
else:
    GXIPY_IMPORT_ERROR = ""

import numpy as np
import threading
import weakref
from typing import Optional, Tuple, Dict, Any
from enum import Enum
import queue
import re
import time
from .base_module import BaseModule
from .events import EventType, Event
from .image_processor import ImageProcessor


# 写给用户看的参数名，和"谁在自动模式下接管了这个参数"，用于把 SDK 的原始报错
# 翻成一句能照着做的话（真机实测：超范围抛 OutOfRange，自动模式开着抛
# InvalidAccess "Node is not writable"）
_FLOAT_FEATURE_LABELS = {
    "ExposureTime": "曝光时间",
    "Gain": "增益",
}
_FLOAT_AUTO_OWNERS = {
    "ExposureTime": (("ExposureAuto", "自动曝光"),),
    "Gain": (("GainAuto", "自动增益"),),
}


class CameraType(Enum):
    """相机类型"""
    COLOR = "color"                  # 彩色偏振相机
    MONO = "mono"                    # 黑白偏振相机
    NORMAL_COLOR = "normal_color"    # 普通彩色相机（非偏振）


# 已知相机型号 → 类型映射，新型号在此添加
KNOWN_CAMERA_TYPES = {
    "MER2-503-23GC-P POL": CameraType.COLOR,
    "MER2-502-79U3M-HS POL": CameraType.MONO,
    "ME2S-2440-16U3C": CameraType.NORMAL_COLOR,
}

class CameraModule(BaseModule):
    """相机控制模块
    
    负责:
    1. 相机的连接和断开
    2. 图像采集
    3. 相机参数控制
    4. 状态管理和错误处理
    """
    
    # 抓帧线程单次等待设备的上限，以及 stop_streaming 等它退出的预算。
    # 前者必须明显小于后者，否则停流时读者还挂在 get_image 里。
    GRAB_TIMEOUT_MS = 100
    STREAM_JOIN_TIMEOUT_S = 2.0
    # 曝光上限实测是 1s，等待窗口要跟着曝光走：固定 100ms 的话长曝光下每秒要空转
    # 十次轮询，而停流也只能等下一轮才发现该收手。上限留在 join 预算之内。
    GRAB_TIMEOUT_MAX_MS = 1500
    # 采集在跑却一帧不来，超过多久才说话（按等待窗口的倍数与这个下限取大）
    STARVATION_MIN_MS = 3000
    STARVATION_FACTOR = 3.0
    # 连续失败多少次就收手。不封顶的话线一断就是每秒十条错误事件，而 GUI 每条弹一个
    # 模态框，队列涨得比人点掉的速度快。
    STREAM_ERROR_LIMIT = 20

    def __init__(self):
        super().__init__("Camera")
        self.device_manager = gx.DeviceManager() if gx is not None else None
        self._camera = None
        self._remote_feature = None
        self._is_streaming = False
        # 有一次单帧抓取正占着设备（stream_on→等曝光→stream_off），ROI 写入要等它结束
        self._one_shot_grab = False
        self._stream_thread: Optional[threading.Thread] = None
        self._frame_queue = queue.Queue(maxsize=4)  # 增加队列大小
        self._stop_flag = False
        self._stream_error_count = 0  # 连续采集失败次数，成功一帧就清零
        self._last_frame_at = 0.0     # 最近真正收到帧的时刻，用来判"采不到帧"
        self._starvation_reported = False
        
        # 缓存最后设置的参数值
        self._last_params = {
            'exposure': 10000.0,
            'gain': 0.0
        }
        self._connected = False  # 添加连接状态标志
        self._device_indices = []  # 添加已打开设备的索引列表
        self._target_device_index = None  # 指定要连接的目标设备索引
        self._camera_type: Optional[CameraType] = None  # 相机类型（彩色/黑白）
        self._bayer_pattern: Optional[int] = None  # Bayer 排列 (PixelColorFilter 值)
        self._pixel_format: Optional[int] = None   # 像素格式 (GxPixelFormatEntry 值)
        self._pixel_format_name: Optional[str] = None  # 像素格式名，如 'Mono10'（决定位深）

    def _do_initialize(self) -> bool:
        """初始化相机设备管理器"""
        if self.device_manager is None:
            self._logger.warning(f"Galaxy SDK 不可用，相机功能已降级: {GXIPY_IMPORT_ERROR}")
            return False
        try:
            device_count, _ = self.device_manager.update_all_device_list()
            if device_count == 0:
                self._logger.warning("未找到相机设备，将在连接时重新检测")
            return True  # 始终成功，设备检测移到连接时
        except Exception as e:
            # 探测结果本来就要丢掉，所以这里不能因为一次抖动就把模块判死：
            # _initialized 留在 False 会让 BaseModule.start() 在 connect() 之前短路，
            # 于是这台相机在这次会话里再也连不上，而没人会重试 initialize。
            self._logger.warning(f"启动时枚举设备失败，稍后连接时重试: {str(e)}")
            return True

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
            self.disconnect()
            # disconnect 自己会在真的关掉之后清索引；这里不能无条件清，否则断开被推迟时
            # 我们既占着设备又忘了占着哪个，重连会去抢下一个索引然后失败。
            return not self._connected
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

    @property
    def sdk_available(self) -> bool:
        """大恒 Galaxy SDK 是否可用。不可用时相机相关功能整体降级。"""
        return self.device_manager is not None

    def enumerate_devices(self) -> tuple:
        """枚举可用设备

        Returns:
            (device_count, device_info_list) tuple
        """
        if self.device_manager is None:
            self._logger.warning("Galaxy SDK 不可用，跳过设备枚举")
            return 0, []
        try:
            return self.device_manager.update_all_device_list()
        except Exception as e:
            self._logger.error(f"枚举设备失败: {str(e)}")
            return 0, []

    def set_target_device_index(self, index: int):
        """设置要连接的目标设备索引（1-based）

        Args:
            index: 设备索引，对应 device_info_list 中的 index 字段
        """
        self._target_device_index = index

    def get_camera_type(self) -> Optional[CameraType]:
        """获取检测到的相机类型"""
        return self._camera_type

    def get_bayer_pattern(self) -> Optional[int]:
        """获取检测到的 Bayer 排列 (GxPixelColorFilterEntry 值)"""
        return self._bayer_pattern

    def _detect_camera_type(self, model_name: str) -> CameraType:
        """检测相机类型（彩色偏振/黑白偏振/普通彩色）

        检测策略:
        1. 查询 PixelColorFilter 特征，记录 Bayer 排列
        2. 查 KNOWN_CAMERA_TYPES 映射表
        3. 未知型号根据 PixelColorFilter 推断
        4. 均失败则默认 COLOR
        """
        # 1. 查询 PixelColorFilter（所有相机通用，记录 Bayer 排列）
        self._bayer_pattern = None
        try:
            if self._camera and self._camera.PixelColorFilter.is_implemented():
                value, desc = self._camera.PixelColorFilter.get()
                self._bayer_pattern = value
                self._logger.info(
                    f"PixelColorFilter: {model_name} -> value={value}, desc={desc}"
                )
        except Exception as e:
            self._logger.warning(f"查询 PixelColorFilter 失败: {e}")

        # 2. 查映射表
        if model_name in KNOWN_CAMERA_TYPES:
            camera_type = KNOWN_CAMERA_TYPES[model_name]
            self._logger.info(f"相机类型（映射表）: {model_name} -> {camera_type.value}")
            return camera_type

        # 3. 未知型号根据 PixelColorFilter 推断（无法区分偏振/非偏振，默认偏振）
        if self._bayer_pattern is not None:
            camera_type = CameraType.MONO if self._bayer_pattern == 0 else CameraType.COLOR
            self._logger.info(
                f"相机类型（PixelColorFilter推断）: {model_name} -> {camera_type.value}"
            )
            return camera_type

        # 4. 偏振传感器的 PixelColorFilter 读不出来（实测这台 POL 相机就是
        #    InvalidAccess），改用设备自报的可选像素格式判断黑白/彩色
        camera_type = self._infer_camera_type_from_pixel_formats()
        if camera_type is not None:
            self._logger.warning(
                f"型号不在映射表里，按设备像素格式推断为 {camera_type.value}: "
                f"{model_name}，请确认是否偏振相机"
            )
            return camera_type

        # 5. 默认 COLOR
        self._logger.warning(f"无法检测相机类型: {model_name}，默认为彩色偏振相机")
        return CameraType.COLOR

    def _infer_camera_type_from_pixel_formats(self) -> Optional[CameraType]:
        """用设备自报的 PixelFormat 候选列表判断传感器是黑白还是彩色。

        只有 Mono* 格式 → 黑白 MPFA；出现 Bayer/RGB/BGR → 彩色 CPFA。读不到就返回
        None，让上层按默认值走。
        """
        if not self._remote_feature:
            return None
        try:
            entries = self._remote_feature.get_enum_feature("PixelFormat").get_range()
        except Exception as e:
            self._logger.warning(f"读取 PixelFormat 候选列表失败: {e}")
            return None

        if isinstance(entries, dict):
            names = list(entries)
        else:
            names = [entry['symbolic'] for entry in entries]
        if not names:
            return None
        if all(name.startswith('Mono') for name in names):
            return CameraType.MONO
        if any(name.startswith(('Bayer', 'RGB', 'BGR')) for name in names):
            return CameraType.COLOR
        return None

    def connect(self) -> bool:
        """连接相机"""
        # 一进来就把指定的设备取走：留到成功路径才清的话，这次只要在任何一处提前
        # 返回（SDK 不可用、枚举到 0 台、打开失败），那个索引就会留给下一次连接 ——
        # 而下一次可能是"没人选设备"的单相机自动连接，结果是打开一台用户没选的相机
        target_device_index = self._target_device_index
        self._target_device_index = None

        if target_device_index is None and self._connected and self._camera is not None:
            # _do_start 已经连过一次。再走一遍会去取下一个空闲索引，真机实测只有一台相机
            # 时报 "DeviceManager.open_device_by_index: invalid index"，然后失败路径把正在
            # 用的那台关掉并标成未连接 —— 一次多余的 connect() 就能把好的连接弄断。
            self._logger.info("相机已连接，忽略重复的连接请求")
            return True

        try:
            if self.device_manager is None:
                self._logger.error("Galaxy SDK 不可用，无法连接相机")
                return False

            # 检查设备列表
            device_count, device_list = self.device_manager.update_all_device_list()
            if device_count == 0:
                self._logger.error("未找到相机设备")
                return False

            # 确定要连接的设备索引
            if target_device_index is not None:
                device_index = target_device_index
            else:
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

            self._remote_feature = self._camera.get_remote_device_feature_control()
            cached_params = self._last_params.copy()

            # 初始化相机参数
            self._init_camera_parameters()
            self._last_params.update(cached_params)
            self._restore_cached_parameters()

            # 设置连接状态
            self._connected = True
            # 到这里才算真的占住这一格；失败路径上设备会被关掉，索引也就无需回滚
            self._device_indices.append(device_index)

            # 获取实际设备信息
            device_info = device_list[device_index - 1] if device_list and len(device_list) >= device_index else {}
            if isinstance(device_info, dict):
                display_name = device_info.get('model_name', 'Unknown')
            else:
                display_name = str(device_info or 'Unknown')

            # 检测相机类型
            self._camera_type = self._detect_camera_type(display_name)

            # 查询像素格式（用于 gxipy 格式转换）
            self._pixel_format = None
            try:
                pixel_format_value, pixel_format_str = self._remote_feature.get_enum_feature("PixelFormat").get()
                self._pixel_format = pixel_format_value
                self._pixel_format_name = pixel_format_str
                self._logger.info(f"PixelFormat: {pixel_format_str} (0x{pixel_format_value:08X})")
            except Exception as e:
                self._logger.warning(f"查询 PixelFormat 失败: {e}")

            # 发布连接成功事件
            self.publish_event(EventType.CAMERA_CONNECTED, {
                "device_info": display_name,
                "camera_type": self._camera_type,
                "bayer_pattern": self._bayer_pattern,
                "pixel_format": self._pixel_format,
                # 量程由相机自己报，面板按它设置滑条；实测这台是 20us-1s / 0-24dB，
                # 但换一台就不一定是这个数了
                "exposure_range": self.get_parameter_range("ExposureTime"),
                "gain_range": self.get_parameter_range("Gain"),
            })

            self._logger.info(f"相机连接成功: index={device_index}, model={display_name}")
            return True

        except Exception as e:
            self._logger.error(f"连接相机失败: {str(e)}")
            # 只把 _camera 置 None 等于把独占句柄漏到进程结束：_running 从没被置起来，
            # BaseModule.stop() 会 early-return，没人再来 disconnect() 这个设备。
            if self._camera is not None:
                try:
                    self._camera.close_device()
                except Exception as close_error:
                    self._logger.warning(f"关闭未连接成功的相机失败: {close_error}")
            self._camera = None
            self._remote_feature = None
            self._connected = False
            self._target_device_index = None  # 失败时也清除
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })
            return False

    def disconnect(self):
        """断开相机连接"""
        try:
            if self._is_streaming:
                if not self.stop_streaming():
                    # 上一轮 join 预算内线程没出来所以先收了手；它往往就在这句话之间退出了。
                    # 必须再补一次 stop_streaming，否则 stream_off 永远没人调用：流一直开着，
                    # 下面的 close_device 也只是把句柄留在"已打开"状态，之后重连就报
                    # The device has already been opened（真机实测），不重启进程用不了相机。
                    thread = self._stream_thread
                    if thread:
                        thread.join(timeout=self.STREAM_JOIN_TIMEOUT_S)
                    self.stop_streaming()

            if self._stream_thread and self._stream_thread.is_alive():
                # 抓帧线程还挂在 get_image 里，此刻 close_device() 就是当着读者的面
                # 拆原生句柄。留着连接等它退出，也比制造 use-after-free 好。
                self._logger.error("抓帧线程未退出，推迟关闭设备句柄")
                return

            if self._is_streaming and not self.stop_streaming():
                # 线程走了但数据流还开着：绝不能就这么关设备。真机这样关过一次之后，
                # 每次 open 都报 "The device has already been opened"，直到进程退出为止。
                self._logger.error("数据流未能关闭，推迟断开以免留下不可用的设备")
                return

            if self._camera:
                self._camera.close_device()
                self._camera = None
                self._remote_feature = None
                
            self._connected = False
            self._device_indices.clear()  # 清空设备索引列表
            self._camera_type = None
            self._bayer_pattern = None
            self._pixel_format = None
            self._pixel_format_name = None
            time.sleep(0.1)
            
            self.publish_event(EventType.CAMERA_DISCONNECTED)
            
        except Exception as e:
            self._logger.error(f"断开相机连接失败: {str(e)}")
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })
        else:
            # 只有真的走完关闭流程才丢开句柄。写在 finally 里的话，上面两条"推迟关闭"
            # 的分支也会把 _camera/_connected 抹掉：设备在 SDK 里还开着，我们却没有引用
            # 可以关它了 —— 真机实测之后每次 open 都报 -8 already been opened，不重启
            # 进程这台相机就废了。留着状态，下一次 disconnect 才补得上。
            self._camera = None
            self._remote_feature = None
            self._connected = False
            self._device_indices.clear()
            self._camera_type = None
            self._bayer_pattern = None
            self._pixel_format = None
            self._pixel_format_name = None

    def start_streaming(self) -> bool:
        """开始图像采集；返回是否真的在采集。"""
        if self._stream_thread and self._stream_thread.is_alive():
            # 上一轮的抓帧线程还在读数据流。再起一个就是多个线程同时 get_image，
            # 而 stop 时会当着读者的面关流/关设备 —— 复用现有线程，不再起新的。
            self._is_streaming = True
            return True
        if self._is_streaming:
            # 线程已经没了但标志还挂着：上一轮没停干净，收回去重来，不能从此卡死
            self._logger.warning("检测到失效的采集状态，重新建立数据流")
            self._is_streaming = False
        if not self._camera:
            self._logger.error("没有可用相机，无法开始采集")
            return False
            
        try:
            # 发送串流开始事件
            self.publish_event(EventType.PROCESSING_STARTED)
            self.publish_event(EventType.STREAMING_STARTED)
            # 确保事件被处理
            time.sleep(0.1)
            
            self._stop_flag = False
            # 预算要跟着一起清：_stream_once 开头就按它早退，只复位 _stop_flag 的话
            # 重启后的线程每轮都在守卫处返回，既不报错也不退，还跳过所有退避
            self._stream_error_count = 0
            self._last_frame_at = time.perf_counter()
            self._starvation_reported = False
            self._camera.stream_on()
            self._is_streaming = True
            
            # 启动采集线程（只传弱引用，见 _run_stream_loop）
            self._stream_thread = threading.Thread(
                target=self._run_stream_loop,
                args=(weakref.ref(self),),
                daemon=True
            )
            self._stream_thread.start()
            return True
            
        except Exception as e:
            self._logger.error(f"启动图像采集失败: {str(e)}")
            self._is_streaming = False
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })
            return False

    def stop_streaming(self) -> bool:
        """停止图像采集；返回是否真的停下来（数据流已关闭且没有线程在读）。"""
        if not self._is_streaming:
            return True

        if self._camera is None:
            # 设备已经不在了（连接先被关掉，_is_streaming 还挂着 True）。这里没什么可关的：
            # 原来直接走到 self._camera.stream_off() 抛 AttributeError，被下面的 except
            # 转成一条错误事件，用户看到的是一句莫名其妙的"停止采集失败"弹窗。
            self._stop_flag = True
            thread = self._stream_thread
            if thread:
                thread.join(timeout=self.STREAM_JOIN_TIMEOUT_S)
            self._is_streaming = False
            return True

        try:
            self._stop_flag = True
            thread = self._stream_thread
            # 线程可能正卡在 get_image 的等待里（等待窗口跟着曝光走，最长 1.5s）。只 join
            # 一轮的话它往往"下一句就出来了"，而那时 stream_off 已经没人补做 —— 真机实测
            # 这样关掉的设备之后每次 open 都报 "already been opened"，重连几次都救不回来。
            # 两轮封顶，免得真卡死的线程把调用方吊在这里。
            for _ in range(2):
                if not thread or not thread.is_alive():
                    break
                thread.join(timeout=self.STREAM_JOIN_TIMEOUT_S)
                if not thread.is_alive():
                    break
            if thread and thread.is_alive():
                # 抓帧线程还挂在 get_image 里。这时候 stream_off()/close_device() 就是
                # 当着读者的面拆原生句柄；宁可报失败，也不拆。
                self._logger.error("抓帧线程未能退出，跳过数据流关闭以避免破坏正在读取的句柄")
                return False

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

            # 发送串流停止事件
            self.publish_event(EventType.STREAMING_STOPPED)
            self.publish_event(EventType.PROCESSING_COMPLETED)
            return True

        except Exception as e:
            self._logger.error(f"停止图像采集失败: {str(e)}")
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })
            # 收回状态，否则 _is_streaming 永远为真，之后每次 start_streaming 都早退，
            # 界面写着「停止采集」却再也不出帧
            self._is_streaming = False
            return False

    @staticmethod
    def _run_stream_loop(module_ref: "weakref.ReferenceType[CameraModule]") -> None:
        """抓帧循环。

        线程只握 module 的弱引用：以绑定方法 self._streaming_task 作 target 时，那份
        隐式强引用会让 CameraModule 永远回收不掉，开着的数据流句柄跟着一起泄漏，
        线程本身也没有退出条件。
        """
        while True:
            module = module_ref()
            if module is None or module._stop_flag:
                return
            try:
                module._stream_once()
            finally:
                # 必须在这一轮结束时松开这一帧的强引用，否则局部变量本身就够把模块
                # 钉住，弱引用形同虚设
                module = None

    def _to_pipeline_uint8(self, frame: Optional[np.ndarray]) -> Optional[np.ndarray]:
        """把相机帧统一降到 8bit；None 原样返回。

        降位只在这一个入口做。这台相机的 PixelFormat 实测可选 Mono8/Mono10，Mono10 下
        get_numpy_array() 返回右对齐的 uint16（实测取值 0..1022），而处理链的前提是
        8bit：demosaic 认 uint16，calculate_polarization_parameters 却直接 TypeError，
        合并路径上的 astype(uint8) 更会按 256 回绕（合成帧实测 61% 的像素变成 0）。
        """
        if frame is None or frame.dtype == np.uint8 or frame.ndim != 2:
            return frame
        match = re.search(r"(\d+)$", self._pixel_format_name or "")
        depth = int(match.group(1)) if match else frame.dtype.itemsize * 8
        if depth <= 8:
            # 报出来的位深还没超过容器宽度：取高位，别把有效位截掉
            depth = frame.dtype.itemsize * 8
        return np.right_shift(frame, depth - 8).astype(np.uint8)

    def _grab_timeout_ms(self) -> int:
        """等待窗口跟着曝光走，但不超过停流能等的时长。"""
        exposure_ms = float(self._last_params.get('exposure') or 0.0) / 1000.0
        return int(min(self.GRAB_TIMEOUT_MAX_MS, max(self.GRAB_TIMEOUT_MS, exposure_ms + 50)))

    def _report_starvation_if_due(self) -> None:
        """采集明明开着，却一帧都不来 —— 说一次，别静默装死。

        实测把 TriggerMode 留在 On（别的程序或相机用户集设的）时，get_image 只是返回
        None，不抛异常，所以原来的错误预算完全不动：界面显示"采集中"、画面冻住、没有任何
        提示。
        """
        if self._starvation_reported:
            return
        window_ms = max(self.STARVATION_MIN_MS,
                        self._grab_timeout_ms() * self.STARVATION_FACTOR)
        if (time.perf_counter() - self._last_frame_at) * 1000.0 < window_ms:
            return
        self._starvation_reported = True
        exposure_ms = float(self._last_params.get('exposure') or 0.0) / 1000.0
        message = (f"{window_ms / 1000.0:.0f}s 内没有采到帧：检查触发模式是否被设成 On、"
                   f"曝光是否过长（当前 {exposure_ms:.0f}ms）")
        self._logger.warning(message)
        self.publish_event(EventType.STATUS_MESSAGE_UPDATE, {'message': message})

    def _stream_once(self) -> None:
        """采集一帧并投递；失败时短暂退避。"""
        if self._stream_error_count >= self.STREAM_ERROR_LIMIT:
            return  # 已经报过"收手"了，别再重复发布
        try:
            # 开始计时
            t_start = time.perf_counter()

            # 获取图像：这里的等待必须明显短于 stop_streaming 的 join 预算，
            # 否则 join 超时后就只能当着读者的面关句柄
            raw_image = self._camera.data_stream[0].get_image(timeout=self._grab_timeout_ms())
            self._stream_error_count = 0
            frame = self._to_pipeline_uint8(raw_image.get_numpy_array()) if raw_image else None
            if frame is None:
                self._report_starvation_if_due()
                time.sleep(0.001)  # 短暂暂停避免空转
                return

            self._last_frame_at = time.perf_counter()
            self._starvation_reported = False
            # 计算采集时间
            t_capture = time.perf_counter() - t_start

            # 当队列满时，移除最旧的帧
            try:
                if self._frame_queue.full():
                    self._frame_queue.get_nowait()
            except queue.Empty:
                pass

            # 将新帧放入队列
            self._frame_queue.put(frame)

            # 发布帧捕获事件，包含采集时间
            self.publish_event(EventType.FRAME_CAPTURED, {
                "frame": frame,
                "capture_time": t_capture,
                "timestamp": time.time()
            })

        except Exception as e:
            self._stream_error_count += 1
            self._logger.error(f"图像采集错误: {str(e)}")
            if self._stream_error_count >= self.STREAM_ERROR_LIMIT:
                # 到这儿就不是抖一下了：再转下去只是每秒十条错误事件，而 GUI 每条会
                # 弹一个模态框，队列涨得比人点掉快。留一条说清楚的话，然后收手。
                self._stop_flag = True
                self._logger.error(f"连续 {self._stream_error_count} 次采集失败，停止采流")
                self.publish_event(EventType.ERROR_OCCURRED, {
                    "source": "camera",
                    "error": f"连续 {self._stream_error_count} 次采集失败，已停止采集: {str(e)}"
                })
                return
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
                frame = self._to_pipeline_uint8(raw_image.get_numpy_array())
                return frame
        except Exception as e:
            self._logger.error(f"获取图像失败: {str(e)}")
        return None

    def get_capture_settings(self) -> Dict[str, Any]:
        """把设备当前的曝光/增益/ROI 抄成一份可序列化的字典。

        只在单帧采集的抓取路径上调，读的是"这一帧即将用/刚用过的参数"；GUI 事后现问
        设备的话，长曝光期间用户动一下滑条，存进图库的元数据就描述错帧了。
        """
        return {
            'exposure_us': self.get_exposure_time(),
            'gain_db': self.get_gain(),
            'roi': list(self.get_roi()),
            'sensor_size': list(self.get_sensor_size()),
        }

    def get_frame(self) -> Optional[np.ndarray]:
        """获取最新图像帧"""
        try:
            t_start = time.perf_counter()
            if not self._is_streaming:
                # 参数必须在开流**之前**抄：曝光一开始，这一帧就锁定用当时的值，而抓取
                # 途中用户动滑条只影响下一帧。真机实测在抓取结束后才读的话，记下来的是
                # 改过之后的 20ms，而像素是 400ms 曝的。
                settings = self.get_capture_settings()
                # 单帧采集时，临时开启数据流。整段抓取都对设备有独占性：真机实测这期间
                # 写 Width/Height/OffsetX/OffsetY 一律 is not writeable，所以标记要罩住
                # 含收尾 sleep 的整段，让 set_roi 在碰设备之前就挡下来。
                self.claim_frame_capture()
                try:
                    self._camera.stream_on()
                    time.sleep(0.1)  # 等待数据流启动

                    try:
                        raw_image = self._camera.data_stream[0].get_image()
                        if raw_image:
                            frame = self._to_pipeline_uint8(raw_image.get_numpy_array())
                            t_capture = time.perf_counter() - t_start
                            # 添加时间信息；settings 是开流前抄的那份（见上）
                            self.publish_event(EventType.FRAME_CAPTURED, {
                                "frame": frame,
                                "capture_time": t_capture,
                                "settings": settings,
                                "timestamp": time.time()
                            })
                            return frame
                    finally:
                        # 确保数据流被关闭
                        self._camera.stream_off()
                        time.sleep(0.1)  # 等待数据流关闭
                finally:
                    self.release_frame_capture()
            else:
                # 这一帧在入队的那一刻就已经广播过一次了，这里再发一遍就是重复事件：
                # GUI 会把同一帧再解码再处理一次，而此处 t_capture 量到的是排队等待时间，
                # 显示出来的"采集耗时"是假的。所以只把帧交回去。
                try:
                    return self._frame_queue.get(timeout=0.1)
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
            
        except Exception as e:
            self._logger.error(f"初始化相机参数失败: {str(e)}")
            self.publish_event(EventType.ERROR_OCCURRED, {
                "source": "camera",
                "error": str(e)
            })

    def _restore_cached_parameters(self):
        """将缓存参数恢复到当前相机会话。"""
        if not self._remote_feature:
            return

        for feature_name, setter, param_key in (
                ("ExposureTime", self.set_exposure_time, 'exposure'),
                ("Gain", self.set_gain, 'gain')):
            try:
                writable = self._remote_feature.get_float_feature(feature_name).is_writable()
            except Exception:
                writable = True
            if not writable:
                # 实测自动曝光开着时曝光节点根本不可写，硬写只会冒一条"设不成"的提示，
                # 每次重连都要来一遍。跳过即可，设备自己会给出值。
                self._logger.info(f"{feature_name} 由自动模式接管，跳过恢复")
                continue
            setter(self._last_params[param_key])

    def _explain_float_write(self, feature_name: str, value: float, error: Exception) -> str:
        """把两种"必然失败"的写入翻成一句人话。

        真机实测：写 19us 抛 OutOfRange（"must be greater than or equal 20.0"），
        自动曝光开着时写曝光抛 InvalidAccess（"Node is not writable"）。这两种都不是
        设备故障，把 SDK 的原文塞进模态框对用户没有意义，所以给出范围/自动模式，
        并走状态栏而不是错误弹窗。读不到辅助信息时返回空串，让调用方回退到原报错。
        """
        text = str(error)
        label = _FLOAT_FEATURE_LABELS.get(feature_name, feature_name)
        try:
            if "must be greater than or equal" in text or "must be smaller than or equal" in text:
                rng = self.get_parameter_range(feature_name)
                if rng:
                    return (f"{label} 设不成 {value}{rng.get('unit') or ''}："
                            f"相机只接受 {rng['min']}-{rng['max']}{rng.get('unit') or ''}")
                return f"{label} 设不成 {value}：超出相机允许范围"
            if "not writable" in text:
                for auto_feature, owner in _FLOAT_AUTO_OWNERS.get(feature_name, ()):
                    try:
                        _, mode = self._remote_feature.get_enum_feature(auto_feature).get()
                    except Exception:
                        continue
                    if mode and mode != "Off":
                        return f"{label} 当前不可写：{owner}正开着（{mode}），先关掉自动再手动设"
                return f"{label} 当前不可写"
        except Exception as e:
            self._logger.debug(f"翻译写入失败时又出错: {e}")
        return ""

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
            self._report_parameter_rejected("ExposureTime", exposure, e)

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
            self._report_parameter_rejected("Gain", gain, e)

    def _report_parameter_rejected(self, feature_name: str, value: float, error: Exception):
        """ predictable 的拒绝走状态栏，真正的故障仍然按错误上报。"""
        friendly = self._explain_float_write(feature_name, value, error)
        if friendly:
            self._logger.warning(f"{friendly}（SDK: {error}）")
            self.publish_event(EventType.STATUS_MESSAGE_UPDATE, {'message': friendly})
            return
        error_msg = f"设置{feature_name}失败: {str(error)}"
        self._logger.error(error_msg)
        self.publish_event(EventType.ERROR_OCCURRED, {
            "source": "camera",
            "error": error_msg
        })

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

    def _wait_auto_once(self, auto_feature: str, label: str, max_wait_s: float = 5.0) -> bool:
        """设成 Once，等相机自己回到 Off；回不来就把模式收回，别把状态留坏。

        真机实测：没开流（没有画面可看）时这台相机的自动永远不会收敛，5s 到点仍停在
        Once；而 Once 状态下曝光/增益节点是不可写的（实测抛 InvalidAccess
        "Node is not writable"），留着它等于用户按一次"单次自动"之后手动值就再也写不进去。
        """
        enum = self._remote_feature.get_enum_feature(auto_feature)
        enum.set("Once")
        deadline = time.time() + max_wait_s
        while time.time() < deadline:
            # EnumFeature.get() 返回 (枚举值, 描述字符串)，拿元组和 "Off" 比永远为假
            _, mode = enum.get()
            if mode == "Off":
                return True
            time.sleep(0.1)
        try:
            enum.set("Off")
        except Exception as e:
            self._logger.error(f"收回{label}自动模式失败: {str(e)}")
        self._logger.warning(f"单次{label}自动未在 {max_wait_s:.0f}s 内完成，已收回手动模式")
        self.publish_event(EventType.STATUS_MESSAGE_UPDATE, {
            'message': f"单次{label}自动 {max_wait_s:.0f}s 内未完成（需要画面在采集才行），"
                       f"已收回手动模式"
        })
        return False

    def set_exposure_once(self):
        """执行单次自动曝光"""
        if not self._remote_feature:
            return
            
        try:
            self._wait_auto_once("ExposureAuto", "曝光")
                
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
            self._wait_auto_once("GainAuto", "增益")
                
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

    def is_capturing_frame(self) -> bool:
        """返回是否有一次单帧抓取正占着设备。

        这段窗口里（含开流前后的 sleep）设备的 Width/Height/OffsetX/OffsetY 一律
        is not writeable，任何 ROI 写入都得先让开。
        """
        return self._one_shot_grab

    def claim_frame_capture(self) -> None:
        """占住设备。

        由受理请求的一方（GUI）同步调用：抓取线程起步要等调度，等它进 get_frame 再立
        标记的话，中间这一次点击照样会把 ROI 写进正在采集的设备里。
        """
        self._one_shot_grab = True

    def release_frame_capture(self) -> None:
        """交还设备，与 claim_frame_capture 成对。"""
        self._one_shot_grab = False

    def get_last_exposure(self) -> float:
        """获取最后设置的曝光值"""
        return self._last_params['exposure']

    def get_last_gain(self) -> float:
        """获取最后设置的增益值"""
        return self._last_params['gain']

    def get_parameter_range(self, name: str) -> Optional[Dict[str, Any]]:
        """读取相机自己报告的浮点参数量程。

        Args:
            name: GenICam 参数名，如 'ExposureTime'、'Gain'
        Returns:
            {'min': .., 'max': .., 'unit': ..}，未连接或读不到时返回 None
        """
        if not self._remote_feature:
            return None
        try:
            rng = self._remote_feature.get_float_feature(name).get_range()
            return {'min': rng['min'], 'max': rng['max'], 'unit': rng.get('unit', '')}
        except Exception as e:
            self._logger.warning(f"读取参数量程失败 {name}: {e}")
            return None

    # ==================== ROI 控制 ====================

    def get_sensor_size(self) -> Tuple[int, int]:
        """获取传感器完整尺寸

        Returns:
            (sensor_width, sensor_height)
        """
        if not self._camera:
            return (0, 0)
        try:
            w = self._camera.SensorWidth.get()
            h = self._camera.SensorHeight.get()
            return (w, h)
        except Exception as e:
            self._logger.error(f"获取传感器尺寸失败: {e}")
            return (0, 0)

    def get_roi(self) -> Tuple[int, int, int, int]:
        """获取当前 ROI

        Returns:
            (offset_x, offset_y, width, height)
        """
        if not self._camera:
            return (0, 0, 0, 0)
        try:
            ox = self._camera.OffsetX.get()
            oy = self._camera.OffsetY.get()
            w = self._camera.Width.get()
            h = self._camera.Height.get()
            return (ox, oy, w, h)
        except Exception as e:
            self._logger.error(f"获取 ROI 失败: {e}")
            return (0, 0, 0, 0)

    def get_roi_constraints(self) -> dict:
        """获取 ROI 对齐约束

        Returns:
            包含 width_inc, height_inc, width_min, height_min,
            offset_x_inc, offset_y_inc 的字典
        """
        if not self._camera:
            return {}
        try:
            w_range = self._camera.Width.get_range()
            h_range = self._camera.Height.get_range()
            ox_range = self._camera.OffsetX.get_range()
            oy_range = self._camera.OffsetY.get_range()
            return {
                'width_inc': w_range['inc'],
                'height_inc': h_range['inc'],
                'width_min': w_range['min'],
                'height_min': h_range['min'],
                'offset_x_inc': ox_range['inc'],
                'offset_y_inc': oy_range['inc'],
            }
        except Exception as e:
            self._logger.error(f"获取 ROI 约束失败: {e}")
            return {}

    @staticmethod
    def _align_value(value: int, increment: int) -> int:
        """将值向下对齐到最近的有效增量

        Args:
            value: 待对齐的值
            increment: 对齐步长（如 2, 4, 8）
        Returns:
            对齐后的值
        """
        if increment <= 1:
            return value
        return (value // increment) * increment

    @staticmethod
    def _align_offset(value: int, increment: int) -> int:
        """把偏移对齐到最近的有效步进，向最近的一侧取。

        尺寸可以一律向下，偏移不行：调用方（放大/缩小）是按"当前 ROI 的中心"发请求的，
        向下对齐每次都把中心朝左上推掉最多一个步进，推完的结果又不是下一次请求的
        不动点，于是视场一边报「已达最大放大倍率」一边一格一格往左走。
        """
        if increment <= 1:
            return value
        return ((value + increment // 2) // increment) * increment

    def set_roi(self, offset_x: int, offset_y: int, width: int, height: int) -> bool:
        """设置相机 ROI，自动处理流暂停/恢复

        执行顺序:
        1. 停止流（如果正在采集）
        2. 将偏移归零防止越界
        3. 设置 Width, Height
        4. 设置 OffsetX, OffsetY
        5. 恢复流（如果之前在采集）

        所有值自动对齐到相机增量约束。

        Args:
            offset_x, offset_y: 传感器坐标系中的左上角
            width, height: ROI 尺寸
        Returns:
            是否成功
        """
        if not self._camera:
            return False

        if self._one_shot_grab:
            # 抓取占着设备时这四个节点全是 is not writeable（真机实测），写下去只会
            # 换来一条用户看不懂的「相机错误」对话框，而他要的操作其实没做成。
            self._logger.debug("单帧采集进行中，跳过本次 ROI 设置")
            return False

        was_streaming = self._is_streaming

        try:
            constraints = self.get_roi_constraints()
            if not constraints:
                return False

            sensor_w, sensor_h = self.get_sensor_size()
            if sensor_w == 0 or sensor_h == 0:
                return False

            # 对齐下限只关乎偏振栅格的相位，设备步进由 get_roi_constraints 提供。
            # 实测这台黑白偏振相机 Width 步进 8、Height 步进 2，而它的 MPFA 周期是 2，
            # 所以固定按 4 对齐会白丢一半纵向 ROI 分辨率；彩色偏振的 CPFA 才是 4x4。
            is_pol = self._camera_type in (CameraType.COLOR, CameraType.MONO)
            align = ImageProcessor.cpfa_period(self._camera_type is CameraType.MONO) \
                if is_pol else 1

            w_inc = max(constraints['width_inc'], align)
            h_inc = max(constraints['height_inc'], align)
            ox_inc = max(constraints['offset_x_inc'], align)
            oy_inc = max(constraints['offset_y_inc'], align)

            # 对齐尺寸
            width = self._align_value(width, w_inc)
            height = self._align_value(height, h_inc)

            # 钳位到最小尺寸
            width = max(width, constraints['width_min'])
            height = max(height, constraints['height_min'])

            # 钳位尺寸不超过传感器
            width = min(width, sensor_w)
            height = min(height, sensor_h)

            # 对齐偏移（取最近，理由见 _align_offset），再钳位到不超出传感器范围。
            # 钳位上限本身先向下对齐：传感器尺寸和宽高都是步进的整数倍时它已经对齐，
            # 万一不是，向下取也保证钳完的结果还落在合法步进上。
            offset_x = self._align_offset(offset_x, ox_inc)
            offset_y = self._align_offset(offset_y, oy_inc)
            max_offset_x = self._align_value(sensor_w - width, ox_inc)
            max_offset_y = self._align_value(sensor_h - height, oy_inc)
            offset_x = max(0, min(offset_x, max_offset_x))
            offset_y = max(0, min(offset_y, max_offset_y))

            # 停止流
            if was_streaming:
                self.stop_streaming()

            # 设置 ROI：先归零偏移，再设尺寸，最后设偏移
            self._camera.OffsetX.set(0)
            self._camera.OffsetY.set(0)
            self._camera.Width.set(width)
            self._camera.Height.set(height)
            self._camera.OffsetX.set(offset_x)
            self._camera.OffsetY.set(offset_y)

            self._logger.info(
                f"ROI 已设置: offset=({offset_x},{offset_y}), size=({width}x{height})"
            )

            # 发布 ROI 变更事件
            self.publish_event(EventType.ROI_CHANGED, {
                'offset_x': offset_x,
                'offset_y': offset_y,
                'width': width,
                'height': height,
                'sensor_width': sensor_w,
                'sensor_height': sensor_h,
            })

            # 恢复流
            if was_streaming:
                self.start_streaming()

            return True

        except Exception as e:
            self._logger.error(f"设置 ROI 失败: {e}")
            self.publish_event(EventType.ERROR_OCCURRED, {
                'source': 'camera',
                'error': f"设置 ROI 失败: {e}"
            })
            # 尝试恢复流
            if was_streaming and not self._is_streaming:
                try:
                    self.start_streaming()
                except Exception:
                    pass
            return False

    def reset_roi(self) -> bool:
        """重置 ROI 为全传感器尺寸"""
        if not self._camera:
            return False
        sensor_w, sensor_h = self.get_sensor_size()
        if sensor_w == 0 or sensor_h == 0:
            return False
        return self.set_roi(0, 0, sensor_w, sensor_h)
