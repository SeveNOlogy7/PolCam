"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

import pytest
from polcam.core.base_module import BaseModule
from polcam.core.events import EventManager, EventType

class TestModule(BaseModule):
    """测试用模块类"""
    def __init__(self):
        super().__init__("TestModule")
        self.initialize_called = False
        self.start_called = False
        self.stop_called = False
        self.destroy_called = False
        
    def _do_initialize(self) -> bool:
        self.initialize_called = True
        return True
        
    def _do_start(self) -> bool:
        self.start_called = True
        return True
        
    def _do_stop(self) -> bool:
        self.stop_called = True
        return True
        
    def _do_destroy(self) -> bool:
        self.destroy_called = True
        return True

@pytest.fixture
def test_module():
    return TestModule()

def test_lifecycle(test_module):
    """测试模块生命周期"""
    # 测试初始化
    assert test_module.initialize()
    assert test_module.is_initialized()
    assert test_module.initialize_called
    
    # 测试启动
    assert test_module.start()
    assert test_module.is_running()
    assert test_module.start_called
    
    # 测试停止
    assert test_module.stop()
    assert not test_module.is_running()
    assert test_module.stop_called
    
    # 测试销毁
    assert test_module.destroy()
    assert not test_module.is_initialized()
    assert test_module.destroy_called

def test_state_management(test_module):
    """测试状态管理"""
    # 设置状态
    test_module.set_state("test_key", "test_value")
    assert test_module.get_state("test_key") == "test_value"
    
    # 获取默认值
    assert test_module.get_state("non_existent", "default") == "default"

def test_event_handling(test_module):
    """测试事件处理"""
    events_received = []
    
    def on_event(event):
        events_received.append(event)
    
    # 订阅事件
    test_module.subscribe_event(EventType.CAMERA_CONNECTED, on_event)
    
    # 发布事件
    test_module.publish_event(EventType.CAMERA_CONNECTED, {"status": True})
    
    # 等待事件处理
    import time
    time.sleep(0.1)
    
    # 验证事件接收
    assert len(events_received) == 1
    assert events_received[0].type == EventType.CAMERA_CONNECTED
    assert events_received[0].data["status"] is True

def test_error_handling(test_module):
    """测试错误处理"""
    class ErrorModule(TestModule):
        def _do_initialize(self) -> bool:
            raise Exception("测试错误")
    
    error_module = ErrorModule()
    assert not error_module.initialize()
    assert not error_module.is_initialized()

def test_destroy_removes_the_module_subscriptions():
    """destroy() 必须真的把订阅取消掉。

    _unsubscribe_all() 给 EventManager.unsubscribe 传的是 None，而它按回调身份移除，
    所以那句话永远是 no-op：进程级单例继续握着已销毁模块的绑定方法，模块本体也
    跟着永远回收不掉。
    """
    event_manager = EventManager()
    event_type = EventType.ROI_CHANGED
    before = len(event_manager._subscribers.get(event_type, set()))

    module = TestModule()
    module.initialize()
    module.subscribe_event(event_type, lambda event: None)
    assert len(event_manager._subscribers[event_type]) == before + 1

    assert module.destroy() is True

    assert len(event_manager._subscribers.get(event_type, set())) == before


class _DestroyFails(TestModule):
    """_do_destroy 返回 False 的模块。"""

    def _do_destroy(self) -> bool:
        self.destroy_called = True
        return False


def test_a_failing_do_destroy_still_leaves_the_module_unusable():
    """_do_destroy() 说不行，也不能把模块留在"还能用"的状态。

    destroy() 原本只在 success 时才复位 _initialized 并退订，于是拆毁失败的模块
    is_initialized() 仍为 True，之后 start() 会在一个已经拆过的模块上再跑 _do_start，
    initialize() 也变成静默空操作。
    """
    module = _DestroyFails()
    assert module.initialize() and module.start()

    assert module.destroy() is False
    assert module.is_initialized() is False, "拆毁失败却还报告已初始化"
    assert module.start() is False, "拆毁失败的模块还能被启动"


def test_destroy_reports_a_failed_stop():
    """stop() 失败时 destroy() 不能报成功。

    原来 self.stop() 的返回值被直接丢掉：_do_stop 失败会留下 _running=True，
    destroy() 照样返回 True。
    """
    class _StopFails(TestModule):
        def _do_stop(self) -> bool:
            self.stop_called = True
            return False

    module = _StopFails()
    assert module.initialize() and module.start()

    assert module.destroy() is False
