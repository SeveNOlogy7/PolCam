"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

import os
import pytest
import subprocess
import sys
import threading
import time
from qtpy import QtCore, QtGui
from qtpy.QtCore import Qt, QSize
from qtpy.QtWidgets import QApplication
from unittest.mock import MagicMock, patch
from polcam.gui.main_window import MainWindow
from polcam.gui.camera_control import CameraControl
from polcam.gui.image_display import ImageDisplay
from polcam.gui.styles import Styles
from polcam.core.image_plotter import ImagePlotter
from polcam.core.events import Event, EventManager, EventType
from polcam.core.processing_module import ProcessingMode
import numpy as np

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
    control.exposure_control.value_spin.setValue(5000)
    assert control.exposure_control.value_spin.value() == 5000
    
    # 测试增益控制
    control.gain_control.value_spin.setValue(10)
    assert control.gain_control.value_spin.value() == 10
    
    # 测试自动模式切换
    control.exposure_control.auto_check.setChecked(True)
    assert control.exposure_control.value_spin.isReadOnly()
    assert not control.exposure_control.once_btn.isEnabled()
    
    control.gain_control.auto_check.setChecked(True)
    assert control.gain_control.value_spin.isReadOnly()
    assert not control.gain_control.once_btn.isEnabled()

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
        (0, 0, 32, 32),
        (0, 0, 32, 32),
    ]
    display.toolbar_controller.set_camera_module(mock_camera)

    display.toolbar_controller._handle_zoom_in(True)
    display.toolbar_controller._handle_zoom_click(5, 5)

    mock_camera.set_roi.assert_called_once()
    _, _, new_w, new_h = mock_camera.set_roi.call_args.args
    assert new_w == new_h == 32
    # 1000x1000 / 32² 才落回 1000x 以内；曾经断言的 31 对应 1040x，
    # 正好是这个用例名字说要防住的越界
    assert (1000 * 1000) / (new_w * new_h) <= 1000.0

def test_image_toolbar_controller_reset_view_uses_software_path_for_static_image(qapp):
    """测试静态图像重置视图不会修改相机 ROI。"""
    display = ImageDisplay()
    display.show_image(np.zeros((120, 160, 3), dtype=np.uint8))
    display.apply_software_zoom_click(60, 40, 'zoom_in')

    mock_camera = MagicMock()
    mock_camera.is_connected.return_value = True
    mock_camera.is_streaming.return_value = False
    # 复原要不要碰相机，取决于 ROI 是否还被裁着；这里给一个满幅 ROI 表示“没裁”
    mock_camera.get_roi.return_value = (0, 0, 1600, 1200)
    mock_camera.get_sensor_size.return_value = (1600, 1200)
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
    assert not main_window.status_indicator._status
    
    # 连接成功状态
    mock_camera = MagicMock()
    mock_camera.connect.return_value = (True, "")
    main_window.camera = mock_camera
    
    # 模拟相机连接
    main_window.handle_connect(True)
    assert main_window.status_indicator.isEnabled()
    assert main_window.status_indicator._status
    assert "相机已连接" in main_window.status_label.text()
    
    # 测试断开连接
    main_window.handle_connect(False)
    assert not main_window.status_indicator.isEnabled()
    assert not main_window.status_indicator._status
    assert main_window.status_label.text() == "就绪"

def test_style_application(main_window):
    """测试样式应用"""
    # 测试按钮样式
    assert main_window.camera_control.connect_btn.font().pointSize() == Styles.FONT_MEDIUM
    assert main_window.camera_control.connect_btn.minimumHeight() == Styles.HEIGHT_MEDIUM
    
    # 测试下拉框样式
    assert main_window.image_display.display_mode.font().pointSize() == Styles.FONT_MEDIUM
    assert main_window.image_display.display_mode.minimumHeight() == Styles.HEIGHT_MEDIUM


def test_main_window_dispatches_gui_events_on_main_thread(main_window, qapp):
    """测试后台线程发出的 GUI 事件会排队切回主线程执行。"""

    class EventThreadRecorder(QtCore.QObject):
        def __init__(self):
            super().__init__()
            self.gui_thread = None
            self.python_thread_id = None

        def record(self, _event):
            self.gui_thread = QtCore.QThread.currentThread()
            self.python_thread_id = threading.get_ident()

    recorder = EventThreadRecorder()
    main_window._event_bridge.dispatch_event.connect(
        recorder.record,
        QtCore.Qt.ConnectionType.QueuedConnection,
    )

    def emit_from_worker():
        main_window._event_bridge.dispatch_event.emit(
            Event(EventType.STATUS_MESSAGE_UPDATE, {"message": "后台线程消息"})
        )

    worker = threading.Thread(target=emit_from_worker)
    worker.start()
    worker.join()

    deadline = time.time() + 1.0
    while time.time() < deadline:
        qapp.processEvents()
        if main_window.status_label.text() == "后台线程消息" and recorder.gui_thread is not None:
            break
        time.sleep(0.01)

    assert main_window.status_label.text() == "后台线程消息"
    assert recorder.gui_thread == qapp.thread()
    assert recorder.python_thread_id == threading.main_thread().ident


