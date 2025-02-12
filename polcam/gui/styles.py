from qtpy.QtGui import QFont, QFontDatabase
from qtpy.QtCore import QSize

class Styles:
    """统一管理GUI样式的类"""
    
    # 字体大小定义
    FONT_LARGE = 12    # 大号字体
    FONT_MEDIUM = 11   # 中号字体
    FONT_SMALL = 10    # 小号字体
    
    # 字体族定义
    FONT_FAMILIES = ["Microsoft YaHei", "SimHei", "sans-serif"]
    
    # 控件高度定义
    HEIGHT_LARGE = 32  # 大号高度
    HEIGHT_MEDIUM = 30 # 中号高度
    HEIGHT_SMALL = 26  # 小号高度

    # 工具栏样式定义
    TOOLBAR_ICON_SIZE = QSize(32, 32)  # 工具栏图标尺寸
    TOOLBAR_HEIGHT = 48                 # 工具栏高度

    # 图像标题样式定义
    IMAGE_TITLE_FONT_SCALE = 3.0    # 标题字体大小
    IMAGE_TITLE_THICKNESS = 4        # 标题线条粗细
    IMAGE_TITLE_COLOR = (255, 255, 255)  # 标题颜色 (BGR)
    IMAGE_TITLE_Y_OFFSET = 70       # 标题Y轴偏移
    IMAGE_TITLE_X_OFFSET = 20       # 标题X轴偏移
    
    @classmethod
    def get_font(cls, size: int) -> QFont:
        """获取指定大小的字体"""
        font = QFont()
        # 设置字体族
        font.setFamilies(cls.FONT_FAMILIES)
        font.setPointSize(size)
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
