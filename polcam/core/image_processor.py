"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

import numpy as np
import polanalyser as pa
import cv2
from typing import List, Tuple, Union

class ImageProcessor:
    def __init__(self):
        pass

    @staticmethod
    def demosaic_polarization(raw_image: np.ndarray) -> List[np.ndarray]:
        """仅解码获取彩色偏振图像"""
        # 输入类型验证
        if not isinstance(raw_image, np.ndarray):
            raise TypeError("输入必须是numpy数组类型")
            
        # 输入尺寸验证
        if len(raw_image.shape) != 2:
            raise ValueError("输入图像必须是2维数组")
            
        if raw_image.shape[0] % 4 != 0 or raw_image.shape[1] % 4 != 0:
            raise ValueError("输入图像的宽度和高度必须是4的倍数")
            
        if raw_image.shape[0] < 4 or raw_image.shape[1] < 4:
            raise ValueError("输入图像尺寸太小，最小需要4x4像素")

        # 偏振解码
        [img_000, img_045, img_090, img_135] = pa.demosaicing(
            raw_image, pa.COLOR_PolarRGB_EA
        )
        
        return [img_000, img_045, img_090, img_135]

    @staticmethod
    def to_grayscale(color_images) -> np.ndarray:
        """将彩色图像或图像列表转换为灰度图像
        
        Args:
            color_images: 单张图像或图像列表，支持RGB和已经是灰度的图像
            
        Returns:
            单张灰度图像或灰度图像列表
        """
        def _to_gray(img):
            # 如果已经是灰度图，直接返回
            if len(img.shape) == 2 or (len(img.shape) == 3 and img.shape[2] == 1):
                return img
            # 否则转换为灰度图
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
        if isinstance(color_images, list):
            return [_to_gray(img) for img in color_images]
        else:
            return _to_gray(color_images)

    @staticmethod
    def calculate_polarization_parameters(color_images: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """计算偏振参数：线偏振度(DoLP)、偏振角(AoLP)和圆偏振度(DoCP)"""
        # 验证输入
        if not isinstance(color_images, list):
            raise TypeError("输入必须是图像列表")
            
        if len(color_images) != 4:
            raise ValueError("必须提供4个角度的图像")
            
        # 确保图像类型和尺寸一致
        for img in color_images:
            if not isinstance(img, np.ndarray):
                raise TypeError("输入图像必须是numpy数组")
            if img.dtype != np.uint8:
                raise TypeError("输入图像必须是uint8类型")
        
        # 确保输入都是灰度图
        gray_images = [
            img if len(img.shape) == 2 
            else cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_BGR2GRAY) 
            for img in color_images
        ]
        
        I_000, I_045, I_090, I_135 = gray_images
        
        # 计算Stokes参数
        S0 = (I_000 + I_090 + I_045 + I_135) / 2
        S1 = I_000 - I_090
        S2 = I_045 - I_135
        
        # 避免除零并处理NaN
        S0 = np.where(S0 == 0, 1e-6, S0)
        
        # 计算线偏振度 (DoLP)
        dolp = np.clip(np.sqrt(S1**2 + S2**2) / S0, 0, 1)  # 限制在[0,1]范围内
        
        # 计算偏振角 (AoLP)
        aolp = np.arctan2(S2, S1) / 2
        # 转换到0-180度
        aolp = np.rad2deg(aolp) + 90
        
        # 模拟圆偏振度 (实际需要四分之一波片才能测量)
        docp = np.zeros_like(dolp)
        
        return dolp, aolp, docp

    def auto_white_balance(self, image: np.ndarray, return_gains: bool = False) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        """自动白平衡处理
        
        Args:
            image: 输入图像 (BGR格式)
            return_gains: 是否返回白平衡增益值
            
        Returns:
            如果return_gains为False，返回处理后的图像
            如果return_gains为True，返回元组(处理后的图像, 白平衡增益值)
        """
        if len(image.shape) != 3:
            return (image, np.ones(3)) if return_gains else image
            
        # 计算每个通道的平均值
        b, g, r = cv2.split(image)
        b_avg = np.mean(b)
        g_avg = np.mean(g)
        r_avg = np.mean(r)
        
        # 计算增益值，以绿色通道为基准
        if g_avg == 0:
            gains = np.ones(3)
        else:
            b_gain = g_avg / b_avg if b_avg > 0 else 1.0
            r_gain = g_avg / r_avg if r_avg > 0 else 1.0
            gains = np.array([b_gain, 1.0, r_gain])
            
        # 限制增益范围
        gains = np.clip(gains, 0.1, 3.0)
        
        # 保存现有的处理结果
        result = image.copy()
        for i in range(3):  # BGR
            result[:, :, i] = cv2.multiply(image[:, :, i], gains[i])
            
        return (result, gains) if return_gains else result