def test_show_polarization_quad_view_reuses_precolored_canvas(qapp):
    """测试预计算偏振画布时不会在主线程重复做伪彩映射。"""
    display = ImageDisplay()
    image = np.zeros((40, 40, 3), dtype=np.uint8)
    scalar = np.zeros((40, 40), dtype=np.float32)
    precolored = [np.zeros((40, 40, 3), dtype=np.uint8) for _ in range(4)]
    canvas = np.zeros((80, 80, 3), dtype=np.uint8)

    with patch('polcam.gui.image_display.ImageProcessor.colormap_polarization') as colormap:
        display.show_polarization_quad_view(
            image,
            scalar,
            scalar,
            scalar,
            precolored=precolored,
            canvas=canvas,
        )

    colormap.assert_not_called()
    assert display.quad_size == (40, 40)
    assert len(display.quad_positions) == 4


def test_show_quad_view_reuses_prebuilt_canvas(qapp):
    """测试预计算四分图画布时主线程不会重新组装画布。"""
    display = ImageDisplay()
    images = [np.zeros((30, 30), dtype=np.uint8) for _ in range(4)]
    canvas = np.zeros((60, 60, 3), dtype=np.uint8)

    with patch('polcam.gui.image_display.ImagePlotter.create_quad_canvas') as create_canvas:
        display.show_quad_view(images, gray=True, canvas=canvas)

    create_canvas.assert_not_called()
    assert display.quad_size == (30, 30)
    assert len(display.quad_positions) == 4


def test_resize_refresh_reuses_cached_quad_canvas_without_software_zoom(qapp):
    """测试四分图在无软件缩放时 resize 只重缩放当前画布，不重新组装。"""
    display = ImageDisplay()
    images = [np.full((80, 80), fill_value=index, dtype=np.uint8) for index in range(4)]

    display.set_processing_mode(ProcessingMode.QUAD_GRAY)
    display.show_quad_view(images, gray=True)

    with patch.object(display, '_compose_current_view_canvas', side_effect=AssertionError('should not recompose')), \
         patch.object(display, '_render_canvas', wraps=display._render_canvas) as render_canvas:
        display._refresh_after_resize()

    render_canvas.assert_called_once_with(display._current_canvas)


def test_quad_cursor_overlay_does_not_rerender_canvas_on_mouse_move(qapp):
    """测试四分图游标移动时不再重绘整张画布。"""
    display = ImageDisplay()
    images = [np.full((80, 80), fill_value=index, dtype=np.uint8) for index in range(4)]

    display.resize(800, 600)
    display.set_processing_mode(ProcessingMode.QUAD_GRAY)
    display.show_quad_view(images, gray=True)
    display.show()
    qapp.processEvents()
    display.set_cursor_mode(True)

    geom = display._get_display_geometry()
    assert geom is not None
    x_offset, y_offset, display_width, display_height = geom
    event_x = int(x_offset + display_width * 0.25)
    event_y = int(y_offset + display_height * 0.25)
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove,
        QtCore.QPointF(event_x, event_y),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )

    with patch.object(display, '_render_canvas') as render_canvas:
        display._on_mouse_move(event)

    render_canvas.assert_not_called()
    assert display.cursor_info is not None
    assert display._cursor_overlay.isVisible()


def test_quad_roi_mapping_uses_cached_render_shape(qapp):
    """测试四分图交互坐标映射使用缓存尺寸而不是重组画布。"""
    display = ImageDisplay()
    images = [np.full((80, 80), fill_value=index, dtype=np.uint8) for index in range(4)]

    display.resize(800, 600)
    display.set_processing_mode(ProcessingMode.QUAD_GRAY)
    display.show_quad_view(images, gray=True)
    display.show()
    qapp.processEvents()

    geom = display._get_display_geometry()
    assert geom is not None
    x_offset, y_offset, display_width, display_height = geom
    event_x = int(x_offset + display_width * 0.25)
    event_y = int(y_offset + display_height * 0.25)

    with patch.object(display, '_compose_current_view_canvas', side_effect=AssertionError('should not recompose')):
        source_coords = display._display_to_source_coords(event_x, event_y)
        render_coords = display._display_to_render_canvas_coords(event_x, event_y)
        quad_rect = display._get_quad_display_rect(event_x, event_y)

    assert source_coords is not None
    assert render_coords is not None
    assert quad_rect is not None


