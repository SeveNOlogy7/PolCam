"""
相机模块测试代码
"""

import pytest
import time
from unittest.mock import MagicMock, patch
import numpy as np
from polcam.core.camera_module import CameraModule
from polcam.core.events import EventType

@pytest.fixture
def camera_module():
    with patch('gxipy.DeviceManager') as mock_dm:
        module = CameraModule()
        mock_dm.return_value.update_all_device_list.return_value = (1, ['dev1'])
        
        # 创建模拟设备和远程功能控制
        mock_device = MagicMock()
        mock_remote_feature = MagicMock()
        mock_dm.return_value.open_device_by_index.return_value = mock_device
        mock_device.get_remote_device_feature_control.return_value = mock_remote_feature
        
        # 设置默认参数值
        mock_remote_feature.get_float_feature.return_value.get.return_value = 10000.0
        mock_remote_feature.get_enum_feature.return_value.get.return_value = "Off"
        
        yield module

def test_module_lifecycle(camera_module):
    """测试模块生命周期"""
    # 测试初始化
    assert camera_module.initialize()
    assert camera_module.is_initialized()
    
    # 测试启动
    assert camera_module.start()
    assert camera_module.is_running()
    assert camera_module.is_connected()
    
    # 测试停止
    assert camera_module.stop()
    assert not camera_module.is_running()
    
    # 测试销毁
    assert camera_module.destroy()
    assert not camera_module.is_initialized()
    assert not camera_module.is_connected()

def test_camera_streaming(camera_module):
    """测试图像采集功能"""
    # 初始化并启动模块
    camera_module.initialize()
    camera_module.start()
    
    # 测试开始采集
    camera_module.start_streaming()
    assert camera_module.is_streaming()
    
    # 测试停止采集
    camera_module.stop_streaming()
    assert not camera_module.is_streaming()
    
    # 清理
    camera_module.destroy()

def test_parameter_control(camera_module):
    """测试参数控制"""
    # 初始化并启动模块
    camera_module.initialize()
    camera_module.start()
    
    # 测试曝光控制
    camera_module.set_exposure_time(20000.0)
    assert camera_module.get_last_exposure() == 20000.0
    
    # 测试增益控制
    camera_module.set_gain(10.0)
    assert camera_module.get_last_gain() == 10.0
    
    # 测试白平衡控制
    camera_module.set_white_balance_auto(True)
    assert camera_module.is_wb_auto()
    
    # 清理
    camera_module.destroy()

def test_event_emission(camera_module):
    """测试事件发送"""
    events_received = []
    
    def on_event(event):
        events_received.append(event)
    
    # 订阅事件
    camera_module.subscribe_event(EventType.CAMERA_CONNECTED, on_event)
    camera_module.subscribe_event(EventType.PARAMETER_CHANGED, on_event)
    
    # 初始化并启动模块
    camera_module.initialize()
    camera_module.start()
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 验证连接事件 - 确保至少接收到了CAMERA_CONNECTED事件
    assert any(event.type == EventType.CAMERA_CONNECTED for event in events_received)
    
    # 清除已接收的事件
    events_received.clear()
    
    # 测试参数改变事件
    camera_module.set_exposure_time(20000.0)
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 验证参数改变事件
    exposure_events = [
        event for event in events_received 
        if event.type == EventType.PARAMETER_CHANGED 
        and event.data.get("parameter") == "exposure"
    ]
    assert len(exposure_events) == 1
    assert exposure_events[0].data["value"] == 20000.0
    
    # 清理
    camera_module.destroy()

