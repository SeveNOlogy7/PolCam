"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from polcam.core.camera import Camera
from polcam.core.image_processor import ImageProcessor
from polcam.gui.main_window import MainWindow
from tests.test_camera import mock_camera  # 导入mock_camera fixture

def test_camera_to_processor_integration(mock_camera):
    """测试相机采集到图像处理的集成"""
    success, _ = mock_camera.connect()
    assert success

    # 创建模拟帧数据
    mock_frame = np.zeros((16, 16), dtype=np.uint8)
    # 设置偏振马赛克模式
    mock_frame[0::2, 0::2] = 100  # 0度
    mock_frame[0::2, 1::2] = 150  # 45度
    mock_frame[1::2, 0::2] = 200  # 90度
    mock_frame[1::2, 1::2] = 250  # 135度
    mock_camera.get_frame = lambda: mock_frame

    # 获取帧并验证
    frame = mock_camera.get_frame()
    assert frame is not None
    assert frame.shape == (16, 16)

    # 创建图像处理器实例
    processor = ImageProcessor()

    # 测试解马赛克处理
    color_images = processor.demosaic_polarization(frame)
    assert len(color_images) == 4
    assert all(img.shape == (16, 16, 3) for img in color_images)
    
    # 转换为灰度图像
    gray_images = processor.to_grayscale(color_images)
    assert len(gray_images) == 4
    assert all(img.shape == (16, 16) for img in gray_images)

    # 计算偏振参数并验证
    dolp, aolp, docp = processor.calculate_polarization_parameters(color_images)
    assert dolp.shape == (16, 16)
    assert aolp.shape == (16, 16)
    assert docp.shape == (16, 16)
    assert np.all(dolp >= 0) and np.all(dolp <= 1)
    assert np.all(aolp >= 0) and np.all(aolp <= 180)

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

def test_camera_processor_pipeline(mock_camera):
    """测试相机和图像处理器的完整工作流"""
    processor = ImageProcessor()
    
    # 模拟相机采集帧
    mock_frame = np.zeros((16, 16), dtype=np.uint8)
    for y in range(0, 16, 2):
        for x in range(0, 16, 2):
            mock_frame[y, x] = 200      # 0度位置
            mock_frame[y, x+1] = 150    # 45度位置
            mock_frame[y+1, x] = 100    # 90度位置
            mock_frame[y+1, x+1] = 50   # 135度位置
    
    # 1. 偏振图像解码
    color_images = processor.demosaic_polarization(mock_frame)
    assert len(color_images) == 4
    
    # 2. 白平衡处理
    balanced_images = [processor.auto_white_balance(img) for img in color_images]
    assert all(img.dtype == np.uint8 for img in balanced_images)
    
    # 3. 偏振参数计算
    dolp, aolp, docp = processor.calculate_polarization_parameters(balanced_images)
    assert all(param.shape == (16, 16) for param in [dolp, aolp, docp])

def test_gui_camera_streaming(qapp, mock_camera):
    """测试GUI和相机的流模式集成"""
    window = MainWindow()
    window.camera = mock_camera
    
    # 设置模拟帧
    mock_frames = []
    for i in range(3):  # 创建3帧测试数据
        frame = np.zeros((16, 16), dtype=np.uint8)
        frame.fill(50 * (i + 1))  # 每帧递增亮度
        mock_frames.append(frame)
    
    frame_index = 0
    def mock_get_frame():
        nonlocal frame_index
        frame = mock_frames[frame_index % len(mock_frames)]
        frame_index += 1
        return frame
    
    mock_camera.get_frame = mock_get_frame
    
    # 测试流模式
    window.handle_stream(True)
    assert window.timer.isActive()
    
    # 模拟几次定时器触发
    for _ in range(3):
        window.update_frame()
        
    window.handle_stream(False)
    assert not window.timer.isActive()