@pytest.mark.parametrize(
    ('height', 'width', 'expected_factor', 'expected_quad_size'),
    [
        (3000, 16, 2, (1500, 8)),
        (5000, 16, 4, (1250, 4)),
    ],
)
def test_create_quad_canvas_downsamples_large_tiles_for_display(height, width, expected_factor, expected_quad_size):
    """测试超大四分图分块会按 1/2 或 1/4 进行显示降采样。"""
    images = [np.zeros((height, width, 3), dtype=np.uint8) for _ in range(4)]

    factor = ImagePlotter.get_quad_downsample_factor(images[0].shape, ImagePlotter.MAX_DISPLAY_QUAD_TILE_SIZE)
    canvas, _, quad_size = ImagePlotter.create_quad_canvas(
        images,
        ['0 deg', '45 deg', '90 deg', '135 deg'],
        draw_titles=False,
        max_tile_size=ImagePlotter.MAX_DISPLAY_QUAD_TILE_SIZE,
    )

    assert factor == expected_factor
    assert quad_size == expected_quad_size
    assert canvas.shape[:2] == (expected_quad_size[0] * 2, expected_quad_size[1] * 2)


def test_large_canvas_uses_fast_scaling_mode(qapp):
    """测试大图刷新使用更轻的快速缩放模式。"""
    display = ImageDisplay()

    mode = display._get_scaling_transformation_mode((2048, 2448))

    assert mode == QtCore.Qt.FastTransformation


def test_small_canvas_keeps_smooth_scaling_mode(qapp):
    """测试普通尺寸图像仍使用平滑缩放。"""
    display = ImageDisplay()

    mode = display._get_scaling_transformation_mode((800, 800))

    assert mode == QtCore.Qt.SmoothTransformation


@pytest.mark.skipif(getattr(QtGui.QImage, 'Format_BGR888', None) is None, reason='Qt backend does not expose Format_BGR888')
def test_show_canvas_skips_bgr_to_rgb_conversion_when_direct_bgr_supported(qapp):
    """测试支持 BGR888 时不再调用 cvtColor 做整图颜色转换。"""
    display = ImageDisplay()
    image = np.zeros((64, 64, 3), dtype=np.uint8)

    with patch('polcam.gui.image_display.cv2.cvtColor', side_effect=AssertionError('cvtColor should not be called')):
        display._show_canvas(image)

    assert display.image_label.pixmap() is not None

def test_gui_error_handling(main_window):
    """测试GUI错误处理"""
    # 测试未连接相机时的错误处理（断言弹框，而不是真的弹出模态框阻塞测试）
    with patch('polcam.gui.main_window.QtWidgets.QMessageBox.warning') as mock_warning:
        main_window.handle_capture()  # 应该显示错误消息而不是崩溃
        assert mock_warning.called
        assert "相机未连接" in mock_warning.call_args[0][2]

    # 测试无效的显示模式
    main_window.image_display.display_mode.setCurrentIndex(0)
    main_window._update_frame_and_display(None)  # 应该优雅地处理空帧


def test_frame_captured_does_not_auto_save_after_continuous_capture_stops(main_window):
    """测试停止连续采集后的尾帧不会被误当作单帧自动保存。"""
    frame = np.zeros((8, 8), dtype=np.uint8)
    main_window._continuous_mode = False
    main_window._single_capture_requested = False

    with patch.object(main_window, '_auto_save_captured_frame') as auto_save:
        main_window._on_frame_captured(Event(EventType.FRAME_CAPTURED, {
            'frame': frame,
            'capture_time': 0.01,
            'timestamp': 123.0,
        }))

    auto_save.assert_not_called()


def test_frame_captured_auto_saves_only_for_explicit_single_capture(main_window):
    """测试只有显式单帧采集完成时才会自动保存一次。"""
    frame = np.zeros((8, 8), dtype=np.uint8)
    main_window._continuous_mode = False
    main_window._single_capture_requested = True

    with patch.object(main_window, '_auto_save_captured_frame') as auto_save:
        main_window._on_frame_captured(Event(EventType.FRAME_CAPTURED, {
            'frame': frame,
            'capture_time': 0.01,
            'timestamp': 456.0,
        }))

    auto_save.assert_called_once_with(frame, 456.0)
    assert main_window._single_capture_requested is False


