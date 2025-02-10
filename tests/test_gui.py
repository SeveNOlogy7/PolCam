"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

import pytest
from qtpy.QtCore import Qt, QSize
from qtpy.QtWidgets import QApplication
from unittest.mock import MagicMock, patch
from polcam.gui.main_window import MainWindow
from polcam.gui.camera_control import CameraControl
from polcam.gui.image_display import ImageDisplay
from polcam.gui.styles import Styles
import numpy as np

@pytest.fixture
def main_window(qapp):
    return MainWindow()

def test_main_window_init(main_window):
    """测试主窗口初始化"""
    assert isinstance(main_window.camera_control, CameraControl)
    assert isinstance(main_window.image_display, ImageDisplay)
    assert main_window.windowTitle() == "偏振相机控制系统"
    assert main_window.size() == QSize(1200, 800)

def test_camera_control(qapp):
    control = CameraControl()
    
    # 测试初始状态
    assert not control.capture_btn.isEnabled()
    assert not control.stream_btn.isEnabled()
    
    # 测试连接状态改变
    control.set_connected(True)
    assert control.capture_btn.isEnabled()
    assert control.stream_btn.isEnabled()

def test_camera_control_signals(qapp):
    """测试相机控制信号"""
    control = CameraControl()
    
    # 测试按钮信号
    signals_received = []
    control.connect_clicked.connect(lambda x: signals_received.append(('connect', x)))
    control.capture_clicked.connect(lambda: signals_received.append('capture'))
    control.stream_clicked.connect(lambda x: signals_received.append(('stream', x)))
    
    # 先启用相机连接
    control.connect_btn.click()  # 连接相机
    control.set_connected(True)  # 模拟成功连接
    
    # 触发其他信号
    control.capture_btn.click()
    control.stream_btn.click()
    
    # 验证信号接收
    assert ('connect', True) in signals_received
    assert 'capture' in signals_received
    assert ('stream', True) in signals_received
    
    # 测试断开连接
    signals_received.clear()
    control.connect_btn.click()  # 断开连接
    assert ('connect', False) in signals_received

def test_camera_control_disabled_signals(qapp):
    """测试未连接状态下的信号"""
    control = CameraControl()
    
    # 测试按钮信号
    signals_received = []
    control.capture_clicked.connect(lambda: signals_received.append('capture'))
    control.stream_clicked.connect(lambda x: signals_received.append(('stream', x)))
    
    # 在未连接状态下点击按钮
    control.capture_btn.click()
    control.stream_btn.click()
    
    # 验证没有信号被触发
    assert len(signals_received) == 0

def test_camera_control_parameter_controls(qapp):
    """测试参数控制功能"""
    control = CameraControl()
    
    # 测试曝光控制
    control.exposure_spin.setValue(5000)
    assert control.exposure_spin.value() == 5000
    
    # 测试增益控制
    control.gain_spin.setValue(10)
    assert control.gain_spin.value() == 10
    
    # 测试自动模式切换
    control.exposure_auto.setChecked(True)
    assert control.exposure_spin.isReadOnly()
    assert not control.exposure_once.isEnabled()
    
    control.gain_auto.setChecked(True)
    assert control.gain_spin.isReadOnly()
    assert not control.gain_once.isEnabled()

def test_image_display(qapp):
    display = ImageDisplay()
    
    # 测试显示模式数量（实际有8种模式）
    assert display.display_mode.count() == 8
    assert display.display_mode.currentIndex() == 0

def test_image_display_interaction(qapp):
    display = ImageDisplay()
    
    # 测试切换显示模式
    display.display_mode.setCurrentIndex(1)
    expected_modes = [
        "原始图像",
        "单角度彩色",
        "单角度灰度",
        "彩色图像",
        "灰度图像",
        "四角度彩色",
        "四角度灰度",
        "偏振度图像"
    ]
    assert display.display_mode.currentText() in expected_modes

