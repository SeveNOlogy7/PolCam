"""子进程探针：关掉并丢掉引用的 MainWindow 有没有被谁钉住。

必须在别的进程里跑：在本进程里强行 gc.collect() 会顺带收尾别人留下的 Qt 原生对象。
真机接上时还实测到更直接的问题：close 之后 del window 再 gc.collect()，6 次里 4 次
直接 0xC0000374 堆损坏 —— 让收集器按任意顺序销毁这棵控件树本身就是未定义行为。所以
先用 shiboken6.delete() 按 Qt 要求的顺序把 C++ 树拆掉（conftest 的 fixture 一直是这
么做的），再把"还剩谁引用这个 Python 对象"交给 gc。

打印 collected / leaked，退出码 0 表示窗口能被回收。

它证明的是"没有 Python 侧的引用把窗口钉在总线上"（当年就是这么漏的：总线留着回调，
回调留着 module 和线程）。它不再证明"Qt 连接表里没有 lambda 攥着窗口"——因为
shiboken6.delete 先把发送者销毁了，连接表跟着没了，那种引用也就测不出来。Qt 连接表
那条路由 tests/test_gui.py 里针对 once_clicked 两个信号的用例盯着。
"""

import gc
import os
import sys
import tempfile
import weakref
from pathlib import Path
from unittest.mock import patch

from qtpy import QtCore, QtWidgets

# 没有大恒驱动时 gxipy 在 import 期就会抛错，借用 conftest 的桩
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import conftest  # noqa: E402,F401

try:
    import shiboken6
except ImportError:
    print("no-shiboken")
    sys.exit(3)

# closeEvent 会 save_settings()。SettingsService 用的是 ~/PolCam/settings.ini 的绝对
# 路径，下面 setDefaultFormat/setPath 那两句管不到显式 filePath，所以在本进程里
# patch Path.home()。不要去改子进程的 HOME/USERPROFILE：大恒 SDK 也读它们，实测改了
# 探针子进程直接 0xc0000409 崩掉。
Path.home = classmethod(lambda cls: Path(tempfile.mkdtemp(prefix="polcam_gc_probe_home_")))

tmp = tempfile.mkdtemp(prefix="polcam_gc_probe_")
QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat,
                         QtCore.QSettings.Scope.UserScope, os.path.join(tmp, "s.ini"))

from polcam.gui.main_window import MainWindow  # noqa: E402

app = QtWidgets.QApplication(sys.argv)

window = MainWindow()
with patch('polcam.gui.main_window.QtWidgets.QMessageBox.warning') as warning:
    window.close()
if warning.called:
    print("close-failed", warning.call_args)
    sys.exit(2)

ref = weakref.ref(window)
shiboken6.delete(window)
del window
gc.collect()

print("collected" if ref() is None else "leaked", flush=True)
sys.exit(0 if ref() is None else 1)

