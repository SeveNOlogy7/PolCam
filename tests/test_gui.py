"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

import pytest
from qtpy.QtCore import Qt, QSize
from qtpy import QtWidgets
from qtpy.QtWidgets import QApplication
from unittest.mock import MagicMock, patch
from polcam.gui.main_window import MainWindow
from polcam.gui.camera_control import CameraControl
from polcam.gui.image_display import ImageDisplay
from polcam.gui.widgets.tool_bar import ToolBar
from polcam.gui.styles import Styles
from polcam.core.processing_module import ProcessingMode, ProcessingResult
from polcam.core.toolbar_controller import ToolbarController
import numpy as np


class DummySettingsService:
    def __init__(self, directory: str):
        self.directory = directory

    def get_last_directory(self):
        return self.directory

    def set_last_directory(self, directory: str):
        self.directory = directory


class DummyMainWindow(QtWidgets.QMainWindow):
    def __init__(self, directory: str):
        super().__init__()
        self.toolbar = ToolBar(self)
        self.settings_service = DummySettingsService(directory)
        self.status_label = QtWidgets.QLabel("就绪")

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

def test_image_display_software_zoom_persists_across_refresh_and_resize(qapp):
    """测试静态图像的软件缩放在刷新和调整尺寸后保持不变。"""
    display = ImageDisplay()
    test_image = np.zeros((120, 160, 3), dtype=np.uint8)

    display.show_image(test_image)
    assert not display.is_software_zoom_active()

    assert display.apply_software_zoom_click(80, 60, 'zoom_in')
    zoomed_roi = display._get_current_view_roi()

    display.refresh_current_image()
    assert display._get_current_view_roi() == zoomed_roi

    display.resize(900, 700)
    assert display._get_current_view_roi() == zoomed_roi

    assert display.reset_software_view()
    assert not display.is_software_zoom_active()

def test_image_display_cropped_canvas_is_contiguous(qapp):
    """测试软件缩放后的显示画布使用连续内存。"""
    display = ImageDisplay()
    test_image = np.zeros((120, 160, 3), dtype=np.uint8)

    display.show_image(test_image)
    assert display.apply_software_zoom_click(80, 60, 'zoom_in')

    cropped = display._compose_current_view_canvas()
    assert cropped.flags['C_CONTIGUOUS']


def test_image_display_software_zoom_respects_configured_max_zoom(qapp):
    """测试静态软件缩放遵守可配置的最大放大倍率。"""
    display = ImageDisplay()
    display.set_max_zoom(4.0)
    test_image = np.zeros((100, 100, 3), dtype=np.uint8)

    display.show_image(test_image)
    assert display.apply_software_zoom_area(40, 40, 5, 5)

    assert display.get_software_zoom_ratio() == pytest.approx(4.0, rel=0.05)

def test_image_display_quad_software_zoom_preserves_quad_layout(qapp):
    """测试静态四分图缩放时保持四分图布局，只缩放子图 ROI。"""
    display = ImageDisplay()
    images = [np.full((80, 80), fill_value=index, dtype=np.uint8) for index in range(4)]

    display.set_processing_mode(ProcessingMode.QUAD_GRAY)
    display.show_quad_view(images, gray=True)
    full_canvas = display._compose_current_view_canvas()
    assert full_canvas.shape[:2] == (160, 160)

    assert display.apply_software_zoom_click(40, 40, 'zoom_in')

    zoomed_canvas = display._compose_current_view_canvas()
    assert display.is_quad_view_mode()
    assert display.quad_size == (53, 53)
    assert zoomed_canvas.shape[:2] == (106, 106)
    assert len(display.quad_positions) == 4

def test_image_display_static_quad_zoom_maps_rendered_quad_center_to_view_roi_center(qapp):
    """测试静态四分图软件缩放后，左上子图中心映射回当前 view_roi 中心。"""
    display = ImageDisplay()
    images = [np.full((80, 80), fill_value=index, dtype=np.uint8) for index in range(4)]

    display.resize(800, 600)
    display.set_processing_mode(ProcessingMode.QUAD_GRAY)
    display.show_quad_view(images, gray=True)
    display.show()
    qapp.processEvents()

    assert display.apply_software_zoom_click(40, 40, 'zoom_in')

    rendered_canvas = display._compose_current_view_canvas()
    geom = display._get_display_geometry()
    view_roi = display._get_current_view_roi()

    assert rendered_canvas is not None
    assert geom is not None
    assert view_roi is not None

    x_offset, y_offset, display_width, display_height = geom
    canvas_h, canvas_w = rendered_canvas.shape[:2]
    quad_y, quad_x = display.quad_positions[0]
    quad_h, quad_w = display.quad_size

    display_x = int(x_offset + (quad_x + quad_w / 2) * display_width / canvas_w)
    display_y = int(y_offset + (quad_y + quad_h / 2) * display_height / canvas_h)

    source_x, source_y = display._display_to_source_coords(display_x, display_y)
    view_x, view_y, view_w, view_h = view_roi

    expected_x = int(view_x + view_w / 2)
    expected_y = int(view_y + view_h / 2)

    assert abs(source_x - expected_x) <= 1
    assert abs(source_y - expected_y) <= 1

