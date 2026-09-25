"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

import threading
import time

import numpy as np

from polcam.core.events import EventType
from polcam.core.processing_module import ProcessingModule


def _processing_loop_threads():
    return [
        t for t in threading.enumerate()
        if getattr(t._target, "__name__", "") == "_processing_loop"
]


def _worker_of(module):
    """找出 module 自己的工作线程。

    套件里同时飘着别的测试泄漏下来的线程，所以只能按身份认领，不能用全局计数做差。
    """
    for thread in _processing_loop_threads():
        args = getattr(thread, "_args", ())
        if args and args[0]() is module:
            return thread
    return None


def test_processing_thread_exits_when_module_is_collected():
    """工作线程不得把 module 钉在内存里。

    线程曾经以绑定方法 self._processing_loop 作为 target，那份隐式强引用会让线程
    反过来把 module 钉在内存里永不回收，并在 module 被丢弃后继续访问已释放的
    Qt 对象（CI 上表现为 0xc0000374 堆损坏）。

    这里刻意不调用 gc.collect()：引用计数就足以回收 ProcessingModule，而全量 GC 会
    顺带回收前面测试泄漏下来的 PySide6 包装器，在 Windows 上同样触发 0xc0000374。
    """
    modules = []
    workers = []
    for _ in range(3):
        module = ProcessingModule()
        assert module.initialize()
        worker = _worker_of(module)
        assert worker is not None, "initialize() 没有起工作线程"
        modules.append(module)
        workers.append(worker)
    del module

    del modules

    for worker in workers:
        started = time.perf_counter()
        worker.join(timeout=5.0)
        assert not worker.is_alive(), "模块被回收后工作线程仍在运行"
        elapsed = time.perf_counter() - started
        assert elapsed < 0.5, (
            f"工作线程 {elapsed:.2f}s 后才退出，说明它在靠超时轮询而不是靠停止信号醒来"
        )


def _wait_for_processed(module, frame, timeout=5.0):
    """提交一帧，返回是否在超时前等到 FRAME_PROCESSED。"""
    processed = threading.Event()
    module.subscribe_event(EventType.FRAME_PROCESSED, lambda event: processed.set())
    module.process_frame(frame)
    return processed.wait(timeout=timeout)


def test_worker_restarts_after_stop():
    """stop() 之后再 start() 必须真的把工作线程重新拉起来。

    BaseModule.start() 见 _initialized 为真就短路，而 _do_start 只翻一个标志位，于是
    重启后 is_running() 为真、工作线程却已经随上次 stop() 退出，画面永久停更。
    """
    module = ProcessingModule()
    assert module.initialize()
    assert module.start()
    assert module.stop()
    assert module.start()

    frame = np.zeros((16, 16), dtype=np.uint8)
    assert _wait_for_processed(module, frame), "重启后没有工作线程在处理帧"

    module.stop()


def test_stop_succeeds_while_tasks_are_queued():
    """队列里还有待处理任务时 stop() 也要成功。

    _do_stop 用 put(None) 当毒药信号，而 PriorityQueue 比较元素，None 与
    ProcessingTask 不可比会抛 TypeError —— stop() 返回 False，_running 卡在真，
    线程也没被 join。
    """
    module = ProcessingModule()
    assert module.initialize()
    assert module.start()
    assert module.stop()
    # 没有消费者的时候塞任务，让队列在 stop() 时确定性地非空
    assert module.start()
    module._stop_flag = True

    frame = np.zeros((16, 16), dtype=np.uint8)
    for _ in range(3):
        module.process_frame(frame)
    assert not module._task_queue.empty()

    assert module.stop() is True
    assert module.is_running() is False


def test_destroy_stops_the_worker_even_if_start_was_never_called():
    """只 initialize() 过的模块，destroy() 也必须把工作线程收走。

    MainWindow 就是这么用的：initialize() 起线程，然后一直直接 process_frame()，
    从不调用 start()。于是 _running 永远是 False，BaseModule.stop() 走 early-return，
    closeEvent 里的 stop() 根本没设 _stop_flag —— 线程带着一个没人管的模块每秒醒一次。
    """
    module = ProcessingModule()
    assert module.initialize()
    worker = _worker_of(module)
    assert worker is not None, "initialize() 没有起工作线程"

    assert module.destroy() is True

    worker.join(timeout=5.0)
    assert not worker.is_alive(), "destroy() 之后工作线程还活着"


def test_drain_releases_abandoned_workers():
    """被丢弃的工作线程要能在测试结束时收干净。

    测试里建了 MainWindow 却从不 close，处理线程就会带着活的 module 一直每秒醒一次；
    解释器 finalize 时正好醒着的守护线程是 0xc0000374 的来源。
    """
    from conftest import drain_processing_workers

    module = ProcessingModule()
    assert module.initialize()
    assert module.start()

    drain_processing_workers()

    assert _processing_loop_threads() == []
    assert module.is_running() is False
