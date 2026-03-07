"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.

原始图像文件读写服务
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np


class RawImageService:
    """提供原始图像的统一保存、读取和命名能力。"""

    DEFAULT_EXTENSION = ".tiff"

    def format_timestamp(self, timestamp: Optional[Union[datetime, float]]) -> str:
        if timestamp is None:
            timestamp = datetime.now()
        elif isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp)
        return timestamp.strftime("%Y%m%d_%H%M%S")

    def build_auto_save_path(
        self,
        directory: Union[str, Path],
        timestamp: Optional[Union[datetime, float]] = None,
        suffix: str = "_RAW",
        extension: str = DEFAULT_EXTENSION,
    ) -> Path:
        save_dir = Path(directory).expanduser()
        save_dir.mkdir(parents=True, exist_ok=True)

        ext = extension if extension.startswith(".") else f".{extension}"
        stem = f"{self.format_timestamp(timestamp)}{suffix}"
        candidate = save_dir / f"{stem}{ext}"
        index = 1
        while candidate.exists():
            candidate = save_dir / f"{stem}_{index:03d}{ext}"
            index += 1
        return candidate

    def verify_image_size(self, data: np.ndarray) -> bool:
        if data is None or len(data.shape) != 2:
            return False
        height, width = data.shape
        return height % 8 == 0 and width % 8 == 0

    def save_image(self, frame: np.ndarray, file_path: Union[str, Path]) -> Path:
        if frame is None:
            raise ValueError("没有可保存的图像数据")

        path = Path(file_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)

        success = cv2.imwrite(str(path), frame)
        if not success:
            raise IOError(f"无法保存图像文件: {path}")
        return path

    def load_image(self, file_path: Union[str, Path]) -> np.ndarray:
        path = Path(file_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"图像文件不存在: {path}")

        raw_data = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if raw_data is None:
            raise ValueError("无法读取图像文件")
        if not self.verify_image_size(raw_data):
            raise ValueError("图像尺寸必须是8x8马赛克的整数倍")
        return raw_data
