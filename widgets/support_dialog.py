# support_dialog.py
import os
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QGroupBox, QScrollArea, QWidget, QFormLayout,
    QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QDesktopServices
from PyQt6.QtCore import QUrl
from core.group_framework_styles import apply_group_framework_style, setup_group_framework_layout

class SupportDialog(QDialog):
    """官方支持信息对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("官方支持 - 炫舞OCR")
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
        
        # 联系方式组
        contact_group = QGroupBox("📞 联系方式")
        contact_layout = QFormLayout(contact_group)
        
        contact_info = QTextEdit()
        contact_info.setMaximumHeight(120)
        contact_info.setReadOnly(True)
        contact_info.setHtml("""
        <p><b>📧 官方邮箱：</b> support@xuanwu-ocr.com</p>
        <p><b>🌐 官方网站：</b> https://xuanwu-ocr.com</p>
        <p><b>📱 QQ交流群：</b> 123456789</p>
        <p><b>💬 微信群：</b> 扫描官网二维码加入</p>
        <p><b>📞 技术热线：</b> 400-123-4567 (工作日 9:00-18:00)</p>
        """)
        contact_layout.addRow(contact_info)
        
        # 在线资源组
        resources_group = QGroupBox("🌐 在线资源")
        resources_layout = QFormLayout(resources_group)
        
        resources_info = QTextEdit()
        resources_info.setMaximumHeight(100)
        resources_info.setReadOnly(True)
        resources_info.setHtml("""
        <p><b>📖 用户手册：</b> https://docs.xuanwu-ocr.com</p>
        <p><b>🎥 视频教程：</b> https://video.xuanwu-ocr.com</p>
        <p><b>💡 常见问题：</b> https://faq.xuanwu-ocr.com</p>
        <p><b>🔧 API文档：</b> https://api.xuanwu-ocr.com</p>
        """)
        resources_layout.addRow(resources_info)
        
        # 常见问题组
        faq_group = QGroupBox("❓ 常见问题")
        faq_layout = QFormLayout(faq_group)
        
        faq_info = QTextEdit()
        faq_info.setMaximumHeight(150)
        faq_info.setReadOnly(True)
        faq_info.setHtml("""
        <p><b>Q: OCR识别不准确怎么办？</b></p>
        <p>A: 请确保图像清晰，文字对比度高，可尝试调整OCR引擎设置。</p>
        
        <p><b>Q: 如何添加自定义关键词？</b></p>
        <p>A: 在关键词面板中点击"添加"按钮，输入关键词即可。</p>
        
        <p><b>Q: 软件运行缓慢怎么办？</b></p>
        <p>A: 检查系统资源占用，关闭不必要的程序，或联系技术支持。</p>
        """)
        faq_layout.addRow(faq_info)
        
        # 反馈建议组
        feedback_group = QGroupBox("💬 反馈建议")
        feedback_layout = QFormLayout(feedback_group)
        
        feedback_info = QTextEdit()
        feedback_info.setMaximumHeight(100)
        feedback_info.setReadOnly(True)
        feedback_info.setHtml("""
        <p><b>🐛 Bug反馈：</b> bug@xuanwu-ocr.com</p>
        <p><b>💡 功能建议：</b> feature@xuanwu-ocr.com</p>
        <p><b>⭐ 用户评价：</b> review@xuanwu-ocr.com</p>
        <p><b>📝 使用体验：</b> feedback@xuanwu-ocr.com</p>
        """)
        feedback_layout.addRow(feedback_info)
        
        # 技术支持组
        tech_group = QGroupBox("🔧 技术支持")
        tech_layout = QFormLayout(tech_group)
        
        tech_info = QTextEdit()
        tech_info.setMaximumHeight(120)
        tech_info.setReadOnly(True)
        tech_info.setHtml("""
        <p><b>🕐 支持时间：</b> 工作日 9:00-18:00</p>
        <p><b>⚡ 响应时间：</b> 一般问题24小时内回复</p>
        <p><b>🚨 紧急问题：</b> 2小时内回复</p>
        <p><b>📋 远程协助：</b> 提供TeamViewer远程支持</p>
        <p><b>🎓 培训服务：</b> 提供企业用户培训服务</p>
        """)
        tech_layout.addRow(tech_info)
        
        # 添加所有组到内容布局
        content_layout.addWidget(contact_group)
        content_layout.addWidget(resources_group)
        content_layout.addWidget(faq_group)
        content_layout.addWidget(feedback_group)
        content_layout.addWidget(tech_group)
        content_layout.addStretch()
        
        # 设置滚动区域内容
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        # 访问官网按钮
        website_button = QPushButton("🌐 访问官网")
        website_button.clicked.connect(self.open_website)
        website_button.setDefault(False)  # 禁用默认按钮行为
        website_button.setAutoDefault(False)  # 禁用自动默认按钮行为
        button_layout.addWidget(website_button)
        
        button_layout.addStretch()
        
        # 关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.close)
        close_button.setDefault(False)  # 禁用默认按钮行为
        close_button.setAutoDefault(False)  # 禁用自动默认按钮行为
        button_layout.addWidget(close_button)
        
        main_layout.addLayout(button_layout)
    
    def open_website(self):
        """打开官网"""
        try:
            QDesktopServices.openUrl(QUrl("https://xuanwu-ocr.com"))
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开官网：{e}")