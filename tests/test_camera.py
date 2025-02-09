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
        assert mock_camera.connect()
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
