"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

from pathlib import Path

import cv2
import numpy as np
from qtpy import QtCore

from polcam.core.gallery_service import GalleryItem
from polcam.gui.widgets.gallery_panel import GalleryPanel


def _make_gallery_item(tmp_path: Path, item_id: int) -> GalleryItem:
    image_path = tmp_path / f"item_{item_id}.tiff"
    image = np.full((16, 16), item_id, dtype=np.uint8)
    cv2.imwrite(str(image_path), image)
    return GalleryItem(
        id=item_id,
        file_name=image_path.name,
        file_path=str(image_path),
        captured_at=1700000000.0 + item_id,
        width=16,
        height=16,
        file_size=image_path.stat().st_size,
        file_format="tiff",
        source="single_capture",
        metadata={},
        created_at=1700000000.0 + item_id,
    )


def test_set_items_keeps_every_row_when_one_file_is_gone(qtbot, tmp_path: Path):
    """一条失效路径不该把整个相册面板清空。

    np.fromfile 对不存在的文件是抛 FileNotFoundError 的，而 set_items 的循环原本没有
    逐项兜底；list_items 按 captured_at DESC 排，所以只要最新那行的文件没了，循环第一
    下就断，之后每次刷新都同样失败。
    """
    panel = GalleryPanel()
    qtbot.addWidget(panel)
    panel.show()

    good = [_make_gallery_item(tmp_path, 1), _make_gallery_item(tmp_path, 2)]
    gone = _make_gallery_item(tmp_path, 3)
    Path(gone.file_path).unlink()
    missing = GalleryItem(
        id=3, file_name="vanished.tiff", file_path=str(tmp_path / "vanished.tiff"),
        captured_at=gone.captured_at, width=16, height=16, file_size=0,
        file_format="tiff", source=gone.source, metadata={}, created_at=gone.created_at,
    )

    panel.set_items([missing] + good)

    assert panel.table.rowCount() == 3, "读不出缩略图的那一行把后面所有行一起带走了"
    assert panel.preview_list.count() == 3
    assert panel.count_label.text() == "3 项"
    assert not panel.empty_label.isVisibleTo(panel)


def test_refresh_reuses_thumbnails_instead_of_decoding_the_whole_gallery(qtbot, tmp_path: Path, monkeypatch):
    """刷新只该解新出现的图，而不是每次把整库按全尺寸重读一遍。

    每次单帧采集之后都会 refresh_gallery()，原来会把 N 张全尺寸图全解一遍：实测一张
    2448x2048 的 TIFF 要 32ms，100 张就是每次点击卡 3 秒多。
    """
    from polcam.gui.widgets import gallery_panel as panel_module

    panel = GalleryPanel()
    qtbot.addWidget(panel)

    items = [_make_gallery_item(tmp_path, i) for i in range(1, 4)]
    decodes = []
    real_imdecode = cv2.imdecode

    def counting_imdecode(buf, flags):
        decodes.append(int(buf.shape[0]) if buf is not None else -1)
        return real_imdecode(buf, flags)

    monkeypatch.setattr(panel_module.cv2, "imdecode", counting_imdecode)

    panel.set_items(items)
    first_pass = len(decodes)
    panel.set_items(items)

    assert first_pass == 3, "第一次建立缩略图本该每张解一次"
    assert len(decodes) == first_pass, "同样的条目刷新时又整库重解了一遍"


def test_gallery_panel_emits_multiple_ids_for_delete(qtbot, tmp_path: Path):
    panel = GalleryPanel()
    qtbot.addWidget(panel)
    panel.show()

    items = [_make_gallery_item(tmp_path, 1), _make_gallery_item(tmp_path, 2)]
    panel.set_items(items)
    panel.view_mode_combo.setCurrentIndex(1)

    selection_model = panel.table.selectionModel()
    row0 = panel.table.model().index(0, 0)
    row1 = panel.table.model().index(1, 0)
    selection_model.select(
        row0,
        QtCore.QItemSelectionModel.SelectionFlag.Select | QtCore.QItemSelectionModel.SelectionFlag.Rows,
    )
    selection_model.select(
        row1,
        QtCore.QItemSelectionModel.SelectionFlag.Select | QtCore.QItemSelectionModel.SelectionFlag.Rows,
    )

    deleted_ids = []
    panel.deleteRequested.connect(lambda ids: deleted_ids.append(ids))

    panel._delete_selected_item()

    assert deleted_ids == [[1, 2]]
