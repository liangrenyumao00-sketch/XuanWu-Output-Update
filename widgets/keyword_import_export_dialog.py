import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QRadioButton, QCheckBox, QGroupBox, QProgressBar, QTextEdit,
    QMessageBox, QFileDialog, QTabWidget, QWidget, QGridLayout,
    QComboBox, QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from core.keyword_manager import KeywordManager
from core.i18n import t

class KeywordImportThread(QThread):
    """关键词导入线程"""
    
    finished = pyqtSignal(bool, str, dict)
    
    def __init__(self, keyword_manager, file_path, file_type, merge_mode):
        super().__init__()
        self.keyword_manager = keyword_manager
        self.file_path = file_path
        self.file_type = file_type
        self.merge_mode = merge_mode
        
    def run(self):
        try:
            if self.file_type == 'csv':
                success, message, stats = self.keyword_manager.import_from_csv(self.file_path, self.merge_mode)
            elif self.file_type == 'json':
                success, message, stats = self.keyword_manager.import_from_json(self.file_path, self.merge_mode)
            elif self.file_type == 'txt':
                success, message, stats = self.keyword_manager.import_from_txt(self.file_path, self.merge_mode)
            else:
                success, message, stats = False, f"不支持的文件类型: {self.file_type}", {}
                
            self.finished.emit(success, message, stats)
            
        except Exception as e:
            self.finished.emit(False, f"导入过程中发生错误: {e}", {})

class KeywordExportThread(QThread):
    """关键词导出线程"""
    
    finished = pyqtSignal(bool, str)
    
    def __init__(self, keyword_manager, file_path, file_type, include_metadata=True, separator='\n'):
        super().__init__()
        self.keyword_manager = keyword_manager
        self.file_path = file_path
        self.file_type = file_type
        self.include_metadata = include_metadata
        self.separator = separator
        
    def run(self):
        try:
            if self.file_type == 'csv':
                success, message = self.keyword_manager.export_to_csv(self.file_path, self.include_metadata)
            elif self.file_type == 'json':
                success, message = self.keyword_manager.export_to_json(self.file_path, self.include_metadata)
            elif self.file_type == 'txt':
                success, message = self.keyword_manager.export_to_txt(self.file_path, self.separator)
            else:
                success, message = False, f"不支持的文件类型: {self.file_type}"
                
            self.finished.emit(success, message)
            
        except Exception as e:
            self.finished.emit(False, f"导出过程中发生错误: {e}")

