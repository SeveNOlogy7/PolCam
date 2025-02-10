"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

import pytest
from unittest.mock import MagicMock, patch
from polcam.core.camera import Camera

@pytest.fixture
def mock_camera():
    with patch('gxipy.DeviceManager') as mock_dm:
        camera = Camera()
        mock_dm.return_value.update_all_device_list.return_value = (1, ['dev1'])
        
        # 创建模拟设备和远程功能控制
        mock_device = MagicMock()
        mock_remote_feature = MagicMock()
        mock_dm.return_value.open_device_by_index.return_value = mock_device
        mock_device.get_remote_device_feature_control.return_value = mock_remote_feature
        
        # 设置默认参数值
        mock_remote_feature.get_float_feature.return_value.get.return_value = 10000.0
        mock_remote_feature.get_enum_feature.return_value.get.return_value = "Off"
        
        yield camera

def test_camera_connect(mock_camera):
    # 模拟相机连接
    with patch.object(mock_camera.device_manager, 'open_device_by_index') as mock_open:
        mock_device = MagicMock()
        mock_open.return_value = mock_device
        
        # 测试连接
        success, error_msg = mock_camera.connect()
        assert success
        assert error_msg == ""
        assert mock_camera.camera is not None

def test_camera_disconnect(mock_camera):
    # 设置模拟的相机对象
    mock_camera.camera = MagicMock()
    mock_camera.is_streaming = False
    
    # 测试断开连接
    mock_camera.disconnect()
    assert mock_camera.camera is None

def test_camera_streaming(mock_camera):
    # 设置模拟的相机对象
    mock_camera.camera = MagicMock()
    
    # 测试开始采集
    mock_camera.start_streaming()
    assert mock_camera.is_streaming
    assert mock_camera.camera.stream_on.called
    
    # 测试停止采集
    mock_camera.stop_streaming()
    assert not mock_camera.is_streaming
    assert mock_camera.camera.stream_off.called

def test_camera_get_frame(mock_camera):
    # 设置模拟的相机对象
    mock_camera.camera = MagicMock()
    mock_camera.is_streaming = True
    mock_image = MagicMock()
    mock_image.get_numpy_array.return_value = None
    mock_camera.camera.data_stream = [MagicMock()]
    mock_camera.camera.data_stream[0].get_image.return_value = mock_image
    
    # 测试获取图像
    frame = mock_camera.get_frame()
    assert mock_camera.camera.data_stream[0].get_image.called

def test_camera_connection_timeout(mock_camera):
    with patch.object(mock_camera.device_manager, 'open_device_by_index') as mock_open:
        mock_open.side_effect = TimeoutError("Connection timeout")
        success, error_msg = mock_camera.connect()
        assert not success
        assert "Connection timeout" in error_msg

def test_camera_frame_timeout(mock_camera):
    mock_camera.camera = MagicMock()
    mock_camera.is_streaming = True
    mock_camera.camera.data_stream = [MagicMock()]
    mock_camera.camera.data_stream[0].get_image.side_effect = TimeoutError()
    
    assert mock_camera.get_frame() is None

def test_camera_settings(mock_camera):
    # 创建模拟的相机对象和特性控制
    mock_device = MagicMock()
    mock_remote_feature = MagicMock()
    mock_exposure_feature = MagicMock()
    mock_gain_feature = MagicMock()
    
    # 设置特性控制关系
    mock_device.get_remote_device_feature_control.return_value = mock_remote_feature
    mock_remote_feature.get_float_feature.side_effect = lambda name: {
        'ExposureTime': mock_exposure_feature,
        'Gain': mock_gain_feature
    }[name]
    
    # 设置相机对象
    mock_camera.camera = mock_device
    mock_camera.remote_feature = mock_remote_feature
    
    # 测试曝光时间设置
    mock_camera.set_exposure_time(1000)
    mock_exposure_feature.set.assert_called_once_with(1000.0)
    
    # 测试增益设置
    mock_camera.set_gain(2.0)
    mock_gain_feature.set.assert_called_once_with(2.0)

def test_camera_settings_no_connection(mock_camera):
    # 测试未连接相机时
    mock_camera.camera = None
    mock_camera.set_exposure_time(1000)  # 不应抛出异常，只记录错误
    mock_camera.set_gain(2.0)  # 不应抛出异常，只记录错误

def test_camera_connection_no_device(mock_camera):
    # 测试没有找到设备的情况
    with patch.object(mock_camera.device_manager, 'update_all_device_list') as mock_update:
        mock_update.return_value = (0, [])
        success, error_msg = mock_camera.connect()
        assert not success
        assert "未找到相机设备" in error_msg

