"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

from pathlib import Path

import numpy as np
import os
import pytest
import stat

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


def test_delete_item_removes_the_record_even_if_the_file_is_read_only(
        tmp_path: Path, gallery_service: GalleryService):
    """只读文件也要把记录删掉。

    原来 delete_item 先 unlink 再 DELETE，Windows 上只读属性（从归档/备份拷回来的
    文件很常见）会让 unlink 抛 PermissionError —— 记录没删成，这个条目从此在相册里
    永远删不掉。留下的最坏结果应该是盘上多一个孤儿文件，不是相册里一个打不开的行。
    """
    frame = np.zeros((16, 16), dtype=np.uint8)
    item = gallery_service.save_capture(frame=frame, save_directory=tmp_path, timestamp=1700000010.0)
    os.chmod(item.file_path, stat.S_IREAD)

    try:
        gallery_service.delete_item(item.id)
        assert gallery_service.list_items() == [], "只读文件让条目永远删不掉"
    finally:
        if Path(item.file_path).exists():
            os.chmod(item.file_path, stat.S_IWRITE)


def test_save_capture_checks_the_database_too_when_naming_a_file(
        tmp_path: Path, gallery_service: GalleryService):
    """同一秒再采一次，而盘上那个文件已经被手工删掉 —— 命名只查文件系统就会撞 UNIQUE。

    gallery_items.file_path 是 UNIQUE 的，插入抛 IntegrityError 时图片其实已经写进盘
    了，于是这张图永远不会出现在相册里，用户看到的是"自动保存失败"。
    """
    frame = np.zeros((16, 16), dtype=np.uint8)
    first = gallery_service.save_capture(frame=frame, save_directory=tmp_path, timestamp=1700000020.0)
    Path(first.file_path).unlink()

    second = gallery_service.save_capture(frame=frame, save_directory=tmp_path, timestamp=1700000020.0)

    assert Path(second.file_path).exists()
    assert second.file_path != first.file_path
    assert {item.file_path for item in gallery_service.list_items()} == {
        first.file_path, second.file_path}


def test_corrupt_database_is_quarantined_instead_of_blocking_startup(tmp_path: Path):
    """gallery.db 打不开时程序还是要能起来。

    GalleryService.__init__ 在建窗口的路上（MainWindow.__init__），异常一路冒到
    main.py，而打包版 console=False 让那句 print 什么都不输出 —— 用户双击图标什么也
    看不到，退出码还是 0。图库只是索引，重建一份即可，坏文件要留档别覆盖。
    """
    db_path = tmp_path / "gallery.db"
    db_path.write_bytes(b"not a database at all")

    service = GalleryService(db_path=db_path)

    assert service.list_items() == []
    frame = np.zeros((16, 16), dtype=np.uint8)
    assert service.save_capture(frame=frame, save_directory=tmp_path, timestamp=1700000030.0)
    survivors = [p for p in tmp_path.iterdir()
                 if p.read_bytes() == b"not a database at all"]
    assert survivors, "坏掉的数据库被覆盖掉了，没有留档"
