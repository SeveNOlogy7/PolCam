"""
MIT License
Copyright (c) 2024 PolCam Contributors
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtCore
from ..core.camera import Camera
from ..core.image_processor import ImageProcessor
from .camera_control import CameraControl
from .image_display import ImageDisplay

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("偏振相机控制系统")
        self.setup_ui()
        
        self.camera = Camera()
        self.image_processor = ImageProcessor()
        self.setup_connections()

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

    def handle_connect(self, connect: bool):
        if connect:
            if self.camera.connect():
                self.camera_control.set_connected(True)
                # 初始化相机参数，确保使用浮点数
                self.camera.set_exposure_auto(False)
                self.camera.set_exposure_time(10000.0)  # 10ms, 使用浮点数
                self.camera.set_gain_auto(False)
                self.camera.set_gain(0.0)  # 使用浮点数
        else:
            self.camera.disconnect()
            self.camera_control.set_connected(False)

    def handle_capture(self):
        if not self.camera or not hasattr(self.camera, 'camera'):
            QtWidgets.QMessageBox.warning(self, "错误", "相机未连接")
            return
            
        frame = self.camera.get_frame()
        if frame is not None:
            try:
                self.process_and_display_frame(frame)
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
        frame = self.camera.get_frame()
        if frame is not None:
            self.process_and_display_frame(frame)

    def process_and_display_frame(self, frame):
        try:
            color_images, gray_images = self.image_processor.demosaic_polarization(frame)
            dolp = self.image_processor.calculate_polarization_degree(gray_images)
            self.image_display.update_images(frame, color_images, gray_images, dolp)
        except Exception as e:
            raise Exception(f"图像处理失败: {e}")
