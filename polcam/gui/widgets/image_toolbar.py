"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy import QtWidgets, QtCore, QtGui
import os
from ..styles import Styles

class ImageToolbar(QtWidgets.QWidget):
    """图像工具栏组件，提供图像查看的基本工具"""
    
    # 定义信号
    cursorModeActivated = QtCore.Signal(bool)  # 游标模式
    zoomInActivated = QtCore.Signal(bool)      # 放大
    zoomOutActivated = QtCore.Signal(bool)     # 缩小
    zoomAreaActivated = QtCore.Signal(bool)    # 区域放大
    resetView = QtCore.Signal()   # 复原

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        # 创建布局
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(2)
        
        # 创建工具按钮
        self.cursor_btn = self._create_tool_button("cursor", "选择")
        self.zoom_in_btn = self._create_tool_button("zoom-in", "放大")
        self.zoom_out_btn = self._create_tool_button("zoom-out", "缩小")
        self.zoom_area_btn = self._create_tool_button("zoom-area", "区域放大")
        self.reset_btn = self._create_tool_button("reset", "复原")
        
        # 统一设置按钮属性
        for btn in [self.cursor_btn, self.zoom_in_btn, self.zoom_out_btn, 
                   self.zoom_area_btn, self.reset_btn]:
            btn.setFocusPolicy(QtCore.Qt.NoFocus)  # 禁用焦点
            btn.setCursor(QtCore.Qt.PointingHandCursor)  # 设置鼠标指针
        
        # 设置按钮为可选中状态
        self.cursor_btn.setCheckable(True)
        self.zoom_in_btn.setCheckable(True)
        self.zoom_out_btn.setCheckable(True)
        self.zoom_area_btn.setCheckable(True)
        # reset_btn 不需要设置为可选中
        
        # 创建按钮组，允许取消选择
        self.button_group = QtWidgets.QButtonGroup(self)
        # 设置为非互斥，另外处理互斥逻辑
        self.button_group.setExclusive(False)
        
        # 添加按钮到按钮组
        self.button_group.addButton(self.cursor_btn)
        self.button_group.addButton(self.zoom_in_btn)
        self.button_group.addButton(self.zoom_out_btn)
        self.button_group.addButton(self.zoom_area_btn)
        
        # 连接按钮组信号
        self.button_group.buttonClicked.connect(self._on_button_group_clicked)
        
        # 连接复原按钮信号（不属于按钮组）
        self.reset_btn.clicked.connect(self._on_reset_clicked)
        
        # 添加按钮到布局
        layout.addWidget(self.cursor_btn)
        layout.addWidget(self.zoom_in_btn)
        layout.addWidget(self.zoom_out_btn)
        layout.addWidget(self.zoom_area_btn)
        layout.addWidget(self.reset_btn)
        
        # 固定高度
        self.setFixedHeight(Styles.TOOLBAR_HEIGHT)
        
        # 设置固定宽度为工具栏高度乘以按钮数量
        button_count = layout.count()
        self.setFixedWidth(Styles.TOOLBAR_HEIGHT * button_count)
        
    def _create_tool_button(self, icon_name: str, tooltip: str) -> QtWidgets.QPushButton:
        """创建工具按钮"""
        btn = QtWidgets.QPushButton()
        btn.setToolTip(tooltip)
        
        # 使用Styles中定义的工具栏按钮尺寸
        btn_size = Styles.TOOLBAR_ICON_SIZE
        btn.setFixedSize(btn_size)
        
        # 设置按钮属性
        btn.setFlat(True)  # 设置为平面按钮
        
        # 加载SVG图标
        icon_path = os.path.join(
            os.path.dirname(__file__), 
            "..", "..", "resources", "icon", "imagetoolbar",
            f"{icon_name}.svg"
        )
        
        if os.path.exists(icon_path):
            icon = QtGui.QIcon(icon_path)
            btn.setIcon(icon)
            # 设置图标大小为按钮大小的85%
            icon_size = btn_size * 0.85
            btn.setIconSize(icon_size)
        
        return btn
    
    def _on_button_group_clicked(self, clicked_button: QtWidgets.QPushButton):
        """处理按钮组点击事件"""
        # 获取所有按钮组中的按钮
        all_buttons = self.button_group.buttons()
        
        if clicked_button.isChecked():
            # 如果点击的按钮被选中，取消其他按钮的选中状态
            for button in all_buttons:
                if button != clicked_button:
                    button.setChecked(False)
                    # 处理非当前按钮的模式取消
                    self._handle_mode_change(button, False)
            # 处理当前按钮的模式激活
            self._handle_mode_change(clicked_button, True)
        else:
            # 处理非当前按钮的模式取消
            self._handle_mode_change(clicked_button, False)
    
    def _handle_mode_change(self, button: QtWidgets.QPushButton, enabled: bool):
        """处理模式改变
        
        Args:
            button: 工具栏按钮
            enabled: 是否启用该模式
        """
        # 发送对应的信号
        if button == self.cursor_btn:
            self.cursorModeActivated.emit(enabled)
        if button == self.zoom_in_btn:
            self.zoomInActivated.emit(enabled)
        if button == self.zoom_out_btn:
            self.zoomOutActivated.emit(enabled)
        if button == self.zoom_area_btn:
            self.zoomAreaActivated.emit( enabled)
                    
    def _on_reset_clicked(self):
        """处理复原按钮点击"""
        # 取消所有工具按钮的选中状态
        for button in self.button_group.buttons():
            button.setChecked(False)
        # 发送对应的信号
        self.resetView.emit()

