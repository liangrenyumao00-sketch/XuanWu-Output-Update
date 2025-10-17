# -*- coding: utf-8 -*-
"""
高级测试客户端
提供功能强大、完整且可自定义的客户端测试功能
"""

import sys
import json
import time
import socket
import ssl
import threading
import urllib.request
import urllib.parse
import urllib.error
import http.client
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
    QGroupBox, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QComboBox, QPushButton, QTextEdit, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
    QMessageBox, QFileDialog, QSlider, QFrame, QScrollArea,
    QApplication, QMenu, QWidget
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSettings, QSize
)
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor


@dataclass
class TestConfig:
    """测试配置"""
    host: str = "localhost"
    port: int = 8080
    protocol: str = "TCP"  # TCP, HTTP, HTTPS, WebSocket
    use_ssl: bool = False
    timeout: float = 5.0
    retry_count: int = 3
    retry_delay: float = 1.0
    concurrent_connections: int = 1
    test_duration: float = 10.0
    message_interval: float = 1.0
    custom_commands: List[str] = None
    auth_token: str = ""
    user_agent: str = "AdvancedTestClient/1.0"
    http_method: str = "GET"  # GET, POST, PUT, DELETE
    http_path: str = "/"
    http_headers: Dict[str, str] = None
    post_data: str = ""
    websocket_subprotocol: str = ""  # WebSocket子协议
    websocket_ping_interval: int = 30  # WebSocket ping间隔(秒)
    
    def __post_init__(self):
        if self.custom_commands is None:
            self.custom_commands = ["ping", "status", "help"]
        if self.http_headers is None:
            self.http_headers = {"User-Agent": self.user_agent}


@dataclass
class TestResult:
    """测试结果"""
    success: bool
    start_time: float
    end_time: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    min_response_time: float
    max_response_time: float
    error_messages: List[str]
    detailed_log: List[str]
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100


class TestWorkerThread(QThread):
    """测试工作线程"""
    progress_updated = pyqtSignal(int)  # 进度百分比
    status_updated = pyqtSignal(str)    # 状态信息
    log_updated = pyqtSignal(str)       # 日志信息
    result_ready = pyqtSignal(object)   # 测试结果
    
    def __init__(self, config: TestConfig):
        super().__init__()
        self.config = config
        self.is_running = False
        self.should_stop = False
        self.current_stats = None  # 实时统计数据
        
    def run(self):
        """执行测试"""
        self.is_running = True
        self.should_stop = False
        
        result = TestResult(
            success=False,
            start_time=time.time(),
            end_time=0,
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            average_response_time=0,
            min_response_time=float('inf'),
            max_response_time=0,
            error_messages=[],
            detailed_log=[]
        )
        
        try:
            self._run_test(result)
        except Exception as e:
            result.error_messages.append(f"测试异常: {str(e)}")
            self.log_updated.emit(f"错误: {str(e)}")
        finally:
            result.end_time = time.time()
            result.success = result.successful_requests > 0 and len(result.error_messages) == 0
            if result.total_requests > 0:
                result.average_response_time = sum([float(log.split('响应时间:')[1].split('ms')[0]) 
                                                   for log in result.detailed_log 
                                                   if '响应时间:' in log]) / result.successful_requests
            self.result_ready.emit(result)
            self.is_running = False
    
    def _run_test(self, result: TestResult):
        """执行具体测试逻辑"""
        self.status_updated.emit("开始连接测试...")
        
        # 计算总测试次数
        total_tests = len(self.config.custom_commands) * self.config.concurrent_connections
        if self.config.test_duration > 0:
            total_tests = int(self.config.test_duration / self.config.message_interval) * self.config.concurrent_connections
        
        completed_tests = 0
        
        # 并发连接测试
        if self.config.concurrent_connections > 1:
            self._run_concurrent_test(result, total_tests, completed_tests)
        else:
            self._run_single_test(result, total_tests, completed_tests)
    
    def _run_single_test(self, result: TestResult, total_tests: int, completed_tests: int):
        """单连接测试"""
        for retry in range(self.config.retry_count):
            if self.should_stop:
                break
                
            try:
                sock = self._create_connection()
                if sock:
                    self._test_commands(sock, result, total_tests, completed_tests)
                    sock.close()
                    break
            except Exception as e:
                result.error_messages.append(f"重试 {retry + 1}: {str(e)}")
                if retry < self.config.retry_count - 1:
                    time.sleep(self.config.retry_delay)
    
    def _run_concurrent_test(self, result: TestResult, total_tests: int, completed_tests: int):
        """并发连接测试"""
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.concurrent_connections) as executor:
            futures = []
            for i in range(self.config.concurrent_connections):
                if self.should_stop:
                    break
                future = executor.submit(self._worker_test, result, i)
                futures.append(future)
            
            # 等待所有任务完成
            for future in concurrent.futures.as_completed(futures):
                if self.should_stop:
                    break
                try:
                    future.result()
                except Exception as e:
                    result.error_messages.append(f"并发测试异常: {str(e)}")
    
    def _worker_test(self, result: TestResult, worker_id: int):
        """工作线程测试"""
        try:
            sock = self._create_connection()
            if sock:
                self.log_updated.emit(f"工作线程 {worker_id} 连接成功")
                self._test_commands(sock, result, 0, 0, worker_id)
                sock.close()
        except Exception as e:
            result.error_messages.append(f"工作线程 {worker_id} 错误: {str(e)}")
    
    def _create_connection(self) -> Optional[socket.socket]:
        """创建连接"""
        try:
            if self.config.protocol in ["HTTP", "HTTPS"]:
                # HTTP/HTTPS协议不需要持久连接，直接返回None表示使用HTTP客户端
                self.log_updated.emit(f"准备HTTP连接到 {self.config.protocol.lower()}://{self.config.host}:{self.config.port}")
                return None
            elif self.config.protocol == "WebSocket":
                # WebSocket协议使用专门的客户端，返回None
                self.log_updated.emit(f"准备WebSocket连接到 ws://{self.config.host}:{self.config.port}")
                return None
            else:
                # TCP连接
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.config.timeout)
                
                self.log_updated.emit(f"连接到 {self.config.host}:{self.config.port}")
                sock.connect((self.config.host, self.config.port))
                
                if self.config.use_ssl or self.config.protocol == "HTTPS":
                    self.log_updated.emit("开始SSL握手...")
                    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                    context.minimum_version = ssl.TLSVersion.TLSv1_2
                    context.maximum_version = ssl.TLSVersion.TLSv1_3
                    sock = context.wrap_socket(sock, server_hostname=self.config.host)
                    self.log_updated.emit("SSL握手成功")
                
                return sock
            
        except Exception as e:
            self.log_updated.emit(f"连接失败: {str(e)}")
            return None
    
    def _test_commands(self, sock: socket.socket, result: TestResult, total_tests: int, completed_tests: int, worker_id: int = 0):
        """测试命令"""
        start_time = time.time()
        
        while not self.should_stop:
            if self.config.protocol in ["HTTP", "HTTPS"]:
                # HTTP/HTTPS协议测试
                for cmd in self.config.custom_commands:
                    if self.should_stop:
                        break
                    self._test_http_request(cmd, result, worker_id)
                    completed_tests += 1
                    if total_tests > 0:
                        progress = int((completed_tests / total_tests) * 100)
                        self.progress_updated.emit(progress)
                    
                    # 检查测试持续时间
                    if self.config.test_duration > 0 and (time.time() - start_time) >= self.config.test_duration:
                        return
                    
                    time.sleep(self.config.message_interval)
            elif self.config.protocol == "WebSocket":
                # WebSocket协议测试
                if WEBSOCKET_AVAILABLE:
                    self._test_websocket_messages(result, total_tests, completed_tests, worker_id)
                else:
                    error_msg = "WebSocket库未安装，请运行: pip install websocket-client"
                    self.log_updated.emit(error_msg)
                    result.error_messages.append(error_msg)
                    result.failed_requests += len(self.config.custom_commands)
                return
            else:
                # TCP协议测试
                for cmd in self.config.custom_commands:
                    if self.should_stop:
                        break
                        
                    cmd_start = time.time()
                    try:
                        # 发送命令
                        message = f"{cmd}\n"
                        sock.send(message.encode('utf-8'))
                        
                        # 接收响应
                        response = sock.recv(1024).decode('utf-8')
                        cmd_end = time.time()
                        response_time = (cmd_end - cmd_start) * 1000  # 毫秒
                        
                        result.total_requests += 1
                        result.successful_requests += 1
                        result.min_response_time = min(result.min_response_time, response_time)
                        result.max_response_time = max(result.max_response_time, response_time)
                        
                        # 更新实时统计
                        if result.successful_requests > 0:
                            avg_response = sum([float(log.split('响应时间:')[1].split('ms')[0]) 
                                              for log in result.detailed_log 
                                              if '响应时间:' in log]) / result.successful_requests
                        else:
                            avg_response = 0.0
                            
                        self.current_stats = {
                            'total_requests': result.total_requests,
                            'successful_requests': result.successful_requests,
                            'failed_requests': result.failed_requests,
                            'average_response_time': avg_response
                        }
                        
                        log_msg = f"[工作线程{worker_id}] 命令 '{cmd}' 成功, 响应时间: {response_time:.2f}ms, 响应: {response.strip()[:50]}"
                        result.detailed_log.append(log_msg)
                        self.log_updated.emit(log_msg)
                        
                        completed_tests += 1
                        if total_tests > 0:
                            progress = int((completed_tests / total_tests) * 100)
                            self.progress_updated.emit(progress)
                        
                    except Exception as e:
                        result.total_requests += 1
                        result.failed_requests += 1
                        
                        # 更新实时统计
                        if result.successful_requests > 0:
                            avg_response = sum([float(log.split('响应时间:')[1].split('ms')[0]) 
                                              for log in result.detailed_log 
                                              if '响应时间:' in log]) / result.successful_requests
                        else:
                            avg_response = 0.0
                            
                        self.current_stats = {
                            'total_requests': result.total_requests,
                            'successful_requests': result.successful_requests,
                            'failed_requests': result.failed_requests,
                            'average_response_time': avg_response
                        }
                        
                        error_msg = f"[工作线程{worker_id}] 命令 '{cmd}' 失败: {str(e)}"
                        result.error_messages.append(error_msg)
                        self.log_updated.emit(error_msg)
                    
                    # 检查测试持续时间
                    if self.config.test_duration > 0 and (time.time() - start_time) >= self.config.test_duration:
                        return
                    
                    time.sleep(self.config.message_interval)
            
            # 如果不是持续测试，执行一轮后退出
            if self.config.test_duration <= 0:
                break
    
    def _test_websocket_messages(self, result: TestResult, total_tests: int, completed_tests: int, worker_id: int = 0):
        """测试WebSocket消息"""
        ws = None
        try:
            # 构建WebSocket URL
            protocol = "wss" if self.config.use_ssl else "ws"
            url = f"{protocol}://{self.config.host}:{self.config.port}{self.config.http_path}"
            
            # 设置WebSocket选项
            ws_options = {
                "timeout": self.config.timeout,
                "ping_interval": self.config.websocket_ping_interval,
                "ping_timeout": 10
            }
            
            if self.config.websocket_subprotocol:
                ws_options["subprotocols"] = [self.config.websocket_subprotocol]
            
            # 添加认证头
            headers = {}
            if self.config.auth_token:
                headers["Authorization"] = f"Bearer {self.config.auth_token}"
            if self.config.http_headers:
                headers.update(self.config.http_headers)
            if headers:
                ws_options["header"] = headers
            
            self.log_updated.emit(f"[工作线程{worker_id}] 正在连接到 WebSocket: {url}")
            
            # 创建WebSocket连接
            connection_start = time.time()
            ws = websocket.create_connection(url, **ws_options)
            connection_time = (time.time() - connection_start) * 1000
            
            self.log_updated.emit(f"[工作线程{worker_id}] WebSocket连接成功，连接时间: {connection_time:.2f}ms")
            
            try:
                start_time = time.time()
                
                # 检查是否有自定义命令
                if not self.config.custom_commands:
                    self.log_updated.emit(f"[工作线程{worker_id}] 警告: 没有配置测试命令")
                    return
                
                # 发送测试消息
                for message in self.config.custom_commands:
                    if self.should_stop:
                        self.log_updated.emit(f"[工作线程{worker_id}] 测试被用户停止")
                        break
                    
                    msg_start = time.time()
                    try:
                        # 发送消息
                        ws.send(message)
                        self.log_updated.emit(f"[工作线程{worker_id}] 发送消息: {message}")
                        
                        # 接收响应（设置超时）
                        ws.settimeout(self.config.timeout)
                        response = ws.recv()
                        msg_end = time.time()
                        response_time = (msg_end - msg_start) * 1000  # 毫秒
                        
                        result.total_requests += 1
                        result.successful_requests += 1
                        
                        # 更新响应时间统计
                        if result.min_response_time == float('inf') or response_time < result.min_response_time:
                            result.min_response_time = response_time
                        if response_time > result.max_response_time:
                            result.max_response_time = response_time
                        
                        # 截断长响应内容
                        display_response = response[:100] + "..." if len(response) > 100 else response
                        log_msg = f"[工作线程{worker_id}] 收到响应: {display_response} (响应时间: {response_time:.2f}ms)"
                        self.log_updated.emit(log_msg)
                        result.detailed_log.append(log_msg)
                        
                    except websocket.WebSocketTimeoutException:
                        result.total_requests += 1
                        result.failed_requests += 1
                        error_msg = f"[工作线程{worker_id}] 发送 '{message}' -> 超时错误 (>{self.config.timeout}s)"
                        self.log_updated.emit(error_msg)
                        result.detailed_log.append(error_msg)
                        result.error_messages.append(f"WebSocket超时: {message}")
                    except websocket.WebSocketConnectionClosedException:
                        result.total_requests += 1
                        result.failed_requests += 1
                        error_msg = f"[工作线程{worker_id}] 发送 '{message}' -> 连接已关闭"
                        self.log_updated.emit(error_msg)
                        result.detailed_log.append(error_msg)
                        result.error_messages.append(f"WebSocket连接关闭: {message}")
                        break  # 连接关闭，退出循环
                    except Exception as e:
                        result.total_requests += 1
                        result.failed_requests += 1
                        error_msg = f"[工作线程{worker_id}] 发送 '{message}' -> 错误: {str(e)}"
                        self.log_updated.emit(error_msg)
                        result.detailed_log.append(error_msg)
                        result.error_messages.append(f"WebSocket错误: {str(e)}")
                    
                    completed_tests += 1
                    if total_tests > 0:
                        progress = int((completed_tests / total_tests) * 100)
                        self.progress_updated.emit(progress)
                    
                    # 检查测试持续时间
                    if self.config.test_duration > 0 and (time.time() - start_time) >= self.config.test_duration:
                        self.log_updated.emit(f"[工作线程{worker_id}] 达到测试持续时间限制")
                        break
                    
                    # 消息间隔
                    if self.config.message_interval > 0:
                        time.sleep(self.config.message_interval)
                    
            finally:
                if ws:
                    try:
                        ws.close()
                        self.log_updated.emit(f"[工作线程{worker_id}] WebSocket连接已关闭")
                    except Exception as e:
                        self.log_updated.emit(f"[工作线程{worker_id}] 关闭WebSocket连接时出错: {str(e)}")
                
        except websocket.WebSocketException as e:
            error_msg = f"WebSocket连接失败: {str(e)}"
            self.log_updated.emit(f"[工作线程{worker_id}] {error_msg}")
            result.error_messages.append(error_msg)
            if self.config.custom_commands:
                result.failed_requests += len(self.config.custom_commands)
        except Exception as e:
            error_msg = f"WebSocket测试出现未知错误: {str(e)}"
            self.log_updated.emit(f"[工作线程{worker_id}] {error_msg}")
            result.error_messages.append(error_msg)
            if self.config.custom_commands:
                result.failed_requests += len(self.config.custom_commands)
    
    def _test_http_request(self, url_path: str, result: TestResult, worker_id: int = 0):
        """执行HTTP请求测试"""
        cmd_start = time.time()
        try:
            # 构建完整URL
            protocol = self.config.protocol.lower()
            if url_path.startswith('http'):
                url = url_path
            else:
                url = f"{protocol}://{self.config.host}:{self.config.port}{self.config.http_path if url_path == 'default' else url_path}"
            
            # 创建请求
            req = urllib.request.Request(url, method=self.config.http_method)
            
            # 添加请求头
            for key, value in self.config.http_headers.items():
                req.add_header(key, value)
            
            # 添加POST数据
            if self.config.http_method in ['POST', 'PUT'] and self.config.post_data:
                req.data = self.config.post_data.encode('utf-8')
                req.add_header('Content-Type', 'application/json')
            
            # 发送请求
            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                response_data = response.read().decode('utf-8')
                cmd_end = time.time()
                response_time = (cmd_end - cmd_start) * 1000  # 毫秒
                
                result.total_requests += 1
                result.successful_requests += 1
                result.min_response_time = min(result.min_response_time, response_time)
                result.max_response_time = max(result.max_response_time, response_time)
                
                log_msg = f"[工作线程{worker_id}] HTTP {self.config.http_method} {url} 成功, 状态码: {response.status}, 响应时间: {response_time:.2f}ms"
                result.detailed_log.append(log_msg)
                self.log_updated.emit(log_msg)
                
        except urllib.error.HTTPError as e:
            cmd_end = time.time()
            response_time = (cmd_end - cmd_start) * 1000
            result.total_requests += 1
            result.failed_requests += 1
            
            # 读取错误响应内容
            error_content = ""
            try:
                error_content = e.read().decode('utf-8')
            except:
                pass
            
            # 根据不同的HTTP错误码提供更详细的错误信息
            if e.code == 400:
                error_msg = f"[工作线程{worker_id}] HTTP 400 错误 {url}: 请求格式错误或协议不匹配, 响应时间: {response_time:.2f}ms"
                if error_content:
                    error_msg += f"\n响应内容: {error_content[:200]}..."
                error_msg += "\n建议: 检查请求格式、HTTP方法和数据格式是否正确"
            elif e.code == 404:
                error_msg = f"[工作线程{worker_id}] HTTP 404 错误 {url}: 资源未找到, 响应时间: {response_time:.2f}ms"
            elif e.code == 500:
                error_msg = f"[工作线程{worker_id}] HTTP 500 错误 {url}: 服务器内部错误, 响应时间: {response_time:.2f}ms"
            else:
                error_msg = f"[工作线程{worker_id}] HTTP {e.code} 错误 {url}: {e.reason}, 响应时间: {response_time:.2f}ms"
                if error_content:
                    error_msg += f"\n响应内容: {error_content[:200]}..."
            
            result.error_messages.append(error_msg)
            self.log_updated.emit(error_msg)
            
        except Exception as e:
            result.total_requests += 1
            result.failed_requests += 1
            error_msg = f"[工作线程{worker_id}] 请求失败 {url_path}: {str(e)}"
            result.error_messages.append(error_msg)
            self.log_updated.emit(error_msg)
    
    def stop(self):
        """停止测试"""
        self.should_stop = True


