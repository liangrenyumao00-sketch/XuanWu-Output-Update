# core/group_framework_styles.py
"""
统一的分组框架样式管理器
为所有重新设计的窗口提供一致的视觉层次、间距布局和交互体验
"""

from typing import Dict, Optional
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class GroupFrameworkStyleManager:
    """分组框架样式管理器"""
    
    def __init__(self):
        pass
        
    def _detect_current_theme(self) -> str:
        """检测当前主题"""
        try:
            from core.settings import load_settings
            settings = load_settings()
            return settings.get('theme', '浅色')
        except Exception:
            return '浅色'
    
    def is_dark_theme(self) -> bool:
        """判断是否为深色主题"""
        current_theme = self._detect_current_theme()
        return current_theme in ['深色', '蓝色', '绿色', '紫色', '高对比度']
    
    def get_base_dialog_style(self) -> str:
        """获取基础对话框样式"""
        if self.is_dark_theme():
            return """
                QDialog {
                    background-color: #2b2b2b;
                    color: #ffffff;
                    font-family: "Microsoft YaHei UI", "微软雅黑", sans-serif;
                }
            """
        else:
            return """
                QDialog {
                    background-color: #f8f9fa;
                    color: #212529;
                    font-family: "Microsoft YaHei UI", "微软雅黑", sans-serif;
                }
            """
    
    def get_group_box_style(self) -> str:
        """获取分组框样式 - 优化版本"""
        if self.is_dark_theme():
            return """
                QGroupBox {
                    font-weight: 600;
                    font-size: 13px;
                    border: 2px solid #4a4a4a;
                    border-radius: 10px;
                    margin-top: 18px;
                    padding-top: 18px;
                    padding-left: 12px;
                    padding-right: 12px;
                    padding-bottom: 12px;
                    background-color: #353535;
                    color: #ffffff;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 15px;
                    padding: 0 10px 0 10px;
                    color: #ffffff;
                    background-color: #353535;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 4px;
                }
            """
        else:
            return """
                QGroupBox {
                    font-weight: 600;
                    font-size: 13px;
                    border: 2px solid #d1d5db;
                    border-radius: 10px;
                    margin-top: 18px;
                    padding-top: 18px;
                    padding-left: 12px;
                    padding-right: 12px;
                    padding-bottom: 12px;
                    background-color: #ffffff;
                    color: #374151;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 15px;
                    padding: 0 10px 0 10px;
                    color: #374151;
                    background-color: #ffffff;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 4px;
                }
            """
    
    def get_text_widget_style(self) -> str:
        """获取文本控件样式 - 优化版本"""
        if self.is_dark_theme():
            return """
                QTextEdit, QTextBrowser, QPlainTextEdit {
                    background-color: #404040;
                    border: 1px solid #555555;
                    border-radius: 8px;
                    color: #ffffff;
                    padding: 12px;
                    font-size: 12px;
                    line-height: 1.5;
                    selection-background-color: #0078d4;
                }
                QTextEdit:focus, QTextBrowser:focus, QPlainTextEdit:focus {
                    border: 2px solid #0078d4;
                    background-color: #454545;
                }
            """
        else:
            return """
                QTextEdit, QTextBrowser, QPlainTextEdit {
                    border: 1px solid #d1d5db;
                    border-radius: 8px;
                    color: #374151;
                    padding: 12px;
                    font-size: 12px;
                    line-height: 1.5;
                    selection-background-color: #0078d4;
                }
                QTextEdit:focus, QTextBrowser:focus, QPlainTextEdit:focus {
                    border: 2px solid #0078d4;
                }
            """
    
    def get_input_widget_style(self) -> str:
        """获取输入控件样式 - 优化版本"""
        if self.is_dark_theme():
            return """
                QLineEdit, QComboBox {
                    background-color: #404040;
                    border: 1px solid #555555;
                    border-radius: 6px;
                    color: #ffffff;
                    padding: 8px 12px;
                    font-size: 12px;
                    min-height: 20px;
                }
                QLineEdit {
                    placeholder-text-color: #999999;
                }
                QLineEdit:focus, QComboBox:focus {
                    border: 2px solid #0078d4;
                    background-color: #454545;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 25px;
                    background-color: #505050;
                    border-top-right-radius: 6px;
                    border-bottom-right-radius: 6px;
                }
                QComboBox::down-arrow {
                    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQgNkw4IDEwTDEyIDYiIHN0cm9rZT0iI2ZmZmZmZiIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
                    width: 16px;
                    height: 16px;
                }
                QComboBox QAbstractItemView {
                    background-color: #404040;
                    border: 1px solid #555555;
                    color: #ffffff;
                    selection-background-color: #0078d4;
                }
                QCheckBox {
                    color: #ffffff;
                    spacing: 8px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border: 1px solid #646464;
                    background-color: #3c3c3c;
                }
                QCheckBox::indicator:checked {
                    background-color: #007acc;
                    border-color: #007acc;
                }
                QCheckBox::indicator:checked::after {
                    content: "✓";
                    color: white;
                    font-weight: bold;
                    font-size: 12px;
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 16px;
                    height: 16px;
                    text-align: center;
                    line-height: 16px;
                }
            """
        else:
            return """
                QLineEdit, QComboBox {
                    border: 1px solid #d1d5db;
                    border-radius: 6px;
                    color: #374151;
                    padding: 8px 12px;
                    font-size: 12px;
                    min-height: 20px;
                }
                QLineEdit:focus, QComboBox:focus {
                    border: 2px solid #0078d4;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 25px;
                    background-color: #e5e7eb;
                    border-top-right-radius: 6px;
                    border-bottom-right-radius: 6px;
                }
                QComboBox::down-arrow {
                    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQgNkw4IDEwTDEyIDYiIHN0cm9rZT0iIzM3NDE1MSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
                    width: 16px;
                    height: 16px;
                }
                QComboBox QAbstractItemView {
                    border: 1px solid #d1d5db;
                    color: #374151;
                    selection-background-color: #0078d4;
                    selection-color: #ffffff;
                }
                QCheckBox {
                    color: #374151;
                    spacing: 8px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border: 1px solid #d1d5db;
                }
                QCheckBox::indicator:checked {
                background-color: #0078d4;
                border-color: #0078d4;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border-color: #0078d4;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEzIDRMNiAxMUwzIDgiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
                text-align: center;
                line-height: 16px;
            }
            """
    
    def get_button_style(self) -> str:
        """获取按钮样式 - 系统原生样式"""
        # 返回空字符串，完全使用系统默认样式
        return ""
    
    def get_list_widget_style(self) -> str:
        """获取列表控件样式 - 优化版本"""
        if self.is_dark_theme():
            return """
                QListWidget {
                    background-color: #404040;
                    border: 1px solid #555555;
                    border-radius: 8px;
                    color: #ffffff;
                    outline: none;
                }
                QListWidget::item {
                    padding: 12px 16px;
                    border-bottom: 1px solid #555555;
                    border-radius: 4px;
                    margin: 2px;
                }
                QListWidget::item:selected {
                    background-color: #0078d4;
                    color: #ffffff;
                }
                QListWidget::item:hover {
                    background-color: #505050;
                }
                QListWidget::item:selected:hover {
                    background-color: #106ebe;
                }
            """
        else:
            return """
                QListWidget {
                    border: 1px solid #d1d5db;
                    border-radius: 8px;
                    color: #374151;
                    outline: none;
                }
                QListWidget::item {
                    padding: 12px 16px;
                    border-bottom: 1px solid #e5e7eb;
                    border-radius: 4px;
                    margin: 2px;
                }
                QListWidget::item:selected {
                    background-color: #0078d4;
                    color: #ffffff;
                }
                QListWidget::item:hover {
                    background-color: #f3f4f6;
                }
                QListWidget::item:selected:hover {
                    background-color: #106ebe;
                }
            """
    
    def get_splitter_style(self) -> str:
        """获取分割器样式 - 优化版本"""
        if self.is_dark_theme():
            return """
                QSplitter::handle {
                    background-color: #555555;
                    border-radius: 2px;
                }
                QSplitter::handle:horizontal {
                    width: 6px;
                    margin: 2px 0;
                }
                QSplitter::handle:vertical {
                    height: 6px;
                    margin: 0 2px;
                }
                QSplitter::handle:hover {
                    background-color: #0078d4;
                }
            """
        else:
            return """
                QSplitter::handle {
                    background-color: #d1d5db;
                    border-radius: 2px;
                }
                QSplitter::handle:horizontal {
                    width: 6px;
                    margin: 2px 0;
                }
                QSplitter::handle:vertical {
                    height: 6px;
                    margin: 0 2px;
                }
                QSplitter::handle:hover {
                    background-color: #0078d4;
                }
            """
    
    def get_scroll_area_style(self) -> str:
        """获取滚动区域样式 - 优化版本"""
        if self.is_dark_theme():
            return """
                QScrollArea {
                    border: none;
                    background-color: transparent;
                }
                QScrollBar:vertical {
                    background-color: #404040;
                    width: 12px;
                    border-radius: 6px;
                    margin: 0;
                }
                QScrollBar::handle:vertical {
                    background-color: #666666;
                    border-radius: 6px;
                    min-height: 20px;
                    margin: 2px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #0078d4;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar:horizontal {
                    background-color: #404040;
                    height: 12px;
                    border-radius: 6px;
                    margin: 0;
                }
                QScrollBar::handle:horizontal {
                    background-color: #666666;
                    border-radius: 6px;
                    min-width: 20px;
                    margin: 2px;
                }
                QScrollBar::handle:horizontal:hover {
                    background-color: #0078d4;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0px;
                }
            """
        else:
            return """
                QScrollArea {
                    border: none;
                    background-color: transparent;
                }
                QScrollBar:vertical {
                    background-color: #f3f4f6;
                    width: 12px;
                    border-radius: 6px;
                    margin: 0;
                }
                QScrollBar::handle:vertical {
                    background-color: #d1d5db;
                    border-radius: 6px;
                    min-height: 20px;
                    margin: 2px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #0078d4;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
                QScrollBar:horizontal {
                    background-color: #f3f4f6;
                    height: 12px;
                    border-radius: 6px;
                    margin: 0;
                }
                QScrollBar::handle:horizontal {
                    background-color: #d1d5db;
                    border-radius: 6px;
                    min-width: 20px;
                    margin: 2px;
                }
                QScrollBar::handle:horizontal:hover {
                    background-color: #0078d4;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0px;
                }
            """
    
    def get_complete_style(self) -> str:
        """获取完整的样式表"""
        return (
            self.get_base_dialog_style() +
            self.get_group_box_style() +
            self.get_text_widget_style() +
            self.get_input_widget_style() +
            self.get_button_style() +
            self.get_list_widget_style() +
            self.get_splitter_style() +
            self.get_scroll_area_style()
        )
    
    def apply_to_widget(self, widget: QWidget) -> None:
        """将样式应用到指定控件"""
        widget.setStyleSheet(self.get_complete_style())
    
    def get_layout_margins(self) -> tuple:
        """获取推荐的布局边距"""
        return (15, 15, 15, 15)  # left, top, right, bottom
    
    def get_layout_spacing(self) -> int:
        """获取推荐的布局间距"""
        return 12
    
    def get_group_spacing(self) -> int:
        """获取分组之间的间距"""
        return 20
    
    def setup_layout_properties(self, layout) -> None:
        """设置布局属性"""
        margins = self.get_layout_margins()
        layout.setContentsMargins(*margins)
        layout.setSpacing(self.get_layout_spacing())

# 全局样式管理器实例
_style_manager = None

def get_style_manager() -> GroupFrameworkStyleManager:
    """获取全局样式管理器实例"""
    global _style_manager
    if _style_manager is None:
        _style_manager = GroupFrameworkStyleManager()
    return _style_manager

def reset_style_manager() -> None:
    """重置样式管理器，用于主题切换时"""
    global _style_manager
    _style_manager = None

def apply_group_framework_style(widget: QWidget) -> None:
    """便捷函数：应用分组框架样式到控件"""
    style_manager = get_style_manager()
    style_manager.apply_to_widget(widget)

def setup_group_framework_layout(layout) -> None:
    """便捷函数：设置分组框架布局属性"""
    style_manager = get_style_manager()
    style_manager.setup_layout_properties(layout)