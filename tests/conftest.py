"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

import pytest
from qtpy import QtWidgets
import sys
from unittest.mock import MagicMock


def _make_mock_camera():
    """构造兼容旧集成测试的模拟相机。"""
    camera = MagicMock()
    state = {
        "connected": False,
        "streaming": False,
        "connect_message": "",
    }

    def connect():
        state["connected"] = True
        state["connect_message"] = ""
        return True, ""

    def start():
        result = camera.connect()
        if isinstance(result, tuple):
            success, message = result
        else:
            success, message = bool(result), ""
        state["connected"] = bool(success)
        state["connect_message"] = message
        return success, message

    def stop():
        state["connected"] = False
        state["streaming"] = False
        return True

    def start_streaming():
        state["streaming"] = True

    def stop_streaming():
        state["streaming"] = False

    camera.connect.side_effect = connect
    camera.start.side_effect = start
    camera.stop.side_effect = stop
    camera.start_streaming.side_effect = start_streaming
    camera.stop_streaming.side_effect = stop_streaming
    camera.enumerate_devices.return_value = (1, [{"model_name": "Mock Camera"}])
    camera.is_connected.side_effect = lambda: state["connected"]
    camera.is_streaming.side_effect = lambda: state["streaming"]
    camera.get_last_exposure.return_value = 5000.0
    camera.get_last_gain.return_value = 10.0
    camera.get_exposure_time.return_value = 5000.0
    camera.get_gain.return_value = 10.0
    camera.get_roi.return_value = (0, 0, 16, 16)
    camera.get_sensor_size.return_value = (16, 16)
    camera.get_frame.return_value = None
    camera.device_manager = MagicMock()
    camera.device_manager.update_all_device_list.return_value = (1, ["dev1"])
    camera.set_exposure_time = MagicMock()
    camera.set_gain = MagicMock()
    camera.set_exposure_auto = MagicMock()
    camera.set_gain_auto = MagicMock()
    camera.set_exposure_once = MagicMock()
    camera.set_gain_once = MagicMock()
    return camera

@pytest.fixture(scope="session")
def qapp():
    """创建QApplication实例"""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    yield app


@pytest.fixture
def mock_camera():
    return _make_mock_camera()
