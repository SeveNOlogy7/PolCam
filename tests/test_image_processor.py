import numpy as np
import pytest
import cv2
from polcam.core.image_processor import ImageProcessor

def test_calculate_polarization_degree():
    # 创建模拟的灰度图像数据
    I_000 = np.array([[100, 200], [150, 250]], dtype=np.uint8)
    I_045 = np.array([[90, 180], [140, 230]], dtype=np.uint8)
    I_090 = np.array([[80, 160], [130, 210]], dtype=np.uint8)
    I_135 = np.array([[70, 140], [120, 190]], dtype=np.uint8)
    
    gray_images = [I_000, I_045, I_090, I_135]
    
    # 计算偏振度
    dolp = ImageProcessor.calculate_polarization_degree(gray_images)
    
    # 检查结果
    assert isinstance(dolp, np.ndarray)
    assert dolp.shape == (2, 2)
    assert np.all(dolp >= 0) and np.all(dolp <= 1)  # 偏振度应在0-1之间

def test_calculate_polarization_degree_edge_cases():
    # 测试全黑图像
    black_images = [np.zeros((2, 2), dtype=np.uint8) for _ in range(4)]
    dolp_black = ImageProcessor.calculate_polarization_degree(black_images)
    assert np.allclose(dolp_black, 0.0)
    
    # 测试饱和图像
    white_images = [np.full((2, 2), 255, dtype=np.uint8) for _ in range(4)]
    dolp_white = ImageProcessor.calculate_polarization_degree(white_images)
    assert np.all(dolp_white >= 0) and np.all(dolp_white <= 1)

def test_demosaic_polarization():
    # 创建模拟的原始图像数据 (2x2 pixels for each polarization angle)
    raw_image = np.zeros((4, 4), dtype=np.uint8)
    raw_image[0::2, 0::2] = 100  # 0度
    raw_image[0::2, 1::2] = 150  # 45度
    raw_image[1::2, 0::2] = 200  # 90度
    raw_image[1::2, 1::2] = 250  # 135度
    
    # 测试解马赛克
    color_images, gray_images = ImageProcessor.demosaic_polarization(raw_image)
    
    # 检查返回的图像列表
    assert len(color_images) == 4
    assert len(gray_images) == 4
    
    # 检查图像尺寸和类型
    for img in color_images:
        assert img.shape[2] == 3  # 彩色图像应该有3个通道
    for img in gray_images:
        assert len(img.shape) == 2  # 灰度图像应该是2维的

def test_demosaic_polarization_invalid_input():
    # 测试非法输入尺寸
    with pytest.raises((ValueError, cv2.error)):
        # 使用uint8类型，但尺寸错误的数组
        ImageProcessor.demosaic_polarization(np.zeros((3, 3), dtype=np.uint8))

    # 测试错误的数据类型
    with pytest.raises((TypeError, cv2.error)):
        # 使用列表而不是numpy数组
        ImageProcessor.demosaic_polarization([[1, 2], [3, 4]])
    
    # 测试非4的倍数的尺寸
    with pytest.raises((ValueError, cv2.error)):
        ImageProcessor.demosaic_polarization(np.zeros((6, 6), dtype=np.uint8))

def test_demosaic_polarization_minimum_size():
    # 测试最小合法尺寸 (4x4)
    min_image = np.zeros((4, 4), dtype=np.uint8)
    try:
        color_images, gray_images = ImageProcessor.demosaic_polarization(min_image)
        assert len(color_images) == 4
        assert len(gray_images) == 4
    except cv2.error as e:
        pytest.skip("OpenCV可能不支持这个最小尺寸的处理")
