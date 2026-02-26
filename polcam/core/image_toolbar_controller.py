"""
MIT License
Copyright (c) 2024 Junhao Cai
See LICENSE file for full license details.
"""

from .base_module import BaseModule
from typing import Optional, List
from qtpy import QtWidgets
from .events import Event, EventType

class ImageToolbarController(BaseModule):
    """图像工具栏控制器"""

    ZOOM_FACTOR = 1.5  # 放大/缩小倍率

    def __init__(self, toolbar, image_display=None):
        super().__init__("ImageToolbarController")
        self.toolbar = toolbar
        self.image_display = image_display
        self._cursor_mode = False
        self._zoom_mode = None  # 'zoom_in' | 'zoom_out' | 'zoom_area' | None
        self._camera_module = None

    def set_camera_module(self, camera_module):
        """设置相机模块引用，用于 ROI 控制

        Args:
            camera_module: CameraModule 实例
        """
        self._camera_module = camera_module

    def _do_initialize(self) -> bool:
        """初始化工具栏控制器"""
        try:
            # 连接工具栏信号
            self.toolbar.cursorModeActivated.connect(self._handle_cursor_mode)
            self.toolbar.zoomInActivated.connect(self._handle_zoom_in)
            self.toolbar.zoomOutActivated.connect(self._handle_zoom_out)
            self.toolbar.zoomAreaActivated.connect(self._handle_zoom_area)
            self.toolbar.resetView.connect(self._handle_reset_view)

            if self.image_display:
                self.image_display.cursorPositionChanged.connect(self._handle_cursor_position)
                # 连接缩放交互信号
                self.image_display.zoomClickRequested.connect(self._handle_zoom_click)
                self.image_display.zoomAreaRequested.connect(self._handle_zoom_area_selection)
                self.image_display.zoomAreaPreview.connect(self._handle_zoom_area_preview)

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

    def _show_status_message(self, message: str):
        """发送状态栏消息更新事件"""
        self.publish_event(EventType.STATUS_MESSAGE_UPDATE, {
            'message': message
        })

    def _clear_status_message(self):
        """发送状态栏消息清除事件"""
        self.publish_event(EventType.STATUS_MESSAGE_CLEAR)

    def _handle_cursor_position(self, info: dict):
        """处理游标位置变化"""
        if not self._cursor_mode:
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
                        values_text = []
                        pixel_text = ""
                        if 'quad_rgb_values' in info:
                            for i, (r, g, b) in enumerate(info['quad_rgb_values']):
                                if i < len(quad_titles):
                                    values_text.append(f"{quad_titles[i]}:RGB({r},{g},{b})")
                        elif 'quad_gray_values' in info:
                            for i, gray in enumerate(info['quad_gray_values']):
                                if i < len(quad_titles):
                                    values_text.append(f"{quad_titles[i]}:{gray}")
                        elif 'quad_pol_values' in info:
                            for i, value in enumerate(info['quad_pol_values']):
                                if i < len(quad_titles):
                                    if i == 0:
                                        if isinstance(value, tuple):
                                            r, g, b = value
                                            values_text.append(f"{quad_titles[i]}:RGB({r},{g},{b})")
                                        else:
                                            values_text.append(f"{quad_titles[i]}:{int(value)}")
                                    else:
                                        values_text.append(f"{quad_titles[i]}:{value:.3f}")
                        pixel_text = " | ".join(values_text)

                        status_text = f"{position_text} || {pixel_text}"
                        self._show_status_message(status_text)
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
                self._show_status_message(status_text)

        except Exception as e:
            self._logger.error(f"处理游标位置失败: {str(e)}")

    def _handle_cursor_mode(self, enabled: bool):
        """处理游标模式"""
        if enabled:
            self._cursor_mode = True
            self._zoom_mode = None
            if self.image_display:
                self.image_display.set_interaction_mode('cursor')
            self._show_status_message("游标模式已开启")
        else:
            self._cursor_mode = False
            if self.image_display:
                self.image_display.set_interaction_mode('none')
                self.image_display.refresh_current_image()
            self._clear_status_message()

    # ==================== 缩放控制 ====================

    def _handle_zoom_in(self, enabled: bool):
        """处理放大模式切换"""
        if enabled:
            self._zoom_mode = 'zoom_in'
            self._cursor_mode = False
            if self.image_display:
                self.image_display.set_interaction_mode('zoom_in')
            self._show_status_message("放大模式：点击图像进行放大")
        else:
            self._zoom_mode = None
            if self.image_display:
                self.image_display.set_interaction_mode('none')
            self._clear_status_message()

    def _handle_zoom_out(self, enabled: bool):
        """处理缩小模式切换"""
        if enabled:
            self._zoom_mode = 'zoom_out'
            self._cursor_mode = False
            if self.image_display:
                self.image_display.set_interaction_mode('zoom_out')
            self._show_status_message("缩小模式：点击图像进行缩小")
        else:
            self._zoom_mode = None
            if self.image_display:
                self.image_display.set_interaction_mode('none')
            self._clear_status_message()

    def _handle_zoom_area(self, enabled: bool):
        """处理区域放大模式切换"""
        if enabled:
            self._zoom_mode = 'zoom_area'
            self._cursor_mode = False
            if self.image_display:
                self.image_display.set_interaction_mode('zoom_area')
            self._show_status_message("区域放大模式：拖拽选择放大区域")
        else:
            self._zoom_mode = None
            if self.image_display:
                self.image_display.set_interaction_mode('none')
            self._clear_status_message()

    def _handle_reset_view(self):
        """处理视图复原 — 重置 ROI 为全传感器尺寸"""
        if self._camera_module and self._camera_module.is_connected():
            success = self._camera_module.reset_roi()
            if success:
                self._update_roi_cache()
                self._show_status_message("视图已重置")
            else:
                self._show_status_message("视图重置失败")
        else:
            self.image_display.refresh_current_image()
            self._show_status_message("相机未连接")

    def _handle_zoom_click(self, sensor_x: int, sensor_y: int):
        """处理缩放点击 — 以点击位置为中心进行放大/缩小

        Args:
            sensor_x, sensor_y: 传感器坐标
        """
        if not self._camera_module or not self._camera_module.is_connected():
            self._show_status_message("相机未连接")
            return

        roi = self._camera_module.get_roi()
        if not roi or roi[2] == 0 or roi[3] == 0:
            return

        ox, oy, w, h = roi
        sensor_w, sensor_h = self._camera_module.get_sensor_size()

        if self._zoom_mode == 'zoom_in':
            new_w = int(w / self.ZOOM_FACTOR)
            new_h = int(h / self.ZOOM_FACTOR)
        elif self._zoom_mode == 'zoom_out':
            new_w = int(w * self.ZOOM_FACTOR)
            new_h = int(h * self.ZOOM_FACTOR)
            new_w = min(new_w, sensor_w)
            new_h = min(new_h, sensor_h)
        else:
            return

        # 以点击位置为中心计算新偏移
        new_ox = sensor_x - new_w // 2
        new_oy = sensor_y - new_h // 2

        # 钳位偏移到传感器范围内
        new_ox = max(0, min(new_ox, sensor_w - new_w))
        new_oy = max(0, min(new_oy, sensor_h - new_h))

        success = self._camera_module.set_roi(new_ox, new_oy, new_w, new_h)
        if success:
            self._update_roi_cache()
            actual_roi = self._camera_module.get_roi()
            if actual_roi[2] > 0 and actual_roi[3] > 0:
                zoom_pct = (sensor_w * sensor_h) / (actual_roi[2] * actual_roi[3])
                self._show_status_message(f"缩放: {zoom_pct:.1f}x")

    def _handle_zoom_area_selection(self, sensor_x: int, sensor_y: int,
                                     width: int, height: int):
        """处理区域放大选择

        Args:
            sensor_x, sensor_y: 选区左上角传感器坐标
            width, height: 选区尺寸
        """
        if not self._camera_module or not self._camera_module.is_connected():
            self._show_status_message("相机未连接")
            return

        success = self._camera_module.set_roi(sensor_x, sensor_y, width, height)
        if success:
            self._update_roi_cache()
            actual_roi = self._camera_module.get_roi()
            sensor_w, sensor_h = self._camera_module.get_sensor_size()
            if actual_roi[2] > 0 and actual_roi[3] > 0:
                zoom_pct = (sensor_w * sensor_h) / (actual_roi[2] * actual_roi[3])
                self._show_status_message(f"区域放大: {zoom_pct:.1f}x")

    def _handle_zoom_area_preview(self, sensor_x: int, sensor_y: int,
                                   width: int, height: int):
        """处理区域放大拖拽时的实时预览"""
        self._show_status_message(
            f"选区: ({sensor_x}, {sensor_y}) {width}x{height}"
        )

    def _update_roi_cache(self):
        """更新 ImageDisplay 中的 ROI 缓存"""
        if self._camera_module and self.image_display:
            roi = self._camera_module.get_roi()
            sensor = self._camera_module.get_sensor_size()
            self.image_display.update_roi_info(roi, sensor)

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
