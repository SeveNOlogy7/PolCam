"""生成/校验 Qt Linguist 的翻译目录。

    python tools/build_translations.py            # 抽取 -> 填模板 -> 编译 -> 导出目录
    python tools/build_translations.py --check    # 只校验，CI 用；不一致就非零退出

为什么 .qm 与 sources.json 要提交进仓库：测试和打包版都直接读它们，缺了就是"语言按钮
按了没反应"。--check 会重新生成到临时目录再逐字节比对，所以漏跑这一步合不进去。

抽取的上下文由 Qt 自己定（tr() 用类名，translate() 用第一个实参），所以这里不解析源码。
"""
from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS = ROOT / "polcam" / "translations"
TS_NAME = "polcam_en"
SOURCE_LANGUAGE = "zh_CN"
TARGET_LANGUAGE = "en"
# 只有这些目录里的字面量算界面文案；utils 里的日志格式串、core 的判定逻辑不进目录
SCAN_DIRS = ("polcam/gui", "polcam/core")


def python_files() -> list[str]:
    files = []
    for folder in SCAN_DIRS:
        for path in sorted((ROOT / folder).rglob("*.py")):
            files.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    return files


def qt_tool(name: str) -> str:
    """先找 venv 里的 pyside6-<name>，再退回 PATH。"""
    scripts = Path(sys.executable).parent
    for candidate in (scripts / f"{name}.exe", scripts / name):
        if candidate.exists():
            return str(candidate)
    found = shutil.which(name) or shutil.which(f"pyside6-{name.split('-')[-1]}")
    if not found:
        raise SystemExit(f"找不到 {name}；PySide6 的 tools 没装吗？")
    return found


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT, check=check, text=True, capture_output=True)


def lupdate(ts_path: Path) -> None:
    ts_path.parent.mkdir(parents=True, exist_ok=True)
    command = [qt_tool("pyside6-lupdate"), *python_files(), "-no-obsolete",
               "-target-language", TARGET_LANGUAGE, "-source-language", SOURCE_LANGUAGE,
               "-ts", str(ts_path)]
    result = run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(f"lupdate 失败：\n{result.stdout}\n{result.stderr}")
    print((result.stdout or "").strip().splitlines()[-1] if result.stdout else "")


def unfinished(ts_path: Path) -> list[tuple[str, str]]:
    root = ET.parse(ts_path).getroot()
    gaps = []
    for context in root.findall("context"):
        name = context.findtext("name") or ""
        for message in context.findall("message"):
            translation = message.find("translation")
            text = (translation.text or "").strip() if translation is not None else ""
            if not text or translation.get("type") in ("unfinished", "obsolete"):
                gaps.append((name, " ".join((message.findtext("source") or "").split())))
    return gaps


def lrelease(ts_path: Path, qm_path: Path) -> None:
    result = run([qt_tool("pyside6-lrelease"), str(ts_path), "-qm", str(qm_path)], check=False)
    if result.returncode != 0:
        raise SystemExit(f"lrelease 失败：\n{result.stdout}\n{result.stderr}")


def export_sources(ts_path: Path, json_path: Path) -> int:
    """导出 {context, source, translation} 列表，给 gui/i18n.py 的树遍历还原源文用。"""
    root = ET.parse(ts_path).getroot()
    entries = []
    for context in root.findall("context"):
        name = context.findtext("name") or ""
        for message in context.findall("message"):
            source = message.findtext("source") or ""
            translation = message.find("translation")
            entries.append({
                "context": name,
                "source": source,
                "translation": (translation.text or "").strip() if translation is not None else "",
            })
    json_path.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(entries)


UI_SETTERS = {
    "setText", "setToolTip", "setPlaceholderText", "setWindowTitle", "setAccessibleName",
    "addRow", "addItem", "insertItem", "addTab", "setTabText", "setStatusTip",
    "setHorizontalHeaderLabels", "information", "warning", "critical", "question", "about",
    "_show_status_message", "set_help_subtitle", "set_capability_lines", "make_label",
    "_add_action", "_create_tool_button", "QLabel", "QPushButton", "QCheckBox",
    "QGroupBox", "QRadioButton", "QAction",
}
DIALOG_ONLY = {"information", "warning", "critical", "question", "about"}
# 已经是"取一句"的调用名。translate_source 是本机 i18n 的入口，它内部会查目录，
# 所以包在里面的字面量是源文而不是漏网 —— 不认它就会报假阳性。
TRANSLATOR_NAMES = {"tr", "translate", "translate_source"}


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _cjk_literals(arg: ast.expr) -> list:
    """一个实参里所有带中文的字面量：顶层常量、f-string，以及三元/拼接里的嵌套常量。

    `setText("停止采集" if streaming else "连续采集")` 的字面量藏在 IfExp 里，只看顶层参数
    就会漏 —— 用户截图里的"停止采集"正是这么漏掉的。f-string 内部的常量片段不单独算，
    它们是那条 f-string 的一部分。
    """
    found = []
    inside_joined = set()
    for node in ast.walk(arg):
        if isinstance(node, ast.JoinedStr):
            if has_cjk("".join(v.value if isinstance(v, ast.Constant) else " "
                               for v in node.values)):
                found.append(node)
            inside_joined |= {id(child) for child in ast.walk(node)}
    for node in ast.walk(arg):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and has_cjk(node.value) and id(node) not in inside_joined):
            found.append(node)
    return found


