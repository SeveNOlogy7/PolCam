"""
BaseModule测试代码
"""

import pytest
from polcam.core.base_module import BaseModule
from polcam.core.events import EventType

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
