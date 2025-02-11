"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

import numpy as np
import cv2
import threading
import queue
from typing import List, Tuple, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import time
from dataclasses import dataclass
from enum import Enum, auto

from .base_module import BaseModule
from .events import EventType, Event
from .image_processor import ImageProcessor

class ProcessingMode(Enum):
    """图像处理模式"""
    RAW = auto()               # 原始图像
    SINGLE_COLOR = auto()      # 单角度彩色
    SINGLE_GRAY = auto()       # 单角度灰度
    MERGED_COLOR = auto()      # 合成彩色
    MERGED_GRAY = auto()       # 合成灰度
    QUAD_COLOR = auto()        # 四角度彩色
    QUAD_GRAY = auto()         # 四角度灰度
    POLARIZATION = auto()      # 偏振分析

@dataclass
class ProcessingResult:
    """处理结果数据类"""
    mode: ProcessingMode
    images: List[np.ndarray]
    metadata: Dict[str, Any]
    timestamp: float

class ProcessingTask:
    """处理任务类"""
    def __init__(self, frame: np.ndarray, mode: ProcessingMode, 
                 params: Dict[str, Any], priority: int = 0):
        self.frame = frame
        self.mode = mode
        self.params = params
        self.priority = priority
        self.timestamp = time.time()

    def __lt__(self, other):
        """优先级比较"""
        return self.priority > other.priority  # 值越大优先级越高

