"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtCore, QtGui
import time
import numpy as np
import concurrent.futures
from typing import List, Tuple
from ..core.camera_module import CameraModule
from ..core.image_processor import ImageProcessor
from ..core.events import EventType
from .camera_control import CameraControl
from .image_display import ImageDisplay
from .status_indicator import StatusIndicator
from .styles import Styles
import logging

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 设置日志记录器
        self._logger = logging.getLogger("polcam.gui.MainWindow")
        
        # 设置全局字体
        app = QtWidgets.QApplication.instance()
        Styles.setup_application_font(app)
        
        self.setWindowTitle("偏振相机控制系统")
        self.setup_ui()
        
        self.camera = CameraModule()
        self.camera.initialize()  # 初始化相机模块
        self.image_processor = ImageProcessor()
        self.setup_connections()
        self.setup_statusbar()
        self.current_frame = None      # 原始帧缓存
        
        # 设置关闭事件处理标志
        self.close_flag = False

        # 订阅相机事件
        self.camera.subscribe_event(EventType.CAMERA_CONNECTED, self._on_camera_connected)
        self.camera.subscribe_event(EventType.CAMERA_DISCONNECTED, self._on_camera_disconnected)
        self.camera.subscribe_event(EventType.FRAME_CAPTURED, self._on_frame_captured)
        self.camera.subscribe_event(EventType.ERROR_OCCURRED, self._on_error)
        self.camera.subscribe_event(EventType.PARAMETER_CHANGED, self._on_parameter_changed)

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
        
        # 设置更新定时器
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_frame)
        
        # 添加参数控制连接
        self.camera_control.exposure_changed.connect(self.camera.set_exposure_time)
        self.camera_control.exposure_auto_changed.connect(self.camera.set_exposure_auto)
        self.camera_control.gain_changed.connect(self.camera.set_gain)
        self.camera_control.gain_auto_changed.connect(self.camera.set_gain_auto)
        self.camera_control.wb_auto_changed.connect(self.camera.set_white_balance_auto)
        
        # 添加显示模式变化和白平衡状态变化的信号处理
        self.image_display.display_mode.currentIndexChanged.connect(
            lambda: self.process_and_display_frame(self.current_frame, reprocess=True)
        )
        
        # 修改单次按钮连接
        self.camera_control.exposure_once.clicked.connect(self.camera.set_exposure_once)
        self.camera_control.gain_once.clicked.connect(self.camera.set_gain_once)
        self.camera_control.wb_once.clicked.connect(self.camera.set_balance_white_once)

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
            if self.timer.isActive():
                self.handle_stream(False)  # 停止连续采集
                self.camera_control.stream_btn.setChecked(False)  # 更新按钮状态
            self.camera.stop()  # 使用CameraModule的stop方法
            self.camera_control.set_connected(False)
            self.status_indicator.setEnabled(False)
            self.status_indicator.setStatus(False)

    def _update_auto_parameters(self):
        """更新自动参数的显示值"""
        if self.camera_control.exposure_auto.isChecked():
            current_exposure = self.camera.get_exposure_time()
            if current_exposure != self.camera_control.exposure_spin.value():
                self.camera_control.update_exposure_value(current_exposure)
            
        if self.camera_control.gain_auto.isChecked():
            current_gain = self.camera.get_gain()
            if current_gain != self.camera_control.gain_spin.value():
                self.camera_control.update_gain_value(current_gain)

    def handle_capture(self):
        if not self.camera.is_connected():
            QtWidgets.QMessageBox.warning(self, "错误", "相机未连接")
            return
        
        self._set_capture_buttons_enabled(False)
        
        try:
            frame = self.camera.get_frame()
            if frame is not None:
                t_capture, t_proc = self._handle_frame_processing(frame)
                self._update_auto_parameters()
                self._update_timing_display(t_capture, t_proc)
            else:
                QtWidgets.QMessageBox.warning(self, "错误", "获取图像失败")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "错误", f"获取图像失败: {str(e)}")
        finally:
            self._set_capture_buttons_enabled(True)

    def _set_capture_buttons_enabled(self, enabled: bool):
        """设置采集按钮的启用状态"""
        self.camera_control.capture_btn.setEnabled(enabled)
        self.camera_control.stream_btn.setEnabled(enabled)

    def _update_timing_display(self, t_capture: float, t_proc: float):
        """更新时间显示"""
        self.time_label.setText(
            f"采集: {t_capture*1000:.1f}ms | 处理: {t_proc*1000:.1f}ms"
        )

    def handle_stream(self, start: bool):
        # 如果程序正在关闭，不允许开始新的采集
        if self.close_flag and start:
            return
            
        if start:
            # 开始连续采集时禁用单帧采集
            self.camera_control.capture_btn.setEnabled(False)
            self.camera.start_streaming()
            self.timer.start(33)  # ~30 FPS
            self.camera_control.stream_btn.setText("停止采集")  # 更新按钮文字
        else:
            # 停止连续采集时启用单帧采集
            self.camera.stop_streaming()
            self.timer.stop()
            self.camera_control.capture_btn.setEnabled(True)
            self.camera_control.stream_btn.setText("连续采集")  # 恢复按钮文字

    def update_frame(self):
        t_start = time.perf_counter()
        try:
            frame = self.camera.get_frame()
            if frame is not None:
                
                t_capture = time.perf_counter() - t_start
                t_proc_start = time.perf_counter()
                self.process_and_display_frame(frame)
                t_proc = time.perf_counter() - t_proc_start
                
                self._update_auto_parameters()  # 更新自动参数值
                
                # 更新状态栏时间信息
                self.time_label.setText(
                    f"采集: {t_capture*1000:.1f}ms | 处理: {t_proc*1000:.1f}ms"
                )
        except Exception as e:
            # 流模式下的错误不显示弹窗，只更新状态栏
            self.status_label.setText(f"采集错误: {str(e)}")

    def _process_image_by_mode(self, mode: int, color_images: List[np.ndarray], color_image: np.ndarray) -> None:
        """根据显示模式处理并显示图像
        
        Args:
            mode: 显示模式索引
            color_images: 四个角度的彩色图像列表
            color_image: 合成的彩色图像
        """
        if mode == 1:  # 单角度彩色
            self.image_display.show_image(color_images[0])
        elif mode == 2:  # 单角度灰度
            gray_image = self.image_processor.to_grayscale(color_images[0])
            self.image_display.show_image(gray_image)
        elif mode == 3:  # 彩色图像
            self.image_display.show_image(color_image)
        elif mode == 4:  # 灰度图像
            gray_image = self.image_processor.to_grayscale(color_image)
            self.image_display.show_image(gray_image)
        elif mode == 5:  # 四角度彩色
            self.image_display.show_quad_view(color_images, gray=False)
        elif mode == 6:  # 四角度灰度
            gray_images = [self.image_processor.to_grayscale(img) for img in color_images]
            self.image_display.show_quad_view(gray_images, gray=True)
        elif mode == 7:  # 偏振分析
            dolp, aolp, docp = self.image_processor.calculate_polarization_parameters(color_images)
            self.image_display.show_polarization_quad_view(color_image, dolp, aolp, docp)

    def _apply_white_balance(self, color_images: List[np.ndarray]) -> List[np.ndarray]:
        """应用白平衡处理
        
        Args:
            color_images: 原始彩色图像列表
            
        Returns:
            处理后的彩色图像列表
        """
        if self.camera.is_wb_auto() and self.camera.is_using_software_wb():
            # 对第一个角度图像执行自动白平衡以获取增益系数
            color_images[0] = self.image_processor.auto_white_balance(color_images[0])
            # 对其他角度图像应用相同的白平衡系数
            for i in range(1, 4):
                color_images[i] = self.image_processor.apply_white_balance(color_images[i])
        return color_images

    def _handle_frame_processing(self, frame: np.ndarray) -> Tuple[float, float]:
        """处理单帧图像并返回处理时间
        
        Args:
            frame: 输入图像帧
            
        Returns:
            (采集时间, 处理时间) 的元组
        """
        t_start = time.perf_counter()
        t_capture = time.perf_counter() - t_start
        
        t_proc_start = time.perf_counter()
        self.process_and_display_frame(frame)
        t_proc = time.perf_counter() - t_proc_start
        
        return t_capture, t_proc

    def process_and_display_frame(self, frame, reprocess=False):
        if frame is None:
            return
            
        try:
            self.current_frame = frame
            mode = self.image_display.display_mode.currentIndex()
            
            if mode == 0:  # 原始图像
                self.image_display.show_image(frame)
                return
                
            # 解码彩色图像
            color_images = self.image_processor.demosaic_polarization(frame)
            
            # 应用白平衡处理
            color_images = self._apply_white_balance(color_images)
            
            # 计算合成彩色图像
            color_image = np.mean(color_images, axis=0).astype(np.uint8)
            
            # 根据显示模式处理
            self._process_image_by_mode(mode, color_images, color_image)
                    
        except Exception as e:
            raise Exception(f"图像处理失败: {e}")

    def _handle_wb_auto_changed(self, auto: bool):
        """处理白平衡状态改变"""
        # 设置相机白平衡状态
        self.camera.set_balance_white_auto(auto)
        
        # 只在非连续采集模式下触发重新处理
        if not self.timer.isActive() and self.current_frame is not None:
            self.process_and_display_frame(self.current_frame, reprocess=True)

    def _handle_exposure_once(self):
        """处理单次自动曝光"""
        # 禁用相关控件
        self.camera_control.enable_exposure_controls(False)
        
        def on_complete(future):
            try:
                future.result()
                QtCore.QTimer.singleShot(0, self._update_exposure_controls)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "错误", f"单次自动曝光失败: {str(e)}")
                QtCore.QTimer.singleShot(0, lambda: self.camera_control.enable_exposure_controls(True))
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(self.camera.set_exposure_once)
            future.add_done_callback(on_complete)

    def _handle_gain_once(self):
        """处理单次自动增益"""
        self.camera_control.enable_gain_controls(False)
        
        def on_complete(future):
            try:
                future.result()
                QtCore.QTimer.singleShot(0, self._update_gain_controls)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "错误", f"单次自动增益失败: {str(e)}")
                QtCore.QTimer.singleShot(0, lambda: self.camera_control.enable_gain_controls(True))
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(self.camera.set_gain_once)
            future.add_done_callback(on_complete)

    def _handle_wb_once(self):
        """处理单次白平衡"""
        self.camera_control.enable_wb_controls(False)
        
        def on_complete(future):
            try:
                future.result()
                QtCore.QTimer.singleShot(0, self._update_wb_controls)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "错误", f"单次白平衡失败: {str(e)}")
                QtCore.QTimer.singleShot(0, lambda: self.camera_control.enable_wb_controls(True))
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(self.camera.set_balance_white_once)
            future.add_done_callback(on_complete)

    @QtCore.Slot()
    def _update_exposure_controls(self):
        """更新曝光控件状态"""
        self.camera_control.enable_exposure_controls(True)
        # 更新显示值
        current_exposure = self.camera.get_exposure_time()
        self.camera_control.update_exposure_value(current_exposure)

    @QtCore.Slot()
    def _update_gain_controls(self):
        """更新增益控件状态"""
        self.camera_control.enable_gain_controls(True)
        current_gain = self.camera.get_gain()
        self.camera_control.update_gain_value(current_gain)

    @QtCore.Slot()
    def _update_wb_controls(self):
        """更新白平衡控件状态"""
        self.camera_control.enable_wb_controls(True)
        self.camera_control.wb_once.setChecked(False)

    def closeEvent(self, event: QtGui.QCloseEvent):
        """处理窗口关闭事件"""
        self.close_flag = True  # 设置关闭标志
        
        try:
            # 如果正在连续采集，先停止采集
            if self.timer.isActive():
                self.handle_stream(False)
                self.camera_control.stream_btn.setChecked(False)
            
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

    def _on_frame_captured(self, event):
        """处理帧捕获事件"""
        frame = event.data.get("frame")
        if frame is not None:
            self.process_and_display_frame(frame)

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