def test_display_mode_items(qapp):
    display = ImageDisplay()
    expected_modes = [
        "原始图像",
        "单角度彩色",
        "单角度灰度",
        "彩色图像",
        "灰度图像",
        "四角度彩色",
        "四角度灰度",
        "偏振度图像"
    ]
    
    # 测试所有显示模式是否存在
    actual_modes = [display.display_mode.itemText(i) 
                   for i in range(display.display_mode.count())]
    assert actual_modes == expected_modes
    
    # 测试初始模式
    assert display.display_mode.currentIndex() == 0
    assert display.display_mode.currentText() == expected_modes[0]

def test_image_display_modes(qapp):
    """测试图像显示模式"""
    display = ImageDisplay()
    
    # 测试所有显示模式
    expected_modes = [
        "原始图像",
        "单角度彩色",
        "单角度灰度",
        "彩色图像",
        "灰度图像",
        "四角度彩色",
        "四角度灰度",
        "偏振度图像"
    ]
    actual_modes = [display.display_mode.itemText(i) 
                   for i in range(display.display_mode.count())]
    assert actual_modes == expected_modes

def test_image_display_resize(qapp):
    """测试图像显示区域大小调整"""
    display = ImageDisplay()
    
    # 创建测试图像
    test_image = np.zeros((100, 100, 3), dtype=np.uint8)
    test_image[25:75, 25:75] = [100, 150, 200]
    
    # 显示图像并调整大小
    display.show_image(test_image)
    display.resize(800, 600)
    
    # 验证图像标签大小
    assert display.image_label.width() <= 800
    assert display.image_label.height() <= 600

@pytest.mark.parametrize("button_name", ["capture_btn", "stream_btn"])
def test_camera_control_buttons(qapp, button_name):
    control = CameraControl()
    button = getattr(control, button_name)
    
    # 测试按钮状态变化
    control.set_connected(True)
    assert button.isEnabled()
    
    # 测试点击事件
    clicked = False
    def on_click():
        nonlocal clicked
        clicked = True
    button.clicked.connect(on_click)
    button.click()
    assert clicked

def test_status_bar(main_window):
    """测试状态栏功能"""
    # 测试初始状态
    assert main_window.status_label.text() == "就绪"
    assert not main_window.status_indicator.isEnabled()
    assert main_window.camera_info.text() == ""
    assert not main_window.status_indicator.isStatus()  # 检查指示灯状态
    
    # 连接成功状态
    mock_camera = MagicMock()
    mock_camera.connect.return_value = (True, "")
    main_window.camera = mock_camera
    
    # 模拟相机连接
    main_window.handle_connect(True)
    assert main_window.status_indicator.isEnabled()
    assert main_window.status_indicator.isStatus()
    assert "相机已连接" in main_window.status_label.text()
    
    # 测试断开连接
    main_window.handle_connect(False)
    assert not main_window.status_indicator.isEnabled()
    assert not main_window.status_indicator.isStatus()
    assert main_window.status_label.text() == "就绪"

def test_style_application(qapp):
    """测试样式应用"""
    window = MainWindow()
    
    # 测试按钮样式
    assert window.camera_control.connect_btn.font().pointSize() == Styles.FONT_MEDIUM
    assert window.camera_control.connect_btn.minimumHeight() == Styles.HEIGHT_MEDIUM
    
    # 测试下拉框样式
    assert window.image_display.display_mode.font().pointSize() == Styles.FONT_MEDIUM
    assert window.image_display.display_mode.minimumHeight() == Styles.HEIGHT_MEDIUM

def test_gui_error_handling(main_window):
    """测试GUI错误处理"""
    # 测试未连接相机时的错误处理
    main_window.handle_capture()  # 应该显示错误消息而不是崩溃
    
    # 测试无效的显示模式
    main_window.image_display.display_mode.setCurrentIndex(0)
    main_window.process_and_display_frame(None)  # 应该优雅地处理空帧
