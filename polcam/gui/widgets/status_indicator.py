"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtCore, QtGui

class StatusIndicator(QtWidgets.QWidget):
    """相机状态指示灯，用形状和颜色双重编码状态。"""

    COLOR_DISABLED = QtGui.QColor(158, 163, 170)
    COLOR_IDLE = QtGui.QColor(120, 130, 145)
    COLOR_PROCESSING = QtGui.QColor(230, 162, 60)
    COLOR_CONNECTED = QtGui.QColor(46, 125, 50)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = False
        self._processing = False
        self.setMinimumSize(16, 16)
        self.setMaximumSize(16, 16)
        self._update_accessibility_text()

    def setStatus(self, status: bool):
        """设置连接状态"""
        if self._status != status:
            self._status = status
            self._update_accessibility_text()
            self.update()

    def setProcessing(self, processing: bool):
        """设置处理状态"""
        if self._processing != processing:
            self._processing = processing
            self._update_accessibility_text()
            self.update()

    def changeEvent(self, event: QtCore.QEvent):
        if event.type() == QtCore.QEvent.EnabledChange:
            self._update_accessibility_text()
        super().changeEvent(event)

    def _state_text(self) -> str:
        if not self.isEnabled():
            return "未连接"
        if self._processing:
            return "正在处理"
        return "已连接" if self._status else "未连接"

    def _update_accessibility_text(self):
        text = f"相机状态：{self._state_text()}"
        self.setAccessibleName(text)
        self.setToolTip(text)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        if not self.isEnabled():
            color = self.COLOR_DISABLED
        elif self._processing:
            color = self.COLOR_PROCESSING
        elif self._status:
            color = self.COLOR_CONNECTED
        else:
            color = self.COLOR_IDLE

        # 空心环表示无连接，实心圆表示已连接或处理中，使状态不只依赖颜色
        if self.isEnabled() and not self._status and not self._processing:
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtGui.QPen(color, 2))
        else:
            painter.setBrush(color)
            painter.setPen(QtGui.QPen(color.darker(120), 1))

        painter.drawEllipse(self.rect().adjusted(2, 2, -2, -2))
