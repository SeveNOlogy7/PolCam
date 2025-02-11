"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.

通用缓存管理
"""

from typing import Any, Dict, Optional, TypeVar, Generic
import time

T = TypeVar('T')

class TimedCache(Generic[T]):
    """
    带有时间有效期的通用缓存类
    
    支持:
    1. 自动过期
    2. 分层缓存结构
    3. 泛型数据类型
    """
    
    def __init__(self, valid_duration: float = 2.0):
        self._data: Dict[str, T] = {}
        self._timestamps: Dict[str, float] = {}
        self._valid_duration = valid_duration
        self._is_permanent = False  # 添加永久缓存标志
        
    def get(self, key: str) -> Optional[T]:
        """获取缓存的值"""
        if key not in self._data:
            return None
            
        if self.is_expired(key):
            self.remove(key)
            return None
            
        return self._data[key]
        
    def set(self, key: str, value: T):
        """设置缓存值"""
        self._data[key] = value
        self._timestamps[key] = time.time()
        
    def remove(self, key: str):
        """移除指定的缓存项"""
        self._data.pop(key, None)
        self._timestamps.pop(key, None)
        
    def clear(self):
        """清空所有缓存"""
        self._data.clear()
        self._timestamps.clear()
        
    def is_expired(self, key: str) -> bool:
        """检查缓存项是否过期"""
        if key not in self._timestamps:
            return True
        # 如果设置为永久缓存，永不过期
        if self._is_permanent:
            return False
        return time.time() - self._timestamps[key] > self._valid_duration
        
    def set_valid_duration(self, duration: float):
        """设置缓存有效期"""
        if duration <= 0:
            raise ValueError("缓存有效期必须大于0")
        self._valid_duration = duration
        # 设置新的有效期时自动切换到临时缓存模式
        self._is_permanent = False
        
    def get_valid_duration(self) -> float:
        """获取当前的缓存有效期"""
        return self._valid_duration

    def set_permanent(self):
        """设置为永久缓存（永不过期）"""
        self._is_permanent = True

    def set_temporary(self, duration: float = None):
        """恢复为临时缓存
        
        Args:
            duration: 如果指定，将更新缓存有效期；
                     如果未指定，保持原有的有效期不变
        """
        self._is_permanent = False
        if duration is not None and duration > 0:
            self._valid_duration = duration
            
    def is_permanent(self) -> bool:
        """返回是否为永久缓存"""
        return self._is_permanent

class WhiteBalanceCache:
    """
    白平衡参数的多模式缓存管理器
    
    为不同的显示模式提供独立的缓存管理
    """
    
    def __init__(self, valid_duration: float = 2.0):
        # 创建不同模式的缓存对象
        self._single_mode = TimedCache[Dict[int, Any]](valid_duration)
        self._merged_mode = TimedCache[Any](valid_duration)
        self._quad_mode = TimedCache[Dict[int, Any]](valid_duration)
        self._pol_mode = TimedCache[Any](valid_duration)
        
    def get_single(self, angle: int) -> Optional[Any]:
        """获取单角度模式的缓存"""
        cache = self._single_mode.get('angles')
        if cache is None:
            return None
        return cache.get(angle)
        
    def set_single(self, angle: int, gains: Any):
        """设置单角度模式的缓存"""
        cache = self._single_mode.get('angles') or {}
        cache[angle] = gains
        self._single_mode.set('angles', cache)
        
    def get_merged(self) -> Optional[Any]:
        """获取合成模式的缓存"""
        return self._merged_mode.get('gains')
        
    def set_merged(self, gains: Any):
        """设置合成模式的缓存"""
        self._merged_mode.set('gains', gains)
        
    def get_quad(self, angle: int) -> Optional[Any]:
        """获取四角度模式的缓存"""
        cache = self._quad_mode.get('angles')
        if cache is None:
            return None
        return cache.get(angle)
        
    def set_quad(self, angle: int, gains: Any):
        """设置四角度模式的缓存"""
        cache = self._quad_mode.get('angles') or {}
        cache[angle] = gains
        self._quad_mode.set('angles', cache)
        
    def get_pol(self) -> Optional[Any]:
        """获取偏振分析模式的缓存"""
        return self._pol_mode.get('gains')
        
    def set_pol(self, gains: Any):
        """设置偏振分析模式的缓存"""
        self._pol_mode.set('gains', gains)
        
    def clear_all(self):
        """清空所有模式的缓存"""
        self._single_mode.clear()
        self._merged_mode.clear()
        self._quad_mode.clear()
        self._pol_mode.clear()
        
    def set_valid_duration(self, duration: float):
        """设置所有模式的缓存有效期"""
        self._single_mode.set_valid_duration(duration)
        self._merged_mode.set_valid_duration(duration)
        self._quad_mode.set_valid_duration(duration)
        self._pol_mode.set_valid_duration(duration)

    def set_permanent_single(self, angle: int):
        """设置单角度模式为永久缓存"""
        self._single_mode.set_permanent()
        
    def set_permanent_merged(self):
        """设置合成模式为永久缓存"""
        self._merged_mode.set_permanent()
        
    def set_permanent_quad(self):
        """设置四角度模式为永久缓存"""
        self._quad_mode.set_permanent()
        
    def set_permanent_pol(self):
        """设置偏振分析模式为永久缓存"""
        self._pol_mode.set_permanent()

    def reset_to_temporary(self, duration: float = 2.0):
        """将所有模式重置为临时缓存"""
        self._single_mode.set_temporary(duration)
        self._merged_mode.set_temporary(duration)
        self._quad_mode.set_temporary(duration)
        self._pol_mode.set_temporary(duration)
