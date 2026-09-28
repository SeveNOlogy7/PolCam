"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

from types import SimpleNamespace

from polcam.core.toolbar_controller import ToolbarController
from polcam.gui.widgets.tool_bar import ToolBar


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
