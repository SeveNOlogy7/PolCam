"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

import logging

import pytest

import main as app_entry


def test_a_fatal_startup_error_is_logged_and_exits_non_zero(monkeypatch, caplog):
    """启动炸了要留下痕迹，也不能对外报告"正常退出"。

    原来 except 分支只 print(f"程序异常退出: {e}")：打包版 console=False 时 sys.stdout
    是 None，那句 print 什么都不输出，堆栈也没有，退出码还是 0 —— 用户双击图标看不到任何
    反应，而外面的启动器以为跑成功了。
    """

    def boom():
        raise RuntimeError("gallery.db 打不开")

    monkeypatch.setattr(app_entry, "main", boom)

    with caplog.at_level(logging.ERROR):
        code = app_entry.run()

    assert code == 1, f"致命错误被报告成成功退出: {code}"
    assert "gallery.db 打不开" in caplog.text
    assert "Traceback" in caplog.text, "只留下一行消息，堆栈没进日志"


def test_a_clean_start_returns_the_exit_code_from_the_event_loop(monkeypatch):
    monkeypatch.setattr(app_entry, "main", lambda: 0)
    assert app_entry.run() == 0
