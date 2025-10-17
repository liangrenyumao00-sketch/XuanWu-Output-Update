import os
import json
from datetime import datetime
from typing import Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox,
    QCheckBox, QGroupBox, QTextEdit, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFormLayout, QFrame, QSplitter
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from core.cloud_sync import CloudSyncManager, CloudSyncThread

class CloudSyncDialog(QDialog):
    """云同步设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("云同步设置")
        self.setFixedSize(800, 600)
        
        # 应用主题样式
        self.apply_theme_styles()
        
        # 初始化云同步管理器
        self.sync_manager = CloudSyncManager()
        self.sync_thread = None
        
        # 连接信号
        self.sync_manager.sync_progress.connect(self.update_sync_progress)
        self.sync_manager.sync_completed.connect(self.on_sync_completed)
        self.sync_manager.conflict_detected.connect(self.handle_sync_conflict)
        
        self.setup_ui()
        self.load_config()
        
        # 状态更新定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)  # 每5秒更新一次状态
        
    def setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 服务器设置标签页
        self.setup_server_tab()
        
        # 同步设置标签页
        self.setup_sync_tab()
        
        # 同步状态标签页
        self.setup_status_tab()
        
        layout.addWidget(self.tab_widget)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self.test_connection)
        
        self.sync_now_btn = QPushButton("立即同步")
        self.sync_now_btn.clicked.connect(self.sync_now)
        
        self.save_btn = QPushButton("保存设置")
        self.save_btn.clicked.connect(self.save_config)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        
        button_layout.addWidget(self.test_btn)
        button_layout.addWidget(self.sync_now_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
    def setup_server_tab(self):
        """设置服务器配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 启用云同步
        self.enable_sync_cb = QCheckBox("启用云同步功能")
        layout.addWidget(self.enable_sync_cb)
        
        # 服务器类型
        server_group = QGroupBox("云服务配置")
        server_layout = QFormLayout(server_group)
        
        self.service_type_combo = QComboBox()
        # 添加服务类型选项
        self.service_type_combo.addItem("WebDAV服务器", "webdav")
        self.service_type_combo.addItem("FTP服务器", "ftp")
        self.service_type_combo.addItem("自定义API接口", "custom_api")
        self.service_type_combo.currentTextChanged.connect(self.on_service_type_changed)
        server_layout.addRow("服务类型:", self.service_type_combo)
        
        self.server_url_edit = QLineEdit()
        self.server_url_edit.setPlaceholderText("例如: https://your-server.com/webdav")
        server_layout.addRow("服务器地址:", self.server_url_edit)
        
        self.username_edit = QLineEdit()
        server_layout.addRow("用户名:", self.username_edit)
        
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        server_layout.addRow("密码:", self.password_edit)
        
        layout.addWidget(server_group)
        
        # 安全设置
        security_group = QGroupBox("安全设置")
        security_layout = QFormLayout(security_group)
        
        self.encryption_cb = QCheckBox("启用数据加密")
        self.encryption_cb.setChecked(True)
        security_layout.addRow(self.encryption_cb)
        
        # 设备ID显示
        self.device_id_label = QLabel()
        self.device_id_label.setStyleSheet("color: gray; font-family: monospace;")
        security_layout.addRow("设备ID:", self.device_id_label)
        
        layout.addWidget(security_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "服务器设置")
        
    def setup_sync_tab(self):
        """设置同步选项标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 自动同步设置
        auto_group = QGroupBox("自动同步")
        auto_layout = QFormLayout(auto_group)
        
        self.auto_sync_cb = QCheckBox("启用自动同步")
        auto_layout.addRow(self.auto_sync_cb)
        
        self.sync_interval_spin = QSpinBox()
        self.sync_interval_spin.setRange(5, 1440)  # 5分钟到24小时
        self.sync_interval_spin.setValue(30)
        self.sync_interval_spin.setSuffix(" 分钟")
        auto_layout.addRow("同步间隔:", self.sync_interval_spin)
        
        layout.addWidget(auto_group)
        
        # 同步内容设置
        content_group = QGroupBox("同步内容")
        content_layout = QVBoxLayout(content_group)
        
        self.sync_keywords_cb = QCheckBox("关键词列表")
        self.sync_keywords_cb.setChecked(True)
        content_layout.addWidget(self.sync_keywords_cb)
        
        self.sync_settings_cb = QCheckBox("应用设置")
        self.sync_settings_cb.setChecked(True)
        content_layout.addWidget(self.sync_settings_cb)
        
        self.sync_logs_cb = QCheckBox("日志文件（最近7天）")
        content_layout.addWidget(self.sync_logs_cb)
        
        self.sync_screenshots_cb = QCheckBox("截图文件（最近100张）")
        content_layout.addWidget(self.sync_screenshots_cb)
        
        layout.addWidget(content_group)
        
        # 冲突处理设置
        conflict_group = QGroupBox("冲突处理")
        conflict_layout = QFormLayout(conflict_group)
        
        self.conflict_combo = QComboBox()
        # 添加冲突解决策略选项
        self.conflict_combo.addItem("询问用户", "ask")
        self.conflict_combo.addItem("保留本地版本", "local")
        self.conflict_combo.addItem("使用云端版本", "remote")
        self.conflict_combo.addItem("尝试合并", "merge")
        conflict_layout.addRow("冲突解决策略:", self.conflict_combo)
        
        layout.addWidget(conflict_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "同步设置")
        
    def setup_status_tab(self):
        """设置同步状态标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 当前状态
        status_group = QGroupBox("同步状态")
        status_layout = QFormLayout(status_group)
        
        self.status_label = QLabel("未知")
        status_layout.addRow("当前状态:", self.status_label)
        
        self.last_sync_label = QLabel("从未同步")
        status_layout.addRow("上次同步:", self.last_sync_label)
        
        self.next_sync_label = QLabel("未设置")
        status_layout.addRow("下次同步:", self.next_sync_label)
        
        layout.addWidget(status_group)
        
        # 同步进度
        progress_group = QGroupBox("同步进度")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        progress_layout.addWidget(self.progress_label)
        
        layout.addWidget(progress_group)
        
        # 同步日志
        log_group = QGroupBox("同步日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        # 日志控制按钮
        log_btn_layout = QHBoxLayout()
        
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self.clear_log)
        
        self.export_log_btn = QPushButton("导出日志")
        self.export_log_btn.clicked.connect(self.export_log)
        
        log_btn_layout.addWidget(self.clear_log_btn)
        log_btn_layout.addWidget(self.export_log_btn)
        log_btn_layout.addStretch()
        
        log_layout.addLayout(log_btn_layout)
        
        layout.addWidget(log_group)
        
        self.tab_widget.addTab(tab, "同步状态")
        
    def on_service_type_changed(self, text):
        """服务类型改变时更新界面"""
        # 获取当前选中项的数据值
        current_index = self.service_type_combo.currentIndex()
        service_type = self.service_type_combo.itemData(current_index)
        
        if service_type == "webdav":
            self.server_url_edit.setPlaceholderText("例如: https://your-server.com/webdav")
        elif service_type == "ftp":
            self.server_url_edit.setPlaceholderText("例如: ftp.your-server.com:21")
        elif service_type == "custom_api":
            self.server_url_edit.setPlaceholderText("例如: https://api.your-server.com")
            
    def load_config(self):
        """加载配置"""
        try:
            config = self.sync_manager.get_sync_config()
            
            # 服务器设置
            self.enable_sync_cb.setChecked(config.get('enabled', False))
            
            service_type = config.get('service_type', 'webdav')
            index = self.service_type_combo.findData(service_type)
            if index >= 0:
                self.service_type_combo.setCurrentIndex(index)
                
            self.server_url_edit.setText(config.get('server_url', ''))
            self.username_edit.setText(config.get('username', ''))
            self.password_edit.setText(config.get('password', ''))
            self.encryption_cb.setChecked(config.get('encryption_enabled', True))
            self.device_id_label.setText(config.get('device_id', 'unknown'))
            
            # 同步设置
            self.auto_sync_cb.setChecked(config.get('auto_sync', True))
            self.sync_interval_spin.setValue(config.get('sync_interval', 30))
            
            sync_items = config.get('sync_items', {})
            self.sync_keywords_cb.setChecked(sync_items.get('keywords', True))
            self.sync_settings_cb.setChecked(sync_items.get('settings', True))
            self.sync_logs_cb.setChecked(sync_items.get('logs', False))
            self.sync_screenshots_cb.setChecked(sync_items.get('screenshots', False))
            
            conflict_resolution = config.get('conflict_resolution', 'ask')
            index = self.conflict_combo.findData(conflict_resolution)
            if index >= 0:
                self.conflict_combo.setCurrentIndex(index)
                
        except Exception as e:
            self.add_log(f"加载配置失败: {e}")
            
    def save_config(self):
        """保存配置"""
        try:
            config = {
                'enabled': self.enable_sync_cb.isChecked(),
                'service_type': self.service_type_combo.currentData(),
                'server_url': self.server_url_edit.text().strip(),
                'username': self.username_edit.text().strip(),
                'password': self.password_edit.text(),
                'sync_interval': self.sync_interval_spin.value(),
                'auto_sync': self.auto_sync_cb.isChecked(),
                'sync_items': {
                    'keywords': self.sync_keywords_cb.isChecked(),
                    'settings': self.sync_settings_cb.isChecked(),
                    'logs': self.sync_logs_cb.isChecked(),
                    'screenshots': self.sync_screenshots_cb.isChecked()
                },
                'conflict_resolution': self.conflict_combo.currentData(),
                'encryption_enabled': self.encryption_cb.isChecked(),
                'device_id': self.device_id_label.text()
            }
            
            if self.sync_manager.save_sync_config(config):
                # 重新启动自动同步
                self.sync_manager.stop_auto_sync()
                if config.get('enabled', False) and config.get('auto_sync', True):
                    self.sync_manager.start_auto_sync()
                    
                self.add_log("配置保存成功")
                QMessageBox.information(self, "成功", "云同步配置已保存")
            else:
                QMessageBox.warning(self, "错误", "保存配置失败")
                
        except Exception as e:
            error_msg = f"保存配置失败: {e}"
            self.add_log(error_msg)
            QMessageBox.critical(self, "错误", error_msg)
            
    def test_connection(self):
        """测试连接"""
        try:
            config = {
                'service_type': self.service_type_combo.currentData(),
                'server_url': self.server_url_edit.text().strip(),
                'username': self.username_edit.text().strip(),
                'password': self.password_edit.text()
            }
            
            self.test_btn.setEnabled(False)
            self.test_btn.setText("测试中...")
            
            success, message = self.sync_manager.test_connection(config)
            
            if success:
                self.add_log(f"连接测试成功: {message}")
                QMessageBox.information(self, "连接测试", message)
            else:
                self.add_log(f"连接测试失败: {message}")
                QMessageBox.warning(self, "连接测试", message)
                
        except Exception as e:
            error_msg = f"连接测试失败: {e}"
            self.add_log(error_msg)
            QMessageBox.critical(self, "错误", error_msg)
        finally:
            self.test_btn.setEnabled(True)
            self.test_btn.setText("测试连接")
            
    def sync_now(self):
        """立即同步"""
        try:
            if self.sync_thread and self.sync_thread.isRunning():
                QMessageBox.information(self, "提示", "同步操作正在进行中，请稍候")
                return
                
            # 先保存当前配置
            self.save_config()
            
            # 检查配置
            config = self.sync_manager.get_sync_config()
            if not config.get('enabled', False):
                QMessageBox.warning(self, "警告", "请先启用云同步功能")
                return
                
            if not all([config.get('server_url'), config.get('username'), config.get('password')]):
                QMessageBox.warning(self, "警告", "请先完善服务器配置信息")
                return
                
            # 显示进度
            self.progress_bar.setVisible(True)
            self.progress_label.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_label.setText("准备同步...")
            
            self.sync_now_btn.setEnabled(False)
            self.sync_now_btn.setText("同步中...")
            
            # 启动同步线程
            self.sync_thread = CloudSyncThread(self.sync_manager, 'upload')
            self.sync_thread.finished.connect(self.on_sync_thread_finished)
            self.sync_thread.start()
            
            self.add_log("开始手动同步...")
            
        except Exception as e:
            error_msg = f"启动同步失败: {e}"
            self.add_log(error_msg)
            QMessageBox.critical(self, "错误", error_msg)
            
    def update_sync_progress(self, value, message):
        """更新同步进度"""
        self.progress_bar.setValue(value)
        self.progress_label.setText(message)
        self.add_log(f"[{value}%] {message}")
        
    def on_sync_completed(self, success, message, stats):
        """同步完成"""
        if success:
            self.add_log(f"同步成功: {message}")
            if stats:
                self.add_log(f"同步统计: 数据大小 {stats.get('data_size', 0)} 字节, 同步项目 {stats.get('items_synced', 0)} 个")
        else:
            self.add_log(f"同步失败: {message}")
            
    def on_sync_thread_finished(self, success, message, stats):
        """同步线程完成"""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        
        self.sync_now_btn.setEnabled(True)
        self.sync_now_btn.setText("立即同步")
        
        if success:
            QMessageBox.information(self, "同步完成", message)
        else:
            QMessageBox.warning(self, "同步失败", message)
            
    def handle_sync_conflict(self, file_path, local_data, remote_data):
        """处理同步冲突"""
        self.add_log(f"检测到同步冲突: {file_path}")
        # 这里可以实现冲突解决对话框
        # 暂时使用简单的消息框
        reply = QMessageBox.question(
            self, "同步冲突",
            f"文件 {file_path} 存在冲突，是否使用本地版本？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.add_log("选择保留本地版本")
        else:
            self.add_log("选择使用云端版本")
            
    def update_status(self):
        """更新状态显示"""
        try:
            status = self.sync_manager.get_sync_status()
            
            # 更新状态标签
            if status.get('enabled', False):
                if status.get('is_syncing', False):
                    self.status_label.setText("同步中...")
                    self.status_label.setStyleSheet("color: orange;")
                else:
                    self.status_label.setText("已启用")
                    self.status_label.setStyleSheet("color: green;")
            else:
                self.status_label.setText("已禁用")
                self.status_label.setStyleSheet("color: red;")
                
            # 更新上次同步时间
            last_sync = status.get('last_sync_time')
            if last_sync:
                try:
                    sync_time = datetime.fromisoformat(last_sync)
                    self.last_sync_label.setText(sync_time.strftime('%Y-%m-%d %H:%M:%S'))
                except:
                    self.last_sync_label.setText(last_sync)
            else:
                self.last_sync_label.setText("从未同步")
                
            # 更新下次同步时间
            if status.get('enabled', False) and status.get('auto_sync', True):
                interval = status.get('sync_interval', 30)
                if last_sync:
                    try:
                        sync_time = datetime.fromisoformat(last_sync)
                        next_sync = sync_time.timestamp() + interval * 60
                        next_sync_dt = datetime.fromtimestamp(next_sync)
                        self.next_sync_label.setText(next_sync_dt.strftime('%Y-%m-%d %H:%M:%S'))
                    except:
                        self.next_sync_label.setText("计算中...")
                else:
                    self.next_sync_label.setText("等待首次同步")
            else:
                self.next_sync_label.setText("自动同步已禁用")
                
        except Exception as e:
            self.add_log(f"更新状态失败: {e}")
            
    def add_log(self, message):
        """添加日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_message = f"[{timestamp}] {message}"
        self.log_text.append(log_message)
        
        # 限制日志行数
        if self.log_text.document().blockCount() > 1000:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, 100)
            cursor.removeSelectedText()
            
    def clear_log(self):
        """清空日志"""
        self.log_text.clear()
        self.add_log("日志已清空")
        
    def export_log(self):
        """导出日志"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            
            filename, _ = QFileDialog.getSaveFileName(
                self, "导出同步日志",
                f"sync_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "文本文件 (*.txt)"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                    
                self.add_log(f"日志已导出到: {filename}")
                QMessageBox.information(self, "成功", f"日志已导出到:\n{filename}")
                
        except Exception as e:
            error_msg = f"导出日志失败: {e}"
            self.add_log(error_msg)
            QMessageBox.critical(self, "错误", error_msg)
            
    def closeEvent(self, event):
        """关闭事件"""
        # 停止状态更新定时器
        self.status_timer.stop()
        
        # 等待同步线程完成
        if self.sync_thread and self.sync_thread.isRunning():
            reply = QMessageBox.question(
                self, "确认关闭",
                "同步操作正在进行中，是否强制关闭？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            else:
                self.sync_thread.terminate()
    
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
                    QLineEdit {
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
                    QSpinBox {
                        background-color: #555555;
                        color: #ffffff;
                        border: 1px solid #666666;
                        border-radius: 4px;
                        padding: 4px;
                    }
                    QCheckBox {
                        color: #ffffff;
                        spacing: 8px;
                    }
                    QTextEdit {
                        background-color: #555555;
                        color: #ffffff;
                        border: 1px solid #666666;
                        border-radius: 4px;
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
                    QProgressBar {
                        border: 1px solid #666666;
                        border-radius: 4px;
                        background-color: #555555;
                    }
                    QProgressBar::chunk {
                        background-color: #0078d4;
                        border-radius: 3px;
                    }
                    QFrame {
                        color: #666666;
                    }
                """)
            else:
                self.setStyleSheet("")
        except Exception:
            pass
    
    def closeEvent(self, event):
        """关闭事件处理"""
        if hasattr(self, 'sync_thread') and self.sync_thread and self.sync_thread.isRunning():
            self.sync_thread.wait()
                
        event.accept()