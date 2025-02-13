"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.

日志系统配置
提供统一的日志格式和输出设置
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

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
    
    # 创建日志文件，使用日期作为文件名
    log_file = log_dir / f"polcam_{datetime.now().strftime('%Y%m%d')}.log"
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(log_level)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # 创建格式器
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 设置格式器
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
