from .base_module import BaseModule
from typing import Optional
from qtpy import QtWidgets

class ImageToolbarController(BaseModule):
    """图像工具栏控制器"""
    
    def __init__(self, toolbar, image_display=None):
        super().__init__("ImageToolbarController")
        self.toolbar = toolbar
        self.image_display = image_display
        self._cursor_mode = False
        self._status_bar = None  # 使用私有属性
        self._init_status_bar()  # 初始化时就获取状态栏
        self._init_handlers()

    def _init_status_bar(self):
        """初始化状态栏引用"""
        try:
            if self.image_display:
                main_window = self.image_display.window()
                if isinstance(main_window, QtWidgets.QMainWindow):
                    self._status_bar = main_window.statusBar()
                    self._logger.debug("状态栏初始化成功")
                else:
                    self._logger.warning("未找到主窗口")
        except Exception as e:
            self._logger.error(f"状态栏初始化失败: {str(e)}")
            
    @property
    def status_bar(self):
        """状态栏访问器"""
        if self._status_bar is None:
            self._init_status_bar()  # 尝试重新初始化
        return self._status_bar
        
    def _init_handlers(self):
        """初始化按钮组处理器"""
        if self.toolbar:
            # 连接按钮组的信号
            self.toolbar.button_group.buttonClicked.connect(self._on_button_group_clicked)
            
    def _on_button_group_clicked(self, button):
        """处理按钮组点击事件"""
        # 如果点击已选中的按钮，则取消选中并关闭对应模式
        if button.isChecked():
            # 其他按钮被点击时，确保未选中的按钮对应的模式被关闭
            for btn in self.toolbar.button_group.buttons():
                if btn != button and btn.isChecked():
                    btn.setChecked(False)
                    self._handle_mode_change(btn, False)
            # 处理当前按钮的模式激活
            self._handle_mode_change(button, True)
        else:
            # 按钮取消选中时关闭对应模式
            self._handle_mode_change(button, False)
    
    def _handle_mode_change(self, button, enabled: bool):
        """处理模式改变
        
        Args:
            button: 被点击的按钮
            enabled: 是否启用该模式
        """
        if button == self.toolbar.cursor_btn:
            self._cursor_mode = enabled
            if self.image_display:
                self.image_display.set_cursor_mode(enabled)
            # 更新状态栏显示
            if self.status_bar:
                if enabled:
                    self.status_bar.showMessage("游标模式已开启")
                else:
                    self.status_bar.clearMessage()
        elif button == self.toolbar.zoom_area_btn:
            # 处理区域放大模式
            pass  # 这里添加区域放大模式的处理
        elif button == self.toolbar.zoom_in_btn:
            # 处理放大模式
            pass  # 这里添加放大模式的处理
        elif button == self.toolbar.zoom_out_btn:
            # 处理缩小模式
            pass  # 这里添加缩小模式的处理
                
    def _do_initialize(self) -> bool:
        """初始化工具栏控制器"""
        try:
            # 连接工具栏信号
            self.toolbar.cursorModeActivated.connect(self._handle_cursor_mode)
            self.toolbar.zoomInActivated.connect(self._handle_zoom_in)
            self.toolbar.zoomOutActivated.connect(self._handle_zoom_out)
            self.toolbar.zoomAreaActivated.connect(self._handle_zoom_area)
            self.toolbar.resetViewActivated.connect(self._handle_reset_view)
            
            # 获取主窗口的状态栏引用
            if self.image_display:
                self.image_display.cursorPositionChanged.connect(self._handle_cursor_position)
                
            # 初始化游标模式状态
            self._cursor_mode = self.toolbar.cursor_btn.isChecked()
            if self.image_display and self._cursor_mode:
                self.image_display.set_cursor_mode(True)
                
            # 初始化按钮组处理器
            self._init_handlers()
                
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
        # 移除这个方法的内容，因为已经在_handle_mode_change中处理了
        pass
            
    def _handle_cursor_position(self, info: dict):
        """处理游标位置变化"""
        if not self._cursor_mode:
            return
            
        if self.status_bar is None:
            self._logger.warning("状态栏未初始化")
            return
            
        try:
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
            elif 'gray' in info:
                gray = info['gray']
                rgb_text = f"灰度: {gray}"
            else:
                rgb_text = ""
                
            # 显示在状态栏
            self.status_bar.showMessage(f"{position_text} {rgb_text}")
            
        except Exception as e:
            self._logger.error(f"处理游标位置失败: {str(e)}")
        
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
