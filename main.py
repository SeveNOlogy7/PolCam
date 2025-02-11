import sys
from qtpy import QtWidgets
from polcam.gui.main_window import MainWindow
from polcam.utils.logger import setup_logger

def main():
    setup_logger()
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"程序异常退出: {e}")
