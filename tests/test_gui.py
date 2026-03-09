"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

import pytest
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
from polcam.core.events import Event, EventType
from polcam.core.processing_module import ProcessingMode
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

def test_style_application(qapp):
    """测试样式应用"""
    window = MainWindow()
    
    # 测试按钮样式
    assert window.camera_control.connect_btn.font().pointSize() == Styles.FONT_MEDIUM
    assert window.camera_control.connect_btn.minimumHeight() == Styles.HEIGHT_MEDIUM
    
    # 测试下拉框样式
    assert window.image_display.display_mode.font().pointSize() == Styles.FONT_MEDIUM
    assert window.image_display.display_mode.minimumHeight() == Styles.HEIGHT_MEDIUM


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
    # 测试未连接相机时的错误处理
    main_window.handle_capture()  # 应该显示错误消息而不是崩溃
    
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
