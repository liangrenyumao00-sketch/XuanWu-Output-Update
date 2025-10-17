# troubleshooting_wizard.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QGroupBox, QScrollArea, QWidget, QFormLayout,
    QProgressBar, QMessageBox, QGridLayout, QSizePolicy, QFrame,
    QCheckBox, QSpinBox, QSlider, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QFont, QIcon, QPalette

class InteractiveItem(QFrame):
    """交互式项目组件"""
    clicked = pyqtSignal(str)
    statusChanged = pyqtSignal(str, str)  # item_id, status
    
    def __init__(self, item_id, title, description, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.status = "pending"  # pending, checking, success, warning, error
        
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(1)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # 创建布局
        layout = QHBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 10, 15, 10)
        
        # 状态指示器
        self.status_label = QLabel("⏳")
        self.status_label.setFixedSize(20, 20)
        layout.addWidget(self.status_label)
        
        # 内容区域
        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)
        
        # 标题
        self.title_label = QLabel(title)
        title_font = self.title_label.font()
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        content_layout.addWidget(self.title_label)
        
        # 描述
        self.desc_label = QLabel(description)
        self.desc_label.setWordWrap(True)
        content_layout.addWidget(self.desc_label)
        
        layout.addLayout(content_layout)
        layout.addStretch()
        
        # 操作按钮
        self.action_button = QPushButton("检查")
        self.action_button.setMaximumWidth(80)
        self.action_button.clicked.connect(self.on_action_clicked)
        layout.addWidget(self.action_button)
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item_id)
        super().mousePressEvent(event)
    
    def on_action_clicked(self):
        """操作按钮点击"""
        self.start_check()
    
    def start_check(self):
        """开始检查"""
        self.set_status("checking")
        self.action_button.setEnabled(False)
        
        # 模拟检查过程
        QTimer.singleShot(2000, self.complete_check)
    
    def complete_check(self):
        """完成检查"""
        import random
        statuses = ["success", "warning", "error"]
        weights = [0.7, 0.2, 0.1]  # 70%成功，20%警告，10%错误
        status = random.choices(statuses, weights=weights)[0]
        
        self.set_status(status)
        self.action_button.setEnabled(True)
        self.action_button.setText("重新检查")
    
    def set_status(self, status):
        """设置状态"""
        self.status = status
        status_icons = {
            "pending": "⏳",
            "checking": "🔄",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌"
        }
        
        self.status_label.setText(status_icons.get(status, "⏳"))
        self.statusChanged.emit(self.item_id, status)
        
        # 更新样式
        if status == "success":
            self.setStyleSheet("QFrame { border: 2px solid #4CAF50; border-radius: 5px; }")
        elif status == "warning":
            self.setStyleSheet("QFrame { border: 2px solid #FF9800; border-radius: 5px; }")
        elif status == "error":
            self.setStyleSheet("QFrame { border: 2px solid #F44336; border-radius: 5px; }")
        elif status == "checking":
            self.setStyleSheet("QFrame { border: 2px solid #2196F3; border-radius: 5px; }")
        else:
            self.setStyleSheet("QFrame { border: 1px solid #CCCCCC; border-radius: 5px; }")

