"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

from pathlib import Path

import tools.run_tests as run_tests


def test_runner_exchanges_utf8_with_the_child_not_the_local_codec(monkeypatch):
    """子进程输出一律按 UTF-8 解码，并让子进程也按 UTF-8 输出。

    实测撞到过：text=True 不指定 encoding 时用 locale codec（中文 Windows 是 cp936），
    pytest 打出 UTF-8 中文时解码线程抛 UnicodeDecodeError，result.stdout 成了 None，
    runner 自己崩在 sys.stdout.write(None) 上——第一个非 ASCII 输出把后面所有测试文件
    的结果都掩盖掉了，正是这个 runner 存在的理由。
    """
    calls = []

    class FakeResult:
        returncode = 0
        stdout = "5 passed in 0.2s\n"
        stderr = ""

    def fake_run(command, **kwargs):
        calls.append(kwargs)
        return FakeResult()

    monkeypatch.setattr(run_tests.subprocess, "run", fake_run)
    run_tests.run_one(Path(run_tests.ROOT) / "tests" / "test_not_collected_probe.py", ["-q"])

    assert len(calls) == 1, "run_one 没有启动子进程"
    kwargs = calls[0]
    assert kwargs.get("encoding") == "utf-8", f"没显式指定解码编码：{kwargs}"
    assert kwargs.get("errors") == "replace", "解码失败不该让整条腿崩掉"
    assert kwargs["env"]["PYTHONIOENCODING"] == "utf-8", "子进程也要按 UTF-8 写 stdout"
