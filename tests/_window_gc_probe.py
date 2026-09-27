"""子进程探针：关掉并丢掉引用的 MainWindow 能不能被回收。

必须在别的进程里跑：在 pytest 进程里强行 gc.collect() 会顺带收尾别人留下的 Qt
原生对象，撞上的就是这个仓库历史上那个 0xc0000374 堆损坏。这里只有一个窗口，
收尾的只有它自己。

打印 collected / leaked，退出码 0 表示回收成功。
"""

import gc
import os
import sys
import tempfile
import weakref
from unittest.mock import patch

from qtpy import QtCore, QtWidgets

# 没有大恒驱动时 gxipy 在 import 期就会抛错，借用 conftest 的桩
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import conftest  # noqa: E402,F401

# closeEvent 会 save_settings()，把 QSettings 指到临时文件，别碰真实配置
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
del window
gc.collect()

print("collected" if ref() is None else "leaked")
sys.exit(0 if ref() is None else 1)
