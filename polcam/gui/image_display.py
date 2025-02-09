"""
MIT License
Copyright (c) 2024 PolCam Contributors
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtCore, QtGui
import numpy as np
import cv2
from typing import List

class ImageDisplay(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)  # 设置内边距
        
        # 显示模式选择
        self.display_mode = QtWidgets.QComboBox()
        self.display_mode.addItems([
            "原始图像",
            "单角度彩色",
            "单角度灰度",
            "四角度视图",
            "偏振度图像"
        ])
        layout.addWidget(self.display_mode)
        
        # 图像显示区域
        self.image_label = QtWidgets.QLabel()
        self.image_label.setMinimumSize(640, 480)
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)  # 居中对齐
        self.image_label.setSizePolicy(                       # 设置大小策略
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
        layout.addWidget(self.image_label)
        
        self.display_mode.currentIndexChanged.connect(self.update_display)
        
        # 设置尺寸策略为扩展
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
        
    def resizeEvent(self, event: QtGui.QResizeEvent):
        """窗口大小变化时重新显示图像"""
        super().resizeEvent(event)
        self.update_display()
        
    def update_images(self, raw: np.ndarray, color_images: List[np.ndarray], 
                     gray_images: List[np.ndarray], dolp: np.ndarray):
        self.raw = raw
        self.color_images = color_images
        self.gray_images = gray_images
        self.dolp = dolp
        self.update_display()
        
    def update_display(self):
        if not hasattr(self, 'raw'):
            return
            
        mode = self.display_mode.currentIndex()
        if mode == 0:  # 原始图像
            self.show_image(self.raw)
        elif mode == 1:  # 单角度彩色
            self.show_image(self.color_images[0])
        elif mode == 2:  # 单角度灰度
            self.show_image(self.gray_images[0])
        elif mode == 3:  # 四角度视图
            self.show_quad_view(self.color_images)
        elif mode == 4:  # 偏振度图像
            self.show_image(self.dolp)
            
    def show_image(self, image: np.ndarray):
        try:
            if image is None:
                return

            if len(image.shape) == 2:
                # 单通道图像直接显示
                h, w = image.shape
                bytes_per_line = w
                qt_image = QtGui.QImage(image.data, w, h, 
                                      bytes_per_line, QtGui.QImage.Format_Grayscale8)
            else:
                # 三通道图像转RGB
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                h, w = image.shape[:2]
                bytes_per_line = 3 * w
                qt_image = QtGui.QImage(image.data.tobytes(), w, h, 
                                      bytes_per_line, QtGui.QImage.Format_RGB888)
            
            # 调整图像大小以适应显示区域
            pixmap = QtGui.QPixmap.fromImage(qt_image)
            label_size = self.image_label.size()
            scaled_pixmap = pixmap.scaled(
                label_size,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            
            # 更新显示
            self.image_label.setPixmap(scaled_pixmap)
            
        except Exception as e:
            print(f"图像显示错误: {e}")
        
    def show_quad_view(self, images: List[np.ndarray]):
        h, w = images[0].shape[:2]
        canvas = np.zeros((h*2, w*2, 3), dtype=np.uint8)
        
        # 排列四张图像
        positions = [(0, 0), (0, w), (h, 0), (h, w)]
        titles = ['0°', '45°', '90°', '135°']
        
        for img, (y, x) in zip(images, positions):
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            canvas[y:y+h, x:x+w] = img_rgb
            
            # 添加标题
            cv2.putText(canvas, titles[positions.index((y, x))],
                       (x+10, y+30), cv2.FONT_HERSHEY_SIMPLEX,
                       1, (255, 255, 255), 2)
        
        self.show_image(canvas)
