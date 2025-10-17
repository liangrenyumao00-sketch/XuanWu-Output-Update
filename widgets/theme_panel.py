# widgets/theme_panel.py
"""
主题设置面板模块

该模块提供了应用程序的主题设置界面，支持自动主题切换、手动主题选择、
主题预览等功能。可以跟随系统主题或手动选择特定主题。

主要功能：
- 自动主题：跟随系统主题自动切换
- 手动选择：提供多种预设主题选择
- 实时预览：即时查看主题切换效果
- 主题描述：显示每个主题的详细说明
- 设置保存：持久化主题配置

依赖：
- PyQt6：GUI框架
- core.settings：设置管理
- core.theme：主题管理

作者：XuanWu OCR Team
版本：2.1.7
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, 
    QCheckBox, QGroupBox, QGridLayout, QFrame, QButtonGroup, QRadioButton
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont
import logging
import platform
import subprocess

from core.settings import load_settings, save_settings
from core.theme import apply_theme, get_available_themes


class ThemePanel(QDialog):
    """
    简洁的主题切换面板
    
    提供应用程序主题设置功能，包括自动主题切换和手动主题选择。
    支持实时预览和主题描述显示。
    
    Attributes:
        settings (dict): 当前设置配置
        auto_theme_cb (QCheckBox): 自动主题复选框
        theme_combo (QComboBox): 主题选择下拉框
        theme_desc_label (QLabel): 主题描述标签
        preview_btn (QPushButton): 预览按钮
        reset_btn (QPushButton): 重置按钮
        cancel_btn (QPushButton): 取消按钮
        ok_btn (QPushButton): 确定按钮
    
    Signals:
        settings_changed (dict): 设置发生变化时发出的信号
    
    Example:
        >>> panel = ThemePanel(parent_widget)
        >>> panel.settings_changed.connect(on_settings_changed)
        >>> panel.show()
    """
    settings_changed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        
        # 连接语言切换信号
        self.connect_language_signal()
        
        self.init_ui()
        self.load_values()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("主题设置")
        self.setFixedSize(400, 300)
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        
        # 自动主题组
        auto_group = QGroupBox("自动主题")
        auto_layout = QVBoxLayout()
        
        self.auto_theme_cb = QCheckBox("跟随系统主题")
        self.auto_theme_cb.stateChanged.connect(self.on_auto_theme_changed)
        auto_layout.addWidget(self.auto_theme_cb)
        
        auto_group.setLayout(auto_layout)
        main_layout.addWidget(auto_group)
        
        # 手动主题选择组
        manual_group = QGroupBox("手动选择主题")
        manual_layout = QVBoxLayout()
        
        # 主题选择标签
        theme_label = QLabel("选择主题:")
        manual_layout.addWidget(theme_label)
        
        # 主题下拉框
        self.theme_combo = QComboBox()
        available_themes = get_available_themes()
        self.theme_combo.addItems(available_themes)
        manual_layout.addWidget(self.theme_combo)
        
        # 主题描述
        self.theme_desc_label = QLabel()
        self.theme_desc_label.setWordWrap(True)
        manual_layout.addWidget(self.theme_desc_label)
        
        manual_group.setLayout(manual_layout)
        main_layout.addWidget(manual_group)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 预览按钮
        self.preview_btn = QPushButton("预览")
        self.preview_btn.clicked.connect(self.preview_theme)
        button_layout.addWidget(self.preview_btn)
        
        # 重置按钮
        self.reset_btn = QPushButton("重置")
        self.reset_btn.clicked.connect(self.reset_settings)
        button_layout.addWidget(self.reset_btn)
        
        # 弹簧
        button_layout.addStretch()
        
        # 取消按钮
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        # 确定按钮
        self.ok_btn = QPushButton("确定")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(self.ok_btn)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        
        # 连接信号
        self.theme_combo.currentTextChanged.connect(self.update_theme_description)
        
    def on_auto_theme_changed(self):
        """自动主题选项改变时的处理"""
        is_auto = self.auto_theme_cb.isChecked()
        self.theme_combo.setEnabled(not is_auto)
        self.preview_btn.setEnabled(not is_auto)
        
        if is_auto:
            # 自动检测系统主题
            system_theme = self.detect_system_theme()
            index = self.theme_combo.findText(system_theme)
            if index >= 0:
                self.theme_combo.setCurrentIndex(index)
                
    def update_theme_description(self):
        """更新主题描述"""
        current_theme = self.theme_combo.currentText()
        descriptions = {
            "浅色": "经典的浅色主题，适合日间使用",
            "深色": "护眼的深色主题，适合夜间使用",
            "蓝色": "专业的蓝色主题，商务风格",
            "绿色": "清新的绿色主题，自然风格",
            "紫色": "优雅的紫色主题，时尚风格",
            "高对比度": "高对比度主题，提升可读性"
        }
        
        desc = descriptions.get(current_theme, "")
        self.theme_desc_label.setText(desc)
        
    def load_values(self):
        """加载设置值"""
        # 加载自动主题设置
        auto_theme = self.settings.get("auto_theme", False)
        self.auto_theme_cb.setChecked(auto_theme)
        
        # 加载当前主题
        current_theme = self.settings.get("theme", "浅色")
        index = self.theme_combo.findText(current_theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
            
        # 更新控件状态
        self.on_auto_theme_changed()
        self.update_theme_description()
        
    def preview_theme(self):
        """预览主题"""
        try:
            from PyQt6.QtWidgets import QApplication
            selected_theme = self.theme_combo.currentText()
            apply_theme(QApplication.instance(), selected_theme)
        except Exception as e:
            logging.error(f"预览主题失败: {e}")
            
    def reset_settings(self):
        """重置设置"""
        self.auto_theme_cb.setChecked(False)
        self.theme_combo.setCurrentText("浅色")
        self.on_auto_theme_changed()
        self.update_theme_description()
        
    def save_settings(self):
        """保存设置"""
        try:
            # 保存自动主题设置
            auto_theme = self.auto_theme_cb.isChecked()
            self.settings["auto_theme"] = auto_theme
            
            # 保存主题选择
            if auto_theme:
                # 如果是自动主题，保存检测到的系统主题
                theme = self.detect_system_theme()
            else:
                # 否则保存用户选择的主题
                theme = self.theme_combo.currentText()
                
            self.settings["theme"] = theme
            
            # 保存到文件
            save_settings(self.settings)
            
            # 应用主题
            from PyQt6.QtWidgets import QApplication
            apply_theme(QApplication.instance(), theme)
            
            # 发送信号
            self.settings_changed.emit(self.settings)
            
            # 关闭对话框
            self.accept()
            
        except Exception as e:
            logging.error(f"保存主题设置失败: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "错误", f"保存设置失败: {str(e)}")
            
    def detect_system_theme(self):
        """检测系统主题"""
        system = platform.system()
        try:
            if system == "Windows":
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                    value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    return "浅色" if value == 1 else "深色"
                    
            elif system == "Darwin":  # macOS
                result = subprocess.run(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
                )
                return "深色" if result.stdout else "浅色"
                
        except Exception as e:
            logging.warning(f"检测系统主题失败: {e}")
            
        return "浅色"  # 默认返回浅色主题
    
    def connect_language_signal(self):
        """连接语言切换信号"""
        pass
    
    def refresh_ui_text(self):
        """刷新UI文本的国际化显示"""
        try:
            from core.i18n import t
            
            # 刷新窗口标题
            self.setWindowTitle(t('主题设置'))
            
            # 刷新组框标题
            auto_group = self.findChild(QGroupBox)
            if auto_group:
                auto_group.setTitle(t('auto_theme'))
            
            # 刷新复选框文本
            self.auto_theme_cb.setText(t('follow_system_theme'))
            
            # 刷新按钮文本
            self.preview_btn.setText(t('preview'))
            self.reset_btn.setText(t('reset'))
            self.cancel_btn.setText(t('cancel'))
            self.ok_btn.setText(t('ok'))
            
        except Exception as e:
            import logging
            logging.error(f"刷新ThemePanel UI文本时出错: {e}")
    
    def clear_layout(self, layout):
        """清除布局中的所有控件"""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_layout(child.layout())