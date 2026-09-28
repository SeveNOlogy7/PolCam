"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

原始图像文件读写服务
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np


class RawImageService:
    """提供原始图像的统一保存、读取和命名能力。"""

    DEFAULT_EXTENSION = ".tiff"

    def __init__(self):
        self._logger = logging.getLogger(f"{__name__}.{type(self).__name__}")
    # RAW 帧必须是偏振栅格周期的整数倍。取 2 是因为实测的真机（MER2-502-79U3M-HS POL）
    # Height 步进就是 2：按 8 校验会拒掉相机自己产出的合法帧，而按角度解码真正要求的是
    # 奇偶对齐。更严的周期（彩色偏振的 4x4）由 demosaic_polarization 按相机类型再查一遍。
    RAW_ALIGNMENT = 2

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
        return height % self.RAW_ALIGNMENT == 0 and width % self.RAW_ALIGNMENT == 0

    def save_image(self, frame: np.ndarray, file_path: Union[str, Path]) -> Path:
        if frame is None:
            raise ValueError("没有可保存的图像数据")

        path = Path(file_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)

        # cv2.imwrite/imread 按进程 ANSI 代码页解析路径，中文目录或文件名会直接失败
        # （imwrite 只是返回 False，文件根本不落盘），所以自己编码再按字节写。
        extension = path.suffix or self.DEFAULT_EXTENSION
        encoded, buffer = cv2.imencode(extension, frame)
        if not encoded:
            raise IOError(f"无法编码图像文件: {path}")
        path.write_bytes(buffer.tobytes())
        return path

    def load_image(self, file_path: Union[str, Path]) -> np.ndarray:
        path = Path(file_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"图像文件不存在: {path}")

        # IMREAD_GRAYSCALE 会把读到的东西强行折成单通道 uint8：文件里明明是 16bit
        # 也只剩 8bit，三通道结果也被悄悄压成灰度再报"已加载图像"。原始帧的定义是
        # 单通道，所以按原样读，对不上就明确拒绝。
        raw_data = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if raw_data is None:
            raise ValueError("无法读取图像文件")
        if raw_data.ndim != 2:
            raise ValueError(f"原始图像必须是单通道帧，读到了 {raw_data.shape[-1]} 通道图像")
        if not self.verify_image_size(raw_data):
            raise ValueError(f"图像尺寸必须是{self.RAW_ALIGNMENT}x{self.RAW_ALIGNMENT}偏振栅格的整数倍")
        return self._downshift_to_uint8(raw_data)

    def _downshift_to_uint8(self, data: np.ndarray) -> np.ndarray:
        """把超出 8bit 的文件按有效位降位读入，并留一条 warning。

        整条处理链的前提是 8bit（`calculate_polarization_parameters` 直接拒收别的
        dtype），所以读入边界必须自己收到 uint8；真机在 Mono10 下存出来的文件就是
        uint16。右移取高位，直接 astype 会按 256 回绕。

        位移量按数据本身推出来：文件里只有容器位宽（uint16），有效位可能是 10/12，
        照容器移会把 10bit 的 0..1022 压成 0..3。
        """
        if data.dtype == np.uint8:
            return data
        if not np.issubdtype(data.dtype, np.integer):
            raise ValueError(f"原始图像必须是整数像素，读到了 {data.dtype}")
        depth = int(data.max()).bit_length() if data.size else 0
        if depth <= 8:
            return data.astype(np.uint8)
        self._logger.warning(
            f"读到的原始帧是 {np.iinfo(data.dtype).bits}bit 容器、有效位 {depth}，"
            f"已右移 {depth - 8} 位降为 8bit；偏振参数会损失精度，需要全量程请直采")
        return np.right_shift(data, depth - 8).astype(np.uint8)
