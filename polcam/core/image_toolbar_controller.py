from .base_module import BaseModule
from typing import Optional

class ImageToolbarController(BaseModule):
    """图像工具栏控制器"""
    
    def __init__(self, toolbar, image_display=None):
        super().__init__("ImageToolbarController")
        self.toolbar = toolbar
        self.image_display = image_display
        self._cursor_mode = False
        
    def _do_initialize(self) -> bool:
        """初始化工具栏控制器"""
        try:
            # 连接工具栏信号
            self.toolbar.cursorModeActivated.connect(self._handle_cursor_mode)
            self.toolbar.zoomInActivated.connect(self._handle_zoom_in)
            self.toolbar.zoomOutActivated.connect(self._handle_zoom_out)
            self.toolbar.zoomAreaActivated.connect(self._handle_zoom_area)
            self.toolbar.resetViewActivated.connect(self._handle_reset_view)
            if self.image_display:
                self.image_display.cursorPositionChanged.connect(self._handle_cursor_position)
            return True
        except Exception as e:
            self._logger.error(f"初始化失败: {str(e)}")
            return False
            
    def _do_start(self) -> bool:
        return True
        
    def _do_stop(self) -> bool:
        return True
        
    def _do_destroy(self) -> bool:
        # 断开所有信号连接
        try:
            self.toolbar.cursorModeActivated.disconnect()
            self.toolbar.zoomInActivated.disconnect()
            self.toolbar.zoomOutActivated.disconnect()
            self.toolbar.zoomAreaActivated.disconnect()
            self.toolbar.resetViewActivated.disconnect()
            return True
        except:
            return False
            
    def _handle_cursor_mode(self):
        """处理游标模式激活/关闭"""
        self._cursor_mode = self.toolbar.cursor_btn.isChecked()
        if self.image_display:
            self.image_display.set_cursor_mode(self._cursor_mode)
            
    def _handle_cursor_position(self, info: dict):
        """处理游标位置变化"""
        if not self._cursor_mode or not self.status_bar:
            return
            
        x, y = info['position']
        mode = info['mode']
        quad_index = info.get('quad_index')
        
        # 构建状态栏信息
        if quad_index is not None:
            position_text = f"区域 {quad_index + 1}: ({x}, {y})"
        else:
            position_text = f"位置: ({x}, {y})"
            
        # 添加RGB值信息
        if 'rgb' in info:
            r, g, b = info['rgb']
            rgb_text = f"RGB: ({r}, {g}, {b})"
        else:
            rgb_text = ""
            
        # 显示在状态栏
        self.status_bar.showMessage(f"{position_text} {rgb_text}")
        
    def _handle_zoom_in(self):
        """处理放大"""
        pass
        
    def _handle_zoom_out(self):
        """处理缩小"""
        pass
        
    def _handle_zoom_area(self):
        """处理区域放大"""
        pass
        
    def _handle_reset_view(self):
        """处理视图复原"""
        pass
