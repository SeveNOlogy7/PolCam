import pytest
from qtpy import QtWidgets
import sys

@pytest.fixture(scope="session")
def qapp():
    """创建QApplication实例"""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    yield app
