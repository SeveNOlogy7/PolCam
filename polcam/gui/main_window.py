"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtCore
import time
import numpy as np
from ..core.camera import Camera
from ..core.image_processor import ImageProcessor
from .camera_control import CameraControl
from .image_display import ImageDisplay
from .status_indicator import StatusIndicator

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("偏振相机控制系统")
        self.setup_ui()
        
        self.camera = Camera()
        self.image_processor = ImageProcessor()
        self.setup_connections()
        self.setup_statusbar()
        self.current_frame = None  # 添加原始帧缓存

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
        self.camera_control.wb_auto_changed.connect(self.camera.set_balance_white_auto)
        
        # 添加显示模式变化的信号处理
        self.image_display.display_mode.currentIndexChanged.connect(
            lambda: self.process_and_display_frame(self.current_frame, reprocess=True)
        )

    def setup_statusbar(self):
        # 创建状态栏
        self.statusBar().setFixedHeight(24)
        
        # 添加状态指示灯
        self.status_indicator = StatusIndicator()
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
            success, error_msg = self.camera.connect()
            if success:
                self.camera_control.set_connected(True)
                self.status_indicator.setEnabled(True)
                self.status_indicator.setStatus(True)
                self.status_label.setText("相机已连接")
                # 获取并显示相机信息
                self.camera_info.setText("MER2-503-23GC-POL")
                
                # 初始化相机参数 - 使用相机当前值
                self.camera.set_exposure_auto(False)
                self.camera.set_gain_auto(False)
                
                # 更新控制面板显示值
                self.camera_control.update_exposure_value(self.camera.get_last_exposure())
                self.camera_control.update_gain_value(self.camera.get_last_gain())
            else:
                # 连接失败，恢复按钮状态和指示器状态
                self.camera_control.connect_btn.setChecked(False)
                self.camera_control.set_connected(False)
                self.status_indicator.setEnabled(False)
                self.status_indicator.setStatus(False)
                self.status_label.setText(error_msg)
                self.camera_info.clear()
        else:
            self.camera.disconnect()
            self.camera_control.set_connected(False)
            self.status_indicator.setEnabled(False)
            self.status_indicator.setStatus(False)
            self.status_label.setText("就绪")
            self.camera_info.clear()

    def _update_auto_parameters(self):
        """更新自动参数的显示值"""
        if self.camera_control.exposure_auto.isChecked():
            current_exposure = self.camera.get_exposure_time()
            self.camera_control.update_exposure_value(current_exposure)
            
        if self.camera_control.gain_auto.isChecked():
            current_gain = self.camera.get_gain()
            self.camera_control.update_gain_value(current_gain)

    def handle_capture(self):
        if not self.camera or not hasattr(self.camera, 'camera'):
            QtWidgets.QMessageBox.warning(self, "错误", "相机未连接")
            return
            
        # 开始计时
        t_start = time.perf_counter()
        
        frame = self.camera.get_frame()
        if frame is not None:
            # 记录采集时间
            t_capture = time.perf_counter() - t_start
            
            try:
                # 图像处理开始计时
                t_proc_start = time.perf_counter()
                self.process_and_display_frame(frame)
                # 记录处理时间
                t_proc = time.perf_counter() - t_proc_start
                
                self._update_auto_parameters()  # 更新自动参数值
                
                # 更新状态栏时间信息
                self.time_label.setText(
                    f"采集: {t_capture*1000:.1f}ms | 处理: {t_proc*1000:.1f}ms"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "错误", f"处理图像失败: {e}")
        else:
            QtWidgets.QMessageBox.warning(self, "错误", "获取图像失败")

    def handle_stream(self, start: bool):
        if start:
            self.camera.start_streaming()
            self.timer.start(33)  # ~30 FPS
        else:
            self.camera.stop_streaming()
            self.timer.stop()

    def update_frame(self):
        t_start = time.perf_counter()
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

    def process_and_display_frame(self, frame, reprocess=False):
        if frame is None:
            return
            
        try:
            is_new_frame = frame is not self.current_frame
            self.current_frame = frame
            mode = self.image_display.display_mode.currentIndex()
            
            if mode == 0:  # 原始图像
                self.image_display.show_image(frame)
            else:
                # 在新帧到来或需要重新处理时进行解码
                if is_new_frame or reprocess or not hasattr(self, '_color_images'):
                    self._color_images, self._gray_images = (
                        self.image_processor.demosaic_polarization(frame)
                    )
                    # 计算合成图像
                    self._color_image = np.mean(self._color_images, axis=0).astype(np.uint8)
                    self._gray_image = np.mean(self._gray_images, axis=0).astype(np.uint8)
                    # 计算偏振参数
                    self._dolp, self._aolp, self._docp = (
                        self.image_processor.calculate_polarization_parameters(
                            self._gray_images
                        )
                    )
                
                if mode == 1:  # 单角度彩色
                    self.image_display.show_image(self._color_images[0])
                elif mode == 2:  # 单角度灰度
                    self.image_display.show_image(self._gray_images[0])
                elif mode == 3:  # 彩色图像
                    self.image_display.show_image(self._color_image)
                elif mode == 4:  # 灰度图像
                    self.image_display.show_image(self._gray_image)
                elif mode == 5:  # 四角度视图
                    self.image_display.show_quad_view(self._color_images)
                elif mode == 6:  # 偏振分析
                    self.image_display.show_polarization_quad_view(
                        self._color_image, self._dolp, self._aolp, self._docp
                    )
                    
        except Exception as e:
            raise Exception(f"图像处理失败: {e}")
