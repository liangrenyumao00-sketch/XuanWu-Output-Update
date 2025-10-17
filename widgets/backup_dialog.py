import os
import json
import logging
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QCheckBox, QSpinBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QTextEdit, QMessageBox, QFileDialog, QTabWidget,
    QWidget, QGridLayout, QComboBox, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from core.backup_manager import BackupManager, BackupThread
from core.enhanced_logger import enhanced_logger

class BackupDialog(QDialog):
    """备份管理对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        enhanced_logger.debug_function_call("BackupDialog.__init__")
        enhanced_logger.debug_memory_snapshot("备份对话框初始化前")
        logging.debug("初始化备份管理对话框")
        
        self.backup_manager = BackupManager()
        self.backup_thread = None
        
        # 应用主题样式
        self.apply_theme_styles()
        
        self.init_ui()
        self.connect_signals()
        self.load_backup_config()
        self.refresh_backup_list()
        
        enhanced_logger.debug_memory_snapshot("备份对话框初始化后")
        logging.debug("备份管理对话框初始化完成")
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("备份管理")
        self.setFixedSize(600, 500)
        
        layout = QVBoxLayout()
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 备份设置标签页
        self.settings_tab = self.create_settings_tab()
        self.tab_widget.addTab(self.settings_tab, "备份设置")
        
        # 备份管理标签页
        self.management_tab = self.create_management_tab()
        self.tab_widget.addTab(self.management_tab, "备份管理")
        
        layout.addWidget(self.tab_widget)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("保存设置")
        self.save_btn.clicked.connect(self.save_backup_config)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def create_settings_tab(self):
        """创建备份设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 自动备份设置
        auto_group = QGroupBox("自动备份设置")
        auto_layout = QGridLayout()
        
        self.auto_backup_cb = QCheckBox("启用自动备份")
        auto_layout.addWidget(self.auto_backup_cb, 0, 0, 1, 2)
        
        auto_layout.addWidget(QLabel("备份间隔(小时):"), 1, 0)
        self.backup_interval_spin = QSpinBox()
        self.backup_interval_spin.setRange(1, 168)  # 1小时到7天
        self.backup_interval_spin.setValue(24)
        auto_layout.addWidget(self.backup_interval_spin, 1, 1)
        
        auto_layout.addWidget(QLabel("最大备份数量:"), 2, 0)
        self.max_backups_spin = QSpinBox()
        self.max_backups_spin.setRange(1, 100)
        self.max_backups_spin.setValue(10)
        auto_layout.addWidget(self.max_backups_spin, 2, 1)
        
        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)
        
        # 备份内容设置
        content_group = QGroupBox("备份内容")
        content_layout = QVBoxLayout()
        
        self.backup_logs_cb = QCheckBox("备份日志文件")
        self.backup_logs_cb.setChecked(True)
        content_layout.addWidget(self.backup_logs_cb)
        
        self.backup_screenshots_cb = QCheckBox("备份截图文件")
        self.backup_screenshots_cb.setChecked(True)
        content_layout.addWidget(self.backup_screenshots_cb)
        
        self.backup_settings_cb = QCheckBox("备份设置文件")
        self.backup_settings_cb.setChecked(True)
        content_layout.addWidget(self.backup_settings_cb)
        
        self.backup_keywords_cb = QCheckBox("备份关键词文件")
        self.backup_keywords_cb.setChecked(True)
        content_layout.addWidget(self.backup_keywords_cb)
        
        content_group.setLayout(content_layout)
        layout.addWidget(content_group)
        
        # 其他功能分组
        other_group = QGroupBox("其他功能")
        other_layout = QVBoxLayout()
        
        self.auto_upload_cb = QCheckBox("自动上传日志到服务器")
        other_layout.addWidget(self.auto_upload_cb)
        
        # 服务器配置
        server_layout = QHBoxLayout()
        server_layout.addWidget(QLabel("服务器地址:"))
        self.server_url_edit = QLineEdit()
        self.server_url_edit.setPlaceholderText("https://your-log-server.com/api/logs")
        server_layout.addWidget(self.server_url_edit)
        other_layout.addLayout(server_layout)
        
        # 添加手动上传按钮
        upload_layout = QHBoxLayout()
        self.manual_upload_btn = QPushButton("立即上传日志")
        self.manual_upload_btn.clicked.connect(self.upload_logs_to_server)
        upload_layout.addWidget(self.manual_upload_btn)
        upload_layout.addStretch()
        other_layout.addLayout(upload_layout)
        
        self.export_history_btn = QPushButton("历史数据导出")
        self.export_history_btn.clicked.connect(self.export_history_data)
        other_layout.addWidget(self.export_history_btn)
        
        other_group.setLayout(other_layout)
        layout.addWidget(other_group)
        
        # 立即备份按钮
        backup_now_layout = QHBoxLayout()
        self.backup_now_btn = QPushButton("立即创建备份")
        self.backup_now_btn.clicked.connect(self.create_backup_now)
        backup_now_layout.addWidget(self.backup_now_btn)
        backup_now_layout.addStretch()
        
        layout.addLayout(backup_now_layout)
        
        # 进度条和状态
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
        
    def create_management_tab(self):
        """创建备份管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 备份列表
        list_layout = QHBoxLayout()
        list_layout.addWidget(QLabel("现有备份:"))
        list_layout.addStretch()
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_backup_list)
        list_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(list_layout)
        
        # 备份表格
        self.backup_table = QTableWidget()
        self.backup_table.setColumnCount(4)
        self.backup_table.setHorizontalHeaderLabels(["备份名称", "创建时间", "大小", "操作"])
        self.backup_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.backup_table)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.restore_btn = QPushButton("恢复选中备份")
        self.restore_btn.clicked.connect(self.restore_selected_backup)
        button_layout.addWidget(self.restore_btn)
        
        self.delete_btn = QPushButton("删除选中备份")
        self.delete_btn.clicked.connect(self.delete_selected_backup)
        button_layout.addWidget(self.delete_btn)
        
        self.export_btn = QPushButton("导出备份")
        self.export_btn.clicked.connect(self.export_backup)
        button_layout.addWidget(self.export_btn)
        
        self.import_btn = QPushButton("导入备份")
        self.import_btn.clicked.connect(self.import_backup)
        button_layout.addWidget(self.import_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 备份统计信息
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("")
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)
        
        widget.setLayout(layout)
        return widget
        
    def connect_signals(self):
        """连接信号"""
        self.backup_manager.backup_progress.connect(self.update_progress)
        self.backup_manager.backup_completed.connect(self.backup_completed)
        
    def load_backup_config(self):
        """加载备份配置"""
        enhanced_logger.debug_function_call("load_backup_config")
        enhanced_logger.debug_performance("加载备份配置开始")
        logging.debug("加载备份配置")
        
        try:
            config = self.backup_manager.get_backup_config()
            
            self.auto_backup_cb.setChecked(config.get('auto_backup', True))
            self.backup_interval_spin.setValue(config.get('backup_interval', 24))
            self.max_backups_spin.setValue(config.get('max_backups', 10))
            
            self.backup_logs_cb.setChecked(config.get('backup_logs', True))
            self.backup_screenshots_cb.setChecked(config.get('backup_screenshots', True))
            self.backup_settings_cb.setChecked(config.get('backup_settings', True))
            self.backup_keywords_cb.setChecked(config.get('backup_keywords', True))
            
            logging.debug(f"备份配置加载完成 - 自动备份: {config.get('auto_backup', True)}, 间隔: {config.get('backup_interval', 24)}小时")
            
            # 加载其他功能设置
            from core.settings import load_settings
            settings = load_settings()
            self.auto_upload_cb.setChecked(settings.get('auto_upload_log', False))
            self.server_url_edit.setText(settings.get('log_server_url', 'https://httpbin.org/post'))
            
            enhanced_logger.debug_performance("加载备份配置完成")
        except Exception as e:
            enhanced_logger.debug_error(f"加载备份配置失败: {e}")
            logging.error(f"加载备份配置失败: {e}")
        
    def save_backup_config(self):
        """保存备份配置"""
        enhanced_logger.debug_function_call("save_backup_config")
        enhanced_logger.debug_performance("保存备份配置开始")
        logging.debug("保存备份配置")
        
        try:
            config = {
                'auto_backup': self.auto_backup_cb.isChecked(),
                'backup_interval': self.backup_interval_spin.value(),
                'max_backups': self.max_backups_spin.value(),
                'backup_logs': self.backup_logs_cb.isChecked(),
                'backup_screenshots': self.backup_screenshots_cb.isChecked(),
                'backup_settings': self.backup_settings_cb.isChecked(),
                'backup_keywords': self.backup_keywords_cb.isChecked()
            }
            
            logging.debug(f"备份配置: 自动备份={config['auto_backup']}, 间隔={config['backup_interval']}小时, 最大数量={config['max_backups']}")
            
            self.backup_manager.update_backup_config(config)
            
            # 保存其他功能设置
            from core.settings import load_settings, save_settings
            settings = load_settings()
            auto_upload_enabled = self.auto_upload_cb.isChecked()
            settings['auto_upload_log'] = auto_upload_enabled
            settings['log_server_url'] = self.server_url_edit.text().strip() or 'https://httpbin.org/post'
            save_settings(settings)
            
            logging.debug(f"其他设置保存完成 - 自动上传日志: {auto_upload_enabled}")
            
            # 如果启用了自动上传日志，立即执行一次上传
            if auto_upload_enabled:
                logging.debug("启用自动上传，立即执行一次上传")
                self.upload_logs_to_server()
            
            QMessageBox.information(self, "成功", "备份设置已保存")
            enhanced_logger.debug_performance("保存备份配置完成")
        except Exception as e:
            enhanced_logger.debug_error(f"保存备份配置失败: {e}")
            logging.error(f"保存备份配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存备份配置失败: {e}")
        
    def create_backup_now(self):
        """立即创建备份"""
        enhanced_logger.debug_function_call("create_backup_now")
        enhanced_logger.debug_performance("立即创建备份开始")
        logging.debug("用户请求立即创建备份")
        
        if self.backup_thread and self.backup_thread.isRunning():
            logging.debug("备份线程正在运行，拒绝新的备份请求")
            QMessageBox.warning(self, "警告", "备份操作正在进行中，请稍候...")
            return
            
        try:
            self.backup_now_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            logging.debug("备份界面状态已更新")
            
            # 先保存当前配置
            self.save_backup_config()
            
            # 创建备份线程
            self.backup_thread = BackupThread(self.backup_manager, 'create')
            self.backup_thread.finished.connect(self.backup_thread_finished)
            self.backup_thread.start()
            
            logging.debug("备份线程已启动")
            enhanced_logger.debug_performance("立即创建备份启动完成")
        except Exception as e:
            enhanced_logger.debug_error(f"启动备份失败: {e}")
            logging.error(f"启动备份失败: {e}")
            self.backup_now_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "错误", f"启动备份失败: {e}")
        
    def refresh_backup_list(self):
        """刷新备份列表"""
        enhanced_logger.debug_function_call("refresh_backup_list")
        enhanced_logger.debug_performance("刷新备份列表开始")
        logging.debug("刷新备份列表")
        
        try:
            backups = self.backup_manager.list_backups()
            logging.debug(f"获取到备份数量: {len(backups)}")
            
            self.backup_table.setRowCount(len(backups))
            
            for row, backup in enumerate(backups):
                # 备份名称
                name_item = QTableWidgetItem(backup['name'])
                logging.debug(f"处理备份项: {backup['name']}")
                self.backup_table.setItem(row, 0, name_item)
                
                # 创建时间
                time_str = backup['created_time'].strftime('%Y-%m-%d %H:%M:%S')
                time_item = QTableWidgetItem(time_str)
                self.backup_table.setItem(row, 1, time_item)
                
                # 文件大小
                size_mb = backup['size'] / (1024 * 1024)
                size_item = QTableWidgetItem(f"{size_mb:.1f} MB")
                self.backup_table.setItem(row, 2, size_item)
                
                # 操作按钮（这里简化为显示路径）
                path_item = QTableWidgetItem(backup['path'])
                path_item.setFlags(path_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.backup_table.setItem(row, 3, path_item)
            
            # 更新统计信息
            total_size = self.backup_manager.get_backup_size()
            size_mb = total_size / (1024 * 1024)
            self.stats_label.setText(f"总计 {len(backups)} 个备份，占用空间 {size_mb:.1f} MB")
        except Exception as e:
            enhanced_logger.error(f"刷新备份列表失败: {e}")
            QMessageBox.critical(self, "错误", f"刷新备份列表失败: {e}")
        
    def restore_selected_backup(self):
        """恢复选中的备份"""
        current_row = self.backup_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请选择要恢复的备份")
            return
            
        backup_path = self.backup_table.item(current_row, 3).text()
        backup_name = self.backup_table.item(current_row, 0).text()
        
        reply = QMessageBox.question(
            self, "确认恢复", 
            f"确定要恢复备份 '{backup_name}' 吗？\n\n这将覆盖当前的数据文件。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.backup_thread and self.backup_thread.isRunning():
                QMessageBox.warning(self, "警告", "备份操作正在进行中，请稍候...")
                return
                
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # 创建恢复线程
            self.backup_thread = BackupThread(self.backup_manager, 'restore', backup_path)
            self.backup_thread.finished.connect(self.backup_thread_finished)
            self.backup_thread.start()
            
    def delete_selected_backup(self):
        """删除选中的备份"""
        current_row = self.backup_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请选择要删除的备份")
            return
            
        backup_path = self.backup_table.item(current_row, 3).text()
        backup_name = self.backup_table.item(current_row, 0).text()
        
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除备份 '{backup_name}' 吗？\n\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success, message = self.backup_manager.delete_backup(backup_path)
            if success:
                QMessageBox.information(self, "成功", message)
                self.refresh_backup_list()
            else:
                QMessageBox.critical(self, "错误", message)
                
    def export_backup(self):
        """导出备份"""
        current_row = self.backup_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请选择要导出的备份")
            return
            
        backup_path = self.backup_table.item(current_row, 3).text()
        backup_name = self.backup_table.item(current_row, 0).text()
        
        export_path, _ = QFileDialog.getSaveFileName(
            self, "导出备份", f"{backup_name}.zip", "ZIP文件 (*.zip)"
        )
        
        if export_path:
            try:
                import shutil
                shutil.copy2(backup_path, export_path)
                QMessageBox.information(self, "成功", f"备份已导出到: {export_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")
                
    def import_backup(self):
        """导入备份"""
        import_path, _ = QFileDialog.getOpenFileName(
            self, "导入备份", "", "ZIP文件 (*.zip)"
        )
        
        if import_path:
            try:
                import shutil
                backup_name = os.path.splitext(os.path.basename(import_path))[0]
                target_path = os.path.join(self.backup_manager.backup_dir, f"{backup_name}.zip")
                
                # 如果目标文件已存在，添加时间戳
                if os.path.exists(target_path):
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    backup_name = f"{backup_name}_{timestamp}"
                    target_path = os.path.join(self.backup_manager.backup_dir, f"{backup_name}.zip")
                    
                shutil.copy2(import_path, target_path)
                QMessageBox.information(self, "成功", f"备份已导入: {backup_name}")
                self.refresh_backup_list()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入失败: {e}")
                
    def update_progress(self, value, message):
        """更新进度"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
        
    def backup_completed(self, success, message):
        """备份完成"""
        if success:
            QMessageBox.information(self, "成功", message)
            self.refresh_backup_list()
        else:
            QMessageBox.critical(self, "错误", message)
            
    def export_history_data(self):
        """导出历史数据"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            filename, _ = QFileDialog.getSaveFileName(
                self, "导出历史数据", "history_export.json", 
                "JSON Files (*.json);;All Files (*)"
            )
            if filename:
                # TODO: 实际导出数据，这里先创建一个空的JSON文件
                import json
                export_data = {
                    "export_time": datetime.now().isoformat(),
                    "version": "2.1.7",
                    "data": {}
                }
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "成功", "历史数据已导出！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {e}")
            
    def upload_logs_to_server(self):
        """上传日志到服务器"""
        try:
            import requests
            import os
            import json
            from datetime import datetime
            
            # 获取日志文件路径
            log_dir = os.path.join(os.getcwd(), "XuanWu_Logs")
            if not os.path.exists(log_dir):
                QMessageBox.warning(self, "警告", "日志目录不存在")
                return False
                
            # 收集日志文件
            log_files = []
            for filename in os.listdir(log_dir):
                if filename.endswith('.log') or filename.endswith('.txt'):
                    file_path = os.path.join(log_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            log_files.append({
                                'filename': filename,
                                'content': content,
                                'size': len(content)
                            })
                    except Exception as e:
                        print(f"读取日志文件失败 {filename}: {e}")
                        
            if not log_files:
                QMessageBox.information(self, "提示", "没有找到可上传的日志文件")
                return False
                
            # 准备上传数据
            upload_data = {
                'timestamp': datetime.now().isoformat(),
                'device_id': 'xuanwu_client',
                'version': '2.1.7',
                'log_files': log_files
            }
            
            # 获取配置的服务器地址
            from core.settings import load_settings
            settings = load_settings()
            server_url = settings.get('log_server_url', 'https://httpbin.org/post')
            
            response = requests.post(
                server_url,
                json=upload_data,
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                QMessageBox.information(self, "成功", f"日志已成功上传到服务器\n上传了 {len(log_files)} 个日志文件")
                return True
            else:
                QMessageBox.warning(self, "警告", f"上传失败，服务器返回状态码: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "错误", f"网络请求失败: {e}")
            return False
        except Exception as e:
            QMessageBox.critical(self, "错误", f"上传日志失败: {e}")
            return False
            
    def apply_theme_styles(self):
        """应用主题样式"""
        try:
            from utils.theme import get_current_theme
            current_theme = get_current_theme()
            
            if current_theme == 'dark':
                self.setStyleSheet("""
                    QDialog {
                        background-color: #464646;
                        color: #ffffff;
                    }
                    QLabel {
                        color: #ffffff;
                        background-color: transparent;
                    }
                    QTabWidget::pane {
                        border: 1px solid #666666;
                        background-color: #464646;
                    }
                    QTabBar::tab {
                        background-color: #555555;
                        color: #ffffff;
                        padding: 8px 16px;
                        margin: 2px;
                        border-radius: 4px;
                    }
                    QTabBar::tab:selected {
                        background-color: #0078d4;
                    }
                    QTabBar::tab:hover {
                        background-color: #666666;
                    }
                    QGroupBox {
                        color: #ffffff;
                        border: 1px solid #666666;
                        border-radius: 4px;
                        margin-top: 10px;
                        padding-top: 10px;
                    }
                    QGroupBox::title {
                        subcontrol-origin: margin;
                        left: 10px;
                        padding: 0 5px 0 5px;
                    }
                    QPushButton {
                        background-color: #555555;
                        color: #ffffff;
                        border: 1px solid #666666;
                        padding: 8px 16px;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background-color: #666666;
                    }
                    QTableWidget {
                        background-color: #555555;
                        color: #ffffff;
                        border: 1px solid #666666;
                        gridline-color: #666666;
                    }
                    QTableWidget::item {
                        border-bottom: 1px solid #666666;
                    }
                    QTableWidget::item:selected {
                        background-color: #0078d4;
                    }
                    QCheckBox {
                        color: #ffffff;
                        spacing: 8px;
                    }
                    QSpinBox {
                        background-color: #555555;
                        color: #ffffff;
                        border: 1px solid #666666;
                        border-radius: 4px;
                        padding: 4px;
                    }
                    QComboBox {
                        background-color: #555555;
                        color: #ffffff;
                        border: 1px solid #666666;
                        border-radius: 4px;
                        padding: 4px;
                    }
                    QLineEdit {
                        background-color: #555555;
                        color: #ffffff;
                        border: 1px solid #666666;
                        border-radius: 4px;
                        padding: 4px;
                    }
                    QTextEdit {
                        background-color: #555555;
                        color: #ffffff;
                        border: 1px solid #666666;
                        border-radius: 4px;
                    }
                    QProgressBar {
                        border: 1px solid #666666;
                        border-radius: 4px;
                        background-color: #555555;
                    }
                    QProgressBar::chunk {
                        background-color: #0078d4;
                        border-radius: 3px;
                    }
                """)
            else:
                self.setStyleSheet("")
        except Exception:
            pass
    
    def backup_thread_finished(self):
        """备份线程完成"""
        self.backup_now_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("")
        self.backup_thread = None