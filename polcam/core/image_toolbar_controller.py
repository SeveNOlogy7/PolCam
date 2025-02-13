from .base_module import BaseModule
from typing import Optional, List
from qtpy import QtWidgets

class ImageToolbarController(BaseModule):
    """图像工具栏控制器"""
    
    def __init__(self, toolbar, image_display=None):
        super().__init__("ImageToolbarController")
        self.toolbar = toolbar
        self.image_display = image_display
        self._cursor_mode = False  # 默认关闭游标模式
        self._status_bar = None  # 使用私有属性
        self._init_status_bar()  # 初始化时就获取状态栏

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
                
    def _do_initialize(self) -> bool:
        """初始化工具栏控制器"""
        try:
            # 连接工具栏信号
            self.toolbar.cursorModeActivated.connect(self._handle_cursor_mode)
            self.toolbar.zoomInActivated.connect(self._handle_zoom_in)
            self.toolbar.zoomOutActivated.connect(self._handle_zoom_out)
            self.toolbar.zoomAreaActivated.connect(self._handle_zoom_area)
            self.toolbar.resetView.connect(self._handle_reset_view)
            
            # 获取主窗口的状态栏引用
            if self.image_display:
                self.image_display.cursorPositionChanged.connect(self._handle_cursor_position)
                
            # 初始化时确保所有模式都是关闭状态
            self._cursor_mode = False
            if self.image_display:
                self.image_display.set_cursor_mode(False)
                
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
            return True
        except:
            return False
            
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
            
            if mode == 'quad':
                # 四分图模式
                cursor_quad_position = info.get('cursor_quad_position')
                if cursor_quad_position and quad_index is not None:
                    rel_x, rel_y = cursor_quad_position
                    # 获取分图标题列表
                    quad_titles = self._get_quad_titles(info)
                    
                    # 确保quad_index在有效范围内
                    if 0 <= quad_index < len(quad_titles):
                        position_text = f"({rel_x}, {rel_y})"
                        
                        # 获取所有区域的像素值/数值
                        if 'quad_rgb_values' in info:
                            values_text = []
                            for i, (r, g, b) in enumerate(info['quad_rgb_values']):
                                if i < len(quad_titles):
                                    values_text.append(f"{quad_titles[i]}:RGB({r},{g},{b})")
                            pixel_text = " | ".join(values_text)
                        elif 'quad_gray_values' in info:
                            values_text = []
                            for i, gray in enumerate(info['quad_gray_values']):
                                if i < len(quad_titles):
                                    # 复用了四分量灰度与偏振度的处理逻辑
                                    values_text.append(f"{quad_titles[i]}:{int(gray) if gray.is_integer() else f'{gray:.3f}'}")
                            pixel_text = " | ".join(values_text)
                        else:
                            pixel_text = ""
                        
                        status_text = f"{position_text} || {pixel_text}"
                        self.status_bar.showMessage(status_text)
            else:
                # 单图模式
                position_text = f"({x}, {y})"
                if 'rgb' in info:
                    r, g, b = info['rgb']
                    pixel_text = f"RGB: ({r}, {g}, {b})"
                elif 'gray' in info:
                    gray = info['gray']
                    pixel_text = f"灰度: {gray}"
                else:
                    pixel_text = ""
                    
                status_text = f"{position_text} || {pixel_text}"
                self.status_bar.showMessage(status_text)
            
        except Exception as e:
            self._logger.error(f"处理游标位置失败: {str(e)}")

    def _get_quad_titles(self, info: dict) -> List[str]:
        """根据不同的四分图模式返回对应的标题列表"""
        mode = info.get('mode')
        if not mode == 'quad':
            return []
        
        # 从ImageDisplay的当前显示模式获取
        if self.image_display:
            current_mode = self.image_display.display_mode.currentText()
            
            # 根据显示模式返回对应的标题
            if current_mode in ["四角度彩色", "四角度灰度"]:
                return ['0°', '45°', '90°', '135°']
            elif current_mode == "偏振度图像":
                return ['合成图', 'DOLP', 'AOLP', 'DOCP']
                
        # 默认返回通用标题
        return ['区域1', '区域2', '区域3', '区域4']
    
    def _handle_cursor_mode(self, enabled: bool):
        """处理游标"""
        if self.status_bar:
            if enabled:
                self.status_bar.showMessage("游标模式已开启")
                self._cursor_mode=True
                self.image_display.set_cursor_mode(True)
            else:
                self.status_bar.clearMessage()
                self.image_display.set_cursor_mode(False)
                self.image_display.refresh_current_image()

    def _handle_zoom_in(self, enabled: bool):
        """处理放大"""
        if self.status_bar:
            if enabled:
                self.status_bar.showMessage("放大模式未实现")
            else:
                self.status_bar.clearMessage()
        
    def _handle_zoom_out(self, enabled: bool):
        """处理缩小"""
        if self.status_bar:
            if enabled:
                self.status_bar.showMessage("缩小模式未实现")
            else:
                self.status_bar.clearMessage()
        
    def _handle_zoom_area(self, enabled: bool):
        """处理区域放大"""
        if self.status_bar:
            if enabled:
                self.status_bar.showMessage("区域放大模式未实现")
            else:
                self.status_bar.clearMessage()
            
    def _handle_reset_view(self):
        """处理复原"""
        self.image_display.refresh_current_image()
