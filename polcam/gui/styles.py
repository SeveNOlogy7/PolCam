from qtpy.QtGui import QFont, QFontDatabase

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
