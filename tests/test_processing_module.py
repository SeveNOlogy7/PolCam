"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

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

    线程曾经以绑定方法 self._processing_loop 作为 target，那份隐式强引用会让线程
    反过来把 module 钉在内存里永不回收，并在 module 被丢弃后继续访问已释放的
    Qt 对象（CI 上表现为 0xc0000374 堆损坏）。

    这里刻意不调用 gc.collect()：引用计数就足以回收 ProcessingModule，而全量 GC 会
    顺带回收前面测试泄漏下来的 PySide6 包装器，在 Windows 上同样触发 0xc0000374。
    """
    before = len(_processing_loop_threads())

    modules = []
    for _ in range(3):
        module = ProcessingModule()
        assert module.initialize()
        modules.append(module)
    del module

    assert len(_processing_loop_threads()) == before + 3

    del modules

    deadline = time.time() + 5.0
    while time.time() < deadline and len(_processing_loop_threads()) > before:
        time.sleep(0.1)

    leaked = len(_processing_loop_threads()) - before
    assert leaked == 0, f"{leaked} 个处理线程在模块被回收后仍在运行"
