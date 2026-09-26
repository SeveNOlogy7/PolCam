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


def test_polarization_parameter_maps_skip_enhancement():
    """显示增强只能动强度图，不能动 DoLP/AoLP/DoCP 参数图。

    _enhance_images 里那句“跳过偏振参数图”的判据是 len(shape) < 2，而参数图是 2D，
    所以一个都没跳过；亮度调到非 1.0 时 float32 的 0-1 数据被 convertScaleAbs 变成
    全 255 的 uint8，而工具栏正是拿这几条数组上色并写成“原始偏振度数据”的 .npy。
    """
    import numpy as np

    from polcam.core.processing_module import (
        DEFAULT_PROCESSING_PARAMS,
        ProcessingTask,
        ProcessingMode,
    )

    params = dict(DEFAULT_PROCESSING_PARAMS)
    params['brightness'] = 1.5

    module = ProcessingModule()
    assert module.initialize()
    frame = np.linspace(0, 200, 16 * 16, dtype=np.uint8).reshape(16, 16)

    result = module._process_task(ProcessingTask(
        frame=frame, mode=ProcessingMode.POLARIZATION, params=params
    ))

    merged, dolp, aolp, docp = result.images
    assert dolp.dtype == np.float32, f"参数图被改成 {dolp.dtype} 了"
    assert 0.0 <= float(dolp.min()) and float(dolp.max()) <= 1.0, (
        f"DoLP 逃出物理区间 [{dolp.min()}, {dolp.max()}]"
    )
    assert 0.0 <= float(aolp.min()) and float(aolp.max()) <= 180.0
    assert len(np.unique(dolp)) > 1, "DoLP 被增强压成了单一值"
    # 强度图仍然应该吃到亮度设置，别把两边一起改掉
    assert merged.dtype == np.uint8
    module.destroy()


def test_cached_result_is_keyed_by_the_params_that_produced_it():
    """缓存必须按“产出它的那份参数”记键，而不是按记下它时的实时参数。

    记缓存曾经用的是 self._params，结果却是用 task.params 算出来的；处理途中调
    一下亮度，这条结果就被登记到另一个参数集名下 —— 新设置看起来毫无反应，而它真正
    对应的那份渲染再也回不来。
    """
    import numpy as np

    from polcam.core.processing_module import (
        DEFAULT_PROCESSING_PARAMS,
        ProcessingTask,
        ProcessingMode,
    )

    frame = np.linspace(0, 200, 16 * 16, dtype=np.uint8).reshape(16, 16)
    params_a = dict(DEFAULT_PROCESSING_PARAMS)
    params_b = dict(DEFAULT_PROCESSING_PARAMS)
    params_b['brightness'] = 1.5
    task_a = ProcessingTask(frame=frame, mode=ProcessingMode.RAW, params=params_a)
    task_b = ProcessingTask(frame=frame, mode=ProcessingMode.RAW, params=params_b)

    module = ProcessingModule()
    assert module.initialize()
    module._params = dict(params_a)

    result_a = module._process_task(task_a)

    module._params = dict(params_b)

    # 记下 result_a 用的是 task_a 的键，所以再问一次仍然应该是同一条缓存
    assert module._process_task(task_a) is result_a
    # 换参数就是另一次计算，不能命中上面那条
    result_b = module._process_task(task_b)
    assert result_b is not result_a
    assert not np.array_equal(result_a.images[0], result_b.images[0]), (
        "brightness=1.5 命中了 brightness=1.0 的缓存，新设置没有生效"
    )
    module.destroy()


def test_clear_cache_drops_the_white_balance_gains():
    """清缓存必须连白平衡增益一起清。

    set_camera_type() 就是靠 clear_cache() 换相机状态的，而 _wb_cache 不在它管范围内，
    于是换一台相机后最多 2 秒里仍然沿用上一台算出来的增益。
    """
    import numpy as np

    from polcam.core.processing_module import ProcessingModule

    module = ProcessingModule()
    assert module.initialize()
    module._wb_cache.set_merged(np.array([1.2, 1.0, 0.8], dtype=np.float32))
    assert module._wb_cache.get_merged() is not None

    module.clear_cache()

    assert module._wb_cache.get_merged() is None, "旧相机的白平衡增益活过了换相机"


def test_camera_config_swaps_in_one_step(monkeypatch):
    """换相机配置必须一次性生效，不能先拆掉再建。

    set_camera_type 以前先把 _image_format_convert/_pixel_format 置 None 再重建，
    工作线程在这两步之间进来就会读到 None 转换器（AttributeError 丢帧），
    或者用旧转换器算出的缓冲容量交给新转换器去做转换。
    """
    import polcam.core.processing_module as pm
    from polcam.core.camera_module import CameraType

    module = pm.ProcessingModule()
    assert module.initialize()

    observed = []

    class HalfBuiltVisible(Exception):
        pass

    class FakeConvert:
        def _record(self):
            observed.append((module._image_format_convert, module._pixel_format))

        def __init__(self):
            self._record()

        def set_dest_format(self, *args):
            self._record()

        def set_valid_bits(self, *args):
            self._record()

    monkeypatch.setattr(pm, "ImageFormatConvert", FakeConvert)
    entry = pm.GxPixelFormatEntry

    module.set_camera_type(CameraType.NORMAL_COLOR, None, entry.MONO8)
    assert module._image_format_convert is not None and module._pixel_format is not None

    # 第二次才是关键：重建期间工作线程看到的必须仍然是上一份完整配置
    observed.clear()
    module.set_camera_type(CameraType.NORMAL_COLOR, None, entry.BGR8)

    assert observed, "FakeConvert 没被调用，测试没覆盖到重建过程"
    torn = [state for state in observed if state[0] is None or state[1] is None]
    assert not torn, f"重建期间工作线程能读到半构造状态: {torn}"