def test_frame_capture(camera_module):
    """测试图像采集"""
    # 初始化并启动模块，确保相机连接
    camera_module.initialize()
    camera_module.start()
    
    # 模拟图像数据
    mock_frame = np.zeros((1000, 1000), dtype=np.uint8)
    mock_image = MagicMock()
    mock_image.get_numpy_array.return_value = mock_frame
    mock_stream = MagicMock()
    mock_stream.get_image.return_value = mock_image
    
    # 为相机对象添加数据流
    camera_module._camera.data_stream = [mock_stream]
    
    frames_received = []
    def on_frame(event):
        frames_received.append(event.data["frame"])
    
    # 订阅帧捕获事件
    camera_module.subscribe_event(EventType.FRAME_CAPTURED, on_frame)
    
    # 启动采集
    camera_module.start_streaming()
    
    # 等待接收帧
    time.sleep(0.2)
    
    # 验证接收到的帧
    assert len(frames_received) > 0
    assert isinstance(frames_received[0], np.ndarray)
    assert frames_received[0].shape == (1000, 1000)
    
    # 停止采集并清理
    camera_module.stop_streaming()
    camera_module.destroy()

def test_error_handling(camera_module):
    """测试错误处理"""
    errors_received = []
    
    def on_error(event):
        errors_received.append(event)
    
    camera_module.subscribe_event(EventType.ERROR_OCCURRED, on_error)
    
    # 确保模块已初始化
    camera_module.initialize()
    
    # 模拟设备打开失败
    with patch.object(camera_module.device_manager, 'open_device_by_index') as mock_open:
        mock_open.side_effect = Exception("模拟设备打开失败")
        
        # 尝试连接
        success = camera_module.connect()
        assert not success
        
        # 等待事件处理
        time.sleep(0.1)
        
        # 验证错误事件
        assert len(errors_received) > 0
        error_events = [e for e in errors_received if e.type == EventType.ERROR_OCCURRED]
        assert len(error_events) == 1
        assert "模拟设备打开失败" in error_events[0].data["error"]
        
    # 清理
    camera_module.destroy()

def test_parameter_validation(camera_module):
    """测试参数验证和边界条件"""
    camera_module.initialize()
    camera_module.start()
    
    # 测试正常范围的参数
    camera_module.set_exposure_time(10000.0)
    assert camera_module.get_last_exposure() == 10000.0
    
    camera_module.set_gain(10.0)
    assert camera_module.get_last_gain() == 10.0
    
    # 清理
    camera_module.destroy()

def test_streaming_lifecycle(camera_module):
    """测试流采集的生命周期"""
    camera_module.initialize()
    camera_module.start()
    
    # 测试启动流采集
    camera_module.start_streaming()
    assert camera_module.is_streaming()
    
    # 测试重复启动
    camera_module.start_streaming()  # 不应该有影响
    assert camera_module.is_streaming()
    
    # 测试停止流采集
    camera_module.stop_streaming()
    assert not camera_module.is_streaming()
    
    # 测试重复停止
    camera_module.stop_streaming()  # 不应该有影响
    assert not camera_module.is_streaming()
    
    # 清理
    camera_module.destroy()

def test_module_state(camera_module):
    """测试模块状态管理"""
    # 测试初始状态
    assert not camera_module.is_initialized()
    assert not camera_module.is_running()
    assert not camera_module.is_connected()
    assert not camera_module.is_streaming()
    
    # 测试初始化后的状态
    camera_module.initialize()
    assert camera_module.is_initialized()
    assert not camera_module.is_running()
    
    # 测试启动后的状态
    camera_module.start()
    assert camera_module.is_initialized()
    assert camera_module.is_running()
    assert camera_module.is_connected()
    
    # 测试停止后的状态
    camera_module.stop()
    assert camera_module.is_initialized()
    assert not camera_module.is_running()
    
    # 测试销毁后的状态
    camera_module.destroy()
    assert not camera_module.is_initialized()
    assert not camera_module.is_running()
    assert not camera_module.is_connected()

