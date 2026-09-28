"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

from types import SimpleNamespace

from polcam.core.toolbar_controller import ToolbarController
from polcam.gui.widgets.tool_bar import ToolBar


def test_loading_a_file_is_refused_while_the_stream_is_running(tmp_path, qapp):
    """采集中不能加载文件：屏幕会被实时帧冲掉，而 _current_frame 已经变成文件内容。

    真机实测：1024x1024、均值 200 的文件在连续采集中打开，画面一直是实时帧
    （2448x2048、均值 15），用户看不到任何反应；紧接着按「保存原始图像」，写盘的是那个
    旧文件的像素（存回均值 200），不是屏幕上正在看的画面。
    """
    import cv2
    import numpy as np
    from unittest.mock import MagicMock

    live_frame = np.full((8, 8), 15, dtype=np.uint8)
    path = tmp_path / "old.tiff"
    cv2.imwrite(str(path), np.full((16, 16), 200, dtype=np.uint8))

    main_window = SimpleNamespace(toolbar=ToolBar(), camera=MagicMock(),
                                  status_label=MagicMock())
    main_window.camera.is_streaming.return_value = True
    controller = ToolbarController(main_window)
    controller.update_current_frame(live_frame)

    assert controller.load_raw_file(str(path)) is None, "采集中仍然把文件加载进来了"
    assert controller._current_frame is live_frame, "_current_frame 被换成了文件内容"
    main_window.status_label.setText.assert_called_once()
    assert "停止采集" in main_window.status_label.setText.call_args[0][0]

    main_window.camera.is_streaming.return_value = False
    loaded = controller.load_raw_file(str(path), publish_event=False)
    assert loaded is not None and loaded.shape == (16, 16), "停止采集后应该照常打开"


def test_polarization_npy_records_the_signed_docp_contract(tmp_path, qapp):
    """导出的 npy 要自带"符号有没有物理意义"，否则读的人会拿噪声当旋向。"""
    import numpy as np

    controller = ToolbarController(SimpleNamespace(toolbar=ToolBar()))
    controller._save_polarization_data(
        np.zeros((2, 2), dtype=np.float32),
        np.zeros((2, 2), dtype=np.float32),
        np.full((2, 2), -0.5, dtype=np.float32),
        str(tmp_path), "case",
        docp_signed=True,
        retarder={'fast_axis_degrees': (0.0, 45.0), 'rank': 4},
    )

    saved = np.load(tmp_path / "case_POL.npy", allow_pickle=True).item()
    assert bool(saved['docp_signed']) is True
    assert saved['retarder']['fast_axis_degrees'] == (0.0, 45.0)
    assert np.allclose(saved['docp'], -0.5)


def test_toolbar_controller_destroy_disconnects_every_action(qapp):
    """销毁要断开全部 6 个 action。

    _do_initialize 连了 6 个，_do_destroy 只断了 5 个 —— open_raw_action 上那份还挂着
    控制器（连带整个窗口）。BaseModule.destroy() 会把 _initialized 复位，于是重新
    initialize() 之后同一个 action 上叠了两个槽：点一次"打开原始图像"弹两个文件框，
    后一次的 load_raw_file 把前一次的结果盖掉。
    """
    toolbar = ToolBar()
    controller = ToolbarController(SimpleNamespace(toolbar=toolbar))
    calls = []
    controller._handle_open_raw = lambda: calls.append(1)   # 先换掉，connect 才拿得到它

    assert controller.initialize()
    toolbar.open_raw_action.trigger()
    assert len(calls) == 1

    assert controller.destroy()
    assert controller.initialize()

    toolbar.open_raw_action.trigger()
    assert len(calls) == 2, f"一次点击触发了 {len(calls) - 1} 次打开对话框"


