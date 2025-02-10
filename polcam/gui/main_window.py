"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtCore, QtGui
import time
import numpy as np
import concurrent.futures
from ..core.camera import Camera
from ..core.image_processor import ImageProcessor
from .camera_control import CameraControl
from .image_display import ImageDisplay
from .status_indicator import StatusIndicator
from .styles import Styles

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 设置全局字体
        app = QtWidgets.QApplication.instance()
        Styles.setup_application_font(app)
        
        self.setWindowTitle("偏振相机控制系统")
        self.setup_ui()
        
        self.camera = Camera()
        self.image_processor = ImageProcessor()
        self.setup_connections()
        self.setup_statusbar()
        self.current_frame = None      # 原始帧缓存
        self.raw_changed = False      # 原始帧改变标志
        self.params_changed = False   # 参数改变标志
        self._cache = {              # 处理结果缓存
            'color_images': None,     # 解码后的彩色图像
            'color_image': None,      # 合成的彩色图像
            'gray_images': None,      # 灰度图像缓存
            'dolp': None,            # 偏振度缓存
            'aolp': None,            # 偏振角缓存
            'docp': None             # 圆偏振度缓存
        }
        
        # 设置关闭事件处理标志
        self.close_flag = False

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
        self.camera_control.wb_auto_changed.connect(self._handle_wb_auto_changed)
        
        # 添加显示模式变化和白平衡状态变化的信号处理
        self.image_display.display_mode.currentIndexChanged.connect(
            lambda: self.process_and_display_frame(self.current_frame, reprocess=True)
        )
        
        # 修改单次按钮连接
        self.camera_control.exposure_once.clicked.connect(self._handle_exposure_once)
        self.camera_control.gain_once.clicked.connect(self._handle_gain_once)
        self.camera_control.wb_once.clicked.connect(self._handle_wb_once)

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
            # 断开前先停止连续采集
            if self.timer.isActive():
                self.handle_stream(False)  # 停止连续采集
                self.camera_control.stream_btn.setChecked(False)  # 更新按钮状态
            self.camera.disconnect()
            self.camera_control.set_connected(False)
            self.status_indicator.setEnabled(False)
            self.status_indicator.setStatus(False)
            self.status_label.setText("就绪")
            self.camera_info.clear()

    def _update_auto_parameters(self):
        """更新自动参数的显示值，并标记参数改变"""
        params_changed = False
        if self.camera_control.exposure_auto.isChecked():
            current_exposure = self.camera.get_exposure_time()
            if current_exposure != self.camera_control.exposure_spin.value():
                self.camera_control.update_exposure_value(current_exposure)
                params_changed = True
            
        if self.camera_control.gain_auto.isChecked():
            current_gain = self.camera.get_gain()
            if current_gain != self.camera_control.gain_spin.value():
                self.camera_control.update_gain_value(current_gain)
                params_changed = True
                
        if params_changed:
            self.params_changed = True
            self._clear_cache()

    def _clear_cache(self, full=False):
        """清除缓存
        Args:
            full: 是否完全清除。True则清除所有缓存，False只清除依赖于参数的缓存
        """
        if full:
            self._cache = {key: None for key in self._cache}
        else:
            # 只清除依赖于相机参数的缓存
            self._cache.update({
                'color_images': None,
                'color_image': None
            })

    def handle_capture(self):
        if not self.camera or not hasattr(self.camera, 'camera'):
            QtWidgets.QMessageBox.warning(self, "错误", "相机未连接")
            return
        
        # 禁用采集按钮
        self.camera_control.capture_btn.setEnabled(False)
        self.camera_control.stream_btn.setEnabled(False)
            
        # 开始计时
        t_start = time.perf_counter()
        
        try:
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
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "错误", f"获取图像失败: {str(e)}")
        finally:
            # 重新启用采集按钮
            self.camera_control.capture_btn.setEnabled(True)
            self.camera_control.stream_btn.setEnabled(True)

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

    def process_and_display_frame(self, frame, reprocess=False):
        if frame is None:
            return
            
        try:
            # 检查帧是否改变
            if frame is not self.current_frame:
                self.current_frame = frame
                self.raw_changed = True
                self._clear_cache(full=True)
            
            mode = self.image_display.display_mode.currentIndex()
            
            if mode == 0:  # 原始图像
                self.image_display.show_image(frame)
                return
                
            # 需要重新处理的情况
            need_reprocess = (
                self.raw_changed or      # 原始帧改变
                self.params_changed or   # 参数改变
                reprocess or             # 强制重新处理
                self._cache['color_images'] is None  # 缓存不存在
            )
            
            if need_reprocess:
                # 解码彩色图像
                self._cache['color_images'] = self.image_processor.demosaic_polarization(frame)
                
                # 应用白平衡处理
                if self.camera.is_wb_auto():
                    # 对第一个角度图像执行自动白平衡以获取增益系数
                    self._cache['color_images'][0] = self.image_processor.auto_white_balance(
                        self._cache['color_images'][0]
                    )
                    # 对其他角度图像应用相同的白平衡系数
                    for i in range(1, 4):
                        self._cache['color_images'][i] = self.image_processor.apply_white_balance(
                            self._cache['color_images'][i]
                        )
                
                # 计算合成彩色图像
                self._cache['color_image'] = np.mean(
                    self._cache['color_images'], axis=0
                ).astype(np.uint8)
                
                # 重置状态标志
                self.raw_changed = False
                self.params_changed = False
            
            # 根据显示模式处理
            if mode == 1:  # 单角度彩色
                self.image_display.show_image(self._cache['color_images'][0])
            elif mode == 2:  # 单角度灰度
                if self._cache.get('gray_images') is None:
                    self._cache['gray_images'] = [
                        self.image_processor.to_grayscale(img) 
                        for img in self._cache['color_images']
                    ]
                self.image_display.show_image(self._cache['gray_images'][0])
            elif mode == 3:  # 彩色图像
                self.image_display.show_image(self._cache['color_image'])
            elif mode == 4:  # 灰度图像
                if self._cache.get('gray_image') is None:
                    self._cache['gray_image'] = self.image_processor.to_grayscale(
                        self._cache['color_image']
                    )
                self.image_display.show_image(self._cache['gray_image'])
            elif mode == 5:  # 四角度彩色
                self.image_display.show_quad_view(self._cache['color_images'], gray=False)
            elif mode == 6:  # 四角度灰度
                if self._cache.get('gray_images') is None:
                    self._cache['gray_images'] = [
                        self.image_processor.to_grayscale(img) 
                        for img in self._cache['color_images']
                    ]
                self.image_display.show_quad_view(self._cache['gray_images'], gray=True)
            elif mode == 7:  # 偏振分析
                # 仅在需要时计算偏振参数
                if (self._cache['dolp'] is None or 
                    self._cache['aolp'] is None or 
                    self._cache['docp'] is None):
                    self._cache['dolp'], self._cache['aolp'], self._cache['docp'] = (
                        self.image_processor.calculate_polarization_parameters(
                            self._cache['color_images']
                        )
                    )
                self.image_display.show_polarization_quad_view(
                    self._cache['color_image'], 
                    self._cache['dolp'],
                    self._cache['aolp'], 
                    self._cache['docp']
                )
                    
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
            if self.camera and hasattr(self.camera, 'camera') and self.camera.camera is not None:
                self.camera.disconnect()
                
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
