"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

import pytest
import time
from concurrent.futures import ThreadPoolExecutor
from polcam.core.events import EventManager, EventType, Event

@pytest.fixture
def event_manager():
    return EventManager()

def test_singleton():
    """测试事件管理器的单例模式"""
    manager1 = EventManager()
    manager2 = EventManager()
    assert manager1 is manager2

def test_sync_subscribe_and_publish(event_manager):
    """测试同步事件订阅和发布"""
    received_events = []

    def callback(event):
        received_events.append(event)

    # 订阅事件
    event_manager.subscribe(EventType.CAMERA_CONNECTED, callback)
    
    # 发布事件
    test_event = Event(EventType.CAMERA_CONNECTED, {"status": True})
    event_manager.publish(test_event)
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 验证结果
    assert len(received_events) == 1
    assert received_events[0].type == EventType.CAMERA_CONNECTED
    assert received_events[0].data["status"] is True

def test_async_subscribe_and_publish(event_manager):
    """测试异步事件订阅和发布"""
    async_received_events = []

    def async_callback(event):
        time.sleep(0.1)  # 模拟异步操作
        async_received_events.append(event)

    # 订阅异步事件
    event_manager.subscribe(EventType.FRAME_CAPTURED, async_callback, is_async=True)
    
    # 发布事件
    test_event = Event(EventType.FRAME_CAPTURED, {"frame_id": 1})
    event_manager.publish(test_event)
    
    # 等待异步处理完成
    time.sleep(0.3)
    
    # 验证结果
    assert len(async_received_events) == 1
    assert async_received_events[0].type == EventType.FRAME_CAPTURED
    assert async_received_events[0].data["frame_id"] == 1

def test_multiple_subscribers(event_manager):
    """测试多个订阅者"""
    sync_events = []
    async_events = []

    def sync_callback(event):
        sync_events.append(event)

    def async_callback(event):
        time.sleep(0.1)
        async_events.append(event)

    # 添加多个订阅者
    event_manager.subscribe(EventType.PARAMETER_CHANGED, sync_callback)
    event_manager.subscribe(EventType.PARAMETER_CHANGED, async_callback, is_async=True)
    
    # 发布事件
    test_event = Event(EventType.PARAMETER_CHANGED, {"param": "exposure", "value": 100})
    event_manager.publish(test_event)
    
    # 等待处理完成
    time.sleep(0.3)
    
    # 验证结果
    assert len(sync_events) == 1
    assert len(async_events) == 1
    assert sync_events[0].data["param"] == "exposure"
    assert async_events[0].data["param"] == "exposure"
    assert sync_events[0].data["value"] == 100
    assert async_events[0].data["value"] == 100

def test_unsubscribe(event_manager):
    """测试取消订阅"""
    events = []
    
    def callback(event):
        events.append(event)

    # 订阅并发布
    event_manager.subscribe(EventType.ERROR_OCCURRED, callback)
    event_manager.publish(Event(EventType.ERROR_OCCURRED, {"error": "test"}))
    
    # 等待处理
    time.sleep(0.1)
    assert len(events) == 1
    assert events[0].data["error"] == "test"

    # 取消订阅并再次发布
    event_manager.unsubscribe(EventType.ERROR_OCCURRED, callback)
    event_manager.publish(Event(EventType.ERROR_OCCURRED, {"error": "test2"}))
    
    # 等待处理
    time.sleep(0.1)
    assert len(events) == 1  # 事件数量应该保持不变

def test_event_timestamp(event_manager):
    """测试事件时间戳"""
    received_event = None
    
    def callback(event):
        nonlocal received_event
        received_event = event
    
    # 订阅事件
    event_manager.subscribe(EventType.CAMERA_CONNECTED, callback)
    
    # 记录发布时间并发布事件
    event_manager.publish(Event(EventType.CAMERA_CONNECTED))
    
    # 等待处理
    time.sleep(0.1)
    
    # 验证时间戳
    assert received_event is not None
    # 确保时间戳是最近的时间（1秒误差）
    assert time.time() - received_event.timestamp < 1.0 

def test_error_handling(event_manager):
    """测试错误处理"""
    def faulty_callback(event):
        raise Exception("测试错误")
    
    # 订阅事件
    event_manager.subscribe(EventType.ERROR_OCCURRED, faulty_callback)
    
    # 发布事件 - 不应该抛出异常
    try:
        event_manager.publish(Event(EventType.ERROR_OCCURRED))
        time.sleep(0.1)
        assert True  # 如果到达这里，说明错误被正确处理
    except Exception:
        assert False  # 不应该到达这里

def test_event_types():
    """测试所有事件类型"""
    # 验证所有预定义的事件类型
    expected_types = {
        'CAMERA_CONNECTED',
        'CAMERA_DISCONNECTED',
        'FRAME_CAPTURED',
        'FRAME_PROCESSED',
        'PARAMETER_CHANGED',
        'ERROR_OCCURRED',
        'DISPLAY_MODE_CHANGED',
        'PROCESSING_STARTED',
        'PROCESSING_COMPLETED'
    }
    
    actual_types = {e.name for e in EventType}
    assert actual_types == expected_types

def test_multiple_event_types(event_manager):
    """测试多种事件类型的处理"""
    events_received = []
    
    def callback(event):
        events_received.append(event)
    
    # 订阅多个事件类型
    event_types = [
        EventType.CAMERA_CONNECTED,
        EventType.FRAME_CAPTURED,
        EventType.PROCESSING_COMPLETED
    ]
    
    for event_type in event_types:
        event_manager.subscribe(event_type, callback)
    
    # 发布不同类型的事件
    for event_type in event_types:
        event_manager.publish(Event(event_type, {"test": event_type.name}))
    
    # 等待处理
    time.sleep(0.1)
    
    # 验证结果
    assert len(events_received) == len(event_types)
    received_types = {event.type for event in events_received}
    assert received_types == set(event_types)

def test_concurrent_publish(event_manager):
    """测试并发发布事件"""
    received_events = []
    
    def callback(event):
        received_events.append(event)
    
    event_manager.subscribe(EventType.FRAME_CAPTURED, callback)
    
    # 并发发布多个事件
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for i in range(10):
            futures.append(
                executor.submit(
                    event_manager.publish,
                    Event(EventType.FRAME_CAPTURED, {"id": i})
                )
            )
    
    # 等待所有事件处理完成
    time.sleep(0.5)
    
    # 验证结果
    assert len(received_events) == 10
    received_ids = {event.data["id"] for event in received_events}
    assert received_ids == set(range(10))
