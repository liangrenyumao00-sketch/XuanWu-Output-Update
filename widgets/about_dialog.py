# about_dialog.py
import sys
import os
import platform
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QGroupBox, QScrollArea, QWidget, QFormLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from core.group_framework_styles import apply_group_framework_style, setup_group_framework_layout

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 炫舞OCR")
        self.resize(600, 500)
        self.setMinimumSize(500, 400)
        
        # 应用主题样式
        self.apply_theme_styles()
        
        # 创建界面
        self.setup_ui()
    
    def apply_theme_styles(self):
        """应用主题样式"""
        try:
            # 使用新的统一分组框架样式管理器
            apply_group_framework_style(self)
        except Exception as e:
            print(f"应用主题样式时出错: {e}")
    
    def setup_ui(self):
        """设置用户界面"""
        main_layout = QVBoxLayout(self)
        setup_group_framework_layout(main_layout)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 创建内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # 应用信息组
        app_group = QGroupBox("应用信息")
        app_layout = QFormLayout(app_group)
        
        app_info = QTextEdit()
        app_info.setMaximumHeight(120)
        app_info.setReadOnly(True)
        app_info.setHtml("""
        <h3>炫舞OCR v2.1.7</h3>
        <p><b>开发者：</b> 炫舞开发团队</p>
        <p><b>发布日期：</b> 2024年1月</p>
        <p><b>许可证：</b> MIT License</p>
        <p><b>描述：</b> 专业的OCR文字识别工具，支持多种语言识别和智能关键词匹配。</p>
        """)
        app_layout.addRow(app_info)
        
        # 系统信息组
        system_group = QGroupBox("系统信息")
        system_layout = QFormLayout(system_group)
        
        system_info = QTextEdit()
        system_info.setMaximumHeight(100)
        system_info.setReadOnly(True)
        system_info.setPlainText(f"""
操作系统: {platform.system()} {platform.release()}
Python版本: {sys.version.split()[0]}
架构: {platform.machine()}
处理器: {platform.processor()}
        """)
        system_layout.addRow(system_info)
        
        # 功能特性组
        features_group = QGroupBox("主要功能")
        features_layout = QFormLayout(features_group)
        
        features_info = QTextEdit()
        features_info.setMaximumHeight(150)
        features_info.setReadOnly(True)
        features_info.setHtml("""
        <ul>
        <li><b>智能OCR识别：</b> 支持多种语言的文字识别</li>
        <li><b>关键词匹配：</b> 自定义关键词实时监控</li>
        <li><b>屏幕截图：</b> 灵活的区域选择和截图功能</li>
        <li><b>数据分析：</b> 详细的识别统计和分析</li>
        <li><b>云端同步：</b> 配置和数据云端备份</li>
        <li><b>主题切换：</b> 支持明暗主题切换</li>
        </ul>
        """)
        features_layout.addRow(features_info)
        
        # 联系信息组
        contact_group = QGroupBox("联系我们")
        contact_layout = QFormLayout(contact_group)
        
        contact_info = QTextEdit()
        contact_info.setMaximumHeight(80)
        contact_info.setReadOnly(True)
        contact_info.setHtml("""
        <p><b>官方网站：</b> https://xuanwu-ocr.com</p>
        <p><b>技术支持：</b> support@xuanwu-ocr.com</p>
        <p><b>用户反馈：</b> feedback@xuanwu-ocr.com</p>
        """)
        contact_layout.addRow(contact_info)
        
        # 添加所有组到内容布局
        content_layout.addWidget(app_group)
        content_layout.addWidget(system_group)
        content_layout.addWidget(features_group)
        content_layout.addWidget(contact_group)
        content_layout.addStretch()
        
        # 设置滚动区域内容
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.close)
        close_button.setDefault(False)  # 禁用默认按钮行为
        close_button.setAutoDefault(False)  # 禁用自动默认按钮行为
        button_layout.addWidget(close_button)
        
        main_layout.addLayout(button_layout)
    
    def get_version_info(self):
        """获取版本信息"""
        try:
            version_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'version.txt')
            if os.path.exists(version_file):
                with open(version_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
        except Exception:
            pass
        return "2.1.7"
    
    def refresh_ui_text(self):
        """刷新UI文本的国际化显示"""
        try:
            from core.i18n import t
            
            # 刷新窗口标题
            self.setWindowTitle(t('about_dialog_title'))
            
            # 刷新组框标题
            for group_box in self.findChildren(QGroupBox):
                if '应用信息' in group_box.title() or 'Application Info' in group_box.title():
                    group_box.setTitle(t('application_info'))
                elif '系统信息' in group_box.title() or 'System Info' in group_box.title():
                    group_box.setTitle(t('system_info'))
                elif '功能特性' in group_box.title() or 'Features' in group_box.title():
                    group_box.setTitle(t('features'))
                elif '联系方式' in group_box.title() or 'Contact' in group_box.title():
                    group_box.setTitle(t('contact_info'))
            
            # 刷新按钮文本
            for button in self.findChildren(QPushButton):
                if button.text() == '关闭' or button.text() == 'Close':
                    button.setText(t('close'))
            
        except Exception as e:
            import logging
            logging.error(f"刷新AboutDialog UI文本时出错: {e}")