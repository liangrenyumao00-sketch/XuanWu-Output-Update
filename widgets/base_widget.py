# widgets/base_widget.py
"""
基础Widget类

该模块提供所有Widget的基础类，包含通用功能：
- 统一的样式管理
- 配置加载和保存
- 国际化支持
- 异常处理
- 性能监控
- 日志记录

作者：XuanWu OCR Team
版本：2.1.7
"""

import logging
import time
from typing import Dict, Any, Optional, Callable
from PyQt6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QMessageBox, QProgressBar
)
from PyQt6.QtCore import QTimer, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QFont, QPalette, QColor

from core.settings import load_settings, save_settings
from core.i18n import t
from core.enhanced_logger import get_enhanced_logger
from core.thread_pool_manager import get_thread_pool_manager, TaskPriority, PoolType


class BaseWidget(QWidget):
    """基础Widget类"""
    
    # 信号定义
    error_occurred = pyqtSignal(str)  # 错误信号
    status_changed = pyqtSignal(str)  # 状态变化信号
    progress_updated = pyqtSignal(int)  # 进度更新信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 基础属性
        self.logger = get_enhanced_logger()
        self.thread_manager = get_thread_pool_manager()
        self.settings = load_settings()
        self._widget_name = self.__class__.__name__
        
        # 性能监控
        self._creation_time = time.time()
        self._operation_times = {}
        
        # 初始化
        self._init_ui()
        self._init_connections()
        self._apply_theme()
        
        self.logger.debug(f"{self._widget_name} 初始化完成")
    
    def _init_ui(self):
        """初始化UI - 子类应重写此方法"""
        pass
    
    def _init_connections(self):
        """初始化信号连接 - 子类可重写此方法"""
        self.error_occurred.connect(self._handle_error)
        self.status_changed.connect(self._handle_status_change)
    
    def _apply_theme(self):
        """应用主题样式"""
        try:
            theme = self.settings.get('theme', '浅色')
            font_size = self.settings.get('font_size', 9)
            
            # 设置字体
            font = QFont()
            font.setPointSize(font_size)
            self.setFont(font)
            
            # 应用主题样式
            if theme == '深色':
                self._apply_dark_theme()
            else:
                self._apply_light_theme()
                
        except Exception as e:
            self.logger.error(f"主题应用失败: {e}")
    
    def _apply_dark_theme(self):
        """应用深色主题"""
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                border: none;
            }
            QPushButton {
                background-color: #404040;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 12px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #505050;
                border-color: #666666;
            }
            QPushButton:pressed {
                background-color: #353535;
            }
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #666666;
                border-color: #444444;
            }
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #404040;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px;
                color: #ffffff;
            }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
                border-color: #0078d4;
            }
            QComboBox {
                background-color: #404040;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px;
                color: #ffffff;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QGroupBox {
                border: 1px solid #555555;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
                color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
    
    def _apply_light_theme(self):
        """应用浅色主题"""
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                color: #000000;
                border: none;
            }
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 6px 12px;
                color: #000000;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border-color: #999999;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QPushButton:disabled {
                background-color: #f5f5f5;
                color: #999999;
                border-color: #dddddd;
            }
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 4px;
                color: #000000;
            }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
                border-color: #0078d4;
            }
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 4px;
                color: #000000;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #000000;
            }
            QLabel {
                color: #000000;
            }
            QGroupBox {
                border: 1px solid #cccccc;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
                color: #000000;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
    
    def _handle_error(self, error_message: str):
        """处理错误信号"""
        self.logger.error(f"{self._widget_name} 错误: {error_message}")
        self.show_error_message(error_message)
    
    def _handle_status_change(self, status: str):
        """处理状态变化信号"""
        self.logger.info(f"{self._widget_name} 状态: {status}")
    
    def show_error_message(self, message: str, title: str = None):
        """显示错误消息"""
        if title is None:
            title = t("错误")
        
        QMessageBox.critical(self, title, message)
    
    def show_info_message(self, message: str, title: str = None):
        """显示信息消息"""
        if title is None:
            title = t("信息")
        
        QMessageBox.information(self, title, message)
    
    def show_warning_message(self, message: str, title: str = None):
        """显示警告消息"""
        if title is None:
            title = t("警告")
        
        QMessageBox.warning(self, title, message)
    
    def confirm_action(self, message: str, title: str = None) -> bool:
        """确认操作"""
        if title is None:
            title = t("确认")
        
        reply = QMessageBox.question(
            self, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes
    
    def save_setting(self, key: str, value: Any):
        """保存设置"""
        try:
            self.settings[key] = value
            save_settings(self.settings)
            self.logger.debug(f"设置已保存: {key} = {value}")
        except Exception as e:
            self.logger.error(f"保存设置失败: {e}")
            self.error_occurred.emit(f"保存设置失败: {e}")
    
    def get_setting(self, key: str, default_value: Any = None) -> Any:
        """获取设置"""
        return self.settings.get(key, default_value)
    
    def reload_settings(self):
        """重新加载设置"""
        try:
            self.settings = load_settings()
            self._apply_theme()
            self.logger.debug(f"{self._widget_name} 设置已重新加载")
        except Exception as e:
            self.logger.error(f"重新加载设置失败: {e}")
            self.error_occurred.emit(f"重新加载设置失败: {e}")
    
    def run_async_task(self, 
                      func: Callable,
                      *args,
                      pool_type: PoolType = PoolType.GENERAL,
                      priority: TaskPriority = TaskPriority.NORMAL,
                      callback: Optional[Callable] = None,
                      error_callback: Optional[Callable] = None,
                      **kwargs) -> str:
        """
        运行异步任务
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            pool_type: 线程池类型
            priority: 任务优先级
            callback: 成功回调函数
            error_callback: 错误回调函数
            **kwargs: 函数关键字参数
            
        Returns:
            任务ID
        """
        def wrapped_func(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                if callback:
                    callback(result)
                return result
            except Exception as e:
                self.logger.error(f"异步任务执行失败: {e}")
                if error_callback:
                    error_callback(e)
                else:
                    self.error_occurred.emit(str(e))
                raise
        
        return self.thread_manager.submit(
            wrapped_func, *args,
            pool_type=pool_type,
            priority=priority,
            **kwargs
        )
    
    def measure_performance(self, operation_name: str):
        """性能测量装饰器"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    self._operation_times[operation_name] = duration
                    self.logger.debug(f"{self._widget_name}.{operation_name} 耗时: {duration:.3f}秒")
            return wrapper
        return decorator
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            'widget_name': self._widget_name,
            'creation_time': self._creation_time,
            'uptime': time.time() - self._creation_time,
            'operation_times': self._operation_times.copy()
        }
    
    def cleanup(self):
        """清理资源 - 子类应重写此方法"""
        try:
            self.logger.debug(f"{self._widget_name} 正在清理资源")
            # 子类可以在这里添加特定的清理逻辑
        except Exception as e:
            self.logger.error(f"{self._widget_name} 清理资源时出错: {e}")


class BaseDialog(QDialog):
    """基础对话框类"""
    
    def __init__(self, parent=None, title: str = ""):
        super().__init__(parent)
        
        # 基础属性
        self.logger = get_enhanced_logger()
        self.thread_manager = get_thread_pool_manager()
        self.settings = load_settings()
        self._dialog_name = self.__class__.__name__
        
        # 设置对话框属性
        if title:
            self.setWindowTitle(title)
        
        # 初始化
        self._init_ui()
        self._init_connections()
        self._apply_theme()
        
        self.logger.debug(f"{self._dialog_name} 初始化完成")
    
    def _init_ui(self):
        """初始化UI - 子类应重写此方法"""
        # 创建基础布局
        self.layout = QVBoxLayout(self)
        
        # 创建按钮布局
        self.button_layout = QHBoxLayout()
        self.layout.addLayout(self.button_layout)
        
        # 添加确定和取消按钮
        self.ok_button = QPushButton(t("确定"))
        self.cancel_button = QPushButton(t("取消"))
        
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.ok_button)
        self.button_layout.addWidget(self.cancel_button)
    
    def _init_connections(self):
        """初始化信号连接"""
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
    
    def _apply_theme(self):
        """应用主题样式"""
        try:
            theme = self.settings.get('theme', '浅色')
            font_size = self.settings.get('font_size', 9)
            
            # 设置字体
            font = QFont()
            font.setPointSize(font_size)
            self.setFont(font)
            
            # 应用主题样式（与BaseWidget相同）
            if theme == '深色':
                self._apply_dark_theme()
            else:
                self._apply_light_theme()
                
        except Exception as e:
            self.logger.error(f"主题应用失败: {e}")
    
    def _apply_dark_theme(self):
        """应用深色主题"""
        # 与BaseWidget相同的样式
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QPushButton {
                background-color: #404040;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 12px;
                color: #ffffff;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #505050;
                border-color: #666666;
            }
            QPushButton:pressed {
                background-color: #353535;
            }
            QLabel {
                color: #ffffff;
            }
        """)
    
    def _apply_light_theme(self):
        """应用浅色主题"""
        # 与BaseWidget相同的样式
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                color: #000000;
            }
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 6px 12px;
                color: #000000;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border-color: #999999;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QLabel {
                color: #000000;
            }
        """)
    
    def show_error_message(self, message: str, title: str = None):
        """显示错误消息"""
        if title is None:
            title = t("错误")
        
        QMessageBox.critical(self, title, message)
    
    def show_info_message(self, message: str, title: str = None):
        """显示信息消息"""
        if title is None:
            title = t("信息")
        
        QMessageBox.information(self, title, message)


class ProgressDialog(BaseDialog):
    """进度对话框"""
    
    def __init__(self, parent=None, title: str = "", message: str = ""):
        self.progress_bar = None
        self.message_label = None
        super().__init__(parent, title)
        
        if message:
            self.set_message(message)
    
    def _init_ui(self):
        """初始化UI"""
        self.layout = QVBoxLayout(self)
        
        # 消息标签
        self.message_label = QLabel("")
        self.layout.addWidget(self.message_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.layout.addWidget(self.progress_bar)
        
        # 取消按钮
        self.button_layout = QHBoxLayout()
        self.cancel_button = QPushButton(t("取消"))
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.button_layout)
    
    def _init_connections(self):
        """初始化信号连接"""
        self.cancel_button.clicked.connect(self.reject)
    
    def set_message(self, message: str):
        """设置消息"""
        if self.message_label:
            self.message_label.setText(message)
    
    def set_progress(self, value: int):
        """设置进度"""
        if self.progress_bar:
            self.progress_bar.setValue(value)
    
    def set_range(self, minimum: int, maximum: int):
        """设置进度范围"""
        if self.progress_bar:
            self.progress_bar.setRange(minimum, maximum)