def _inside_translator(node, parents: dict) -> bool:
    """往上走，看它是不是已经躺在某个"取一句"的调用里。"""
    current = parents.get(node)
    while current is not None:
        if isinstance(current, ast.Call):
            name = getattr(current.func, "attr", None) or getattr(current.func, "id", None)
            if name in TRANSLATOR_NAMES:
                return True
        current = parents.get(current)
    return False


def unwrapped_ui_text() -> list[str]:
    """找"设文字的调用里塞了中文，却没包 tr()/translate()"的地方。

    这是 --check 里唯一会漏翻译的口子：漏一处，英文界面就有一块留在中文，而目录看起来是满的。
    两种写法都要抓：常量字面量（含嵌套在子表达式里的），以及 f-string —— f-string 不是字面量，
    lupdate 扫不到，得改成 `translate(ctx, "…%1…").replace("%1", …)`。
    """
    problems = []
    for rel in python_files():
        path = ROOT / rel
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name not in UI_SETTERS:
                continue
            if name in DIALOG_ONLY:
                receiver = getattr(func, "value", None)
                while isinstance(receiver, ast.Attribute):
                    receiver = receiver.value
                if getattr(receiver, "id", None) not in ("QMessageBox", "QtWidgets"):
                    continue        # self._logger.warning(...) 是日志正文，不该译
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                for item in _cjk_literals(arg):
                    if _inside_translator(item, parents):
                        continue
                    if isinstance(item, ast.JoinedStr):
                        problems.append(f"{rel}:{item.lineno} {name}(...) 用 f-string 拼中文，"
                                        f"要改成 translate() + %1")
                    else:
                        problems.append(f"{rel}:{item.lineno} {name}(...) 里的字面量没包 tr()")
    return problems



def _without_locations(path: Path) -> bytes:
    """丢掉 <location> 行再比较。

    那些只是给编辑器跳转用的文件名与行号：挪一行代码就变，不代表目录过期。
    而且 lupdate 写的是**相对 .ts 位置**的路径，所以比对时两边必须在同一个目录里生成。
    """
    lines = [line for line in path.read_bytes().splitlines() if b"<location" not in line]
    return b"\n".join(lines)


def build(check: bool) -> int:
    problems = unwrapped_ui_text()
    if problems:
        for line in problems:
            print(f"漏网: {line}")
        if check:
            return 1

    if check:
        committed_ts = TRANSLATIONS / f"{TS_NAME}.ts"
        # 临时 .ts 必须落在同一个目录：lupdate 的 location 是相对路径，换了目录就全变
        probe = committed_ts.with_name(f".{TS_NAME}.check.ts")
        try:
            shutil.copyfile(committed_ts, probe)
            lupdate(probe)
            gaps = unfinished(probe)
            if gaps:
                for context, source in gaps:
                    print(f"缺译文: [{context}] {source[:70]}")
                return 1
            qm = probe.with_suffix(".qm")
            lrelease(probe, qm)
            sources = probe.with_name(".sources.check.json")
            export_sources(probe, sources)
            stale = []
            if _without_locations(probe) != _without_locations(committed_ts):
                stale.append(f"{committed_ts.name} 与重新抽取的结果不一致（跑一次不带 --check 的本脚本）")
            for generated, committed in ((qm, TRANSLATIONS / f"{TS_NAME}.qm"),
                                         (sources, TRANSLATIONS / "sources.json")):
                if not committed.exists():
                    stale.append(f"{committed.name} 没提交")
                elif generated.read_bytes() != committed.read_bytes():
                    stale.append(f"{committed.name} 与重新生成的结果不一致")
            if stale:
                for line in stale:
                    print(f"过期: {line}")
                return 1
        finally:
            for leftover in (probe, probe.with_suffix(".qm"),
                             probe.with_name(".sources.check.json")):
                leftover.unlink(missing_ok=True)
        print(f"翻译目录完整且是最新的：{len(unfinished(committed_ts))} 条缺译文")
        return 0

    ts = TRANSLATIONS / f"{TS_NAME}.ts"
    lupdate(ts)
    gaps = unfinished(ts)
    qm = TRANSLATIONS / f"{TS_NAME}.qm"
    lrelease(ts, qm)
    count = export_sources(ts, TRANSLATIONS / "sources.json")
    print(f"共 {count} 条，其中 {len(gaps)} 条还没有译文")
    if gaps:
        print("填完 " + str(ts) + " 之后再跑一次本脚本")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="只校验：漏翻译、目录过期、字面量没包 tr() 都算失败")
    sys.exit(build(parser.parse_args().check))