def test_image_display_resize_does_not_crash_with_single_image_in_quad_mode(qapp):
    """测试四分图模式下只有单图缓存时，resize 刷新不会触发四分图重组异常。"""
    display = ImageDisplay()
    image = np.zeros((120, 160, 3), dtype=np.uint8)

    display.show_image(image)
    display.set_processing_mode(ProcessingMode.QUAD_GRAY)

    display.resize(900, 700)
    display.refresh_current_image()

    assert display.image_label.pixmap() is not None
    assert display.quad_size is None
    assert display.quad_positions == []


def test_image_display_quad_title_overlays_follow_quad_layout(qapp):
    display = ImageDisplay()
    images = [np.zeros((80, 80, 3), dtype=np.uint8) for _ in range(4)]

    display.resize(800, 600)
    display.show()
    qapp.processEvents()

    display.set_processing_mode(ProcessingMode.QUAD_COLOR)
    display.show_quad_view(images)
    qapp.processEvents()

    visible_labels = [label for label in display._quad_title_labels if label.isVisible()]
    assert [label.text() for label in visible_labels] == ['0 deg', '45 deg', '90 deg', '135 deg']

    top_left = display._quad_title_labels[0].pos()
    top_right = display._quad_title_labels[1].pos()
    bottom_left = display._quad_title_labels[2].pos()
    assert top_right.x() > top_left.x()
    assert bottom_left.y() > top_left.y()

    display.show_image(images[0])
    qapp.processEvents()

    assert not any(label.isVisible() for label in display._quad_title_labels)


def test_toolbar_controller_exports_quad_composite_with_titles(qapp, tmp_path):
    main_window = DummyMainWindow(str(tmp_path))
    controller = ToolbarController(main_window)
    controller.initialize()

    images = [np.full((16, 16, 3), fill_value=index * 20, dtype=np.uint8) for index in range(4)]
    controller.update_last_result(
        ProcessingResult(
            mode=ProcessingMode.QUAD_COLOR,
            images=images,
            metadata={'wb_enabled': False},
            timestamp=0.0,
        )
    )

    saved_files = []

    def fake_imwrite(filename, image):
        saved_files.append((filename, image.shape))
        return True

    with patch.object(controller, '_get_save_filename', return_value=(str(tmp_path / 'result'), '.png', True)), \
         patch('polcam.core.toolbar_controller.cv2.imwrite', side_effect=fake_imwrite), \
         patch('polcam.core.toolbar_controller.QtWidgets.QMessageBox.information'):
        controller._handle_save_result()

    file_names = [str(path) for path, _ in saved_files]
    assert any(name.endswith('result_COLOR_0.png') for name in file_names)
    assert any(name.endswith('result_COLOR_45.png') for name in file_names)
    assert any(name.endswith('result_COLOR_90.png') for name in file_names)
    assert any(name.endswith('result_COLOR_135.png') for name in file_names)
    assert any(name.endswith('result_COLOR_QUAD_COMPOSITE.png') for name in file_names)

    composite_shapes = [shape for path, shape in saved_files if str(path).endswith('result_COLOR_QUAD_COMPOSITE.png')]
    assert composite_shapes == [(32, 32, 3)]