def test_exposure_control(mock_camera):
    """测试曝光控制功能"""
    # 连接相机
    success, _ = mock_camera.connect()
    assert success
    
    # 测试设置曝光时间
    mock_camera.set_exposure_time(20000.0)
    mock_camera.remote_feature.get_float_feature.assert_called_with("ExposureTime")
    
    # 测试自动曝光
    mock_camera.set_exposure_auto(True)
    mock_camera.remote_feature.get_enum_feature.assert_called_with("ExposureAuto")
    mock_camera.remote_feature.get_enum_feature.return_value.set.assert_called_with("Continuous")
    
    # 测试单次自动曝光
    mock_camera.set_exposure_once()
    mock_camera.remote_feature.get_enum_feature.return_value.set.assert_called_with("Once")
    
    # 测试获取曝光值
    assert mock_camera.get_exposure_time() == 10000.0

def test_gain_control(mock_camera):
    """测试增益控制功能"""
    success, _ = mock_camera.connect()
    assert success
    
    # 测试设置增益值
    mock_camera.set_gain(5.0)
    mock_camera.remote_feature.get_float_feature.assert_called_with("Gain")
    
    # 测试自动增益
    mock_camera.set_gain_auto(True)
    mock_camera.remote_feature.get_enum_feature.assert_called_with("GainAuto")
    mock_camera.remote_feature.get_enum_feature.return_value.set.assert_called_with("Continuous")
    
    # 测试单次自动增益
    mock_camera.set_gain_once()
    mock_camera.remote_feature.get_enum_feature.return_value.set.assert_called_with("Once")
    
    # 测试获取增益值
    assert mock_camera.get_gain() == 10000.0

def test_white_balance_control(mock_camera):
    """测试白平衡控制功能"""
    success, _ = mock_camera.connect()
    assert success
    
    # 测试自动白平衡
    mock_camera.set_balance_white_auto(True)
    mock_camera.remote_feature.get_enum_feature.assert_called_with("BalanceWhiteAuto")
    mock_camera.remote_feature.get_enum_feature.return_value.set.assert_called_with("Continuous")
    
    # 测试单次白平衡
    mock_camera.set_balance_white_once()
    mock_camera.remote_feature.get_enum_feature.return_value.set.assert_called_with("Once")
    
    # 测试获取白平衡状态
    assert mock_camera.is_wb_auto() is False

def test_streaming_control(mock_camera):
    """测试图像流控制功能"""
    success, _ = mock_camera.connect()
    assert success
    
    # 测试开始采集
    mock_camera.start_streaming()
    assert mock_camera.is_streaming is True
    mock_camera.camera.stream_on.assert_called_once()
    
    # 测试获取帧
    mock_image = MagicMock()
    mock_image.get_numpy_array.return_value = "frame_data"
    mock_camera.camera.data_stream = [MagicMock()]
    mock_camera.camera.data_stream[0].get_image.return_value = mock_image
    
    frame = mock_camera.get_frame()
    assert frame == "frame_data"
    
    # 测试停止采集
    mock_camera.stop_streaming()
    assert mock_camera.is_streaming is False
    mock_camera.camera.stream_off.assert_called_once()

def test_error_handling(mock_camera):
    """测试错误处理"""
    # 测试设备未找到
    with patch.object(mock_camera.device_manager, 'update_all_device_list') as mock_update:
        mock_update.return_value = (0, [])
        success, error_msg = mock_camera.connect()
        assert not success
        assert "未找到相机设备" in error_msg
    
    # 测试连接超时
    with patch.object(mock_camera.device_manager, 'open_device_by_index') as mock_open:
        mock_open.side_effect = TimeoutError("Connection timeout")
        success, error_msg = mock_camera.connect()
        assert not success
        assert "Connection timeout" in error_msg
    
    # 测试断开连接时的错误处理
    mock_camera.camera = MagicMock()
    mock_camera.camera.close_device.side_effect = Exception("Disconnect error")
    mock_camera.disconnect()  # 不应抛出异常
    assert mock_camera.camera is None  # 即使出错，相机对象也应被清除

def test_parameter_validation(mock_camera):
    """测试参数验证"""
    success, _ = mock_camera.connect()
    assert success
    
    # 测试曝光时间范围
    mock_camera.set_exposure_time(-1)  # 应该被忽略或记录错误
    mock_camera.set_exposure_time(1000000.1)  # 应该被忽略或记录错误
    
    # 测试增益范围
    mock_camera.set_gain(-0.1)  # 应该被忽略或记录错误
    mock_camera.set_gain(24.1)  # 应该被忽略或记录错误

def test_camera_state(mock_camera):
    """测试相机状态维护"""
    # 测试初始状态
    assert mock_camera.camera is None
    assert mock_camera.is_streaming is False
    assert mock_camera._wb_auto is False
    
    # 连接后的状态
    success, _ = mock_camera.connect()
    assert success
    assert mock_camera.camera is not None
    
    # 开始采集后的状态
    mock_camera.start_streaming()
    assert mock_camera.is_streaming is True
    
    # 断开连接后的状态
    mock_camera.disconnect()
    assert mock_camera.camera is None
    assert mock_camera.is_streaming is False
