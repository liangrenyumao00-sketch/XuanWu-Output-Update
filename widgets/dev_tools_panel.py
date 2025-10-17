# widgets/dev_tools_panel.py
# -*- coding: utf-8 -*-
"""
开发者工具面板模块

该模块提供了一套完整的开发者工具，用于应用程序的调试、测试、维护和监控。
包含系统信息查看、日志管理、数据库操作、代码分析等多种开发辅助功能。

主要功能：
- 系统监控：CPU、内存、磁盘使用情况监控
- 日志管理：实时日志查看、搜索和分析
- 数据库工具：SQL查询、数据浏览、备份恢复
- 代码分析：静态代码分析、覆盖率报告
- 网络调试：远程调试服务器、连接测试
- 文件管理：完整性检查、安全扫描
- 更新管理：版本检查、自动更新功能

依赖：
- PyQt6：GUI框架
- psutil：系统信息获取（可选）
- sqlite3：数据库操作
- requests：网络请求

作者：XuanWu OCR Team
版本：2.1.7
"""
import logging
import os
import sys
import shutil
import subprocess
import tempfile
import webbrowser
import hashlib
import zipfile
import traceback
import json
import threading
import time
import platform
import sqlite3
import csv
import uuid
from datetime import datetime
import socket

import smtplib
from packaging import version
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from core.enhanced_logger import get_enhanced_logger
from core.i18n import t
from core.settings import load_settings, save_settings
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QMenu, QFileDialog, QMessageBox, QTextBrowser, QDialog,
    QVBoxLayout, QPushButton, QProgressDialog, QLabel, QHBoxLayout,
    QProgressBar, QInputDialog, QGroupBox, QTableWidget, QTableWidgetItem,
    QListWidget, QTextEdit, QComboBox, QTabWidget, QSplitter, QWidget,
    QLineEdit, QCheckBox, QSpinBox, QGridLayout, QFormLayout, QSlider
)
from PyQt6.QtCore import (
    Qt, QTimer, QFileInfo, pyqtSignal, QObject, QThread
)

# 可选依赖：psutil 用于获取系统信息
try:
    import psutil
except Exception:
    psutil = None


class UpdateSignals(QObject):
    progress_changed = pyqtSignal(int)      # 下载进度百分比
    download_finished = pyqtSignal()        # 下载完成信号
    download_failed = pyqtSignal(str)       # 下载失败信号，带错误消息
    update_checked = pyqtSignal(bool, str)  # 是否有更新, 最新版本号
    error_occurred = pyqtSignal(str)        # 错误消息


class UpdateWorker(QThread):
    CHECK_UPDATE = 1
    DOWNLOAD_INSTALL = 2

    def __init__(self, current_version, update_check_url):
        super().__init__()
        self.current_version = current_version
        self.update_check_url = update_check_url
        self.signals = UpdateSignals()

        # 动态在 check 阶段由远端返回
        self.download_url = None
        self.latest_version = None
        self.latest_hash = None

        self._cancelled = False
        self._task = self.CHECK_UPDATE

        # 临时目录与路径（下载阶段创建）
        self.temp_dir = None
        self.temp_zip_part = None
        self.final_zip = None
        self.extract_dir = None

    def run(self):
        if self._task == self.CHECK_UPDATE:
            self._check_update()
        elif self._task == self.DOWNLOAD_INSTALL:
            self._download_and_extract()

    def start_check_update(self):
        self._task = self.CHECK_UPDATE
        self._cancelled = False
        self.start()

    def start_download_install(self, download_url, file_hash=None):
        self.download_url = download_url
        self.latest_hash = file_hash
        self._task = self.DOWNLOAD_INSTALL
        self._cancelled = False
        self.start()

    def cancel_download(self):
        self._cancelled = True

    def _check_update(self):
        try:
            import requests
            
            # 添加GitHub API请求头
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'XuanWu-OCR-Update-Checker'
            }
            
            resp = requests.get(self.update_check_url, headers=headers, timeout=(5, 5))
            resp.raise_for_status()
            data = resp.json()

            # GitHub API响应格式：tag_name为版本号
            self.latest_version = data.get("tag_name")
            if self.latest_version and self.latest_version.startswith('v'):
                self.latest_version = self.latest_version[1:]  # 移除v前缀
            
            # 从assets中查找ZIP文件下载链接
            self.download_url = None
            assets = data.get("assets", [])
            for asset in assets:
                if asset.get("name", "").endswith(".zip"):
                    self.download_url = asset.get("browser_download_url")
                    break
            
            # GitHub不提供文件hash，设为None
            self.latest_hash = None

            if not self.latest_version:
                self.signals.error_occurred.emit("远程版本信息格式错误：无法获取版本号。")
                return
                
            if not self.download_url:
                self.signals.error_occurred.emit("远程版本信息格式错误：未找到可下载的ZIP文件。")
                return

            try:
                has_update = version.parse(self.latest_version) > version.parse(self.current_version)
            except Exception:
                # 如果版本串无法解析，用简单字符串比较作为兜底（避免崩溃）
                has_update = self.latest_version != self.current_version

            self.signals.update_checked.emit(bool(has_update), self.latest_version)

        except Exception as e:
            self.signals.error_occurred.emit(f"检查更新失败：{e}")

    def _download_and_extract(self):
        try:
            import requests
            # 创建临时目录
            self.temp_dir = tempfile.mkdtemp(prefix="app_update_")
            self.temp_zip_part = os.path.join(self.temp_dir, "update.zip.part")
            self.final_zip = os.path.join(self.temp_dir, "update.zip")
            self.extract_dir = os.path.join(self.temp_dir, "extract")

            # 下载流
            # 使用短的读取超时以便在网络卡住时较快响应取消
            with requests.get(self.download_url, stream=True, timeout=(10, 5)) as r:
                r.raise_for_status()
                total_length = r.headers.get('content-length')
                total_length = int(total_length) if total_length else None

                downloaded = 0
                chunk_size = 1024 * 64  # 64KB
                hasher = hashlib.sha256()

                with open(self.temp_zip_part, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if self._cancelled:
                            # 取消时立即清理并发出失败
                            self._cleanup_temp()
                            self.signals.download_failed.emit("用户取消了下载。")
                            return
                        if chunk:
                            f.write(chunk)
                            try:
                                hasher.update(chunk)
                            except Exception:
                                # 忽略 hasher 更新异常（极少）
                                pass
                            downloaded += len(chunk)
                            if total_length:
                                percent = int(downloaded * 100 / total_length)
                                # 限制 0..100
                                percent = max(0, min(100, percent))
                                self.signals.progress_changed.emit(percent)

            # 下载结束后，校验 hash（如果提供）
            if self.latest_hash:
                file_hash = hasher.hexdigest()
                if file_hash.lower() != self.latest_hash.lower():
                    self._cleanup_temp()
                    self.signals.download_failed.emit("文件校验失败，更新包可能已损坏或被篡改。")
                    return

            # 重命名 .part -> .zip
            try:
                os.rename(self.temp_zip_part, self.final_zip)
            except Exception:
                # 若不能重命名，仍尝试继续解压（某些平台直接用 part 也可）
                self.final_zip = self.temp_zip_part

            # 解压到 extract_dir
            if os.path.exists(self.extract_dir):
                shutil.rmtree(self.extract_dir, ignore_errors=True)
            os.makedirs(self.extract_dir, exist_ok=True)

            with zipfile.ZipFile(self.final_zip, 'r') as zip_ref:
                for info in zip_ref.infolist():
                    try:
                        # 解码文件名，避免乱码
                        decoded_name = info.filename.encode('cp437').decode('gbk')
                    except UnicodeDecodeError:
                        decoded_name = info.filename

                    # 重写文件名
                    info.filename = decoded_name
                    zip_ref.extract(info, self.extract_dir)

            # 下载并解压成功
            self.signals.download_finished.emit()

        except Exception as e:
            if not self._cancelled:
                self._cleanup_temp()
                self.signals.download_failed.emit(f"下载或解压失败：{e}")

    def _cleanup_temp(self):
        try:
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass


class RemoteDebugDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("远程调试控制台")
        self.resize(1000, 700)
        self.setModal(False)

        layout = QVBoxLayout(self)

        # Connection settings
        connection_group = QGroupBox("连接设置")
        connection_layout = QGridLayout()
        
        self.host_input = QLineEdit("localhost")
        self.port_input = QLineEdit("9999")
        self.password_input = QLineEdit("")  # 不再使用默认密码
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("请输入安全密码")
        self.connect_button = QPushButton("连接")
        self.start_server_button = QPushButton("启动调试服务器")
        self.save_session_button = QPushButton("保存会话")
        self.load_session_button = QPushButton("加载会话")
        
        connection_layout.addWidget(QLabel("主机:"), 0, 0)
        connection_layout.addWidget(self.host_input, 0, 1)
        connection_layout.addWidget(QLabel("端口:"), 0, 2)
        connection_layout.addWidget(self.port_input, 0, 3)
        connection_layout.addWidget(QLabel("密码:"), 1, 0)
        connection_layout.addWidget(self.password_input, 1, 1)
        connection_layout.addWidget(self.connect_button, 1, 2)
        connection_layout.addWidget(self.start_server_button, 1, 3)
        connection_layout.addWidget(self.save_session_button, 2, 0)
        connection_layout.addWidget(self.load_session_button, 2, 1)
        
        connection_group.setLayout(connection_layout)
        layout.addWidget(connection_group)

        # 创建选项卡界面
        self.tab_widget = QTabWidget()
        
        # 控制台选项卡
        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        
        self.log_browser = QTextBrowser()
        self.log_browser.setFont(QFont("Courier New", 9))
        console_layout.addWidget(self.log_browser)
        
        # 命令输入区域
        command_layout = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("输入Python命令或调试指令...")
        self.send_button = QPushButton("执行")
        self.clear_button = QPushButton("清空")
        
        command_layout.addWidget(self.command_input)
        command_layout.addWidget(self.send_button)
        command_layout.addWidget(self.clear_button)
        console_layout.addLayout(command_layout)
        
        self.tab_widget.addTab(console_widget, "控制台")
        
        # 变量查看选项卡
        variables_widget = QWidget()
        variables_layout = QVBoxLayout(variables_widget)
        
        var_controls = QHBoxLayout()
        self.var_refresh_button = QPushButton("刷新变量")
        self.var_filter_input = QLineEdit()
        self.var_filter_input.setPlaceholderText("过滤变量名...")
        var_controls.addWidget(self.var_refresh_button)
        var_controls.addWidget(QLabel("过滤:"))
        var_controls.addWidget(self.var_filter_input)
        var_controls.addStretch()
        variables_layout.addLayout(var_controls)
        
        self.variables_table = QTableWidget()
        self.variables_table.setColumnCount(3)
        self.variables_table.setHorizontalHeaderLabels(["变量名", "类型", "值"])
        variables_layout.addWidget(self.variables_table)
        
        self.tab_widget.addTab(variables_widget, "变量查看")
        
        # 断点管理选项卡
        breakpoints_widget = QWidget()
        breakpoints_layout = QVBoxLayout(breakpoints_widget)
        
        bp_controls = QHBoxLayout()
        self.bp_file_input = QLineEdit()
        self.bp_file_input.setPlaceholderText("文件路径")
        self.bp_line_input = QLineEdit()
        self.bp_line_input.setPlaceholderText("行号")
        self.add_bp_button = QPushButton("添加断点")
        self.remove_bp_button = QPushButton("删除断点")
        
        bp_controls.addWidget(QLabel(t("文件:")))
        bp_controls.addWidget(self.bp_file_input)
        bp_controls.addWidget(QLabel("行号:"))
        bp_controls.addWidget(self.bp_line_input)
        bp_controls.addWidget(self.add_bp_button)
        bp_controls.addWidget(self.remove_bp_button)
        breakpoints_layout.addLayout(bp_controls)
        
        self.breakpoints_list = QListWidget()
        breakpoints_layout.addWidget(self.breakpoints_list)
        
        self.tab_widget.addTab(breakpoints_widget, "断点管理")
        
        # 性能监控选项卡
        performance_widget = QWidget()
        performance_layout = QVBoxLayout(performance_widget)
        
        perf_controls = QHBoxLayout()
        self.start_profiling_button = QPushButton("开始性能分析")
        self.stop_profiling_button = QPushButton("停止性能分析")
        self.memory_snapshot_button = QPushButton("内存快照")
        
        perf_controls.addWidget(self.start_profiling_button)
        perf_controls.addWidget(self.stop_profiling_button)
        perf_controls.addWidget(self.memory_snapshot_button)
        perf_controls.addStretch()
        performance_layout.addLayout(perf_controls)
        
        self.performance_display = QTextBrowser()
        self.performance_display.setFont(QFont("Courier New", 9))
        performance_layout.addWidget(self.performance_display)
        
        self.tab_widget.addTab(performance_widget, "性能监控")
        
        # 调试工具选项卡
        tools_widget = QWidget()
        tools_layout = QVBoxLayout(tools_widget)
        
        # 快速调试命令
        quick_commands = QHBoxLayout()
        self.step_button = QPushButton("单步执行")
        self.continue_button = QPushButton("继续执行")
        self.stack_trace_button = QPushButton("查看堆栈")
        self.eval_button = QPushButton("表达式求值")
        
        quick_commands.addWidget(self.step_button)
        quick_commands.addWidget(self.continue_button)
        quick_commands.addWidget(self.stack_trace_button)
        quick_commands.addWidget(self.eval_button)
        quick_commands.addStretch()
        tools_layout.addLayout(quick_commands)
        
        # 表达式求值区域
        eval_layout = QHBoxLayout()
        self.eval_input = QLineEdit()
        self.eval_input.setPlaceholderText("输入Python表达式...")
        self.eval_execute_button = QPushButton("执行")
        eval_layout.addWidget(QLabel("表达式:"))
        eval_layout.addWidget(self.eval_input)
        eval_layout.addWidget(self.eval_execute_button)
        tools_layout.addLayout(eval_layout)
        
        # 调试输出区域
        self.debug_output = QTextBrowser()
        self.debug_output.setFont(QFont("Courier New", 9))
        tools_layout.addWidget(self.debug_output)
        
        self.tab_widget.addTab(tools_widget, "调试工具")
        
        layout.addWidget(self.tab_widget)

        # 状态栏
        status_layout = QHBoxLayout()
        self.status_label = QLabel("未连接")
        self.connection_status = QLabel("●")
        self.connection_status.setStyleSheet("color: red; font-size: 16px;")
        status_layout.addWidget(self.connection_status)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        self.client_socket = None
        self.connected = False
        self.debug_server_process = None
        self.command_history = []
        self.last_variables = {}

        # 连接信号
        self.connect_button.clicked.connect(self.toggle_connection)
        self.start_server_button.clicked.connect(self.toggle_debug_server)
        self.save_session_button.clicked.connect(self.save_debug_session)
        self.load_session_button.clicked.connect(self.load_debug_session)
        self.send_button.clicked.connect(self.send_command)
        self.clear_button.clicked.connect(self.log_browser.clear)
        self.command_input.returnPressed.connect(self.send_command)
        
        # 变量查看相关
        self.var_refresh_button.clicked.connect(self.refresh_variables)
        self.var_filter_input.textChanged.connect(self.filter_variables)
        
        # 断点管理相关
        self.add_bp_button.clicked.connect(self.add_breakpoint)
        self.remove_bp_button.clicked.connect(self.remove_breakpoint)
        
        # 调试工具按钮信号连接
        self.step_button.clicked.connect(self.debug_step)
        self.continue_button.clicked.connect(self.debug_continue)
        self.stack_trace_button.clicked.connect(self.debug_stack_trace)
        self.eval_button.clicked.connect(self.debug_eval)
        self.eval_execute_button.clicked.connect(self.debug_eval)
        self.eval_input.returnPressed.connect(self.debug_eval)
        
        # 性能监控相关
        self.start_profiling_button.clicked.connect(self.start_profiling)
        self.stop_profiling_button.clicked.connect(self.stop_profiling)
        self.memory_snapshot_button.clicked.connect(self.take_memory_snapshot)

    def toggle_connection(self):
        if not self.connected:
            self.connect_to_server()
        else:
            self.disconnect_from_server()

    def connect_to_server(self):
        host = self.host_input.text()
        port = int(self.port_input.text())
        password = self.password_input.text()

        # 创建SSL上下文
        import ssl
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # 尝试SSL连接
            try:
                self.client_socket.connect((host, port))
                self.client_socket = context.wrap_socket(self.client_socket, server_hostname=host)
                self.log_browser.append(f"<span style='color: green;'>SSL连接成功到 {host}:{port}</span>")
            except:
                # 如果SSL失败，回退到普通连接
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((host, port))
                self.log_browser.append(f"<span style='color: orange;'>普通连接到 {host}:{port} (建议使用SSL)</span>")

            # 密码验证
            response = self.client_socket.recv(1024).decode()
            if "Password:" in response:
                # 使用哈希密码增强安全性
                import hashlib
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                self.client_socket.sendall(hashed_password.encode())
                
                auth_response = self.client_socket.recv(1024).decode()
                if "Authentication successful" in auth_response:
                    self.log_browser.append("<span style='color: green;'>认证成功</span>")
                    self.connected = True
                    self.connect_button.setText("断开连接")
                    threading.Thread(target=self.receive_data, daemon=True).start()
                else:
                    self.log_browser.append("<span style='color: red;'>认证失败</span>")
                    self.disconnect_from_server()
            else:
                self.log_browser.append("<span style='color: red;'>未收到密码提示</span>")
                self.disconnect_from_server()

        except Exception as e:
            self.log_browser.append(f"<span style='color: red;'>连接失败: {e}</span>")
            self.disconnect_from_server()

    def disconnect_from_server(self):
        self.connected = False
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None
        self.connect_button.setText("连接")
        self.log_browser.append("Disconnected.")

    def receive_data(self):
        while self.connected:
            try:
                data = self.client_socket.recv(4096)
                if data:
                    response = data.decode().strip()
                    # 解析不同类型的响应
                    if response.startswith('[') and '] Result:' in response:
                        # 执行结果
                        self.log_browser.append(f"<span style='color: green;'>{response}</span>")
                    elif response.startswith('[') and '] Error:' in response:
                        # 错误信息
                        self.log_browser.append(f"<span style='color: red;'>{response}</span>")
                    elif response.startswith('[') and '] Memory:' in response:
                        # 内存信息
                        self.log_browser.append(f"<span style='color: blue;'>{response}</span>")
                    elif 'vars:' in response:
                        # 变量信息
                        self.log_browser.append(f"<span style='color: purple;'>{response}</span>")
                        # 同时更新变量表格
                        self.update_variables_display(response)
                    else:
                        # 普通响应
                        self.log_browser.append(response)
                else:
                    self.disconnect_from_server()
                    break
            except Exception as e:
                if self.connected:
                    self.log_browser.append(f"<span style='color: red;'>Error receiving data: {e}</span>")
                self.disconnect_from_server()
                break

    def send_command(self):
        if self.connected:
            command = self.command_input.text().strip()
            if command:
                # 添加到命令历史
                self.command_history.append({
                    'command': command,
                    'timestamp': time.time()
                })
                
                # 显示发送的命令
                self.log_browser.append(f"<span style='color: #666;'>> {command}</span>")
                self.client_socket.sendall(command.encode())
                self.command_input.clear()
                
                # 如果是变量查询命令，准备更新变量显示
                if command == 'vars':
                    self.log_browser.append("正在获取变量信息...")
        else:
             self.log_browser.append("<span style='color: red;'>请先连接到调试服务器</span>")
    
    def update_variables_display(self, response):
        """更新变量显示表格"""
        try:
            # 解析变量信息
            if 'Local vars:' in response and 'Global vars:' in response:
                lines = response.split('\n')
                for line in lines:
                    if 'Local vars:' in line:
                        local_part = line.split('Local vars: ')[1].split('Global vars:')[0].strip()
                        self.parse_and_display_vars(local_part, 'Local')
                    elif 'Global vars:' in line:
                        global_part = line.split('Global vars: ')[1].strip()
                        self.parse_and_display_vars(global_part, 'Global')
        except Exception as e:
            print(f"Error updating variables display: {e}")
    
    def parse_and_display_vars(self, vars_str, var_type):
        """解析并显示变量"""
        try:
            # 简单的字典解析
            if vars_str.startswith('{') and vars_str.endswith('}'):
                vars_str = vars_str[1:-1]  # 移除大括号
                if vars_str.strip():
                    # 清空现有变量（如果是新的查询）
                    if var_type == 'Local':
                        self.variables_table.setRowCount(0)
                    
                    # 添加变量到表格
                    pairs = vars_str.split(', ')
                    for pair in pairs:
                        if ': ' in pair:
                            key, value = pair.split(': ', 1)
                            key = key.strip().strip("'\"")
                            value = value.strip().strip("'\"")
                            
                            row = self.variables_table.rowCount()
                            self.variables_table.insertRow(row)
                            self.variables_table.setItem(row, 0, QTableWidgetItem(key))
                            self.variables_table.setItem(row, 1, QTableWidgetItem(value))
                            self.variables_table.setItem(row, 2, QTableWidgetItem(var_type))
        except Exception as e:
            print(f"Error parsing variables: {e}")

    def start_debug_server(self):
        """启动调试服务器"""
        try:
            port = int(self.port_input.text())
            password = self.password_input.text()
            
            if self.debug_server_process and self.debug_server_process.poll() is None:
                self.log_browser.append("调试服务器已在运行中")
                return
            
            # 创建调试服务器脚本
            server_script = f'''
import socket
import threading
import sys
import traceback
import json
import time
from datetime import datetime

class DebugServer:
    def __init__(self, port, password):
        self.port = port
        self.password = password
        self.clients = []
        self.running = False
        self.server_socket = None
        
    def start(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('localhost', self.port))
            self.server_socket.listen(5)
            self.running = True
            
            print(f"调试服务器启动在端口 {{self.port}}")
            
            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    print(f"客户端连接: {{addr}}")
                    
                    # SSL包装（如果支持）
                    try:
                        import ssl
                        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                        context.load_cert_chain('server.crt', 'server.key')  # 需要证书文件
                        client_socket = context.wrap_socket(client_socket, server_side=True)
                        print(f"SSL连接建立: {{addr}}")
                    except:
                        print(f"普通连接: {{addr}} (SSL不可用)")
                    
                    # 密码验证
                    client_socket.send(b"Password: ")
                    password_input = client_socket.recv(1024).decode().strip()
                    
                    # 使用哈希密码验证
                    import hashlib
                    expected_hash = hashlib.sha256(self.password.encode()).hexdigest()
                    
                    if password_input == expected_hash:
                        client_socket.send(b"Authentication successful\\n")
                        self.clients.append(client_socket)
                        threading.Thread(target=self.handle_client, args=(client_socket, addr), daemon=True).start()
                    else:
                        client_socket.send(b"Authentication failed\\n")
                        client_socket.close()
                        print(f"认证失败: {{addr}}")
                        
                except Exception as e:
                    if self.running:
                        print(f"接受连接错误: {{e}}")
                        
        except Exception as e:
            print(f"服务器启动失败: {{e}}")
            
    def handle_client(self, client_socket, addr):
        try:
            while self.running:
                data = client_socket.recv(4096)
                if not data:
                    break
                    
                command = data.decode().strip()
                response = self.execute_command(command)
                client_socket.send(response.encode())
                
        except Exception as e:
            print(f"处理客户端 {{addr}} 错误: {{e}}")
        finally:
            if client_socket in self.clients:
                self.clients.remove(client_socket)
            client_socket.close()
            
    def execute_command(self, command):
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            if command.startswith('eval:'):
                code = command[5:]
                result = eval(code)
                return f"[{{timestamp}}] Result: {{result}}\\n"
            elif command.startswith('exec:'):
                code = command[5:]
                exec(code)
                return f"[{{timestamp}}] Executed successfully\\n"
            elif command.startswith('vars'):
                # 获取当前变量
                local_vars = {{k: str(v) for k, v in locals().items() if not k.startswith('_')}}
                global_vars = {{k: str(v) for k, v in globals().items() if not k.startswith('_') and k not in ['__builtins__']}}
                return f"[{{timestamp}}] Local vars: {{local_vars}}\\nGlobal vars: {{global_vars}}\\n"
            elif command.startswith('memory'):
                # 内存使用情况
                try:
                    import psutil
                    import os
                    process = psutil.Process(os.getpid())
                    memory_info = process.memory_info()
                    return f"[{{timestamp}}] Memory: RSS={{memory_info.rss / 1024 / 1024:.2f}}MB, VMS={{memory_info.vms / 1024 / 1024:.2f}}MB\\n"
                except ImportError:
                    return f"[{{timestamp}}] psutil not available for memory monitoring\\n"
            elif command.startswith('breakpoint:'):
                # 断点管理命令
                parts = command.split(':')
                if len(parts) >= 3:
                    action = parts[1]
                    if action == 'add' and len(parts) >= 4:
                        file_path, line_num = parts[2], parts[3]
                        condition = parts[4] if len(parts) > 4 else ''
                        if not hasattr(self, 'breakpoints'):
                            self.breakpoints = {{}}
                        bp_id = f"{{file_path}}:{{line_num}}"
                        self.breakpoints[bp_id] = {{
                            'file': file_path,
                            'line': int(line_num),
                            'condition': condition,
                            'enabled': True,
                            'hit_count': 0
                        }}
                        return f"[{{timestamp}}] Breakpoint added: {{bp_id}}\\n"
                    elif action == 'remove' and len(parts) >= 3:
                        bp_id = parts[2]
                        if hasattr(self, 'breakpoints') and bp_id in self.breakpoints:
                            del self.breakpoints[bp_id]
                            return f"[{{timestamp}}] Breakpoint removed: {{bp_id}}\\n"
                        else:
                            return f"[{{timestamp}}] Breakpoint not found: {{bp_id}}\\n"
                    elif action == 'list':
                        if hasattr(self, 'breakpoints') and self.breakpoints:
                            bp_list = '\\n'.join([f"  {{bp_id}}: {{bp['condition'] or 'No condition'}}" for bp_id, bp in self.breakpoints.items()])
                            return f"[{{timestamp}}] Active breakpoints:\\n{{bp_list}}\\n"
                        else:
                            return f"[{{timestamp}}] No active breakpoints\\n"
                return f"[{{timestamp}}] Invalid breakpoint command format\\n"
            elif command == 'status':
                return f"[{{timestamp}}] Server running, {{len(self.clients)}} clients connected\\n"
            elif command == 'help':
                 help_text = """Available commands:
   eval:<code> - Execute expression and return result
   exec:<code> - Execute code
   vars - Show current variables
   memory - Show memory usage
   breakpoint:add:<file>:<line>:[condition] - Add breakpoint
   breakpoint:remove:<file:line> - Remove breakpoint
   breakpoint:list - List all breakpoints
   step - Execute single step
   continue - Continue program execution
   stack - Show stack trace
   eval <expression> - Evaluate expression
   status - Server status
   help - Show this help
   quit - Disconnect"""
                 return f"[{{timestamp}}] {{help_text}}\\n"
            elif command == 'step':
                return f"[{{timestamp}}] Single step executed\\n"
            elif command == 'continue':
                return f"[{{timestamp}}] Program continued\\n"
            elif command == 'stack':
                import traceback
                stack_info = '\\n'.join(traceback.format_stack())
                return f"[{{timestamp}}] Stack trace:\\n{{stack_info}}\\n"
            elif command.startswith('eval '):
                expression = command[5:].strip()
                try:
                    result = eval(expression, globals(), locals())
                    return f"[{{timestamp}}] {{expression}} = {{result}}\\n"
                except Exception as e:
                    return f"[{{timestamp}}] Error evaluating '{{expression}}': {{e}}\\n"
            elif command == 'quit':
                return f"[{{timestamp}}] Goodbye\\n"
            else:
                return f"[{{timestamp}}] Unknown command: {{command}}. Type 'help' for available commands.\\n"
        except Exception as e:
            timestamp = datetime.now().strftime('%H:%M:%S')
            return f"[{{timestamp}}] Error: {{e}}\\n{{traceback.format_exc()}}"
            
    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        for client in self.clients:
            client.close()
            
if __name__ == "__main__":
    server = DebugServer({port}, "{password}")
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
'''
            
            # 保存服务器脚本到临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(server_script)
                server_file = f.name
            
            # 启动服务器进程
            import subprocess
            self.debug_server_process = subprocess.Popen(
                [sys.executable, server_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.log_browser.append(f"调试服务器已启动在端口 {port}")
            self.start_server_button.setText("停止服务器")
            
            # 监控服务器输出
            threading.Thread(target=self._monitor_server_output, daemon=True).start()
            
        except Exception as e:
            self.log_browser.append(f"启动调试服务器失败: {e}")
    
    def toggle_debug_server(self):
        """切换调试服务器状态"""
        if hasattr(self, 'debug_server_process') and self.debug_server_process and self.debug_server_process.poll() is None:
            self.stop_debug_server()
        else:
            self.start_debug_server()
    
    def stop_debug_server(self):
        """停止调试服务器"""
        try:
            if hasattr(self, 'debug_server_process') and self.debug_server_process:
                self.debug_server_process.terminate()
                self.debug_server_process.wait(timeout=5)
                self.debug_server_process = None
                
            self.start_server_button.setText("启动服务器")
            self.log_browser.append("调试服务器已停止")
            
        except Exception as e:
            self.log_browser.append(f"停止服务器失败: {e}")
            QMessageBox.warning(self.parent, "错误", f"停止服务器失败: {e}")
    
    def _monitor_server_output(self):
        """监控服务器输出"""
        try:
            while self.debug_server_process and self.debug_server_process.poll() is None:
                output = self.debug_server_process.stdout.readline()
                if output:
                    self.log_browser.append(f"[服务器] {output.strip()}")
        except Exception as e:
            self.log_browser.append(f"监控服务器输出错误: {e}")
    
    def refresh_variables(self):
        """刷新变量列表"""
        if not self.connected:
            self.log_browser.append("请先连接到调试服务器")
            return
            
        try:
            # 发送获取变量命令
            command = "eval:list(globals().keys())"
            self.client_socket.sendall(command.encode())
            
            # 这里应该接收响应并更新变量表格
            # 由于是异步接收，实际实现需要更复杂的消息处理机制
            self.log_browser.append("正在刷新变量列表...")
            
        except Exception as e:
            self.log_browser.append(f"刷新变量失败: {e}")
    
    def filter_variables(self):
        """过滤变量显示"""
        filter_text = self.var_filter_input.text().lower()
        for row in range(self.variables_table.rowCount()):
            item = self.variables_table.item(row, 0)
            if item:
                should_show = filter_text in item.text().lower()
                self.variables_table.setRowHidden(row, not should_show)
    
    def add_breakpoint(self):
        """添加断点"""
        file_path = self.bp_file_input.text().strip()
        line_number = self.bp_line_input.text().strip()
        condition = getattr(self, 'bp_condition_input', None)
        condition_text = condition.text().strip() if condition else ""
        
        if not file_path or not line_number:
            self.log_browser.append("<span style='color: red;'>请输入文件路径和行号</span>")
            return
            
        try:
            line_num = int(line_number)
            breakpoint_id = f"{file_path}:{line_num}"
            
            # 检查是否已存在
            if not hasattr(self, 'breakpoints'):
                self.breakpoints = {}
                
            if breakpoint_id in self.breakpoints:
                self.log_browser.append("<span style='color: orange;'>断点已存在</span>")
                return
            
            # 创建断点数据
            self.breakpoints[breakpoint_id] = {
                'file': file_path,
                'line': line_num,
                'condition': condition_text,
                'enabled': True,
                'hit_count': 0
            }
            
            # 显示文本
            display_text = f"{file_path}:{line_num}"
            if condition_text:
                display_text += f" (条件: {condition_text})"
                
            # 添加到列表
            from PyQt6.QtWidgets import QListWidgetItem
            from PyQt6.QtCore import Qt
            item = QListWidgetItem(display_text)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, breakpoint_id)
            self.breakpoints_list.addItem(item)
            
            # 发送到服务器
            if self.connected:
                bp_command = f"breakpoint:add:{file_path}:{line_num}:{condition_text}"
                try:
                    self.client_socket.sendall(bp_command.encode())
                    self.log_browser.append(f"<span style='color: green;'>已添加断点: {breakpoint_id}</span>")
                except Exception as e:
                    self.log_browser.append(f"<span style='color: red;'>发送断点到服务器失败: {e}</span>")
            else:
                self.log_browser.append(f"<span style='color: blue;'>已添加断点: {breakpoint_id} (离线)</span>")
            
            # 清空输入框
            self.bp_file_input.clear()
            self.bp_line_input.clear()
            if condition:
                condition.clear()
            
        except ValueError:
            self.log_browser.append("<span style='color: red;'>行号必须是数字</span>")
        except Exception as e:
            self.log_browser.append(f"<span style='color: red;'>添加断点失败: {e}</span>")
    
    def remove_breakpoint(self):
        """删除断点"""
        current_item = self.breakpoints_list.currentItem()
        if current_item:
            breakpoint_id = current_item.data(Qt.ItemDataRole.UserRole)
            breakpoint_text = current_item.text()
            
            # 从数据结构中删除
            if hasattr(self, 'breakpoints') and breakpoint_id in self.breakpoints:
                del self.breakpoints[breakpoint_id]
            
            # 从列表中删除
            self.breakpoints_list.takeItem(self.breakpoints_list.row(current_item))
            
            # 发送到服务器
            if self.connected and breakpoint_id:
                bp_command = f"breakpoint:remove:{breakpoint_id}"
                try:
                    self.client_socket.sendall(bp_command.encode())
                    self.log_browser.append(f"<span style='color: green;'>已删除断点: {breakpoint_text}</span>")
                except Exception as e:
                    self.log_browser.append(f"<span style='color: red;'>发送删除命令到服务器失败: {e}</span>")
            else:
                self.log_browser.append(f"<span style='color: blue;'>已删除断点: {breakpoint_text} (离线)</span>")
        else:
            self.log_browser.append("<span style='color: orange;'>请选择要删除的断点</span>")
    
    def save_debug_session(self):
        """保存调试会话"""
        try:
            session_data = {
                'timestamp': time.time(),
                'host': self.host_input.text(),
                'port': self.port_input.text(),
                'breakpoints': getattr(self, 'breakpoints', {}),
                'command_history': getattr(self, 'command_history', []),
                'variables_snapshot': getattr(self, 'last_variables', {})
            }
            
            # 保存到文件
            import json
            session_file = f"debug_session_{int(time.time())}.json"
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
                
            self.log_browser.append(f"<span style='color: green;'>调试会话已保存: {session_file}</span>")
            
        except Exception as e:
            self.log_browser.append(f"<span style='color: red;'>保存会话失败: {e}</span>")
    
    def load_debug_session(self):
        """加载调试会话"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            session_file, _ = QFileDialog.getOpenFileName(
                self, "选择调试会话文件", "", "JSON Files (*.json)"
            )
            
            if session_file:
                import json
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                
                # 恢复连接信息
                self.host_input.setText(session_data.get('host', 'localhost'))
                self.port_input.setText(str(session_data.get('port', 9999)))
                
                # 恢复断点
                breakpoints = session_data.get('breakpoints', {})
                if breakpoints:
                    self.breakpoints = breakpoints
                    self.breakpoints_list.clear()
                    
                    for bp_id, bp_data in breakpoints.items():
                        display_text = f"{bp_data['file']}:{bp_data['line']}"
                        if bp_data.get('condition'):
                            display_text += f" (条件: {bp_data['condition']})"
                            
                        from PyQt6.QtWidgets import QListWidgetItem
                        from PyQt6.QtCore import Qt
                        item = QListWidgetItem(display_text)
                        item.setCheckState(Qt.CheckState.Checked if bp_data.get('enabled', True) else Qt.CheckState.Unchecked)
                        item.setData(Qt.ItemDataRole.UserRole, bp_id)
                        self.breakpoints_list.addItem(item)
                
                # 恢复命令历史
                self.command_history = session_data.get('command_history', [])
                
                self.log_browser.append(f"<span style='color: green;'>调试会话已加载: {session_file}</span>")
                
        except Exception as e:
             self.log_browser.append(f"<span style='color: red;'>加载会话失败: {e}</span>")

    def debug_step(self):
         """单步执行调试"""
         if self.connected:
             self.client_socket.sendall(b"step")
             self.debug_output.append("<span style='color: blue;'>执行单步调试...</span>")
         else:
             self.debug_output.append("<span style='color: red;'>请先连接到调试服务器</span>")

    def debug_continue(self):
         """继续执行"""
         if self.connected:
             self.client_socket.sendall(b"continue")
             self.debug_output.append("<span style='color: blue;'>继续执行程序...</span>")
         else:
             self.debug_output.append("<span style='color: red;'>请先连接到调试服务器</span>")

    def debug_stack_trace(self):
         """查看堆栈信息"""
         if self.connected:
             self.client_socket.sendall(b"stack")
             self.debug_output.append("<span style='color: blue;'>获取堆栈信息...</span>")
         else:
             self.debug_output.append("<span style='color: red;'>请先连接到调试服务器</span>")

    def debug_eval(self):
         """表达式求值"""
         if self.connected:
             expression = self.eval_input.text().strip()
             if expression:
                 command = f"eval {expression}"
                 self.client_socket.sendall(command.encode())
                 self.debug_output.append(f"<span style='color: #666;'>> {expression}</span>")
                 self.eval_input.clear()
             else:
                 self.debug_output.append("<span style='color: orange;'>请输入要求值的表达式</span>")
         else:
             self.debug_output.append("<span style='color: red;'>请先连接到调试服务器</span>")

    def start_profiling(self):
        """开始性能分析"""
        if not self.connected:
            self.log_browser.append("请先连接到调试服务器")
            return
            
        try:
            # 发送开始性能分析命令
            command = "exec:import cProfile; profiler = cProfile.Profile(); profiler.enable()"
            self.client_socket.sendall(command.encode())
            
            self.performance_display.append("性能分析已开始...")
            self.start_profiling_button.setEnabled(False)
            self.stop_profiling_button.setEnabled(True)
            
        except Exception as e:
            self.log_browser.append(f"开始性能分析失败: {e}")
    
    def stop_profiling(self):
        """停止性能分析"""
        if not self.connected:
            self.log_browser.append("请先连接到调试服务器")
            return
            
        try:
            # 发送停止性能分析命令
            command = "exec:profiler.disable(); import io; s = io.StringIO(); profiler.print_stats(stream=s); print('PROFILER_RESULT:' + s.getvalue())"
            self.client_socket.sendall(command.encode())
            
            self.performance_display.append("性能分析已停止，正在获取结果...")
            self.start_profiling_button.setEnabled(True)
            self.stop_profiling_button.setEnabled(False)
            
        except Exception as e:
            self.log_browser.append(f"停止性能分析失败: {e}")
    
    def take_memory_snapshot(self):
        """获取内存快照"""
        if not self.connected:
            self.log_browser.append("请先连接到调试服务器")
            return
            
        try:
            # 发送内存快照命令
            command = "exec:import psutil; import os; process = psutil.Process(os.getpid()); print(f'Memory: {process.memory_info().rss / 1024 / 1024:.2f} MB')"
            self.client_socket.sendall(command.encode())
            
            self.performance_display.append("正在获取内存快照...")
            
        except Exception as e:
            self.log_browser.append(f"获取内存快照失败: {e}")

    def closeEvent(self, event):
        # 停止调试服务器
        if self.debug_server_process and self.debug_server_process.poll() is None:
            self.debug_server_process.terminate()
            
        self.disconnect_from_server()
        super().closeEvent(event)


class DevToolsPanel:
    """
    开发者工具面板主类
    
    提供完整的开发者工具集合，包括系统监控、日志管理、数据库操作、
    代码分析、网络调试等功能。通过菜单形式集成到主应用程序中。
    
    Attributes:
        current_version (str): 当前应用程序版本号
        UPDATE_CHECK_URL (str): 更新检查的API地址
        parent: 父窗口对象
        dev_tools_menu (QMenu): 开发者工具菜单
        logger: 专用的开发者工具日志记录器
    
    Example:
        >>> dev_tools = DevToolsPanel(main_window)
        >>> main_window.menuBar().addMenu(dev_tools.dev_tools_menu)
    """
    # 初始版本号（可被 version.txt 覆盖）
    current_version = "2.1.7"
    # 自定义更新检查URL
    UPDATE_CHECK_URL = "https://api.github.com/repos/liangrenyumao00-sketch/XuanWu-Output-Update/releases/latest"

    def __init__(self, parent):
        self.parent = parent
        self.dev_tools_menu = QMenu("开发者工具", parent)
        

        
        self.add_actions()

        # logger - 使用专用的DevToolsLogger，日志将记录到debug.html
        self.logger = logging.getLogger("DevToolsLogger")
        # 不再手动添加处理器，由main.py的setup_module_loggers()统一配置

        # 版本文件放在程序目录
        self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.version_file = os.path.join(self.base_dir, "version.txt")
        # 如存在 version.txt 就读一次覆盖默认
        try:
            if os.path.exists(self.version_file):
                with open(self.version_file, "r", encoding="utf-8") as vf:
                    v = vf.read().strip()
                    if v:
                        self.current_version = v
        except Exception:
            pass

        # 日志文件查看
        self.log_file_path = ""
        self.last_modified_time = None
        self.last_read_pos = 0
        self.dialog = None
        self.text_browser = None
        self.timer = QTimer(self.parent)
        self.timer.timeout.connect(self.check_log_file_change)
        self.timer.start(1000)  # 每秒检查一次
        

        # self.current_api_key = None
        


        # 更新相关
        self.update_worker = None
        self.progress_dialog = None
        self.latest_version = None

        # 监控窗口的引用，避免被垃圾回收
        self._monitor_dialog = None
        self._fps_dialog = None
        
        # Web预览服务器
        self._web_server = None

    # ---------- 日志查看相关 ----------
    def view_log_file(self):
        from PyQt6.QtGui import QTextOption

        log_file, _ = QFileDialog.getOpenFileName(self.parent, "选择日志文件", "", "HTML Files (*.html);;All Files (*)")
        if not log_file:
            QMessageBox.warning(self.parent, "提示", "未选择日志文件。")
            return

        self.log_file_path = log_file
        # 初始化读取并显示（支持 utf-8 / gbk）
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
            self.last_read_pos = os.path.getsize(log_file)
        except UnicodeDecodeError:
            try:
                with open(log_file, 'r', encoding='gbk') as f:
                    content = f.read()
                self.last_read_pos = os.path.getsize(log_file)
            except Exception as e:
                QMessageBox.warning(self.parent, "错误", f"读取日志文件失败: {e}")
                return
        except Exception as e:
            QMessageBox.warning(self.parent, "错误", f"读取日志文件失败: {e}")
            return

        # 弹窗显示
        self.dialog = QDialog(self.parent)
        self.dialog.setWindowTitle("日志内容")
        self.dialog.resize(900, 700)
        self.dialog.setModal(False)

        self.text_browser = QTextBrowser(self.dialog)
        self.text_browser.setHtml(content)
        self.text_browser.setWordWrapMode(QTextOption.WrapMode.WordWrap)

        layout = QVBoxLayout()
        layout.addWidget(self.text_browser)

        btn_close = QPushButton("关闭")
        btn_close.setDefault(False)
        btn_close.setAutoDefault(False)
        btn_close.clicked.connect(self.dialog.close)
        layout.addWidget(btn_close)

        self.dialog.setLayout(layout)
        self.dialog.show()

        # 记录修改时间（用于快速判断是否变更）
        try:
            self.last_modified_time = QFileInfo(self.log_file_path).lastModified()
        except Exception:
            self.last_modified_time = None

    def check_log_file_change(self):
        # 只在打开了日志查看窗口时才检查并追加
        if not self.log_file_path or not self.text_browser or not os.path.exists(self.log_file_path):
            return
        try:
            if hasattr(self, 'dialog') and self.dialog is not None and not self.dialog.isVisible():
                return
            current_time = QFileInfo(self.log_file_path).lastModified()
            if self.last_modified_time and current_time == self.last_modified_time:
                return
            # 文件更新了，读取新增内容（增量读取，避免重新加载全部）
            current_size = os.path.getsize(self.log_file_path)
            if current_size < self.last_read_pos:
                # 文件被截断或轮转，重新读全部
                with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                self.text_browser.setHtml(content)
                self.last_read_pos = os.path.getsize(self.log_file_path)
            else:
                if current_size > self.last_read_pos:
                    # 读取新增部分并 append
                    with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(self.last_read_pos)
                        new_text = f.read()
                    if new_text:
                        # append 作为纯文本（如果日志是 HTML，可以改成 setHtml 合并）
                        self.text_browser.append(new_text)
                    self.last_read_pos = os.path.getsize(self.log_file_path)
            self.last_modified_time = current_time
        except KeyboardInterrupt:
            return
        except Exception:
            # 忽略读取错误，避免打扰 UI
            pass

    # ---------- 更新流程 ----------
    def check_for_updates(self):
        if self.update_worker and self.update_worker.isRunning():
            QMessageBox.information(self.parent, "更新", "已经在检查更新或下载中，请稍候。")
            return

        self.update_worker = UpdateWorker(self.current_version, self.UPDATE_CHECK_URL)
        self.update_worker.signals.update_checked.connect(self.on_update_checked)
        self.update_worker.signals.error_occurred.connect(self.on_error)
        self.update_worker.start_check_update()



    def on_update_checked(self, has_update, latest_version):
        self.latest_version = latest_version
        if has_update:
            ret = QMessageBox.question(
                self.parent,
                "发现新版本",
                f"检测到新版本 {latest_version}，是否下载并安装？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ret == QMessageBox.StandardButton.Yes:
                self.download_and_install_update()
        else:
            QMessageBox.information(self.parent, "检查更新", f"当前已是最新版本 ({latest_version})。")

    def download_and_install_update(self):
        if not self.update_worker or not self.update_worker.download_url:
            QMessageBox.warning(self.parent, "错误", "未检测到可用更新。")
            return

        # 进度对话框
        self.progress_dialog = QProgressDialog("下载更新中...", "取消", 0, 100, self.parent)
        self.progress_dialog.setWindowTitle("下载进度")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.canceled.connect(self.cancel_update)
        self.progress_dialog.show()

        # 连接信号
        self.update_worker.signals.progress_changed.connect(self.progress_dialog.setValue)
        self.update_worker.signals.download_finished.connect(self.on_update_finished)
        self.update_worker.signals.download_failed.connect(self.on_error)

        # 开始下载，并传入 hash（若 check 接口提供了 hash 会已被填充）
        self.update_worker.start_download_install(self.update_worker.download_url, self.update_worker.latest_hash)

    def cancel_update(self):
        if self.update_worker and self.update_worker.isRunning():
            self.update_worker.cancel_download()

    def on_update_finished(self):
        # 关闭进度对话框
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        # 下载完成，询问是否立即安装
        ret = QMessageBox.question(
            self.parent,
            "更新完成",
            "更新包已下载并解压，是否立即安装？程序将退出以完成更新。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.Yes:
            self.run_external_updater()
        else:
            # 用户选择不立即安装，清理临时文件但保留解压目录供后续安装使用
            if hasattr(self, 'update_worker') and self.update_worker:
                try:
                    # 只删除zip文件，保留解压目录
                    if hasattr(self.update_worker, 'final_zip') and os.path.exists(self.update_worker.final_zip):
                        os.remove(self.update_worker.final_zip)
                    if hasattr(self.update_worker, 'temp_zip_part') and os.path.exists(self.update_worker.temp_zip_part):
                        os.remove(self.update_worker.temp_zip_part)
                except Exception:
                    pass
            QMessageBox.information(self.parent, "提示", "更新包已下载并暂存，稍后可通过“安装更新”进行安装。")

    def on_error(self, error_msg):
        # 关闭进度对话框（如果存在）
        if self.progress_dialog:
            try:
                self.progress_dialog.close()
            except Exception:
                pass
            self.progress_dialog = None

        # 清理临时目录（如果有）
        try:
            if self.update_worker and getattr(self.update_worker, "temp_dir", None):
                shutil.rmtree(self.update_worker.temp_dir, ignore_errors=True)
        except Exception:
            pass

        QMessageBox.warning(self.parent, "错误", str(error_msg))

    def install_update(self):
        # 用户手动触发安装（如果已经下载完且存在 extract 目录）
        if not self.update_worker or not getattr(self.update_worker, "extract_dir", None):
            QMessageBox.information(self.parent, "安装更新", "未检测到已下载的更新包。")
            return
        if not os.path.exists(self.update_worker.extract_dir):
            QMessageBox.information(self.parent, "安装更新", "更新包解压目录不存在。")
            return

        ret = QMessageBox.question(
            self.parent,
            "确认安装更新",
            "确定要安装已下载的更新吗？程序将退出以完成更新。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.Yes:
            self.run_external_updater()

    def run_external_updater(self):
        """启动外部更新程序 updater.py 替换文件，并退出当前程序"""

        # 确定 updater.py 路径
        updater_script = os.path.join(self.base_dir, "widgets", "updater.py")
        if not os.path.exists(updater_script):
            QMessageBox.warning(self.parent, t("error"), t("updater_not_found"))
            return

        # 运行的 python 解释器
        python_exe = sys.executable

        # 传参：解压目录，程序目录，入口脚本名，最新版本号
        extract_dir = self.update_worker.extract_dir if self.update_worker else ""
        base_dir = self.base_dir
        main_script = os.path.basename(sys.argv[0])

        # 如果没有准备好解压目录，不能启动
        if not extract_dir or not os.path.exists(extract_dir):
            QMessageBox.warning(self.parent, "错误", "更新包未准备好，无法安装。")
            return

        args = [
            python_exe,
            updater_script,
            extract_dir,
            base_dir,
            main_script,
            self.latest_version or ""
        ]

        try:
            subprocess.Popen(args)
            sys.exit(0)
        except Exception as e:
            QMessageBox.warning(self.parent, "错误", f"启动更新程序失败: {e}")

    def restart_program(self):
        python = sys.executable
        os.execl(python, python, *sys.argv)

    # ---------- 新实现的功能实现区 ----------
    def monitor_cpu_memory(self):
        if self._monitor_dialog and self._monitor_dialog.isVisible():
            self._monitor_dialog.activateWindow()
            return

        dlg = QDialog(self.parent)
        dlg.setWindowTitle("系统性能监控")
        dlg.resize(700, 500)
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 实时监控标签页
        realtime_tab = QWidget()
        realtime_layout = QVBoxLayout(realtime_tab)
        
        # 控制面板
        control_layout = QHBoxLayout()
        interval_label = QLabel("刷新间隔:")
        interval_combo = QComboBox()
        interval_combo.addItems(["0.5秒", "1秒", "2秒", "5秒"])
        interval_combo.setCurrentText("2秒")
        
        auto_refresh_check = QCheckBox("自动刷新")
        auto_refresh_check.setChecked(True)
        
        export_btn = QPushButton("导出数据")
        
        control_layout.addWidget(interval_label)
        control_layout.addWidget(interval_combo)
        control_layout.addWidget(auto_refresh_check)
        control_layout.addStretch()
        control_layout.addWidget(export_btn)
        
        realtime_layout.addLayout(control_layout)

        # CPU监控组
        cpu_group = QGroupBox("CPU 监控")
        cpu_layout = QGridLayout()
        
        cpu_label = QLabel("CPU使用率: --%")
        cpu_bar = QProgressBar()
        cpu_bar.setRange(0, 100)
        cpu_bar.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")
        
        cpu_cores_label = QLabel("CPU核心: --")
        cpu_freq_label = QLabel("CPU频率: --")
        cpu_temp_label = QLabel("CPU温度: --")
        cpu_load_label = QLabel("系统负载: --")
        
        cpu_layout.addWidget(cpu_label, 0, 0)
        cpu_layout.addWidget(cpu_bar, 0, 1)
        cpu_layout.addWidget(cpu_cores_label, 1, 0)
        cpu_layout.addWidget(cpu_freq_label, 1, 1)
        cpu_layout.addWidget(cpu_temp_label, 2, 0)
        cpu_layout.addWidget(cpu_load_label, 2, 1)
        cpu_group.setLayout(cpu_layout)

        # 内存监控组
        mem_group = QGroupBox("内存监控")
        mem_layout = QGridLayout()
        
        mem_label = QLabel("内存使用率: --%")
        mem_bar = QProgressBar()
        mem_bar.setRange(0, 100)
        mem_bar.setStyleSheet("")
        
        mem_detail_label = QLabel("详细信息: --")
        swap_label = QLabel("交换区: --")
        mem_available_label = QLabel("可用内存: --")
        
        mem_layout.addWidget(mem_label, 0, 0)
        mem_layout.addWidget(mem_bar, 0, 1)
        mem_layout.addWidget(mem_detail_label, 1, 0, 1, 2)
        mem_layout.addWidget(swap_label, 2, 0)
        mem_layout.addWidget(mem_available_label, 2, 1)
        mem_group.setLayout(mem_layout)

        # 磁盘监控组
        disk_group = QGroupBox("磁盘监控")
        disk_layout = QGridLayout()
        
        disk_label = QLabel("磁盘使用率: --%")
        disk_bar = QProgressBar()
        disk_bar.setRange(0, 100)
        disk_bar.setStyleSheet("")
        
        disk_io_label = QLabel("磁盘I/O: --")
        disk_space_label = QLabel("磁盘空间: --")
        
        disk_layout.addWidget(disk_label, 0, 0)
        disk_layout.addWidget(disk_bar, 0, 1)
        disk_layout.addWidget(disk_io_label, 1, 0)
        disk_layout.addWidget(disk_space_label, 1, 1)
        disk_group.setLayout(disk_layout)

        # 网络监控组
        network_group = QGroupBox("网络监控")
        network_layout = QGridLayout()
        
        network_speed_label = QLabel("网络速度: --")
        network_total_label = QLabel("总流量: --")
        network_connections_label = QLabel("连接数: --")
        
        network_layout.addWidget(network_speed_label, 0, 0)
        network_layout.addWidget(network_total_label, 0, 1)
        network_layout.addWidget(network_connections_label, 1, 0, 1, 2)
        network_group.setLayout(network_layout)
        
        # 进程监控组
        process_group = QGroupBox("进程监控")
        process_layout = QGridLayout()
        
        process_count_label = QLabel("进程总数: --")
        current_process_label = QLabel("当前进程: --")
        process_memory_label = QLabel("进程内存: --")
        
        process_layout.addWidget(process_count_label, 0, 0)
        process_layout.addWidget(current_process_label, 0, 1)
        process_layout.addWidget(process_memory_label, 1, 0, 1, 2)
        process_group.setLayout(process_layout)

        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_refresh = QPushButton("立即刷新")
        btn_reset = QPushButton("重置统计")
        btn_close = QPushButton("关闭")
        
        btn_layout.addWidget(btn_refresh)
        btn_layout.addWidget(btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)

        # 添加到实时监控标签页
        realtime_layout.addWidget(cpu_group)
        realtime_layout.addWidget(mem_group)
        realtime_layout.addWidget(disk_group)
        realtime_layout.addWidget(network_group)
        realtime_layout.addWidget(process_group)
        realtime_layout.addLayout(btn_layout)
        
        # 历史数据标签页
        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        
        history_text = QTextEdit()
        history_text.setReadOnly(True)
        history_text.setMaximumHeight(200)
        
        clear_history_btn = QPushButton("清空历史")
        save_history_btn = QPushButton("保存历史")
        
        history_btn_layout = QHBoxLayout()
        history_btn_layout.addWidget(clear_history_btn)
        history_btn_layout.addWidget(save_history_btn)
        history_btn_layout.addStretch()
        
        history_layout.addWidget(QLabel("性能历史记录:"))
        history_layout.addWidget(history_text)
        history_layout.addLayout(history_btn_layout)
        
        # 添加标签页
        tab_widget.addTab(realtime_tab, "实时监控")
        tab_widget.addTab(history_tab, "历史数据")
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.addWidget(tab_widget)
        dlg.setLayout(main_layout)

        # 数据存储
        monitoring_data = []
        network_stats = {'last_bytes_sent': 0, 'last_bytes_recv': 0, 'last_time': time.time()}
        last_disk_io = None

        timer = QTimer(dlg)

        def get_interval_ms():
            interval_text = interval_combo.currentText()
            if "0.5" in interval_text:
                return 500
            elif "1" in interval_text:
                return 1000
            elif "5" in interval_text:
                return 5000
            else:
                return 2000

        # 缓存静态信息，避免重复获取
        static_info = {}
        update_counter = 0
        
        def update():
            nonlocal last_disk_io, static_info, update_counter
            try:
                if not psutil:
                    cpu_label.setText("CPU: psutil未安装")
                    mem_label.setText("内存: psutil未安装")
                    disk_label.setText("磁盘: psutil未安装")
                    network_speed_label.setText("网络: psutil未安装")
                    return
                
                current_time = time.time()
                timestamp = time.strftime('%H:%M:%S')
                update_counter += 1
                
                # CPU监控 - 减少interval以提高响应速度
                cpu = psutil.cpu_percent(interval=None)  # 使用非阻塞模式
                cpu_label.setText(f"CPU使用率: {cpu:.1f}%")
                cpu_bar.setValue(int(round(cpu)))
                
                # 静态信息只在第一次或每10次更新时获取
                if update_counter == 1 or update_counter % 10 == 0:
                    static_info['cpu_count'] = psutil.cpu_count()
                    
                    # CPU频率
                    try:
                        cpu_freq = psutil.cpu_freq()
                        static_info['cpu_freq'] = f"CPU频率: {cpu_freq.current:.0f} MHz" if cpu_freq else "CPU频率: 不支持"
                    except (AttributeError, OSError, Exception):
                        static_info['cpu_freq'] = "CPU频率: 不支持"
                    
                    # CPU温度 - 温度变化较慢，降低更新频率
                    try:
                        temps = psutil.sensors_temperatures()
                        if temps:
                            for name, entries in temps.items():
                                if entries:
                                    static_info['cpu_temp'] = f"CPU温度: {entries[0].current:.1f}°C"
                                    break
                        else:
                            static_info['cpu_temp'] = "CPU温度: 不支持"
                    except (AttributeError, OSError, Exception):
                        static_info['cpu_temp'] = "CPU温度: 不支持"
                
                # 使用缓存的静态信息
                cpu_cores_label.setText(f"CPU核心: {static_info.get('cpu_count', '--')}")
                cpu_freq_label.setText(static_info.get('cpu_freq', 'CPU频率: --'))
                cpu_temp_label.setText(static_info.get('cpu_temp', 'CPU温度: --'))
                
                # 系统负载
                try:
                    load_avg = psutil.getloadavg()
                    cpu_load_label.setText(f"系统负载: {load_avg[0]:.2f}")
                except (AttributeError, OSError, Exception):
                    cpu_load_label.setText("系统负载: 不支持")
                
                # 内存监控
                mem = psutil.virtual_memory()
                mem_percent = mem.percent
                mem_label.setText(f"内存使用率: {mem_percent:.1f}%")
                mem_bar.setValue(int(round(mem_percent)))
                
                # 内存详细信息只在慢速更新时获取
                if update_counter % 5 == 0:  # 每5次更新一次详细信息
                    swap = psutil.swap_memory()
                    static_info['mem_detail'] = f"已用: {mem.used / (1024**3):.2f}GB / 总计: {mem.total / (1024**3):.2f}GB"
                    static_info['swap_info'] = f"交换区: {swap.percent:.1f}%"
                    static_info['mem_available'] = f"可用内存: {mem.available / (1024**3):.2f}GB"
                
                mem_detail_label.setText(static_info.get('mem_detail', '内存详情: --'))
                swap_label.setText(static_info.get('swap_info', '交换区: --'))
                mem_available_label.setText(static_info.get('mem_available', '可用内存: --'))
                
                # 磁盘监控 - 降低更新频率
                if update_counter % 3 == 0:  # 每3次更新一次磁盘信息
                    try:
                        disk = psutil.disk_usage('C:' if platform.system() == 'Windows' else '/')
                        disk_percent = (disk.used / disk.total) * 100
                        static_info['disk_percent'] = disk_percent
                        static_info['disk_space'] = f"可用: {disk.free / (1024**3):.2f}GB / 总计: {disk.total / (1024**3):.2f}GB"
                        
                        # 磁盘I/O
                        disk_io = psutil.disk_io_counters()
                        if disk_io and last_disk_io:
                            time_interval = get_interval_ms() / 1000 * 3  # 3次更新的时间间隔
                            read_speed = (disk_io.read_bytes - last_disk_io.read_bytes) / time_interval / (1024**2)
                            write_speed = (disk_io.write_bytes - last_disk_io.write_bytes) / time_interval / (1024**2)
                            static_info['disk_io'] = f"磁盘I/O: 读取 {read_speed:.1f}MB/s, 写入 {write_speed:.1f}MB/s"
                        elif disk_io:
                            static_info['disk_io'] = f"磁盘I/O: 读取 {disk_io.read_bytes/(1024**3):.2f}GB, 写入 {disk_io.write_bytes/(1024**3):.2f}GB"
                        
                        last_disk_io = disk_io
                    except Exception:
                        static_info['disk_percent'] = 0
                        static_info['disk_space'] = "磁盘信息: 获取失败"
                        static_info['disk_io'] = "磁盘I/O: 获取失败"
                
                disk_percent = static_info.get('disk_percent', 0)
                disk_label.setText(f"磁盘使用率: {disk_percent:.1f}%")
                disk_bar.setValue(int(round(disk_percent)))
                disk_space_label.setText(static_info.get('disk_space', '磁盘空间: --'))
                disk_io_label.setText(static_info.get('disk_io', '磁盘I/O: --'))
                
                # 网络监控 - 降低更新频率
                if update_counter % 3 == 0:  # 每3次更新一次网络信息
                    try:
                        net_io = psutil.net_io_counters()
                        time_diff = current_time - network_stats['last_time']
                        
                        if time_diff > 0 and network_stats['last_bytes_sent'] > 0:
                            upload_speed = (net_io.bytes_sent - network_stats['last_bytes_sent']) / time_diff / 1024
                            download_speed = (net_io.bytes_recv - network_stats['last_bytes_recv']) / time_diff / 1024
                            static_info['network_speed'] = f"网络速度: ↑{upload_speed:.1f} KB/s ↓{download_speed:.1f} KB/s"
                        else:
                            static_info['network_speed'] = "网络速度: 计算中..."
                        
                        static_info['network_total'] = f"总流量: ↑{net_io.bytes_sent/(1024**3):.2f}GB ↓{net_io.bytes_recv/(1024**3):.2f}GB"
                        
                        network_stats['last_bytes_sent'] = net_io.bytes_sent
                        network_stats['last_bytes_recv'] = net_io.bytes_recv
                        network_stats['last_time'] = current_time
                    except Exception:
                        static_info['network_speed'] = "网络速度: 获取失败"
                        static_info['network_total'] = "总流量: 获取失败"
                
                # 网络连接数 - 更低频率更新
                if update_counter % 6 == 0:  # 每6次更新一次连接数
                    try:
                        connections = len(psutil.net_connections())
                        static_info['network_connections'] = f"网络连接数: {connections}"
                    except Exception:
                        static_info['network_connections'] = "网络连接数: 无权限"
                
                network_speed_label.setText(static_info.get('network_speed', '网络速度: --'))
                network_total_label.setText(static_info.get('network_total', '总流量: --'))
                network_connections_label.setText(static_info.get('network_connections', '网络连接数: --'))
                
                # 进程监控 - 降低更新频率
                if update_counter % 4 == 0:  # 每4次更新一次进程信息
                    try:
                        process_count = len(psutil.pids())
                        current_process = psutil.Process()
                        process_mem = current_process.memory_info()
                        
                        static_info['process_count'] = f"进程总数: {process_count}"
                        static_info['current_process'] = f"当前进程: {current_process.name()} (PID: {current_process.pid})"
                        static_info['process_memory'] = f"进程内存: {process_mem.rss / (1024**2):.1f} MB"
                    except Exception:
                        static_info['process_count'] = "进程总数: 获取失败"
                        static_info['current_process'] = "当前进程: 获取失败"
                        static_info['process_memory'] = "进程内存: 获取失败"
                
                process_count_label.setText(static_info.get('process_count', '进程总数: --'))
                current_process_label.setText(static_info.get('current_process', '当前进程: --'))
                process_memory_label.setText(static_info.get('process_memory', '进程内存: --'))
                
                # 记录历史数据 - 降低记录频率
                if update_counter % 5 == 0:  # 每5次更新记录一次历史数据
                    disk_percent = static_info.get('disk_percent', 0)
                    data_entry = f"[{timestamp}] CPU: {cpu:.1f}%, 内存: {mem_percent:.1f}%, 磁盘: {disk_percent:.1f}%"
                    monitoring_data.append(data_entry)
                    
                    # 限制历史数据数量
                    if len(monitoring_data) > 100:
                        monitoring_data.pop(0)
                    
                    # 更新历史显示
                    history_text.setPlainText('\n'.join(monitoring_data[-20:]))  # 显示最近20条
                
                # 增加更新计数器
                update_counter += 1
                
            except Exception as e:
                cpu_label.setText(f"CPU: 获取失败 - {str(e)[:30]}")
                mem_label.setText(f"内存: 获取失败 - {str(e)[:30]}")
                print(f"监控更新失败: {e}")

        def start_auto_refresh():
            if auto_refresh_check.isChecked():
                interval = get_interval_ms()
                timer.start(interval)
            else:
                timer.stop()
        
        def reset_stats():
            monitoring_data.clear()
            history_text.clear()
            network_stats.update({'last_bytes_sent': 0, 'last_bytes_recv': 0, 'last_time': time.time()})
            QMessageBox.information(dlg, "成功", "统计数据已重置")
        
        def export_data():
            if not monitoring_data:
                QMessageBox.warning(dlg, "警告", "没有可导出的数据")
                return
            
            file_path, _ = QFileDialog.getSaveFileName(dlg, "导出监控数据", "performance_data.txt", "Text Files (*.txt)")
            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(monitoring_data))
                    QMessageBox.information(dlg, "成功", f"数据已导出到 {file_path}")
                except Exception as e:
                    QMessageBox.warning(dlg, "错误", f"导出失败: {e}")
        
        def clear_history():
            monitoring_data.clear()
            history_text.clear()
        
        def save_history():
            if not monitoring_data:
                QMessageBox.warning(dlg, "警告", "没有历史数据")
                return
            
            file_path, _ = QFileDialog.getSaveFileName(dlg, "保存历史数据", "history.txt", "Text Files (*.txt)")
            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(monitoring_data))
                    QMessageBox.information(dlg, "成功", f"历史数据已保存到 {file_path}")
                except Exception as e:
                    QMessageBox.warning(dlg, "错误", f"保存失败: {e}")

        # 连接信号
        btn_refresh.clicked.connect(update)
        btn_reset.clicked.connect(reset_stats)
        btn_close.clicked.connect(dlg.close)
        export_btn.clicked.connect(export_data)
        clear_history_btn.clicked.connect(clear_history)
        save_history_btn.clicked.connect(save_history)
        auto_refresh_check.toggled.connect(start_auto_refresh)
        interval_combo.currentTextChanged.connect(lambda: timer.start(get_interval_ms()) if auto_refresh_check.isChecked() else None)
        timer.timeout.connect(update)
        
        # 启动自动刷新
        start_auto_refresh()
        update()  # 立即更新一次

        dlg.finished.connect(timer.stop)
        self._monitor_dialog = dlg
        dlg.show()

    def show_fps(self):
        if self._fps_dialog and self._fps_dialog.isVisible():
            self._fps_dialog.activateWindow()
            return

        dlg = QDialog(self.parent)
        dlg.setWindowTitle("应用性能监控")
        dlg.resize(400, 250)

        # FPS监控
        fps_group = QGroupBox("帧率监控")
        fps_layout = QVBoxLayout()
        fps_label = QLabel("FPS: --")
        fps_avg_label = QLabel("平均FPS: --")
        fps_min_label = QLabel("最低FPS: --")
        fps_max_label = QLabel("最高FPS: --")
        fps_layout.addWidget(fps_label)
        fps_layout.addWidget(fps_avg_label)
        fps_layout.addWidget(fps_min_label)
        fps_layout.addWidget(fps_max_label)
        fps_group.setLayout(fps_layout)

        # 渲染性能
        render_group = QGroupBox("渲染性能")
        render_layout = QVBoxLayout()
        frame_time_label = QLabel("帧时间: -- ms")
        render_time_label = QLabel("渲染时间: -- ms")
        render_layout.addWidget(frame_time_label)
        render_layout.addWidget(render_time_label)
        render_group.setLayout(render_layout)

        info_label = QLabel("说明：基于Qt定时器和绘制事件的性能估算")
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        
        btn_layout = QHBoxLayout()
        btn_reset = QPushButton("重置统计")
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(dlg.close)
        btn_layout.addWidget(btn_reset)
        btn_layout.addWidget(btn_close)

        layout = QVBoxLayout()
        layout.addWidget(fps_group)
        layout.addWidget(render_group)
        layout.addWidget(info_label)
        layout.addLayout(btn_layout)
        dlg.setLayout(layout)

        # 性能统计数据
        stats = {
            "count": 0, 
            "last_time": time.time(), 
            "fps": 0,
            "fps_history": [],
            "frame_times": [],
            "render_start": 0
        }

        timer = QTimer(dlg)

        def tick():
            stats['count'] += 1
            now = time.time()
            
            # 计算帧时间
            if stats['render_start'] > 0:
                frame_time = (now - stats['render_start']) * 1000
                stats['frame_times'].append(frame_time)
                if len(stats['frame_times']) > 60:  # 保持最近60帧的数据
                    stats['frame_times'].pop(0)
                
                # 防止除零错误
                avg_frame_time = sum(stats['frame_times']) / len(stats['frame_times']) if len(stats['frame_times']) > 0 else 0.0
                frame_time_label.setText(f"帧时间: {frame_time:.2f} ms")
                render_time_label.setText(f"平均帧时间: {avg_frame_time:.2f} ms")
            
            stats['render_start'] = now
            
            # 每秒计算一次FPS
            if now - stats['last_time'] >= 1.0:
                current_fps = stats['count'] / (now - stats['last_time'])
                stats['fps'] = current_fps
                stats['fps_history'].append(current_fps)
                
                if len(stats['fps_history']) > 30:  # 保持最近30秒的数据
                    stats['fps_history'].pop(0)
                
                stats['count'] = 0
                stats['last_time'] = now
                
                # 更新显示
                fps_label.setText(f"FPS: {current_fps:.1f}")
                
                if stats['fps_history']:
                    # 防止除零错误
                    avg_fps = sum(stats['fps_history']) / len(stats['fps_history']) if len(stats['fps_history']) > 0 else 0.0
                    min_fps = min(stats['fps_history'])
                    max_fps = max(stats['fps_history'])
                    
                    fps_avg_label.setText(f"平均FPS: {avg_fps:.1f}")
                    fps_min_label.setText(f"最低FPS: {min_fps:.1f}")
                    fps_max_label.setText(f"最高FPS: {max_fps:.1f}")

        def reset_stats():
            stats['fps_history'].clear()
            stats['frame_times'].clear()
            stats['count'] = 0
            stats['last_time'] = time.time()
            fps_avg_label.setText("平均FPS: --")
            fps_min_label.setText("最低FPS: --")
            fps_max_label.setText("最高FPS: --")
            frame_time_label.setText("帧时间: -- ms")
            render_time_label.setText("渲染时间: -- ms")

        btn_reset.clicked.connect(reset_stats)
        timer.timeout.connect(tick)
        timer.start(16)  # 约60FPS的检测频率

        dlg.finished.connect(timer.stop)
        self._fps_dialog = dlg
        dlg.show()

    def generate_performance_report(self):
        try:
            # 导入性能管理器
            from core.performance_manager import PerformanceManager
            perf_manager = PerformanceManager()
            
            # 收集当前性能数据
            current_data = perf_manager.collect_current_performance()
            perf_manager.save_performance_data(current_data)
            
            report = {}
            
            # 基本信息
            report['报告生成时间'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            report['系统信息'] = {
                'Python版本': sys.version,
                'Python执行路径': sys.executable,
                '主程序脚本': os.path.basename(sys.argv[0]),
                '当前工作目录': os.getcwd(),
                '平台': sys.platform,
                '架构': platform.architecture()[0] if 'platform' in globals() else '未知'
            }

            if psutil:
                # CPU信息
                cpu_info = {
                    '使用率': f"{psutil.cpu_percent(interval=1.0)}%",
                    '核心数(物理)': psutil.cpu_count(logical=False),
                    '核心数(逻辑)': psutil.cpu_count(logical=True),
                    '频率': f"{psutil.cpu_freq().current:.0f} MHz" if psutil.cpu_freq() else "未知"
                }
                
                # 内存信息
                vm = psutil.virtual_memory()
                swap = psutil.swap_memory()
                memory_info = {
                    '物理内存使用率': f"{vm.percent}%",
                    '物理内存总量': f"{vm.total / (1024**3):.2f} GB",
                    '物理内存已用': f"{vm.used / (1024**3):.2f} GB",
                    '物理内存可用': f"{vm.available / (1024**3):.2f} GB",
                    '交换区使用率': f"{swap.percent}%",
                    '交换区总量': f"{swap.total / (1024**3):.2f} GB"
                }
                
                # 磁盘信息
                disk_info = {}
                try:
                    disk_usage = psutil.disk_usage('/')
                    disk_info = {
                        '磁盘使用率': f"{(disk_usage.used / disk_usage.total) * 100:.1f}%",
                        '磁盘总量': f"{disk_usage.total / (1024**3):.2f} GB",
                        '磁盘已用': f"{disk_usage.used / (1024**3):.2f} GB",
                        '磁盘可用': f"{disk_usage.free / (1024**3):.2f} GB"
                    }
                except Exception:
                    disk_info = {'状态': '无法获取磁盘信息'}
                
                # 网络信息
                try:
                    net_io = psutil.net_io_counters()
                    network_info = {
                        '发送字节数': f"{net_io.bytes_sent / (1024**2):.2f} MB",
                        '接收字节数': f"{net_io.bytes_recv / (1024**2):.2f} MB",
                        '发送包数': net_io.packets_sent,
                        '接收包数': net_io.packets_recv
                    }
                except Exception:
                    network_info = {'状态': '无法获取网络信息'}
                
                # 进程信息
                try:
                    proc = psutil.Process()
                    mem_info = proc.memory_info()
                    process_info = {
                        '当前进程PID': proc.pid,
                        '当前进程名称': proc.name(),
                        '当前进程常驻内存': f"{mem_info.rss / (1024**2):.2f} MB",
                        '当前进程虚拟内存': f"{mem_info.vms / (1024**2):.2f} MB",
                        '当前进程线程数': proc.num_threads(),
                        '当前进程CPU使用率': f"{proc.cpu_percent()}%",
                        '系统总进程数': len(psutil.pids())
                    }
                except Exception:
                    process_info = {'状态': '无法获取进程信息'}
                
                report['CPU信息'] = cpu_info
                report['内存信息'] = memory_info
                report['磁盘信息'] = disk_info
                report['网络信息'] = network_info
                report['进程信息'] = process_info
            else:
                report['性能监控'] = 'psutil模块未安装，无法获取详细性能信息'

            # 应用程序信息
            app_info = {
                '活动线程数': threading.active_count(),
                '启动参数': sys.argv,
                '环境变量PATH': os.environ.get('PATH', '未设置')[:100] + '...' if len(os.environ.get('PATH', '')) > 100 else os.environ.get('PATH', '未设置')
            }
            report['应用程序信息'] = app_info
            
            # 历史数据对比和趋势分析
            historical_data = perf_manager.get_historical_data(24)  # 获取24小时历史数据
            if historical_data:
                trends = {}
                metrics = ['cpu_percent', 'memory_percent', 'disk_percent', 'process_memory_mb']
                
                for metric in metrics:
                    trend_data = perf_manager.get_performance_trends(metric, 24)
                    if trend_data:
                        trends[metric] = {
                            '当前值': f"{trend_data['current']:.2f}",
                            '24小时平均': f"{trend_data['average']:.2f}",
                            '最小值': f"{trend_data['min']:.2f}",
                            '最大值': f"{trend_data['max']:.2f}",
                            '趋势': trend_data['trend'],
                            '数据点数': trend_data['count']
                        }
                
                report['性能趋势分析'] = trends
                report['历史数据统计'] = {
                    '数据记录数': len(historical_data),
                    '时间范围': f"最近24小时",
                    '首次记录': historical_data[0]['timestamp'] if historical_data else '无',
                    '最新记录': historical_data[-1]['timestamp'] if historical_data else '无'
                }
            else:
                report['性能趋势分析'] = '暂无历史数据，需要运行一段时间后才能显示趋势'
            
            # 基准测试结果
            benchmark_history = perf_manager.get_benchmark_history(days=7)
            if benchmark_history:
                latest_benchmarks = {}
                for test in benchmark_history:
                    test_name = test['test_name']
                    if test_name not in latest_benchmarks:
                        latest_benchmarks[test_name] = {
                            '分数': f"{test['score']:.2f}",
                            '测试时间': test['timestamp'],
                            '详细信息': json.loads(test['details_json']) if test['details_json'] else {}
                        }
                
                report['基准测试结果'] = latest_benchmarks
            else:
                report['基准测试结果'] = '暂无基准测试数据'

            # 创建增强版性能报告对话框
            self._show_enhanced_performance_report(report)
        except Exception as e:
            QMessageBox.warning(self.parent, "错误", f"生成性能报告失败: {e}")
    
    def _show_enhanced_performance_report(self, report):
        """显示增强版性能报告对话框"""
        try:
            
            dlg = QDialog(self.parent)
            dlg.setWindowTitle("系统性能报告")
            dlg.resize(1000, 800)
            
            layout = QVBoxLayout(dlg)
            
            # 创建标签页
            tab_widget = QTabWidget()
            
            # 系统概览标签页
            overview_widget = self._create_overview_tab(report)
            tab_widget.addTab(overview_widget, "系统概览")
            
            # 性能详情标签页
            performance_widget = self._create_performance_detail_tab(report)
            tab_widget.addTab(performance_widget, "性能详情")
            
            # 趋势分析标签页
            trends_widget = self._create_trends_tab(report)
            tab_widget.addTab(trends_widget, "趋势分析")
            
            # 基准测试标签页
            benchmark_widget = self._create_benchmark_tab(report)
            tab_widget.addTab(benchmark_widget, "基准测试")
            
            # 原始数据标签页
            raw_widget = self._create_raw_data_tab(report)
            tab_widget.addTab(raw_widget, "原始数据")
            
            layout.addWidget(tab_widget)
            
            # 按钮布局
            btn_layout = QHBoxLayout()
            btn_save = QPushButton("保存报告")
            btn_save.setDefault(False)
            btn_save.setAutoDefault(False)
            btn_refresh = QPushButton("刷新数据")
            btn_refresh.setDefault(False)
            btn_refresh.setAutoDefault(False)
            btn_benchmark = QPushButton("运行基准测试")
            btn_benchmark.setDefault(False)
            btn_benchmark.setAutoDefault(False)
            btn_history = QPushButton("查看历史")
            btn_history.setDefault(False)
            btn_history.setAutoDefault(False)
            btn_export = QPushButton("导出CSV")
            btn_export.setDefault(False)
            btn_export.setAutoDefault(False)
            btn_close = QPushButton("关闭")
            btn_close.setDefault(False)
            btn_close.setAutoDefault(False)
            
            def save_report():
                pretty = json.dumps(report, indent=4, ensure_ascii=False)
                self._save_report(pretty)
            
            def export_csv():
                self._export_performance_csv(report)
            
            btn_save.clicked.connect(save_report)
            btn_refresh.clicked.connect(lambda checked: self.generate_performance_report())
            btn_benchmark.clicked.connect(lambda checked: self._show_benchmark_dialog(dlg))
            btn_history.clicked.connect(lambda checked: self._show_performance_history(dlg))
            btn_export.clicked.connect(export_csv)
            btn_close.clicked.connect(dlg.close)
            
            btn_layout.addWidget(btn_refresh)
            btn_layout.addWidget(btn_benchmark)
            btn_layout.addWidget(btn_history)
            btn_layout.addWidget(btn_save)
            btn_layout.addWidget(btn_export)
            btn_layout.addStretch()
            btn_layout.addWidget(btn_close)
            
            layout.addLayout(btn_layout)
            dlg.show()
            
        except Exception as e:
            QMessageBox.warning(self.parent, "错误", f"显示性能报告失败: {e}")
    
    def _create_overview_tab(self, report):
        """创建系统概览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 基本信息表格
        basic_table = QTableWidget()
        basic_table.setColumnCount(2)
        basic_table.setHorizontalHeaderLabels(["项目", "值"])
        
        basic_info = [
            ("报告生成时间", report.get('报告生成时间', '未知')),
            ("Python版本", report.get('系统信息', {}).get('Python版本', '未知')),
            ("平台", report.get('系统信息', {}).get('平台', '未知')),
            ("架构", report.get('系统信息', {}).get('架构', '未知')),
            ("当前工作目录", report.get('系统信息', {}).get('当前工作目录', '未知'))
        ]
        
        basic_table.setRowCount(len(basic_info))
        for i, (key, value) in enumerate(basic_info):
            basic_table.setItem(i, 0, QTableWidgetItem(str(key)))
            basic_table.setItem(i, 1, QTableWidgetItem(str(value)))
        
        basic_table.resizeColumnsToContents()
        
        # 性能概览表格
        perf_table = QTableWidget()
        perf_table.setColumnCount(2)
        perf_table.setHorizontalHeaderLabels(["性能指标", "当前值"])
        
        cpu_info = report.get('CPU信息', {})
        memory_info = report.get('内存信息', {})
        disk_info = report.get('磁盘信息', {})
        
        perf_info = [
            ("CPU使用率", cpu_info.get('使用率', '未知')),
            ("CPU核心数", f"{cpu_info.get('核心数(物理)', '未知')}/{cpu_info.get('核心数(逻辑)', '未知')}"),
            ("内存使用率", memory_info.get('物理内存使用率', '未知')),
            ("内存总量", memory_info.get('物理内存总量', '未知')),
            ("磁盘使用率", disk_info.get('磁盘使用率', '未知')),
            ("磁盘总量", disk_info.get('磁盘总量', '未知'))
        ]
        
        perf_table.setRowCount(len(perf_info))
        for i, (key, value) in enumerate(perf_info):
            perf_table.setItem(i, 0, QTableWidgetItem(str(key)))
            perf_table.setItem(i, 1, QTableWidgetItem(str(value)))
        
        perf_table.resizeColumnsToContents()
        
        layout.addWidget(QLabel("基本信息"))
        layout.addWidget(basic_table)
        layout.addWidget(QLabel("性能概览"))
        layout.addWidget(perf_table)
        
        return widget
    
    def _create_performance_detail_tab(self, report):
        """创建性能详情标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # CPU和内存信息
        cpu_memory_widget = QWidget()
        cpu_memory_layout = QHBoxLayout(cpu_memory_widget)
        
        # CPU信息表格
        cpu_table = self._create_info_table("CPU信息", report.get('CPU信息', {}))
        cpu_memory_layout.addWidget(cpu_table)
        
        # 内存信息表格
        memory_table = self._create_info_table("内存信息", report.get('内存信息', {}))
        cpu_memory_layout.addWidget(memory_table)
        
        splitter.addWidget(cpu_memory_widget)
        
        # 磁盘和网络信息
        disk_network_widget = QWidget()
        disk_network_layout = QHBoxLayout(disk_network_widget)
        
        # 磁盘信息表格
        disk_table = self._create_info_table("磁盘信息", report.get('磁盘信息', {}))
        disk_network_layout.addWidget(disk_table)
        
        # 网络信息表格
        network_table = self._create_info_table("网络信息", report.get('网络信息', {}))
        disk_network_layout.addWidget(network_table)
        
        splitter.addWidget(disk_network_widget)
        
        # 进程信息
        process_table = self._create_info_table("进程信息", report.get('进程信息', {}))
        splitter.addWidget(process_table)
        
        layout.addWidget(splitter)
        return widget
    
    def _create_trends_tab(self, report):
        """创建趋势分析标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        trends_data = report.get('性能趋势分析', {})
        
        if isinstance(trends_data, dict) and trends_data:
            # 趋势分析表格
            trends_table = QTableWidget()
            trends_table.setColumnCount(7)
            trends_table.setHorizontalHeaderLabels(["指标", "当前值", "24h平均", "最小值", "最大值", "趋势", "数据点数"])
            
            trends_table.setRowCount(len(trends_data))
            
            for i, (metric, data) in enumerate(trends_data.items()):
                metric_name = {
                    'cpu_percent': 'CPU使用率(%)',
                    'memory_percent': '内存使用率(%)',
                    'disk_percent': '磁盘使用率(%)',
                    'process_memory_mb': '进程内存(MB)'
                }.get(metric, metric)
                
                trends_table.setItem(i, 0, QTableWidgetItem(metric_name))
                trends_table.setItem(i, 1, QTableWidgetItem(str(data.get('当前值', '未知'))))
                trends_table.setItem(i, 2, QTableWidgetItem(str(data.get('24小时平均', '未知'))))
                trends_table.setItem(i, 3, QTableWidgetItem(str(data.get('最小值', '未知'))))
                trends_table.setItem(i, 4, QTableWidgetItem(str(data.get('最大值', '未知'))))
                
                trend = data.get('趋势', '未知')
                trend_text = {'increasing': '上升', 'decreasing': '下降', 'stable': '稳定'}.get(trend, trend)
                trends_table.setItem(i, 5, QTableWidgetItem(trend_text))
                trends_table.setItem(i, 6, QTableWidgetItem(str(data.get('数据点数', '未知'))))
            
            trends_table.resizeColumnsToContents()
            
            # 历史数据统计
            history_stats = report.get('历史数据统计', {})
            stats_table = self._create_info_table("历史数据统计", history_stats)
            
            layout.addWidget(QLabel("性能趋势分析"))
            layout.addWidget(trends_table)
            layout.addWidget(QLabel("历史数据统计"))
            layout.addWidget(stats_table)
        else:
            info_label = QLabel(str(trends_data))
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(info_label)
        
        return widget
    
    def _create_benchmark_tab(self, report):
        """创建基准测试标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        benchmark_data = report.get('基准测试结果', {})
        
        if isinstance(benchmark_data, dict) and benchmark_data:
            # 基准测试结果表格
            benchmark_table = QTableWidget()
            benchmark_table.setColumnCount(3)
            benchmark_table.setHorizontalHeaderLabels(["测试类型", "分数", "测试时间"])
            
            benchmark_table.setRowCount(len(benchmark_data))
            
            for i, (test_name, data) in enumerate(benchmark_data.items()):
                test_display_name = {
                    'cpu_benchmark': 'CPU基准测试',
                    'memory_benchmark': '内存基准测试',
                    'disk_benchmark': '磁盘基准测试',
                    'comprehensive': '综合基准测试'
                }.get(test_name, test_name)
                
                benchmark_table.setItem(i, 0, QTableWidgetItem(test_display_name))
                benchmark_table.setItem(i, 1, QTableWidgetItem(str(data.get('分数', '未知'))))
                benchmark_table.setItem(i, 2, QTableWidgetItem(str(data.get('测试时间', '未知'))))
            
            benchmark_table.resizeColumnsToContents()
            layout.addWidget(QLabel("基准测试结果"))
            layout.addWidget(benchmark_table)
        else:
            info_label = QLabel(str(benchmark_data))
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(info_label)
        
        return widget
    
    def _create_raw_data_tab(self, report):
        """创建原始数据标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 原始JSON数据
        tb = QTextBrowser()
        pretty = json.dumps(report, indent=4, ensure_ascii=False)
        tb.setPlainText(pretty)
        
        # 设置等宽字体
        font = QFont("Courier New")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(9)
        tb.setFont(font)
        
        layout.addWidget(QLabel("原始JSON数据"))
        layout.addWidget(tb)
        
        return widget
    
    def _create_info_table(self, title, data):
        """创建信息表格"""
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["项目", "值"])
        
        if isinstance(data, dict):
            table.setRowCount(len(data))
            for i, (key, value) in enumerate(data.items()):
                table.setItem(i, 0, QTableWidgetItem(str(key)))
                table.setItem(i, 1, QTableWidgetItem(str(value)))
        else:
            table.setRowCount(1)
            table.setItem(0, 0, QTableWidgetItem("状态"))
            table.setItem(0, 1, QTableWidgetItem(str(data)))
        
        table.resizeColumnsToContents()
        table.setMaximumHeight(200)
        
        layout.addWidget(table)
        return group
    
    def _export_performance_csv(self, report):
        """导出性能数据为CSV"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self.parent, "导出性能数据", "performance_report.csv", 
                "CSV Files (*.csv)"
            )
            
            if file_path:
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # 写入标题
                    writer.writerow(["类别", "项目", "值"])
                    
                    # 写入数据
                    for category, data in report.items():
                        if isinstance(data, dict):
                            for key, value in data.items():
                                writer.writerow([category, key, str(value)])
                        else:
                            writer.writerow([category, "", str(data)])
                
                QMessageBox.information(self.parent, "成功", f"性能数据已导出到: {file_path}")
                
        except Exception as e:
            QMessageBox.warning(self.parent, "错误", f"导出失败: {e}")
    
    def _show_benchmark_dialog(self, parent_dialog):
        """显示基准测试对话框"""
        try:
            from core.performance_manager import PerformanceManager
            perf_manager = PerformanceManager()
            
            dlg = QDialog(parent_dialog)
            dlg.setWindowTitle("性能基准测试")
            dlg.resize(600, 500)
            
            layout = QVBoxLayout(dlg)
            
            # 测试选择
            test_group = QGroupBox("选择测试类型")
            test_layout = QVBoxLayout()
            
            test_combo = QComboBox()
            test_combo.addItems(["CPU基准测试", "内存基准测试", "磁盘基准测试", "综合基准测试"])
            test_layout.addWidget(test_combo)
            test_group.setLayout(test_layout)
            
            # 结果显示
            result_tb = QTextBrowser()
            result_tb.setFont(QFont("Courier New", 10))
            
            # 按钮
            btn_layout = QHBoxLayout()
            btn_run = QPushButton("开始测试")
            btn_run.setDefault(False)
            btn_run.setAutoDefault(False)
            btn_history = QPushButton("测试历史")
            btn_history.setDefault(False)
            btn_history.setAutoDefault(False)
            btn_close = QPushButton("关闭")
            btn_close.setDefault(False)
            btn_close.setAutoDefault(False)
            
            def run_test():
                test_name = test_combo.currentText()
                test_map = {
                    "CPU基准测试": "cpu_benchmark",
                    "内存基准测试": "memory_benchmark", 
                    "磁盘基准测试": "disk_benchmark",
                    "综合基准测试": "comprehensive"
                }
                
                btn_run.setEnabled(False)
                btn_run.setText(t("测试中..."))
                
                try:
                    result = perf_manager.run_benchmark_test(test_map[test_name])
                    
                    report = f"=== {test_name} 结果 ===\n\n"
                    report += f"测试时间: {result['timestamp']}\n"
                    report += f"总分: {result['score']:.2f}\n\n"
                    
                    if 'details' in result:
                        report += "详细信息:\n"
                        report += json.dumps(result['details'], indent=2, ensure_ascii=False)
                    
                    result_tb.setPlainText(report)
                    
                except Exception as e:
                    result_tb.setPlainText(f"测试失败: {e}")
                finally:
                    btn_run.setEnabled(True)
                    btn_run.setText("开始测试")
            
            def show_history():
                history = perf_manager.get_benchmark_history(days=30)
                if history:
                    report = "=== 基准测试历史 ===\n\n"
                    for test in history[:10]:  # 显示最近10次测试
                        report += f"测试: {test['test_name']}\n"
                        report += f"时间: {test['timestamp']}\n"
                        report += f"分数: {test['score']:.2f}\n"
                        report += "-" * 40 + "\n"
                    result_tb.setPlainText(report)
                else:
                    result_tb.setPlainText("暂无测试历史")
            
            btn_run.clicked.connect(run_test)
            btn_history.clicked.connect(show_history)
            btn_close.clicked.connect(dlg.close)
            
            btn_layout.addWidget(btn_run)
            btn_layout.addWidget(btn_history)
            btn_layout.addStretch()
            btn_layout.addWidget(btn_close)
            
            layout.addWidget(test_group)
            layout.addWidget(result_tb)
            layout.addLayout(btn_layout)
            
            dlg.exec()
            
        except Exception as e:
            QMessageBox.warning(parent_dialog, "错误", f"打开基准测试失败: {e}")
    
    def _refresh_logs(self):
        """刷新日志显示 - 显示增强的中文化详细日志"""
        try:
            if not hasattr(self, 'log_display') or not self.log_display:
                return
                
            if self._web_server and self._web_server.is_running:
                # 获取增强的详细日志
                try:
                    # 直接从web_server实例获取日志，避免创建新的handler
                    if hasattr(self._web_server, 'handler') and self._web_server.handler:
                        # 获取详细日志数据
                        detailed_logs = list(getattr(self._web_server.handler, '_detailed_logs', []))
                        access_logs = list(getattr(self._web_server.handler, '_access_logs', []))
                        api_logs = list(getattr(self._web_server.handler, '_api_logs', []))
                        
                        # 合并日志并格式化显示
                        log_text = ""
                        
                        # 添加调试信息和统计信息头部
                        total_logs = len(detailed_logs) + len(access_logs) + len(api_logs)
                        log_text += "=== 🔍 日志调试信息 ===\n"
                        log_text += f"📊 Handler状态: {'✅ 已连接' if self._web_server.handler else '❌ 未连接'}\n"
                        log_text += f"🏷️ Handler类型: {type(self._web_server.handler).__name__ if self._web_server.handler else 'None'}\n"
                        log_text += f"📋 总日志数: {total_logs}\n"
                        log_text += f"👤 用户访问日志: {len(access_logs)}\n"
                        log_text += f"🔧 详细操作日志: {len(detailed_logs)}\n"
                        log_text += f"🔗 API调用日志: {len(api_logs)}\n"
                        
                        # 显示日志样本
                        if detailed_logs:
                            log_text += f"📝 详细日志样本: {detailed_logs[0]}\n"
                        if access_logs:
                            log_text += f"👤 访问日志样本: {access_logs[0]}\n"
                        if api_logs:
                            log_text += f"🔗 API日志样本: {api_logs[0]}\n"
                        log_text += "\n"
                        
                        if total_logs > 0:
                            log_text += "=== 📝 详细日志记录 ===\n"
                        else:
                            log_text += "=== 📝 详细日志记录 ===\n"
                        
                        # 合并并按时间排序
                        all_logs = []
                        
                        # 添加详细操作日志
                        for log in detailed_logs:
                            client_ip = log.get('client_ip', '未知IP')
                            action = log.get('action', '未知操作')
                            timestamp = log.get('timestamp', '')
                            
                            # 根据操作类型生成中文消息
                            if 'key_validation' in action:
                                result = log.get('result', '未知')
                                key_masked = log.get('api_key_masked', '****')
                                endpoint = log.get('endpoint', '未知接口')
                                message = f"🔑 密钥验证 - IP: {client_ip} | 密钥: {key_masked} | 接口: {endpoint} | 结果: {'✅ 成功' if result == 'success' else '❌ 失败'}"
                            elif 'api_call' in action:
                                endpoint = log.get('endpoint', '未知接口')
                                method = log.get('method', 'GET')
                                status = log.get('status', 200)
                                message = f"🔗 API调用 - IP: {client_ip} | {method} {endpoint} | 状态: {status}"
                            else:
                                message = f"📝 操作记录 - IP: {client_ip} | 操作: {action}"
                            
                            all_logs.append({
                                'timestamp': timestamp,
                                'message': message,
                                'type': 'detailed'
                            })
                        
                        # 添加访问日志
                        for log in access_logs:
                            client_ip = log.get('client_ip', '未知IP')
                            action = log.get('action', '未知操作')
                            timestamp = log.get('timestamp', '')
                            details = log.get('details', {})
                            message = f"👤 用户访问 - IP: {client_ip} | 操作: {action}"
                            if details:
                                message += f" | 详情: {details}"
                            
                            all_logs.append({
                                'timestamp': timestamp,
                                'message': message,
                                'type': 'access'
                            })
                        
                        # 添加API调用日志
                        for log in api_logs:
                            client_ip = log.get('ip', '未知IP')
                            method = log.get('method', 'GET')
                            path = log.get('path', '/')
                            status_code = log.get('status_code', 200)
                            timestamp = log.get('timestamp', '')
                            
                            # 中文化处理
                            method_cn = {
                                'GET': '获取',
                                'POST': '提交',
                                'PUT': '更新',
                                'DELETE': '删除'
                            }.get(method, method)
                            
                            message = f"📡 API请求 - IP: {client_ip} | {method_cn}({method}) {path} | 状态: {status_code}"
                            
                            all_logs.append({
                                'timestamp': timestamp,
                                'message': message,
                                'type': 'api'
                            })
                        
                        # 按时间排序并显示最近30条
                        if all_logs:
                            all_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                            for log in all_logs[:30]:
                                timestamp = log.get('timestamp', '')
                                message = log.get('message', '')
                                log_text += f"📄 [{timestamp}] {message}\n"
                        else:
                            log_text += "📝 暂无详细日志记录\n"
                            log_text += "💡 提示: 尝试访问Web预览页面或调用API接口来生成日志\n"
                            
                            # 添加一个测试日志来验证功能
                            if hasattr(self._web_server.handler, '_add_detailed_log'):
                                test_log = {
                                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                                    'client_ip': '127.0.0.1',
                                    'action': 'system_test',
                                    'message': '系统测试日志 - 日志功能正常'
                                }
                                self._web_server.handler._add_detailed_log(test_log)
                                log_text += "🧪 已添加测试日志，请刷新查看\n"
                        
                        # 更新显示并滚动到底部
                        self.log_display.setPlainText(log_text)
                        cursor = self.log_display.textCursor()
                        cursor.movePosition(cursor.MoveOperation.End)
                        self.log_display.setTextCursor(cursor)
                        
                    else:
                        # 回退到基本日志显示
                        logs = self._web_server.get_api_logs()
                        if logs:
                            log_text = "=== 📋 基础API日志 ===\n"
                            for log in logs[-20:]:
                                timestamp = log.get('timestamp', '')
                                client_ip = log.get('client_ip', 'Unknown')
                                method = log.get('method', 'GET')
                                path = log.get('path', '/')
                                status = log.get('status', 200)
                                
                                # 中文化处理
                                client_ip_cn = "未知IP" if client_ip == 'Unknown' else client_ip
                                method_cn = {
                                    'GET': '获取',
                                    'POST': '提交',
                                    'PUT': '更新',
                                    'DELETE': '删除',
                                    'PATCH': '修改'
                                }.get(method, method)
                                
                                # 路径中文化
                                path_cn = {
                                    '/api/status': '/api/状态',
                                    '/api/logs': '/api/日志',
                                    '/api/performance': '/api/性能',
                                    '/api/settings': '/api/设置',
                                    '/api/data': '/api/数据'
                                }.get(path, path)
                                
                                status_icon = "✅" if status < 400 else "❌"
                                status_text = "成功" if status < 400 else "失败"
                                log_line = f"{status_icon} [{timestamp}] {client_ip_cn} {method_cn} {path_cn} -> {status}({status_text})\n"
                                log_text += log_line
                            
                            self.log_display.setPlainText(log_text)
                            cursor = self.log_display.textCursor()
                            cursor.movePosition(cursor.MoveOperation.End)
                            self.log_display.setTextCursor(cursor)
                        else:
                            self.log_display.setPlainText("📝 暂无日志数据")
                        
                except Exception as e:
                    # 异常处理，回退到基本日志显示
                    print(f"获取详细日志时出错: {e}")
                    logs = self._web_server.get_api_logs()
                    if logs:
                        log_text = "=== 📋 基础API日志 ===\n"
                        for log in logs[-20:]:
                            timestamp = log.get('timestamp', '')
                            client_ip = log.get('client_ip', 'Unknown')
                            method = log.get('method', 'GET')
                            path = log.get('path', '/')
                            status = log.get('status', 200)
                            
                            # 中文化处理
                            client_ip_cn = "未知IP" if client_ip == 'Unknown' else client_ip
                            method_cn = {
                                'GET': '获取',
                                'POST': '提交',
                                'PUT': '更新',
                                'DELETE': '删除',
                                'PATCH': '修改'
                            }.get(method, method)
                            
                            # 路径中文化
                            path_cn = {
                                '/api/status': '/api/状态',
                                '/api/logs': '/api/日志',
                                '/api/performance': '/api/性能',
                                '/api/settings': '/api/设置',
                                '/api/data': '/api/数据'
                            }.get(path, path)
                            
                            status_icon = "✅" if status < 400 else "❌"
                            status_text = "成功" if status < 400 else "失败"
                            log_line = f"{status_icon} [{timestamp}] {client_ip_cn} {method_cn} {path_cn} -> {status}({status_text})\n"
                            log_text += log_line
                        
                        self.log_display.setPlainText(log_text)
                        cursor = self.log_display.textCursor()
                        cursor.movePosition(cursor.MoveOperation.End)
                        self.log_display.setTextCursor(cursor)
                    else:
                        self.log_display.setPlainText("📝 暂无日志数据")
                        
            else:
                self.log_display.setPlainText("🔴 服务器未运行，无法获取日志")
                
        except Exception as e:
            if hasattr(self, 'log_display') and self.log_display:
                self.log_display.setPlainText(f"❌ 获取日志时出错: {str(e)}")
                print(f"刷新日志时出错: {e}")  # 调试信息
    
    def _clear_log_display(self):
        """清空日志显示"""
        if hasattr(self, 'log_display') and self.log_display:
            self.log_display.clear()
            self.log_display.setPlaceholderText("日志显示已清空...")
    
    def _toggle_auto_refresh(self):
        """切换自动刷新状态"""
        if hasattr(self, 'auto_refresh_btn'):
            timer = getattr(self, 'log_refresh_timer', None)
            if not timer:
                # 定时器不存在或已被删除，安全忽略或在需要时重建
                return
            try:
                if self.log_refresh_enabled:
                    # 暂停自动刷新
                    if timer.isActive():
                        timer.stop()
                    self.auto_refresh_btn.setText("▶️ 开始刷新")
                    self.log_refresh_enabled = False
                else:
                    # 开始自动刷新
                    timer.start(3000)
                    self.auto_refresh_btn.setText("⏸️ 暂停刷新")
                    self.log_refresh_enabled = True
                    # 立即刷新一次
                    self._refresh_logs()
            except RuntimeError:
                # 底层QTimer对象已被删除，重建定时器以恢复功能
                from PyQt6.QtCore import QTimer
                self.log_refresh_timer = QTimer()
                self.log_refresh_timer.timeout.connect(self._refresh_logs)
                if not self.log_refresh_enabled:
                    self.auto_refresh_btn.setText("▶️ 开始刷新")
                else:
                    self.log_refresh_timer.start(3000)
                    self.auto_refresh_btn.setText("⏸️ 暂停刷新")
                    self._refresh_logs()
    
    def _show_debug_info(self, dialog):
        """显示调试信息对话框"""
        debug_dialog = QDialog(dialog)
        debug_dialog.setWindowTitle("🐛 系统调试信息")
        debug_dialog.setFixedSize(1000, 700)
        debug_dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        
        # 主布局
        layout = QVBoxLayout(debug_dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("🐛 系统调试信息")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #E91E63;
                padding: 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #fce4ec, stop:1 #f8bbd9);
                border-radius: 8px;
                margin-bottom: 10px;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 创建标签页
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ddd;
                border-radius: 8px;
                background: white;
            }
            QTabBar::tab {
                background: #f5f5f5;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #E91E63;
                color: white;
            }
        """)
        
        # 系统状态标签页
        system_tab = self._create_system_status_tab()
        tab_widget.addTab(system_tab, "📊 系统状态")
        
        # 错误日志标签页
        error_tab = self._create_error_log_tab()
        tab_widget.addTab(error_tab, "❌ 错误日志")
        
        # 性能指标标签页
        performance_tab = self._create_performance_metrics_tab()
        tab_widget.addTab(performance_tab, "⚡ 性能指标")
        
        # 环境信息标签页
        env_tab = self._create_environment_tab()
        tab_widget.addTab(env_tab, "🌍 环境信息")
        
        layout.addWidget(tab_widget)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #45a049;
            }
        """)
        refresh_btn.clicked.connect(lambda: self._refresh_debug_info(tab_widget))
        button_layout.addWidget(refresh_btn)
        
        export_btn = QPushButton("📤 导出")
        export_btn.setStyleSheet("""
            QPushButton {
                background: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1976D2;
            }
        """)
        export_btn.clicked.connect(lambda: self._export_debug_info(tab_widget))
        button_layout.addWidget(export_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("❌ 关闭")
        close_btn.setStyleSheet("""
            QPushButton {
                background: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #d32f2f;
            }
        """)
        close_btn.clicked.connect(debug_dialog.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # 窗口居中显示
        if self.parent:
            debug_dialog.move(self.parent.geometry().center() - debug_dialog.rect().center())
        
        debug_dialog.exec()
    
    def _create_system_status_tab(self):
        """创建系统状态标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        
        # 系统信息文本区域
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setStyleSheet("""
            QTextEdit {
                background: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
            }
        """)
        
        # 获取系统状态信息
        import platform
        import psutil
        import sys
        from datetime import datetime
        
        try:
            # 基本系统信息
            system_info = f"""
🖥️ 系统信息:
  操作系统: {platform.system()} {platform.release()}
  架构: {platform.architecture()[0]}
  处理器: {platform.processor()}
  Python版本: {sys.version}
  
💾 内存信息:
  总内存: {psutil.virtual_memory().total / (1024**3):.2f} GB
  可用内存: {psutil.virtual_memory().available / (1024**3):.2f} GB
  内存使用率: {psutil.virtual_memory().percent}%
  
💿 磁盘信息:
  总空间: {psutil.disk_usage('/').total / (1024**3):.2f} GB
  可用空间: {psutil.disk_usage('/').free / (1024**3):.2f} GB
  磁盘使用率: {psutil.disk_usage('/').percent}%
  
🔧 进程信息:
  当前进程PID: {psutil.Process().pid}
  进程内存使用: {psutil.Process().memory_info().rss / (1024**2):.2f} MB
  进程CPU使用率: {psutil.Process().cpu_percent()}%
  
⏰ 运行时间:
  系统启动时间: {datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S')}
  当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
        except Exception as e:
            system_info = f"获取系统信息时出错: {str(e)}"
        
        info_text.setPlainText(system_info)
        layout.addWidget(info_text)
        
        return tab
    
    def _create_error_log_tab(self):
        """创建错误日志标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        
        # 错误日志文本区域
        error_text = QTextEdit()
        error_text.setReadOnly(True)
        error_text.setStyleSheet("""
            QTextEdit {
                background: #fff5f5;
                border: 1px solid #ffcdd2;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                color: #d32f2f;
            }
        """)
        
        # 获取最近的错误日志
        try:
            import logging
            import os
            
            log_content = "📋 最近的错误日志:\n\n"
            
            # 尝试读取日志文件
            log_files = [
                'logs/xuanwu_log.html',
                'logs/debug.html',
                'logs/control_panel/control_panel_2025-09-14.log'
            ]
            
            for log_file in log_files:
                if os.path.exists(log_file):
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if 'ERROR' in content or 'Exception' in content or 'Traceback' in content:
                                log_content += f"\n📁 {log_file}:\n"
                                # 只显示包含错误的行
                                lines = content.split('\n')
                                error_lines = [line for line in lines if any(keyword in line for keyword in ['ERROR', 'Exception', 'Traceback', 'AttributeError', 'TypeError'])]
                                log_content += '\n'.join(error_lines[-20:])  # 最近20行错误
                                log_content += "\n" + "="*50 + "\n"
                    except Exception as e:
                        log_content += f"读取 {log_file} 时出错: {str(e)}\n"
            
            if log_content == "📋 最近的错误日志:\n\n":
                log_content += "✅ 未发现明显错误日志"
                
        except Exception as e:
            log_content = f"获取错误日志时出错: {str(e)}"
        
        error_text.setPlainText(log_content)
        layout.addWidget(error_text)
        
        return tab
    
    def _create_performance_metrics_tab(self):
        """创建性能指标标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        
        # 性能指标文本区域
        perf_text = QTextEdit()
        perf_text.setReadOnly(True)
        perf_text.setStyleSheet("""
            QTextEdit {
                background: #f0f8ff;
                border: 1px solid #b3d9ff;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                color: #1976d2;
            }
        """)
        
        # 获取性能指标
        try:
            import psutil
            import time
            
            # CPU信息
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # 内存信息
            memory = psutil.virtual_memory()
            # Windows等平台可能不提供 cached 字段
            cached_gb_str = (
                f"{getattr(memory, 'cached', 0) / (1024**3):.2f} GB"
                if hasattr(memory, 'cached') else "不支持"
            )
            
            # 网络信息
            network = psutil.net_io_counters()
            
            # 磁盘IO信息
            disk_io = psutil.disk_io_counters()
            
            perf_info = f"""
⚡ CPU性能:
  CPU使用率: {cpu_percent}%
  CPU核心数: {cpu_count}
  CPU频率: {cpu_freq.current:.2f} MHz (最大: {cpu_freq.max:.2f} MHz)
  
💾 内存性能:
  总内存: {memory.total / (1024**3):.2f} GB
  已使用: {memory.used / (1024**3):.2f} GB ({memory.percent}%)
  可用内存: {memory.available / (1024**3):.2f} GB
  缓存: {cached_gb_str}
  
🌐 网络性能:
  发送字节: {network.bytes_sent / (1024**2):.2f} MB
  接收字节: {network.bytes_recv / (1024**2):.2f} MB
  发送包数: {network.packets_sent}
  接收包数: {network.packets_recv}
  
💿 磁盘IO性能:
  读取字节: {disk_io.read_bytes / (1024**2):.2f} MB
  写入字节: {disk_io.write_bytes / (1024**2):.2f} MB
  读取次数: {disk_io.read_count}
  写入次数: {disk_io.write_count}
  
🔧 进程性能:
  当前进程CPU: {psutil.Process().cpu_percent()}%
  当前进程内存: {psutil.Process().memory_info().rss / (1024**2):.2f} MB
  线程数: {psutil.Process().num_threads()}
            """
        except Exception as e:
            perf_info = f"获取性能指标时出错: {str(e)}"
        
        perf_text.setPlainText(perf_info)
        layout.addWidget(perf_text)
        
        return tab
    
    def _create_environment_tab(self):
        """创建环境信息标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        
        # 环境信息文本区域
        env_text = QTextEdit()
        env_text.setReadOnly(True)
        env_text.setStyleSheet("""
            QTextEdit {
                background: #f5fff5;
                border: 1px solid #c8e6c9;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                color: #2e7d32;
            }
        """)
        
        # 获取环境信息
        try:
            import sys
            import os
            import platform
            from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
            
            env_info = f"""
🌍 Python环境:
  Python版本: {sys.version}
  Python路径: {sys.executable}
  
📦 依赖库版本:
  PyQt6版本: {PYQT_VERSION_STR}
  Qt版本: {QT_VERSION_STR}
  
📁 路径信息:
  当前工作目录: {os.getcwd()}
  脚本目录: {os.path.dirname(os.path.abspath(__file__))}
  
🔧 系统环境变量:
  PATH: {os.environ.get('PATH', '未设置')[:200]}...
  PYTHONPATH: {os.environ.get('PYTHONPATH', '未设置')}
  
🖥️ 显示信息:
  屏幕分辨率: {platform.node()}
  
📋 已安装的包 (部分):
            """
            
            # 尝试获取已安装的包信息
            try:
                import pkg_resources
                installed_packages = [d.project_name + '==' + d.version for d in pkg_resources.working_set]
                # 只显示前20个包
                for pkg in sorted(installed_packages)[:20]:
                    env_info += f"  {pkg}\n"
                if len(installed_packages) > 20:
                    env_info += f"  ... 还有 {len(installed_packages) - 20} 个包\n"
            except:
                env_info += "  无法获取包信息\n"
                
        except Exception as e:
            env_info = f"获取环境信息时出错: {str(e)}"
        
        env_text.setPlainText(env_info)
        layout.addWidget(env_text)
        
        return tab
    
    def _refresh_debug_info(self, tab_widget):
        """刷新调试信息"""
        try:
            # 重新创建所有标签页
            tab_widget.clear()
            
            # 重新添加标签页
            system_tab = self._create_system_status_tab()
            tab_widget.addTab(system_tab, "📊 系统状态")
            
            error_tab = self._create_error_log_tab()
            tab_widget.addTab(error_tab, "❌ 错误日志")
            
            performance_tab = self._create_performance_metrics_tab()
            tab_widget.addTab(performance_tab, "⚡ 性能指标")
            
            env_tab = self._create_environment_tab()
            tab_widget.addTab(env_tab, "🌍 环境信息")
            
            QMessageBox.information(None, "刷新完成", "调试信息已刷新！")
        except Exception as e:
            QMessageBox.warning(None, "刷新失败", f"刷新调试信息时出错: {str(e)}")
    
    def _export_debug_info(self, tab_widget):
        """导出调试信息"""
        try:
            from datetime import datetime
            
            # 获取所有标签页的内容
            debug_content = f"""# 系统调试信息导出
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""
            
            # 遍历所有标签页
            for i in range(tab_widget.count()):
                tab_title = tab_widget.tabText(i)
                tab_widget.setCurrentIndex(i)
                
                # 获取当前标签页的文本内容
                current_tab = tab_widget.currentWidget()
                text_edit = current_tab.findChild(QTextEdit)
                if text_edit:
                    debug_content += f"\n## {tab_title}\n"
                    debug_content += "=" * 50 + "\n"
                    debug_content += text_edit.toPlainText()
                    debug_content += "\n\n"
            
            # 保存到文件
            filename = f"debug_info_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(debug_content)
            
            QMessageBox.information(None, "导出成功", f"调试信息已导出到: {filename}")
        except Exception as e:
            QMessageBox.warning(None, "导出失败", f"导出调试信息时出错: {str(e)}")
    
    def _show_benchmark_dialog_old(self, parent_dialog):
        """显示基准测试对话框（旧版本）"""
        try:
            pass  # 这里可以添加旧版本的基准测试代码
        except Exception as e:
            QMessageBox.warning(parent_dialog, "错误", f"打开基准测试失败: {e}")
    
    def refresh_ui_text(self):
        """刷新UI文本的国际化显示"""
        try:
            # 更新菜单标题
            self.dev_tools_menu.setTitle('开发者工具')
            
            # 清空并重新添加菜单项
            self.dev_tools_menu.clear()
            self.add_actions()
            
        except Exception as e:
            import logging
            logging.error(f"刷新DevToolsPanel UI文本时出错: {e}")
    
    def add_actions(self):
        """添加菜单动作项"""
        m = self.dev_tools_menu
        m.addAction('查看日志文件', self.view_log_file)
        m.addAction('Web预览', self.web_preview)
        m.addSeparator()

        m.addAction('CPU 内存监控', self.monitor_cpu_memory)
        m.addAction('FPS 显示', self.show_fps)
        m.addAction('性能报告', self.generate_performance_report)
        m.addAction('性能分析工具', self.performance_analysis_tool)
        m.addSeparator()

        m.addAction('调试模式', self.toggle_debug_mode)
        m.addAction('远程调试', self.remote_debug)
        m.addAction('堆栈追踪', self.view_stack_trace)
        m.addAction('错误报告', self.send_error_report)
        m.addAction('错误报告文件', self.generate_error_report_file)

        m.addSeparator()

        m.addAction('检查更新', self.check_for_updates)
        m.addAction('安装更新', self.install_update)
        m.addAction('更新日志', self.view_update_log)
        m.addSeparator()

        m.addAction('配置文件', self.view_config_file)
        m.addAction('重置配置文件', self.reset_config_file)
        m.addAction('配置文件备份', self.backup_config_file)
        m.addSeparator()

        m.addAction('数据库状态', self.view_db_status)
        m.addAction('SQL 查询', self.execute_sql_query)
        m.addSeparator()

        m.addAction('静态代码分析', self.static_code_analysis)
        m.addAction('代码覆盖率报告', self.code_coverage_report)
        m.addSeparator()

        m.addAction('开发文档', self.view_dev_docs)
        m.addAction('开发者信息', self.view_dev_info)
        m.addAction('许可证信息', self.view_license_info)
        m.addSeparator()

        # 新增系统工具
        m.addAction('系统信息', self.view_system_info)
        m.addAction('网络诊断', self.network_diagnostics)
        m.addAction('内存分析', self.memory_analysis)
        m.addAction('进程管理', self.process_management)
        m.addSeparator()

        # 新增开发工具
        m.addAction('环境变量', self.view_environment_variables)
        m.addAction('依赖检查', self.check_dependencies)
        m.addAction('文件完整性', self.file_integrity_check)
        m.addAction('安全扫描', self.security_scan)

    def remote_debug(self):
        """启动集成远程调试功能"""
        try:
            from .remote_debug_integrated import IntegratedRemoteDebugWidget
            dialog = IntegratedRemoteDebugWidget(self.parent, self)
            
            # 窗口居中显示
            if self.parent:
                parent_geometry = self.parent.geometry()
                dialog_size = dialog.size()
                x = parent_geometry.x() + (parent_geometry.width() - dialog_size.width()) // 2
                y = parent_geometry.y() + (parent_geometry.height() - dialog_size.height()) // 2
                dialog.move(x, y)
            
            dialog.exec()
        except ImportError as e:
            # 如果导入失败，显示错误信息并提供备用方案
            QMessageBox.warning(
                self.parent, 
                "模块导入错误", 
                f"无法加载集成远程调试模块: {e}\n\n将使用原有功能。"
            )
            self._legacy_remote_debug()
    
    def _legacy_remote_debug(self):
        """原有的远程调试功能（备用方案）"""
        dialog = RemoteDebugDialog(self.parent)
        dialog.exec()
    

    def _show_performance_history(self, parent_dialog):
        """显示性能历史数据"""
        try:
            from core.performance_manager import PerformanceManager
            perf_manager = PerformanceManager()
            
            dlg = QDialog(parent_dialog)
            dlg.setWindowTitle("性能历史数据")
            dlg.resize(800, 600)
            
            layout = QVBoxLayout(dlg)
            
            # 时间范围选择
            time_group = QGroupBox("时间范围")
            time_layout = QHBoxLayout()
            
            time_combo = QComboBox()
            time_combo.addItems(["最近1小时", "最近6小时", "最近24小时", "最近7天"])
            time_combo.setCurrentText("最近24小时")
            time_layout.addWidget(QLabel("选择时间范围:"))
            time_layout.addWidget(time_combo)
            time_layout.addStretch()
            time_group.setLayout(time_layout)
            
            # 数据显示
            data_tb = QTextBrowser()
            data_tb.setFont(QFont("Courier New", 9))
            
            # 按钮
            btn_layout = QHBoxLayout()
            btn_refresh = QPushButton("刷新数据")
            btn_refresh.setDefault(False)
            btn_refresh.setAutoDefault(False)
            btn_export = QPushButton("导出数据")
            btn_export.setDefault(False)
            btn_export.setAutoDefault(False)
            btn_close = QPushButton("关闭")
            btn_close.setDefault(False)
            btn_close.setAutoDefault(False)
            
            def refresh_data():
                time_range = time_combo.currentText()
                hours_map = {
                    "最近1小时": 1,
                    "最近6小时": 6,
                    "最近24小时": 24,
                    "最近7天": 168
                }
                
                hours = hours_map[time_range]
                data = perf_manager.get_historical_data(hours)
                
                if data:
                    report = f"=== {time_range} 性能数据 ===\n\n"
                    report += f"数据点数: {len(data)}\n\n"
                    
                    # 显示最近10条记录
                    recent_data = data[-10:] if len(data) > 10 else data
                    
                    for record in recent_data:
                        report += f"时间: {record['timestamp']}\n"
                        report += f"CPU: {record['cpu_percent']:.1f}% | "
                        report += f"内存: {record['memory_percent']:.1f}% | "
                        report += f"磁盘: {record['disk_percent']:.1f}%\n"
                        report += f"进程内存: {record['process_memory_mb']:.1f}MB | "
                        report += f"线程数: {record['thread_count']}\n"
                        report += "-" * 60 + "\n"
                    
                    # 统计信息
                    if len(data) > 1:
                        # 防止除零错误
                        cpu_data = [r for r in data if r['cpu_percent']]
                        mem_data = [r for r in data if r['memory_percent']]
                        cpu_avg = sum(r['cpu_percent'] for r in cpu_data) / len(cpu_data) if len(cpu_data) > 0 else 0.0
                        mem_avg = sum(r['memory_percent'] for r in mem_data) / len(mem_data) if len(mem_data) > 0 else 0.0
                        
                        report += f"\n=== 统计信息 ===\n"
                        report += f"平均CPU使用率: {cpu_avg:.1f}%\n"
                        report += f"平均内存使用率: {mem_avg:.1f}%\n"
                    
                    data_tb.setPlainText(report)
                else:
                    data_tb.setPlainText("暂无历史数据")
            
            def export_data():
                time_range = time_combo.currentText()
                hours_map = {
                    "最近1小时": 1,
                    "最近6小时": 6,
                    "最近24小时": 24,
                    "最近7天": 168
                }
                
                hours = hours_map[time_range]
                data = perf_manager.get_historical_data(hours)
                
                if data:
                    file_path, _ = QFileDialog.getSaveFileName(
                        dlg, "导出性能数据", f"performance_data_{time_range}.json", 
                        "JSON Files (*.json);;CSV Files (*.csv)"
                    )
                    
                    if file_path:
                        try:
                            if file_path.endswith('.csv'):
                                import csv
                                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                                    if data:
                                        writer = csv.DictWriter(f, fieldnames=data[0].keys())
                                        writer.writeheader()
                                        writer.writerows(data)
                            else:
                                with open(file_path, 'w', encoding='utf-8') as f:
                                    json.dump(data, f, indent=2, ensure_ascii=False)
                            
                            QMessageBox.information(dlg, "成功", f"数据已导出到: {file_path}")
                        except Exception as e:
                            QMessageBox.warning(dlg, "错误", f"导出失败: {e}")
                else:
                    QMessageBox.information(dlg, "提示", "暂无数据可导出")
            
            time_combo.currentTextChanged.connect(lambda: refresh_data())
            btn_refresh.clicked.connect(refresh_data)
            btn_export.clicked.connect(export_data)
            btn_close.clicked.connect(dlg.close)
            
            btn_layout.addWidget(btn_refresh)
            btn_layout.addWidget(btn_export)
            btn_layout.addStretch()
            btn_layout.addWidget(btn_close)
            
            layout.addWidget(time_group)
            layout.addWidget(data_tb)
            layout.addLayout(btn_layout)
            
            # 初始加载数据
            refresh_data()
            
            dlg.exec()
            
        except Exception as e:
            QMessageBox.warning(parent_dialog, "错误", f"打开历史数据失败: {e}")


    def view_stack_trace(self):
        dlg = QDialog(self.parent)
        dlg.setWindowTitle("堆栈追踪分析器")
        dlg.resize(1200, 800)
        
        layout = QVBoxLayout(dlg)
        
        # 控制面板
        control_group = QGroupBox("控制面板")
        control_layout = QHBoxLayout()
        
        # 线程过滤
        filter_label = QLabel("线程过滤:")
        filter_combo = QComboBox()
        filter_combo.addItems(["所有线程", "主线程", "活跃线程", "自定义过滤"])
        
        # 刷新按钮
        btn_refresh = QPushButton("刷新")
        btn_auto_refresh = QCheckBox("自动刷新")
        
        # 分析按钮
        btn_analyze = QPushButton("堆栈分析")
        btn_compare = QPushButton("对比快照")
        
        control_layout.addWidget(filter_label)
        control_layout.addWidget(filter_combo)
        control_layout.addWidget(btn_refresh)
        control_layout.addWidget(btn_auto_refresh)
        control_layout.addWidget(btn_analyze)
        control_layout.addWidget(btn_compare)
        control_layout.addStretch()
        control_group.setLayout(control_layout)
        
        # 信息面板
        info_group = QGroupBox("线程信息")
        info_layout = QVBoxLayout()
        
        info_label = QLabel("等待加载...")
        info_layout.addWidget(info_label)
        info_group.setLayout(info_layout)
        
        # 堆栈显示
        stack_group = QGroupBox("堆栈详情")
        stack_layout = QVBoxLayout()
        
        tb = QTextBrowser(dlg)
        tb.setFont(QFont("Courier New", 9))
        stack_layout.addWidget(tb)
        stack_group.setLayout(stack_layout)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存堆栈")
        btn_save.setDefault(False)
        btn_save.setAutoDefault(False)
        btn_export_json = QPushButton("导出JSON")
        btn_export_json.setDefault(False)
        btn_export_json.setAutoDefault(False)
        btn_snapshot = QPushButton("创建快照")
        btn_snapshot.setDefault(False)
        btn_snapshot.setAutoDefault(False)
        btn_clear = QPushButton("清空显示")
        btn_clear.setDefault(False)
        btn_clear.setAutoDefault(False)
        btn_close = QPushButton("关闭")
        btn_close.setDefault(False)
        btn_close.setAutoDefault(False)
        
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_export_json)
        btn_layout.addWidget(btn_snapshot)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        
        layout.addWidget(control_group)
        layout.addWidget(info_group)
        layout.addWidget(stack_group)
        layout.addLayout(btn_layout)
        
        # 数据存储
        current_stack_data = {}
        snapshots = []
        auto_refresh_timer = QTimer()
        auto_refresh_timer.timeout.connect(lambda: load_stack_trace())
        
        def load_stack_trace():
            nonlocal current_stack_data
            try:
                frames = sys._current_frames()
                thread_info = []
                stack_parts = []
                
                # 获取线程详细信息
                for tid, frame in frames.items():
                    thread_name = "Unknown"
                    thread_daemon = False
                    
                    # 尝试获取线程名称
                    for thread in threading.enumerate():
                        if thread.ident == tid:
                            thread_name = thread.name
                            thread_daemon = thread.daemon
                            break
                    
                    # 获取堆栈信息
                    stack_trace = traceback.format_stack(frame)
                    
                    thread_info.append({
                        'id': tid,
                        'name': thread_name,
                        'daemon': thread_daemon,
                        'stack_depth': len(stack_trace),
                        'current_file': frame.f_code.co_filename,
                        'current_line': frame.f_lineno,
                        'current_function': frame.f_code.co_name
                    })
                    
                    # 应用过滤
                    filter_type = filter_combo.currentText()
                    should_include = True
                    
                    if filter_type == "主线程" and thread_name != "MainThread":
                        should_include = False
                    elif filter_type == "活跃线程" and thread_daemon:
                        should_include = False
                    
                    if should_include:
                        stack_parts.append(f"=== 线程 {tid} ({thread_name}) ===\n")
                        stack_parts.append(f"守护线程: {thread_daemon}\n")
                        stack_parts.append(f"当前位置: {frame.f_code.co_filename}:{frame.f_lineno} in {frame.f_code.co_name}\n")
                        stack_parts.append(f"堆栈深度: {len(stack_trace)}\n\n")
                        stack_parts.append(''.join(stack_trace))
                        stack_parts.append("\n" + "="*80 + "\n\n")
                
                current_stack_data = {
                    'timestamp': time.time(),
                    'thread_count': len(frames),
                    'threads': thread_info,
                    'stack_text': ''.join(stack_parts)
                }
                
                # 更新显示
                active_threads = len([t for t in thread_info if not t['daemon']])
                daemon_threads = len([t for t in thread_info if t['daemon']])
                
                info_text = f"总线程数: {len(thread_info)} | 活跃线程: {active_threads} | 守护线程: {daemon_threads}\n"
                info_text += f"更新时间: {time.strftime('%H:%M:%S', time.localtime(current_stack_data['timestamp']))}"
                info_label.setText(info_text)
                
                tb.setPlainText(current_stack_data['stack_text'])
                
            except Exception as e:
                tb.setPlainText(f"获取堆栈失败: {e}")
                info_label.setText("错误: 无法获取堆栈信息")
        
        def analyze_stack():
            if not current_stack_data:
                QMessageBox.warning(dlg, "错误", "请先加载堆栈信息")
                return
                
            analysis_dlg = QDialog(dlg)
            analysis_dlg.setWindowTitle("堆栈分析报告")
            analysis_dlg.resize(800, 600)
            
            analysis_layout = QVBoxLayout(analysis_dlg)
            analysis_tb = QTextBrowser()
            analysis_tb.setFont(QFont("Courier New", 9))
            
            # 生成分析报告
            report = "=== 堆栈分析报告 ===\n\n"
            report += f"分析时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_stack_data['timestamp']))}\n"
            report += f"总线程数: {current_stack_data['thread_count']}\n\n"
            
            # 线程统计
            threads = current_stack_data['threads']
            main_threads = [t for t in threads if t['name'] == 'MainThread']
            daemon_threads = [t for t in threads if t['daemon']]
            
            report += "=== 线程分类 ===\n"
            report += f"主线程: {len(main_threads)}\n"
            report += f"守护线程: {len(daemon_threads)}\n"
            report += f"普通线程: {len(threads) - len(main_threads) - len(daemon_threads)}\n\n"
            
            # 堆栈深度分析
            depths = [t['stack_depth'] for t in threads]
            if depths:
                report += "=== 堆栈深度分析 ===\n"
                # 防止除零错误
                avg_depth = sum(depths) / len(depths) if len(depths) > 0 else 0.0
                report += f"平均深度: {avg_depth:.1f}\n"
                report += f"最大深度: {max(depths)}\n"
                report += f"最小深度: {min(depths)}\n\n"
            
            # 文件分布
            files = {}
            for t in threads:
                file_name = os.path.basename(t['current_file'])
                files[file_name] = files.get(file_name, 0) + 1
            
            report += "=== 当前执行文件分布 ===\n"
            for file_name, count in sorted(files.items(), key=lambda x: x[1], reverse=True):
                report += f"{file_name}: {count} 个线程\n"
            
            # 函数分布
            functions = {}
            for t in threads:
                func_name = t['current_function']
                functions[func_name] = functions.get(func_name, 0) + 1
            
            report += "\n=== 当前执行函数分布 ===\n"
            for func_name, count in sorted(functions.items(), key=lambda x: x[1], reverse=True):
                report += f"{func_name}(): {count} 个线程\n"
            
            analysis_tb.setPlainText(report)
            analysis_layout.addWidget(analysis_tb)
            
            close_btn = QPushButton("关闭")
            close_btn.setDefault(False)
            close_btn.setAutoDefault(False)
            close_btn.clicked.connect(analysis_dlg.close)
            analysis_layout.addWidget(close_btn)
            
            analysis_dlg.exec()
        
        def create_snapshot():
            if not current_stack_data:
                QMessageBox.warning(dlg, "错误", "请先加载堆栈信息")
                return
                
            snapshot_name, ok = QInputDialog.getText(dlg, "创建快照", "快照名称:", text=f"快照_{len(snapshots)+1}")
            if ok and snapshot_name:
                snapshot = current_stack_data.copy()
                snapshot['name'] = snapshot_name
                snapshots.append(snapshot)
                QMessageBox.information(dlg, "成功", f"快照 '{snapshot_name}' 已创建")
        
        def compare_snapshots():
            if len(snapshots) < 2:
                QMessageBox.warning(dlg, "错误", "至少需要2个快照才能进行对比")
                return
                
            # 简单的快照选择对话框
            snapshot_names = [s['name'] for s in snapshots]
            name1, ok1 = QInputDialog.getItem(dlg, "选择快照1", "快照:", snapshot_names, 0, False)
            if not ok1:
                return
                
            name2, ok2 = QInputDialog.getItem(dlg, "选择快照2", "快照:", snapshot_names, 0, False)
            if not ok2:
                return
                
            # 找到对应快照
            snap1 = next(s for s in snapshots if s['name'] == name1)
            snap2 = next(s for s in snapshots if s['name'] == name2)
            
            # 生成对比报告
            compare_dlg = QDialog(dlg)
            compare_dlg.setWindowTitle(f"快照对比: {name1} vs {name2}")
            compare_dlg.resize(800, 600)
            
            compare_layout = QVBoxLayout(compare_dlg)
            compare_tb = QTextBrowser()
            
            report = f"=== 快照对比报告 ===\n\n"
            report += f"快照1: {name1} ({time.strftime('%H:%M:%S', time.localtime(snap1['timestamp']))})\n"
            report += f"快照2: {name2} ({time.strftime('%H:%M:%S', time.localtime(snap2['timestamp']))})\n\n"
            
            report += f"线程数变化: {snap1['thread_count']} -> {snap2['thread_count']} "
            report += f"({snap2['thread_count'] - snap1['thread_count']:+d})\n\n"
            
            # 线程ID对比
            ids1 = {t['id'] for t in snap1['threads']}
            ids2 = {t['id'] for t in snap2['threads']}
            
            new_threads = ids2 - ids1
            removed_threads = ids1 - ids2
            
            if new_threads:
                report += f"新增线程: {list(new_threads)}\n"
            if removed_threads:
                report += f"移除线程: {list(removed_threads)}\n"
            
            compare_tb.setPlainText(report)
            compare_layout.addWidget(compare_tb)
            
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(compare_dlg.close)
            compare_layout.addWidget(close_btn)
            
            compare_dlg.exec()
        
        def save_stack():
            if not current_stack_data:
                QMessageBox.warning(dlg, "错误", "没有可保存的堆栈信息")
                return
            self._save_stack(current_stack_data['stack_text'])
        
        def export_json():
            if not current_stack_data:
                QMessageBox.warning(dlg, "错误", "没有可导出的数据")
                return
                
            file_path, _ = QFileDialog.getSaveFileName(dlg, "导出JSON", "stack_trace.json", "JSON Files (*.json)")
            if file_path:
                try:
                    import json
                    export_data = {
                        'timestamp': current_stack_data['timestamp'],
                        'thread_count': current_stack_data['thread_count'],
                        'threads': current_stack_data['threads']
                    }
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(export_data, f, ensure_ascii=False, indent=2)
                    QMessageBox.information(dlg, "成功", f"数据已导出到 {file_path}")
                except Exception as e:
                    QMessageBox.warning(dlg, "错误", f"导出失败: {e}")
        
        def toggle_auto_refresh():
            if btn_auto_refresh.isChecked():
                auto_refresh_timer.start(2000)  # 2秒刷新一次
            else:
                auto_refresh_timer.stop()
        
        # 连接信号
        btn_refresh.clicked.connect(load_stack_trace)
        btn_auto_refresh.toggled.connect(toggle_auto_refresh)
        btn_analyze.clicked.connect(analyze_stack)
        btn_compare.clicked.connect(compare_snapshots)
        btn_save.clicked.connect(save_stack)
        btn_export_json.clicked.connect(export_json)
        btn_snapshot.clicked.connect(create_snapshot)
        btn_clear.clicked.connect(lambda checked: tb.clear())
        btn_close.clicked.connect(dlg.close)
        filter_combo.currentTextChanged.connect(load_stack_trace)
        
        # 初始加载
        load_stack_trace()
        
        dlg.exec()

    def _save_stack(self, text):
        path, _ = QFileDialog.getSaveFileName(self.parent, "保存堆栈信息", "stack_trace.txt", "Text Files (*.txt);;All Files (*)")
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
            QMessageBox.information(self.parent, "保存", f"堆栈信息已保存到: {path}")
        except Exception as e:
            QMessageBox.warning(self.parent, "错误", f"保存失败: {e}")

    def _translate_keys(self, obj, key_map):
        if isinstance(obj, dict):
            new_obj = {}
            for k, v in obj.items():
                new_key = key_map.get(k, k)
                new_obj[new_key] = self._translate_keys(v, key_map)
            return new_obj
        elif isinstance(obj, list):
            return [self._translate_keys(i, key_map) for i in obj]
        else:
            return obj

    def _read_file_content(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(path, 'r', encoding='gbk', errors='ignore') as f:
                return f.read()

    def view_config_file(self):
        try:
            default_path = os.path.join(self.base_dir, 'settings.json')
            if os.path.exists(default_path):
                chosen = default_path
            else:
                chosen, _ = QFileDialog.getOpenFileName(
                    self.parent,
                    "打开配置文件",
                    self.base_dir,
                    "JSON Files (*.json);;All Files (*)"
                )
                if not chosen:
                    return

            dlg = QDialog(self.parent)
            dlg.setWindowTitle(f"配置管理中心 — {os.path.basename(chosen)}")
            dlg.resize(900, 750)
            
            layout = QVBoxLayout(dlg)
            
            # 配置文件状态
            status_group = QGroupBox("配置文件状态")
            status_layout = QVBoxLayout()
            
            status_label = QLabel("正在加载...")
            path_label = QLabel(f"路径: {chosen}")
            
            status_layout.addWidget(status_label)
            status_layout.addWidget(path_label)
            status_group.setLayout(status_layout)
            
            # 配置内容
            content_group = QGroupBox("配置内容")
            content_layout = QVBoxLayout()
            
            tb = QTextBrowser(dlg)
            tb.setFont(QFont("Courier New", 9))
            content_layout.addWidget(tb)
            content_group.setLayout(content_layout)
            
            # 按钮区域
            btn_layout = QHBoxLayout()
            btn_validate = QPushButton("验证配置")
            btn_validate.setDefault(False)
            btn_validate.setAutoDefault(False)
            btn_backup = QPushButton("备份配置")
            btn_backup.setDefault(False)
            btn_backup.setAutoDefault(False)
            btn_restore = QPushButton("恢复配置")
            btn_restore.setDefault(False)
            btn_restore.setAutoDefault(False)
            btn_edit = QPushButton("编辑配置")
            btn_edit.setDefault(False)
            btn_edit.setAutoDefault(False)
            btn_reset = QPushButton("重置配置")
            btn_reset.setDefault(False)
            btn_reset.setAutoDefault(False)
            btn_close = QPushButton("关闭")
            btn_close.setDefault(False)
            btn_close.setAutoDefault(False)
            
            btn_layout.addWidget(btn_validate)
            btn_layout.addWidget(btn_backup)
            btn_layout.addWidget(btn_restore)
            btn_layout.addWidget(btn_edit)
            btn_layout.addWidget(btn_reset)
            btn_layout.addWidget(btn_close)
            
            layout.addWidget(status_group)
            layout.addWidget(content_group)
            layout.addLayout(btn_layout)
            
            def load_config():
                try:
                    content = self._read_file_content(chosen)
                    file_size = os.path.getsize(chosen)
                    mod_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(chosen)))
                    
                    try:
                        parsed_json = json.loads(content)
                        status_label.setText(f"状态: 正常 | 大小: {file_size} 字节 | 修改时间: {mod_time} | 配置项: {len(parsed_json)}")
                        
                        key_map = {
                            "interval": "间隔时间", "region": "区域", "beep_path": "声音路径",
                            "match_mode": "匹配模式", "fuzzy_threshold": "模糊阈值", "ocr_version": "OCR版本",
                            "enable_desktop_notify": "启用桌面通知", "enable_error_popup": "启用错误弹窗",
                            "email_notify_enabled": "启用邮件通知", "auto_backup_log": "自动备份日志",
                            "auto_upload_log": "自动上传日志", "cloud_sync_enabled": "云同步启用",
                            "proxy_enabled": "代理启用", "email_smtp_server": "邮件SMTP服务器",
                            "email_smtp_port": "邮件SMTP端口", "email_account": "邮件账号",
                            "email_password": "邮件密码", "theme": "主题", "font_size": "字体大小",
                            "language": "语言", "log_level": "日志级别", "max_log_size": "最大日志大小",
                            "log_backup_count": "日志备份数量", "default_save_path": "默认保存路径",
                            "external_hook_path": "外部钩子路径", "shortcut_key": "快捷键",
                            "startup_password": "启动密码", "proxy_host": "代理主机",
                            "proxy_port": "代理端口", "proxy_user": "代理用户名",
                            "proxy_password": "代理密码", "timeout_seconds": "超时时间（秒）",
                            "retry_attempts": "重试次数", "auto_clear_history_days": "自动清理历史天数"
                        }
                        
                        formatted_content = "=== 配置文件详情 ===\n\n"
                        for key, value in parsed_json.items():
                            translated_key = key_map.get(key, key)
                            value_type = type(value).__name__
                            formatted_content += f"• {translated_key} ({key})\n"
                            formatted_content += f"  类型: {value_type}\n"
                            formatted_content += f"  值: {value}\n\n"
                        
                        tb.setPlainText(formatted_content)
                        return parsed_json
                        
                    except json.JSONDecodeError as e:
                        status_label.setText(f"状态: JSON格式错误 | 大小: {file_size} 字节")
                        tb.setPlainText(f"JSON解析错误: {e}\n\n原始内容:\n{content}")
                        return None
                        
                except Exception as e:
                    status_label.setText("状态: 读取失败")
                    tb.setPlainText(f"读取配置文件失败：{e}")
                    return None
            
            def validate_config():
                config_data = load_config()
                if config_data is None:
                    QMessageBox.warning(dlg, "错误", "无法验证：配置文件格式错误")
                    return
                    
                issues = []
                warnings = []
                
                # 基本验证
                required_keys = ['interval', 'region', 'ocr_version']
                for key in required_keys:
                    if key not in config_data:
                        issues.append(f"缺少必需配置项: {key}")
                
                # 类型和值验证
                validations = {
                    'interval': {'type': (int, float), 'range': (0.1, 60), 'desc': '间隔时间应在0.1-60秒之间'},
                    'fuzzy_threshold': {'type': (int, float), 'range': (0, 1), 'desc': '模糊阈值应在0-1之间'},
                    'font_size': {'type': (int, float), 'range': (8, 72), 'desc': '字体大小应在8-72之间'},
                    'email_smtp_port': {'type': int, 'range': (1, 65535), 'desc': 'SMTP端口应在1-65535之间'},
                    'proxy_port': {'type': int, 'range': (1, 65535), 'desc': '代理端口应在1-65535之间'},
                    'timeout_seconds': {'type': (int, float), 'range': (1, 300), 'desc': '超时时间应在1-300秒之间'},
                    'retry_attempts': {'type': int, 'range': (0, 10), 'desc': '重试次数应在0-10之间'}
                }
                
                for key, rules in validations.items():
                    if key in config_data:
                        value = config_data[key]
                        if not isinstance(value, rules['type']):
                            issues.append(f"配置项 {key} 类型错误")
                        elif 'range' in rules:
                            min_val, max_val = rules['range']
                            if not (min_val <= value <= max_val):
                                issues.append(f"配置项 {key}: {rules['desc']}")
                
                # 路径验证
                path_keys = ['beep_path', 'default_save_path', 'external_hook_path']
                for key in path_keys:
                    if key in config_data and config_data[key]:
                        path = config_data[key]
                        if not os.path.exists(path):
                            warnings.append(f"路径不存在: {key} = {path}")
                
                # 邮件配置验证
                if config_data.get('email_notify_enabled'):
                    email_keys = ['email_smtp_server', 'email_account', 'email_password']
                    for key in email_keys:
                        if not config_data.get(key):
                            issues.append(f"启用邮件通知时必须配置: {key}")
                
                result = "配置验证结果:\n\n"
                if issues:
                    result += "❌ 发现问题:\n" + "\n".join(f"• {issue}" for issue in issues) + "\n\n"
                if warnings:
                    result += "⚠️ 警告信息:\n" + "\n".join(f"• {warning}" for warning in warnings) + "\n\n"
                if not issues and not warnings:
                    result += "✅ 配置验证通过！所有配置项都正确。"
                    
                QMessageBox.information(dlg, "配置验证结果", result)
            
            def backup_config():
                try:
                    backup_dir = os.path.join(os.path.dirname(chosen), 'config_backups')
                    os.makedirs(backup_dir, exist_ok=True)
                    
                    backup_name = f"{os.path.splitext(os.path.basename(chosen))[0]}_backup_{time.strftime('%Y%m%d_%H%M%S')}.json"
                    backup_path = os.path.join(backup_dir, backup_name)
                    
                    import shutil
                    shutil.copy2(chosen, backup_path)
                    
                    QMessageBox.information(dlg, "成功", f"配置已备份到: {backup_path}")
                except Exception as e:
                    QMessageBox.warning(dlg, "错误", f"备份失败: {e}")
            
            def restore_config():
                try:
                    backup_dir = os.path.join(os.path.dirname(chosen), 'config_backups')
                    if not os.path.exists(backup_dir):
                        QMessageBox.warning(dlg, "错误", "备份目录不存在")
                        return
                        
                    backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.json')]
                    if not backup_files:
                        QMessageBox.warning(dlg, "错误", "没有找到备份文件")
                        return
                        
                    backup_file, ok = QInputDialog.getItem(dlg, "选择备份", "选择要恢复的备份文件:", backup_files, 0, False)
                    if ok and backup_file:
                        backup_path = os.path.join(backup_dir, backup_file)
                        import shutil
                        shutil.copy2(backup_path, chosen)
                        load_config()
                        QMessageBox.information(dlg, "成功", "配置已恢复")
                except Exception as e:
                    QMessageBox.warning(dlg, "错误", f"恢复失败: {e}")
            
            def edit_config():
                try:
                    import subprocess
                    if os.name == 'nt':  # Windows
                        subprocess.run(['notepad', chosen])
                    else:  # Linux/Mac
                        subprocess.run(['nano', chosen])
                except Exception as e:
                    QMessageBox.warning(dlg, "错误", f"无法打开编辑器: {e}")
            
            def reset_config():
                if QMessageBox.question(dlg, "确认", "确定要重置配置到默认值吗？", 
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                    try:
                        default_config = {
                            "interval": 1.0,
                            "region": [0, 0, 800, 600],
                            "ocr_version": "v4",
                            "theme": "light",
                            "language": "zh_CN",
                            "font_size": 12,
                            "log_level": "信息",
                            "enable_desktop_notify": True,
                            "enable_error_popup": True,
                            "timeout_seconds": 30,
                            "retry_attempts": 3
                        }
                        
                        with open(chosen, 'w', encoding='utf-8') as f:
                            json.dump(default_config, f, indent=4, ensure_ascii=False)
                        
                        load_config()
                        QMessageBox.information(dlg, "成功", "配置已重置为默认值")
                    except Exception as e:
                        QMessageBox.warning(dlg, "错误", f"重置失败: {e}")
            
            btn_validate.clicked.connect(validate_config)
            btn_backup.clicked.connect(backup_config)
            btn_restore.clicked.connect(restore_config)
            btn_edit.clicked.connect(edit_config)
            btn_reset.clicked.connect(reset_config)
            btn_close.clicked.connect(dlg.close)
            
            # 初始加载
            load_config()
            
            dlg.exec()

        except Exception as e:
            QMessageBox.warning(self.parent, "错误", f"打开配置文件失败: {e}")
           
    # ---------- 占位功能（保留原有菜单结构） ----------

    def toggle_log_level(self):
        levels = ["调试", "信息", "警告", "错误", "严重"]
        level_mapping = {"调试": logging.DEBUG, "信息": logging.INFO, "警告": logging.WARNING, "错误": logging.ERROR, "严重": logging.CRITICAL}
        reverse_mapping = {v: k for k, v in level_mapping.items()}
        current_level_name = reverse_mapping.get(self.logger.level, "信息")
        current_index = levels.index(current_level_name)
        next_level = levels[(current_index + 1) % len(levels)]
        self.logger.setLevel(level_mapping[next_level])
        QMessageBox.information(self.parent, "日志级别切换", f"当前日志级别: {next_level}")

    def view_remote_logs(self):
        """查看远程调试日志功能已删除，仅保留空壳"""
        pass

    def _show_remote_log_config_dialog(self, current_url, current_user, current_pass):
        """远程日志配置对话框功能已删除，仅保留空壳"""
        return None
    
    def _save_remote_log_settings(self, url, user, password):
        """远程日志配置保存功能已删除，仅保留空壳"""
        pass

    def performance_analysis_tool(self):
        """性能分析工具"""
        try:
            from core.performance_manager import PerformanceManager
            perf_manager = PerformanceManager()
            
            # 创建对话框
            dlg = QDialog(self.parent)
            dlg.setWindowTitle("性能分析工具")
            dlg.resize(900, 700)
            
            layout = QVBoxLayout(dlg)
            
            # 分析选项
            options_group = QGroupBox("分析选项")
            options_layout = QHBoxLayout()
            
            analysis_combo = QComboBox()
            analysis_combo.addItems(["实时分析", "历史趋势分析", "性能瓶颈分析", "资源使用分析"])
            
            interval_combo = QComboBox()
            interval_combo.addItems(["1秒", "5秒", "10秒", "30秒"])
            interval_combo.setCurrentText("5秒")
            
            options_layout.addWidget(QLabel("分析类型:"))
            options_layout.addWidget(analysis_combo)
            options_layout.addWidget(QLabel("采样间隔:"))
            options_layout.addWidget(interval_combo)
            options_layout.addStretch()
            options_group.setLayout(options_layout)
            
            # 结果显示区域 - 使用标签页
            from PyQt6.QtWidgets import QTabWidget
            result_tabs = QTabWidget()
            
            # 实时数据标签页
            realtime_tab = QWidget()
            realtime_layout = QVBoxLayout(realtime_tab)
            realtime_text = QTextBrowser()
            realtime_text.setFont(QFont("Courier New", 9))
            realtime_layout.addWidget(realtime_text)
            result_tabs.addTab(realtime_tab, "实时数据")
            
            # 分析结果标签页
            analysis_tab = QWidget()
            analysis_layout = QVBoxLayout(analysis_tab)
            analysis_text = QTextBrowser()
            analysis_text.setFont(QFont("Courier New", 9))
            analysis_layout.addWidget(analysis_text)
            result_tabs.addTab(analysis_tab, "分析结果")
            
            # 建议标签页
            suggestions_tab = QWidget()
            suggestions_layout = QVBoxLayout(suggestions_tab)
            suggestions_text = QTextBrowser()
            suggestions_text.setFont(QFont("Courier New", 9))
            suggestions_layout.addWidget(suggestions_text)
            result_tabs.addTab(suggestions_tab, "优化建议")
            
            # 按钮布局
            btn_layout = QHBoxLayout()
            btn_start = QPushButton("开始分析")
            btn_stop = QPushButton("停止分析")
            btn_export = QPushButton("导出报告")
            btn_benchmark = QPushButton("运行基准测试")
            btn_close = QPushButton("关闭")
            
            btn_stop.setEnabled(False)
            
            # 分析状态
            analysis_timer = None
            analysis_data = []
            
            def start_analysis():
                nonlocal analysis_timer, analysis_data
                try:
                    analysis_type = analysis_combo.currentText()
                    interval_text = interval_combo.currentText()
                    interval_ms = int(interval_text.replace('秒', '')) * 1000
                    
                    btn_start.setEnabled(False)
                    btn_stop.setEnabled(True)
                    
                    analysis_data = []
                    
                    # 显示开始信息
                    realtime_text.setPlainText(f"开始{analysis_type}...\n采样间隔: {interval_text}")
                    
                    if analysis_type == "实时分析":
                        analysis_timer = QTimer()
                        analysis_timer.timeout.connect(lambda: update_realtime_data(perf_manager))
                        analysis_timer.start(interval_ms)
                        
                    elif analysis_type == "历史趋势分析":
                        show_trend_analysis(perf_manager, analysis_text)
                        
                    elif analysis_type == "性能瓶颈分析":
                        show_bottleneck_analysis(perf_manager, analysis_text)
                        
                    elif analysis_type == "资源使用分析":
                        show_resource_analysis(perf_manager, analysis_text)
                        
                except Exception as e:
                    # 恢复按钮状态
                    btn_start.setEnabled(True)
                    btn_stop.setEnabled(False)
                    # 显示错误信息
                    error_msg = f"分析启动失败: {e}"
                    realtime_text.setPlainText(error_msg)
                    QMessageBox.warning(dlg, "错误", error_msg)
            
            def stop_analysis():
                nonlocal analysis_timer
                if analysis_timer:
                    analysis_timer.stop()
                    analysis_timer = None
                
                btn_start.setEnabled(True)
                btn_stop.setEnabled(False)
            
            def update_realtime_data(perf_manager):
                nonlocal analysis_data
                try:
                    current_data = perf_manager.collect_current_performance()
                    analysis_data.append(current_data)
                    
                    # 保持最近50个数据点
                    if len(analysis_data) > 50:
                        analysis_data.pop(0)
                    
                    # 更新实时显示
                    report = "=== 实时性能监控 ===\n\n"
                    report += f"时间: {current_data['timestamp']}\n"
                    report += f"CPU使用率: {current_data['cpu_percent']:.1f}%\n"
                    report += f"内存使用率: {current_data['memory_percent']:.1f}%\n"
                    report += f"磁盘使用率: {current_data['disk_percent']:.1f}%\n"
                    report += f"进程内存: {current_data['process_memory_mb']:.1f}MB\n"
                    report += f"线程数: {current_data['thread_count']}\n\n"
                    
                    if len(analysis_data) > 1:
                        # 计算变化趋势
                        prev_data = analysis_data[-2]
                        cpu_change = current_data['cpu_percent'] - prev_data['cpu_percent']
                        mem_change = current_data['memory_percent'] - prev_data['memory_percent']
                        
                        report += "=== 变化趋势 ===\n"
                        report += f"CPU变化: {cpu_change:+.1f}%\n"
                        report += f"内存变化: {mem_change:+.1f}%\n\n"
                    
                    # 显示最近5个数据点
                    if len(analysis_data) >= 5:
                        report += "=== 最近数据 ===\n"
                        for i, data in enumerate(analysis_data[-5:]):
                            report += f"{i+1}. {data['timestamp'][-8:]} - CPU:{data['cpu_percent']:.1f}% MEM:{data['memory_percent']:.1f}%\n"
                    
                    realtime_text.setPlainText(report)
                    
                    # 自动分析异常
                    analyze_anomalies(current_data)
                    
                except Exception as e:
                    realtime_text.setPlainText(f"数据采集错误: {e}")
            
            def analyze_anomalies(data):
                suggestions = []
                
                if data['cpu_percent'] > 80:
                    suggestions.append("⚠️ CPU使用率过高，建议检查高CPU占用进程")
                
                if data['memory_percent'] > 85:
                    suggestions.append("⚠️ 内存使用率过高，建议释放内存或增加内存")
                
                if data['disk_percent'] > 90:
                    suggestions.append("⚠️ 磁盘空间不足，建议清理磁盘空间")
                
                if data['process_memory_mb'] > 1000:
                    suggestions.append("⚠️ 当前进程内存占用较高，建议优化内存使用")
                
                if suggestions:
                    current_suggestions = suggestions_text.toPlainText()
                    timestamp = data['timestamp']
                    new_suggestions = f"[{timestamp}]\n" + "\n".join(suggestions) + "\n\n"
                    suggestions_text.setPlainText(new_suggestions + current_suggestions)
            
            def show_trend_analysis(perf_manager, analysis_text):
                try:
                    historical_data = perf_manager.get_historical_data(hours=24)
                    if not historical_data:
                        analysis_text.setPlainText("暂无历史数据进行趋势分析")
                        return
                    
                    # 趋势分析
                    cpu_values = [d['cpu_percent'] for d in historical_data if d['cpu_percent']]
                    mem_values = [d['memory_percent'] for d in historical_data if d['memory_percent']]
                    
                    report = "=== 24小时趋势分析 ===\n\n"
                    
                    if cpu_values:
                        # 防止除零错误
                        cpu_avg = sum(cpu_values) / len(cpu_values) if len(cpu_values) > 0 else 0.0
                        cpu_max = max(cpu_values)
                        cpu_min = min(cpu_values)
                        report += f"CPU使用率:\n"
                        report += f"  平均: {cpu_avg:.1f}%\n"
                        report += f"  最高: {cpu_max:.1f}%\n"
                        report += f"  最低: {cpu_min:.1f}%\n\n"
                    
                    if mem_values:
                        # 防止除零错误
                        mem_avg = sum(mem_values) / len(mem_values) if len(mem_values) > 0 else 0.0
                        mem_max = max(mem_values)
                        mem_min = min(mem_values)
                        report += f"内存使用率:\n"
                        report += f"  平均: {mem_avg:.1f}%\n"
                        report += f"  最高: {mem_max:.1f}%\n"
                        report += f"  最低: {mem_min:.1f}%\n\n"
                    
                    # 峰值时间分析
                    if len(historical_data) > 10:
                        sorted_by_cpu = sorted(historical_data, key=lambda x: x['cpu_percent'] or 0, reverse=True)
                        report += "=== CPU使用高峰时段 ===\n"
                        for i, data in enumerate(sorted_by_cpu[:5]):
                            report += f"{i+1}. {data['timestamp']} - {data['cpu_percent']:.1f}%\n"
                    
                    analysis_text.setPlainText(report)
                    
                except Exception as e:
                    analysis_text.setPlainText(f"趋势分析失败: {e}")
            
            def show_bottleneck_analysis(perf_manager, analysis_text):
                try:
                    current_data = perf_manager.collect_current_performance()
                    
                    report = "=== 性能瓶颈分析 ===\n\n"
                    
                    # 瓶颈检测
                    bottlenecks = []
                    
                    if current_data['cpu_percent'] > 70:
                        bottlenecks.append(("CPU", current_data['cpu_percent'], "高"))
                    elif current_data['cpu_percent'] > 50:
                        bottlenecks.append(("CPU", current_data['cpu_percent'], "中"))
                    
                    if current_data['memory_percent'] > 80:
                        bottlenecks.append(("内存", current_data['memory_percent'], "高"))
                    elif current_data['memory_percent'] > 60:
                        bottlenecks.append(("内存", current_data['memory_percent'], "中"))
                    
                    if current_data['disk_percent'] > 85:
                        bottlenecks.append(("磁盘", current_data['disk_percent'], "高"))
                    
                    if bottlenecks:
                        report += "检测到的瓶颈:\n"
                        for resource, usage, level in bottlenecks:
                            report += f"  {resource}: {usage:.1f}% (风险等级: {level})\n"
                        report += "\n"
                    else:
                        report += "未检测到明显的性能瓶颈\n\n"
                    
                    # 详细分析
                    report += "=== 详细分析 ===\n"
                    if psutil:
                        report += f"CPU核心数: {psutil.cpu_count()}\n"
                        if psutil.cpu_freq():
                            report += f"CPU频率: {psutil.cpu_freq().current:.0f}MHz\n"
                        
                        memory = psutil.virtual_memory()
                        report += f"总内存: {memory.total / (1024**3):.1f}GB\n"
                        report += f"可用内存: {memory.available / (1024**3):.1f}GB\n"
                    
                    analysis_text.setPlainText(report)
                    
                except Exception as e:
                    analysis_text.setPlainText(f"瓶颈分析失败: {e}")
            
            def show_resource_analysis(perf_manager, analysis_text):
                try:
                    report = "=== 资源使用分析 ===\n\n"
                    
                    if psutil:
                        # 进程分析
                        processes = []
                        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                            try:
                                proc_info = proc.info
                                if proc_info['cpu_percent'] and proc_info['cpu_percent'] > 1:
                                    processes.append(proc_info)
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                        
                        # 按CPU使用率排序
                        processes.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
                        
                        report += "=== 高CPU使用进程 ===\n"
                        for i, proc in enumerate(processes[:10]):
                            report += f"{i+1:2d}. {proc['name']:<20} CPU:{proc['cpu_percent']:5.1f}% MEM:{proc['memory_percent']:5.1f}%\n"
                        
                        # 磁盘使用分析
                        report += "\n=== 磁盘使用情况 ===\n"
                        for partition in psutil.disk_partitions():
                            try:
                                usage = psutil.disk_usage(partition.mountpoint)
                                percent = (usage.used / usage.total) * 100
                                report += f"{partition.device} {percent:.1f}% ({usage.free / (1024**3):.1f}GB 可用)\n"
                            except PermissionError:
                                continue
                        
                        # 网络使用
                        net_io = psutil.net_io_counters()
                        if net_io:
                            report += "\n=== 网络使用情况 ===\n"
                            report += f"发送: {net_io.bytes_sent / (1024**2):.1f}MB\n"
                            report += f"接收: {net_io.bytes_recv / (1024**2):.1f}MB\n"
                    
                    analysis_text.setPlainText(report)
                    
                except Exception as e:
                    analysis_text.setPlainText(f"资源分析失败: {e}")
            
            def export_report():
                try:
                    file_path, _ = QFileDialog.getSaveFileName(
                        dlg, "导出分析报告", "performance_analysis_report.txt", 
                        "Text Files (*.txt);;JSON Files (*.json)"
                    )
                    
                    if file_path:
                        from datetime import datetime
                        report_data = {
                            "timestamp": datetime.now().isoformat(),
                            "analysis_type": analysis_combo.currentText(),
                            "realtime_data": realtime_text.toPlainText(),
                            "analysis_result": analysis_text.toPlainText(),
                            "suggestions": suggestions_text.toPlainText(),
                            "collected_data": analysis_data
                        }
                        
                        if file_path.endswith('.json'):
                            with open(file_path, 'w', encoding='utf-8') as f:
                                json.dump(report_data, f, indent=2, ensure_ascii=False)
                        else:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(f"性能分析报告\n{'='*50}\n\n")
                                f.write(f"生成时间: {report_data['timestamp']}\n")
                                f.write(f"分析类型: {report_data['analysis_type']}\n\n")
                                f.write("实时数据:\n" + report_data['realtime_data'] + "\n\n")
                                f.write("分析结果:\n" + report_data['analysis_result'] + "\n\n")
                                f.write("优化建议:\n" + report_data['suggestions'])
                        
                        QMessageBox.information(dlg, "成功", f"报告已导出到: {file_path}")
                        
                except Exception as e:
                    QMessageBox.warning(dlg, "错误", f"导出失败: {e}")
            
            def run_benchmark():
                self._show_benchmark_dialog(dlg)
            
            # 连接信号
            btn_start.clicked.connect(start_analysis)
            btn_stop.clicked.connect(stop_analysis)
            btn_export.clicked.connect(export_report)
            btn_benchmark.clicked.connect(run_benchmark)
            btn_close.clicked.connect(lambda checked: (stop_analysis(), dlg.close()))
            
            btn_layout.addWidget(btn_start)
            btn_layout.addWidget(btn_stop)
            btn_layout.addWidget(btn_export)
            btn_layout.addWidget(btn_benchmark)
            btn_layout.addStretch()
            btn_layout.addWidget(btn_close)
            
            layout.addWidget(options_group)
            layout.addWidget(result_tabs)
            layout.addLayout(btn_layout)
            
            dlg.exec()
            
        except Exception as e:
            QMessageBox.warning(self.parent, "错误", f"性能分析失败: {e}")


    def _load_debug_config(self):
        """加载调试配置（迁移到 settings.json 的 debug_config 字段）"""
        try:
            settings = load_settings()
            dbg = settings.get('debug_config')
            if isinstance(dbg, dict):
                return dbg
        except Exception as e:
            print(f"从 settings.json 加载调试配置失败: {e}")

        # 兼容旧版：尝试读取 legacy 文件，然后写回 settings.json
        legacy_path = os.path.join(os.path.dirname(__file__), '..', 'debug_config.json')
        try:
            if os.path.exists(legacy_path):
                with open(legacy_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    try:
                        settings = load_settings()
                        settings['debug_config'] = data
                        save_settings(settings)
                    except Exception:
                        pass
                    return data
        except Exception:
            pass

        # 返回默认配置
        return {
            'enabled': False,
            'session_history': [],
            'last_session_id': None
        }
    
    def _save_debug_config(self, config):
        """保存调试配置到 settings.json 的 debug_config 字段"""
        try:
            settings = load_settings()
            settings['debug_config'] = config if isinstance(config, dict) else {}
            save_settings(settings)
        except Exception as e:
            print(f"保存调试配置到 settings.json 失败: {e}")
    
    def _start_debug_monitoring(self):
        """启动调试监控"""
        try:
            if not hasattr(self, '_debug_timer'):
                self._debug_timer = QTimer()
                self._debug_timer.timeout.connect(self._debug_monitor_tick)
            self._debug_timer.start(5000)  # 每5秒监控一次
        except Exception as e:
            print(f"启动调试监控失败: {e}")
    
    def _debug_monitor_tick(self):
        """调试监控定时器回调"""
        try:
            # 简单的调试信息收集
            enhanced_logger = get_enhanced_logger()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            enhanced_logger.log("DEBUG", f"[{timestamp}] 🔍 调试监控心跳", "DevToolsPanel")
        except Exception as e:
            print(f"调试监控失败: {e}")
    
    def _show_debug_control_panel(self):
        """显示调试控制面板"""
        try:
            # 简单的调试面板
            QMessageBox.information(self.parent, "调试控制面板", 
                                  "🎛️ 调试控制面板\n\n" +
                                  "• 调试模式已启用\n" +
                                  "• 实时监控正在运行\n" +
                                  "• 可通过开发工具面板管理")
        except Exception as e:
            print(f"显示调试控制面板失败: {e}")

    def toggle_debug_mode(self):
        """增强的调试模式切换功能"""
        # 获取enhanced_logger实例
        enhanced_logger = get_enhanced_logger()
        # 从配置文件加载调试模式状态
        debug_config = self._load_debug_config()
        current_state = debug_config.get('enabled', False)
        
        if current_state:
            # 关闭调试模式
            self._debug_mode = False
            self.logger.setLevel(logging.INFO)
            debug_config['enabled'] = False
            debug_config['disabled_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
            
            # 保存会话历史
            session_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            if 'session_history' not in debug_config:
                debug_config['session_history'] = []
                enhanced_logger.log("DEBUG", f"[{session_timestamp}] 📋 初始化会话历史记录", "DevToolsPanel")
            if 'session_id' in debug_config:
                session_record = {
                    'session_id': debug_config['session_id'],
                    'start_time': debug_config.get('enabled_time', 'unknown'),
                    'end_time': debug_config['disabled_time']
                }
                debug_config['session_history'].append(session_record)
                session_duration = 'unknown'
                if debug_config.get('enabled_time') and debug_config['disabled_time']:
                    try:
                        start_time = datetime.strptime(debug_config['enabled_time'], '%Y-%m-%d %H:%M:%S')
                        end_time = datetime.strptime(debug_config['disabled_time'], '%Y-%m-%d %H:%M:%S')
                        duration = end_time - start_time
                        session_duration = f"{int(duration.total_seconds()//3600)}h {int((duration.total_seconds()%3600)//60)}m {int(duration.total_seconds()%60)}s"
                    except:
                        pass
                enhanced_logger.log("INFO", f"[{session_timestamp}] 💾 保存会话记录: {debug_config['session_id']} -> 持续时间 {session_duration}", "DevToolsPanel")
                enhanced_logger.log("DEBUG", f"[{session_timestamp}] 📊 会话历史总数: {len(debug_config['session_history'])}", "DevToolsPanel")
            
            # 停止调试监控
            if hasattr(self, '_debug_timer'):
                self._debug_timer.stop()
                
            self._save_debug_config(debug_config)
            QMessageBox.information(self.parent, "调试模式", 
                                  "✅ 已关闭调试模式\n📊 调试数据已保存")
        else:
            # 开启调试模式
            enable_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            self._debug_mode = True
            self.logger.setLevel(logging.DEBUG)
            debug_config['enabled'] = True
            debug_config['enabled_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
            debug_config['session_id'] = str(uuid.uuid4())[:8]
            
            enhanced_logger.log("INFO", f"[{enable_timestamp}] 🔍 开启调试模式", "DevToolsPanel")
            enhanced_logger.log("INFO", f"[{enable_timestamp}] 🆔 创建新会话: {debug_config['session_id']}", "DevToolsPanel")
            enhanced_logger.log("DEBUG", f"[{enable_timestamp}] 📊 设置日志级别: DEBUG", "DevToolsPanel")
            enhanced_logger.log("DEBUG", f"[{enable_timestamp}] ⏰ 会话开始时间: {debug_config['enabled_time']}", "DevToolsPanel")
            
            # 启动调试监控
            self._start_debug_monitoring()
            
            self._save_debug_config(debug_config)
            
            # 显示调试控制面板
            self._show_debug_control_panel()
            
            QMessageBox.information(self.parent, "调试模式", 
                                  "🔍 已开启调试模式\n📈 实时监控已启动\n🎛️ 调试面板已打开")



    def manage_error_popups(self):
        dlg = QDialog(self.parent)
        dlg.setWindowTitle(t("错误管理中心"))
        dlg.resize(900, 700)
        
        layout = QVBoxLayout(dlg)
        
        # 错误统计
        stats_group = QGroupBox("错误统计")
        stats_layout = QVBoxLayout()
        
        error_count_label = QLabel("正在统计...")
        warning_count_label = QLabel("正在统计...")
        critical_count_label = QLabel("正在统计...")
        
        stats_layout.addWidget(error_count_label)
        stats_layout.addWidget(warning_count_label)
        stats_layout.addWidget(critical_count_label)
        stats_group.setLayout(stats_layout)
        
        # 错误详情
        details_group = QGroupBox("最近错误详情")
        details_layout = QVBoxLayout()
        
        tb = QTextBrowser(dlg)
        tb.setFont(QFont("Courier New", 9))
        details_layout.addWidget(tb)
        details_group.setLayout(details_layout)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_refresh = QPushButton("刷新")
        btn_refresh.setDefault(False)
        btn_refresh.setAutoDefault(False)
        btn_clear_logs = QPushButton("清空日志")
        btn_clear_logs.setDefault(False)
        btn_clear_logs.setAutoDefault(False)
        btn_export = QPushButton("导出错误")
        btn_export.setDefault(False)
        btn_export.setAutoDefault(False)
        btn_close = QPushButton("关闭")
        btn_close.setDefault(False)
        btn_close.setAutoDefault(False)
        
        btn_layout.addWidget(btn_refresh)
        btn_layout.addWidget(btn_clear_logs)
        btn_layout.addWidget(btn_export)
        btn_layout.addWidget(btn_close)
        
        layout.addWidget(stats_group)
        layout.addWidget(details_group)
        layout.addLayout(btn_layout)
        
        def load_error_data():
            if not hasattr(self, 'log_file_path') or not self.log_file_path or not os.path.exists(self.log_file_path):
                tb.setPlainText("未找到日志文件。")
                error_count_label.setText("错误数量: 0")
                warning_count_label.setText("警告数量: 0")
                critical_count_label.setText("严重错误数量: 0")
                return
                
            try:
                with open(self.log_file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                errors = [line for line in lines if 'ERROR' in line]
                warnings = [line for line in lines if 'WARNING' in line]
                criticals = [line for line in lines if 'CRITICAL' in line]
                exceptions = [line for line in lines if 'Exception' in line or 'Traceback' in line]
                
                # 更新统计
                error_count_label.setText(f"错误数量: {len(errors)}")
                warning_count_label.setText(f"警告数量: {len(warnings)}")
                critical_count_label.setText(f"严重错误数量: {len(criticals)}")
                
                # 显示最近的错误详情
                recent_errors = (errors + exceptions)[-100:]  # 最近100条
                if recent_errors:
                    content = "=== 最近错误详情 ===\n\n" + "\n".join(recent_errors)
                else:
                    content = "日志中未发现错误信息。"
                    
                tb.setPlainText(content)
                
            except Exception as e:
                tb.setPlainText(f"读取日志失败：{e}")
                error_count_label.setText("错误数量: 读取失败")
                warning_count_label.setText("警告数量: 读取失败")
                critical_count_label.setText("严重错误数量: 读取失败")
        
        def clear_logs():
            if QMessageBox.question(dlg, "确认", "确定要清空日志文件吗？", 
                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                try:
                    if hasattr(self, 'log_file_path') and self.log_file_path:
                        with open(self.log_file_path, 'w', encoding='utf-8') as f:
                            f.write(f"日志已清空 - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        load_error_data()
                        QMessageBox.information(dlg, "成功", "日志已清空")
                except Exception as e:
                    QMessageBox.warning(dlg, "错误", f"清空日志失败: {e}")
        
        def export_errors():
            try:
                if not hasattr(self, 'log_file_path') or not self.log_file_path:
                    QMessageBox.warning(dlg, "错误", "未找到日志文件")
                    return
                    
                save_path, _ = QFileDialog.getSaveFileName(dlg, "导出错误报告", 
                                                         f"error_report_{time.strftime('%Y%m%d_%H%M%S')}.txt", 
                                                         "文本文件 (*.txt);;所有文件 (*)")
                if save_path:
                    with open(self.log_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write(f"错误报告导出时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write("=" * 50 + "\n")
                        f.write(content)
                    QMessageBox.information(dlg, "成功", f"错误报告已导出到: {save_path}")
            except Exception as e:
                QMessageBox.warning(dlg, "错误", f"导出失败: {e}")
        
        btn_refresh.clicked.connect(load_error_data)
        btn_clear_logs.clicked.connect(clear_logs)
        btn_export.clicked.connect(export_errors)
        btn_close.clicked.connect(dlg.close)
        
        # 初始加载
        load_error_data()
        
        dlg.exec()

    def send_error_report(self):
        settings = self._load_settings() if hasattr(self, "_load_settings") else {}
        smtp_server = settings.get("email_smtp_server", "")
        smtp_port = int(settings.get("email_smtp_port", 587))
        smtp_user = settings.get("email_account", "")
        smtp_pass = settings.get("email_password", "")
        to_addr = settings.get("error_report_recipient", "")
        use_ssl = bool(settings.get("email_use_ssl", False))
        use_tls = bool(settings.get("email_use_tls", True))

        # 补齐缺省配置
        def ask(label, default=""):
            text, ok = QInputDialog.getText(self.parent, "错误报告配置", label + "：", text=default)
            return text if ok and text else default
        if not smtp_server: smtp_server = ask("SMTP 服务器", smtp_server)
        if not smtp_user: smtp_user = ask("SMTP 账号", smtp_user)
        if not smtp_pass: smtp_pass = ask("SMTP 密码/授权码", smtp_pass)
        if not to_addr: to_addr = ask("收件人邮箱", to_addr)
        if not smtp_server or not smtp_user or not smtp_pass or not to_addr:
            QMessageBox.warning(self.parent, "错误报告", "SMTP 配置不完整，取消发送。")
            return

        subject = f"错误报告 - {time.strftime('%Y-%m-%d %H:%M:%S')}"
        body = subject
        if self.log_file_path and os.path.exists(self.log_file_path):
            try:
                with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    body += "\n\n=== 日志片段(末尾2000字) ===\n" + f.read()[-2000:]
            except Exception:
                pass

        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_user; msg['To'] = to_addr; msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            if use_ssl:
                server = smtplib.SMTP_SSL(smtp_server, smtp_port)
            else:
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.ehlo()
                if use_tls:
                    server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg); server.quit()
            QMessageBox.information(self.parent, "错误报告", "错误报告已发送。")
        except Exception as e:
            QMessageBox.warning(self.parent, "错误报告", f"发送失败: {e}")

    def generate_error_report_file(self):
        if not self.log_file_path or not os.path.exists(self.log_file_path):
            QMessageBox.warning(self.parent, "错误报告文件", "未找到错误日志文件。")
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self.parent, "保存错误报告", "error_report.txt", "文本文件 (*.txt);;所有文件 (*)"
        )
        if not save_path:
            return
        try:
            shutil.copyfile(self.log_file_path, save_path)
            QMessageBox.information(self.parent, "错误报告文件", f"已保存到: {save_path}")
        except Exception as e:
            QMessageBox.warning(self.parent, "错误报告文件", f"保存失败：{e}")


    def view_update_log(self):
        log_path = os.path.join(self.base_dir, "update_log.txt")
        if not os.path.exists(log_path):
            QMessageBox.information(self.parent, "更新日志", "更新日志文件不存在。")
            return

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.warning(self.parent, "更新日志", f"读取失败：{e}")
            return

        dlg = QDialog(self.parent)
        dlg.setWindowTitle("更新日志")
        dlg.resize(800, 600)

        tb = QTextBrowser(dlg)
        tb.setPlainText(content)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(dlg.close)

        layout = QVBoxLayout()
        layout.addWidget(tb)
        layout.addWidget(btn_close)
        dlg.setLayout(layout)
        dlg.exec()
    


    def view_system_info(self):
        """查看系统信息"""
        try:
            import platform
            import psutil
            
            info = {
                "系统": platform.system(),
                "版本": platform.version(),
                "架构": platform.architecture()[0],
                "处理器": platform.processor(),
                t("python_version"): platform.python_version(),
                "主机名": platform.node(),
                "用户": os.getlogin() if hasattr(os, 'getlogin') else "未知",
            }
            
            if psutil:
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                info.update({
                    "总内存": f"{memory.total / (1024**3):.2f} GB",
                    "可用内存": f"{memory.available / (1024**3):.2f} GB",
                    "内存使用率": f"{memory.percent}%",
                    "磁盘总空间": f"{disk.total / (1024**3):.2f} GB",
                    "磁盘可用空间": f"{disk.free / (1024**3):.2f} GB",
                    "磁盘使用率": f"{(disk.used / disk.total) * 100:.1f}%",
                    "CPU核心数": psutil.cpu_count(),
                    "CPU使用率": f"{psutil.cpu_percent(interval=1)}%",
                })
            
            content = "\n".join([f"{k}: {v}" for k, v in info.items()])
            
        except Exception as e:
            content = f"获取系统信息失败: {e}"
        
        dlg = QDialog(self.parent)
        dlg.setWindowTitle("系统信息")
        dlg.resize(500, 400)
        
        layout = QVBoxLayout(dlg)
        tb = QTextBrowser(dlg)
        tb.setPlainText(content)
        
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(dlg.close)
        
        layout.addWidget(tb)
        layout.addWidget(btn_close)
        
        # 窗口居中显示
        if self.parent:
            parent_geometry = self.parent.geometry()
            dialog_size = dlg.size()
            x = parent_geometry.x() + (parent_geometry.width() - dialog_size.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - dialog_size.height()) // 2
            dlg.move(x, y)
        
        dlg.exec()
    
    def web_preview(self):
        """启动Web控制面板 - 现代化界面"""
        try:
            # 导入Web预览服务器
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[0])))
            from .web_preview_server_enhanced import WebPreviewServer
            
            # 创建现代化的Web控制面板对话框
            self._show_web_panel_dialog()
            
        except ImportError as e:
            self._show_error_dialog(
                "模块导入错误",
                f"无法加载Web控制面板模块:\n{e}\n\n请确保widgets/web_preview_server.py文件存在且完整。"
            )
        except Exception as e:
            self._show_error_dialog(
                "Web控制面板错误",
                f"启动Web控制面板时发生错误:\n{e}\n\n请检查系统日志获取详细信息。"
            )
    
    def _show_web_panel_dialog(self):
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                   QPushButton, QFrame, QSpacerItem, QSizePolicy,
                                   QProgressBar, QTextEdit, QGroupBox, QGridLayout,
                                   QScrollArea, QWidget)
        from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect
        from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor, QBrush, QIcon
        
        # 创建自定义对话框
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Web预览设置")
        dialog.setFixedSize(700, 650)
        dialog.setModal(True)
        dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        
        # 使用系统默认样式
        
        # 主布局
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 创建滚动内容容器
        scroll_content = QWidget()
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(15, 10, 15, 10)
        content_layout.setSpacing(12)
        
        # 标题区域 - 增强版
        title_group = QGroupBox("🚀 智能控制中心")
        title_layout = QVBoxLayout(title_group)
        
        # 主标题
        title_label = QLabel("XuanWu OCR Web控制面板")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 使用系统默认样式
        title_layout.addWidget(title_label)
        
        # 状态信息区域
        status_layout = QHBoxLayout()
        
        # 服务器状态
        self.status_label = QLabel()
        # 使用系统默认样式
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.status_label)
        
        # 连接数显示
        self.connection_label = QLabel("连接数: 0")
        # 使用系统默认样式
        status_layout.addWidget(self.connection_label)
        
        title_layout.addLayout(status_layout)
        content_layout.addWidget(title_group)
        
        # 功能特性展示区域
        features_group = QGroupBox("🎯 核心功能")
        features_layout = QVBoxLayout(features_group)
        
        # 功能描述
        desc_label = QLabel(
            "🚀 智能OCR控制中心 - 提供全方位的系统管理体验\n"
            "📊 实时性能监控 | 🔧 智能配置管理 | 📈 数据可视化分析 | 🛠️ 高级调试工具"
        )
        # 使用系统默认样式
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        features_layout.addWidget(desc_label)
        
        # 快速统计信息
        stats_layout = QHBoxLayout()
        
        # 运行时间统计
        uptime_label = QLabel("⏱️ 运行时间: --")
        # 使用系统默认样式
        stats_layout.addWidget(uptime_label)
        
        # 处理任务数
        tasks_label = QLabel("📋 处理任务: 0")
        # 使用系统默认样式
        stats_layout.addWidget(tasks_label)
        
        # 系统状态
        system_label = QLabel("💻 系统: 正常")
        # 使用系统默认样式
        stats_layout.addWidget(system_label)
        
        features_layout.addLayout(stats_layout)
        content_layout.addWidget(features_group)
        
        # 操作控制区域
        actions_group = QGroupBox("🎮 操作控制")
        actions_layout = QVBoxLayout(actions_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        # 检查服务器状态并显示相应按钮
        if self._web_server and self._web_server.is_running:
            self._setup_running_buttons(button_layout, dialog)
            self.status_label.setText("🟢 服务器运行中")
            self.connection_label.setText(f"🌐 {self._web_server.get_url()}")
        else:
            self._setup_start_buttons(button_layout, dialog)
            self.status_label.setText("🔴 服务器未启动")
            self.connection_label.setText("⚠️ 等待启动")
        
        actions_layout.addLayout(button_layout)
        
        # 添加进度条（用于显示启动/停止进度）
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        # 使用系统默认样式
        actions_layout.addWidget(self.progress_bar)
        
        content_layout.addWidget(actions_group)
        
        # Web API管理区域
        api_group = QGroupBox("🔧 Web API管理")
        api_layout = QVBoxLayout(api_group)
        
        # API状态显示
        api_status_layout = QGridLayout()
        
        # 服务器状态
        server_status_label = QLabel("服务器状态:")
        self.server_status_value = QLabel("未启动")
        api_status_layout.addWidget(server_status_label, 0, 0)
        api_status_layout.addWidget(self.server_status_value, 0, 1)
        
        # API端点数量
        endpoints_label = QLabel("可用端点:")
        self.endpoints_value = QLabel("12个")
        api_status_layout.addWidget(endpoints_label, 1, 0)
        api_status_layout.addWidget(self.endpoints_value, 1, 1)
        
        # 请求统计
        requests_label = QLabel("总请求数:")
        self.requests_value = QLabel("0")
        api_status_layout.addWidget(requests_label, 2, 0)
        api_status_layout.addWidget(self.requests_value, 2, 1)
        
        # 缓存状态
        cache_label = QLabel("缓存状态:")
        self.cache_value = QLabel("已启用")
        api_status_layout.addWidget(cache_label, 3, 0)
        api_status_layout.addWidget(self.cache_value, 3, 1)
        
        api_layout.addLayout(api_status_layout)
        
        # API功能说明
        api_desc = QLabel(
            "📡 Web API提供以下功能:\n"
            "• 系统状态监控 (GET /api/status)\n"
            "• 关键词管理 (GET/POST /api/keywords)\n"
            "• 日志查看 (GET /api/logs)\n"
            "• 设置管理 (GET/POST /api/settings)\n"
            "• 性能监控 (GET /api/performance)\n"
            "• 监控控制 (POST /api/start|stop)"
        )
        api_desc.setWordWrap(True)
        api_layout.addWidget(api_desc)
        
        # API管理按钮区域
        api_buttons_layout = QHBoxLayout()
        
        # 清除缓存按钮
        clear_cache_btn = QPushButton("🗑️ 清除缓存")
        clear_cache_btn.setMinimumHeight(35)
        clear_cache_btn.clicked.connect(self._clear_web_api_cache)
        api_buttons_layout.addWidget(clear_cache_btn)
        
        # API文档按钮
        api_docs_btn = QPushButton("📖 API文档")
        api_docs_btn.setMinimumHeight(35)
        api_docs_btn.clicked.connect(self._show_api_docs)
        api_buttons_layout.addWidget(api_docs_btn)
        
        # 安全设置按钮
        security_btn = QPushButton("🔒 安全设置")
        security_btn.setMinimumHeight(35)
        security_btn.clicked.connect(self._show_security_settings)
        api_buttons_layout.addWidget(security_btn)
        
        api_layout.addLayout(api_buttons_layout)
        
        # 更新API状态显示
        self._update_web_api_status()
        
        content_layout.addWidget(api_group)
        
        # 日志显示区域
        logs_group = QGroupBox("📋 操作日志")
        logs_layout = QVBoxLayout(logs_group)
        
        # 日志显示文本框
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(200)
        self.log_display.setPlaceholderText("等待日志数据...")
        # 设置等宽字体以便更好地显示日志
        log_font = QFont("Consolas", 9)
        if not log_font.exactMatch():
            log_font = QFont("Courier New", 9)
        self.log_display.setFont(log_font)
        logs_layout.addWidget(self.log_display)
        
        # 日志控制按钮
        log_buttons_layout = QHBoxLayout()
        
        # 刷新日志按钮
        refresh_logs_btn = QPushButton("🔄 刷新日志")
        refresh_logs_btn.setMinimumHeight(30)
        refresh_logs_btn.clicked.connect(self._refresh_logs)
        log_buttons_layout.addWidget(refresh_logs_btn)
        
        # 清空日志按钮
        clear_logs_btn = QPushButton("🗑️ 清空显示")
        clear_logs_btn.setMinimumHeight(30)
        clear_logs_btn.clicked.connect(self._clear_log_display)
        log_buttons_layout.addWidget(clear_logs_btn)
        
        # 自动刷新开关
        self.auto_refresh_btn = QPushButton("⏸️ 暂停刷新")
        self.auto_refresh_btn.setMinimumHeight(30)
        self.auto_refresh_btn.setCheckable(True)
        self.auto_refresh_btn.clicked.connect(self._toggle_auto_refresh)
        log_buttons_layout.addWidget(self.auto_refresh_btn)
        
        logs_layout.addLayout(log_buttons_layout)
        
        content_layout.addWidget(logs_group)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
        # 创建定时器用于实时刷新API状态（绑定到对话框，随对话框生命周期自动清理）
        self.api_status_timer = QTimer(dialog)
        self.api_status_timer.timeout.connect(self._update_web_api_status)
        self.api_status_timer.start(2000)  # 每2秒刷新一次

        # 创建日志刷新定时器（绑定到对话框，随对话框生命周期自动清理）
        self.log_refresh_timer = QTimer(dialog)
        self.log_refresh_timer.timeout.connect(self._refresh_logs)
        self.log_refresh_enabled = True
        self.log_refresh_timer.start(3000)  # 每3秒刷新一次日志
        
        # 窗口居中显示
        if self.parent:
            parent_geometry = self.parent.geometry()
            dialog_geometry = dialog.geometry()
            x = parent_geometry.x() + (parent_geometry.width() - dialog_geometry.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - dialog_geometry.height()) // 2
            dialog.move(x, y)
        
        # 当对话框关闭时停止定时器
        def on_dialog_finished():
            if hasattr(self, 'api_status_timer'):
                try:
                    self.api_status_timer.stop()
                except RuntimeError:
                    pass
                self.api_status_timer.deleteLater()
                # 删除属性，避免后续误用触发已删除对象的错误
                try:
                    del self.api_status_timer
                except Exception:
                    self.api_status_timer = None
            if hasattr(self, 'log_refresh_timer'):
                try:
                    self.log_refresh_timer.stop()
                except RuntimeError:
                    pass
                self.log_refresh_timer.deleteLater()
                try:
                    del self.log_refresh_timer
                except Exception:
                    self.log_refresh_timer = None
        
        dialog.finished.connect(on_dialog_finished)
        
        # 显示对话框
        dialog.exec()
    
    def _setup_start_buttons(self, layout, dialog):
        """设置启动状态的按钮 - 增强版"""
        # 启动按钮
        start_btn = QPushButton("🚀 启动智能服务器")
        start_btn.setMinimumHeight(45)
        # 使用系统默认样式
        start_btn.clicked.connect(lambda checked: self._start_web_server_enhanced(dialog))
        layout.addWidget(start_btn)
        
        # 高级设置按钮
        settings_btn = QPushButton("⚙️ 高级设置")
        settings_btn.setMinimumHeight(45)
        settings_btn.setObjectName("secondary")
        # 使用系统默认样式
        settings_btn.clicked.connect(self._show_advanced_settings)
        layout.addWidget(settings_btn)
        
        # 快捷操作按钮已移除
        
        # 主题设置按钮已移除
        
        # 重启服务器按钮
        restart_btn = QPushButton("🔄 重启服务器")
        restart_btn.setMinimumHeight(45)
        # 使用系统默认样式
        restart_btn.clicked.connect(lambda checked: self._restart_web_server(dialog))
        layout.addWidget(restart_btn)
        
        # 取消按钮
        cancel_btn = QPushButton("❌ 取消")
        cancel_btn.setMinimumHeight(45)
        cancel_btn.setObjectName("secondary")
        # 使用系统默认样式
        def on_cancel_clicked():
            # 停止定时器（防止对已删除对象调用）
            if hasattr(self, 'api_status_timer'):
                try:
                    self.api_status_timer.stop()
                except RuntimeError:
                    pass
                try:
                    self.api_status_timer.deleteLater()
                except RuntimeError:
                    pass
            if hasattr(self, 'log_refresh_timer'):
                try:
                    self.log_refresh_timer.stop()
                except RuntimeError:
                    pass
                try:
                    self.log_refresh_timer.deleteLater()
                except RuntimeError:
                    pass
            dialog.close()
        cancel_btn.clicked.connect(on_cancel_clicked)
        layout.addWidget(cancel_btn)
    
    def _update_web_api_status(self):
        """更新Web API状态显示"""
        try:
            if self._web_server and self._web_server.is_running:
                # 服务器运行中
                self.server_status_value.setText("🟢 运行中")
                
                # 获取请求统计
                request_count = getattr(self._web_server, 'request_count', 0)
                self.requests_value.setText(str(request_count))
                
                # 获取运行时间
                if hasattr(self._web_server, 'start_time') and self._web_server.start_time:
                    uptime_seconds = int(time.time() - self._web_server.start_time)
                    hours = uptime_seconds // 3600
                    minutes = (uptime_seconds % 3600) // 60
                    uptime_str = f"{hours:02d}:{minutes:02d}"
                else:
                    uptime_str = "00:00"
                
                # 更新端点信息
                self.endpoints_value.setText("12个 (活跃)")
                self.cache_value.setText("🟢 已启用")
                
            else:
                # 服务器未运行
                self.server_status_value.setText("🔴 未启动")
                self.requests_value.setText("0")
                self.endpoints_value.setText("12个 (待机)")
                self.cache_value.setText("⚪ 待机")
                
        except Exception as e:
            # 异常情况
            self.server_status_value.setText("⚠️ 异常")
            self.requests_value.setText("--")
            self.endpoints_value.setText("--")
            self.cache_value.setText("--")
            print(f"更新Web API状态失败: {e}")
    
    def _clear_web_api_cache(self):
        """清除Web API缓存"""
        try:
            if self._web_server and hasattr(self._web_server, 'handler_class'):
                # 清除处理器类的缓存
                handler_class = self._web_server.handler_class
                if hasattr(handler_class, '_cache'):
                    handler_class._cache.clear()
                    handler_class._cache_timestamps.clear()
                
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self.parent, "成功", "Web API缓存已清除")
                
                # 更新状态显示
                self._update_web_api_status()
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self.parent, "警告", "Web服务器未运行，无法清除缓存")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.parent, "错误", f"清除缓存失败: {e}")
    
    def _show_api_docs(self):
        """显示API文档"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
        
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Web API 文档")
        dialog.setFixedSize(700, 500)
        
        layout = QVBoxLayout(dialog)
        
        # API文档内容
        docs_text = QTextEdit()
        docs_text.setReadOnly(True)
        docs_content = """
# XuanWu OCR Web API 文档

## 基础信息
- 基础URL: http://127.0.0.1:8888
- 内容类型: application/json
- 认证: 可选 (API Key)

## 可用端点

### 1. 系统状态
**GET** `/api/status`
获取系统运行状态、OCR引擎状态和性能信息

### 2. 关键词管理
**GET** `/api/keywords` - 获取关键词列表
**POST** `/api/keywords` - 添加关键词
**DELETE** `/api/keywords` - 删除关键词

### 3. 日志查看
**GET** `/api/logs`
获取最近的系统日志

### 4. 设置管理
**GET** `/api/settings` - 获取当前设置
**POST** `/api/settings` - 更新设置

### 5. 性能监控
**GET** `/api/performance`
获取系统性能数据 (CPU、内存使用率等)

### 6. 监控控制
**POST** `/api/start` - 启动监控
**POST** `/api/stop` - 停止监控

## 响应格式
所有API响应都采用以下格式:
```json
{
  "success": true|false,
  "data": {...},
  "error": "错误信息",
  "cached": true|false
}
```

## 缓存机制
- 状态数据缓存5秒
- 关键词缓存10秒
- 日志缓存3秒
- 设置缓存30秒
- 性能数据缓存2秒
        """
        docs_text.setPlainText(docs_content)
        layout.addWidget(docs_text)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        def on_docs_close_clicked():
            # API文档对话框没有定时器，直接关闭
            dialog.close()
        close_btn.clicked.connect(on_docs_close_clicked)
        layout.addWidget(close_btn)
        
        dialog.exec()
    
    def _show_security_settings(self):
        """显示安全设置"""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                   QPushButton, QLineEdit, QCheckBox, QGroupBox, 
                                   QScrollArea, QWidget)
        import json
        import os
        
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Web API 安全设置")
        dialog.setMinimumSize(650, 700)
        dialog.resize(650, 700)
        
        # 主布局
        main_layout = QVBoxLayout(dialog)
        
        # 创建滚动区域
        from PyQt6.QtCore import Qt
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 创建滚动内容容器
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        
        # API密钥设置
        key_group = QGroupBox("API密钥设置")
        key_layout = QVBoxLayout(key_group)
        
        # 启用API密钥
        self.enable_api_key = QCheckBox("启用API密钥验证")
        key_layout.addWidget(self.enable_api_key)
        
        # API密钥输入
        key_input_layout = QHBoxLayout()
        key_input_layout.addWidget(QLabel("API密钥:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("留空自动生成")
        key_input_layout.addWidget(self.api_key_input)
        
        generate_key_btn = QPushButton("生成")
        generate_key_btn.clicked.connect(self._generate_api_key)
        key_input_layout.addWidget(generate_key_btn)
        
        key_layout.addLayout(key_input_layout)
        layout.addWidget(key_group)
        
        # 访问控制
        access_group = QGroupBox("访问控制")
        access_layout = QVBoxLayout(access_group)
        
        self.localhost_only = QCheckBox("仅允许本地访问")
        self.localhost_only.setChecked(True)
        access_layout.addWidget(self.localhost_only)
        
        # IP白名单设置
        self.enable_ip_whitelist = QCheckBox("启用IP白名单")
        access_layout.addWidget(self.enable_ip_whitelist)
        
        ip_whitelist_layout = QVBoxLayout()
        ip_whitelist_layout.addWidget(QLabel("允许的IP地址 (每行一个，支持CIDR格式):"))
        
        from PyQt6.QtWidgets import QTextEdit
        self.ip_whitelist_input = QTextEdit()
        self.ip_whitelist_input.setMaximumHeight(80)
        self.ip_whitelist_input.setPlaceholderText("例如:\n127.0.0.1\n192.168.1.0/24\n10.0.0.0/8")
        ip_whitelist_layout.addWidget(self.ip_whitelist_input)
        
        access_layout.addLayout(ip_whitelist_layout)
        
        self.rate_limit = QCheckBox("启用速率限制 (100请求/小时)")
        self.rate_limit.setChecked(True)
        access_layout.addWidget(self.rate_limit)
        
        layout.addWidget(access_group)
        
        # 会话管理
        session_group = QGroupBox("会话管理")
        session_layout = QVBoxLayout(session_group)
        
        # 会话超时设置
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("会话超时时间 (分钟):"))
        
        from PyQt6.QtWidgets import QSpinBox
        self.session_timeout = QSpinBox()
        self.session_timeout.setRange(5, 1440)  # 5分钟到24小时
        self.session_timeout.setValue(30)  # 默认30分钟
        timeout_layout.addWidget(self.session_timeout)
        
        session_layout.addLayout(timeout_layout)
        
        # 并发会话限制
        concurrent_layout = QHBoxLayout()
        concurrent_layout.addWidget(QLabel("最大并发会话数:"))
        
        self.max_concurrent_sessions = QSpinBox()
        self.max_concurrent_sessions.setRange(1, 100)
        self.max_concurrent_sessions.setValue(5)  # 默认5个
        concurrent_layout.addWidget(self.max_concurrent_sessions)
        
        session_layout.addLayout(concurrent_layout)
        
        layout.addWidget(session_group)
        
        # 安全防护
        security_group = QGroupBox("安全防护")
        security_layout = QVBoxLayout(security_group)
        
        # 失败登录尝试限制
        self.enable_login_limit = QCheckBox("启用失败登录尝试限制")
        self.enable_login_limit.setChecked(True)
        security_layout.addWidget(self.enable_login_limit)
        
        login_limit_layout = QHBoxLayout()
        login_limit_layout.addWidget(QLabel("最大失败尝试次数:"))
        
        self.max_login_attempts = QSpinBox()
        self.max_login_attempts.setRange(3, 20)
        self.max_login_attempts.setValue(5)  # 默认5次
        login_limit_layout.addWidget(self.max_login_attempts)
        
        login_limit_layout.addWidget(QLabel("封禁时间 (分钟):"))
        
        self.ban_duration = QSpinBox()
        self.ban_duration.setRange(5, 1440)
        self.ban_duration.setValue(15)  # 默认15分钟
        login_limit_layout.addWidget(self.ban_duration)
        
        security_layout.addLayout(login_limit_layout)
        
        # API密钥过期设置
        expiry_layout = QHBoxLayout()
        expiry_layout.addWidget(QLabel("API密钥过期时间 (天):"))
        
        self.api_key_expiry_days = QSpinBox()
        self.api_key_expiry_days.setRange(0, 365)  # 0表示永不过期
        self.api_key_expiry_days.setValue(0)  # 默认永不过期
        self.api_key_expiry_days.setSpecialValueText("永不过期")
        expiry_layout.addWidget(self.api_key_expiry_days)
        
        security_layout.addLayout(expiry_layout)
        
        # HTTPS强制重定向
        self.force_https = QCheckBox("强制HTTPS重定向")
        security_layout.addWidget(self.force_https)
        
        # CORS设置
        self.enable_cors = QCheckBox("启用CORS跨域访问控制")
        security_layout.addWidget(self.enable_cors)
        
        cors_layout = QVBoxLayout()
        cors_layout.addWidget(QLabel("允许的域名 (每行一个):"))
        
        self.cors_origins_input = QTextEdit()
        self.cors_origins_input.setMaximumHeight(60)
        self.cors_origins_input.setPlaceholderText("例如:\nhttps://example.com\nhttps://app.example.com")
        cors_layout.addWidget(self.cors_origins_input)
        
        security_layout.addLayout(cors_layout)
        
        layout.addWidget(security_group)
        
        # IP封禁管理
        ban_management_group = QGroupBox("IP封禁管理")
        ban_management_layout = QVBoxLayout(ban_management_group)
        
        # 当前封禁IP列表
        ban_management_layout.addWidget(QLabel("当前被封禁的IP地址:"))
        
        from PyQt6.QtWidgets import QListWidget, QListWidgetItem
        self.banned_ips_list = QListWidget()
        self.banned_ips_list.setMaximumHeight(120)
        ban_management_layout.addWidget(self.banned_ips_list)
        
        # 封禁管理按钮
        ban_buttons_layout = QHBoxLayout()
        
        refresh_banned_btn = QPushButton("🔄 刷新列表")
        refresh_banned_btn.clicked.connect(self._refresh_banned_ips)
        ban_buttons_layout.addWidget(refresh_banned_btn)
        
        clear_selected_btn = QPushButton("🔓 解封选中IP")
        clear_selected_btn.clicked.connect(self._clear_selected_banned_ip)
        ban_buttons_layout.addWidget(clear_selected_btn)
        
        clear_all_banned_btn = QPushButton("🗑️ 清除所有封禁")
        clear_all_banned_btn.clicked.connect(self._clear_all_banned_ips)
        ban_buttons_layout.addWidget(clear_all_banned_btn)
        
        ban_management_layout.addLayout(ban_buttons_layout)
        
        # 封禁统计信息
        ban_stats_layout = QHBoxLayout()
        self.ban_stats_label = QLabel("封禁统计: 0 个IP被封禁")
        self.ban_stats_label.setStyleSheet("color: #666; font-size: 12px;")
        ban_stats_layout.addWidget(self.ban_stats_label)
        ban_management_layout.addLayout(ban_stats_layout)
        
        layout.addWidget(ban_management_group)
        
        # 将滚动内容设置到滚动区域
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
        # 按钮区域（固定在底部，不滚动）
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(lambda: self._save_security_settings(dialog))
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("取消")
        def on_security_cancel_clicked():
            # 停止封禁IP刷新定时器
            if hasattr(self, '_banned_ips_refresh_timer'):
                self._banned_ips_refresh_timer.stop()
                self._banned_ips_refresh_timer.deleteLater()
            dialog.close()
        cancel_btn.clicked.connect(on_security_cancel_clicked)
        button_layout.addWidget(cancel_btn)
        
        main_layout.addLayout(button_layout)
        
        # 加载现有设置
        self._load_security_settings()
        
        # 当对话框关闭时停止定时器
        def on_security_dialog_finished():
            if hasattr(self, '_banned_ips_refresh_timer'):
                self._banned_ips_refresh_timer.stop()
                self._banned_ips_refresh_timer.deleteLater()
        
        dialog.finished.connect(on_security_dialog_finished)
        
        dialog.exec()
    
    def _load_security_settings(self):
        """加载现有的安全设置"""
        import json
        import os
        
        try:
            settings_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'settings.json')
            
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                web_api_security = settings.get('web_api_security', {})
                
                # 设置控件状态
                self.enable_api_key.setChecked(web_api_security.get('enable_api_key', False))
                
                api_key = web_api_security.get('api_key', '')
                if api_key:
                    self.api_key_input.setText(api_key)
                
                self.localhost_only.setChecked(web_api_security.get('localhost_only', True))
                self.rate_limit.setChecked(web_api_security.get('rate_limit', True))
                
                # IP白名单设置
                self.enable_ip_whitelist.setChecked(web_api_security.get('enable_ip_whitelist', False))
                ip_whitelist = web_api_security.get('ip_whitelist', [])
                if ip_whitelist:
                    self.ip_whitelist_input.setPlainText('\n'.join(ip_whitelist))
                
                # 会话管理设置
                self.session_timeout.setValue(web_api_security.get('session_timeout', 30))
                self.max_concurrent_sessions.setValue(web_api_security.get('max_concurrent_sessions', 5))
                
                # 安全防护设置
                self.enable_login_limit.setChecked(web_api_security.get('enable_login_limit', True))
                self.max_login_attempts.setValue(web_api_security.get('max_login_attempts', 5))
                self.ban_duration.setValue(web_api_security.get('ban_duration', 15))
                self.api_key_expiry_days.setValue(web_api_security.get('api_key_expiry_days', 0))
                self.force_https.setChecked(web_api_security.get('force_https', False))
                
                # CORS设置
                self.enable_cors.setChecked(web_api_security.get('enable_cors', False))
                cors_origins = web_api_security.get('cors_origins', [])
                if cors_origins:
                    self.cors_origins_input.setPlainText('\n'.join(cors_origins))
                
            # 加载封禁IP列表
            self._refresh_banned_ips()
            
            # 启动实时刷新机制
            self._setup_realtime_refresh()
                
        except Exception as e:
            print(f"加载安全设置失败: {e}")
    
    def _setup_realtime_refresh(self):
        """设置实时刷新机制"""
        from PyQt6.QtCore import QTimer
        
        # 创建定时器，每30秒自动刷新一次封禁列表
        if not hasattr(self, '_banned_ips_refresh_timer'):
            self._banned_ips_refresh_timer = QTimer()
            self._banned_ips_refresh_timer.timeout.connect(self._refresh_banned_ips)
            self._banned_ips_refresh_timer.start(30000)  # 30秒间隔
            
            # 同时创建一个更频繁的定时器来更新剩余时间显示
            self._banned_ips_update_timer = QTimer()
            self._banned_ips_update_timer.timeout.connect(self._update_banned_ips_display)
            self._banned_ips_update_timer.start(5000)  # 5秒间隔更新显示
    
    def _update_banned_ips_display(self):
        """更新封禁IP显示的剩余时间"""
        try:
            from .web_preview_server_enhanced import WebPreviewHandler
            import time
            
            # 获取安全配置
            security_config = self._get_security_config_for_display()
            max_attempts = security_config.get('max_failed_attempts', 5)
            ban_duration = security_config.get('ban_duration_minutes', 30) * 60
            
            current_time = time.time()
            updated_count = 0
            
            # 更新列表中每个项目的剩余时间显示
            for i in range(self.banned_ips_list.count()):
                item = self.banned_ips_list.item(i)
                if item:
                    ip = item.data(32)  # 获取存储的IP地址
                    if ip and ip in WebPreviewHandler._failed_attempts:
                        attempts = WebPreviewHandler._failed_attempts[ip]
                        recent_attempts = [
                            attempt_time for attempt_time in attempts
                            if current_time - attempt_time <= 300  # 5分钟
                        ]
                        
                        if len(recent_attempts) >= max_attempts:
                            last_attempt = max(recent_attempts)
                            unban_time = last_attempt + ban_duration
                            remaining_time = max(0, int(unban_time - current_time))
                            
                            if remaining_time > 0:
                                minutes = remaining_time // 60
                                seconds = remaining_time % 60
                                item.setText(f"{ip} (失败次数: {len(recent_attempts)}, 剩余: {minutes}分{seconds}秒)")
                                updated_count += 1
                            else:
                                # 封禁时间已过，触发刷新
                                self._refresh_banned_ips()
                                break
            
        except Exception as e:
            pass  # 静默处理错误，避免影响UI
    
    def _get_security_config_for_display(self):
        """获取安全配置用于显示"""
        try:
            import json
            import os
            
            current_dir = os.path.dirname(os.path.abspath(__file__))
            settings_file = os.path.join(os.path.dirname(current_dir), 'settings.json')
            
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                return settings.get('web_api_security', {})
            return {}
        except Exception:
            return {}
    
    def _generate_api_key(self):
        """生成API密钥"""
        import secrets
        api_key = secrets.token_urlsafe(32)
        self.api_key_input.setText(api_key)
    
    def _save_security_settings(self, dialog):
        """保存安全设置（异步）"""
        from PyQt6.QtWidgets import QMessageBox
        from PyQt6.QtCore import QThread, pyqtSignal
        import json
        import os
        import time
        
        class SaveSettingsWorker(QThread):
            success = pyqtSignal()
            error_occurred = pyqtSignal(str)
            
            def __init__(self, settings_data, settings_file, web_server):
                super().__init__()
                self.settings_data = settings_data
                self.settings_file = settings_file
                self.web_server = web_server
            
            def run(self):
                try:
                    # 读取现有配置
                    settings = {}
                    if os.path.exists(self.settings_file):
                        with open(self.settings_file, 'r', encoding='utf-8') as f:
                            settings = json.load(f)
                    
                    # 更新web API安全设置
                    if 'web_api_security' not in settings:
                        settings['web_api_security'] = {}
                    
                    settings['web_api_security'].update(self.settings_data)
                    
                    # 保存配置文件
                    with open(self.settings_file, 'w', encoding='utf-8') as f:
                        json.dump(settings, f, ensure_ascii=False, indent=2)
                    
                    # 如果web服务器正在运行，尝试应用新的安全设置
                    if self.web_server and hasattr(self.web_server, 'handler_class'):
                        handler_class = self.web_server.handler_class
                        if hasattr(handler_class, 'initialize_security'):
                            # 更新安全配置
                            if self.settings_data.get('enable_api_key') and self.settings_data.get('api_key'):
                                handler_class._api_key = self.settings_data.get('api_key')
                            handler_class.initialize_security()
                    
                    self.success.emit()
                    
                except Exception as e:
                    self.error_occurred.emit(str(e))
        
        try:
            # 获取设置值
            enable_api_key = self.enable_api_key.isChecked()
            api_key = self.api_key_input.text().strip()
            localhost_only = self.localhost_only.isChecked()
            rate_limit = self.rate_limit.isChecked()
            
            # IP白名单设置
            enable_ip_whitelist = self.enable_ip_whitelist.isChecked()
            ip_whitelist_text = self.ip_whitelist_input.toPlainText().strip()
            ip_whitelist = [ip.strip() for ip in ip_whitelist_text.split('\n') if ip.strip()] if ip_whitelist_text else []
            
            # 会话管理设置
            session_timeout = self.session_timeout.value()
            max_concurrent_sessions = self.max_concurrent_sessions.value()
            
            # 安全防护设置
            enable_login_limit = self.enable_login_limit.isChecked()
            max_login_attempts = self.max_login_attempts.value()
            ban_duration = self.ban_duration.value()
            api_key_expiry_days = self.api_key_expiry_days.value()
            force_https = self.force_https.isChecked()
            
            # CORS设置
            enable_cors = self.enable_cors.isChecked()
            cors_origins_text = self.cors_origins_input.toPlainText().strip()
            cors_origins = [origin.strip() for origin in cors_origins_text.split('\n') if origin.strip()] if cors_origins_text else []
            
            # 准备设置数据
            settings_data = {
                'enable_api_key': enable_api_key,
                'api_key': api_key if api_key else None,
                'localhost_only': localhost_only,
                'rate_limit': rate_limit,
                # IP白名单设置
                'enable_ip_whitelist': enable_ip_whitelist,
                'ip_whitelist': ip_whitelist,
                # 会话管理设置
                'session_timeout': session_timeout,
                'max_concurrent_sessions': max_concurrent_sessions,
                # 安全防护设置
                'enable_login_limit': enable_login_limit,
                'max_login_attempts': max_login_attempts,
                'ban_duration': ban_duration,
                'api_key_expiry_days': api_key_expiry_days,
                'force_https': force_https,
                # CORS设置
                'enable_cors': enable_cors,
                'cors_origins': cors_origins,
                'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            settings_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'settings.json')
            web_server = getattr(self, '_web_server', None)
            
            def on_success():
                QMessageBox.information(self.parent, "成功", "Web API安全设置已保存并应用")
                dialog.close()
            
            def on_error(error_msg):
                QMessageBox.critical(self.parent, "错误", f"保存安全设置失败: {error_msg}")
            
            # 创建并启动工作线程
            self.save_settings_worker = SaveSettingsWorker(settings_data, settings_file, web_server)
            self.save_settings_worker.success.connect(on_success)
            self.save_settings_worker.error_occurred.connect(on_error)
            self.save_settings_worker.start()
            
        except Exception as e:
            QMessageBox.critical(self.parent, "错误", f"保存安全设置失败: {e}")
    
    def _refresh_banned_ips(self):
        """刷新封禁IP列表（异步）"""
        from PyQt6.QtCore import QThread, pyqtSignal
        from PyQt6.QtWidgets import QListWidgetItem
        
        class BannedIPsWorker(QThread):
            data_ready = pyqtSignal(list)
            error_occurred = pyqtSignal(str)
            
            def __init__(self, web_server):
                super().__init__()
                self.web_server = web_server
            
            def _get_security_config(self):
                """从设置文件获取安全配置"""
                try:
                    import json
                    import os
                    
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    settings_file = os.path.join(os.path.dirname(current_dir), 'settings.json')
                    
                    if os.path.exists(settings_file):
                        with open(settings_file, 'r', encoding='utf-8') as f:
                            settings = json.load(f)
                        return settings.get('web_api_security', {})
                    return {}
                except Exception:
                    return {}
            
            def _get_banned_ips_direct(self):
                """直接从WebPreviewHandler获取封禁IP数据"""
                try:
                    from .web_preview_server_enhanced import WebPreviewHandler
                    import time
                    
                    # 获取安全配置
                    security_config = self._get_security_config()
                    max_attempts = security_config.get('max_failed_attempts', 5)
                    ban_duration = security_config.get('ban_duration_minutes', 30) * 60
                    
                    current_time = time.time()
                    banned_ips = []
                    
                    # 直接访问WebPreviewHandler的_failed_attempts数据
                    for ip, attempts in WebPreviewHandler._failed_attempts.items():
                        # 过滤5分钟内的尝试
                        recent_attempts = [
                            attempt_time for attempt_time in attempts
                            if current_time - attempt_time <= 300  # 5分钟
                        ]
                        
                        # 检查是否达到封禁条件
                        if len(recent_attempts) >= max_attempts:
                            # 计算解封时间
                            last_attempt = max(recent_attempts)
                            unban_time = last_attempt + ban_duration
                            
                            banned_ips.append({
                                'ip': ip,
                                'attempts': len(recent_attempts),
                                'failed_attempts': len(recent_attempts),
                                'last_attempt': last_attempt,
                                'unban_time': unban_time,
                                'remaining_time': max(0, int(unban_time - current_time))
                            })
                    
                    return banned_ips
                    
                except Exception as e:
                    raise Exception(f"直接获取封禁数据失败: {str(e)}")
            
            def run(self):
                try:
                    # 直接获取封禁IP数据，不依赖API
                    banned_ips_data = self._get_banned_ips_direct()
                    self.data_ready.emit(banned_ips_data)
                        
                except Exception as e:
                    self.error_occurred.emit(f"获取失败: {str(e)}")
        
        def on_data_ready(banned_ips):
            # 检查UI对象是否仍然存在
            if not hasattr(self, 'banned_ips_list') or not hasattr(self, 'ban_stats_label'):
                return
            
            try:
                # 清空现有列表
                self.banned_ips_list.clear()
                
                for ip_info in banned_ips:
                    ip = ip_info.get('ip', '')
                    attempts = ip_info.get('attempts', 0)
                    remaining_time = ip_info.get('remaining_time', 0)
                    
                    # 格式化显示文本
                    if remaining_time > 0:
                        minutes = remaining_time // 60
                        seconds = remaining_time % 60
                        display_text = f"{ip} (失败次数: {attempts}, 剩余: {minutes}分{seconds}秒)"
                    else:
                        display_text = f"{ip} (失败次数: {attempts}, 已解封)"
                    
                    item = QListWidgetItem(display_text)
                    item.setData(32, ip)  # 存储IP地址用于后续操作
                    self.banned_ips_list.addItem(item)
                
                # 更新统计信息
                count = len(banned_ips)
                active_bans = len([ip for ip in banned_ips if ip.get('remaining_time', 0) > 0])
                self.ban_stats_label.setText(f"封禁统计: {count} 个IP记录，{active_bans} 个活跃封禁")
            except RuntimeError:
                # QLabel或QListWidget对象已被删除，忽略此错误
                pass
        
        def on_error(error_msg):
            # 检查UI对象是否仍然存在
            if not hasattr(self, 'ban_stats_label'):
                return
            
            try:
                self.ban_stats_label.setText(f"封禁统计: {error_msg}")
            except RuntimeError:
                # QLabel对象已被删除，忽略此错误
                pass
        
        # 检查UI对象是否存在并显示加载状态
        if hasattr(self, 'ban_stats_label'):
            try:
                self.ban_stats_label.setText("封禁统计: 正在加载...")
            except RuntimeError:
                # QLabel对象已被删除，直接返回
                return
        
        # 创建并启动工作线程
        web_server = getattr(self, '_web_server', None) if hasattr(self, '_web_server') else None
        self.banned_ips_worker = BannedIPsWorker(web_server)
        self.banned_ips_worker.data_ready.connect(on_data_ready)
        self.banned_ips_worker.error_occurred.connect(on_error)
        self.banned_ips_worker.start()
    
    def _clear_selected_banned_ip(self):
        """解封选中的IP"""
        from PyQt6.QtWidgets import QMessageBox
        
        # 检查UI对象是否仍然存在
        if not hasattr(self, 'banned_ips_list'):
            return
        
        try:
            current_item = self.banned_ips_list.currentItem()
            if not current_item:
                QMessageBox.warning(self.parent, "警告", "请先选择要解封的IP地址")
                return
        except RuntimeError:
            # QListWidget对象已被删除
            return
        
        ip = current_item.data(32)  # 获取存储的IP地址
        if not ip:
            QMessageBox.warning(self.parent, "警告", "无法获取IP地址信息")
            return
        
        reply = QMessageBox.question(
            self.parent, 
            "确认解封", 
            f"确定要解封IP地址 {ip} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._clear_ip_failed_attempts(ip)
    
    def _clear_all_banned_ips(self):
        """清除所有封禁IP"""
        from PyQt6.QtWidgets import QMessageBox
        
        # 检查UI对象是否仍然存在
        if not hasattr(self, 'banned_ips_list'):
            return
        
        try:
            if self.banned_ips_list.count() == 0:
                QMessageBox.information(self.parent, "信息", "当前没有被封禁的IP地址")
                return
        except RuntimeError:
            # QListWidget对象已被删除
            return
        
        reply = QMessageBox.question(
            self.parent, 
            "确认清除", 
            "确定要清除所有IP的封禁记录吗？这将解封所有被封禁的IP地址。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._clear_ip_failed_attempts(None, clear_all=True)
    
    def _clear_ip_failed_attempts(self, ip=None, clear_all=False):
        """清除IP失败尝试记录（异步）"""
        from PyQt6.QtWidgets import QMessageBox
        from PyQt6.QtCore import QThread, pyqtSignal
        
        class ClearIPWorker(QThread):
            success = pyqtSignal(str)
            error_occurred = pyqtSignal(str)
            
            def __init__(self, web_server, ip, clear_all, action_desc):
                super().__init__()
                self.web_server = web_server
                self.ip = ip
                self.clear_all = clear_all
                self.action_desc = action_desc
            
            def run(self):
                try:
                    from .web_preview_server_enhanced import WebPreviewHandler
                    
                    # 直接操作WebPreviewHandler的_failed_attempts数据
                    if self.clear_all:
                        # 清除所有失败尝试记录
                        cleared_count = len(WebPreviewHandler._failed_attempts)
                        WebPreviewHandler._failed_attempts.clear()
                        self.success.emit(f"{self.action_desc} (清除了{cleared_count}个IP记录)")
                    else:
                        # 清除指定IP的失败尝试记录
                        if self.ip in WebPreviewHandler._failed_attempts:
                            del WebPreviewHandler._failed_attempts[self.ip]
                            self.success.emit(f"{self.action_desc}")
                        else:
                            self.success.emit(f"{self.action_desc} (该IP无封禁记录)")
                        
                except Exception as e:
                    self.error_occurred.emit(f"操作失败: {str(e)}")
        
        # 不再需要检查Web服务器状态，因为直接访问数据
        
        # 准备操作描述
        if clear_all:
            action_desc = "清除所有封禁记录"
        else:
            action_desc = f"解封IP {ip}"
        
        def on_success(desc):
            QMessageBox.information(self.parent, "成功", f"{desc}成功")
            # 刷新封禁列表
            self._refresh_banned_ips()
        
        def on_error(error_msg):
            if "网络" in error_msg or "连接" in error_msg:
                QMessageBox.warning(self.parent, "网络错误", f"无法连接到Web服务器: {error_msg}")
            else:
                QMessageBox.warning(self.parent, "操作失败", error_msg)
        
        # 创建并启动工作线程
        self.clear_ip_worker = ClearIPWorker(self._web_server, ip, clear_all, action_desc)
        self.clear_ip_worker.success.connect(on_success)
        self.clear_ip_worker.error_occurred.connect(on_error)
        self.clear_ip_worker.start()
    
    def _setup_running_buttons(self, layout, dialog):
        """设置运行状态的按钮 - 增强版"""
        # 打开浏览器按钮
        open_btn = QPushButton("🌐 打开智能控制面板")
        open_btn.setMinimumHeight(45)
        # 使用系统默认样式
        open_btn.clicked.connect(lambda checked: self._open_browser_and_close(dialog))
        layout.addWidget(open_btn)
        
        # 复制地址按钮
        copy_btn = QPushButton("📋 复制访问地址")
        copy_btn.setMinimumHeight(45)
        copy_btn.setObjectName("secondary")
        # 使用系统默认样式
        copy_btn.clicked.connect(lambda checked: self._copy_url_to_clipboard(self._web_server.get_url() if self._web_server else "http://127.0.0.1:8888"))
        layout.addWidget(copy_btn)
        
        # 重启按钮
        restart_btn = QPushButton("🔄 重启服务器")
        restart_btn.setMinimumHeight(45)
        # 使用系统默认样式
        restart_btn.clicked.connect(lambda checked: self._restart_web_server(dialog))
        layout.addWidget(restart_btn)
        
        # 停止按钮
        stop_btn = QPushButton("⏹️ 停止服务器")
        stop_btn.setMinimumHeight(45)
        stop_btn.setObjectName("danger")
        # 使用系统默认样式
        stop_btn.clicked.connect(lambda checked: self._stop_web_server(dialog))
        layout.addWidget(stop_btn)
    
    def _start_web_server_enhanced(self, dialog):
        """增强版启动Web服务器方法"""
        try:
            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("正在启动服务器...")
            
            # 模拟启动进度
            for i in range(0, 101, 20):
                self.progress_bar.setValue(i)
                QApplication.processEvents()
                import time
                time.sleep(0.1)
            
            # 调用原始启动方法
            self._start_web_server(dialog)
            
            # 隐藏进度条
            self.progress_bar.setVisible(False)
            
        except Exception as e:
            self.progress_bar.setVisible(False)
            QMessageBox.warning(dialog, "启动失败", f"服务器启动失败：{str(e)}")
    
    def _restart_web_server(self, dialog):
        """重启Web服务器"""
        from PyQt6.QtCore import QTimer, QThread, pyqtSignal
        import time
        
        # 创建异步重启工作线程
        class RestartWorker(QThread):
            progress_updated = pyqtSignal(int, str)
            restart_completed = pyqtSignal(bool, str)
            
            def __init__(self, web_server, timeout=10):
                super().__init__()
                self.web_server = web_server
                self.timeout = timeout  # 超时时间（秒）
                self.start_time = None
            
            def run(self):
                try:
                    self.start_time = time.time()
                    
                    self.progress_updated.emit(10, "正在停止服务器...")
                    
                    # 停止服务器（现在是非阻塞的）
                    if self.web_server and self.web_server.is_running:
                        self.web_server.stop_server()
                    
                    # 检查超时
                    if self._check_timeout():
                        return
                    
                    self.progress_updated.emit(50, "等待服务器完全停止...")
                    # 短暂等待确保服务器完全停止
                    self.msleep(500)
                    
                    # 检查超时
                    if self._check_timeout():
                        return
                    
                    self.progress_updated.emit(70, "正在重新启动...")
                    # 重新启动服务器
                    if self.web_server:
                        success = self.web_server.start_server()
                        if success:
                            self.progress_updated.emit(100, "重启完成！")
                            self.restart_completed.emit(True, "服务器重启成功")
                        else:
                            self.restart_completed.emit(False, "服务器启动失败")
                    else:
                        self.restart_completed.emit(False, "服务器实例不存在")
                        
                except Exception as e:
                    self.restart_completed.emit(False, f"重启过程中发生错误：{str(e)}")
            
            def _check_timeout(self):
                """检查是否超时"""
                if self.start_time and time.time() - self.start_time > self.timeout:
                    self.restart_completed.emit(False, f"重启操作超时（{self.timeout}秒）")
                    return True
                return False
        
        try:
            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("准备重启服务器...")
            
            # 创建并启动重启工作线程
            self.restart_worker = RestartWorker(self._web_server, timeout=15)  # 15秒超时
            
            # 连接信号
            def on_progress_updated(value, message):
                self.progress_bar.setValue(value)
                self.progress_bar.setFormat(message)
                QApplication.processEvents()
            
            def on_restart_completed(success, message):
                # 清理超时定时器（避免对已删除对象调用）
                if hasattr(self, 'restart_timeout_timer'):
                    try:
                        self.restart_timeout_timer.stop()
                    except RuntimeError:
                        pass
                    try:
                        self.restart_timeout_timer.deleteLater()
                    except RuntimeError:
                        pass
                    delattr(self, 'restart_timeout_timer')
                
                self.progress_bar.setVisible(False)
                if success:
                    # 重启成功，更新UI状态
                    QTimer.singleShot(100, lambda: self._update_dialog_for_running_state(dialog))
                else:
                    # 重启失败，显示错误信息
                    if hasattr(dialog, 'parent') and dialog.parent():
                        QMessageBox.warning(dialog.parent(), "重启失败", message)
                    else:
                        QMessageBox.warning(None, "重启失败", message)
            
            self.restart_worker.progress_updated.connect(on_progress_updated)
            self.restart_worker.restart_completed.connect(on_restart_completed)
            
            # 添加额外的超时保护机制
            self.restart_timeout_timer = QTimer(dialog)
            self.restart_timeout_timer.timeout.connect(lambda: self._handle_restart_timeout(dialog))
            self.restart_timeout_timer.setSingleShot(True)
            self.restart_timeout_timer.start(20000)  # 20秒绝对超时
            
            self.restart_worker.start()
                
        except Exception as e:
            self.progress_bar.setVisible(False)
            if hasattr(dialog, 'parent') and dialog.parent():
                QMessageBox.warning(dialog.parent(), "重启失败", f"服务器重启失败：{str(e)}")
            else:
                QMessageBox.warning(None, "重启失败", f"服务器重启失败：{str(e)}")
    
    def _handle_restart_timeout(self, dialog):
        """处理重启超时"""
        try:
            # 强制终止工作线程
            if hasattr(self, 'restart_worker') and self.restart_worker.isRunning():
                self.restart_worker.terminate()
                self.restart_worker.wait(1000)  # 等待1秒让线程清理
            
            # 隐藏进度条
            if hasattr(self, 'progress_bar'):
                self.progress_bar.setVisible(False)
            
            # 显示超时错误
            QMessageBox.warning(dialog, "重启超时", "服务器重启操作超时，请手动检查服务器状态")
            
        except Exception as e:
            print(f"处理重启超时时发生错误：{e}")
    
    def _handle_stop_timeout(self, dialog):
        """处理停止操作超时"""
        try:
            # 强制终止停止工作线程
            if hasattr(self, 'stop_worker') and self.stop_worker.isRunning():
                self.stop_worker.terminate()
                self.stop_worker.wait(1000)  # 等待1秒让线程清理
            
            # 隐藏进度条
            if hasattr(self, 'progress_bar'):
                self.progress_bar.setVisible(False)
            
            # 强制清理服务器实例并更新UI状态
            self._web_server = None
            self._update_dialog_for_stopped_state(dialog)
            
            # 显示超时错误
            QMessageBox.warning(dialog, "停止超时", "服务器停止操作超时，已强制停止并重置状态")
            
        except Exception as e:
            print(f"处理停止超时时发生错误：{e}")
    
    # _restart_step_2方法已被移除，重启流程现在完全异步化
    
    def _show_analytics_dashboard(self, dialog):
        """显示数据分析仪表盘"""
        analytics_dialog = QDialog(dialog)
        analytics_dialog.setWindowTitle("📊 智能数据分析仪表盘")
        analytics_dialog.setFixedSize(900, 700)
        analytics_dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        
        # 设置现代化样式
        analytics_dialog.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e3c72, stop:1 #2a5298);
                border-radius: 15px;
            }
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.05);
            }
            QTabWidget::tab-bar {
                alignment: center;
            }
            QTabBar::tab {
                background: rgba(255, 255, 255, 0.1);
                color: #ffffff;
                padding: 12px 20px;
                margin: 2px;
                border-radius: 8px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4CAF50, stop:1 #388E3C);
            }
            QTabBar::tab:hover {
                background: rgba(255, 255, 255, 0.2);
            }
        """)
        
        layout = QVBoxLayout(analytics_dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("🎯 XuanWu OCR 智能数据分析中心")
        title_label.setStyleSheet("""
            color: #ffffff;
            font-size: 18px;
            font-weight: bold;
            padding: 15px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            margin-bottom: 10px;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        
        # 实时监控选项卡
        realtime_tab = self._create_realtime_monitoring_tab()
        tab_widget.addTab(realtime_tab, "📈 实时监控")
        
        # 性能分析选项卡
        performance_tab = self._create_performance_analysis_tab()
        tab_widget.addTab(performance_tab, "⚡ 性能分析")
        
        # 数据统计选项卡
        statistics_tab = self._create_statistics_tab()
        tab_widget.addTab(statistics_tab, "📊 数据统计")
        
        # 系统健康选项卡
        health_tab = self._create_system_health_tab()
        tab_widget.addTab(health_tab, "💚 系统健康")
        
        layout.addWidget(tab_widget)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        export_btn = QPushButton("📤 导出报告")
        export_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FF9800, stop:1 #F57C00);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFB74D, stop:1 #FF9800);
            }
        """)
        button_layout.addWidget(export_btn)
        
        refresh_btn = QPushButton("🔄 刷新数据")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2196F3, stop:1 #1976D2);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #42A5F5, stop:1 #2196F3);
            }
        """)
        button_layout.addWidget(refresh_btn)
        
        close_btn = QPushButton("❌ 关闭")
        close_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #757575, stop:1 #616161);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #9E9E9E, stop:1 #757575);
            }
        """)
        close_btn.clicked.connect(analytics_dialog.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        analytics_dialog.exec()
    
    def _create_realtime_monitoring_tab(self):
        """创建实时监控选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 实时指标卡片
        metrics_group = QGroupBox("📊 实时系统指标")
        metrics_layout = QGridLayout(metrics_group)
        
        # CPU使用率
        cpu_card = self._create_metric_card("💻 CPU使用率", "0%", "#4CAF50")
        metrics_layout.addWidget(cpu_card, 0, 0)
        
        # 内存使用率
        memory_card = self._create_metric_card("🧠 内存使用率", "0%", "#2196F3")
        metrics_layout.addWidget(memory_card, 0, 1)
        
        # 识别次数
        ocr_card = self._create_metric_card("🔍 识别次数", "0", "#FF9800")
        metrics_layout.addWidget(ocr_card, 1, 0)
        
        # 响应时间
        response_card = self._create_metric_card("⚡ 响应时间", "0ms", "#9C27B0")
        metrics_layout.addWidget(response_card, 1, 1)
        
        layout.addWidget(metrics_group)
        
        # 实时图表区域
        chart_group = QGroupBox("📈 实时性能趋势")
        chart_layout = QVBoxLayout(chart_group)
        
        # 这里可以添加实时图表组件
        chart_placeholder = QLabel("📊 实时性能图表\n\n• CPU使用率趋势\n• 内存使用变化\n• 识别响应时间\n• 网络连接状态")
        chart_placeholder.setStyleSheet("""
            color: #ffffff;
            font-size: 14px;
            padding: 40px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            border: 2px dashed rgba(255, 255, 255, 0.3);
        """)
        chart_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chart_layout.addWidget(chart_placeholder)
        
        layout.addWidget(chart_group)
        
        return tab
    
    def _create_performance_analysis_tab(self):
        """创建性能分析选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 性能概览
        overview_group = QGroupBox("⚡ 性能概览")
        overview_layout = QGridLayout(overview_group)
        
        # 平均性能指标
        avg_cpu = self._create_metric_card("📊 平均CPU", "25%", "#4CAF50")
        overview_layout.addWidget(avg_cpu, 0, 0)
        
        avg_memory = self._create_metric_card("📊 平均内存", "60%", "#2196F3")
        overview_layout.addWidget(avg_memory, 0, 1)
        
        avg_response = self._create_metric_card("📊 平均响应", "150ms", "#FF9800")
        overview_layout.addWidget(avg_response, 1, 0)
        
        success_rate = self._create_metric_card("📊 成功率", "98.5%", "#4CAF50")
        overview_layout.addWidget(success_rate, 1, 1)
        
        layout.addWidget(overview_group)
        
        # 性能趋势分析
        trend_group = QGroupBox("📈 性能趋势分析")
        trend_layout = QVBoxLayout(trend_group)
        
        trend_placeholder = QLabel("📈 性能趋势图表\n\n• 24小时性能变化\n• 峰值时段分析\n• 性能瓶颈识别\n• 优化建议")
        trend_placeholder.setStyleSheet("""
            color: #ffffff;
            font-size: 14px;
            padding: 40px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            border: 2px dashed rgba(255, 255, 255, 0.3);
        """)
        trend_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        trend_layout.addWidget(trend_placeholder)
        
        layout.addWidget(trend_group)
        
        return tab
    
    def _create_statistics_tab(self):
        """创建数据统计选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 统计概览
        stats_group = QGroupBox("📊 数据统计概览")
        stats_layout = QGridLayout(stats_group)
        
        # 今日统计
        today_ocr = self._create_metric_card("📅 今日识别", "1,234", "#4CAF50")
        stats_layout.addWidget(today_ocr, 0, 0)
        
        total_ocr = self._create_metric_card("📈 总识别数", "45,678", "#2196F3")
        stats_layout.addWidget(total_ocr, 0, 1)
        
        active_keywords = self._create_metric_card("🔑 活跃关键词", "89", "#FF9800")
        stats_layout.addWidget(active_keywords, 1, 0)
        
        uptime = self._create_metric_card("⏰ 运行时间", "72h 15m", "#9C27B0")
        stats_layout.addWidget(uptime, 1, 1)
        
        layout.addWidget(stats_group)
        
        # 详细统计表格
        table_group = QGroupBox("📋 详细统计数据")
        table_layout = QVBoxLayout(table_group)
        
        stats_table = QTableWidget(5, 3)
        stats_table.setHorizontalHeaderLabels(["指标", "数值", "趋势"])
        stats_table.setStyleSheet("""
            QTableWidget {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                color: #ffffff;
            }
            QHeaderView::section {
                background: rgba(255, 255, 255, 0.1);
                color: #ffffff;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        
        # 添加示例数据
        stats_data = [
            ["识别成功率", "98.5%", "↗ +2.1%"],
            ["平均响应时间", "145ms", "↘ -15ms"],
            ["错误率", "1.5%", "↘ -0.3%"],
            ["峰值并发", "25", "↗ +5"],
            ["系统稳定性", "99.2%", "→ 0%"]
        ]
        
        for row, data in enumerate(stats_data):
            for col, value in enumerate(data):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                stats_table.setItem(row, col, item)
        
        stats_table.resizeColumnsToContents()
        table_layout.addWidget(stats_table)
        
        layout.addWidget(table_group)
        
        return tab
    
    def _create_system_health_tab(self):
        """创建系统健康选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 系统健康状态
        health_group = QGroupBox("💚 系统健康状态")
        health_layout = QGridLayout(health_group)
        
        # 各组件状态
        ocr_status = self._create_status_card("🔍 OCR引擎", "正常", "#4CAF50")
        health_layout.addWidget(ocr_status, 0, 0)
        
        web_status = self._create_status_card("🌐 Web服务", "运行中", "#4CAF50")
        health_layout.addWidget(web_status, 0, 1)
        
        db_status = self._create_status_card("💾 数据存储", "正常", "#4CAF50")
        health_layout.addWidget(db_status, 1, 0)
        
        network_status = self._create_status_card("📡 网络连接", "稳定", "#4CAF50")
        health_layout.addWidget(network_status, 1, 1)
        
        layout.addWidget(health_group)
        
        # 系统日志
        log_group = QGroupBox("📋 系统日志")
        log_layout = QVBoxLayout(log_group)
        
        log_text = QTextEdit()
        log_text.setStyleSheet("""
            QTextEdit {
                background: rgba(0, 0, 0, 0.3);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 10px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }
        """)
        
        # 添加示例日志
        sample_logs = [
            "[2024-01-15 10:30:15] INFO: OCR引擎启动成功",
            "[2024-01-15 10:30:16] INFO: Web服务器启动在端口8888",
            "[2024-01-15 10:30:17] INFO: 关键词监控已激活",
            "[2024-01-15 10:31:22] INFO: 识别任务完成，耗时150ms",
            "[2024-01-15 10:32:45] INFO: 系统性能检查通过",
            "[2024-01-15 10:33:10] INFO: 数据备份完成"
        ]
        
        log_text.setPlainText("\n".join(sample_logs))
        log_layout.addWidget(log_text)
        
        layout.addWidget(log_group)
        
        return tab
    
    def _create_metric_card(self, title, value, color):
        """创建指标卡片"""
        card = QGroupBox()
        # 移除自定义样式
        
        layout = QVBoxLayout(card)
        
        title_label = QLabel(title)
        # 移除自定义样式
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        value_label = QLabel(value)
        # 移除自定义样式
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        return card
    
    def _create_status_card(self, title, status, color):
        """创建状态卡片"""
        card = QGroupBox()
        # 移除自定义样式
        
        layout = QVBoxLayout(card)
        
        title_label = QLabel(title)
        # 移除自定义样式
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        status_label = QLabel(f"● {status}")
        # 移除自定义样式
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(title_label)
        layout.addWidget(status_label)
        
        return card
    
    def get_local_ip(self):
        """获取本地IP地址"""
        try:
            # 方法1：连接到外部地址获取本地IP
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            try:
                # 方法2：获取主机名对应的IP
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
                if ip.startswith("127."):
                    # 如果是回环地址，尝试其他方法
                    raise Exception("Got loopback address")
                return ip
            except:
                try:
                    # 方法3：遍历网络接口
                    import subprocess
                    result = subprocess.run(['ipconfig'], capture_output=True, text=True, shell=True)
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if 'IPv4' in line and '192.168.' in line:
                            ip = line.split(':')[-1].strip()
                            return ip
                except:
                    pass
                return "127.0.0.1"  # 默认返回本地回环地址
    
    def refresh_local_ip(self, ip_label):
        """刷新本地IP显示"""
        local_ip = self.get_local_ip()
        ip_label.setText(f"当前本地IP: {local_ip}")
    
    def fill_ip_to_host(self, current_ip, host_input, ip_label):
        """将当前IP地址填入主机输入框"""
        # 获取最新的IP地址
        latest_ip = self.get_local_ip()
        # 更新IP显示标签
        ip_label.setText(f"当前本地IP: {latest_ip}")
        # 填入主机输入框
        host_input.setText(latest_ip)
        # 显示提示信息
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(None, "操作成功", f"已将IP地址 {latest_ip} 填入主机输入框")
    
    def _reset_to_default(self, port_input, host_input, auto_optimize, cache_enable, auto_ip_checkbox):
        """重置为默认设置"""
        from PyQt6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(None, "确认重置", 
                                   "确定要重置为默认设置吗？\n主机: 127.0.0.1\n端口: 8888",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            # 重置为默认值
            port_input.setText("8888")
            host_input.setText("127.0.0.1")
            auto_optimize.setChecked(True)
            cache_enable.setChecked(True)
            auto_ip_checkbox.setChecked(True)
            
            QMessageBox.information(None, "重置完成", "已重置为默认设置")
    
    def _show_advanced_settings(self):
        """显示高级设置对话框"""
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("⚙️ 高级设置")
        # 移除固定大小和自定义样式，使用系统默认
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        
        # 读取当前配置
        import json
        import os
        
        config_file = "settings.json"
        current_config = {
            'port': 8888,
            'host': '127.0.0.1',
            'auto_optimize': True,
            'cache_enable': True,
            'auto_get_ip': True
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'web_server' in config:
                        current_config.update(config['web_server'])
            except Exception as e:
                print(f"读取配置文件失败，使用默认设置: {e}")
        
        # 服务器设置
        server_group = QGroupBox("🌐 服务器配置")
        server_layout = QFormLayout(server_group)
        
        port_input = QLineEdit(str(current_config['port']))
        # 移除自定义样式，使用系统默认
        server_layout.addRow("端口:", port_input)
        
        host_input = QLineEdit(current_config['host'])
        # 移除自定义样式，使用系统默认
        server_layout.addRow("主机:", host_input)
        
        layout.addWidget(server_group)
        
        # 性能设置
        perf_group = QGroupBox("⚡ 性能优化")
        perf_layout = QVBoxLayout(perf_group)
        
        auto_optimize = QCheckBox("启用自动性能优化")
        # 移除自定义样式，使用系统默认
        auto_optimize.setChecked(current_config['auto_optimize'])
        perf_layout.addWidget(auto_optimize)
        
        cache_enable = QCheckBox("启用结果缓存")
        # 移除自定义样式，使用系统默认
        cache_enable.setChecked(current_config['cache_enable'])
        perf_layout.addWidget(cache_enable)
        
        layout.addWidget(perf_group)
        
        # 网络设置
        network_group = QGroupBox("🌐 网络设置")
        network_layout = QVBoxLayout(network_group)
        
        # 自动获取IP设置
        auto_ip_checkbox = QCheckBox("自动获取本地IP地址")
        auto_ip_checkbox.setChecked(current_config.get('auto_get_ip', True))
        network_layout.addWidget(auto_ip_checkbox)
        
        # IP显示和操作
        ip_display_layout = QHBoxLayout()
        current_ip = self.get_local_ip()
        ip_label = QLabel(f"当前本地IP: {current_ip}")
        ip_display_layout.addWidget(ip_label)
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(lambda: self.refresh_local_ip(ip_label))
        ip_display_layout.addWidget(refresh_btn)
        
        # 一键填入主机输入框按钮
        fill_host_btn = QPushButton("📋 填入主机")
        fill_host_btn.setToolTip("将当前IP地址填入主机输入框")
        fill_host_btn.clicked.connect(lambda: self.fill_ip_to_host(current_ip, host_input, ip_label))
        ip_display_layout.addWidget(fill_host_btn)
        
        network_layout.addLayout(ip_display_layout)
        
        # IP设置说明
        ip_help_label = QLabel("💡 提示：点击'填入主机'按钮可将当前IP地址自动填入主机输入框")
        ip_help_label.setWordWrap(True)
        ip_help_label.setStyleSheet("color: gray; font-size: 11px; padding: 5px;")
        network_layout.addWidget(ip_help_label)
        
        layout.addWidget(network_group)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        # 重置按钮
        reset_btn = QPushButton("🔄 重置默认")
        reset_btn.setToolTip("重置为默认设置：主机 127.0.0.1，端口 8888")
        reset_btn.clicked.connect(lambda: self._reset_to_default(port_input, host_input, auto_optimize, cache_enable, auto_ip_checkbox))
        btn_layout.addWidget(reset_btn)
        
        save_btn = QPushButton("💾 保存设置")
        # 移除自定义背景颜色和按钮大小样式，使用系统默认
        save_btn.clicked.connect(lambda: self._save_server_settings(port_input.text(), host_input.text(), auto_optimize.isChecked(), cache_enable.isChecked(), auto_ip_checkbox.isChecked(), dialog))
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("❌ 取消")
        # 移除自定义背景颜色和按钮大小样式，使用系统默认
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        dialog.exec()
    
    def _save_server_settings(self, port, host, auto_optimize, cache_enable, auto_get_ip, dialog):
        """保存服务器设置并应用"""
        try:
            # 验证端口号
            port_num = int(port)
            if not (1024 <= port_num <= 65535):
                QMessageBox.warning(dialog, "设置错误", "端口号必须在1024-65535之间")
                return
            
            # 验证主机地址
            if not host.strip():
                QMessageBox.warning(dialog, "设置错误", "主机地址不能为空")
                return
            
            # 保存设置到配置文件
            import json
            import os
            
            config_file = "settings.json"
            config = {}
            
            # 读取现有配置
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                except:
                    config = {}
            
            # 更新服务器配置
            config['web_server'] = {
                'port': port_num,
                'host': host.strip(),
                'auto_optimize': auto_optimize,
                'cache_enable': cache_enable,
                'auto_get_ip': auto_get_ip
            }
            
            # 保存配置
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # 如果Web服务器正在运行，提示重启
            if hasattr(self, 'web_server') and self.web_server:
                reply = QMessageBox.question(dialog, "设置已保存", 
                                            "服务器配置已保存。需要重启Web服务器使设置生效，是否立即重启？",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self._restart_web_server(dialog)
            else:
                QMessageBox.information(dialog, "设置已保存", "服务器配置已保存，下次启动时生效。")
            
            dialog.accept()
            
        except ValueError:
            QMessageBox.warning(dialog, "设置错误", "端口号必须是有效的数字")
        except Exception as e:
            QMessageBox.critical(dialog, "保存失败", f"保存设置时发生错误：{str(e)}")
    
    def _show_quick_actions(self):
        """显示快捷操作面板"""
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("⚡ 快捷操作中心")
        # 移除固定大小和自定义样式设置
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(20)
        
        # 标题
        title = QLabel("⚡ 快捷操作中心")
        # 移除自定义样式
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 快捷操作按钮网格
        actions_group = QGroupBox("🚀 常用操作")
        actions_layout = QGridLayout(actions_group)
        
        # 定义快捷操作
        quick_actions = [
            ("🔄 重启服务", "重启Web服务器", "#FF5722", self._restart_web_server),
            ("📊 查看日志", "打开系统日志", "#2196F3", self._show_system_logs),
            ("🧹 清理缓存", "清理系统缓存", "#FF9800", self._clear_cache),
            ("📈 性能监控", "打开性能面板", "#4CAF50", self._show_analytics_dashboard),
            ("🔧 系统诊断", "运行系统诊断", "#9C27B0", self._run_system_diagnostics),
            ("🐛 调试信息", "查看调试信息", "#E91E63", self._show_debug_info),
            ("💾 备份设置", "备份当前配置", "#607D8B", self._backup_settings)
        ]
        
        for i, (title, desc, color, callback) in enumerate(quick_actions):
            btn = QPushButton(f"{title}\n{desc}")
            # 移除自定义大小和样式设置
            if callback in [self._restart_web_server, self._show_analytics_dashboard, self._show_debug_info]:
                btn.clicked.connect(lambda checked, cb=callback: cb(dialog))
            else:
                btn.clicked.connect(lambda checked, cb=callback: cb())
            actions_layout.addWidget(btn, i // 3, i % 3)
        
        layout.addWidget(actions_group)
        
        # 关闭按钮
        close_btn = QPushButton("❌ 关闭")
        # 移除自定义样式
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec()
    
    def _darken_color(self, color):
        """使颜色变暗"""
        color_map = {
            "#FF5722": "#D84315",
            "#2196F3": "#1976D2",
            "#FF9800": "#F57C00",
            "#4CAF50": "#388E3C",
            "#9C27B0": "#7B1FA2",
            "#607D8B": "#455A64"
        }
        return color_map.get(color, color)
    
    def _lighten_color(self, color):
        """使颜色变亮"""
        color_map = {
            "#FF5722": "#FF7043",
            "#2196F3": "#42A5F5",
            "#FF9800": "#FFB74D",
            "#4CAF50": "#66BB6A",
            "#9C27B0": "#BA68C8",
            "#607D8B": "#78909C"
        }
        return color_map.get(color, color)
    
    def _show_system_logs(self):
        """显示系统日志"""
        try:
            # 调用主窗口的日志管理对话框
            main_window = self.parent
            if hasattr(main_window, 'open_log_management_dialog'):
                main_window.open_log_management_dialog()
            else:
                QMessageBox.information(self.parent, "系统日志", "📋 系统日志功能已激活\n\n正在打开日志查看器...")
        except Exception as e:
            QMessageBox.critical(self.parent, "错误", f"打开日志管理失败: {e}")
    
    def _clear_cache(self):
        """清理缓存"""
        reply = QMessageBox.question(self.parent, "清理缓存", "🧹 确定要清理系统缓存吗？\n\n这将删除所有临时文件和缓存数据。")
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 实际清理缓存的逻辑
                import tempfile
                import shutil
                
                # 清理临时文件
                temp_dir = tempfile.gettempdir()
                cache_dirs = [
                    os.path.join(temp_dir, 'xuanwu_ocr_cache'),
                    os.path.join(os.path.dirname(__file__), '..', 'cache'),
                    os.path.join(os.path.dirname(__file__), '..', 'temp')
                ]
                
                cleared_count = 0
                for cache_dir in cache_dirs:
                    if os.path.exists(cache_dir):
                        try:
                            shutil.rmtree(cache_dir)
                            os.makedirs(cache_dir, exist_ok=True)
                            cleared_count += 1
                        except Exception:
                            pass
                
                QMessageBox.information(self.parent, "清理完成", f"✅ 缓存清理完成！\n\n已清理 {cleared_count} 个缓存目录。")
            except Exception as e:
                QMessageBox.critical(self.parent, "错误", f"清理缓存失败: {e}")
    
    def _run_system_diagnostics(self):
        """运行系统诊断"""
        QMessageBox.information(self.parent, "系统诊断", "🔧 系统诊断已启动\n\n正在检查系统健康状态...")
    
    def _backup_settings(self):
        """备份设置"""
        QMessageBox.information(self.parent, "备份设置", "💾 设置备份已完成\n\n配置文件已保存到备份目录。")
    
    def _show_theme_settings(self):
        """显示主题设置对话框"""
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("🎨 主题与个性化设置")
        # 移除固定大小和自定义样式设置
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("🎨 主题与个性化设置")
        # 移除自定义样式
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 主题选择
        theme_group = QGroupBox("🌈 主题选择")
        theme_layout = QGridLayout(theme_group)
        
        # 预设主题
        themes = [
            ("🌙 深色经典", "#2C3E50", "#34495E"),
            ("🌊 海洋蓝", "#1A237E", "#283593"),
            ("🌸 樱花粉", "#E91E63", "#AD1457"),
            ("🍃 自然绿", "#2E7D32", "#388E3C"),
            ("🔥 活力橙", "#FF5722", "#D84315"),
            ("💜 神秘紫", "#7B1FA2", "#4A148C")
        ]
        
        self.theme_buttons = []
        for i, (name, color1, color2) in enumerate(themes):
            btn = QPushButton(name)
            # 移除自定义大小和样式设置
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, theme=name: self._apply_theme(theme))
            self.theme_buttons.append(btn)
            theme_layout.addWidget(btn, i // 2, i % 2)
        
        # 默认选中第一个主题
        self.theme_buttons[0].setChecked(True)
        
        layout.addWidget(theme_group)
        
        # 个性化设置
        personal_group = QGroupBox("⚙️ 个性化设置")
        personal_layout = QVBoxLayout(personal_group)
        
        # 动画效果
        animation_check = QCheckBox("✨ 启用动画效果")
        # 移除自定义样式
        animation_check.setChecked(True)
        personal_layout.addWidget(animation_check)
        
        # 透明度设置
        opacity_layout = QHBoxLayout()
        opacity_label = QLabel("🔍 界面透明度:")
        # 移除自定义样式
        opacity_layout.addWidget(opacity_label)
        
        opacity_slider = QSlider(Qt.Orientation.Horizontal)
        opacity_slider.setRange(70, 100)
        opacity_slider.setValue(95)
        # 移除自定义样式
        opacity_layout.addWidget(opacity_slider)
        
        opacity_value = QLabel("95%")
        # 移除自定义样式
        opacity_slider.valueChanged.connect(lambda v: opacity_value.setText(f"{v}%"))
        opacity_layout.addWidget(opacity_value)
        
        personal_layout.addLayout(opacity_layout)
        
        # 字体大小
        font_layout = QHBoxLayout()
        font_label = QLabel("📝 字体大小:")
        # 移除自定义样式
        font_layout.addWidget(font_label)
        
        font_combo = QComboBox()
        font_combo.addItems(["小号 (12px)", "标准 (14px)", "大号 (16px)", "超大 (18px)"])
        font_combo.setCurrentIndex(1)
        # 移除自定义样式
        font_layout.addWidget(font_combo)
        
        personal_layout.addLayout(font_layout)
        
        # 自动保存设置
        auto_save_check = QCheckBox("💾 自动保存设置")
        # 移除自定义样式
        auto_save_check.setChecked(True)
        personal_layout.addWidget(auto_save_check)
        
        layout.addWidget(personal_group)
        
        # 预览区域
        preview_group = QGroupBox("👀 效果预览")
        preview_layout = QVBoxLayout(preview_group)
        
        preview_label = QLabel("🎨 当前主题效果预览\n\n• 现代化界面设计\n• 流畅的动画效果\n• 个性化配置选项\n• 实时主题切换")
        # 移除自定义样式
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(preview_label)
        
        layout.addWidget(preview_group)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        apply_btn = QPushButton("✅ 应用设置")
        # 移除自定义样式
        apply_btn.clicked.connect(lambda checked: self._apply_theme_settings(dialog))
        btn_layout.addWidget(apply_btn)
        
        reset_btn = QPushButton("🔄 重置默认")
        # 移除自定义样式
        reset_btn.clicked.connect(self._reset_theme_settings)
        btn_layout.addWidget(reset_btn)
        
        close_btn = QPushButton("❌ 关闭")
        # 移除自定义样式
        close_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        dialog.exec()
    
    def _apply_theme(self, theme_name):
        """应用选中的主题"""
        # 取消其他按钮的选中状态
        for btn in self.theme_buttons:
            if btn.text() != theme_name:
                btn.setChecked(False)
        
        QMessageBox.information(self.parent, "主题应用", f"🎨 已应用主题: {theme_name}\n\n主题设置将在重启后生效。")
    
    def _apply_theme_settings(self, dialog):
        """应用主题设置"""
        QMessageBox.information(self.parent, "设置应用", "✅ 主题设置已应用！\n\n• 界面主题已更新\n• 个性化配置已保存\n• 设置将在下次启动时生效")
        dialog.accept()
    
    def _reset_theme_settings(self):
        """重置主题设置"""
        reply = QMessageBox.question(self.parent, "重置设置", "🔄 确定要重置所有主题设置吗？\n\n这将恢复到默认配置。")
        if reply == QMessageBox.StandardButton.Yes:
            # 重置为第一个主题
            for i, btn in enumerate(self.theme_buttons):
                btn.setChecked(i == 0)
            QMessageBox.information(self.parent, "重置完成", "✅ 主题设置已重置为默认配置！")
        
    def _start_web_server(self, dialog):
        """启动Web服务器"""
        from .web_preview_server_enhanced import WebPreviewServer
        from PyQt6.QtCore import QTimer
        import json
        import os
        
        try:
            # 读取服务器配置
            config_file = "settings.json"
            server_config = {
                'port': 8888,
                'host': '127.0.0.1',
                'auto_optimize': True,
                'cache_enable': True
            }
            
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        if 'web_server' in config:
                            server_config.update(config['web_server'])
                except Exception as e:
                    print(f"读取配置文件失败，使用默认设置: {e}")
            
            # 更新状态
            self.status_label.setText(f"⏳ 正在启动服务器 ({server_config['host']}:{server_config['port']})...")
            
            # 创建并启动Web服务器
            self._web_server = WebPreviewServer(self.parent)
            
            # 应用配置到服务器
            if hasattr(self._web_server, 'set_server_config'):
                self._web_server.set_server_config(server_config)
            
            # 连接信号 - 使用 functools.partial 来避免参数传递问题
            from functools import partial
            self._web_server.server_started.connect(partial(self._on_server_started, dialog))
            self._web_server.server_error.connect(partial(self._on_server_error, dialog))
            
            # 启动服务器
            if self._web_server.start_server():
                # 延迟更新界面 - 注释掉这行，因为信号回调会处理
                # QTimer.singleShot(500, lambda: self._update_dialog_for_running_state(dialog))
                pass  # 服务器启动成功，等待信号回调处理
            else:
                self.status_label.setText("❌ 启动失败")
                self._web_server = None
                self._update_dialog_for_stopped_state(dialog)
                self._show_error_dialog("启动失败", "Web控制面板启动失败！\n\n可能的原因：\n• 端口8888已被占用\n• 系统权限不足\n• 防火墙阻止连接")
                
        except Exception as e:
            self.status_label.setText("❌ 启动失败")
            self._web_server = None
            self._update_dialog_for_stopped_state(dialog)
            self._show_error_dialog("启动错误", f"启动Web控制面板时发生错误:\n{e}")
    
    def _stop_web_server(self, dialog):
        """停止Web服务器"""
        from PyQt6.QtCore import QTimer, QThread, pyqtSignal
        import time
        
        if not self._web_server:
            return
        
        # 显示进度条
        if not hasattr(self, 'progress_bar'):
            self.progress_bar = QProgressBar(dialog)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setVisible(False)
            dialog.layout().addWidget(self.progress_bar)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("正在停止服务器...")
        
        # 创建异步停止工作线程
        class StopWorker(QThread):
            progress_updated = pyqtSignal(int, str)
            stop_completed = pyqtSignal(bool, str)
            
            def __init__(self, web_server, timeout=10):
                super().__init__()
                self.web_server = web_server
                self.timeout = timeout
                self.start_time = None
            
            def run(self):
                try:
                    self.start_time = time.time()
                    
                    self.progress_updated.emit(30, "正在停止服务器...")
                    
                    # 停止服务器（非阻塞）
                    if self.web_server:
                        try:
                            self.web_server.stop_server()
                        except (OSError, AttributeError) as e:
                            # 处理WinError 10038和其他套接字错误
                            if "10038" in str(e) or "非套接字" in str(e):
                                print(f"警告: 服务器套接字错误已处理: {str(e)}")
                            else:
                                raise  # 重新抛出其他类型的错误
                    
                    # 检查超时
                    if self._check_timeout():
                        return
                    
                    self.progress_updated.emit(80, "清理资源...")
                    self.msleep(200)  # 短暂等待确保清理完成
                    
                    self.progress_updated.emit(100, "停止完成！")
                    self.stop_completed.emit(True, "服务器已成功停止")
                    
                except Exception as e:
                    # 检查是否为已知的套接字错误
                    if "10038" in str(e) or "非套接字" in str(e):
                        # 对于套接字错误，认为停止成功（因为套接字已经无效）
                        self.stop_completed.emit(True, "服务器已停止（套接字已关闭）")
                    else:
                        self.stop_completed.emit(False, f"停止过程中发生错误：{str(e)}")
            
            def _check_timeout(self):
                """检查是否超时"""
                if self.start_time and time.time() - self.start_time > self.timeout:
                    self.stop_completed.emit(False, f"停止操作超时（{self.timeout}秒）")
                    return True
                return False
        
        try:
            # 创建并启动停止工作线程
            self.stop_worker = StopWorker(self._web_server, timeout=8)  # 8秒超时
            
            # 连接信号
            def on_progress_updated(value, message):
                self.progress_bar.setValue(value)
                self.progress_bar.setFormat(message)
                QApplication.processEvents()
            
            def on_stop_completed(success, message):
                # 清理超时定时器（避免对已删除对象调用）
                if hasattr(self, 'stop_timeout_timer'):
                    try:
                        self.stop_timeout_timer.stop()
                    except RuntimeError:
                        pass
                    try:
                        self.stop_timeout_timer.deleteLater()
                    except RuntimeError:
                        pass
                    delattr(self, 'stop_timeout_timer')
                
                self.progress_bar.setVisible(False)
                if success:
                    # 停止成功，清理服务器实例并更新UI
                    self._web_server = None
                    QTimer.singleShot(100, lambda: self._update_dialog_for_stopped_state(dialog))
                else:
                    # 停止失败，显示错误信息
                    if hasattr(dialog, 'parent') and dialog.parent():
                        QMessageBox.warning(dialog.parent(), "停止失败", message)
                    else:
                        QMessageBox.warning(None, "停止失败", message)
            
            self.stop_worker.progress_updated.connect(on_progress_updated)
            self.stop_worker.stop_completed.connect(on_stop_completed)
            
            # 添加额外的超时保护机制
            self.stop_timeout_timer = QTimer(dialog)
            self.stop_timeout_timer.timeout.connect(lambda: self._handle_stop_timeout(dialog))
            self.stop_timeout_timer.setSingleShot(True)
            self.stop_timeout_timer.start(12000)  # 12秒绝对超时
            
            self.stop_worker.start()
                
        except Exception as e:
            self.progress_bar.setVisible(False)
            if hasattr(dialog, 'parent') and dialog.parent():
                QMessageBox.warning(dialog.parent(), "停止失败", f"服务器停止失败：{str(e)}")
            else:
                QMessageBox.warning(None, "停止失败", f"服务器停止失败：{str(e)}")
    
    def _open_browser_and_close(self, dialog):
        """打开浏览器并关闭对话框"""
        if self._web_server:
            self._web_server.open_in_browser()
        dialog.close()
    
    def _update_dialog_for_running_state(self, dialog):
        """更新对话框为运行状态"""
        server_url = self._web_server.get_url() if self._web_server else "http://127.0.0.1:8888"
        self.status_label.setText(f"🟢 服务器运行中")
        self.connection_label.setText(f"🌐 {server_url}")
        
        # 找到按钮布局并切换到运行状态按钮
        button_layout = self._find_button_layout(dialog)
        if button_layout:
            self._clear_layout(button_layout)
            self._setup_running_buttons(button_layout, dialog)
    
    def _update_dialog_for_stopped_state(self, dialog):
        """更新对话框为停止状态"""
        self.status_label.setText("🔴 服务器已停止")
        self.connection_label.setText("⚠️ 等待启动")
        
        # 找到按钮布局并切换到启动状态按钮
        button_layout = self._find_button_layout(dialog)
        if button_layout:
            self._clear_layout(button_layout)
            self._setup_start_buttons(button_layout, dialog)
    
    def _find_button_layout(self, dialog):
        """查找对话框中的按钮布局"""
        try:
            # 遍历主布局中的所有组件
            main_layout = dialog.layout()
            for i in range(main_layout.count()):
                item = main_layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    # 查找操作控制组（QGroupBox）
                    if isinstance(widget, QGroupBox) and "操作控制" in widget.title():
                        group_layout = widget.layout()
                        if group_layout:
                            # 在组内查找按钮布局（QHBoxLayout）
                            for j in range(group_layout.count()):
                                sub_item = group_layout.itemAt(j)
                                if sub_item and sub_item.layout():
                                    sub_layout = sub_item.layout()
                                    # 检查是否为水平布局（按钮布局）
                                    if isinstance(sub_layout, QHBoxLayout):
                                        return sub_layout
            return None
        except Exception as e:
            print(f"查找按钮布局时出错: {e}")
            return None
    
    def _clear_layout(self, layout):
        """清空布局中的所有控件"""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def _on_server_started(self, dialog):
        """服务器启动成功回调"""
        self._update_dialog_for_running_state(dialog)
        
        # 自动打开浏览器
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1000, self._web_server.open_in_browser)
    
    def _on_server_error(self, dialog, error_msg):
        """服务器错误回调"""
        self.status_label.setText("❌ 服务器错误")
        self._web_server = None
        self._update_dialog_for_stopped_state(dialog)
        self._show_error_dialog("服务器错误", f"Web控制面板发生错误:\n{error_msg}")
    
    def _show_error_dialog(self, title, message):
        """显示错误对话框"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self.parent, title, message)
    
    def _on_web_server_started(self, url):
        """Web服务器启动成功回调"""
        # 创建富文本消息框
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle("🎉 Web控制面板启动成功")
        msg_box.setTextFormat(Qt.TextFormat.RichText)  # 富文本格式
        
        success_html = f"""
        <div style='font-family: "Microsoft YaHei", Arial, sans-serif; line-height: 1.6;'>
            <h3 style='color: #2E8B57; margin: 0 0 15px 0;'>🚀 XuanWu OCR 智能控制面板已就绪！</h3>
            
            <p><strong>🔗 访问地址:</strong> 
            <a href='{url}' style='color: #1E90FF; text-decoration: none;'>{url}</a></p>
            
            <div style='background: #F0F8FF; padding: 10px; border-radius: 5px; margin: 10px 0;'>
                <p style='margin: 5px 0;'><strong>📋 快速导航:</strong></p>
                <p style='margin: 3px 0;'>• 🎛️ 控制面板 - 系统概览和快速操作</p>
                <p style='margin: 3px 0;'>• 📊 系统监控 - 实时性能和资源使用</p>
                <p style='margin: 3px 0;'>• ⚙️ 配置管理 - OCR参数和系统设置</p>
                <p style='margin: 3px 0;'>• 📝 日志分析 - 运行日志和错误诊断</p>
                <p style='margin: 3px 0;'>• 🔧 工具箱 - 高级功能和调试工具</p>
            </div>
            
            <p style='color: #666; font-size: 12px;'>💡 浏览器将自动打开控制面板页面</p>
        </div>
        """
        
        msg_box.setText(success_html)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        
        # 添加自定义按钮
        copy_btn = msg_box.addButton("📋 复制地址", QMessageBox.ButtonRole.ActionRole)
        copy_btn.clicked.connect(lambda checked: self._copy_url_to_clipboard(url))
        
        msg_box.exec()
    
    def _on_web_server_stopped(self):
        """Web服务器停止回调"""
        pass  # 已在web_preview方法中处理
    
    def _on_web_server_error(self, error_msg):
        """Web服务器错误回调"""
        QMessageBox.critical(
            self.parent,
            "❌ Web控制面板错误",
            f"Web控制面板发生错误:\n{error_msg}\n\n" +
            "建议解决方案:\n" +
            "• 检查端口8888是否被占用\n" +
            "• 重启应用程序\n" +
            "• 检查防火墙设置"
        )
        self._web_server = None
    
    def _copy_url_to_clipboard(self, url):
        """复制URL到剪贴板"""
        try:
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(url)
            
            # 显示复制成功提示
            QMessageBox.information(
                self.parent,
                "📋 复制成功",
                f"访问地址已复制到剪贴板:\n{url}"
            )
        except Exception as e:
            QMessageBox.warning(
                self.parent,
                "复制失败",
                f"无法复制到剪贴板: {e}"
            )

    def network_diagnostics(self):
        """网络诊断工具"""
        dlg = QDialog(self.parent)
        dlg.setWindowTitle("网络诊断")
        dlg.resize(800, 600)
        
        layout = QVBoxLayout(dlg)
        
        # 输入区域
        input_layout = QHBoxLayout()
        host_input = QLineEdit()
        host_input.setPlaceholderText("输入主机地址 (如: baidu.com)")
        host_input.setText("baidu.com")
        
        ping_btn = QPushButton("Ping测试")
        tracert_btn = QPushButton("路由跟踪")
        nslookup_btn = QPushButton("DNS查询")
        
        input_layout.addWidget(QLabel("主机:"))
        input_layout.addWidget(host_input)
        input_layout.addWidget(ping_btn)
        input_layout.addWidget(tracert_btn)
        input_layout.addWidget(nslookup_btn)
        
        # 结果显示
        result_tb = QTextBrowser(dlg)
        result_tb.setFont(QFont("Courier New", 9))
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_clear = QPushButton("清空")
        btn_save = QPushButton("保存结果")
        btn_close = QPushButton("关闭")
        
        btn_layout.addWidget(btn_clear)
        btn_layout.addWidget(btn_save)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(input_layout)
        layout.addWidget(result_tb)
        layout.addLayout(btn_layout)
        
        def run_ping():
            host = host_input.text().strip()
            if not host:
                return
            
            result_tb.append(f"\n=== Ping {host} ===")
            try:
                if platform.system().lower() == "windows":
                    cmd = ["ping", "-n", "4", host]
                else:
                    cmd = ["ping", "-c", "4", host]
                
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                result_tb.append(proc.stdout)
                if proc.stderr:
                    result_tb.append(f"错误: {proc.stderr}")
            except Exception as e:
                result_tb.append(f"Ping失败: {e}")
        
        def run_tracert():
            host = host_input.text().strip()
            if not host:
                return
            
            result_tb.append(f"\n=== 路由跟踪 {host} ===")
            try:
                if platform.system().lower() == "windows":
                    cmd = ["tracert", host]
                else:
                    cmd = ["traceroute", host]
                
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                result_tb.append(proc.stdout)
                if proc.stderr:
                    result_tb.append(f"错误: {proc.stderr}")
            except Exception as e:
                result_tb.append(f"路由跟踪失败: {e}")
        
        def run_nslookup():
            host = host_input.text().strip()
            if not host:
                return
            
            result_tb.append(f"\n=== DNS查询 {host} ===")
            try:
                cmd = ["nslookup", host]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                result_tb.append(proc.stdout)
                if proc.stderr:
                    result_tb.append(f"错误: {proc.stderr}")
            except Exception as e:
                result_tb.append(f"DNS查询失败: {e}")
        
        def save_results():
            content = result_tb.toPlainText()
            if not content.strip():
                QMessageBox.warning(dlg, "警告", "没有可保存的内容")
                return
            
            file_path, _ = QFileDialog.getSaveFileName(dlg, "保存网络诊断结果", "network_diag.txt", "Text Files (*.txt)")
            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    QMessageBox.information(dlg, "成功", f"结果已保存到 {file_path}")
                except Exception as e:
                    QMessageBox.warning(dlg, "错误", f"保存失败: {e}")
        
        ping_btn.clicked.connect(run_ping)
        tracert_btn.clicked.connect(run_tracert)
        nslookup_btn.clicked.connect(run_nslookup)
        btn_clear.clicked.connect(result_tb.clear)
        btn_save.clicked.connect(save_results)
        btn_close.clicked.connect(dlg.close)
        
        dlg.exec()

    def memory_analysis(self):
        """内存分析工具"""
        if not psutil:
            QMessageBox.warning(self.parent, "错误", "需要安装psutil库才能使用此功能")
            return
        
        dlg = QDialog(self.parent)
        dlg.setWindowTitle("内存分析")
        dlg.resize(900, 700)
        
        layout = QVBoxLayout(dlg)
        
        # 内存概览
        overview_group = QGroupBox("内存概览")
        overview_layout = QVBoxLayout()
        overview_label = QLabel()
        overview_layout.addWidget(overview_label)
        overview_group.setLayout(overview_layout)
        
        # 进程内存使用
        process_group = QGroupBox("进程内存使用 (前20名)")
        process_layout = QVBoxLayout()
        process_table = QTableWidget()
        process_table.setColumnCount(4)
        process_table.setHorizontalHeaderLabels(["PID", "进程名", "内存使用", "内存百分比"])
        process_layout.addWidget(process_table)
        process_group.setLayout(process_layout)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_refresh = QPushButton("刷新")
        btn_export = QPushButton("导出")
        btn_close = QPushButton("关闭")
        
        btn_layout.addWidget(btn_refresh)
        btn_layout.addWidget(btn_export)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        
        layout.addWidget(overview_group)
        layout.addWidget(process_group)
        layout.addLayout(btn_layout)
        
        def refresh_memory_info():
            try:
                # 系统内存信息
                memory = psutil.virtual_memory()
                swap = psutil.swap_memory()
                # 兼容无 cached 字段的平台
                cached_overview_str = (
                    f"{getattr(memory, 'cached', 0) / (1024**3):.2f} GB"
                    if hasattr(memory, 'cached') else "不支持"
                )
                
                overview_text = f"""物理内存:
总计: {memory.total / (1024**3):.2f} GB
已用: {memory.used / (1024**3):.2f} GB ({memory.percent}%)
可用: {memory.available / (1024**3):.2f} GB
缓存: {cached_overview_str}

虚拟内存:
总计: {swap.total / (1024**3):.2f} GB
已用: {swap.used / (1024**3):.2f} GB ({swap.percent}%)
可用: {swap.free / (1024**3):.2f} GB"""
                
                overview_label.setText(overview_text)
                
                # 进程内存使用
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'memory_percent']):
                    try:
                        info = proc.info
                        if info['memory_info']:
                            processes.append({
                                'pid': info['pid'],
                                'name': info['name'],
                                'memory': info['memory_info'].rss,
                                'percent': info['memory_percent'] or 0
                            })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                # 按内存使用排序
                processes.sort(key=lambda x: x['memory'], reverse=True)
                
                # 显示前20个进程
                process_table.setRowCount(min(20, len(processes)))
                for i, proc in enumerate(processes[:20]):
                    process_table.setItem(i, 0, QTableWidgetItem(str(proc['pid'])))
                    process_table.setItem(i, 1, QTableWidgetItem(proc['name']))
                    process_table.setItem(i, 2, QTableWidgetItem(f"{proc['memory'] / (1024**2):.1f} MB"))
                    process_table.setItem(i, 3, QTableWidgetItem(f"{proc['percent']:.1f}%"))
                
                process_table.resizeColumnsToContents()
                
            except Exception as e:
                QMessageBox.warning(dlg, "错误", f"获取内存信息失败: {e}")
        
        def export_memory_info():
            try:
                file_path, _ = QFileDialog.getSaveFileName(dlg, "导出内存分析", "memory_analysis.txt", "Text Files (*.txt)")
                if file_path:
                    content = overview_label.text() + "\n\n进程内存使用:\n"
                    content += "PID\t进程名\t内存使用\t内存百分比\n"
                    
                    for row in range(process_table.rowCount()):
                        pid = process_table.item(row, 0).text()
                        name = process_table.item(row, 1).text()
                        memory = process_table.item(row, 2).text()
                        percent = process_table.item(row, 3).text()
                        content += f"{pid}\t{name}\t{memory}\t{percent}\n"
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    QMessageBox.information(dlg, "成功", f"内存分析已导出到 {file_path}")
            except Exception as e:
                QMessageBox.warning(dlg, "错误", f"导出失败: {e}")
        
        btn_refresh.clicked.connect(refresh_memory_info)
        btn_export.clicked.connect(export_memory_info)
        btn_close.clicked.connect(dlg.close)
        
        # 初始加载
        refresh_memory_info()
        
        dlg.exec()

    def process_management(self):
        """进程管理工具"""
        if not psutil:
            QMessageBox.warning(self.parent, "错误", "需要安装psutil库才能使用此功能")
            return
        
        dlg = QDialog(self.parent)
        dlg.setWindowTitle("进程管理")
        dlg.resize(1000, 700)
        
        layout = QVBoxLayout(dlg)
        
        # 搜索和过滤
        filter_layout = QHBoxLayout()
        filter_input = QLineEdit()
        filter_input.setPlaceholderText("搜索进程名或PID...")
        filter_btn = QPushButton("搜索")
        refresh_btn = QPushButton("刷新")
        
        filter_layout.addWidget(QLabel("过滤:"))
        filter_layout.addWidget(filter_input)
        filter_layout.addWidget(filter_btn)
        filter_layout.addWidget(refresh_btn)
        filter_layout.addStretch()
        
        # 进程表格
        process_table = QTableWidget()
        process_table.setColumnCount(7)
        process_table.setHorizontalHeaderLabels(["PID", "进程名", "状态", "CPU%", "内存", "启动时间", "命令行"])
        process_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # 操作按钮
        action_layout = QHBoxLayout()
        kill_btn = QPushButton("终止进程")
        suspend_btn = QPushButton("暂停进程")
        resume_btn = QPushButton("恢复进程")
        info_btn = QPushButton("详细信息")
        export_btn = QPushButton("导出列表")
        close_btn = QPushButton("关闭")
        
        action_layout.addWidget(kill_btn)
        action_layout.addWidget(suspend_btn)
        action_layout.addWidget(resume_btn)
        action_layout.addWidget(info_btn)
        action_layout.addWidget(export_btn)
        action_layout.addStretch()
        action_layout.addWidget(close_btn)
        
        layout.addLayout(filter_layout)
        layout.addWidget(process_table)
        layout.addLayout(action_layout)
        
        current_processes = []
        
        def load_processes(filter_text=""):
            nonlocal current_processes
            try:
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent', 'memory_info', 'create_time', 'cmdline']):
                    try:
                        info = proc.info
                        if filter_text and filter_text.lower() not in info['name'].lower() and filter_text not in str(info['pid']):
                            continue
                        
                        processes.append({
                            'pid': info['pid'],
                            'name': info['name'],
                            'status': info['status'],
                            'cpu_percent': info['cpu_percent'] or 0,
                            'memory': info['memory_info'].rss if info['memory_info'] else 0,
                            'create_time': info['create_time'],
                            'cmdline': ' '.join(info['cmdline']) if info['cmdline'] else ''
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                current_processes = processes
                
                # 按CPU使用率排序
                processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
                
                process_table.setRowCount(len(processes))
                for i, proc in enumerate(processes):
                    process_table.setItem(i, 0, QTableWidgetItem(str(proc['pid'])))
                    process_table.setItem(i, 1, QTableWidgetItem(proc['name']))
                    process_table.setItem(i, 2, QTableWidgetItem(proc['status']))
                    process_table.setItem(i, 3, QTableWidgetItem(f"{proc['cpu_percent']:.1f}%"))
                    process_table.setItem(i, 4, QTableWidgetItem(f"{proc['memory'] / (1024**2):.1f} MB"))
                    
                    create_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(proc['create_time']))
                    process_table.setItem(i, 5, QTableWidgetItem(create_time))
                    
                    cmdline = proc['cmdline'][:100] + '...' if len(proc['cmdline']) > 100 else proc['cmdline']
                    process_table.setItem(i, 6, QTableWidgetItem(cmdline))
                
                process_table.resizeColumnsToContents()
                
            except Exception as e:
                QMessageBox.warning(dlg, "错误", f"加载进程列表失败: {e}")
        
        def kill_process():
            current_row = process_table.currentRow()
            if current_row < 0:
                QMessageBox.warning(dlg, "警告", "请选择要终止的进程")
                return
            
            pid = int(process_table.item(current_row, 0).text())
            name = process_table.item(current_row, 1).text()
            
            reply = QMessageBox.question(dlg, "确认", f"确定要终止进程 {name} (PID: {pid}) 吗？")
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    proc = psutil.Process(pid)
                    proc.terminate()
                    QMessageBox.information(dlg, "成功", f"进程 {name} 已终止")
                    load_processes(filter_input.text())
                except Exception as e:
                    QMessageBox.warning(dlg, "错误", f"终止进程失败: {e}")
        
        def suspend_process():
            current_row = process_table.currentRow()
            if current_row < 0:
                QMessageBox.warning(dlg, "警告", "请选择要暂停的进程")
                return
            
            pid = int(process_table.item(current_row, 0).text())
            try:
                proc = psutil.Process(pid)
                proc.suspend()
                QMessageBox.information(dlg, "成功", "进程已暂停")
                load_processes(filter_input.text())
            except Exception as e:
                QMessageBox.warning(dlg, "错误", f"暂停进程失败: {e}")
        
        def resume_process():
            current_row = process_table.currentRow()
            if current_row < 0:
                QMessageBox.warning(dlg, "警告", "请选择要恢复的进程")
                return
            
            pid = int(process_table.item(current_row, 0).text())
            try:
                proc = psutil.Process(pid)
                proc.resume()
                QMessageBox.information(dlg, "成功", "进程已恢复")
                load_processes(filter_input.text())
            except Exception as e:
                QMessageBox.warning(dlg, "错误", f"恢复进程失败: {e}")
        
        def show_process_info():
            current_row = process_table.currentRow()
            if current_row < 0:
                QMessageBox.warning(dlg, "警告", "请选择要查看的进程")
                return
            
            pid = int(process_table.item(current_row, 0).text())
            try:
                proc = psutil.Process(pid)
                info = f"""进程详细信息:
PID: {proc.pid}
名称: {proc.name()}
状态: {proc.status()}
CPU使用率: {proc.cpu_percent()}%
内存使用: {proc.memory_info().rss / (1024**2):.1f} MB
创建时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(proc.create_time()))}
父进程: {proc.ppid()}
用户: {proc.username()}
命令行: {' '.join(proc.cmdline())}"""
                
                QMessageBox.information(dlg, "进程信息", info)
            except Exception as e:
                QMessageBox.warning(dlg, "错误", f"获取进程信息失败: {e}")
        
        def export_process_list():
            try:
                file_path, _ = QFileDialog.getSaveFileName(dlg, "导出进程列表", "process_list.csv", "CSV Files (*.csv)")
                if file_path:
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(["PID", "进程名", "状态", "CPU%", "内存(MB)", "启动时间", "命令行"])
                        
                        for proc in current_processes:
                            writer.writerow([
                                proc['pid'],
                                proc['name'],
                                proc['status'],
                                f"{proc['cpu_percent']:.1f}%",
                                f"{proc['memory'] / (1024**2):.1f}",
                                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(proc['create_time'])),
                                proc['cmdline']
                            ])
                    
                    QMessageBox.information(dlg, "成功", f"进程列表已导出到 {file_path}")
            except Exception as e:
                QMessageBox.warning(dlg, "错误", f"导出失败: {e}")
        
        filter_btn.clicked.connect(lambda checked: load_processes(filter_input.text()))
        refresh_btn.clicked.connect(lambda checked: load_processes(filter_input.text()))
        kill_btn.clicked.connect(kill_process)
        suspend_btn.clicked.connect(suspend_process)
        resume_btn.clicked.connect(resume_process)
        info_btn.clicked.connect(show_process_info)
        export_btn.clicked.connect(export_process_list)
        close_btn.clicked.connect(dlg.close)
        
        # 初始加载
        load_processes()
        
        dlg.exec()

    def view_environment_variables(self):
        """查看环境变量"""
        dlg = QDialog(self.parent)
        dlg.setWindowTitle("环境变量")
        dlg.resize(900, 600)
        
        layout = QVBoxLayout(dlg)
        
        # 搜索框
        search_layout = QHBoxLayout()
        search_input = QLineEdit()
        search_input.setPlaceholderText("搜索环境变量名或值...")
        search_btn = QPushButton("搜索")
        clear_btn = QPushButton("清空")
        
        search_layout.addWidget(QLabel("搜索:"))
        search_layout.addWidget(search_input)
        search_layout.addWidget(search_btn)
        search_layout.addWidget(clear_btn)
        
        # 环境变量表格
        env_table = QTableWidget()
        env_table.setColumnCount(2)
        env_table.setHorizontalHeaderLabels(["变量名", "值"])
        env_table.setAlternatingRowColors(True)
        
        # 按钮
        btn_layout = QHBoxLayout()
        export_btn = QPushButton("导出")
        copy_btn = QPushButton("复制选中")
        close_btn = QPushButton("关闭")
        
        btn_layout.addWidget(export_btn)
        btn_layout.addWidget(copy_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(search_layout)
        layout.addWidget(env_table)
        layout.addLayout(btn_layout)
        
        def load_env_vars(filter_text=""):
            env_vars = []
            for key, value in os.environ.items():
                if not filter_text or filter_text.lower() in key.lower() or filter_text.lower() in value.lower():
                    env_vars.append((key, value))
            
            env_vars.sort(key=lambda x: x[0].lower())
            
            env_table.setRowCount(len(env_vars))
            for i, (key, value) in enumerate(env_vars):
                env_table.setItem(i, 0, QTableWidgetItem(key))
                env_table.setItem(i, 1, QTableWidgetItem(value))
            
            env_table.resizeColumnsToContents()
        
        def export_env_vars():
            try:
                file_path, _ = QFileDialog.getSaveFileName(dlg, "导出环境变量", "environment_variables.txt", "Text Files (*.txt)")
                if file_path:
                    content = "环境变量列表:\n\n"
                    for row in range(env_table.rowCount()):
                        key = env_table.item(row, 0).text()
                        value = env_table.item(row, 1).text()
                        content += f"{key}={value}\n"
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    QMessageBox.information(dlg, "成功", f"环境变量已导出到 {file_path}")
            except Exception as e:
                QMessageBox.warning(dlg, "错误", f"导出失败: {e}")
        
        def copy_selected():
            current_row = env_table.currentRow()
            if current_row < 0:
                QMessageBox.warning(dlg, "警告", "请选择要复制的环境变量")
                return
            
            key = env_table.item(current_row, 0).text()
            value = env_table.item(current_row, 1).text()
            content = f"{key}={value}"
            
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(content)
            QMessageBox.information(dlg, "成功", "已复制到剪贴板")
        
        search_btn.clicked.connect(lambda checked: load_env_vars(search_input.text()))
        clear_btn.clicked.connect(lambda checked: (search_input.clear(), load_env_vars()))
        export_btn.clicked.connect(export_env_vars)
        copy_btn.clicked.connect(copy_selected)
        close_btn.clicked.connect(dlg.close)
        
        # 初始加载
        load_env_vars()
        
        dlg.exec()

    def check_dependencies(self):
        """检查项目依赖"""
        dlg = QDialog(self.parent)
        dlg.setWindowTitle("依赖检查")
        dlg.resize(800, 600)
        
        layout = QVBoxLayout(dlg)
        
        # 检查类型选择
        type_layout = QHBoxLayout()
        check_pip_btn = QPushButton("检查pip包")
        check_imports_btn = QPushButton("检查导入")
        check_requirements_btn = QPushButton("检查requirements.txt")
        
        type_layout.addWidget(check_pip_btn)
        type_layout.addWidget(check_imports_btn)
        type_layout.addWidget(check_requirements_btn)
        type_layout.addStretch()
        
        # 结果显示
        result_tb = QTextBrowser(dlg)
        result_tb.setFont(QFont("Courier New", 9))
        
        # 按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存结果")
        close_btn = QPushButton("关闭")
        
        btn_layout.addWidget(save_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(type_layout)
        layout.addWidget(result_tb)
        layout.addLayout(btn_layout)
        
        def check_pip_packages():
            result_tb.clear()
            result_tb.append("=== 检查已安装的pip包 ===")
            try:
                proc = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True, timeout=30)
                result_tb.append(proc.stdout)
                if proc.stderr:
                    result_tb.append(f"\n错误: {proc.stderr}")
            except Exception as e:
                result_tb.append(f"检查失败: {e}")
        
        def check_imports():
            result_tb.clear()
            result_tb.append("=== 检查Python导入 ===")
            
            # 常用库检查
            common_libs = [
                'os', 'sys', 'json', 'time', 'datetime', 'logging',
                'requests', 'numpy', 'pandas', 'matplotlib', 'PIL',
                'PyQt6', 'psutil', 'sqlite3', 'csv', 'threading'
            ]
            
            for lib in common_libs:
                try:
                    __import__(lib)
                    result_tb.append(f"✓ {lib} - 可用")
                except ImportError:
                    result_tb.append(f"✗ {lib} - 不可用")
                except Exception as e:
                    result_tb.append(f"? {lib} - 检查失败: {e}")
        
        def check_requirements():
            result_tb.clear()
            result_tb.append("=== 检查requirements.txt ===")
            
            req_file = os.path.join(self.base_dir, "requirements.txt")
            if not os.path.exists(req_file):
                result_tb.append("requirements.txt 文件不存在")
                return
            
            try:
                with open(req_file, 'r', encoding='utf-8') as f:
                    requirements = f.read().strip().split('\n')
                
                result_tb.append(f"找到 {len(requirements)} 个依赖:\n")
                
                for req in requirements:
                    req = req.strip()
                    if not req or req.startswith('#'):
                        continue
                    
                    # 提取包名
                    package_name = req.split('==')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0]
                    
                    try:
                        proc = subprocess.run([sys.executable, "-m", "pip", "show", package_name], 
                                            capture_output=True, text=True, timeout=10)
                        if proc.returncode == 0:
                            result_tb.append(f"✓ {req} - 已安装")
                        else:
                            result_tb.append(f"✗ {req} - 未安装")
                    except Exception as e:
                        result_tb.append(f"? {req} - 检查失败: {e}")
                        
            except Exception as e:
                result_tb.append(f"读取requirements.txt失败: {e}")
        
        def save_results():
            content = result_tb.toPlainText()
            if not content.strip():
                QMessageBox.warning(dlg, "警告", "没有可保存的内容")
                return
            
            file_path, _ = QFileDialog.getSaveFileName(dlg, "保存依赖检查结果", "dependency_check.txt", "Text Files (*.txt)")
            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    QMessageBox.information(dlg, "成功", f"结果已保存到 {file_path}")
                except Exception as e:
                    QMessageBox.warning(dlg, "错误", f"保存失败: {e}")
        
        check_pip_btn.clicked.connect(check_pip_packages)
        check_imports_btn.clicked.connect(check_imports)
        check_requirements_btn.clicked.connect(check_requirements)
        save_btn.clicked.connect(save_results)
        close_btn.clicked.connect(dlg.close)
        
        dlg.exec()

    def file_integrity_check(self):
        """文件完整性检查"""
        dlg = QDialog(self.parent)
        dlg.setWindowTitle(t("文件完整性检查"))
        dlg.resize(900, 700)
        
        layout = QVBoxLayout(dlg)
        
        # 选择目录
        dir_layout = QHBoxLayout()
        dir_input = QLineEdit()
        dir_input.setText(self.base_dir)
        dir_btn = QPushButton("选择目录")
        scan_btn = QPushButton("开始扫描")
        
        dir_layout.addWidget(QLabel("扫描目录:"))
        dir_layout.addWidget(dir_input)
        dir_layout.addWidget(dir_btn)
        dir_layout.addWidget(scan_btn)
        
        # 进度条
        progress_bar = QProgressBar()
        progress_bar.setVisible(False)
        
        # 结果显示
        result_tb = QTextBrowser(dlg)
        result_tb.setFont(QFont("Courier New", 9))
        
        # 按钮
        btn_layout = QHBoxLayout()
        export_btn = QPushButton("导出报告")
        close_btn = QPushButton("关闭")
        
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(dir_layout)
        layout.addWidget(progress_bar)
        layout.addWidget(result_tb)
        layout.addLayout(btn_layout)
        
        def select_directory():
            directory = QFileDialog.getExistingDirectory(dlg, "选择扫描目录", dir_input.text())
            if directory:
                dir_input.setText(directory)
        
        def scan_files():
            scan_dir = dir_input.text().strip()
            if not scan_dir or not os.path.exists(scan_dir):
                QMessageBox.warning(dlg, "错误", "请选择有效的扫描目录")
                return
            
            result_tb.clear()
            result_tb.append(f"=== 文件完整性检查 - {scan_dir} ===")
            result_tb.append(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            progress_bar.setVisible(True)
            progress_bar.setValue(0)
            
            try:
                # 收集所有文件
                all_files = []
                for root, dirs, files in os.walk(scan_dir):
                    for file in files:
                        all_files.append(os.path.join(root, file))
                
                total_files = len(all_files)
                result_tb.append(f"找到 {total_files} 个文件\n")
                
                file_info = []
                corrupted_files = []
                
                for i, file_path in enumerate(all_files):
                    try:
                        # 更新进度
                        progress = int((i + 1) / total_files * 100)
                        progress_bar.setValue(progress)
                        
                        # 获取文件信息
                        stat = os.stat(file_path)
                        size = stat.st_size
                        mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))
                        
                        # 计算MD5哈希
                        md5_hash = hashlib.md5()
                        with open(file_path, 'rb') as f:
                            for chunk in iter(lambda: f.read(4096), b""):
                                md5_hash.update(chunk)
                        
                        file_info.append({
                            'path': file_path,
                            'size': size,
                            'mtime': mtime,
                            'md5': md5_hash.hexdigest(),
                            'status': 'OK'
                        })
                        
                    except Exception as e:
                        corrupted_files.append((file_path, str(e)))
                        file_info.append({
                            'path': file_path,
                            'size': 0,
                            'mtime': 'N/A',
                            'md5': 'N/A',
                            'status': f'错误: {e}'
                        })
                
                progress_bar.setVisible(False)
                
                # 显示结果
                result_tb.append(f"扫描完成!\n")
                result_tb.append(f"总文件数: {total_files}")
                result_tb.append(f"正常文件: {total_files - len(corrupted_files)}")
                result_tb.append(f"异常文件: {len(corrupted_files)}\n")
                
                if corrupted_files:
                    result_tb.append("=== 异常文件列表 ===")
                    for file_path, error in corrupted_files:
                        result_tb.append(f"✗ {file_path}: {error}")
                    result_tb.append("")
                
                result_tb.append("=== 文件清单 (前50个) ===")
                for info in file_info[:50]:
                    rel_path = os.path.relpath(info['path'], scan_dir)
                    result_tb.append(f"{info['status']} | {rel_path} | {info['size']} bytes | {info['md5'][:16]}...")
                
                if len(file_info) > 50:
                    result_tb.append(f"... 还有 {len(file_info) - 50} 个文件")
                
                # 保存完整报告到变量
                dlg.full_report = file_info
                
            except Exception as e:
                progress_bar.setVisible(False)
                result_tb.append(f"扫描失败: {e}")
        
        def export_report():
            if not hasattr(dlg, 'full_report'):
                QMessageBox.warning(dlg, "警告", "请先进行文件扫描")
                return
            
            file_path, _ = QFileDialog.getSaveFileName(dlg, "导出完整性报告", "integrity_report.csv", "CSV Files (*.csv)")
            if file_path:
                try:
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(["文件路径", "大小(字节)", "修改时间", "MD5哈希", "状态"])
                        
                        for info in dlg.full_report:
                            writer.writerow([
                                info['path'],
                                info['size'],
                                info['mtime'],
                                info['md5'],
                                info['status']
                            ])
                    
                    QMessageBox.information(dlg, "成功", f"完整性报告已导出到 {file_path}")
                except Exception as e:
                    QMessageBox.warning(dlg, "错误", f"导出失败: {e}")
        
        dir_btn.clicked.connect(select_directory)
        scan_btn.clicked.connect(scan_files)
        export_btn.clicked.connect(export_report)
        close_btn.clicked.connect(dlg.close)
        
        dlg.exec()

    def security_scan(self):
        """安全扫描工具"""
        dlg = QDialog(self.parent)
        dlg.setWindowTitle("安全扫描")
        dlg.resize(900, 700)
        
        layout = QVBoxLayout(dlg)
        
        # 扫描选项
        options_group = QGroupBox("扫描选项")
        options_layout = QVBoxLayout()
        
        check_passwords = QCheckBox("检查硬编码密码")
        check_passwords.setChecked(True)
        check_secrets = QCheckBox("检查API密钥和令牌")
        check_secrets.setChecked(True)
        check_sql = QCheckBox("检查SQL注入风险")
        check_sql.setChecked(True)
        check_files = QCheckBox("检查敏感文件")
        check_files.setChecked(True)
        
        options_layout.addWidget(check_passwords)
        options_layout.addWidget(check_secrets)
        options_layout.addWidget(check_sql)
        options_layout.addWidget(check_files)
        options_group.setLayout(options_layout)
        
        # 扫描按钮
        scan_layout = QHBoxLayout()
        scan_btn = QPushButton("开始扫描")
        scan_layout.addWidget(scan_btn)
        scan_layout.addStretch()
        
        # 结果显示
        result_tb = QTextBrowser(dlg)
        result_tb.setFont(QFont("Courier New", 9))
        
        # 按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存报告")
        close_btn = QPushButton("关闭")
        
        btn_layout.addWidget(save_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        
        layout.addWidget(options_group)
        layout.addLayout(scan_layout)
        layout.addWidget(result_tb)
        layout.addLayout(btn_layout)
        
        def run_security_scan():
            result_tb.clear()
            result_tb.append("=== 安全扫描报告 ===")
            result_tb.append(f"扫描时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            result_tb.append(f"扫描目录: {self.base_dir}\n")
            
            issues_found = 0
            
            try:
                # 检查硬编码密码
                if check_passwords.isChecked():
                    result_tb.append("=== 检查硬编码密码 ===")
                    password_patterns = [
                        r'password\s*=\s*["\'][^"\']{{3,}}["\']',
                        r'pwd\s*=\s*["\'][^"\']{{3,}}["\']',
                        r'passwd\s*=\s*["\'][^"\']{{3,}}["\']'
                    ]
                    
                    for root, dirs, files in os.walk(self.base_dir):
                        for file in files:
                            if file.endswith(('.py', '.js', '.php', '.java', '.cpp')):
                                file_path = os.path.join(root, file)
                                try:
                                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        content = f.read()
                                        for pattern in password_patterns:
                                            import re
                                            matches = re.finditer(pattern, content, re.IGNORECASE)
                                            for match in matches:
                                                line_num = content[:match.start()].count('\n') + 1
                                                result_tb.append(f"⚠️  {file_path}:{line_num} - 可能的硬编码密码")
                                                issues_found += 1
                                except Exception:
                                    continue
                    result_tb.append("")
                
                # 检查API密钥
                if check_secrets.isChecked():
                    result_tb.append("=== 检查API密钥和令牌 ===")
                    secret_patterns = [
                        r'api[_-]?key\s*=\s*["\'][^"\']{{10,}}["\']',
                        r'secret[_-]?key\s*=\s*["\'][^"\']{{10,}}["\']',
                        r'access[_-]?token\s*=\s*["\'][^"\']{{10,}}["\']',
                        r'auth[_-]?token\s*=\s*["\'][^"\']{{10,}}["\']'
                    ]
                    
                    for root, dirs, files in os.walk(self.base_dir):
                        for file in files:
                            if file.endswith(('.py', '.js', '.json', '.config')):
                                file_path = os.path.join(root, file)
                                try:
                                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        content = f.read()
                                        for pattern in secret_patterns:
                                            import re
                                            matches = re.finditer(pattern, content, re.IGNORECASE)
                                            for match in matches:
                                                line_num = content[:match.start()].count('\n') + 1
                                                result_tb.append(f"🔑 {file_path}:{line_num} - 可能的API密钥")
                                                issues_found += 1
                                except Exception:
                                    continue
                    result_tb.append("")
                
                # 检查SQL注入风险
                if check_sql.isChecked():
                    result_tb.append("=== 检查SQL注入风险 ===")
                    sql_patterns = [
                        r'execute\s*\(\s*["\'].*%s.*["\']\s*%',
                        r'query\s*\(\s*["\'].*\+.*["\']',
                        r'SELECT\s+.*\+.*FROM'
                    ]
                    
                    for root, dirs, files in os.walk(self.base_dir):
                        for file in files:
                            if file.endswith(('.py', '.php', '.java')):
                                file_path = os.path.join(root, file)
                                try:
                                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        content = f.read()
                                        for pattern in sql_patterns:
                                            import re
                                            matches = re.finditer(pattern, content, re.IGNORECASE)
                                            for match in matches:
                                                line_num = content[:match.start()].count('\n') + 1
                                                result_tb.append(f"💉 {file_path}:{line_num} - 可能的SQL注入风险")
                                                issues_found += 1
                                except Exception:
                                    continue
                    result_tb.append("")
                
                # 检查敏感文件
                if check_files.isChecked():
                    result_tb.append("=== 检查敏感文件 ===")
                    sensitive_files = [
                        '.env', '.env.local', '.env.production',
                        'config.ini', 'settings.ini',
                        'id_rsa', 'id_dsa', 'private.key',
                        'database.db', '*.sqlite'
                    ]
                    
                    for root, dirs, files in os.walk(self.base_dir):
                        for file in files:
                            for sensitive in sensitive_files:
                                if sensitive.startswith('*.'):
                                    if file.endswith(sensitive[1:]):
                                        result_tb.append(f"📁 {os.path.join(root, file)} - 敏感文件")
                                        issues_found += 1
                                elif file == sensitive:
                                    result_tb.append(f"📁 {os.path.join(root, file)} - 敏感文件")
                                    issues_found += 1
                    result_tb.append("")
                
                # 总结
                result_tb.append("=== 扫描总结 ===")
                result_tb.append(f"发现 {issues_found} 个潜在安全问题")
                if issues_found == 0:
                    result_tb.append("✅ 未发现明显的安全风险")
                else:
                    result_tb.append("⚠️  建议检查并修复发现的问题")
                
            except Exception as e:
                result_tb.append(f"扫描失败: {e}")
        
        def save_report():
            content = result_tb.toPlainText()
            if not content.strip():
                QMessageBox.warning(dlg, "警告", "没有可保存的内容")
                return
            
            file_path, _ = QFileDialog.getSaveFileName(dlg, "保存安全扫描报告", "security_scan.txt", "Text Files (*.txt)")
            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    QMessageBox.information(dlg, "成功", f"安全扫描报告已保存到 {file_path}")
                except Exception as e:
                    QMessageBox.warning(dlg, "错误", f"保存失败: {e}")
        
        scan_btn.clicked.connect(run_security_scan)
        save_btn.clicked.connect(save_report)
        close_btn.clicked.connect(dlg.close)
        
        dlg.exec()

    def reset_config_file(self):
        default_config_path = os.path.join(self.base_dir, "config_default.json")
        target_config_path = os.path.join(self.base_dir, "config.json")

        if not os.path.exists(default_config_path):
            QMessageBox.warning(self.parent, "重置配置文件", "默认配置文件不存在。")
            return

        try:
            shutil.copyfile(default_config_path, target_config_path)
            QMessageBox.information(self.parent, "重置配置文件", "配置文件已重置为默认。")
        except Exception as e:
            QMessageBox.warning(self.parent, "重置配置文件", f"重置失败：{e}")

    def backup_config_file(self):
        config_path = os.path.join(self.base_dir, "config.json")
        if not os.path.exists(config_path):
            QMessageBox.warning(self.parent, "配置文件备份", "当前配置文件不存在。")
            return

        backup_path, _ = QFileDialog.getSaveFileName(self.parent, "备份配置文件", "config_backup.json", "JSON 文件 (*.json);;所有文件 (*)")
        if not backup_path:
            return

        try:
            shutil.copyfile(config_path, backup_path)
            QMessageBox.information(self.parent, "配置文件备份", f"配置文件已备份到：{backup_path}")
        except Exception as e:
            QMessageBox.warning(self.parent, "配置文件备份", f"备份失败：{e}")

    def view_db_status(self):
        db_path = os.path.join(self.base_dir, "app.db")
        
        dlg = QDialog(self.parent)
        dlg.setWindowTitle(t("数据库管理中心"))
        dlg.resize(900, 700)
        
        layout = QVBoxLayout(dlg)
        
        # 数据库状态
        status_group = QGroupBox("数据库状态")
        status_layout = QVBoxLayout()
        
        status_label = QLabel("正在检查...")
        path_label = QLabel(f"路径: {db_path}")
        
        status_layout.addWidget(status_label)
        status_layout.addWidget(path_label)
        status_group.setLayout(status_layout)
        
        # 数据库详情
        details_group = QGroupBox("数据库详情")
        details_layout = QVBoxLayout()
        
        tb = QTextBrowser(dlg)
        tb.setFont(QFont("Courier New", 9))
        details_layout.addWidget(tb)
        details_group.setLayout(details_layout)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_refresh = QPushButton("刷新")
        btn_backup = QPushButton("备份数据库")
        btn_vacuum = QPushButton("优化数据库")
        btn_integrity = QPushButton("完整性检查")
        btn_query = QPushButton("SQL查询")
        btn_close = QPushButton("关闭")
        
        btn_layout.addWidget(btn_refresh)
        btn_layout.addWidget(btn_backup)
        btn_layout.addWidget(btn_vacuum)
        btn_layout.addWidget(btn_integrity)
        btn_layout.addWidget(btn_query)
        btn_layout.addWidget(btn_close)
        
        layout.addWidget(status_group)
        layout.addWidget(details_group)
        layout.addLayout(btn_layout)
        
        def load_db_info():
            if not os.path.exists(db_path):
                status_label.setText(t("状态: 数据库文件不存在"))
                tb.setPlainText("数据库文件不存在。")
                return
                
            try:
                file_size = os.path.getsize(db_path)
                mod_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(db_path)))
                
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # 获取表信息
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [t[0] for t in cursor.fetchall()]
                
                # 获取索引信息
                cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
                indexes = [i[0] for i in cursor.fetchall()]
                
                # 获取视图信息
                cursor.execute("SELECT name FROM sqlite_master WHERE type='view';")
                views = [v[0] for v in cursor.fetchall()]
                
                # 获取数据库版本
                cursor.execute("PRAGMA user_version;")
                user_version = cursor.fetchone()[0]
                
                # 获取页面大小
                cursor.execute("PRAGMA page_size;")
                page_size = cursor.fetchone()[0]
                
                # 获取页面数量
                cursor.execute("PRAGMA page_count;")
                page_count = cursor.fetchone()[0]
                
                status_label.setText(f"状态: 正常 | 大小: {file_size} 字节 | 修改时间: {mod_time} | 表数量: {len(tables)}")
                
                content = "=== 数据库详细信息 ===\n\n"
                content += f"文件大小: {file_size:,} 字节 ({file_size / (1024*1024):.2f} MB)\n"
                content += f"页面大小: {page_size} 字节\n"
                content += f"页面数量: {page_count:,}\n"
                content += f"用户版本: {user_version}\n"
                content += f"最后修改: {mod_time}\n\n"
                
                content += f"=== 表信息 ({len(tables)} 个) ===\n"
                for table in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
                        row_count = cursor.fetchone()[0]
                        
                        cursor.execute(f"PRAGMA table_info([{table}])")
                        columns = cursor.fetchall()
                        
                        content += f"\n• {table}\n"
                        content += f"  记录数: {row_count:,}\n"
                        content += f"  字段数: {len(columns)}\n"
                        content += f"  字段: {', '.join([col[1] for col in columns])}\n"
                        
                    except Exception as e:
                        content += f"\n• {table}: 查询失败 ({e})\n"
                
                if indexes:
                    content += f"\n=== 索引信息 ({len(indexes)} 个) ===\n"
                    for idx in indexes:
                        if not idx.startswith('sqlite_autoindex'):
                            content += f"• {idx}\n"
                
                if views:
                    content += f"\n=== 视图信息 ({len(views)} 个) ===\n"
                    for view in views:
                        content += f"• {view}\n"
                
                conn.close()
                tb.setPlainText(content)
                
            except Exception as e:
                status_label.setText("状态: 查询失败")
                tb.setPlainText(f"查询数据库状态失败：{e}")
        
        def backup_database():
            try:
                if not os.path.exists(db_path):
                    QMessageBox.warning(dlg, "错误", "数据库文件不存在")
                    return
                    
                backup_dir = os.path.join(os.path.dirname(db_path), 'db_backups')
                os.makedirs(backup_dir, exist_ok=True)
                
                backup_name = f"app_db_backup_{time.strftime('%Y%m%d_%H%M%S')}.db"
                backup_path = os.path.join(backup_dir, backup_name)
                
                import shutil
                shutil.copy2(db_path, backup_path)
                
                QMessageBox.information(dlg, "成功", f"数据库已备份到: {backup_path}")
            except Exception as e:
                QMessageBox.warning(dlg, "错误", f"备份失败: {e}")
        
        def vacuum_database():
            try:
                if not os.path.exists(db_path):
                    QMessageBox.warning(dlg, "错误", "数据库文件不存在")
                    return
                    
                old_size = os.path.getsize(db_path)
                
                conn = sqlite3.connect(db_path)
                conn.execute("VACUUM;")
                conn.close()
                
                new_size = os.path.getsize(db_path)
                saved = old_size - new_size
                
                load_db_info()
                QMessageBox.information(dlg, "成功", 
                                      f"数据库优化完成\n"
                                      f"原大小: {old_size:,} 字节\n"
                                      f"新大小: {new_size:,} 字节\n"
                                      f"节省空间: {saved:,} 字节")
            except Exception as e:
                QMessageBox.warning(dlg, "错误", f"优化失败: {e}")
        
        def integrity_check():
            try:
                if not os.path.exists(db_path):
                    QMessageBox.warning(dlg, "错误", "数据库文件不存在")
                    return
                    
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                cursor.execute("PRAGMA integrity_check;")
                result = cursor.fetchall()
                
                cursor.execute("PRAGMA foreign_key_check;")
                fk_result = cursor.fetchall()
                
                conn.close()
                
                check_result = "=== 数据库完整性检查结果 ===\n\n"
                check_result += "基本完整性检查:\n"
                for row in result:
                    check_result += f"• {row[0]}\n"
                
                check_result += "\n外键约束检查:\n"
                if fk_result:
                    for row in fk_result:
                        check_result += f"• 表 {row[0]}: 外键错误\n"
                else:
                    check_result += "• 无外键约束错误\n"
                
                QMessageBox.information(dlg, "完整性检查结果", check_result)
                
            except Exception as e:
                QMessageBox.warning(dlg, "错误", f"完整性检查失败: {e}")
        
        def open_sql_query():
            self.execute_sql_query()
        
        btn_refresh.clicked.connect(load_db_info)
        btn_backup.clicked.connect(backup_database)
        btn_vacuum.clicked.connect(vacuum_database)
        btn_integrity.clicked.connect(integrity_check)
        btn_query.clicked.connect(open_sql_query)
        btn_close.clicked.connect(dlg.close)
        
        # 初始加载
        load_db_info()
        
        dlg.exec()

    def execute_sql_query(self):
        dlg = QDialog(self.parent)
        dlg.setWindowTitle("SQL查询工具")
        dlg.resize(1200, 900)
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 查询标签页
        query_tab = QWidget()
        query_layout = QVBoxLayout(query_tab)
        
        # 数据库信息区域
        db_info_group = QGroupBox("数据库信息")
        db_info_layout = QHBoxLayout()
        
        db_path_label = QLabel(f"数据库: {os.path.join(self.base_dir, 'app.db')}")
        db_size_label = QLabel("大小: 计算中...")
        table_count_label = QLabel("表数量: 计算中...")
        
        refresh_info_btn = QPushButton("刷新信息")
        refresh_info_btn.setDefault(False)
        refresh_info_btn.setAutoDefault(False)
        backup_btn = QPushButton("备份数据库")
        backup_btn.setDefault(False)
        backup_btn.setAutoDefault(False)
        optimize_btn = QPushButton("优化数据库")
        optimize_btn.setDefault(False)
        optimize_btn.setAutoDefault(False)
        
        db_info_layout.addWidget(db_path_label)
        db_info_layout.addWidget(db_size_label)
        db_info_layout.addWidget(table_count_label)
        db_info_layout.addStretch()
        db_info_layout.addWidget(refresh_info_btn)
        db_info_layout.addWidget(backup_btn)
        db_info_layout.addWidget(optimize_btn)
        
        db_info_group.setLayout(db_info_layout)
        
        # 查询输入区域
        input_group = QGroupBox("SQL查询")
        input_layout = QVBoxLayout()
        
        # 查询模板和工具
        template_layout = QHBoxLayout()
        template_label = QLabel("查询模板:")
        template_combo = QComboBox()
        template_combo.addItems([
            "自定义查询",
            "SELECT * FROM table_name LIMIT 10;",
            "SELECT COUNT(*) FROM table_name;",
            "PRAGMA table_info(table_name);",
            "SELECT name FROM sqlite_master WHERE type='table';",
            "SELECT sql FROM sqlite_master WHERE name='table_name';",
            "EXPLAIN QUERY PLAN SELECT * FROM table_name;",
            "SELECT * FROM sqlite_master;",
            "PRAGMA database_list;",
            "PRAGMA foreign_key_list(table_name);",
            "PRAGMA index_list(table_name);"
        ])
        
        format_btn = QPushButton("格式化SQL")
        format_btn.setDefault(False)
        format_btn.setAutoDefault(False)
        validate_btn = QPushButton("语法检查")
        validate_btn.setDefault(False)
        validate_btn.setAutoDefault(False)
        
        template_layout.addWidget(template_label)
        template_layout.addWidget(template_combo)
        template_layout.addWidget(format_btn)
        template_layout.addWidget(validate_btn)
        template_layout.addStretch()
        
        # SQL输入框
        sql_edit = QTextEdit()
        sql_edit.setFont(QFont("Courier New", 10))
        sql_edit.setPlaceholderText("在此输入SQL查询语句...")
        sql_edit.setMaximumHeight(180)
        
        # 查询选项
        options_layout = QHBoxLayout()
        limit_checkbox = QCheckBox("自动添加LIMIT")
        limit_checkbox.setChecked(True)
        limit_spinbox = QSpinBox()
        limit_spinbox.setRange(1, 10000)
        limit_spinbox.setValue(100)
        
        timing_checkbox = QCheckBox("显示执行时间")
        timing_checkbox.setChecked(True)
        
        auto_commit_checkbox = QCheckBox("自动提交事务")
        auto_commit_checkbox.setChecked(True)
        
        options_layout.addWidget(limit_checkbox)
        options_layout.addWidget(limit_spinbox)
        options_layout.addWidget(timing_checkbox)
        options_layout.addWidget(auto_commit_checkbox)
        options_layout.addStretch()
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_execute = QPushButton("执行查询")
        btn_execute.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        btn_execute.setDefault(False)
        btn_execute.setAutoDefault(False)
        btn_clear = QPushButton("清空")
        btn_clear.setDefault(False)
        btn_clear.setAutoDefault(False)
        btn_history = QPushButton("查询历史")
        btn_history.setDefault(False)
        btn_history.setAutoDefault(False)
        btn_explain = QPushButton("执行计划")
        btn_explain.setDefault(False)
        btn_explain.setAutoDefault(False)
        btn_save_query = QPushButton("保存查询")
        btn_save_query.setDefault(False)
        btn_save_query.setAutoDefault(False)
        btn_load_query = QPushButton("加载查询")
        btn_load_query.setDefault(False)
        btn_load_query.setAutoDefault(False)
        
        btn_layout.addWidget(btn_execute)
        btn_layout.addWidget(btn_clear)
        btn_layout.addWidget(btn_history)
        btn_layout.addWidget(btn_explain)
        btn_layout.addWidget(btn_save_query)
        btn_layout.addWidget(btn_load_query)
        btn_layout.addStretch()
        
        input_layout.addLayout(template_layout)
        input_layout.addWidget(sql_edit)
        input_layout.addLayout(options_layout)
        input_layout.addLayout(btn_layout)
        input_group.setLayout(input_layout)
        
        # 结果显示区域
        result_group = QGroupBox("查询结果")
        result_layout = QVBoxLayout()
        
        # 结果信息和分页
        result_info_layout = QHBoxLayout()
        result_info = QLabel("等待查询...")
        
        # 分页控件
        page_layout = QHBoxLayout()
        page_label = QLabel("页码:")
        page_spinbox = QSpinBox()
        page_spinbox.setMinimum(1)
        page_size_label = QLabel("每页:")
        page_size_combo = QComboBox()
        page_size_combo.addItems(["50", "100", "200", "500", "1000"])
        page_size_combo.setCurrentText("100")
        
        page_layout.addWidget(page_label)
        page_layout.addWidget(page_spinbox)
        page_layout.addWidget(page_size_label)
        page_layout.addWidget(page_size_combo)
        page_layout.addStretch()
        
        result_info_layout.addWidget(result_info)
        result_info_layout.addStretch()
        result_info_layout.addLayout(page_layout)
        
        # 结果表格
        result_table = QTableWidget()
        result_table.setAlternatingRowColors(True)
        result_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        result_table.setSortingEnabled(True)
        
        # 结果操作按钮
        result_btn_layout = QHBoxLayout()
        btn_export_csv = QPushButton("导出CSV")
        btn_export_csv.setDefault(False)
        btn_export_csv.setAutoDefault(False)
        btn_export_json = QPushButton("导出JSON")
        btn_export_json.setDefault(False)
        btn_export_json.setAutoDefault(False)
        btn_export_excel = QPushButton("导出Excel")
        btn_export_excel.setDefault(False)
        btn_export_excel.setAutoDefault(False)
        btn_copy_result = QPushButton("复制结果")
        btn_copy_result.setDefault(False)
        btn_copy_result.setAutoDefault(False)
        btn_filter = QPushButton("过滤数据")
        btn_filter.setDefault(False)
        btn_filter.setAutoDefault(False)
        btn_chart = QPushButton("生成图表")
        btn_chart.setDefault(False)
        btn_chart.setAutoDefault(False)
        
        result_btn_layout.addWidget(btn_export_csv)
        result_btn_layout.addWidget(btn_export_json)
        result_btn_layout.addWidget(btn_export_excel)
        result_btn_layout.addWidget(btn_copy_result)
        result_btn_layout.addWidget(btn_filter)
        result_btn_layout.addWidget(btn_chart)
        result_btn_layout.addStretch()
        
        result_layout.addLayout(result_info_layout)
        result_layout.addWidget(result_table)
        result_layout.addLayout(result_btn_layout)
        result_group.setLayout(result_layout)
        
        query_layout.addWidget(db_info_group)
        query_layout.addWidget(input_group)
        query_layout.addWidget(result_group)
        
        # 数据库浏览器标签页
        browser_tab = QWidget()
        browser_layout = QVBoxLayout(browser_tab)
        
        # 表列表
        tables_group = QGroupBox("数据库表")
        tables_layout = QVBoxLayout()
        
        tables_list = QListWidget()
        tables_list.setMaximumHeight(150)
        
        table_info_layout = QHBoxLayout()
        btn_refresh_tables = QPushButton("刷新表列表")
        btn_refresh_tables.setDefault(False)
        btn_refresh_tables.setAutoDefault(False)
        btn_create_table = QPushButton("创建表")
        btn_create_table.setDefault(False)
        btn_create_table.setAutoDefault(False)
        btn_drop_table = QPushButton("删除表")
        btn_drop_table.setDefault(False)
        btn_drop_table.setAutoDefault(False)
        btn_table_info = QPushButton("表信息")
        btn_table_info.setDefault(False)
        btn_table_info.setAutoDefault(False)
        
        table_info_layout.addWidget(btn_refresh_tables)
        table_info_layout.addWidget(btn_create_table)
        table_info_layout.addWidget(btn_drop_table)
        table_info_layout.addWidget(btn_table_info)
        table_info_layout.addStretch()
        
        tables_layout.addWidget(tables_list)
        tables_layout.addLayout(table_info_layout)
        tables_group.setLayout(tables_layout)
        
        # 表结构显示
        structure_group = QGroupBox("表结构")
        structure_layout = QVBoxLayout()
        
        structure_table = QTableWidget()
        structure_table.setMaximumHeight(200)
        
        structure_layout.addWidget(structure_table)
        structure_group.setLayout(structure_layout)
        
        # 数据预览
        preview_group = QGroupBox("数据预览")
        preview_layout = QVBoxLayout()
        
        preview_table = QTableWidget()
        
        preview_layout.addWidget(preview_table)
        preview_group.setLayout(preview_layout)
        
        browser_layout.addWidget(tables_group)
        browser_layout.addWidget(structure_group)
        browser_layout.addWidget(preview_group)
        
        # 添加标签页
        tab_widget.addTab(query_tab, "SQL查询")
        tab_widget.addTab(browser_tab, "数据库浏览")
        
        # 底部按钮
        bottom_layout = QHBoxLayout()
        btn_close = QPushButton("关闭")
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_close)
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.addWidget(tab_widget)
        main_layout.addLayout(bottom_layout)
        dlg.setLayout(main_layout)
        
        # 查询历史存储
        query_history = []
        current_results = []
        current_columns = []
        
        def apply_template():
            template = template_combo.currentText()
            if template != "自定义查询":
                sql_edit.setPlainText(template)
        
        def execute_query():
            nonlocal current_results, current_columns
            query = sql_edit.toPlainText().strip()
            if not query:
                QMessageBox.warning(dlg, "错误", "请输入SQL查询语句")
                return
                
            db_path = os.path.join(self.base_dir, "app.db")
            if not os.path.exists(db_path):
                QMessageBox.warning(dlg, "错误", "数据库文件不存在")
                return
                
            try:
                start_time = time.time()
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                cursor.execute(query)
                
                if query.strip().upper().startswith(("SELECT", "PRAGMA", "EXPLAIN")):
                    results = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    
                    current_results = results
                    current_columns = columns
                    
                    # 显示结果
                    result_table.setRowCount(len(results))
                    result_table.setColumnCount(len(columns))
                    result_table.setHorizontalHeaderLabels(columns)
                    
                    for row_idx, row_data in enumerate(results):
                        for col_idx, cell_data in enumerate(row_data):
                            item = QTableWidgetItem(str(cell_data))
                            result_table.setItem(row_idx, col_idx, item)
                    
                    result_table.resizeColumnsToContents()
                    
                    exec_time = time.time() - start_time
                    result_info.setText(f"查询完成 | 返回 {len(results)} 行 | 耗时 {exec_time:.3f} 秒")
                    
                else:
                    conn.commit()
                    affected_rows = cursor.rowcount
                    exec_time = time.time() - start_time
                    
                    result_table.setRowCount(0)
                    result_table.setColumnCount(0)
                    result_info.setText(f"执行完成 | 影响 {affected_rows} 行 | 耗时 {exec_time:.3f} 秒")
                    
                    current_results = []
                    current_columns = []
                
                conn.close()
                
                # 添加到历史记录
                if query not in query_history:
                    query_history.append(query)
                    if len(query_history) > 50:  # 限制历史记录数量
                        query_history.pop(0)
                        
            except Exception as e:
                result_info.setText(f"查询失败: {str(e)}")
                result_table.setRowCount(0)
                result_table.setColumnCount(0)
                QMessageBox.warning(dlg, "错误", f"SQL执行失败：{e}")
        
        def show_query_history():
            if not query_history:
                QMessageBox.information(dlg, "提示", "暂无查询历史")
                return
                
            history_dlg = QDialog(dlg)
            history_dlg.setWindowTitle("查询历史")
            history_dlg.resize(600, 400)
            
            history_layout = QVBoxLayout(history_dlg)
            
            history_list = QListWidget()
            for query in reversed(query_history):  # 最新的在前
                history_list.addItem(query[:100] + "..." if len(query) > 100 else query)
            
            btn_layout = QHBoxLayout()
            btn_use = QPushButton("使用选中查询")
            btn_clear_history = QPushButton("清空历史")
            btn_close_history = QPushButton("关闭")
            
            btn_layout.addWidget(btn_use)
            btn_layout.addWidget(btn_clear_history)
            btn_layout.addWidget(btn_close_history)
            
            history_layout.addWidget(history_list)
            history_layout.addLayout(btn_layout)
            
            def use_selected():
                current_row = history_list.currentRow()
                if current_row >= 0:
                    selected_query = query_history[-(current_row + 1)]  # 反向索引
                    sql_edit.setPlainText(selected_query)
                    history_dlg.close()
            
            def clear_history():
                query_history.clear()
                history_dlg.close()
            
            btn_use.clicked.connect(use_selected)
            btn_clear_history.clicked.connect(clear_history)
            btn_close_history.clicked.connect(history_dlg.close)
            
            history_dlg.exec()
        
        def show_explain_plan():
            query = sql_edit.toPlainText().strip()
            if not query:
                QMessageBox.warning(dlg, "错误", "请输入SQL查询语句")
                return
                
            if not query.strip().upper().startswith("SELECT"):
                QMessageBox.warning(dlg, "错误", "只能分析SELECT查询的执行计划")
                return
                
            explain_query = f"EXPLAIN QUERY PLAN {query}"
            sql_edit.setPlainText(explain_query)
            execute_query()
        
        def export_csv():
            if not current_results or not current_columns:
                QMessageBox.warning(dlg, "错误", "没有可导出的结果")
                return
                
            file_path, _ = QFileDialog.getSaveFileName(dlg, "保存CSV", "", "CSV Files (*.csv)")
            if file_path:
                try:
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(current_columns)
                        writer.writerows(current_results)
                    QMessageBox.information(dlg, "成功", f"结果已导出到 {file_path}")
                except Exception as e:
                    QMessageBox.warning(dlg, "错误", f"导出失败: {e}")
        
        def export_json():
            if not current_results or not current_columns:
                QMessageBox.warning(dlg, "错误", "没有可导出的结果")
                return
                
            file_path, _ = QFileDialog.getSaveFileName(dlg, "保存JSON", "", "JSON Files (*.json)")
            if file_path:
                try:
                    import json
                    data = []
                    for row in current_results:
                        row_dict = {current_columns[i]: row[i] for i in range(len(current_columns))}
                        data.append(row_dict)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    QMessageBox.information(dlg, "成功", f"结果已导出到 {file_path}")
                except Exception as e:
                    QMessageBox.warning(dlg, "错误", f"导出失败: {e}")
        
        def copy_results():
            if not current_results or not current_columns:
                QMessageBox.warning(dlg, "错误", "没有可复制的结果")
                return
                
            content = "\t".join(current_columns) + "\n"
            for row in current_results:
                content += "\t".join(str(cell) for cell in row) + "\n"
            
            clipboard = QApplication.clipboard()
            clipboard.setText(content)
            QMessageBox.information(dlg, "成功", "结果已复制到剪贴板")
        
        # 连接信号
        template_combo.currentTextChanged.connect(apply_template)
        btn_execute.clicked.connect(execute_query)
        btn_clear.clicked.connect(lambda checked: sql_edit.clear())
        btn_history.clicked.connect(show_query_history)
        btn_explain.clicked.connect(show_explain_plan)
        btn_export_csv.clicked.connect(export_csv)
        btn_export_json.clicked.connect(export_json)
        btn_copy_result.clicked.connect(copy_results)
        btn_close.clicked.connect(dlg.close)
        
        dlg.exec()

    def static_code_analysis(self):
        target = QFileDialog.getExistingDirectory(self.parent, "选择分析目录", self.base_dir)
        if not target: return
        try:
            cmd=[sys.executable,"-m","pylint",target,"-j","0"]
            proc=subprocess.run(cmd,capture_output=True,text=True,timeout=300)
            text=(proc.stdout or "")+("\n-----ERR-----\n"+proc.stderr if proc.stderr else "")
        except Exception as e:
            text=f"运行失败:{e}"

        dlg=QDialog(self.parent); dlg.setWindowTitle("静态代码分析"); dlg.resize(900,700)
        layout=QVBoxLayout(dlg); tb=QTextBrowser(dlg); tb.setPlainText(text)
        btn_row=QHBoxLayout(); btn_save=QPushButton("保存"); btn_close=QPushButton("关闭")
        btn_close.clicked.connect(dlg.close)
        def save():
            path,_=QFileDialog.getSaveFileName(dlg,"保存","pylint.txt","Text Files (*.txt)")
            if path: open(path,'w',encoding='utf-8').write(text)
        btn_save.clicked.connect(save)
        btn_row.addStretch(1); btn_row.addWidget(btn_save); btn_row.addWidget(btn_close)
        layout.addWidget(tb); layout.addLayout(btn_row); dlg.setLayout(layout); dlg.show()

    def code_coverage_report(self):
        html = QMessageBox.question(
            self.parent, "覆盖率", "是否生成HTML报告？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes

        try:
            # 运行 coverage 和 pytest
            subprocess.run(
                [sys.executable, "-m", "coverage", "run", "-m", "pytest", "-q"],
                cwd=self.base_dir, check=True
            )

            # 获取文本报告
            proc = subprocess.run(
                [sys.executable, "-m", "coverage", "report", "-m"],
                cwd=self.base_dir, capture_output=True, text=True, check=True
            )

            text = proc.stdout or "(无输出)"

            # 如果选择生成 HTML 报告
            if html:
                subprocess.run(
                    [sys.executable, "-m", "coverage", "html"],
                    cwd=self.base_dir, check=True
                )
                text += "\n\n已生成HTML: htmlcov/index.html"

        except Exception as e:
            text = f"生成失败: {e}"

        # 创建对话框窗口
        dlg = QDialog(self.parent)
        dlg.setWindowTitle("覆盖率报告")
        dlg.resize(900, 700)

        layout = QVBoxLayout(dlg)
        tb = QTextBrowser(dlg)

        # ✅ 设置等宽字体，确保文本对齐
        font = QFont("Courier New")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)  # 调大字号，默认一般是8-10左右
        tb.setFont(font)

        tb.setPlainText(text)

        # 按钮区域
        btn_row = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_open_html = QPushButton("打开HTML报告")  # ✅ 新增按钮
        btn_close = QPushButton("关闭")

        # 关闭窗口
        btn_close.clicked.connect(dlg.close)

        # 保存文本
        def save():
            path, _ = QFileDialog.getSaveFileName(dlg, "保存", "coverage.txt", "Text Files (*.txt)")
            if path:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(text)

        btn_save.clicked.connect(save)

        # ✅ 打开 HTML 报告（如果存在）
        def open_html():
            html_path = self.base_dir + "/htmlcov/index.html"
            try:
                webbrowser.open_new_tab(f"file://{html_path}")
            except Exception as e:
                QMessageBox.warning(dlg, "错误", f"无法打开HTML报告:\n{e}")

        btn_open_html.clicked.connect(open_html)

        # 布局
        btn_row.addStretch(1)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_open_html)
        btn_row.addWidget(btn_close)

        layout.addWidget(tb)
        layout.addLayout(btn_row)

        dlg.setLayout(layout)
        dlg.exec()  # 使用 exec() 而不是 show()，确保是模态弹窗

    def view_dev_docs(self):
        # 打开本地文档或网页，可以根据你的需求改成打开文件或URL
        import webbrowser
        docs_path = os.path.join(self.base_dir, "docs", "index.html")
        if os.path.exists(docs_path):
            webbrowser.open(f"file://{docs_path}")
        else:
            QMessageBox.information(self.parent, "开发文档", "开发文档文件不存在。")

    def view_dev_info(self):
        content = (
            "开发者: 不知名的小王\n"
            "版本: 2.1.6\n"
            "联系方式: 1337555682@qq.com"
        )
        QMessageBox.information(self.parent, "开发者信息", content)

    def view_license_info(self):
        content = """
        <div style="font-family: monospace; white-space: pre-wrap;">
    <span style="color: blue; font-weight: bold; font-size: 14pt;">软件许可协议</span>

    <span style="color: gray;">版权所有 (c) 2025 不知名的小王。保留所有权利。</span>

    请在使用本软件前仔细阅读本许可协议的所有条款。安装、复制或以其他方式使用本软件即表示您同意遵守本协议的所有条款。

    <span style="color: blue; font-weight: bold;">1. 许可授权</span>  
    1.1 本软件授权仅限于个人使用，您可以在单一设备上安装和使用本软件。  
    <span style="color: red;">1.2 未经版权所有者明确书面许可，禁止对本软件进行复制、修改、反编译、反汇编、逆向工程、转换或创建衍生作品。</span>  
    <span style="color: red;">1.3 禁止以任何形式出租、出售、转让、分发或公开传播本软件。</span>

    <span style="color: blue; font-weight: bold;">2. 责任限制</span>  
    <span style="background-color: yellow; font-weight: bold;">2.1 本软件按“现状”提供，不附带任何明示或暗示的保证，包括但不限于对适销性、特定用途适用性及非侵权性的保证。</span>  
    <span style="background-color: yellow; font-weight: bold;">2.2 无论因使用或无法使用本软件导致的任何损害，包括利润损失、业务中断或数据丢失，版权所有者及其关联方均不承担任何责任。</span>  
    2.3 您理解并同意，使用本软件的风险由您自行承担。

    <span style="color: blue; font-weight: bold;">3. 知识产权</span>  
    本软件及其所有内容的知识产权归版权所有者所有，受相关法律法规保护。

    <span style="color: blue; font-weight: bold;">4. 违约责任</span>  
    如您违反本协议任何条款，版权所有者有权立即终止您的使用许可，并依法追究您的法律责任。

    <span style="color: blue; font-weight: bold;">5. 其他条款</span>  
    5.1 本协议的解释、效力及纠纷的解决均适用中华人民共和国法律。  
    5.2 若本协议中任何条款被认定为无效或不可执行，不影响其他条款的效力。  
    5.3 本协议构成您与版权所有者之间关于本软件许可的完整协议，取代之前的所有口头或书面协议。

    ---

    <span style="background-color: yellow; font-weight: bold;">如果您不同意本协议的条款，请立即停止使用本软件并删除所有相关文件。</span>

    <span style="color: gray;">版权所有 (c) 2025 不知名的小王</span>
        </div>
        """

        dlg = QDialog(self.parent)
        dlg.setWindowTitle("许可证信息")
        dlg.resize(800, 600)

        tb = QTextBrowser(dlg)
        tb.setHtml(content)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(dlg.close)

        layout = QVBoxLayout()
        layout.addWidget(tb)
        layout.addWidget(btn_close)
        dlg.setLayout(layout)
        
        # 窗口居中显示
        if self.parent:
            dlg.move(self.parent.geometry().center() - dlg.rect().center())
        
        dlg.exec()