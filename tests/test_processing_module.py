"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

import gc
import threading
import time


from polcam.core.processing_module import ProcessingModule


def _processing_loop_threads():
    return [
        t for t in threading.enumerate()
        if getattr(t._target, "__name__", "") == "_processing_loop"
    ]


def test_processing_thread_exits_when_module_is_collected():
    """工作线程不得把 module 钉在内存里。

    线程曾经以绑定方法 self._processing_loop 作为 target，那份隐式强引用让模块
    永远无法回收、线程永远不退出；累积几十个之后 Qt 事件循环会访问到已释放对象，
    在 CI 上表现为 0xc0000374 堆损坏。
    """
    before = len(_processing_loop_threads())

    modules = []
    for _ in range(3):
        module = ProcessingModule()
        assert module.initialize()
        modules.append(module)

    assert len(_processing_loop_threads()) == before + 3

    del modules
    gc.collect()

    deadline = time.time() + 5.0
    while time.time() < deadline and len(_processing_loop_threads()) > before:
        time.sleep(0.1)

    leaked = len(_processing_loop_threads()) - before
    assert leaked == 0, f"{leaked} 个处理线程在模块被回收后仍在运行"