class ProcessingModule(BaseModule):
    """图像处理模块
    
    负责:
    1. 图像处理流水线管理
    2. 不同处理模式的实现
    3. 处理参数管理
    4. 处理结果的事件发布
    """
    
    def __init__(self):
        super().__init__("Processing")
        
        # 基础组件
        self._processor = ImageProcessor()
        self._task_queue = queue.PriorityQueue()
        self._thread_pool = ThreadPoolExecutor(max_workers=4)
        self._processing_thread: Optional[threading.Thread] = None
        
        # 状态控制
        self._stop_flag = False
        self._is_processing = False
        self._current_mode = ProcessingMode.RAW
        
        # 参数管理
        self._params = {
            'wb_auto': False,           # 自动白平衡开关
            'wb_roi': None,             # 白平衡ROI
            'brightness': 1.0,          # 亮度调节
            'contrast': 1.0,            # 对比度调节
            'sharpness': 0.0,          # 锐化强度
            'denoise': 0.0,            # 降噪强度
        }
        
        # 缓存管理
        self._last_result: Optional[ProcessingResult] = None
        self._frame_cache = {}          # 缓存最近处理过的帧
        self._max_cache_size = 10
        
    def _do_initialize(self) -> bool:
        """初始化处理模块"""
        try:
            # 初始化处理器
            self._processor = ImageProcessor()
            
            # 启动处理线程
            self._processing_thread = threading.Thread(
                target=self._processing_loop,
                daemon=True
            )
            self._processing_thread.start()
            
            return True
        except Exception as e:
            self._logger.error(f"初始化处理模块失败: {str(e)}")
            return False
            
    def _do_start(self) -> bool:
        """启动处理模块"""
        try:
            self._stop_flag = False
            return True
        except Exception as e:
            self._logger.error(f"启动处理模块失败: {str(e)}")
            return False
            
    def _do_stop(self) -> bool:
        """停止处理模块"""
        try:
            self._stop_flag = True
            if self._processing_thread:
                self._task_queue.put(None)  # 发送停止信号
                self._processing_thread.join(timeout=1.0)
            return True
        except Exception as e:
            self._logger.error(f"停止处理模块失败: {str(e)}")
            return False
            
    def _do_destroy(self) -> bool:
        """销毁处理模块"""
        try:
            self._thread_pool.shutdown(wait=True)
            return True
        except Exception as e:
            self._logger.error(f"销毁处理模块失败: {str(e)}")
            return False

    def set_mode(self, mode: ProcessingMode):
        """设置处理模式"""
        if mode != self._current_mode:
            self._current_mode = mode
            # 清空任务队列
            while not self._task_queue.empty():
                try:
                    self._task_queue.get_nowait()
                except queue.Empty:
                    break
            # 发布模式改变事件
            self.publish_event(EventType.DISPLAY_MODE_CHANGED, {
                'mode': mode
            })

    def set_parameter(self, name: str, value: Any):
        """设置处理参数"""
        if name in self._params and self._params[name] != value:
            self._params[name] = value
            # 发布参数改变事件
            self.publish_event(EventType.PARAMETER_CHANGED, {
                'parameter': name,
                'value': value
            })

    def process_frame(self, frame: np.ndarray, priority: int = 0):
        """添加处理任务
        
        Args:
            frame: 输入图像帧
            priority: 优先级（0-10，值越大优先级越高）
        """
        if frame is None:
            return
            
        # 创建处理任务
        task = ProcessingTask(
            frame=frame,
            mode=self._current_mode,
            params=self._params.copy(),
            priority=priority
        )
        
        # 添加到任务队列
        self._task_queue.put(task)
        
        # 发布处理开始事件
        self.publish_event(EventType.PROCESSING_STARTED, {
            'timestamp': task.timestamp
        })

    def _processing_loop(self):
        """处理循环"""
        while not self._stop_flag:
            try:
                task = self._task_queue.get()
                if task is None or self._stop_flag:
                    break
                    
                self._is_processing = True
                t_start = time.perf_counter()
                
                try:
                    result = self._process_task(task)
                    t_proc = time.perf_counter() - t_start
                    
                    if result:
                        self.publish_event(EventType.FRAME_PROCESSED, {
                            'result': result,
                            'processing_time': t_proc,
                            'timestamp': time.time()
                        })
                        
                    self._update_cache(task.frame, result)
                    
                    # 发送处理完成事件
                    self.publish_event(EventType.PROCESSING_COMPLETED)
                    
                except Exception as e:
                    self._logger.error(f"处理任务失败: {str(e)}")
                    self.publish_event(EventType.ERROR_OCCURRED, {
                        'source': 'processing',
                        'error': str(e)
                    })
                    
                finally:
                    self._is_processing = False
                    self._task_queue.task_done()
                    
            except Exception as e:
                self._logger.error(f"处理循环错误: {str(e)}")
                time.sleep(0.1)

    def _process_task(self, task: ProcessingTask) -> Optional[ProcessingResult]:
        """处理单个任务"""
        try:
            # 检查缓存
            cache_key = self._get_cache_key(task)
            if cache_key in self._frame_cache:
                return self._frame_cache[cache_key]
                
            # 根据模式处理图像
            if task.mode == ProcessingMode.RAW:
                images = [task.frame]
                metadata = {}
                
            elif task.mode in [ProcessingMode.SINGLE_COLOR, ProcessingMode.SINGLE_GRAY]:
                # 解码获取单角度图像
                decoded = self._processor.demosaic_polarization(task.frame)
                images = [decoded[0]]  # 使用0度方向
                if task.mode == ProcessingMode.SINGLE_GRAY:
                    images = [self._processor.to_grayscale(img) for img in images]
                metadata = {'angle': 0}
                
            elif task.mode in [ProcessingMode.MERGED_COLOR, ProcessingMode.MERGED_GRAY]:
                # 解码并合成图像
                decoded = self._processor.demosaic_polarization(task.frame)
                merged = np.mean(decoded, axis=0).astype(np.uint8)
                images = [merged]
                if task.mode == ProcessingMode.MERGED_GRAY:
                    images = [self._processor.to_grayscale(merged)]
                metadata = {}
                
            elif task.mode in [ProcessingMode.QUAD_COLOR, ProcessingMode.QUAD_GRAY]:
                # 解码获取四角度图像
                decoded = self._processor.demosaic_polarization(task.frame)
                images = decoded
                if task.mode == ProcessingMode.QUAD_GRAY:
                    images = [self._processor.to_grayscale(img) for img in images]
                metadata = {'angles': [0, 45, 90, 135]}
                
            elif task.mode == ProcessingMode.POLARIZATION:
                # 偏振分析
                decoded = self._processor.demosaic_polarization(task.frame)
                merged = np.mean(decoded, axis=0).astype(np.uint8)
                dolp, aolp, docp = self._processor.calculate_polarization_parameters(decoded)
                images = [merged, dolp, aolp, docp]
                metadata = {
                    'type': ['merged', 'dolp', 'aolp', 'docp']
                }
                
            else:
                raise ValueError(f"未知的处理模式: {task.mode}")
                
            # 应用图像增强
            images = self._enhance_images(images, task.params)
                
            # 创建结果对象
            result = ProcessingResult(
                mode=task.mode,
                images=images,
                metadata=metadata,
                timestamp=time.time()
            )
            
            return result
            
        except Exception as e:
            self._logger.error(f"处理任务失败: {str(e)}")
            raise

    def _enhance_images(self, images: List[np.ndarray], 
                       params: Dict[str, Any]) -> List[np.ndarray]:
        """应用图像增强"""
        try:
            enhanced = []
            wb_applied = False  # 跟踪白平衡是否已应用
            
            for img in images:
                # 跳过非图像数据（如偏振参数图）
                if len(img.shape) < 2:
                    enhanced.append(img)
                    continue
                    
                # 应用白平衡（仅对彩色图像）
                if len(img.shape) == 3 and params.get('wb_auto', False):
                    if not wb_applied:  # 仅对第一个图像执行自动白平衡
                        img = self._processor.auto_white_balance(img)
                        wb_applied = True
                    else:
                        img = self._processor.apply_white_balance(img)
                
                # 应用亮度和对比度调节
                if params['brightness'] != 1.0 or params['contrast'] != 1.0:
                    img = cv2.convertScaleAbs(
                        img, 
                        alpha=params['contrast'],
                        beta=params['brightness'] * 255
                    )
                
                # 应用锐化
                if params['sharpness'] > 0:
                    kernel = np.array([
                        [-1,-1,-1],
                        [-1,9,-1],
                        [-1,-1,-1]
                    ]) * params['sharpness']
                    img = cv2.filter2D(img, -1, kernel)
                
                # 应用降噪
                if params['denoise'] > 0:
                    if len(img.shape) == 3:
                        img = cv2.fastNlMeansDenoisingColored(
                            img,
                            None,
                            params['denoise'] * 10,
                            params['denoise'] * 10,
                            7,
                            21
                        )
                    else:
                        img = cv2.fastNlMeansDenoising(
                            img,
                            None,
                            params['denoise'] * 10,
                            7,
                            21
                        )
                
                enhanced.append(img)
                
            return enhanced
            
        except Exception as e:
            self._logger.error(f"图像增强失败: {str(e)}")
            return images

    def _get_cache_key(self, task: ProcessingTask) -> str:
        """生成缓存键"""
        # 使用帧哈希、模式和关键参数生成缓存键
        frame_hash = hash(task.frame.tobytes())
        params_hash = hash(frozenset(task.params.items()))
        return f"{frame_hash}_{task.mode}_{params_hash}"

    def _update_cache(self, frame: np.ndarray, result: ProcessingResult):
        """更新结果缓存"""
        if result is None:
            return
            
        # 生成缓存键
        cache_key = self._get_cache_key(ProcessingTask(
            frame=frame,
            mode=result.mode,
            params=self._params
        ))
        
        # 更新缓存
        self._frame_cache[cache_key] = result
        
        # 限制缓存大小
        if len(self._frame_cache) > self._max_cache_size:
            # 移除最早的缓存项
            oldest_key = next(iter(self._frame_cache))
            del self._frame_cache[oldest_key]

    def get_current_mode(self) -> ProcessingMode:
        """获取当前处理模式"""
        return self._current_mode

    def is_processing(self) -> bool:
        """返回是否正在处理"""
        return self._is_processing

    def clear_cache(self):
        """清空处理结果缓存"""
        self._frame_cache.clear()
        self._last_result = None

    def get_last_result(self) -> Optional[ProcessingResult]:
        """获取最近一次处理结果"""
        return self._last_result

    def get_task_count(self) -> int:
        """获取等待处理的任务数量"""
        return self._task_queue.qsize()

    @staticmethod
    def mode_to_index(mode: ProcessingMode) -> int:
        """将处理模式转换为显示模式索引"""
        mode_map = {
            ProcessingMode.RAW: 0,
            ProcessingMode.SINGLE_COLOR: 1,
            ProcessingMode.SINGLE_GRAY: 2,
            ProcessingMode.MERGED_COLOR: 3,
            ProcessingMode.MERGED_GRAY: 4,
            ProcessingMode.QUAD_COLOR: 5,
            ProcessingMode.QUAD_GRAY: 6,
            ProcessingMode.POLARIZATION: 7
        }
        return mode_map.get(mode, 0)

    @staticmethod
    def index_to_mode(index: int) -> ProcessingMode:
        """将显示模式索引转换为处理模式"""
        index_map = {
            0: ProcessingMode.RAW,
            1: ProcessingMode.SINGLE_COLOR,
            2: ProcessingMode.SINGLE_GRAY,
            3: ProcessingMode.MERGED_COLOR,
            4: ProcessingMode.MERGED_GRAY,
            5: ProcessingMode.QUAD_COLOR,
            6: ProcessingMode.QUAD_GRAY,
            7: ProcessingMode.POLARIZATION
        }
        return index_map.get(index, ProcessingMode.RAW)

    def get_parameters(self) -> Dict[str, Any]:
        """获取当前处理参数的副本"""
        return self._params.copy()

    def reset_parameters(self):
        """重置所有处理参数为默认值"""
        self._params = {
            'wb_auto': False,
            'wb_roi': None,
            'brightness': 1.0,
            'contrast': 1.0,
            'sharpness': 0.0,
            'denoise': 0.0
        }
        # 发送参数重置事件
        self.publish_event(EventType.PARAMETER_CHANGED, {
            'parameter': 'all',
            'value': 'reset'
        })

    def cancel_all_tasks(self):
        """取消所有待处理任务"""
        while not self._task_queue.empty():
            try:
                self._task_queue.get_nowait()
                self._task_queue.task_done()
            except queue.Empty:
                break

    def reprocess_last_frame(self):
        """重新处理最后一帧图像"""
        if self._last_result is None:
            return

        # 创建新的处理任务，使用最高优先级
        self.process_frame(self._last_result.images[0], priority=10)

    def get_mode_description(self, mode: Optional[ProcessingMode] = None) -> str:
        """获取处理模式的描述文本
        
        Args:
            mode: 处理模式，如果为None则使用当前模式
            
        Returns:
            str: 模式描述文本
        """
        if mode is None:
            mode = self._current_mode
            
        descriptions = {
            ProcessingMode.RAW: "原始图像",
            ProcessingMode.SINGLE_COLOR: "单偏振角度彩色图像",
            ProcessingMode.SINGLE_GRAY: "单偏振角度灰度图像",
            ProcessingMode.MERGED_COLOR: "合成彩色图像",
            ProcessingMode.MERGED_GRAY: "合成灰度图像",
            ProcessingMode.QUAD_COLOR: "四角度彩色图像",
            ProcessingMode.QUAD_GRAY: "四角度灰度图像",
            ProcessingMode.POLARIZATION: "偏振分析"
        }
        return descriptions.get(mode, "未知模式")

    def is_cache_enabled(self) -> bool:
        """返回是否启用了缓存"""
        return self._max_cache_size > 0

    def set_cache_size(self, size: int):
        """设置缓存大小
        
        Args:
            size: 新的缓存大小，0表示禁用缓存
        """
        if size < 0:
            raise ValueError("缓存大小不能为负数")
        
        self._max_cache_size = size
        
        # 如果新的大小小于当前缓存数量，删除多余的缓存
        while len(self._frame_cache) > size:
            oldest_key = next(iter(self._frame_cache))
            del self._frame_cache[oldest_key]
