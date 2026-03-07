"""
MIT License
Copyright (c) 2024 Junhao Cai
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
