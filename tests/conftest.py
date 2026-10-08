"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

import gc
import pytest
import sys
import threading
from pathlib import Path
from unittest import mock
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

import shiboken6
from qtpy import QtCore, QtWidgets


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
        return True

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


@pytest.fixture(scope="session", autouse=True)
def isolate_user_directories(tmp_path_factory):
    """测试期间把用户主目录换到临时目录，真实 ~/PolCam 一个字都不能动。

    两层原因：
    1. SettingsService 现在用 ~/PolCam/settings.ini 的绝对路径构造 QSettings，
       `QSettings.setPath` 只影响"按 organization/app 名解析默认位置"那条路，对显式
       filePath 无效。实测跑完一轮测试后，用户配置里的 auto_save_directory 变成了
       pytest 的临时目录，display_mode/retarder 也被测试窗口盖掉。
    2. gallery.db 和 logs 同样在 ~/PolCam 下（gallery_service._build_default_db_path、
       utils.logger），测试建的是真库真日志。
    Path.home() 是这三处唯一的入口，所以按它收口，而不是逐个模块打补丁。
    注意：这个补丁只在本进程有效。会另起 python 跑 PolCam 代码的测试（test_gui 里的 GC
    探针）要在子进程自己 patch Path.home()——不能改 HOME/USERPROFILE，大恒 SDK 也读它们，
    实测改了探针子进程直接 0xc0000409 崩掉。
    QSettings 的默认格式仍然设为 Ini+临时路径：那是 _migrate_legacy_settings 里
    `QSettings()` 读老配置那条路，不能让它去碰注册表。
    """
    home = tmp_path_factory.mktemp("home")
    mpatch = pytest.MonkeyPatch()
    mpatch.setattr(Path, "home", classmethod(lambda cls: home))

    path = tmp_path_factory.mktemp("qsettings") / "polcam-test.ini"
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat,
                             QtCore.QSettings.Scope.UserScope, str(path))
    yield home
    mpatch.undo()


@pytest.fixture
def mock_camera():
    return _make_mock_camera()


@pytest.fixture(scope="session", autouse=True)
def keep_the_collector_out_of_event_dispatch():
    """整个测试会话关掉自动的循环引用回收。

    Qt 的控件树不该由收集器按它挑的顺序销毁 —— main_window 那个 fixture 自己
    shiboken6.delete 就是这个原因。但收集器什么时候跑是 CPython 按分配次数定的，而它
    偏偏会撞进 pytest-qt 泵事件的那一刻：容器里实测 tests/test_gui.py 在 Linux 上 8 次崩
    3 次，faulthandler 的栈是 "Garbage-collecting" 停在 pytestqt/plugin.py:_process_events；
    gc.disable() 之后同样 8 次全过。用 gc.DEBUG_SAVEALL 数出来的待销毁对象（90 个
    MainWindow、132 个 ImageToolbar、130 个 QTimer）在 1.1.1 的基线上一模一样 —— 不是新漏
    了什么，只是多出来的分配让回收更常落在坏时机上。

    引用计数照常工作；剩下的环交给 tools/run_tests.py 的"一个文件一个进程"，进程一退就没了。
    """
    was_enabled = gc.isenabled()
    gc.disable()
    yield
    if was_enabled:
        gc.enable()


@pytest.fixture
def main_window(qapp):
    """建一个主窗口，用完关掉。

    谁建谁关：MainWindow 会把 12 类事件订阅到单例 EventManager 上，不关的话订阅
    和桥对象一直留在进程里。窗口现在能被回收了，留着订阅更危险 —— 回收发生在测试
    之间的任意时刻，总线上线时桥的原生对象已经没了（RuntimeError: Signal source
    has been deleted），coverage 的收尾时序下直接崩成 0xc0000409。
    关窗里的异常一律变成失败，而不是弹一个阻塞的模态框。
    """
    from polcam.gui.main_window import MainWindow

    window = MainWindow()
    yield window
    with mock.patch('polcam.gui.main_window.QtWidgets.QMessageBox.warning') as warning:
        window.close()
    assert not warning.called, f"窗口关闭时 closeEvent 抛了异常: {warning.call_args}"
    # 关掉的窗口还留着一整棵控件树。pytest 在收尾时会连做 5 次 gc.collect()
    # （_pytest/unraisableexception.cleanup），由收集器去销毁 Qt 对象就是崩溃现场；
    # 趁 QApplication 还在的时候把树一次性删掉，就没有什么留给收集器收尾了。
    shiboken6.delete(window)


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
    # 事件线程是个 while True 的守护线程，退出时它还活着就会在解释器收尾阶段去回调
    # 原生对象已经不在了的订阅者（实测过 RuntimeError: Signal source has been deleted），
    # coverage 的时序下直接崩成 0xc0000409。
    from polcam.core.events import EventManager
    EventManager().shutdown(timeout=2.0)