def test_continuous_capture_throttles_nonessential_ui_updates(main_window):
    """测试连续采集时跳过高频工具栏和状态刷新热路径。"""
    frame = np.zeros((8, 8), dtype=np.uint8)
    main_window._continuous_mode = True

    with patch.object(main_window, '_should_refresh_continuous_ui', side_effect=[False, False]) as should_refresh, \
         patch.object(main_window, '_update_capture_time') as update_capture_time, \
         patch.object(main_window, '_update_auto_parameters') as update_auto_parameters, \
         patch.object(main_window.toolbar_controller, 'update_current_frame') as update_current_frame, \
         patch.object(main_window.toolbar_controller, 'enable_save_raw') as enable_save_raw:
        main_window._on_frame_captured(Event(EventType.FRAME_CAPTURED, {
            'frame': frame,
            'capture_time': 0.01,
            'timestamp': 789.0,
        }))

    assert should_refresh.call_count == 2
    update_capture_time.assert_not_called()
    update_auto_parameters.assert_not_called()
    update_current_frame.assert_not_called()
    enable_save_raw.assert_not_called()


def test_stop_streaming_updates_toolbar_with_latest_frame(main_window):
    """测试停止连续采集后会同步最新帧到工具栏缓存。"""
    frame = np.zeros((8, 8), dtype=np.uint8)
    main_window.current_frame = frame
    main_window._current_frame_timestamp = 123.0
    main_window._continuous_mode = True

    with patch.object(main_window.camera, 'stop_streaming') as stop_streaming, \
         patch.object(main_window.processor, 'cancel_all_tasks') as cancel_all_tasks, \
         patch.object(main_window.toolbar_controller, 'update_current_frame') as update_current_frame, \
         patch.object(main_window.toolbar_controller, 'enable_save_raw') as enable_save_raw, \
         patch.object(main_window.image_display.toolbar_controller, 'sync_zoom_coordinate_space'):
        main_window.handle_stream(False)

    stop_streaming.assert_called_once()
    cancel_all_tasks.assert_called_once()
    update_current_frame.assert_called_once_with(frame, 123.0)
    enable_save_raw.assert_called_once_with(True)

def test_one_shot_complete_releases_the_wb_button(qapp):
    """一次性白平衡做完后要把白平衡控件恢复成可用。

    这里写的是 wb_control.once_button，而 WhiteBalance 里的控件叫 once_btn，所以
    wb 分支一走到就 AttributeError。（目前没有调用方：单次白平衡在相机侧还没实现。）
    """
    control = CameraControl()
    control.wb_control.set_enabled(False)
    assert not control.wb_control.auto_check.isEnabled()

    control.handle_one_shot_complete('wb')

    assert control.wb_control.auto_check.isEnabled()
    assert control.wb_control.once_btn.isEnabled()

def test_visibility_setters_tolerate_a_parentless_widget(qapp):
    """没有父控件时设置可见性不该炸。

    set_pol_controls_visible 判了 parentWidget() 是否存在，另外两个 setter 没判。
    """
    control = CameraControl()

    control.set_wb_controls_visible(True)
    control.set_angle_controls_visible(True)

def test_one_shot_exposure_restores_the_manual_control(main_window):
    """单次自动曝光：期间禁用手动滑块，SDK 报回结果时恢复。

    handle_one_shot_auto / handle_one_shot_complete 之前没有任何调用方，
    所以按下去只有一段静默的阻塞式轮询，界面上毫无反馈。
    """
    main_window.camera = MagicMock()
    exposure = main_window.camera_control.exposure_control
    assert exposure.value_spin.isEnabled()

    exposure.once_clicked.emit()
    assert not exposure.value_spin.isEnabled(), "单次自动曝光期间没有禁用手动控件"

    main_window._on_parameter_changed(
        Event(EventType.PARAMETER_CHANGED, {"parameter": "exposure", "value": 4321.0}))
    assert exposure.value_spin.isEnabled(), "单次完成后没有恢复手动控件"

def test_one_shot_gain_restores_the_manual_control(main_window):
    """增益的那半程和曝光一样要接上。"""
    main_window.camera = MagicMock()
    gain = main_window.camera_control.gain_control
    assert gain.value_spin.isEnabled()

    gain.once_clicked.emit()
    assert not gain.value_spin.isEnabled(), "单次自动增益期间没有禁用手动控件"

    main_window._on_parameter_changed(
        Event(EventType.PARAMETER_CHANGED, {"parameter": "gain", "value": 3.5}))
    assert gain.value_spin.isEnabled(), "单次完成后没有恢复手动控件"


