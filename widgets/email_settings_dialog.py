# widgets/email_settings_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QSpinBox, QCheckBox, QPushButton, QLabel, 
    QTextEdit, QListWidget, QMessageBox, QProgressBar, QComboBox,
    QSlider, QColorDialog, QFrame, QTabWidget, QWidget, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from core.email_notifier import EmailNotifier

import logging

class EmailTestThread(QThread):
    """邮件测试线程"""
    test_completed = pyqtSignal(bool, str)
    
    def __init__(self, notifier, config):
        super().__init__()
        self.notifier = notifier
        self.config = config
        
    def run(self):
        success, message = self.notifier.test_email_config(self.config)
        self.test_completed.emit(success, message)

class EmailSettingsDialog(QDialog):
    """邮件设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("邮件通知设置")
        self.setMinimumSize(650, 600)
        self.resize(650, 800)
        self.setModal(True)
        
        self.notifier = EmailNotifier()
        self.test_thread = None
        
        # 应用主题样式
        self.apply_theme_styles()
        
        self.init_ui()
        self.load_settings()
        
        # 窗口居中显示
        if parent:
            self.move(parent.geometry().center() - self.rect().center())
        
    def init_ui(self):
        """初始化界面"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        # 创建滚动内容容器
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        scroll_layout.setSpacing(15)
        
        # 启用邮件通知
        self.enable_checkbox = QCheckBox("启用邮件通知")
        self.enable_checkbox.stateChanged.connect(self.on_enable_changed)
        scroll_layout.addWidget(self.enable_checkbox)
        
        # SMTP服务器设置
        smtp_group = QGroupBox("SMTP服务器设置")
        smtp_layout = QFormLayout(smtp_group)
        # 设置表单布局策略，防止输入框变形
        smtp_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        smtp_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        smtp_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        smtp_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.smtp_server_edit = QLineEdit()
        self.smtp_server_edit.setPlaceholderText("例如: smtp.qq.com")
        smtp_layout.addRow("SMTP服务器:", self.smtp_server_edit)
        
        self.smtp_port_spin = QSpinBox()
        self.smtp_port_spin.setRange(1, 65535)
        self.smtp_port_spin.setValue(465)
        smtp_layout.addRow("端口:", self.smtp_port_spin)
        
        # 加密方式选择
        encryption_layout = QHBoxLayout()
        self.use_tls_checkbox = QCheckBox("TLS (端口587)")
        self.use_ssl_checkbox = QCheckBox("SSL (端口465) 推荐")
        self.use_ssl_checkbox.setChecked(True)
        
        # 互斥选择
        def on_tls_changed(checked):
            if checked:
                self.use_ssl_checkbox.setChecked(False)
                self.smtp_port_spin.setValue(587)
        
        def on_ssl_changed(checked):
            if checked:
                self.use_tls_checkbox.setChecked(False)
                self.smtp_port_spin.setValue(465)
        
        self.use_tls_checkbox.toggled.connect(on_tls_changed)
        self.use_ssl_checkbox.toggled.connect(on_ssl_changed)
        
        encryption_layout.addWidget(self.use_tls_checkbox)
        encryption_layout.addWidget(self.use_ssl_checkbox)
        encryption_layout.addStretch()
        smtp_layout.addRow("加密方式:", encryption_layout)
        
        # 连接超时设置
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 120)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(" 秒")
        smtp_layout.addRow("连接超时:", self.timeout_spin)
        
        scroll_layout.addWidget(smtp_group)
        
        # 邮箱账号设置
        account_group = QGroupBox("邮箱账号设置")
        account_layout = QFormLayout(account_group)
        # 设置表单布局策略，防止输入框变形
        account_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        account_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        account_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        account_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.sender_email_edit = QLineEdit()
        self.sender_email_edit.setPlaceholderText("发送方邮箱地址")
        account_layout.addRow("发送邮箱:", self.sender_email_edit)
        
        self.sender_password_edit = QLineEdit()
        self.sender_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.sender_password_edit.setPlaceholderText("邮箱密码或授权码")
        account_layout.addRow("邮箱密码:", self.sender_password_edit)
        
        self.recipient_email_edit = QLineEdit()
        self.recipient_email_edit.setPlaceholderText("接收方邮箱地址")
        account_layout.addRow("接收邮箱:", self.recipient_email_edit)
        
        scroll_layout.addWidget(account_group)
        
        # 通知设置
        notification_group = QGroupBox("通知设置")
        notification_layout = QVBoxLayout(notification_group)
        
        # 冷却时间
        cooldown_layout = QHBoxLayout()
        cooldown_layout.addWidget(QLabel("通知冷却时间:"))
        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(60, 3600)  # 1分钟到1小时
        self.cooldown_spin.setValue(300)  # 默认5分钟
        self.cooldown_spin.setSuffix(" 秒")
        cooldown_layout.addWidget(self.cooldown_spin)
        cooldown_layout.addStretch()
        notification_layout.addLayout(cooldown_layout)
        
        # 特定关键词通知
        notification_layout.addWidget(QLabel("特定关键词通知 (留空表示所有关键词):"))
        
        keywords_layout = QHBoxLayout()
        self.keywords_list = QListWidget()
        self.keywords_list.setMaximumHeight(100)
        keywords_layout.addWidget(self.keywords_list)
        
        keywords_buttons_layout = QVBoxLayout()
        self.add_keyword_edit = QLineEdit()
        self.add_keyword_edit.setPlaceholderText("输入关键词")
        self.add_keyword_edit.returnPressed.connect(self.add_notification_keyword)
        keywords_buttons_layout.addWidget(self.add_keyword_edit)
        
        self.add_keyword_btn = QPushButton("添加")
        self.add_keyword_btn.setDefault(False)
        self.add_keyword_btn.setAutoDefault(False)
        self.add_keyword_btn.clicked.connect(self.add_notification_keyword)
        keywords_buttons_layout.addWidget(self.add_keyword_btn)
        
        self.remove_keyword_btn = QPushButton("删除")
        self.remove_keyword_btn.setDefault(False)
        self.remove_keyword_btn.setAutoDefault(False)
        self.remove_keyword_btn.clicked.connect(self.remove_notification_keyword)
        keywords_buttons_layout.addWidget(self.remove_keyword_btn)
        
        keywords_buttons_layout.addStretch()
        keywords_layout.addLayout(keywords_buttons_layout)
        
        notification_layout.addLayout(keywords_layout)
        scroll_layout.addWidget(notification_group)
        
        # 高级功能设置组 - 使用标签页
        advanced_group = QGroupBox("高级功能设置")
        advanced_main_layout = QVBoxLayout(advanced_group)
        
        # 创建标签页控件
        self.advanced_tabs = QTabWidget()
        
        # 1. 动态主题色彩标签页
        theme_tab = QWidget()
        theme_layout = QFormLayout(theme_tab)
        
        self.dynamic_theme_checkbox = QCheckBox("启用动态主题色彩")
        self.dynamic_theme_checkbox.setToolTip("根据关键词类型自动调整邮件配色方案")
        theme_layout.addRow(self.dynamic_theme_checkbox)
        
        # 主题配色方案选择
        self.theme_scheme_combo = QComboBox()
        self.theme_scheme_combo.addItems(["自动检测", "商务蓝", "警告橙", "紧急红", "成功绿", "优雅紫"])
        theme_layout.addRow("配色方案:", self.theme_scheme_combo)
        
        # 自定义主色调
        theme_color_layout = QHBoxLayout()
        self.theme_color_btn = QPushButton("选择主色调")
        self.theme_color_btn.setDefault(False)
        self.theme_color_btn.setAutoDefault(False)
        self.theme_color_btn.clicked.connect(self.select_theme_color)
        self.theme_color_preview = QLabel("#007bff")
        self.theme_color_preview.setStyleSheet("border: 1px solid #ccc; padding: 5px;")
        theme_color_layout.addWidget(self.theme_color_btn)
        theme_color_layout.addWidget(self.theme_color_preview)
        theme_layout.addRow("自定义主色调:", theme_color_layout)
        
        # 渐变强度
        self.gradient_intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self.gradient_intensity_slider.setRange(0, 100)
        self.gradient_intensity_slider.setValue(50)
        self.gradient_intensity_label = QLabel("50%")
        self.gradient_intensity_slider.valueChanged.connect(lambda v: self.gradient_intensity_label.setText(f"{v}%"))
        gradient_layout = QHBoxLayout()
        gradient_layout.addWidget(self.gradient_intensity_slider)
        gradient_layout.addWidget(self.gradient_intensity_label)
        theme_layout.addRow("渐变强度:", gradient_layout)
        
        self.advanced_tabs.addTab(theme_tab, "动态主题")
        
        # 2. AI智能摘要标签页
        summary_tab = QWidget()
        summary_layout = QFormLayout(summary_tab)
        
        self.ai_summary_checkbox = QCheckBox("启用AI智能摘要")
        self.ai_summary_checkbox.setToolTip("自动生成OCR内容的关键信息摘要")
        summary_layout.addRow(self.ai_summary_checkbox)
        
        # 摘要长度控制
        self.summary_length_combo = QComboBox()
        self.summary_length_combo.addItems(["简短(50字)", "中等(100字)", "详细(200字)", "完整(300字)"])
        self.summary_length_combo.setCurrentIndex(1)
        summary_layout.addRow("摘要长度:", self.summary_length_combo)
        
        # 摘要风格
        self.summary_style_combo = QComboBox()
        self.summary_style_combo.addItems(["正式商务", "简洁明了", "详细分析", "要点列表"])
        summary_layout.addRow("摘要风格:", self.summary_style_combo)
        
        # 关键词突出显示
        self.highlight_keywords_checkbox = QCheckBox("突出显示关键词")
        self.highlight_keywords_checkbox.setChecked(True)
        summary_layout.addRow(self.highlight_keywords_checkbox)
        
        self.advanced_tabs.addTab(summary_tab, "AI摘要")
        
        # 3. 数据可视化标签页
        chart_tab = QWidget()
        chart_layout = QFormLayout(chart_tab)
        
        self.data_visualization_checkbox = QCheckBox("启用数据可视化图表")
        self.data_visualization_checkbox.setToolTip("显示关键词匹配趋势和统计信息")
        chart_layout.addRow(self.data_visualization_checkbox)
        
        # 图表类型选择
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["柱状图", "饼图", "折线图", "雷达图", "组合图表"])
        chart_layout.addRow("图表类型:", self.chart_type_combo)
        
        # 数据时间范围
        self.data_range_combo = QComboBox()
        self.data_range_combo.addItems(["最近7天", "最近30天", "最近90天", "全部数据"])
        self.data_range_combo.setCurrentIndex(1)
        chart_layout.addRow("数据范围:", self.data_range_combo)
        
        # 图表尺寸
        self.chart_size_combo = QComboBox()
        self.chart_size_combo.addItems(["小(300x200)", "中(500x300)", "大(700x400)", "超大(900x500)"])
        self.chart_size_combo.setCurrentIndex(1)
        chart_layout.addRow("图表尺寸:", self.chart_size_combo)
        
        # 显示数据标签
        self.show_data_labels_checkbox = QCheckBox("显示数据标签")
        self.show_data_labels_checkbox.setChecked(True)
        chart_layout.addRow(self.show_data_labels_checkbox)
        
        self.advanced_tabs.addTab(chart_tab, "数据图表")
        
        # 4. 多语言支持标签页
        lang_tab = QWidget()
        lang_layout = QFormLayout(lang_tab)
        
        self.multilingual_checkbox = QCheckBox("启用多语言支持")
        self.multilingual_checkbox.setToolTip("根据用户设置自动切换邮件模板语言")
        lang_layout.addRow(self.multilingual_checkbox)
        
        # 默认语言选择
        self.default_language_combo = QComboBox()
        self.default_language_combo.addItems(["中文(简体)", "English", "日本語", "한국어", "Français", "Deutsch"])
        lang_layout.addRow("默认语言:", self.default_language_combo)
        
        # 自动检测语言
        self.auto_detect_language_checkbox = QCheckBox("自动检测OCR内容语言")
        self.auto_detect_language_checkbox.setChecked(True)
        lang_layout.addRow(self.auto_detect_language_checkbox)
        
        # 翻译服务
        self.translation_service_combo = QComboBox()
        self.translation_service_combo.addItems(["内置词典", "百度翻译", "谷歌翻译", "有道翻译"])
        lang_layout.addRow("翻译服务:", self.translation_service_combo)
        
        self.advanced_tabs.addTab(lang_tab, "多语言")
        
        # 5. 交互式元素标签页
        interactive_tab = QWidget()
        interactive_layout = QFormLayout(interactive_tab)
        
        self.interactive_elements_checkbox = QCheckBox("启用交互式元素")
        self.interactive_elements_checkbox.setToolTip("添加一键操作按钮、快速回复链接等")
        interactive_layout.addRow(self.interactive_elements_checkbox)
        
        # 按钮样式
        self.button_style_combo = QComboBox()
        self.button_style_combo.addItems(["现代扁平", "经典立体", "圆角卡片", "简约线条"])
        interactive_layout.addRow("按钮样式:", self.button_style_combo)
        
        # 交互功能选择
        self.quick_reply_checkbox = QCheckBox("快速回复按钮")
        self.quick_reply_checkbox.setChecked(True)
        interactive_layout.addRow(self.quick_reply_checkbox)
        
        self.action_buttons_checkbox = QCheckBox("一键操作按钮")
        self.action_buttons_checkbox.setChecked(True)
        interactive_layout.addRow(self.action_buttons_checkbox)
        
        self.feedback_buttons_checkbox = QCheckBox("反馈评价按钮")
        self.feedback_buttons_checkbox.setChecked(False)
        interactive_layout.addRow(self.feedback_buttons_checkbox)
        
        # 按钮颜色
        button_color_layout = QHBoxLayout()
        self.button_color_btn = QPushButton("选择按钮颜色")
        self.button_color_btn.setDefault(False)
        self.button_color_btn.setAutoDefault(False)
        self.button_color_btn.clicked.connect(self.select_button_color)
        self.button_color_preview = QLabel("#28a745")
        self.button_color_preview.setStyleSheet("border: 1px solid #ccc; padding: 5px;")
        button_color_layout.addWidget(self.button_color_btn)
        button_color_layout.addWidget(self.button_color_preview)
        interactive_layout.addRow("按钮颜色:", button_color_layout)
        
        self.advanced_tabs.addTab(interactive_tab, "交互元素")
        
        # 6. 模板个性化标签页
        template_tab = QWidget()
        template_layout = QFormLayout(template_tab)
        
        self.template_personalization_checkbox = QCheckBox("启用模板个性化定制")
        self.template_personalization_checkbox.setToolTip("允许用户自定义邮件样式和布局")
        template_layout.addRow(self.template_personalization_checkbox)
        
        # 字体系列
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(["系统默认", "微软雅黑", "宋体", "Arial", "Times New Roman", "Helvetica"])
        template_layout.addRow("字体系列:", self.font_family_combo)
        
        # 字体大小
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setRange(12, 24)
        self.font_size_slider.setValue(14)
        self.font_size_label = QLabel("14px")
        self.font_size_slider.valueChanged.connect(lambda v: self.font_size_label.setText(f"{v}px"))
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(self.font_size_slider)
        font_size_layout.addWidget(self.font_size_label)
        template_layout.addRow("字体大小:", font_size_layout)
        
        # 内容密度
        self.content_density_combo = QComboBox()
        self.content_density_combo.addItems(["紧凑", "正常", "宽松", "超宽松"])
        self.content_density_combo.setCurrentIndex(1)
        template_layout.addRow("内容密度:", self.content_density_combo)
        
        # 布局样式
        self.layout_style_combo = QComboBox()
        self.layout_style_combo.addItems(["现代卡片", "经典表格", "简约列表", "杂志风格"])
        template_layout.addRow("布局样式:", self.layout_style_combo)
        
        # 圆角半径
        self.border_radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.border_radius_slider.setRange(0, 20)
        self.border_radius_slider.setValue(8)
        self.border_radius_label = QLabel("8px")
        self.border_radius_slider.valueChanged.connect(lambda v: self.border_radius_label.setText(f"{v}px"))
        border_radius_layout = QHBoxLayout()
        border_radius_layout.addWidget(self.border_radius_slider)
        border_radius_layout.addWidget(self.border_radius_label)
        template_layout.addRow("圆角半径:", border_radius_layout)
        
        # 阴影效果
        self.shadow_enabled_checkbox = QCheckBox("启用阴影效果")
        self.shadow_enabled_checkbox.setChecked(True)
        template_layout.addRow(self.shadow_enabled_checkbox)
        
        self.advanced_tabs.addTab(template_tab, "模板定制")
        
        # 将标签页添加到主布局
        advanced_main_layout.addWidget(self.advanced_tabs)
        scroll_layout.addWidget(advanced_group)
        
        # 测试和帮助
        test_group = QGroupBox("测试和帮助")
        test_layout = QVBoxLayout(test_group)
        
        # 测试按钮和进度条
        test_button_layout = QHBoxLayout()
        self.test_btn = QPushButton("测试邮件配置")
        self.test_btn.setDefault(False)
        self.test_btn.setAutoDefault(False)
        self.test_btn.clicked.connect(self.test_email_config)
        test_button_layout.addWidget(self.test_btn)
        
        self.test_progress = QProgressBar()
        self.test_progress.setVisible(False)
        test_button_layout.addWidget(self.test_progress)
        
        test_layout.addLayout(test_button_layout)
        
        # 帮助信息
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setMaximumHeight(120)
        help_text.setHtml("""
        <b>使用说明:</b><br>
        1. <b>QQ邮箱:</b> SMTP服务器: smtp.qq.com, SSL端口: 465 (推荐) 或 TLS端口: 587, 密码使用授权码<br>
        2. <b>163邮箱:</b> SMTP服务器: smtp.163.com, SSL端口: 465/994 或 TLS端口: 25<br>
        3. <b>Gmail:</b> SMTP服务器: smtp.gmail.com, SSL端口: 465 或 TLS端口: 587<br>
        4. <b>连接方式:</b> SSL (推荐) 直接建立加密连接，更安全稳定；TLS先建立普通连接再升级<br>
        5. <b>连接超时:</b> 网络较慢时可适当增加超时时间 (10-120秒)<br>
        6. <b>通知冷却:</b> 防止频繁发送邮件，设置两次通知间的最小间隔<br>
        7. <b>特定关键词:</b> 只有匹配这些关键词时才发送通知，留空表示所有关键词都通知
        """)
        test_layout.addWidget(help_text)
        
        scroll_layout.addWidget(test_group)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
        # 按钮布局（在滚动区域外）
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        self.save_btn = QPushButton("保存")
        self.save_btn.setDefault(False)
        self.save_btn.setAutoDefault(False)
        self.save_btn.clicked.connect(self.save_settings)
        buttons_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setDefault(False)
        self.cancel_btn.setAutoDefault(False)
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(buttons_layout)
        
    def on_enable_changed(self, state):
        """启用状态改变"""
        enabled = state == Qt.CheckState.Checked.value
        
        # 启用/禁用配置控件（测试按钮始终可用）
        widgets = [
            self.smtp_server_edit, self.smtp_port_spin, self.use_tls_checkbox, self.use_ssl_checkbox, self.timeout_spin,
            self.sender_email_edit, self.sender_password_edit, self.recipient_email_edit,
            self.cooldown_spin, self.keywords_list, self.add_keyword_edit,
            self.add_keyword_btn, self.remove_keyword_btn
        ]
        
        for widget in widgets:
            widget.setEnabled(enabled)
            
        # 测试按钮始终可用，方便用户测试配置
        self.test_btn.setEnabled(True)
            
    def add_notification_keyword(self):
        """添加通知关键词"""
        keyword = self.add_keyword_edit.text().strip()
        if keyword:
            # 检查是否已存在
            for i in range(self.keywords_list.count()):
                if self.keywords_list.item(i).text() == keyword:
                    QMessageBox.information(self, "提示", "关键词已存在")
                    return
            
            self.keywords_list.addItem(keyword)
            self.add_keyword_edit.clear()
            
    def remove_notification_keyword(self):
        """删除通知关键词"""
        current_row = self.keywords_list.currentRow()
        if current_row >= 0:
            self.keywords_list.takeItem(current_row)
            
    def get_notification_keywords(self):
        """获取通知关键词列表"""
        keywords = []
        for i in range(self.keywords_list.count()):
            keywords.append(self.keywords_list.item(i).text())
        return keywords
        
    def set_notification_keywords(self, keywords):
        """设置通知关键词列表"""
        self.keywords_list.clear()
        for keyword in keywords:
            self.keywords_list.addItem(keyword)
            
    def get_config(self):
        """获取当前配置"""
        return {
            'email_notification_enabled': self.enable_checkbox.isChecked(),
            'smtp_server': self.smtp_server_edit.text().strip(),
            'smtp_port': self.smtp_port_spin.value(),
            'use_tls': self.use_tls_checkbox.isChecked(),
            'use_ssl': self.use_ssl_checkbox.isChecked(),
            'timeout': self.timeout_spin.value(),
            'sender_email': self.sender_email_edit.text().strip(),
            'sender_password': self.sender_password_edit.text(),
            'recipient_email': self.recipient_email_edit.text().strip(),
            'notification_cooldown': self.cooldown_spin.value(),
            'notification_keywords': self.get_notification_keywords(),
            # 高级功能设置
            'dynamic_theme_enabled': self.dynamic_theme_checkbox.isChecked(),
            'theme_scheme': self.theme_scheme_combo.currentText(),
            'theme_color': self.theme_color_preview.text(),
            'gradient_intensity': self.gradient_intensity_slider.value(),
            'ai_summary_enabled': self.ai_summary_checkbox.isChecked(),
            'summary_length': self.summary_length_combo.currentText(),
            'summary_style': self.summary_style_combo.currentText(),
            'highlight_keywords': self.highlight_keywords_checkbox.isChecked(),
            'data_visualization_enabled': self.data_visualization_checkbox.isChecked(),
            'chart_type': self.chart_type_combo.currentText(),
            'data_range': self.data_range_combo.currentText(),
            'chart_size': self.chart_size_combo.currentText(),
            'show_data_labels': self.show_data_labels_checkbox.isChecked(),
            'multilingual_enabled': self.multilingual_checkbox.isChecked(),
            'default_language': self.default_language_combo.currentText(),
            'auto_detect_language': self.auto_detect_language_checkbox.isChecked(),
            'translation_service': self.translation_service_combo.currentText(),
            'interactive_elements_enabled': self.interactive_elements_checkbox.isChecked(),
            'button_style': self.button_style_combo.currentText(),
            'quick_reply': self.quick_reply_checkbox.isChecked(),
            'action_buttons': self.action_buttons_checkbox.isChecked(),
            'feedback_buttons': self.feedback_buttons_checkbox.isChecked(),
            'button_color': self.button_color_preview.text(),
            'template_personalization_enabled': self.template_personalization_checkbox.isChecked(),
            'font_family': self.font_family_combo.currentText(),
            'font_size': self.font_size_slider.value(),
            'content_density': self.content_density_combo.currentText(),
            'layout_style': self.layout_style_combo.currentText(),
            'border_radius': self.border_radius_slider.value(),
            'shadow_enabled': self.shadow_enabled_checkbox.isChecked()
        }
        
    def load_settings(self):
        """加载设置"""
        config = self.notifier.get_email_config()
        
        self.enable_checkbox.setChecked(config.get('enabled', False))
        self.smtp_server_edit.setText(config.get('smtp_server', 'smtp.qq.com'))
        self.smtp_port_spin.setValue(config.get('smtp_port', 587))
        self.use_tls_checkbox.setChecked(config.get('use_tls', True))
        self.use_ssl_checkbox.setChecked(config.get('use_ssl', False))
        self.timeout_spin.setValue(config.get('timeout', 30))
        self.sender_email_edit.setText(config.get('sender_email', ''))
        self.sender_password_edit.setText(config.get('sender_password', ''))
        self.recipient_email_edit.setText(config.get('recipient_email', ''))
        self.cooldown_spin.setValue(config.get('notification_cooldown', 300))
        self.set_notification_keywords(config.get('notification_keywords', []))
        
        # 加载高级功能设置
        self.dynamic_theme_checkbox.setChecked(config.get('dynamic_theme_enabled', True))
        theme_scheme = config.get('theme_scheme', '自动检测')
        index = self.theme_scheme_combo.findText(theme_scheme)
        if index >= 0:
            self.theme_scheme_combo.setCurrentIndex(index)
        
        theme_color = config.get('theme_color', '#007bff')
        self.theme_color_preview.setText(theme_color)
        self.theme_color_preview.setStyleSheet("border: 1px solid #ccc; padding: 5px;")
        
        self.gradient_intensity_slider.setValue(config.get('gradient_intensity', 50))
        
        self.ai_summary_checkbox.setChecked(config.get('ai_summary_enabled', True))
        summary_length = config.get('summary_length', '中等(100字)')
        index = self.summary_length_combo.findText(summary_length)
        if index >= 0:
            self.summary_length_combo.setCurrentIndex(index)
        
        summary_style = config.get('summary_style', '简洁明了')
        index = self.summary_style_combo.findText(summary_style)
        if index >= 0:
            self.summary_style_combo.setCurrentIndex(index)
        
        self.highlight_keywords_checkbox.setChecked(config.get('highlight_keywords', True))
        
        self.data_visualization_checkbox.setChecked(config.get('data_visualization_enabled', True))
        chart_type = config.get('chart_type', '柱状图')
        index = self.chart_type_combo.findText(chart_type)
        if index >= 0:
            self.chart_type_combo.setCurrentIndex(index)
        
        data_range = config.get('data_range', '最近30天')
        index = self.data_range_combo.findText(data_range)
        if index >= 0:
            self.data_range_combo.setCurrentIndex(index)
        
        chart_size = config.get('chart_size', '中(500x300)')
        index = self.chart_size_combo.findText(chart_size)
        if index >= 0:
            self.chart_size_combo.setCurrentIndex(index)
        
        self.show_data_labels_checkbox.setChecked(config.get('show_data_labels', True))
        
        self.multilingual_checkbox.setChecked(config.get('multilingual_enabled', True))
        default_language = config.get('default_language', '中文(简体)')
        index = self.default_language_combo.findText(default_language)
        if index >= 0:
            self.default_language_combo.setCurrentIndex(index)
        
        self.auto_detect_language_checkbox.setChecked(config.get('auto_detect_language', True))
        
        translation_service = config.get('translation_service', '内置词典')
        index = self.translation_service_combo.findText(translation_service)
        if index >= 0:
            self.translation_service_combo.setCurrentIndex(index)
        
        self.interactive_elements_checkbox.setChecked(config.get('interactive_elements_enabled', True))
        button_style = config.get('button_style', '现代扁平')
        index = self.button_style_combo.findText(button_style)
        if index >= 0:
            self.button_style_combo.setCurrentIndex(index)
        
        self.quick_reply_checkbox.setChecked(config.get('quick_reply', True))
        self.action_buttons_checkbox.setChecked(config.get('action_buttons', True))
        self.feedback_buttons_checkbox.setChecked(config.get('feedback_buttons', False))
        
        button_color = config.get('button_color', '#28a745')
        self.button_color_preview.setText(button_color)
        self.button_color_preview.setStyleSheet("border: 1px solid #ccc; padding: 5px;")
        
        self.template_personalization_checkbox.setChecked(config.get('template_personalization_enabled', True))
        font_family = config.get('font_family', '系统默认')
        index = self.font_family_combo.findText(font_family)
        if index >= 0:
            self.font_family_combo.setCurrentIndex(index)
        
        self.font_size_slider.setValue(config.get('font_size', 14))
        
        content_density = config.get('content_density', '正常')
        index = self.content_density_combo.findText(content_density)
        if index >= 0:
            self.content_density_combo.setCurrentIndex(index)
        
        layout_style = config.get('layout_style', '现代卡片')
        index = self.layout_style_combo.findText(layout_style)
        if index >= 0:
            self.layout_style_combo.setCurrentIndex(index)
        
        self.border_radius_slider.setValue(config.get('border_radius', 8))
        self.shadow_enabled_checkbox.setChecked(config.get('shadow_enabled', True))
        
        # 触发启用状态改变
        self.on_enable_changed(self.enable_checkbox.checkState().value)
        
    def save_settings(self):
        """保存设置"""
        config = self.get_config()
        
        # 如果启用了邮件通知，验证必要字段
        if config['email_notification_enabled']:
            required_fields = {
                'smtp_server': 'SMTP服务器',
                'sender_email': '发送邮箱',
                'sender_password': '邮箱密码',
                'recipient_email': '接收邮箱'
            }
            
            for field, name in required_fields.items():
                if not config[field]:
                    QMessageBox.warning(self, "配置错误", f"请填写{name}")
                    return
        
        # 保存配置
        self.notifier.update_email_config(config)
        
        QMessageBox.information(self, "成功", "邮件设置已保存")
        self.accept()
        
    def select_theme_color(self):
        """选择主题颜色"""
        # 获取当前颜色作为初始颜色
        current_color = QColor(0, 123, 255)  # 默认蓝色
        if hasattr(self, 'theme_color_preview') and self.theme_color_preview.text():
            try:
                current_color = QColor(self.theme_color_preview.text())
            except:
                current_color = QColor(0, 123, 255)
        
        # 使用标准颜色选择对话框
        color = QColorDialog.getColor(current_color, self, "选择主题颜色")
        
        if color.isValid():
            color_hex = color.name()
            self.theme_color_preview.setText(color_hex)
            self.theme_color_preview.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #ccc; padding: 5px;")
    
    def select_button_color(self):
        """选择按钮颜色"""
        # 获取当前颜色作为初始颜色
        current_color = QColor(108, 117, 125)  # 默认灰色
        if hasattr(self, 'button_color_preview') and self.button_color_preview.text():
            try:
                current_color = QColor(self.button_color_preview.text())
            except:
                current_color = QColor(108, 117, 125)
        
        # 使用标准颜色选择对话框
        color = QColorDialog.getColor(current_color, self, "选择按钮颜色")
        
        if color.isValid():
            color_hex = color.name()
            self.button_color_preview.setText(color_hex)
            self.button_color_preview.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #ccc; padding: 5px;")
    
    def test_email_config(self):
        """测试邮件配置"""
        config = self.get_config()
        
        # 验证必要字段是否填写
        required_fields = {
            'smtp_server': 'SMTP服务器',
            'sender_email': '发送邮箱',
            'sender_password': '邮箱密码',
            'recipient_email': '接收邮箱'
        }
        
        for field, name in required_fields.items():
            if not config[field]:
                QMessageBox.warning(self, "配置错误", f"请填写{name}")
                return
            
        # 显示进度条
        self.test_progress.setVisible(True)
        self.test_progress.setRange(0, 0)  # 无限进度条
        self.test_btn.setEnabled(False)
        
        # 启动测试线程
        self.test_thread = EmailTestThread(self.notifier, config)
        self.test_thread.test_completed.connect(self.on_test_completed)
        self.test_thread.start()
        
    def on_test_completed(self, success, message):
        """测试完成"""
        # 隐藏进度条
        self.test_progress.setVisible(False)
        self.test_btn.setEnabled(True)
        
        # 显示结果
        if success:
            QMessageBox.information(self, "测试成功", message)
        else:
            QMessageBox.warning(self, "测试失败", message)
            
        # 清理线程
    
    def apply_theme_styles(self):
        """应用主题样式"""
        from main import MainWindow
        if hasattr(MainWindow, 'current_theme') and MainWindow.current_theme == 'dark':
            # 深色主题
            self.setStyleSheet("""
                QDialog {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QLabel {
                    color: #ffffff;
                }
                QLineEdit {
                    background-color: #404040;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 4px;
                    border-radius: 4px;
                    placeholder-text-color: #999999;
                }
                QTextEdit {
                    background-color: #404040;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QPushButton {
                    background-color: #404040;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #505050;
                }
                QGroupBox {
                    color: #ffffff;
                    border: 1px solid #555555;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    color: #ffffff;
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
                QCheckBox {
                    color: #ffffff;
                    spacing: 8px;
                }
                QSpinBox {
                    background-color: #404040;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QComboBox {
                    background-color: #404040;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QListWidget {
                    background-color: #404040;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QTabWidget::pane {
                    border: 1px solid #555555;
                    background-color: #2b2b2b;
                }
                QTabBar::tab {
                    background-color: #404040;
                    color: #ffffff;
                    padding: 8px 16px;
                    border: 1px solid #555555;
                }
                QTabBar::tab:selected {
                    background-color: #0078d4;
                }
                QScrollArea {
                    background-color: #2b2b2b;
                    border: none;
                }
            """)
        else:
            # 浅色主题
            self.setStyleSheet("")
        if self.test_thread:
            self.test_thread.deleteLater()
            self.test_thread = None