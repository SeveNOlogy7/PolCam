from qtpy import QtWidgets, QtCore
import cv2
import numpy as np
import os
from datetime import datetime
from typing import Optional, Tuple, Union, List
from polcam.core.image_processor import ImageProcessor
from .base_module import BaseModule
from ..core.processing_module import ProcessingMode

class ToolbarController(BaseModule):
    def __init__(self, main_window):
        super().__init__("ToolbarController")
        self._main_window = main_window
        self._toolbar = main_window.toolbar
        
        # 缓存最近的图像和结果
        self._current_frame = None
        self._last_result = None
        self._current_frame_timestamp = None
        self._last_result_timestamp = None

    def _do_initialize(self) -> bool:
        """初始化工具栏控制器"""
        try:
            # 连接信号
            self._toolbar.save_raw_action.triggered.connect(self._handle_save_raw)
            self._toolbar.save_result_action.triggered.connect(self._handle_save_result)
            self._toolbar.settings_action.triggered.connect(self._handle_settings)
            self._toolbar.about_action.triggered.connect(self._handle_about)
            self._toolbar.help_action.triggered.connect(self._handle_help)
            self._toolbar.open_raw_action.triggered.connect(self._handle_open_raw)
            return True
        except Exception as e:
            self._logger.error(f"工具栏控制器初始化失败: {str(e)}")
            return False

    def _do_start(self) -> bool:
        """启动工具栏控制器"""
        return True

    def _do_stop(self) -> bool:
        """停止工具栏控制器"""
        return True

    def _do_destroy(self) -> bool:
        """销毁工具栏控制器"""
        try:
            # 断开所有信号连接
            self._toolbar.save_raw_action.triggered.disconnect(self._handle_save_raw)
            self._toolbar.save_result_action.triggered.disconnect(self._handle_save_result)
            self._toolbar.settings_action.triggered.disconnect(self._handle_settings)
            self._toolbar.about_action.triggered.disconnect(self._handle_about)
            self._toolbar.help_action.triggered.disconnect(self._handle_help)  # 添加这行
            return True
        except Exception as e:
            self._logger.error(f"工具栏控制器销毁失败: {str(e)}")
            return False

    def enable_save_raw(self, enable: bool):
        """启用/禁用保存原始图像按钮"""
        self._toolbar.save_raw_action.setEnabled(enable)

    def enable_save_result(self, enable: bool):
        """启用/禁用保存处理结果按钮"""
        self._toolbar.save_result_action.setEnabled(enable)

    def update_current_frame(self, frame: np.ndarray, timestamp: Optional[datetime] = None):
        """更新当前帧"""
        self._current_frame = frame
        self._current_frame_timestamp = timestamp

    def update_last_result(self, result, timestamp: Optional[datetime] = None):
        """更新最近的处理结果"""
        self._last_result = result
        self._last_result_timestamp = timestamp

    def _format_timestamp(self, timestamp: Optional[Union[datetime, float]]) -> str:
        """格式化时间戳
        
        Args:
            timestamp: 时间戳，可以是datetime对象或者UNIX时间戳(float)
            
        Returns:
            str: 格式化的时间字符串
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        if isinstance(timestamp, float):
            timestamp = datetime.fromtimestamp(timestamp)
            
        return timestamp.strftime("%Y%m%d_%H%M%S")

    def _get_processing_mode_str(self) -> str:
        """获取处理模式字符串，从处理结果的metadata中获取信息"""
        if not self._last_result:
            return ""
            
        # 基本模式映射
        mode_map = {
            ProcessingMode.RAW: "RAW",
            ProcessingMode.SINGLE_COLOR: "SINGLE",
            ProcessingMode.SINGLE_GRAY: "SINGLE",
            ProcessingMode.MERGED_COLOR: "MERGED",
            ProcessingMode.MERGED_GRAY: "MERGED",
            ProcessingMode.QUAD_COLOR: "QUAD",
            ProcessingMode.QUAD_GRAY: "QUAD",
            ProcessingMode.POLARIZATION: "POL"
        }
        
        mode_str = mode_map.get(self._last_result.mode, "UNKNOWN")
        metadata = self._last_result.metadata
        
        # 添加颜色/灰度标识
        if self._last_result.mode != ProcessingMode.RAW:
            if self._last_result.mode in [ProcessingMode.SINGLE_COLOR, ProcessingMode.MERGED_COLOR, ProcessingMode.QUAD_COLOR]:
                mode_str += "_COLOR"
            else:
                mode_str += "_GRAY"
            
        # 添加白平衡标记 (仅对彩色图像)
        if metadata.get('wb_enabled', False):
            mode_str += "_WB"
        # 对于偏振模式的特殊处理
        elif self._last_result.mode == ProcessingMode.POLARIZATION and metadata.get('pol_wb_enabled', False):
            if metadata.get('is_color', False):
                mode_str += "_WB"
                
        # 添加角度信息 
        if self._last_result.mode in [ProcessingMode.SINGLE_COLOR, ProcessingMode.SINGLE_GRAY]:
            angle = metadata.get('angle', 0)
            mode_str += f"_{angle}"
                
        # 添加偏振信息
        if self._last_result.mode == ProcessingMode.POLARIZATION:
            pol_types = metadata.get('type', [])
            if len(pol_types) > 1:  # 跳过第一个merged类型
                mode_str += f"_{pol_types[1].upper()}"  # 使用第二个类型(通常是DOLP)
                
        return mode_str

    def _get_save_filename(self, title: str, timestamp: Optional[datetime] = None, mode_str: str = "") -> Tuple[str, str, bool]:
        """获取保存文件名和扩展名
        
        Args:
            title: 对话框标题
            timestamp: 时间戳
            mode_str: 处理模式字符串（可选）
        
        Returns:
            (filepath, extension, success): 完整文件路径、扩展名和是否成功
        """
        timestamp_str = self._format_timestamp(timestamp)
        default_name = f"{timestamp_str}{mode_str}"
        
        dialog = QtWidgets.QFileDialog(self._main_window)
        dialog.setWindowTitle(title)
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        dialog.setNameFilter("TIFF files (*.tiff *.tif);;BMP files (*.bmp);;PNG files (*.png)")
        dialog.selectNameFilter("TIFF files (*.tiff *.tif)")
        dialog.selectFile(default_name)
        
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            filename = dialog.selectedFiles()[0]
            # 分离基础名称和扩展名
            base_name, ext = os.path.splitext(filename)
            
            # 如果没有扩展名，根据选择的过滤器添加扩展名
            if not ext:
                filter_text = dialog.selectedNameFilter()
                if "*.tiff" in filter_text or "*.tif" in filter_text:
                    ext = ".tiff"
                elif "*.bmp" in filter_text:
                    ext = ".bmp"
                elif "*.png" in filter_text:
                    ext = ".png"
                    
            return base_name, ext, True
        return "", "", False

    def _get_load_filename(self, title: str) -> Tuple[str, bool]:
        """获取要加载的文件名
        
        复用保存对话框的过滤器设置，保持一致的用户体验
        """
        dialog = QtWidgets.QFileDialog(self._main_window)
        dialog.setWindowTitle(title)
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptOpen)
        dialog.setNameFilter("TIFF files (*.tiff *.tif);;BMP files (*.bmp);;PNG files (*.png);;Raw files (*.raw *.bin);;All Files (*)")
        
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            return dialog.selectedFiles()[0], True
        return "", False

    def _verify_image_size(self, data: np.ndarray) -> bool:
        """验证图像尺寸是否为8x8马赛克的整数倍
        
        Args:
            data: 要验证的图像数据
            
        Returns:
            bool: 是否符合要求
        """
        if len(data.shape) != 2:
            return False
        shape = data.shape
        return shape[0] % 8 == 0 and shape[1] % 8 == 0

    def _save_image_set(self, images: List[np.ndarray], base_name: str, suffixes: List[str], 
                       save_dir: str, extension: str) -> bool:
        """保存一组图像
        
        Args:
            images: 要保存的图像列表
            base_name: 基础文件名
            suffixes: 每个图像对应的后缀名列表
            save_dir: 保存目录
            extension: 图像文件扩展名
        
        Returns:
            bool: 是否全部保存成功
        """
        success = True
        for img, suffix in zip(images, suffixes):
            filename = os.path.join(save_dir, f"{base_name}_{suffix}{extension}")
            try:
                cv2.imwrite(filename, img)
                self._main_window.status_label.setText(f"已保存: {os.path.basename(filename)}")
                self._logger.info(f"图像已保存: {filename}")
            except Exception as e:
                self._main_window.status_label.setText(f"保存失败: {os.path.basename(filename)}")
                self._logger.error(f"保存图像失败 {suffix}: {str(e)}")
                success = False
        return success

    def _save_polarization_data(self, dolp: np.ndarray, aolp: np.ndarray, docp: np.ndarray, 
                               save_dir: str, base_name: str) -> bool:
        """保存原始偏振数据
        
        Args:
            dolp: 线偏振度数据
            aolp: 偏振角数据
            docp: 圆偏振度数据
            save_dir: 保存目录
            base_name: 基础文件名
            
        Returns:
            bool: 是否保存成功
        """
        try:
            pol_data = {
                'dolp': dolp,  # 原始偏振度数据
                'aolp': aolp,  # 原始偏振角数据
                'docp': docp   # 原始圆偏振度数据
            }
            npy_filename = os.path.join(save_dir, f"{base_name}_POL.npy")
            np.save(npy_filename, pol_data)
            self._logger.info(f"偏振数据已保存: {npy_filename}")
            return True
        except Exception as e:
            self._logger.error(f"保存偏振数据失败: {str(e)}")
            return False

    def _handle_save_raw(self):
        """处理保存原始图像事件"""
        if self._current_frame is None:
            return
            
        base_name, ext, success = self._get_save_filename(
            "保存原始图像",
            self._current_frame_timestamp,
            "_RAW"
        )
        
        if success:
            filename = f"{base_name}{ext}"
            try:
                cv2.imwrite(filename, self._current_frame)
                self._main_window.status_label.setText(f"已保存: {os.path.basename(filename)}")
                self._logger.info(f"原始图像已保存: {filename}")
                # 添加保存成功对话框
                QtWidgets.QMessageBox.information(
                    self._main_window,
                    "保存成功",
                    f"原始图像已保存到:\n{os.path.dirname(filename)}"
                )
                self._main_window.status_label.setText("就绪")
            except Exception as e:
                self._main_window.status_label.setText(f"保存失败: {os.path.basename(filename)}")
                self._logger.error(f"保存原始图像失败: {str(e)}")
                QtWidgets.QMessageBox.warning(
                    self._main_window,
                    "保存失败",
                    f"保存原始图像失败: {str(e)}"
                )
                self._main_window.status_label.setText("保存失败")

    def _handle_save_result(self):
        """处理保存处理结果事件"""
        if self._last_result is None:
            return
            
        filepath, ext, success = self._get_save_filename(
            "保存处理结果",
            self._last_result_timestamp
        )
        
        if not success:
            return

        try:
            save_dir = os.path.dirname(filepath)
            base_name = os.path.basename(filepath)

            if self._last_result.mode == ProcessingMode.POLARIZATION:
                # 获取原始图像和参数
                merged = self._last_result.images[0]
                dolp = self._last_result.images[1]    # 原始偏振度数据
                aolp = self._last_result.images[2]    # 原始偏振角数据
                docp = self._last_result.images[3]    # 原始圆偏振度数据
                
                # 保存原始偏振数据
                save_npy_success = self._save_polarization_data(
                    dolp, aolp, docp,
                    save_dir, base_name
                )
                
                # 对偏振参数进行颜色映射用于可视化保存
                dolp_colored, aolp_colored, docp_colored = ImageProcessor.colormap_polarization(
                    dolp, aolp, docp
                )
                
                # 准备文件名
                metadata = self._last_result.metadata
                is_color = metadata.get('is_color', False)
                wb_enabled = metadata.get('pol_wb_enabled', False)
                merged_name = f"_MERGED_{'COLOR' if is_color else 'GRAY'}{'_WB' if wb_enabled else ''}"
                
                # 保存彩色映射图像
                success = self._save_image_set(
                    images=[merged, dolp_colored, aolp_colored, docp_colored],
                    base_name=base_name,
                    suffixes=[merged_name, 'DOLP', 'AOLP', 'DOCP'],
                    save_dir=save_dir,
                    extension=ext
                )
                
                # 更新总体保存状态
                success = success and save_npy_success

            elif self._last_result.mode in [ProcessingMode.QUAD_COLOR, ProcessingMode.QUAD_GRAY]:
                # 基础文件名添加模式信息
                mode_str = "COLOR" if self._last_result.mode == ProcessingMode.QUAD_COLOR else "GRAY"
                if self._last_result.metadata.get('wb_enabled', False):
                    mode_str += "_WB"
                base_name = f"{base_name}_{mode_str}"
                
                # 使用统一的保存方法
                success = self._save_image_set(
                    self._last_result.images,
                    base_name,
                    ['0', '45', '90', '135'],
                    save_dir,
                    ext
                )

            else:
                # 其他模式
                mode_str = self._get_processing_mode_str()
                filename = os.path.join(save_dir, f"{base_name}_{mode_str}{ext}")
                try:
                    cv2.imwrite(filename, self._last_result.images[0])
                    self._main_window.status_label.setText(f"已保存: {os.path.basename(filename)}")
                    success = True
                    self._logger.info(f"图像已保存: {filename}")
                except Exception as e:
                    self._main_window.status_label.setText(f"保存失败: {os.path.basename(filename)}")
                    self._logger.error(f"保存图像失败: {str(e)}")
                    success = False

            if success:
                QtWidgets.QMessageBox.information(
                    self._main_window,
                    "保存成功",
                    f"处理结果已保存到目录:\n{save_dir}"
                )
                self._main_window.status_label.setText("就绪")
            else:
                QtWidgets.QMessageBox.warning(
                    self._main_window,
                    "保存失败",
                    "部分图像保存失败，请检查日志"
                )
                self._main_window.status_label.setText("保存失败")

        except Exception as e:
            self._logger.error(f"保存处理结果失败: {str(e)}")
            QtWidgets.QMessageBox.warning(
                self._main_window,
                "保存失败",
                f"保存处理结果失败: {str(e)}"
            )

    def _handle_open_raw(self):
        """处理打开原始图像"""
        file_path, success = self._get_load_filename("打开原始图像")
        
        if not success:
            return
            
        try:
            # 读取原始图像文件
            raw_data = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            if raw_data is None:
                raise ValueError("无法读取图像文件")
            
            # 验证图像尺寸
            if not self._verify_image_size(raw_data):
                raise ValueError("图像尺寸必须是8x8马赛克的整数倍")
            
            
            frame = raw_data
            timestamp = QtCore.QDateTime.currentDateTime()
            
            # 更新主窗口的状态
            self._main_window.current_frame = frame
            self._main_window._current_frame_timestamp = timestamp
            
            # 更新当前帧
            self.update_current_frame(frame, timestamp)
            self.enable_save_raw(True)
            
            # 获取当前显示模式并更新显示
            current_mode = ProcessingMode.index_to_mode(
                self._main_window.image_display.display_mode.currentIndex()
            )
            
            if current_mode == ProcessingMode.RAW:
                self._main_window.image_display.show_image(frame)
            else:
                self._main_window.processor.process_frame(frame)
            
            self._main_window.status_label.setText(f"已加载图像: {file_path}")
                
        except Exception as e:
            self._logger.error(f"打开原始图像失败: {str(e)}")
            QtWidgets.QMessageBox.warning(
                self._main_window,
                "错误",
                f"无法读取图像文件: {str(e)}"
            )

    def _handle_settings(self):
        """处理设置事件"""
        # TODO: 实现设置对话框
        self._main_window.status_label.setText("显示设置界面（不支持）")

    def _handle_about(self):
        """处理关于事件"""
        about_text = """
        <h3>PolCam</h3>
        <p>版本: 1.0.0</p>
        <p>偏振相机采集和处理软件</p>
        <p>作者: Junhao Cai</p>
        <p>Copyright © 2024</p>
        """
        QtWidgets.QMessageBox.about(self._main_window, "关于", about_text)
        self._main_window.status_label.setText("显示关于信息")

    def _handle_help(self):
        """处理帮助按钮点击事件"""
        # 显示默认的帮助图像
        self._main_window.image_display.show_default_image()
        self._main_window.status_label.setText("显示帮助信息")
