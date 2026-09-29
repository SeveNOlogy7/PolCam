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
    mock_camera.is_capturing_frame.return_value = False
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
    mock_camera.is_capturing_frame.return_value = False
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


def test_retarder_panel_drives_the_processing_params(qapp, main_window):
    """面板上的波片开关和角度要真的落到处理参数上。"""
    main_window.camera_control.pol_control.retarder_check.setChecked(True)

    assert main_window.processor.get_parameters()['retarder_in_path'] is True
    assert main_window.camera_control.pol_control.retarder_angle_spin.isEnabled()

    main_window.camera_control.pol_control.retarder_angle_spin.setValue(30.0)
    assert main_window.processor.get_parameters()['retarder_fast_axis_deg'] == 30.0

    main_window.camera_control.pol_control.retarder_check.setChecked(False)
    assert main_window.processor.get_parameters()['retarder_in_path'] is False
    assert not main_window.camera_control.pol_control.retarder_angle_spin.isEnabled()


def test_settings_dialog_offers_only_the_modes_this_camera_can_show(qapp, main_window):
    """设置里的"默认显示模式"不能列出接上的相机根本显示不了的模式。

    真机（MER2-502-79U3M-HS POL，黑白偏振，只有 5 个可用模式）实测：对话框仍然列 8 个，
    选了「四角度彩色」点确定之后 set_processing_mode 找不到就退回第一项，用户每次启动
    都拿到「原始图像」，而那个不可能的偏好已经被写进 INI。
    """
    from polcam.core.camera_module import CameraType
    from polcam.gui.settings_dialog import SettingsDialog

    main_window.image_display.set_camera_modes(CameraType.MONO)
    available = main_window.image_display.get_active_modes()
    assert ProcessingMode.QUAD_COLOR not in available, "替身场景不对：黑白机不该有彩色模式"

    dialog = SettingsDialog(main_window.build_current_settings(), main_window,
                            available_modes=available)
    listed = [dialog.display_mode_combo.itemData(i)
              for i in range(dialog.display_mode_combo.count())]
    assert listed == available, f"对话框列出的模式和相机能给的不一致: {listed}"

    dialog.display_mode_combo.setCurrentIndex(len(available) - 1)
    chosen = dialog.get_settings().ui.display_mode
    assert chosen == available[-1] and chosen in available


def test_settings_menu_passes_the_camera_modes_to_the_dialog(qapp, main_window, monkeypatch):
    """打开设置菜单时要把当前相机的可用模式带进对话框，不能让它写死一份彩色清单。"""
    from polcam.core.camera_module import CameraType
    from polcam.gui.settings_dialog import SettingsDialog

    main_window.image_display.set_camera_modes(CameraType.MONO)
    available = main_window.image_display.get_active_modes()

    seen = {}
    real_init = SettingsDialog.__init__

    def spy(self, current_settings, parent=None, available_modes=None):
        seen['modes'] = available_modes
        real_init(self, current_settings, parent, available_modes)

    monkeypatch.setattr(SettingsDialog, "__init__", spy)
    monkeypatch.setattr(SettingsDialog, "exec_", lambda self: 0)
    main_window.toolbar_controller._handle_settings()

    assert seen.get('modes') == available, \
        f"对话框没拿到相机的模式列表，而是自己那份: {seen.get('modes')}"


def test_restore_defaults_keeps_the_waveplate_where_the_user_left_it(qapp, main_window):
    """设置对话框的「恢复默认」不能把波片从光路里收走。

    真机实测：侧栏设成"1/4 波片在光路 / 快轴 45°"之后那一帧的解算是 rank=3、DoCP 带符号；
    这时打开设置页（本页根本没有波片控件），只点了「恢复默认」再确定，参数就变成
    retarder_in_path=False、快轴=0.0。对话框自己的注释写着波片不在本页编辑、保存时要沿用
    当前生效的值，可 _restore_defaults 连基线一起换成了出厂值，用户没碰过的物理状态被改了。
    """
    from polcam.gui.settings_dialog import SettingsDialog

    settings = main_window.build_current_settings()
    settings.processing.retarder_in_path = True
    settings.processing.retarder_fast_axis_deg = 45.0
    main_window.apply_settings(settings, persist=False)

    dialog = SettingsDialog(main_window.build_current_settings(), main_window)
    dialog.max_zoom_spin.setValue(50.0)
    dialog._restore_defaults()
    restored = dialog.get_settings()

    assert restored.processing.retarder_in_path is True, "恢复默认把波片挪出光路了"
    assert float(restored.processing.retarder_fast_axis_deg) == 45.0, "快轴角度被重置"
    assert restored.ui.max_zoom == 1000.0, "其余偏好该回到默认却没回"


def test_apply_settings_survives_a_multi_angle_fast_axis_value(qapp, main_window):
    """一串快轴角度不能把 apply_settings 拦腰打断。

    真机实测：`set_retarder_state` 对 list 做 float() 抛 TypeError
    （float() argument must be a string or a real number, not 'list'），于是它后面的
    处理参数循环、显示模式恢复和持久化全都没跑。而 `load_processing_settings` 的
    `_to_angles` 恰恰会把列表原样送回来。
    """
    from polcam.core.processing_module import ProcessingMode

    settings = main_window.build_current_settings()
    settings.processing.retarder_in_path = True
    settings.processing.retarder_fast_axis_deg = [0.0, 45.0]
    settings.ui.display_mode = ProcessingMode.POLARIZATION

    main_window.apply_settings(settings, persist=False)

    panel = main_window.camera_control.pol_control
    assert panel.retarder_check.isChecked()
    assert panel.retarder_angle_spin.value() == 0.0, "面板只有一个自旋框，应回填第一个角度"
    assert main_window.processor.get_parameters()['retarder_fast_axis_deg'] == [0.0, 45.0], \
        "完整角度序列必须留在处理参数里"
    assert main_window.image_display.get_current_processing_mode() == ProcessingMode.POLARIZATION, \
        "异常发生在前面就把显示模式的应用也吃掉了"


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
        Event(EventType.PARAMETER_CHANGED, {"parameter": "exposure", "value": 4321.0,
                                       "one_shot": True}))
    assert exposure.value_spin.isEnabled(), "单次完成后没有恢复手动控件"

def test_one_shot_gain_restores_the_manual_control(main_window):
    """增益的那半程和曝光一样要接上。"""
    main_window.camera = MagicMock()
    gain = main_window.camera_control.gain_control
    assert gain.value_spin.isEnabled()

    gain.once_clicked.emit()
    assert not gain.value_spin.isEnabled(), "单次自动增益期间没有禁用手动控件"

    main_window._on_parameter_changed(
        Event(EventType.PARAMETER_CHANGED, {"parameter": "gain", "value": 3.5, "one_shot": True}))
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
    camera.is_capturing_frame.return_value = False
    camera.get_roi.return_value = (0, 0, 50, 50)
    camera.get_sensor_size.return_value = (100, 100)
    camera.reset_roi.return_value = True
    controller.set_camera_module(camera)

    controller._handle_reset_view()

    assert camera.reset_roi.called, "相机 ROI 仍是裁剪状态，没有被复原"