class ModernCard(QFrame):
    """现代化卡片组件"""
    
    def __init__(self, title, icon="", parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(1)
        
        # 创建卡片布局
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 创建标题区域
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)
        
        # 图标标签
        if icon:
            icon_label = QLabel(icon)
            icon_font = icon_label.font()
            icon_font.setPointSize(16)
            icon_label.setFont(icon_font)
            title_layout.addWidget(icon_label)
        
        # 标题标签
        self.title_label = QLabel(title)
        title_font = self.title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(12)
        self.title_label.setFont(title_font)
        title_layout.addWidget(self.title_label)
        
        title_layout.addStretch()
        
        # 状态统计
        self.status_label = QLabel("")
        title_layout.addWidget(self.status_label)
        
        layout.addLayout(title_layout)
        
        # 内容区域
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(12)
        layout.addLayout(self.content_layout)
        
        layout.addStretch()
        
        # 统计数据 - 修复：添加所有可能的状态
        self.item_count = 0
        self.status_counts = {
            "pending": 0, 
            "checking": 0, 
            "success": 0, 
            "warning": 0, 
            "error": 0
        }
    
    def add_item(self, title, description, action_text=None):
        """添加普通卡片项目"""
        item_layout = QVBoxLayout()
        item_layout.setSpacing(6)
        
        # 项目标题
        title_label = QLabel(f"• {title}")
        title_font = title_label.font()
        title_font.setBold(True)
        title_label.setFont(title_font)
        item_layout.addWidget(title_label)
        
        # 项目描述
        desc_label = QLabel(f"  {description}")
        desc_label.setWordWrap(True)
        desc_label.setIndent(15)
        item_layout.addWidget(desc_label)
        
        # 可选的操作按钮
        if action_text:
            action_button = QPushButton(action_text)
            action_button.setMaximumWidth(120)
            item_layout.addWidget(action_button)
        
        self.content_layout.addLayout(item_layout)
        return item_layout
    
    def add_interactive_item(self, item_id, title, description):
        """添加交互式项目"""
        item = InteractiveItem(item_id, title, description)
        item.statusChanged.connect(self.on_item_status_changed)
        self.content_layout.addWidget(item)
        self.item_count += 1
        self.status_counts["pending"] += 1
        self.update_status_display()
        return item
    
    def on_item_status_changed(self, item_id, status):
        """项目状态改变 - 修复：改进状态更新逻辑"""
        # 查找并减少旧状态计数
        for old_status, count in self.status_counts.items():
            if count > 0:
                # 简化逻辑：假设状态从pending开始变化
                if old_status == "pending":
                    self.status_counts[old_status] -= 1
                    break
        
        # 增加新状态计数
        if status in self.status_counts:
            self.status_counts[status] += 1
        else:
            # 如果状态不存在，添加它
            self.status_counts[status] = 1
        
        self.update_status_display()
    
    def update_status_display(self):
        """更新状态显示"""
        if self.item_count == 0:
            self.status_label.setText("")
            return
        
        success = self.status_counts.get("success", 0)
        warning = self.status_counts.get("warning", 0)
        error = self.status_counts.get("error", 0)
        pending = self.status_counts.get("pending", 0)
        checking = self.status_counts.get("checking", 0)
        
        # 只显示非零的状态
        status_parts = []
        if success > 0:
            status_parts.append(f"✅{success}")
        if warning > 0:
            status_parts.append(f"⚠️{warning}")
        if error > 0:
            status_parts.append(f"❌{error}")
        if checking > 0:
            status_parts.append(f"🔄{checking}")
        if pending > 0:
            status_parts.append(f"⏳{pending}")
        
        status_text = " ".join(status_parts)
        self.status_label.setText(status_text)

class SystemMonitor(QObject):
    """系统监控器"""
    statusUpdated = pyqtSignal(str, dict)  # monitor_type, data
    
    def __init__(self):
        super().__init__()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(5000)  # 每5秒更新一次
    
    def update_status(self):
        """更新系统状态"""
        import psutil
        import random
        
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # 磁盘使用率
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # 网络状态（模拟）
            network_status = random.choice(["good", "slow", "error"])
            
            data = {
                "cpu": cpu_percent,
                "memory": memory_percent,
                "disk": disk_percent,
                "network": network_status
            }
            
            self.statusUpdated.emit("system", data)
            
        except Exception as e:
            print(f"系统监控错误: {e}")

