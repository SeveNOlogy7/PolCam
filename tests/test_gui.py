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

def test_image_display_interaction(qapp):
    display = ImageDisplay()
    
    # 测试切换显示模式
    display.display_mode.setCurrentIndex(1)
    expected_modes = ['原始图像', '单角度彩色', '单角度灰度', '四角度视图', '偏振度图像']
    assert display.display_mode.currentText() in expected_modes

def test_display_mode_items(qapp):
    display = ImageDisplay()
    expected_modes = ['原始图像', '单角度彩色', '单角度灰度', '四角度视图', '偏振度图像']
    
    # 测试所有显示模式是否存在
    actual_modes = [display.display_mode.itemText(i) 
                   for i in range(display.display_mode.count())]
    assert actual_modes == expected_modes
    
    # 测试初始模式
    assert display.display_mode.currentIndex() == 0
    assert display.display_mode.currentText() == expected_modes[0]

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