def test_toolbar_controller_exports_polarization_composite_with_titles(qapp, tmp_path):
    main_window = DummyMainWindow(str(tmp_path))
    controller = ToolbarController(main_window)
    controller.initialize()

    merged = np.full((16, 16, 3), fill_value=64, dtype=np.uint8)
    dolp = np.full((16, 16), fill_value=32, dtype=np.uint8)
    aolp = np.full((16, 16), fill_value=96, dtype=np.uint8)
    docp = np.full((16, 16), fill_value=128, dtype=np.uint8)
    controller.update_last_result(
        ProcessingResult(
            mode=ProcessingMode.POLARIZATION,
            images=[merged, dolp, aolp, docp],
            metadata={'is_color': False, 'pol_wb_enabled': False},
            timestamp=0.0,
        )
    )

    saved_files = []
    saved_arrays = []

    def fake_imwrite(filename, image):
        saved_files.append((filename, image.shape))
        return True

    def fake_save(filename, data, allow_pickle=True):
        saved_arrays.append((filename, sorted(data.keys()), allow_pickle))

    with patch.object(controller, '_get_save_filename', return_value=(str(tmp_path / 'pol_result'), '.png', True)), \
         patch('polcam.core.toolbar_controller.cv2.imwrite', side_effect=fake_imwrite), \
         patch('polcam.core.toolbar_controller.np.save', side_effect=fake_save), \
         patch('polcam.core.toolbar_controller.QtWidgets.QMessageBox.information'):
        controller._handle_save_result()

    file_names = [str(path) for path, _ in saved_files]
    assert any(name.endswith('pol_result_MERGED_GRAY.png') for name in file_names)
    assert any(name.endswith('pol_result_DOLP.png') for name in file_names)
    assert any(name.endswith('pol_result_AOLP.png') for name in file_names)
    assert any(name.endswith('pol_result_DOCP.png') for name in file_names)
    assert any(name.endswith('pol_result_POLARIZATION_QUAD_COMPOSITE.png') for name in file_names)

    composite_shapes = [shape for path, shape in saved_files if str(path).endswith('pol_result_POLARIZATION_QUAD_COMPOSITE.png')]
    assert composite_shapes == [(32, 32, 3)]

    assert saved_arrays == [
        (str(tmp_path / 'pol_result_POL.npy'), ['aolp', 'docp', 'dolp'], True)
    ]

def test_image_toolbar_controller_uses_software_zoom_for_static_image(qapp):
    """测试非连续采集时工具栏缩放走显示层软件缩放而非相机 ROI。"""
    display = ImageDisplay()
    display.show_image(np.zeros((100, 100, 3), dtype=np.uint8))

    mock_camera = MagicMock()
    mock_camera.is_connected.return_value = True
    mock_camera.is_streaming.return_value = False
    display.toolbar_controller.set_camera_module(mock_camera)

    with patch.object(display, 'apply_software_zoom_click', wraps=display.apply_software_zoom_click) as software_zoom:
        display.toolbar_controller._handle_zoom_in(True)
        display.toolbar_controller._handle_zoom_click(50, 50)

    software_zoom.assert_called_once_with(50, 50, 'zoom_in', zoom_factor=display.toolbar_controller.ZOOM_FACTOR)
    mock_camera.set_roi.assert_not_called()


def test_image_toolbar_controller_max_zoom_defaults_to_1000(qapp):
    """测试图像工具栏默认最大放大倍率为 1000x。"""
    display = ImageDisplay()

    assert display.toolbar_controller.get_max_zoom() == 1000.0
    assert display.get_max_zoom() == 1000.0


def test_image_toolbar_controller_hardware_zoom_respects_configured_max_zoom(qapp):
    """测试连续采集硬件 ROI 路径也受最大放大倍率约束。"""
    display = ImageDisplay()
    display.toolbar_controller.set_max_zoom(1000.0)

    mock_camera = MagicMock()
    mock_camera.is_connected.return_value = True
    mock_camera.is_streaming.return_value = True
    mock_camera.get_roi.return_value = (0, 0, 10, 10)
    mock_camera.get_sensor_size.return_value = (1000, 1000)
    mock_camera.set_roi.return_value = True
    mock_camera.get_roi.side_effect = [
        (0, 0, 10, 10),
        (0, 0, 31, 31),
        (0, 0, 31, 31),
    ]
    display.toolbar_controller.set_camera_module(mock_camera)

    display.toolbar_controller._handle_zoom_in(True)
    display.toolbar_controller._handle_zoom_click(5, 5)

    mock_camera.set_roi.assert_called_once()
    _, _, new_w, new_h = mock_camera.set_roi.call_args.args
    assert new_w == 31
    assert new_h == 31

def test_image_toolbar_controller_reset_view_uses_software_path_for_static_image(qapp):
    """测试静态图像重置视图不会修改相机 ROI。"""
    display = ImageDisplay()
    display.show_image(np.zeros((120, 160, 3), dtype=np.uint8))
    display.apply_software_zoom_click(60, 40, 'zoom_in')

    mock_camera = MagicMock()
    mock_camera.is_connected.return_value = True
    mock_camera.is_streaming.return_value = False
    display.toolbar_controller.set_camera_module(mock_camera)

    display.toolbar_controller._handle_reset_view()

    assert not display.is_software_zoom_active()
    mock_camera.reset_roi.assert_not_called()

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