def test_a_one_shot_worker_does_not_report_into_a_closed_window(qapp):
    """窗口销毁之后，还在轮询硬件的工作线程不该再往它发信号。

    closeEvent 走完、控件树被销毁之后，线程 finally 里那句 emit 就是
    RuntimeError: Signal source has been deleted —— 线程里没人接这个异常，产品里就是
    收尾阶段的 use-after-free。这里不用 main_window fixture：它是在测试体跑完之后才
    销毁窗口的，那样信号早就发完了，测不到这条。
    """
    import shiboken6

    seen = []
    monkeypatch_thread_hook = threading.excepthook
    threading.excepthook = lambda args: seen.append(args.exc_value)
    try:
        release = threading.Event()
        camera = MagicMock()
        camera.set_exposure_once.side_effect = lambda: release.wait(2.0)

        window = MainWindow()
        window.camera = camera
        window.camera_control.exposure_control.once_clicked.emit()

        window.close()
        shiboken6.delete(window)
        del window
        release.set()

        worker = next(t for t in threading.enumerate() if t.name == "PolCam-OneShot-exposure")
        assert _wait_until(lambda: not worker.is_alive()), "工作线程没结束"
        assert seen == [], f"窗口没了之后工作线程还在往它发信号: {seen}"
    finally:
        threading.excepthook = monkeypatch_thread_hook


def test_two_overlapping_one_shots_both_get_restored(main_window):
    """两路单次调整叠在一起时，先发起的那一路也要被恢复。

    _one_shot_pending 只有一个槽位，第二次点击直接把它改成 gain，于是 exposure 的完成
    通知被当成"不是我在等的"丢掉 —— 曝光那组控件从此永久禁用，得断开重连才回来。实测
    两路都上报完成之后：exposure spin/auto/once 全 False，gain 那组全 True。
    """
    release = threading.Event()

    def slow_once():
        release.wait(2.0)

    camera = MagicMock()
    camera.set_exposure_once.side_effect = slow_once
    camera.is_connected.return_value = True
    main_window.camera = camera
    exposure = main_window.camera_control.exposure_control
    gain = main_window.camera_control.gain_control

    exposure.once_clicked.emit()
    gain.once_clicked.emit()
    release.set()

    assert _wait_until(lambda: exposure.value_spin.isEnabled() and gain.value_spin.isEnabled()),\
        "叠加的两次单次调整里，先发起那一路的控件没有恢复"


def test_a_one_shot_landing_after_disconnect_does_not_re_enable(main_window):
    """断开之后才落地的单次调整不能把手动控件又打开。

    handle_one_shot_complete 无条件 set_enabled(True)；断开那一路已经把整组禁用了，
    工作线程晚一步回来就把它们点亮，之后改的值根本写不进硬件（没有 remote feature
    时 set_* 直接 return），面板显示的是相机没收到的数。
    """
    release = threading.Event()

    def slow_once():
        release.wait(2.0)

    camera = MagicMock()
    camera.set_exposure_once.side_effect = slow_once
    camera.is_connected.return_value = True
    main_window.camera = camera
    exposure = main_window.camera_control.exposure_control

    exposure.once_clicked.emit()
    assert not exposure.value_spin.isEnabled()

    camera.is_connected.return_value = False
    main_window.handle_connect(False)                 # 用户点了「断开相机」
    release.set()
    assert _wait_until(
        lambda: not any(t.name == "PolCam-OneShot-exposure" for t in threading.enumerate())),\
        "工作线程没结束"
    # 排队回 GUI 线程的完成信号得有机会落地，否则这条断言什么都没等到
    _wait_until(lambda: exposure.value_spin.isEnabled(), timeout=0.3)

    assert not exposure.value_spin.isEnabled(), "相机已断开，曝光控件却被重新启用了"