def test_auto_exposure_control(camera_module):
    """测试自动曝光控制"""
    camera_module.initialize()
    camera_module.start()
    
    # 记录事件
    events_received = []
    def on_event(event):
        events_received.append(event)
    camera_module.subscribe_event(EventType.PARAMETER_CHANGED, on_event)
    
    # 测试自动曝光开关
    camera_module.set_exposure_auto(True)
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 验证参数变化事件
    exposure_auto_events = [
        e for e in events_received 
        if (e.type == EventType.PARAMETER_CHANGED and 
            e.data.get("parameter") == "exposure_auto")
    ]
    assert len(exposure_auto_events) == 1
    assert exposure_auto_events[0].data["value"] is True
    
    # 清除已接收的事件
    events_received.clear()
    
    # 测试单次自动曝光
    camera_module.set_exposure_once()
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 验证曝光值变化事件
    exposure_events = [
        e for e in events_received 
        if (e.type == EventType.PARAMETER_CHANGED and 
            e.data.get("parameter") == "exposure")
    ]
    assert len(exposure_events) == 1
    assert isinstance(exposure_events[0].data["value"], (int, float))
    
    # 清理
    camera_module.destroy()

def test_auto_gain_control(camera_module):
    """测试自动增益控制"""
    camera_module.initialize()
    camera_module.start()
    
    # 记录事件
    events_received = []
    def on_event(event):
        events_received.append(event)
    camera_module.subscribe_event(EventType.PARAMETER_CHANGED, on_event)
    
    # 测试自动增益开关
    camera_module.set_gain_auto(True)
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 验证参数变化事件
    gain_auto_events = [
        e for e in events_received 
        if (e.type == EventType.PARAMETER_CHANGED and 
            e.data.get("parameter") == "gain_auto")
    ]
    assert len(gain_auto_events) == 1
    assert gain_auto_events[0].data["value"] is True
    
    # 清除已接收的事件
    events_received.clear()
    
    # 测试单次自动增益
    camera_module.set_gain_once()
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 验证增益值变化事件
    gain_events = [
        e for e in events_received 
        if (e.type == EventType.PARAMETER_CHANGED and 
            e.data.get("parameter") == "gain")
    ]
    assert len(gain_events) == 1
    assert isinstance(gain_events[0].data["value"], (int, float))
    
    # 清理
    camera_module.destroy()

def test_white_balance_control(camera_module):
    """测试白平衡控制"""
    camera_module.initialize()
    camera_module.start()
    
    # 记录事件
    events_received = []
    def on_event(event):
        events_received.append(event)
    camera_module.subscribe_event(EventType.PARAMETER_CHANGED, on_event)
    
    # 测试自动白平衡开关
    camera_module.set_white_balance_auto(True)
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 验证参数变化事件
    wb_auto_events = [
        e for e in events_received 
        if (e.type == EventType.PARAMETER_CHANGED and 
            e.data.get("parameter") == "white_balance_auto")
    ]
    assert len(wb_auto_events) == 1
    assert wb_auto_events[0].data["value"] is True
    assert camera_module.is_wb_auto()
    
    # 清除已接收的事件
    events_received.clear()
    
    # 测试单次白平衡
    camera_module.set_balance_white_once()
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 验证白平衡完成事件
    wb_events = [
        e for e in events_received 
        if (e.type == EventType.PARAMETER_CHANGED and 
            e.data.get("parameter") == "white_balance")
    ]
    assert len(wb_events) == 1
    assert wb_events[0].data["value"] == "once_completed"
    
    # 清理
    camera_module.destroy()

def test_parameter_persistence(camera_module):
    """测试参数持久化"""
    camera_module.initialize()
    camera_module.start()
    
    # 设置参数
    test_exposure = 15000.0
    test_gain = 5.0
    
    camera_module.set_exposure_time(test_exposure)
    camera_module.set_gain(test_gain)
    
    # 验证最后设置的参数值
    assert camera_module.get_last_exposure() == test_exposure
    assert camera_module.get_last_gain() == test_gain
    
    # 模拟断开重连
    camera_module.stop()
    camera_module.start()
    
    # 验证参数是否保持
    assert camera_module.get_last_exposure() == test_exposure
    assert camera_module.get_last_gain() == test_gain
    
    # 清理
    camera_module.destroy()

