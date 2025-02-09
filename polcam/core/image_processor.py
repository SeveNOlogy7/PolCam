"""
MIT License
Copyright (c) 2024 PolCam Contributors
See LICENSE file for full license details.
"""

import numpy as np
import polanalyser as pa
import cv2
from typing import List, Tuple

class ImageProcessor:
    @staticmethod
    def demosaic_polarization(raw_image: np.ndarray) -> Tuple[List[np.ndarray], List[np.ndarray]]:
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
        
        # 转换为灰度图
        gray_000 = cv2.cvtColor(img_000, cv2.COLOR_BGR2GRAY)
        gray_045 = cv2.cvtColor(img_045, cv2.COLOR_BGR2GRAY)
        gray_090 = cv2.cvtColor(img_090, cv2.COLOR_BGR2GRAY)
        gray_135 = cv2.cvtColor(img_135, cv2.COLOR_BGR2GRAY)

        return ([img_000, img_045, img_090, img_135], 
                [gray_000, gray_045, gray_090, gray_135])

    @staticmethod
    def calculate_polarization_degree(gray_images: List[np.ndarray]) -> np.ndarray:
        I_000, I_045, I_090, I_135 = gray_images
        
        # 计算Stokes参数
        S0 = (I_000 + I_090 + I_045 + I_135) / 2
        S1 = I_000 - I_090
        S2 = I_045 - I_135
        
        # 计算偏振度
        DOLP = np.sqrt(S1**2 + S2**2) / (S0 + 1e-6)
        return DOLP