class KeywordImportExportDialog(QDialog):
    """关键词导入导出对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.keyword_manager = KeywordManager()
        self.import_thread = None
        self.export_thread = None
        
        # 应用主题样式
        self.apply_theme_styles()
        
        self.init_ui()
        self.connect_signals()
        self.load_current_stats()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("关键词批量导入导出")
        self.setFixedSize(700, 600)
        
        layout = QVBoxLayout()
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 导入标签页
        self.import_tab = self.create_import_tab()
        self.tab_widget.addTab(self.import_tab, "批量导入")
        
        # 导出标签页
        self.export_tab = self.create_export_tab()
        self.tab_widget.addTab(self.export_tab, "批量导出")
        
        # 统计标签页
        self.stats_tab = self.create_stats_tab()
        self.tab_widget.addTab(self.stats_tab, "统计信息")
        
        layout.addWidget(self.tab_widget)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("刷新统计")
        self.refresh_btn.clicked.connect(self.load_current_stats)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        
        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def create_import_tab(self):
        """创建导入标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 文件选择区域
        file_group = QGroupBox(t("选择导入文件"))
        file_layout = QGridLayout()
        
        self.import_file_label = QLabel(t("未选择文件"))
        self.import_file_label.setStyleSheet("QLabel { border: 1px solid gray; padding: 5px; }")
        file_layout.addWidget(QLabel(t("文件路径:")), 0, 0)
        file_layout.addWidget(self.import_file_label, 0, 1)
        
        self.browse_import_btn = QPushButton(t("浏览文件"))
        self.browse_import_btn.clicked.connect(self.browse_import_file)
        file_layout.addWidget(self.browse_import_btn, 0, 2)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # 导入选项
        options_group = QGroupBox(t("导入选项"))
        options_layout = QVBoxLayout()
        
        # 合并模式
        merge_layout = QHBoxLayout()
        merge_layout.addWidget(QLabel(t("导入模式:")))
        
        self.merge_radio = QRadioButton(t("合并模式（保留现有关键词）"))
        self.merge_radio.setChecked(True)
        self.replace_radio = QRadioButton(t("替换模式（清空现有关键词）"))
        
        merge_layout.addWidget(self.merge_radio)
        merge_layout.addWidget(self.replace_radio)
        merge_layout.addStretch()
        
        options_layout.addLayout(merge_layout)
        
        # 文件格式提示
        format_label = QLabel(
            t("支持的文件格式:\n• CSV: 逗号分隔值文件，支持多种分隔符\n• JSON: 标准JSON格式，支持多种结构\n• TXT: 纯文本文件，支持多种分隔符")
        )
        format_label.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        options_layout.addWidget(format_label)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # 导入按钮和进度
        import_layout = QHBoxLayout()
        
        self.import_btn = QPushButton(t("开始导入"))
        self.import_btn.clicked.connect(self.start_import)
        self.import_btn.setEnabled(False)
        import_layout.addWidget(self.import_btn)
        import_layout.addStretch()
        
        layout.addLayout(import_layout)
        
        # 进度条
        self.import_progress = QProgressBar()
        self.import_progress.setVisible(False)
        layout.addWidget(self.import_progress)
        
        # 状态标签
        self.import_status = QLabel("")
        layout.addWidget(self.import_status)
        
        # 结果显示
        self.import_result = QTextEdit()
        self.import_result.setMaximumHeight(150)
        self.import_result.setVisible(False)
        layout.addWidget(self.import_result)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
        
    def create_export_tab(self):
        """创建导出标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 导出格式选择
        format_group = QGroupBox("选择导出格式")
        format_layout = QGridLayout()
        
        self.csv_radio = QRadioButton("CSV格式")
        self.csv_radio.setChecked(True)
        self.json_radio = QRadioButton("JSON格式")
        self.txt_radio = QRadioButton("TXT格式")
        
        format_layout.addWidget(self.csv_radio, 0, 0)
        format_layout.addWidget(self.json_radio, 0, 1)
        format_layout.addWidget(self.txt_radio, 0, 2)
        
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        # 导出选项
        export_options_group = QGroupBox("导出选项")
        export_options_layout = QVBoxLayout()
        
        # 包含元数据
        self.include_metadata_cb = QCheckBox("包含元数据信息（导出时间、数量等）")
        self.include_metadata_cb.setChecked(True)
        export_options_layout.addWidget(self.include_metadata_cb)
        
        # TXT分隔符选择
        separator_layout = QHBoxLayout()
        separator_layout.addWidget(QLabel("TXT分隔符:"))
        
        self.separator_combo = QComboBox()
        self.separator_combo.addItems(["换行符", "逗号", "分号", "制表符"])
        separator_layout.addWidget(self.separator_combo)
        separator_layout.addStretch()
        
        export_options_layout.addLayout(separator_layout)
        
        export_options_group.setLayout(export_options_layout)
        layout.addWidget(export_options_group)
        
        # 导出按钮
        export_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("选择位置并导出")
        self.export_btn.clicked.connect(self.start_export)
        export_layout.addWidget(self.export_btn)
        export_layout.addStretch()
        
        layout.addLayout(export_layout)
        
        # 进度条
        self.export_progress = QProgressBar()
        self.export_progress.setVisible(False)
        layout.addWidget(self.export_progress)
        
        # 状态标签
        self.export_status = QLabel("")
        layout.addWidget(self.export_status)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
        
    def create_stats_tab(self):
        """创建统计标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 基本统计
        basic_group = QGroupBox("基本统计")
        basic_layout = QGridLayout()
        
        self.total_count_label = QLabel("0")
        self.avg_length_label = QLabel("0")
        self.longest_label = QLabel("-")
        self.shortest_label = QLabel("-")
        
        basic_layout.addWidget(QLabel("关键词总数:"), 0, 0)
        basic_layout.addWidget(self.total_count_label, 0, 1)
        basic_layout.addWidget(QLabel("平均长度:"), 1, 0)
        basic_layout.addWidget(self.avg_length_label, 1, 1)
        basic_layout.addWidget(QLabel("最长关键词:"), 2, 0)
        basic_layout.addWidget(self.longest_label, 2, 1)
        basic_layout.addWidget(QLabel("最短关键词:"), 3, 0)
        basic_layout.addWidget(self.shortest_label, 3, 1)
        
        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)
        
        # 类型分布
        type_group = QGroupBox("类型分布")
        type_layout = QGridLayout()
        
        self.chinese_count_label = QLabel("0")
        self.english_count_label = QLabel("0")
        self.number_count_label = QLabel("0")
        self.mixed_count_label = QLabel("0")
        
        type_layout.addWidget(QLabel("中文关键词:"), 0, 0)
        type_layout.addWidget(self.chinese_count_label, 0, 1)
        type_layout.addWidget(QLabel("英文关键词:"), 1, 0)
        type_layout.addWidget(self.english_count_label, 1, 1)
        type_layout.addWidget(QLabel("数字关键词:"), 2, 0)
        type_layout.addWidget(self.number_count_label, 2, 1)
        type_layout.addWidget(QLabel("混合关键词:"), 3, 0)
        type_layout.addWidget(self.mixed_count_label, 3, 1)
        
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # 长度分布表格
        length_group = QGroupBox("长度分布")
        length_layout = QVBoxLayout()
        
        self.length_table = QTableWidget()
        self.length_table.setColumnCount(2)
        self.length_table.setHorizontalHeaderLabels(["字符长度", "数量"])
        self.length_table.horizontalHeader().setStretchLastSection(True)
        self.length_table.setMaximumHeight(200)
        
        length_layout.addWidget(self.length_table)
        length_group.setLayout(length_layout)
        layout.addWidget(length_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
        
    def connect_signals(self):
        """连接信号"""
        self.keyword_manager.import_progress.connect(self.update_import_progress)
        self.keyword_manager.export_progress.connect(self.update_export_progress)
        
    def browse_import_file(self):
        """浏览导入文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, t("选择关键词文件"), "", 
            t("所有支持格式 (*.csv *.json *.txt);;CSV文件 (*.csv);;JSON文件 (*.json);;文本文件 (*.txt)")
        )
        
        if file_path:
            self.import_file_label.setText(file_path)
            self.import_btn.setEnabled(True)
            
    def start_import(self):
        """开始导入"""
        file_path = self.import_file_label.text()
        if file_path == "未选择文件" or not os.path.exists(file_path):
            QMessageBox.warning(self, "警告", "请选择有效的导入文件")
            return
            
        if self.import_thread and self.import_thread.isRunning():
            QMessageBox.warning(self, "警告", "导入操作正在进行中，请稍候...")
            return
            
        # 确定文件类型
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext == '.csv':
            file_type = 'csv'
        elif file_ext == '.json':
            file_type = 'json'
        elif file_ext == '.txt':
            file_type = 'txt'
        else:
            QMessageBox.warning(self, "警告", "不支持的文件格式")
            return
            
        # 确定导入模式
        merge_mode = self.merge_radio.isChecked()
        
        # 显示进度条
        self.import_progress.setVisible(True)
        self.import_progress.setValue(0)
        self.import_btn.setEnabled(False)
        self.import_result.setVisible(False)
        
        # 创建导入线程
        self.import_thread = KeywordImportThread(
            self.keyword_manager, file_path, file_type, merge_mode
        )
        self.import_thread.finished.connect(self.import_finished)
        self.import_thread.start()
        
    def start_export(self):
        """开始导出"""
        if self.export_thread and self.export_thread.isRunning():
            QMessageBox.warning(self, "警告", "导出操作正在进行中，请稍候...")
            return
            
        # 确定导出格式
        if self.csv_radio.isChecked():
            file_type = 'csv'
            filter_str = "CSV文件 (*.csv)"
            default_name = "keywords.csv"
        elif self.json_radio.isChecked():
            file_type = 'json'
            filter_str = "JSON文件 (*.json)"
            default_name = "keywords.json"
        elif self.txt_radio.isChecked():
            file_type = 'txt'
            filter_str = "文本文件 (*.txt)"
            default_name = "keywords.txt"
        else:
            QMessageBox.warning(self, "警告", "请选择导出格式")
            return
            
        # 选择保存位置
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存关键词文件", default_name, filter_str
        )
        
        if not file_path:
            return
            
        # 获取导出选项
        include_metadata = self.include_metadata_cb.isChecked()
        
        # TXT分隔符
        separator_map = {
            "换行符": "\n",
            "逗号": ",",
            "分号": ";",
            "制表符": "\t"
        }
        separator = separator_map.get(self.separator_combo.currentText(), "\n")
        
        # 显示进度条
        self.export_progress.setVisible(True)
        self.export_progress.setValue(0)
        self.export_btn.setEnabled(False)
        
        # 创建导出线程
        self.export_thread = KeywordExportThread(
            self.keyword_manager, file_path, file_type, include_metadata, separator
        )
        self.export_thread.finished.connect(self.export_finished)
        self.export_thread.start()
        
    def update_import_progress(self, value, message):
        """更新导入进度"""
        self.import_progress.setValue(value)
        self.import_status.setText(message)
        
    def update_export_progress(self, value, message):
        """更新导出进度"""
        self.export_progress.setValue(value)
        self.export_status.setText(message)
        
    def import_finished(self, success, message, stats):
        """导入完成"""
        self.import_btn.setEnabled(True)
        self.import_progress.setVisible(False)
        self.import_status.setText("")
        
        if success:
            QMessageBox.information(self, t("导入成功"), message)
            
            # 显示详细统计
            if stats:
                result_text = f"{t('导入统计')}:\n"
                result_text += f"• {t('导入文件包含')}: {stats.get('imported_count', 0)} {t('个关键词')}\n"
                result_text += f"• {t('新增关键词')}: {stats.get('new_count', 0)} {t('个')}\n"
                result_text += f"• {t('当前总数')}: {stats.get('total_count', 0)} {t('个')}\n"
                if 'duplicates_removed' in stats:
                    result_text += f"• {t('去除重复')}: {stats['duplicates_removed']} {t('个')}\n"
                    
                self.import_result.setText(result_text)
                self.import_result.setVisible(True)
                
            # 刷新统计信息
            self.load_current_stats()

            # 导入成功后，刷新主窗口中的 KeywordPanel 显示
            try:
                parent = self.parent()
                if parent is not None and hasattr(parent, 'keyword_panel') and parent.keyword_panel is not None:
                    parent.keyword_panel.reload_keywords()
            except Exception as e:
                # 避免影响导入流程，仅记录日志
                import logging
                logging.error(f"刷新 KeywordPanel 显示失败: {e}")
        else:
            QMessageBox.critical(self, t("导入失败"), message)
        
        self.import_thread = None
        
    def export_finished(self, success, message):
        """导出完成"""
        self.export_btn.setEnabled(True)
        self.export_progress.setVisible(False)
        self.export_status.setText("")
        
        if success:
            QMessageBox.information(self, "导出成功", message)
        else:
            QMessageBox.critical(self, "导出失败", message)
            
        self.export_thread = None
        
    def load_current_stats(self):
        """加载当前统计信息"""
        try:
            stats = self.keyword_manager.get_import_stats()
            
            if stats:
                # 基本统计
                self.total_count_label.setText(str(stats.get('total_keywords', 0)))
                self.avg_length_label.setText(f"{stats.get('average_length', 0):.1f}")
                self.longest_label.setText(stats.get('longest_keyword', '-'))
                self.shortest_label.setText(stats.get('shortest_keyword', '-'))
                
                # 类型分布
                type_dist = stats.get('type_distribution', {})
                self.chinese_count_label.setText(str(type_dist.get('chinese', 0)))
                self.english_count_label.setText(str(type_dist.get('english', 0)))
                self.number_count_label.setText(str(type_dist.get('number', 0)))
                self.mixed_count_label.setText(str(type_dist.get('mixed', 0)))
                
                # 长度分布
                length_dist = stats.get('length_distribution', {})
                self.length_table.setRowCount(len(length_dist))
                
                for row, (length, count) in enumerate(sorted(length_dist.items())):
                    length_item = QTableWidgetItem(str(length))
                    count_item = QTableWidgetItem(str(count))
                    self.length_table.setItem(row, 0, length_item)
                    self.length_table.setItem(row, 1, count_item)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"加载统计信息失败: {e}")
    
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
                QRadioButton {
                    color: #ffffff;
                }
                QCheckBox {
                    color: #ffffff;
                    spacing: 8px;
                }
                QTextEdit {
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
                QComboBox {
                    background-color: #404040;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QSpinBox {
                    background-color: #404040;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QTableWidget {
                    background-color: #404040;
                    color: #ffffff;
                    border: 1px solid #555555;
                    gridline-color: #555555;
                }
                QTableWidget::item {
                    background-color: #404040;
                    color: #ffffff;
                }
                QHeaderView::section {
                    background-color: #505050;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QProgressBar {
                    background-color: #404040;
                    border: 1px solid #555555;
                    border-radius: 4px;
                }
                QProgressBar::chunk {
                    background-color: #0078d4;
                    border-radius: 4px;
                }
            """)
        else:
            # 浅色主题
            self.setStyleSheet("")