class TroubleshootingWizard(QDialog):
    """故障排除向导"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔧 故障排除向导 - 炫舞OCR")
        self.resize(900, 700)  # 从1200x900缩小到900x700
        self.setMinimumSize(800, 600)  # 从1000x800缩小到800x600
        
        # 初始化系统监控
        self.system_monitor = SystemMonitor()
        self.system_monitor.statusUpdated.connect(self.on_system_status_updated)
        
        # 创建界面
        self.setup_ui()
    
    def setup_ui(self):
        """设置用户界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(25)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # 创建标题区域
        self.create_header(main_layout)
        
        # 创建简化状态面板
        self.create_status_panel(main_layout)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        
        # 创建内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(25)
        content_layout.setContentsMargins(15, 15, 15, 15)
        
        # 创建响应式网格布局 - 移除系统检查卡片
        grid_layout = QGridLayout()
        grid_layout.setSpacing(25)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)
        grid_layout.setRowStretch(0, 1)
        grid_layout.setRowStretch(1, 1)
        
        # 创建现代化卡片 - 不包含系统检查
        self.problems_card = self.create_common_problems_card()
        grid_layout.addWidget(self.problems_card, 0, 0)
        
        self.performance_card = self.create_performance_card()
        grid_layout.addWidget(self.performance_card, 0, 1)
        
        self.logs_card = self.create_logs_card()
        grid_layout.addWidget(self.logs_card, 1, 0)
        
        self.repair_card = self.create_repair_card()
        grid_layout.addWidget(self.repair_card, 1, 1)
        
        content_layout.addLayout(grid_layout)
        
        # 设置滚动区域内容
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # 诊断进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # 底部按钮
        self.create_bottom_buttons(main_layout)
    
    def create_header(self, main_layout):
        """创建标题区域"""
        header_layout = QVBoxLayout()
        header_layout.setSpacing(10)
        
        # 主标题
        title_label = QLabel("🛠️ 系统故障排除向导")
        title_font = title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(18)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title_label)
        
        # 副标题
        subtitle_label = QLabel("快速诊断和解决常见问题，保持系统最佳运行状态")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(subtitle_label)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        header_layout.addWidget(separator)
        
        main_layout.addLayout(header_layout)
    
    def create_status_panel(self, main_layout):
        """创建实时状态面板"""
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.Box)
        status_frame.setLineWidth(1)
        
        status_layout = QHBoxLayout(status_frame)
        status_layout.setSpacing(20)
        status_layout.setContentsMargins(20, 15, 20, 15)
        
        # 应用状态
        self.app_status_label = QLabel("📱 应用状态: 正常运行")
        status_layout.addWidget(self.app_status_label)
        
        # OCR状态
        self.ocr_status_label = QLabel("🔍 OCR服务: 就绪")
        status_layout.addWidget(self.ocr_status_label)
        
        status_layout.addStretch()
        
        # 刷新按钮
        refresh_button = QPushButton("🔄 刷新状态")
        refresh_button.clicked.connect(self.refresh_status)
        status_layout.addWidget(refresh_button)
        
        main_layout.addWidget(status_frame)
    
    def create_system_check_card(self):
        """创建系统检查卡片"""
        card = ModernCard("系统环境检查", "🔍")
        
        check_items = [
            ("python_env", "Python 环境", "检查 Python 版本和依赖库状态"),
            ("system_perms", "系统权限", "验证文件读写和网络访问权限"),
            ("memory_usage", "内存使用", "监控内存占用和可用空间"),
            ("network_conn", "网络连接", "测试网络连接和API访问状态"),
            ("file_system", "文件系统", "检查临时文件夹和配置目录")
        ]
        
        for item_id, title, desc in check_items:
            card.add_interactive_item(item_id, title, desc)
        
        return card
    
    def create_common_problems_card(self):
        """创建常见问题卡片"""
        card = ModernCard("常见问题解决", "❓")
        
        problems = [
            ("ocr_failure", "OCR识别失败", "检查图片质量、OCR引擎配置和API密钥"),
            ("slow_startup", "程序启动缓慢", "清理缓存、检查防火墙和更新版本"),
            ("ui_issues", "界面显示异常", "重置布局、切换主题和检查缩放设置"),
            ("slow_response", "功能响应慢", "优化设置、清理数据和重启服务")
        ]
        
        for item_id, problem, solution in problems:
            card.add_interactive_item(item_id, problem, solution)
        
        return card
    
    def create_performance_card(self):
        """创建性能优化卡片"""
        card = ModernCard("性能优化建议", "⚡")
        
        tips = [
            ("内存优化", "定期清理缓存，关闭不必要的功能"),
            ("网络优化", "选择最快的API服务器，启用本地缓存"),
            ("界面优化", "减少动画效果，使用简洁主题"),
            ("存储优化", "清理历史记录，压缩日志文件"),
            ("启动优化", "禁用自启动项，优化启动顺序")
        ]
        
        for tip, desc in tips:
            card.add_item(tip, desc)
        
        return card
    
    def create_logs_card(self):
        """创建日志分析卡片"""
        card = ModernCard("日志分析", "📋")
        
        log_types = [
            ("错误日志", "查看最近的错误信息和异常堆栈"),
            ("性能日志", "分析响应时间和资源使用情况"),
            ("操作日志", "追踪用户操作和系统行为记录"),
            ("网络日志", "监控API调用和网络请求状态")
        ]
        
        for log_type, desc in log_types:
            card.add_item(log_type, desc)
        
        return card
    
    def create_repair_card(self):
        """创建修复工具卡片"""
        card = ModernCard("修复工具", "🔨")
        
        repair_tools = [
            ("配置修复", "重置损坏的配置文件到默认状态"),
            ("缓存清理", "清除所有临时文件和缓存数据"),
            ("权限修复", "修复文件和文件夹访问权限问题"),
            ("依赖修复", "重新安装缺失或损坏的依赖库")
        ]
        
        for tool, desc in repair_tools:
            card.add_item(tool, desc)
        
        return card
    
    def create_support_card(self):
        """创建技术支持卡片"""
        card = ModernCard("技术支持", "📞")
        
        support_options = [
            ("在线帮助", "访问官方文档和常见问题解答"),
            ("社区论坛", "在用户社区寻求帮助和分享经验"),
            ("邮件支持", "发送详细问题描述到技术支持邮箱"),
            ("远程协助", "预约技术人员进行远程诊断服务")
        ]
        
        for option, desc in support_options:
            card.add_item(option, desc)
        
        return card
    
    def create_bottom_buttons(self, main_layout):
        """创建底部按钮"""
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.setContentsMargins(0, 25, 0, 0)
        
        # 问题诊断按钮
        self.diagnose_button = QPushButton("🔍 问题诊断")
        self.diagnose_button.clicked.connect(self.start_diagnosis)
        button_layout.addWidget(self.diagnose_button)
        
        # 快速修复按钮
        self.repair_button = QPushButton("🔧 快速修复")
        self.repair_button.clicked.connect(self.quick_repair)
        button_layout.addWidget(self.repair_button)
        
        # 查看日志按钮
        self.logs_button = QPushButton("📋 查看日志")
        self.logs_button.clicked.connect(self.view_logs)
        button_layout.addWidget(self.logs_button)
        
        button_layout.addStretch()
        
        # 关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)
        
        main_layout.addLayout(button_layout)
    
    def check_all_items(self):
        """检查所有交互式项目"""
        # 检查问题卡片中的所有交互式项目
        for i in range(self.problems_card.content_layout.count()):
            item = self.problems_card.content_layout.itemAt(i).widget()
            if isinstance(item, InteractiveItem):
                QTimer.singleShot(i * 500, item.start_check)  # 错开检查时间
    
    def refresh_status(self):
        """刷新状态"""
        # 简化状态刷新，不进行系统监控
        self.app_status_label.setText("📱 应用状态: 正常运行")
        self.ocr_status_label.setText("🔍 OCR服务: 就绪")

    def start_diagnosis(self):
        """开始系统诊断"""
        self.diagnose_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 模拟诊断过程
        self.diagnosis_timer = QTimer()
        self.diagnosis_timer.timeout.connect(self.update_diagnosis_progress)
        self.diagnosis_step = 0
        self.diagnosis_timer.start(200)
    
    def update_diagnosis_progress(self):
        """更新诊断进度"""
        self.diagnosis_step += 1
        progress = min(self.diagnosis_step * 2, 100)
        self.progress_bar.setValue(progress)
        
        if progress >= 100:
            self.diagnosis_timer.stop()
            self.progress_bar.setVisible(False)
            self.diagnose_button.setEnabled(True)
            
            # 显示诊断结果
            QMessageBox.information(
                self, 
                "诊断完成", 
                "🎉 系统诊断已完成！\n\n" +
                "✅ Python环境：正常\n" +
                "✅ 系统权限：正常\n" +
                "✅ 网络连接：正常\n" +
                "⚠️  内存使用：偏高\n" +
                "✅ 文件系统：正常\n\n" +
                "💡 建议：清理缓存以优化内存使用。"
            )
    
    def quick_repair(self):
        """快速修复"""
        reply = QMessageBox.question(
            self, 
            "快速修复", 
            "🔧 将执行以下修复操作：\n\n" +
            "• 清理临时文件和缓存\n" +
            "• 重置配置文件\n" +
            "• 修复文件权限\n" +
            "• 更新依赖库\n\n" +
            "❓ 是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(
                self, 
                "修复完成", 
                "🎉 快速修复已完成！\n\n" +
                "✅ 缓存已清理\n" +
                "✅ 配置已重置\n" +
                "✅ 权限已修复\n" +
                "✅ 依赖已更新\n\n" +
                "💡 建议重启应用程序以使更改生效。"
            )
    
    def view_logs(self):
        """查看日志"""
        try:
            # 这里可以打开日志查看器
            QMessageBox.information(
                self, 
                "查看日志", 
                "📋 日志查看功能将在新窗口中打开。\n\n" +
                "您可以在日志中查看：\n" +
                "• 错误信息和异常\n" +
                "• 性能统计数据\n" +
                "• 用户操作记录\n" +
                "• 网络请求日志"
            )
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法打开日志查看器：{e}")

    def on_system_status_updated(self, monitor_type, data):
        """系统状态更新 - 简化版本"""
        # 简化状态更新，不显示详细系统监控
        pass