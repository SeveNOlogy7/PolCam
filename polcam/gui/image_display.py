"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtCore, QtGui
import numpy as np
import cv2
from typing import List
from polcam.core.image_processor import ImageProcessor
from polcam.gui.styles import Styles
from ..core.processing_module import ProcessingMode
from ..core.image_plotter import ImagePlotter
from ..core.camera_module import CameraType

# 彩色相机可用模式（全部8种）
COLOR_MODES = [
    ProcessingMode.RAW, ProcessingMode.SINGLE_COLOR, ProcessingMode.SINGLE_GRAY,
    ProcessingMode.MERGED_COLOR, ProcessingMode.MERGED_GRAY,
    ProcessingMode.QUAD_COLOR, ProcessingMode.QUAD_GRAY, ProcessingMode.POLARIZATION,
]

# 黑白相机可用模式（5种，去掉彩色相关）
MONO_MODES = [
    ProcessingMode.RAW, ProcessingMode.SINGLE_GRAY,
    ProcessingMode.MERGED_GRAY, ProcessingMode.QUAD_GRAY, ProcessingMode.POLARIZATION,
]

# 普通彩色相机可用模式（3种）
NORMAL_COLOR_MODES = [
    ProcessingMode.RAW, ProcessingMode.MERGED_COLOR, ProcessingMode.MERGED_GRAY,
]

# 模式显示标签
MODE_LABELS = {
    ProcessingMode.RAW: "原始图像",
    ProcessingMode.SINGLE_COLOR: "单角度彩色",
    ProcessingMode.SINGLE_GRAY: "单角度灰度",
    ProcessingMode.MERGED_COLOR: "彩色图像",
    ProcessingMode.MERGED_GRAY: "灰度图像",
    ProcessingMode.QUAD_COLOR: "四角度彩色",
    ProcessingMode.QUAD_GRAY: "四角度灰度",
    ProcessingMode.POLARIZATION: "偏振度图像",
}

