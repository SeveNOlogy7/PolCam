"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtCore, QtGui

class StatusIndicator(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = False
        self._processing = False
        self.setMinimumSize(16, 16)
        self.setMaximumSize(16, 16)
        
    def setStatus(self, status: bool):
        """设置连接状态"""
        if self._status != status:
            self._status = status
            self.update()
            
    def setProcessing(self, processing: bool):
        """设置处理状态"""
        if self._processing != processing:
            self._processing = processing
            self.update()
            
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # 简单的颜色选择
        if not self.isEnabled():
            color = QtGui.QColor(128, 128, 128)  # 灰色表示禁用
        elif self._processing:
            color = QtGui.QColor(255, 165, 0)    # 橙色表示处理中
        elif self._status:
            color = QtGui.QColor(0, 255, 0)      # 绿色表示已连接
        else:
            color = QtGui.QColor(255, 0, 0)      # 红色表示未连接
            
        # 简单绘制一个填充圆
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.setBrush(color)
        painter.setPen(QtGui.QPen(color.darker(), 1))
        painter.drawEllipse(rect)