def test_cache_key_distinguishes_frames_that_share_bytes():
    """键必须带上帧的形状/类型，否则同字节不同形的两帧会共用一条结果。"""
    import numpy as np

    from polcam.core.processing_module import (
        DEFAULT_PROCESSING_PARAMS,
        ProcessingTask,
        ProcessingMode,
    )

    module = ProcessingModule()
    assert module.initialize()
    pixels = np.arange(256, dtype=np.uint8)
    tall = pixels.reshape(16, 16)
    wide = pixels.reshape(8, 32)
    params = dict(DEFAULT_PROCESSING_PARAMS)
    key = lambda frame: module._get_cache_key(ProcessingTask(
        frame=frame, mode=ProcessingMode.RAW, params=params))

    assert key(tall) != key(wide), "16x16 与 8x32 撞了同一个缓存键"
    assert key(tall) != key(tall.astype(np.int8)), "同形状不同 dtype 撞了同一个缓存键"


def test_get_last_result_returns_the_last_computed_result():
    """算出来的结果必须留得住。

    _last_result 以前只被 clear_cache() 置 None，从未赋值，所以 get_last_result()
    永远返回 None，reprocess_last_frame() 也永远不排任务。
    """
    import numpy as np

    from polcam.core.processing_module import (
        DEFAULT_PROCESSING_PARAMS,
        ProcessingTask,
        ProcessingMode,
    )

    module = ProcessingModule()
    assert module.initialize()
    frame = np.linspace(0, 200, 16 * 16, dtype=np.uint8).reshape(16, 16)

    assert module.get_last_result() is None
    module.reprocess_last_frame()
    assert module.get_task_count() == 0

    result = module._process_task(ProcessingTask(
        frame=frame, mode=ProcessingMode.RAW, params=dict(DEFAULT_PROCESSING_PARAMS)))

    assert module.get_last_result() is result


def test_result_carries_the_timestamp_of_its_frame():
    """结果必须自带它那一帧的采集时间戳，而不是让 GUI 事后去猜。

    连续采集里处理耗时超过帧间隔时，FRAME_CAPTURED(N+1) 会先于
    FRAME_PROCESSED(N) 到达同一条派发队列，届时 main_window._current_frame_timestamp
    已经是下一帧的了。
    """
    import numpy as np
    from datetime import datetime

    from polcam.core.processing_module import (
        DEFAULT_PROCESSING_PARAMS,
        ProcessingTask,
        ProcessingMode,
    )

    stamp = datetime(2026, 9, 26, 12, 0, 0)
    module = ProcessingModule()
    assert module.initialize()
    frame = np.linspace(0, 200, 16 * 16, dtype=np.uint8).reshape(16, 16)

    result = module._process_task(ProcessingTask(
        frame=frame, mode=ProcessingMode.RAW,
        params=dict(DEFAULT_PROCESSING_PARAMS), capture_timestamp=stamp))

    assert result.capture_timestamp == stamp


def _raw_task(frame):
    from polcam.core.processing_module import (
        DEFAULT_PROCESSING_PARAMS,
        ProcessingTask,
        ProcessingMode,
    )
    return ProcessingTask(frame=frame, mode=ProcessingMode.RAW,
                          params=dict(DEFAULT_PROCESSING_PARAMS))


def test_frame_cache_evicts_the_least_recently_used_result():
    """要踢最久没用过的，不是最早写入的。

    这条缓存存在的意义就是切显示模式时当前帧不重算；FIFO 下你反复查看的那一帧会被
    几张路过的帧挤掉。
    """
    import numpy as np

    frames = [np.full((16, 16), i, dtype=np.uint8) for i in range(3)]
    module = ProcessingModule()
    assert module.initialize()
    module._max_cache_size = 2
    module._max_cache_bytes = 10 ** 9

    first = module._process_task(_raw_task(frames[0]))
    second = module._process_task(_raw_task(frames[1]))
    # 再看一眼第一帧 —— 它就此变成“最近用过”，最久没用的换成第二帧
    assert module._process_task(_raw_task(frames[0])) is first

    module._process_task(_raw_task(frames[2]))

    assert module._process_task(_raw_task(frames[0])) is first, "被查看的帧被挤掉了"
    assert module._process_task(_raw_task(frames[1])) is not second, "该被挤掉的没挤掉"


def test_frame_cache_is_bounded_by_bytes_not_entry_count():
    """上限要按内存算：一条 QUAD 结果可以是几十 MB，条数兜不住。"""
    import numpy as np

    module = ProcessingModule()
    assert module.initialize()
    module._max_cache_size = 100
    small = np.zeros((16, 16), dtype=np.uint8)          # 256 B
    big = np.full((512, 512), 7, dtype=np.uint8)       # 256 KiB
    # 只够留下一条大结果 + 一条小结果，第二条大结果进来就必须挤掉东西
    module._max_cache_bytes = big.nbytes + small.nbytes

    module._process_task(_raw_task(small))
    kept_small = dict(module._frame_cache)
    module._process_task(_raw_task(big))
    module._process_task(_raw_task(np.full((512, 512), 9, dtype=np.uint8)))

    total = sum(size for _, size in module._frame_cache.values())
    assert total <= module._max_cache_bytes, f"缓存里还留着 {total} 字节"
    assert len(module._frame_cache) < len(kept_small) + 2, "没有按字节淘汰"
