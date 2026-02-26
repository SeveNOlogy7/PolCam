"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.

事件系统核心实现
提供事件的发布、订阅和异步处理功能
"""

from typing import Any, Callable, Dict, List, Set
from concurrent.futures import ThreadPoolExecutor
import threading
import logging
from enum import Enum, auto
import queue
import traceback
import time

class EventType(Enum):
    """定义系统中的事件类型"""
    CAMERA_CONNECTED = auto()      # 相机连接成功事件
    CAMERA_DISCONNECTED = auto()   # 相机断开连接事件
    FRAME_CAPTURED = auto()        # 帧采集完成事件
    FRAME_PROCESSED = auto()       # 帧处理完成事件
    PARAMETER_CHANGED = auto()     # 相机参数改变事件
    ERROR_OCCURRED = auto()        # 错误发生事件
    DISPLAY_MODE_CHANGED = auto()  # 显示模式改变事件
    PROCESSING_STARTED = auto()    # 处理开始事件
    PROCESSING_COMPLETED = auto()  # 处理完成事件
    STREAMING_STARTED = auto()     # 流采集开始事件
    STREAMING_STOPPED = auto()     # 流采集停止事件
    RAW_FILE_LOADED = auto()       # RAW文件加载完成事件
    STATUS_MESSAGE_UPDATE = auto() # 状态栏消息更新事件
    STATUS_MESSAGE_CLEAR = auto()  # 状态栏消息清除事件
    ROI_CHANGED = auto()           # ROI变更事件

class Event:
    """事件对象"""
    def __init__(self, event_type: EventType, data: Any = None):
        self.type = event_type
        self.data = data
        self.timestamp = time.time()  # 使用time.time()替代asyncio.get_event_loop().time()

class EventManager:
    """事件管理器"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self._subscribers: Dict[EventType, Set[Callable]] = {}
        self._async_subscribers: Dict[EventType, Set[Callable]] = {}
        self._thread_pool = ThreadPoolExecutor(max_workers=4)
        self._event_queue = queue.Queue()
        self._is_processing = False
        self._logger = logging.getLogger(__name__)
        
        # 启动事件处理线程
        self._start_event_processing()

    def subscribe(self, event_type: EventType, callback: Callable, is_async: bool = False):
        """订阅事件
        
        Args:
            event_type: 事件类型
            callback: 回调函数
            is_async: 是否异步处理
        """
        if is_async:
            if event_type not in self._async_subscribers:
                self._async_subscribers[event_type] = set()
            self._async_subscribers[event_type].add(callback)
        else:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = set()
            self._subscribers[event_type].add(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable):
        """取消订阅"""
        if event_type in self._subscribers and callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)
        if event_type in self._async_subscribers and callback in self._async_subscribers[event_type]:
            self._async_subscribers[event_type].remove(callback)

    def publish(self, event: Event):
        """发布事件"""
        self._event_queue.put(event)

    def _start_event_processing(self):
        """启动事件处理线程"""
        def process_events():
            while True:
                try:
                    event = self._event_queue.get()
                    self._process_event(event)
                except Exception as e:
                    self._logger.error(f"处理事件时发生错误: {str(e)}\n{traceback.format_exc()}")
                finally:
                    self._event_queue.task_done()

        thread = threading.Thread(target=process_events, daemon=True)
        thread.start()

    def _process_event(self, event: Event):
        """处理单个事件"""
        # 处理同步回调
        if event.type in self._subscribers:
            for callback in self._subscribers[event.type]:
                try:
                    callback(event)
                except Exception as e:
                    self._logger.error(f"执行同步回调时发生错误: {str(e)}\n{traceback.format_exc()}")

        # 处理异步回调
        if event.type in self._async_subscribers:
            for callback in self._async_subscribers[event.type]:
                self._thread_pool.submit(self._run_async_callback, callback, event)

    def _run_async_callback(self, callback: Callable, event: Event):
        """在线程池中执行异步回调"""
        try:
            callback(event)
        except Exception as e:
            self._logger.error(f"执行异步回调时发生错误: {str(e)}\n{traceback.format_exc()}")
