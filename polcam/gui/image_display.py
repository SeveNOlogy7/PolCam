"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtCore, QtGui
import numpy as np
import cv2
from typing import List
from PIL import Image, ImageDraw, ImageFont
import os
from .styles import Styles

class ImageDisplay(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.current_image = None  # 添加当前图像缓存
        self.show_default_image()
        
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)  # 设置内边距
        
        # 显示模式选择
        self.display_mode = QtWidgets.QComboBox()
        Styles.apply_combobox_style(self.display_mode)
        self.display_mode.setFont(QtGui.QFont("", 11))  # 设置下拉框字体
        self.display_mode.setMinimumHeight(30)  # 增加高度
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
        # 如果有当前图像，则重新显示
        if self.current_image is not None:
            self.show_image(self.current_image)
        
    def update_display(self):
        """显示模式改变时的处理"""
        if not hasattr(self, 'raw') or self.raw is None:
            return
            
        # 触发主窗口重新处理当前帧
        self.parent().process_and_display_frame(self.raw, reprocess=True)

    def show_image(self, image: np.ndarray):
        """统一的图像显示接口，自动调整图像大小以适应显示区域"""
        try:
            if image is None:
                return
                
            # 保存当前图像的副本以便窗口大小改变时重新显示
            self.current_image = image.copy() if isinstance(image, np.ndarray) else None

            # 转换为QImage
            if len(image.shape) == 2:
                h, w = image.shape
                bytes_per_line = w
                qt_image = QtGui.QImage(image.data, w, h, 
                                      bytes_per_line, QtGui.QImage.Format_Grayscale8)
            else:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                h, w = image.shape[:2]
                bytes_per_line = 3 * w
                qt_image = QtGui.QImage(image.data.tobytes(), w, h, 
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
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)
        
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
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)
            
        self.show_image(canvas)
        
    def get_default_image(self) -> np.ndarray:
        """获取默认的帮助图像
        
        Returns:
            np.ndarray: 帮助图像
        """
        # 创建PIL图像 (1920x1080)
        pil_image = Image.new('RGB', (1920, 1080), color='black')
        draw = ImageDraw.Draw(pil_image)
        
        # 加载中文字体
        try:
            font_path = "C:/Windows/Fonts/msyh.ttc"  # 微软雅黑
            if not os.path.exists(font_path):
                font_path = "C:/Windows/Fonts/simhei.ttf"  # 备选：黑体
            title_font = ImageFont.truetype(font_path, 48)
            text_font = ImageFont.truetype(font_path, 36)
        except Exception as e:
            self._logger.error(f"加载字体失败: {e}")
            return None
        
        # 帮助文字内容
        guide_text = [
            "偏振相机控制系统使用说明",
            "",
            "基本操作：",
            "1. 连接相机：点击左侧'连接相机'按钮",
            "2. 调节图像：使用曝光和增益控制",
            "3. 采集图像：可选择'单帧采集'或'连续采集'",
            "4. 显示模式：在顶部下拉框选择不同显示方式",
            "",
            "高级功能：",
            "- 白平衡：彩色模式下可开启自动白平衡",
            "- 偏振分析：可查看DOLP、AOLP等偏振信息",
            "- 图像保存：工具栏中的保存按钮可保存原始图像和处理结果"
        ]
        
        # 计算文字位置
        text_height = 70
        start_y = (1080 - len(guide_text) * text_height) // 2
        
        # 绘制每行文字
        for i, text in enumerate(guide_text):
            if i == 0:  # 标题
                font = title_font
                color = (100, 200, 255)
            else:  # 正文
                font = text_font
                color = (200, 200, 200)
            
            text_width = font.getlength(text)
            x = (1920 - text_width) // 2
            y = start_y + i * text_height
            
            draw.text((x, y), text, font=font, fill=color)
        
        # 转换为OpenCV格式
        cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        return cv_image

    def show_default_image(self):
        """显示默认的帮助图像"""
        default_image = self.get_default_image()
        if default_image is not None:
            self.show_image(default_image)