def test_error_event_emission(camera_module):
    """测试错误事件发送"""
    # 记录错误事件
    errors_received = []
    def on_error(event):
        if event.type == EventType.ERROR_OCCURRED:
            errors_received.append(event)
    
    # 订阅错误事件
    camera_module.subscribe_event(EventType.ERROR_OCCURRED, on_error)
    
    # 初始化和启动模块
    camera_module.initialize()
    camera_module.start()
    
    # 模拟远程特性对象
    mock_feature = MagicMock()
    mock_feature.set = MagicMock(side_effect=Exception("模拟设置参数失败"))
    
    # 替换get_float_feature方法
    camera_module._remote_feature.get_float_feature = MagicMock(return_value=mock_feature)
    
    # 尝试设置参数
    camera_module.set_exposure_time(10000.0)
    
    # 等待事件处理
    time.sleep(0.2)
    
    # 验证错误事件
    error_events = [
        e for e in errors_received 
        if e.type == EventType.ERROR_OCCURRED and 
        "模拟设置参数失败" in str(e.data.get("error", ""))
    ]
    assert len(error_events) > 0
    
    # 检查错误内容
    error_event = error_events[0]
    assert error_event.data["source"] == "camera"
    assert "模拟设置参数失败" in error_event.data["error"]
    
    # 清理
    camera_module.destroy()

def test_streaming_events(camera_module):
    """测试流采集相关事件"""
    camera_module.initialize()
    camera_module.start()
    
    # 记录事件
    events_received = []
    event_order = []  # 记录事件顺序
    
    def on_event(event):
        events_received.append(event)
        event_order.append(event.type)
    
    # 先订阅事件
    camera_module.subscribe_event(EventType.PROCESSING_STARTED, on_event)
    camera_module.subscribe_event(EventType.PROCESSING_COMPLETED, on_event)
    camera_module.subscribe_event(EventType.FRAME_CAPTURED, on_event)
    
    # 设置模拟图像数据
    mock_frame = np.zeros((1000, 1000), dtype=np.uint8)
    mock_image = MagicMock()
    mock_image.get_numpy_array.return_value = mock_frame
    mock_stream = MagicMock()
    mock_stream.get_image.return_value = mock_image
    camera_module._camera.data_stream = [mock_stream]
    
    # 启动流采集
    camera_module.start_streaming()
    
    # 等待足够长的时间以接收多个帧
    time.sleep(0.5)
    
    # 停止流采集
    camera_module.stop_streaming()
    
    # 额外等待以确保所有事件都被处理
    time.sleep(0.2)
    
    # 打印事件顺序以帮助调试
    print(f"事件顺序: {[e.name for e in event_order]}")
    
    # 验证基本事件存在
    assert any(e.type == EventType.PROCESSING_STARTED for e in events_received), "缺少处理开始事件"
    assert any(e.type == EventType.FRAME_CAPTURED for e in events_received), "缺少帧捕获事件"
    assert any(e.type == EventType.PROCESSING_COMPLETED for e in events_received), "缺少处理完成事件"
    
    # 验证事件顺序
    start_index = event_order.index(EventType.PROCESSING_STARTED)
    complete_index = event_order.index(EventType.PROCESSING_COMPLETED)
    assert start_index == 0, "处理开始事件应该是第一个事件"
    assert complete_index == len(event_order) - 1, "处理完成事件应该是最后一个事件"
    
    # 验证帧事件在开始和完成事件之间
    frame_events = [e for e in events_received if e.type == EventType.FRAME_CAPTURED]
    assert len(frame_events) > 0, "应该至少捕获一帧"
    for frame_event in frame_events:
        assert "frame" in frame_event.data, "帧事件缺少frame数据"
        assert "timestamp" in frame_event.data, "帧事件缺少timestamp数据"
        assert isinstance(frame_event.data["frame"], np.ndarray), "帧数据类型错误"
    
    # 清理
    camera_module.destroy()