def test_save_result_writes_the_file_set_verified_on_the_device(tmp_path, qapp, monkeypatch):
    """「保存处理结果」在偏振分析模式该写出哪几个文件，用真机核对过，现在锁住。

    真机（MER2-502-79U3M-HS POL，2448x2048）实测写出 6 个文件：合成图是 2D 灰度，
    DOLP/AOLP/DOCP 都是上色后的 3 通道 uint8，另有一份四分合成图和 _POL.npy（float32
    原值 + docp_signed）。这段代码在测试里从没跑过，而浮点参数图一旦被直接当图像存盘就会
    被静默截成 8bit（DoLP 0..1 折进 0/1，出来一张近黑的图）—— 原值必须走 .npy。
    """
    import cv2
    import numpy as np
    from unittest.mock import MagicMock
    from qtpy import QtWidgets
    from polcam.core.processing_module import ProcessingMode, ProcessingResult

    main_window = SimpleNamespace(toolbar=ToolBar(), camera=MagicMock(), status_label=MagicMock(),
                                  settings_service=MagicMock())
    controller = ToolbarController(main_window)
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    names = []

    def fake_name(self, title, timestamp=None, mode_str=""):
        names.append(mode_str)
        return str(tmp_path / f"shot{len(names)}"), ".tiff", True

    monkeypatch.setattr(ToolbarController, "_get_save_filename", fake_name)

    dolp = np.full((16, 16), 0.5, dtype=np.float32)
    controller._last_result = ProcessingResult(
        mode=ProcessingMode.POLARIZATION,
        images=[np.zeros((16, 16), dtype=np.uint8), dolp,
                np.full((16, 16), 90.0, dtype=np.float32),
                np.full((16, 16), -0.25, dtype=np.float32)],
        metadata={'type': ['merged', 'dolp', 'aolp', 'docp'], 'is_color': False,
                  'pol_wb_enabled': False, 'docp_signed': True,
                  'retarder': {'in_path': True, 'angles_deg': (45.0,)}},
        timestamp=0.0, capture_timestamp=0.0)
    controller._last_result_timestamp = 0.0

    controller._handle_save_result()

    written = sorted(p.name for p in tmp_path.iterdir())
    assert written == ['shot1_AOLP.tiff', 'shot1_DOCP.tiff', 'shot1_DOLP.tiff',
                       'shot1_MERGED_GRAY.tiff', 'shot1_POL.npy',
                       'shot1_POLARIZATION_QUAD_COMPOSITE.tiff'], written

    params = np.load(tmp_path / "shot1_POL.npy", allow_pickle=True).item()
    assert params['dolp'].dtype == np.float32 and params['dolp'].shape == (16, 16)
    assert params['docp_signed'] is True
    assert params['retarder']['angles_deg'] == (45.0,)
    for suffix in ('DOLP', 'AOLP', 'DOCP'):
        img = cv2.imdecode(np.fromfile(str(tmp_path / f"shot1_{suffix}.tiff"), dtype=np.uint8),
                           cv2.IMREAD_UNCHANGED)
        assert img.shape == (16, 16, 3) and img.dtype == np.uint8, f"{suffix} 没有被上色成 3 通道"

    # 四角度灰度：四个角度各一张 + 一张 2x 尺寸的四分合成图（真机同样核对过 5 个文件）
    controller._last_result = ProcessingResult(
        mode=ProcessingMode.QUAD_GRAY,
        images=[np.full((16, 16), v, dtype=np.uint8) for v in (10, 20, 30, 40)],
        metadata={'angles': [0, 45, 90, 135], 'wb_enabled': False,
                  'quad_titles': ['0 deg', '45 deg', '90 deg', '135 deg']},
        timestamp=0.0, capture_timestamp=0.0)
    controller._handle_save_result()

    quad_files = sorted(p.name for p in tmp_path.iterdir() if p.name.startswith("shot2"))
    assert quad_files == ['shot2_GRAY_0.tiff', 'shot2_GRAY_135.tiff', 'shot2_GRAY_45.tiff',
                          'shot2_GRAY_90.tiff', 'shot2_GRAY_QUAD_COMPOSITE.tiff'], quad_files
    tile = cv2.imdecode(np.fromfile(str(tmp_path / "shot2_GRAY_45.tiff"), dtype=np.uint8),
                        cv2.IMREAD_UNCHANGED)
    assert tile.shape == (16, 16) and int(tile[0, 0]) == 20, "45° 那张存的不是 45° 的角度图"
