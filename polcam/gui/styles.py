"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

from qtpy.QtGui import QFont, QFontDatabase
from qtpy.QtCore import QSize
from qtpy import QtWidgets

class Styles:
    """统一管理GUI样式的类"""
    
    # 字体大小定义
    FONT_XL = 14     # 特大号字体（引导页标题）
    FONT_LARGE = 12  # 大号字体
    FONT_MEDIUM = 11 # 中号字体
    FONT_SMALL = 10  # 小号字体
    
    # 字体族定义
    FONT_FAMILIES = ["Microsoft YaHei", "SimHei", "sans-serif"]
    
    # 间距定义
    SPACING_SMALL = 4
    SPACING_MEDIUM = 8
    SPACING_LARGE = 16

    # 控件高度定义
    HEIGHT_LARGE = 32  # 大号高度
    HEIGHT_MEDIUM = 30 # 中号高度
    HEIGHT_SMALL = 26  # 小号高度

    # 布局下限。图像区是等比适配的预览，最小值只需保证还能看清构图，
    # 不需要按传感器尺寸来；这两个值直接决定窗口能缩到多小。
    # 控制面板取 281（8 个显示模式下实测的 minimumSizeHint 宽度）之上，
    # 低于它会让分割条给出比内容所需更窄的空间。
    IMAGE_VIEW_MIN_SIZE = QSize(520, 360)
    IMAGE_PANEL_MIN_WIDTH = 560
    CONTROL_PANEL_MIN_WIDTH = 290
    CONTROL_PANEL_MAX_WIDTH = 400

    # 工具栏样式定义
    TOOLBAR_ICON_SIZE = QSize(32, 32)  # 工具栏图标尺寸
    TOOLBAR_HEIGHT = 48                 # 工具栏高度

    # 图像标题样式定义（参考高度 2048 下的基准值）
    IMAGE_TITLE_FONT_SCALE = 3.0    # 标题字体大小
    IMAGE_TITLE_THICKNESS = 4        # 标题线条粗细
    IMAGE_TITLE_COLOR = (255, 255, 255)  # 标题颜色 (BGR)
    IMAGE_TITLE_Y_OFFSET = 70       # 标题Y轴偏移
    IMAGE_TITLE_X_OFFSET = 20       # 标题X轴偏移
    IMAGE_TITLE_REFERENCE_HEIGHT = 2048  # 上述基准值对应的子图高度
    QUAD_TITLE_OVERLAY_FONT_SIZE = 11
    QUAD_TITLE_OVERLAY_X_OFFSET = 8
    QUAD_TITLE_OVERLAY_Y_OFFSET = 6
    QUAD_TITLE_OVERLAY_STYLE = (
        "QLabel {"
        "color: white;"
        "background-color: rgba(0, 0, 0, 128);"
        "padding: 2px 6px;"
        "border-radius: 3px;"
        "}"
    )
    
    @classmethod
    def get_font(cls, size: int) -> QFont:
        """获取指定大小的字体"""
        font = QFont()
        # 设置字体族
        font.setFamilies(cls.FONT_FAMILIES)
        font.setPointSize(size)
        return font
    
    @classmethod
    def get_bold_font(cls, size: int) -> QFont:
        """获取指定大小的粗体字体"""
        font = cls.get_font(size)
        font.setBold(True)
        return font

    @classmethod
    def setup_application_font(cls, app):
        """设置应用程序全局字体"""
        font = cls.get_font(cls.FONT_MEDIUM)
        app.setFont(font)
    
    @classmethod
    def apply_button_style(cls, button):
        """应用按钮样式"""
        button.setFont(cls.get_font(cls.FONT_MEDIUM))
        button.setMinimumHeight(cls.HEIGHT_MEDIUM)
    
    @classmethod
    def apply_spinbox_style(cls, spinbox):
        """应用数值框样式"""
        spinbox.setFont(cls.get_font(cls.FONT_MEDIUM))
        spinbox.setMinimumHeight(cls.HEIGHT_MEDIUM)
    
    @classmethod
    def apply_checkbox_style(cls, checkbox):
        """应用复选框样式"""
        checkbox.setFont(cls.get_font(cls.FONT_MEDIUM))
    
    @classmethod
    def apply_group_title_style(cls, group):
        """应用分组标题样式"""
        group.setFont(cls.get_font(cls.FONT_LARGE))
    
    @classmethod
    def apply_combobox_style(cls, combobox):
        """应用下拉框样式"""
        combobox.setFont(cls.get_font(cls.FONT_MEDIUM))
        combobox.setMinimumHeight(cls.HEIGHT_MEDIUM)

    @classmethod
    def apply_toolbar_style(cls, toolbar):
        """应用工具栏样式"""
        toolbar.setIconSize(cls.TOOLBAR_ICON_SIZE)
        toolbar.setMinimumHeight(cls.TOOLBAR_HEIGHT)
        toolbar.setStyleSheet("""
            QToolBar {
                spacing: 8px;
                padding: 4px;
            }
            QToolButton {
                padding: 6px;
            }
        """)

    @classmethod
    def apply_splitter_style(cls, splitter: QtWidgets.QSplitter):
        """统一分割器样式，使面板边界更清晰且便于拖动。"""
        splitter.setHandleWidth(3)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: transparent;
            }
            QSplitter::handle:hover {
                background-color: transparent;
            }
            QSplitter::handle:pressed {
                background-color: transparent;
            }
            QSplitter::handle:horizontal {
                margin: 0;
                border-left: 1px solid #aeb6c1;
            }
            QSplitter::handle:vertical {
                margin: 0;
                border-top: 1px solid #aeb6c1;
            }
            QSplitter::handle:horizontal:hover {
                border-left-color: #7f95ac;
            }
            QSplitter::handle:vertical:hover {
                border-top-color: #7f95ac;
            }
            QSplitter::handle:horizontal:pressed {
                border-left-color: #667c94;
            }
            QSplitter::handle:vertical:pressed {
                border-top-color: #667c94;
            }
        """)