def _wait_until(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        QApplication.processEvents()
        time.sleep(0.01)
    return predicate()

def test_one_shot_polling_leaves_the_gui_thread(main_window):
    """单次自动调整的阻塞轮询不能占住 GUI 线程。

    相机侧的 set_*_once 会一直轮询硬件到自动关闭（最长 5 秒），它原先是 once_clicked
    的直接槽函数，那几秒里整个界面是冻住的。
    """
    ran_on = []

    def fake_once():
        ran_on.append(threading.current_thread())
        time.sleep(0.2)

    main_window.camera.set_exposure_once = fake_once

    main_window.camera_control.exposure_control.once_clicked.emit()

    assert _wait_until(lambda: len(ran_on) == 1)
    assert threading.main_thread() not in ran_on

def test_one_shot_restores_the_control_even_without_a_result(main_window):
    """SDK 没给出结果时也要把手动控件放回来。

    超时、相机没连（set_*_once 直接 return）和 SDK 抛错这三条路都不发
    PARAMETER_CHANGED，只靠那个事件恢复会让控件永久禁用。
    """
    def failing_once():
        raise RuntimeError("ExposureAuto 写不进去")

    main_window.camera.set_exposure_once = failing_once
    exposure = main_window.camera_control.exposure_control
    assert exposure.value_spin.isEnabled()

    exposure.once_clicked.emit()
    assert not exposure.value_spin.isEnabled()

    assert _wait_until(lambda: exposure.value_spin.isEnabled()), "单次失败后控件没有恢复"

def test_software_area_zoom_stays_inside_the_canvas(qapp):
    """贴着画布右下角框选，放大窗口不能超出画布。

    apply_software_zoom_area 先把宽高裁到画布边缘，再按最大倍率把窗口放大，但放大
    之后没有重新收原点；存下来的 ROI 越界，读的时候被 _get_current_view_roi 平移回
    画布内 —— 于是显示的是用户没框住的那块。断言存下来的值，不是被修好的那个。
    """
    display = ImageDisplay()
    display.show_image(np.zeros((300, 400, 3), dtype=np.uint8))
    full = display._get_full_view_roi()

    assert display.apply_software_zoom_area(full[2] - 1, full[3] - 1, 1, 1)

    x, y, w, h = display._software_view_roi
    assert x + w <= full[2], f"视图右边界 {x + w} 超出画布宽 {full[2]}"
    assert y + h <= full[3], f"视图下边界 {y + h} 超出画布高 {full[3]}"

def test_software_area_zoom_respects_the_max_zoom_at_the_floor(qapp):
    """为满足最大倍率而放大窗口时，不能因为取整反而超过上限。"""
    display = ImageDisplay()
    max_zoom = 1000.0
    display.set_max_zoom(max_zoom)
    display.show_image(np.zeros((300, 400, 3), dtype=np.uint8))
    full = display._get_full_view_roi()

    assert display.apply_software_zoom_area(full[2] - 1, full[3] - 1, 1, 1)

    _, _, w, h = display._software_view_roi
    ratio = (full[2] * full[3]) / (w * h)
    assert ratio <= max_zoom * 1.001, f"实际倍率 {ratio:.1f}x 超过上限 {max_zoom}x"

def test_reset_view_disarms_the_armed_interaction_modes(qapp):
    """点「复原」要同时退出游标/放大模式，否则按钮弹起了但模式还武装着。

    _on_reset_clicked 只把按钮 setChecked(False)，没有发对应的 *Activated(False) 信号，
    而 _handle_reset_view 也从不清 _zoom_mode/_cursor_mode。
    """
    display = ImageDisplay()
    controller = display.toolbar_controller

    controller._handle_zoom_area(True)
    assert controller._zoom_mode == 'zoom_area'

    controller._handle_reset_view()
    assert controller._zoom_mode is None, "复原后区域放大模式仍然武装"

    controller._handle_cursor_mode(True)
    assert controller._cursor_mode

    controller._handle_reset_view()
    assert not controller._cursor_mode, "复原后游标模式仍然武装"

def test_reset_view_also_restores_a_cropped_camera_roi(qapp):
    """硬件放大留下的 ROI 必须被复原，即使现在走的是软件缩放分支。

    连续采集里放大、停止采集、再点复原：_should_use_software_zoom 已经为真，
    于是只重置了软件视图，相机 ROI 还裁着，状态栏却写着「视图已重置」。
    """
    display = ImageDisplay()
    display.show_image(np.zeros((100, 100, 3), dtype=np.uint8))
    controller = display.toolbar_controller

    camera = MagicMock()
    camera.is_connected.return_value = True
    camera.is_streaming.return_value = False
    camera.get_roi.return_value = (0, 0, 50, 50)
    camera.get_sensor_size.return_value = (100, 100)
    camera.reset_roi.return_value = True
    controller.set_camera_module(camera)

    controller._handle_reset_view()

    assert camera.reset_roi.called, "相机 ROI 仍是裁剪状态，没有被复原"

def test_failed_streaming_start_leaves_the_ui_out_of_capture_mode(main_window):
    """开始连续采集失败时不能谎报「连续采集中」。

    start_streaming() 以前不告诉调用方成败（没设备直接 return，异常也只写日志），
    而 handle_stream 在它后面无条件把按钮文字、状态灯和 _continuous_mode 都设成采集中。
    """
    camera = MagicMock()
    camera.start_streaming.return_value = False
    camera.is_connected.return_value = True
    main_window.camera = camera
    stream_btn = main_window.camera_control.stream_btn

    main_window.handle_stream(True)

    assert not main_window._continuous_mode, "启动失败却进入了连续采集模式"
    assert stream_btn.text() != "停止采集"
    assert not stream_btn.isChecked()

def test_processed_result_is_filed_under_its_own_frame_timestamp(main_window):
    """保存处理结果用的时间戳必须来自产生它的那一帧。

    _on_frame_processed 以前读的是可变的 self._current_frame_timestamp；处理耗时超过
    一帧间隔时那里已经是下一帧的时间，于是存出来的文件名对不上内容。
    """
    from datetime import datetime

    own = datetime(2026, 9, 26, 11, 59, 0)
    newer = datetime(2026, 9, 26, 12, 0, 1)
    frame = np.linspace(0, 200, 16 * 16, dtype=np.uint8).reshape(16, 16)

    main_window.processor.process_frame(frame, capture_timestamp=own)
    # 这一帧还在处理时，下一帧的采集时间已经落到实时值上
    main_window._current_frame_timestamp = newer

    assert _wait_until(
        lambda: main_window.toolbar_controller._last_result_timestamp is not None)
    assert main_window.toolbar_controller._last_result_timestamp == own


def test_closing_main_window_unsubscribes_its_bus_callbacks(qapp):
    """关窗要把它挂在事件总线上的订阅摘干净。

    EventManager 是单例，活得比窗口长，订阅留着就会把 _MainThreadEventBridge 一直
    挂在进程上。实测三个窗口建完关掉，总线上从 0 涨到 36 且不回落。
    """
    window = MainWindow()
    bus = EventManager()
    handler = window._event_bridge.dispatch_event.emit

    for event_type in window._gui_event_handlers:
        assert handler in bus._subscribers[event_type], "订阅本身没建立，断言无从判断"

    with patch('polcam.gui.main_window.QtWidgets.QMessageBox.warning') as warning:
        window.close()
    assert not warning.called, f"closeEvent 抛异常并弹了框: {warning.call_args}"

    left = [
        event_type.name for event_type in window._gui_event_handlers
        if handler in bus._subscribers[event_type]
    ]
    assert not left, f"关窗后仍在总线上: {left}"


def test_closing_windows_does_not_accumulate_bus_subscriptions(qapp):
    """反复开关窗口不该在总线上越攒越多回调。

    这是上面那条的实际后果：EventManager 是单例，订阅留着就等于把那一任窗口的桥
    一直挂在进程上。实测三个窗口建完关掉，关之前之后总数不变。
    """
    bus = EventManager()
    before = sum(len(callbacks) for callbacks in bus._subscribers.values())

    for _ in range(3):
        window = MainWindow()
        with patch('polcam.gui.main_window.QtWidgets.QMessageBox.warning'):
            window.close()

    after = sum(len(callbacks) for callbacks in bus._subscribers.values())
    assert after == before, f"三轮开关窗口后总线上多了 {after - before} 条"


def test_closing_main_window_destroys_the_camera_even_without_streaming(main_window):
    """接了相机但没出流，关窗时也要把它拆掉。

    closeEvent 写的是 `if camera.is_running(): stop(); destroy()`，而 is_running 只在
    start() 之后才为真 —— 于是"连上相机、看几眼、关程序"这条最常见的路径根本不会
    destroy，设备句柄一直开到进程结束。BaseModule.destroy() 在 _running 时自己会先
    stop()，所以那个 guard 既多余又有害。
    """
    camera = MagicMock()
    camera.is_connected.return_value = True
    camera.is_running.return_value = False
    main_window.camera = camera

    with patch('polcam.gui.main_window.QtWidgets.QMessageBox.warning') as warning:
        main_window.close()

    assert not warning.called, f"closeEvent 抛异常并弹了框: {warning.call_args}"
    camera.destroy.assert_called_once()


def test_a_new_frame_invalidates_the_previous_result(main_window):
    """换了帧就不能再把上一帧的处理结果存出去。

    _last_result 只在 update_last_result 里赋值，全仓没有第二处碰它；而
    _update_frame_and_display 在处理队列还忙的时候会静默丢掉新帧（main_window.py:744）。
    于是"载入帧 B → 屏幕是 B → 点保存处理结果"写出的是帧 A 的四张图和 A 的时间戳。
    """
    from polcam.core.processing_module import ProcessingMode, ProcessingResult

    controller = main_window.toolbar_controller
    frame_a = np.zeros((16, 16), dtype=np.uint8)
    frame_b = np.ones((16, 16), dtype=np.uint8)
    result = ProcessingResult(mode=ProcessingMode.RAW, images=[frame_a], metadata={},
                              timestamp=0.0)

    controller.update_current_frame(frame_a)
    controller.update_last_result(result)
    controller.enable_save_result(True)

    controller.update_current_frame(frame_b)

    assert controller._last_result is None, "新帧到了，缓存的结果还是上一帧的"
    assert not main_window.toolbar.save_result_action.isEnabled()


def test_closed_main_window_is_released_for_gc():
    """关掉又丢掉引用的窗口要真的能被回收。

    两条 once_clicked 以前是拿 lambda 连的，lambda 的闭包握着窗口；PySide 的连接表
    把注册过的槽函数一直留着，于是订阅从总线上摘干净之后窗口还是回不来。实测：只断开
    这两条连接，同一个流程立刻就能被回收；同一段里 wb_once_clicked 连的是绑定方法，
    那才是能被回收的写法。

    探针跑在子进程里，因为强行 gc.collect() 会顺带收尾本进程里其他已经没原生对象的
    Qt 控件 —— 那就是这个仓库历史上那个 0xc0000374 堆损坏。
    """
    probe = os.path.join(os.path.dirname(__file__), "_window_gc_probe.py")
    env = {**os.environ,
           "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", "offscreen")}
    result = subprocess.run([sys.executable, probe], capture_output=True, text=True, env=env)

    assert result.returncode == 0, (
        f"探针退出码 {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr[-1500:]}")




