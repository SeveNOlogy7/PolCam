"""一个测试文件一个进程地跑完整个套件。

测试里造出来的 MainWindow 不会被关闭，同一个 pytest 进程里攒到十几个之后，一次偶发的
循环垃圾回收会在 pytest-qt 泵事件时回收已经被删掉的 C++ 对象，Windows 上表现为
STATUS_HEAP_CORRUPTION (0xc0000374)，退出时也偶发段错误。分开进程把这种累积限制在
单个文件内，顺带让一个文件的崩溃不再掩盖其他文件的结果。

用法：uv run python tools/run_tests.py [传给每个 pytest 进程的额外参数]
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_one(test_file: Path, extra_args: list[str]) -> int:
    env = {**os.environ, "COVERAGE_FILE": f".coverage.{test_file.stem}"}
    # --cov-report= 压掉 pytest.ini 里的 html，报告最后由 combine 统一出一份
    command = [
        sys.executable,
        "-m",
        "pytest",
        str(test_file),
        "--cov=polcam",
        "--cov-report=",
        *extra_args,
    ]
    return subprocess.run(command, cwd=ROOT, env=env).returncode


def combine_coverage() -> None:
    if not list(ROOT.glob(".coverage.test_*")):
        return
    subprocess.run([sys.executable, "-m", "coverage", "combine"], cwd=ROOT)
    subprocess.run([sys.executable, "-m", "coverage", "html"], cwd=ROOT)


def main() -> int:
    test_files = sorted(ROOT.glob("tests/test_*.py"))
    if not test_files:
        print("no test_*.py found under tests/", file=sys.stderr)
        return 1

    failed = []
    for test_file in test_files:
        print(f"\n=== {test_file.name} ===", flush=True)
        if run_one(test_file, sys.argv[1:]) != 0:
            failed.append(test_file.name)

    combine_coverage()

    if failed:
        print(f"\nfailed test files: {', '.join(failed)}", file=sys.stderr)
        return 1
    print(f"\nall {len(test_files)} test files passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