def test_reset_view_waits_for_an_in_flight_capture(qapp):
    """单帧采集还握着设备时点「复原」，要等一次，别拿注定失败的写入换一条报错。

    真机实测：抓取线程还停在 stream_on/stream_off 里时点复原，ROI 四个节点全部
    is not writeable，界面弹「相机错误：设置 ROI 失败」，而用户要的复原毫无效果。
    """
    display = ImageDisplay()
    display.show_image(np.zeros((100, 100, 3), dtype=np.uint8))
    controller = display.toolbar_controller

    camera = MagicMock()
    camera.is_connected.return_value = True
    camera.is_streaming.return_value = False
    camera.get_roi.return_value = (0, 0, 50, 50)
    camera.get_sensor_size.return_value = (100, 100)
    camera.is_capturing_frame.return_value = True
    controller.set_camera_module(camera)

    messages = []
    controller.publish_event = lambda event_type, data=None: messages.append((event_type, data))

    controller._handle_reset_view()

    assert not camera.reset_roi.called, "采集还没结束就去写 ROI，设备会直接拒绝"
    text = " ".join(str(d.get('message')) for t, d in messages
                    if t == EventType.STATUS_MESSAGE_UPDATE and d)
    assert "采集" in text, f"只说了失败，没告诉用户是在等采集结束：{text!r}"


def test_hardware_zoom_waits_for_an_in_flight_capture(qapp):
    """没有显示图像时放大走的是硬件 ROI，同样不能插进一次正在进行的抓取。"""
    controller = ImageDisplay().toolbar_controller

    camera = MagicMock()
    camera.is_connected.return_value = True
    camera.is_streaming.return_value = False
    camera.get_roi.return_value = (0, 0, 100, 100)
    camera.get_sensor_size.return_value = (100, 100)
    camera.is_capturing_frame.return_value = True
    controller.set_camera_module(camera)
    assert not controller._should_use_software_zoom(), "该用例要走硬件 ROI 分支"

    controller._handle_zoom_in(True)
    controller._handle_zoom_click(50, 50)

    assert not camera.set_roi.called, "抓取途中仍然下发 ROI 写入"


def test_single_capture_does_not_hold_the_gui_thread(qapp, main_window, monkeypatch):
    """单帧采集不能把一整个曝光的等待压在 GUI 线程里。

    真机实测：没有连续采集时点「单帧采集」，`handle_capture()` 占住 GUI 244ms（曝光
    10ms）/ 350ms（200ms）/ 650ms（500ms），这期间 10ms 周期的定时器一格都不走 ——
    整个窗口是冻住的。采集完按钮必须自己恢复，失败也要能在界面上看到原因。
    """
    calls = {}

    def fake_get_frame():
        calls["starts"] = calls.get("starts", 0) + 1
        calls["thread"] = threading.current_thread().name
        time.sleep(0.12)
        return np.zeros((8, 8), dtype=np.uint8)

    monkeypatch.setattr(main_window.camera, "is_connected", lambda: True)
    monkeypatch.setattr(main_window.camera, "get_frame", fake_get_frame)

    main_window.handle_capture()
    assert not main_window.camera_control.capture_btn.isEnabled(), "采集期间按钮没禁用"
    assert not main_window.camera_control.connect_btn.isEnabled(), \
        "抓取还占着设备时不该能断开相机"
    # 占用标记必须在 handle_capture 这一次调用里就立起来：真机实测抓取线程还没起步时
    # GUI 点「视图复原」，set_roi 照样下发到设备，节点写被采集吞掉（界面报"视图已重置"
    # 而 ROI 仍裁着）。等 worker 进 get_frame 再立标记就晚了。
    assert main_window.camera.is_capturing_frame(), "请求已经受理，设备占用状态却看不出来"

    # 抓取没结束前重复请求必须被忽略：真机实测两次 get_frame 重叠时后一次抛
    # DataStream.get_image:{-1}Unknown exception
    main_window.handle_capture()

    def wait_until(condition, timeout=5.0):
        deadline = time.time() + timeout
        while not condition() and time.time() < deadline:
            QApplication.processEvents()
            time.sleep(0.01)
        return condition()

    assert wait_until(lambda: main_window.camera_control.capture_btn.isEnabled()), \
        "收尾后采集按钮没恢复"
    assert not main_window.camera.is_capturing_frame(), "抓取结束了却没交还设备"
    assert calls.get("thread") not in (None, "MainThread"), f"抓帧还跑在 GUI 线程里: {calls}"
    assert calls.get("starts") == 1, f"重复请求没被挡掉，一共起了 {calls.get('starts')} 轮抓帧"
    assert main_window.camera_control.stream_btn.isEnabled()

    boxes = []
    from qtpy import QtWidgets
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning",
                        staticmethod(lambda parent, title, text, *a, **k: boxes.append(text)))

    def boom():
        calls["failed_thread"] = threading.current_thread().name
        raise RuntimeError("设备没响应")

    monkeypatch.setattr(main_window.camera, "get_frame", boom)
    main_window.handle_capture()
    assert wait_until(lambda: boxes), "采集失败没有反馈到界面上"
    assert "设备没响应" in boxes[0], boxes
    assert wait_until(lambda: main_window.camera_control.capture_btn.isEnabled())
    assert main_window._single_capture_requested is False, "失败后还留着待采集标记"


def test_a_frame_that_arrives_after_disconnect_keeps_the_last_readout(qapp, main_window):
    """断开之后才送达的那一帧，不能把曝光/增益读数写成设备量程下限。

    真机实测（MER2-502-79U3M-HS POL）：连续采集中断开相机，事件队列里还没送达的
    FRAME_CAPTURED 会在断开之后进来。这时 get_exposure_time() 因为设备句柄已经没了而回
    0.0，QDoubleSpinBox 再把 0.0 夹成它的下限 20.0 —— 相机明明断开了，框里却显示
    "20.0 µs"，而断开前设备的真实值是 119498 µs。同一类读数在
    `_build_capture_metadata` 里早就用 is_connected() 挡过了，这条漏了。
    """
    control = main_window.camera_control
    control.exposure_control.auto_check.setChecked(True)
    control.gain_control.auto_check.setChecked(True)
    control.update_exposure_value(119498.0)
    control.update_gain_value(12.5)

    main_window.camera._camera = None
    main_window.camera._remote_feature = None
    main_window._on_frame_captured(Event(EventType.FRAME_CAPTURED, {
        "frame": np.zeros((8, 8), dtype=np.uint8),
        "capture_time": 0.01,
        "timestamp": time.time(),
    }))

    assert control.exposure_control.value_spin.value() == 119498.0, \
        "断开后的晚到帧把曝光读数写成了设备量程下限"
    assert control.gain_control.value_spin.value() == 12.5, \
        "断开后的晚到帧把增益读数写成了 0 dB"