def test_camera_error_dialogs_are_coalesced(main_window):
    """相机错误连着一起来时不能一条一个框。

    采流线程出错之后还会反复发 ERROR_OCCURRED，而 _on_error 对 source=camera 无条件弹
    模态框；模态框自己是嵌套事件循环，用户点掉一个又来一个，界面实际就被钉住了。状态栏
    那条照旧每次都更新。
    """
    def emit_error(message):
        main_window._on_error(Event(EventType.ERROR_OCCURRED, {
            "source": "camera", "error": message}))

    with patch('polcam.gui.main_window.QtWidgets.QMessageBox.warning') as warning:
        emit_error("第一条")
        emit_error("第二条")
        emit_error("第三条")

        assert warning.call_count == 1, f"三条错误弹了 {warning.call_count} 个模态框"
        assert "第三条" in main_window.status_label.text()

        main_window._last_camera_error_dialog_at -= main_window.CAMERA_ERROR_DIALOG_INTERVAL_S
        emit_error("隔了一阵的另一条")
        assert warning.call_count == 2, "隔了多久都不再提醒，用户就看不到新故障了"
        assert "隔了一阵的另一条" in main_window.status_label.text()


def test_a_camera_without_the_current_mode_lands_on_one_it_supports(main_window):
    """换到不支持当前模式的相机时，界面和处理模块要一起落到实际生效的那个模式。

    重建模式列表时 combo 被 blockSignals 归到 0，随后恢复偏好模式发现索引没变，
    currentIndexChanged 根本不触发 —— 于是下拉框写着"原始图像"，白平衡组还留着，
    处理模块仍在跑四角度彩色；偏好模式也没改，下次连接再来一遍。
    """
    from polcam.core.camera_module import CameraType

    main_window.show()   # 可见性断言要真的显示出来才有意义（offscreen 下很便宜）
    main_window.image_display.set_processing_mode(ProcessingMode.QUAD_COLOR)
    main_window._on_display_mode_changed(main_window.image_display.display_mode.currentIndex())
    assert main_window.processor._current_mode == ProcessingMode.QUAD_COLOR
    assert main_window.camera_control.wb_control.isVisible()

    main_window.camera = MagicMock()
    main_window._on_camera_connected(Event(EventType.CAMERA_CONNECTED, {
        "device_info": "普通彩色相机",
        "camera_type": CameraType.NORMAL_COLOR,
    }))

    shown_mode = main_window.image_display.get_current_processing_mode()
    assert main_window.processor._current_mode == shown_mode, (
        f"下拉框是 {shown_mode.name}，处理模块还在 {main_window.processor._current_mode.name}")
    assert main_window._preferred_display_mode == shown_mode
    assert main_window.camera_control.wb_control.isHidden(), "RAW/合成模式下白平衡组还在显示"


def test_hardware_zoom_area_selection_respects_configured_max_zoom(qapp):
    """框选放大也要受最大放大倍率约束。

    点击放大那条路的 int() 换成 ceil 是修过的（1000x1000/31² = 1040x 会越过上限），
    但区域选择这条姊妹路径还是 int()，于是状态栏理直气壮地写着"已调整到最大放大倍率
    1040.6x"。
    """
    display = ImageDisplay()
    controller = display.toolbar_controller
    controller.set_max_zoom(1000.0)

    mock_camera = MagicMock()
    mock_camera.is_connected.return_value = True
    mock_camera.get_sensor_size.return_value = (1000, 1000)
    mock_camera.get_roi.return_value = (0, 0, 31, 31)
    mock_camera.set_roi.return_value = True
    controller.set_camera_module(mock_camera)

    controller._handle_zoom_area_selection(0, 0, 31, 31)

    mock_camera.set_roi.assert_called_once()
    _, _, new_w, new_h = mock_camera.set_roi.call_args.args
    assert (1000 * 1000) / (new_w * new_h) <= 1000.0, (
        f"{new_w}x{new_h} 实际上是 {(1000 * 1000) / (new_w * new_h):.1f}x，超过了 1000x 上限")
