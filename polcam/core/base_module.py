"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.

模块系统基类
提供基础的模块生命周期管理和事件处理功能
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Set
import logging
from .events import EventManager, EventType, Event

class BaseModule(ABC):
    """模块基类
    
    提供:
    1. 模块生命周期管理（初始化、启动、停止、销毁）
    2. 事件发布和订阅机制
    3. 状态管理
    4. 错误处理
    """
    
    def __init__(self, name: str):
        """初始化模块
        
        Args:
            name: 模块名称
        """
        self.name = name
        self._event_manager = EventManager()
        self._logger = logging.getLogger(f"polcam.{name}")
        self._initialized = False
        self._running = False
        self._subscribed_events: Set[EventType] = set()
        self._state: Dict[str, Any] = {}
        
    def initialize(self) -> bool:
        """初始化模块
        
        Returns:
            bool: 初始化是否成功
        """
        if self._initialized:
            return True
            
        try:
            self._logger.info(f"正在初始化模块: {self.name}")
            success = self._do_initialize()
            if success:
                self._initialized = True
                self._logger.info(f"模块初始化成功: {self.name}")
            else:
                self._logger.error(f"模块初始化失败: {self.name}")
            return success
        except Exception as e:
            self._logger.error(f"模块初始化出错: {self.name}, 错误: {str(e)}")
            return False
    
    def start(self) -> bool:
        """启动模块
        
        Returns:
            bool: 启动是否成功
        """
        if not self._initialized:
            self._logger.error(f"模块未初始化，无法启动: {self.name}")
            return False
            
        if self._running:
            return True
            
        try:
            self._logger.info(f"正在启动模块: {self.name}")
            success = self._do_start()
            if success:
                self._running = True
                self._logger.info(f"模块启动成功: {self.name}")
            else:
                self._logger.error(f"模块启动失败: {self.name}")
            return success
        except Exception as e:
            self._logger.error(f"模块启动出错: {self.name}, 错误: {str(e)}")
            return False
    
    def stop(self) -> bool:
        """停止模块
        
        Returns:
            bool: 停止是否成功
        """
        if not self._running:
            return True
            
        try:
            self._logger.info(f"正在停止模块: {self.name}")
            success = self._do_stop()
            if success:
                self._running = False
                self._logger.info(f"模块停止成功: {self.name}")
            else:
                self._logger.error(f"模块停止失败: {self.name}")
            return success
        except Exception as e:
            self._logger.error(f"模块停止出错: {self.name}, 错误: {str(e)}")
            return False
    
    def destroy(self) -> bool:
        """销毁模块
        
        Returns:
            bool: 销毁是否成功
        """
        if self._running:
            self.stop()
            
        try:
            self._logger.info(f"正在销毁模块: {self.name}")
            success = self._do_destroy()
            if success:
                self._initialized = False
                self._unsubscribe_all()
                self._logger.info(f"模块销毁成功: {self.name}")
            else:
                self._logger.error(f"模块销毁失败: {self.name}")
            return success
        except Exception as e:
            self._logger.error(f"模块销毁出错: {self.name}, 错误: {str(e)}")
            return False
    
    def publish_event(self, event_type: EventType, data: Any = None):
        """发布事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        event = Event(event_type, data)
        self._event_manager.publish(event)
        
    def subscribe_event(self, event_type: EventType, callback, is_async: bool = False):
        """订阅事件
        
        Args:
            event_type: 事件类型
            callback: 回调函数
            is_async: 是否异步处理
        """
        self._event_manager.subscribe(event_type, callback, is_async)
        self._subscribed_events.add(event_type)
        
    def _unsubscribe_all(self):
        """取消所有事件订阅"""
        for event_type in self._subscribed_events:
            self._event_manager.unsubscribe(event_type, None)
        self._subscribed_events.clear()
        
    def get_state(self, key: str, default: Any = None) -> Any:
        """获取状态值"""
        return self._state.get(key, default)
        
    def set_state(self, key: str, value: Any):
        """设置状态值"""
        self._state[key] = value
        
    def is_running(self) -> bool:
        """返回模块是否正在运行"""
        return self._running
        
    def is_initialized(self) -> bool:
        """返回模块是否已初始化"""
        return self._initialized
    
    @abstractmethod
    def _do_initialize(self) -> bool:
        """执行具体的初始化操作"""
        pass
    
    @abstractmethod
    def _do_start(self) -> bool:
        """执行具体的启动操作"""
        pass
    
    @abstractmethod
    def _do_stop(self) -> bool:
        """执行具体的停止操作"""
        pass
    
    @abstractmethod
    def _do_destroy(self) -> bool:
        """执行具体的销毁操作"""
        pass
