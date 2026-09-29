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


def test_set_items_keeps_every_row_when_a_file_is_unreadable(qtbot, tmp_path: Path):
    """读不出内容的文件也不能把面板带走 —— cv2.error 不是 OSError。

    上一条覆盖的是"文件不在了"（np.fromfile 抛 FileNotFoundError）。还有一种：路径在、
    内容坏（拷断的、0 字节的），cv2.imdecode 抛的是 cv2.error，
    isinstance(cv2.error, OSError) 实测为 False，所以只兜 OSError 的 except 漏掉了它，
    而 set_items 是先清空两个视图再逐条填，异常一冒出来面板就剩 0 行。
    """
    panel = GalleryPanel()
    qtbot.addWidget(panel)
    panel.show()

    good = [_make_gallery_item(tmp_path, 1), _make_gallery_item(tmp_path, 2)]
    broken = _make_gallery_item(tmp_path, 3)
    Path(broken.file_path).write_bytes(b"")          # 存在，但内容为空

    panel.set_items([broken] + good)

    assert panel.table.rowCount() == 3, "坏文件那行把后面所有行一起带走了"
    assert panel.preview_list.count() == 3
    assert panel.count_label.text() == "3 项"


def test_a_transient_decode_failure_is_not_cached(qtbot, tmp_path: Path, monkeypatch):
    """一次读失败不该被缓存成永久占位。

    文件被别的进程独占、杀毒正在扫，这类情况会自愈；按 (路径, mtime) 存住失败结果的话，
    好端端一张图在面板上永远是中性图标 —— mtime 没变就永不再试。
    """
    from polcam.gui.widgets import gallery_panel as panel_module

    panel = GalleryPanel()
    qtbot.addWidget(panel)
    item = _make_gallery_item(tmp_path, 7)
    real_imdecode = cv2.imdecode
    attempts = []
    state = {"fail_first": True}

    def flaky_imdecode(buf, flags):
        attempts.append(1)
        if state["fail_first"]:
            state["fail_first"] = False
            return None                      # 模拟一次"读不出内容"
        return real_imdecode(buf, flags)

    monkeypatch.setattr(panel_module.cv2, "imdecode", flaky_imdecode)

    panel.set_items([item])
    assert len(attempts) == 1
    panel.set_items([item])                  # 刷新一次，这次能读出来

    assert len(attempts) == 2, "失败结果被按 (路径, mtime) 缓存住了，刷新再也不会重读"
    assert (120, 120) in [(s.width(), s.height()) for s in
                          panel.preview_list.item(0).icon().availableSizes()], \
        "重读成功了却还挂着占位图标"


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


def test_a_refresh_keeps_the_items_the_user_had_selected(qtbot, tmp_path: Path):
    """采集后的自动刷新不许把用户刚选中的项洗掉。

    refresh_gallery() 每次自动保存后都会跑，而 set_items 是 `preview_list.clear()` +
    `table.setRowCount(0)` 整表重建：真机实测选中一项后按「单帧采集」，选区当场清空、
    「读取」/「删除」变灰（禁用状态的 QPushButton 点了没有任何反应），用户只能回头重选。
    """
    panel = GalleryPanel()
    qtbot.addWidget(panel)
    panel.show()

    items = [_make_gallery_item(tmp_path, i) for i in (1, 2, 3)]
    panel.set_items(items)

    panel.preview_list.item(1).setSelected(True)
    panel.preview_list.item(2).setSelected(True)
    assert panel.selected_item_ids() == [2, 3], "前提：缩略图视图里的多选应当读得到"
    assert panel.delete_button.isEnabled()

    panel.set_items(items)

    assert panel.selected_item_ids() == [2, 3], f"刷新把选区清了：{panel.selected_item_ids()}"
    assert panel.delete_button.isEnabled(), "选区回来了但按钮还是灰的"


def test_a_refresh_in_table_view_keeps_the_selection_too(qtbot, tmp_path: Path):
    """列表视图那条路同样要保住选区 —— 两种视图共用一次刷新。"""
    panel = GalleryPanel()
    qtbot.addWidget(panel)
    panel.show()

    items = [_make_gallery_item(tmp_path, i) for i in (1, 2, 3)]
    panel.set_items(items)
    panel.view_mode_combo.setCurrentIndex(1)

    flags = QtCore.QItemSelectionModel.SelectionFlag.Select | QtCore.QItemSelectionModel.SelectionFlag.Rows
    panel.table.selectionModel().select(panel.table.model().index(0, 0), flags)

    panel.set_items(items)

    assert panel.selected_item_ids() == [1], f"表格视图刷新后选区：{panel.selected_item_ids()}"
    assert panel.open_button.isEnabled(), "单选一项时「读取」应当可用"


def test_a_refresh_only_keeps_the_selection_that_still_exists(qtbot, tmp_path: Path):
    """被删掉的那一项不能凭空回到选区。"""
    panel = GalleryPanel()
    qtbot.addWidget(panel)
    panel.show()

    items = [_make_gallery_item(tmp_path, i) for i in (1, 2, 3)]
    panel.set_items(items)
    panel.preview_list.item(0).setSelected(True)
    panel.preview_list.item(1).setSelected(True)

    panel.set_items([items[2]])

    assert panel.selected_item_ids() == []
    assert not panel.open_button.isEnabled()
    assert not panel.delete_button.isEnabled()
