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
        self.setEnabled(False)  # 初始状态为禁用
        self.setFixedSize(16, 16)  # 设置固定大小
        
    def setStatus(self, status: bool):
        self._status = status
        self.update()
        
    def isStatus(self) -> bool:
        """获取当前状态"""
        return self._status
        
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # 定义颜色
        if self._status:
            color = QtGui.QColor(0, 255, 0)  # 绿色
        else:
            color = QtGui.QColor(128, 128, 128)  # 灰色
            
        # 绘制圆形指示灯
        painter.setBrush(color)
        painter.setPen(QtGui.QPen(color.darker(150), 1))
        painter.drawEllipse(2, 2, 12, 12)
