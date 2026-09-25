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

    with pytest.raises(ValueError, match="8x8"):
        raw_image_service.load_image(image_path)


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