def test_camera_parameter_control(qapp, mock_camera):
    """测试相机参数控制集成"""
    window = MainWindow()
    
    # 首先mock所有需要的相机方法
    mock_device = MagicMock()
    mock_feature = MagicMock()
    exposure_feature = MagicMock()
    gain_feature = MagicMock()
    
    # 设置预期值
    expected_exposure = 5000.0
    expected_gain = 10.0
    
    # 配置mock对象
    mock_camera.remote_feature = mock_feature
    mock_camera.camera = mock_device
    mock_feature.get_float_feature.side_effect = lambda name: {
        'ExposureTime': exposure_feature,
        'Gain': gain_feature
    }[name]
    exposure_feature.get.return_value = expected_exposure
    gain_feature.get.return_value = expected_gain
    
    # Mock所有需要的相机方法
    mock_camera.set_exposure_time = MagicMock()
    mock_camera.set_gain = MagicMock()
    mock_camera.set_exposure_auto = MagicMock()
    mock_camera.set_gain_auto = MagicMock()
    
    # 设置相机对象
    window.camera = mock_camera
    
    # 确保信号连接正确设置
    window.setup_connections()
    
    # 模拟相机连接
    with patch.object(mock_camera.device_manager, 'update_all_device_list', 
                     return_value=(1, ['dev1'])):
        # 连接相机
        window.handle_connect(True)
        qapp.processEvents()
        
        # 验证控件状态
        assert window.camera_control.exposure_spin.isEnabled()
        assert window.camera_control.gain_spin.isEnabled()
        
        # 测试曝光控制 - 通过控件设置值
        window.camera_control.exposure_spin.setValue(expected_exposure)
        qapp.processEvents()
        mock_camera.set_exposure_time.assert_called_with(expected_exposure)
        
        # 测试增益控制 - 通过控件设置值
        window.camera_control.gain_spin.setValue(expected_gain)
        qapp.processEvents()
        mock_camera.set_gain.assert_called_with(expected_gain)
        
        # 测试自动曝光
        window.camera_control.exposure_auto.setChecked(True)
        qapp.processEvents()
        mock_camera.set_exposure_auto.assert_called_with(True)
        
        # 测试自动增益
        window.camera_control.gain_auto.setChecked(True)
        qapp.processEvents()
        mock_camera.set_gain_auto.assert_called_with(True)

def test_error_propagation(qapp, mock_camera):
    """测试错误传播处理"""
    window = MainWindow()
    window.camera = mock_camera
    
    # 首先建立正常连接
    with patch.object(mock_camera.device_manager, 'update_all_device_list', 
                     return_value=(1, ['dev1'])):
        window.handle_connect(True)
        qapp.processEvents()
    
    # 模拟图像获取错误
    error_message = "模拟错误"
    def raise_error(*args):
        raise Exception(error_message)
    
    mock_camera.get_frame = raise_error
    
    # 捕获可能的警告对话框
    with patch('PyQt5.QtWidgets.QMessageBox.warning') as mock_warning:
        # 测试单帧采集错误处理
        window.handle_capture()
        # 验证错误警告是否被显示
        assert mock_warning.called
        assert error_message in mock_warning.call_args[0][2]  # 完整的错误消息
        
        # 重置mock
        mock_warning.reset_mock()
        
        # 测试流模式错误处理
        window.handle_stream(True)
        window.update_frame()  # 这应该不会引发未捕获的异常
        # 流模式下的错误可能会显示不同的警告或不显示警告
        
        window.handle_stream(False)

def test_display_mode_integration(qapp, mock_camera):
    """测试显示模式和图像处理集成"""
    window = MainWindow()
    window.camera = mock_camera
    
    # 创建测试帧
    test_frame = np.zeros((16, 16), dtype=np.uint8)
    test_frame[4:12, 4:12] = 200  # 添加一个明显的特征
    mock_camera.get_frame = lambda: test_frame
    
    # 测试所有显示模式
    for mode in range(window.image_display.display_mode.count()):
        window.image_display.display_mode.setCurrentIndex(mode)
        window.handle_capture()
        assert window.image_display.image_label.pixmap() is not None