def test_a_stale_parameter_notice_does_not_finish_a_one_shot(qapp, main_window):
    """点击之前那次手动写入的迟到通知，不能替之后的「单次自动」收尾。

    真机混合手势 soak 里 6/6 轮都是这个形状：面板写曝光 → PARAMETER_CHANGED 进事件队列
    → 紧接着点「单次自动」→ 那个排队的通知被当成自动调整完成了，控件恢复、在飞集合清空，
    而相机这时才真的进入 Once。之后用户再改曝光一律被 Node is not writable 挡掉，界面上
    只留一条 WARNING，看起来像"曝光滑条时不时失灵"。
    """
    control = main_window.camera_control
    control.exposure_control.set_value(50000.0)
    main_window._one_shot_pending.add('exposure')

    main_window._on_parameter_changed(Event(EventType.PARAMETER_CHANGED, {
        "parameter": "exposure", "value": 50000.0}))

    assert 'exposure' in main_window._one_shot_pending, \
        "手动写入的迟到通知把还没结束的单次自动调整报成了完成"
    assert control.exposure_control.value_spin.value() == 50000.0, \
        "被挡下来的通知仍然应该照常刷新显示值"


def test_the_one_shot_notification_does_finish_the_adjustment(qapp, main_window):
    """自动调整自己报回来的那条才作数：清空在飞、恢复控件、显示测得的值。"""
    control = main_window.camera_control
    main_window.camera_control.handle_one_shot_auto('exposure')
    main_window._one_shot_pending.add('exposure')

    main_window._on_parameter_changed(Event(EventType.PARAMETER_CHANGED, {
        "parameter": "exposure", "value": 437839.0, "one_shot": True}))

    assert not main_window._one_shot_pending
    assert control.exposure_control.value_spin.value() == 437839.0
    assert control.exposure_control.value_spin.isEnabled(), "控件没有随调整完成而恢复"


def test_a_frame_dropped_by_the_busy_gate_is_not_lost(qapp, main_window, monkeypatch):
    """处理器正忙时进来的那一帧不能直接丢掉，否则屏幕永远停在旧图上。

    真机实测（全尺寸 + 降噪 0.6）：载入 A，趁 A 还在解算时载入 B —— 状态栏说"已加载图像: B"，
    但 20 秒后屏幕上仍然是 A（均值 40 而不是 200），而 toolbar 的 `_current_frame` 已经指向 B：
    看到的一张、要存/要重处理的另一张。忙判断本身是对的（连续采集不能堆任务），缺的是
    "最近一帧"补交这一步。
    """
    submitted = []
    busy = {"flag": True}
    main_window.processor.process_frame = lambda frame, capture_timestamp=None: submitted.append(frame)
    monkeypatch.setattr(main_window.processor, "get_task_count", lambda: 1 if busy["flag"] else 0)
    monkeypatch.setattr(main_window.processor, "is_processing", lambda: busy["flag"])
    image_display = main_window.image_display
    monkeypatch.setattr(image_display, "get_current_processing_mode",
                        lambda: ProcessingMode.MERGED_GRAY)

    a = np.full((8, 8), 40, dtype=np.uint8)
    b = np.full((8, 8), 200, dtype=np.uint8)
    main_window._update_frame_and_display(a)
    main_window._update_frame_and_display(b)
    assert submitted == [], "忙的时候不该抢先提交"

    busy["flag"] = False
    main_window._on_processing_completed(Event(EventType.PROCESSING_COMPLETED))
    assert submitted == [b], f"忙完之后要补交最近的一帧，实际提交了 {len(submitted)} 帧"

def test_a_repeated_failed_connect_still_speaks_up(qapp, main_window, monkeypatch):
    """用户主动点「连接相机」的失败，每一次都要报，不能被流错误的合并窗口吞掉。

    真机实测（只有一台相机、被另一个进程占着）：第一次点「连接相机」弹一个框；隔几秒再点
    一次，一个框都没有、状态栏文字一模一样 —— 界面上就像按钮坏了。那个去抖是给采集线程的
    错误洪流准备的（一条重复错误弹一次框会把界面钉住），用户自己点的这一下不该被它压掉。
    """
    boxes = []
    from qtpy import QtWidgets
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning",
                        staticmethod(lambda parent, title, text, *a, **k: boxes.append(text)))
    main_window._last_camera_error_dialog_at = 0.0

    def camera_error(text, from_connect):
        data = {"source": "camera", "error": text}
        if from_connect:
            data["from_connect"] = True
        main_window._on_error(Event(EventType.ERROR_OCCURRED, data))

    camera_error("连接相机失败: -1004 The device has been open", True)
    camera_error("连接相机失败: -1004 The device has been open", True)
    assert len(boxes) == 2, f"两次主动连接失败只报了 {len(boxes)} 次"

    boxes.clear()
    main_window._last_camera_error_dialog_at = 0.0
    camera_error("采流线程出错", False)
    camera_error("采流线程出错", False)
    assert len(boxes) == 1, "采集线程的错误洪流必须仍然只弹一次"


def test_two_one_shot_auto_adjusts_do_not_run_at_once(qapp, main_window, monkeypatch):
    """两路单次自动调整也不能同时在飞 —— 真机上它们会互相拖死。

    实测（连续采集中，暗场）：单独点曝光「单次」0.8s 收敛（顶到 1 000 000µs 是暗场下 AE
    该给的答案），单独点增益「单次」0.4s 收敛到 24.0dB；两个连着点则 5.1s 内谁都不收敛，
    双双走满超时被强制收回手动，最后停在 (1 000 000µs, 6.6dB) —— 这组值谁都没打算选，而
    这 5 秒里两组控件一直是禁的。相机的曝光与增益算法互相影响，一次只能让一路在飞。
    """
    started = []

    def fake_exposure_once():
        started.append('exposure')
        time.sleep(0.4)

    def fake_gain_once():
        started.append('gain')
        time.sleep(0.4)

    monkeypatch.setattr(main_window.camera, "is_connected", lambda: True)
    monkeypatch.setattr(main_window.camera, "set_exposure_once", fake_exposure_once)
    monkeypatch.setattr(main_window.camera, "set_gain_once", fake_gain_once)

    main_window._handle_exposure_once()
    assert main_window._one_shot_pending == {'exposure'}
    gain_spin = main_window.camera_control.gain_control.value_spin
    assert gain_spin.isEnabled(), "只调曝光不该把增益也禁掉"

    main_window._handle_gain_once()
    assert 'gain' not in main_window._one_shot_pending, "第二路自动调整被放行了"
    assert gain_spin.isEnabled(), "被让开的请求不该把增益控件禁掉"
    assert ("自动" in main_window.status_label.text()
            or "稍候" in main_window.status_label.text()), \
        f"没告诉用户为什么没反应：{main_window.status_label.text()!r}"

    deadline = time.time() + 5
    while main_window._one_shot_pending and time.time() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    assert started == ['exposure'], f"第二路还是起了线程：{started}"
    assert not main_window._one_shot_pending


