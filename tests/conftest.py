"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

import pytest
import sys
import threading
from unittest.mock import MagicMock

try:  # 真实 SDK 可用时不干预，保证有相机/驱动的机器上测的是真代码
    import gxipy  # noqa: F401
except Exception:  # 未安装大恒 Galaxy 驱动时 gxipy 在 import 阶段就会抛错
    for _gxipy_module in (
        "gxipy",
        "gxipy.gxiapi",
        "gxipy.gxwrapper",
        "gxipy.ImageFormatConvert",
        "gxipy.ImageProc",
        "gxipy.gxidef",
    ):
        sys.modules[_gxipy_module] = MagicMock()

from qtpy import QtWidgets


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


def drain_processing_workers(timeout=5.0):
    """收掉所有仍在运行的处理线程。

    测试里造出来的 MainWindow 从不 close，它们各自的 ProcessingModule 就一直活着；
    工作线程只握着 module 的弱引用，那份引用就在 Thread._args[0] 里，取回来 stop() 即可。
    不 drain 的话这些守护线程每秒醒一次，撞上解释器 finalize 就是 0xc0000374 堆损坏。
    """
    workers = [
        thread for thread in threading.enumerate()
        if getattr(thread._target, "__name__", "") == "_processing_loop"
    ]

    # 先让所有线程都看到停止标志再逐个 join：线程最迟一秒后才会醒来，
    # 边停边等会把 N 个线程的唤醒延迟串起来。用 destroy() 而不是 stop()，因为
    # 这些模块大多只 initialize() 过，stop() 会 early-return 什么也不做。
    for thread in workers:
        args = getattr(thread, "_args", ())
        module_ref = args[0] if args else None
        module = module_ref() if module_ref is not None else None
        if module is not None:
            module.destroy()

    for thread in workers:
        thread.join(timeout=timeout)


@pytest.fixture(scope="session", autouse=True)
def drain_processing_workers_at_exit():
    yield
    drain_processing_workers()
