"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

from unittest.mock import MagicMock

import pytest

from polcam.gui.camera_select_dialog import CameraSelectDialog


def _fake_camera(devices):
    camera = MagicMock()
    state = {"connected": False}
    camera.is_connected.side_effect = lambda: state["connected"]
    camera.enumerate_devices.side_effect = lambda: (len(devices), list(devices))
    camera.start.side_effect = lambda: state.update(connected=True) or True
    camera.stop.side_effect = lambda: state.update(connected=False) or True
    return camera, state


M1 = {"index": 1, "model_name": "M1", "sn": "SN1", "access_status": 1}
M2 = {"index": 2, "model_name": "M2", "sn": "SN2", "access_status": 1}


def test_refresh_keeps_disconnect_available_when_the_connected_row_is_gone(qtbot):
    """独占打开的那台从列表里消失时，对话框不能把"断开"这条路一起带走。

    _update_button_states 原本只在"选中的正是已连接那台"时才给断开按钮；而 M1 被本进程
    独占之后，下一次枚举往往只报 M2，它还坐在第 0 行 —— 于是 selected_index(2) !=
    _connected_index(1)，按钮变成禁用的"连接"，这一场会话里再也脱不开那个句柄。
    """
    camera, state = _fake_camera([M1, M2])
    dialog = CameraSelectDialog(camera, [M1, M2])
    qtbot.addWidget(dialog)
    dialog._populate_table()
    dialog._table.selectRow(0)

    dialog._handle_connect()
    assert state["connected"]
    assert dialog._connect_btn.text() == "断开"

    camera.enumerate_devices.side_effect = lambda: (1, [M2])   # 重举只剩 M2
    dialog._handle_refresh()
    dialog._table.selectRow(0)

    assert dialog._connect_btn.isEnabled(), "已连接却没有任何可用的断开入口"
    assert dialog._connect_btn.text() == "断开"


def test_refresh_stops_claiming_the_gone_device_is_connected(qtbot):
    """列表里没有已连接那台时，信息栏要照实说。"""
    camera, state = _fake_camera([M1, M2])
    dialog = CameraSelectDialog(camera, [M1, M2])
    qtbot.addWidget(dialog)
    dialog._populate_table()
    dialog._table.selectRow(0)
    dialog._handle_connect()

    camera.enumerate_devices.side_effect = lambda: (1, [M2])
    dialog._handle_refresh()

    assert "M1" not in dialog._info_label.text() or "不在当前列表" in dialog._info_label.text(), \
        dialog._info_label.text()
