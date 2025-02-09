import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from polcam.core.camera import Camera
from polcam.core.image_processor import ImageProcessor
from polcam.gui.main_window import MainWindow
from tests.test_camera import mock_camera  # 导入mock_camera fixture

def test_camera_to_processor_integration(mock_camera):
    # 测试相机采集到图像处理的集成
    success, _ = mock_camera.connect()
    assert success
    
    # 创建模拟帧数据 - 使用16x16的测试图像以确保足够的尺寸
    mock_frame = np.zeros((16, 16), dtype=np.uint8)
    # 设置一些有意义的测试数据
    mock_frame[0::2, 0::2] = 100  # 0度
    mock_frame[0::2, 1::2] = 150  # 45度
    mock_frame[1::2, 0::2] = 200  # 90度
    mock_frame[1::2, 1::2] = 250  # 135度
    mock_camera.get_frame = lambda: mock_frame
    
    frame = mock_camera.get_frame()
    assert frame is not None
    assert frame.shape == (16, 16)
    
    # 测试解马赛克处理
    color_images, gray_images = ImageProcessor.demosaic_polarization(frame)
    assert len(color_images) == 4
    assert len(gray_images) == 4
    
    # 验证解马赛克后的图像尺寸 - 保持原始尺寸
    for img in color_images:
        assert img.shape[:2] == (16, 16)  # 解马赛克后保持原始尺寸
        assert img.shape[2] == 3  # 确认是彩色图像
    for img in gray_images:
        assert img.shape == (16, 16)  # 灰度图也保持原始尺寸
    
    # 计算偏振度并验证
    dolp = ImageProcessor.calculate_polarization_degree(gray_images)
    assert dolp is not None
    assert dolp.shape == (16, 16)  # DoLP保持与输入相同的尺寸
    assert np.all(dolp >= 0) and np.all(dolp <= 1)

def test_gui_camera_integration(qapp, mock_camera):
    window = MainWindow()
    window.camera = mock_camera
    
    # 测试相机连接
    window.camera_control.connect_btn.setChecked(True)
    window.handle_connect(True)
    assert window.camera_control.capture_btn.isEnabled()
    assert window.camera_control.stream_btn.isEnabled()
    assert window.status_indicator.isEnabled()
    
    # 创建模拟图像数据
    mock_frame = np.zeros((16, 16), dtype=np.uint8)
    mock_camera.get_frame = lambda: mock_frame
    
    # 测试图像显示更新
    window.process_and_display_frame(mock_frame)
    assert window.image_display.image_label.pixmap() is not None

def test_gui_camera_integration_connection_failure(qapp, mock_camera):
    window = MainWindow()
    window.camera = mock_camera
    
    # 模拟连接失败
    # 先设置假连接
    window.camera_control.connect_btn.setChecked(True)
    window.handle_connect(True)
    # 然后断开连接
    window.handle_connect(False)
    
    # 验证所有控件都处于禁用状态
    assert not window.camera_control.capture_btn.isEnabled()
    assert not window.camera_control.stream_btn.isEnabled()
    assert not window.status_indicator.isEnabled()
    assert not window.status_indicator.isStatus()  # 检查状态指示器的状态
    assert window.status_label.text() == "就绪"

def test_gui_camera_direct_connection_failure(qapp, mock_camera):
    window = MainWindow()
    window.camera = mock_camera
    
    # 直接模拟连接失败
    with patch.object(mock_camera, 'connect', return_value=(False, "连接失败测试")):
        window.camera_control.connect_btn.setChecked(True)
        window.handle_connect(True)
        
        # 验证失败状态
        assert not window.camera_control.capture_btn.isEnabled()
        assert not window.camera_control.stream_btn.isEnabled()
        assert not window.status_indicator.isEnabled()
        assert not window.status_indicator.isStatus()
        assert window.status_label.text() == "连接失败测试"

def test_gui_display_modes(qapp, mock_camera):
    window = MainWindow()
    window.camera = mock_camera
    
    # 创建测试图像并添加一些测试数据
    mock_frame = np.zeros((16, 16), dtype=np.uint8)
    mock_frame[0::2, 0::2] = 100
    
    # 测试不同显示模式
    for mode_index in range(5):  # 测试所有5种显示模式
        window.image_display.display_mode.setCurrentIndex(mode_index)
        window.process_and_display_frame(mock_frame)
        assert window.image_display.image_label.pixmap() is not None