def test_a_one_shot_auto_adjust_and_a_capture_do_not_share_the_device(qapp, main_window,
                                                                      monkeypatch):
    """两条各自独占设备的路不能同时在飞。

    抓帧挪到工作线程之后，「单帧采集」和「单次自动曝光」可以同时跑起来，真机实测（曝光
    500ms）两种顺序都会坏：先自动后采集，自动那一路 5s 不收敛被强制收回，之后单抓一帧拿到
    的是 None（SDK: RawImage.get_numpy_array: This is a incomplete image）；先采集后自动，
    采集的 stream_off 把自动打断，相机停在 Once 而界面以为调整已完成，此后手动写曝光被静默
    丢掉。两边都得等对方让开设备。
    """
    release = threading.Event()
    one_shot_threads = []
    grab_threads = []

    def fake_get_frame():
        grab_threads.append(threading.current_thread().name)
        time.sleep(0.25)
        return np.zeros((8, 8), dtype=np.uint8)

    def fake_exposure_once():
        one_shot_threads.append(threading.current_thread().name)
        release.wait(5)

    monkeypatch.setattr(main_window.camera, "is_connected", lambda: True)
    monkeypatch.setattr(main_window.camera, "get_frame", fake_get_frame)
    monkeypatch.setattr(main_window.camera, "set_exposure_once", fake_exposure_once)

    def wait_until(condition, timeout=5.0):
        deadline = time.time() + timeout
        while not condition() and time.time() < deadline:
            QApplication.processEvents()
            time.sleep(0.01)
        return condition()

    # 采集在独占设备：单次自动调整必须让开，连线程都不能起
    main_window.handle_capture()
    main_window._handle_exposure_once()
    assert one_shot_threads == [], "抓取还占着设备就起了自动调整线程"
    assert 'exposure' not in main_window._one_shot_pending, \
        "被让开的请求还挂在在飞表里，之后的晚到完成会点亮已经过时的控件"
    assert "采集" in main_window.status_label.text(), "让开的时候没在界面上说原因"

    assert wait_until(lambda: main_window.camera_control.capture_btn.isEnabled())

    # 反过来：自动调整在轮询硬件，采集必须让开
    main_window._handle_exposure_once()
    assert wait_until(lambda: len(one_shot_threads) == 1)
    grabs_before = len(grab_threads)
    pending = set(main_window._one_shot_pending)
    main_window.handle_capture()
    assert pending == {'exposure'}, f"自动调整没被记成在飞: {pending}"
    assert len(grab_threads) == grabs_before, "自动调整还没收工就起了第二路设备操作"
    assert main_window.camera_control.capture_btn.isEnabled(), \
        "请求被让开了却把按钮禁成了正在采集的样子"

    release.set()
    assert wait_until(lambda: not main_window._one_shot_pending)

    # 让开不是永久封死：对方收工后两边照常走
    main_window.handle_capture()
    assert wait_until(lambda: len(grab_threads) == grabs_before + 1)
    assert grab_threads[0] != "MainThread"


def test_a_result_from_the_mode_the_user_left_is_dropped(main_window):
    """切走模式之后，上一个模式还在路上算完的结果不能糊到屏幕上。

    真机实测：偏振度图像 + 降噪（一帧 0.6 s）做一次单帧采集，立刻切到「原始图像」；
    1 秒后那张 4096x4896 的四联图被画上来并停在那里（单次采集没有下一帧覆盖它），
    `_last_result` 也变成它，「保存结果」按钮跟着亮起来。
    """
    from polcam.core.processing_module import ProcessingResult

    display = main_window.image_display
    display.show_image(np.zeros((32, 32, 3), dtype=np.uint8))
    display.set_processing_mode(ProcessingMode.RAW)
    canvas_before = display._current_canvas.copy()
    main_window.toolbar_controller._last_result = None
    main_window.toolbar_controller.enable_save_result(False)

    stale = ProcessingResult(
        mode=ProcessingMode.POLARIZATION,
        images=[np.zeros((16, 16), dtype=np.uint8)]
               + [np.zeros((16, 16), dtype=np.float32) for _ in range(3)],
        metadata={}, timestamp=0.0,
        display_canvas=np.zeros((32, 32, 3), dtype=np.uint8))
    event = Event(EventType.FRAME_PROCESSED, {'result': stale, 'processing_time': 0.6})

    main_window._on_frame_processed(event)

    assert np.array_equal(display._current_canvas, canvas_before), "过期结果把画面换掉了"
    assert main_window.toolbar_controller._last_result is None, "过期结果成了「最近一次结果」"
    assert not main_window.toolbar.save_result_action.isEnabled(), "过期结果把保存按钮点亮了"

    display.set_processing_mode(ProcessingMode.POLARIZATION)
    main_window._on_frame_processed(event)
    assert len(display.current_images) == 4, "模式对得上时结果应当照常画出来"


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


def test_closed_main_window_is_released_for_gc(tmp_path):
    """关掉又丢掉引用的窗口要真的能被回收。

    两条 once_clicked 以前是拿 lambda 连的，lambda 的闭包握着窗口；PySide 的连接表
    把注册过的槽函数一直留着，于是订阅从总线上摘干净之后窗口还是回不来。实测：只断开
    这两条连接，同一个流程立刻就能被回收；同一段里 wb_once_clicked 连的是绑定方法，
    那才是能被回收的写法。

    探针跑在子进程里，因为强行 gc.collect() 会顺带收尾本进程里其他已经没原生对象的
    Qt 控件 —— 那就是这个仓库历史上那个 0xc0000374 堆损坏。真机接上后又实测：子进程里
    「close → del → gc.collect()」6 次崩 4 次（0xC0000374，faulthandler 停在
    Garbage-collecting），所以探针改成先 shiboken6.delete() 按 Qt 的顺序拆 C++ 树，再让
    gc 判可达性；同一个流程不调 collect 时 0/6，正常退出也是 0/6，说明应用本身没有这条
    路径，崩的是探针的做法。
    """
    probe = os.path.join(os.path.dirname(__file__), "_window_gc_probe.py")
    # 显式 UTF-8：text=True 不指定 encoding 就用 locale codec（中文 Windows 是 cp936），
    # 探针往 stderr 打中文日志时解码线程抛 UnicodeDecodeError，result.stdout 成了 None，
    # 于是断言失败信息里的 result.stderr[-1500:] 自己先 TypeError，真正的失败原因被吃掉。
    # HOME/USERPROFILE 不能在这里改：大恒 SDK 也读它们，实测改了子进程直接
    # 0xc0000409 崩掉。配置隔离由探针自己在进程内 patch Path.home() 完成。
    env = {**os.environ,
           "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", "offscreen"),
           "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run([sys.executable, probe, str(tmp_path / "gcprobe")],
                            capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=env)

    assert result.returncode == 0, (
        f"探针退出码 {result.returncode}\nstdout: {result.stdout or ''}\n"
        f"stderr: {(result.stderr or '')[-1500:]}")




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


