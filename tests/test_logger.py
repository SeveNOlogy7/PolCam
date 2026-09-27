"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

import logging
import shutil
from pathlib import Path

import pytest

from polcam.utils import logger as logger_module


@pytest.fixture
def isolated_logger(tmp_path: Path, monkeypatch):
    """把日志目录挪到 tmp_path，并给一次干净的 "polcam" logger。"""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    root = logging.getLogger("polcam")
    saved_handlers, saved_level = list(root.handlers), root.level
    root.handlers.clear()
    yield root, tmp_path
    for handler in list(root.handlers):
        handler.close()
        root.removeHandler(handler)
    root.handlers, root.level = saved_handlers, saved_level


def _file_handlers(root):
    return [h for h in root.handlers if isinstance(h, logging.FileHandler)]


def test_logger_writes_to_the_day_it_rolls_into(isolated_logger, monkeypatch):
    """跨零点之后要继续写进当天那个文件。

    文件名原本只在启动时算一次，于是一个长会话的日志一直往开机那天那个文件里追加 ——
    而排查问题时让人看的正是"今天"的日志（PolCam.spec 里写的就是按日期命名的文件）。
    """
    root, tmp_path = isolated_logger
    logger_module.setup_logger(logging.INFO)
    log_dir = tmp_path / "PolCam" / "logs"

    logging.getLogger("polcam.day1").info("第一天")
    day_one_files = set(log_dir.iterdir())

    monkeypatch.setattr(logger_module, "_today", lambda: "20260102")
    logging.getLogger("polcam.day2").info("第二天")

    rolled = log_dir / "polcam_20260102.log"
    assert rolled.exists(), f"跨天之后还在写旧文件: {sorted(p.name for p in log_dir.iterdir())}"
    assert "第二天" in rolled.read_text(encoding="utf-8")
    old = next(p for p in day_one_files if p.is_file())
    assert "第一天" in old.read_text(encoding="utf-8")


def test_a_missing_log_directory_does_not_raise_into_the_caller(isolated_logger, monkeypatch):
    """日志目录被清掉之后，记日志这个动作不能把异常抛回业务代码。

    全项目到处都在 except 块里 _logger.error(...)：日志自己一抛，真正该记的异常就被顶
    掉了。标准 FileHandler 把 _open() 包在自己的 try 里交给 handleError，而换日时的
    doRollover 是我们自己在 emit 里调的，没有人兜。顺带要求目录能重建 —— 用户的日志
    不该因为有人清理过一次就永久断掉。
    """
    root, tmp_path = isolated_logger
    logger_module.setup_logger(logging.INFO)
    log_dir = tmp_path / "PolCam" / "logs"
    handler = _file_handlers(root)[0]
    handler.close()                       # Windows 上要先放句柄才删得掉
    shutil.rmtree(log_dir)

    monkeypatch.setattr(logger_module, "_today", lambda: "20990101")
    logging.getLogger("polcam.next").error("换天后的第一条")

    rolled = log_dir / "polcam_20990101.log"
    assert rolled.exists(), "日志目录没被重建"
    assert "换天后的第一条" in rolled.read_text(encoding="utf-8")


def test_console_handler_is_not_installed_without_a_console(isolated_logger, monkeypatch):
    """打包版 console=False 时 sys.stdout/stderr 都是 None，别再挂一个吞掉一切的流处理器。

    StreamHandler(None) 会退回 sys.stderr，而那个在窗口版里同样是 None：每次 emit 内部
    抛 AttributeError，又被 handleError 静默吞掉（连报错的流都没有），日志一声不响。
    """
    root, _ = isolated_logger
    monkeypatch.setattr(logger_module.sys, "stdout", None)
    monkeypatch.setattr(logger_module.sys, "stderr", None)

    logger_module.setup_logger(logging.INFO)

    streams = [getattr(h, "stream", "n/a") for h in root.handlers]
    assert None not in streams, f"挂了流为 None 的处理器: {root.handlers}"
    assert _file_handlers(root), "文件日志还是要有的"
