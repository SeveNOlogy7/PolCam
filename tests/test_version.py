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


def test_about_dialog_shows_the_live_version(main_window, monkeypatch):
    """关于框里的版本号必须是 polcam.__version__ —— 它以前硬编码 1.0.0，长期不一致。

    看的是弹出来的那段文字，不是源码里的写法：措辞进了翻译目录之后句式会变（`v%1` + replace），
    按源码 grep 的测试会为了一个无关的重构而变红。
    """
    from qtpy import QtWidgets

    captured = {}
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "about",
        staticmethod(lambda parent, title, text: captured.__setitem__("text", text)))

    main_window.toolbar_controller._handle_about()

    assert f"v{polcam.__version__}" in captured["text"], captured["text"]
    assert "v1.0.0" not in captured["text"], captured["text"]


def test_release_version_is_shown_with_v_prefix():
    """对人展示的版本一律带 v 前缀；pyproject 里的数字版本受 PEP 440 约束不能带。"""
    assert polcam.__version__ == _pyproject_version()
    assert not polcam.__version__.startswith("v")
