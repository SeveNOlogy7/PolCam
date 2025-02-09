import pytest
from qtpy.QtCore import Qt
from polcam.gui.main_window import MainWindow
from polcam.gui.camera_control import CameraControl
from polcam.gui.image_display import ImageDisplay

def test_main_window(qapp):
    window = MainWindow()
    assert isinstance(window.camera_control, CameraControl)
    assert isinstance(window.image_display, ImageDisplay)

def test_camera_control(qapp):
    control = CameraControl()
    
    # 测试初始状态
    assert not control.capture_btn.isEnabled()
    assert not control.stream_btn.isEnabled()
    
    # 测试连接状态改变
    control.set_connected(True)
    assert control.capture_btn.isEnabled()
    assert control.stream_btn.isEnabled()

def test_image_display(qapp):
    display = ImageDisplay()
    
    # 测试显示模式
    assert display.display_mode.count() == 5
    assert display.display_mode.currentIndex() == 0
