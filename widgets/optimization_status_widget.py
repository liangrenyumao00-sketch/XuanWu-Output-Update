# widgets/optimization_status_widget.py
"""
优化功能状态监控组件

该组件显示所有优化功能的运行状态，让用户了解哪些功能正在自动运行。

作者：XuanWu OCR Team
版本：2.1.7
"""

import json
import os
from typing import Dict, Any
from PyQt6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QGroupBox, QPushButton, QTextEdit, QScrollArea,
                            QFrame, QGridLayout, QProgressBar)
from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor

from core.i18n import t


class StatusIndicator(QWidget):
    """状态指示器"""
    
    def __init__(self, status: bool = False):
        super().__init__()
        self.status = status
        self.setFixedSize(16, 16)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制圆形指示器
        color = QColor(0, 255, 0) if self.status else QColor(255, 0, 0)
        painter.setBrush(color)
        painter.setPen(color)
        painter.drawEllipse(2, 2, 12, 12)
    
    def set_status(self, status: bool):
        self.status = status
        self.update()


class OptimizationStatusWidget(QDialog):
    """优化功能状态监控组件"""
    
    refresh_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("优化功能状态"))
        self.setMinimumSize(600, 500)
        self.resize(800, 600)
        
        # 设置窗口属性，确保独立显示
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowMinMaxButtonsHint)
        self.setModal(False)  # 非模态窗口
        
        # 状态指示器
        self.status_indicators = {}
        
        # 刷新定时器
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.start(5000)  # 每5秒刷新一次
        
        self.setup_ui()
        self.refresh_status()
    
    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel(t("优化功能运行状态"))
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # 核心优化功能状态
        self.create_core_status_group(scroll_layout)
        
        # 性能指标显示
        self.create_performance_metrics_group(scroll_layout)
        
        # 配置信息
        self.create_config_info_group(scroll_layout)
        
        # 操作按钮
        self.create_action_buttons_group(scroll_layout)
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        # 底部状态栏
        self.create_status_bar(layout)
    
    def create_core_status_group(self, parent_layout):
        """创建核心功能状态组"""
        group = QGroupBox(t("核心优化功能"))
        layout = QGridLayout(group)
        
        # 功能列表
        features = [
            ("performance_monitoring", "性能监控", "实时监控CPU、内存使用情况"),
            ("thread_pool_manager", "线程池管理", "智能管理应用程序线程资源"),
            ("cache_manager", "缓存管理", "自动管理内存和磁盘缓存"),
            ("error_handler", "异常处理", "自动捕获和处理程序异常"),
            ("config_manager", "配置管理", "动态配置加载和验证"),
        ]
        
        for i, (key, name, desc) in enumerate(features):
            # 状态指示器
            indicator = StatusIndicator()
            self.status_indicators[key] = indicator
            layout.addWidget(indicator, i, 0)
            
            # 功能名称
            name_label = QLabel(t(name))
            name_font = QFont()
            name_font.setBold(True)
            name_label.setFont(name_font)
            layout.addWidget(name_label, i, 1)
            
            # 功能描述
            desc_label = QLabel(t(desc))
            desc_label.setStyleSheet("color: #666666;")
            layout.addWidget(desc_label, i, 2)
        
        parent_layout.addWidget(group)
    
    def create_performance_metrics_group(self, parent_layout):
        """创建性能指标组"""
        group = QGroupBox(t("实时性能指标"))
        layout = QGridLayout(group)
        
        # CPU使用率
        layout.addWidget(QLabel(t("CPU使用率:")), 0, 0)
        self.cpu_progress = QProgressBar()
        self.cpu_progress.setRange(0, 100)
        layout.addWidget(self.cpu_progress, 0, 1)
        self.cpu_label = QLabel("0%")
        layout.addWidget(self.cpu_label, 0, 2)
        
        # 内存使用率
        layout.addWidget(QLabel(t("内存使用率:")), 1, 0)
        self.memory_progress = QProgressBar()
        self.memory_progress.setRange(0, 100)
        layout.addWidget(self.memory_progress, 1, 1)
        self.memory_label = QLabel("0%")
        layout.addWidget(self.memory_label, 1, 2)
        
        # 线程数量
        layout.addWidget(QLabel(t("活跃线程数:")), 2, 0)
        self.thread_label = QLabel("0")
        layout.addWidget(self.thread_label, 2, 1, 1, 2)
        
        # 缓存命中率
        layout.addWidget(QLabel(t("缓存命中率:")), 3, 0)
        self.cache_label = QLabel("N/A")
        layout.addWidget(self.cache_label, 3, 1, 1, 2)
        
        parent_layout.addWidget(group)
    
    def create_config_info_group(self, parent_layout):
        """创建配置信息组"""
        group = QGroupBox(t("当前配置"))
        layout = QVBoxLayout(group)
        
        self.config_text = QTextEdit()
        self.config_text.setMaximumHeight(150)
        self.config_text.setReadOnly(True)
        layout.addWidget(self.config_text)
        
        parent_layout.addWidget(group)
    
    def create_action_buttons_group(self, parent_layout):
        """创建操作按钮组"""
        group = QGroupBox(t("操作"))
        layout = QHBoxLayout(group)
        
        # 刷新按钮
        refresh_btn = QPushButton(t("刷新状态"))
        refresh_btn.clicked.connect(self.refresh_status)
        layout.addWidget(refresh_btn)
        
        # 优化内存按钮
        optimize_btn = QPushButton(t("优化内存"))
        optimize_btn.clicked.connect(self.optimize_memory)
        layout.addWidget(optimize_btn)
        
        # 导出报告按钮
        export_btn = QPushButton(t("导出性能报告"))
        export_btn.clicked.connect(self.export_performance_report)
        layout.addWidget(export_btn)
        
        layout.addStretch()
        parent_layout.addWidget(group)
    
    def create_status_bar(self, parent_layout):
        """创建状态栏"""
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        status_layout = QHBoxLayout(status_frame)
        
        self.status_label = QLabel(t("就绪"))
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.last_update_label = QLabel("")
        status_layout.addWidget(self.last_update_label)
        
        parent_layout.addWidget(status_frame)
    
    def refresh_status(self):
        """刷新状态"""
        try:
            import time
            
            # 更新核心功能状态
            self.update_core_status()
            
            # 更新性能指标
            self.update_performance_metrics()
            
            # 更新配置信息
            self.update_config_info()
            
            # 更新状态栏
            self.last_update_label.setText(
                t("最后更新: ") + time.strftime("%H:%M:%S")
            )
            self.status_label.setText(t("状态正常"))
            
        except Exception as e:
            self.status_label.setText(t(f"更新失败: {str(e)}"))
    
    def update_core_status(self):
        """更新核心功能状态"""
        try:
            # 检查性能监控
            try:
                from core.performance_monitor import get_performance_monitor
                monitor = get_performance_monitor()
                self.status_indicators["performance_monitoring"].set_status(
                    monitor.is_monitoring
                )
            except:
                self.status_indicators["performance_monitoring"].set_status(False)
            
            # 检查线程池管理器
            try:
                from core.thread_pool_manager import get_thread_pool_manager
                manager = get_thread_pool_manager()
                self.status_indicators["thread_pool_manager"].set_status(True)
            except:
                self.status_indicators["thread_pool_manager"].set_status(False)
            
            # 检查缓存管理器
            try:
                from core.cache_manager import get_cache_manager
                cache = get_cache_manager()
                self.status_indicators["cache_manager"].set_status(True)
            except:
                self.status_indicators["cache_manager"].set_status(False)
            
            # 检查错误处理器
            try:
                from core.error_handler import get_error_handler
                handler = get_error_handler()
                self.status_indicators["error_handler"].set_status(True)
            except:
                self.status_indicators["error_handler"].set_status(False)
            
            # 检查配置管理器
            try:
                from core.config_manager import get_config_manager
                config = get_config_manager()
                self.status_indicators["config_manager"].set_status(True)
            except:
                self.status_indicators["config_manager"].set_status(False)
                
        except Exception as e:
            self.logger.error(f"更新核心功能状态失败: {e}")
    
    def update_performance_metrics(self):
        """更新性能指标"""
        try:
            from core.performance_monitor import get_performance_monitor
            monitor = get_performance_monitor()
            
            current_metrics = monitor.get_current_metrics()
            if current_metrics:
                # CPU使用率
                cpu_percent = int(current_metrics.cpu_percent)
                self.cpu_progress.setValue(cpu_percent)
                self.cpu_label.setText(f"{cpu_percent}%")
                
                # 内存使用率
                memory_percent = int(current_metrics.memory_percent)
                self.memory_progress.setValue(memory_percent)
                self.memory_label.setText(f"{memory_percent}%")
                
                # 线程数量
                self.thread_label.setText(str(current_metrics.thread_count))
            
            # 缓存命中率
            try:
                from core.cache_manager import get_cache_manager
                cache_manager = get_cache_manager()
                stats = cache_manager.get_stats()
                if stats.get('total_requests', 0) > 0:
                    hit_rate = (stats.get('cache_hits', 0) / stats['total_requests']) * 100
                    self.cache_label.setText(f"{hit_rate:.1f}%")
                else:
                    self.cache_label.setText("N/A")
            except:
                self.cache_label.setText("N/A")
                
        except Exception as e:
            self.logger.error(f"更新性能指标失败: {e}")
    
    def update_config_info(self):
        """更新配置信息"""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                'config', 'optimization_config.json'
            )
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 格式化显示配置
                auto_start = config.get('optimization_settings', {}).get('auto_start', {})
                config_text = "自动启动配置:\n"
                for key, value in auto_start.items():
                    status = "✅ 启用" if value else "❌ 禁用"
                    config_text += f"  {key}: {status}\n"
                
                self.config_text.setPlainText(config_text)
            else:
                self.config_text.setPlainText("配置文件不存在")
                
        except Exception as e:
            self.config_text.setPlainText(f"读取配置失败: {e}")
    
    def optimize_memory(self):
        """优化内存"""
        try:
            from core.performance_monitor import optimize_memory
            optimize_memory()
            self.status_label.setText(t("内存优化完成"))
        except Exception as e:
            self.status_label.setText(t(f"内存优化失败: {str(e)}"))
    
    def export_performance_report(self):
        """导出性能报告"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            import time
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                t("导出性能报告"),
                f"performance_report_{time.strftime('%Y%m%d_%H%M%S')}.json",
                "JSON Files (*.json)"
            )
            
            if file_path:
                from core.performance_monitor import export_performance_report
                if export_performance_report(file_path):
                    self.status_label.setText(t("性能报告导出成功"))
                else:
                    self.status_label.setText(t("性能报告导出失败"))
                    
        except Exception as e:
            self.status_label.setText(t(f"导出失败: {str(e)}"))
    
    def closeEvent(self, event):
        """关闭事件"""
        self.refresh_timer.stop()
        super().closeEvent(event)