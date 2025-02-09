import pytest
from unittest.mock import MagicMock, patch
from polcam.core.camera import Camera

@pytest.fixture
def mock_camera():
    with patch('gxipy.DeviceManager') as mock_dm:
        camera = Camera()
        mock_dm.return_value.update_all_device_list.return_value = (1, ['dev1'])
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