class AdvancedTestClientDialog(QDialog):
    """高级测试客户端对话框"""
    
    def __init__(self, parent=None, initial_config=None):
        super().__init__(parent)
        self.config = initial_config or TestConfig()
        self.test_thread = None
        self.test_results = []
        
        self.setWindowTitle("高级测试客户端")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)
        
        # 初始化面板折叠状态
        self.panel_collapsed = {
            'network': False,
            'data_flow': False,
            'content': False
        }
        self.panel_widgets = {}
        self.visual_splitter = None
        
        # 手动测试相关状态
        self._detected_http_server = False
        
        # 端口自动识别相关状态
        self._port_manually_changed = False  # 跟踪用户是否手动修改过端口
        self._last_auto_port = None  # 记录上次自动设置的端口
        
        self._setup_ui()
        self._load_settings()
        self._update_ui_from_config()
        
        # 窗口居中显示（在加载设置之后）
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - 1200) // 2
        y = (screen.height() - 800) // 2
        self.move(x, y)
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 配置标签页
        self._create_config_tab()
        
        # 测试标签页
        self._create_test_tab()
        
        # 手动测试标签页
        self._create_manual_test_tab()
        
        # 结果标签页
        self._create_results_tab()
        
        # 日志标签页
        self._create_log_tab()
        
        # 底部按钮
        self._create_bottom_buttons(layout)
    
    def _create_config_tab(self):
        """创建配置标签页"""
        tab = QScrollArea()
        content = QFrame()
        layout = QVBoxLayout(content)
        
        # 连接配置组
        conn_group = QGroupBox("连接配置")
        conn_layout = QGridLayout(conn_group)
        
        # 协议选择
        conn_layout.addWidget(QLabel("协议:"), 0, 0)
        self.protocol_combo = QComboBox()
        protocols = ["TCP", "HTTP", "HTTPS"]
        if WEBSOCKET_AVAILABLE:
            protocols.append("WebSocket")
        self.protocol_combo.addItems(protocols)
        self.protocol_combo.currentTextChanged.connect(self._on_protocol_changed)
        conn_layout.addWidget(self.protocol_combo, 0, 1)
        
        # 主机
        conn_layout.addWidget(QLabel("主机:"), 0, 2)
        self.host_edit = QLineEdit()
        conn_layout.addWidget(self.host_edit, 0, 3)
        
        # 端口
        conn_layout.addWidget(QLabel("端口:"), 1, 0)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.valueChanged.connect(self._on_port_manually_changed)
        conn_layout.addWidget(self.port_spin, 1, 1)
        
        # SSL
        self.ssl_check = QCheckBox("使用SSL")
        conn_layout.addWidget(self.ssl_check, 1, 2)
        
        # 超时
        conn_layout.addWidget(QLabel("超时(秒):"), 1, 3)
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(0.1, 60.0)
        self.timeout_spin.setSingleStep(0.5)
        conn_layout.addWidget(self.timeout_spin, 1, 4)
        
        # 认证令牌
        conn_layout.addWidget(QLabel("认证令牌:"), 2, 0)
        self.auth_edit = QLineEdit()
        self.auth_edit.setEchoMode(QLineEdit.EchoMode.Password)
        conn_layout.addWidget(self.auth_edit, 2, 1, 1, 4)
        
        # 端口自动识别重置按钮
        reset_port_btn = QPushButton("重置端口自动识别")
        reset_port_btn.setToolTip("重置端口自动识别状态，允许程序根据协议自动设置端口")
        reset_port_btn.clicked.connect(self._reset_port_auto_detection)
        conn_layout.addWidget(reset_port_btn, 3, 0, 1, 2)
        
        # 端口状态提示标签
        self.port_status_label = QLabel("")
        self.port_status_label.setStyleSheet("color: #666; font-size: 11px;")
        conn_layout.addWidget(self.port_status_label, 3, 2, 1, 3)
        
        layout.addWidget(conn_group)
        
        # 测试配置组
        test_group = QGroupBox("测试配置")
        test_layout = QGridLayout(test_group)
        
        # 重试次数
        test_layout.addWidget(QLabel("重试次数:"), 0, 0)
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(1, 10)
        test_layout.addWidget(self.retry_spin, 0, 1)
        
        # 重试延迟
        test_layout.addWidget(QLabel("重试延迟(秒):"), 0, 2)
        self.retry_delay_spin = QDoubleSpinBox()
        self.retry_delay_spin.setRange(0.1, 10.0)
        self.retry_delay_spin.setSingleStep(0.1)
        test_layout.addWidget(self.retry_delay_spin, 0, 3)
        
        # 并发连接数
        test_layout.addWidget(QLabel("并发连接数:"), 1, 0)
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 100)
        test_layout.addWidget(self.concurrent_spin, 1, 1)
        
        # 测试持续时间
        test_layout.addWidget(QLabel("测试持续时间(秒, 0=单次):"), 1, 2)
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0, 3600)
        self.duration_spin.setSingleStep(1.0)
        test_layout.addWidget(self.duration_spin, 1, 3)
        
        # 消息间隔
        test_layout.addWidget(QLabel("消息间隔(秒):"), 2, 0)
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 10.0)
        self.interval_spin.setSingleStep(0.1)
        test_layout.addWidget(self.interval_spin, 2, 1)
        
        # User Agent
        test_layout.addWidget(QLabel("User Agent:"), 2, 2)
        self.user_agent_edit = QLineEdit()
        test_layout.addWidget(self.user_agent_edit, 2, 3)
        
        layout.addWidget(test_group)
        
        # HTTP配置组
        self.http_group = QGroupBox("HTTP配置")
        http_layout = QGridLayout(self.http_group)
        
        # HTTP方法
        http_layout.addWidget(QLabel("HTTP方法:"), 0, 0)
        self.http_method_combo = QComboBox()
        self.http_method_combo.addItems(["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"])
        http_layout.addWidget(self.http_method_combo, 0, 1)
        
        # HTTP路径
        http_layout.addWidget(QLabel("默认路径:"), 0, 2)
        self.http_path_edit = QLineEdit()
        self.http_path_edit.setPlaceholderText("/api/test")
        http_layout.addWidget(self.http_path_edit, 0, 3)
        
        # 请求头
        http_layout.addWidget(QLabel("请求头(JSON):"), 1, 0)
        self.http_headers_edit = QTextEdit()
        self.http_headers_edit.setMaximumHeight(60)
        self.http_headers_edit.setPlaceholderText('{"Content-Type": "application/json", "Authorization": "Bearer token"}')
        http_layout.addWidget(self.http_headers_edit, 1, 1, 1, 3)
        
        # POST数据
        http_layout.addWidget(QLabel("POST数据:"), 2, 0)
        self.post_data_edit = QTextEdit()
        self.post_data_edit.setMaximumHeight(60)
        self.post_data_edit.setPlaceholderText('{"key": "value", "test": true}')
        http_layout.addWidget(self.post_data_edit, 2, 1, 1, 3)
        
        layout.addWidget(self.http_group)
        
        # WebSocket配置组
        self.websocket_group = QGroupBox("WebSocket配置")
        ws_layout = QGridLayout(self.websocket_group)
        
        # 子协议
        ws_layout.addWidget(QLabel("子协议:"), 0, 0)
        self.websocket_subprotocol_edit = QLineEdit()
        self.websocket_subprotocol_edit.setPlaceholderText("chat, echo等")
        ws_layout.addWidget(self.websocket_subprotocol_edit, 0, 1)
        
        # Ping间隔
        ws_layout.addWidget(QLabel("Ping间隔(秒):"), 0, 2)
        self.websocket_ping_spin = QSpinBox()
        self.websocket_ping_spin.setRange(5, 300)
        self.websocket_ping_spin.setValue(30)
        ws_layout.addWidget(self.websocket_ping_spin, 0, 3)
        
        layout.addWidget(self.websocket_group)
        
        # 自定义命令组
        cmd_group = QGroupBox("自定义测试命令")
        cmd_layout = QVBoxLayout(cmd_group)
        
        self.commands_edit = QTextEdit()
        self.commands_edit.setMaximumHeight(100)
        self.commands_edit.setPlaceholderText("每行一个命令，例如:\nping\nstatus\nhelp\nget_info")
        cmd_layout.addWidget(self.commands_edit)
        
        # 预设命令按钮
        preset_layout = QHBoxLayout()
        preset_basic_btn = QPushButton("基础命令")
        preset_basic_btn.clicked.connect(lambda: self._load_preset_commands("basic"))
        preset_layout.addWidget(preset_basic_btn)
        
        preset_debug_btn = QPushButton("调试命令")
        preset_debug_btn.clicked.connect(lambda: self._load_preset_commands("debug"))
        preset_layout.addWidget(preset_debug_btn)
        
        preset_stress_btn = QPushButton("压力测试命令")
        preset_stress_btn.clicked.connect(lambda: self._load_preset_commands("stress"))
        preset_layout.addWidget(preset_stress_btn)
        
        preset_api_btn = QPushButton("REST API")
        preset_api_btn.clicked.connect(lambda: self._load_preset_commands("rest_api"))
        preset_layout.addWidget(preset_api_btn)
        
        preset_layout.addStretch()
        cmd_layout.addLayout(preset_layout)
        
        layout.addWidget(cmd_group)
        
        # 配置管理组
        config_group = QGroupBox("配置管理")
        config_layout = QHBoxLayout(config_group)
        
        save_config_btn = QPushButton("保存配置到文件")
        save_config_btn.clicked.connect(self._save_config_to_file)
        save_config_btn.setToolTip("将当前配置保存到JSON文件")
        config_layout.addWidget(save_config_btn)
        
        load_config_btn = QPushButton("从文件加载配置")
        load_config_btn.clicked.connect(self._load_config_from_file)
        load_config_btn.setToolTip("从JSON文件加载配置")
        config_layout.addWidget(load_config_btn)
        
        apply_config_btn = QPushButton("应用当前配置")
        apply_config_btn.clicked.connect(self._apply_current_config)
        apply_config_btn.setToolTip("应用并保存当前界面的配置")
        config_layout.addWidget(apply_config_btn)
        
        reset_config_btn = QPushButton("重置配置")
        reset_config_btn.clicked.connect(self._reset_config)
        reset_config_btn.setToolTip("重置所有配置为默认值")
        config_layout.addWidget(reset_config_btn)
        
        config_layout.addStretch()
        layout.addWidget(config_group)
        
        layout.addStretch()
        tab.setWidget(content)
        self.tab_widget.addTab(tab, "配置")
    
    def _create_test_tab(self):
        """创建测试标签页"""
        tab = QFrame()
        layout = QVBoxLayout(tab)
        
        # 测试控制组
        control_group = QGroupBox("测试控制")
        control_layout = QHBoxLayout(control_group)
        
        self.start_test_btn = QPushButton("开始测试")
        self.start_test_btn.clicked.connect(self._start_test)
        control_layout.addWidget(self.start_test_btn)
        
        self.stop_test_btn = QPushButton("停止测试")
        self.stop_test_btn.clicked.connect(self._stop_test)
        self.stop_test_btn.setEnabled(False)
        control_layout.addWidget(self.stop_test_btn)
        
        control_layout.addStretch()
        
        # 快速测试按钮
        quick_ping_btn = QPushButton("快速Ping")
        quick_ping_btn.clicked.connect(self._quick_ping_test)
        control_layout.addWidget(quick_ping_btn)
        
        quick_stress_btn = QPushButton("快速压力测试")
        quick_stress_btn.clicked.connect(self._quick_stress_test)
        control_layout.addWidget(quick_stress_btn)
        
        layout.addWidget(control_group)
        
        # 测试状态组
        status_group = QGroupBox("测试状态")
        status_layout = QVBoxLayout(status_group)
        
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("font-weight: bold; color: green;")
        status_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        status_layout.addWidget(self.progress_bar)
        
        # 实时统计
        stats_layout = QGridLayout()
        
        stats_layout.addWidget(QLabel("总请求:"), 0, 0)
        self.total_requests_label = QLabel("0")
        stats_layout.addWidget(self.total_requests_label, 0, 1)
        
        stats_layout.addWidget(QLabel("成功:"), 0, 2)
        self.success_requests_label = QLabel("0")
        self.success_requests_label.setStyleSheet("color: green;")
        stats_layout.addWidget(self.success_requests_label, 0, 3)
        
        stats_layout.addWidget(QLabel("失败:"), 0, 4)
        self.failed_requests_label = QLabel("0")
        self.failed_requests_label.setStyleSheet("color: red;")
        stats_layout.addWidget(self.failed_requests_label, 0, 5)
        
        stats_layout.addWidget(QLabel("成功率:"), 1, 0)
        self.success_rate_label = QLabel("0%")
        stats_layout.addWidget(self.success_rate_label, 1, 1)
        
        stats_layout.addWidget(QLabel("平均响应时间:"), 1, 2)
        self.avg_response_label = QLabel("0ms")
        stats_layout.addWidget(self.avg_response_label, 1, 3)
        
        stats_layout.addWidget(QLabel("测试时长:"), 1, 4)
        self.test_duration_label = QLabel("0s")
        stats_layout.addWidget(self.test_duration_label, 1, 5)
        
        status_layout.addLayout(stats_layout)
        layout.addWidget(status_group)
        
        # 实时日志
        log_group = QGroupBox("实时日志")
        log_layout = QVBoxLayout(log_group)
        
        self.realtime_log = QTextEdit()
        self.realtime_log.setMaximumHeight(200)
        self.realtime_log.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.realtime_log)
        
        # 日志控制
        log_control_layout = QHBoxLayout()
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.clicked.connect(self.realtime_log.clear)
        log_control_layout.addWidget(clear_log_btn)
        
        self.auto_scroll_check = QCheckBox("自动滚动")
        self.auto_scroll_check.setChecked(True)
        log_control_layout.addWidget(self.auto_scroll_check)
        
        log_control_layout.addStretch()
        log_layout.addLayout(log_control_layout)
        
        layout.addWidget(log_group)
        
        self.tab_widget.addTab(tab, "测试")
    
    def _create_results_tab(self):
        """创建结果标签页"""
        tab = QFrame()
        layout = QVBoxLayout(tab)
        
        # 结果表格
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(8)
        self.results_table.setHorizontalHeaderLabels([
            "时间", "成功", "总请求", "成功率", "平均响应时间", "最小响应时间", "最大响应时间", "持续时间"
        ])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.results_table)
        
        # 结果操作
        result_control_layout = QHBoxLayout()
        
        clear_results_btn = QPushButton("清空结果")
        clear_results_btn.clicked.connect(self._clear_results)
        result_control_layout.addWidget(clear_results_btn)
        
        export_results_btn = QPushButton("导出结果")
        export_results_btn.clicked.connect(self._export_results)
        result_control_layout.addWidget(export_results_btn)
        
        result_control_layout.addStretch()
        layout.addLayout(result_control_layout)
        
        self.tab_widget.addTab(tab, "结果")
    
    def _create_log_tab(self):
        """创建日志标签页"""
        tab = QFrame()
        layout = QVBoxLayout(tab)
        
        self.detailed_log = QTextEdit()
        self.detailed_log.setFont(QFont("Consolas", 9))
        layout.addWidget(self.detailed_log)
        
        # 日志操作
        log_control_layout = QHBoxLayout()
        
        clear_detailed_log_btn = QPushButton("清空详细日志")
        clear_detailed_log_btn.clicked.connect(self.detailed_log.clear)
        log_control_layout.addWidget(clear_detailed_log_btn)
        
        save_log_btn = QPushButton("保存日志")
        save_log_btn.clicked.connect(self._save_log)
        log_control_layout.addWidget(save_log_btn)
        
        log_control_layout.addStretch()
        layout.addLayout(log_control_layout)
        
        self.tab_widget.addTab(tab, "详细日志")
    
    def _create_manual_test_tab(self):
        """创建手动测试标签页 - 现代化三栏式布局"""
        tab = QFrame()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 顶部工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # 创建主分割器（三栏布局）
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setStyleSheet("""
            QSplitter::handle {
                background: #dee2e6;
                width: 3px;
                border-radius: 1px;
            }
            QSplitter::handle:hover {
                background: #6c757d;
            }
        """)
        layout.addWidget(main_splitter)
        
        # 左侧控制面板
        left_panel = self._create_control_panel()
        
        # 中间响应面板
        center_panel = self._create_response_panel()
        
        # 右侧可视化面板
        right_panel = self._create_visualization_panel()
        
        # 添加面板到分割器
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(center_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([300, 400, 500])  # 左侧300，中间400，右侧500
        
        self.tab_widget.addTab(tab, "手动测试")
        
        # 初始化手动测试相关变量
        self.manual_connection = None
        self.manual_websocket = None
        self.manual_sent_count_value = 0
        self.manual_received_count_value = 0
        self.manual_connection_start_time = None
        self.manual_response_times = []
        
        # 创建定时器用于更新连接时间
        self.manual_timer = QTimer()
        self.manual_timer.timeout.connect(self._update_manual_connection_time)
        
        # 初始化可视化显示
        self._update_data_flow_visual("INIT", "系统初始化完成", "SYSTEM")
        
        return main_splitter
    
    def _create_toolbar(self):
        """创建顶部工具栏"""
        toolbar = QFrame()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        
        # 连接状态指示器
        self.connection_indicator = QLabel("●")
        toolbar_layout.addWidget(QLabel("状态:"))
        toolbar_layout.addWidget(self.connection_indicator)
        
        self.manual_connection_status = QLabel("未连接")
        toolbar_layout.addWidget(self.manual_connection_status)
        
        toolbar_layout.addStretch()
        
        # 快速操作按钮
        self.manual_connect_btn = QPushButton("🔗 连接")
        self.manual_connect_btn.clicked.connect(self._manual_connect)
        toolbar_layout.addWidget(self.manual_connect_btn)
        
        self.manual_disconnect_btn = QPushButton("🔌 断开")
        self.manual_disconnect_btn.clicked.connect(self._manual_disconnect)
        self.manual_disconnect_btn.setEnabled(False)
        toolbar_layout.addWidget(self.manual_disconnect_btn)
        
        return toolbar
    
    def _create_control_panel(self):
        """创建左侧控制面板"""
        panel = QFrame()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 连接信息组
        info_group = QGroupBox("📡 连接信息")
        info_layout = QVBoxLayout(info_group)
        
        self.manual_connection_info = QTextEdit()
        self.manual_connection_info.setMaximumHeight(100)
        self.manual_connection_info.setReadOnly(True)
        self.manual_connection_info.setFont(QFont("Consolas", 9))
        info_layout.addWidget(self.manual_connection_info)
        layout.addWidget(info_group)
        
        # 命令输入组
        command_group = QGroupBox("⌨️ 命令输入")
        command_layout = QVBoxLayout(command_group)
        
        # 命令输入框
        self.manual_command_input = QLineEdit()
        self.manual_command_input.setPlaceholderText("输入命令或消息...")
        self.manual_command_input.returnPressed.connect(self._manual_send_command)
        command_layout.addWidget(self.manual_command_input)
        
        # 发送按钮组
        send_layout = QHBoxLayout()
        self.manual_send_btn = QPushButton("📤 发送")
        self.manual_send_btn.clicked.connect(self._manual_send_command)
        self.manual_send_btn.setEnabled(False)
        send_layout.addWidget(self.manual_send_btn)
        
        clear_input_btn = QPushButton("🗑️ 清空")
        clear_input_btn.clicked.connect(self.manual_command_input.clear)
        send_layout.addWidget(clear_input_btn)
        
        command_layout.addLayout(send_layout)
        
        # 快捷命令
        quick_label = QLabel("⚡ 快捷命令:")
        command_layout.addWidget(quick_label)
        
        # 创建快捷命令容器
        self.quick_commands_widget = QWidget()
        self.quick_commands_layout = QVBoxLayout(self.quick_commands_widget)
        self.quick_commands_layout.setContentsMargins(0, 0, 0, 0)
        
        # 命令搜索框
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍 搜索:"))
        self.command_search_input = QLineEdit()
        self.command_search_input.setPlaceholderText("输入命令关键词进行搜索...")
        self.command_search_input.textChanged.connect(self._filter_commands)
        search_layout.addWidget(self.command_search_input)
        
        clear_search_btn = QPushButton("清除")
        clear_search_btn.setMaximumWidth(50)
        clear_search_btn.clicked.connect(lambda: self.command_search_input.clear())
        search_layout.addWidget(clear_search_btn)
        
        self.quick_commands_layout.addLayout(search_layout)
        
        # 特殊功能按钮
        special_layout = QHBoxLayout()
        self.quick_http_btn = QPushButton("🌐 发送HTTP请求")
        self.quick_http_btn.setToolTip("直接发送HTTP请求（不插入到输入框）")
        self.quick_http_btn.clicked.connect(self._manual_send_http_request)
        special_layout.addWidget(self.quick_http_btn)
        
        # 添加预设加载按钮
        load_preset_btn = QPushButton("📋 加载预设")
        load_preset_btn.setToolTip("加载当前协议的预设命令到命令列表")
        load_preset_btn.clicked.connect(self._show_preset_menu)
        special_layout.addWidget(load_preset_btn)
        
        special_layout.addStretch()
        self.quick_commands_layout.addLayout(special_layout)
        
        # 命令分组标签页
        self.quick_commands_tabs = QTabWidget()
        self.quick_commands_tabs.setMaximumHeight(150)
        
        # 初始化快捷命令按钮
        self._init_quick_command_buttons()
        
        self.quick_commands_layout.addWidget(self.quick_commands_tabs)
        command_layout.addWidget(self.quick_commands_widget)
        layout.addWidget(command_group)
        
        # 统计信息组
        stats_group = QGroupBox("📊 会话统计")
        stats_layout = QGridLayout(stats_group)
        
        stats_layout.addWidget(QLabel("发送:"), 0, 0)
        self.manual_sent_count = QLabel("0")
        stats_layout.addWidget(self.manual_sent_count, 0, 1)
        
        stats_layout.addWidget(QLabel("接收:"), 0, 2)
        self.manual_received_count = QLabel("0")
        stats_layout.addWidget(self.manual_received_count, 0, 3)
        
        stats_layout.addWidget(QLabel("时长:"), 1, 0)
        self.manual_connection_time = QLabel("00:00:00")
        stats_layout.addWidget(self.manual_connection_time, 1, 1)
        
        stats_layout.addWidget(QLabel("响应:"), 1, 2)
        self.manual_avg_response = QLabel("0ms")
        stats_layout.addWidget(self.manual_avg_response, 1, 3)
        
        layout.addWidget(stats_group)
        layout.addStretch()
        
        return panel
    
    def _create_response_panel(self):
        """创建中间响应面板"""
        panel = QFrame()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 响应显示区域
        response_group = QGroupBox("💬 消息历史")
        response_layout = QVBoxLayout(response_group)
        
        self.manual_response_display = QTextEdit()
        self.manual_response_display.setReadOnly(True)
        self.manual_response_display.setFont(QFont("Consolas", 10))
        response_layout.addWidget(self.manual_response_display)
        
        # 响应控制按钮
        control_layout = QHBoxLayout()
        
        self.manual_clear_btn = QPushButton("🗑️ 清空历史")
        self.manual_clear_btn.clicked.connect(self._clear_manual_response)
        control_layout.addWidget(self.manual_clear_btn)
        
        self.manual_save_btn = QPushButton("💾 保存日志")
        self.manual_save_btn.clicked.connect(self._save_manual_log)
        control_layout.addWidget(self.manual_save_btn)
        
        self.manual_auto_scroll = QCheckBox("📜 自动滚动")
        self.manual_auto_scroll.setChecked(True)
        control_layout.addWidget(self.manual_auto_scroll)
        
        control_layout.addStretch()
        
        # 消息过滤
        filter_label = QLabel("🔍 过滤:")
        control_layout.addWidget(filter_label)
        
        self.message_filter = QComboBox()
        self.message_filter.addItems(["全部", "发送", "接收", "系统", "错误"])
        self.message_filter.currentTextChanged.connect(self._filter_messages)
        control_layout.addWidget(self.message_filter)
        
        response_layout.addLayout(control_layout)
        layout.addWidget(response_group)
        
        # 响应详情面板
        details_group = QGroupBox("📋 响应详情")
        details_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #495057;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
            }
        """)
        details_layout = QVBoxLayout(details_group)
        
        # 响应时间和状态
        status_layout = QHBoxLayout()
        
        status_layout.addWidget(QLabel("状态:"))
        self.response_status = QLabel("未连接")
        status_layout.addWidget(self.response_status)
        
        status_layout.addStretch()
        
        status_layout.addWidget(QLabel("响应时间:"))
        self.response_time = QLabel("0ms")
        status_layout.addWidget(self.response_time)
        
        status_layout.addStretch()
        
        status_layout.addWidget(QLabel("数据大小:"))
        self.response_size = QLabel("0B")
        status_layout.addWidget(self.response_size)
        
        details_layout.addLayout(status_layout)
        
        # 原始数据显示
        self.raw_data_display = QTextEdit()
        self.raw_data_display.setMaximumHeight(120)
        self.raw_data_display.setReadOnly(True)
        self.raw_data_display.setFont(QFont("Consolas", 9))
        self.raw_data_display.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 8px;
                color: #495057;
            }
        """)
        self.raw_data_display.setPlaceholderText("原始响应数据将在此显示...")
        details_layout.addWidget(self.raw_data_display)
        
        layout.addWidget(details_group)
        
        return panel
    
    def _create_visualization_panel(self):
        """创建右侧可视化面板"""
        panel = QFrame()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 网络状态可视化
        network_group = QGroupBox("🌐 网络状态")
        network_layout = QVBoxLayout(network_group)
        
        # 连接状态图表
        self.network_status_widget = QFrame()
        self.network_status_widget.setMinimumHeight(150)
        network_layout.addWidget(self.network_status_widget)
        
        # 网络指标
        metrics_layout = QGridLayout()
        
        # 延迟指标
        metrics_layout.addWidget(QLabel("延迟:"), 0, 0)
        self.latency_value = QLabel("0ms")
        metrics_layout.addWidget(self.latency_value, 0, 1)
        
        self.latency_bar = QProgressBar()
        self.latency_bar.setMaximum(1000)
        metrics_layout.addWidget(self.latency_bar, 0, 2)
        
        # 吞吐量指标
        metrics_layout.addWidget(QLabel("吞吐量:"), 1, 0)
        self.throughput_value = QLabel("0 msg/s")
        metrics_layout.addWidget(self.throughput_value, 1, 1)
        
        self.throughput_bar = QProgressBar()
        self.throughput_bar.setMaximum(100)
        metrics_layout.addWidget(self.throughput_bar, 1, 2)
        
        network_layout.addLayout(metrics_layout)
        layout.addWidget(network_group)
        
        # 数据流可视化
        flow_group = QGroupBox("📊 数据流")
        flow_layout = QVBoxLayout(flow_group)
        
        # 数据流图表区域
        self.data_flow_widget = QFrame()
        self.data_flow_widget.setMinimumHeight(200)
        flow_layout.addWidget(self.data_flow_widget)
        
        # 数据流控制
        flow_control_layout = QHBoxLayout()
        
        self.flow_pause_btn = QPushButton("⏸️ 暂停")
        flow_control_layout.addWidget(self.flow_pause_btn)
        
        self.flow_clear_btn = QPushButton("🗑️ 清空")
        flow_control_layout.addWidget(self.flow_clear_btn)
        
        flow_control_layout.addStretch()
        
        # 数据流速度控制
        flow_control_layout.addWidget(QLabel("速度:"))
        self.flow_speed = QSlider(Qt.Orientation.Horizontal)
        self.flow_speed.setRange(1, 10)
        self.flow_speed.setValue(5)
        flow_control_layout.addWidget(self.flow_speed)
        
        flow_layout.addLayout(flow_control_layout)
        layout.addWidget(flow_group)
        
        # 响应内容预览
        preview_group = QGroupBox("👁️ 内容预览")
        preview_layout = QVBoxLayout(preview_group)
        
        # 内容类型选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("类型:"))
        
        self.content_type = QComboBox()
        self.content_type.addItems(["JSON", "XML", "文本", "二进制"])
        type_layout.addWidget(self.content_type)
        
        type_layout.addStretch()
        
        # 格式化按钮
        format_btn = QPushButton("🎨 格式化")
        type_layout.addWidget(format_btn)
        
        preview_layout.addLayout(type_layout)
        
        # 内容预览区域
        self.content_preview = QTextEdit()
        self.content_preview.setMaximumHeight(150)
        self.content_preview.setReadOnly(True)
        self.content_preview.setFont(QFont("Consolas", 9))
        self.content_preview.setPlaceholderText("响应内容预览将在此显示...")
        preview_layout.addWidget(self.content_preview)
        
        layout.addWidget(preview_group)
        
        return panel
    
    def _clear_manual_response(self):
        """清空手动测试响应显示"""
        if hasattr(self, 'manual_response_display'):
            self.manual_response_display.clear()
    
    def _save_manual_log(self):
        """保存手动测试日志"""
        if hasattr(self, 'manual_response_display'):
            content = self.manual_response_display.toPlainText()
            if content:
                filename, _ = QFileDialog.getSaveFileName(
                    self, "保存手动测试日志", "manual_test_log.txt", "文本文件 (*.txt)")
                if filename:
                    try:
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(content)
                        QMessageBox.information(self, "成功", "日志已保存")
                    except Exception as e:
                        QMessageBox.warning(self, "错误", f"保存失败: {str(e)}")
    
    def _filter_messages(self, filter_type):
        """过滤消息显示"""
        # 这里可以实现消息过滤逻辑
        pass
    
    def _init_quick_command_buttons(self):
        """初始化快捷命令按钮"""
        # 定义所有命令分组
        self.command_groups = {
            "基础命令": {
                "TCP": ["ping", "status", "help", "version", "info"],
                "HTTP": ["/", "/api/status", "/api/health", "/api/version", "/api/info"],
                "WebSocket": ['{"type":"ping"}', '{"type":"status"}', '{"type":"info"}']
            },
            "调试命令": {
                "TCP": ["debug_info", "get_clients", "get_stats", "memory_info", "threads"],
                "HTTP": ["/api/debug", "/api/metrics", "/admin/stats", "/api/clients", "/debug/memory"],
                "WebSocket": ['{"type":"debug"}', '{"type":"metrics"}', '{"type":"clients"}']
            },
            "API命令": {
                "TCP": ["get_users", "get_config", "set_config", "reload", "shutdown"],
                "HTTP": ["/api/users", "/api/config", "/api/reload", "/api/shutdown", "/api/auth/login"],
                "WebSocket": ['{"action":"get_users"}', '{"action":"get_config"}', '{"action":"reload"}']
            },
            "测试命令": {
                "TCP": ["echo test", "stress_test", "benchmark", "load_test", "noop"],
                "HTTP": ["/test", "/api/echo", "/api/benchmark", "/stress", "/load_test"],
                "WebSocket": ['{"type":"echo","message":"test"}', '{"type":"benchmark"}', '{"type":"stress"}']
            },
            "系统命令": {
                "TCP": ["uptime", "cpu_info", "disk_info", "network_info", "processes"],
                "HTTP": ["/api/system/uptime", "/api/system/cpu", "/api/system/disk", "/api/system/network"],
                "WebSocket": ['{"type":"system","info":"uptime"}', '{"type":"system","info":"cpu"}']
            }
        }
        
        # 创建分组标签页
        self._create_command_group_tabs()
        
        # 监听协议变化以更新按钮
        if hasattr(self, 'protocol_combo'):
            self.protocol_combo.currentTextChanged.connect(self._update_quick_commands)
            # 初始化时更新一次
            QTimer.singleShot(100, self._update_quick_commands)
    
    def _create_command_group_tabs(self):
        """创建命令分组标签页"""
        for group_name, protocols in self.command_groups.items():
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            tab_layout.setContentsMargins(5, 5, 5, 5)
            
            # 创建滚动区域
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            
            scroll_widget = QWidget()
            scroll_layout = QGridLayout(scroll_widget)
            scroll_layout.setSpacing(3)
            
            # 存储按钮引用以便后续更新
            if not hasattr(self, '_quick_command_buttons'):
                self._quick_command_buttons = {}
            self._quick_command_buttons[group_name] = []
            
            scroll_area.setWidget(scroll_widget)
            tab_layout.addWidget(scroll_area)
            
            self.quick_commands_tabs.addTab(tab_widget, group_name)
    
    def _update_quick_commands(self):
        """根据当前协议更新快捷命令按钮（异步优化版本）"""
        # 使用QTimer延迟执行，避免阻塞UI
        QTimer.singleShot(0, self._do_update_quick_commands)
    
    def _do_update_quick_commands(self):
        """实际执行快捷命令按钮更新"""
        try:
            current_protocol = self.protocol_combo.currentText() if hasattr(self, 'protocol_combo') else "TCP"
            
            # 映射协议名称
            protocol_map = {
                "TCP": "TCP",
                "HTTP": "HTTP",
                "HTTPS": "HTTP",
                "WebSocket": "WebSocket"
            }
            
            mapped_protocol = protocol_map.get(current_protocol, "TCP")
            
            # 批量处理，减少UI更新频率
            self.quick_commands_tabs.setUpdatesEnabled(False)
            
            try:
                # 更新每个分组的按钮
                for i, (group_name, protocols) in enumerate(self.command_groups.items()):
                    if i < self.quick_commands_tabs.count():
                        self._update_tab_commands(i, protocols, mapped_protocol)
            finally:
                self.quick_commands_tabs.setUpdatesEnabled(True)
                
        except Exception as e:
            print(f"更新快捷命令时出错: {e}")
    
    def _update_tab_commands(self, tab_index, protocols, mapped_protocol):
        """更新单个标签页的命令按钮"""
        tab_widget = self.quick_commands_tabs.widget(tab_index)
        scroll_area = tab_widget.findChild(QScrollArea)
        if not scroll_area:
            return
            
        scroll_widget = scroll_area.widget()
        scroll_layout = scroll_widget.layout()
        
        # 获取新命令列表
        commands = protocols.get(mapped_protocol, [])
        
        # 清除现有按钮（批量删除）
        self._clear_layout_widgets(scroll_layout)
        
        # 批量添加新按钮
        self._add_command_buttons(scroll_layout, commands)
    
    def _clear_layout_widgets(self, layout):
        """清除布局中的所有控件"""
        widgets_to_delete = []
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                widgets_to_delete.append(child.widget())
        
        # 批量删除控件
        for widget in widgets_to_delete:
            widget.deleteLater()
    
    def _add_command_buttons(self, layout, commands):
        """批量添加命令按钮"""
        row, col = 0, 0
        max_cols = 4
        
        for cmd in commands:
            btn = QPushButton(self._format_command_display(cmd))
            btn.setToolTip(f"插入命令: {cmd}")
            btn.setMaximumWidth(120)
            btn.clicked.connect(lambda checked, c=cmd: self._insert_quick_command(c))
            
            layout.addWidget(btn, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
    
    def _format_command_display(self, command):
        """格式化命令显示文本"""
        if command.startswith('{'):
            # JSON命令，提取type或action
            try:
                import json
                cmd_obj = json.loads(command)
                if 'type' in cmd_obj:
                    return f"📡 {cmd_obj['type']}"
                elif 'action' in cmd_obj:
                    return f"⚡ {cmd_obj['action']}"
                else:
                    return "📋 JSON"
            except:
                return "📋 JSON"
        elif command.startswith('/'):
            # HTTP路径
            parts = command.split('/')
            if len(parts) > 1:
                return f"🌐 {parts[-1] or 'root'}"
            return "🌐 HTTP"
        else:
            # 普通命令
            return f"⚡ {command}"
    
    def _filter_commands(self, search_text):
        """根据搜索文本过滤命令（优化版本）"""
        # 使用防抖机制，避免频繁更新
        if hasattr(self, '_filter_timer'):
            self._filter_timer.stop()
        else:
            self._filter_timer = QTimer()
            self._filter_timer.setSingleShot(True)
            self._filter_timer.timeout.connect(lambda: self._do_filter_commands(search_text))
        
        # 延迟300ms执行，避免输入时频繁触发
        self._filter_timer.start(300)
    
    def _do_filter_commands(self, search_text):
        """实际执行命令过滤"""
        try:
            search_text = search_text.lower().strip()
            
            if not search_text:
                # 如果搜索框为空，显示所有命令
                self._update_quick_commands()
                return
            
            current_protocol = self.protocol_combo.currentText() if hasattr(self, 'protocol_combo') else "TCP"
            protocol_map = {
                "TCP": "TCP",
                "HTTP": "HTTP",
                "HTTPS": "HTTP",
                "WebSocket": "WebSocket"
            }
            mapped_protocol = protocol_map.get(current_protocol, "TCP")
            
            # 批量处理，减少UI更新频率
            self.quick_commands_tabs.setUpdatesEnabled(False)
            
            try:
                # 过滤并显示匹配的命令
                for i, (group_name, protocols) in enumerate(self.command_groups.items()):
                    if i < self.quick_commands_tabs.count():
                        self._filter_tab_commands(i, protocols, mapped_protocol, search_text)
            finally:
                self.quick_commands_tabs.setUpdatesEnabled(True)
                
        except Exception as e:
            print(f"过滤命令时出错: {e}")
    
    def _filter_tab_commands(self, tab_index, protocols, mapped_protocol, search_text):
        """过滤单个标签页的命令"""
        tab_widget = self.quick_commands_tabs.widget(tab_index)
        scroll_area = tab_widget.findChild(QScrollArea)
        if not scroll_area:
            return
            
        scroll_widget = scroll_area.widget()
        scroll_layout = scroll_widget.layout()
        
        # 过滤命令
        commands = protocols.get(mapped_protocol, [])
        filtered_commands = [
            cmd for cmd in commands 
            if search_text in cmd.lower() or 
               search_text in self._format_command_display(cmd).lower()
        ]
        
        # 清除现有按钮（批量删除）
        self._clear_layout_widgets(scroll_layout)
        
        # 批量添加过滤后的按钮
        self._add_command_buttons(scroll_layout, filtered_commands)
    
    def _show_preset_menu(self):
        """显示预设命令菜单"""
        current_protocol = self.protocol_combo.currentText() if hasattr(self, 'protocol_combo') else "TCP"
        protocol_map = {
            "TCP": "TCP",
            "HTTP": "HTTP",
            "HTTPS": "HTTP",
            "WebSocket": "WebSocket"
        }
        mapped_protocol = protocol_map.get(current_protocol, "TCP")
        
        # 获取预设命令
        preset_commands = self._get_all_preset_commands()
        protocol_presets = preset_commands.get(mapped_protocol, {})
        
        if not protocol_presets:
            QMessageBox.information(self, "提示", f"当前协议 {current_protocol} 没有可用的预设命令")
            return
        
        # 创建菜单
        menu = QMenu(self)
        
        for preset_name, commands in protocol_presets.items():
            action = menu.addAction(f"📋 {preset_name} ({len(commands)}个命令)")
            action.triggered.connect(lambda checked, cmds=commands, name=preset_name: self._load_preset_to_input(cmds, name))
        
        # 显示菜单
        menu.exec(self.sender().mapToGlobal(self.sender().rect().bottomLeft()))
    
    def _load_preset_to_input(self, commands, preset_name):
        """将预设命令加载到命令输入框"""
        if not hasattr(self, 'commands_edit'):
            return
        
        # 获取当前命令列表
        current_text = self.commands_edit.toPlainText().strip()
        current_commands = [cmd.strip() for cmd in current_text.split('\n') if cmd.strip()] if current_text else []
        
        # 添加新命令（避免重复）
        new_commands = []
        for cmd in commands:
            if cmd not in current_commands:
                new_commands.append(cmd)
        
        if new_commands:
            all_commands = current_commands + new_commands
            self.commands_edit.setPlainText('\n'.join(all_commands))
            
            # 更新快捷命令显示
            self._update_quick_commands()
            
            QMessageBox.information(self, "成功", f"已添加 {len(new_commands)} 个新命令到命令列表\n预设: {preset_name}")
        else:
            QMessageBox.information(self, "提示", f"预设 {preset_name} 中的所有命令都已存在")
    
    def _insert_quick_command(self, command):
        """插入快捷命令"""
        if hasattr(self, 'manual_command_input'):
            self.manual_command_input.setText(command)
            self.manual_command_input.setFocus()
    
    def _toggle_panel_visibility(self, panel_name):
        """切换面板的显示/隐藏状态（占位方法）"""
        pass
    
    def _update_connection_visual(self, connected, config=None, data_info=None):
        """更新连接可视化显示（占位方法）"""
        pass
    
    def _adjust_splitter_sizes(self):
        """调整分割器尺寸（占位方法）"""
        pass
    
    def _update_data_flow_visual(self, direction, data, data_type="TEXT"):
        """更新数据流可视化"""
        try:
            # 更新计数器
            if direction == "发送":
                self.manual_sent_count_value += 1
            elif direction == "接收":
                self.manual_received_count_value += 1
            elif direction == "INIT":
                # 初始化时重置计数器
                self.manual_sent_count_value = 0
                self.manual_received_count_value = 0
                return
            
            # 在数据流区域显示简单的可视化信息
            if hasattr(self, 'data_flow_widget'):
                # 创建简单的文本显示
                current_time = time.strftime('%H:%M:%S')
                flow_info = f"[{current_time}] {direction}: {data[:50]}{'...' if len(data) > 50 else ''}"
                
                # 如果还没有显示区域，创建一个
                if not hasattr(self, 'data_flow_display'):
                    from PyQt6.QtWidgets import QTextEdit
                    self.data_flow_display = QTextEdit()
                    self.data_flow_display.setMaximumHeight(180)
                    self.data_flow_display.setReadOnly(True)
                    self.data_flow_display.setFont(QFont("Consolas", 8))
                    self.data_flow_display.setStyleSheet("""
                        QTextEdit {
                            background-color: #1e1e1e;
                            color: #ffffff;
                            border: 1px solid #555;
                        }
                    """)
                    
                    # 将显示区域添加到数据流widget中
                    if self.data_flow_widget.layout() is None:
                        from PyQt6.QtWidgets import QVBoxLayout
                        layout = QVBoxLayout(self.data_flow_widget)
                        layout.addWidget(self.data_flow_display)
                
                # 添加新的流量信息
                color = "#00ff00" if direction == "发送" else "#00aaff" if direction == "接收" else "#ffaa00"
                formatted_info = f'<span style="color: {color}">{flow_info}</span>'
                self.data_flow_display.append(formatted_info)
                
                # 限制显示行数，避免内存占用过多
                document = self.data_flow_display.document()
                if document.blockCount() > 100:
                    cursor = self.data_flow_display.textCursor()
                    cursor.movePosition(cursor.MoveOperation.Start)
                    cursor.select(cursor.SelectionType.BlockUnderCursor)
                    cursor.removeSelectedText()
                    cursor.deletePreviousChar()  # 删除换行符
                
                # 自动滚动到底部
                scrollbar = self.data_flow_display.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
                
        except Exception as e:
            # 静默处理错误，避免影响主要功能
            pass
    
    def _update_data_flow_visual_no_count(self, direction, data, data_type="TEXT"):
        """更新数据流可视化但不增加计数器（用于空响应等情况）"""
        try:
            # 在数据流区域显示简单的可视化信息，但不更新计数器
            if hasattr(self, 'data_flow_widget'):
                # 创建简单的文本显示
                current_time = time.strftime('%H:%M:%S')
                flow_info = f"[{current_time}] {direction}: {data[:50]}{'...' if len(data) > 50 else ''}"
                
                # 如果还没有显示区域，创建一个
                if not hasattr(self, 'data_flow_display'):
                    from PyQt6.QtWidgets import QTextEdit
                    self.data_flow_display = QTextEdit()
                    self.data_flow_display.setMaximumHeight(180)
                    self.data_flow_display.setReadOnly(True)
                    self.data_flow_display.setFont(QFont("Consolas", 8))
                    self.data_flow_display.setStyleSheet("""
                        QTextEdit {
                            background-color: #1e1e1e;
                            color: #ffffff;
                            border: 1px solid #555;
                        }
                    """)
                    
                    # 将显示区域添加到数据流widget中
                    if self.data_flow_widget.layout() is None:
                        from PyQt6.QtWidgets import QVBoxLayout
                        layout = QVBoxLayout(self.data_flow_widget)
                        layout.addWidget(self.data_flow_display)
                
                # 添加新的流量信息（使用灰色表示无效响应）
                color = "#888888"  # 灰色表示无效响应
                formatted_info = f'<span style="color: {color}">{flow_info}</span>'
                self.data_flow_display.append(formatted_info)
                
                # 限制显示行数，避免内存占用过多
                document = self.data_flow_display.document()
                if document.blockCount() > 100:
                    cursor = self.data_flow_display.textCursor()
                    cursor.movePosition(cursor.MoveOperation.Start)
                    cursor.select(cursor.SelectionType.BlockUnderCursor)
                    cursor.removeSelectedText()
                    cursor.deletePreviousChar()  # 删除换行符
                
                # 自动滚动到底部
                scrollbar = self.data_flow_display.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
                
        except Exception as e:
            # 静默处理错误，避免影响主要功能
            pass
    
    def _get_current_config(self):
        """获取当前配置"""
        try:
            self._update_config_from_ui()
            return self.config
        except Exception as e:
            return None
    
    def _manual_connect(self):
        """手动测试连接"""
        try:
            config = self._get_current_config()
            if not config:
                self._append_manual_response("错误: 请先配置连接参数")
                return
            
            self._append_manual_response(f"正在连接到 {config.host}:{config.port} ({config.protocol})...")
            
            if config.protocol.upper() == 'WEBSOCKET':
                self._manual_connect_websocket(config)
            else:
                self._manual_connect_socket(config)
                
        except Exception as e:
            self._append_manual_response(f"连接失败: {str(e)}")
    
    def _manual_connect_socket(self, config):
        """手动测试Socket连接"""
        try:
            self.manual_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.manual_connection.settimeout(config.timeout)
            
            start_time = time.time()
            self.manual_connection.connect((config.host, config.port))
            connect_time = (time.time() - start_time) * 1000
            
            self._update_manual_connection_status(True, config, connect_time)
            self._update_connection_visual(True, config)
            self._append_manual_response(f"✅ Socket连接成功! 连接时间: {connect_time:.2f}ms")
            
        except socket.timeout:
            self._update_manual_connection_status(False, None, 0)
            self._update_connection_visual(False)
            self._append_manual_response(f"❌ Socket连接超时 (>{config.timeout}s)")
            self._append_manual_response("💡 建议: 检查目标服务器是否运行，或增加超时时间")
            if self.manual_connection:
                self.manual_connection.close()
                self.manual_connection = None
        except ConnectionRefusedError:
            self._update_manual_connection_status(False, None, 0)
            self._update_connection_visual(False)
            self._append_manual_response(f"❌ Socket连接被拒绝 - 目标端口 {config.port} 未开放")
            self._append_manual_response("💡 建议: 确认服务器正在运行并监听指定端口")
            if self.manual_connection:
                self.manual_connection.close()
                self.manual_connection = None
        except socket.gaierror as e:
            self._update_manual_connection_status(False, None, 0)
            self._update_connection_visual(False)
            self._append_manual_response(f"❌ 域名解析失败: {config.host}")
            self._append_manual_response("💡 建议: 检查主机名是否正确，或使用IP地址")
            if self.manual_connection:
                self.manual_connection.close()
                self.manual_connection = None
        except Exception as e:
            self._update_manual_connection_status(False, None, 0)
            self._update_connection_visual(False)
            self._append_manual_response(f"❌ Socket连接失败: {str(e)}")
            self._append_manual_response("💡 建议: 检查网络连接和防火墙设置")
            if self.manual_connection:
                self.manual_connection.close()
                self.manual_connection = None
    
    def _manual_connect_websocket(self, config):
        """手动测试WebSocket连接"""
        try:
            import websocket
            
            url = f"ws://{config.host}:{config.port}"
            if config.protocol.upper() == 'WSS':
                url = f"wss://{config.host}:{config.port}"
            
            start_time = time.time()
            self.manual_websocket = websocket.create_connection(url, timeout=config.timeout)
            connect_time = (time.time() - start_time) * 1000
            
            self._update_manual_connection_status(True, config, connect_time)
            self._update_connection_visual(True, config)
            self._append_manual_response(f"WebSocket连接成功! 连接时间: {connect_time:.2f}ms")
            
        except ImportError:
            self._append_manual_response("❌ 错误: 未安装websocket-client库")
            self._append_manual_response("💡 建议: 运行 'pip install websocket-client' 安装依赖")
        except websocket.WebSocketTimeoutException:
            self._update_manual_connection_status(False, None, 0)
            self._update_connection_visual(False)
            self._append_manual_response(f"❌ WebSocket连接超时 (>{config.timeout}s)")
            self._append_manual_response("💡 建议: 检查WebSocket服务器状态，或增加超时时间")
            if hasattr(self, 'manual_websocket') and self.manual_websocket:
                self.manual_websocket.close()
                self.manual_websocket = None
        except websocket.WebSocketBadStatusException as e:
            self._update_manual_connection_status(False, None, 0)
            self._update_connection_visual(False)
            self._append_manual_response(f"❌ WebSocket握手失败: HTTP {e.status_code}")
            if e.status_code == 404:
                self._append_manual_response("💡 建议: 检查WebSocket路径是否正确")
            elif e.status_code == 401:
                self._append_manual_response("💡 建议: 检查认证信息或访问权限")
            elif e.status_code == 403:
                self._append_manual_response("💡 建议: 服务器拒绝连接，检查访问权限")
            else:
                self._append_manual_response("💡 建议: 检查服务器配置和WebSocket支持")
            if hasattr(self, 'manual_websocket') and self.manual_websocket:
                self.manual_websocket.close()
                self.manual_websocket = None
        except ConnectionRefusedError:
            self._update_manual_connection_status(False, None, 0)
            self._update_connection_visual(False)
            self._append_manual_response(f"❌ WebSocket连接被拒绝 - 端口 {config.port} 未开放")
            self._append_manual_response("💡 建议: 确认WebSocket服务器正在运行")
            if hasattr(self, 'manual_websocket') and self.manual_websocket:
                self.manual_websocket.close()
                self.manual_websocket = None
        except Exception as e:
             self._update_manual_connection_status(False, None, 0)
             self._update_connection_visual(False)
             self._append_manual_response(f"❌ WebSocket连接失败: {str(e)}")
             self._append_manual_response("💡 建议: 检查URL格式、网络连接和SSL证书")
             if hasattr(self, 'manual_websocket') and self.manual_websocket:
                 self.manual_websocket.close()
                 self.manual_websocket = None
    
    def _manual_disconnect(self):
        """手动测试断开连接"""
        try:
            if self.manual_connection:
                self.manual_connection.close()
                self.manual_connection = None
                self._append_manual_response("Socket连接已断开")
            
            if self.manual_websocket:
                self.manual_websocket.close()
                self.manual_websocket = None
                self._append_manual_response("WebSocket连接已断开")
            
            self._update_manual_connection_status(False, None, 0)
            self._update_connection_visual(False)
            
        except Exception as e:
            self._append_manual_response(f"断开连接时出错: {str(e)}")
    
    def _manual_send_command(self):
        """手动发送命令"""
        command = self.manual_command_input.text().strip()
        if not command:
            return
        
        try:
            self._append_manual_response(f">>> {command}")
            self._update_data_flow_visual("发送", command)
            
            start_time = time.time()
            
            if self.manual_websocket:
                self._manual_send_websocket(command)
            elif self.manual_connection:
                # 检测是否收到HTTP响应，如果是则切换到HTTP模式
                if hasattr(self, '_detected_http_server') and self._detected_http_server:
                    self._manual_send_as_http(command)
                else:
                    self._manual_send_socket(command)
            else:
                self._append_manual_response("错误: 未建立连接")
                return
            
            response_time = (time.time() - start_time) * 1000
            self.manual_response_times.append(response_time)
            
            # 更新发送计数显示（计数逻辑在_update_data_flow_visual中处理）
            self.manual_sent_count.setText(str(self.manual_sent_count_value))
            
            # 更新平均响应时间
            avg_time = sum(self.manual_response_times) / len(self.manual_response_times)
            self.manual_avg_response.setText(f"{avg_time:.1f}ms")
            
            self.manual_command_input.clear()
            
        except Exception as e:
            self._append_manual_response(f"发送失败: {str(e)}")
    
    def _manual_send_socket(self, command):
        """通过Socket发送命令"""
        try:
            # 记录开始时间
            start_time = time.time()
            
            # 发送命令
            self.manual_connection.send((command + "\n").encode('utf-8'))
            
            # 接收响应
            self.manual_connection.settimeout(5.0)  # 设置接收超时
            response = self.manual_connection.recv(4096).decode('utf-8', errors='ignore')
            
            # 计算响应时间
            response_time = (time.time() - start_time) * 1000
            
            if response and response.strip():  # 检查响应是否非空且不只是空白字符
                # 计算数据大小
                data_size = len(response.encode('utf-8'))
                
                # 更新状态显示标签
                self.response_status.setText("TCP 响应成功")
                self.response_time.setText(f"{response_time:.2f}ms")
                if data_size >= 1024:
                    self.response_size.setText(f"{data_size/1024:.1f}KB")
                else:
                    self.response_size.setText(f"{data_size}B")
                
                # 检测是否为HTTP响应
                if response.startswith('<!DOCTYPE HTML') or response.startswith('HTTP/') or 'Error response' in response:
                    self._detected_http_server = True
                    self._append_manual_response(f"<<< {response.strip()}")
                    self._append_manual_response("🔍 检测到HTTP服务器，后续命令将使用HTTP协议发送")
                    self._append_manual_response("💡 提示: 请使用HTTP路径格式，如 '/api/status' 或 '/ping'")
                else:
                    self._append_manual_response(f"<<< {response.strip()}")
                
                # 更新原始数据显示
                self.raw_data_display.setPlainText(response)
                
                # 只有有效响应才更新接收计数
                self._update_data_flow_visual("接收", response.strip())
                self.manual_received_count.setText(str(self.manual_received_count_value))
            else:
                # 更新状态显示标签（无响应情况）
                self.response_status.setText("TCP 无响应")
                self.response_time.setText(f"{response_time:.2f}ms")
                self.response_size.setText("0B")
                
                self._append_manual_response("<<< (无响应或空响应)")
                # 更新原始数据显示为空响应提示
                self.raw_data_display.setPlainText("(无响应或空响应)")
                # 空响应不计入接收统计，只显示在数据流中
                self._update_data_flow_visual_no_count("接收", "(无响应)")
                
        except socket.timeout:
            # 更新状态显示（超时）
            self.response_status.setText("TCP 超时")
            self.response_time.setText(">5000ms")
            self.response_size.setText("0B")
            
            self._append_manual_response("❌ 响应超时 (>5s)")
            self._append_manual_response("💡 建议: 服务器可能处理较慢，或检查网络连接")
        except ConnectionResetError:
            # 更新状态显示（连接重置）
            self.response_status.setText("TCP 连接重置")
            self.response_time.setText("0ms")
            self.response_size.setText("0B")
            
            self._append_manual_response("❌ 连接被服务器重置")
            self._append_manual_response("💡 建议: 服务器可能关闭了连接，请重新连接")
            self._manual_disconnect()  # 自动断开连接
        except BrokenPipeError:
            # 更新状态显示（管道断开）
            self.response_status.setText("TCP 管道断开")
            self.response_time.setText("0ms")
            self.response_size.setText("0B")
            
            self._append_manual_response("❌ 连接管道已断开")
            self._append_manual_response("💡 建议: 连接已中断，请重新建立连接")
            self._manual_disconnect()  # 自动断开连接
        except OSError as e:
            # 更新状态显示（系统错误）
            self.response_status.setText("TCP 系统错误")
            self.response_time.setText("0ms")
            self.response_size.setText("0B")
            
            if e.errno == 10054:  # Windows: 远程主机强制关闭连接
                self._append_manual_response("❌ 远程主机强制关闭了连接")
                self._append_manual_response("💡 建议: 服务器可能崩溃或重启，请检查服务器状态")
                self._manual_disconnect()
            else:
                self._append_manual_response(f"❌ 网络错误: {str(e)}")
                self._append_manual_response("💡 建议: 检查网络连接状态")
        except Exception as e:
            # 更新状态显示（一般错误）
            self.response_status.setText("TCP 发送错误")
            self.response_time.setText("0ms")
            self.response_size.setText("0B")
            
            self._append_manual_response(f"❌ Socket发送错误: {str(e)}")
            self._append_manual_response("💡 建议: 检查连接状态和命令格式")
    
    def _manual_send_websocket(self, command):
        """通过WebSocket发送命令"""
        try:
            # 记录开始时间
            start_time = time.time()
            
            # 发送命令
            self.manual_websocket.send(command)
            
            # 接收响应
            self.manual_websocket.settimeout(5.0)  # 设置接收超时
            response = self.manual_websocket.recv()
            
            # 计算响应时间
            response_time = (time.time() - start_time) * 1000  # 转换为毫秒
            
            if response and response.strip():  # 检查响应是否非空且不只是空白字符
                self._append_manual_response(f"<<< {response}")
                # 更新原始数据显示
                self.raw_data_display.setPlainText(response)
                # 只有有效响应才更新接收计数
                self._update_data_flow_visual("接收", response)
                self.manual_received_count.setText(str(self.manual_received_count_value))
                
                # 更新状态显示
                data_size = len(response.encode('utf-8'))  # 计算数据大小
                self.response_status.setText("响应成功")
                self.response_time.setText(f"{response_time:.1f}ms")
                self.response_size.setText(f"{data_size}B")
            else:
                self._append_manual_response("<<< (无响应或空响应)")
                # 更新原始数据显示为空响应提示
                self.raw_data_display.setPlainText("(无响应或空响应)")
                # 空响应不计入接收统计，只显示在数据流中
                self._update_data_flow_visual_no_count("接收", "(无响应)")
                
                # 更新状态显示
                self.response_status.setText("无响应")
                self.response_time.setText(f"{response_time:.1f}ms")
                self.response_size.setText("0B")
                
        except websocket.WebSocketTimeoutException:
            self._append_manual_response("❌ WebSocket响应超时 (>5s)")
            self._append_manual_response("💡 建议: 服务器响应较慢，或检查WebSocket连接状态")
            # 更新状态显示
            response_time = (time.time() - start_time) * 1000
            self.response_status.setText("响应超时")
            self.response_time.setText(f"{response_time:.1f}ms")
            self.response_size.setText("0B")
        except websocket.WebSocketConnectionClosedException:
            self._append_manual_response("❌ WebSocket连接已关闭")
            self._append_manual_response("💡 建议: 连接被服务器关闭，请重新建立连接")
            self._manual_disconnect()  # 自动断开连接
            # 更新状态显示
            response_time = (time.time() - start_time) * 1000
            self.response_status.setText("连接已关闭")
            self.response_time.setText(f"{response_time:.1f}ms")
            self.response_size.setText("0B")
        except ConnectionResetError:
            self._append_manual_response("❌ WebSocket连接被重置")
            self._append_manual_response("💡 建议: 服务器强制关闭了连接，请重新连接")
            self._manual_disconnect()  # 自动断开连接
            # 更新状态显示
            response_time = (time.time() - start_time) * 1000
            self.response_status.setText("连接被重置")
            self.response_time.setText(f"{response_time:.1f}ms")
            self.response_size.setText("0B")
        except Exception as e:
            error_msg = str(e).lower()
            response_time = (time.time() - start_time) * 1000
            if 'connection' in error_msg and ('closed' in error_msg or 'reset' in error_msg):
                self._append_manual_response("❌ WebSocket连接中断")
                self._append_manual_response("💡 建议: 连接已断开，请重新建立连接")
                self._manual_disconnect()
                # 更新状态显示
                self.response_status.setText("连接中断")
                self.response_time.setText(f"{response_time:.1f}ms")
                self.response_size.setText("0B")
            elif 'timeout' in error_msg:
                self._append_manual_response("❌ WebSocket操作超时")
                self._append_manual_response("💡 建议: 网络延迟较高，请检查网络连接")
                # 更新状态显示
                self.response_status.setText("操作超时")
                self.response_time.setText(f"{response_time:.1f}ms")
                self.response_size.setText("0B")
            else:
                self._append_manual_response(f"❌ WebSocket发送错误: {str(e)}")
                self._append_manual_response("💡 建议: 检查WebSocket连接状态和消息格式")
                # 更新状态显示
                self.response_status.setText("发送错误")
                self.response_time.setText(f"{response_time:.1f}ms")
                self.response_size.setText("0B")
    
    def _manual_send_as_http(self, path):
        """以HTTP请求方式发送命令"""
        try:
            config = self._get_current_config()
            if not config:
                self._append_manual_response("错误: 无法获取配置")
                return
            
            # 如果路径不以/开头，自动添加
            if not path.startswith('/'):
                path = '/' + path
            
            # 构建HTTP请求
            url = f"http://{config.host}:{config.port}{path}"
            
            # 创建请求
            request = urllib.request.Request(url)
            request.add_header('User-Agent', config.user_agent)
            
            # 记录开始时间
            start_time = time.time()
            
            # 发送请求并获取响应
            with urllib.request.urlopen(request, timeout=config.timeout) as response:
                response_data = response.read().decode('utf-8', errors='ignore')
                status_code = response.getcode()
                
                # 计算响应时间
                response_time = (time.time() - start_time) * 1000  # 转换为毫秒
                
                # 显示响应
                if response_data and response_data.strip():
                    self._append_manual_response(f"<<< HTTP {status_code} - {response_data.strip()[:200]}{'...' if len(response_data) > 200 else ''}")
                    # 更新原始数据显示
                    self.raw_data_display.setPlainText(response_data)
                    self._update_data_flow_visual("接收", f"HTTP {status_code}")
                    # 更新接收计数
                    self.manual_received_count_value += 1
                    self.manual_received_count.setText(str(self.manual_received_count_value))
                    
                    # 更新状态显示
                    data_size = len(response_data.encode('utf-8'))  # 计算数据大小
                    self.response_status.setText(f"HTTP {status_code}")
                    self.response_time.setText(f"{response_time:.1f}ms")
                    self.response_size.setText(f"{data_size}B")
                else:
                    self._append_manual_response(f"<<< HTTP {status_code} - (空响应体)")
                    # 更新原始数据显示为空响应提示
                    self.raw_data_display.setPlainText(f"HTTP {status_code} - (空响应体)")
                    self._update_data_flow_visual_no_count("接收", f"HTTP {status_code} (空响应)")
                    
                    # 更新状态显示
                    self.response_status.setText(f"HTTP {status_code}")
                    self.response_time.setText(f"{response_time:.1f}ms")
                    self.response_size.setText("0B")
                
        except urllib.error.HTTPError as e:
            response_time = (time.time() - start_time) * 1000
            error_msg = e.read().decode('utf-8', errors='ignore') if hasattr(e, 'read') else str(e)
            self._append_manual_response(f"<<< HTTP {e.code} - {error_msg.strip()[:200]}{'...' if len(error_msg) > 200 else ''}")
            # 更新原始数据显示为错误信息
            self.raw_data_display.setPlainText(f"HTTP {e.code} Error\n\n{error_msg}")
            self._update_data_flow_visual("接收", f"HTTP {e.code} Error")
            
            # 更新接收计数（错误响应也算接收）
            self.manual_received_count_value += 1
            self.manual_received_count.setText(str(self.manual_received_count_value))
            
            # 更新状态显示
            data_size = len(error_msg.encode('utf-8')) if error_msg else 0
            self.response_status.setText(f"HTTP {e.code}")
            self.response_time.setText(f"{response_time:.1f}ms")
            self.response_size.setText(f"{data_size}B")
            
        except urllib.error.URLError as e:
            response_time = (time.time() - start_time) * 1000
            self._append_manual_response(f"❌ HTTP请求失败: {str(e)}")
            self._append_manual_response("💡 建议: 检查URL格式和网络连接")
            # 更新状态显示
            self.response_status.setText("请求失败")
            self.response_time.setText(f"{response_time:.1f}ms")
            self.response_size.setText("0B")
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self._append_manual_response(f"❌ HTTP请求异常: {str(e)}")
            # 更新状态显示
            self.response_status.setText("请求异常")
            self.response_time.setText(f"{response_time:.1f}ms")
            self.response_size.setText("0B")
            self._append_manual_response("💡 建议: 检查服务器状态和请求格式")
    
    def _manual_send_http_request(self):
         """发送HTTP请求"""
         try:
             config = self._get_current_config()
             if not config:
                 self._append_manual_response("❌ 错误: 请先配置连接参数")
                 return
             
             # 构建URL
             protocol = "https" if config.use_ssl else "http"
             url = f"{protocol}://{config.host}:{config.port}{config.http_path}"
             
             self._append_manual_response(f">>> HTTP {config.http_method} {url}")
             self._update_data_flow_visual("发送", f"HTTP {config.http_method} {url}")
             
             start_time = time.time()
             
             # 创建请求
             req = urllib.request.Request(url, method=config.http_method)
             
             # 添加请求头
             req.add_header('User-Agent', config.user_agent)
             for key, value in config.http_headers.items():
                 req.add_header(key, value)
             
             # 添加POST数据
             if config.http_method in ['POST', 'PUT'] and config.post_data:
                 req.data = config.post_data.encode('utf-8')
                 req.add_header('Content-Type', 'application/json')
             
             # 发送请求
             with urllib.request.urlopen(req, timeout=config.timeout) as response:
                 response_data = response.read().decode('utf-8', errors='ignore')
                 response_time = (time.time() - start_time) * 1000
                 
                 # 显示响应
                 status_line = f"HTTP {response.status} {response.reason}"
                 self._append_manual_response(f"<<< {status_line}")
                 
                 # 显示响应头（限制显示数量）
                 headers_shown = 0
                 for header, value in response.headers.items():
                     if headers_shown < 5:  # 只显示前5个重要头
                         if header.lower() in ['content-type', 'content-length', 'server', 'date', 'connection']:
                             self._append_manual_response(f"    {header}: {value}")
                             headers_shown += 1
                 
                 # 显示响应体（截断长内容）
                 if response_data and response_data.strip():
                     if len(response_data) > 500:
                         truncated_data = response_data[:500] + "...(截断)"
                         self._append_manual_response(f"    Body: {truncated_data}")
                     else:
                         self._append_manual_response(f"    Body: {response_data}")
                     # 更新原始数据显示
                     self.raw_data_display.setPlainText(response_data)
                 else:
                     self._append_manual_response(f"    Body: (空响应体)")
                     # 更新原始数据显示为空响应提示
                     self.raw_data_display.setPlainText(f"HTTP {response.status} - (空响应体)")
                 
                 self._append_manual_response(f"    响应时间: {response_time:.2f}ms")
                 
                 self._update_data_flow_visual("接收", f"{status_line} ({response_time:.2f}ms)")
                 
                 # 更新响应详情区域
                 self.response_status.setText(f"HTTP {response.status} {response.reason}")
                 self.response_time.setText(f"{response_time:.2f}ms")
                 data_size = len(response_data.encode('utf-8')) if response_data else 0
                 if data_size >= 1024:
                     self.response_size.setText(f"{data_size/1024:.1f}KB")
                 else:
                     self.response_size.setText(f"{data_size}B")
                 
                 # 更新统计
                 self.manual_response_times.append(response_time)
                 self.manual_sent_count_value += 1
                 # 只有有效响应体才计入接收统计
                 if response_data and response_data.strip():
                     self.manual_received_count_value += 1
                 self.manual_sent_count.setText(str(self.manual_sent_count_value))
                 self.manual_received_count.setText(str(self.manual_received_count_value))
                 
                 avg_time = sum(self.manual_response_times) / len(self.manual_response_times)
                 self.manual_avg_response.setText(f"{avg_time:.1f}ms")
                 
         except urllib.error.HTTPError as e:
             response_time = (time.time() - start_time) * 1000 if 'start_time' in locals() else 0
             self._append_manual_response(f"❌ HTTP错误: {e.code} {e.reason}")
             
             # 更新原始数据显示为错误信息
             error_msg = e.read().decode('utf-8', errors='ignore') if hasattr(e, 'read') else str(e)
             self.raw_data_display.setPlainText(f"HTTP {e.code} Error\n\n{error_msg}")
             
             # 更新响应详情区域
             self.response_status.setText(f"HTTP {e.code} {e.reason}")
             self.response_time.setText(f"{response_time:.2f}ms")
             error_size = len(error_msg.encode('utf-8')) if error_msg else 0
             if error_size >= 1024:
                 self.response_size.setText(f"{error_size/1024:.1f}KB")
             else:
                 self.response_size.setText(f"{error_size}B")
             
             if e.code == 400:
                 self._append_manual_response("💡 建议: 检查请求参数和数据格式")
             elif e.code == 401:
                 self._append_manual_response("💡 建议: 检查认证信息或Token")
             elif e.code == 403:
                 self._append_manual_response("💡 建议: 检查访问权限")
             elif e.code == 404:
                 self._append_manual_response("💡 建议: 检查URL路径是否正确")
             elif e.code == 500:
                 self._append_manual_response("💡 建议: 服务器内部错误，检查服务器日志")
             elif e.code == 502:
                 self._append_manual_response("💡 建议: 网关错误，检查代理服务器配置")
             elif e.code == 503:
                 self._append_manual_response("💡 建议: 服务不可用，稍后重试")
             else:
                 self._append_manual_response("💡 建议: 检查服务器状态和请求参数")
                 
             self._update_data_flow_visual("接收", f"HTTP {e.code} 错误")
             
         except urllib.error.URLError as e:
             # 更新原始数据显示为连接错误信息
             self.raw_data_display.setPlainText(f"URL Error\n\n{str(e)}")
             
             # 更新响应详情区域
             self.response_status.setText("连接失败")
             self.response_time.setText("0ms")
             error_size = len(str(e).encode('utf-8'))
             if error_size >= 1024:
                 self.response_size.setText(f"{error_size/1024:.1f}KB")
             else:
                 self.response_size.setText(f"{error_size}B")
             
             if "timed out" in str(e).lower():
                 self._append_manual_response(f"❌ HTTP请求超时 (>{config.timeout}s)")
                 self._append_manual_response("💡 建议: 增加超时时间或检查网络连接")
             elif "connection refused" in str(e).lower():
                 self._append_manual_response(f"❌ HTTP连接被拒绝 - 端口 {config.port} 未开放")
                 self._append_manual_response("💡 建议: 确认HTTP服务器正在运行")
             elif "name or service not known" in str(e).lower() or "nodename nor servname provided" in str(e).lower():
                 self._append_manual_response(f"❌ 域名解析失败: {config.host}")
                 self._append_manual_response("💡 建议: 检查主机名是否正确，或使用IP地址")
             else:
                 self._append_manual_response(f"❌ HTTP连接错误: {str(e)}")
                 self._append_manual_response("💡 建议: 检查网络连接和服务器状态")
                 
         except Exception as e:
             # 更新原始数据显示为异常信息
             self.raw_data_display.setPlainText(f"异常\n\n{str(e)}")
             
             # 更新响应详情区域
             self.response_status.setText("请求失败")
             self.response_time.setText("0ms")
             error_size = len(str(e).encode('utf-8'))
             if error_size >= 1024:
                 self.response_size.setText(f"{error_size/1024:.1f}KB")
             else:
                 self.response_size.setText(f"{error_size}B")
             
             self._append_manual_response(f"❌ HTTP请求失败: {str(e)}")
             self._append_manual_response("💡 建议: 检查配置参数和网络连接")
    

    
    def _append_manual_response(self, text):
        """添加响应文本"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.manual_response_display.append(f"[{timestamp}] {text}")
        
        # 自动滚动到底部
        cursor = self.manual_response_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.manual_response_display.setTextCursor(cursor)
    
    def _update_manual_connection_status(self, connected, config, connect_time):
        """更新手动测试连接状态"""
        if connected:
            self.manual_connection_status.setText("🟢 已连接")
            
            info_text = f"📡 协议: {config.protocol}\n"
            info_text += f"🌐 地址: {config.host}:{config.port}\n"
            info_text += f"⚡ 连接时间: {connect_time:.2f}ms"
            self.manual_connection_info.setText(info_text)
            
            # 更新状态显示标签
            self.response_status.setText(f"{config.protocol} 已连接")
            self.response_time.setText(f"{connect_time:.2f}ms")
            self.response_size.setText("0B")  # 连接时数据大小为0
            
            self.manual_connect_btn.setEnabled(False)
            self.manual_disconnect_btn.setEnabled(True)
            self.manual_send_btn.setEnabled(True)
            
            # 开始计时
            self.manual_connection_start_time = time.time()
            self.manual_timer.start(1000)  # 每秒更新一次
            
        else:
            self.manual_connection_status.setText("🔴 未连接")
            self.manual_connection_info.clear()
            
            # 重置状态显示标签
            self.response_status.setText("未连接")
            self.response_time.setText("0ms")
            self.response_size.setText("0B")
            
            self.manual_connect_btn.setEnabled(True)
            self.manual_disconnect_btn.setEnabled(False)
            self.manual_send_btn.setEnabled(False)
            
            # 停止计时
            self.manual_timer.stop()
            self.manual_connection_time.setText("00:00:00")
    
    def _update_manual_connection_time(self):
        """更新连接时长"""
        if self.manual_connection_start_time:
            elapsed = int(time.time() - self.manual_connection_start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            self.manual_connection_time.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def _save_manual_response(self):
        """保存手动测试响应"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            from datetime import datetime
            
            filename, _ = QFileDialog.getSaveFileName(
                self, "保存响应日志", 
                f"manual_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "文本文件 (*.txt);;所有文件 (*.*)"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.manual_response_display.toPlainText())
                self._append_manual_response(f"响应日志已保存到: {filename}")
                
        except Exception as e:
            self._append_manual_response(f"保存失败: {str(e)}")
    
    def _create_bottom_buttons(self, layout):
        """创建底部按钮"""
        button_layout = QHBoxLayout()
        
        help_btn = QPushButton("帮助")
        help_btn.clicked.connect(self._show_help)
        button_layout.addWidget(help_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _update_ui_from_config(self):
        """从配置更新UI"""
        self.protocol_combo.setCurrentText(self.config.protocol)
        self.host_edit.setText(self.config.host)
        self.port_spin.setValue(self.config.port)
        self.ssl_check.setChecked(self.config.use_ssl)
        self.timeout_spin.setValue(self.config.timeout)
        self.retry_spin.setValue(self.config.retry_count)
        self.retry_delay_spin.setValue(self.config.retry_delay)
        self.concurrent_spin.setValue(self.config.concurrent_connections)
        self.duration_spin.setValue(self.config.test_duration)
        self.interval_spin.setValue(self.config.message_interval)
        self.auth_edit.setText(self.config.auth_token)
        self.user_agent_edit.setText(self.config.user_agent)
        self.http_method_combo.setCurrentText(self.config.http_method)
        self.http_path_edit.setText(self.config.http_path)
        self.http_headers_edit.setPlainText(json.dumps(self.config.http_headers, indent=2, ensure_ascii=False))
        self.post_data_edit.setPlainText(self.config.post_data)
        
        # WebSocket配置
        if hasattr(self, 'websocket_subprotocol_edit'):
            self.websocket_subprotocol_edit.setText(self.config.websocket_subprotocol)
            self.websocket_ping_spin.setValue(self.config.websocket_ping_interval)
        
        self.commands_edit.setPlainText("\n".join(self.config.custom_commands))
        
        # 触发协议改变处理
        self._on_protocol_changed(self.config.protocol)
    
    def _update_config_from_ui(self):
        """从UI更新配置"""
        self.config.protocol = self.protocol_combo.currentText()
        self.config.host = self.host_edit.text().strip()
        self.config.port = self.port_spin.value()
        self.config.use_ssl = self.ssl_check.isChecked()
        self.config.timeout = self.timeout_spin.value()
        self.config.retry_count = self.retry_spin.value()
        self.config.retry_delay = self.retry_delay_spin.value()
        self.config.concurrent_connections = self.concurrent_spin.value()
        self.config.test_duration = self.duration_spin.value()
        self.config.message_interval = self.interval_spin.value()
        self.config.auth_token = self.auth_edit.text().strip()
        self.config.user_agent = self.user_agent_edit.text().strip()
        self.config.http_method = self.http_method_combo.currentText()
        self.config.http_path = self.http_path_edit.text().strip() or "/"
        self.config.post_data = self.post_data_edit.toPlainText().strip()
        
        # 解析HTTP请求头
        try:
            headers_text = self.http_headers_edit.toPlainText().strip()
            if headers_text:
                self.config.http_headers = json.loads(headers_text)
            else:
                self.config.http_headers = {"User-Agent": self.config.user_agent}
        except json.JSONDecodeError:
            self.config.http_headers = {"User-Agent": self.config.user_agent}
        
        # WebSocket配置
        if hasattr(self, 'websocket_subprotocol_edit'):
            self.config.websocket_subprotocol = self.websocket_subprotocol_edit.text().strip()
            self.config.websocket_ping_interval = self.websocket_ping_spin.value()
        
        # 获取自定义命令
        commands_text = self.commands_edit.toPlainText().strip()
        self.config.custom_commands = [cmd.strip() for cmd in commands_text.split('\n') if cmd.strip()] if commands_text else ["ping"]
    
    def _get_all_preset_commands(self):
        """获取所有预设命令的字典结构"""
        return {
            "HTTP": {
                "basic": ["/", "/api/status", "/api/health", "/api/version"],
                "debug": ["/", "/api/status", "/api/debug", "/api/metrics", "/api/info", "/admin/stats"],
                "stress": ["/"] * 20 + ["/api/status"] * 10 + ["/api/health"] * 5,
                "rest_api": ["/api/users", "/api/products", "/api/orders", "/api/auth/login", "/api/config"]
            },
            "WebSocket": {
                "basic": ['{"type":"ping"}', '{"type":"echo","message":"Hello WebSocket"}', '{"type":"status"}'],
                "debug": ['{"type":"ping"}', '{"type":"status"}', '{"type":"info"}', '{"type":"debug"}', '{"type":"metrics"}'],
                "stress": ['{"type":"ping"}'] * 20 + ['{"type":"echo","message":"test"}'] * 10,
                "chat": ['{"type":"join","room":"test"}', '{"type":"message","text":"Hello"}', '{"type":"leave","room":"test"}'],
                "subscribe": ['{"type":"subscribe","channel":"updates"}', '{"type":"ping"}', '{"type":"unsubscribe","channel":"updates"}']
            },
            "TCP": {
                "basic": ["ping", "status", "help", "version"],
                "debug": ["ping", "status", "debug_info", "get_clients", "get_stats", "memory_info"],
                "stress": ["ping"] * 10 + ["status"] * 5 + ["help"] * 3,
                "telnet": ["help", "quit", "status", "info"],
                "custom": ["HELO", "QUIT", "NOOP", "RSET"]
            }
        }
    
    def _load_preset_commands(self, preset_type: str):
        """加载预设命令"""
        if self.protocol_combo.currentText() in ["HTTP", "HTTPS"]:
            # HTTP/HTTPS预设
            presets = {
                "basic": ["/", "/api/status", "/api/health", "/api/version"],
                "debug": ["/", "/api/status", "/api/debug", "/api/metrics", "/api/info", "/admin/stats"],
                "stress": ["/"] * 20 + ["/api/status"] * 10 + ["/api/health"] * 5,
                "rest_api": ["/api/users", "/api/products", "/api/orders", "/api/auth/login", "/api/config"]
            }
        elif self.protocol_combo.currentText() == "WebSocket":
            # WebSocket预设
            presets = {
                "basic": ['{"type":"ping"}', '{"type":"echo","message":"Hello WebSocket"}', '{"type":"status"}'],
                "debug": ['{"type":"ping"}', '{"type":"status"}', '{"type":"info"}', '{"type":"debug"}', '{"type":"metrics"}'],
                "stress": ['{"type":"ping"}'] * 20 + ['{"type":"echo","message":"test"}'] * 10,
                "chat": ['{"type":"join","room":"test"}', '{"type":"message","text":"Hello"}', '{"type":"leave","room":"test"}'],
                "subscribe": ['{"type":"subscribe","channel":"updates"}', '{"type":"ping"}', '{"type":"unsubscribe","channel":"updates"}']
            }
        else:
            # TCP预设
            presets = {
                "basic": ["ping", "status", "help", "version"],
                "debug": ["ping", "status", "debug_info", "get_clients", "get_stats", "memory_info"],
                "stress": ["ping"] * 10 + ["status"] * 5 + ["help"] * 3,
                "telnet": ["help", "quit", "status", "info"],
                "custom": ["HELO", "QUIT", "NOOP", "RSET"]
            }
        
        if preset_type in presets:
            self.commands_edit.setPlainText("\n".join(presets[preset_type]))
    
    def _on_port_manually_changed(self, value):
        """端口被用户手动修改时的处理"""
        # 如果当前端口值不是自动设置的，则标记为手动修改
        if self._last_auto_port is None or value != self._last_auto_port:
            self._port_manually_changed = True
            self._update_port_status_label()
    
    def _on_protocol_changed(self, protocol: str):
        """协议改变时的处理"""
        # 显示或隐藏配置组
        self.http_group.setVisible(protocol in ["HTTP", "HTTPS"])
        if hasattr(self, 'websocket_group'):
            self.websocket_group.setVisible(protocol == "WebSocket")
        
        # 智能端口设置：只有在用户没有手动修改过端口时才自动设置
        if not self._port_manually_changed:
            default_port = self._get_default_port_for_protocol(protocol)
            if default_port:
                # 临时断开信号连接，避免触发手动修改标记
                self.port_spin.valueChanged.disconnect(self._on_port_manually_changed)
                self.port_spin.setValue(default_port)
                self._last_auto_port = default_port
                # 重新连接信号
                self.port_spin.valueChanged.connect(self._on_port_manually_changed)
        
        # 更新端口状态标签
        self._update_port_status_label()
        
        # 设置SSL选项
        if protocol == "HTTP":
            self.ssl_check.setChecked(False)
        elif protocol == "HTTPS":
            self.ssl_check.setChecked(True)
        elif protocol == "WebSocket":
            self.ssl_check.setChecked(False)
        elif protocol == "TCP":
            self.ssl_check.setChecked(False)
        
        # 更新命令提示
        if protocol in ["HTTP", "HTTPS"]:
            self.commands_edit.setPlaceholderText("每行一个URL路径，例如:\n/\n/api/status\n/api/health\n/api/users")
        elif protocol == "WebSocket":
            self.commands_edit.setPlaceholderText("每行一个消息，例如:\n{\"type\": \"ping\"}\n{\"action\": \"subscribe\", \"channel\": \"test\"}\nHello WebSocket")
        else:
            self.commands_edit.setPlaceholderText("每行一个命令，例如:\nping\nstatus\nhelp\nget_info")
    
    def _get_default_port_for_protocol(self, protocol: str) -> int:
        """获取协议的默认端口"""
        default_ports = {
            "HTTP": 80,
            "HTTPS": 443,
            "WebSocket": 8080,
            "TCP": 8080
        }
        return default_ports.get(protocol, 8080)
    
    def _reset_port_auto_detection(self):
        """重置端口自动识别状态，允许重新自动设置端口"""
        self._port_manually_changed = False
        self._last_auto_port = None
        # 立即应用当前协议的默认端口
        current_protocol = self.protocol_combo.currentText()
        if current_protocol:
            self._on_protocol_changed(current_protocol)
        QMessageBox.information(self, "成功", "端口自动识别已重置，程序将根据协议自动设置端口")
    
    def _update_port_status_label(self):
        """更新端口状态标签"""
        if hasattr(self, 'port_status_label'):
            if self._port_manually_changed:
                self.port_status_label.setText("端口已手动设置")
                self.port_status_label.setStyleSheet("color: #ff6b35; font-size: 11px;")
            else:
                current_protocol = self.protocol_combo.currentText() if hasattr(self, 'protocol_combo') else ""
                if current_protocol:
                    default_port = self._get_default_port_for_protocol(current_protocol)
                    self.port_status_label.setText(f"自动设置 ({current_protocol}默认: {default_port})")
                    self.port_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
                else:
                    self.port_status_label.setText("")
                    self.port_status_label.setStyleSheet("color: #666; font-size: 11px;")
    
    def _start_test(self):
        """开始测试"""
        if self.test_thread and self.test_thread.is_running:
            QMessageBox.warning(self, "警告", "测试正在进行中")
            return
        
        self._update_config_from_ui()
        
        # 验证配置
        if not self.config.host:
            QMessageBox.warning(self, "错误", "请输入主机地址")
            return
        
        if not self.config.custom_commands:
            QMessageBox.warning(self, "错误", "请输入至少一个测试命令")
            return
        
        # 重置UI状态
        self.realtime_log.clear()
        self.progress_bar.setValue(0)
        self._update_stats_display(0, 0, 0, 0, 0)
        
        # 创建并启动测试线程
        self.test_thread = TestWorkerThread(self.config)
        self.test_thread.progress_updated.connect(self.progress_bar.setValue)
        self.test_thread.status_updated.connect(self._update_status)
        self.test_thread.log_updated.connect(self._add_realtime_log)
        self.test_thread.result_ready.connect(self._on_test_completed)
        
        self.test_thread.start()
        
        # 更新UI状态
        self.start_test_btn.setEnabled(False)
        self.stop_test_btn.setEnabled(True)
        self.status_label.setText("测试进行中...")
        self.status_label.setStyleSheet("font-weight: bold; color: orange;")
        
        # 启动统计更新定时器
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_realtime_stats)
        self.stats_timer.start(1000)  # 每秒更新一次
    
    def _stop_test(self):
        """停止测试"""
        if self.test_thread:
            self.test_thread.stop()
            self.status_label.setText("正在停止测试...")
            self.status_label.setStyleSheet("font-weight: bold; color: red;")
    
    def _quick_ping_test(self):
        """快速Ping测试"""
        self.commands_edit.setPlainText("ping")
        self.concurrent_spin.setValue(1)
        self.duration_spin.setValue(0)
        self.retry_spin.setValue(1)
        self._start_test()
    
    def _quick_stress_test(self):
        """快速压力测试"""
        self.commands_edit.setPlainText("ping\nstatus")
        self.concurrent_spin.setValue(5)
        self.duration_spin.setValue(10)
        self.interval_spin.setValue(0.5)
        self._start_test()
    
    def _update_status(self, status: str):
        """更新状态"""
        self.status_label.setText(status)
    
    def _add_realtime_log(self, message: str):
        """添加实时日志"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.realtime_log.append(log_entry)
        self.detailed_log.append(log_entry)
        
        if self.auto_scroll_check.isChecked():
            from PyQt6.QtGui import QTextCursor
            self.realtime_log.moveCursor(QTextCursor.MoveOperation.End)
            self.detailed_log.moveCursor(QTextCursor.MoveOperation.End)
    
    def _update_realtime_stats(self):
        """更新实时统计"""
        if self.test_thread and self.test_thread.is_running:
            # 获取测试线程的实时统计数据
            if hasattr(self, 'test_start_time'):
                duration = time.time() - self.test_start_time
                self.test_duration_label.setText(f"{duration:.1f}s")
                
                # 尝试从测试线程获取实时统计
                if hasattr(self.test_thread, 'current_stats'):
                    stats = self.test_thread.current_stats
                    if stats:
                        self._update_stats_display(
                            stats.get('total_requests', 0),
                            stats.get('successful_requests', 0), 
                            stats.get('failed_requests', 0),
                            stats.get('average_response_time', 0.0),
                            duration
                        )
    
    def _update_stats_display(self, total: int, success: int, failed: int, avg_response: float, duration: float):
        """更新统计显示"""
        self.total_requests_label.setText(str(total))
        self.success_requests_label.setText(str(success))
        self.failed_requests_label.setText(str(failed))
        
        if total > 0:
            success_rate = (success / total) * 100
            self.success_rate_label.setText(f"{success_rate:.1f}%")
            
            if success_rate >= 90:
                self.success_rate_label.setStyleSheet("color: green;")
            elif success_rate >= 70:
                self.success_rate_label.setStyleSheet("color: orange;")
            else:
                self.success_rate_label.setStyleSheet("color: red;")
        else:
            self.success_rate_label.setText("0%")
        
        self.avg_response_label.setText(f"{avg_response:.2f}ms")
        self.test_duration_label.setText(f"{duration:.1f}s")
        
        # 更新网络状态指标
        if hasattr(self, 'latency_value') and hasattr(self, 'throughput_value'):
            # 更新延迟显示
            self.latency_value.setText(f"{avg_response:.2f}ms")
            # 更新延迟进度条 (假设1000ms为最大值)
            latency_percent = min(int(avg_response), 1000)
            self.latency_bar.setValue(latency_percent)
            
            # 计算吞吐量 (请求数/秒)
            if duration > 0:
                throughput = total / duration
                self.throughput_value.setText(f"{throughput:.1f} msg/s")
                # 更新吞吐量进度条 (假设100 msg/s为最大值)
                throughput_percent = min(int(throughput), 100)
                self.throughput_bar.setValue(throughput_percent)
            else:
                self.throughput_value.setText("0 msg/s")
                self.throughput_bar.setValue(0)
    
    def _on_test_completed(self, result: TestResult):
        """测试完成处理"""
        # 停止统计定时器
        if hasattr(self, 'stats_timer'):
            self.stats_timer.stop()
        
        # 更新UI状态
        self.start_test_btn.setEnabled(True)
        self.stop_test_btn.setEnabled(False)
        
        if result.success:
            self.status_label.setText("测试完成")
            self.status_label.setStyleSheet("font-weight: bold; color: green;")
        else:
            self.status_label.setText("测试失败")
            self.status_label.setStyleSheet("font-weight: bold; color: red;")
        
        # 更新统计显示
        self._update_stats_display(
            result.total_requests,
            result.successful_requests,
            result.failed_requests,
            result.average_response_time,
            result.duration
        )
        
        # 添加到结果列表
        self.test_results.append(result)
        self._add_result_to_table(result)
        
        # 显示结果摘要
        self._show_test_summary(result)
    
    def _add_result_to_table(self, result: TestResult):
        """添加结果到表格"""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(result.start_time))
        
        items = [
            timestamp,
            "是" if result.success else "否",
            str(result.total_requests),
            f"{result.success_rate:.1f}%",
            f"{result.average_response_time:.2f}ms",
            f"{result.min_response_time:.2f}ms" if result.min_response_time != float('inf') else "N/A",
            f"{result.max_response_time:.2f}ms",
            f"{result.duration:.1f}s"
        ]
        
        for col, item in enumerate(items):
            table_item = QTableWidgetItem(item)
            if col == 1:  # 成功列
                if result.success:
                    table_item.setBackground(QColor(200, 255, 200))
                else:
                    table_item.setBackground(QColor(255, 200, 200))
            self.results_table.setItem(row, col, table_item)
    
    def _show_test_summary(self, result: TestResult):
        """显示测试摘要"""
        summary = f"""测试完成摘要:

总请求数: {result.total_requests}
成功请求: {result.successful_requests}
失败请求: {result.failed_requests}
成功率: {result.success_rate:.1f}%

响应时间统计:
平均: {result.average_response_time:.2f}ms
最小: {result.min_response_time:.2f}ms (如果有成功请求)
最大: {result.max_response_time:.2f}ms

测试持续时间: {result.duration:.1f}秒
"""
        
        if result.error_messages:
            summary += f"\n错误信息:\n" + "\n".join(result.error_messages[:5])
            if len(result.error_messages) > 5:
                summary += f"\n... 还有 {len(result.error_messages) - 5} 个错误"
        
        if result.success:
            QMessageBox.information(self, "测试完成", summary)
        else:
            QMessageBox.warning(self, "测试失败", summary)
    
    def _clear_results(self):
        """清空结果"""
        self.test_results.clear()
        self.results_table.setRowCount(0)
    
    def _export_results(self):
        """导出结果"""
        if not self.test_results:
            QMessageBox.information(self, "提示", "没有测试结果可导出")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出测试结果", f"test_results_{int(time.time())}.json", "JSON文件 (*.json)"
        )
        
        if filename:
            try:
                export_data = {
                    "export_time": time.time(),
                    "export_time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "config": asdict(self.config),
                    "results": [asdict(result) for result in self.test_results]
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                
                QMessageBox.information(self, "成功", f"结果已导出到: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
    
    def _save_log(self):
        """保存日志"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存详细日志", f"test_log_{int(time.time())}.txt", "文本文件 (*.txt)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.detailed_log.toPlainText())
                QMessageBox.information(self, "成功", f"日志已保存到: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
    
    def _save_config_to_file(self):
        """保存配置到文件"""
        try:
            self._update_config_from_ui()
            
            filename, _ = QFileDialog.getSaveFileName(
                self, "保存测试配置", f"test_config_{int(time.time())}.json", "JSON文件 (*.json)"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(asdict(self.config), f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "成功", f"配置已保存到: {filename}")
                # 同时保存到应用程序设置
                self._save_settings()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
    
    def _load_config_from_file(self):
        """从文件加载配置"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "加载测试配置", "", "JSON文件 (*.json)"
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # 创建新配置对象
                self.config = TestConfig(**config_data)
                self._update_ui_from_config()
                
                # 保存到应用程序设置
                self._save_settings()
                
                QMessageBox.information(self, "成功", f"配置已从 {filename} 加载")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载失败: {str(e)}")
    
    def _reset_config(self):
        """重置配置"""
        reply = QMessageBox.question(
            self, "确认", "确定要重置所有配置到默认值吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.config = TestConfig()
            self._reset_port_auto_detection()  # 重置端口自动识别状态
            self._update_ui_from_config()
            # 保存重置后的配置
            self._save_settings()
            QMessageBox.information(self, "成功", "配置已重置为默认值")
    
    def _show_help(self):
        """显示帮助"""
        help_text = """高级测试客户端帮助

功能说明:
• 支持单连接和并发连接测试
• 可自定义测试命令和参数
• 支持SSL/TLS连接测试
• 提供详细的性能统计
• 支持配置保存和加载
• 支持测试结果导出

使用步骤:
1. 在"配置"标签页设置连接参数
2. 配置测试参数（重试、并发等）
3. 设置自定义测试命令
4. 在"测试"标签页开始测试
5. 查看实时日志和统计
6. 在"结果"标签页查看历史结果

快速测试:
• 快速Ping: 执行单次ping命令测试
• 快速压力测试: 执行10秒并发测试

预设命令:
• 基础命令: 常用的基本测试命令
• 调试命令: 用于调试的详细命令
• 压力测试命令: 用于压力测试的重复命令

注意事项:
• 确保目标服务器正在运行
• 高并发测试可能对服务器造成压力
• SSL测试需要服务器支持SSL/TLS
• 测试结果会自动保存到结果表格中
"""
        
        QMessageBox.information(self, "帮助", help_text)
    
    def _load_settings(self):
        """加载设置"""
        try:
            settings = QSettings("AdvancedTestClient", "Config")
            
            # 恢复窗口大小和位置
            if settings.contains("geometry"):
                self.restoreGeometry(settings.value("geometry"))
            
            # 恢复配置
            if settings.contains("config"):
                try:
                    config_data = json.loads(settings.value("config"))
                    self.config = TestConfig(**config_data)
                except Exception as e:
                    print(f"加载配置失败，使用默认配置: {e}")
                    self.config = TestConfig()
        except Exception as e:
            print(f"加载设置失败: {e}")
            self.config = TestConfig()
    
    def _apply_current_config(self):
        """应用当前配置"""
        try:
            self._update_config_from_ui()
            self._save_settings()
            QMessageBox.information(self, "成功", "当前配置已应用并保存")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"应用配置失败: {str(e)}")
    
    def _save_settings(self):
        """保存设置"""
        try:
            settings = QSettings("AdvancedTestClient", "Config")
            
            # 保存窗口大小和位置
            settings.setValue("geometry", self.saveGeometry())
            
            # 保存配置
            self._update_config_from_ui()
            settings.setValue("config", json.dumps(asdict(self.config)))
            settings.sync()  # 强制同步到磁盘
        except Exception as e:
            print(f"保存设置失败: {e}")
    
    def closeEvent(self, event):
        """关闭事件"""
        # 停止正在运行的测试
        if self.test_thread and self.test_thread.is_running:
            reply = QMessageBox.question(
                self, "确认", "测试正在进行中，确定要关闭吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            
            self.test_thread.stop()
            self.test_thread.wait(3000)  # 等待最多3秒
        
        # 保存设置
        self._save_settings()
        
        event.accept()


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    
    # 创建测试配置
    config = TestConfig(
        host="localhost",
        port=8080,
        use_ssl=False,
        custom_commands=["ping", "status", "help"]
    )
    
    dialog = AdvancedTestClientDialog(initial_config=config)
    dialog.show()
    
    sys.exit(app.exec())