def test_a_reconnect_leaves_no_auto_flag_the_device_does_not_have(qapp, main_window):
    """勾着「自动」断开再重连：连接时设备被写回手动，面板的勾必须一起回来。

    真机实测（MER2-502-79U3M-HS POL）：勾选自动曝光后设备 ExposureAuto=Continuous、数值框
    只读且去掉箭头；断开再连接，`_init_camera_parameters()` 把设备写成 Off，而复选框还挂着
    勾、数值框仍然只读无箭头 —— 界面宣称在自动曝光，实际既没有自动，用户也改不了曝光数值，
    只能靠猜出"把勾去掉"这一招。
    """
    from polcam.core.events import Event, EventType
    from polcam.core.camera_module import CameraType

    exp = main_window.camera_control.exposure_control
    gain = main_window.camera_control.gain_control
    exp.auto_check.setChecked(True)
    gain.auto_check.setChecked(True)
    assert exp.value_spin.isReadOnly(), "前提：勾着自动时数值框是只读的"

    main_window._on_camera_connected(Event(EventType.CAMERA_CONNECTED, {
        "device_info": "黑白偏振相机", "camera_type": CameraType.MONO}))

    assert not exp.auto_check.isChecked(), "面板还在宣称自动曝光，设备已经是手动"
    assert not gain.auto_check.isChecked(), "同上，增益"
    assert not exp.value_spin.isReadOnly(), "用户仍然改不动曝光数值"
    assert not gain.value_spin.isReadOnly()
    assert exp.once_btn.isEnabled(), "「单次」还因为挂着自动而被禁用"


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
    mock_camera.is_capturing_frame.return_value = False
    mock_camera.get_sensor_size.return_value = (1000, 1000)
    mock_camera.get_roi.return_value = (0, 0, 31, 31)
    mock_camera.set_roi.return_value = True
    controller.set_camera_module(mock_camera)

    controller._handle_zoom_area_selection(0, 0, 31, 31)

    mock_camera.set_roi.assert_called_once()
    _, _, new_w, new_h = mock_camera.set_roi.call_args.args
    assert (1000 * 1000) / (new_w * new_h) <= 1000.0, (
        f"{new_w}x{new_h} 实际上是 {(1000 * 1000) / (new_w * new_h):.1f}x，超过了 1000x 上限")


def test_clicking_the_image_after_leaving_a_tool_mode_still_works(qapp):
    """退出工具模式之后点图像，不该把 None 当成槽函数去调。

    set_interaction_mode('none')（以及 set_cursor_mode(False)）把三个鼠标虚函数赋成
    None，而 PySide 照旧按实例属性去找并调用它们。实测第一次点击就是
    TypeError: Error calling Python override of QLabel::mousePressEvent():
    'NoneType' object is not callable —— 事件被丢掉，还往日志里灌错误。
    """
    from qtpy.QtCore import QPoint, Qt
    from qtpy.QtTest import QTest

    display = ImageDisplay()
    try:
        display.show_image(np.zeros((120, 160, 3), dtype=np.uint8))
        display.set_interaction_mode('zoom_in')
        display.set_interaction_mode('none')

        QTest.mouseClick(display.image_label, Qt.LeftButton, Qt.NoModifier, QPoint(30, 30))
    finally:
        import shiboken6
        if shiboken6.isValid(display):
            shiboken6.delete(display)


def test_restoring_a_display_mode_runs_the_refresh_once(main_window):
    """补那次"索引没动也要刷新"不能变成"索引动了还再刷一次"。

    set_processing_mode 内部就是 setCurrentIndex，而 currentIndexChanged 没被屏蔽，所以
    模式真的换了的时候刷新已经跑过一遍；_restore_display_mode 再手动调一次，等于同一件
    事做两遍：连接/断开一次相机，_on_display_mode_changed 跑两次、帧被排队处理两次，
    状态灯跟着闪两下。
    """
    from polcam.core.camera_module import CameraType
    from polcam.core.processing_module import ProcessingMode

    main_window.image_display.set_processing_mode(ProcessingMode.RAW)
    main_window._preferred_display_mode = ProcessingMode.QUAD_COLOR
    main_window.camera = MagicMock()
    reappraised = []
    original = main_window._reprocessing_from_current_frame

    def counting(*args):
        reappraised.append(args)
        original(*args)

    main_window._reprocessing_from_current_frame = counting
    try:
        main_window._on_camera_connected(Event(EventType.CAMERA_CONNECTED, {
            "device_info": "彩色偏振相机", "camera_type": CameraType.COLOR}))
    finally:
        main_window._reprocessing_from_current_frame = original

    assert main_window.image_display.get_current_processing_mode() != ProcessingMode.RAW, \
        "这个用例要跑在「模式真的换了」的情形上"
    assert len(reappraised) == 1, f"一次连接把显示模式刷新了 {len(reappraised)} 遍"


