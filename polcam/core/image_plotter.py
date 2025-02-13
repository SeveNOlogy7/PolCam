"""用于图像绘制的工具类"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
from typing import List, Tuple
from ..gui.styles import Styles

class ImagePlotter:
    """图像绘制工具类，负责所有的图像绘制操作"""
    
    @staticmethod
    def draw_quad_cursors(canvas: np.ndarray, 
                         cursor_info: dict,
                         quad_positions: List[Tuple[int, int]],
                         quad_size: Tuple[int, int],
                         display_size: Tuple[int, int]) -> np.ndarray:
        """在四分图上绘制同步游标，保持屏幕空间显示一致性"""
        if not cursor_info or 'position' not in cursor_info:
            return canvas
            
        # 获取相对于单个分图的坐标
        x, y = cursor_info['position']
        h, w = quad_size
        
        # 确保坐标在单个分图范围内
        x = x % w
        y = y % h
        
        # 计算图像缩放比例
        display_w, display_h = display_size
        canvas_h, canvas_w = canvas.shape[:2]
        scale_x = display_w / canvas_w
        scale_y = display_h / canvas_h
        scale = min(scale_x, scale_y)
        
        # 根据显示尺寸计算游标参数
        target_cursor_size_px = 20
        target_thickness_px = 1.5
        
        cursor_size = int(target_cursor_size_px / scale)
        line_thickness = max(1, int(target_thickness_px / scale))
        
        cursor_color = (0, 255, 0)  # 绿色游标
        
        # 在每个分图上绘制游标
        for quad_y, quad_x in quad_positions:
            center_x = quad_x + x
            center_y = quad_y + y

            # 绘制主十字游标
            cv2.line(canvas,
                    (center_x - cursor_size, center_y),
                    (center_x + cursor_size, center_y),
                    cursor_color, line_thickness)
            cv2.line(canvas,
                    (center_x, center_y - cursor_size),
                    (center_x, center_y + cursor_size),
                    cursor_color, line_thickness)
            
            # 绘制中心点
            dot_radius = max(2, line_thickness * 2)
            cv2.circle(canvas, (center_x, center_y), dot_radius, 
                      cursor_color, -1)

            # 绘制延伸的白色虚线
            thin_thickness = max(1, line_thickness // 2)
            white_color = (255, 255, 255)
            dash_length = 5

            # 水平延伸线
            for i in range(cursor_size, w, dash_length * 2):
                # 左延伸
                start_x = center_x - i - dash_length
                if start_x >= quad_x:
                    cv2.line(canvas,
                            (start_x, center_y),
                            (start_x + dash_length, center_y),
                            white_color, thin_thickness)
                # 右延伸
                start_x = center_x + i
                if start_x + dash_length <= quad_x + w:
                    cv2.line(canvas,
                            (start_x, center_y),
                            (start_x + dash_length, center_y),
                            white_color, thin_thickness)

            # 垂直延伸线
            for i in range(cursor_size, h, dash_length * 2):
                # 上延伸
                start_y = center_y - i - dash_length
                if start_y >= quad_y:
                    cv2.line(canvas,
                            (center_x, start_y),
                            (center_x, start_y + dash_length),
                            white_color, thin_thickness)
                # 下延伸
                start_y = center_y + i
                if start_y + dash_length <= quad_y + h:
                    cv2.line(canvas,
                            (center_x, start_y),
                            (center_x, start_y + dash_length),
                            white_color, thin_thickness)
                    
        return canvas

    @staticmethod
    def create_quad_canvas(images: List[np.ndarray], 
                          titles: List[str]) -> Tuple[np.ndarray, List[Tuple[int, int]], Tuple[int, int]]:
        """创建四分图画布"""
        if len(images) != 4 or len(titles) != 4:
            raise ValueError("必须提供4张图像和4个标题")
            
        h, w = images[0].shape[:2]
        canvas = np.zeros((h*2, w*2, 3), dtype=np.uint8)
        
        # 计算布局信息
        quad_positions = [(0, 0), (0, w), (h, 0), (h, w)]
        quad_size = (h, w)
        
        # 确保所有图像都是三通道BGR格式
        processed_images = []
        for img in images:
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            processed_images.append(img)
        
        # 绘制图像和标题
        for img, (y, x), title in zip(processed_images, quad_positions, titles):
            canvas[y:y+h, x:x+w] = img
            cv2.putText(canvas, title, 
                       (x + Styles.IMAGE_TITLE_X_OFFSET, 
                        y + Styles.IMAGE_TITLE_Y_OFFSET),
                       cv2.FONT_HERSHEY_SIMPLEX, 
                       Styles.IMAGE_TITLE_FONT_SCALE, 
                       Styles.IMAGE_TITLE_COLOR, 
                       Styles.IMAGE_TITLE_THICKNESS)
        
        return canvas, quad_positions, quad_size

    @staticmethod
    def get_default_image() -> np.ndarray:
        """创建默认的帮助图像"""
        pil_image = Image.new('RGB', (1920, 1080), color='black')
        draw = ImageDraw.Draw(pil_image)
        
        # 加载中文字体
        try:
            font_path = "C:/Windows/Fonts/msyh.ttc"
            if not os.path.exists(font_path):
                font_path = "C:/Windows/Fonts/simhei.ttf"
            title_font = ImageFont.truetype(font_path, 48)
            text_font = ImageFont.truetype(font_path, 36)
        except Exception as e:
            print(f"加载字体失败: {e}")
            return None
        
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
        
        text_height = 70
        start_y = (1080 - len(guide_text) * text_height) // 2
        
        for i, text in enumerate(guide_text):
            font = title_font if i == 0 else text_font
            color = (100, 200, 255) if i == 0 else (200, 200, 200)
            
            text_width = font.getlength(text)
            x = (1920 - text_width) // 2
            y = start_y + i * text_height
            
            draw.text((x, y), text, font=font, fill=color)
        
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
