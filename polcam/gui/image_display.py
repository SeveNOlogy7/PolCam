"""
MIT License
Copyright (c) 2024 Junhao Cai
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
            "单角度彩色",   # 单偏振角度分量的彩色图像
            "单角度灰度",   # 单偏振角度分量的灰度图像
            "彩色图像",     # 全偏振分量合成的彩色图像
            "灰度图像",     # 全偏振分量合成的灰度图像
            "四角度彩色",   # 四个角度的彩色图像
            "四角度灰度",   # 四个角度的灰度图像
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
        
    def update_display(self):
        """显示模式改变时的处理"""
        if not hasattr(self, 'raw') or self.raw is None:
            return
            
        # 触发主窗口重新处理当前帧
        self.parent().process_and_display_frame(self.raw, reprocess=True)

    def show_image(self, image: np.ndarray):
        """统一的图像显示接口"""
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
        
    def to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """将彩色图像转换为灰度图像"""
        if len(image.shape) == 2:
            return image
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def show_quad_view(self, images: List[np.ndarray], gray: bool = False):
        """四角度视图显示接口
        
        Args:
            images: 四个角度的图像列表
            gray: 是否显示灰度图像
        """
        if gray:
            # 使用内部的灰度转换方法
            images = [self.to_grayscale(img) for img in images]
            # 转换单通道灰度图为三通道图像以便添加文字
            images = [cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) for img in images]
        else:
            images = [cv2.cvtColor(img, cv2.COLOR_BGR2RGB) for img in images]
            
        h, w = images[0].shape[:2]
        canvas = np.zeros((h*2, w*2, 3), dtype=np.uint8)
        
        # 排列四张图像
        positions = [(0, 0), (0, w), (h, 0), (h, w)]
        titles = ['0°', '45°', '90°', '135°']
        
        for img, (y, x), title in zip(images, positions, titles):
            canvas[y:y+h, x:x+w] = img
            
            # 添加标题
            cv2.putText(canvas, title, (x+10, y+30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        self.show_image(canvas)

    def show_polarization_quad_view(self, color_image: np.ndarray, 
                                  dolp: np.ndarray, aolp: np.ndarray, 
                                  docp: np.ndarray):
        """显示偏振分析的四视图"""
        h, w = color_image.shape[:2]
        canvas = np.zeros((h*2, w*2, 3), dtype=np.uint8)
        
        # 准备四个显示图像
        # 1. 彩色图像直接使用
        # 2. DoLP图像：转为热力图
        dolp_colored = cv2.applyColorMap((dolp * 255).astype(np.uint8), 
                                       cv2.COLORMAP_JET)
        # 3. AoLP图像：使用HSV颜色空间
        aolp_normalized = (aolp / 180 * 255).astype(np.uint8)
        aolp_colored = cv2.applyColorMap(aolp_normalized, cv2.COLORMAP_HSV)
        # 4. DoCP图像：转为热力图
        docp_colored = cv2.applyColorMap((docp * 255).astype(np.uint8), 
                                        cv2.COLORMAP_JET)
        
        # 排列四张图像
        images = [color_image, dolp_colored, aolp_colored, docp_colored]
        positions = [(0, 0), (0, w), (h, 0), (h, w)]
        titles = ['彩色图像', '线偏振度', '偏振角', '圆偏振度']
        
        for img, (y, x), title in zip(images, positions, titles):
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            canvas[y:y+h, x:x+w] = img_rgb
            
            # 添加标题
            cv2.putText(canvas, title, (x+10, y+30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
        self.show_image(canvas)
