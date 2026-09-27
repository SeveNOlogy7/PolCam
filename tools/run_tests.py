"""一个测试文件一个进程地跑完整个套件。

测试里造出来的 MainWindow 不会被关闭，同一个 pytest 进程里攒到十几个之后，一次偶发的
循环垃圾回收会在 pytest-qt 泵事件时回收已经被删掉的 C++ 对象，Windows 上表现为
STATUS_HEAP_CORRUPTION (0xc0000374)，退出时也偶发段错误。分开进程把这种累积限制在
单个文件内，顺带让一个文件的崩溃不再掩盖其他文件的结果。

用法：uv run python tools/run_tests.py [传给每个 pytest 进程的额外参数]
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 单个测试文件的墙钟上限。这个 runner 存在的理由就是"某个文件能把进程卡死"：一个残留
# 的模态框、一个不回的线程，都会让 subprocess.run 永远等下去，两条 CI 腿一起烧到 GitHub
# 的 360 分钟超时才报错。宁可超时报错，也不要静默挂住。
PER_FILE_TIMEOUT_S = 300

# pytest 结束时才会打的汇总行；进程中途退出（含 native crash 与 os._exit）就看不到它。
# -q 会把两侧的 "=== " 装饰去掉（`5 passed, 1 warning in 0.15s`），所以只认计数本身。
_SUMMARY = re.compile(r"\b\d+ (?:passed|failed|errors?\b)|\bno tests ran\b")


def coverage_file(test_file: Path) -> Path:
    # 键要含目录：glob 是 tests/**/test_*.py，只取 stem 的话 tests/gui/test_toolbar.py 和
    # tests/core/test_toolbar.py 会写同一个数据文件，后者 unlink 掉前者的，combine 只剩
    # 最后一份，汇总覆盖率静默少一块
    relative = test_file.relative_to(ROOT).with_suffix("")
    return ROOT / (".coverage." + "_".join(relative.parts))


def verdict(test_file: Path, returncode: int, output: str) -> str | None:
    """返回 None 表示这个文件真的跑完了；否则给出失败原因。

    只看退出码不够：test 里一句 os._exit(0) 能让退出码为 0 而后面的测试根本没跑。
    """
    if returncode != 0:
        return f"退出码 {returncode}"

    summary = _SUMMARY.search(output)
    if summary is None:
        return "没跑到 pytest 汇总行（进程中途退出，结果不完整）"
    if "no tests ran" in summary.group(0):
        return "没有收集到任何测试"
    if "failed" in summary.group(0) or "error" in summary.group(0):
        return summary.group(0).strip("= ").strip()

    # 覆盖率数据由解释器正常退出时的 atexit 写出，缺它就说明这个子进程没有善终
    if not coverage_file(test_file).exists():
        return "缺少覆盖率数据文件，子进程未正常结束"
    return None


def run_one(test_file: Path, extra_args: list[str]) -> str | None:
    data_file = coverage_file(test_file)
    if data_file.exists():
        data_file.unlink()

    env = {**os.environ, "COVERAGE_FILE": data_file.name}
    # -o addopts= 清掉 pytest.ini 里的 --cov-report=html：子进程各写一份 htmlcov 既浪费
    # 又会留下半成品，统一报告交给下面的 combine 出一次。注意单个 --cov-report= 是追加
    # 而不是覆盖，压不住 ini 里那份。
    command = [
        sys.executable,
        "-m",
        "pytest",
        str(test_file),
        "-o",
        "addopts=",
        "--cov=polcam",
        "--cov-report=",
        *extra_args,
    ]
    try:
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                                timeout=PER_FILE_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        partial = (exc.output or b"") if isinstance(exc.output, bytes) else (exc.output or "")
        sys.stdout.write(partial)
        sys.stdout.write(f"\n[runner] {test_file.relative_to(ROOT)} 超过 {PER_FILE_TIMEOUT_S}s "
                         f"没结束，已杀掉：挂住的测试会掩盖后面所有文件的结果\n")
        sys.stdout.flush()
        return f"超过 {PER_FILE_TIMEOUT_S}s 未完成（已终止）"
    sys.stdout.write(result.stdout)
    sys.stdout.flush()
    sys.stderr.write(result.stderr)
    return verdict(test_file, result.returncode, result.stdout)


def combine_coverage() -> str | None:
    data_files = sorted(ROOT.glob(".coverage.*"))
    if not data_files:
        return "没有任何覆盖率数据文件，无法出报告"
    for step in (["combine"], ["html"]):
        result = subprocess.run(
            [sys.executable, "-m", "coverage", *step], cwd=ROOT, capture_output=True, text=True
        )
        if result.returncode != 0:
            sys.stderr.write(result.stdout + result.stderr)
            return f"coverage {' '.join(step)} 失败"
    return None


def main() -> int:
    test_files = sorted(ROOT.glob("tests/**/test_*.py"))
    if not test_files:
        print("no test_*.py found under tests/", file=sys.stderr)
        return 1

    failures = []
    for test_file in test_files:
        print(f"\n=== {test_file.relative_to(ROOT)} ===", flush=True)
        reason = run_one(test_file, sys.argv[1:])
        if reason:
            failures.append(f"{test_file.relative_to(ROOT)}: {reason}")

    coverage_problem = combine_coverage()

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    if coverage_problem:
        print(f"FAIL coverage: {coverage_problem}", file=sys.stderr)
    if failures or coverage_problem:
        return 1

    print(f"\nall {len(test_files)} test files passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
