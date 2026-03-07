"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

from pathlib import Path

import numpy as np
import pytest

from polcam.core.gallery_service import GalleryService


@pytest.fixture
def gallery_service(tmp_path: Path):
    db_path = tmp_path / "gallery.db"
    return GalleryService(db_path=db_path)


def test_save_capture_creates_db_record_and_file(tmp_path: Path, gallery_service: GalleryService):
    frame = np.zeros((16, 24), dtype=np.uint8)
    frame[1:4, 1:4] = 128

    item = gallery_service.save_capture(
        frame=frame,
        save_directory=tmp_path,
        timestamp=1700000000.0,
        metadata={"exposure_us": 40000.0, "gain_db": 0.0},
    )

    assert item.id > 0
    assert Path(item.file_path).exists()
    assert item.width == 24
    assert item.height == 16
    assert item.metadata["exposure_us"] == 40000.0

    items = gallery_service.list_items()
    assert len(items) == 1
    assert items[0].file_path == item.file_path


def test_delete_item_removes_file_and_record(tmp_path: Path, gallery_service: GalleryService):
    frame = np.zeros((16, 16), dtype=np.uint8)
    item = gallery_service.save_capture(frame=frame, save_directory=tmp_path, timestamp=1700000001.0)

    deleted_item = gallery_service.delete_item(item.id)

    assert deleted_item.id == item.id
    assert not Path(item.file_path).exists()
    assert gallery_service.list_items() == []

    with pytest.raises(KeyError):
        gallery_service.get_item(item.id)
