# widgets/analytics_panel.py
"""
数据分析和统计面板模块

该模块提供了一个综合的数据分析和统计界面，用于展示OCR识别结果的各种统计信息，
包括关键词统计、时间趋势分析、详细报告等功能。

主要功能：
- 数据概览：显示总体统计信息
- 关键词分析：统计和分析识别到的关键词
- 时间趋势：展示数据随时间的变化趋势
- 详细报告：生成和导出详细的分析报告

依赖：
- PyQt6：GUI框架
- core.config：配置管理
- core.index_builder：日志索引构建
- core.i18n：国际化支持

作者：XuanWu OCR Team
版本：2.1.7
"""
import os
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit,
    QGroupBox, QGridLayout, QProgressBar, QComboBox, QDateEdit,
    QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QDate, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QPalette
from core.config import LOG_DIR, SCREENSHOT_DIR
from core.index_builder import build_log_index
from .chart_widget import SimpleBarChart, SimplePieChart, SimpleLineChart
from core.i18n import t

class AnalyticsPanel(QWidget):
    """
    数据分析和统计面板
    
    提供OCR识别结果的综合数据分析功能，包括统计图表、趋势分析、
    关键词统计等多种数据可视化和分析工具。
    
    Attributes:
        refresh_timer (QTimer): 定时刷新数据的计时器
        tab_widget (QTabWidget): 主要的标签页容器
        overview_tab (QWidget): 概览标签页
        keywords_tab (QWidget): 关键词统计标签页
        trends_tab (QWidget): 时间趋势标签页
        reports_tab (QWidget): 详细报告标签页
    
    Signals:
        data_refreshed: 数据刷新完成时发出的信号
    
    Example:
        >>> analytics = AnalyticsPanel()
        >>> analytics.show()
        >>> analytics.refresh_data()  # 手动刷新数据
    """
    
    # 定义信号
    data_refreshed = pyqtSignal()
    
    def __init__(self):
        """
        初始化数据分析面板
        
        设置UI界面，加载初始数据，并启动定时刷新机制。
        """
        super().__init__()
        self.init_ui()
        self.load_data()
        
        # 定时刷新数据
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(30000)  # 30秒刷新一次
    
    def init_ui(self):
        """
        初始化用户界面
        
        创建主要的UI组件，包括标签页、图表区域、控制按钮等。
        设置样式和布局。
        """
        layout = QVBoxLayout(self)
        layout.setSpacing(5)  # 减小间距
        layout.setContentsMargins(5, 5, 5, 5)  # 设置边距
        
        # 标题
        title = QLabel("📊 数据分析与统计")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))  # 减小字体
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: #2196F3;
                padding: 5px;  
                border-bottom: 2px solid #2196F3;
                margin-bottom: 5px;
            }
        """)
        layout.addWidget(title)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #cccccc;
                border-radius: 5px;
            }
            QTabBar::tab {
                padding: 5px 12px;  
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
        """)
        
        # 概览标签页
        self.overview_tab = self.create_overview_tab()
        self.tab_widget.addTab(self.overview_tab, "📈 概览")
        
        # 关键词统计标签页
        self.keywords_tab = self.create_keywords_tab()
        self.tab_widget.addTab(self.keywords_tab, "🔍 关键词")
        
        # 时间趋势标签页
        self.trends_tab = self.create_trends_tab()
        self.tab_widget.addTab(self.trends_tab, "📅 趋势")
        
        # 详细报告标签页
        self.reports_tab = self.create_reports_tab()
        self.tab_widget.addTab(self.reports_tab, "📋 报告")
        
        layout.addWidget(self.tab_widget)
        
        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新数据")
        refresh_btn.setMinimumHeight(28)  # 减小按钮高度
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_data)
        layout.addWidget(refresh_btn)
    
    def create_overview_tab(self):
        """创建概览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 总体统计卡片
        stats_frame = QFrame()
        stats_frame.setFrameStyle(QFrame.Shape.Box)
        stats_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        stats_layout = QGridLayout(stats_frame)
        
        # 统计数据标签
        self.total_captures_label = QLabel(t("总识别次数: 0"))
        self.total_hits_label = QLabel(t("总命中次数: 0"))
        self.hit_rate_label = QLabel(t("命中率: 0%"))
        self.active_keywords_label = QLabel(t("活跃关键词: 0"))
        
        # 设置标签样式
        for i, label in enumerate([self.total_captures_label, self.total_hits_label, 
                                  self.hit_rate_label, self.active_keywords_label]):
            label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("""
                QLabel {
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 15px;
                    margin: 5px;
                }
            """)
            stats_layout.addWidget(label, i // 2, i % 2)
        
        layout.addWidget(stats_frame)
        
        # 添加图表区域
        charts_layout = QHBoxLayout()
        
        # 关键词匹配饼图
        self.keyword_pie_chart = SimplePieChart()
        self.keyword_pie_chart.set_data([], [], "关键词匹配分布")
        charts_layout.addWidget(self.keyword_pie_chart)
        
        # 每日识别趋势折线图
        self.daily_trend_chart = SimpleLineChart()
        self.daily_trend_chart.set_data([], [], "7天识别趋势")
        charts_layout.addWidget(self.daily_trend_chart)
        
        layout.addLayout(charts_layout)
        
        # 最近活动
        recent_group = QGroupBox("📋 最近活动")
        recent_layout = QVBoxLayout(recent_group)
        
        self.recent_activity = QTextEdit()
        self.recent_activity.setMaximumHeight(200)
        self.recent_activity.setReadOnly(True)
        self.recent_activity.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                font-family: Consolas, monospace;
            }
        """)
        recent_layout.addWidget(self.recent_activity)
        
        layout.addWidget(recent_group)
        
        return widget
    
    def create_keywords_tab(self):
        """创建关键词统计标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 关键词统计图表
        self.keywords_bar_chart = SimpleBarChart()
        self.keywords_bar_chart.set_data([], [], "关键词匹配次数统计")
        layout.addWidget(self.keywords_bar_chart)
        
        # 关键词统计表格
        self.keywords_table = QTableWidget()
        self.keywords_table.setColumnCount(4)
        self.keywords_table.setHorizontalHeaderLabels(["关键词", "命中次数", "最后命中时间", "命中率"])
        self.keywords_table.setAlternatingRowColors(True)
        self.keywords_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #ddd;
            }
            QHeaderView::section {
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        
        # 调整列宽
        header = self.keywords_table.horizontalHeader()
        header.setStretchLastSection(True)
        
        layout.addWidget(self.keywords_table)
        
        return widget
    
    def create_trends_tab(self):
        """创建时间趋势标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 时间范围选择
        time_frame = QFrame()
        time_layout = QHBoxLayout(time_frame)
        
        time_layout.addWidget(QLabel("时间范围:"))
        
        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems(["今天", "最近7天", "最近30天", "全部时间"])
        self.time_range_combo.currentTextChanged.connect(self.update_trends)
        time_layout.addWidget(self.time_range_combo)
        
        time_layout.addStretch()
        layout.addWidget(time_frame)
        
        # 趋势图表区域（使用文本显示简单图表）
        self.trends_display = QTextEdit()
        self.trends_display.setReadOnly(True)
        self.trends_display.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.trends_display)
        
        return widget
    
    def create_reports_tab(self):
        """创建详细报告标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 报告生成控件
        controls_frame = QFrame()
        controls_layout = QHBoxLayout(controls_frame)
        
        controls_layout.addWidget(QLabel("报告类型:"))
        
        self.report_type_combo = QComboBox()
        self.report_type_combo.addItems(["日报", "周报", "月报", "自定义"])
        controls_layout.addWidget(self.report_type_combo)
        
        generate_btn = QPushButton("📊 生成报告")
        generate_btn.setMinimumHeight(30)
        generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        generate_btn.clicked.connect(self.generate_report)
        controls_layout.addWidget(generate_btn)
        
        export_btn = QPushButton("💾 导出报告")
        export_btn.setMinimumHeight(30)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self.export_report)
        controls_layout.addWidget(export_btn)
        
        controls_layout.addStretch()
        layout.addWidget(controls_frame)
        
        # 报告内容显示
        self.report_content = QTextEdit()
        self.report_content.setReadOnly(True)
        self.report_content.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 15px;
                font-family: Arial, sans-serif;
                line-height: 1.6;
            }
        """)
        layout.addWidget(self.report_content)
        
        return widget
    
    def load_data(self):
        """加载数据"""
        try:
            # 构建日志索引
            build_log_index()
            
            # 读取日志索引
            index_file = os.path.join(LOG_DIR, "log_index.json")
            if os.path.exists(index_file):
                with open(index_file, 'r', encoding='utf-8') as f:
                    self.log_data = json.load(f)
            else:
                self.log_data = []
            
            self.update_overview()
            self.update_keywords_table()
            self.update_trends()
            
        except Exception as e:
            logging.error(f"加载数据失败: {e}")
            self.log_data = []
    
    def update_overview(self):
        """更新概览数据"""
        try:
            total_captures = len(self.log_data)
            total_hits = total_captures  # 每个日志条目都是一次命中
            hit_rate = 100 if total_captures > 0 else 0
            
            # 统计活跃关键词
            keywords = set()
            for entry in self.log_data:
                if 'keywords' in entry:
                    keywords.update(entry['keywords'].split('_'))
            active_keywords = len(keywords)
            
            self.total_captures_label.setText(f"总识别次数: {total_captures}")
            self.total_hits_label.setText(f"总命中次数: {total_hits}")
            self.hit_rate_label.setText(f"命中率: {hit_rate:.1f}%")
            self.active_keywords_label.setText(f"活跃关键词: {active_keywords}")
            
            # 更新最近活动
            recent_text = "最近10次识别记录:\n\n"
            for entry in self.log_data[-10:]:
                timestamp = entry.get('timestamp', 'Unknown')
                keywords = entry.get('keywords', 'Unknown')
                recent_text += f"🕒 {timestamp} - 关键词: {keywords}\n"
            
            self.recent_activity.setPlainText(recent_text)
            
        except Exception as e:
            logging.error(f"更新概览数据失败: {e}")
    
    def get_keyword_statistics(self):
        """获取关键词统计数据"""
        try:
            keyword_stats = defaultdict(int)
            
            for entry in self.log_data:
                if 'keywords' in entry:
                    keywords = entry['keywords'].split('_')
                    for keyword in keywords:
                        keyword_stats[keyword] += 1
            
            return dict(keyword_stats)
        except Exception as e:
            logging.error(f"获取关键词统计失败: {e}")
            return {}
    
    def get_daily_statistics(self):
        """获取每日统计数据"""
        try:
            daily_stats = defaultdict(int)
            
            for entry in self.log_data:
                try:
                    # 解析时间戳
                    timestamp_str = entry.get('timestamp', '')
                    if timestamp_str:
                        # 假设时间戳格式为 YYYY-MM-DD_HH-MM-SS
                        date_part = timestamp_str.split('_')[0]
                        entry_date = datetime.strptime(date_part, '%Y-%m-%d')
                        date_key = entry_date.strftime('%Y-%m-%d')
                        daily_stats[date_key] += 1
                except:
                    continue
            
            return dict(daily_stats)
        except Exception as e:
            logging.error(f"获取每日统计失败: {e}")
            return {}
    
    def update_keywords_table(self):
        """更新关键词统计表格"""
        try:
            # 统计关键词
            keyword_stats = defaultdict(lambda: {'count': 0, 'last_time': None})
            
            for entry in self.log_data:
                if 'keywords' in entry and 'timestamp' in entry:
                    keywords = entry['keywords'].split('_')
                    timestamp = entry['timestamp']
                    
                    for keyword in keywords:
                        keyword_stats[keyword]['count'] += 1
                        if (keyword_stats[keyword]['last_time'] is None or 
                            timestamp > keyword_stats[keyword]['last_time']):
                            keyword_stats[keyword]['last_time'] = timestamp
            
            # 更新表格
            self.keywords_table.setRowCount(len(keyword_stats))
            
            total_hits = sum(stats['count'] for stats in keyword_stats.values())
            
            for row, (keyword, stats) in enumerate(sorted(keyword_stats.items(), 
                                                         key=lambda x: x[1]['count'], 
                                                         reverse=True)):
                self.keywords_table.setItem(row, 0, QTableWidgetItem(keyword))
                self.keywords_table.setItem(row, 1, QTableWidgetItem(str(stats['count'])))
                self.keywords_table.setItem(row, 2, QTableWidgetItem(stats['last_time'] or 'N/A'))
                
                hit_rate = (stats['count'] / total_hits * 100) if total_hits > 0 else 0
                self.keywords_table.setItem(row, 3, QTableWidgetItem(f"{hit_rate:.1f}%"))
            
            self.keywords_table.resizeColumnsToContents()
            
        except Exception as e:
            logging.error(f"更新关键词表格失败: {e}")
    
    def update_trends(self):
        """更新时间趋势"""
        try:
            time_range = self.time_range_combo.currentText()
            
            # 根据时间范围过滤数据
            now = datetime.now()
            if time_range == "今天":
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif time_range == "最近7天":
                start_date = now - timedelta(days=7)
            elif time_range == "最近30天":
                start_date = now - timedelta(days=30)
            else:  # 全部时间
                start_date = datetime.min
            
            # 按日期统计
            daily_stats = defaultdict(int)
            
            for entry in self.log_data:
                try:
                    # 解析时间戳
                    timestamp_str = entry.get('timestamp', '')
                    if timestamp_str:
                        # 假设时间戳格式为 YYYY-MM-DD_HH-MM-SS
                        date_part = timestamp_str.split('_')[0]
                        entry_date = datetime.strptime(date_part, '%Y-%m-%d')
                        
                        if entry_date >= start_date:
                            date_key = entry_date.strftime('%Y-%m-%d')
                            daily_stats[date_key] += 1
                except:
                    continue
            
            # 生成简单的文本图表
            trends_text = f"📈 {time_range} 识别趋势\n\n"
            
            if daily_stats:
                max_count = max(daily_stats.values())
                for date, count in sorted(daily_stats.items()):
                    bar_length = int((count / max_count) * 30) if max_count > 0 else 0
                    bar = '█' * bar_length
                    trends_text += f"{date}: {bar} ({count})\n"
            else:
                trends_text += "暂无数据\n"
            
            self.trends_display.setPlainText(trends_text)
            
        except Exception as e:
            logging.error(f"更新趋势数据失败: {e}")
    
    def generate_report(self):
        """生成报告"""
        try:
            report_type = self.report_type_combo.currentText()
            
            report = f"# {report_type} - OCR识别统计报告\n\n"
            report += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # 总体统计
            total_captures = len(self.log_data)
            report += f"## 总体统计\n"
            report += f"- 总识别次数: {total_captures}\n"
            report += f"- 总命中次数: {total_captures}\n"
            
            # 关键词统计
            keyword_stats = defaultdict(int)
            for entry in self.log_data:
                if 'keywords' in entry:
                    keywords = entry['keywords'].split('_')
                    for keyword in keywords:
                        keyword_stats[keyword] += 1
            
            report += f"\n## 关键词统计\n"
            for keyword, count in sorted(keyword_stats.items(), key=lambda x: x[1], reverse=True):
                report += f"- {keyword}: {count} 次\n"
            
            # 时间分析
            if self.log_data:
                first_entry = min(self.log_data, key=lambda x: x.get('timestamp', ''))
                last_entry = max(self.log_data, key=lambda x: x.get('timestamp', ''))
                
                report += f"\n## 时间范围\n"
                report += f"- 首次记录: {first_entry.get('timestamp', 'Unknown')}\n"
                report += f"- 最新记录: {last_entry.get('timestamp', 'Unknown')}\n"
            
            self.report_content.setPlainText(report)
            
        except Exception as e:
            logging.error(f"生成报告失败: {e}")
            self.report_content.setPlainText(f"生成报告失败: {e}")
    
    def export_report(self):
        """导出报告"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            
            filename, _ = QFileDialog.getSaveFileName(
                self, "导出报告", f"OCR_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "Text Files (*.txt);;All Files (*)"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.report_content.toPlainText())
                
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "导出成功", f"报告已导出到: {filename}")
                
        except Exception as e:
            logging.error(f"导出报告失败: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "导出失败", f"导出报告失败: {e}")
    
    def refresh_data(self):
        """刷新数据"""
        self.load_data()
        
        # 更新图表数据
        try:
            # 获取关键词统计数据
            keyword_stats = self.get_keyword_statistics()
            
            # 更新关键词柱状图
            if keyword_stats:
                sorted_keywords = sorted(keyword_stats.items(), key=lambda x: x[1], reverse=True)
                keywords = [k for k, v in sorted_keywords[:10]]  # 只显示前10个
                counts = [v for k, v in sorted_keywords[:10]]
                
                if hasattr(self, 'keywords_bar_chart'):
                    self.keywords_bar_chart.set_data(counts, keywords, "关键词匹配次数统计")
                
                # 更新概览页面的饼图
                if hasattr(self, 'keyword_pie_chart'):
                    self.keyword_pie_chart.set_data(counts[:5], keywords[:5], "关键词匹配分布")
            else:
                if hasattr(self, 'keywords_bar_chart'):
                    self.keywords_bar_chart.set_data([], [], "关键词匹配次数统计")
                if hasattr(self, 'keyword_pie_chart'):
                    self.keyword_pie_chart.set_data([], [], "关键词匹配分布")
            
            # 更新每日趋势折线图
            daily_stats = self.get_daily_statistics()
            if daily_stats:
                # 获取最近7天的数据
                sorted_dates = sorted(daily_stats.items())[-7:]
                dates = [d for d, c in sorted_dates]
                counts = [c for d, c in sorted_dates]
                
                if hasattr(self, 'daily_trend_chart'):
                    self.daily_trend_chart.set_data(counts, dates, "7天识别趋势")
            else:
                if hasattr(self, 'daily_trend_chart'):
                    self.daily_trend_chart.set_data([], [], "7天识别趋势")
                    
        except Exception as e:
            logging.error(f"更新图表数据失败: {e}")
        
        logging.info("统计数据已刷新")
    
    def refresh_ui_text(self):
        """刷新UI文本的国际化显示"""
        try:
            from core.i18n import t
            
            # 更新标签页标题
            self.tab_widget.setTabText(0, t('概览'))
            self.tab_widget.setTabText(1, t('关键词'))
            self.tab_widget.setTabText(2, t('趋势分析'))
            self.tab_widget.setTabText(3, t('分析报告'))
            
            # 更新主标题
            if hasattr(self, 'title_label'):
                self.title_label.setText(t('analytics_title'))
            
            # 更新刷新按钮文本
            if hasattr(self, 'refresh_btn'):
                self.refresh_btn.setText(t('analytics_refresh_data'))
            
        except Exception as e:
            import logging
            logging.error(f"刷新AnalyticsPanel UI文本时出错: {e}")