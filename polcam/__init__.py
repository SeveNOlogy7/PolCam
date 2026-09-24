"""
PolCam - A Polarization Camera Control System
"""

import sys
import tomllib
from pathlib import Path


def _read_version() -> str:
    """版本号只在 pyproject.toml 声明一次。

    打包后 pyproject.toml 随 --add-data 落在 sys._MEIPASS，源码运行时在仓库根目录，
    两种情况共用同一份解析逻辑。
    """
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    try:
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        return data["project"]["version"]
    except (OSError, KeyError):
        return "0.0.0+unknown"


__version__ = _read_version()
