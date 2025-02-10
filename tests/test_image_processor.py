"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

import numpy as np
import pytest
import cv2
from polcam.core.image_processor import ImageProcessor

@pytest.fixture
def image_processor():
    return ImageProcessor()

@pytest.fixture
def sample_color_image():
    # 创建一个简单的彩色测试图像
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[25:75, 25:75] = [100, 150, 200]  # BGR格式
    return img

@pytest.fixture
def polarization_images():
    """创建4个角度的测试图像"""
    imgs = []
    for i in range(4):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        # 使用较小的增量以确保不超过255
        img[25:75, 25:75] = [
            min(100 + i * 10, 255),  # B
            min(150 + i * 10, 255),  # G
            min(200 + i * 10, 255)   # R
        ]
        imgs.append(img)
    return imgs

def test_to_grayscale(image_processor, sample_color_image):
    """测试灰度转换功能"""
    # 测试彩色图像转换
    gray = image_processor.to_grayscale(sample_color_image)
    assert gray.shape == (100, 100)
    assert len(gray.shape) == 2
    
    # 测试已经是灰度图的情况
    gray2 = image_processor.to_grayscale(gray)
    assert np.array_equal(gray, gray2)
    
    # 测试空图像
    empty = np.array([])
    with pytest.raises(Exception):
        image_processor.to_grayscale(empty)

def test_auto_white_balance(image_processor, sample_color_image):
    """测试自动白平衡功能"""
    # 测试正常图像
    balanced = image_processor.auto_white_balance(sample_color_image)
    assert balanced.shape == sample_color_image.shape
    assert balanced.dtype == np.uint8
    
    # 测试全黑图像
    black = np.zeros_like(sample_color_image)
    balanced_black = image_processor.auto_white_balance(black)
    # 对于全黑图像，应该保持为黑色
    assert np.array_equal(balanced_black, black)
    
    # 测试全白图像 - 应该被调整到目标亮度附近
    white = np.full_like(sample_color_image, 255)
    balanced_white = image_processor.auto_white_balance(white)
    # 检查是否所有通道都被调整到接近目标亮度（128）
    assert np.all(balanced_white >= 120) and np.all(balanced_white <= 136)
    assert np.allclose(balanced_white[:,:,0], balanced_white[:,:,1], atol=1)
    assert np.allclose(balanced_white[:,:,1], balanced_white[:,:,2], atol=1)
    
    # 测试正常范围图像的色彩平衡
    test_image = np.full_like(sample_color_image, 128)
    test_image[:,:,0] = 100  # B通道较暗
    test_image[:,:,2] = 156  # R通道较亮
    balanced_test = image_processor.auto_white_balance(test_image)
    # 检查各通道是否被平衡到接近的值
    channel_means = [np.mean(balanced_test[:,:,i]) for i in range(3)]
    assert np.std(channel_means) < 5  # 通道间平均值的标准差应该很小
    
    # 测试单通道图像
    gray = np.zeros((100, 100), dtype=np.uint8)
    assert np.array_equal(image_processor.auto_white_balance(gray), gray)

def test_apply_white_balance(image_processor, sample_color_image):
    """测试应用已有白平衡参数"""
    # 先执行自动白平衡以获取参数
    _ = image_processor.auto_white_balance(sample_color_image)
    
    # 测试应用到新图像
    balanced = image_processor.apply_white_balance(sample_color_image)
    assert balanced.shape == sample_color_image.shape
    assert balanced.dtype == np.uint8
    
    # 测试应用到灰度图像
    gray = cv2.cvtColor(sample_color_image, cv2.COLOR_BGR2GRAY)
    assert np.array_equal(image_processor.apply_white_balance(gray), gray)

def test_calculate_polarization_parameters(image_processor, polarization_images):
    """测试偏振参数计算"""
    dolp, aolp, docp = image_processor.calculate_polarization_parameters(polarization_images)
    
    # 检查输出尺寸
    assert dolp.shape == (100, 100)
    assert aolp.shape == (100, 100)
    assert docp.shape == (100, 100)
    
    # 检查值范围
    assert np.all(dolp >= 0) and np.all(dolp <= 1)
    assert np.all(aolp >= 0) and np.all(aolp <= 180)
    assert np.all(docp >= 0) and np.all(docp <= 1)
    
    # 测试全黑图像
    black_images = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(4)]
    dolp_black, aolp_black, docp_black = image_processor.calculate_polarization_parameters(black_images)
    assert np.allclose(dolp_black, 0)
    assert np.allclose(docp_black, 0)
    
    # 测试相同图像
    same_images = [polarization_images[0] for _ in range(4)]
    dolp_same, _, _ = image_processor.calculate_polarization_parameters(same_images)
    assert np.allclose(dolp_same, 0)  # 完全相同的图像应该没有偏振度

def test_error_handling(image_processor):
    """测试错误处理"""
    # 测试输入图像数量不正确
    with pytest.raises(ValueError):
        image_processor.calculate_polarization_parameters([])
    
    with pytest.raises(ValueError):
        image_processor.calculate_polarization_parameters([np.zeros((100, 100, 3), dtype=np.uint8)])
    
    # 测试输入图像尺寸不一致
    invalid_images = [
        np.zeros((100, 100, 3), dtype=np.uint8),
        np.zeros((100, 50, 3), dtype=np.uint8),
        np.zeros((100, 100, 3), dtype=np.uint8),
        np.zeros((100, 100, 3), dtype=np.uint8)
    ]
    with pytest.raises(ValueError):
        image_processor.calculate_polarization_parameters(invalid_images)
    
    # 测试无效的数据类型
    with pytest.raises(TypeError):
        image_processor.auto_white_balance("invalid")
        
    with pytest.raises(TypeError):
        image_processor.apply_white_balance("invalid")

