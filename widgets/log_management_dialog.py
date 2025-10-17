# widgets/log_management_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QPushButton, QComboBox, QCheckBox, 
    QGroupBox, QGridLayout, QSpinBox, QPlainTextEdit,
    QMessageBox, QTabWidget, QLineEdit, QDateEdit,
    QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QTextEdit, QSplitter,
    QFrame, QScrollArea, QToolBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer, QDate
from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QTextCursor, QTextDocument
import json
import os
import re
import csv
from datetime import datetime, timedelta
from core.enhanced_logger import get_enhanced_logger
from core.log_config_manager import get_log_config_manager, LogLevel
from core.i18n import t
from core.settings import load_settings, save_settings
from core.desktop_notifier import DesktopNotifier
from core.email_notifier import EmailNotifier
import logging

# 创建专用logger
logger = logging.getLogger('log_management_dialog')
enhanced_logger = get_enhanced_logger()


class LogHighlighter(QSyntaxHighlighter):
    """日志语法高亮器"""
    
    def __init__(self, document):
        super().__init__(document)
        self.setup_highlighting_rules()
    
    def setup_highlighting_rules(self):
        """设置高亮规则"""
        self.highlighting_rules = []
        
        # 调试级别 - 灰色
        debug_format = QTextCharFormat()
        debug_format.setForeground(QColor("#808080"))
        self.highlighting_rules.append((r'\b调试\b.*', debug_format))
        
        # 信息级别 - 白色
        info_format = QTextCharFormat()
        info_format.setForeground(QColor("#d4d4d4"))
        self.highlighting_rules.append((r'\b信息\b.*', info_format))
        
        # 警告级别 - 黄色
        warning_format = QTextCharFormat()
        warning_format.setForeground(QColor("#ffcc00"))
        warning_format.setFontWeight(QFont.Weight.Bold)
        self.highlighting_rules.append((r'\b警告\b.*', warning_format))
        
        # 错误级别 - 红色
        error_format = QTextCharFormat()
        error_format.setForeground(QColor("#ff6b6b"))
        error_format.setFontWeight(QFont.Weight.Bold)
        self.highlighting_rules.append((r'\b错误\b.*', error_format))
        
        # 严重级别 - 深红色背景
        critical_format = QTextCharFormat()
        critical_format.setForeground(QColor("#ffffff"))
        critical_format.setBackground(QColor("#cc0000"))
        critical_format.setFontWeight(QFont.Weight.Bold)
        self.highlighting_rules.append((r'\b严重\b.*', critical_format))
        
        # 时间戳 - 青色
        timestamp_format = QTextCharFormat()
        timestamp_format.setForeground(QColor("#4ec9b0"))
        self.highlighting_rules.append((r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', timestamp_format))
        
        # 文件名和行号 - 蓝色
        file_format = QTextCharFormat()
        file_format.setForeground(QColor("#569cd6"))
        self.highlighting_rules.append((r'\w+\.py:\d+', file_format))
        
        # 异常类名 - 橙色
        exception_format = QTextCharFormat()
        exception_format.setForeground(QColor("#ff8c00"))
        exception_format.setFontWeight(QFont.Weight.Bold)
        self.highlighting_rules.append((r'\b\w*Exception\b|\b\w*Error\b', exception_format))
        
        # IP地址 - 绿色
        ip_format = QTextCharFormat()
        ip_format.setForeground(QColor("#90ee90"))
        self.highlighting_rules.append((r'\b(?:\d{1,3}\.){3}\d{1,3}\b', ip_format))
        
        # URL - 下划线蓝色
        url_format = QTextCharFormat()
        url_format.setForeground(QColor("#87ceeb"))
        url_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
        self.highlighting_rules.append((r'https?://[^\s]+', url_format))
    
    def highlightBlock(self, text):
        """高亮文本块"""
        for pattern, format in self.highlighting_rules:
            import re
            for match in re.finditer(pattern, text, re.IGNORECASE):
                start, end = match.span()
                self.setFormat(start, end - start, format)

class LogSearchThread(QThread):
    """日志搜索线程"""
    search_finished = pyqtSignal(list)
    progress_updated = pyqtSignal(int)
    
    def __init__(self, log_files, search_term, date_range=None):
        super().__init__()
        self.log_files = log_files
        self.search_term = search_term
        self.date_range = date_range
        self.results = []
    
    def run(self):
        total_files = len(self.log_files)
        for i, log_file in enumerate(self.log_files):
            try:
                if os.path.exists(log_file):
                    with open(log_file, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            if self.search_term.lower() in line.lower():
                                self.results.append({
                                    'file': os.path.basename(log_file),
                                    'line': line_num,
                                    'content': line.strip(),
                                    'timestamp': self.extract_timestamp(line)
                                })
                self.progress_updated.emit(int((i + 1) / total_files * 100))
            except Exception as e:
                continue
        
        self.search_finished.emit(self.results)
    
    def extract_timestamp(self, line):
        """从日志行中提取时间戳"""
        timestamp_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'
        match = re.search(timestamp_pattern, line)
        return match.group(1) if match else ''

class LogManagementDialog(QMainWindow):
    """增强版日志管理对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 调试日志 - 函数调用追踪
        enhanced_logger.debug_function_call(
            "LogManagementDialog.__init__", 
            "log_management_dialog",
            context="初始化日志管理对话框"
        )
        
        try:
            # 内存快照
            enhanced_logger.memory_snapshot("LogManagementDialog初始化开始")
            
            self.config_manager = get_log_config_manager()
            self.search_thread = None
            self.level_descriptions = {
                "调试": "🔍 调试信息 - 显示所有日志，包括详细的调试信息（适用于开发调试）",
                "信息": "ℹ️ 一般信息 - 显示程序运行的关键信息（推荐日常使用）", 
                "警告": "⚠️ 警告信息 - 显示可能的问题和警告（适用于生产环境）",
                "错误": "❌ 错误信息 - 只显示错误和严重问题（适用于故障排查）",
                "严重": "🚨 严重错误 - 只显示可能导致程序崩溃的严重错误（最小化日志）"
            }
            
            logging.debug(f"日志管理对话框初始化完成，父窗口: {parent}")
            
        except Exception as e:
            enhanced_logger.error_with_traceback(
                f"日志管理对话框初始化失败: {e}",
                "log_management_dialog"
            )
            raise
        
        # 自动刷新定时器
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.auto_refresh_all)
        self.auto_refresh_enabled = False
        self.auto_refresh_interval = 30  # 默认30秒

        # 告警监控相关
        self.alert_monitor_timer = QTimer()
        self.alert_monitor_timer.setSingleShot(False)
        self.alert_monitor_timer.timeout.connect(self.run_alert_checks)
        self.alert_monitor_enabled = False
        self.alert_check_interval_minutes = 5
        self.desktop_notifier = DesktopNotifier(self)
        self.email_notifier = EmailNotifier()
        
        self.init_ui()
        
        # 窗口居中显示
        if parent:
            self.move(parent.geometry().center() - self.rect().center())
        
        self.load_current_config()

        # 基于已保存设置初始化告警监控
        self.initialize_alert_monitor_from_settings()

        # 加载各页已保存设置
        try:
            self.load_viewer_settings()
        except Exception:
            pass
        try:
            self.load_debug_settings()
        except Exception:
            pass
        try:
            self.load_management_settings()
        except Exception:
            pass
        try:
            self.load_search_settings()
        except Exception:
            pass
    
    def mousePressEvent(self, event):
        """鼠标点击事件 - 点击时将窗口置顶"""
        try:
            self.raise_()
            self.activateWindow()
            super().mousePressEvent(event)
        except Exception as e:
            logger.exception(f"日志管理窗口置顶失败: {e}")
            super().mousePressEvent(event)
    
    def init_ui(self):
        # 调试日志 - 函数调用追踪
        enhanced_logger.debug_function_call(
            "init_ui", 
            "log_management_dialog",
            context="初始化日志管理UI"
        )
        
        try:
            with enhanced_logger.performance_monitor("UI初始化"):
                self.setWindowTitle(t('enhanced_log_management'))
                self.setMinimumWidth(900)
                self.setMinimumHeight(700)
                # 设置窗口标志，确保窗口可以被其他窗口覆盖，不保持在最上层
                self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowMinMaxButtonsHint)
                
                logging.debug("日志管理UI窗口属性设置完成")
                
        except Exception as e:
            enhanced_logger.error_with_traceback(
                f"日志管理UI初始化失败: {e}",
                "log_management_dialog"
            )
            raise
        
        # 创建中央窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 创建滚动内容部件
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 配置标签页
        self.config_tab = self.create_config_tab()
        self.tab_widget.addTab(self.config_tab, t('config_tab'))
        
        # 日志查看器标签页
        self.viewer_tab = self.create_viewer_tab()
        self.tab_widget.addTab(self.viewer_tab, t('viewer_tab'))
        
        # 调试日志专用标签页
        self.debug_tab = self.create_debug_tab()
        self.tab_widget.addTab(self.debug_tab, t('debug_log_tab'))
        
        # 搜索标签页
        self.search_tab = self.create_search_tab()
        self.tab_widget.addTab(self.search_tab, t('search_tab'))
        
        # 分析标签页
        self.analytics_tab = self.create_analytics_tab()
        self.tab_widget.addTab(self.analytics_tab, t('analytics_tab'))
        
        # 管理标签页
        self.management_tab = self.create_management_tab()
        self.tab_widget.addTab(self.management_tab, t('management_tab'))
        
        layout.addWidget(self.tab_widget)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        help_btn = QPushButton(t('help_button'))
        help_btn.setDefault(False)
        help_btn.setAutoDefault(False)
        help_btn.clicked.connect(self.show_help)
        button_layout.addWidget(help_btn)
        
        # 告警设置按钮
        alert_settings_btn = QPushButton(t('alert_settings_button'))
        alert_settings_btn.setDefault(False)
        alert_settings_btn.setAutoDefault(False)
        alert_settings_btn.clicked.connect(self.show_alert_settings)
        button_layout.addWidget(alert_settings_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton(t('close_button'))
        close_btn.setDefault(False)
        close_btn.setAutoDefault(False)
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # 设置滚动区域的内容
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
        # 调试日志实时监控定时器
        self.debug_monitor_timer = QTimer()
        self.debug_monitor_timer.timeout.connect(self.update_debug_logs)
        self.debug_monitoring_enabled = False
    
    def create_debug_tab(self):
        """创建调试日志专用标签页"""
        # 调试日志 - 函数调用追踪
        enhanced_logger.debug_function_call(
            "create_debug_tab", 
            "log_management_dialog",
            context="创建调试日志专用标签页"
        )
        
        try:
            with enhanced_logger.performance_monitor("调试日志标签页创建"):
                widget = QWidget()
                layout = QVBoxLayout()
                
                enhanced_logger.debug_info(
                    "开始创建调试日志专用标签页",
                    "log_management_dialog",
                    context="UI组件初始化"
                )
                
        except Exception as e:
            enhanced_logger.error_with_traceback(
                f"创建调试日志标签页失败: {e}",
                "log_management_dialog"
            )
            raise
        
        # 调试日志控制面板
        control_group = QGroupBox(t('debug_log_control_panel'))
        control_layout = QGridLayout()
        
        # 实时监控开关
        self.debug_monitor_check = QCheckBox(t('enable_realtime_monitoring'))
        self.debug_monitor_check.setToolTip(t('realtime_monitoring_tooltip'))
        self.debug_monitor_check.toggled.connect(self.toggle_debug_monitoring)
        control_layout.addWidget(self.debug_monitor_check, 0, 0)
        
        # 监控间隔设置
        control_layout.addWidget(QLabel(t('monitoring_interval_seconds')), 0, 1)
        self.debug_interval_spin = QSpinBox()
        self.debug_interval_spin.setRange(1, 60)
        self.debug_interval_spin.setValue(5)
        self.debug_interval_spin.setSuffix(t('seconds_suffix'))
        control_layout.addWidget(self.debug_interval_spin, 0, 2)
        
        # 调试级别过滤
        control_layout.addWidget(QLabel(t('debug_level')), 1, 0)
        self.debug_level_combo = QComboBox()
        self.debug_level_combo.addItems([t('all'), "debug_info", "debug_function_call", "debug_error", "performance_monitor", "memory_snapshot"])
        self.debug_level_combo.currentTextChanged.connect(self.filter_debug_logs)
        control_layout.addWidget(self.debug_level_combo, 1, 1, 1, 2)
        
        # 模块过滤
        control_layout.addWidget(QLabel(t('module_filter')), 2, 0)
        self.debug_module_combo = QComboBox()
        self.debug_module_combo.addItems([t('all_modules'), "ocr_worker_threaded", "email_notifier", "desktop_notifier", "log_management_dialog"])
        self.debug_module_combo.currentTextChanged.connect(self.filter_debug_logs)
        control_layout.addWidget(self.debug_module_combo, 2, 1, 1, 2)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        refresh_debug_btn = QPushButton(t('refresh_button'))
        refresh_debug_btn.clicked.connect(self.refresh_debug_logs)
        button_layout.addWidget(refresh_debug_btn)
        
        clear_debug_btn = QPushButton(t('clear_button'))
        clear_debug_btn.clicked.connect(self.clear_debug_logs)
        button_layout.addWidget(clear_debug_btn)
        
        export_debug_btn = QPushButton(t('export_button'))
        export_debug_btn.clicked.connect(self.export_debug_logs)
        button_layout.addWidget(export_debug_btn)

        # 保存设置按钮
        save_debug_btn = QPushButton("💾 保存设置")
        save_debug_btn.setDefault(False)
        save_debug_btn.setAutoDefault(False)
        save_debug_btn.clicked.connect(self.save_debug_settings)
        button_layout.addWidget(save_debug_btn)
        
        button_layout.addStretch()
        
        control_layout.addLayout(button_layout, 3, 0, 1, 3)
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # 调试日志显示区域
        display_group = QGroupBox(t('debug_log_content'))
        display_layout = QVBoxLayout()
        
        # 统计信息
        stats_layout = QHBoxLayout()
        self.debug_total_label = QLabel(t('total_count_0'))
        self.debug_errors_label = QLabel(t('error_count_0'))
        self.debug_functions_label = QLabel(t('function_call_count_0'))
        self.debug_performance_label = QLabel(t('performance_monitor_count_0'))
        
        stats_layout.addWidget(self.debug_total_label)
        stats_layout.addWidget(self.debug_errors_label)
        stats_layout.addWidget(self.debug_functions_label)
        stats_layout.addWidget(self.debug_performance_label)
        stats_layout.addStretch()
        
        display_layout.addLayout(stats_layout)
        
        # 调试日志文本显示
        self.debug_text = QTextEdit()
        self.debug_text.setReadOnly(True)
        self.debug_text.setFont(QFont("Consolas", 9))
        self.debug_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        
        # 为调试日志添加语法高亮
        self.debug_highlighter = LogHighlighter(self.debug_text.document())
        
        display_layout.addWidget(self.debug_text)
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)
        
        widget.setLayout(layout)
        return widget
    
    def toggle_debug_monitoring(self, enabled):
        """切换调试日志实时监控"""
        enhanced_logger.debug_function_call(
            "toggle_debug_monitoring", 
            "log_management_dialog",
            context=f"切换调试监控状态: {enabled}"
        )
        
        self.debug_monitoring_enabled = enabled
        
        if enabled:
            interval = self.debug_interval_spin.value() * 1000  # 转换为毫秒
            self.debug_monitor_timer.start(interval)
            enhanced_logger.debug_info(
                f"启用调试日志实时监控，间隔: {self.debug_interval_spin.value()}秒",
                "log_management_dialog"
            )
        else:
            self.debug_monitor_timer.stop()
            enhanced_logger.debug_info(
                "停用调试日志实时监控",
                "log_management_dialog"
            )
    
    def update_debug_logs(self):
        """更新调试日志显示"""
        try:
            if not self.debug_monitoring_enabled:
                return
            
            # 获取最新的调试日志
            debug_logs = self.get_debug_logs()
            
            # 应用过滤
            filtered_logs = self.apply_debug_filters(debug_logs)
            
            # 更新显示
            self.display_debug_logs(filtered_logs)
            
            # 更新统计
            self.update_debug_statistics(filtered_logs)
            
        except Exception as e:
            enhanced_logger.debug_error(
                f"更新调试日志失败: {e}",
                "log_management_dialog",
                error_code="DEBUG_UPDATE_FAILED"
            )
    
    def get_debug_logs(self):
        """获取调试日志数据"""
        debug_logs = []
        
        try:
            # 从日志文件中提取调试日志
            log_files = self.get_log_files()
            
            for log_file in log_files:
                if os.path.exists(log_file):
                    with open(log_file, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            line = line.strip()
                            if not line:
                                continue
                            
                            # 检查是否为调试日志
                            if any(debug_type in line for debug_type in 
                                   ['debug_info', 'debug_function_call', 'debug_error', 
                                    'performance_monitor', 'memory_snapshot']):
                                debug_logs.append({
                                    'file': os.path.basename(log_file),
                                    'line': line_num,
                                    'content': line,
                                    'timestamp': self.extract_timestamp(line),
                                    'type': self.extract_debug_type(line),
                                    'module': self.extract_module(line)
                                })
        
        except Exception as e:
            enhanced_logger.debug_error(
                f"获取调试日志失败: {e}",
                "log_management_dialog",
                error_code="DEBUG_LOGS_FETCH_FAILED"
            )
        
        return debug_logs
    
    def extract_debug_type(self, line):
        """从日志行中提取调试类型"""
        debug_types = ['debug_info', 'debug_function_call', 'debug_error', 
                      'performance_monitor', 'memory_snapshot']
        
        for debug_type in debug_types:
            if debug_type in line:
                return debug_type
        
        return 'unknown'
    
    def extract_module(self, line):
        """从日志行中提取模块名"""
        # 尝试从日志行中提取模块信息
        import re
        
        # 查找模块名模式
        module_pattern = r'"module":\s*"([^"]+)"'
        match = re.search(module_pattern, line)
        
        if match:
            return match.group(1)
        
        return 'unknown'
    
    def apply_debug_filters(self, debug_logs):
        """应用调试日志过滤器"""
        filtered_logs = debug_logs
        
        # 级别过滤
        selected_level = self.debug_level_combo.currentText()
        if selected_level != "全部":
            filtered_logs = [log for log in filtered_logs if log['type'] == selected_level]
        
        # 模块过滤
        selected_module = self.debug_module_combo.currentText()
        if selected_module != "全部模块":
            filtered_logs = [log for log in filtered_logs if log['module'] == selected_module]
        
        return filtered_logs
    
    def display_debug_logs(self, debug_logs):
        """显示调试日志"""
        try:
            # 限制显示的日志数量，避免界面卡顿
            max_logs = 1000
            display_logs = debug_logs[-max_logs:] if len(debug_logs) > max_logs else debug_logs
            
            # 格式化日志内容
            formatted_content = []
            for log in display_logs:
                formatted_line = f"[{log['timestamp']}] [{log['type']}] [{log['module']}] {log['content']}"
                formatted_content.append(formatted_line)
            
            # 更新文本显示
            self.debug_text.setPlainText('\n'.join(formatted_content))
            
            # 滚动到底部显示最新日志
            cursor = self.debug_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.debug_text.setTextCursor(cursor)
            
        except Exception as e:
            enhanced_logger.debug_error(
                f"显示调试日志失败: {e}",
                "log_management_dialog",
                error_code="DEBUG_DISPLAY_FAILED"
            )
    
    def update_debug_statistics(self, debug_logs):
        """更新调试日志统计信息"""
        try:
            total_count = len(debug_logs)
            error_count = len([log for log in debug_logs if log['type'] == 'debug_error'])
            function_count = len([log for log in debug_logs if log['type'] == 'debug_function_call'])
            performance_count = len([log for log in debug_logs if log['type'] == 'performance_monitor'])
            
            self.debug_total_label.setText(f"总数: {total_count}")
            self.debug_errors_label.setText(f"错误: {error_count}")
            self.debug_functions_label.setText(f"函数调用: {function_count}")
            self.debug_performance_label.setText(f"性能监控: {performance_count}")
            
        except Exception as e:
            enhanced_logger.debug_error(
                f"更新调试统计失败: {e}",
                "log_management_dialog",
                error_code="DEBUG_STATS_UPDATE_FAILED"
            )
    
    def filter_debug_logs(self):
        """过滤调试日志"""
        enhanced_logger.debug_function_call(
            "filter_debug_logs", 
            "log_management_dialog",
            context="应用调试日志过滤器"
        )
        
        # 重新获取和显示日志
        self.refresh_debug_logs()
    
    def refresh_debug_logs(self):
        """刷新调试日志"""
        enhanced_logger.debug_function_call(
            "refresh_debug_logs", 
            "log_management_dialog",
            context="手动刷新调试日志"
        )
        
        try:
            debug_logs = self.get_debug_logs()
            filtered_logs = self.apply_debug_filters(debug_logs)
            self.display_debug_logs(filtered_logs)
            self.update_debug_statistics(filtered_logs)
            
            enhanced_logger.debug_info(
                f"调试日志刷新完成，显示 {len(filtered_logs)} 条记录",
                "log_management_dialog"
            )
            
        except Exception as e:
            enhanced_logger.debug_error(
                f"刷新调试日志失败: {e}",
                "log_management_dialog",
                error_code="DEBUG_REFRESH_FAILED"
            )
    
    def clear_debug_logs(self):
        """清空调试日志显示"""
        enhanced_logger.debug_function_call(
            "clear_debug_logs", 
            "log_management_dialog",
            context="清空调试日志显示"
        )
        
        self.debug_text.clear()
        self.debug_total_label.setText("总数: 0")
        self.debug_errors_label.setText("错误: 0")
        self.debug_functions_label.setText("函数调用: 0")
        self.debug_performance_label.setText("性能监控: 0")
        
        enhanced_logger.debug_info(
            "调试日志显示已清空",
            "log_management_dialog"
        )
    
    def export_debug_logs(self):
        """导出调试日志"""
        enhanced_logger.debug_function_call(
            "export_debug_logs", 
            "log_management_dialog",
            context="导出调试日志"
        )
        
        try:
            # 获取当前显示的调试日志
            debug_logs = self.get_debug_logs()
            filtered_logs = self.apply_debug_filters(debug_logs)
            
            if not filtered_logs:
                QMessageBox.warning(self, "警告", "没有调试日志可导出")
                return
            
            # 选择导出文件
            file_path, _ = QFileDialog.getSaveFileName(
                self, 
                "导出调试日志", 
                f"debug_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "文本文件 (*.txt);;CSV文件 (*.csv);;JSON文件 (*.json)"
            )
            
            if file_path:
                if file_path.endswith('.csv'):
                    self.export_debug_logs_csv(file_path, filtered_logs)
                elif file_path.endswith('.json'):
                    self.export_debug_logs_json(file_path, filtered_logs)
                else:
                    self.export_debug_logs_txt(file_path, filtered_logs)
                
                enhanced_logger.debug_info(
                    f"调试日志导出完成: {file_path}",
                    "log_management_dialog",
                    context=f"导出 {len(filtered_logs)} 条记录"
                )
                
                QMessageBox.information(self, "成功", f"调试日志已导出到:\n{file_path}")
        
        except Exception as e:
            enhanced_logger.debug_error(
                f"导出调试日志失败: {e}",
                "log_management_dialog",
                error_code="DEBUG_EXPORT_FAILED"
            )
            QMessageBox.critical(self, "错误", f"导出调试日志失败: {e}")
    
    def export_debug_logs_txt(self, file_path, debug_logs):
        """导出调试日志为文本格式"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"调试日志导出报告\n")
            f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"总记录数: {len(debug_logs)}\n")
            f.write("=" * 80 + "\n\n")
            
            for log in debug_logs:
                f.write(f"时间: {log['timestamp']}\n")
                f.write(f"类型: {log['type']}\n")
                f.write(f"模块: {log['module']}\n")
                f.write(f"文件: {log['file']}:{log['line']}\n")
                f.write(f"内容: {log['content']}\n")
                f.write("-" * 80 + "\n")
    
    def export_debug_logs_csv(self, file_path, debug_logs):
        """导出调试日志为CSV格式"""
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['时间戳', '类型', '模块', '文件', '行号', '内容'])
            
            for log in debug_logs:
                writer.writerow([
                    log['timestamp'],
                    log['type'],
                    log['module'],
                    log['file'],
                    log['line'],
                    log['content']
                ])
    
    def export_debug_logs_json(self, file_path, debug_logs):
        """导出调试日志为JSON格式"""
        export_data = {
            'export_time': datetime.now().isoformat(),
            'total_count': len(debug_logs),
            'logs': debug_logs
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    def create_config_tab(self):
        """创建配置标签页"""
        # 调试日志 - 函数调用追踪
        enhanced_logger.debug_function_call(
            "create_config_tab", 
            "log_management_dialog",
            context="创建日志配置标签页"
        )
        
        try:
            with enhanced_logger.performance_monitor("配置标签页创建"):
                widget = QWidget()
                layout = QVBoxLayout()
                
                logging.debug("开始创建日志配置标签页")
                
        except Exception as e:
            enhanced_logger.error_with_traceback(
                f"创建配置标签页失败: {e}",
                "log_management_dialog"
            )
            raise
        
        # 基础配置组
        basic_group = QGroupBox("基础配置")
        basic_layout = QGridLayout()
        
        # 日志级别
        basic_layout.addWidget(QLabel("日志级别:"), 0, 0)
        self.level_combo = QComboBox()
        self.level_combo.addItems(["调试", "信息", "警告", "错误", "严重"])
        self.level_combo.currentTextChanged.connect(self.on_level_changed)
        basic_layout.addWidget(self.level_combo, 0, 1)
        
        # 级别说明
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        # 设置默认说明文字
        self.description_label.setText("ℹ️ 一般信息 - 显示程序运行的关键信息（推荐日常使用）")
        # 根据主题设置样式
        settings = load_settings()
        current_theme = settings.get('theme', '浅色')
        if current_theme == '深色':
            # 深色主题样式
            self.description_label.setStyleSheet("""
                QLabel {
                    background-color: #2d2d2d !important;
                    border: 1px solid #0078d4 !important;
                    border-radius: 3px !important;
                    padding: 5px !important;
                    color: #ffffff !important;
                    font-weight: bold !important;
                }
            """)
        else:
            # 浅色主题样式
            self.description_label.setStyleSheet("""
                QLabel {
                    background-color: #e8f5e8 !important;
                    border: 1px solid #4CAF50 !important;
                    border-radius: 3px !important;
                    padding: 5px !important;
                    color: #2e7d32 !important;
                    font-weight: bold !important;
                }
            """)
        basic_layout.addWidget(self.description_label, 1, 0, 1, 2)
        
        # 输出选项
        basic_layout.addWidget(QLabel("输出选项:"), 2, 0)
        output_layout = QHBoxLayout()
        self.console_check = QCheckBox("控制台输出")
        self.file_check = QCheckBox("文件输出")
        output_layout.addWidget(self.console_check)
        output_layout.addWidget(self.file_check)
        output_widget = QWidget()
        output_widget.setLayout(output_layout)
        basic_layout.addWidget(output_widget, 2, 1)
        
        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)
        
        # 高级配置组
        advanced_group = QGroupBox("高级配置")
        advanced_layout = QGridLayout()
        
        # 日志轮转
        self.rotation_check = QCheckBox("启用日志轮转")
        advanced_layout.addWidget(self.rotation_check, 0, 0, 1, 2)
        
        advanced_layout.addWidget(QLabel("最大文件大小(MB):"), 1, 0)
        self.max_size_spin = QSpinBox()
        self.max_size_spin.setRange(1, 1000)
        self.max_size_spin.setValue(10)
        advanced_layout.addWidget(self.max_size_spin, 1, 1)
        
        advanced_layout.addWidget(QLabel("备份文件数:"), 2, 0)
        self.backup_files_spin = QSpinBox()
        self.backup_files_spin.setRange(1, 50)
        self.backup_files_spin.setValue(5)
        advanced_layout.addWidget(self.backup_files_spin, 2, 1)
        
        # 性能选项
        self.async_check = QCheckBox("启用异步写入")
        advanced_layout.addWidget(self.async_check, 3, 0, 1, 2)
        
        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)
        
        # 自动刷新配置组
        refresh_group = QGroupBox("🔄 自动刷新配置")
        refresh_layout = QGridLayout()
        
        # 自动刷新开关
        self.auto_refresh_check = QCheckBox("启用自动刷新")
        self.auto_refresh_check.setToolTip("启用后将自动刷新所有标签页的内容")
        self.auto_refresh_check.toggled.connect(self.toggle_auto_refresh)
        refresh_layout.addWidget(self.auto_refresh_check, 0, 0, 1, 2)
        
        # 刷新间隔设置
        refresh_layout.addWidget(QLabel("刷新间隔(秒):"), 1, 0)
        self.refresh_interval_spin = QSpinBox()
        self.refresh_interval_spin.setRange(5, 300)  # 5秒到5分钟
        self.refresh_interval_spin.setValue(30)
        self.refresh_interval_spin.setSuffix(" 秒")
        self.refresh_interval_spin.setToolTip("设置自动刷新的时间间隔（5-300秒）")
        self.refresh_interval_spin.valueChanged.connect(self.update_refresh_interval)
        refresh_layout.addWidget(self.refresh_interval_spin, 1, 1)
        
        # 刷新状态显示
        self.refresh_status_label = QLabel("自动刷新: 已禁用")
        self.refresh_status_label.setStyleSheet("""
            QLabel {
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 5px;
                color: #666;
            }
        """)
        refresh_layout.addWidget(self.refresh_status_label, 2, 0, 1, 2)
        
        refresh_group.setLayout(refresh_layout)
        layout.addWidget(refresh_group)
        
        # 预览区域
        preview_group = QGroupBox("📊 日志预览")
        preview_layout = QVBoxLayout()
        
        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(150)
        self.preview_text.setStyleSheet("""
            QPlainTextEdit {
                font-family: 'Consolas', monospace;
                font-size: 9pt;
                border: 1px solid #555;
                border-radius: 3px;
            }
        """)
        preview_layout.addWidget(self.preview_text)
        
        # 统计信息
        self.stats_label = QLabel("正在加载统计信息...")
        self.stats_label.setStyleSheet("padding: 5px; border-radius: 3px;")
        preview_layout.addWidget(self.stats_label)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 刷新预览")
        refresh_btn.setDefault(False)
        refresh_btn.setAutoDefault(False)
        refresh_btn.clicked.connect(self.refresh_preview)
        button_layout.addWidget(refresh_btn)
        
        test_btn = QPushButton("🧪 测试配置")
        test_btn.setDefault(False)
        test_btn.setAutoDefault(False)
        test_btn.clicked.connect(self.test_config)
        button_layout.addWidget(test_btn)
        
        button_layout.addStretch()
        
        save_btn = QPushButton("💾 保存配置")
        save_btn.setDefault(False)
        save_btn.setAutoDefault(False)
        save_btn.clicked.connect(self.save_config)
        save_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_viewer_tab(self):
        """创建日志查看器标签页"""
        # 调试日志 - 函数调用追踪
        enhanced_logger.debug_function_call(
            "create_viewer_tab", 
            "log_management_dialog",
            context="创建日志查看器标签页"
        )
        
        try:
            with enhanced_logger.performance_monitor("查看器标签页创建"):
                widget = QWidget()
                layout = QVBoxLayout()
                
                logging.debug("开始创建日志查看器标签页")
                
        except Exception as e:
            enhanced_logger.error_with_traceback(
                f"创建查看器标签页失败: {e}",
                "log_management_dialog"
            )
            raise
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setDefault(False)
        refresh_btn.setAutoDefault(False)
        refresh_btn.clicked.connect(self.refresh_log_viewer)
        toolbar_layout.addWidget(refresh_btn)
        
        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.setDefault(False)
        clear_btn.setAutoDefault(False)
        clear_btn.clicked.connect(self.clear_log_viewer)
        toolbar_layout.addWidget(clear_btn)
        
        # 导出按钮
        export_btn = QPushButton("📤 导出")
        export_btn.setDefault(False)
        export_btn.setAutoDefault(False)
        export_btn.clicked.connect(self.export_logs)
        toolbar_layout.addWidget(export_btn)
        
        # 自动滚动开关
        self.auto_scroll_check = QCheckBox("自动滚动")
        self.auto_scroll_check.setChecked(True)
        toolbar_layout.addWidget(self.auto_scroll_check)
        
        # 语法高亮开关
        self.syntax_highlight_check = QCheckBox("语法高亮")
        self.syntax_highlight_check.setChecked(True)
        self.syntax_highlight_check.toggled.connect(self.toggle_syntax_highlight)
        toolbar_layout.addWidget(self.syntax_highlight_check)
        
        toolbar_layout.addStretch()
        
        # 级别过滤
        toolbar_layout.addWidget(QLabel("级别:"))
        self.viewer_level_combo = QComboBox()
        self.viewer_level_combo.addItems(["全部", "调试", "信息", "警告", "错误", "严重"])
        self.viewer_level_combo.currentTextChanged.connect(self.filter_logs)
        toolbar_layout.addWidget(self.viewer_level_combo)
        
        # 每页行数
        toolbar_layout.addWidget(QLabel("每页:"))
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["100", "500", "1000", "2000", "全部"])
        self.page_size_combo.setCurrentText("全部")
        self.page_size_combo.currentTextChanged.connect(self.change_page_size)
        toolbar_layout.addWidget(self.page_size_combo)
        
        layout.addLayout(toolbar_layout)
        
        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索:"))
        self.viewer_search_input = QLineEdit()
        self.viewer_search_input.setPlaceholderText("输入关键词搜索...")
        self.viewer_search_input.textChanged.connect(self.search_in_viewer)
        search_layout.addWidget(self.viewer_search_input)
        
        # 搜索选项
        self.case_sensitive_check = QCheckBox("区分大小写")
        search_layout.addWidget(self.case_sensitive_check)
        
        self.regex_search_check = QCheckBox("正则表达式")
        search_layout.addWidget(self.regex_search_check)
        
        # 搜索导航
        prev_btn = QPushButton("⬆️")
        prev_btn.setDefault(False)
        prev_btn.setAutoDefault(False)
        prev_btn.setMaximumWidth(30)
        prev_btn.clicked.connect(self.find_previous)
        search_layout.addWidget(prev_btn)
        
        next_btn = QPushButton("⬇️")
        next_btn.setDefault(False)
        next_btn.setAutoDefault(False)
        next_btn.setMaximumWidth(30)
        next_btn.clicked.connect(self.find_next)
        search_layout.addWidget(next_btn)
        
        self.search_count_label = QLabel("0/0")
        search_layout.addWidget(self.search_count_label)
        
        search_layout.addStretch()
        layout.addLayout(search_layout)
        
        # 日志显示区域
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setFont(QFont("Consolas", 9))
        self.log_viewer.setStyleSheet("""
            QTextEdit {
                border: 1px solid #3c3c3c;
                border-radius: 3px;
            }
        """)
        
        # 添加语法高亮
        self.highlighter = LogHighlighter(self.log_viewer.document())
        
        layout.addWidget(self.log_viewer)
        
        # 分页控件
        pagination_layout = QHBoxLayout()
        
        self.first_page_btn = QPushButton("⏮️ 首页")
        self.first_page_btn.setDefault(False)
        self.first_page_btn.setAutoDefault(False)
        self.first_page_btn.clicked.connect(self.go_to_first_page)
        pagination_layout.addWidget(self.first_page_btn)
        
        self.prev_page_btn = QPushButton("⏪ 上一页")
        self.prev_page_btn.setDefault(False)
        self.prev_page_btn.setAutoDefault(False)
        self.prev_page_btn.clicked.connect(self.go_to_prev_page)
        pagination_layout.addWidget(self.prev_page_btn)
        
        self.page_info_label = QLabel("第 1 页，共 1 页")
        self.page_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pagination_layout.addWidget(self.page_info_label)
        
        self.next_page_btn = QPushButton("⏩ 下一页")
        self.next_page_btn.setDefault(False)
        self.next_page_btn.setAutoDefault(False)
        self.next_page_btn.clicked.connect(self.go_to_next_page)
        pagination_layout.addWidget(self.next_page_btn)
        
        self.last_page_btn = QPushButton("⏭️ 末页")
        self.last_page_btn.setDefault(False)
        self.last_page_btn.setAutoDefault(False)
        self.last_page_btn.clicked.connect(self.go_to_last_page)
        pagination_layout.addWidget(self.last_page_btn)
        
        pagination_layout.addStretch()
        
        # 跳转到指定页
        pagination_layout.addWidget(QLabel("跳转到:"))
        self.page_input = QLineEdit()
        self.page_input.setMaximumWidth(60)
        self.page_input.setPlaceholderText("页码")
        self.page_input.returnPressed.connect(self.go_to_page)
        pagination_layout.addWidget(self.page_input)
        
        go_btn = QPushButton("跳转")
        go_btn.setDefault(False)
        go_btn.setAutoDefault(False)
        go_btn.clicked.connect(self.go_to_page)
        pagination_layout.addWidget(go_btn)
        
        layout.addLayout(pagination_layout)
        
        # 初始化分页变量
        self.current_page = 1
        self.total_pages = 1
        self.page_size = float('inf')  # 默认显示全部
        self.all_logs = []
        self.filtered_logs = []
        self.search_matches = []
        self.current_match = -1

        # 底部保存设置按钮
        viewer_buttons_layout = QHBoxLayout()
        viewer_buttons_layout.addStretch()
        save_viewer_btn = QPushButton("💾 保存设置")
        save_viewer_btn.setDefault(False)
        save_viewer_btn.setAutoDefault(False)
        save_viewer_btn.clicked.connect(self.save_viewer_settings)
        viewer_buttons_layout.addWidget(save_viewer_btn)
        layout.addLayout(viewer_buttons_layout)

        widget.setLayout(layout)
        return widget
    
    def create_search_tab(self):
        """创建搜索标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 搜索控件
        search_group = QGroupBox("🔍 搜索条件")
        search_layout = QGridLayout()
        
        search_layout.addWidget(QLabel("搜索关键词:"), 0, 0)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入要搜索的关键词...")
        search_layout.addWidget(self.search_input, 0, 1)
        
        search_btn = QPushButton("🔍 搜索")
        search_btn.clicked.connect(self.start_search)
        search_layout.addWidget(search_btn, 0, 2)
        
        # 日期范围
        search_layout.addWidget(QLabel("日期范围:"), 1, 0)
        date_layout = QHBoxLayout()
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-7))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        date_layout.addWidget(QLabel("从"))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("到"))
        date_layout.addWidget(self.end_date)
        date_widget = QWidget()
        date_widget.setLayout(date_layout)
        search_layout.addWidget(date_widget, 1, 1, 1, 2)
        
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # 搜索进度
        self.search_progress = QProgressBar()
        self.search_progress.setVisible(False)
        layout.addWidget(self.search_progress)
        
        # 搜索结果
        results_group = QGroupBox("📋 搜索结果")
        results_layout = QVBoxLayout()
        
        self.search_results = QTableWidget()
        self.search_results.setColumnCount(4)
        self.search_results.setHorizontalHeaderLabels(["文件", "行号", "时间", "内容"])
        self.search_results.horizontalHeader().setStretchLastSection(True)
        self.search_results.setAlternatingRowColors(True)
        self.search_results.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        results_layout.addWidget(self.search_results)
        
        # 导出搜索结果
        export_layout = QHBoxLayout()
        export_layout.addStretch()
        export_btn = QPushButton("📤 导出结果")
        export_btn.clicked.connect(self.export_search_results)
        export_layout.addWidget(export_btn)
        results_layout.addLayout(export_layout)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        # 保存默认搜索设置按钮
        search_buttons_layout = QHBoxLayout()
        search_buttons_layout.addStretch()
        save_search_btn = QPushButton("💾 保存默认搜索设置")
        save_search_btn.setDefault(False)
        save_search_btn.setAutoDefault(False)
        save_search_btn.clicked.connect(self.save_search_settings)
        search_buttons_layout.addWidget(save_search_btn)
        layout.addLayout(search_buttons_layout)

        widget.setLayout(layout)
        return widget
    
    def create_analytics_tab(self):
        """创建分析标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        refresh_analytics_btn = QPushButton("🔄 刷新分析")
        refresh_analytics_btn.clicked.connect(self.refresh_analytics)
        export_analytics_btn = QPushButton("📊 导出报告")
        export_analytics_btn.clicked.connect(self.export_analytics_report)
        
        toolbar_layout.addWidget(refresh_analytics_btn)
        toolbar_layout.addWidget(export_analytics_btn)
        toolbar_layout.addStretch()
        
        layout.addLayout(toolbar_layout)
        
        # 基础统计信息区域
        stats_group = QGroupBox("📈 基础统计")
        stats_layout = QGridLayout()
        
        self.total_logs_label = QLabel("总日志数: 0")
        self.error_count_label = QLabel("错误数: 0")
        self.warning_count_label = QLabel("警告数: 0")
        self.file_size_label = QLabel("文件大小: 0 B")
        
        # 设置标签样式
        for label in [self.total_logs_label, self.error_count_label, 
                     self.warning_count_label, self.file_size_label]:
            label.setStyleSheet("""
                QLabel {
                    padding: 8px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background-color: #f9f9f9;
                    font-weight: bold;
                }
            """)
        
        stats_layout.addWidget(self.total_logs_label, 0, 0)
        stats_layout.addWidget(self.error_count_label, 0, 1)
        stats_layout.addWidget(self.warning_count_label, 1, 0)
        stats_layout.addWidget(self.file_size_label, 1, 1)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # 创建水平分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 详细信息区域
        detail_group = QGroupBox("📋 详细信息")
        detail_layout = QVBoxLayout()
        
        self.analytics_detail_text = QTextEdit()
        self.analytics_detail_text.setReadOnly(True)
        self.analytics_detail_text.setMaximumHeight(300)
        self.analytics_detail_text.setPlainText("点击'刷新分析'按钮获取详细统计信息...")
        
        detail_layout.addWidget(self.analytics_detail_text)
        detail_group.setLayout(detail_layout)
        splitter.addWidget(detail_group)
        
        # 图表区域
        chart_group = QGroupBox("📊 可视化图表")
        chart_layout = QVBoxLayout()
        
        self.analytics_chart_text = QTextEdit()
        self.analytics_chart_text.setReadOnly(True)
        self.analytics_chart_text.setMaximumHeight(300)
        self.analytics_chart_text.setFont(QFont("Consolas", 9))  # 使用等宽字体
        self.analytics_chart_text.setPlainText("点击'刷新分析'按钮生成图表...")
        
        chart_layout.addWidget(self.analytics_chart_text)
        chart_group.setLayout(chart_layout)
        splitter.addWidget(chart_group)
        
        # 设置分割器比例
        splitter.setSizes([400, 400])
        layout.addWidget(splitter)
        
        # 趋势分析区域
        trend_group = QGroupBox("📈 趋势分析")
        trend_layout = QVBoxLayout()
        
        self.trend_text = QTextEdit()
        self.trend_text.setReadOnly(True)
        self.trend_text.setMaximumHeight(150)
        self.trend_text.setPlainText("趋势分析将在刷新后显示...")
        
        trend_layout.addWidget(self.trend_text)
        trend_group.setLayout(trend_layout)
        layout.addWidget(trend_group)
        
        widget.setLayout(layout)
        return widget
    
    def create_management_tab(self):
        """创建管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 文件管理
        file_group = QGroupBox("📁 文件管理")
        file_layout = QVBoxLayout()
        
        # 日志文件列表
        self.log_files_table = QTableWidget()
        self.log_files_table.setColumnCount(3)
        self.log_files_table.setHorizontalHeaderLabels(["文件名", "大小", "修改时间"])
        self.log_files_table.horizontalHeader().setStretchLastSection(True)
        self.log_files_table.setAlternatingRowColors(True)
        
        file_layout.addWidget(self.log_files_table)
        
        # 文件操作按钮
        file_buttons_layout = QHBoxLayout()
        
        refresh_files_btn = QPushButton("🔄 刷新列表")
        refresh_files_btn.setDefault(False)
        refresh_files_btn.setAutoDefault(False)
        refresh_files_btn.clicked.connect(self.refresh_file_list)
        file_buttons_layout.addWidget(refresh_files_btn)
        
        open_folder_btn = QPushButton("📂 打开文件夹")
        open_folder_btn.setDefault(False)
        open_folder_btn.setAutoDefault(False)
        open_folder_btn.clicked.connect(self.open_log_folder)
        file_buttons_layout.addWidget(open_folder_btn)
        
        file_buttons_layout.addStretch()
        
        export_logs_btn = QPushButton("📤 导出日志")
        export_logs_btn.setDefault(False)
        export_logs_btn.setAutoDefault(False)
        export_logs_btn.clicked.connect(self.export_logs)
        file_buttons_layout.addWidget(export_logs_btn)
        
        cleanup_btn = QPushButton("清理日志")
        cleanup_btn.setDefault(False)
        cleanup_btn.setAutoDefault(False)
        cleanup_btn.clicked.connect(self.cleanup_logs)
        cleanup_btn.setStyleSheet("")
        file_buttons_layout.addWidget(cleanup_btn)
        
        file_layout.addLayout(file_buttons_layout)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # 清理选项
        cleanup_group = QGroupBox("清理选项")
        cleanup_layout = QGridLayout()
        
        cleanup_layout.addWidget(QLabel("保留天数:"), 0, 0)
        self.keep_days_spin = QSpinBox()
        self.keep_days_spin.setRange(1, 365)
        self.keep_days_spin.setValue(30)
        cleanup_layout.addWidget(self.keep_days_spin, 0, 1)
        
        self.auto_cleanup_check = QCheckBox("启用自动清理")
        cleanup_layout.addWidget(self.auto_cleanup_check, 1, 0, 1, 2)
        
        cleanup_group.setLayout(cleanup_layout)
        layout.addWidget(cleanup_group)

        # 保存清理设置按钮
        mgmt_buttons_layout = QHBoxLayout()
        mgmt_buttons_layout.addStretch()
        save_cleanup_btn = QPushButton("💾 保存设置")
        save_cleanup_btn.setDefault(False)
        save_cleanup_btn.setAutoDefault(False)
        save_cleanup_btn.clicked.connect(self.save_management_settings)
        mgmt_buttons_layout.addWidget(save_cleanup_btn)
        layout.addLayout(mgmt_buttons_layout)

        widget.setLayout(layout)
        return widget
    
    def load_current_config(self):
        """加载当前配置"""
        try:
            config = self.config_manager.get_config()
            
            self.level_combo.setCurrentText(config.level)
            # 立即调用级别变更处理函数，确保说明文字显示
            self.on_level_changed(config.level)
            
            self.console_check.setChecked(config.enable_console)
            self.file_check.setChecked(config.enable_file)
            
            self.rotation_check.setChecked(config.enable_rotation)
            self.max_size_spin.setValue(config.max_file_size_mb)
            self.backup_files_spin.setValue(config.max_backup_files)
            
            self.async_check.setChecked(config.enable_async)
            
            # 加载自动刷新配置
            self.load_auto_refresh_config()
            
            self.refresh_preview()
            self.update_statistics()
        except Exception as e:
            QMessageBox.warning(self, "警告", f"加载配置失败: {e}")
    
    def on_level_changed(self, level):
        """当日志级别改变时更新说明"""
        if level in self.level_descriptions:
            self.description_label.setText(self.level_descriptions[level])
        self.refresh_preview()
        self.update_statistics()
    
    def refresh_preview(self):
        """刷新日志预览"""
        current_level = self.level_combo.currentText()
        preview_logs = self.generate_preview_logs(current_level)
        self.preview_text.setPlainText(preview_logs)
    
    def generate_preview_logs(self, level):
        """生成预览日志示例"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        all_logs = [
            ("调试", f"{now} - 调试 - 🔍 OCR识别开始，区域坐标: (100, 200, 300, 400)"),
            ("调试", f"{now} - 调试 - 🔍 API调用参数: {{\"image_type\": \"base64\", \"detect_direction\": true}}"),
            ("信息", f"{now} - 信息 - ℹ️ 程序启动成功，版本: 2.1.7"),
            ("信息", f"{now} - 信息 - ℹ️ 关键词匹配成功: 找到目标文本 '重要信息'"),
            ("警告", f"{now} - 警告 - ⚠️ API调用响应时间较长: 3.2秒"),
            ("警告", f"{now} - 警告 - ⚠️ 内存使用率较高: 85%"),
            ("错误", f"{now} - 错误 - ❌ OCR识别失败: 网络连接超时"),
            ("错误", f"{now} - 错误 - ❌ 配置文件读取错误: 文件格式不正确"),
            ("严重", f"{now} - 严重 - 🚨 系统内存不足，程序可能崩溃"),
            ("严重", f"{now} - 严重 - 🚨 API密钥验证失败，服务不可用")
        ]
        
        # 根据选择的级别过滤日志
        level_priority = {"调试": 0, "信息": 1, "警告": 2, "错误": 3, "严重": 4}
        current_priority = level_priority.get(level, 1)
        
        filtered_logs = []
        for log_level, log_msg in all_logs:
            if level_priority.get(log_level, 1) >= current_priority:
                filtered_logs.append(log_msg)
                
        if not filtered_logs:
            return f"当前级别 {level} 下暂无日志输出"
            
        return "\n".join(filtered_logs)
    
    def update_statistics(self):
        """更新日志统计信息"""
        try:
            current_level = self.level_combo.currentText()
            
            stats_info = {
                "调试": "📊 预计日志量: 很高 | 性能影响: 中等 | 适用场景: 开发调试",
                "信息": "📊 预计日志量: 中等 | 性能影响: 较低 | 适用场景: 日常使用",
                "警告": "📊 预计日志量: 较低 | 性能影响: 很低 | 适用场景: 生产监控",
                "错误": "📊 预计日志量: 低 | 性能影响: 最低 | 适用场景: 故障排查",
                "严重": "📊 预计日志量: 很低 | 性能影响: 最低 | 适用场景: 严重错误监控"
            }
            
            self.stats_label.setText(stats_info.get(current_level, "无统计信息"))
            
        except Exception as e:
            self.stats_label.setText(f"统计信息加载失败: {e}")
    
    def test_config(self):
        """测试配置"""
        try:
            validation = self.config_manager.validate_config()
            if validation['valid']:
                QMessageBox.information(self, "验证成功", "配置验证通过！\n\n✅ 所有设置都是有效的")
            else:
                issues = "\n".join([f"• {issue}" for issue in validation['issues']])
                warnings = "\n".join([f"• {warning}" for warning in validation['warnings']])
                msg = f"配置验证结果:\n\n❌ 问题:\n{issues}\n\n⚠️ 警告:\n{warnings}"
                QMessageBox.warning(self, "验证结果", msg)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"配置验证失败: {e}")
    
    def save_config(self):
        """保存配置"""
        try:
            self.config_manager.update_config(
                level=self.level_combo.currentText(),
                enable_console=self.console_check.isChecked(),
                enable_file=self.file_check.isChecked(),
                enable_rotation=self.rotation_check.isChecked(),
                max_file_size_mb=self.max_size_spin.value(),
                max_backup_files=self.backup_files_spin.value(),
                enable_async=self.async_check.isChecked()
            )
            
            # 保存自动刷新配置
            self.save_auto_refresh_config()
            
            QMessageBox.information(self, "成功", "✅ 日志配置已保存！\n\n新配置将在下次日志写入时生效。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"❌ 保存配置失败: {e}")
    
    # 新增功能方法
    def refresh_log_viewer(self):
        """刷新日志查看器"""
        # 调试日志 - 函数调用追踪
        enhanced_logger.debug_function_call(
            "refresh_log_viewer", 
            "log_management_dialog",
            context="刷新日志查看器内容"
        )
        
        try:
            with enhanced_logger.performance_monitor("日志查看器刷新"):
                logging.debug("开始刷新日志查看器")
                
        except Exception as e:
            enhanced_logger.error_with_traceback(
                f"刷新日志查看器失败: {e}",
                "log_management_dialog"
            )
            return
        try:
            log_files = self.get_log_files()
            if log_files:
                # 获取所有HTML文件
                html_files = [f for f in log_files if f.endswith('.html')]
                if html_files:
                    # 合并所有HTML文件的内容
                    all_content = []
                    for html_file in html_files:
                        file_content = self.extract_logs_from_html(html_file)
                        if file_content:
                            # 添加文件标识
                            file_name = os.path.basename(html_file)
                            all_content.append(f"\n=== {file_name} ===")
                            all_content.append(file_content)
                    
                    content = '\n'.join(all_content)
                else:
                    # 如果没有HTML文件，读取第一个文件
                    with open(log_files[0], 'r', encoding='utf-8') as f:
                        content = f.read()
                
                # 将内容分割成行并存储到filtered_logs中
                self.filtered_logs = content.split('\n')
                
                # 更新分页信息
                self.update_pagination()
                
                # 显示当前页
                self.display_current_page()
        except Exception as e:
            QMessageBox.warning(self, "警告", f"刷新日志失败: {e}")
    
    def clear_log_viewer(self):
        """清空日志查看器"""
        self.log_viewer.clear()
    
    def filter_logs(self, level):
        """根据级别过滤日志"""
        if level == "全部":
            self.refresh_log_viewer()
        else:
            try:
                # 如果filtered_logs不存在，先刷新
                if not hasattr(self, 'filtered_logs') or not self.filtered_logs:
                    self.refresh_log_viewer()
                    return
                
                # 从已解析的日志中过滤指定级别
                filtered_content = []
                for line in self.filtered_logs:
                    # 检查日志行是否包含指定级别
                    # 使用更精确的匹配，避免误匹配
                    if f"] {level}:" in line or f"] {level} " in line:
                        filtered_content.append(line)
                
                # 更新filtered_logs为过滤后的内容
                self.filtered_logs = filtered_content
                
                # 重置分页
                self.current_page = 1
                self.update_pagination()
                self.display_current_page()
                
            except Exception as e:
                QMessageBox.warning(self, "警告", f"过滤日志失败: {e}")
    
    def start_search(self):
        """开始搜索"""
        search_term = self.search_input.text().strip()
        if not search_term:
            QMessageBox.warning(self, "警告", "请输入搜索关键词")
            return
        
        log_files = self.get_log_files()
        if not log_files:
            QMessageBox.warning(self, "警告", "未找到日志文件")
            return
        
        self.search_progress.setVisible(True)
        self.search_progress.setValue(0)
        self.search_results.setRowCount(0)
        
        # 启动搜索线程
        self.search_thread = LogSearchThread(log_files, search_term)
        self.search_thread.progress_updated.connect(self.search_progress.setValue)
        self.search_thread.search_finished.connect(self.on_search_finished)
        self.search_thread.start()
    
    def on_search_finished(self, results):
        """搜索完成处理"""
        self.search_progress.setVisible(False)
        
        self.search_results.setRowCount(len(results))
        for i, result in enumerate(results):
            self.search_results.setItem(i, 0, QTableWidgetItem(result['file']))
            self.search_results.setItem(i, 1, QTableWidgetItem(str(result['line'])))
            self.search_results.setItem(i, 2, QTableWidgetItem(result['timestamp']))
            self.search_results.setItem(i, 3, QTableWidgetItem(result['content']))
        
        QMessageBox.information(self, "搜索完成", f"找到 {len(results)} 条匹配记录")
    
    def export_search_results(self):
        """导出搜索结果"""
        if self.search_results.rowCount() == 0:
            QMessageBox.warning(self, "警告", "没有搜索结果可导出")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出搜索结果", "search_results.csv", "CSV文件 (*.csv)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    # 写入表头
                    writer.writerow(["文件", "行号", "时间", "内容"])
                    
                    # 写入数据
                    for row in range(self.search_results.rowCount()):
                        row_data = []
                        for col in range(self.search_results.columnCount()):
                            item = self.search_results.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)
                
                QMessageBox.information(self, "成功", f"搜索结果已导出到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")
    
    def refresh_analytics(self):
        """刷新分析数据"""
        try:
            log_files = self.get_log_files()
            
            # 统计数据
            stats = {
                'total_logs': 0,
                'debug_count': 0,
                'info_count': 0,
                'warning_count': 0,
                'error_count': 0,
                'critical_count': 0,
                'total_size': 0,
                'files_count': len(log_files),
                'hourly_stats': {},
                'daily_stats': {},
                'recent_errors': []
            }
            
            # 分析每个日志文件
            for log_file in log_files:
                if os.path.exists(log_file):
                    stats['total_size'] += os.path.getsize(log_file)
                    
                    with open(log_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            
                            stats['total_logs'] += 1
                            
                            # 级别统计
                            if 'DEBUG' in line:
                                stats['debug_count'] += 1
                            elif 'INFO' in line:
                                stats['info_count'] += 1
                            elif 'WARNING' in line:
                                stats['warning_count'] += 1
                            elif 'ERROR' in line:
                                stats['error_count'] += 1
                                # 收集最近的错误
                                if len(stats['recent_errors']) < 10:
                                    stats['recent_errors'].append(line[:100] + '...' if len(line) > 100 else line)
                            elif 'CRITICAL' in line:
                                stats['critical_count'] += 1
                            
                            # 时间统计
                            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}):', line)
                            if timestamp_match:
                                date_str = timestamp_match.group(1)
                                hour_str = timestamp_match.group(2)
                                
                                # 按日统计
                                if date_str not in stats['daily_stats']:
                                    stats['daily_stats'][date_str] = 0
                                stats['daily_stats'][date_str] += 1
                                
                                # 按小时统计
                                if hour_str not in stats['hourly_stats']:
                                    stats['hourly_stats'][hour_str] = 0
                                stats['hourly_stats'][hour_str] += 1
            
            # 更新界面显示
            self.update_analytics_display(stats)
            
        except Exception as e:
            QMessageBox.warning(self, "警告", f"分析数据失败: {e}")
    
    def update_analytics_display(self, stats):
        """更新分析显示界面"""
        # 调试日志 - 函数调用追踪
        enhanced_logger.debug_function_call(
            "update_analytics_display", 
            "log_management_dialog",
            context=f"更新分析显示，总日志数: {stats.get('total_logs', 0)}"
        )
        
        try:
            with enhanced_logger.performance_monitor("分析显示更新"):
                logging.debug(f"更新分析显示界面，统计数据: {len(stats)} 项")
            # 基础统计
            self.total_logs_label.setText(f"总日志数: {stats['total_logs']:,}")
            self.error_count_label.setText(f"错误数: {stats['error_count']:,}")
            self.warning_count_label.setText(f"警告数: {stats['warning_count']:,}")
            self.file_size_label.setText(f"文件大小: {self.format_size(stats['total_size'])}")
            
            # 详细统计信息
            detail_text = f"""
📊 详细统计信息

📁 文件统计:
  • 日志文件数: {stats['files_count']}
  • 总文件大小: {self.format_size(stats['total_size'])}
  • 平均文件大小: {self.format_size(stats['total_size'] // max(stats['files_count'], 1))}

📈 级别分布:
  • DEBUG: {stats['debug_count']:,} ({self.get_percentage(stats['debug_count'], stats['total_logs']):.1f}%)
  • INFO: {stats['info_count']:,} ({self.get_percentage(stats['info_count'], stats['total_logs']):.1f}%)
  • WARNING: {stats['warning_count']:,} ({self.get_percentage(stats['warning_count'], stats['total_logs']):.1f}%)
  • ERROR: {stats['error_count']:,} ({self.get_percentage(stats['error_count'], stats['total_logs']):.1f}%)
  • CRITICAL: {stats['critical_count']:,} ({self.get_percentage(stats['critical_count'], stats['total_logs']):.1f}%)

⏰ 时间分布:
  • 活跃时段: {self.get_peak_hours(stats['hourly_stats'])}
  • 活跃日期: {self.get_peak_days(stats['daily_stats'])}

🚨 最近错误:
"""
            
            for i, error in enumerate(stats['recent_errors'][:5], 1):
                detail_text += f"  {i}. {error}\n"
            
            if len(stats['recent_errors']) > 5:
                detail_text += f"  ... 还有 {len(stats['recent_errors']) - 5} 个错误\n"
            
            # 更新详细信息显示
            if hasattr(self, 'analytics_detail_text'):
                self.analytics_detail_text.setPlainText(detail_text)
            
            # 生成简单的文本图表
            chart_text = self.generate_text_chart(stats)
            if hasattr(self, 'analytics_chart_text'):
                self.analytics_chart_text.setPlainText(chart_text)
            
            # 生成趋势分析
            trend_text = self.generate_trend_analysis(stats)
            if hasattr(self, 'trend_text'):
                self.trend_text.setPlainText(trend_text)
                
        except Exception as e:
            print(f"更新分析显示失败: {e}")
    
    def generate_trend_analysis(self, stats):
        """生成趋势分析"""
        trend_text = "📈 日志趋势分析\n\n"
        
        try:
            # 分析日志级别趋势
            total_logs = stats['total_logs']
            if total_logs > 0:
                error_rate = (stats['error_count'] / total_logs) * 100
                warning_rate = (stats['warning_count'] / total_logs) * 100
                
                trend_text += "🔍 健康状况评估:\n"
                if error_rate > 5:
                    trend_text += f"  ⚠️  错误率较高 ({error_rate:.1f}%)，建议重点关注\n"
                elif error_rate > 1:
                    trend_text += f"  ⚡ 错误率中等 ({error_rate:.1f}%)，需要监控\n"
                else:
                    trend_text += f"  ✅ 错误率较低 ({error_rate:.1f}%)，系统运行良好\n"
                
                if warning_rate > 10:
                    trend_text += f"  ⚠️  警告率较高 ({warning_rate:.1f}%)，建议优化\n"
                elif warning_rate > 5:
                    trend_text += f"  ⚡ 警告率中等 ({warning_rate:.1f}%)，可以改进\n"
                else:
                    trend_text += f"  ✅ 警告率较低 ({warning_rate:.1f}%)，表现良好\n"
            
            # 分析时间分布趋势
            if stats['hourly_stats']:
                trend_text += "\n⏰ 时间分布分析:\n"
                
                # 找出最活跃的时间段
                sorted_hours = sorted(stats['hourly_stats'].items(), key=lambda x: x[1], reverse=True)
                if sorted_hours:
                    peak_hour, peak_count = sorted_hours[0]
                    trend_text += f"  📊 最活跃时段: {peak_hour}时 ({peak_count:,} 条日志)\n"
                
                # 分析工作时间 vs 非工作时间
                work_hours_count = sum(count for hour, count in stats['hourly_stats'].items() 
                                     if 9 <= int(hour) <= 17)
                non_work_hours_count = sum(count for hour, count in stats['hourly_stats'].items() 
                                         if int(hour) < 9 or int(hour) > 17)
                
                if work_hours_count > 0 or non_work_hours_count > 0:
                    work_percentage = (work_hours_count / (work_hours_count + non_work_hours_count)) * 100
                    trend_text += f"  🕘 工作时间日志: {work_percentage:.1f}% ({work_hours_count:,} 条)\n"
                    trend_text += f"  🌙 非工作时间日志: {100-work_percentage:.1f}% ({non_work_hours_count:,} 条)\n"
            
            # 分析日期分布趋势
            if stats['daily_stats']:
                trend_text += "\n📅 日期分布分析:\n"
                
                sorted_days = sorted(stats['daily_stats'].items())
                if len(sorted_days) >= 2:
                    # 计算日志增长趋势
                    recent_days = sorted_days[-3:] if len(sorted_days) >= 3 else sorted_days
                    if len(recent_days) >= 2:
                        trend_direction = "增长" if recent_days[-1][1] > recent_days[0][1] else "下降"
                        trend_text += f"  📈 最近趋势: {trend_direction}\n"
                    
                    # 找出最活跃的日期
                    max_day = max(sorted_days, key=lambda x: x[1])
                    trend_text += f"  📊 最活跃日期: {max_day[0]} ({max_day[1]:,} 条日志)\n"
            
            # 文件大小分析
            if stats['file_details']:
                trend_text += "\n📁 文件分析:\n"
                
                # 找出最大的文件
                largest_file = max(stats['file_details'], key=lambda x: x['size'])
                trend_text += f"  📦 最大文件: {largest_file['name']} ({self.format_size(largest_file['size'])})\n"
                
                # 计算平均文件大小
                avg_size = stats['total_size'] // max(len(stats['file_details']), 1)
                trend_text += f"  📊 平均文件大小: {self.format_size(avg_size)}\n"
                
                # 分析文件数量
                file_count = len(stats['file_details'])
                if file_count > 10:
                    trend_text += f"  ⚠️  文件数量较多 ({file_count} 个)，建议定期清理\n"
                elif file_count > 5:
                    trend_text += f"  ⚡ 文件数量中等 ({file_count} 个)，可以管理\n"
                else:
                    trend_text += f"  ✅ 文件数量合理 ({file_count} 个)\n"
            
            # 提供建议
            trend_text += "\n💡 优化建议:\n"
            
            if stats['error_count'] > 0:
                trend_text += "  • 关注错误日志，及时修复问题\n"
            
            if stats['total_size'] > 100 * 1024 * 1024:  # 100MB
                trend_text += "  • 日志文件较大，建议启用日志轮转\n"
            
            if len(stats['file_details']) > 10:
                trend_text += "  • 日志文件过多，建议定期归档或清理\n"
            
            if stats['warning_count'] > stats['error_count'] * 5:
                trend_text += "  • 警告数量较多，建议优化代码减少警告\n"
            
            trend_text += "  • 定期监控日志趋势，及时发现异常\n"
            trend_text += "  • 建议设置日志告警，自动监控关键指标\n"
            
        except Exception as e:
            trend_text += f"\n❌ 趋势分析失败: {e}\n"
        
        return trend_text
    
    def get_percentage(self, count, total):
        """计算百分比"""
        return (count / max(total, 1)) * 100
    
    def get_peak_hours(self, hourly_stats):
        """获取活跃时段"""
        if not hourly_stats:
            return "无数据"
        
        sorted_hours = sorted(hourly_stats.items(), key=lambda x: x[1], reverse=True)
        top_hours = sorted_hours[:3]
        return ", ".join([f"{hour}时({count}条)" for hour, count in top_hours])
    
    def get_peak_days(self, daily_stats):
        """获取活跃日期"""
        if not daily_stats:
            return "无数据"
        
        sorted_days = sorted(daily_stats.items(), key=lambda x: x[1], reverse=True)
        top_days = sorted_days[:3]
        return ", ".join([f"{day}({count}条)" for day, count in top_days])
    
    def generate_text_chart(self, stats):
        """生成文本图表"""
        chart_text = "📊 日志级别分布图表\n\n"
        
        levels = [
            ('DEBUG', stats['debug_count']),
            ('INFO', stats['info_count']),
            ('WARNING', stats['warning_count']),
            ('ERROR', stats['error_count']),
            ('CRITICAL', stats['critical_count'])
        ]
        
        max_count = max([count for _, count in levels]) if levels else 1
        
        for level, count in levels:
            if max_count > 0:
                bar_length = int((count / max_count) * 40)  # 最大40个字符
                bar = '█' * bar_length + '░' * (40 - bar_length)
                percentage = self.get_percentage(count, stats['total_logs'])
                chart_text += f"{level:8} │{bar}│ {count:6,} ({percentage:5.1f}%)\n"
        
        chart_text += "\n" + "─" * 60 + "\n"
        chart_text += f"总计: {stats['total_logs']:,} 条日志\n"
        
        # 添加时间分布图表
        if stats['hourly_stats']:
            chart_text += "\n⏰ 24小时分布图表\n\n"
            max_hourly = max(stats['hourly_stats'].values()) if stats['hourly_stats'] else 1
            
            for hour in range(24):
                hour_str = f"{hour:02d}"
                count = stats['hourly_stats'].get(hour_str, 0)
                bar_length = int((count / max_hourly) * 20) if max_hourly > 0 else 0
                bar = '█' * bar_length + '░' * (20 - bar_length)
                chart_text += f"{hour_str}时 │{bar}│ {count:4,}\n"
        
        return chart_text
    
    def export_analytics_report(self):
        """导出分析报告"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出分析报告", 
                f"log_analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                "HTML文件 (*.html);;文本文件 (*.txt)"
            )
            
            if not file_path:
                return
            
            # 获取当前分析数据
            log_files = self.get_log_files()
            stats = self.get_analytics_stats(log_files)
            
            if file_path.endswith('.html'):
                self.export_html_report(file_path, stats)
            else:
                self.export_text_report(file_path, stats)
            
            QMessageBox.information(self, "成功", f"分析报告已导出到: {file_path}")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"导出报告失败: {e}")
    
    def get_analytics_stats(self, log_files):
        """获取分析统计数据"""
        stats = {
            'total_logs': 0,
            'debug_count': 0,
            'info_count': 0,
            'warning_count': 0,
            'error_count': 0,
            'critical_count': 0,
            'total_size': 0,
            'files_count': len(log_files),
            'hourly_stats': {},
            'daily_stats': {},
            'recent_errors': [],
            'file_details': []
        }
        
        for log_file in log_files:
            if os.path.exists(log_file):
                file_size = os.path.getsize(log_file)
                stats['total_size'] += file_size
                
                file_stats = {
                    'name': os.path.basename(log_file),
                    'path': log_file,
                    'size': file_size,
                    'modified': datetime.fromtimestamp(os.path.getmtime(log_file)).strftime('%Y-%m-%d %H:%M:%S'),
                    'log_count': 0
                }
                
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        stats['total_logs'] += 1
                        file_stats['log_count'] += 1
                        
                        # 级别统计
                        if 'DEBUG' in line:
                            stats['debug_count'] += 1
                        elif 'INFO' in line:
                            stats['info_count'] += 1
                        elif 'WARNING' in line:
                            stats['warning_count'] += 1
                        elif 'ERROR' in line:
                            stats['error_count'] += 1
                            if len(stats['recent_errors']) < 20:
                                stats['recent_errors'].append({
                                    'file': os.path.basename(log_file),
                                    'content': line[:200] + '...' if len(line) > 200 else line
                                })
                        elif 'CRITICAL' in line:
                            stats['critical_count'] += 1
                        
                        # 时间统计
                        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}):', line)
                        if timestamp_match:
                            date_str = timestamp_match.group(1)
                            hour_str = timestamp_match.group(2)
                            
                            if date_str not in stats['daily_stats']:
                                stats['daily_stats'][date_str] = 0
                            stats['daily_stats'][date_str] += 1
                            
                            if hour_str not in stats['hourly_stats']:
                                stats['hourly_stats'][hour_str] = 0
                            stats['hourly_stats'][hour_str] += 1
                
                stats['file_details'].append(file_stats)
        
        return stats
    
    def export_html_report(self, file_path, stats):
        """导出HTML格式报告"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>日志分析报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }}
        .stat-item {{ background: #f9f9f9; padding: 10px; border-radius: 3px; text-align: center; }}
        .chart {{ font-family: monospace; background: #f5f5f5; padding: 10px; border-radius: 3px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 日志分析报告</h1>
        <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="section">
        <h2>📈 基础统计</h2>
        <div class="stats-grid">
            <div class="stat-item">
                <h3>{stats['total_logs']:,}</h3>
                <p>总日志数</p>
            </div>
            <div class="stat-item">
                <h3>{stats['error_count']:,}</h3>
                <p>错误数</p>
            </div>
            <div class="stat-item">
                <h3>{stats['warning_count']:,}</h3>
                <p>警告数</p>
            </div>
            <div class="stat-item">
                <h3>{self.format_size(stats['total_size'])}</h3>
                <p>文件大小</p>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>📋 级别分布</h2>
        <table>
            <tr><th>级别</th><th>数量</th><th>百分比</th></tr>
            <tr><td>DEBUG</td><td>{stats['debug_count']:,}</td><td>{self.get_percentage(stats['debug_count'], stats['total_logs']):.1f}%</td></tr>
            <tr><td>INFO</td><td>{stats['info_count']:,}</td><td>{self.get_percentage(stats['info_count'], stats['total_logs']):.1f}%</td></tr>
            <tr><td>WARNING</td><td>{stats['warning_count']:,}</td><td>{self.get_percentage(stats['warning_count'], stats['total_logs']):.1f}%</td></tr>
            <tr><td>ERROR</td><td>{stats['error_count']:,}</td><td>{self.get_percentage(stats['error_count'], stats['total_logs']):.1f}%</td></tr>
            <tr><td>CRITICAL</td><td>{stats['critical_count']:,}</td><td>{self.get_percentage(stats['critical_count'], stats['total_logs']):.1f}%</td></tr>
        </table>
    </div>
    
    <div class="section">
        <h2>📁 文件详情</h2>
        <table>
            <tr><th>文件名</th><th>大小</th><th>日志数</th><th>修改时间</th></tr>"""
        
        for file_detail in stats['file_details']:
            html_content += f"""
            <tr>
                <td>{file_detail['name']}</td>
                <td>{self.format_size(file_detail['size'])}</td>
                <td>{file_detail['log_count']:,}</td>
                <td>{file_detail['modified']}</td>
            </tr>"""
        
        html_content += """
        </table>
    </div>
    
    <div class="section">
        <h2>🚨 最近错误</h2>
        <ul>"""
        
        for error in stats['recent_errors'][:10]:
            html_content += f"<li><strong>{error['file']}:</strong> {error['content']}</li>"
        
        html_content += """
        </ul>
    </div>
</body>
</html>"""
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def export_text_report(self, file_path, stats):
        """导出文本格式报告"""
        report_content = f"""
📊 日志分析报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'='*60}

📈 基础统计:
  总日志数: {stats['total_logs']:,}
  错误数: {stats['error_count']:,}
  警告数: {stats['warning_count']:,}
  文件大小: {self.format_size(stats['total_size'])}
  文件数量: {stats['files_count']}

📋 级别分布:
  DEBUG: {stats['debug_count']:,} ({self.get_percentage(stats['debug_count'], stats['total_logs']):.1f}%)
  INFO: {stats['info_count']:,} ({self.get_percentage(stats['info_count'], stats['total_logs']):.1f}%)
  WARNING: {stats['warning_count']:,} ({self.get_percentage(stats['warning_count'], stats['total_logs']):.1f}%)
  ERROR: {stats['error_count']:,} ({self.get_percentage(stats['error_count'], stats['total_logs']):.1f}%)
  CRITICAL: {stats['critical_count']:,} ({self.get_percentage(stats['critical_count'], stats['total_logs']):.1f}%)

📁 文件详情:
"""
        
        for file_detail in stats['file_details']:
            report_content += f"  {file_detail['name']}: {self.format_size(file_detail['size'])}, {file_detail['log_count']:,} 条日志\n"
        
        report_content += "\n🚨 最近错误:\n"
        for i, error in enumerate(stats['recent_errors'][:10], 1):
            report_content += f"  {i}. [{error['file']}] {error['content']}\n"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
    
    def show_alert_settings(self):
         """显示告警设置对话框"""
         dialog = QDialog(self)
         dialog.setWindowTitle("🔔 日志告警设置")
         dialog.setModal(True)
         dialog.resize(500, 400)
         
         layout = QVBoxLayout(dialog)
         
         # 告警规则设置
         rules_group = QGroupBox("📋 告警规则")
         rules_layout = QVBoxLayout()
         
         # 错误率告警
         error_layout = QHBoxLayout()
         error_layout.addWidget(QLabel("错误率超过:"))
         self.error_threshold_spin = QSpinBox()
         self.error_threshold_spin.setRange(1, 100)
         self.error_threshold_spin.setValue(5)
         self.error_threshold_spin.setSuffix("%")
         error_layout.addWidget(self.error_threshold_spin)
         error_layout.addWidget(QLabel("时触发告警"))
         error_layout.addStretch()
         rules_layout.addLayout(error_layout)
         
         # 文件大小告警
         size_layout = QHBoxLayout()
         size_layout.addWidget(QLabel("单个日志文件超过:"))
         self.size_threshold_spin = QSpinBox()
         self.size_threshold_spin.setRange(1, 1000)
         self.size_threshold_spin.setValue(100)
         self.size_threshold_spin.setSuffix(" MB")
         size_layout.addWidget(self.size_threshold_spin)
         size_layout.addWidget(QLabel("时触发告警"))
         size_layout.addStretch()
         rules_layout.addLayout(size_layout)
         
         # 关键词告警
         keyword_layout = QVBoxLayout()
         keyword_layout.addWidget(QLabel("关键词告警 (每行一个):"))
         self.keyword_text = QTextEdit()
         self.keyword_text.setMaximumHeight(80)
         self.keyword_text.setPlainText("CRITICAL\nFATAL\nOUT OF MEMORY")
         keyword_layout.addWidget(self.keyword_text)
         rules_layout.addLayout(keyword_layout)
         
         rules_group.setLayout(rules_layout)
         layout.addWidget(rules_group)
         
         # 通知设置
         notify_group = QGroupBox("📢 通知设置")
         notify_layout = QVBoxLayout()
         
         # 通知方式
         self.desktop_notify_check = QCheckBox("桌面通知")
         self.desktop_notify_check.setChecked(True)
         notify_layout.addWidget(self.desktop_notify_check)
         
         self.sound_notify_check = QCheckBox("声音提醒")
         notify_layout.addWidget(self.sound_notify_check)
         
         self.email_notify_check = QCheckBox("邮件通知")
         notify_layout.addWidget(self.email_notify_check)
         
         # 邮件设置
         email_layout = QGridLayout()
         email_layout.addWidget(QLabel("邮箱地址:"), 0, 0)
         self.email_input = QLineEdit()
         self.email_input.setPlaceholderText("admin@example.com")
         email_layout.addWidget(self.email_input, 0, 1)
         
         notify_layout.addLayout(email_layout)
         notify_group.setLayout(notify_layout)
         layout.addWidget(notify_group)
         
         # 监控设置
         monitor_group = QGroupBox("⏱️ 监控设置")
         monitor_layout = QVBoxLayout()
         
         interval_layout = QHBoxLayout()
         interval_layout.addWidget(QLabel("检查间隔:"))
         self.check_interval_spin = QSpinBox()
         self.check_interval_spin.setRange(1, 60)
         self.check_interval_spin.setValue(5)
         self.check_interval_spin.setSuffix(" 分钟")
         interval_layout.addWidget(self.check_interval_spin)
         interval_layout.addStretch()
         monitor_layout.addLayout(interval_layout)
         
         self.auto_monitor_check = QCheckBox("启用自动监控")
         monitor_layout.addWidget(self.auto_monitor_check)
         
         monitor_group.setLayout(monitor_layout)
         layout.addWidget(monitor_group)
         
         # 按钮
         button_layout = QHBoxLayout()
         
         test_btn = QPushButton("🧪 测试告警")
         test_btn.setDefault(False)
         test_btn.setAutoDefault(False)
         test_btn.clicked.connect(lambda: self.test_alert(dialog))
         button_layout.addWidget(test_btn)
         
         button_layout.addStretch()
         
         save_btn = QPushButton("💾 保存设置")
         save_btn.setDefault(False)
         save_btn.setAutoDefault(False)
         save_btn.clicked.connect(lambda: self.save_alert_settings(dialog))
         button_layout.addWidget(save_btn)
         
         cancel_btn = QPushButton("❌ 取消")
         cancel_btn.setDefault(False)
         cancel_btn.setAutoDefault(False)
         cancel_btn.clicked.connect(dialog.reject)
         button_layout.addWidget(cancel_btn)
         
         layout.addLayout(button_layout)
         
         # 加载现有设置
         self.load_alert_settings()
         
         dialog.exec()
     
    def load_alert_settings(self):
         """加载告警设置"""
         try:
             s = load_settings()
             alerts = s.get('log_alerts', {
                 'error_threshold': 5,
                 'size_threshold': 100,
                 'keywords': ['CRITICAL', 'FATAL', 'OUT OF MEMORY'],
                 'desktop_notify': s.get('enable_desktop_notify', False),
                 'sound_notify': False,
                 'email_notify': s.get('email_notification_enabled', False),
                 'email_address': s.get('recipient_email', ''),
                 'check_interval': 5,
                 'auto_monitor': False
             })

             self.error_threshold_spin.setValue(int(alerts.get('error_threshold', 5)))
             self.size_threshold_spin.setValue(int(alerts.get('size_threshold', 100)))

             kws = alerts.get('keywords') or []
             if isinstance(kws, list):
                 self.keyword_text.setPlainText("\n".join([str(k).strip() for k in kws if str(k).strip()]))
             else:
                 self.keyword_text.setPlainText(str(kws))

             self.desktop_notify_check.setChecked(bool(alerts.get('desktop_notify', s.get('enable_desktop_notify', False))))
             self.sound_notify_check.setChecked(bool(alerts.get('sound_notify', False)))
             self.email_notify_check.setChecked(bool(alerts.get('email_notify', s.get('email_notification_enabled', False))))
             self.email_input.setText(str(alerts.get('email_address', s.get('recipient_email', ''))))
             self.check_interval_spin.setValue(int(alerts.get('check_interval', 5)))
             self.auto_monitor_check.setChecked(bool(alerts.get('auto_monitor', False)))
         except Exception as e:
             print(f"加载告警设置失败: {e}")
     
    def save_alert_settings(self, dialog):
         """保存告警设置，并根据设置启动/停止自动监控"""
         try:
             alerts = {
                 'error_threshold': int(self.error_threshold_spin.value()),
                 'size_threshold': int(self.size_threshold_spin.value()),
                 'keywords': [k.strip() for k in self.keyword_text.toPlainText().strip().split('\n') if k.strip()],
                 'desktop_notify': bool(self.desktop_notify_check.isChecked()),
                 'sound_notify': bool(self.sound_notify_check.isChecked()),
                 'email_notify': bool(self.email_notify_check.isChecked()),
                 'email_address': self.email_input.text().strip(),
                 'check_interval': int(self.check_interval_spin.value()),
                 'auto_monitor': bool(self.auto_monitor_check.isChecked())
             }

             s = load_settings()
             s['log_alerts'] = alerts

             # 同步全局桌面通知开关以便系统托盘通知生效
             s['enable_desktop_notify'] = alerts['desktop_notify']

             # 可选：同步收件人邮箱（仅在提供时）
             if alerts['email_address']:
                 s['recipient_email'] = alerts['email_address']

             save_settings(s)

             # 根据设置启动或停止自动监控
             self.alert_check_interval_minutes = alerts['check_interval']
             if alerts['auto_monitor']:
                 self.start_alert_monitoring()
             else:
                 self.stop_alert_monitoring()

             QMessageBox.information(dialog, "成功", "告警设置已保存！")
             dialog.accept()
         except Exception as e:
             QMessageBox.warning(dialog, "错误", f"保存告警设置失败: {e}")

    def initialize_alert_monitor_from_settings(self):
         try:
             s = load_settings()
             alerts = s.get('log_alerts', {})
             self.alert_check_interval_minutes = int(alerts.get('check_interval', 5))
             if bool(alerts.get('auto_monitor', False)):
                 self.start_alert_monitoring()
             else:
                 self.stop_alert_monitoring()
         except Exception:
             # 安全忽略初始化失败
             self.stop_alert_monitoring()

    def start_alert_monitoring(self):
         try:
             interval_ms = max(1, int(self.alert_check_interval_minutes)) * 60 * 1000
             self.alert_monitor_timer.setInterval(interval_ms)
             if not self.alert_monitor_enabled:
                 self.alert_monitor_timer.start()
                 self.alert_monitor_enabled = True
         except Exception as e:
             logger.exception(f"启动告警监控失败: {e}")

    def stop_alert_monitoring(self):
         try:
             if self.alert_monitor_enabled:
                 self.alert_monitor_timer.stop()
                 self.alert_monitor_enabled = False
         except Exception as e:
             logger.exception(f"停止告警监控失败: {e}")

    def run_alert_checks(self):
         try:
             s = load_settings()
             alerts = s.get('log_alerts', {})
             if not alerts:
                 return

             error_threshold = int(alerts.get('error_threshold', 5))
             size_threshold_mb = int(alerts.get('size_threshold', 100))
             keywords = alerts.get('keywords') or []
             keywords = [str(k).strip().lower() for k in keywords if str(k).strip()]
             use_desktop = bool(alerts.get('desktop_notify', s.get('enable_desktop_notify', False)))
             use_sound = bool(alerts.get('sound_notify', False))
             use_email = bool(alerts.get('email_notify', False))

             log_files = self.get_log_files()

             total_lines = 0
             error_lines = 0
             matched_keywords = set()
             size_violations = []

             for fp in log_files:
                 try:
                     size_bytes = os.path.getsize(fp)
                     if size_bytes > size_threshold_mb * 1024 * 1024:
                         size_violations.append((os.path.basename(fp), size_bytes))

                     if fp.endswith('.html'):
                         content = self.extract_logs_from_html(fp)
                     else:
                         with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                             content = f.read()

                     lines = content.splitlines()
                     total_lines += len(lines)

                     for line in lines:
                         ll = line.lower()
                         # 错误级别判断（中英文）
                         if (' error' in ll) or ('严重' in ll) or ('critical' in ll) or ('fatal' in ll):
                             error_lines += 1
                         # 关键词匹配
                         for kw in keywords:
                             if kw and kw in ll:
                                 matched_keywords.add(kw)
                 except Exception as fe:
                     logger.debug(f"读取日志文件失败: {fp} | {fe}")

             error_rate = (error_lines / total_lines * 100) if total_lines > 0 else 0.0
             triggered = bool(size_violations or matched_keywords or (error_rate >= error_threshold))

             if not triggered:
                 return

             title = "日志告警触发"
             parts = []
             if error_rate >= error_threshold:
                 parts.append(f"错误率 {error_rate:.1f}% ≥ 阈值 {error_threshold}%")
             if matched_keywords:
                 parts.append("关键词: " + ", ".join(sorted(matched_keywords)))
             if size_violations:
                 sv = ", ".join([f"{name} 超过 {self.format_size(sz)}" for name, sz in size_violations])
                 parts.append(f"文件大小告警: {sv}")
             message = "；".join(parts)

             # 通知触发
             try:
                 if use_desktop:
                     self.desktop_notifier.show_notification(title, message)
             except Exception as de:
                 logger.debug(f"桌面通知失败: {de}")

             try:
                 if use_sound:
                     import winsound
                     beep_path = s.get('beep_path', os.path.join('assets', '7499.wav'))
                     if os.path.exists(beep_path):
                         winsound.PlaySound(beep_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                     else:
                         winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
             except Exception as se:
                 logger.debug(f"声音提醒失败: {se}")

             try:
                 if use_email and matched_keywords:
                     # 仅在存在关键词匹配时发送邮件，避免噪音
                     ocr_text = f"日志告警摘要：{message}"
                     log_path = log_files[0] if log_files else None
                     self.email_notifier.send_notification(list(matched_keywords), ocr_text, None, log_path)
             except Exception as ee:
                 logger.debug(f"邮件通知失败: {ee}")
         except Exception as e:
             logger.exception(f"执行告警检查失败: {e}")
     
    def test_alert(self, dialog):
         """测试告警功能"""
         try:
             # 模拟告警
             if self.desktop_notify_check.isChecked():
                 QMessageBox.information(dialog, "🔔 测试告警", 
                     "这是一个测试告警通知！\n\n"
                     "如果您看到此消息，说明桌面通知功能正常工作。")
             
             if self.sound_notify_check.isChecked():
                 # 这里可以播放系统提示音
                 import winsound
                 winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
             
         except Exception as e:
             QMessageBox.warning(dialog, "错误", f"测试告警失败: {e}")
     
    def show_help(self):
         """显示帮助信息"""
         help_dialog = QDialog(self)
         help_dialog.setWindowTitle("❓ 帮助信息")
         help_dialog.setModal(True)
         help_dialog.resize(600, 500)
         
         layout = QVBoxLayout(help_dialog)
         
         # 创建标签页
         tab_widget = QTabWidget()
         
         # 功能介绍标签页
         features_tab = QWidget()
         features_layout = QVBoxLayout(features_tab)
         
         features_text = QTextEdit()
         features_text.setReadOnly(True)
         features_text.setHtml("""
         <h2>🚀 功能介绍</h2>
         
         <h3>📊 配置管理</h3>
         <ul>
             <li><b>日志级别设置:</b> 配置应用程序的日志输出级别</li>
             <li><b>输出选项:</b> 选择日志输出到控制台和/或文件</li>
             <li><b>文件配置:</b> 设置日志文件路径、大小限制等</li>
             <li><b>高级选项:</b> 配置异步写入、缓冲区大小等</li>
         </ul>
         
         <h3>👁️ 日志查看器</h3>
         <ul>
             <li><b>实时查看:</b> 实时显示最新的日志内容</li>
             <li><b>语法高亮:</b> 不同级别的日志使用不同颜色显示</li>
             <li><b>过滤功能:</b> 按级别、关键词过滤日志</li>
             <li><b>导出功能:</b> 将日志导出为多种格式</li>
         </ul>
         
         <h3>🔍 搜索功能</h3>
         <ul>
             <li><b>关键词搜索:</b> 在日志中搜索特定关键词</li>
             <li><b>正则表达式:</b> 支持正则表达式搜索</li>
             <li><b>时间范围:</b> 按时间范围筛选搜索结果</li>
             <li><b>结果导出:</b> 导出搜索结果</li>
         </ul>
         
         <h3>📈 分析统计</h3>
         <ul>
             <li><b>统计图表:</b> 显示日志级别分布、时间分布等</li>
             <li><b>趋势分析:</b> 分析日志趋势和系统健康状况</li>
             <li><b>报告导出:</b> 生成详细的分析报告</li>
         </ul>
         
         <h3>🗂️ 文件管理</h3>
         <ul>
             <li><b>文件清理:</b> 清理过期的日志文件</li>
             <li><b>文件归档:</b> 将旧日志文件压缩归档</li>
             <li><b>空间管理:</b> 监控磁盘空间使用情况</li>
         </ul>
         
         <h3>🔔 告警通知</h3>
         <ul>
             <li><b>智能告警:</b> 基于错误率、文件大小等指标的告警</li>
             <li><b>关键词监控:</b> 监控特定关键词的出现</li>
             <li><b>多种通知:</b> 支持桌面通知、邮件通知等</li>
         </ul>
         """)
         
         features_layout.addWidget(features_text)
         tab_widget.addTab(features_tab, "功能介绍")
         
         # 使用技巧标签页
         tips_tab = QWidget()
         tips_layout = QVBoxLayout(tips_tab)
         
         tips_text = QTextEdit()
         tips_text.setReadOnly(True)
         tips_text.setHtml("""
         <h2>💡 使用技巧</h2>
         
         <h3>🎯 最佳实践</h3>
         <ul>
             <li><b>合理设置日志级别:</b> 生产环境建议使用 INFO 或 WARNING 级别</li>
             <li><b>定期清理日志:</b> 避免日志文件占用过多磁盘空间</li>
             <li><b>启用日志轮转:</b> 设置合理的文件大小限制</li>
             <li><b>监控关键指标:</b> 关注错误率、警告数量等</li>
         </ul>
         
         <h3>🔧 性能优化</h3>
         <ul>
             <li><b>异步写入:</b> 在高并发场景下启用异步写入</li>
             <li><b>缓冲区设置:</b> 适当增加缓冲区大小提高性能</li>
             <li><b>文件分割:</b> 避免单个日志文件过大</li>
         </ul>
         
         <h3>🚨 故障排查</h3>
         <ul>
             <li><b>查看错误日志:</b> 优先关注 ERROR 和 CRITICAL 级别</li>
             <li><b>时间关联分析:</b> 结合时间戳分析问题发生时间</li>
             <li><b>关键词搜索:</b> 使用关键词快速定位问题</li>
             <li><b>趋势分析:</b> 观察错误趋势判断问题严重程度</li>
         </ul>
         
         <h3>📊 数据分析</h3>
         <ul>
             <li><b>定期生成报告:</b> 定期导出分析报告了解系统状况</li>
             <li><b>对比分析:</b> 对比不同时间段的日志数据</li>
             <li><b>告警设置:</b> 设置合理的告警阈值</li>
         </ul>
         """)
         
         tips_layout.addWidget(tips_text)
         tab_widget.addTab(tips_tab, "使用技巧")
         
         # 快捷键标签页
         shortcuts_tab = QWidget()
         shortcuts_layout = QVBoxLayout(shortcuts_tab)
         
         shortcuts_text = QTextEdit()
         shortcuts_text.setReadOnly(True)
         shortcuts_text.setHtml("""
         <h2>⌨️ 快捷键</h2>
         
         <table border="1" cellpadding="5" cellspacing="0" style="width:100%">
             <tr style="background-color:#f0f0f0">
                 <th>功能</th>
                 <th>快捷键</th>
                 <th>说明</th>
             </tr>
             <tr>
                 <td>刷新日志</td>
                 <td>F5</td>
                 <td>刷新当前查看的日志内容</td>
             </tr>
             <tr>
                 <td>搜索</td>
                 <td>Ctrl+F</td>
                 <td>打开搜索功能</td>
             </tr>
             <tr>
                 <td>导出</td>
                 <td>Ctrl+E</td>
                 <td>导出当前日志或搜索结果</td>
             </tr>
             <tr>
                 <td>清理</td>
                 <td>Ctrl+D</td>
                 <td>打开日志清理功能</td>
             </tr>
             <tr>
                 <td>设置</td>
                 <td>Ctrl+,</td>
                 <td>打开配置设置</td>
             </tr>
             <tr>
                 <td>帮助</td>
                 <td>F1</td>
                 <td>显示帮助信息</td>
             </tr>
             <tr>
                 <td>关闭</td>
                 <td>Esc</td>
                 <td>关闭当前对话框</td>
             </tr>
         </table>
         
         <h3>📝 文本编辑快捷键</h3>
         <ul>
             <li><b>Ctrl+A:</b> 全选文本</li>
             <li><b>Ctrl+C:</b> 复制选中文本</li>
             <li><b>Ctrl+V:</b> 粘贴文本</li>
             <li><b>Ctrl+Z:</b> 撤销操作</li>
             <li><b>Ctrl+Y:</b> 重做操作</li>
         </ul>
         """)
         
         shortcuts_layout.addWidget(shortcuts_text)
         tab_widget.addTab(shortcuts_tab, "快捷键")
         
         layout.addWidget(tab_widget)
         
         # 关闭按钮
         close_btn = QPushButton("关闭")
         close_btn.setDefault(False)
         close_btn.setAutoDefault(False)
         close_btn.clicked.connect(help_dialog.accept)
         layout.addWidget(close_btn)
         
         help_dialog.exec()
     
    def toggle_syntax_highlight(self, enabled):
         """切换语法高亮"""
         if enabled:
             if not hasattr(self, 'highlighter'):
                 self.highlighter = LogHighlighter(self.log_viewer.document())
         else:
             if hasattr(self, 'highlighter'):
                 self.highlighter.setDocument(None)
                 delattr(self, 'highlighter')
     
    def change_page_size(self, size_text):
         """改变每页显示的行数"""
         try:
             if size_text == "全部":
                 self.page_size = len(self.filtered_logs) if self.filtered_logs else 1000
             else:
                 self.page_size = int(size_text)
             
             self.current_page = 1
             self.update_pagination()
             self.display_current_page()
         except Exception as e:
             print(f"改变页面大小失败: {e}")
     
    def search_in_viewer(self, text):
        """在查看器中搜索"""
        if not text:
            self.search_matches = []
            self.current_match = -1
            self.search_count_label.setText("0/0")
            return

        try:
            import re

            # 获取搜索选项
            case_sensitive = self.case_sensitive_check.isChecked()
            use_regex = self.regex_search_check.isChecked()

            # 清除之前的搜索结果
            self.search_matches = []

            # 获取文档内容
            document = self.log_viewer.document()

            if use_regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                pattern = re.compile(text, flags)

            # 搜索匹配项
            cursor = QTextCursor(document)
            while not cursor.isNull() and not cursor.atEnd():
                if use_regex:
                    # 正则表达式搜索
                    block = cursor.block()
                    block_text = block.text()
                    if pattern.search(block_text):
                        self.search_matches.append(cursor.position())
                else:
                    # 普通文本搜索
                    flags = QTextDocument.FindFlag(0)
                    if case_sensitive:
                        flags |= QTextDocument.FindFlag.FindCaseSensitively

                    found_cursor = document.find(text, cursor, flags)
                    if not found_cursor.isNull():
                        self.search_matches.append(found_cursor.selectionStart())
                        cursor = found_cursor
                    else:
                        break

                cursor.movePosition(QTextCursor.MoveOperation.NextCharacter)

            # 更新搜索计数
            self.current_match = 0 if self.search_matches else -1
            self.search_count_label.setText(f"{len(self.search_matches)}/0" if self.search_matches else "0/0")

            # 高亮第一个匹配项
            if self.search_matches:
                self.highlight_current_match()

        except Exception as e:
            print(f"搜索失败: {e}")
     
    def find_next(self):
         """查找下一个匹配项"""
         if not self.search_matches:
             return
         
         self.current_match = (self.current_match + 1) % len(self.search_matches)
         self.highlight_current_match()
         self.search_count_label.setText(f"{len(self.search_matches)}/{self.current_match + 1}")
     
    def find_previous(self):
         """查找上一个匹配项"""
         if not self.search_matches:
             return
         
         self.current_match = (self.current_match - 1) % len(self.search_matches)
         self.highlight_current_match()
         self.search_count_label.setText(f"{len(self.search_matches)}/{self.current_match + 1}")
     
    def highlight_current_match(self):
         """高亮当前匹配项"""
         if self.current_match < 0 or self.current_match >= len(self.search_matches):
             return
         
         position = self.search_matches[self.current_match]
         cursor = self.log_viewer.textCursor()
         cursor.setPosition(position)
         
         # 选择匹配的文本
         search_text = self.viewer_search_input.text()
         cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, 
                           QTextCursor.MoveMode.KeepAnchor, len(search_text))
         
         self.log_viewer.setTextCursor(cursor)
         self.log_viewer.ensureCursorVisible()
     
    def go_to_first_page(self):
        """跳转到首页"""
        if self.page_size_combo.currentText() == "全部":
            return
        self.current_page = 1
        self.display_current_page()
        self.update_pagination_buttons()
    
    def go_to_prev_page(self):
        """跳转到上一页"""
        if self.page_size_combo.currentText() == "全部":
            return
        if self.current_page > 1:
            self.current_page -= 1
            self.display_current_page()
            self.update_pagination_buttons()
    
    def go_to_next_page(self):
        """跳转到下一页"""
        if self.page_size_combo.currentText() == "全部":
            return
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.display_current_page()
            self.update_pagination_buttons()
    
    def go_to_last_page(self):
        """跳转到末页"""
        if self.page_size_combo.currentText() == "全部":
            return
        self.current_page = self.total_pages
        self.display_current_page()
        self.update_pagination_buttons()
     
    def go_to_page(self):
        """跳转到指定页"""
        try:
            # 检查是否为"全部"模式
            if self.page_size_combo.currentText() == "全部":
                QMessageBox.information(self, "提示", "当前为显示全部模式，无需分页跳转")
                return
            
            page = int(self.page_input.text())
            if 1 <= page <= self.total_pages:
                self.current_page = page
                self.display_current_page()
                self.update_pagination_buttons()
            else:
                QMessageBox.warning(self, "错误", f"页码必须在 1 到 {self.total_pages} 之间")
        except ValueError:
            QMessageBox.warning(self, "错误", "请输入有效的页码")
     
    def update_pagination(self):
         """更新分页信息"""
         if self.page_size_combo.currentText() == "全部":
             self.total_pages = 1
         else:
             total_logs = len(self.filtered_logs)
             self.total_pages = max(1, (total_logs + self.page_size - 1) // self.page_size)
         
         if self.current_page > self.total_pages:
             self.current_page = self.total_pages
         
         self.update_pagination_buttons()
     
    def update_pagination_buttons(self):
         """更新分页按钮状态"""
         self.first_page_btn.setEnabled(self.current_page > 1)
         self.prev_page_btn.setEnabled(self.current_page > 1)
         self.next_page_btn.setEnabled(self.current_page < self.total_pages)
         self.last_page_btn.setEnabled(self.current_page < self.total_pages)
         
         self.page_info_label.setText(f"第 {self.current_page} 页，共 {self.total_pages} 页")
     
    def display_current_page(self):
         """显示当前页的日志"""
         try:
             if self.page_size_combo.currentText() == "全部":
                 # 显示所有日志
                 logs_to_show = self.filtered_logs
             else:
                 # 分页显示
                 start_idx = (self.current_page - 1) * self.page_size
                 end_idx = start_idx + self.page_size
                 logs_to_show = self.filtered_logs[start_idx:end_idx]
             
             # 清空并显示日志
             self.log_viewer.clear()
             for log_line in logs_to_show:
                 self.log_viewer.append(log_line)
             
             # 自动滚动到底部
             if self.auto_scroll_check.isChecked():
                 scrollbar = self.log_viewer.verticalScrollBar()
                 scrollbar.setValue(scrollbar.maximum())
         
         except Exception as e:
             print(f"显示当前页失败: {e}")
    
    def export_viewer_logs(self):
        """导出查看器中的日志"""
        if not hasattr(self, 'filtered_logs') or not self.filtered_logs:
            QMessageBox.warning(self, "警告", "没有日志内容可导出")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", "", "文本文件 (*.txt);;CSV文件 (*.csv)"
        )
        
        if file_path:
            try:
                if file_path.endswith('.csv'):
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(['行号', '内容'])
                        for i, line in enumerate(self.filtered_logs, 1):
                            writer.writerow([i, line])
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(self.filtered_logs))
                
                QMessageBox.information(self, "成功", f"日志已导出到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
    
    def toggle_auto_scroll(self, enabled):
        """切换自动滚动"""
        try:
            if enabled and hasattr(self, 'filtered_logs') and self.filtered_logs:
                # 跳转到最后一页
                if self.page_size_combo.currentText() != "全部":
                    total_pages = (len(self.filtered_logs) - 1) // self.page_size + 1
                    self.current_page = total_pages
                    self.update_pagination()
                self.display_current_page()
        except Exception as e:
            print(f"切换自动滚动失败: {e}")
     
    def refresh_file_list(self):
        """刷新文件列表"""
        try:
            log_files = self.get_log_files()
            self.log_files_table.setRowCount(len(log_files))
            
            for i, log_file in enumerate(log_files):
                if os.path.exists(log_file):
                    file_name = os.path.basename(log_file)
                    file_size = self.format_size(os.path.getsize(log_file))
                    mod_time = datetime.fromtimestamp(os.path.getmtime(log_file)).strftime('%Y-%m-%d %H:%M:%S')
                    
                    self.log_files_table.setItem(i, 0, QTableWidgetItem(file_name))
                    self.log_files_table.setItem(i, 1, QTableWidgetItem(file_size))
                    self.log_files_table.setItem(i, 2, QTableWidgetItem(mod_time))
        except Exception as e:
            QMessageBox.warning(self, "警告", f"刷新文件列表失败: {e}")
    
    def open_log_folder(self):
        """打开日志文件夹"""
        try:
            log_dir = os.path.join(os.getcwd(), "logs")
            if os.path.exists(log_dir):
                os.startfile(log_dir)
            else:
                QMessageBox.warning(self, "警告", "日志文件夹不存在")
        except Exception as e:
            QMessageBox.warning(self, "警告", f"打开文件夹失败: {e}")
    
    def export_logs(self):
        """高级日志导出"""
        # 调试日志 - 函数调用追踪
        enhanced_logger.debug_function_call(
            "export_logs", 
            "log_management_dialog",
            context="导出日志文件"
        )
        
        try:
            with enhanced_logger.performance_monitor("日志导出"):
                logging.debug("开始导出日志文件")
            log_files = self.get_log_files()
            if not log_files:
                QMessageBox.warning(self, "警告", "没有日志文件可导出")
                return
            
            # 创建导出选项对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("导出日志")
            dialog.setFixedSize(400, 300)
            
            layout = QVBoxLayout(dialog)
            
            # 导出格式选择
            format_group = QGroupBox("导出格式")
            format_layout = QVBoxLayout(format_group)
            
            format_combo = QComboBox()
            format_combo.addItems(["原始格式 (.log/.html)", "CSV格式 (.csv)", "JSON格式 (.json)", "XML格式 (.xml)", "纯文本 (.txt)"])
            format_layout.addWidget(format_combo)
            
            layout.addWidget(format_group)
            
            # 过滤选项
            filter_group = QGroupBox("过滤选项")
            filter_layout = QVBoxLayout(filter_group)
            
            level_filter = QComboBox()
            level_filter.addItems(["全部级别", "错误", "警告", "信息", "调试"])
            filter_layout.addWidget(QLabel("日志级别:"))
            filter_layout.addWidget(level_filter)
            
            # 日期范围
            date_layout = QHBoxLayout()
            start_date = QDateEdit()
            start_date.setDate(QDate.currentDate().addDays(-7))
            end_date = QDateEdit()
            end_date.setDate(QDate.currentDate())
            
            date_layout.addWidget(QLabel("开始日期:"))
            date_layout.addWidget(start_date)
            date_layout.addWidget(QLabel("结束日期:"))
            date_layout.addWidget(end_date)
            filter_layout.addLayout(date_layout)
            
            layout.addWidget(filter_group)
            
            # 按钮
            button_layout = QHBoxLayout()
            export_btn = QPushButton("导出")
            cancel_btn = QPushButton("取消")
            
            button_layout.addWidget(export_btn)
            button_layout.addWidget(cancel_btn)
            layout.addLayout(button_layout)
            
            # 连接信号
            export_btn.clicked.connect(lambda: self.perform_export(
                dialog, format_combo.currentText(), level_filter.currentText(),
                start_date.date(), end_date.date()
            ))
            cancel_btn.clicked.connect(dialog.reject)
            
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {e}")
    
    def perform_export(self, dialog, export_format, level_filter, start_date, end_date):
        """执行导出操作"""
        try:
            # 选择保存位置
            if "原始格式" in export_format:
                export_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
                if not export_dir:
                    return
                self.export_original_format(export_dir)
            else:
                # 获取文件扩展名
                ext_map = {
                    "CSV格式": ".csv",
                    "JSON格式": ".json", 
                    "XML格式": ".xml",
                    "纯文本": ".txt"
                }
                ext = ext_map.get(export_format.split(" ")[0] + "格式", ".txt")
                
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "保存导出文件", f"logs_export{ext}",
                    f"{export_format} (*{ext})"
                )
                
                if file_path:
                    self.export_formatted_logs(
                        file_path, export_format, level_filter, 
                        start_date.toPython(), end_date.toPython()
                    )
            
            dialog.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {e}")
    
    def export_original_format(self, export_dir):
        """导出原始格式日志"""
        import shutil
        log_files = self.get_log_files()
        
        for log_file in log_files:
            if os.path.exists(log_file):
                dest_file = os.path.join(export_dir, os.path.basename(log_file))
                shutil.copy2(log_file, dest_file)
        
        QMessageBox.information(self, "成功", f"已导出 {len(log_files)} 个日志文件到: {export_dir}")
    
    def export_formatted_logs(self, file_path, export_format, level_filter, start_date, end_date):
        """导出格式化日志"""
        import json
        import xml.etree.ElementTree as ET
        from xml.dom import minidom
        
        log_files = self.get_log_files()
        all_logs = []
        
        # 收集日志数据
        for log_file in log_files:
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        
                        # 级别过滤
                        if level_filter != "全部级别" and level_filter not in line:
                            continue
                        
                        # 解析日志条目
                        log_entry = self.parse_log_line(line, os.path.basename(log_file), line_num)
                        
                        # 日期过滤
                        if log_entry.get('timestamp'):
                            try:
                                log_date = datetime.strptime(log_entry['timestamp'][:10], '%Y-%m-%d').date()
                                if not (start_date <= log_date <= end_date):
                                    continue
                            except:
                                pass
                        
                        all_logs.append(log_entry)
        
        # 根据格式导出
        if "CSV" in export_format:
            self.export_to_csv(file_path, all_logs)
        elif "JSON" in export_format:
            self.export_to_json(file_path, all_logs)
        elif "XML" in export_format:
            self.export_to_xml(file_path, all_logs)
        elif "纯文本" in export_format:
            self.export_to_txt(file_path, all_logs)
        
        QMessageBox.information(self, "成功", f"已导出 {len(all_logs)} 条日志记录到: {file_path}")
    
    def parse_log_line(self, line, filename, line_num):
        """解析日志行"""
        # 尝试解析时间戳和级别
        import re
        
        # 匹配时间戳模式
        timestamp_pattern = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})'
        level_pattern = r'(调试|信息|警告|错误|严重)'
        
        timestamp_match = re.search(timestamp_pattern, line)
        level_match = re.search(level_pattern, line)
        
        return {
            'file': filename,
            'line': line_num,
            'timestamp': timestamp_match.group(1) if timestamp_match else '',
            'level': level_match.group(1) if level_match else 'UNKNOWN',
            'content': line
        }
    
    def export_to_csv(self, file_path, logs):
        """导出为CSV格式"""
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['文件', '行号', '时间戳', '级别', '内容'])
            
            for log in logs:
                writer.writerow([
                    log['file'], log['line'], log['timestamp'], 
                    log['level'], log['content']
                ])
    
    def export_to_json(self, file_path, logs):
        """导出为JSON格式"""
        import json
        
        export_data = {
            'export_time': datetime.now().isoformat(),
            'total_logs': len(logs),
            'logs': logs
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    def export_to_xml(self, file_path, logs):
        """导出为XML格式"""
        import xml.etree.ElementTree as ET
        from xml.dom import minidom
        
        root = ET.Element('logs')
        root.set('export_time', datetime.now().isoformat())
        root.set('total_logs', str(len(logs)))
        
        for log in logs:
            log_elem = ET.SubElement(root, 'log')
            
            file_elem = ET.SubElement(log_elem, 'file')
            file_elem.text = log['file']
            
            line_elem = ET.SubElement(log_elem, 'line')
            line_elem.text = str(log['line'])
            
            timestamp_elem = ET.SubElement(log_elem, 'timestamp')
            timestamp_elem.text = log['timestamp']
            
            level_elem = ET.SubElement(log_elem, 'level')
            level_elem.text = log['level']
            
            content_elem = ET.SubElement(log_elem, 'content')
            content_elem.text = log['content']
        
        # 格式化XML
        rough_string = ET.tostring(root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(reparsed.toprettyxml(indent='  '))
    
    def export_to_txt(self, file_path, logs):
        """导出为纯文本格式"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"日志导出报告\n")
            f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"总记录数: {len(logs)}\n")
            f.write("=" * 80 + "\n\n")
            
            for log in logs:
                f.write(f"文件: {log['file']} | 行号: {log['line']} | 时间: {log['timestamp']} | 级别: {log['level']}\n")
                f.write(f"内容: {log['content']}\n")
                f.write("-" * 80 + "\n")
    
    def cleanup_logs(self):
        """高级日志清理和归档"""
        try:
            # 创建清理选项对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("日志清理和归档")
            dialog.setFixedSize(450, 400)
            
            layout = QVBoxLayout(dialog)
            
            # 清理选项
            cleanup_group = QGroupBox("清理选项")
            cleanup_layout = QVBoxLayout(cleanup_group)
            
            # 保留天数
            days_layout = QHBoxLayout()
            days_layout.addWidget(QLabel("保留天数:"))
            keep_days = QSpinBox()
            keep_days.setRange(1, 365)
            keep_days.setValue(self.keep_days_spin.value())
            days_layout.addWidget(keep_days)
            days_layout.addWidget(QLabel("天"))
            cleanup_layout.addLayout(days_layout)
            
            # 清理选项
            delete_old_cb = QCheckBox("删除过期日志文件")
            delete_old_cb.setChecked(True)
            cleanup_layout.addWidget(delete_old_cb)
            
            archive_old_cb = QCheckBox("归档过期日志文件")
            cleanup_layout.addWidget(archive_old_cb)
            
            compress_cb = QCheckBox("压缩归档文件")
            cleanup_layout.addWidget(compress_cb)
            
            layout.addWidget(cleanup_group)
            
            # 归档选项
            archive_group = QGroupBox("归档选项")
            archive_layout = QVBoxLayout(archive_group)
            
            # 归档目录
            archive_dir_layout = QHBoxLayout()
            archive_dir_layout.addWidget(QLabel("归档目录:"))
            archive_dir_edit = QLineEdit()
            archive_dir_edit.setText(os.path.join(os.getcwd(), "logs", "archive"))
            archive_dir_layout.addWidget(archive_dir_edit)
            
            browse_btn = QPushButton("浏览")
            browse_btn.clicked.connect(lambda: self.browse_archive_dir(archive_dir_edit))
            archive_dir_layout.addWidget(browse_btn)
            archive_layout.addLayout(archive_dir_layout)
            
            # 归档格式
            format_layout = QHBoxLayout()
            format_layout.addWidget(QLabel("归档格式:"))
            archive_format = QComboBox()
            archive_format.addItems(["ZIP压缩", "TAR.GZ压缩", "原始文件"])
            format_layout.addWidget(archive_format)
            archive_layout.addLayout(format_layout)
            
            layout.addWidget(archive_group)
            
            # 预览信息
            preview_group = QGroupBox("清理预览")
            preview_layout = QVBoxLayout(preview_group)
            
            preview_text = QTextEdit()
            preview_text.setMaximumHeight(100)
            preview_text.setReadOnly(True)
            preview_layout.addWidget(preview_text)
            
            # 更新预览
            def update_preview():
                try:
                    log_files = self.get_log_files()
                    cutoff_date = datetime.now() - timedelta(days=keep_days.value())
                    
                    old_files = []
                    total_size = 0
                    
                    for log_file in log_files:
                        if os.path.exists(log_file):
                            file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
                            if file_time < cutoff_date:
                                old_files.append(log_file)
                                total_size += os.path.getsize(log_file)
                    
                    preview_info = f"找到 {len(old_files)} 个过期文件\n"
                    preview_info += f"总大小: {self.format_size(total_size)}\n"
                    preview_info += f"文件列表:\n"
                    
                    for file in old_files[:10]:  # 只显示前10个
                        preview_info += f"  - {os.path.basename(file)}\n"
                    
                    if len(old_files) > 10:
                        preview_info += f"  ... 还有 {len(old_files) - 10} 个文件"
                    
                    preview_text.setPlainText(preview_info)
                    
                except Exception as e:
                    preview_text.setPlainText(f"预览失败: {e}")
            
            keep_days.valueChanged.connect(update_preview)
            update_preview()  # 初始预览
            
            layout.addWidget(preview_group)
            
            # 按钮
            button_layout = QHBoxLayout()
            start_btn = QPushButton("开始清理")
            start_btn.setDefault(False)
            start_btn.setAutoDefault(False)
            cancel_btn = QPushButton("取消")
            cancel_btn.setDefault(False)
            cancel_btn.setAutoDefault(False)
            
            button_layout.addWidget(start_btn)
            button_layout.addWidget(cancel_btn)
            layout.addLayout(button_layout)
            
            # 连接信号
            start_btn.clicked.connect(lambda: self.perform_cleanup(
                dialog, keep_days.value(), delete_old_cb.isChecked(),
                archive_old_cb.isChecked(), compress_cb.isChecked(),
                archive_dir_edit.text(), archive_format.currentText()
            ))
            cancel_btn.clicked.connect(dialog.reject)
            
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"清理失败: {e}")
    
    def browse_archive_dir(self, line_edit):
        """浏览归档目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择归档目录")
        if dir_path:
            line_edit.setText(dir_path)
    
    def perform_cleanup(self, dialog, keep_days, delete_old, archive_old, compress_archive, archive_dir, archive_format):
        """执行清理操作"""
        try:
            log_files = self.get_log_files()
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            
            old_files = []
            for log_file in log_files:
                if os.path.exists(log_file):
                    file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
                    if file_time < cutoff_date:
                        old_files.append(log_file)
            
            if not old_files:
                QMessageBox.information(self, "清理完成", "没有找到需要清理的文件")
                dialog.accept()
                return
            
            # 确认操作
            action_text = []
            if delete_old:
                action_text.append("删除")
            if archive_old:
                action_text.append("归档")
            
            reply = QMessageBox.question(
                self, "确认清理",
                f"确定要{'/'.join(action_text)} {len(old_files)} 个过期日志文件吗？\n\n此操作不可撤销！",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            processed_count = 0
            
            # 归档文件
            if archive_old:
                os.makedirs(archive_dir, exist_ok=True)
                
                if "ZIP" in archive_format:
                    processed_count += self.archive_to_zip(old_files, archive_dir)
                elif "TAR" in archive_format:
                    processed_count += self.archive_to_tar(old_files, archive_dir)
                else:
                    processed_count += self.archive_original(old_files, archive_dir)
            
            # 删除文件
            if delete_old:
                for log_file in old_files:
                    if os.path.exists(log_file):
                        os.remove(log_file)
                        processed_count += 1
            
            QMessageBox.information(self, "清理完成", f"已处理 {processed_count} 个文件")
            self.refresh_file_list()
            dialog.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"清理失败: {e}")
    
    def archive_to_zip(self, files, archive_dir):
        """归档到ZIP文件"""
        import zipfile
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_path = os.path.join(archive_dir, f"logs_archive_{timestamp}.zip")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files:
                if os.path.exists(file_path):
                    zipf.write(file_path, os.path.basename(file_path))
        
        return len(files)
    
    def archive_to_tar(self, files, archive_dir):
        """归档到TAR.GZ文件"""
        import tarfile
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        tar_path = os.path.join(archive_dir, f"logs_archive_{timestamp}.tar.gz")
        
        with tarfile.open(tar_path, 'w:gz') as tarf:
            for file_path in files:
                if os.path.exists(file_path):
                    tarf.add(file_path, arcname=os.path.basename(file_path))
        
        return len(files)
    
    def archive_original(self, files, archive_dir):
        """归档原始文件"""
        import shutil
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_subdir = os.path.join(archive_dir, f"logs_archive_{timestamp}")
        os.makedirs(archive_subdir, exist_ok=True)
        
        for file_path in files:
            if os.path.exists(file_path):
                dest_path = os.path.join(archive_subdir, os.path.basename(file_path))
                shutil.copy2(file_path, dest_path)
        
        return len(files)
    
    def toggle_auto_refresh(self, enabled):
        """切换自动刷新状态"""
        self.auto_refresh_enabled = enabled
        
        if enabled:
            # 启动定时器
            interval_ms = self.refresh_interval_spin.value() * 1000
            self.auto_refresh_timer.start(interval_ms)
            self.refresh_status_label.setText(f"自动刷新: 已启用 (每{self.refresh_interval_spin.value()}秒)")
            self.refresh_status_label.setStyleSheet("""
                QLabel {
                    background-color: #e8f5e8;
                    border: 1px solid #4CAF50;
                    border-radius: 3px;
                    padding: 5px;
                    color: #2e7d32;
                }
            """)
        else:
            # 停止定时器
            self.auto_refresh_timer.stop()
            self.refresh_status_label.setText("自动刷新: 已禁用")
            self.refresh_status_label.setStyleSheet("""
                QLabel {
                    background-color: #f0f0f0;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    padding: 5px;
                    color: #666;
                }
            """)
    
    def update_refresh_interval(self, value):
        """更新刷新间隔"""
        self.auto_refresh_interval = value
        
        # 如果自动刷新已启用，重新启动定时器
        if self.auto_refresh_enabled:
            self.auto_refresh_timer.stop()
            self.auto_refresh_timer.start(value * 1000)
            self.refresh_status_label.setText(f"自动刷新: 已启用 (每{value}秒)")
    
    def auto_refresh_all(self):
        """自动刷新所有标签页内容"""
        try:
            current_tab = self.tab_widget.currentIndex()
            
            # 刷新配置标签页
            if hasattr(self, 'preview_text'):
                self.refresh_preview()
            
            # 刷新查看器标签页
            if hasattr(self, 'log_viewer'):
                self.refresh_log_viewer()
            
            # 刷新分析标签页
            if hasattr(self, 'analytics_text'):
                self.refresh_analytics()
            
            # 刷新管理标签页
            if hasattr(self, 'log_files_table'):
                self.refresh_file_list()
            
            # 更新状态显示时间
            current_time = datetime.now().strftime('%H:%M:%S')
            if hasattr(self, 'refresh_status_label'):
                status_text = f"自动刷新: 已启用 (每{self.auto_refresh_interval}秒) - 最后更新: {current_time}"
                self.refresh_status_label.setText(status_text)
                
        except Exception as e:
            # 如果刷新出错，记录日志但不中断定时器
            logger = get_enhanced_logger()
            logger.error(f"自动刷新失败: {str(e)}")
    
    def load_auto_refresh_config(self):
        """加载自动刷新配置"""
        try:
            # 从设置文件加载自动刷新配置
            settings_file = os.path.join(os.path.dirname(__file__), '..', 'settings.json')
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    
                auto_refresh_settings = settings.get('auto_refresh', {})
                
                # 设置自动刷新开关
                enabled = auto_refresh_settings.get('enabled', False)
                self.auto_refresh_check.setChecked(enabled)
                
                # 设置刷新间隔
                interval = auto_refresh_settings.get('interval', 30)
                self.refresh_interval_spin.setValue(interval)
                
                # 应用设置
                self.auto_refresh_enabled = enabled
                self.auto_refresh_interval = interval
                
                # 如果启用了自动刷新，启动定时器
                if enabled:
                    self.toggle_auto_refresh(True)
                    
        except Exception as e:
            # 如果加载失败，使用默认设置
            self.auto_refresh_check.setChecked(False)
            self.refresh_interval_spin.setValue(30)
            self.auto_refresh_enabled = False
            self.auto_refresh_interval = 30
    
    def save_auto_refresh_config(self):
        """保存自动刷新配置"""
        try:
            settings_file = os.path.join(os.path.dirname(__file__), '..', 'settings.json')
            
            # 读取现有设置
            settings = {}
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            
            # 更新自动刷新设置
            settings['auto_refresh'] = {
                'enabled': self.auto_refresh_check.isChecked(),
                'interval': self.refresh_interval_spin.value()
            }
            
            # 保存设置
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger = get_enhanced_logger()
            logger.error(f"保存自动刷新配置失败: {str(e)}")
     
    def show_help(self):
        """显示帮助信息"""
        help_text = """
📋 增强日志管理帮助

⚙️ 配置标签页:
• 设置日志级别和输出选项
• 配置日志轮转和性能选项
• 配置自动刷新功能（5-300秒间隔）
• 预览和测试配置

🔄 自动刷新功能:
• 启用后自动刷新所有标签页内容
• 可设置5秒到5分钟的刷新间隔
• 实时显示最后更新时间
• 出错时不会中断定时器

👁️ 查看器标签页:
• 实时查看日志内容
• 支持语法高亮显示
• 按级别过滤日志

🔍 搜索标签页:
• 搜索日志内容
• 支持日期范围过滤
• 导出搜索结果

📊 分析标签页:
• 查看日志统计信息
• 分析错误和警告数量
• 监控文件大小

🗂️ 管理标签页:
• 管理日志文件
• 导出和清理日志
• 设置自动清理选项
        """
        QMessageBox.information(self, "帮助", help_text)
    
    # ===== 设置保存/加载（查看器、调试、管理、搜索） =====
    def save_viewer_settings(self):
        """保存查看器页设置"""
        try:
            s = load_settings()
            lm = s.get('log_management', {})
            viewer = {
                'auto_scroll': bool(self.auto_scroll_check.isChecked()),
                'syntax_highlight': bool(self.syntax_highlight_check.isChecked()),
                'level': str(self.viewer_level_combo.currentText()),
                'page_size': str(self.page_size_combo.currentText()),
                'search_term': self.viewer_search_input.text(),
                'case_sensitive': bool(self.case_sensitive_check.isChecked()),
                'regex': bool(self.regex_search_check.isChecked())
            }
            lm['viewer'] = viewer
            s['log_management'] = lm
            save_settings(s)
            QMessageBox.information(self, "成功", "查看器设置已保存！")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存查看器设置失败: {e}")

    def load_viewer_settings(self):
        """加载查看器页设置并应用"""
        try:
            s = load_settings()
            viewer = s.get('log_management', {}).get('viewer', {})
            if viewer:
                self.auto_scroll_check.setChecked(bool(viewer.get('auto_scroll', False)))
                syntax_on = bool(viewer.get('syntax_highlight', True))
                self.syntax_highlight_check.setChecked(syntax_on)
                self.toggle_syntax_highlight(syntax_on)

                level = viewer.get('level')
                if level:
                    self.viewer_level_combo.setCurrentText(str(level))
                    self.filter_logs()

                size_text = viewer.get('page_size')
                if size_text:
                    self.page_size_combo.setCurrentText(str(size_text))
                    self.change_page_size(str(size_text))

                self.case_sensitive_check.setChecked(bool(viewer.get('case_sensitive', False)))
                self.regex_search_check.setChecked(bool(viewer.get('regex', False)))

                term = viewer.get('search_term', '')
                self.viewer_search_input.setText(str(term))
                if term:
                    self.search_in_viewer(str(term))
        except Exception as e:
            print(f"加载查看器设置失败: {e}")

    def save_debug_settings(self):
        """保存调试日志页设置"""
        try:
            s = load_settings()
            lm = s.get('log_management', {})
            debug = {
                'monitor_enabled': bool(self.debug_monitor_check.isChecked()),
                'monitor_interval': int(self.debug_interval_spin.value()),
                'level': str(self.debug_level_combo.currentText()),
                'module': str(self.debug_module_combo.currentText())
            }
            lm['debug'] = debug
            s['log_management'] = lm
            save_settings(s)

            # 应用设置到UI及功能
            self.debug_interval_spin.setValue(debug['monitor_interval'])
            self.debug_monitor_check.setChecked(debug['monitor_enabled'])
            self.toggle_debug_monitoring(debug['monitor_enabled'])
            self.debug_level_combo.setCurrentText(debug['level'])
            self.debug_module_combo.setCurrentText(debug['module'])
            self.filter_debug_logs()

            QMessageBox.information(self, "成功", "调试日志设置已保存！")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存调试日志设置失败: {e}")

    def load_debug_settings(self):
        """加载调试日志页设置并应用"""
        try:
            s = load_settings()
            debug = s.get('log_management', {}).get('debug', {})
            if debug:
                self.debug_interval_spin.setValue(int(debug.get('monitor_interval', 5)))
                enabled = bool(debug.get('monitor_enabled', False))
                self.debug_monitor_check.setChecked(enabled)
                self.toggle_debug_monitoring(enabled)
                level = debug.get('level')
                if level:
                    self.debug_level_combo.setCurrentText(str(level))
                module = debug.get('module')
                if module:
                    self.debug_module_combo.setCurrentText(str(module))
                self.filter_debug_logs()
        except Exception as e:
            print(f"加载调试日志设置失败: {e}")

    def save_management_settings(self):
        """保存管理页清理设置"""
        try:
            s = load_settings()
            lm = s.get('log_management', {})
            management = {
                'keep_days': int(self.keep_days_spin.value()),
                'auto_cleanup': bool(self.auto_cleanup_check.isChecked())
            }
            lm['management'] = management
            s['log_management'] = lm
            save_settings(s)
            QMessageBox.information(self, "成功", "管理清理设置已保存！")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存管理清理设置失败: {e}")

    def load_management_settings(self):
        """加载管理页清理设置并应用"""
        try:
            s = load_settings()
            mg = s.get('log_management', {}).get('management', {})
            if mg:
                self.keep_days_spin.setValue(int(mg.get('keep_days', 30)))
                self.auto_cleanup_check.setChecked(bool(mg.get('auto_cleanup', False)))
        except Exception as e:
            print(f"加载管理清理设置失败: {e}")

    def save_search_settings(self):
        """保存默认搜索设置"""
        try:
            s = load_settings()
            lm = s.get('log_management', {})
            search_defaults = {
                'keyword': self.search_input.text(),
                'start_date': self.start_date.date().toString('yyyy-MM-dd'),
                'end_date': self.end_date.date().toString('yyyy-MM-dd')
            }
            lm['search'] = search_defaults
            s['log_management'] = lm
            save_settings(s)
            QMessageBox.information(self, "成功", "默认搜索设置已保存！")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存默认搜索设置失败: {e}")

    def load_search_settings(self):
        """加载默认搜索设置并应用"""
        try:
            s = load_settings()
            sd = s.get('log_management', {}).get('search', {})
            if sd:
                self.search_input.setText(str(sd.get('keyword', '')))
                from_str = sd.get('start_date')
                to_str = sd.get('end_date')
                if from_str:
                    d = QDate.fromString(str(from_str), 'yyyy-MM-dd')
                    if d.isValid():
                        self.start_date.setDate(d)
                if to_str:
                    d2 = QDate.fromString(str(to_str), 'yyyy-MM-dd')
                    if d2.isValid():
                        self.end_date.setDate(d2)
        except Exception as e:
            print(f"加载默认搜索设置失败: {e}")

    def get_log_files(self):
        """获取日志文件列表"""
        log_dir = os.path.join(os.getcwd(), "logs")
        log_files = []
        
        if os.path.exists(log_dir):
            for file in os.listdir(log_dir):
                if file.endswith(('.log', '.html')):
                    log_files.append(os.path.join(log_dir, file))
        
        return log_files
    
    def extract_logs_from_html(self, html_file_path):
        """从HTML日志文件中提取纯文本日志内容"""
        try:
            from bs4 import BeautifulSoup
            
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            log_entries = soup.find_all('div', class_='log-entry')
            
            extracted_logs = []
            for entry in log_entries:
                # 修正：使用div而不是span
                timestamp_elem = entry.find('div', class_='log-timestamp')
                level_elem = entry.find('div', class_='log-level')
                message_elem = entry.find('div', class_='log-message')
                
                if timestamp_elem and level_elem and message_elem:
                    timestamp = timestamp_elem.get_text(strip=True)
                    level = level_elem.get_text(strip=True)
                    message = message_elem.get_text(strip=True)
                    
                    # 获取CSS类信息以确定日志级别
                    entry_classes = entry.get('class', [])
                    css_level = None
                    for cls in entry_classes:
                        if cls in ['调试', '信息', '警告', '错误', '严重']:
                            css_level = cls
                            break
                    
                    # 使用CSS类级别或文本级别
                    final_level = css_level if css_level else level
                    
                    log_line = f"[{timestamp}] {final_level}: {message}"
                    extracted_logs.append(log_line)
            
            return '\n'.join(extracted_logs)
            
        except ImportError:
            # 如果没有BeautifulSoup，使用简单的正则表达式提取
            import re
            
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # 修正：使用div而不是span，同时提取CSS类信息
            pattern = r'<div class="log-entry\s+([^"]*?)"[^>]*>.*?<div class="log-timestamp">([^<]+)</div>.*?<div class="log-level">([^<]+)</div>.*?<div class="log-message">([^<]+)</div>.*?</div>'
            matches = re.findall(pattern, html_content, re.DOTALL)
            
            extracted_logs = []
            for css_class, timestamp, level, message in matches:
                # 从CSS类中提取级别信息
                css_level = None
                for cls in css_class.split():
                    if cls in ['调试', '信息', '警告', '错误', '严重']:
                        css_level = cls
                        break
                
                # 使用CSS类级别或文本级别
                final_level = css_level if css_level else level.strip()
                
                log_line = f"[{timestamp.strip()}] {final_level}: {message.strip()}"
                extracted_logs.append(log_line)
            
            return '\n'.join(extracted_logs)
            
        except Exception as e:
            return f"解析HTML日志文件失败: {e}"
    
    def format_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"