def _left_right_balance(pixmap):
    image = pixmap.toImage()
    y = image.height() // 2
    left = sum(image.pixel(x, y) & 0xFF for x in range(image.width() // 4))
    right = sum(image.pixel(x, y) & 0xFF
                for x in range(image.width() * 3 // 4, image.width()))
    return left, right


_STEP = np.broadcast_to(np.arange(64)[None, :], (64, 64)) < 32

@pytest.mark.parametrize("frame", [
    pytest.param(np.where(_STEP, 0, 65535).astype(np.uint16), id="uint16"),
    pytest.param(np.where(_STEP, 0.0, 1.0).astype(np.float32), id="float32"),
])
def test_a_non_8bit_frame_is_not_displayed_as_random_noise(qapp, frame):
    """_create_qimage 只看形状不看 dtype，非 8bit 的帧会被按 uint8 的 stride 解释。

    原始帧读取现在保留文件真实位深（IMREAD_UNCHANGED），16bit 的 Mono10/12/16 TIFF
    就是这么进到显示路径的：bytes_per_line 还是按 w 算，于是每行读到的字节错位，
    半黑半白的图整屏变成一个灰值。用左右阶梯而不是渐变来测，因为渐变按字节错位读
    出来还是渐变，看不出错。
    """
    display = ImageDisplay()
    try:
        display.show_image(frame)
        pixmap = display.image_label.pixmap()
        assert pixmap is not None and not pixmap.isNull()
        left, right = _left_right_balance(pixmap)
        assert right > left * 4, f"左半 {left}、右半 {right}：阶梯被抹平了"
    finally:
        import shiboken6
        if shiboken6.isValid(display):
            shiboken6.delete(display)


def _overlay_green_centroid(overlay):
    image = overlay.grab().toImage()
    xs = ys = hits = 0
    for y in range(0, image.height(), 2):
        for x in range(0, image.width(), 2):
            pixel = image.pixel(x, y)
            if (pixel >> 8) & 0xFF > 200 and (pixel >> 16) & 0xFF < 80 and pixel & 0xFF < 80:
                xs += x; ys += y; hits += 1
    return (xs / hits, ys / hits) if hits else None


def test_loaded_file_loses_the_sensor_coordinate_readout(qapp, main_window, monkeypatch):
    """载入的文件不是传感器帧，游标读数不能再报传感器坐标。

    真机实测：相机 ROI=(1200,1000,800,600) 时打开一个 1024x1024 的文件，状态栏把文件
    里的 (258, 258) 说成“传感器 (1401, 1151)”——那串数字属于上一次相机的窗口。
    """
    monkeypatch.setattr(main_window.camera, 'is_connected', lambda: True)
    monkeypatch.setattr(main_window.camera, 'get_roi', lambda: (1200, 1000, 800, 600))
    monkeypatch.setattr(main_window.camera, 'get_sensor_size', lambda: (2448, 2048))
    display = main_window.image_display
    display.show_image(np.zeros((600, 800, 3), dtype=np.uint8))
    display.update_roi_info((1200, 1000, 800, 600), (2448, 2048))
    assert display._source_to_sensor_position(10, 20) == (1210, 1020)

    main_window._on_raw_file_loaded(Event(EventType.RAW_FILE_LOADED, {
        'frame': np.full((1024, 1024), 123, dtype=np.uint8),
        'timestamp': None,
        'filepath': 'scene.tiff',
    }))
    assert not display.has_roi_info(), "载入文件后还留着相机的 ROI 缓存"
    assert display._source_to_sensor_position(10, 20) is None

    main_window._on_frame_captured(Event(EventType.FRAME_CAPTURED, {
        'frame': np.zeros((600, 800), dtype=np.uint8),
        'capture_time': 1,
        'timestamp': None,
    }))
    assert display.has_roi_info(), "回到实时帧后读数应恢复成传感器坐标"
    assert display._source_to_sensor_position(10, 20) == (1210, 1020)

    main_window._on_camera_disconnected(Event(EventType.CAMERA_DISCONNECTED, {}))
    assert not display.has_roi_info(), "断开之后没有传感器可换算"


def test_roi_changed_event_refreshes_the_display_cache(qapp, main_window):
    """采集进行中 ROI 变更要真的回填显示层缓存，不能只记日志。

    真机实测：外部 set_roi(1200,1000,800,600) 之后 ImageDisplay 里还是
    (0,0,2448,2048)，游标读数和缩放用的传感器换算都按上一次的窗口算，读数差整个 ROI
    偏移。工具栏那两条路是自己回填才碰巧没错，事件里本来就带着权威值，统一在这里回填。
    连续采集中才会来新帧，所以这条只在 `_continuous_mode` 为真时生效。
    """
    from polcam.core.events import Event, EventType

    main_window._continuous_mode = True
    main_window.image_display.update_roi_info((0, 0, 2448, 2048), (2448, 2048))

    main_window._on_roi_changed(Event(EventType.ROI_CHANGED, {
        'offset_x': 1200, 'offset_y': 1000, 'width': 800, 'height': 600,
        'sensor_width': 2448, 'sensor_height': 2048}))

    assert main_window.image_display._current_roi == (1200, 1000, 800, 600), \
        f"缓存没跟上设备：{main_window.image_display._current_roi}"


def test_a_roi_change_while_stopped_does_not_relabel_the_frame_on_screen(qapp, main_window):
    """停止采集时改设备 ROI，不许把屏上那张旧图的传感器坐标一起改掉。

    真机实测：ROI=(808,342,1632,1364) 采一帧后点「复原」，设备回到全幅、屏上还是那张
    裁剪图（同一个像素值没变），中心读数却从 (1624, 1024) 变成 (1224, 1024)。缓存应当
    描述"屏幕上这些像素来自哪块传感器"，而不是"设备下一帧打算用哪块"。
    """
    from polcam.core.events import Event, EventType

    display = main_window.image_display
    display.show_image(np.zeros((600, 800), dtype=np.uint8))
    display.update_roi_info((1200, 1000, 800, 600), (2448, 2048))
    main_window._continuous_mode = False

    main_window._on_roi_changed(Event(EventType.ROI_CHANGED, {
        'offset_x': 0, 'offset_y': 0, 'width': 2448, 'height': 2048,
        'sensor_width': 2448, 'sensor_height': 2048}))

    assert display._current_roi == (1200, 1000, 800, 600), \
        f"旧帧被按新 ROI 重新贴标：{display._current_roi}"
    assert display._source_to_sensor_position(10, 20) == (1210, 1020)


def test_reset_view_leaves_the_readout_on_the_pixels_it_shows(qapp, main_window, monkeypatch):
    """「复原视图」把设备恢复全幅，但屏上那张裁剪图的读数必须继续按裁剪窗口算。

    真机实测的中心点读数：复原前 (1624, 1024)（正确），复原后 (1224, 1024)（编的），
    期间屏幕上的像素一个都没变。工具栏自己在软件分支里回填缓存是这条错误读数的来源。
    """
    cam = main_window.camera
    device = {'roi': (808, 342, 1632, 1364)}
    monkeypatch.setattr(cam, 'is_connected', lambda: True)
    monkeypatch.setattr(cam, 'is_streaming', lambda: False)
    monkeypatch.setattr(cam, 'is_capturing_frame', lambda: False)
    monkeypatch.setattr(cam, 'get_sensor_size', lambda: (2448, 2048))
    monkeypatch.setattr(cam, 'get_roi', lambda: device['roi'])

    def _reset_roi():
        device['roi'] = (0, 0, 2448, 2048)
        return True

    monkeypatch.setattr(cam, 'reset_roi', _reset_roi)

    display = main_window.image_display
    display.show_image(np.zeros((1364, 1632), dtype=np.uint8))
    display.update_roi_info((808, 342, 1632, 1364), (2448, 2048))
    assert display._source_to_sensor_position(816, 682) == (1624, 1024)

    display.toolbar_controller._handle_reset_view()

    assert device['roi'] == (0, 0, 2448, 2048), "前提：设备 ROI 确实被复原了"
    assert display._current_roi == (808, 342, 1632, 1364), \
        f"屏上还是那张裁剪图，缓存却改成了 {display._current_roi}"
    assert display._source_to_sensor_position(816, 682) == (1624, 1024)


def test_a_single_capture_relabels_the_readout_with_its_own_snapshot(qapp, main_window):
    """新帧一到，坐标换算就得换成这一帧自己的参数快照，不能继续用上一张的窗口。

    承接上一条：停止期间设备被复原（缓存故意留着旧裁剪窗口），随后单帧采集拍到全幅。
    这时屏上的像素已经是全幅，而缓存还写着裁剪窗口 —— 真机实测这条会把中心点报成
    (1624, 1024) 而不是 (1224, 1024)。帧里本来就带着抓取时的 roi/sensor_size。
    """
    from polcam.core.events import Event, EventType

    display = main_window.image_display
    display.show_image(np.zeros((200, 300), dtype=np.uint8))
    display.update_roi_info((100, 50, 300, 200), (600, 400))

    main_window._on_frame_captured(Event(EventType.FRAME_CAPTURED, {
        'frame': np.zeros((400, 600), dtype=np.uint8),
        'capture_time': 1,
        'timestamp': None,
        'settings': {'exposure_us': 10000.0, 'gain_db': 0.0,
                     'roi': [0, 0, 600, 400], 'sensor_size': [600, 400]},
    }))

    assert display._current_roi == (0, 0, 600, 400), \
        f"新帧还挂着上一张的窗口：{display._current_roi}"


def test_starting_a_stream_syncs_the_readout_with_the_roi_its_frames_use(qapp, main_window, monkeypatch):
    """连续采集的帧不带参数快照，开流那一刻要把设备 ROI 同步给显示层一次。

    真机路径：停止时把设备复原成全幅（缓存留着旧裁剪窗口是对的），接着点「连续采集」，
    流里的帧全是全幅，而缓存还是 (808,342,1632,1364) —— 读数会一路错到下一次 ROI 变更。
    """
    cam = main_window.camera
    monkeypatch.setattr(cam, 'start_streaming', lambda: True)
    monkeypatch.setattr(cam, 'is_connected', lambda: True)
    monkeypatch.setattr(cam, 'get_roi', lambda: (0, 0, 2448, 2048))
    monkeypatch.setattr(cam, 'get_sensor_size', lambda: (2448, 2048))

    display = main_window.image_display
    display.show_image(np.zeros((1364, 1632), dtype=np.uint8))
    display.update_roi_info((808, 342, 1632, 1364), (2448, 2048))

    main_window.handle_stream(True)

    assert display._current_roi == (0, 0, 2448, 2048), \
        f"开流后缓存还停在 {display._current_roi}"


def test_cursor_readout_uses_sensor_coordinates_after_a_hardware_crop(qapp):
    """硬件放大之后，游标读数要报传感器绝对坐标而不是画布坐标。

    真机实测：ROI=(1200,1000,800,600) 时状态栏把一个物理点报成 "(1, 1)"，它的传感器
    坐标其实是 (1201, 1001)。画布坐标在裁剪后与传感器坐标差着整个 ROI 偏移，用户照着
    读数描述位置就会指错地方。
    """
    display = ImageDisplay()
    controller = display.toolbar_controller
    shown = []
    # 事件总线是队列+后台线程，订阅它要等投递；直接记 `_show_status_message` 的入参，
    # 断言只取决于读数本身
    controller._show_status_message = shown.append

    display.show_image(np.zeros((600, 800, 3), dtype=np.uint8))
    display.update_roi_info((1200, 1000, 800, 600), (2448, 2048))

    assert display._source_to_sensor_position(0, 0) == (1200, 1000)
    assert display._source_to_sensor_position(1, 1) == (1201, 1001)
    assert display._source_to_sensor_position(799, 599) == (1999, 1599)

    # 去马赛克出来的单角度图是半分辨率，但覆盖同一视场，换算要带上这个 2x
    display.show_quad_view([np.zeros((300, 400), dtype=np.uint8) for _ in range(4)], gray=True)
    assert display._source_to_sensor_position(399, 299) == (1998, 1598)

    controller._cursor_mode = True
    controller._handle_cursor_position({
        'position': (1, 1), 'sensor_position': (1201, 1001), 'mode': 'single', 'gray': 10})
    assert shown, "游标读数没发到状态栏"
    assert '(1201, 1001)' in shown[-1], shown[-1]
    assert '(1, 1)' not in shown[-1], f"还在报画布坐标：{shown[-1]}"

    display.deleteLater()


def test_quad_cursor_overlay_follows_the_software_crop(qapp):
    """游标画在裁剪后的哪一格，得按裁剪窗口算，不能拿源图坐标直接乘。

    _QuadCursorOverlay.paintEvent 把 cursor_quad_position（源图坐标）当作裁剪画布的
    tile 坐标来用：`(quad_x + rel_x) * scale_x`。没裁剪、没降采样时两者恰好相等，所以
    平时看不出来；一框选放大就露馅 —— 实测裁剪到 (60,60,64,64) 后，被裁掉的 (20,20)
    照旧画出来，而窗内的 (80,80) 被算到画布外，什么都看不见。
    """
    from polcam.gui.image_display import _QuadCursorOverlay

    display = ImageDisplay()
    try:
        # 叠加层只在四分图模式下工作，这个判据取的是显示模式 combo，不是画布
        display.set_processing_mode(ProcessingMode.QUAD_GRAY)
        display.show_quad_view([np.full((128, 128), 40, dtype=np.uint8) for _ in range(4)])
        display.resize(700, 500)
        display.show()
        QApplication.processEvents()
        display.set_cursor_mode(True)
        overlay = next(c for c in display.image_label.children()
                       if isinstance(c, _QuadCursorOverlay))

        def at(source_xy):
            # 游标状态归 ImageDisplay 管：每次重渲染都会把叠加层重新同步回
            # display.cursor_info。实测直接写叠加层的私有字段时，一次 16ms 的 resize
            # 刷新就能把游标抹掉，用例就变成了看时序的随机测试。
            display.cursor_info = {"cursor_quad_position": source_xy}
            display._update_cursor_overlay()
            overlay.repaint()
            return _overlay_green_centroid(overlay)

        unzoomed_origin = at((0, 0))
        assert unzoomed_origin is not None, "游标根本没画出来，用例无从判断"

        assert display.apply_software_zoom_area(60, 60, 64, 64)
        QApplication.processEvents()

        assert at((20, 20)) is None, "裁剪窗口外的点还画在视图里"
        cropped_origin = at((60, 60))
        assert cropped_origin is not None, "裁剪窗左上角那个点被算到了画布外"
        assert abs(cropped_origin[0] - unzoomed_origin[0]) < 12 and \
            abs(cropped_origin[1] - unzoomed_origin[1]) < 12, (
            f"裁剪窗原点应落在未裁剪原点附近：{cropped_origin} vs {unzoomed_origin}")
    finally:
        import shiboken6
        if shiboken6.isValid(display):
            shiboken6.delete(display)


def test_quad_area_zoom_is_clamped_to_the_tile_it_started_in(qapp, qtbot):
    """四分图里拖框选区：钳在起手那一格，换算出的传感器矩形左右两列要对齐。

    真机实测（2448x2048，画布 672x563，四格 336x281/282）：从格0 中心拖到格3 中心，
    请求是 (1216,1018,1224,1019) —— 正好是格0 自己的右下四分之一，没有跨到别的角度图；
    同一次相对拖拽在左右两列给出的 x 完全相同，说明格子的画布偏移被正确减掉了。
    这段橡皮筋代码（_on_zoom_mouse_press/move/release）此前一行都没被测试走过。
    """
    import shiboken6

    display = ImageDisplay()
    tiles = [np.full((64, 64), i, dtype=np.uint8) for i in range(4)]
    requests = []
    display.zoomAreaRequested.connect(lambda *a: requests.append(a))
    try:
        display.resize(800, 600)
        display.set_processing_mode(ProcessingMode.QUAD_GRAY)
        display.show_quad_view(tiles, gray=True)
        display.show()
        qapp.processEvents()
        display.update_roi_info((0, 0, 64, 64), (64, 64))
        display.set_interaction_mode('zoom_area')

        geom = display._get_display_geometry()
        assert geom is not None, "离屏窗口没拿到几何，测不到折算"
        gx, gy, dw, dh = geom
        tile_w, tile_h = dw / 2, dh / 2

        def drag(tile_col, tile_row):
            requests.clear()
            # 每一次拖拽本身就会缩放视图，不复原就没法横向比较（真机上第一版探针就栽在
            # 这里：四格的矩形一轮比一轮小，看着像映射错了）
            display.reset_software_view()
            qapp.processEvents()
            left = gx + tile_col * tile_w
            top = gy + tile_row * tile_h
            p0 = QtCore.QPoint(int(left + tile_w * 0.1), int(top + tile_h * 0.1))
            p1 = QtCore.QPoint(int(left + tile_w * 0.6), int(top + tile_h * 0.6))
            qtbot.mousePress(display.image_label, QtCore.Qt.LeftButton, pos=p0)
            qtbot.mouseMove(display.image_label, pos=p1)
            qtbot.mouseRelease(display.image_label, QtCore.Qt.LeftButton, pos=p1)
            assert requests, "一次格内拖拽没有产生选区请求"
            return requests[-1]

        per_tile = [drag(c, r) for r, c in ((0, 0), (0, 1), (1, 0), (1, 1))]
        for (sx, sy, sw, sh) in per_tile:
            assert sx >= 0 and sy >= 0 and sx + sw <= 64 and sy + sh <= 64, \
                f"选区越出传感器范围: {(sx, sy, sw, sh)}"
        rounded = [tuple(int(round(v, 1)) for v in req) for req in per_tile]
        assert len({(r[0], r[2]) for r in rounded}) == 1, \
            f"同一格内相对位置的横向选区，左右两列不该给出不同的传感器 x: {rounded}"
        assert len({(r[1], r[3]) for r in rounded}) == 1, \
            f"同一格内相对位置的纵向选区，上下两行不该给出不同的传感器 y: {rounded}"

        # 跨格拖拽：必须被钳回起手那一格（格0），也就是不越界且不超过单格面积的一半
        requests.clear()
        display.reset_software_view()
        qapp.processEvents()
        start = QtCore.QPoint(int(gx + tile_w * 0.5), int(gy + tile_h * 0.5))
        far = QtCore.QPoint(int(gx + tile_w * 1.9), int(gy + tile_h * 1.9))
        qtbot.mousePress(display.image_label, QtCore.Qt.LeftButton, pos=start)
        qtbot.mouseMove(display.image_label, pos=far)
        qtbot.mouseRelease(display.image_label, QtCore.Qt.LeftButton, pos=far)
        assert requests, "跨格拖拽没有产生选区请求"
        sx, sy, sw, sh = requests[-1]
        assert sx >= 0 and sy >= 0 and sx + sw <= 64 and sy + sh <= 64, \
            f"跨格拖拽没被钳在起手格内: {(sx, sy, sw, sh)}"
        assert sw <= 36 and sh <= 36, f"钳位后仍覆盖了不止半格: {(sx, sy, sw, sh)}"
    finally:
        display.set_interaction_mode('none')
        qapp.processEvents()
        shiboken6.delete(display)


def test_quad_cursor_mapping_survives_a_software_crop(qapp):
    """四分图 + 软件裁剪时，游标必须仍然指着"看上去那一格的那个位置"。

    真机实测（四角度灰度，4 张 2448x2048，软件放大到 view=(680,568,1088,910)、倍率 5.06）：
    左上/右上/右下三格的源画布位置、四张角度图的像素值、传感器读数、所在格序号与独立算出的
    期望值全部一致。这段"控件 → 渲染画布 → 第几格的格内比例 → 源画布 → 传感器"的折算此前只
    在无裁剪时被测过：裁剪之后渲染画布是 2x2 个"裁剪后的格子"拼的，`quad_size` 也跟着变小，
    按源画布尺寸换算就会指到别的格子、别的像素。
    """
    import shiboken6

    display = ImageDisplay()
    xs = np.arange(80, dtype=np.uint8)
    ys = np.arange(80, dtype=np.uint8)
    # 每格每张图都随位置递增且互不相同：错位一格或错一个像素都能看出来
    tiles = [(60 * i + np.add.outer(ys, xs) + i).astype(np.uint8) for i in range(4)]

    try:
        display.resize(800, 600)
        display.set_processing_mode(ProcessingMode.QUAD_GRAY)
        display.show_quad_view(tiles, gray=True)
        display.show()
        qapp.processEvents()
        display.set_cursor_mode(True)
        display.update_roi_info((100, 200, 320, 240), (640, 480))
        display.apply_software_zoom_click(40, 40, 'zoom_in', zoom_factor=2.0)

        view = display._get_current_view_roi()
        geom = display._get_display_geometry()
        assert geom is not None and view is not None, "离屏窗口没拿到几何，折算测不到"
        rc_h, rc_w = display._rendered_canvas_shape
        assert (rc_w, rc_h) == (view[2] * 2, view[3] * 2), \
            f"渲染画布应当是 2x2 个裁剪格: {rc_w}x{rc_h} view={view}"

        gx, gy, dw, dh = geom
        for fx, fy, expected_index in ((0.12, 0.10, 0), (0.88, 0.15, 1),
                                       (0.15, 0.90, 2), (0.90, 0.88, 3)):
            wx, wy = int(gx + dw * fx), int(gy + dh * fy)
            rx, ry = int((wx - gx) * rc_w / dw), int((wy - gy) * rc_h / dh)
            col, row = 0 if rx < rc_w / 2 else 1, 0 if ry < rc_h / 2 else 1
            exp_src = (int(view[0] + (rx - col * rc_w / 2) / (rc_w / 2) * view[2]),
                       int(view[1] + (ry - row * rc_h / 2) / (rc_h / 2) * view[3]))
            exp_values = [int(tiles[i][exp_src[1], exp_src[0]]) for i in range(4)]
            # ROI (100,200,320,240) 覆盖 80x80 的源图：横每像素 4、纵每像素 3 个传感器像素
            exp_sensor = (100 + exp_src[0] * 320 // 80, 200 + exp_src[1] * 240 // 80)

            event = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, QtCore.QPointF(wx, wy),
                                      QtCore.Qt.MouseButton.NoButton, QtCore.Qt.MouseButton.NoButton,
                                      QtCore.Qt.KeyboardModifier.NoModifier)
            display._on_mouse_move(event)

            info = display.cursor_info
            assert info is not None, f"第 {expected_index} 格没有游标读数"
            assert info['quad_index'] == expected_index, \
                f"光标在第 {expected_index} 格，读数指到了 {info['quad_index']}"
            assert tuple(info['position']) == exp_src, \
                f"({fx}, {fy}) 处源画布位置: 期望 {exp_src} 实得 {info['position']}"
            assert [int(v) for v in info['quad_gray_values']] == exp_values
            assert tuple(info['sensor_position']) == exp_sensor, \
                f"传感器读数: 期望 {exp_sensor} 实得 {info['sensor_position']}"
    finally:
        # 显式按 Qt 要求的顺序拆掉这棵已经 realized 的控件树：留给解释器退出时的垃圾回收
        # 就是本仓库那个 0xC0000374 堆损坏（conftest 关窗口用的是同一招）。
        shiboken6.delete(display)


def test_auto_save_records_the_frame_not_the_device_now(qapp, main_window, monkeypatch):
    """图库元数据必须写"这一帧是用什么参数拍的"，不是保存那一刻设备上的值。

    真机实测：400 ms 曝光的抓取还在飞的时候把曝光改成 20 ms，存进图库的那条记录
    exposure_us 就成了 20000.0，而文件的像素是 400 ms 的（均值 43.78）；裁剪同理。
    抓帧挪到工作线程之后，抓取到存盘之间隔着一整个曝光，所以这个值必须在抓取那边抄。
    """
    main_window._last_capture_settings = {
        'exposure_us': 400000.0, 'gain_db': 3.0,
        'roi': [0, 0, 2448, 2048], 'sensor_size': [2448, 2048]}
    monkeypatch.setattr(main_window.camera, "is_connected", lambda: True)
    monkeypatch.setattr(main_window.camera, "get_exposure_time", lambda: 20000.0)
    monkeypatch.setattr(main_window.camera, "get_gain", lambda: 0.0)
    monkeypatch.setattr(main_window.camera, "get_roi", lambda: (1200, 1000, 800, 600))
    monkeypatch.setattr(main_window.camera, "get_sensor_size", lambda: (2448, 2048))

    meta = main_window._build_capture_metadata(np.zeros((8, 8), dtype=np.uint8), 1.0)

    assert meta['exposure_us'] == 400000.0, "记的是保存那一刻的曝光，不是这一帧的"
    assert meta['gain_db'] == 3.0
    assert meta['roi'] == [0, 0, 2448, 2048]
