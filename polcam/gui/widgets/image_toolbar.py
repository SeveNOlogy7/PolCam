from qtpy import QtWidgets, QtCore, QtGui
import os
from ..styles import Styles

class ImageToolbar(QtWidgets.QWidget):
    """图像工具栏组件，提供图像查看的基本工具"""
    
    # 定义信号
    cursorModeActivated = QtCore.Signal()  # 游标模式
    zoomInActivated = QtCore.Signal()      # 放大
    zoomOutActivated = QtCore.Signal()     # 缩小
    zoomAreaActivated = QtCore.Signal()    # 区域放大
    resetViewActivated = QtCore.Signal()   # 复原视图

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        # 创建布局
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(2)  # 减小按钮间距
        
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
        
        # 创建按钮组，实现互斥选择
        self.button_group = QtWidgets.QButtonGroup(self)
        self.button_group.addButton(self.cursor_btn)
        self.button_group.addButton(self.zoom_in_btn)
        self.button_group.addButton(self.zoom_out_btn)
        self.button_group.addButton(self.zoom_area_btn)
        
        # 默认选中cursor_btn
        self.cursor_btn.setChecked(True)
        
        # 添加按钮到布局
        layout.addWidget(self.cursor_btn)
        layout.addWidget(self.zoom_in_btn)
        layout.addWidget(self.zoom_out_btn)
        layout.addWidget(self.zoom_area_btn)
        layout.addWidget(self.reset_btn)
        
        # 连接信号
        self.cursor_btn.clicked.connect(self._on_cursor_clicked)
        self.zoom_in_btn.clicked.connect(self.zoomInActivated)
        self.zoom_out_btn.clicked.connect(self.zoomOutActivated)
        self.zoom_area_btn.clicked.connect(self._on_zoom_area_clicked)
        self.reset_btn.clicked.connect(self.resetViewActivated)
        
        # 固定高度
        self.setFixedHeight(Styles.HEIGHT_MEDIUM)
        
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
            # 设置图标大小为按钮大小的75%
            icon_size = btn_size * 0.75
            btn.setIconSize(icon_size)
        
        return btn
        
    def _on_cursor_clicked(self):
        """处理游标按钮点击"""
        self.zoom_area_btn.setChecked(False)
        self.cursorModeActivated.emit()
        
    def _on_zoom_area_clicked(self):
        """处理区域放大按钮点击"""
        self.cursor_btn.setChecked(False)
        self.zoomAreaActivated.emit()
        
   