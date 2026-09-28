"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

from pathlib import Path

import numpy as np
import pytest

from polcam.core.raw_image_service import RawImageService


@pytest.fixture
def raw_image_service():
    return RawImageService()


def test_save_and_load_image(tmp_path: Path, raw_image_service: RawImageService):
    frame = np.zeros((16, 16), dtype=np.uint8)
    frame[2:6, 2:6] = 255
    image_path = tmp_path / "frame.tiff"

    saved_path = raw_image_service.save_image(frame, image_path)
    loaded_frame = raw_image_service.load_image(saved_path)

    assert saved_path == image_path
    assert np.array_equal(loaded_frame, frame)


def test_build_auto_save_path_avoids_collision(tmp_path: Path, raw_image_service: RawImageService):
    first_path = raw_image_service.build_auto_save_path(tmp_path, timestamp=1700000000.0)
    first_path.write_bytes(b"test")

    second_path = raw_image_service.build_auto_save_path(tmp_path, timestamp=1700000000.0)

    assert first_path != second_path
    assert second_path.name.endswith("_001.tiff")


def test_load_image_rejects_invalid_size(tmp_path: Path, raw_image_service: RawImageService):
    frame = np.zeros((15, 16), dtype=np.uint8)
    image_path = tmp_path / "invalid.tiff"
    raw_image_service.save_image(frame, image_path)

    with pytest.raises(ValueError, match="偏振栅格"):
        raw_image_service.load_image(image_path)


def test_device_legal_roi_sizes_round_trip(tmp_path: Path, raw_image_service: RawImageService):
    """真机合法的 ROI 尺寸不该被当成坏帧。

    实测 MER2-502-79U3M-HS POL：Height 步进是 2 而不是 8，所以按 8x8 校验会拒掉相机
    自己产出的合法帧（1020 高的裁剪存得下、读不回来）。
    """
    frame = np.arange(1020 * 8, dtype=np.uint8).reshape(1020, 8)

    loaded = raw_image_service.load_image(raw_image_service.save_image(frame, tmp_path / "roi.tiff"))

    assert loaded.shape == (1020, 8)
    assert raw_image_service.verify_image_size(loaded)


def test_save_and_load_keep_16bit_depth(tmp_path: Path, raw_image_service: RawImageService):
    """16bit 帧存成 TIFF 再读回来不该被压成 8bit。

    load_image 用的 IMREAD_GRAYSCALE 会把位深强行折到 uint8 —— 文件里确实是 uint16
    （65535 还在），读回来只剩 255。相机出 10/12/16bit 时，自动保存的图重开就是一张
    被量化过的近黑图。
    """
    frame = np.linspace(0, 65535, 16 * 16, dtype=np.uint16).reshape(16, 16)

    loaded = raw_image_service.load_image(raw_image_service.save_image(frame, tmp_path / "u16.tiff"))

    assert loaded.dtype == np.uint16
    assert np.array_equal(loaded, frame)


def test_load_image_rejects_multi_channel_file(tmp_path: Path, raw_image_service: RawImageService):
    """处理结果是三通道，不该被当成原始帧悄悄灰度化。

    以前 BGR(200,10,5) 存进去、读出来变成 (16,16) 全是 30 的灰度图，状态栏还报
    "已加载图像"。原始帧按定义是单通道，拿不到就该说清楚。
    """
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    frame[:, :] = (200, 10, 5)
    saved = raw_image_service.save_image(frame, tmp_path / "color.tiff")

    with pytest.raises(ValueError, match="单通道"):
        raw_image_service.load_image(saved)


def test_save_and_load_survive_non_ascii_paths(tmp_path: Path, raw_image_service: RawImageService):
    """中文目录名和文件名也要能存能读。

    cv2.imwrite/imread 用进程的 ANSI 代码页解析路径，在简体中文 Windows 上遇到非
    ASCII 路径直接失败：imwrite 只是返回 False，文件根本不落盘。
    """
    frame = np.arange(16 * 16, dtype=np.uint8).reshape(16, 16)
    image_path = tmp_path / "偏振图目录" / "原始帧.tiff"

    saved = raw_image_service.save_image(frame, image_path)
    assert saved.exists(), "非 ASCII 路径下文件没有写出来"

    assert np.array_equal(raw_image_service.load_image(saved), frame)
