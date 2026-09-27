"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

日志系统配置
提供统一的日志格式和输出设置
"""

import logging
import os
import sys
from pathlib import Path
from datetime import datetime

def _today() -> str:
    """当天日期，日志文件名按它走。单独抽出来是为了能测跨天。"""
    return datetime.now().strftime("%Y%m%d")


class DailyFileHandler(logging.FileHandler):
    """按天命名的日志文件，跨零点之后换到当天那个文件继续写。

    原来文件名只在启动时算一次，于是长会话一直往开机那天的文件里追加 —— 而排查时让人
    去看的正是"今天"的日志（PolCam.spec 里写的就是 ~/PolCam/logs 下按日期命名的文件）。
    """

    def __init__(self, directory: Path, encoding: str = "utf-8"):
        self._directory = Path(directory)
        self._date = _today()
        super().__init__(self._directory / f"polcam_{self._date}.log",
                         mode="a", encoding=encoding)

    def emit(self, record: logging.LogRecord):
        # 换文件这件事只能在 emit 里查：普通 FileHandler 根本不会去问 shouldRollover，
        # 那个钩子只有 BaseRotatingHandler.emit 才会调。
        # 也不能就这么裸调 doRollover：日志目录被清掉时 _open() 会抛，而全项目都在
        # except 块里记日志 —— 一抛就把真正该记的异常顶掉了。交给 handleError，
        # 让失败走 logging 自己的报告路径。
        if _today() != self._date:
            try:
                self.doRollover()
            except Exception:
                self.handleError(record)
                return
        super().emit(record)

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        self._date = _today()
        self._directory.mkdir(parents=True, exist_ok=True)
        target = self._directory / f"polcam_{self._date}.log"
        self.baseFilename = os.path.abspath(str(target))
        self.stream = self._open()

def setup_logger(log_level=logging.INFO):
    """设置日志系统
    
    Args:
        log_level: 日志级别，默认为INFO
    """
    # 创建根日志记录器
    logger = logging.getLogger("polcam")
    logger.setLevel(log_level)
    
    # 如果已经有处理器，不重复添加
    if logger.handlers:
        return logger
        
    # 创建日志目录
    log_dir = Path.home() / "PolCam" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建文件处理器
    file_handler = DailyFileHandler(log_dir)
    file_handler.setLevel(log_level)

    # 创建格式器
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 设置格式器
    file_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)

    # 有控制台才挂控制台输出。打包版 console=False 时 sys.stdout/stderr 都是 None，
    # 而 StreamHandler 会静默吞掉每次写入 —— 看着像配了，其实一声不响。
    console_stream = sys.stdout if sys.stdout is not None else sys.stderr
    if console_stream is not None:
        console_handler = logging.StreamHandler(console_stream)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
