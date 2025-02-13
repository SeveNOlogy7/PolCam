"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

import numpy as np
from qtpy import QtWidgets, QtCore, QtGui
from ..core.camera_module import CameraModule
from ..core.events import EventType, Event, EventManager  # 添加 EventManager 导入
from .camera_control import CameraControl
from .image_display import ImageDisplay
from .status_indicator import StatusIndicator
from .styles import Styles
import logging
from ..core.processing_module import ProcessingModule, ProcessingMode
import os
from ..core.toolbar_controller import ToolbarController
from .widgets.tool_bar import ToolBar

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 设置日志记录器
        self._logger = logging.getLogger("polcam.gui.MainWindow")
        
        # 设置全局字体
        app = QtWidgets.QApplication.instance()
        Styles.setup_application_font(app)
        
        # 设置窗口标题和图标
        self.setWindowTitle("PolCam")

        icon_path = os.path.join(os.path.dirname(__file__), "..", "resources", "icon", "icon.svg")
        if os.path.exists(icon_path):
            icon = QtGui.QIcon(icon_path)
            self._logger.info(f"加载图标: {icon_path}")
        
        if not icon.isNull():
            self.setWindowIcon(icon)
            self._logger.info("成功设置窗口图标")
        else:
            self._logger.error("无法加载图标")
        
        # 首先创建toolbar
        self.toolbar = ToolBar(self)
        self.addToolBar(self.toolbar)
        
        # 然后创建并初始化工具栏控制器
        self.toolbar_controller = ToolbarController(self)
        self.toolbar_controller.initialize()
        
        # 创建其他UI组件
        self.setup_ui()
        
        self.camera = CameraModule()
        self.camera.initialize()  # 初始化相机模块
        self.setup_connections()
        self.setup_statusbar()
        self.current_frame = None      # 原始帧缓存
        
        # 初始化处理模块
        self.processor = ProcessingModule()
        self.processor.initialize()
        
        # 订阅处理模块事件
        self.processor.subscribe_event(EventType.FRAME_PROCESSED, self._on_frame_processed)
        self.processor.subscribe_event(EventType.ERROR_OCCURRED, self._on_error)
        self.processor.subscribe_event(EventType.PROCESSING_STARTED, self._on_processing_started)
        self.processor.subscribe_event(EventType.PROCESSING_COMPLETED, self._on_processing_completed)
        
        # 更新显示模式改变的连接
        self.image_display.display_mode.currentIndexChanged.connect(self._on_display_mode_changed)
        
        # 设置关闭事件处理标志
        self.close_flag = False

        # 订阅相机事件
        self.camera.subscribe_event(EventType.CAMERA_CONNECTED, self._on_camera_connected)
        self.camera.subscribe_event(EventType.CAMERA_DISCONNECTED, self._on_camera_disconnected)
        self.camera.subscribe_event(EventType.FRAME_CAPTURED, self._on_frame_captured)
        self.camera.subscribe_event(EventType.ERROR_OCCURRED, self._on_error)
        self.camera.subscribe_event(EventType.PARAMETER_CHANGED, self._on_parameter_changed)

        self._last_capture_time = 0.0  # 添加采集时间缓存
        self._last_process_time = 0.0  # 添加处理时间缓存
        self._continuous_mode = False  # 添加连续采集模式标志
        self._current_frame_timestamp = None  # 添加时间戳属性

        # 订阅RAW_FILE_LOADED事件
        self.toolbar_controller.subscribe_event(EventType.RAW_FILE_LOADED, self._on_raw_file_loaded)

    def setup_ui(self):
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        
        layout = QtWidgets.QHBoxLayout(self.central_widget)
        
        # 左侧控制面板
        self.camera_control = CameraControl()
        self.camera_control.setMinimumWidth(300)  # 设置最小宽度
        self.camera_control.setMaximumWidth(400)  # 设置最大宽度
        layout.addWidget(self.camera_control, 1)  # 比例因子为1
        
        # 右侧图像显示
        self.image_display = ImageDisplay()
        self.image_display.setMinimumWidth(640)  # 设置最小宽度
        layout.addWidget(self.image_display, 4)  # 比例因子为4
        
        # 设置布局的边距和控件之间的间距
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        self.resize(1200, 800)

    def setup_connections(self):
        # 连接相机控制信号
        self.camera_control.connect_clicked.connect(self.handle_connect)
        self.camera_control.capture_clicked.connect(self.handle_capture)
        self.camera_control.stream_clicked.connect(self.handle_stream)
        
        # 添加参数控制连接
        self.camera_control.exposure_control.value_changed.connect(self.camera.set_exposure_time)
        self.camera_control.exposure_control.auto_changed.connect(self.camera.set_exposure_auto)
        self.camera_control.gain_control.value_changed.connect(self.camera.set_gain)
        self.camera_control.gain_control.auto_changed.connect(self.camera.set_gain_auto)
        self.camera_control.wb_control.auto_changed.connect(self._handle_wb_auto_changed)
        
        # 修改单次按钮连接
        self.camera_control.exposure_control.once_clicked.connect(self.camera.set_exposure_once)
        self.camera_control.gain_control.once_clicked.connect(self.camera.set_gain_once)
        self.camera_control.wb_control.once_clicked.connect(self._handle_wb_once)

        # 添加角度选择信号处理
        self.camera_control.angle_selector.angle_changed.connect(self._handle_angle_changed)
        
        # 添加偏振分析颜色控制连接
        self.camera_control.pol_control.color_mode_changed.connect(self._handle_pol_color_mode_changed)
        self.camera_control.pol_control.wb_auto_changed.connect(self._handle_pol_wb_auto_changed)
        self.camera_control.pol_control.wb_once_clicked.connect(self._handle_pol_wb_once)

    def setup_statusbar(self):
        # 创建状态栏
        self.statusBar().setFixedHeight(24)
        
        # 添加状态指示灯
        self.status_indicator = StatusIndicator()
        self.status_indicator.setEnabled(False)  # 初始状态设为禁用
        self.statusBar().addWidget(self.status_indicator)
        
        # 添加分隔线
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.VLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.statusBar().addWidget(separator)
        
        # 添加状态文本
        self.status_label = QtWidgets.QLabel("就绪")
        self.statusBar().addWidget(self.status_label, 1)  # 1表示拉伸因子
        
        # 添加相机信息标签
        self.camera_info = QtWidgets.QLabel()
        self.statusBar().addPermanentWidget(self.camera_info)  # 添加到右侧
        
        # 添加处理时间信息
        self.time_label = QtWidgets.QLabel()
        self.statusBar().addPermanentWidget(QtWidgets.QLabel("|"))  # 分隔符
        self.statusBar().addPermanentWidget(self.time_label)

    def handle_connect(self, connect: bool):
        if connect:
            success = self.camera.start()  # 使用CameraModule的start方法
            if success:
                self.camera_control.set_connected(True)
                self.status_indicator.setEnabled(True)
                self.status_indicator.setStatus(True)
                # 添加连接状态日志
                self._logger.info("相机连接状态: " + str(self.camera.is_connected()))
            else:
                self.camera_control.connect_btn.setChecked(False)
                self.camera_control.set_connected(False)
                self.status_indicator.setEnabled(False)
                self.status_indicator.setStatus(False)
        else:
            # 断开前先停止连续采集
            if self._continuous_mode:
                self.handle_stream(False)  # 停止连续采集
                self.camera_control.stream_btn.setChecked(False)  # 更新按钮状态
            self.camera.stop()  # 使用CameraModule的stop方法
            self.camera_control.set_connected(False)
            self.status_indicator.setEnabled(False)
            self.status_indicator.setStatus(False)

    def _update_auto_parameters(self):
        """更新自动参数的显示值"""
        if self.camera_control.exposure_control.auto_check.isChecked():
            current_exposure = self.camera.get_exposure_time()
            if current_exposure != self.camera_control.exposure_control.value_spin.value():
                self.camera_control.update_exposure_value(current_exposure)
            
        if self.camera_control.gain_control.auto_check.isChecked():
            current_gain = self.camera.get_gain()
            if current_gain != self.camera_control.gain_control.value_spin.value():
                self.camera_control.update_gain_value(current_gain)

    def handle_capture(self):
        if not self.camera.is_connected():
            QtWidgets.QMessageBox.warning(self, "错误", "相机未连接")
            return
        
        self._set_capture_buttons_enabled(False)
        
        try:
            frame = self.camera.get_frame()
            if frame is not None:
                self.current_frame = frame
                current_mode = ProcessingMode.index_to_mode(self.image_display.display_mode.currentIndex())
                if current_mode == ProcessingMode.RAW:
                    # 原始图像模式直接显示，不经过处理模块
                    self.image_display.show_image(frame)
                    self.toolbar_controller.enable_save_raw(not self._continuous_mode)
                else:
                    # 其他模式需要通过处理模块
                    self.status_indicator.setProcessing(True)
                    self.processor.process_frame(frame)
                self._update_auto_parameters()
            else:
                QtWidgets.QMessageBox.warning(self, "错误", "获取图像失败")
                self.status_indicator.setProcessing(False)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "错误", f"获取图像失败: {str(e)}")
            self.status_indicator.setProcessing(False) 
        finally:
            self._set_capture_buttons_enabled(True)

    def _set_capture_buttons_enabled(self, enabled: bool):
        """设置采集按钮的启用状态"""
        self.camera_control.capture_btn.setEnabled(enabled)
        self.camera_control.stream_btn.setEnabled(enabled)

    def _update_timing_display(self):
        """更新时间显示
        使用缓存的采集和处理时间更新显示
        """
        self.time_label.setText(
            f"采集: {self._last_capture_time*1000:.1f}ms | 处理: {self._last_process_time*1000:.1f}ms"
        )

    def _update_capture_time(self, t_capture: float):
        """更新采集时间"""
        self._last_capture_time = t_capture
        self._update_timing_display()

    def _update_process_time(self, t_proc: float):
        """更新处理时间"""
        self._last_process_time = t_proc
        self._update_timing_display()

    def handle_stream(self, start: bool):
        """处理连续采集开关"""
        # 如果程序正在关闭，不允许开始新的采集
        if self.close_flag and start:
            return
            
        if start:
            # 开始连续采集时禁用单帧采集和保存按钮
            self.camera_control.capture_btn.setEnabled(False)
            self.toolbar_controller.enable_save_raw(False)
            self.toolbar_controller.enable_save_result(False)
            self.camera.start_streaming()
            self.camera_control.stream_btn.setText("停止采集")
            # 设置连续模式标志并更新状态
            self._continuous_mode = True
            self.status_indicator.setProcessing(True)
            self.status_label.setText("连续采集中...")
        else:
            # 停止连续采集
            self.camera.stop_streaming()
            self.camera_control.capture_btn.setEnabled(True)
            self.camera_control.stream_btn.setText("连续采集")
            
            # 取消所有待处理任务并重置状态
            self.processor.cancel_all_tasks()
            self._continuous_mode = False
            self.status_indicator.setProcessing(False)
            self.status_label.setText("就绪")
            
            # 停止连续采集时，检查是否有可用数据并启用保存原始图像按钮
            if self.current_frame is not None:
                self.toolbar_controller.enable_save_raw(True)
            # 不启用保存当前结果按钮，手动切换显示模式后会自动启用

    def _on_display_mode_changed(self, index: int):
        """处理显示模式改变"""
        mode = ProcessingMode.index_to_mode(index)
        self.processor.set_mode(mode)
        
        # 更新控件可见性
        show_wb = not self._is_grayscale_mode(mode)
        show_angle = mode in [ProcessingMode.SINGLE_COLOR, ProcessingMode.SINGLE_GRAY]
        show_pol = mode == ProcessingMode.POLARIZATION
        
        self._logger.debug(f"显示模式改变: {mode}, 显示白平衡: {show_wb}, 显示角度: {show_angle}")
        
        self.camera_control.set_wb_controls_visible(show_wb)
        self.camera_control.set_angle_controls_visible(show_angle)
        self.camera_control.set_pol_controls_visible(show_pol)
        
        # 禁用 RAW 模式下的保存结果按钮
        if mode == ProcessingMode.RAW:
            self.toolbar_controller.enable_save_result(False)
            # 原始图像模式直接显示，不经过处理模块
            self.image_display.show_image(self.current_frame)       
        else:
            # 重新处理当前帧
            self._reprocessing_from_current_frame()

    def _is_grayscale_mode(self, mode: ProcessingMode) -> bool:
        """判断是否是需要隐藏白平衡的显示模式"""
        grayscale_modes = [
            ProcessingMode.RAW,            # 原始图像
            ProcessingMode.SINGLE_GRAY,    # 单角度灰度
            ProcessingMode.MERGED_GRAY,    # 灰度图像
            ProcessingMode.QUAD_GRAY,      # 四角度灰度
            ProcessingMode.POLARIZATION    # 偏振分析
        ]
        return mode in grayscale_modes

    def _on_frame_processed(self, event: Event):
        """处理帧处理完成事件"""
        result = event.data.get('result')
        proc_time = event.data.get('processing_time', 0)
        if result:
            # 更新工具栏控制器中的处理结果和时间戳
            self.toolbar_controller.update_last_result(result, self._current_frame_timestamp)
            self._update_display(result)
            self._update_process_time(proc_time)
            # 只在非连续采集模式下启用保存处理结果按钮
            self.toolbar_controller.enable_save_result(not self._continuous_mode)

    def _on_processing_started(self, event: Event):
        """处理开始时的处理"""
        if not self._continuous_mode:  # 仅在非连续模式下更新状态
            self.status_indicator.setProcessing(True)
            self.status_label.setText("正在处理...")

    def _on_processing_completed(self, event: Event):
        """处理完成时的处理"""
        if not self._continuous_mode:  # 仅在非连续模式下更新状态
            self.status_indicator.setProcessing(False)
            self.status_label.setText("就绪")

    def _update_display(self, result):
        """更新图像显示"""
        if not result or not result.images:
            return
            
        mode = result.mode
        images = result.images
        
        if mode == ProcessingMode.RAW:
            self.image_display.show_image(images[0])
        elif mode in [ProcessingMode.SINGLE_COLOR, ProcessingMode.SINGLE_GRAY]:
            self.image_display.show_image(images[0])
        elif mode in [ProcessingMode.MERGED_COLOR, ProcessingMode.MERGED_GRAY]:
            self.image_display.show_image(images[0])
        elif mode in [ProcessingMode.QUAD_COLOR, ProcessingMode.QUAD_GRAY]:
            self.image_display.show_quad_view(
                images, 
                gray=(mode == ProcessingMode.QUAD_GRAY)
            )
        elif mode == ProcessingMode.POLARIZATION:
            self.image_display.show_polarization_quad_view(*images)

    def _reprocessing_from_current_frame(self):
        """重新处理当前帧
        清空所有待处理任务，在非连续采集模式下，如果存在当前帧则重新进行处理
        """
        self.processor.cancel_all_tasks()  # 清空所有待处理任务
        if not self._continuous_mode and self.current_frame is not None:
            self.processor.process_frame(self.current_frame)

    def _handle_wb_auto_changed(self, auto: bool):
        """处理白平衡状态改变"""
        self.processor.set_parameter('wb_auto', auto)
        self._logger.info(f"使用软件白平衡，自动模式: {auto}")
        self._reprocessing_from_current_frame()

    def _handle_wb_once(self):
        """处理白平衡一次性调整"""
        pass

    def _handle_pol_color_mode_changed(self, is_color: bool):
        """处理偏振分析模式下的颜色模式改变"""
        self.processor.set_parameter('pol_color_mode', is_color)
        self._reprocessing_from_current_frame()

    def _handle_pol_wb_auto_changed(self, auto: bool):
        """处理偏振分析模式下的自动白平衡改变"""
        self.processor.set_parameter('pol_wb_auto', auto)
        self._reprocessing_from_current_frame()

    def _handle_pol_wb_once(self):
        """处理偏振分析模式下的单次白平衡"""
        pass

    def closeEvent(self, event: QtGui.QCloseEvent):
        """处理窗口关闭事件"""
        self.close_flag = True  # 设置关闭标志
        
        try:
            # 如果正在连续采集，先停止采集
            if self._continuous_mode:  # 修改判断条件
                self.handle_stream(False)
                self.camera_control.stream_btn.setChecked(False)

            # 停止并销毁处理模块
            self.processor.stop()
            self.processor.destroy()
            
            # 如果相机已连接，断开连接
            if self.camera.is_running():
                self.camera.stop()
                self.camera.destroy()  # 清理相机模块资源
                
            # 接受关闭事件
            event.accept()
        except Exception as e:
            # 显示错误消息框
            QtWidgets.QMessageBox.warning(
                self,
                "关闭程序",
                f"关闭程序时发生错误: {str(e)}\n程序将继续关闭。"
            )
            event.accept()

    def _on_camera_connected(self, event):
        """处理相机连接事件"""
        self.camera_info.setText(event.data.get("device_info", ""))
        self.status_label.setText("相机已连接")
        
        # 使用相机当前值更新控制面板
        self.camera_control.update_exposure_value(self.camera.get_last_exposure())
        self.camera_control.update_gain_value(self.camera.get_last_gain())

    def _on_camera_disconnected(self, event):
        """处理相机断开事件"""
        self.status_label.setText("相机已断开")
        self.camera_info.clear()
        
        # 禁用保存按钮
        self.toolbar_controller.enable_save_raw(False)
        self.toolbar_controller.enable_save_result(False)

    def _update_frame_and_display(self, frame: np.ndarray, timestamp=None):
        """更新帧数据并显示
        
        Args:
            frame: 图像数据
            timestamp: 时间戳（可选）
        """
        if frame is not None:
            # 如果显示控件未启用，则启用
            if not self.image_display.is_display_controls_enabled():
                self.image_display.enable_display_controls(True)
                
            # 更新当前帧和时间戳
            self.current_frame = frame
            self._current_frame_timestamp = timestamp

            # 获取当前显示模式
            current_mode = ProcessingMode.index_to_mode(
                self.image_display.display_mode.currentIndex()
            )
            
            # 根据模式更新显示或后处理图像
            if current_mode == ProcessingMode.RAW:
                self.image_display.show_image(frame)
            else:
                self.processor.process_frame(frame)

    def _on_frame_captured(self, event):
        """处理帧捕获事件"""
        frame = event.data.get("frame")
        capture_time = event.data.get("capture_time", 0)
        timestamp = event.data.get("timestamp")
        
        if frame is not None:
            # 更新工具栏控制器中的当前帧和时间戳
            self.toolbar_controller.update_current_frame(frame, timestamp)
            self._update_capture_time(capture_time)
            # 更新自动参数显示
            self._update_auto_parameters()
            # 更新保存按钮状态
            self.toolbar_controller.enable_save_raw(not self._continuous_mode)
            # 更新帧和显示
            self._update_frame_and_display(frame, timestamp)

    def _on_error(self, event):
        """处理错误事件"""
        error_data = event.data
        error_msg = error_data.get("error", "未知错误")
        self.status_label.setText(f"错误: {error_msg}")
        if error_data.get("source") == "camera":
            QtWidgets.QMessageBox.warning(self, "相机错误", error_msg)

    def _on_parameter_changed(self, event):
        """处理参数改变事件"""
        param_data = event.data
        param_name = param_data.get("parameter")
        param_value = param_data.get("value")
        
        if param_name == "exposure":
            self.camera_control.update_exposure_value(param_value)
        elif param_name == "gain":
            self.camera_control.update_gain_value(param_value)

    def _handle_angle_changed(self, angle: int):
        """处理角度选择改变"""
        self.processor.set_parameter('selected_angle', angle)
        self._reprocessing_from_current_frame()

    def _on_raw_file_loaded(self, event: Event):
        """处理原始文件加载事件"""
        try:
            frame = event.data.get('frame')
            timestamp = event.data.get('timestamp')
            filepath = event.data.get('filepath')
            
            # 更新帧和显示
            self._update_frame_and_display(frame, timestamp)
            
            # 更新状态栏显示文件路径
            self.status_label.setText(f"已加载图像: {filepath}")
                
        except Exception as e:
            self._logger.error(f"处理原始文件加载事件失败: {str(e)}")
            self.status_label.setText("加载图像失败")