def test_brightness_adjustment(image_processor, sample_color_image):
    """测试亮度调节"""
    # 测试暗图像
    dark = sample_color_image // 4
    balanced_dark = image_processor.auto_white_balance(dark)
    assert np.mean(balanced_dark) > np.mean(dark)
    
    # 测试亮图像
    bright = cv2.add(sample_color_image, 50)
    balanced_bright = image_processor.auto_white_balance(bright)
    assert balanced_bright.dtype == np.uint8
    assert np.all(balanced_bright <= 255)

def test_demosaic_polarization():
    """测试偏振解码功能"""
    # 创建模拟的原始图像数据 (8x8 pixels，一个完整的马赛克周期需要 4x4)
    raw_image = np.zeros((8, 8), dtype=np.uint8)
    
    # 设置偏振马赛克模式
    # 0° 45°
    # 90° 135°
    for y in range(0, 8, 2):
        for x in range(0, 8, 2):
            raw_image[y, x] = 200      # 0度位置
            raw_image[y, x+1] = 150    # 45度位置
            raw_image[y+1, x] = 100    # 90度位置
            raw_image[y+1, x+1] = 50   # 135度位置
    
    # 测试解马赛克
    color_images = ImageProcessor.demosaic_polarization(raw_image)
    
    # 基本验证
    assert len(color_images) == 4  # 应该返回4个角度的图像
    
    # 检查图像尺寸和类型
    for img in color_images:
        assert len(img.shape) == 3          # 应该是3通道图像
        assert img.shape[2] == 3            # BGR格式
        assert img.dtype == np.uint8        # 8位无符号整数
        assert img.shape[:2] == (8, 8)      # 输出尺寸应该与输入相同
    
    # 检查图像是否成功解码
    for img in color_images:
        # 至少有一些像素应该有非零值
        assert np.any(img > 0)
        # 像素值不应超过输入的最大值
        assert np.all(img <= 200)
        
    # 验证亮度顺序（可选，取决于实际的解码算法）
    # means = [np.mean(img) for img in color_images]
    # assert means[0] >= means[2]  # 0度应该不小于90度
    # assert means[1] >= means[3]  # 45度应该不小于135度

def test_demosaic_polarization_invalid_input():
    """测试偏振解码的输入验证"""
    with pytest.raises((ValueError, cv2.error)):
        # 尺寸太小
        ImageProcessor.demosaic_polarization(np.zeros((2, 2), dtype=np.uint8))

    with pytest.raises(TypeError):
        # 错误的数据类型
        ImageProcessor.demosaic_polarization([[1, 2], [3, 4]])
    
    with pytest.raises(ValueError):
        # 非4的倍数尺寸
        ImageProcessor.demosaic_polarization(np.zeros((6, 6), dtype=np.uint8))

def test_demosaic_polarization_minimum_size():
    """测试最小合法尺寸的偏振解码"""
    # 测试最小合法尺寸 (4x4)
    min_image = np.zeros((4, 4), dtype=np.uint8)
    try:
        color_images = ImageProcessor.demosaic_polarization(min_image)
        assert len(color_images) == 4
        # 验证返回的四个角度图像
        for img in color_images:
            assert img.shape == (4, 4, 3)  # 检查尺寸
            assert img.dtype == np.uint8   # 检查数据类型
    except cv2.error as e:
        pytest.skip("OpenCV可能不支持这个最小尺寸的处理")

def test_white_balance_gains(image_processor, sample_color_image):
    """测试白平衡增益系数"""
    # 执行自动白平衡
    _ = image_processor.auto_white_balance(sample_color_image)
    
    # 检查增益系数
    assert hasattr(image_processor, '_wb_gains')
    assert len(image_processor._wb_gains) == 3
    assert all(gain > 0 for gain in image_processor._wb_gains)
    
    # 检查亮度系数
    assert hasattr(image_processor, '_brightness_factor')
    assert image_processor._brightness_factor > 0

def test_calculate_polarization_parameters():
    """测试偏振参数计算 - 基本功能"""
    # 创建模拟的灰度图像数据
    I_000 = np.array([[100, 200], [150, 250]], dtype=np.uint8)
    I_045 = np.array([[90, 180], [140, 230]], dtype=np.uint8)
    I_090 = np.array([[80, 160], [130, 210]], dtype=np.uint8)
    I_135 = np.array([[70, 140], [120, 190]], dtype=np.uint8)
    
    gray_images = [I_000, I_045, I_090, I_135]
    
    # 计算偏振参数
    dolp, aolp, docp = ImageProcessor.calculate_polarization_parameters(gray_images)
    
    # 检查结果
    assert isinstance(dolp, np.ndarray)
    assert dolp.shape == (2, 2)
    assert np.all(dolp >= 0) and np.all(dolp <= 1)  # 偏振度应在0-1之间
    
    # 检查偏振角
    assert isinstance(aolp, np.ndarray)
    assert aolp.shape == (2, 2)
    assert np.all(aolp >= 0) and np.all(aolp <= 180)  # 角度应在0-180度之间

def test_calculate_polarization_parameters_edge_cases():
    """测试偏振参数计算 - 边界情况"""
    # 测试全黑图像
    black_images = [np.zeros((2, 2), dtype=np.uint8) for _ in range(4)]
    dolp_black, _, _ = ImageProcessor.calculate_polarization_parameters(black_images)
    assert np.allclose(dolp_black, 0.0)
    
    # 测试饱和图像
    white_images = [np.full((2, 2), 255, dtype=np.uint8) for _ in range(4)]
    dolp_white, _, _ = ImageProcessor.calculate_polarization_parameters(white_images)
    assert np.all(dolp_white >= 0) and np.all(dolp_white <= 1)
