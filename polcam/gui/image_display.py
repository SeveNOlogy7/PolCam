"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtCore, QtGui
import numpy as np
import cv2
from typing import List, Optional, Tuple
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
    # 缩放交互信号
    zoomClickRequested = QtCore.Signal(int, int)            # (sensor_x, sensor_y)
    zoomAreaRequested = QtCore.Signal(int, int, int, int)   # (sensor_x, sensor_y, w, h)
    zoomAreaPreview = QtCore.Signal(int, int, int, int)     # 拖拽中实时预览 (sensor_x, sensor_y, w, h)

    def __init__(self):
        super().__init__()
        # 先初始化基本属性
        self.current_images = []      # 原始图像缓存列表
        self._current_canvas = None   # 当前显示源画布缓存（完整画布）
        self.image_rect = None        # 图像在标签中的实际显示区域
        self.scale_factor = 1.0       # 图像缩放因子
        self.image_mode = None        # 当前显示模式
        self.quad_positions = []      # 四分图的四个区域位置
        self.quad_size = None         # 四分图单区域尺寸
        self._display_content_kind = 'single'  # 'single' | 'quad' | 'polarization'
        self._quad_titles = []
        self._quad_title_labels = []
        self._quad_gray_mode = False
        self.cursor_enabled = False   # 游标模式启用状态
        self.cursor_info = None       # 游标信息
        self._active_modes = list(COLOR_MODES)  # 当前可用模式列表
        self._software_view_roi = None         # 当前软件视图窗口: (x, y, width, height)
        self._zoom_coordinate_space = 'hardware'  # 'hardware' | 'canvas'
        self._max_zoom = 1000.0
        # 缩放交互相关
        self._interaction_mode = 'none'     # 'none' | 'cursor' | 'zoom_in' | 'zoom_out' | 'zoom_area'
        self._rubber_band = None            # QRubberBand 选区
        self._rubber_band_origin = None     # 橡皮筋起始点
        self._current_roi = None            # 当前 ROI: (offset_x, offset_y, width, height)
        self._sensor_size = None            # 传感器尺寸: (width, height)
        self._rubber_band_clamp_rect = None # QRect: 四分图模式下橡皮筋的显示空间钳位边界

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
        self._create_quad_title_labels()
        
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

    def _create_quad_title_labels(self):
        """创建四分图标题覆盖控件。"""
        self._quad_title_labels = []
        for _ in range(4):
            label = QtWidgets.QLabel(self.image_label)
            label.setFont(Styles.get_font(Styles.QUAD_TITLE_OVERLAY_FONT_SIZE))
            label.setStyleSheet(Styles.QUAD_TITLE_OVERLAY_STYLE)
            label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
            label.hide()
            self._quad_title_labels.append(label)

    def _hide_quad_title_labels(self):
        """隐藏四分图标题覆盖控件。"""
        for label in self._quad_title_labels:
            label.hide()

    def _update_quad_title_labels(self, canvas: Optional[np.ndarray] = None):
        """根据当前显示几何更新四分图标题覆盖控件。"""
        has_quad_titles = (
            self.is_quad_view_mode()
            and len(self._quad_titles) == 4
            and len(self._quad_title_labels) == 4
            and bool(self.quad_positions)
            and self.quad_size is not None
        )
        if not has_quad_titles:
            self._hide_quad_title_labels()
            return

        geom = self._get_display_geometry()
        if geom is None:
            self._hide_quad_title_labels()
            return

        if canvas is None:
            canvas = self._compose_current_view_canvas()
            if canvas is None:
                self._hide_quad_title_labels()
                return

        x_offset, y_offset, display_width, display_height = geom
        canvas_h, canvas_w = canvas.shape[:2]

        for label, title, (quad_y, quad_x) in zip(self._quad_title_labels, self._quad_titles, self.quad_positions):
            label.setText(title)
            label.adjustSize()

            left = int(quad_x * display_width / canvas_w + x_offset)
            top = int(quad_y * display_height / canvas_h + y_offset)
            label.move(
                left + Styles.QUAD_TITLE_OVERLAY_X_OFFSET,
                top + Styles.QUAD_TITLE_OVERLAY_Y_OFFSET,
            )
            label.show()
            label.raise_()
        
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

    def set_processing_mode(self, mode: ProcessingMode) -> bool:
        """设置当前显示模式。"""
        try:
            index = self._active_modes.index(mode)
        except ValueError:
            self.display_mode.setCurrentIndex(0)
            return False

        self.display_mode.setCurrentIndex(index)
        return True

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

            image = np.ascontiguousarray(image)
                
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

    def has_display_image(self) -> bool:
        """当前是否有可用于显示或软件缩放的图像。"""
        return bool(self.current_images) or (
            isinstance(self._current_canvas, np.ndarray) and self._current_canvas.size > 0
        )

    def set_zoom_coordinate_space(self, coordinate_space: str):
        """设置缩放交互的坐标空间。"""
        if coordinate_space not in ('hardware', 'canvas'):
            raise ValueError(f"Unsupported coordinate space: {coordinate_space}")
        self._zoom_coordinate_space = coordinate_space

    def set_max_zoom(self, max_zoom: float):
        """设置软件缩放允许的最大放大倍率。"""
        self._max_zoom = max(1.0, float(max_zoom))

    def get_max_zoom(self) -> float:
        """获取当前软件缩放最大放大倍率。"""
        return self._max_zoom

    def _constrain_view_size_to_max_zoom(self, width: int, height: int) -> Tuple[int, int]:
        """根据最大放大倍率限制当前视图窗口尺寸。"""
        full_roi = self._get_full_view_roi()
        if full_roi is None:
            return (width, height)

        _, _, full_w, full_h = full_roi
        min_area = (full_w * full_h) / self._max_zoom
        if width > 0 and height > 0 and width * height < min_area:
            scale = (min_area / (width * height)) ** 0.5
            width = int(width * scale)
            height = int(height * scale)

        width = max(1, min(width, full_w))
        height = max(1, min(height, full_h))
        return (width, height)

    def _get_full_view_roi(self) -> Optional[Tuple[int, int, int, int]]:
        """返回完整源画布对应的视图窗口。"""
        if not self.has_display_image():
            return None

        if self.is_quad_view_mode() and self.current_images:
            source_h, source_w = self.current_images[0].shape[:2]
            return (0, 0, source_w, source_h)

        canvas_h, canvas_w = self._current_canvas.shape[:2]
        return (0, 0, canvas_w, canvas_h)

    def _get_current_view_roi(self) -> Optional[Tuple[int, int, int, int]]:
        """返回当前软件缩放视图窗口。"""
        full_roi = self._get_full_view_roi()
        if full_roi is None:
            return None

        if self._software_view_roi is None:
            return full_roi

        full_x, full_y, full_w, full_h = full_roi
        view_x, view_y, view_w, view_h = self._software_view_roi

        view_w = max(1, min(view_w, full_w))
        view_h = max(1, min(view_h, full_h))
        view_x = max(full_x, min(view_x, full_w - view_w))
        view_y = max(full_y, min(view_y, full_h - view_h))
        return (view_x, view_y, view_w, view_h)

    def is_software_zoom_active(self) -> bool:
        """当前软件视图是否已缩放到完整画布之外。"""
        full_roi = self._get_full_view_roi()
        view_roi = self._get_current_view_roi()
        return full_roi is not None and view_roi is not None and view_roi != full_roi

    def get_software_zoom_ratio(self) -> float:
        """返回当前软件缩放倍率。"""
        full_roi = self._get_full_view_roi()
        view_roi = self._get_current_view_roi()
        if full_roi is None or view_roi is None or view_roi[2] <= 0 or view_roi[3] <= 0:
            return 1.0

        return (full_roi[2] * full_roi[3]) / (view_roi[2] * view_roi[3])

    def _crop_to_current_view(self, image: np.ndarray) -> np.ndarray:
        """根据当前软件视图窗口裁切单张源图像。"""
        view_roi = self._get_current_view_roi()
        if view_roi is None:
            return image

        view_x, view_y, view_w, view_h = view_roi
        return np.ascontiguousarray(image[view_y:view_y + view_h, view_x:view_x + view_w])

    def _compose_current_view_canvas(self) -> Optional[np.ndarray]:
        """按当前视图窗口生成实际显示画布。"""
        if not self.has_display_image():
            return None

        has_valid_quad_source = (
            self.is_quad_view_mode()
            and len(self.current_images) == 4
            and len(self._quad_titles) == 4
        )

        if has_valid_quad_source:
            cropped_images = [self._crop_to_current_view(image) for image in self.current_images]

            if self._display_content_kind == 'polarization' and len(cropped_images) == 4:
                image, dolp, aolp, docp = cropped_images
                dolp_colored, aolp_colored, docp_colored = ImageProcessor.colormap_polarization(
                    dolp, aolp, docp
                )
                images = [image, dolp_colored, aolp_colored, docp_colored]
            else:
                images = cropped_images
                if self._quad_gray_mode:
                    images = [self.to_grayscale(img) for img in images]
                    images = [cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) for img in images]

            canvas, self.quad_positions, self.quad_size = ImagePlotter.create_quad_canvas(
                images,
                self._quad_titles,
                draw_titles=False,
            )
            return canvas

        if self.is_quad_view_mode():
            self.quad_positions = []
            self.quad_size = None

        if self._current_canvas is None:
            return None

        return self._crop_to_current_view(self._current_canvas)

    def _render_canvas(self, canvas: np.ndarray):
        """渲染已经组装完成的显示画布。"""
        if canvas is not None:
            self._show_canvas(canvas)
            self._update_quad_title_labels(canvas)

    def _render_current_view(self):
        """渲染当前软件视图。"""
        canvas = self._compose_current_view_canvas()
        if canvas is not None:
            self._render_canvas(canvas)

    def reset_software_view(self, refresh: bool = True) -> bool:
        """重置软件缩放视图到完整画布。"""
        full_roi = self._get_full_view_roi()
        if full_roi is None:
            return False

        self._software_view_roi = full_roi
        if refresh:
            self.refresh_current_image()
        return True

    def apply_software_zoom_click(self, source_x: int, source_y: int,
                                  zoom_mode: str, zoom_factor: float = 1.5,
                                  min_size: int = 16) -> bool:
        """围绕指定源画布坐标执行软件放大/缩小。"""
        full_roi = self._get_full_view_roi()
        view_roi = self._get_current_view_roi()
        if full_roi is None or view_roi is None:
            return False

        _, _, full_w, full_h = full_roi
        _, _, view_w, view_h = view_roi

        if zoom_mode == 'zoom_in':
            new_w = max(min_size, int(view_w / zoom_factor))
            new_h = max(min_size, int(view_h / zoom_factor))
            new_w, new_h = self._constrain_view_size_to_max_zoom(new_w, new_h)
        elif zoom_mode == 'zoom_out':
            new_w = min(full_w, int(view_w * zoom_factor))
            new_h = min(full_h, int(view_h * zoom_factor))
        else:
            return False

        new_x = int(source_x - new_w / 2)
        new_y = int(source_y - new_h / 2)
        new_x = max(0, min(new_x, full_w - new_w))
        new_y = max(0, min(new_y, full_h - new_h))

        self._software_view_roi = (new_x, new_y, new_w, new_h)
        self.refresh_current_image()
        return True

    def apply_software_zoom_area(self, source_x: int, source_y: int,
                                 width: int, height: int,
                                 min_size: int = 16) -> bool:
        """根据源画布选区执行软件区域放大。"""
        full_roi = self._get_full_view_roi()
        if full_roi is None:
            return False

        _, _, full_w, full_h = full_roi
        width = max(min_size, width)
        height = max(min_size, height)

        source_x = max(0, min(source_x, full_w - 1))
        source_y = max(0, min(source_y, full_h - 1))
        width = min(width, full_w - source_x)
        height = min(height, full_h - source_y)
        width, height = self._constrain_view_size_to_max_zoom(width, height)

        if width <= 0 or height <= 0:
            return False

        self._software_view_roi = (source_x, source_y, width, height)
        self.refresh_current_image()
        return True

    def show_image(self, image: np.ndarray):
        """外部图像显示接口
        
        Args:
            image: BGR格式的图像数据
        """
        if image is None:
            return
            
        # 保存原始图像的副本
        self.current_images = [image.copy()] if isinstance(image, np.ndarray) else []
        self._display_content_kind = 'single'
        self._quad_titles = []
        self._quad_gray_mode = False
        self.quad_positions = []
        self.quad_size = None
        # 保存当前画布
        self._current_canvas = image.copy()
        self._software_view_roi = self._get_full_view_roi()
        
        # 显示图像
        self._render_current_view()

    def to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """将彩色图像转换为灰度图像"""
        if len(image.shape) == 2:
            return image
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def show_quad_view(self, images: List[np.ndarray], gray: bool = False):
        """四角度视图显示接口"""
        # 保存原始图像列表的副本
        self.current_images = [img.copy() for img in images if img is not None]
        self._display_content_kind = 'quad'
        self._quad_titles = ['0 deg', '45 deg', '90 deg', '135 deg']
        self._quad_gray_mode = gray
        
        if gray:
            images = [self.to_grayscale(img) for img in images]
            images = [cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) for img in images]
                
        canvas, self.quad_positions, self.quad_size = ImagePlotter.create_quad_canvas(
            images,
            self._quad_titles,
            draw_titles=False,
        )
        
        # 更新画布缓存
        self._current_canvas = canvas.copy()
        self._software_view_roi = self._get_full_view_roi()
        
        # 显示画布
        self._render_current_view()

    def show_polarization_quad_view(self, image: np.ndarray, 
                                  dolp: np.ndarray, aolp: np.ndarray, 
                                  docp: np.ndarray):
        """显示偏振分析的四视图"""
        # 保存原始图像列表的副本
        self.current_images = [img.copy() for img in [image, dolp, aolp, docp] if img is not None]
        self._display_content_kind = 'polarization'
        self._quad_titles = ['IMAGE', 'DOLP', 'AOLP', 'DOCP']
        self._quad_gray_mode = False
        
        dolp_colored, aolp_colored, docp_colored = ImageProcessor.colormap_polarization(
            dolp, aolp, docp)
            
        images = [image, dolp_colored, aolp_colored, docp_colored]
        
        canvas, self.quad_positions, self.quad_size = ImagePlotter.create_quad_canvas(
            images,
            self._quad_titles,
            draw_titles=False,
        )
        
        # 更新画布缓存
        self._current_canvas = canvas.copy()
        self._software_view_roi = self._get_full_view_roi()
        
        # 显示画布
        self._render_current_view()

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

    # ==================== 缩放交互 ====================

    def set_interaction_mode(self, mode: str):
        """设置鼠标交互模式

        Args:
            mode: 'none' | 'cursor' | 'zoom_in' | 'zoom_out' | 'zoom_area'
        """
        self._interaction_mode = mode

        if mode == 'cursor':
            self.set_cursor_mode(True)
        elif mode in ('zoom_in', 'zoom_out', 'zoom_area'):
            # 关闭游标模式
            self.cursor_enabled = False
            self.cursor_info = None
            self.image_label.setCursor(QtCore.Qt.CrossCursor)
            self.image_label.setMouseTracking(False)
            self.image_label.mousePressEvent = self._on_zoom_mouse_press
            self.image_label.mouseReleaseEvent = self._on_zoom_mouse_release
            self.image_label.mouseMoveEvent = self._on_zoom_mouse_move
        else:
            # 'none' — 清除所有事件处理器
            self.set_cursor_mode(False)
            self.image_label.mousePressEvent = None
            self.image_label.mouseReleaseEvent = None
            self.image_label.mouseMoveEvent = None

    def update_roi_info(self, roi: tuple, sensor_size: tuple):
        """缓存当前 ROI 和传感器尺寸，供坐标映射使用

        Args:
            roi: (offset_x, offset_y, width, height)
            sensor_size: (sensor_width, sensor_height)
        """
        self._current_roi = roi
        self._sensor_size = sensor_size

    def _get_display_geometry(self) -> Optional[Tuple[float, float, float, float]]:
        """计算图像在 QLabel 中的显示区域

        Returns:
            (x_offset, y_offset, display_width, display_height) 或 None
        """
        pixmap = self.image_label.pixmap()
        if not pixmap:
            return None

        label_size = self.image_label.size()
        pixmap_size = pixmap.size()

        if label_size.width() / label_size.height() > pixmap_size.width() / pixmap_size.height():
            display_height = label_size.height()
            display_width = pixmap_size.width() * display_height / pixmap_size.height()
            x_offset = (label_size.width() - display_width) / 2
            y_offset = 0
        else:
            display_width = label_size.width()
            display_height = pixmap_size.height() * display_width / pixmap_size.width()
            x_offset = 0
            y_offset = (label_size.height() - display_height) / 2

        return (x_offset, y_offset, display_width, display_height)

    def _display_to_sensor_coords(self, display_x: int, display_y: int,
                                   clamp: bool = False) -> Optional[Tuple[int, int]]:
        """将 QLabel 显示坐标转换为传感器坐标

        非四分图模式: 显示坐标 → 归一化 (0~1) → ROI 相对 → 传感器绝对
        四分图模式: 显示坐标 → 画布像素 → 确定子图 → 子图内归一化 → ROI → 传感器

        Args:
            display_x, display_y: QLabel 内的鼠标坐标
            clamp: 若为 True，允许坐标超出图像显示区域，
                   结果钳位到传感器范围 [0, sensor_size]（用于区域放大外推）
        Returns:
            (sensor_x, sensor_y) 或 None（坐标在图像外且 clamp=False）
        """
        if self._zoom_coordinate_space == 'canvas':
            return self._display_to_source_coords(display_x, display_y, clamp=clamp)

        geom = self._get_display_geometry()
        if geom is None or self._current_roi is None:
            return None

        x_offset, y_offset, display_width, display_height = geom

        mouse_x = display_x - x_offset
        mouse_y = display_y - y_offset

        if mouse_x < 0 or mouse_x >= display_width or mouse_y < 0 or mouse_y >= display_height:
            if not clamp:
                return None

        if (self.is_quad_view_mode()
                and self._current_canvas is not None
                and self.quad_size):
            # 四分图路径: 在子图内归一化
            canvas_h, canvas_w = self._current_canvas.shape[:2]
            img_x = int(mouse_x * canvas_w / display_width)
            img_y = int(mouse_y * canvas_h / display_height)
            img_x = max(0, min(img_x, canvas_w - 1))
            img_y = max(0, min(img_y, canvas_h - 1))

            quad_index = self.get_quad_index(img_x, img_y)
            if quad_index is None:
                return None

            quad_y, quad_x = self.quad_positions[quad_index]
            quad_h, quad_w = self.quad_size
            rel_x = img_x - quad_x
            rel_y = img_y - quad_y

            norm_x = rel_x / quad_w
            norm_y = rel_y / quad_h
        else:
            # 非四分图路径（允许 norm 超出 [0,1] 以便外推）
            norm_x = mouse_x / display_width
            norm_y = mouse_y / display_height

        # 映射到当前 ROI 内的传感器坐标
        roi_ox, roi_oy, roi_w, roi_h = self._current_roi
        sensor_x = int(roi_ox + norm_x * roi_w)
        sensor_y = int(roi_oy + norm_y * roi_h)

        # 钳位到传感器范围
        if clamp and self._sensor_size:
            sensor_w, sensor_h = self._sensor_size
            sensor_x = max(0, min(sensor_x, sensor_w))
            sensor_y = max(0, min(sensor_y, sensor_h))

        return (sensor_x, sensor_y)

    def _display_to_source_coords(self, display_x: int, display_y: int,
                                  clamp: bool = False) -> Optional[Tuple[int, int]]:
        """将 QLabel 显示坐标映射到当前源画布坐标。"""
        geom = self._get_display_geometry()
        view_roi = self._get_current_view_roi()
        if geom is None or view_roi is None:
            return None

        x_offset, y_offset, display_width, display_height = geom
        mouse_x = display_x - x_offset
        mouse_y = display_y - y_offset

        if mouse_x < 0 or mouse_x >= display_width or mouse_y < 0 or mouse_y >= display_height:
            if not clamp:
                return None
            mouse_x = max(0.0, min(mouse_x, display_width))
            mouse_y = max(0.0, min(mouse_y, display_height))

        view_x, view_y, view_w, view_h = view_roi

        if self.is_quad_view_mode() and self.quad_size and self.quad_positions:
            rendered_canvas = self._compose_current_view_canvas()
            if rendered_canvas is None:
                return None

            rendered_canvas_h, rendered_canvas_w = rendered_canvas.shape[:2]
            rendered_x = int(mouse_x * rendered_canvas_w / display_width)
            rendered_y = int(mouse_y * rendered_canvas_h / display_height)
            rendered_x = max(0, min(rendered_x, rendered_canvas_w - 1))
            rendered_y = max(0, min(rendered_y, rendered_canvas_h - 1))

            quad_index = self.get_quad_index(rendered_x, rendered_y)
            if quad_index is None:
                return None

            quad_y, quad_x = self.quad_positions[quad_index]
            quad_h, quad_w = self.quad_size
            rel_x = rendered_x - quad_x
            rel_y = rendered_y - quad_y
            norm_x = rel_x / quad_w if quad_w else 0.0
            norm_y = rel_y / quad_h if quad_h else 0.0
            source_x = int(view_x + norm_x * view_w)
            source_y = int(view_y + norm_y * view_h)
            canvas_h, canvas_w = self.current_images[0].shape[:2]
        else:
            norm_x = mouse_x / display_width if display_width else 0.0
            norm_y = mouse_y / display_height if display_height else 0.0
            source_x = int(view_x + norm_x * view_w)
            source_y = int(view_y + norm_y * view_h)
            canvas_h, canvas_w = self._current_canvas.shape[:2]

        if clamp:
            source_x = max(0, min(source_x, canvas_w))
            source_y = max(0, min(source_y, canvas_h))
        else:
            source_x = max(0, min(source_x, canvas_w - 1))
            source_y = max(0, min(source_y, canvas_h - 1))

        return (source_x, source_y)

    def _get_quad_display_rect(self, display_x: int, display_y: int) -> Optional[QtCore.QRect]:
        """返回给定显示坐标所在子图的显示空间 QRect

        用于四分图模式下橡皮筋选区的钳位。

        Args:
            display_x, display_y: QLabel 内的鼠标坐标
        Returns:
            该子图在 QLabel 中的 QRect，或 None
        """
        geom = self._get_display_geometry()
        if geom is None or not self.quad_size:
            return None

        rendered_canvas = self._compose_current_view_canvas()
        if rendered_canvas is None:
            return None

        x_offset, y_offset, display_width, display_height = geom
        canvas_h, canvas_w = rendered_canvas.shape[:2]

        mouse_x = display_x - x_offset
        mouse_y = display_y - y_offset
        if mouse_x < 0 or mouse_x >= display_width or mouse_y < 0 or mouse_y >= display_height:
            return None

        img_x = int(mouse_x * canvas_w / display_width)
        img_y = int(mouse_y * canvas_h / display_height)
        img_x = max(0, min(img_x, canvas_w - 1))
        img_y = max(0, min(img_y, canvas_h - 1))

        quad_index = self.get_quad_index(img_x, img_y)
        if quad_index is None:
            return None

        quad_y, quad_x = self.quad_positions[quad_index]
        quad_h, quad_w = self.quad_size

        # 画布像素边界 → 显示空间边界
        disp_left   = int(quad_x * display_width / canvas_w + x_offset)
        disp_top    = int(quad_y * display_height / canvas_h + y_offset)
        disp_right  = int((quad_x + quad_w) * display_width / canvas_w + x_offset)
        disp_bottom = int((quad_y + quad_h) * display_height / canvas_h + y_offset)

        return QtCore.QRect(disp_left, disp_top,
                            disp_right - disp_left, disp_bottom - disp_top)

    def _on_zoom_mouse_press(self, event: QtGui.QMouseEvent):
        """处理缩放模式下的鼠标按下事件"""
        if event.button() != QtCore.Qt.LeftButton:
            return

        if self._interaction_mode == 'zoom_area':
            # 开始橡皮筋选区
            self._rubber_band_origin = event.pos()
            # 四分图模式下计算钳位矩形
            self._rubber_band_clamp_rect = None
            if self.is_quad_view_mode():
                self._rubber_band_clamp_rect = self._get_quad_display_rect(
                    event.x(), event.y()
                )
            if self._rubber_band is None:
                self._rubber_band = QtWidgets.QRubberBand(
                    QtWidgets.QRubberBand.Rectangle, self.image_label
                )
            self._rubber_band.setGeometry(QtCore.QRect(self._rubber_band_origin, QtCore.QSize()))
            self._rubber_band.show()

        elif self._interaction_mode in ('zoom_in', 'zoom_out'):
            # 单击缩放
            coords = self._display_to_sensor_coords(event.x(), event.y())
            if coords:
                self.zoomClickRequested.emit(coords[0], coords[1])

    def _on_zoom_mouse_move(self, event: QtGui.QMouseEvent):
        """处理缩放模式下的鼠标移动事件（橡皮筋拖拽）"""
        if self._interaction_mode == 'zoom_area' and self._rubber_band and self._rubber_band_origin:
            current_pos = event.pos()
            # 四分图模式下钳位到子图边界
            if self._rubber_band_clamp_rect is not None:
                cr = self._rubber_band_clamp_rect
                clamped_x = max(cr.left(), min(current_pos.x(), cr.right() - 1))
                clamped_y = max(cr.top(), min(current_pos.y(), cr.bottom() - 1))
                current_pos = QtCore.QPoint(clamped_x, clamped_y)
            rect = QtCore.QRect(self._rubber_band_origin, current_pos).normalized()
            self._rubber_band.setGeometry(rect)

            # 实时发送选区的传感器坐标预览（clamp=True 允许外推到传感器边界）
            if rect.width() >= 10 and rect.height() >= 10:
                tl = self._display_to_sensor_coords(rect.x(), rect.y(), clamp=True)
                br = self._display_to_sensor_coords(
                    rect.x() + rect.width(), rect.y() + rect.height(), clamp=True
                )
                if tl and br:
                    self.zoomAreaPreview.emit(tl[0], tl[1], br[0] - tl[0], br[1] - tl[1])

    def _on_zoom_mouse_release(self, event: QtGui.QMouseEvent):
        """处理缩放模式下的鼠标释放事件（区域放大完成）"""
        if event.button() != QtCore.Qt.LeftButton:
            return

        if self._interaction_mode == 'zoom_area' and self._rubber_band and self._rubber_band_origin:
            self._rubber_band.hide()

            end_pos = event.pos()
            # 四分图模式下钳位到子图边界
            if self._rubber_band_clamp_rect is not None:
                cr = self._rubber_band_clamp_rect
                clamped_x = max(cr.left(), min(end_pos.x(), cr.right() - 1))
                clamped_y = max(cr.top(), min(end_pos.y(), cr.bottom() - 1))
                end_pos = QtCore.QPoint(clamped_x, clamped_y)

            rect = QtCore.QRect(self._rubber_band_origin, end_pos).normalized()

            # 忽略过小的选区
            if rect.width() < 10 or rect.height() < 10:
                self._rubber_band_origin = None
                self._rubber_band_clamp_rect = None
                return

            # 转换矩形两角为传感器坐标（clamp=True 允许外推到传感器边界）
            top_left = self._display_to_sensor_coords(rect.x(), rect.y(), clamp=True)
            bottom_right = self._display_to_sensor_coords(
                rect.x() + rect.width(), rect.y() + rect.height(), clamp=True
            )

            if top_left and bottom_right:
                sx, sy = top_left
                ex, ey = bottom_right
                self.zoomAreaRequested.emit(sx, sy, ex - sx, ey - sy)

            self._rubber_band_origin = None
            self._rubber_band_clamp_rect = None
            
    def _on_mouse_move(self, event: QtGui.QMouseEvent):
        """处理鼠标移动事件"""
        if not self.cursor_enabled or not self.current_images:  # 修改判断条件
            return

        source_coords = self._display_to_source_coords(event.x(), event.y())
        if source_coords is None:
            return

        img_x, img_y = source_coords
        
        # 获取像素值
        if self.is_quad_view_mode():
            rendered_coords = self._display_to_render_canvas_coords(event.x(), event.y())
            if rendered_coords is None:
                return

            rendered_x, rendered_y = rendered_coords
            quad_index = self.get_quad_index(rendered_x, rendered_y)
            if quad_index is None or quad_index >= len(self.current_images):
                return

            # 四分图模式处理
            cursor_quad_position = (img_x, img_y)

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
                'position': cursor_quad_position,
                'mode': 'quad',
                'quad_index': quad_index,
                'cursor_quad_position': cursor_quad_position,
                **pixel_info
            }
                
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
            canvas = self._compose_current_view_canvas()
            if canvas is not None:
                display_size = (self.image_label.width(), self.image_label.height())
                canvas = ImagePlotter.draw_quad_cursors(
                    canvas, self.cursor_info, self.quad_positions, 
                    self.quad_size, display_size
                )
                self._render_canvas(canvas)
        
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
            self._render_current_view()
        elif self.current_images:  # 修改判断条件
            # 如果没有画布缓存，使用第一张原始图像
            self.show_image(self.current_images[0])

    def _display_to_render_canvas_coords(self, display_x: int, display_y: int) -> Optional[Tuple[int, int]]:
        """将显示坐标映射到当前渲染画布坐标。"""
        geom = self._get_display_geometry()
        if geom is None:
            return None

        x_offset, y_offset, display_width, display_height = geom
        mouse_x = display_x - x_offset
        mouse_y = display_y - y_offset
        if mouse_x < 0 or mouse_x >= display_width or mouse_y < 0 or mouse_y >= display_height:
            return None

        composed_canvas = self._compose_current_view_canvas()
        if composed_canvas is None:
            return None

        canvas_h, canvas_w = composed_canvas.shape[:2]
        canvas_x = int(mouse_x * canvas_w / display_width)
        canvas_y = int(mouse_y * canvas_h / display_height)
        canvas_x = max(0, min(canvas_x, canvas_w - 1))
        canvas_y = max(0, min(canvas_y, canvas_h - 1))
        return (canvas_x, canvas_y)
