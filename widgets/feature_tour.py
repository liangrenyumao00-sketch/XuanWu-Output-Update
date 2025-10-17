# feature_tour.py
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QGroupBox, QScrollArea, QWidget, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from core.group_framework_styles import apply_group_framework_style, setup_group_framework_layout, get_style_manager

class FeatureTour(QDialog):
    """功能导览窗口"""
    tour_completed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("功能导览 - 炫舞OCR")
        self.resize(900, 700)
        self.setMinimumSize(800, 600)
        
        # 应用统一分组样式
        self.apply_theme_styles()
        
        # 创建界面
        self.create_layout()

    def _make_rich_label(self, html: str) -> QLabel:
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setText(html)
        # 根据当前主题设置文本颜色，避免深色主题下不可见
        try:
            style_manager = get_style_manager()
            if style_manager.is_dark_theme():
                label.setStyleSheet("QLabel { font-size: 14px; color: #f1f1f1; }")
            else:
                label.setStyleSheet("QLabel { font-size: 14px; color: #374151; }")
        except Exception:
            # 回退：不设置颜色，使用默认调色板
            label.setStyleSheet("QLabel { font-size: 14px; }")
        return label
    
    def create_layout(self):
        """创建界面布局"""
        main_layout = QVBoxLayout(self)
        # 使用统一布局属性
        setup_group_framework_layout(main_layout)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("🎯 功能导览")
        title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 滚动区域（全局滚动，不在组内滚动）
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(5, 5, 5, 5)
        
        # 欢迎信息
        welcome_group = self.create_welcome_group()
        content_layout.addWidget(welcome_group)
        
        # 主要功能
        main_features_group = self.create_main_features_group()
        content_layout.addWidget(main_features_group)
        
        # 高级功能
        advanced_features_group = self.create_advanced_features_group()
        content_layout.addWidget(advanced_features_group)
        
        # 个性化设置
        settings_group = self.create_settings_group()
        content_layout.addWidget(settings_group)
        
        # 快速开始
        quick_start_group = self.create_quick_start_group()
        content_layout.addWidget(quick_start_group)
        
        # 快速操作按钮组
        quick_actions_group = QGroupBox("🧭 快速操作")
        qa_layout = QVBoxLayout(quick_actions_group)
        
        btns_layout_1 = QHBoxLayout()
        api_btn = QPushButton("配置 API 密钥")
        region_btn = QPushButton("选择识别区域")
        history_btn = QPushButton("打开历史记录")
        shortcuts_btn = QPushButton("查看快捷键")
        for b in [api_btn, region_btn, history_btn, shortcuts_btn]:
            b.setMinimumHeight(32)
            btns_layout_1.addWidget(b)
        qa_layout.addLayout(btns_layout_1)
        
        btns_layout_2 = QHBoxLayout()
        settings_btn = QPushButton("统一设置面板")
        logs_btn = QPushButton("日志管理")
        for b in [settings_btn, logs_btn]:
            b.setMinimumHeight(32)
            btns_layout_2.addWidget(b)
        qa_layout.addLayout(btns_layout_2)
        
        # 绑定事件到主窗口方法（如存在）
        try:
            if self.main_window is not None:
                api_btn.clicked.connect(lambda: getattr(self.main_window, 'open_apikey_dialog', lambda: None)())
                region_btn.clicked.connect(lambda: getattr(self.main_window, 'open_region_selector', lambda: None)())
                history_btn.clicked.connect(lambda: getattr(self.main_window, 'open_history_dialog', lambda: None)())
                shortcuts_btn.clicked.connect(lambda: getattr(self.main_window, 'show_shortcuts_window', lambda: None)())
                settings_btn.clicked.connect(lambda: getattr(self.main_window, 'open_setting_dialog', lambda _: None)('unified_settings'))
                logs_btn.clicked.connect(lambda: getattr(self.main_window, 'open_log_management_dialog', lambda: None)())
        except Exception:
            pass
        
        content_layout.addWidget(quick_actions_group)
        
        content_layout.addStretch()
        
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        # 不再显示选项
        self.dont_show_again = QCheckBox("不再显示此导览")
        button_layout.addWidget(self.dont_show_again)
        
        button_layout.addStretch()
        
        # 关闭按钮
        close_button = QPushButton("开始使用")
        close_button.clicked.connect(self.complete_tour)
        close_button.setMinimumSize(120, 35)
        button_layout.addWidget(close_button)
        
        main_layout.addLayout(button_layout)
    
    def create_welcome_group(self):
        """创建欢迎信息组"""
        group = QGroupBox("🎉 欢迎使用炫舞OCR")
        layout = QVBoxLayout(group)
        
        welcome_label = self._make_rich_label(
            """
            <div>
                <p>欢迎使用<b>炫舞OCR</b>！这是一款功能强大的文字识别工具，
                可帮助您快速识别屏幕上的文字内容，并进行智能关键词匹配。</p>
                <p>本导览将为您介绍主要功能，帮助您<b>快速上手</b>使用。</p>
            </div>
            """
        )
        layout.addWidget(welcome_label)
        
        return group
    
    def create_main_features_group(self):
        """创建主要功能组"""
        group = QGroupBox("🔍 主要功能")
        layout = QVBoxLayout(group)
        
        features_label = self._make_rich_label(
            """
            <div>
                <ul>
                    <li><b>OCR文字识别</b>
                        <ul>
                            <li>支持多种OCR引擎（百度、腾讯、阿里云等）</li>
                            <li>实时监控指定屏幕区域</li>
                            <li>高精度文字识别</li>
                        </ul>
                    </li>
                    <li><b>关键词匹配</b>
                        <ul>
                            <li>智能关键词检测</li>
                            <li>多种通知方式（桌面通知、声音提醒、邮件）</li>
                            <li>关键词分组管理</li>
                        </ul>
                    </li>
                    <li><b>数据分析</b>
                        <ul>
                            <li>实时统计信息</li>
                            <li>历史记录查看</li>
                            <li>数据导出功能</li>
                        </ul>
                    </li>
                </ul>
            </div>
            """
        )
        layout.addWidget(features_label)
        
        return group
    
    def create_advanced_features_group(self):
        """创建高级功能组"""
        group = QGroupBox("🔧 高级功能")
        layout = QVBoxLayout(group)
        
        advanced_label = self._make_rich_label(
            """
            <div>
                <ul>
                    <li><b>开发者工具</b>
                        <ul>
                            <li>详细日志查看</li>
                            <li>性能监控</li>
                            <li>API测试工具</li>
                        </ul>
                    </li>
                    <li><b>自动化功能</b>
                        <ul>
                            <li>定时任务</li>
                            <li>批量处理</li>
                            <li>脚本扩展</li>
                        </ul>
                    </li>
                </ul>
            </div>
            """
        )
        layout.addWidget(advanced_label)
        
        return group
    
    def create_settings_group(self):
        """创建个性化设置组"""
        group = QGroupBox("⚙️ 个性化设置")
        layout = QVBoxLayout(group)
        
        settings_label = self._make_rich_label(
            """
            <div>
                <ul>
                    <li>界面主题：支持浅色和深色主题</li>
                    <li>快捷键：自定义快捷键组合</li>
                    <li>通知设置：配置各种提醒方式</li>
                    <li>数据管理：设置数据保存和清理策略</li>
                </ul>
            </div>
            """
        )
        layout.addWidget(settings_label)
        
        return group
    
    def create_quick_start_group(self):
        """创建快速开始组"""
        group = QGroupBox("🚀 快速开始")
        layout = QVBoxLayout(group)
        
        quick_start_label = self._make_rich_label(
            """
            <div>
                <p>开始使用炫舞OCR的简单步骤：</p>
                <ol>
                    <li>配置OCR API密钥（设置 → OCR配置）</li>
                    <li>选择识别区域（点击“区域选择”按钮）</li>
                    <li>添加关键词（在关键词面板中添加）</li>
                    <li>点击“开始”按钮开始监控</li>
                </ol>
                <p>如需帮助，请查看帮助菜单或联系技术支持。</p>
            </div>
            """
        )
        layout.addWidget(quick_start_label)
        
        return group
    
    def complete_tour(self):
        """完成导览"""
        self.save_tour_preference()
        self.tour_completed.emit()
        self.close()
    
    def save_tour_preference(self):
        """保存导览偏好设置"""
        if self.dont_show_again.isChecked():
            try:
                import json
                settings_file = "settings.json"
                
                # 读取现有设置
                settings = {}
                if os.path.exists(settings_file):
                    with open(settings_file, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                
                # 更新设置
                settings['show_feature_tour'] = False
                
                # 保存设置
                with open(settings_file, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, ensure_ascii=False, indent=2)
                    
            except Exception as e:
                print(f"保存设置失败: {e}")
    
    @staticmethod
    def should_show_tour():
        """检查是否应该显示导览"""
        try:
            import json
            settings_file = "settings.json"
            
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                return settings.get('show_feature_tour', True)
            
            return True  # 默认显示
        except:
            return True
    
    def apply_theme_styles(self):
        """应用统一分组框架样式（兼容主题）"""
        try:
            apply_group_framework_style(self)
        except Exception:
            # 如果统一样式应用失败，保持原样
            pass


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    tour = FeatureTour()
    tour.show()
    sys.exit(app.exec())