class ImageDisplay(QtWidgets.QWidget):
    # 添加鼠标位置信号
    cursorPositionChanged = QtCore.Signal(dict)
    
    def __init__(self):
        super().__init__()
        # 先初始化基本属性
        self.current_images = []      # 原始图像缓存列表
        self._current_canvas = None   # 当前显示画布缓存
        self.image_rect = None        # 图像在标签中的实际显示区域
        self.scale_factor = 1.0       # 图像缩放因子
        self.image_mode = None        # 当前显示模式
        self.quad_positions = []      # 四分图的四个区域位置
        self.cursor_enabled = False   # 游标模式启用状态
        self.cursor_info = None       # 游标信息
        self._active_modes = list(COLOR_MODES)  # 当前可用模式列表

        self.setup_ui()
        # 初始化时禁用控件
        self.enable_display_controls(False)
        self.show_default_image()
        
    def setup_ui(self):
        # 创建主布局
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)  # 设置内边距
        
        # 先创建图像显示区域（确保image_label最先创建）
        self.image_label = QtWidgets.QLabel()
        self.image_label.setMinimumSize(640, 480)
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)  # 居中对齐
        self.image_label.setSizePolicy(                       # 设置大小策略
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
        
        # 显示模式选择
        self.display_mode = QtWidgets.QComboBox()
        Styles.apply_combobox_style(self.display_mode)
        self.display_mode.setFont(QtGui.QFont("", 11))
        self.display_mode.setMinimumHeight(30)
        self._populate_display_modes(COLOR_MODES)
        
        # 创建工具栏和控制器
        from .widgets.image_toolbar import ImageToolbar
        self.image_toolbar = ImageToolbar()
        
        # 添加到顶部布局
        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addWidget(self.display_mode)
        top_layout.addWidget(self.image_toolbar)
        
        # 按顺序添加到主布局
        layout.addLayout(top_layout)
        layout.addWidget(self.image_label)
        
        # 初始化工具栏控制器
        from ..core.image_toolbar_controller import ImageToolbarController
        self.toolbar_controller = ImageToolbarController(
            self.image_toolbar,
            self,
        )

        # 尺寸策略
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
        
        # 初始化工具栏控制器（移到最后）
        self.toolbar_controller.initialize()
        
    def enable_display_controls(self, enabled: bool):
        """启用或禁用显示控件
        
        Args:
            enabled (bool): True表示启用，False表示禁用
        """
        self.display_mode.setEnabled(enabled)
        self.image_toolbar.setEnabled(enabled)
        
    def is_display_controls_enabled(self) -> bool:
        """检查显示控件是否已启用

        Returns:
            bool: 显示控件是否已启用
        """
        return self.display_mode.isEnabled()

    def _populate_display_modes(self, modes):
        """根据模式列表填充 combo"""
        self.display_mode.blockSignals(True)
        self.display_mode.clear()
        self._active_modes = list(modes)
        self.display_mode.addItems([MODE_LABELS[m] for m in modes])
        self.display_mode.setCurrentIndex(0)
        self.display_mode.blockSignals(False)

    def set_camera_modes(self, camera_type=None):
        """根据相机类型更新可用显示模式列表

        Args:
            camera_type: CameraType 枚举值，None 表示恢复默认（全部偏振模式）
        """
        if camera_type == CameraType.MONO:
            modes = MONO_MODES
        elif camera_type == CameraType.NORMAL_COLOR:
            modes = NORMAL_COLOR_MODES
        else:
            modes = COLOR_MODES
        self._populate_display_modes(modes)

    def get_current_processing_mode(self) -> ProcessingMode:
        """获取当前 combo 对应的 ProcessingMode"""
        index = self.display_mode.currentIndex()
        if 0 <= index < len(self._active_modes):
            return self._active_modes[index]
        return ProcessingMode.RAW
        
    def resizeEvent(self, event: QtGui.QResizeEvent):
        """窗口大小变化时重新显示图像"""
        super().resizeEvent(event)
        # 如果有当前图像，则重新显示
        self.refresh_current_image()

    def _show_canvas(self, image: np.ndarray):
        """底层显示接口，处理图像缩放和实际显示
        注意：输入图像应该是BGR格式，函数内部会转换为RGB用于显示
        
        Args:
            image: BGR格式的图像数据
        """
        try:
            if image is None:
                return
                
            # 转换为QImage
            if len(image.shape) == 2:
                h, w = image.shape
                bytes_per_line = w
                qt_image = QtGui.QImage(image.data, w, h, 
                                      bytes_per_line, QtGui.QImage.Format_Grayscale8)
            else:
                # 只在这里转换为RGB用于显示
                display_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                h, w = display_image.shape[:2]
                bytes_per_line = 3 * w
                qt_image = QtGui.QImage(display_image.data.tobytes(), w, h, 
                                      bytes_per_line, QtGui.QImage.Format_RGB888)
            
            # 获取显示区域大小
            label_size = self.image_label.size()
            label_w, label_h = label_size.width(), label_size.height()
            
            # 计算图像和显示区域的宽高比
            image_ratio = w / h
            label_ratio = label_w / label_h
            
            # 根据宽高比决定如何缩放
            if image_ratio > label_ratio:
                # 图像更宽，以宽度为准
                new_w = label_w
                new_h = int(label_w / image_ratio)
            else:
                # 图像更高，以高度为准
                new_h = label_h
                new_w = int(label_h * image_ratio)
            
            # 创建QPixmap并缩放
            pixmap = QtGui.QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                new_w, new_h,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            
            # 更新显示
            self.image_label.setPixmap(scaled_pixmap)
            
        except Exception as e:
            print(f"图像显示错误: {e}")

    def show_image(self, image: np.ndarray):
        """外部图像显示接口
        
        Args:
            image: BGR格式的图像数据
        """
        if image is None:
            return
            
        # 保存原始图像的副本
        self.current_images = [image.copy()] if isinstance(image, np.ndarray) else []
        # 保存当前画布
        self._current_canvas = image.copy()
        
        # 显示图像
        self._show_canvas(self._current_canvas)

    def to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """将彩色图像转换为灰度图像"""
        if len(image.shape) == 2:
            return image
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def show_quad_view(self, images: List[np.ndarray], gray: bool = False):
        """四角度视图显示接口"""
        # 保存原始图像列表的副本
        self.current_images = [img.copy() for img in images if img is not None]
        
        if gray:
            images = [self.to_grayscale(img) for img in images]
            images = [cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) for img in images]
                
        titles = ['0 deg', '45 deg', '90 deg', '135 deg']
        canvas, self.quad_positions, self.quad_size = ImagePlotter.create_quad_canvas(images, titles)
        
        # 更新画布缓存
        self._current_canvas = canvas.copy()
        
        # 显示画布
        self._show_canvas(self._current_canvas)

    def show_polarization_quad_view(self, image: np.ndarray, 
                                  dolp: np.ndarray, aolp: np.ndarray, 
                                  docp: np.ndarray):
        """显示偏振分析的四视图"""
        # 保存原始图像列表的副本
        self.current_images = [img.copy() for img in [image, dolp, aolp, docp] if img is not None]
        
        dolp_colored, aolp_colored, docp_colored = ImageProcessor.colormap_polarization(
            dolp, aolp, docp)
            
        images = [image, dolp_colored, aolp_colored, docp_colored]
        
        titles = ['IMAGE', 'DOLP', 'AOLP', 'DOCP']
        canvas, self.quad_positions, self.quad_size = ImagePlotter.create_quad_canvas(images, titles)
        
        # 更新画布缓存
        self._current_canvas = canvas.copy()
        
        # 显示画布
        self._show_canvas(self._current_canvas)

    def show_default_image(self):
        """显示默认的帮助图像"""
        default_image = ImagePlotter.get_default_image()
        if default_image is not None:
            self.show_image(default_image)
            
    def set_cursor_mode(self, enabled: bool):
        """设置游标模式"""
        self.cursor_enabled = enabled
        if enabled:
            self.image_label.setCursor(QtCore.Qt.CrossCursor)
            self.image_label.setMouseTracking(True)
            self.image_label.mouseMoveEvent = self._on_mouse_move
        else:
            self.image_label.setCursor(QtCore.Qt.ArrowCursor)
            self.image_label.setMouseTracking(False)
            self.image_label.mouseMoveEvent = None
            self.cursor_info = None
            
    def _on_mouse_move(self, event: QtGui.QMouseEvent):
        """处理鼠标移动事件"""
        if not self.cursor_enabled or not self.current_images:  # 修改判断条件
            return
            
        # 获取图像实际显示区域
        pixmap = self.image_label.pixmap()
        if not pixmap:
            return
            
        # 计算图像显示区域
        label_size = self.image_label.size()
        pixmap_size = pixmap.size()
        
        # 计算图像在标签中的实际位置和大小
        if label_size.width() / label_size.height() > pixmap_size.width() / pixmap_size.height():
            # 高度适配
            display_height = label_size.height()
            display_width = pixmap_size.width() * display_height / pixmap_size.height()
            x_offset = (label_size.width() - display_width) / 2
            y_offset = 0
        else:
            # 宽度适配
            display_width = label_size.width()
            display_height = pixmap_size.height() * display_width / pixmap_size.width()
            x_offset = 0
            y_offset = (label_size.height() - display_height) / 2
            
        # 计算鼠标在图像上的实际位置
        mouse_x = event.x() - x_offset
        mouse_y = event.y() - y_offset
        
        if (mouse_x < 0 or mouse_x >= display_width or 
            mouse_y < 0 or mouse_y >= display_height):
            return
            
        # 转换为原始图像坐标
        img_x = int(mouse_x * self._current_canvas.shape[1] / display_width)
        img_y = int(mouse_y * self._current_canvas.shape[0] / display_height)
        
        # 确保坐标在图像范围内
        img_x = max(0, min(img_x, self._current_canvas.shape[1] - 1))
        img_y = max(0, min(img_y, self._current_canvas.shape[0] - 1))
        
        # 获取像素值
        if self.is_quad_view_mode():
            # 四分图模式处理
            quad_index = self.get_quad_index(img_x, img_y)
            if quad_index is not None and quad_index < len(self.current_images):
                # 获取当前区域的图像
                current_image = self.current_images[quad_index]
                
                # 计算在四分区中的相对位置
                quad_y, quad_x = self.quad_positions[quad_index]
                cursor_quad_position = (img_x - quad_x, img_y - quad_y)
                
                # 获取所有区域相同位置的像素值
                pixel_values = []
                rel_x, rel_y = cursor_quad_position
                for img in self.current_images:
                    if len(img.shape) == 3:
                        b, g, r = img[rel_y, rel_x]
                        pixel_values.append((r, g, b))
                    else:
                        gray = img[rel_y, rel_x]
                        pixel_values.append(gray)
                
                # 根据显示模式决定像素信息键名
                mode = self.get_current_processing_mode()
                if mode == ProcessingMode.POLARIZATION:
                    info_key = 'quad_pol_values'
                elif mode == ProcessingMode.QUAD_COLOR:
                    info_key = 'quad_rgb_values'
                else:
                    info_key = 'quad_gray_values'
                    
                # 构建像素信息
                pixel_info = {info_key: pixel_values}
                
                # 游标信息
                self.cursor_info = {
                    'position': (img_x, img_y),
                    'mode': 'quad',
                    'quad_index': quad_index,
                    'cursor_quad_position': cursor_quad_position,
                    **pixel_info
                }
            else:
                return
                
        else:
            # 单图模式处理
            current_image = self.current_images[0]
            if len(current_image.shape) == 3:
                b, g, r = current_image[img_y, img_x]
                pixel_info = {'rgb': (r, g, b)}
            else:
                gray = current_image[img_y, img_x]
                pixel_info = {'gray': gray}
                
            # 游标信息
            self.cursor_info = {
                'position': (img_x, img_y),
                'mode': 'single',
                'quad_index': None,
                'cursor_quad_position': None,
                **pixel_info
            }
        
        # 四分图模式下绘制游标
        if self.is_quad_view_mode():
            if self._current_canvas is not None:
                canvas = self._current_canvas.copy()
                display_size = (self.image_label.width(), self.image_label.height())
                canvas = ImagePlotter.draw_quad_cursors(
                    canvas, self.cursor_info, self.quad_positions, 
                    self.quad_size, display_size
                )
                self._show_canvas(canvas)  # 使用_show_canvas替代show_image
        
        # 发送信号
        self.cursorPositionChanged.emit(self.cursor_info)


    def is_quad_view_mode(self):
        """检查当前是否为四分图显示模式
        Returns:
            bool: 是否为四分图模式
        """
        current_index = self.get_current_processing_mode()
        return current_index in [ProcessingMode.QUAD_COLOR, ProcessingMode.QUAD_GRAY, ProcessingMode.POLARIZATION]
    
    def get_quad_index(self, img_x: int, img_y: int) -> int:
        """获取四分图区域索引
        
        Args:
            img_x: 图像中的x坐标
            img_y: 图像中的y坐标
            
        Returns:
            int: 四分图区域索引(0-3)，如果不在任何区域内则返回None
        """
        if not self.quad_positions or not self.quad_size:
            return None
            
        quad_height, quad_width = self.quad_size
        
        # quad_positions = [(0, 0), (0, w), (h, 0), (h, w)]
        # [0, 1 , 2 , 3]
        for i, (pos_y, pos_x) in enumerate(self.quad_positions):
            # 检查点是否在当前四分图区域内
            if (pos_x <= img_x < pos_x + quad_width and 
                pos_y <= img_y < pos_y + quad_height):
                return i
                
        return None

    def refresh_current_image(self):
        """刷新当前显示"""
        if self._current_canvas is not None:
            # 优先使用当前画布进行刷新
            self._show_canvas(self._current_canvas)
        elif self.current_images:  # 修改判断条件
            # 如果没有画布缓存，使用第一张原始图像
            self.show_image(self.current_images[0])
