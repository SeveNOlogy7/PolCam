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


def test_runner_survives_output_the_console_cannot_encode(monkeypatch):
    """把子进程输出转写给控制台时，控制台编码不该有权杀掉后面所有文件。

    实测撞到过：test_gui.py 的输出里有一个 '²'，中文 Windows 的控制台是 GBK，
    sys.stdout.write 直接抛 UnicodeEncodeError —— runner 崩在转写这一步，剩下几个
    文件一个都没跑。这和它要避免的"一个非 ASCII 输出掩盖全部结果"是同一件事，只不
    过这次发生在写的一侧。编不出的字符换成 '?'，宁可少一个字形也不能少一整个文件。
    """

    class StrictStream:
        """和 GBK 控制台一样：编码不了的字符就抛，不做替换。"""
        encoding = "ascii"

        def __init__(self):
            self.written = []

        def write(self, text):
            text.encode(self.encoding)
            self.written.append(text)
            return len(text)

        def flush(self):
            pass

    stream = StrictStream()

    class FakeResult:
        returncode = 0
        stdout = "面积上限 1000² 检查\n1 passed in 0.2s\n"
        stderr = ""

    monkeypatch.setattr(run_tests.sys, "stdout", stream)
    monkeypatch.setattr(run_tests.subprocess, "run", lambda command, **kwargs: FakeResult())

    reason = run_tests.run_one(Path(run_tests.ROOT) / "tests" / "test_not_collected_probe.py", ["-q"])

    written = "".join(stream.written)
    assert "1 passed in 0.2s" in written, f"子进程的输出没有转写出去：{written!r}"
    assert "²" not in written and "?" in written, f"非 ASCII 字符没有被替换掉：{written!r}"
    # 桩里没有覆盖率数据文件，verdict 因此报"未正常结束"；本用例要证明的是 run_one
    # 活着走到了 verdict，而不是死在转写输出那一步。
    assert reason is not None and "覆盖率" in reason, f"没有跑到 verdict：{reason!r}"

