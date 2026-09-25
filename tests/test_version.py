"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

import pathlib
import tomllib

import polcam


def _pyproject_version() -> str:
    root = pathlib.Path(polcam.__file__).resolve().parent.parent
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def test_version_has_a_single_source():
    """pyproject.toml 是版本唯一真相，运行时读到的必须是同一个值。"""
    assert polcam.__version__ == _pyproject_version()


def test_about_dialog_does_not_hardcode_version():
    """关于对话框以前硬编码 1.0.0，与 polcam.__version__ 的 0.1.0 长期不一致。"""
    source = pathlib.Path(polcam.__file__).resolve().parent / "core" / "toolbar_controller.py"
    text = source.read_text(encoding="utf-8")
    assert "版本: v{POLCAM_VERSION}" in text
    assert "版本: 1.0.0" not in text


def test_release_version_is_shown_with_v_prefix():
    """对人展示的版本一律带 v 前缀；pyproject 里的数字版本受 PEP 440 约束不能带。"""
    assert polcam.__version__ == _pyproject_version()
    assert not polcam.__version__.startswith("v")
