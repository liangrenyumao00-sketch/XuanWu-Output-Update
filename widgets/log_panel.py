# widgets/log_panel.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QLabel, 
    QTabWidget, QPushButton, QCheckBox, QSpinBox, QHBoxLayout
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer
import os
import datetime
import re  # 引入正则表达式模块
from typing import List, Dict, Any
from .virtual_list_widget import VirtualListWidget
from core.enhanced_logger import get_enhanced_logger
from core.log_config_manager import get_log_config_manager

class LogPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.html_log_path = os.path.join("logs", "xuanwu_log.html")
        
        # 增强日志系统
        self.enhanced_logger = get_enhanced_logger()
        self.log_config_manager = get_log_config_manager()
        
        # 虚拟化日志相关
        self.log_entries: List[Dict[str, Any]] = []
        self.filtered_log_entries: List[Dict[str, Any]] = []
        self.current_filter_text = ""
        self.max_log_entries = getattr(self.log_config_manager.config, 'max_entries', 10000)
        
        # 存储真实的统计数据
        self.current_statistics = {
            "total_recognitions": 0,
            "keyword_hits": 0,
            "last_recognition_time": "N/A"
        }
        
        # 搜索防抖定时器
        self.filter_timer = QTimer()
        self.filter_timer.setSingleShot(True)
        self.filter_timer.timeout.connect(self._perform_filter)
        
        self.init_ui()
        self._init_html_log()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 传统日志视图
        traditional_tab = QWidget()
        traditional_layout = QVBoxLayout()
        
        # 日志输出区域
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Consolas", 9))
        traditional_layout.addWidget(QLabel("📋 日志输出"))
        traditional_layout.addWidget(self.text_edit)
        
        # 关键词统计区域
        self.stat_edit = QPlainTextEdit()
        self.stat_edit.setReadOnly(True)
        self.stat_edit.setMaximumHeight(150)
        self.stat_edit.setFont(QFont("Consolas", 9))
        traditional_layout.addWidget(QLabel("📊 关键词统计"))
        traditional_layout.addWidget(self.stat_edit)
        
        traditional_tab.setLayout(traditional_layout)
        self.tab_widget.addTab(traditional_tab, "传统视图")
        
        # 虚拟化日志视图
        virtual_tab = QWidget()
        virtual_layout = QVBoxLayout()
        
        # 控制面板
        control_layout = QHBoxLayout()
        
        # 过滤控制
        control_layout.addWidget(QLabel("过滤:"))
        self.filter_checkbox = QCheckBox("启用过滤")
        self.filter_checkbox.stateChanged.connect(self._on_filter_enabled_changed)
        control_layout.addWidget(self.filter_checkbox)
        
        # 最大条目数控制
        control_layout.addWidget(QLabel("最大条目:"))
        self.max_entries_spinbox = QSpinBox()
        self.max_entries_spinbox.setRange(1000, 50000)
        self.max_entries_spinbox.setValue(self.max_log_entries)
        self.max_entries_spinbox.valueChanged.connect(self._on_max_entries_changed)
        control_layout.addWidget(self.max_entries_spinbox)
        
        # 清空按钮
        clear_button = QPushButton("清空日志")
        clear_button.clicked.connect(self._clear_virtual_logs)
        control_layout.addWidget(clear_button)
        
        control_layout.addStretch()
        virtual_layout.addLayout(control_layout)
        
        # 虚拟化列表
        virtual_layout.addWidget(QLabel("📋 虚拟化日志视图"))
        self.virtual_log_list = VirtualListWidget()
        self.virtual_log_list.set_data_loader(self._load_log_data)
        self.virtual_log_list.item_double_clicked.connect(self._on_log_item_double_clicked)
        virtual_layout.addWidget(self.virtual_log_list)
        
        virtual_tab.setLayout(virtual_layout)
        self.tab_widget.addTab(virtual_tab, "虚拟化视图")
        
        layout.addWidget(self.tab_widget)
        self.setLayout(layout)

    def _init_html_log(self):
        """初始化日志文件，使用现代HTML样式"""
        try:
            # 使用专门的xuanwu_logger来初始化日志文件
            import logging
            xuanwu_logger = logging.getLogger('xuanwu_log')
            startup_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            xuanwu_logger.info(f'📘 XuanWu 总日志系统启动 - {startup_time}')
        except Exception as e:
            print(f"初始化日志文件失败: {e}")

    def _on_filter_enabled_changed(self, state):
        """过滤启用状态改变"""
        if state == Qt.CheckState.Checked.value:
            self._perform_filter()
        else:
            self.filtered_log_entries = self.log_entries.copy()
            self.virtual_log_list.set_total_count(len(self.filtered_log_entries))
            self.virtual_log_list.refresh()
    
    def _on_max_entries_changed(self, value):
        """最大条目数改变"""
        self.max_log_entries = value
        self._trim_log_entries()
    
    def _clear_virtual_logs(self):
        """清空虚拟化日志"""
        self.log_entries.clear()
        self.filtered_log_entries.clear()
        self.virtual_log_list.set_total_count(0)
        self.virtual_log_list.refresh()
    
    def _perform_filter(self):
        """执行过滤"""
        if not self.filter_checkbox.isChecked():
            self.filtered_log_entries = self.log_entries.copy()
        else:
            filter_text = self.current_filter_text.lower()
            self.filtered_log_entries = [
                entry for entry in self.log_entries
                if filter_text in entry.get('message', '').lower()
            ]
        self.virtual_log_list.set_total_count(len(self.filtered_log_entries))
        self.virtual_log_list.refresh()
    
    def _load_log_data(self, start_index: int, count: int) -> List[Dict[str, Any]]:
        """为虚拟列表加载日志数据"""
        end_index = min(start_index + count, len(self.filtered_log_entries))
        result = []
        for entry in self.filtered_log_entries[start_index:end_index]:
            # 转换数据格式，虚拟化组件需要'text'字段
            result.append({
                'text': entry.get('message', ''),
                'timestamp': entry.get('timestamp'),
                'level': entry.get('level', 'info')
            })
        return result
    
    def _on_log_item_double_clicked(self, item_data: Dict[str, Any]):
        """日志项双击事件"""
        # 可以在这里实现详细信息显示
        pass
    
    def _trim_log_entries(self):
        """修剪日志条目数量"""
        if len(self.log_entries) > self.max_log_entries:
            self.log_entries = self.log_entries[-self.max_log_entries:]
            self._perform_filter()

    def append_log(self, msg: str):
        """追加日志到面板和 HTML 文件"""
        try:
            # 使用正则去掉重复的时间戳
            # 这里确保日志只保留一次完整的时间戳
            msg = re.sub(r'(\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\])\s*\[\d{2}:\d{2}:\d{2}\]', r'\1', msg)

            # 显示在 UI 上
            self.text_edit.appendPlainText(msg)
            
            # 添加到虚拟化日志
            log_level = self._extract_log_level(msg)
            log_entry = {
                'timestamp': datetime.datetime.now(),
                'message': msg,
                'level': log_level
            }
            self.log_entries.append(log_entry)
            self._trim_log_entries()
            
            # 如果过滤启用，更新过滤结果
            if self.filter_checkbox.isChecked():
                self.filter_timer.start(300)  # 300ms 防抖
            else:
                self.filtered_log_entries = self.log_entries.copy()
                self.virtual_log_list.set_total_count(len(self.filtered_log_entries))
                self.virtual_log_list.refresh()

            # 使用专门的xuanwu_logger写入日志
            import logging
            xuanwu_logger = logging.getLogger('xuanwu_log')
            if log_level == "调试":
                xuanwu_logger.debug(msg)
            elif log_level == "信息":
                xuanwu_logger.info(msg)
            elif log_level == "警告":
                xuanwu_logger.warning(msg)
            elif log_level == "错误":
                xuanwu_logger.error(msg)
            elif log_level == "严重":
                xuanwu_logger.critical(msg)
            else:
                xuanwu_logger.info(msg)

            # 滚动到底部
            scrollbar = self.text_edit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

        except Exception as e:
            print(f"日志写入失败: {e}")

    def _extract_log_level(self, msg: str) -> str:
        """提取日志等级"""
        msg_lower = msg.lower()
        if "debug" in msg_lower or "调试" in msg:
            return "调试"
        elif "info" in msg_lower or "信息" in msg:
            return "信息"
        elif "warning" in msg_lower or "警告" in msg:
            return "警告"
        elif "error" in msg_lower or "错误" in msg:
            return "错误"
        elif "critical" in msg_lower or "严重" in msg:
            return "严重"
        else:
            return "信息"
    


    def update_statistics(self, stats: dict):
        """更新关键词统计区域"""
        try:
            self.stat_edit.clear()
            
            # 解析并存储统计数据
            total_recognitions = 0
            keyword_hits = 0
            
            for k, v in stats.items():
                self.stat_edit.appendPlainText(f"{k}：{v} 次")
                # 累计关键词命中次数
                if isinstance(v, (int, float)):
                    keyword_hits += int(v)
                    total_recognitions += 1
            
            # 更新存储的统计数据
            self.current_statistics["keyword_hits"] = keyword_hits
            self.current_statistics["total_recognitions"] = total_recognitions
            
            # 更新最后识别时间
            import datetime
            self.current_statistics["last_recognition_time"] = datetime.datetime.now()
            
        except Exception as e:
            print(f"更新统计信息失败: {e}")
    
    def refresh_ui_text(self):
        """刷新UI文本的国际化显示"""
        try:
            from core.i18n import t
            
            # 更新标签页标题
            self.tab_widget.setTabText(0, t('传统视图'))
            self.tab_widget.setTabText(1, t('虚拟化视图'))
            
            # 更新复选框文本
            self.filter_checkbox.setText(t('enable_filter'))
            
            # 更新按钮文本
            if hasattr(self, 'clear_button'):
                self.clear_button.setText(t('clear_log'))
            
        except Exception as e:
            import logging
            logging.error(f"刷新LogPanel UI文本时出错: {e}")
    
    def get_statistics(self):
        """获取日志统计信息"""
        try:
            # 返回存储的真实统计数据
            if hasattr(self, 'current_statistics'):
                return self.current_statistics.copy()
            else:
                # 如果没有存储的统计数据，返回默认值
                return {
                    "total_recognitions": 0,
                    "keyword_hits": 0,
                    "last_recognition_time": "N/A"
                }
            
        except Exception as e:
            import logging
            logging.error(f"获取日志统计信息时出错: {e}")
            return {
                "total_recognitions": 0,
                "keyword_hits": 0,
                "last_recognition_time": "N/A"
            }
