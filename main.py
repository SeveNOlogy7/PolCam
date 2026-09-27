import logging
import sys
from qtpy import QtWidgets
from polcam.gui.main_window import MainWindow
from polcam.utils.logger import setup_logger

def main():
    setup_logger()
    app = QtWidgets.QApplication(sys.argv)
    app.setOrganizationName("SeveNOlogy7")
    app.setApplicationName("PolCam")
    window = MainWindow()
    window.show()
    return app.exec()

def run() -> int:
    """启动应用。失败时把堆栈留在日志里，并以非零码退出。

    打包版是 console=False，sys.stdout 为 None：光 print 一句异常既没有输出也丢了堆栈，
    而退出码 0 会让外面的启动器以为一切正常。
    """
    try:
        return main()
    except Exception:
        logging.getLogger("polcam.startup").exception("程序启动失败")
        return 1

if __name__ == "__main__":
    sys.exit(run())
