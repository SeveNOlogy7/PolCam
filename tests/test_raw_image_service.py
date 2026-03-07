"""
MIT License
Copyright (c) 2024 Junhao Cai
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
