#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
远程调试集成模块

整合了三个版本的所有功能：
1. 基础功能 - 完整的远程调试服务器和客户端管理
2. 性能优化 - 连接池、异步处理、缓存机制、虚拟化表格
3. 高级功能 - 插件系统、脚本执行、文件传输、会话管理

特性开关：
- 用户可以选择启用/禁用特定功能模块
- 支持运行时动态切换功能
- 自动性能优化和资源管理
"""

import json
import socket
import threading
import time
import traceback
import sys
import os
import queue
import weakref
import hashlib
import base64
import importlib
import inspect
import tempfile
import secrets
import string
import ssl
from .advanced_test_client import AdvancedTestClientDialog, TestConfig
import zipfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple, Set, Any, Callable, Type
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import deque
from abc import ABC, abstractmethod
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget, QWidget,
    QGroupBox, QLabel, QPushButton, QLineEdit, QTextEdit, QTextBrowser,
    QTableWidget, QTableWidgetItem, QTableView, QComboBox, QSpinBox, QCheckBox,
    QSplitter, QFrame, QProgressBar, QMessageBox, QFileDialog,
    QInputDialog, QMenu, QHeaderView, QTreeWidget, QTreeWidgetItem,
    QListWidget, QListWidgetItem, QPlainTextEdit, QSlider, QDateTimeEdit,
    QAbstractItemView, QStyledItemDelegate, QApplication
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QObject, QThread, QMutex, QWaitCondition,
    QAbstractTableModel, QModelIndex, QVariant, QSortFilterProxyModel,
    QDateTime, QDir, QFileInfo
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QIcon, QAction, QPixmap, QPainter,
    QSyntaxHighlighter, QTextCharFormat
)


# ==================== 安全函数 ====================

def generate_secure_token(length: int = 32) -> str:
    """生成安全的随机令牌"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def validate_password_strength(password: str) -> tuple[bool, str]:
    """验证密码强度"""
    if len(password) < 8:
        return False, "密码长度至少需要8个字符"
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
    
    if not (has_upper and has_lower and has_digit and has_special):
        return False, "密码必须包含大写字母、小写字母、数字和特殊字符"
    
    return True, "密码强度符合要求"

def create_ssl_context(cert_path: str = "", key_path: str = "") -> ssl.SSLContext:
    """创建SSL上下文"""
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    
    if cert_path and key_path and os.path.exists(cert_path) and os.path.exists(key_path):
        context.load_cert_chain(cert_path, key_path)
    else:
        # 使用自签名证书（仅用于开发环境）
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    
    return context

# ==================== 辅助类定义 ====================

class TestClientThread(QThread):
    """测试客户端线程"""
    test_completed = pyqtSignal(bool, str)
    test_progress = pyqtSignal(str)
    
    def __init__(self, parent_widget):
        super().__init__()
        self.parent_widget = parent_widget
        
    def run(self):
        self._run_test()
        
    def _run_test(self):
        """在后台线程中执行测试"""
        try:
            self._perform_connection_test()
        except Exception as e:
            self.test_completed.emit(False, f"测试失败: {str(e)}")
            
    def _perform_connection_test(self):
        """执行实际的连接测试"""
        import socket
        import time
        
        try:
            # 创建测试客户端连接
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(30.0)  # 增加超时时间到30秒
            
            # 连接到服务器
            host = self.parent_widget.config.host
            port = self.parent_widget.config.port
            
            self.test_progress.emit(f"尝试连接到服务器 {host}:{port}, SSL启用: {self.parent_widget.config.enable_ssl}")
            test_socket.connect((host, port))
            
            # 如果启用了SSL，包装socket
            if self.parent_widget.config.enable_ssl:
                import ssl
                self.test_progress.emit("开始SSL握手...")
                context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                # 设置协议版本以兼容服务器
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                context.maximum_version = ssl.TLSVersion.TLSv1_3
                test_socket = context.wrap_socket(test_socket, server_hostname=host)
                self.test_progress.emit("SSL握手成功")
            
            # 处理认证（如果需要）
            authenticated = False
            if self.parent_widget.config.enable_auth:
                try:
                    self.test_progress.emit("等待服务器认证挑战...")
                    # 设置接收超时
                    test_socket.settimeout(15.0)  # 认证阶段使用15秒超时
                    
                    # 接收认证挑战
                    try:
                        auth_challenge_raw = test_socket.recv(1024)
                        self.test_progress.emit(f"[DEBUG] 收到原始数据长度: {len(auth_challenge_raw)} 字节")
                        self.test_progress.emit(f"[DEBUG] 原始数据(hex): {auth_challenge_raw.hex()}")
                        auth_challenge = auth_challenge_raw.decode('utf-8')
                        self.test_progress.emit(f"[DEBUG] 解码后数据: '{auth_challenge}'")
                        self.test_progress.emit(f"收到认证挑战: {auth_challenge.strip()}")
                    except socket.timeout:
                        self.test_progress.emit("等待认证挑战超时")
                        test_socket.close()
                        self.test_completed.emit(False, "认证挑战接收超时")
                        return
                    
                    # 解析认证挑战
                    try:
                        challenge_data = json.loads(auth_challenge)
                        if challenge_data.get('type') == 'auth_challenge':
                            # 发送认证响应
                            auth_token = self.parent_widget.config.auth_token
                            if not auth_token:
                                self.test_progress.emit("错误: 未配置认证令牌")
                                test_socket.close()
                                self.test_completed.emit(False, "认证失败: 未配置认证令牌")
                                return
                            
                            auth_response = json.dumps({
                                "type": "auth_response",
                                "token": auth_token
                            }) + "\n"  # 添加换行符
                            auth_response_bytes = auth_response.encode('utf-8')
                            self.test_progress.emit(f"[DEBUG] 发送认证响应: '{auth_response.strip()}'")
                            self.test_progress.emit(f"[DEBUG] 发送数据长度: {len(auth_response_bytes)} 字节")
                            self.test_progress.emit(f"[DEBUG] 发送数据(hex): {auth_response_bytes.hex()}")
                            test_socket.send(auth_response_bytes)
                            self.test_progress.emit("已发送认证响应，等待结果...")
                            
                            # 接收认证结果
                            try:
                                auth_result_raw = test_socket.recv(1024)
                                self.test_progress.emit(f"[DEBUG] 收到认证结果原始数据长度: {len(auth_result_raw)} 字节")
                                self.test_progress.emit(f"[DEBUG] 认证结果原始数据(hex): {auth_result_raw.hex()}")
                                auth_result = auth_result_raw.decode('utf-8')
                                self.test_progress.emit(f"[DEBUG] 认证结果解码后: '{auth_result}'")
                                self.test_progress.emit(f"认证结果: {auth_result.strip()}")
                            except socket.timeout:
                                self.test_progress.emit("等待认证结果超时")
                                test_socket.close()
                                self.test_completed.emit(False, "认证结果接收超时")
                                return
                            
                            try:
                                result_data = json.loads(auth_result)
                                if result_data.get('success'):
                                    authenticated = True
                                    self.test_progress.emit("认证成功，开始测试命令")
                                else:
                                    self.test_progress.emit(f"认证失败: {result_data.get('message', '未知错误')}")
                                    test_socket.close()
                                    self.test_completed.emit(False, f"认证失败: {result_data.get('message', '未知错误')}")
                                    return
                            except json.JSONDecodeError:
                                self.test_progress.emit("认证结果解析失败")
                                test_socket.close()
                                self.test_completed.emit(False, "认证结果解析失败")
                                return
                    except json.JSONDecodeError:
                        self.test_progress.emit("认证挑战解析失败")
                        test_socket.close()
                        self.test_completed.emit(False, "认证挑战解析失败")
                        return
                        
                except Exception as e:
                    self.test_progress.emit(f"认证过程失败: {str(e)}")
                    test_socket.close()
                    self.test_completed.emit(False, f"认证过程失败: {str(e)}")
                    return
            else:
                authenticated = True  # 未启用认证时直接标记为已认证
                self.test_progress.emit("未启用身份验证，直接开始测试")
            
            # 发送测试消息
            if authenticated:
                # 恢复正常的超时设置用于命令测试
                test_socket.settimeout(10.0)
                test_commands = ["ping", "status", "help"]
                
                for cmd in test_commands:
                    try:
                        # 发送JSON格式的命令
                        command_data = {
                            "command": cmd,
                            "args": []
                        }
                        message = json.dumps(command_data) + "\n"
                        test_socket.send(message.encode('utf-8'))
                        
                        # 接收响应
                        try:
                            response = test_socket.recv(1024).decode('utf-8')
                            self.test_progress.emit(f"测试命令 '{cmd}' 响应: {response.strip()}")
                        except socket.timeout:
                            self.test_progress.emit(f"测试命令 '{cmd}' 响应超时")
                        
                        time.sleep(0.5)  # 短暂延迟
                        
                    except Exception as e:
                        self.test_progress.emit(f"测试命令 '{cmd}' 失败: {str(e)}")
                    
            # 关闭测试连接
            test_socket.close()
            
            # 测试成功
            self.test_completed.emit(True, f"测试客户端连接成功！\n服务器地址: {host}:{port}\n测试命令: {', '.join(test_commands)}\n详细结果请查看日志")
            
        except socket.timeout:
            self.test_completed.emit(False, "连接服务器超时，请检查服务器状态")
            
        except ConnectionRefusedError:
            self.test_completed.emit(False, "无法连接到服务器，请确认服务器正在运行")
            
        except Exception as e:
            self.test_completed.emit(False, f"测试连接时发生错误: {str(e)}")


# ==================== 核心数据结构 ====================

class DebugServerState(Enum):
    """调试服务器状态枚举"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class ClientConnectionState(Enum):
    """客户端连接状态枚举"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class FeatureFlags(Enum):
    """功能开关枚举"""
    BASIC_DEBUG = "basic_debug"  # 基础调试功能
    PERFORMANCE_OPT = "performance_opt"  # 性能优化
    PLUGIN_SYSTEM = "plugin_system"  # 插件系统
    SCRIPT_EXECUTOR = "script_executor"  # 脚本执行
    FILE_TRANSFER = "file_transfer"  # 文件传输
    SESSION_MANAGER = "session_manager"  # 会话管理
    ADVANCED_TOOLS = "advanced_tools"  # 高级工具


@dataclass
class IntegratedServerConfig:
    """集成服务器配置"""
    # 基础配置
    host: str = "127.0.0.1"
    port: int = 9009
    password: str = ""  # 不再使用默认密码，强制用户设置
    max_clients: int = 10
    timeout: int = 30
    enable_auth: bool = True  # 默认启用身份验证
    auth_token: str = ""  # 将在初始化时生成安全令牌
    enable_ssl: bool = True  # 默认启用SSL加密
    ssl_cert_path: str = ""
    ssl_key_path: str = ""
    log_level: str = "调试"
    auto_start: bool = False
    
    # Web服务器配置
    enable_web_interface: bool = False
    web_host: str = "127.0.0.1"
    web_port: int = 8080
    websocket_port: int = 8081
    web_static_dir: str = "web_static"
    enable_websocket: bool = True
    web_auth_required: bool = True
    
    # 性能优化配置
    connection_pool_size: int = 50
    message_buffer_size: int = 100
    log_cache_size: int = 1000
    thread_pool_size: int = 5
    update_interval: int = 1000  # ms
    
    # 高级功能配置
    plugin_dir: str = "plugins"
    script_dir: str = "scripts"
    transfer_dir: str = "transfers"
    session_dir: str = "sessions"
    
    # 功能开关
    enabled_features: Set[FeatureFlags] = field(default_factory=lambda: {
        FeatureFlags.BASIC_DEBUG,
        FeatureFlags.PERFORMANCE_OPT
    })
    
    # UI设置
    auto_scroll: bool = True
    
    def to_dict(self) -> dict:
        data = asdict(self)
        data['enabled_features'] = [f.value for f in self.enabled_features]
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'IntegratedServerConfig':
        if 'enabled_features' in data:
            data['enabled_features'] = {FeatureFlags(f) for f in data['enabled_features']}
        return cls(**data)


@dataclass
class IntegratedClientInfo:
    """集成客户端信息"""
    client_id: str
    socket: socket.socket
    address: Tuple[str, int]
    connect_time: float
    state: ClientConnectionState
    last_activity: float
    user_agent: str = ""
    protocol_version: str = "1.0"
    authenticated: bool = False
    commands_sent: int = 0
    bytes_received: int = 0
    bytes_sent: int = 0
    
    # 性能优化字段
    message_buffer: bytes = field(default_factory=bytes)
    last_ping: float = field(default_factory=time.time)
    response_times: deque = field(default_factory=lambda: deque(maxlen=10))
    
    # 高级功能字段
    session_id: Optional[str] = None
    permissions: Set[str] = field(default_factory=set)
    custom_data: Dict[str, Any] = field(default_factory=dict)
    
    def add_response_time(self, response_time: float):
        """添加响应时间记录"""
        self.response_times.append(response_time)
        
    def get_avg_response_time(self) -> float:
        """获取平均响应时间"""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop('socket', None)  # 不序列化socket对象
        data.pop('message_buffer', None)  # 不序列化缓冲区
        data.pop('response_times', None)  # 不序列化响应时间
        data['permissions'] = list(self.permissions)
        return data


# ==================== 插件系统 ====================

class PluginInterface(ABC):
    """插件接口基类"""
    
    @abstractmethod
    def get_name(self) -> str:
        """获取插件名称"""
        pass
        
    @abstractmethod
    def get_version(self) -> str:
        """获取插件版本"""
        pass
        
    @abstractmethod
    def get_description(self) -> str:
        """获取插件描述"""
        pass
        
    @abstractmethod
    def initialize(self, server_context: Any) -> bool:
        """初始化插件"""
        pass
        
    @abstractmethod
    def cleanup(self) -> bool:
        """清理插件资源"""
        pass
        
    def get_commands(self) -> List[Type['DebugCommand']]:
        """获取插件提供的命令"""
        return []
        
    def get_ui_components(self) -> List[Any]:
        """获取插件提供的UI组件"""
        return []


@dataclass
class PluginInfo:
    """插件信息"""
    name: str
    version: str
    description: str
    author: str
    file_path: str
    enabled: bool = True
    loaded: bool = False
    instance: Optional[PluginInterface] = None
    load_time: Optional[float] = None
    error_message: Optional[str] = None


class PluginManager:
    """插件管理器"""
    
    def __init__(self, plugin_dir: str = "plugins"):
        self.plugin_dir = Path(plugin_dir)
        self.plugins: Dict[str, PluginInfo] = {}
        self.server_context = None
        
    def set_server_context(self, context: Any):
        """设置服务器上下文"""
        self.server_context = context
        
    def scan_plugins(self) -> List[str]:
        """扫描插件目录"""
        if not self.plugin_dir.exists():
            self.plugin_dir.mkdir(parents=True, exist_ok=True)
            return []
            
        plugin_files = []
        for file_path in self.plugin_dir.glob("*.py"):
            if file_path.name.startswith("__"):
                continue
                
            plugin_info = self._load_plugin_info(file_path)
            if plugin_info:
                self.plugins[plugin_info.name] = plugin_info
                plugin_files.append(plugin_info.name)
                
        return plugin_files
        
    def _load_plugin_info(self, file_path: Path) -> Optional[PluginInfo]:
        """加载插件信息"""
        try:
            # 读取插件文件获取元数据
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 简单的元数据解析（实际应该更严格）
            name = file_path.stem
            version = "1.0.0"
            description = "Plugin"
            author = "Unknown"
            
            # 尝试从文件内容中提取元数据
            lines = content.split('\n')
            for line in lines[:20]:  # 只检查前20行
                line = line.strip()
                if line.startswith('# Name:'):
                    name = line.split(':', 1)[1].strip()
                elif line.startswith('# Version:'):
                    version = line.split(':', 1)[1].strip()
                elif line.startswith('# Description:'):
                    description = line.split(':', 1)[1].strip()
                elif line.startswith('# Author:'):
                    author = line.split(':', 1)[1].strip()
                    
            return PluginInfo(
                name=name,
                version=version,
                description=description,
                author=author,
                file_path=str(file_path)
            )
            
        except Exception as e:
            print(f"从 {file_path} 加载插件信息失败: {e}")
            return None
            
    def load_plugin(self, plugin_name: str) -> bool:
        """加载插件"""
        if plugin_name not in self.plugins:
            return False
            
        plugin_info = self.plugins[plugin_name]
        if plugin_info.loaded:
            return True
            
        try:
            # 动态导入插件模块
            spec = importlib.util.spec_from_file_location(
                plugin_name, plugin_info.file_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找插件类
            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, PluginInterface) and 
                    obj != PluginInterface):
                    plugin_class = obj
                    break
                    
            if not plugin_class:
                plugin_info.error_message = "No plugin class found"
                return False
                
            # 创建插件实例
            plugin_instance = plugin_class()
            if not plugin_instance.initialize(self.server_context):
                plugin_info.error_message = "插件初始化失败"
                return False
                
            plugin_info.instance = plugin_instance
            plugin_info.loaded = True
            plugin_info.load_time = time.time()
            plugin_info.error_message = None
            
            return True
            
        except Exception as e:
            plugin_info.error_message = str(e)
            return False
            
    def unload_plugin(self, plugin_name: str) -> bool:
        """卸载插件"""
        if plugin_name not in self.plugins:
            return False
            
        plugin_info = self.plugins[plugin_name]
        if not plugin_info.loaded:
            return True
            
        try:
            if plugin_info.instance:
                plugin_info.instance.cleanup()
                
            plugin_info.instance = None
            plugin_info.loaded = False
            plugin_info.load_time = None
            
            return True
            
        except Exception as e:
            plugin_info.error_message = str(e)
            return False
            
    def get_plugin_commands(self) -> List[Type['DebugCommand']]:
        """获取所有插件提供的命令"""
        commands = []
        for plugin_info in self.plugins.values():
            if plugin_info.loaded and plugin_info.instance:
                commands.extend(plugin_info.instance.get_commands())
        return commands
        
    def get_loaded_plugins(self) -> List[PluginInfo]:
        """获取已加载的插件"""
        return [p for p in self.plugins.values() if p.loaded]
        
    def get_all_plugins(self) -> List[PluginInfo]:
        """获取所有插件"""
        return list(self.plugins.values())


# ==================== 命令系统 ====================

class DebugCommand:
    """调试命令基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        
    def execute(self, client: IntegratedClientInfo, args: List[str]) -> str:
        """执行命令"""
        return "Command not implemented"
        
    def get_help(self) -> str:
        """获取命令帮助"""
        return f"{self.name}: {self.description}"


class PingCommand(DebugCommand):
    """Ping命令"""
    
    def __init__(self):
        super().__init__("ping", "Test connection")
        
    def execute(self, client: IntegratedClientInfo, args: List[str]) -> str:
        return "pong"


class StatusCommand(DebugCommand):
    """状态命令"""
    
    def __init__(self, server):
        super().__init__("status", "Get server status")
        self.server = server
        
    def execute(self, client: IntegratedClientInfo, args: List[str]) -> str:
        stats = self.server.get_performance_stats()
        return json.dumps({
            "status": "running",
            "clients": len(self.server.connection_pool.active_connections),
            "uptime": time.time() - self.server.start_time,
            "stats": stats
        })


class ScriptCommand(DebugCommand):
    """脚本执行命令"""
    
    def __init__(self, script_executor):
        super().__init__("script", "Execute Python script")
        self.script_executor = script_executor
        
    def execute(self, client: IntegratedClientInfo, args: List[str]) -> str:
        if not args:
            return "错误: 未提供脚本"
            
        script = " ".join(args)
        result = self.script_executor.execute_script(script, client.client_id)
        return json.dumps(result)


class HelpCommand(DebugCommand):
    """帮助命令"""
    
    def __init__(self, command_registry):
        super().__init__("help", "Show available commands and their descriptions")
        self.command_registry = command_registry
        
    def execute(self, client: IntegratedClientInfo, args: List[str]) -> str:
        if args and len(args) > 0:
            # 显示特定命令的帮助
            command_name = args[0]
            if command_name in self.command_registry:
                command = self.command_registry[command_name]
                return f"{command.get_help()}\n\n详细说明: {self._get_detailed_help(command_name)}"
            else:
                return f"未知命令: {command_name}\n\n使用 'help' 查看所有可用命令"
        else:
            # 显示所有命令列表
            help_text = "=== 远程调试服务器命令列表 ===\n\n"
            help_text += "基础命令:\n"
            
            # 按类别组织命令
            basic_commands = ['ping', 'status', 'help']
            advanced_commands = ['script']
            
            for cmd_name in basic_commands:
                if cmd_name in self.command_registry:
                    cmd = self.command_registry[cmd_name]
                    help_text += f"  {cmd_name:<12} - {cmd.description}\n"
            
            if any(cmd in self.command_registry for cmd in advanced_commands):
                help_text += "\n高级命令:\n"
                for cmd_name in advanced_commands:
                    if cmd_name in self.command_registry:
                        cmd = self.command_registry[cmd_name]
                        help_text += f"  {cmd_name:<12} - {cmd.description}\n"
            
            # 显示插件命令
            plugin_commands = [name for name in self.command_registry.keys() 
                             if name not in basic_commands + advanced_commands]
            if plugin_commands:
                help_text += "\n插件命令:\n"
                for cmd_name in sorted(plugin_commands):
                    cmd = self.command_registry[cmd_name]
                    help_text += f"  {cmd_name:<12} - {cmd.description}\n"
            
            help_text += "\n使用方法:\n"
            help_text += "  help <命令名>  - 查看特定命令的详细帮助\n"
            help_text += "  help          - 显示此帮助信息\n"
            
            return help_text
    
    def _get_detailed_help(self, command_name: str) -> str:
        """获取命令的详细帮助信息"""
        detailed_help = {
            'ping': '测试与服务器的连接状态，服务器会返回 "pong" 响应',
            'status': '获取服务器当前状态，包括客户端数量、运行时间和性能统计',
            'script': '执行Python脚本代码。用法: script <Python代码>',
            'help': '显示命令帮助信息。用法: help [命令名]'
        }
        return detailed_help.get(command_name, '暂无详细说明')


# ==================== 脚本执行器 ====================

class ScriptExecutor:
    """脚本执行器"""
    
    def __init__(self):
        self.execution_history = deque(maxlen=100)
        self.global_namespace = {
            '__builtins__': __builtins__,
            'time': time,
            'json': json,
            'os': os,
            'sys': sys
        }
        
    def execute_script(self, script: str, client_id: str = None) -> Dict[str, Any]:
        """执行脚本"""
        start_time = time.time()
        
        try:
            # 创建局部命名空间
            local_namespace = {}
            
            # 执行脚本
            exec(script, self.global_namespace, local_namespace)
            
            execution_time = time.time() - start_time
            
            result = {
                "success": True,
                "result": str(local_namespace.get('result', 'Script executed successfully')),
                "execution_time": execution_time,
                "timestamp": time.time(),
                "client_id": client_id
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            result = {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "execution_time": execution_time,
                "timestamp": time.time(),
                "client_id": client_id
            }
            
        # 添加到历史记录
        self.execution_history.append({
            "script": script,
            "result": result,
            "timestamp": time.time()
        })
        
        return result
        
    def get_execution_history(self) -> List[Dict]:
        """获取执行历史"""
        return list(self.execution_history)
        
    def clear_history(self):
        """清空历史记录"""
        self.execution_history.clear()
        
    def reset_namespace(self):
        """重置命名空间"""
        # 保留基础模块，清除用户定义的变量
        user_vars = [k for k in self.global_namespace.keys() 
                    if not k.startswith('__') and k not in ['time', 'json', 'os', 'sys']]
        for var in user_vars:
            del self.global_namespace[var]


# ==================== 文件传输管理器 ====================

class FileTransferManager:
    """文件传输管理器"""
    
    def __init__(self, transfer_dir: str = "transfers"):
        self.transfer_dir = Path(transfer_dir)
        self.transfer_dir.mkdir(parents=True, exist_ok=True)
        self.transfer_history = deque(maxlen=100)
        
    def upload_file(self, file_path: str, data: bytes, client_id: str = None) -> str:
        """上传文件"""
        try:
            # 生成安全的文件名
            safe_filename = self._generate_safe_filename(file_path)
            full_path = self.transfer_dir / safe_filename
            
            # 写入文件
            with open(full_path, 'wb') as f:
                f.write(data)
                
            # 记录传输历史
            transfer_record = {
                "type": "upload",
                "original_path": file_path,
                "stored_path": str(full_path),
                "size": len(data),
                "timestamp": time.time(),
                "client_id": client_id,
                "success": True
            }
            
            self.transfer_history.append(transfer_record)
            return str(full_path)
            
        except Exception as e:
            transfer_record = {
                "type": "upload",
                "original_path": file_path,
                "error": str(e),
                "timestamp": time.time(),
                "client_id": client_id,
                "success": False
            }
            
            self.transfer_history.append(transfer_record)
            raise e
            
    def download_file(self, file_path: str, client_id: str = None) -> Optional[bytes]:
        """下载文件"""
        try:
            full_path = self.transfer_dir / file_path
            
            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
                
            with open(full_path, 'rb') as f:
                data = f.read()
                
            # 记录传输历史
            transfer_record = {
                "type": "download",
                "file_path": file_path,
                "size": len(data),
                "timestamp": time.time(),
                "client_id": client_id,
                "success": True
            }
            
            self.transfer_history.append(transfer_record)
            return data
            
        except Exception as e:
            transfer_record = {
                "type": "download",
                "file_path": file_path,
                "error": str(e),
                "timestamp": time.time(),
                "client_id": client_id,
                "success": False
            }
            
            self.transfer_history.append(transfer_record)
            return None
            
    def _generate_safe_filename(self, original_path: str) -> str:
        """生成安全的文件名"""
        filename = os.path.basename(original_path)
        # 移除危险字符
        safe_chars = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        safe_filename = "".join(c for c in filename if c in safe_chars)
        
        # 添加时间戳避免冲突
        timestamp = str(int(time.time()))
        name, ext = os.path.splitext(safe_filename)
        return f"{timestamp}_{name}{ext}"
        
    def get_transfer_history(self) -> List[Dict]:
        """获取传输历史"""
        return list(self.transfer_history)


# ==================== 会话管理器 ====================

class SessionManager:
    """会话管理器"""
    
    def __init__(self, session_dir: str = "sessions"):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.sessions: Dict[str, Dict] = {}
        self.current_session_id: Optional[str] = None
        
    def create_session(self, name: str, description: str = "") -> str:
        """创建新会话"""
        session_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()[:12]
        
        session_info = {
            "id": session_id,
            "name": name,
            "description": description,
            "created_time": time.time(),
            "last_access": time.time(),
            "state": {},
            "clients": [],
            "commands_history": []
        }
        
        self.sessions[session_id] = session_info
        self._save_session(session_id)
        
        return session_id
        
    def switch_session(self, session_id: str) -> bool:
        """切换会话"""
        if session_id in self.sessions:
            self.current_session_id = session_id
            self.sessions[session_id]["last_access"] = time.time()
            return True
        return False
        
    def save_session_state(self, session_id: str, state: Dict):
        """保存会话状态"""
        if session_id in self.sessions:
            self.sessions[session_id]["state"].update(state)
            self.sessions[session_id]["last_access"] = time.time()
            self._save_session(session_id)
            
    def _save_session(self, session_id: str):
        """保存会话到文件"""
        session_file = self.session_dir / f"{session_id}.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(self.sessions[session_id], f, indent=2)
            
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """获取会话信息"""
        return self.sessions.get(session_id)
        
    def get_all_sessions(self) -> List[Dict]:
        """获取所有会话"""
        return list(self.sessions.values())
        
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            session_file = self.session_dir / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
            return True
        return False


# ==================== 性能优化组件 ====================

class ConnectionPool:
    """连接池管理器"""
    
    def __init__(self, max_size: int = 50):
        self.max_size = max_size
        self.active_connections: Dict[str, IntegratedClientInfo] = {}
        self.connection_queue = queue.Queue(maxsize=max_size)
        self.mutex = threading.Lock()
        
    def add_connection(self, client: IntegratedClientInfo) -> bool:
        """添加连接到池中"""
        with self.mutex:
            if len(self.active_connections) >= self.max_size:
                return False
            self.active_connections[client.client_id] = client
            return True
            
    def remove_connection(self, client_id: str) -> Optional[IntegratedClientInfo]:
        """从池中移除连接"""
        with self.mutex:
            return self.active_connections.pop(client_id, None)
            
    def get_connection(self, client_id: str) -> Optional[IntegratedClientInfo]:
        """获取连接"""
        with self.mutex:
            return self.active_connections.get(client_id)
            
    def get_all_connections(self) -> List[IntegratedClientInfo]:
        """获取所有活跃连接"""
        with self.mutex:
            return list(self.active_connections.values())
            
    def cleanup_inactive_connections(self, timeout: int = 300):
        """清理不活跃的连接"""
        current_time = time.time()
        inactive_clients = []
        
        for client in self.active_connections.values():
            if current_time - client.last_activity > timeout:
                inactive_clients.append(client.client_id)
                
        # 批量清理不活跃连接
        for client_id in inactive_clients:
            client = self.remove_connection(client_id)
            if client and hasattr(client.socket, 'close'):
                try:
                    client.socket.close()
                except:
                    pass
                    
        return len(inactive_clients)
        
    def get_connection_stats(self) -> dict:
        """获取连接池统计信息"""
        current_time = time.time()
        total_connections = len(self.active_connections)
        active_connections = 0
        avg_response_time = 0
        total_response_times = 0
        
        for client in self.active_connections.values():
            if current_time - client.last_activity < 60:  # 1分钟内活跃
                active_connections += 1
            if client.response_times:
                avg_response_time += client.get_avg_response_time()
                total_response_times += 1
                
        return {
            "total_connections": total_connections,
            "active_connections": active_connections,
            "avg_response_time": avg_response_time / max(1, total_response_times),
            "pool_utilization": total_connections / self.max_size * 100
        }


class MessageProcessor:
    """消息处理器"""
    
    def __init__(self, max_workers: int = 5, server=None):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.command_registry: Dict[str, DebugCommand] = {}
        self.command_cache: Dict[str, Any] = {}  # 命令结果缓存
        self.cache_ttl = 60  # 缓存生存时间（秒）
        self.server = server  # 引用服务器实例以使用其_log方法
        self.stats = {
            "messages_processed": 0,
            "errors": 0,
            "avg_processing_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
    def _log(self, level: str, message: str):
        """记录日志"""
        if self.server and hasattr(self.server, '_log'):
            self.server._log(level, message)
        else:
            # 如果没有服务器引用，直接打印到控制台
            print(f"[{level}] {message}")
        
    def register_command(self, command: DebugCommand):
        """注册命令"""
        self.command_registry[command.name] = command
        
    def submit_message(self, client: IntegratedClientInfo, message: str, callback=None):
        """提交消息处理"""
        self._log("DEBUG", f"[PROCESSOR] 接收到消息提交请求 - 客户端: {client.client_id}, 消息: '{message}'")
        
        # 优先级处理：紧急命令优先
        priority = self._get_message_priority(message)
        self._log("DEBUG", f"[PROCESSOR] 消息优先级: {priority} - 客户端: {client.client_id}")
        
        if priority == 'high':
            # 高优先级消息立即处理
            self._log("DEBUG", f"[PROCESSOR] 使用高优先级处理 - 客户端: {client.client_id}")
            future = self.executor.submit(self._process_message, client, message)
        else:
            # 普通消息使用优化处理
            self._log("DEBUG", f"[PROCESSOR] 使用优化处理 - 客户端: {client.client_id}")
            future = self.executor.submit(self._process_message_with_optimization, client, message)
            
        if callback:
            future.add_done_callback(callback)
            self._log("DEBUG", f"[PROCESSOR] 已添加回调函数 - 客户端: {client.client_id}")
        
        self._log("DEBUG", f"[PROCESSOR] 消息已提交到执行器 - 客户端: {client.client_id}")
        return future
        
    def _get_message_priority(self, message: str) -> str:
        """获取消息优先级"""
        try:
            data = json.loads(message)
            command_name = data.get('command', '')
            # 紧急命令列表
            urgent_commands = {'stop', 'emergency', 'kill', 'abort', 'disconnect'}
            return 'high' if command_name in urgent_commands else 'normal'
        except:
            return 'normal'
            
    def _process_message_with_optimization(self, client: IntegratedClientInfo, message: str):
        """带优化的消息处理"""
        # 对于普通消息，进行预处理和优化
        try:
            # 预解析检查消息格式
            data = json.loads(message)
            command_name = data.get('command', '')
            
            # 快速响应常见命令
            if command_name == 'ping':
                client.last_activity = time.time()
                return 'pong'
            elif command_name == 'status' and not data.get('args'):
                # 简单状态查询使用缓存
                cache_key = f"status:{client.client_id}"
                cached_result = self._get_cached_result(cache_key)
                if cached_result:
                    return cached_result
                    
        except json.JSONDecodeError:
            pass
            
        # 使用标准处理流程
        return self._process_message(client, message)
        
    def _process_message(self, client: IntegratedClientInfo, message: str):
        """处理消息"""
        start_time = time.time()
        self._log("DEBUG", f"[PROCESSOR] 开始处理消息 - 客户端: {client.client_id}, 消息: '{message}'")
        
        try:
            # 检查客户端是否已认证（如果启用了身份验证）
            if hasattr(self, 'config') and self.config.enable_auth and not client.authenticated:
                self._log("WARNING", f"[PROCESSOR] 未认证客户端 {client.client_id} 尝试执行命令")
                return "错误: 未认证的客户端无法执行命令"
            
            # 解析消息
            data = json.loads(message)
            command_name = data.get('command', '')
            self._log("DEBUG", f"[PROCESSOR] 解析消息成功 - 命令: '{command_name}', 客户端: {client.client_id}")
            args = data.get('args', [])
            
            # 更新客户端活动时间
            client.last_activity = time.time()
            
            # 检查命令权限
            if not self._check_command_permission(client, command_name):
                return f"错误: 没有执行命令 '{command_name}' 的权限"
            
            # 检查缓存（仅对只读命令）
            cache_key = None
            if self._is_cacheable_command(command_name, args):
                cache_key = self._generate_cache_key(command_name, args)
                cached_result = self._get_cached_result(cache_key)
                if cached_result is not None:
                    self.stats["cache_hits"] += 1
                    return cached_result
                else:
                    self.stats["cache_misses"] += 1
            
            # 执行命令
            if command_name in self.command_registry:
                command = self.command_registry[command_name]
                self._log("DEBUG", f"[PROCESSOR] 执行命令 '{command_name}' 参数: {args}")
                result = command.execute(client, args)
                self._log("DEBUG", f"[PROCESSOR] 命令 '{command_name}' 执行结果: {result}")
                
                # 缓存结果
                if cache_key:
                    self._cache_result(cache_key, result)
                    self._log("DEBUG", f"[PROCESSOR] 命令 '{command_name}' 结果已缓存")
            else:
                result = f"Unknown command: {command_name}"
                self._log("WARNING", f"[PROCESSOR] 未知命令: {command_name}")
                
            self.stats["messages_processed"] += 1
            
            # 记录响应时间
            processing_time = time.time() - start_time
            client.add_response_time(processing_time)
            self._log("DEBUG", f"[PROCESSOR] 命令 '{command_name}' 处理时间: {processing_time:.4f}秒")
            
        except json.JSONDecodeError:
            result = "错误: 无效的JSON格式"
            self.stats["errors"] += 1
        except Exception as e:
            result = f"处理消息时出错: {str(e)}"
            self.stats["errors"] += 1
            
        processing_time = time.time() - start_time
        self._update_avg_processing_time(processing_time)
        
        return result
        
    def _check_command_permission(self, client: IntegratedClientInfo, command_name: str) -> bool:
        """检查命令权限"""
        # 如果未启用身份验证，允许所有命令
        if not hasattr(self, 'config') or not self.config.enable_auth:
            return True
            
        # 如果客户端未认证，只允许基本命令
        if not client.authenticated:
            allowed_commands = {'ping', 'help', 'auth'}
            is_allowed = command_name in allowed_commands
            if not is_allowed:
                # 记录未授权访问尝试
                if hasattr(self, '_log'):
                    self._log("WARNING", f"未认证客户端 {client.client_id} 尝试执行受限命令: {command_name}", security_event=True)
            return is_allowed
            
        # 已认证客户端权限检查
        return self._check_authenticated_command_permission(client, command_name)
        
    def _check_authenticated_command_permission(self, client: IntegratedClientInfo, command_name: str) -> bool:
        """检查已认证客户端的命令权限"""
        # 危险命令列表
        dangerous_commands = {
            'exec', 'eval', 'system', 'shell', 'delete', 'remove', 'kill', 
            'shutdown', 'reboot', 'format', 'rm', 'del'
        }
        
        # 管理员命令列表
        admin_commands = {
            'config', 'users', 'permissions', 'logs', 'restart', 'stop'
        }
        
        # 检查危险命令
        if command_name in dangerous_commands:
            # 记录危险命令执行
            if hasattr(self, '_log'):
                self._log("WARNING", f"客户端 {client.client_id} 执行危险命令: {command_name}", security_event=True)
            # 可以在这里添加额外的验证逻辑
            return True  # 暂时允许，可根据需要修改
            
        # 检查管理员命令
        if command_name in admin_commands:
            # 记录管理员命令执行
            if hasattr(self, '_log'):
                self._log("INFO", f"客户端 {client.client_id} 执行管理员命令: {command_name}", security_event=True)
            return True
            
        # 普通命令允许执行
        return True
        
    def _is_cacheable_command(self, command_name: str, args: List[str]) -> bool:
        """判断命令是否可缓存"""
        # 只缓存只读命令
        cacheable_commands = {'ping', 'status', 'help', 'list'}
        return command_name in cacheable_commands
        
    def _generate_cache_key(self, command_name: str, args: List[str]) -> str:
        """生成缓存键"""
        return f"{command_name}:{':'.join(args)}"
        
    def _get_cached_result(self, cache_key: str) -> Optional[str]:
        """获取缓存结果"""
        if cache_key in self.command_cache:
            cached_data = self.command_cache[cache_key]
            if time.time() - cached_data['timestamp'] < self.cache_ttl:
                return cached_data['result']
            else:
                # 缓存过期，删除
                del self.command_cache[cache_key]
        return None
        
    def _cache_result(self, cache_key: str, result: str):
        """缓存结果"""
        self.command_cache[cache_key] = {
            'result': result,
            'timestamp': time.time()
        }
        
        # 限制缓存大小
        if len(self.command_cache) > 100:
            # 删除最旧的缓存项
            oldest_key = min(self.command_cache.keys(), 
                           key=lambda k: self.command_cache[k]['timestamp'])
            del self.command_cache[oldest_key]
            
    def clear_cache(self):
        """清空缓存"""
        self.command_cache.clear()
        
    def _update_avg_processing_time(self, processing_time: float):
        """更新平均处理时间"""
        current_avg = self.stats["avg_processing_time"]
        total_messages = self.stats["messages_processed"]
        
        if total_messages <= 0:
            # 防止除零错误
            self.stats["avg_processing_time"] = processing_time
        elif total_messages == 1:
            self.stats["avg_processing_time"] = processing_time
        else:
            self.stats["avg_processing_time"] = (
                (current_avg * (total_messages - 1) + processing_time) / total_messages
            )
            
    def shutdown(self):
        """关闭处理器"""
        self.executor.shutdown(wait=True)
        
    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.stats.copy()


class OptimizedLogManager:
    """优化的日志管理器"""
    
    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self.logs = deque(maxlen=max_entries)
        self.mutex = threading.Lock()
        self.min_level = "调试"
        
    def add_log(self, level: str, message: str):
        """添加日志"""
        if not self._should_log(level):
            return
            
        with self.mutex:
            log_entry = {
                "timestamp": time.time() * 1000,  # 转换为毫秒级时间戳
                "level": level,
                "message": message,
                "thread": threading.current_thread().name
            }
            self.logs.append(log_entry)
            
    def get_recent_logs(self, count: int = 100) -> List[dict]:
        """获取最近的日志"""
        with self.mutex:
            return list(self.logs)[-count:]
            
    def clear_logs(self):
        """清空日志"""
        with self.mutex:
            self.logs.clear()
            
    def set_min_level(self, level: str):
        """设置最小日志级别"""
        self.min_level = level
        
    def _should_log(self, level: str) -> bool:
        """判断是否应该记录日志"""
        levels = {"调试": 0, "信息": 1, "警告": 2, "错误": 3, "严重": 4}
        return levels.get(level, 0) >= levels.get(self.min_level, 0)


# ==================== 集成服务器 ====================

class IntegratedDebugServer(QThread):
    """集成调试服务器"""
    
    # 信号定义
    state_changed = pyqtSignal(str)
    client_connected = pyqtSignal(str)
    client_disconnected = pyqtSignal(str)
    command_received = pyqtSignal(str, str, str)
    error_occurred = pyqtSignal(str)
    log_message = pyqtSignal(str, str)
    stats_updated = pyqtSignal(dict)
    
    def __init__(self, config: IntegratedServerConfig, dev_tools_panel=None):
        super().__init__()
        self.config = config
        self.state = DebugServerState.STOPPED
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        self.start_time = None
        self.dev_tools_panel = dev_tools_panel
        
        # 核心组件
        self.connection_pool = ConnectionPool(config.connection_pool_size)
        self.message_processor = MessageProcessor(config.thread_pool_size, self)
        self.log_manager = OptimizedLogManager(config.log_cache_size)
        
        # 设置日志级别
        self.log_manager.set_min_level(config.log_level)
        
        # Web服务器组件
        self.web_server: Optional['DebugWebServer'] = None
        
        # 高级功能组件（按需初始化）
        self.plugin_manager: Optional[PluginManager] = None
        self.script_executor: Optional[ScriptExecutor] = None
        self.file_transfer_manager: Optional[FileTransferManager] = None
        self.session_manager: Optional[SessionManager] = None
        
        # 性能统计
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_processed": 0,
            "errors": 0,
            "uptime": 0,
            "memory_usage": 0,
            "avg_response_time": 0.0,
            "avg_processing_time": 0.0,
            "network_traffic": "0 KB/s",
            "pool_utilization": 0.0
        }
        
        # 定时器
        self.cleanup_timer = QTimer()
        self.stats_timer = QTimer()
        
        self._initialize_components()
        self._register_commands()
        
    def _initialize_components(self):
        """初始化组件"""
        enabled_features = self.config.enabled_features
        
        # Web服务器
        if self.config.enable_web_interface:
            try:
                from .web_server import DebugWebServer, WebServerConfig
                web_config = WebServerConfig()
                web_config.host = self.config.web_host
                web_config.port = self.config.web_port
                web_config.websocket_port = getattr(self.config, 'websocket_port', 8081)
                web_config.static_dir = getattr(self.config, 'web_static_dir', 'web_static')
                web_config.auth_required = getattr(self.config, 'web_auth_required', False)
                web_config.auth_token = self.config.auth_token if self.config.enable_auth else ""
                web_config.enabled = True
                self.web_server = DebugWebServer(web_config, self, self.dev_tools_panel)
            except ImportError as e:
                self._log("ERROR", f"无法导入Web服务器模块: {e}")
                self.config.enable_web_interface = False
        
        # 插件系统
        if FeatureFlags.PLUGIN_SYSTEM in enabled_features:
            self.plugin_manager = PluginManager(self.config.plugin_dir)
            self.plugin_manager.set_server_context(self)
            
        # 脚本执行器
        if FeatureFlags.SCRIPT_EXECUTOR in enabled_features:
            self.script_executor = ScriptExecutor()
            
        # 文件传输
        if FeatureFlags.FILE_TRANSFER in enabled_features:
            self.file_transfer_manager = FileTransferManager(self.config.transfer_dir)
            
        # 会话管理
        if FeatureFlags.SESSION_MANAGER in enabled_features:
            self.session_manager = SessionManager(self.config.session_dir)
            
        # 加载保存的认证令牌
        if self.config.enable_auth:
            if not self._load_auth_token():
                # 如果加载失败，生成新令牌
                self.config.auth_token = self._generate_secure_token()
                self._save_auth_token()
                
        # 初始化安全日志
        self._init_security_logging()
            
    def _register_commands(self):
        """注册命令"""
        # 基础命令
        self.message_processor.register_command(PingCommand())
        self.message_processor.register_command(StatusCommand(self))
        
        # 脚本执行命令
        if self.script_executor:
            self.message_processor.register_command(
                ScriptCommand(self.script_executor)
            )
            
        # 插件命令
        if self.plugin_manager:
            for command_class in self.plugin_manager.get_plugin_commands():
                self.message_processor.register_command(command_class())
        
        # 帮助命令（需要在最后注册，因为它需要访问command_registry）
        self.message_processor.register_command(
            HelpCommand(self.message_processor.command_registry)
        )
                
    def start_server(self) -> bool:
        """启动服务器"""
        if self.state != DebugServerState.STOPPED:
            return False
            
        try:
            self._set_state(DebugServerState.STARTING)
            
            # 创建服务器socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # 如果启用SSL，创建SSL上下文
            if self.config.enable_ssl:
                self.ssl_context = self._create_ssl_context()
                if self.ssl_context is None:
                    self._set_state(DebugServerState.ERROR)
                    self._log("ERROR", "SSL配置失败，无法启动服务器")
                    return False
                    
            self.server_socket.bind((self.config.host, self.config.port))
            self.server_socket.listen(self.config.max_clients)
            
            self.running = True
            self.start_time = time.time()
            
            # 启动定时器
            if FeatureFlags.PERFORMANCE_OPT in self.config.enabled_features:
                self.cleanup_timer.timeout.connect(self._periodic_cleanup)
                self.cleanup_timer.start(60000)  # 每分钟清理一次
                
                self.stats_timer.timeout.connect(self._update_stats)
                self.stats_timer.start(5000)  # 每5秒更新统计
                
            # 启动Web服务器
            if self.web_server:
                try:
                    self.web_server.start_server()
                    self._log("INFO", f"Web界面已启动 - http://{self.config.web_host}:{self.config.web_port}")
                except Exception as e:
                    self._log("ERROR", f"Web服务器启动失败: {e}")
                    # Web服务器启动失败不影响主服务器
            
            # 启动服务器线程
            self.start()
            
            # 设置启动时间
            self.start_time = time.time()
            
            self._set_state(DebugServerState.RUNNING)
            ssl_status = "(SSL启用)" if self.config.enable_ssl else "(SSL禁用)"
            self._log("INFO", f"服务器已启动，地址: {self.config.host}:{self.config.port} {ssl_status}")
            
            # 通知DevToolsPanel设置当前调试服务器实例
            if self.dev_tools_panel and hasattr(self.dev_tools_panel, 'set_current_debug_server'):
                self.dev_tools_panel.set_current_debug_server(self)
            
            return True
            
        except Exception as e:
            self._set_state(DebugServerState.ERROR)
            self._log("ERROR", f"服务器启动失败: {str(e)}")
            return False
            
    def stop_server(self):
        """停止服务器"""
        if self.state == DebugServerState.STOPPED:
            return
            
        self._set_state(DebugServerState.STOPPING)
        self.running = False
        
        # 停止定时器
        self.cleanup_timer.stop()
        self.stats_timer.stop()
        
        # 关闭所有客户端连接
        for client in self.connection_pool.get_all_connections():
            try:
                client.socket.close()
            except (OSError, AttributeError) as e:
                # 处理WinError 10038和其他套接字错误
                if "10038" in str(e) or "非套接字" in str(e):
                    self._log("WARNING", f"客户端套接字已关闭或无效: {str(e)}")
                else:
                    self._log("WARNING", f"关闭客户端连接时发生错误: {str(e)}")
            except Exception as e:
                self._log("WARNING", f"关闭客户端连接时发生未知错误: {str(e)}")
                
        # 关闭服务器socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except (OSError, AttributeError) as e:
                # 处理WinError 10038和其他套接字错误
                if "10038" in str(e) or "非套接字" in str(e):
                    self._log("WARNING", f"服务器套接字已关闭或无效: {str(e)}")
                else:
                    self._log("WARNING", f"关闭服务器套接字时发生错误: {str(e)}")
            except Exception as e:
                self._log("WARNING", f"关闭服务器套接字时发生未知错误: {str(e)}")
            self.server_socket = None
            
        # 等待线程结束
        self.wait()
        
        # 清理资源
        self._cleanup_resources()
        
        self._set_state(DebugServerState.STOPPED)
        self._log("INFO", "服务器已停止")
        
        # 清除启动时间
        self.start_time = None
        
        # 清除DevToolsPanel中的调试服务器引用
        if self.dev_tools_panel and hasattr(self.dev_tools_panel, 'set_current_debug_server'):
            self.dev_tools_panel.set_current_debug_server(None)
        
        # 延迟停止Web服务器，让它能够响应最后的状态查询
        if self.web_server:
            def delayed_stop_web_server():
                try:
                    time.sleep(3)  # 延迟3秒
                    self.web_server.stop_server()
                    self._log("INFO", "Web服务器已停止")
                except (OSError, AttributeError) as e:
                    # 处理WinError 10038和其他套接字错误
                    if "10038" in str(e) or "非套接字" in str(e):
                        self._log("WARNING", f"Web服务器套接字已关闭或无效: {str(e)}")
                    else:
                        self._log("ERROR", f"Web服务器停止失败: {e}")
                except Exception as e:
                    self._log("ERROR", f"Web服务器停止失败: {e}")
            
            import threading
            threading.Thread(target=delayed_stop_web_server, daemon=True).start()
    
    def restart_web_server(self) -> bool:
        """重启Web服务器"""
        try:
            self._log("INFO", "正在重启Web服务器...")
            
            # 停止现有的Web服务器
            if self.web_server:
                self.web_server.stop_server()
                self._log("INFO", "Web服务器已停止")
            
            # 重新初始化Web服务器
            if self.config.enable_web_interface:
                try:
                    from .web_server import DebugWebServer, WebServerConfig
                    web_config = WebServerConfig()
                    web_config.host = self.config.web_host
                    web_config.port = self.config.web_port
                    web_config.websocket_port = getattr(self.config, 'websocket_port', 8081)
                    web_config.static_dir = getattr(self.config, 'web_static_dir', 'web_static')
                    web_config.auth_required = getattr(self.config, 'web_auth_required', False)
                    web_config.auth_token = self.config.auth_token if self.config.enable_auth else ""
                    web_config.enabled = True
                    
                    self.web_server = DebugWebServer(web_config, self, self.dev_tools_panel)
                    
                    # 启动Web服务器
                    if self.web_server.start_server():
                        self._log("INFO", "Web服务器重启成功")
                        return True
                    else:
                        self._log("ERROR", "Web服务器启动失败")
                        return False
                        
                except ImportError as e:
                    self._log("ERROR", f"无法导入Web服务器模块: {e}")
                    return False
            else:
                self._log("WARNING", "Web界面未启用")
                return False
                
        except Exception as e:
            self._log("ERROR", f"重启Web服务器失败: {e}")
            return False
        
    def _cleanup_resources(self):
        """清理资源"""
        # 关闭消息处理器
        self.message_processor.shutdown()
        
        # 卸载插件
        if self.plugin_manager:
            for plugin_info in self.plugin_manager.get_loaded_plugins():
                self.plugin_manager.unload_plugin(plugin_info.name)
                
        # 清理日志
        self.log_manager.clear_logs()
        
    def _periodic_cleanup(self):
        """定期清理"""
        # 清理不活跃的连接
        cleaned_count = self.connection_pool.cleanup_inactive_connections(self.config.timeout)
        if cleaned_count > 0:
            self._log("INFO", f"已清理 {cleaned_count} 个非活跃连接")
        
        # 清理脚本执行历史
        if self.script_executor and len(self.script_executor.execution_history) > 50:
            # 保留最近50条记录
            removed_count = 0
            while len(self.script_executor.execution_history) > 50:
                self.script_executor.execution_history.popleft()
                removed_count += 1
            if removed_count > 0:
                self._log("DEBUG", f"已清理 {removed_count} 个脚本执行记录")
                
        # 清理文件传输历史
        if self.file_transfer_manager and len(self.file_transfer_manager.transfer_history) > 50:
            removed_count = 0
            while len(self.file_transfer_manager.transfer_history) > 50:
                self.file_transfer_manager.transfer_history.popleft()
                removed_count += 1
            if removed_count > 0:
                self._log("DEBUG", f"已清理 {removed_count} 个文件传输记录")
                
        # 清理日志缓存
        if hasattr(self.log_manager, 'logs') and len(self.log_manager.logs) > self.config.log_cache_size:
            excess_count = len(self.log_manager.logs) - self.config.log_cache_size
            for _ in range(excess_count):
                self.log_manager.logs.popleft()
            self._log("DEBUG", f"已清理 {excess_count} 个旧日志条目")
                
    def _update_stats(self):
        """更新统计信息"""
        connection_stats = self.connection_pool.get_connection_stats()
        
        self.stats.update({
            "active_connections": connection_stats["active_connections"],
            "total_connections": connection_stats["total_connections"],
            "pool_utilization": connection_stats["pool_utilization"],
            "avg_response_time": connection_stats["avg_response_time"],
            "uptime": time.time() - self.start_time if self.start_time else 0,
            "messages_processed": self.message_processor.stats["messages_processed"],
            "errors": self.message_processor.stats["errors"],
            "avg_processing_time": self.message_processor.stats["avg_processing_time"]
        })
        
        # 统计信息更新（注释掉日志输出避免在日志列表中显示）
        # self._log("DEBUG", f"Stats updated: {self.stats}")
        
        self.stats_updated.emit(self.stats)
        
    def _set_state(self, new_state: DebugServerState):
        """设置服务器状态"""
        if self.state != new_state:
            self.state = new_state
            self.state_changed.emit(new_state.value)
            
    def _log(self, level: str, message: str, security_event: bool = False):
        """记录日志"""
        self.log_manager.add_log(level, message)
        self.log_message.emit(level, message)
        
        # 广播日志到Web界面
        if self.web_server and self.web_server.is_running:
            log_data = {
                "type": "log",
                "data": {
                    "timestamp": time.time() * 1000,  # 转换为毫秒级时间戳
                    "level": level,
                    "message": message,
                    "thread": threading.current_thread().name
                }
            }
            self.web_server.broadcast_log(log_data)
        
        # 安全事件日志
        if security_event:
            self._log_security_event(level, message)
            
    def _init_security_logging(self):
        """初始化安全日志"""
        try:
            from pathlib import Path
            
            # 创建安全日志目录
            self.security_log_dir = Path("logs") / "security"
            self.security_log_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建当日安全日志文件
            today = time.strftime("%Y-%m-%d")
            self.security_log_file = self.security_log_dir / f"security_{today}.log"
            
            self._log("INFO", f"安全日志已初始化: {self.security_log_file}")
            
        except Exception as e:
            self._log("WARNING", f"初始化安全日志失败: {str(e)}")
            self.security_log_file = None
            
    def _log_security_event(self, level: str, message: str):
        """记录安全事件"""
        if not hasattr(self, 'security_log_file') or not self.security_log_file:
            return
            
        try:
            import json
            import platform
            import threading
            
            timestamp = time.time()
            
            # 基础信息
            security_entry = {
                "timestamp": timestamp,
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp)),
                "level": level,
                "message": message,
                "event_id": hashlib.md5(f"{timestamp}_{message}".encode()).hexdigest()[:16]
            }
            
            # 服务器状态信息
            server_info = {
                "server_state": self.state.value,
                "server_host": self.config.host,
                "server_port": self.config.port,
                "max_clients": self.config.max_clients,
                "timeout": self.config.timeout,
                "uptime": time.time() - (getattr(self, 'start_time', None) or timestamp),
                "auth_enabled": self.config.enable_auth,
                "ssl_enabled": self.config.enable_ssl
            }
            security_entry["server_info"] = server_info
            
            # 客户端连接信息
            connections = self.connection_pool.get_all_connections()
            client_info = {
                "total_clients": len(connections),
                "authenticated_clients": len([c for c in connections if c.authenticated]),
                "active_connections": len([c for c in connections if c.state == ClientConnectionState.CONNECTED]),
                "client_details": []
            }
            
            # 详细客户端信息（最多记录前5个）
            for client in connections[:5]:
                client_detail = {
                    "client_id": client.client_id[:12],
                    "ip_address": client.address[0],
                    "port": client.address[1],
                    "state": client.state.value,
                    "connect_time": client.connect_time,
                    "last_activity": client.last_activity,
                    "authenticated": client.authenticated,
                    "commands_sent": client.commands_sent,
                    "bytes_received": client.bytes_received,
                    "bytes_sent": client.bytes_sent,
                    "user_agent": client.user_agent,
                    "protocol_version": client.protocol_version
                }
                client_info["client_details"].append(client_detail)
            
            security_entry["client_info"] = client_info
            
            # 系统信息
            system_info = {
                "platform": platform.system(),
                "platform_version": platform.version(),
                "architecture": platform.architecture()[0],
                "hostname": platform.node(),
                "python_version": platform.python_version(),
                "thread_count": threading.active_count()
            }
            
            # 性能信息（如果可用）
            try:
                import psutil
                process = psutil.Process()
                memory_info = process.memory_info()
                
                performance_info = {
                    "cpu_percent": psutil.cpu_percent(interval=0.1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "memory_used_gb": psutil.virtual_memory().used / (1024**3),
                    "memory_total_gb": psutil.virtual_memory().total / (1024**3),
                    "process_memory_mb": memory_info.rss / (1024**2),
                    "process_cpu_percent": process.cpu_percent(),
                    "process_threads": process.num_threads(),
                    "disk_usage_percent": psutil.disk_usage('/').percent if hasattr(psutil, 'disk_usage') else 0
                }
                
                # 网络统计
                try:
                    net_io = psutil.net_io_counters()
                    performance_info.update({
                        "network_bytes_sent": net_io.bytes_sent,
                        "network_bytes_recv": net_io.bytes_recv,
                        "network_packets_sent": net_io.packets_sent,
                        "network_packets_recv": net_io.packets_recv
                    })
                except:
                    pass
                    
                system_info["performance"] = performance_info
                
            except ImportError:
                system_info["performance"] = {"status": "psutil_not_available"}
            except Exception as e:
                system_info["performance"] = {"error": str(e)}
            
            security_entry["system_info"] = system_info
            
            # 安全相关信息
            security_context = {
                "log_level": self.config.log_level,
                "security_log_file": os.path.basename(self.security_log_file) if self.security_log_file else None,
                "config_hash": hashlib.md5(str(self.config.to_dict()).encode()).hexdigest()[:16],
                "enabled_features": [f.value for f in self.config.enabled_features] if hasattr(self.config, 'enabled_features') else []
            }
            
            # 如果有消息处理器统计信息
            if hasattr(self, 'message_processor'):
                try:
                    processor_stats = self.message_processor.get_stats()
                    security_context["message_processor"] = {
                        "messages_processed": processor_stats.get("messages_processed", 0),
                        "avg_processing_time": processor_stats.get("avg_processing_time", 0),
                        "cache_hits": processor_stats.get("cache_hits", 0),
                        "cache_misses": processor_stats.get("cache_misses", 0)
                    }
                except:
                    pass
            
            security_entry["security_context"] = security_context
            
            # 写入安全日志文件
            with open(self.security_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(security_entry, ensure_ascii=False, indent=None) + '\n')
                
        except Exception as e:
            self._log("WARNING", f"记录安全事件失败: {str(e)}")
            
    def _log_control_panel_state(self, component: str, action: str, details: dict = None):
        """记录远程控制面板控件状态变化"""
        try:
            import json
            
            timestamp = time.time()
            
            # 收集当前控件状态信息
            control_state = {
                "timestamp": timestamp,
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp)),
                "component": component,
                "action": action,
                "details": details or {},
                
                # 服务器状态信息
                "server_info": {
                    "state": self.state.value,
                    "host": self.config.host,
                    "port": self.config.port,
                    "auth_enabled": self.config.enable_auth,
                    "ssl_enabled": self.config.enable_ssl,
                    "auto_start": self.config.auto_start
                },
                
                # 客户端连接信息
                "client_info": {
                    "total_clients": len(self.connection_pool.get_all_connections()),
                    "max_clients": self.config.max_clients,
                    "connection_pool_usage": f"{len(self.connection_pool.get_all_connections())}/{self.config.connection_pool_size}"
                },
                
                # 性能监控信息
                "performance_info": {
                    "thread_pool_size": self.config.thread_pool_size,
                    "message_buffer_size": self.config.message_buffer_size,
                    "log_cache_size": self.config.log_cache_size,
                    "update_interval": self.config.update_interval
                },
                
                # 功能配置信息
                "feature_info": {
                    "enabled_features": [feature.value for feature in self.config.enabled_features],
                    "plugin_dir": self.config.plugin_dir,
                    "script_dir": self.config.script_dir,
                    "transfer_dir": self.config.transfer_dir,
                    "session_dir": self.config.session_dir
                }
            }
            
            # 记录到主日志（格式化输出）
            formatted_message = self._format_control_state_log(component, action, details)
            self._log("INFO", formatted_message)
            
            # 记录详细的控件状态到专门的日志文件
            control_log_dir = Path("logs") / "control_panel"
            control_log_dir.mkdir(parents=True, exist_ok=True)
            
            today = time.strftime("%Y-%m-%d")
            control_log_file = control_log_dir / f"control_panel_{today}.log"
            
            # 添加格式化的时间戳和分隔符
            formatted_entry = {
                "timestamp_readable": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(control_state["timestamp"])),
                "module": "CONTROL_PANEL",
                "event_type": "STATE_CHANGE",
                **control_state
            }
            
            with open(control_log_file, 'a', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write(f"[{formatted_entry['timestamp_readable']}] {component.upper()}: {action.upper()}\n")
                f.write("=" * 80 + "\n")
                f.write(json.dumps(formatted_entry, ensure_ascii=False, indent=2) + '\n\n')
                
        except Exception as e:
             self._log("WARNING", f"记录控件状态失败: {str(e)}")
             
    def _format_control_state_log(self, component: str, action: str, details: dict = None) -> str:
        """格式化控件状态日志消息"""
        try:
            # 基础消息格式
            message = f"[控件状态] {component.upper()}: {action.upper()}"
            
            # 添加详细信息
            if details:
                detail_parts = []
                for key, value in details.items():
                    if isinstance(value, (dict, list)):
                        detail_parts.append(f"{key}={len(value) if isinstance(value, (list, dict)) else str(value)}")
                    else:
                        detail_parts.append(f"{key}={value}")
                
                if detail_parts:
                    message += f" | {', '.join(detail_parts)}"
            
            # 添加服务器状态摘要
            status_info = []
            if hasattr(self, 'state'):
                status_info.append(f"服务器:{self.state.value}")
            if hasattr(self, 'connection_pool'):
                client_count = len(self.connection_pool.get_all_connections())
                status_info.append(f"客户端:{client_count}")
            
            if status_info:
                message += f" | {', '.join(status_info)}"
                
            return message
            
        except Exception as e:
            return f"[控件状态] {component}: {action} (格式化失败: {str(e)})"
        
    def run(self):
        """服务器主循环"""
        self._log("INFO", "服务器线程已启动")
        
        while self.running and self.server_socket:
            try:
                # 设置超时，避免阻塞
                self.server_socket.settimeout(1.0)
                
                try:
                    client_socket, address = self.server_socket.accept()
                    
                    # 如果启用SSL，包装客户端套接字
                    if self.config.enable_ssl and hasattr(self, 'ssl_context'):
                        try:
                            client_socket = self.ssl_context.wrap_socket(
                                client_socket, 
                                server_side=True
                            )
                            self._log("INFO", f"SSL连接已建立: {address}")
                        except Exception as e:
                            error_msg = str(e)
                            if "HTTP_REQUEST" in error_msg:
                                self._log("WARNING", f"客户端 {address} 使用HTTP协议连接SSL服务器")
                                self._log("INFO", f"解决方案: 客户端应使用HTTPS协议连接 https://{self.config.host}:{self.config.port}")
                            else:
                                self._log("ERROR", f"SSL握手失败 {address}: {error_msg}")
                            client_socket.close()
                            continue
                    
                    self._handle_new_client(client_socket, address)
                except socket.timeout:
                    continue
                except OSError:
                    # Socket已关闭
                    break
                    
            except Exception as e:
                if self.running:
                    self._log("ERROR", f"服务器错误: {str(e)}")
                    self.error_occurred.emit(str(e))
                break
                
        self._log("INFO", "服务器线程已停止")
        
    def _handle_new_client(self, client_socket: socket.socket, address: Tuple[str, int]):
        """处理新客户端连接"""
        client_id = hashlib.md5(f"{address[0]}:{address[1]}:{time.time()}".encode()).hexdigest()[:12]
        
        # 根据是否启用身份验证设置初始状态
        initial_state = ClientConnectionState.CONNECTING if self.config.enable_auth else ClientConnectionState.CONNECTED
        
        client = IntegratedClientInfo(
            client_id=client_id,
            socket=client_socket,
            address=address,
            connect_time=time.time(),
            state=initial_state,
            last_activity=time.time(),
            authenticated=not self.config.enable_auth  # 如果未启用身份验证，则默认已认证
        )
        
        if self.connection_pool.add_connection(client):
            self.stats["total_connections"] += 1
            self.client_connected.emit(client_id)
            
            if self.config.enable_auth:
                self._log("INFO", f"客户端连接等待认证: {client_id} 来自 {address}")
                # 发送认证请求
                self._send_auth_challenge(client)
            else:
                self._log("INFO", f"客户端已连接: {client_id} 来自 {address}")
            
            # 在新线程中处理客户端
            client_thread = threading.Thread(
                target=self._handle_client,
                args=(client,),
                daemon=True
            )
            client_thread.start()
        else:
            # 连接池已满
            client_socket.close()
            self._log("WARNING", f"连接被拒绝 (连接池已满): {address}")
            
    def _handle_client(self, client: IntegratedClientInfo):
        """处理客户端消息"""
        try:
            while self.running and client.state != ClientConnectionState.DISCONNECTED:
                try:
                    # 根据客户端状态设置不同的超时时间
                    if client.authenticated:
                        client.socket.settimeout(5.0)  # 已认证客户端使用较短超时
                    else:
                        client.socket.settimeout(30.0)  # 未认证客户端使用较长超时，给认证过程更多时间
                    data = client.socket.recv(4096)
                    
                    if not data:
                        break
                    
                    # 添加调试日志
                    self._log("DEBUG", f"[SERVER] 从客户端 {client.client_id} 接收到原始数据长度: {len(data)} 字节")
                    self._log("DEBUG", f"[SERVER] 原始数据(hex): {data.hex()}")
                        
                    client.last_activity = time.time()
                    client.bytes_received += len(data)
                    
                    # 将数据添加到缓冲区
                    client.message_buffer += data
                    
                    # 添加调试日志
                    self._log("DEBUG", f"[SERVER] 客户端 {client.client_id} 缓冲区长度: {len(client.message_buffer)} 字节")
                    self._log("DEBUG", f"[SERVER] 缓冲区内容(hex): {client.message_buffer.hex()}")
                    newline_byte = b'\n'
                    self._log("DEBUG", f"[SERVER] 缓冲区是否包含换行符: {newline_byte in client.message_buffer}")
                    
                    # 检查缓冲区大小，防止内存攻击
                    if len(client.message_buffer) > 1024 * 1024:  # 1MB限制
                        self._log("WARNING", f"客户端 {client.client_id} 缓冲区过大，断开连接")
                        break
                    
                    # 处理缓冲区中的完整消息（以换行符分隔）
                    while b'\n' in client.message_buffer:
                        # 提取一条完整消息
                        message_data, client.message_buffer = client.message_buffer.split(b'\n', 1)
                        
                        if not message_data:
                            continue
                            
                        # 添加调试日志
                        self._log("DEBUG", f"[SERVER] 处理客户端 {client.client_id} 消息数据: {message_data.hex()}")
                        
                        # 安全解码数据，处理编码错误
                        try:
                            message = message_data.decode('utf-8')
                            self._log("DEBUG", f"[SERVER] 解码后消息: '{message}'")
                        except UnicodeDecodeError as e:
                            # 尝试使用其他编码或忽略错误
                            try:
                                message = message_data.decode('utf-8', errors='replace')
                                self._log("WARNING", f"客户端 {client.client_id} 数据包含无效UTF-8字节，已替换为占位符: {e}")
                            except Exception:
                                # 如果仍然失败，使用latin-1编码（不会失败）
                                message = message_data.decode('latin-1')
                                self._log("WARNING", f"客户端 {client.client_id} 使用latin-1编码解码数据: {e}")
                        except Exception as e:
                            self._log("ERROR", f"客户端 {client.client_id} 数据解码失败: {e}")
                            continue
                        
                        # 如果启用身份验证且客户端未认证，处理认证消息
                        if self.config.enable_auth and not client.authenticated:
                            self._log("DEBUG", f"[SERVER] 客户端 {client.client_id} 未认证，处理认证消息")
                            if self._handle_auth_message(client, message):
                                self._log("DEBUG", f"[SERVER] 客户端 {client.client_id} 认证消息处理成功")
                                continue
                            else:
                                self._log("DEBUG", f"[SERVER] 客户端 {client.client_id} 认证消息处理失败，断开连接")
                                break  # 认证失败，断开连接
                        
                        # 异步处理消息
                        self._log("DEBUG", f"[SERVER] 提交消息到处理器 - 客户端: {client.client_id}, 消息: '{message}'")
                        future = self.message_processor.submit_message(
                            client, message, 
                            lambda f: self._handle_message_result(client, f)
                        )
                        self._log("DEBUG", f"[SERVER] 消息已提交到处理器队列 - 客户端: {client.client_id}")
                    
                except socket.timeout:
                    continue
                except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
                    # 连接重置、中止或套接字错误（包括WinError 10038）
                    if "10038" in str(e) or "非套接字" in str(e):
                        self._log("WARNING", f"客户端 {client.client_id} 套接字操作错误: {str(e)}")
                    break
                except Exception as e:
                    self._log("ERROR", f"客户端处理错误: {str(e)}")
                    break
                    
        finally:
            self._disconnect_client(client.client_id)
            
    def _send_auth_challenge(self, client: IntegratedClientInfo):
        """发送认证挑战"""
        try:
            challenge_msg = json.dumps({
                "type": "auth_challenge",
                "message": "请提供认证令牌"
            }) + "\n"  # 添加换行符
            # 安全编码发送
            try:
                encoded_msg = challenge_msg.encode('utf-8')
                self._log("DEBUG", f"[SERVER] 发送认证挑战到客户端 {client.client_id}: '{challenge_msg.strip()}'")
                self._log("DEBUG", f"[SERVER] 发送数据长度: {len(encoded_msg)} 字节")
                self._log("DEBUG", f"[SERVER] 发送数据(hex): {encoded_msg.hex()}")
                # 检查是否为SSL socket
                if hasattr(client.socket, 'write'):
                    client.socket.write(encoded_msg)
                else:
                    client.socket.send(encoded_msg)
                client.bytes_sent += len(encoded_msg)
            except UnicodeEncodeError as e:
                self._log("ERROR", f"认证挑战消息编码失败: {str(e)}")
                # 使用错误处理模式重新编码
                encoded_msg = challenge_msg.encode('utf-8', errors='replace')
                if hasattr(client.socket, 'write'):
                    client.socket.write(encoded_msg)
                else:
                    client.socket.send(encoded_msg)
                client.bytes_sent += len(encoded_msg)
        except Exception as e:
            self._log("ERROR", f"发送认证挑战失败: {str(e)}")
            
    def _handle_auth_message(self, client: IntegratedClientInfo, message: str) -> bool:
        """处理认证消息"""
        try:
            self._log("DEBUG", f"[SERVER] 收到客户端 {client.client_id} 认证消息: '{message.strip()}'")
            self._log("DEBUG", f"[SERVER] 消息长度: {len(message)} 字符")
            data = json.loads(message)
            self._log("DEBUG", f"[SERVER] 解析后的JSON数据: {data}")
            
            if data.get('type') == 'auth_response':
                provided_token = data.get('token', '')
                self._log("DEBUG", f"[SERVER] 客户端提供的令牌: '{provided_token}'")
                
                if self._verify_auth_token(provided_token):
                    client.authenticated = True
                    client.state = ClientConnectionState.AUTHENTICATED
                    
                    # 发送认证成功响应
                    success_msg = json.dumps({
                        "type": "auth_result",
                        "success": True,
                        "message": "认证成功"
                    }) + "\n"  # 添加换行符
                    # 安全编码发送
                    try:
                        encoded_msg = success_msg.encode('utf-8')
                        self._log("DEBUG", f"[SERVER] 发送认证成功响应到客户端 {client.client_id}: '{success_msg.strip()}'")
                        self._log("DEBUG", f"[SERVER] 成功响应数据长度: {len(encoded_msg)} 字节")
                        self._log("DEBUG", f"[SERVER] 成功响应数据(hex): {encoded_msg.hex()}")
                        # 检查是否为SSL socket
                        if hasattr(client.socket, 'write'):
                            client.socket.write(encoded_msg)
                        else:
                            client.socket.send(encoded_msg)
                        client.bytes_sent += len(encoded_msg)
                    except UnicodeEncodeError as e:
                        self._log("ERROR", f"认证成功消息编码失败: {str(e)}")
                        encoded_msg = success_msg.encode('utf-8', errors='replace')
                        if hasattr(client.socket, 'write'):
                            client.socket.write(encoded_msg)
                        else:
                            client.socket.send(encoded_msg)
                        client.bytes_sent += len(encoded_msg)
                    
                    self._log("INFO", f"客户端 {client.client_id} 认证成功", security_event=True)
                    return True
                else:
                    # 发送认证失败响应
                    failure_msg = json.dumps({
                        "type": "auth_result",
                        "success": False,
                        "message": "认证失败：无效的令牌"
                    }) + "\n"  # 添加换行符
                    # 安全编码发送
                    try:
                        encoded_msg = failure_msg.encode('utf-8')
                        self._log("DEBUG", f"[SERVER] 发送认证失败响应到客户端 {client.client_id}: '{failure_msg.strip()}'")
                        self._log("DEBUG", f"[SERVER] 失败响应数据长度: {len(encoded_msg)} 字节")
                        self._log("DEBUG", f"[SERVER] 失败响应数据(hex): {encoded_msg.hex()}")
                        # 检查是否为SSL socket
                        if hasattr(client.socket, 'write'):
                            client.socket.write(encoded_msg)
                        else:
                            client.socket.send(encoded_msg)
                        client.bytes_sent += len(encoded_msg)
                    except UnicodeEncodeError as e:
                        self._log("ERROR", f"认证失败消息编码失败: {str(e)}")
                        encoded_msg = failure_msg.encode('utf-8', errors='replace')
                        if hasattr(client.socket, 'write'):
                            client.socket.write(encoded_msg)
                        else:
                            client.socket.send(encoded_msg)
                        client.bytes_sent += len(encoded_msg)
                    
                    self._log("WARNING", f"客户端 {client.client_id} 认证失败：无效令牌", security_event=True)
                    return False
            else:
                # 非认证消息，拒绝处理
                error_msg = json.dumps({
                    "type": "error",
                    "message": "请先完成身份认证"
                }) + "\n"  # 添加换行符
                # 安全编码发送
                try:
                    encoded_msg = error_msg.encode('utf-8')
                    # 检查是否为SSL socket
                    if hasattr(client.socket, 'write'):
                        client.socket.write(encoded_msg)
                    else:
                        client.socket.send(encoded_msg)
                    client.bytes_sent += len(encoded_msg)
                except UnicodeEncodeError as e:
                    self._log("ERROR", f"错误消息编码失败: {str(e)}")
                    encoded_msg = error_msg.encode('utf-8', errors='replace')
                    if hasattr(client.socket, 'write'):
                        client.socket.write(encoded_msg)
                    else:
                        client.socket.send(encoded_msg)
                    client.bytes_sent += len(encoded_msg)
                return True  # 继续等待认证
                
        except json.JSONDecodeError:
            self._log("WARNING", f"客户端 {client.client_id} 发送无效JSON格式消息", security_event=True)
            return False
        except Exception as e:
            self._log("ERROR", f"处理认证消息时出错: {str(e)}")
            return False
            
    def _verify_auth_token(self, token: str) -> bool:
        """验证认证令牌"""
        # 移除了不安全的测试令牌，只使用配置的安全令牌
        if not self.config.auth_token:
            # 如果未设置令牌，生成并保存新令牌
            self.config.auth_token = generate_secure_token()
            self._save_auth_token()
            
        return self._secure_compare(token, self.config.auth_token)
        
    def _generate_secure_token(self) -> str:
        """生成安全的认证令牌"""
        import secrets
        import hashlib
        import time
        
        # 生成基于时间戳和随机数的安全令牌
        timestamp = str(int(time.time()))
        random_bytes = secrets.token_bytes(32)
        
        # 组合时间戳和随机数据
        combined = timestamp.encode() + random_bytes
        
        # 使用SHA-256哈希生成最终令牌
        token_hash = hashlib.sha256(combined).hexdigest()
        
        # 返回URL安全的Base64编码令牌
        return secrets.token_urlsafe(32) + token_hash[:16]
        
    def _secure_compare(self, a: str, b: str) -> bool:
        """安全的字符串比较，防止时序攻击"""
        import hmac
        return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))
    
    def _safe_send_message(self, client: IntegratedClientInfo, message: str) -> bool:
        """安全发送消息，包含编码错误处理和连接状态检查
        
        Args:
            client: 客户端信息
            message: 要发送的消息
            
        Returns:
            bool: 发送是否成功
        """
        if client.state == ClientConnectionState.DISCONNECTED:
            return False
            
        try:
            # 安全编码发送
            try:
                encoded_message = message.encode('utf-8')
                client.socket.send(encoded_message)
                client.bytes_sent += len(encoded_message)
                return True
            except UnicodeEncodeError as e:
                self._log("ERROR", f"消息编码失败: {str(e)}")
                # 使用错误处理模式重新编码
                encoded_message = message.encode('utf-8', errors='replace')
                client.socket.send(encoded_message)
                client.bytes_sent += len(encoded_message)
                return True
        except (OSError, ConnectionError) as e:
            # 套接字已关闭或连接已断开
            self._log("WARNING", f"客户端 {client.client_id} 套接字已关闭: {str(e)}")
            client.state = ClientConnectionState.DISCONNECTED
            return False
        except Exception as e:
            self._log("ERROR", f"发送消息失败: {str(e)}")
            return False
         
    def _save_auth_token(self):
        """保存认证令牌到文件"""
        try:
            import json
            import os
            import time
            from pathlib import Path
             
            # 创建配置目录
            config_dir = Path("config")
            config_dir.mkdir(exist_ok=True)
            
            # 保存令牌信息
            token_info = {
                "token": self.config.auth_token,
                "created_at": time.time(),
                "expires_at": time.time() + (30 * 24 * 3600),  # 30天后过期
                "version": "1.0"
            }
            
            token_file = config_dir / "auth_token.json"
            with open(token_file, 'w', encoding='utf-8') as f:
                json.dump(token_info, f, indent=2)
                
            # 设置文件权限（仅所有者可读写）
            if os.name != 'nt':  # 非Windows系统
                os.chmod(token_file, 0o600)
                
            self._log("INFO", f"认证令牌已保存到: {token_file}")
            
        except Exception as e:
            self._log("WARNING", f"保存认证令牌失败: {str(e)}")
             
    def _load_auth_token(self) -> bool:
        """从文件加载认证令牌"""
        try:
            import json
            import time
            from pathlib import Path
            
            token_file = Path("config") / "auth_token.json"
            if not token_file.exists():
                return False
                
            with open(token_file, 'r', encoding='utf-8') as f:
                token_info = json.load(f)
                
            # 检查令牌是否过期
            current_time = time.time()
            if current_time > token_info.get('expires_at', 0):
                self._log("WARNING", "认证令牌已过期，将生成新令牌")
                return False
                
            self.config.auth_token = token_info['token']
            self._log("INFO", "已加载保存的认证令牌")
            return True
            
        except Exception as e:
            self._log("WARNING", f"加载认证令牌失败: {str(e)}")
            return False
            
    def regenerate_auth_token(self) -> str:
        """重新生成认证令牌"""
        old_token = self.config.auth_token
        self.config.auth_token = self._generate_secure_token()
        self._save_auth_token()
        
        self._log("INFO", "认证令牌已重新生成")
        
        # 断开所有未认证的客户端
        self._disconnect_unauthenticated_clients()
        
        return self.config.auth_token
         
    def _disconnect_unauthenticated_clients(self):
        """断开所有未认证的客户端"""
        if not self.config.enable_auth:
            return
            
        disconnected_count = 0
        for client in self.connection_pool.get_all_connections():
            if not client.authenticated:
                self._disconnect_client(client.client_id)
                disconnected_count += 1
                
        if disconnected_count > 0:
            self._log("INFO", f"已断开 {disconnected_count} 个未认证的客户端连接")
            
    def get_auth_token_info(self) -> dict:
        """获取认证令牌信息"""
        try:
            import json
            import time
            from pathlib import Path
            
            token_file = Path("config") / "auth_token.json"
            if not token_file.exists():
                return {"status": "no_token", "message": "未找到认证令牌文件"}
                
            with open(token_file, 'r', encoding='utf-8') as f:
                token_info = json.load(f)
                
            current_time = time.time()
            expires_at = token_info.get('expires_at', 0)
            
            return {
                "status": "valid" if current_time < expires_at else "expired",
                "created_at": token_info.get('created_at', 0),
                "expires_at": expires_at,
                "days_remaining": max(0, (expires_at - current_time) / (24 * 3600)),
                "version": token_info.get('version', "unknown")
            }
            
        except Exception as e:
            return {"status": "error", "message": f"读取令牌信息失败: {str(e)}"}
         
    def _create_ssl_context(self):
        """创建SSL上下文"""
        try:
            import ssl
            
            # 创建SSL上下文
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            
            # 检查证书文件
            if not self.config.ssl_cert_path or not self.config.ssl_key_path:
                # 如果未指定证书路径，生成自签名证书
                cert_path, key_path = self._generate_self_signed_cert()
                if not cert_path or not key_path:
                    return None
                self.config.ssl_cert_path = cert_path
                self.config.ssl_key_path = key_path
                
            # 验证证书文件存在
            import os
            if not os.path.exists(self.config.ssl_cert_path):
                self._log("ERROR", f"SSL证书文件不存在: {self.config.ssl_cert_path}", security_event=True)
                return None
                
            if not os.path.exists(self.config.ssl_key_path):
                self._log("ERROR", f"SSL私钥文件不存在: {self.config.ssl_key_path}", security_event=True)
                return None
                
            # 加载证书和私钥
            context.load_cert_chain(self.config.ssl_cert_path, self.config.ssl_key_path)
            
            # 验证证书有效性
            if not self._validate_ssl_certificate(self.config.ssl_cert_path):
                self._log("WARNING", "SSL证书验证失败，但仍将使用该证书", security_event=True)
            
            # 设置SSL选项
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE  # 对于调试服务器，不验证客户端证书
            
            # 设置安全的SSL协议版本
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.maximum_version = ssl.TLSVersion.TLSv1_3
            
            # 设置密码套件
            context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
            
            self._log("INFO", f"SSL上下文创建成功，使用证书: {self.config.ssl_cert_path}", security_event=True)
            return context
             
        except ImportError:
            self._log("ERROR", "SSL模块不可用")
            return None
        except ssl.SSLError as e:
            self._log("ERROR", f"SSL配置错误: {str(e)}", security_event=True)
            return None
        except FileNotFoundError as e:
            self._log("ERROR", f"SSL证书文件未找到: {str(e)}", security_event=True)
            return None
        except PermissionError as e:
            self._log("ERROR", f"SSL证书文件权限不足: {str(e)}", security_event=True)
            return None
        except Exception as e:
            self._log("ERROR", f"创建SSL上下文失败: {str(e)}", security_event=True)
            return None
             
    def _validate_ssl_certificate(self, cert_path: str) -> bool:
         """验证SSL证书"""
         try:
             import ssl
             from cryptography import x509
             from cryptography.hazmat.backends import default_backend
             import datetime
             
             # 读取证书文件
             with open(cert_path, 'rb') as f:
                 cert_data = f.read()
                 
             # 解析证书
             cert = x509.load_pem_x509_certificate(cert_data, default_backend())
             
             # 获取当前时间，确保时区一致性
             now = datetime.datetime.now(datetime.timezone.utc)
             
             # 获取证书有效期（使用UTC版本避免弃用警告）
             if hasattr(cert, 'not_valid_after_utc'):
                 not_valid_after = cert.not_valid_after_utc
                 not_valid_before = cert.not_valid_before_utc
             else:
                 not_valid_after = cert.not_valid_after
                 not_valid_before = cert.not_valid_before
             
             # 如果证书时间是offset-naive，添加UTC时区信息
             if not_valid_after.tzinfo is None:
                 not_valid_after = not_valid_after.replace(tzinfo=datetime.timezone.utc)
             if not_valid_before.tzinfo is None:
                 not_valid_before = not_valid_before.replace(tzinfo=datetime.timezone.utc)
             
             # 检查证书是否过期
             if not_valid_after < now:
                 self._log("WARNING", f"SSL证书已过期: {not_valid_after}", security_event=True)
                 return False
                 
             # 检查证书是否还未生效
             if not_valid_before > now:
                 self._log("WARNING", f"SSL证书尚未生效: {not_valid_before}", security_event=True)
                 return False
                 
             # 检查证书即将过期（30天内）
             days_until_expiry = (not_valid_after - now).days
             if days_until_expiry <= 30:
                 self._log("WARNING", f"SSL证书将在 {days_until_expiry} 天后过期", security_event=True)
                 
             # 检查证书主题
             subject = cert.subject
             self._log("INFO", f"SSL证书主题: {subject}")
             
             return True
             
         except ImportError:
             self._log("WARNING", "cryptography库不可用，跳过证书验证")
             return True  # 如果没有cryptography库，假设证书有效
         except Exception as e:
             self._log("WARNING", f"验证SSL证书时出错: {str(e)}")
             return False
             
    def _generate_self_signed_cert(self):
         """生成自签名证书"""
         try:
             from cryptography import x509
             from cryptography.x509.oid import NameOID
             from cryptography.hazmat.primitives import hashes, serialization
             from cryptography.hazmat.primitives.asymmetric import rsa
             import datetime
             import ipaddress
             
             # 生成私钥
             private_key = rsa.generate_private_key(
                 public_exponent=65537,
                 key_size=2048,
             )
             
             # 创建证书主题
             subject = issuer = x509.Name([
                 x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
                 x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Beijing"),
                 x509.NameAttribute(NameOID.LOCALITY_NAME, "Beijing"),
                 x509.NameAttribute(NameOID.ORGANIZATION_NAME, "XuanWu Debug Server"),
                 x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
             ])
             
             # 创建证书
             cert = x509.CertificateBuilder().subject_name(
                 subject
             ).issuer_name(
                 issuer
             ).public_key(
                 private_key.public_key()
             ).serial_number(
                 x509.random_serial_number()
             ).not_valid_before(
                 datetime.datetime.utcnow()
             ).not_valid_after(
                 datetime.datetime.utcnow() + datetime.timedelta(days=365)
             ).add_extension(
                 x509.SubjectAlternativeName([
                     x509.DNSName("localhost"),
                     x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                 ]),
                 critical=False,
             ).sign(private_key, hashes.SHA256())
             
             # 创建SSL证书目录
             from pathlib import Path
             ssl_dir = Path("ssl")
             ssl_dir.mkdir(exist_ok=True)
             
             # 保存证书和私钥
             cert_path = ssl_dir / "ssl_cert.pem"
             key_path = ssl_dir / "ssl_key.pem"
             
             # 写入证书文件
             with open(cert_path, "wb") as f:
                 f.write(cert.public_bytes(serialization.Encoding.PEM))
                 
             # 写入私钥文件
             with open(key_path, "wb") as f:
                 f.write(private_key.private_bytes(
                     encoding=serialization.Encoding.PEM,
                     format=serialization.PrivateFormat.PKCS8,
                     encryption_algorithm=serialization.NoEncryption()
                 ))
                 
             # 设置文件权限（仅所有者可读）
             import os
             if os.name != 'nt':  # 非Windows系统
                 os.chmod(cert_path, 0o600)
                 os.chmod(key_path, 0o600)
                 
             self._log("INFO", f"已生成自签名证书: {cert_path}, {key_path}", security_event=True)
             return str(cert_path), str(key_path)
             
         except ImportError:
             self._log("ERROR", "cryptography库不可用，无法生成自签名证书。请安装: pip install cryptography", security_event=True)
             return None, None
         except PermissionError as e:
             self._log("ERROR", f"生成证书文件权限不足: {str(e)}", security_event=True)
             return None, None
         except OSError as e:
             self._log("ERROR", f"生成证书文件系统错误: {str(e)}", security_event=True)
             return None, None
         except Exception as e:
             self._log("ERROR", f"生成自签名证书失败: {str(e)}", security_event=True)
             return None, None
         
    def _handle_message_result(self, client: IntegratedClientInfo, future):
        """处理消息处理结果"""
        try:
            result = future.result()
            response = json.dumps({"result": result})
            
            # 添加调试日志：记录返回给客户端的信息
            self._log("DEBUG", f"[SERVER] 向客户端 {client.client_id} 返回响应: {response}")
            self._log("DEBUG", f"[SERVER] 响应长度: {len(response)} 字符")
            
            # 检查客户端连接状态，避免对已关闭的套接字进行操作
            if client.state != ClientConnectionState.DISCONNECTED:
                try:
                    # 安全编码发送
                    try:
                        encoded_response = response.encode('utf-8')
                        self._log("DEBUG", f"[SERVER] 发送编码后数据长度: {len(encoded_response)} 字节")
                        self._log("DEBUG", f"[SERVER] 发送数据(hex): {encoded_response.hex()}")
                        client.socket.send(encoded_response)
                        client.bytes_sent += len(encoded_response)
                        client.commands_sent += 1
                        self._log("DEBUG", f"[SERVER] 成功发送响应到客户端 {client.client_id}")
                    except UnicodeEncodeError as e:
                        self._log("ERROR", f"响应消息编码失败: {str(e)}")
                        # 使用错误处理模式重新编码
                        encoded_response = response.encode('utf-8', errors='replace')
                        self._log("DEBUG", f"[SERVER] 使用替换模式重新编码，数据长度: {len(encoded_response)} 字节")
                        client.socket.send(encoded_response)
                        client.bytes_sent += len(encoded_response)
                        client.commands_sent += 1
                        self._log("DEBUG", f"[SERVER] 成功发送替换编码响应到客户端 {client.client_id}")
                except (OSError, ConnectionError) as e:
                    # 套接字已关闭或连接已断开
                    self._log("WARNING", f"客户端 {client.client_id} 套接字已关闭: {str(e)}")
                    client.state = ClientConnectionState.DISCONNECTED
            else:
                self._log("WARNING", f"[SERVER] 客户端 {client.client_id} 已断开连接，跳过响应发送")
            
        except Exception as e:
            self._log("ERROR", f"发送响应失败: {str(e)}")
            
    def _disconnect_client(self, client_id: str):
        """断开客户端连接"""
        client = self.connection_pool.remove_connection(client_id)
        if client:
            try:
                client.socket.close()
            except:
                pass
                
            self.client_disconnected.emit(client_id)
            self._log("INFO", f"客户端已断开连接: {client_id}")
            
    def get_performance_stats(self) -> dict:
        """获取性能统计"""
        stats = self.stats.copy()
        stats.update(self.message_processor.get_stats())
        return stats
        
    def get_client_info(self, client_id: str) -> Optional[IntegratedClientInfo]:
        """获取客户端信息"""
        return self.connection_pool.get_connection(client_id)
        
    def get_all_clients(self) -> List[IntegratedClientInfo]:
        """获取所有客户端"""
        return self.connection_pool.get_all_connections()
        
    def disconnect_client(self, client_id: str) -> bool:
        """断开指定客户端"""
        client = self.connection_pool.get_connection(client_id)
        if client:
            client.state = ClientConnectionState.DISCONNECTED
            return True
        return False
        
    def broadcast_message(self, message: str):
        """广播消息给所有客户端"""
        for client in self.connection_pool.get_all_connections():
            # 检查客户端连接状态，避免对已关闭的套接字进行操作
            if client.state != ClientConnectionState.DISCONNECTED:
                try:
                    # 安全编码发送
                    try:
                        encoded_message = message.encode('utf-8')
                        client.socket.send(encoded_message)
                    except UnicodeEncodeError as e:
                        self._log("ERROR", f"广播消息编码失败: {str(e)}")
                        # 使用错误处理模式重新编码
                        encoded_message = message.encode('utf-8', errors='replace')
                        client.socket.send(encoded_message)
                except (OSError, ConnectionError) as e:
                    # 套接字已关闭或连接已断开，标记为断开状态
                    self._log("WARNING", f"广播时发现客户端 {client.client_id} 套接字已关闭: {str(e)}")
                    client.state = ClientConnectionState.DISCONNECTED
                except Exception:
                    # 其他异常继续忽略
                    pass


# ==================== UI组件 ====================

class ClientTableModel(QAbstractTableModel):
    """客户端表格模型"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.clients: List[IntegratedClientInfo] = []
        self.headers = [
            "客户端ID", "IP地址", "端口", "连接时间", "状态", 
            "最后活动", "命令数", "流量", "响应时间", "会话"
        ]
        self._cache = {}  # 缓存计算结果
        
    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.clients)
        
    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.headers)
        
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.headers[section]
        return QVariant()
        
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.clients):
            return QVariant()
            
        client = self.clients[index.row()]
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            return self._get_display_data(client, col)
        elif role == Qt.ItemDataRole.ForegroundRole:
            return self._get_color_data(client, col)
        elif role == Qt.ItemDataRole.ToolTipRole:
            return self._get_tooltip_data(client, col)
            
        return QVariant()
        
    def _get_display_data(self, client: IntegratedClientInfo, col: int):
        """获取显示数据（带缓存）"""
        cache_key = (client.client_id, col, client.last_activity)
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        if col == 0:  # 客户端ID
            result = client.client_id[:12] + "..."
        elif col == 1:  # IP地址
            result = client.address[0]
        elif col == 2:  # 端口
            result = str(client.address[1])
        elif col == 3:  # 连接时间
            result = time.strftime('%H:%M:%S', time.localtime(client.connect_time))
        elif col == 4:  # 状态
            # 状态中文映射
            state_texts = {
                "connecting": "连接中",
                "connected": "已连接",
                "authenticated": "已认证",
                "disconnected": "已断开",
                "error": "错误"
            }
            result = state_texts.get(client.state.value, client.state.value)
        elif col == 5:  # 最后活动
            elapsed = time.time() - client.last_activity
            if elapsed < 60:
                result = f"{int(elapsed)}秒前"
            elif elapsed < 3600:
                result = f"{int(elapsed/60)}分钟前"
            else:
                result = f"{int(elapsed/3600)}小时前"
        elif col == 6:  # 命令数
            result = str(client.commands_sent)
        elif col == 7:  # 流量
            total_bytes = client.bytes_received + client.bytes_sent
            if total_bytes < 1024:
                result = f"{total_bytes}B"
            elif total_bytes < 1024*1024:
                result = f"{total_bytes/1024:.1f}KB"
            else:
                result = f"{total_bytes/(1024*1024):.1f}MB"
        elif col == 8:  # 响应时间
            avg_time = client.get_avg_response_time()
            result = f"{avg_time*1000:.1f}ms" if avg_time > 0 else "N/A"
        elif col == 9:  # 会话
            result = client.session_id[:8] + "..." if client.session_id else "无"
        else:
            result = ""
            
        self._cache[cache_key] = result
        return result
        
    def _get_color_data(self, client: IntegratedClientInfo, col: int):
        """获取颜色数据"""
        if col == 4:  # 状态列
            if client.state == ClientConnectionState.CONNECTED:
                return QColor(0, 150, 0)  # 绿色
            elif client.state == ClientConnectionState.AUTHENTICATED:
                return QColor(0, 100, 200)  # 蓝色
            elif client.state == ClientConnectionState.ERROR:
                return QColor(200, 0, 0)  # 红色
            else:
                return QColor(150, 150, 0)  # 黄色
        return QVariant()
        
    def _get_tooltip_data(self, client: IntegratedClientInfo, col: int):
        """获取工具提示数据"""
        if col == 0:  # 客户端ID
            return f"完整ID: {client.client_id}\n用户代理: {client.user_agent}\n协议版本: {client.protocol_version}"
        elif col == 5:  # 最后活动
            return f"最后活动时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(client.last_activity))}"
        elif col == 7:  # 流量
            return f"接收: {client.bytes_received} 字节\n发送: {client.bytes_sent} 字节"
        return QVariant()
        
    def update_clients(self, clients: List[IntegratedClientInfo]):
        """更新客户端列表"""
        self.beginResetModel()
        self.clients = clients
        self._cache.clear()  # 清空缓存
        self.endResetModel()
        
    def refresh_client(self, client_id: str):
        """刷新特定客户端"""
        for i, client in enumerate(self.clients):
            if client.client_id == client_id:
                # 清除该客户端的缓存
                keys_to_remove = [k for k in self._cache.keys() if k[0] == client_id]
                for key in keys_to_remove:
                    del self._cache[key]
                    
                # 发出数据变化信号
                top_left = self.index(i, 0)
                bottom_right = self.index(i, self.columnCount() - 1)
                self.dataChanged.emit(top_left, bottom_right)
                break


class AsyncLogWidget(QVBoxLayout):
    """异步日志显示组件"""
    
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        
        # 创建文本浏览器
        self.text_browser = QTextBrowser()
        self.text_browser.document().setMaximumBlockCount(1000)  # 限制最大行数
        
        # 创建自动滚动复选框
        self.auto_scroll_check = QCheckBox("自动滚动")
        auto_scroll_value = config.auto_scroll if config else True
        self.auto_scroll_check.setChecked(auto_scroll_value)
        
        # 连接信号 - 当复选框状态改变时保存配置
        self.auto_scroll_check.toggled.connect(self._on_auto_scroll_toggled)
        
        # 添加到布局
        self.addWidget(self.text_browser)
        self.addWidget(self.auto_scroll_check)
        
        # 日志相关属性
        self.log_buffer = deque(maxlen=100)
        self.flush_timer = QTimer()
        self.flush_timer.timeout.connect(self._flush_logs)
        self.flush_timer.start(100)  # 每100ms刷新一次，提高响应速度
        
    @property
    def auto_scroll(self):
        return self.auto_scroll_check.isChecked()
        
    def add_log_async(self, level: str, message: str):
        """异步添加日志"""
        timestamp = time.time()  # 使用数值时间戳而不是格式化字符串
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        self.log_buffer.append(log_entry)
        
        # 总是触发刷新，滚动逻辑由_flush_logs内部处理
        QTimer.singleShot(10, self._flush_logs)
        
    def _flush_logs(self):
        """刷新日志显示"""
        if not self.log_buffer:
            return
            
        # 批量处理日志
        logs_to_add = []
        while self.log_buffer:
            logs_to_add.append(self.log_buffer.popleft())
            
        # 保存自动滚动状态
        should_auto_scroll = self.auto_scroll_check.isChecked()
        scrollbar = self.text_browser.verticalScrollBar()
        
        # 逐条添加日志，使用带颜色的HTML格式
        for log_entry in logs_to_add:
            color = self._get_level_color(log_entry["level"])
            # 构建带颜色的HTML格式
            log_text = f"<span style='color: {color}'>[{log_entry['timestamp']}] {log_entry['level']}: {log_entry['message']}</span>"
            
            # 使用append添加HTML格式的文本
            self.text_browser.append(log_text)
            
        # 如果启用自动滚动，强制滚动到底部
        if should_auto_scroll:
            # 立即滚动到底部
            scrollbar.setValue(scrollbar.maximum())
            # 延迟再次确保滚动到底部
            QTimer.singleShot(50, lambda: scrollbar.setValue(scrollbar.maximum()))
            
        # 限制日志大小
        self._limit_log_size()
        

        
    def _get_level_color(self, level: str) -> str:
        """获取日志级别对应的颜色，支持深色/浅色主题自适应"""
        # 检测当前主题
        is_dark = self._is_dark_theme()
        
        if is_dark:
            # 深色主题颜色配置
            colors = {
                "调试": "#888888",    # 灰色
                "信息": "#ffffff",     # 白色
                "警告": "#ffaa00",  # 橙色
                "错误": "#ff6666",    # 红色
                "严重": "#ff3333" # 亮红色
            }
        else:
            # 浅色主题颜色配置
            colors = {
                "调试": "#666666",    # 深灰色
                "信息": "#000000",     # 黑色
                "警告": "#cc6600",  # 深橙色
                "错误": "#cc0000",    # 深红色
                "严重": "#990000" # 暗红色
            }
        
        return colors.get(level, "#000000" if not is_dark else "#ffffff")
    
    def _is_dark_theme(self) -> bool:
        """检测当前是否为深色主题"""
        try:
            # 方法1: 检查应用程序调色板
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                palette = app.palette()
                window_color = palette.color(palette.ColorRole.Window)
                # 如果窗口背景颜色较暗，则认为是深色主题
                brightness = (window_color.red() + window_color.green() + window_color.blue()) / 3
                if brightness < 128:
                    return True
            
            # 方法2: 检查设置文件中的主题配置
            try:
                import json
                settings_file = "settings.json"
                if os.path.exists(settings_file):
                    with open(settings_file, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                        theme = settings.get('theme', '浅色')
                        return theme in ['深色', '蓝色', '绿色', '紫色', '高对比度']
            except:
                pass
            
            # 方法3: 检查日志显示区域的样式
            if hasattr(self, 'text_browser'):
                style = self.text_browser.styleSheet()
                if 'color: #ffffff' in style or 'background' in style and '#' in style:
                    # 如果设置了白色文字，可能是深色主题
                    return 'color: #ffffff' in style
            
            return False
        except Exception as e:
            # 默认返回False（浅色主题）
            return False
    
    def _on_theme_changed(self):
        """主题变化时刷新日志颜色"""
        try:
            # 重新应用过滤，这会使用新的主题颜色
            self._filter_logs()
        except Exception as e:
            # 忽略主题变化时的错误
            pass
        
    def _limit_log_size(self):
        """限制日志大小"""
        document = self.text_browser.document()
        if document.blockCount() > 1000:
            cursor = QTextCursor(document)
            cursor.movePosition(cursor.MoveOperation.Start)
            for _ in range(100):  # 删除前100行
                cursor.select(cursor.SelectionType.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()  # 删除换行符
                
    def clear_logs(self):
        """清空日志"""
        self.text_browser.clear()
        self.log_buffer.clear()
        
    def set_auto_scroll(self, enabled: bool):
        """设置自动滚动"""
        if hasattr(self, 'auto_scroll_check'):
            self.auto_scroll_check.setChecked(enabled)
            # 立即保存配置，无需额外的保存按钮
            self._save_auto_scroll_config(enabled)

    def _save_auto_scroll_config(self, enabled: bool):
        """保存自动滚动配置"""
        try:
            # 获取当前配置
            from core.settings import load_settings, save_settings
            settings = load_settings()
            
            # 更新自动滚动设置（保持向后兼容）
            settings['remote_debug.auto_scroll'] = enabled
            
            # 同时更新remote_debug节点中的auto_scroll配置
            if 'remote_debug' not in settings:
                settings['remote_debug'] = {}
            settings['remote_debug']['auto_scroll'] = enabled
            
            # 更新当前配置对象
            self.config.auto_scroll = enabled
            
            save_settings(settings)
        except Exception as e:
            print(f"保存自动滚动配置失败: {e}")
    
    def _load_auto_scroll_config(self):
        """加载自动滚动配置"""
        try:
            from core.settings import load_settings
            settings = load_settings()
            
            # 获取自动滚动设置，默认为True
            auto_scroll_enabled = settings.get('remote_debug.auto_scroll', True)
            
            # 只更新UI，不直接设置auto_scroll属性（因为它是只读的）
            self.auto_scroll_check.setChecked(auto_scroll_enabled)
            
        except Exception as e:
            print(f"加载自动滚动配置失败: {e}")
            # 如果加载失败，使用默认值
            self.auto_scroll_check.setChecked(True)
    

        
    def scroll_to_bottom(self):
        """强制滚动到底部"""
        try:
            # 强制处理所有待处理事件
            QApplication.processEvents()
            
            # 强制更新文档布局
            self.text_browser.document().adjustSize()
            
            # 获取垂直滚动条并强制更新范围
            scrollbar = self.text_browser.verticalScrollBar()
            if scrollbar:
                # 强制更新滚动条范围
                scrollbar.setRange(scrollbar.minimum(), scrollbar.maximum())
                # 设置到最大值
                scrollbar.setValue(scrollbar.maximum())
                
            # 移动光标到文档末尾
            cursor = self.text_browser.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.text_browser.setTextCursor(cursor)
            self.text_browser.ensureCursorVisible()
            
            # 再次强制设置滚动条到最大值
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())
                
            # 最后处理事件确保所有更新生效
            QApplication.processEvents()
            
        except Exception as e:
            # 如果出错，使用最基本的滚动方法
            try:
                scrollbar = self.text_browser.verticalScrollBar()
                if scrollbar:
                    scrollbar.setValue(scrollbar.maximum())
            except:
                pass
    
    def _on_auto_scroll_toggled(self, checked: bool):
        """处理自动滚动复选框状态变化"""
        try:
            # 保存配置
            self._save_auto_scroll_config(checked)
            
            # 如果启用自动滚动，立即滚动到底部
            if checked:
                self.scroll_to_bottom()
                
        except Exception as e:
            print(f"处理自动滚动状态变化失败: {e}")


class PerformanceMonitor(QObject):
    """性能监控器"""
    
    stats_updated = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.server: Optional[IntegratedDebugServer] = None
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._collect_stats)
        self.stats_history = deque(maxlen=100)
        
    def set_server(self, server: IntegratedDebugServer):
        """设置服务器实例"""
        self.server = server
        
    def start_monitoring(self, interval: int = 5000):
        """开始监控"""
        self.monitor_timer.start(interval)
        
    def stop_monitoring(self):
        """停止监控"""
        self.monitor_timer.stop()
        
    def _collect_stats(self):
        """收集统计信息"""
        if not self.server:
            return
            
        stats = self.server.get_performance_stats()
        stats['timestamp'] = time.time()
        
        # 添加系统资源信息
        try:
            import psutil
            process = psutil.Process()
            stats['memory_usage'] = process.memory_info().rss / 1024 / 1024  # MB
            stats['cpu_usage'] = process.cpu_percent()
        except ImportError:
            stats['memory_usage'] = 0
            stats['cpu_usage'] = 0
            
        self.stats_history.append(stats)
        self.stats_updated.emit(stats)
        
    def get_stats_history(self) -> List[dict]:
        """获取统计历史"""
        return list(self.stats_history)


class FeatureConfigWidget(QWidget):
    """功能配置组件"""
    
    feature_changed = pyqtSignal(str, bool)
    features_applied = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.feature_checkboxes = {}
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 功能开关
        features = [
            (FeatureFlags.BASIC_DEBUG, "基础调试功能", "提供基本的远程调试服务器和客户端管理"),
            (FeatureFlags.PERFORMANCE_OPT, "性能优化", "启用连接池、异步处理、缓存机制等优化"),
            (FeatureFlags.PLUGIN_SYSTEM, "插件系统", "支持动态加载和管理插件"),
            (FeatureFlags.SCRIPT_EXECUTOR, "脚本执行", "允许远程执行Python脚本"),
            (FeatureFlags.FILE_TRANSFER, "文件传输", "支持文件上传和下载功能"),
            (FeatureFlags.SESSION_MANAGER, "会话管理", "提供会话创建、切换和状态保存"),
            (FeatureFlags.ADVANCED_TOOLS, "高级工具", "包含各种高级调试和分析工具")
        ]
        
        for feature, name, description in features:
            checkbox = QCheckBox(name)
            checkbox.setToolTip(description)
            # 初始状态设为False，稍后通过set_enabled_features方法从配置文件设置
            checkbox.setChecked(False)
            checkbox.toggled.connect(lambda checked, f=feature: self.feature_changed.emit(f.value, checked))
            
            self.feature_checkboxes[feature] = checkbox
            layout.addWidget(checkbox)
            
        # 应用功能配置按钮
        apply_features_button = QPushButton("应用功能配置")
        apply_features_button.clicked.connect(self._apply_features)
        layout.addWidget(apply_features_button)
            
    def get_enabled_features(self) -> Set[FeatureFlags]:
        """获取启用的功能"""
        enabled = set()
        for feature, checkbox in self.feature_checkboxes.items():
            if checkbox.isChecked():
                enabled.add(feature)
        return enabled
        
    def set_enabled_features(self, features: Set[FeatureFlags]):
        """设置启用的功能"""
        for feature, checkbox in self.feature_checkboxes.items():
            checkbox.setChecked(feature in features)
            
    def _apply_features(self):
        """应用功能配置"""
        enabled_features = self.get_enabled_features()
        self.features_applied.emit()
        
        # 显示应用成功的消息
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "功能配置", 
                              f"已应用功能配置！\n启用的功能: {len(enabled_features)} 个")


class IntegratedRemoteDebugWidget(QDialog):
    """集成远程调试主窗口"""
    
    def __init__(self, parent=None, dev_tools_panel=None):
        super().__init__(parent)
        self.setWindowTitle("远程调试设置")
        self.setMinimumSize(1200, 800)
        
        # 配置和服务器
        self.config = IntegratedServerConfig()
        self.server: Optional[IntegratedDebugServer] = None
        self.dev_tools_panel = dev_tools_panel
        
        # UI组件
        self.client_model = ClientTableModel()
        self.log_widget = AsyncLogWidget(config=self.config)
        self.performance_monitor = PerformanceMonitor()
        self.feature_config = FeatureConfigWidget()
        
        # 初始化自动滚动属性
        self.auto_scroll = True  # 默认启用自动滚动
        
        # 状态
        self.is_server_running = False
        self.start_time = None
        self.session_list = None
        
        # 初始化性能统计标签字典
        self.stats_labels = {}
        
        # 创建定时器用于更新底部状态栏
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_footer_stats)
        
        self._setup_ui()
        self._connect_signals()
        self._load_config()
        
    def _setup_ui(self):
        """设置上下排版的模块化UI界面"""
        # 设置窗口属性
        self.setWindowTitle("远程调试控制面板")
        self.resize(550, 450)
        self.setMinimumSize(500, 400)
        
        # 窗口居中显示
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        window_geometry = self.geometry()
        x = (screen.width() - window_geometry.width()) // 2
        y = (screen.height() - window_geometry.height()) // 2
        self.move(x, y)
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(3)
        
        # 创建头部控制区域
        header_widget = self._create_header_widget()
        main_layout.addWidget(header_widget)
        
        # 创建滚动区域以容纳所有模块
        from PyQt6.QtWidgets import QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 创建主要内容区域（上下排版的模块化布局）
        content_widget = self._create_modular_content_widget()
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, 1)
        
        # 创建底部状态栏
        footer_widget = self._create_footer_widget()
        main_layout.addWidget(footer_widget)
    
    def _create_header_widget(self) -> QWidget:
        """创建简洁头部区域"""
        header_frame = QFrame()
        header_frame.setFixedHeight(30)
        
        layout = QHBoxLayout(header_frame)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(3)
        
        # 标题
        title_label = QLabel("远程调试")
        layout.addWidget(title_label)
        
        # 状态标签
        self.status_label = QLabel("已停止")
        
        # 端口配置
        port_label = QLabel("端口:")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1000, 65535)
        self.port_spin.setValue(9009)
        self.port_spin.setFixedWidth(60)
        
        # 控制按钮
        self.start_button = QPushButton("启动")
        self.stop_button = QPushButton("停止")
        self.help_button = QPushButton("使用说明")
        
        for btn in [self.start_button, self.stop_button]:
            btn.setFixedSize(50, 20)
        
        self.help_button.setFixedSize(60, 20)
        self.stop_button.setEnabled(False)
        
        layout.addWidget(self.status_label)
        layout.addWidget(port_label)
        layout.addWidget(self.port_spin)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.help_button)
        
        return header_frame
    
    def _create_modular_content_widget(self) -> QWidget:
        """创建上下排版的模块化内容区域"""
        content_widget = QWidget()
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(6)
        
        # 第一行 - 状态控制和配置
        top_row = QWidget()
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)
        
        # 服务器状态和控制模块
        status_module = self._create_status_control_module()
        top_layout.addWidget(status_module)
        
        # 服务器配置模块
        config_module = self._create_config_module()
        top_layout.addWidget(config_module)
        
        # 高级功能模块
        advanced_module = self._create_advanced_widget()
        top_layout.addWidget(advanced_module)
        
        # 第二行 - 客户端管理
        clients_module = self._create_clients_module()
        
        # 第三行 - 性能监控和日志
        bottom_row = QWidget()
        bottom_layout = QHBoxLayout(bottom_row)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(6)
        
        # 性能监控模块
        performance_module = self._create_performance_module()
        bottom_layout.addWidget(performance_module)
        
        # 系统日志模块
        logs_module = self._create_logs_module()
        bottom_layout.addWidget(logs_module)
        
        # 添加到主布局
        main_layout.addWidget(top_row)
        main_layout.addWidget(clients_module)
        main_layout.addWidget(bottom_row)
        
        return content_widget
    
    def _create_status_control_module(self) -> QWidget:
        """创建服务器状态和控制模块"""
        module = QGroupBox("服务器状态与控制")
        layout = QVBoxLayout(module)
        layout.setSpacing(3)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # 状态信息区域
        status_frame = QFrame()
        status_layout = QGridLayout(status_frame)
        status_layout.setSpacing(4)
        
        # 状态标签
        self.server_status_label = QLabel("服务器: 已停止")
        self.server_status_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
        self.client_count_label_dash = QLabel("客户端: 0")
        self.message_rate_label = QLabel("消息: 0/分钟")
        self.system_load_label = QLabel("负载: 0%")
        
        status_layout.addWidget(self.server_status_label, 0, 0)
        status_layout.addWidget(self.client_count_label_dash, 0, 1)
        status_layout.addWidget(self.message_rate_label, 1, 0)
        status_layout.addWidget(self.system_load_label, 1, 1)
        
        layout.addWidget(status_frame)
        
        # 快速操作按钮区域
        actions_frame = QFrame()
        actions_layout = QGridLayout(actions_frame)
        actions_layout.setSpacing(3)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        
        self.restart_btn = QPushButton("重启服务器")
        self.clear_logs_btn = QPushButton("清空日志")
        self.export_config_btn = QPushButton("导出配置")
        self.import_config_btn = QPushButton("导入配置")
        self.test_client_btn = QPushButton("测试客户端")
        self.advanced_test_btn = QPushButton("高级测试客户端")
        
        # 上排三个按钮
        actions_layout.addWidget(self.restart_btn, 0, 0)
        actions_layout.addWidget(self.clear_logs_btn, 0, 1)
        actions_layout.addWidget(self.export_config_btn, 0, 2)
        
        # 下排三个按钮
        actions_layout.addWidget(self.import_config_btn, 1, 0)
        actions_layout.addWidget(self.test_client_btn, 1, 1)
        actions_layout.addWidget(self.advanced_test_btn, 1, 2)
        
        layout.addWidget(actions_frame)
        
        return module
    
    def _create_config_module(self) -> QWidget:
        """创建服务器配置模块"""
        module = QGroupBox("服务器配置")
        layout = QVBoxLayout(module)
        layout.setSpacing(3)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # 基础配置区域
        config_frame = QFrame()
        config_layout = QGridLayout(config_frame)
        config_layout.setSpacing(2)
        config_layout.setContentsMargins(0, 0, 0, 0)
        
        # 主机地址
        config_layout.addWidget(QLabel("主机地址:"), 0, 0)
        self.host_edit = QLineEdit("127.0.0.1")
        self.host_edit.setFixedWidth(100)
        config_layout.addWidget(self.host_edit, 0, 1)
        
        # 端口
        config_layout.addWidget(QLabel("端口:"), 0, 2)
        self.port_edit = QSpinBox()
        self.port_edit.setRange(1000, 65535)
        self.port_edit.setValue(9009)
        self.port_edit.setFixedWidth(70)
        config_layout.addWidget(self.port_edit, 0, 3)
        
        # 密码
        config_layout.addWidget(QLabel("密码:"), 1, 0)
        self.password_edit = QLineEdit("")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("请设置强密码")
        self.password_edit.setFixedWidth(100)
        self.password_edit.textChanged.connect(self._validate_password)
        config_layout.addWidget(self.password_edit, 1, 1)
        
        # 最大客户端
        config_layout.addWidget(QLabel("最大客户端:"), 1, 2)
        self.max_clients_spin = QSpinBox()
        self.max_clients_spin.setRange(1, 100)
        self.max_clients_spin.setValue(10)
        self.max_clients_spin.setFixedWidth(70)
        config_layout.addWidget(self.max_clients_spin, 1, 3)
        
        layout.addWidget(config_frame)
        
        # 功能选项区域
        options_frame = QFrame()
        options_layout = QHBoxLayout(options_frame)
        options_layout.setSpacing(2)
        options_layout.setContentsMargins(0, 0, 0, 0)
        
        self.auth_check = QCheckBox("启用身份验证")
        self.ssl_check = QCheckBox("启用SSL加密")
        self.auto_start_check = QCheckBox("自动启动")
        self.web_interface_check = QCheckBox("启用Web界面")
        
        options_layout.addWidget(self.auth_check)
        options_layout.addWidget(self.ssl_check)
        options_layout.addWidget(self.auto_start_check)
        options_layout.addWidget(self.web_interface_check)
        options_layout.addStretch()
        
        layout.addWidget(options_frame)
        
        # Web界面配置区域
        web_config_frame = QFrame()
        web_config_layout = QGridLayout(web_config_frame)
        web_config_layout.setSpacing(2)
        web_config_layout.setContentsMargins(0, 0, 0, 0)
        
        # Web服务器端口
        web_config_layout.addWidget(QLabel("Web端口:"), 0, 0)
        self.web_port_spin = QSpinBox()
        self.web_port_spin.setRange(1000, 65535)
        self.web_port_spin.setValue(8080)
        self.web_port_spin.setFixedWidth(70)
        web_config_layout.addWidget(self.web_port_spin, 0, 1)
        
        # WebSocket端口
        web_config_layout.addWidget(QLabel("WebSocket端口:"), 0, 2)
        self.websocket_port_spin = QSpinBox()
        self.websocket_port_spin.setRange(1000, 65535)
        self.websocket_port_spin.setValue(8081)
        self.websocket_port_spin.setFixedWidth(70)
        web_config_layout.addWidget(self.websocket_port_spin, 0, 3)
        
        # Web界面主机地址
        web_config_layout.addWidget(QLabel("Web主机:"), 1, 0)
        self.web_host_edit = QLineEdit("127.0.0.1")
        self.web_host_edit.setFixedWidth(100)
        web_config_layout.addWidget(self.web_host_edit, 1, 1)
        
        # Web界面访问按钮
        self.open_web_btn = QPushButton("打开Web界面")
        self.open_web_btn.setEnabled(False)
        web_config_layout.addWidget(self.open_web_btn, 1, 2, 1, 2)
        
        layout.addWidget(web_config_frame)
        
        # 连接Web界面配置的启用/禁用逻辑
        def toggle_web_config(enabled):
            self.web_port_spin.setEnabled(enabled)
            self.websocket_port_spin.setEnabled(enabled)
            self.web_host_edit.setEnabled(enabled)
            
        self.web_interface_check.toggled.connect(toggle_web_config)
        toggle_web_config(False)  # 初始状态为禁用
        
        # 配置按钮区域
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setSpacing(5)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        self.apply_btn = QPushButton("应用配置")
        self.save_config_btn = QPushButton("保存配置")
        # self.apply_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 6px 16px; }")
        # self.save_config_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 6px 16px; }")
        
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(self.save_config_btn)
        button_layout.addStretch()
        
        options_layout.addWidget(button_frame)
        
        layout.addWidget(options_frame)
        
        # 身份验证Token管理区域
        self.auth_token_frame = QFrame()
        auth_token_layout = QVBoxLayout(self.auth_token_frame)
        auth_token_layout.setSpacing(2)
        auth_token_layout.setContentsMargins(0, 0, 0, 0)
        
        # Token显示区域
        token_display_frame = QFrame()
        token_display_layout = QHBoxLayout(token_display_frame)
        token_display_layout.setSpacing(2)
        token_display_layout.setContentsMargins(0, 0, 0, 0)
        
        token_display_layout.addWidget(QLabel("认证Token:"))
        self.auth_token_edit = QLineEdit()
        self.auth_token_edit.setReadOnly(True)
        self.auth_token_edit.setPlaceholderText("启用身份验证后将显示Token")
        token_display_layout.addWidget(self.auth_token_edit)
        
        # Token操作按钮
        self.copy_token_btn = QPushButton("复制")
        self.copy_token_btn.setFixedWidth(50)
        self.regenerate_token_btn = QPushButton("重新生成")
        self.regenerate_token_btn.setFixedWidth(70)
        self.show_token_info_btn = QPushButton("详情")
        self.show_token_info_btn.setFixedWidth(50)
        
        token_display_layout.addWidget(self.copy_token_btn)
        token_display_layout.addWidget(self.regenerate_token_btn)
        token_display_layout.addWidget(self.show_token_info_btn)
        
        auth_token_layout.addWidget(token_display_frame)
        
        # Token使用说明
        token_help_label = QLabel("客户端连接时需要提供此Token进行身份验证")
        token_help_label.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        auth_token_layout.addWidget(token_help_label)
        
        layout.addWidget(self.auth_token_frame)
        
        # 初始状态下隐藏Token管理区域
        self.auth_token_frame.setVisible(False)
        
        return module
    
    def _create_clients_module(self) -> QWidget:
        """创建客户端管理模块"""
        module = QGroupBox("客户端管理")
        layout = QVBoxLayout(module)
        layout.setSpacing(3)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # 客户端列表区域
        self.client_table = QTableWidget()
        self.client_table.setColumnCount(6)
        self.client_table.setHorizontalHeaderLabels(["客户端ID", "IP地址", "连接时间", "状态", "消息数", "操作"])
        self.client_table.horizontalHeader().setStretchLastSection(True)
        self.client_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.client_table.setMaximumHeight(100)  # 限制高度以适应上下布局
        self.client_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.client_table)
        
        # 客户端操作按钮区域
        client_actions_frame = QFrame()
        client_actions_layout = QHBoxLayout(client_actions_frame)
        client_actions_layout.setSpacing(3)
        client_actions_layout.setContentsMargins(0, 0, 0, 0)
        
        self.refresh_clients_btn = QPushButton("刷新列表")
        # self.refresh_clients_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 4px 12px; }")
        
        self.disconnect_client_btn = QPushButton("断开选中")
        # self.disconnect_client_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; padding: 4px 12px; }")
        
        self.disconnect_all_btn = QPushButton("断开所有")
        # self.disconnect_all_btn.setStyleSheet("QPushButton { background-color: #FF5722; color: white; font-weight: bold; padding: 4px 12px; }")
        
        self.broadcast_btn = QPushButton("广播消息")
        # self.broadcast_btn.setStyleSheet("QPushButton { background-color: #9C27B0; color: white; font-weight: bold; padding: 4px 12px; }")
        
        client_actions_layout.addWidget(self.refresh_clients_btn)
        client_actions_layout.addWidget(self.disconnect_client_btn)
        client_actions_layout.addWidget(self.disconnect_all_btn)
        client_actions_layout.addWidget(self.broadcast_btn)
        
        layout.addWidget(client_actions_frame)
        
        return module
    
    def _create_performance_module(self) -> QWidget:
        """创建性能监控模块"""
        module = QGroupBox("性能监控")
        layout = QVBoxLayout(module)
        layout.setSpacing(3)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # 性能指标区域
        metrics_frame = QFrame()
        metrics_layout = QGridLayout(metrics_frame)
        metrics_layout.setSpacing(4)
        
        # 性能标签
        self.cpu_label = QLabel("CPU使用率: 0%")
        self.cpu_label.setStyleSheet("QLabel { color: #2196F3; font-weight: bold; }")
        
        self.memory_label_perf = QLabel("内存使用: 0MB")
        self.memory_label_perf.setStyleSheet("QLabel { color: #4CAF50; font-weight: bold; }")
        
        self.network_label = QLabel("网络流量: 0KB/s")
        self.network_label.setStyleSheet("QLabel { color: #FF9800; font-weight: bold; }")
        
        self.connection_pool_label = QLabel("连接池: 0/50")
        self.connection_pool_label.setStyleSheet("QLabel { color: #9C27B0; font-weight: bold; }")
        
        metrics_layout.addWidget(self.cpu_label, 0, 0)
        metrics_layout.addWidget(self.memory_label_perf, 0, 1)
        metrics_layout.addWidget(self.network_label, 1, 0)
        metrics_layout.addWidget(self.connection_pool_label, 1, 1)
        
        layout.addWidget(metrics_frame)
        
        # 性能数据显示区域
        self.performance_display = QTextBrowser()
        self.performance_display.setMaximumHeight(80)  # 限制高度
        
        layout.addWidget(self.performance_display)
        
        # 性能控制按钮
        perf_actions_frame = QFrame()
        perf_actions_layout = QHBoxLayout(perf_actions_frame)
        perf_actions_layout.setSpacing(4)
        
        self.start_monitor_btn = QPushButton("开始监控")
        # self.start_monitor_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 4px 12px; }")
        
        self.stop_monitor_btn = QPushButton("停止监控")
        # self.stop_monitor_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; padding: 4px 12px; }")
        
        self.clear_stats_btn = QPushButton("清空统计")
        # self.clear_stats_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 4px 12px; }")
        
        perf_actions_layout.addWidget(self.start_monitor_btn)
        perf_actions_layout.addWidget(self.stop_monitor_btn)
        perf_actions_layout.addWidget(self.clear_stats_btn)
        
        layout.addWidget(perf_actions_frame)
        
        return module
    
    def _create_logs_module(self) -> QWidget:
        """创建日志管理模块"""
        module = QGroupBox("日志管理")
        layout = QVBoxLayout(module)
        layout.setSpacing(3)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # 日志控制区域
        log_controls_frame = QFrame()
        log_controls_layout = QHBoxLayout(log_controls_frame)
        log_controls_layout.setSpacing(4)
        
        # 日志级别选择
        log_level_label = QLabel("日志级别:")
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["全部", "调试", "信息", "警告", "错误", "严重"])
        self.log_level_combo.setCurrentText("全部")
        
        # 日志过滤
        filter_label = QLabel("过滤:")
        self.log_filter_edit = QLineEdit()
        self.log_filter_edit.setPlaceholderText("输入关键词过滤日志...")
        
        log_controls_layout.addWidget(log_level_label)
        log_controls_layout.addWidget(self.log_level_combo)
        log_controls_layout.addWidget(filter_label)
        log_controls_layout.addWidget(self.log_filter_edit)
        
        layout.addWidget(log_controls_frame)
        
        # 日志显示区域
        self.log_display = QTextBrowser()
        self.log_display.setMaximumHeight(80)  # 限制高度以适应上下布局
        self.log_display.setStyleSheet("QTextBrowser { color: #ffffff; font-family: 'Consolas', monospace; }")
        
        layout.addWidget(self.log_display)
        
        # 日志操作按钮
        log_actions_frame = QFrame()
        log_actions_layout = QHBoxLayout(log_actions_frame)
        log_actions_layout.setSpacing(4)
        
        self.clear_logs_btn_logs = QPushButton("清空日志")
        # self.clear_logs_btn_logs.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; padding: 4px 12px; }")
        
        self.save_logs_btn = QPushButton("保存日志")
        # self.save_logs_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 4px 12px; }")
        
        self.auto_scroll_checkbox = QCheckBox("自动滚动")
        # 从设置中加载自动滚动状态
        try:
            from core.settings import load_settings
            settings = load_settings()
            auto_scroll_enabled = settings.get('remote_debug.auto_scroll', True)
            self.auto_scroll_checkbox.setChecked(auto_scroll_enabled)
        except Exception as e:
            print(f"加载自动滚动设置失败: {e}")
            self.auto_scroll_checkbox.setChecked(True)  # 默认启用
        self.auto_scroll_checkbox.setStyleSheet("QCheckBox { font-weight: bold; }")
        
        # 创建保存设置按钮
        self.save_settings_btn = QPushButton("保存设置")
        self.save_settings_btn.setFixedSize(80, 25)
        self.save_settings_btn.clicked.connect(self._save_settings_manually)
        
        # 添加查看安全日志按钮
        self.view_security_logs_btn = QPushButton("查看安全日志")
        self.view_security_logs_btn.setFixedSize(100, 25)
        self.view_security_logs_btn.clicked.connect(self._view_security_logs)
        
        # 添加日志管理按钮
        self.log_management_btn = QPushButton("日志管理")
        self.log_management_btn.setFixedSize(80, 25)
        self.log_management_btn.clicked.connect(self._open_log_management)
        
        log_actions_layout.addWidget(self.clear_logs_btn_logs)
        log_actions_layout.addWidget(self.save_logs_btn)
        log_actions_layout.addWidget(self.view_security_logs_btn)
        log_actions_layout.addWidget(self.log_management_btn)
        log_actions_layout.addWidget(self.auto_scroll_checkbox)
        log_actions_layout.addWidget(self.save_settings_btn)
        
        layout.addWidget(log_actions_frame)
        
        return module
    
    def _create_footer_widget(self) -> QWidget:
        """创建底部状态栏"""
        footer_frame = QFrame()
        footer_frame.setFixedHeight(18)
        
        layout = QHBoxLayout(footer_frame)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(3)
        
        # 状态信息
        self.client_count_label = QLabel("客户端: 0")
        self.uptime_label = QLabel("运行: 00:00:00")
        self.memory_label = QLabel("内存: 0MB")
        
        layout.addWidget(self.client_count_label)
        layout.addWidget(self.uptime_label)
        layout.addWidget(self.memory_label)
        
        # 版本信息
        version_label = QLabel("v2.1.7")
        layout.addWidget(version_label)
        
        return footer_frame
    
    def _create_dashboard_tab(self) -> QWidget:
        """创建仪表板选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 状态信息
        stats_group = QGroupBox("状态")
        stats_layout = QGridLayout(stats_group)
        stats_layout.setSpacing(2)
        
        # 状态标签
        self.server_status_label = QLabel("服务器: 已停止")
        self.client_count_label_dash = QLabel("客户端: 0")
        self.message_rate_label = QLabel("消息: 0/分钟")
        self.system_load_label = QLabel("负载: 0%")
        
        stats_layout.addWidget(self.server_status_label, 0, 0)
        stats_layout.addWidget(self.client_count_label_dash, 0, 1)
        stats_layout.addWidget(self.message_rate_label, 1, 0)
        stats_layout.addWidget(self.system_load_label, 1, 1)
        
        layout.addWidget(stats_group)
        
        # 操作按钮
        actions_group = QGroupBox("操作")
        actions_layout = QGridLayout(actions_group)
        actions_layout.setSpacing(2)
        
        restart_btn = QPushButton("重启")
        clear_logs_btn = QPushButton("清空日志")
        export_config_btn = QPushButton("导出配置")
        import_config_btn = QPushButton("导入配置")
        
        actions_layout.addWidget(restart_btn, 0, 0)
        actions_layout.addWidget(clear_logs_btn, 0, 1)
        actions_layout.addWidget(export_config_btn, 1, 0)
        actions_layout.addWidget(import_config_btn, 1, 1)
        
        layout.addWidget(actions_group)
        layout.addStretch()
        
        return widget
    

    
    def _create_config_tab(self) -> QWidget:
        """创建服务器配置选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 基础配置
        config_group = QGroupBox("配置")
        form_layout = QGridLayout(config_group)
        form_layout.setSpacing(2)
        
        # 主机地址
        form_layout.addWidget(QLabel("主机:"), 0, 0)
        self.host_edit = QLineEdit("127.0.0.1")
        form_layout.addWidget(self.host_edit, 0, 1)
        
        # 端口
        form_layout.addWidget(QLabel("端口:"), 0, 2)
        self.port_edit = QSpinBox()
        self.port_edit.setRange(1000, 65535)
        self.port_edit.setValue(9009)
        form_layout.addWidget(self.port_edit, 0, 3)
        
        # 密码
        form_layout.addWidget(QLabel("密码:"), 1, 0)
        self.password_edit = QLineEdit("")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("请设置强密码")
        form_layout.addWidget(self.password_edit, 1, 1)
        
        # 最大客户端
        form_layout.addWidget(QLabel("最大客户端:"), 1, 2)
        self.max_clients_spin = QSpinBox()
        self.max_clients_spin.setRange(1, 100)
        self.max_clients_spin.setValue(10)
        form_layout.addWidget(self.max_clients_spin, 1, 3)
        
        layout.addWidget(config_group)
        
        # 功能开关
        features_group = QGroupBox("选项")
        features_layout = QVBoxLayout(features_group)
        features_layout.setSpacing(2)
        
        # 注意：不重复创建auth_check，使用已存在的复选框
        # self.auth_check = QCheckBox("启用身份验证")  # 注释掉重复创建
        self.ssl_check_tab = QCheckBox("启用SSL加密")
        self.auto_start_check_tab = QCheckBox("自动启动")
        
        # features_layout.addWidget(self.auth_check)  # 注释掉重复添加
        features_layout.addWidget(self.ssl_check_tab)
        features_layout.addWidget(self.auto_start_check_tab)
        
        layout.addWidget(features_group)
        
        # 应用配置按钮
        apply_btn = QPushButton("应用配置")
        layout.addWidget(apply_btn)
        
        layout.addStretch()
        return widget
    
    def _create_clients_tab(self) -> QWidget:
        """创建客户端管理选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 客户端列表
        clients_group = QGroupBox("客户端")
        clients_layout = QVBoxLayout(clients_group)
        clients_layout.setSpacing(2)
        
        # 客户端表格
        self.client_table = QTableWidget()
        self.client_table.setColumnCount(6)
        self.client_table.setHorizontalHeaderLabels(["ID", "IP", "连接时间", "状态", "消息数", "操作"])
        self.client_table.horizontalHeader().setStretchLastSection(True)
        self.client_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        clients_layout.addWidget(self.client_table)
        
        # 客户端操作按钮
        client_actions = QHBoxLayout()
        client_actions.setSpacing(2)
        
        refresh_clients_btn = QPushButton("刷新")
        disconnect_client_btn = QPushButton("断开")
        broadcast_btn = QPushButton("广播")
        
        client_actions.addWidget(refresh_clients_btn)
        client_actions.addWidget(disconnect_client_btn)
        client_actions.addWidget(broadcast_btn)
        client_actions.addStretch()
        
        clients_layout.addLayout(client_actions)
        
        layout.addWidget(clients_group)
        layout.addStretch()
        
        return widget
    
    def _create_performance_tab(self) -> QWidget:
        """创建性能监控选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 性能指标
        metrics_group = QGroupBox("性能")
        metrics_layout = QGridLayout(metrics_group)
        metrics_layout.setSpacing(2)
        
        # 性能标签
        self.cpu_label = QLabel("CPU: 0%")
        self.memory_label_perf = QLabel("内存: 0MB")
        self.network_label = QLabel("网络: 0KB/s")
        
        metrics_layout.addWidget(self.cpu_label, 0, 0)
        metrics_layout.addWidget(self.memory_label_perf, 0, 1)
        metrics_layout.addWidget(self.network_label, 1, 0)
        
        layout.addWidget(metrics_group)
        
        # 性能数据
        data_group = QGroupBox("数据")
        data_layout = QVBoxLayout(data_group)
        data_layout.setSpacing(2)
        
        self.performance_display = QTextBrowser()
        self.performance_display.setMaximumHeight(150)
        data_layout.addWidget(self.performance_display)
        
        layout.addWidget(data_group)
        layout.addStretch()
        
        return widget
    
    def _create_advanced_tab(self) -> QWidget:
        """创建高级功能选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 高级功能选项卡
        advanced_tabs = QTabWidget()
        
        # 插件管理
        plugin_widget = self._create_plugin_management_widget()
        advanced_tabs.addTab(plugin_widget, "插件")
        
        # 脚本执行
        script_widget = self._create_script_execution_widget()
        advanced_tabs.addTab(script_widget, "脚本")
        
        # 会话管理
        session_widget = self._create_session_management_widget()
        advanced_tabs.addTab(session_widget, "会话")
        
        layout.addWidget(advanced_tabs)
        
        return widget
    
    def _create_logs_tab(self) -> QWidget:
        """创建系统日志选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 日志控制区域
        log_controls = QGroupBox("系统日志")
        
        controls_layout = QHBoxLayout(log_controls)
        controls_layout.setSpacing(4)
        
        # 日志级别过滤
        level_label = QLabel("日志级别:")
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["全部", "调试", "信息", "警告", "错误"])
        
        # 日志操作按钮
        clear_log_btn = QPushButton("清空")
        export_log_btn = QPushButton("导出")
        auto_scroll_btn = QPushButton("自动滚动")
        auto_scroll_btn.setCheckable(True)
        auto_scroll_btn.setChecked(True)
        
        controls_layout.addWidget(level_label)
        controls_layout.addWidget(self.log_level_combo)
        controls_layout.addStretch()
        controls_layout.addWidget(clear_log_btn)
        controls_layout.addWidget(export_log_btn)
        controls_layout.addWidget(auto_scroll_btn)
        
        layout.addWidget(log_controls)
        
        # 日志显示区域
        log_frame = QGroupBox("日志输出")
        
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(4, 4, 4, 4)
        
        # 使用已经在__init__中创建的log_widget实例
        # AsyncLogWidget是一个QVBoxLayout，需要创建一个容器widget
        log_container = QWidget()
        log_container.setLayout(self.log_widget)
        log_layout.addWidget(log_container)
        
        # 添加测试日志以验证日志显示功能
        self.add_log_async("INFO", "日志系统已初始化完成")
        
        layout.addWidget(log_frame, 1)
        
        return widget
    
    def _create_plugin_management_widget(self) -> QWidget:
        """创建插件管理组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 插件列表
        self.plugin_list = QListWidget()
        
        layout.addWidget(self.plugin_list)
        
        # 插件操作按钮
        plugin_actions = QHBoxLayout()
        plugin_actions.setSpacing(4)
        
        scan_btn = QPushButton("扫描插件")
        load_btn = QPushButton("加载插件")
        unload_btn = QPushButton("卸载插件")
        
        for btn in [scan_btn, load_btn, unload_btn]:
            plugin_actions.addWidget(btn)
        
        plugin_actions.addStretch()
        layout.addLayout(plugin_actions)
        
        return widget
    
    def _create_script_execution_widget(self) -> QWidget:
        """创建脚本执行组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 脚本输入区域
        self.script_edit = QPlainTextEdit()
        self.script_edit.setPlaceholderText("在此输入Python脚本...")
        self.script_edit.setMaximumHeight(150)
        
        layout.addWidget(self.script_edit)
        
        # 执行按钮
        execute_btn = QPushButton("执行脚本")
        
        layout.addWidget(execute_btn)
        
        # 执行结果
        self.script_result = QTextBrowser()
        
        layout.addWidget(self.script_result)
        
        return widget
    
    def _create_session_management_widget(self) -> QWidget:
        """创建会话管理组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 会话列表
        self.session_list = QListWidget()
        
        layout.addWidget(self.session_list)
        
        # 会话操作按钮
        session_actions = QHBoxLayout()
        session_actions.setSpacing(4)
        
        create_btn = QPushButton("创建会话")
        switch_btn = QPushButton("切换会话")
        delete_btn = QPushButton("删除会话")
        
        for btn in [create_btn, switch_btn, delete_btn]:
            session_actions.addWidget(btn)
        
        session_actions.addStretch()
        layout.addLayout(session_actions)
        
        return widget
        
    def _create_compact_config_widget(self) -> QWidget:
        """创建紧凑的配置组件"""
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 基础配置
        layout.addWidget(QLabel("主机:"), 0, 0)
        self.host_edit = QLineEdit("127.0.0.1")
        self.host_edit.setFixedWidth(100)
        layout.addWidget(self.host_edit, 0, 1)
        
        layout.addWidget(QLabel("端口:"), 0, 2)
        self.port_edit = QSpinBox()
        self.port_edit.setRange(1000, 65535)
        self.port_edit.setValue(9009)
        self.port_edit.setFixedWidth(80)
        layout.addWidget(self.port_edit, 0, 3)
        
        layout.addWidget(QLabel("密码:"), 1, 0)
        self.password_edit = QLineEdit("")
        self.password_edit.setFixedWidth(100)
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("请设置强密码")
        layout.addWidget(self.password_edit, 1, 1)
        
        layout.addWidget(QLabel("最大客户端:"), 1, 2)
        self.max_clients_spin = QSpinBox()
        self.max_clients_spin.setRange(1, 100)
        self.max_clients_spin.setValue(10)
        self.max_clients_spin.setFixedWidth(60)
        layout.addWidget(self.max_clients_spin, 1, 3)
        
        # 高级配置（第二行）
        layout.addWidget(QLabel("连接池:"), 2, 0)
        self.pool_size_edit = QSpinBox()
        self.pool_size_edit.setRange(10, 200)
        self.pool_size_edit.setValue(50)
        self.pool_size_edit.setFixedWidth(60)
        layout.addWidget(self.pool_size_edit, 2, 1)
        
        layout.addWidget(QLabel("缓冲区:"), 2, 2)
        self.buffer_size_edit = QSpinBox()
        self.buffer_size_edit.setRange(50, 500)
        self.buffer_size_edit.setValue(100)
        self.buffer_size_edit.setFixedWidth(60)
        layout.addWidget(self.buffer_size_edit, 2, 3)
        
        layout.addWidget(QLabel("线程池:"), 3, 0)
        self.thread_pool_edit = QSpinBox()
        self.thread_pool_edit.setRange(2, 20)
        self.thread_pool_edit.setValue(5)
        self.thread_pool_edit.setFixedWidth(60)
        layout.addWidget(self.thread_pool_edit, 3, 1)
        
        # 应用配置按钮
        apply_btn = QPushButton("应用")
        apply_btn.setFixedSize(50, 24)
        apply_btn.clicked.connect(self._apply_config)
        layout.addWidget(apply_btn, 3, 3)
        
        layout.setColumnStretch(4, 1)
        return widget
        
    def _create_compact_client_widget(self) -> QWidget:
        """创建紧凑的客户端组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 客户端统计
        stats_layout = QHBoxLayout()
        self.client_count_label = QLabel("客户端: 0")
        self.client_count_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        stats_layout.addWidget(self.client_count_label)
        stats_layout.addStretch()
        
        # 快速操作按钮
        disconnect_btn = QPushButton("断开所有")
        disconnect_btn.setFixedSize(60, 24)
        disconnect_btn.clicked.connect(self._disconnect_all_clients)
        stats_layout.addWidget(disconnect_btn)
        
        layout.addLayout(stats_layout)
        
        # 简化的客户端表格
        self.client_table = QTableView()
        self.client_model = ClientTableModel()
        self.client_table.setModel(self.client_model)
        self.client_table.setMaximumHeight(120)
        self.client_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        # 设置表格列宽
        header = self.client_table.horizontalHeader()
        header.setStretchLastSection(True)
        
        layout.addWidget(self.client_table)
        
        return widget
        
    def _create_compact_performance_widget(self) -> QWidget:
        """创建紧凑的性能监控组件"""
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 性能指标
        self.cpu_label = QLabel("CPU: 0%")
        self.memory_label = QLabel("内存: 0MB")
        self.connections_label = QLabel("连接: 0")
        self.messages_label = QLabel("消息: 0")
        
        layout.addWidget(self.cpu_label, 0, 0)
        layout.addWidget(self.memory_label, 0, 1)
        layout.addWidget(self.connections_label, 1, 0)
        layout.addWidget(self.messages_label, 1, 1)
        
        return widget
        
    def _create_advanced_widget(self) -> QWidget:
        """创建高级功能组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 功能选项卡
        tabs = QTabWidget()
        
        # 功能配置选项卡
        tabs.addTab(self.feature_config, "功能开关")
        
        # 插件管理
        plugin_widget = self._create_simple_plugin_widget()
        tabs.addTab(plugin_widget, "插件")
        
        # 脚本执行
        script_widget = self._create_simple_script_widget()
        tabs.addTab(script_widget, "脚本")
        
        # 会话管理
        session_widget = self._create_simple_session_widget()
        tabs.addTab(session_widget, "会话")
        
        layout.addWidget(tabs)
        return widget
        
    def _create_simple_plugin_widget(self) -> QWidget:
        """创建简化的插件组件"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        
        self.plugin_list = QListWidget()
        self.plugin_list.setMaximumHeight(100)
        layout.addWidget(self.plugin_list)
        
        # 插件操作按钮
        btn_layout = QVBoxLayout()
        scan_btn = QPushButton("扫描")
        scan_btn.setFixedSize(50, 24)
        scan_btn.clicked.connect(self._scan_plugins)
        btn_layout.addWidget(scan_btn)
        
        load_btn = QPushButton("加载")
        load_btn.setFixedSize(50, 24)
        load_btn.clicked.connect(self._load_selected_plugin)
        btn_layout.addWidget(load_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return widget
        
    def _create_simple_script_widget(self) -> QWidget:
        """创建简化的脚本组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # 脚本输入
        script_layout = QHBoxLayout()
        self.script_edit = QLineEdit()
        self.script_edit.setPlaceholderText("输入Python脚本...")
        script_layout.addWidget(self.script_edit)
        
        exec_btn = QPushButton("执行")
        exec_btn.setFixedSize(50, 24)
        exec_btn.clicked.connect(self._execute_simple_script)
        script_layout.addWidget(exec_btn)
        
        layout.addLayout(script_layout)
        
        # 结果显示
        self.script_result = QTextEdit()
        self.script_result.setMaximumHeight(60)
        self.script_result.setPlaceholderText("脚本执行结果...")
        layout.addWidget(self.script_result)
        
        return widget
        
    def _create_simple_session_widget(self) -> QWidget:
        """创建简化的会话组件"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # 会话列表
        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(120)
        layout.addWidget(QLabel("会话:"))
        layout.addWidget(self.session_combo)
        
        # 会话操作
        create_btn = QPushButton("新建")
        create_btn.setFixedSize(40, 24)
        create_btn.clicked.connect(self._create_session)
        layout.addWidget(create_btn)
        
        switch_btn = QPushButton("切换")
        switch_btn.setFixedSize(40, 24)
        switch_btn.clicked.connect(self._switch_session)
        layout.addWidget(switch_btn)
        
        layout.addStretch()
        return widget
        
    def _disconnect_all_clients(self):
        """断开所有客户端"""
        if self.server:
            clients = self.server.get_all_clients()
            for client in clients:
                self.server.disconnect_client(client.client_id)
            self.add_log_async("INFO", f"已断开 {len(clients)} 个客户端")
            
    def _execute_simple_script(self):
        """执行简单脚本"""
        script = self.script_edit.text().strip()
        if not script:
            return
            
        try:
            # 优先使用服务器的脚本执行器，如果不存在则使用独立的脚本执行器
            script_executor = None
            if self.server and hasattr(self.server, 'script_executor') and self.server.script_executor:
                script_executor = self.server.script_executor
            elif hasattr(self, 'standalone_script_executor') and self.standalone_script_executor:
                script_executor = self.standalone_script_executor
                
            if script_executor:
                result = script_executor.execute_script(script)
                self.script_result.setText(str(result.get('result', '')))
            else:
                # 简单的本地执行
                result = eval(script)
                self.script_result.setText(str(result))
        except Exception as e:
            self.script_result.setText(f"错误: {str(e)}")
            
    def _create_config_widget(self) -> QWidget:
        """创建配置组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 基础配置
        basic_group = QGroupBox("基础配置")
        basic_layout = QGridLayout(basic_group)
        
        self.host_edit = QLineEdit(self.config.host)
        self.port_edit = QSpinBox()
        self.port_edit.setRange(1, 65535)
        self.port_edit.setValue(self.config.port)
        
        self.password_edit = QLineEdit(self.config.password)
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.max_clients_spin = QSpinBox()
        self.max_clients_spin.setRange(1, 1000)
        self.max_clients_spin.setValue(self.config.max_clients)
        
        basic_layout.addWidget(QLabel("主机:"), 0, 0)
        basic_layout.addWidget(self.host_edit, 0, 1)
        basic_layout.addWidget(QLabel("端口:"), 1, 0)
        basic_layout.addWidget(self.port_edit, 1, 1)
        basic_layout.addWidget(QLabel("密码:"), 2, 0)
        basic_layout.addWidget(self.password_edit, 2, 1)
        basic_layout.addWidget(QLabel("最大客户端:"), 3, 0)
        basic_layout.addWidget(self.max_clients_spin, 3, 1)
        
        layout.addWidget(basic_group)
        
        # 性能配置
        perf_group = QGroupBox("性能配置")
        perf_layout = QGridLayout(perf_group)
        
        self.pool_size_edit = QSpinBox()
        self.pool_size_edit.setRange(10, 1000)
        self.pool_size_edit.setValue(self.config.connection_pool_size)
        
        self.buffer_size_edit = QSpinBox()
        self.buffer_size_edit.setRange(10, 1000)
        self.buffer_size_edit.setValue(self.config.message_buffer_size)
        
        self.thread_pool_edit = QSpinBox()
        self.thread_pool_edit.setRange(1, 20)
        self.thread_pool_edit.setValue(self.config.thread_pool_size)
        
        perf_layout.addWidget(QLabel("连接池大小:"), 0, 0)
        perf_layout.addWidget(self.pool_size_edit, 0, 1)
        perf_layout.addWidget(QLabel("消息缓冲区:"), 1, 0)
        perf_layout.addWidget(self.buffer_size_edit, 1, 1)
        perf_layout.addWidget(QLabel("线程池大小:"), 2, 0)
        perf_layout.addWidget(self.thread_pool_edit, 2, 1)
        
        layout.addWidget(perf_group)
        
        # 应用配置按钮
        apply_button = QPushButton("应用配置")
        apply_button.clicked.connect(self._apply_config)
        layout.addWidget(apply_button)
        
        layout.addStretch()
        return widget
        
    def _create_plugin_widget(self) -> QWidget:
        """创建插件管理组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 插件列表
        self.plugin_list = QTreeWidget()
        self.plugin_list.setHeaderLabels(["插件名称", "版本", "状态", "描述"])
        layout.addWidget(self.plugin_list)
        
        # 插件操作按钮
        button_layout = QHBoxLayout()
        
        scan_button = QPushButton("扫描插件")
        scan_button.clicked.connect(self._scan_plugins)
        
        load_button = QPushButton("加载插件")
        load_button.clicked.connect(self._load_selected_plugin)
        
        unload_button = QPushButton("卸载插件")
        unload_button.clicked.connect(self._unload_selected_plugin)
        
        button_layout.addWidget(scan_button)
        button_layout.addWidget(load_button)
        button_layout.addWidget(unload_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        return widget
        
    def _create_script_widget(self) -> QWidget:
        """创建脚本执行组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 脚本编辑器
        self.script_editor = QPlainTextEdit()
        self.script_editor.setPlainText("# Python脚本\nprint('Hello, Remote Debug!')\nresult = 'Script executed successfully'")
        layout.addWidget(QLabel("脚本内容:"))
        layout.addWidget(self.script_editor)
        
        # 执行按钮
        execute_button = QPushButton("执行脚本")
        execute_button.clicked.connect(self._execute_script)
        layout.addWidget(execute_button)
        
        # 执行结果
        self.script_result = QTextBrowser()
        layout.addWidget(QLabel("执行结果:"))
        layout.addWidget(self.script_result)
        
        return widget
        
    def _create_client_widget(self) -> QWidget:
        """创建客户端管理组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 客户端表格
        self.client_table = QTableView()
        self.client_table.setModel(self.client_model)
        self.client_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.client_table.setAlternatingRowColors(True)
        
        # 设置列宽
        header = self.client_table.horizontalHeader()
        header.setStretchLastSection(True)
        for i in range(self.client_model.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
            
        layout.addWidget(self.client_table)
        
        # 客户端操作按钮
        button_layout = QHBoxLayout()
        
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self._refresh_clients)
        
        disconnect_button = QPushButton("断开连接")
        disconnect_button.clicked.connect(self._disconnect_selected_client)
        
        broadcast_button = QPushButton("广播消息")
        broadcast_button.clicked.connect(self._broadcast_message)
        
        button_layout.addWidget(refresh_button)
        button_layout.addWidget(disconnect_button)
        button_layout.addWidget(broadcast_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        return widget
        
    def _create_performance_widget(self) -> QWidget:
        """创建性能监控组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 性能统计显示
        stats_group = QGroupBox("实时统计")
        stats_layout = QGridLayout(stats_group)
        
        self.stats_labels = {
            "active_connections": QLabel("0"),
            "total_connections": QLabel("0"),
            "messages_processed": QLabel("0"),
            "errors": QLabel("0"),
            "uptime": QLabel("0"),
            "memory_usage": QLabel("0 MB"),
            "cpu_usage": QLabel("0%")
        }
        
        stats_layout.addWidget(QLabel("活跃连接:"), 0, 0)
        stats_layout.addWidget(self.stats_labels["active_connections"], 0, 1)
        stats_layout.addWidget(QLabel("总连接数:"), 1, 0)
        stats_layout.addWidget(self.stats_labels["total_connections"], 1, 1)
        stats_layout.addWidget(QLabel("处理消息:"), 2, 0)
        stats_layout.addWidget(self.stats_labels["messages_processed"], 2, 1)
        stats_layout.addWidget(QLabel("错误数:"), 3, 0)
        stats_layout.addWidget(self.stats_labels["errors"], 3, 1)
        stats_layout.addWidget(QLabel("运行时间:"), 0, 2)
        stats_layout.addWidget(self.stats_labels["uptime"], 0, 3)
        stats_layout.addWidget(QLabel("内存使用:"), 1, 2)
        stats_layout.addWidget(self.stats_labels["memory_usage"], 1, 3)
        stats_layout.addWidget(QLabel("CPU使用:"), 2, 2)
        stats_layout.addWidget(self.stats_labels["cpu_usage"], 2, 3)
        
        layout.addWidget(stats_group)
        
        # 性能图表（简化版）
        chart_group = QGroupBox("性能趋势")
        chart_layout = QVBoxLayout(chart_group)
        
        self.performance_text = QTextBrowser()
        self.performance_text.setMaximumHeight(200)
        chart_layout.addWidget(self.performance_text)
        
        layout.addWidget(chart_group)
        layout.addStretch()
        
        return widget
        
    def _create_session_widget(self) -> QWidget:
        """创建会话管理组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 会话列表
        self.session_list = QListWidget()
        layout.addWidget(QLabel("会话列表:"))
        layout.addWidget(self.session_list)
        
        # 会话操作按钮
        button_layout = QHBoxLayout()
        
        create_button = QPushButton("创建会话")
        create_button.clicked.connect(self._create_session)
        
        switch_button = QPushButton("切换会话")
        switch_button.clicked.connect(self._switch_session)
        
        delete_button = QPushButton("删除会话")
        delete_button.clicked.connect(self._delete_session)
        
        button_layout.addWidget(create_button)
        button_layout.addWidget(switch_button)
        button_layout.addWidget(delete_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 会话详情
        self.session_details = QTextBrowser()
        layout.addWidget(QLabel("会话详情:"))
        layout.addWidget(self.session_details)
        
        return widget
        
    def _connect_signals(self):
        """连接信号"""
        self.start_button.clicked.connect(self._start_server)
        self.stop_button.clicked.connect(self._stop_server)
        self.feature_config.feature_changed.connect(self._on_feature_changed)
        self.feature_config.features_applied.connect(self._on_features_applied)
        self.performance_monitor.stats_updated.connect(self._update_performance_display)
        
        # 连接其他按钮事件（需要在按钮创建后调用）
        self._connect_button_signals()
        
        # 连接控件状态变化监听
        self._connect_control_state_monitoring()
        
    def _connect_button_signals(self):
        """连接按钮信号"""
        # 控制模块按钮
        if hasattr(self, 'restart_btn'):
            self.restart_btn.clicked.connect(self._restart_server)
        if hasattr(self, 'clear_logs_btn'):
            self.clear_logs_btn.clicked.connect(self._clear_logs)
        if hasattr(self, 'export_config_btn'):
            self.export_config_btn.clicked.connect(self._export_config)
        if hasattr(self, 'import_config_btn'):
            self.import_config_btn.clicked.connect(self._import_config)
            
        # 配置模块按钮
        if hasattr(self, 'apply_btn'):
            self.apply_btn.clicked.connect(self._apply_config)
        if hasattr(self, 'save_config_btn'):
            self.save_config_btn.clicked.connect(self._save_config_with_message)
            
        # 客户端管理按钮
        if hasattr(self, 'refresh_clients_btn'):
            self.refresh_clients_btn.clicked.connect(self._refresh_clients)
        if hasattr(self, 'disconnect_client_btn'):
            self.disconnect_client_btn.clicked.connect(self._disconnect_selected_client)
        if hasattr(self, 'disconnect_all_btn'):
            self.disconnect_all_btn.clicked.connect(self._disconnect_all_clients)
        if hasattr(self, 'broadcast_btn'):
            self.broadcast_btn.clicked.connect(self._broadcast_message)
            
        # 性能监控按钮
        if hasattr(self, 'start_monitor_btn'):
            self.start_monitor_btn.clicked.connect(self._start_performance_monitor)
        if hasattr(self, 'stop_monitor_btn'):
            self.stop_monitor_btn.clicked.connect(self._stop_performance_monitor)
        if hasattr(self, 'clear_stats_btn'):
            self.clear_stats_btn.clicked.connect(self._clear_performance_stats)
            
        # 日志管理按钮
        if hasattr(self, 'clear_logs_btn_logs'):
            self.clear_logs_btn_logs.clicked.connect(self._clear_logs)
        if hasattr(self, 'save_logs_btn'):
            self.save_logs_btn.clicked.connect(self._save_logs)
        if hasattr(self, 'log_management_btn'):
            self.log_management_btn.clicked.connect(self._open_log_management)
            
        # 日志过滤功能
        if hasattr(self, 'log_filter_edit'):
            self.log_filter_edit.textChanged.connect(self._filter_logs)
        if hasattr(self, 'log_level_combo'):
            self.log_level_combo.currentTextChanged.connect(self._filter_logs)
            
        # 自动滚动复选框
        if hasattr(self, 'auto_scroll_checkbox'):
            self.auto_scroll_checkbox.toggled.connect(self._on_auto_scroll_toggled)
            # 立即同步复选框状态到AsyncLogWidget
            self._on_auto_scroll_toggled(self.auto_scroll_checkbox.isChecked())
            
        # Token管理按钮
        if hasattr(self, 'copy_token_btn'):
            self.copy_token_btn.clicked.connect(self._copy_auth_token)
        if hasattr(self, 'regenerate_token_btn'):
            self.regenerate_token_btn.clicked.connect(self._regenerate_auth_token)
        if hasattr(self, 'show_token_info_btn'):
            self.show_token_info_btn.clicked.connect(self._show_token_info)
            
        # 帮助和测试按钮
        if hasattr(self, 'help_button'):
            self.help_button.clicked.connect(self._show_help_dialog)
        if hasattr(self, 'test_client_btn'):
            self.test_client_btn.clicked.connect(self._test_client_connection)
        if hasattr(self, 'advanced_test_btn'):
            self.advanced_test_btn.clicked.connect(self._open_advanced_test_client)
            
        # 身份验证选项变化事件
        if hasattr(self, 'auth_check'):
            self.auth_check.toggled.connect(self._on_auth_option_changed)

        
    def _connect_control_state_monitoring(self):
        """连接控件状态变化监听，实现自动日志记录"""
        try:
            # 监听配置相关控件变化
            if hasattr(self, 'host_edit'):
                self.host_edit.textChanged.connect(lambda: self._log_control_change('服务器配置', '主机地址', self.host_edit.text()))
            if hasattr(self, 'port_edit'):
                self.port_edit.textChanged.connect(lambda: self._log_control_change('服务器配置', '端口', self.port_edit.text()))
            if hasattr(self, 'password_edit'):
                self.password_edit.textChanged.connect(lambda: self._log_control_change('服务器配置', '密码', '***已修改***'))
            if hasattr(self, 'max_clients_edit'):
                self.max_clients_edit.textChanged.connect(lambda: self._log_control_change('服务器配置', '最大客户端数', self.max_clients_edit.text()))
            
            # 监听功能选项变化
            if hasattr(self, 'enable_auth_checkbox'):
                self.enable_auth_checkbox.toggled.connect(lambda checked: self._log_control_change('功能选项', '启用身份验证', '是' if checked else '否'))
            if hasattr(self, 'enable_ssl_checkbox'):
                self.enable_ssl_checkbox.toggled.connect(lambda checked: self._log_control_change('功能选项', 'SSL加密', '是' if checked else '否'))
            if hasattr(self, 'auto_start_checkbox'):
                self.auto_start_checkbox.toggled.connect(lambda checked: self._log_control_change('功能选项', '自动启动', '是' if checked else '否'))
            
            # 监听Web界面配置变化
            if hasattr(self, 'web_port_edit'):
                self.web_port_edit.textChanged.connect(lambda: self._log_control_change('Web配置', 'Web端口', self.web_port_edit.text()))
            if hasattr(self, 'websocket_port_edit'):
                self.websocket_port_edit.textChanged.connect(lambda: self._log_control_change('Web配置', 'WebSocket端口', self.websocket_port_edit.text()))
            
            # 监听日志级别变化
            if hasattr(self, 'log_level_combo'):
                self.log_level_combo.currentTextChanged.connect(lambda text: self._log_control_change('日志配置', '日志级别', text))
            
            # 监听性能监控控件变化
            if hasattr(self, 'performance_monitor') and hasattr(self.performance_monitor, 'monitoring_enabled'):
                # 如果性能监控有状态变化信号，连接它
                pass
            
            # 定期记录控件状态快照
            self.control_state_timer = QTimer()
            self.control_state_timer.timeout.connect(self._log_periodic_control_state)
            self.control_state_timer.start(30000)  # 每30秒记录一次状态快照
            
        except Exception as e:
            if hasattr(self, 'log_widget'):
                self.add_log_async("ERROR", f"控件状态监听初始化失败: {str(e)}")
    
    def _log_control_change(self, module: str, control: str, value: str):
        """记录控件变化日志（带重试机制）"""
        self._safe_log_control_change(module, control, value)
    
    def _safe_log_control_change(self, module: str, control: str, value: str, retry_count: int = 0):
        """安全的控件变化日志记录（带重试和错误恢复）"""
        max_retries = 3
        try:
            # 记录到服务器日志
            if hasattr(self, 'server') and self.server:
                self.server._log_control_panel_state(f"控件变化 - {module}.{control}: {value}")
            
            # 记录到UI日志
            if hasattr(self, 'log_widget'):
                self.add_log_async("INFO", f"[控件变化] {module}.{control} = {value}")
                
            # 重置错误计数器
            if hasattr(self, '_control_monitoring_errors'):
                self._control_monitoring_errors = 0
                
        except Exception as e:
            # 增加错误计数
            if not hasattr(self, '_control_monitoring_errors'):
                self._control_monitoring_errors = 0
            self._control_monitoring_errors += 1
            
            # 记录错误
            error_msg = f"记录控件变化失败 ({module}.{control}): {str(e)}"
            
            # 重试机制
            if retry_count < max_retries:
                QTimer.singleShot(1000 * (retry_count + 1), 
                    lambda: self._safe_log_control_change(module, control, value, retry_count + 1))
                error_msg += f" (将在{retry_count + 1}秒后重试)"
            
            # 尝试记录错误到日志
            try:
                if hasattr(self, 'log_widget'):
                    self.add_log_async("ERROR", error_msg)
            except:
                # 如果连错误日志都无法记录，则输出到控制台
                print(f"[控件监控] {error_msg}")
            
            # 如果错误过多，暂时禁用监控
            if hasattr(self, '_control_monitoring_errors') and self._control_monitoring_errors > 10:
                self._temporarily_disable_monitoring()
    
    def _log_periodic_control_state(self):
        """定期记录控件状态快照（带错误恢复）"""
        # 检查监控是否被暂时禁用
        if hasattr(self, '_monitoring_disabled') and self._monitoring_disabled:
            return
            
        try:
            if hasattr(self, 'server') and self.server:
                self.server._log_control_panel_state("系统监控", "定期状态快照")
            
            # 重置错误计数器
            if hasattr(self, '_periodic_monitoring_errors'):
                self._periodic_monitoring_errors = 0
                
        except Exception as e:
            # 增加错误计数
            if not hasattr(self, '_periodic_monitoring_errors'):
                self._periodic_monitoring_errors = 0
            self._periodic_monitoring_errors += 1
            
            error_msg = f"记录定期状态快照失败: {str(e)}"
            
            # 尝试记录错误
            try:
                if hasattr(self, 'log_widget'):
                    self.add_log_async("ERROR", error_msg)
            except:
                print(f"[控件监控] {error_msg}")
            
            # 如果连续失败过多，暂时禁用定期监控
            if self._periodic_monitoring_errors > 5:
                self._temporarily_disable_periodic_monitoring()
    
    def _temporarily_disable_monitoring(self):
        """暂时禁用控件监控"""
        try:
            self._monitoring_disabled = True
            
            # 停止定时器
            if hasattr(self, 'control_state_timer') and self.control_state_timer:
                self.control_state_timer.stop()
            
            # 记录禁用信息
            if hasattr(self, 'log_widget'):
                self.add_log_async("WARNING", "控件监控因错误过多已暂时禁用，将在5分钟后尝试恢复")
            
            # 设置恢复定时器
            if not hasattr(self, 'monitoring_recovery_timer'):
                self.monitoring_recovery_timer = QTimer()
                self.monitoring_recovery_timer.timeout.connect(self._try_recover_monitoring)
            
            self.monitoring_recovery_timer.start(300000)  # 5分钟后尝试恢复
            
        except Exception as e:
            print(f"[控件监控] 禁用监控失败: {str(e)}")
    
    def _temporarily_disable_periodic_monitoring(self):
        """暂时禁用定期监控"""
        try:
            if hasattr(self, 'control_state_timer') and self.control_state_timer:
                self.control_state_timer.stop()
            
            if hasattr(self, 'log_widget'):
                self.add_log_async("WARNING", "定期状态监控因错误过多已暂时禁用，将在10分钟后尝试恢复")
            
            # 设置恢复定时器
            if not hasattr(self, 'periodic_recovery_timer'):
                self.periodic_recovery_timer = QTimer()
                self.periodic_recovery_timer.timeout.connect(self._try_recover_periodic_monitoring)
            
            self.periodic_recovery_timer.start(600000)  # 10分钟后尝试恢复
            
        except Exception as e:
            print(f"[控件监控] 禁用定期监控失败: {str(e)}")
    
    def _try_recover_monitoring(self):
        """尝试恢复控件监控"""
        try:
            # 重置错误计数器
            self._control_monitoring_errors = 0
            self._monitoring_disabled = False
            
            # 重新启动定时器
            if hasattr(self, 'control_state_timer'):
                self.control_state_timer.start(30000)
            
            # 停止恢复定时器
            if hasattr(self, 'monitoring_recovery_timer'):
                self.monitoring_recovery_timer.stop()
            
            if hasattr(self, 'log_widget'):
                self.add_log_async("INFO", "控件监控已恢复")
                
        except Exception as e:
            print(f"[控件监控] 恢复监控失败: {str(e)}")
            # 如果恢复失败，再次尝试（延长时间）
            if hasattr(self, 'monitoring_recovery_timer'):
                self.monitoring_recovery_timer.start(600000)  # 10分钟后再试
    
    def _try_recover_periodic_monitoring(self):
        """尝试恢复定期监控"""
        try:
            # 重置错误计数器
            self._periodic_monitoring_errors = 0
            
            # 重新启动定时器
            if hasattr(self, 'control_state_timer'):
                self.control_state_timer.start(30000)
            
            # 停止恢复定时器
            if hasattr(self, 'periodic_recovery_timer'):
                self.periodic_recovery_timer.stop()
            
            if hasattr(self, 'log_widget'):
                self.add_log_async("INFO", "定期状态监控已恢复")
                
        except Exception as e:
            print(f"[控件监控] 恢复定期监控失败: {str(e)}")
            # 如果恢复失败，再次尝试
            if hasattr(self, 'periodic_recovery_timer'):
                self.periodic_recovery_timer.start(600000)  # 10分钟后再试
        # 使用说明按钮
        if hasattr(self, 'help_button'):
            self.help_button.clicked.connect(self._show_help_dialog)
            
        # Web界面按钮
        if hasattr(self, 'open_web_btn'):
            self.open_web_btn.clicked.connect(self._open_web_interface)
            
        # 测试客户端按钮
        if hasattr(self, 'test_client_btn'):
            self.test_client_btn.clicked.connect(self._test_client_connection)
            
        # 高级测试客户端按钮
        if hasattr(self, 'advanced_test_btn'):
            self.advanced_test_btn.clicked.connect(self._open_advanced_test_client)
        
    def _load_config(self):
        """加载配置"""
        # 从settings.json加载远程调试配置
        settings_file = Path("settings.json")
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                # 检查是否有远程调试配置
                if 'remote_debug' in settings:
                    self.config = IntegratedServerConfig.from_dict(settings['remote_debug'])
                    self._update_config_ui()
                else:
                    # 如果没有远程调试配置，检查是否有旧的配置文件
                    old_config_file = Path("remote_debug_config.json")
                    if old_config_file.exists():
                        with open(old_config_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        self.config = IntegratedServerConfig.from_dict(data)
                        # 迁移到settings.json
                        self._save_config()
                        self.add_log_async("INFO", "已将远程调试配置迁移到settings.json")
                        self._update_config_ui()
            except Exception as e:
                self.log_widget.add_log_async("ERROR", f"加载配置失败: {e}")
        
        # 加载自动滚动配置
        if hasattr(self.log_widget, '_load_auto_scroll_config'):
            self.log_widget._load_auto_scroll_config()
                
    def _save_config(self):
        """保存配置"""
        settings_file = Path("settings.json")
        try:
            # 读取现有的settings.json
            settings = {}
            if settings_file.exists():
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            
            # 更新远程调试配置
            settings['remote_debug'] = self.config.to_dict()
            
            # 保存到settings.json
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.add_log_async("ERROR", f"保存配置失败: {e}")
            
    def _update_config_ui(self):
        """更新配置UI"""
        self.host_edit.setText(self.config.host)
        self.port_edit.setValue(self.config.port)
        self.password_edit.setText(self.config.password)
        self.max_clients_spin.setValue(self.config.max_clients)
        
        # 更新身份验证、SSL加密和自动启动选项
        self.auth_check.setChecked(self.config.enable_auth)
        self.ssl_check.setChecked(self.config.enable_ssl)
        self.auto_start_check.setChecked(self.config.auto_start)
        
        # 更新Web界面配置选项
        if hasattr(self, 'web_interface_check'):
            self.web_interface_check.setChecked(self.config.enable_web_interface)
        if hasattr(self, 'web_host_edit'):
            self.web_host_edit.setText(self.config.web_host)
        if hasattr(self, 'web_port_spin'):
            self.web_port_spin.setValue(self.config.web_port)
        if hasattr(self, 'websocket_port_spin'):
            self.websocket_port_spin.setValue(self.config.websocket_port)
        
        # 检查高级配置控件是否存在
        if hasattr(self, 'pool_size_edit'):
            self.pool_size_edit.setValue(self.config.connection_pool_size)
        if hasattr(self, 'buffer_size_edit'):
            self.buffer_size_edit.setValue(self.config.message_buffer_size)
        if hasattr(self, 'thread_pool_edit'):
            self.thread_pool_edit.setValue(self.config.thread_pool_size)
            
        self.feature_config.set_enabled_features(self.config.enabled_features)
        
        # 更新自动滚动复选框状态
        if hasattr(self, 'log_widget') and hasattr(self.log_widget, 'auto_scroll_check'):
            self.log_widget.auto_scroll_check.setChecked(self.config.auto_scroll)
        
    def _apply_config(self):
        """应用配置"""
        try:
            # 应用配置到内存
            self.config.host = self.host_edit.text()
            self.config.port = self.port_edit.value()
            self.config.password = self.password_edit.text()
            self.config.max_clients = self.max_clients_spin.value()
            
            # 保存身份验证、SSL加密和自动启动选项
            self.config.enable_auth = self.auth_check.isChecked()
            self.config.enable_ssl = self.ssl_check.isChecked()
            self.config.auto_start = self.auto_start_check.isChecked()
            
            # 保存Web界面配置选项
            if hasattr(self, 'web_interface_check'):
                self.config.enable_web_interface = self.web_interface_check.isChecked()
            if hasattr(self, 'web_host_edit'):
                self.config.web_host = self.web_host_edit.text()
            if hasattr(self, 'web_port_spin'):
                self.config.web_port = self.web_port_spin.value()
            if hasattr(self, 'websocket_port_spin'):
                self.config.websocket_port = self.websocket_port_spin.value()
            
            # 检查高级配置控件是否存在
            if hasattr(self, 'pool_size_edit'):
                self.config.connection_pool_size = self.pool_size_edit.value()
            if hasattr(self, 'buffer_size_edit'):
                self.config.message_buffer_size = self.buffer_size_edit.value()
            if hasattr(self, 'thread_pool_edit'):
                self.config.thread_pool_size = self.thread_pool_edit.value()
                
            self.config.enabled_features = self.feature_config.get_enabled_features()
            
            # 保存自动滚动状态
            if hasattr(self, 'log_widget') and hasattr(self.log_widget, 'auto_scroll_check'):
                self.config.auto_scroll = self.log_widget.auto_scroll_check.isChecked()
            
            # 重新初始化功能组件
            self._initialize_feature_components()
            
            # 自动保存配置
            self._save_config()
            
            # 记录日志
            self.add_log_async("INFO", "配置已应用并自动保存")
            
            # 显示成功提示
            if self.is_server_running:
                QMessageBox.information(
                    self, 
                    "配置应用成功", 
                    "配置已成功应用并保存！\n\n功能组件已重新初始化，可立即使用。"
                )
            else:
                QMessageBox.information(
                    self, 
                    "配置应用成功", 
                    "配置已成功应用并保存！\n\n功能组件已初始化，配置将在下次启动服务器时生效。"
                )
                
        except Exception as e:
            # 显示错误提示
            QMessageBox.critical(
                self, 
                "配置应用失败", 
                f"配置应用失败！\n\n错误信息: {str(e)}\n\n请检查配置参数是否正确。"
            )
            
            # 记录错误日志
            self.add_log_async("ERROR", f"配置应用失败: {str(e)}")
            
    def _initialize_feature_components(self):
        """初始化功能组件（独立于服务器）"""
        try:
            # 初始化插件管理器
            if FeatureFlags.PLUGIN_SYSTEM in self.config.enabled_features:
                self.plugin_manager = PluginManager(self.config.plugin_dir)
                self.add_log_async("INFO", "插件管理器已初始化")
            else:
                self.plugin_manager = None
                
            # 初始化脚本执行器
            if FeatureFlags.SCRIPT_EXECUTOR in self.config.enabled_features:
                self.script_executor = ScriptExecutor()
                self.add_log_async("INFO", "脚本执行器已初始化")
            else:
                self.script_executor = None
                
            # 初始化会话管理器
            if FeatureFlags.SESSION_MANAGER in self.config.enabled_features:
                self.session_manager = SessionManager(self.config.session_dir)
                self.add_log_async("INFO", "会话管理器已初始化")
            else:
                self.session_manager = None
                
            # 初始化文件传输管理器
            if FeatureFlags.FILE_TRANSFER in self.config.enabled_features:
                self.file_transfer_manager = FileTransferManager(self.config.transfer_dir)
                self.add_log_async("INFO", "文件传输管理器已初始化")
            else:
                self.file_transfer_manager = None
                
        except Exception as e:
            self.add_log_async("ERROR", f"功能组件初始化失败: {str(e)}")
            
    def _start_server(self):
        """启动服务器"""
        if self.is_server_running:
            return
            
        try:
            # 创建服务器实例
            self.server = IntegratedDebugServer(self.config, self.dev_tools_panel)
            
            # 连接服务器信号
            self.server.state_changed.connect(self._on_server_state_changed)
            self.server.client_connected.connect(self._on_client_connected)
            self.server.client_disconnected.connect(self._on_client_disconnected)
            self.server.log_message.connect(self._on_log_message)
            self.server.stats_updated.connect(self._update_performance_display)
            
            # 设置性能监控
            self.performance_monitor.set_server(self.server)
            
            # 监听应用程序调色板变化（主题切换）
            try:
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
                if app:
                    app.paletteChanged.connect(self._on_theme_changed)
            except:
                pass
            
            # 启动服务器
            if self.server.start_server():
                self.is_server_running = True
                self.start_time = datetime.now()  # 设置启动时间
                self.stats_timer.start(100)  # 每100ms更新一次底部状态栏，实现实时显示
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                
                # 更新状态标签
                if hasattr(self, 'status_label'):
                    self.status_label.setText("状态: 运行中")
                    self.status_label.setStyleSheet("color: green; font-weight: bold;")
                
                # 更新服务器状态标签
                if hasattr(self, 'server_status_label'):
                    self.server_status_label.setText("服务器: 运行中")
                    self.server_status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
                
                # 如果启用了Web界面，启用Web界面按钮
                if hasattr(self, 'open_web_btn') and self.config.enable_web_interface:
                    self.open_web_btn.setEnabled(True)
                    
                self.performance_monitor.start_monitoring(1000)  # 1秒更新一次，实现实时显示
                self.add_log_async("INFO", "服务器启动成功")
                
                # 延迟启动客户端连接测试
                QTimer.singleShot(2000, self._auto_test_client_connection)  # 2秒后自动测试
            else:
                self.add_log_async("ERROR", "服务器启动失败")
                # 启动失败时更新状态标签
                if hasattr(self, 'status_label'):
                    self.status_label.setText("状态: 错误")
                    self.status_label.setStyleSheet("color: red; font-weight: bold;")
                
                if hasattr(self, 'server_status_label'):
                    self.server_status_label.setText("服务器: 错误")
                    self.server_status_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
                
        except Exception as e:
            self.add_log_async("ERROR", f"启动服务器时出错: {str(e)}")
            # 异常时更新状态标签
            if hasattr(self, 'status_label'):
                self.status_label.setText("状态: 错误")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")
            
            if hasattr(self, 'server_status_label'):
                self.server_status_label.setText("服务器: 错误")
                self.server_status_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
            
            QMessageBox.critical(self, "错误", f"启动服务器失败:\n{str(e)}")
            
    def _stop_server(self):
        """停止服务器"""
        if not self.is_server_running or not self.server:
            return
            
        try:
            self.performance_monitor.stop_monitoring()
            self.server.stop_server()
            
            self.is_server_running = False
            self.start_time = None  # 清除启动时间
            self.stats_timer.stop()  # 停止定时器
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            
            # 禁用Web界面按钮
            if hasattr(self, 'open_web_btn'):
                self.open_web_btn.setEnabled(False)
            
            # 更新状态标签
            if hasattr(self, 'status_label'):
                self.status_label.setText("状态: 已停止")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")
            
            # 更新服务器状态标签
            if hasattr(self, 'server_status_label'):
                self.server_status_label.setText("服务器: 已停止")
                self.server_status_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
            
            # 清空客户端列表
            self.client_model.update_clients([])
            
            self.add_log_async("INFO", "服务器已停止")
            
        except Exception as e:
            self.add_log_async("ERROR", f"停止服务器时出错: {str(e)}")
            
    def _on_server_state_changed(self, state: str):
        """服务器状态变化"""
        state_colors = {
            "stopped": "red",
            "starting": "orange",
            "running": "green",
            "stopping": "orange",
            "error": "red"
        }
        
        # 状态中文映射
        state_texts = {
            "stopped": "已停止",
            "starting": "启动中",
            "running": "运行中",
            "stopping": "停止中",
            "error": "错误"
        }
        
        color = state_colors.get(state, "black")
        chinese_state = state_texts.get(state, state)
        self.status_label.setText(f"状态: {chinese_state}")
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        
        # 状态指示器已移除，仅保留文本状态显示
    
    def _update_footer_stats(self):
        """更新底部状态栏统计信息"""
        # 检查服务器状态，如果服务器已停止，停止定时器
        if not self.server or not hasattr(self, 'start_time') or not self.start_time:
            if hasattr(self, 'stats_timer') and self.stats_timer.isActive():
                self.stats_timer.stop()
            # 重置显示为停止状态
            if hasattr(self, 'client_count_label'):
                self.client_count_label.setText("客户端: 0")
            if hasattr(self, 'client_count_label_dash'):
                self.client_count_label_dash.setText("客户端: 0")
            if hasattr(self, 'server_status_label'):
                self.server_status_label.setText("服务器: 已停止")
                self.server_status_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
            if hasattr(self, 'message_rate_label'):
                self.message_rate_label.setText("消息: 0/分钟")
            if hasattr(self, 'system_load_label'):
                self.system_load_label.setText("负载: 0%")
            if hasattr(self, 'uptime_label'):
                self.uptime_label.setText("运行时间: 00:00:00")
            if hasattr(self, 'memory_label'):
                try:
                    import psutil
                    process = psutil.Process()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    self.memory_label.setText(f"内存: {memory_mb:.1f} MB")
                except ImportError:
                    self.memory_label.setText("内存: N/A")
            return
        
        if hasattr(self, 'client_count_label'):
            # 从服务器获取实际的客户端数量
            client_count = 0
            if self.server and hasattr(self.server, 'connection_pool'):
                client_count = len(self.server.connection_pool.get_all_connections())
            self.client_count_label.setText(f"客户端: {client_count}")
        
        # 同时更新状态控制模块中的客户端数量标签
        if hasattr(self, 'client_count_label_dash'):
            client_count = 0
            if self.server and hasattr(self.server, 'connection_pool'):
                client_count = len(self.server.connection_pool.get_all_connections())
            self.client_count_label_dash.setText(f"客户端: {client_count}")
        
        if hasattr(self, 'uptime_label'):
            if hasattr(self, 'start_time') and self.start_time:
                uptime = datetime.now() - self.start_time
                hours, remainder = divmod(int(uptime.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                self.uptime_label.setText(f"运行时间: {hours:02d}:{minutes:02d}:{seconds:02d}")
            else:
                self.uptime_label.setText("运行时间: 00:00:00")
        
        if hasattr(self, 'memory_label'):
            try:
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                self.memory_label.setText(f"内存: {memory_mb:.1f} MB")
            except ImportError:
                self.memory_label.setText("内存: N/A")
        
        # 更新服务器状态与控制模块中的状态标签
        if hasattr(self, 'server_status_label'):
            if self.server and hasattr(self.server, 'state'):
                state_texts = {
                    "stopped": "已停止",
                    "starting": "启动中",
                    "running": "运行中",
                    "stopping": "停止中",
                    "error": "错误"
                }
                state_colors = {
                    "stopped": "red",
                    "starting": "orange",
                    "running": "green",
                    "stopping": "orange",
                    "error": "red"
                }
                state = self.server.state.value if hasattr(self.server.state, 'value') else str(self.server.state)
                chinese_state = state_texts.get(state, state)
                color = state_colors.get(state, "black")
                self.server_status_label.setText(f"服务器: {chinese_state}")
                self.server_status_label.setStyleSheet(f"QLabel {{ color: {color}; font-weight: bold; }}")
            else:
                self.server_status_label.setText("服务器: 已停止")
                self.server_status_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
        
        # 更新消息速率标签
        if hasattr(self, 'message_rate_label'):
            if self.server and hasattr(self.server, 'message_processor'):
                stats = self.server.message_processor.get_stats()
                messages_per_minute = stats.get('messages_processed', 0)
                self.message_rate_label.setText(f"消息: {messages_per_minute}/分钟")
            else:
                self.message_rate_label.setText("消息: 0/分钟")
        
        # 更新系统负载标签
        if hasattr(self, 'system_load_label'):
            try:
                import psutil
                cpu_percent = psutil.cpu_percent(interval=None)
                self.system_load_label.setText(f"负载: {cpu_percent:.1f}%")
            except ImportError:
                self.system_load_label.setText("负载: N/A")
            except:
                self.system_load_label.setText("负载: 0%")
    
    def _update_stat_card(self, card_widget, title: str, value: str, color: str):
        """更新统计卡片"""
        if hasattr(card_widget, 'value_label'):
            card_widget.value_label.setText(value)
        if hasattr(card_widget, 'title_label'):
            card_widget.title_label.setText(title)
        
    def _on_client_connected(self, client_id: str):
        """客户端连接"""
        self.add_log_async("INFO", f"客户端连接: {client_id}")
        self._refresh_clients()
        
    def _on_client_disconnected(self, client_id: str):
        """客户端断开"""
        self.add_log_async("INFO", f"客户端断开: {client_id}")
        self._refresh_clients()
        
    def add_log_async(self, level: str, message: str):
        """统一的日志添加方法"""
        # 1. 向AsyncLogWidget发送日志（主要的日志显示组件）
        if hasattr(self, 'log_widget') and self.log_widget:
            self.log_widget.add_log_async(level, message)
        
        # 2. 向log_display发送日志（用于过滤功能）
        if hasattr(self, 'log_display') and self.log_display:
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # 存储日志条目用于过滤
            if not hasattr(self, '_all_log_entries'):
                self._all_log_entries = []
            
            log_entry = {
                'level': level,
                'message': message,
                'timestamp': timestamp
            }
            self._all_log_entries.append(log_entry)
            
            # 限制存储的日志条目数量，避免内存过多占用
            if len(self._all_log_entries) > 1000:
                self._all_log_entries = self._all_log_entries[-1000:]
            
            # 应用当前的过滤条件显示日志
            self._filter_logs()
    
    def _on_log_message(self, level: str, message: str):
        """处理服务器日志消息"""
        # 使用统一的日志方法
        self.add_log_async(level, message)
        
    def _on_feature_changed(self, feature: str, enabled: bool):
        """功能开关变化"""
        feature_flag = FeatureFlags(feature)
        if enabled:
            self.config.enabled_features.add(feature_flag)
        else:
            self.config.enabled_features.discard(feature_flag)
        
        # 功能名称映射
        feature_names = {
            "basic_debug": "基础调试功能",
            "performance_opt": "性能优化",
            "plugin_system": "插件系统",
            "script_executor": "脚本执行",
            "file_transfer": "文件传输",
            "session_manager": "会话管理",
            "advanced_tools": "高级工具"
        }
        
        feature_name = feature_names.get(feature, feature)
        self.add_log_async("INFO", f"功能 {feature_name} {'启用' if enabled else '禁用'}")
        
    def _on_features_applied(self):
        """功能配置应用处理"""
        enabled_features = self.feature_config.get_enabled_features()
        self.config.enabled_features = enabled_features
        self._save_config()
        
        # 如果服务器正在运行，重新启动以应用新配置
        if self.server and self.server.state == DebugServerState.RUNNING:
            self.add_log_async("INFO", "重新启动服务器以应用新的功能配置...")
            self._stop_server()
            QTimer.singleShot(1000, self._start_server)  # 延迟1秒后重启
        
        # 功能名称映射
        feature_names = {
            "basic_debug": "基础调试功能",
            "performance_opt": "性能优化",
            "plugin_system": "插件系统",
            "script_executor": "脚本执行",
            "file_transfer": "文件传输",
            "session_manager": "会话管理",
            "advanced_tools": "高级工具"
        }
        
        enabled_feature_names = [feature_names.get(f.value, f.value) for f in enabled_features]
        self.add_log_async("INFO", f"功能配置已应用: {enabled_feature_names}")
        
    def _refresh_clients(self):
        """刷新客户端列表"""
        if self.server:
            clients = self.server.get_all_clients()
            if hasattr(self, 'client_model'):
                self.client_model.update_clients(clients)
            self.add_log_async("INFO", f"客户端列表已刷新，当前连接数: {len(clients)}")
        else:
            self.add_log_async("WARNING", "服务器未运行，无法刷新客户端列表")
            
    def _disconnect_selected_client(self):
        """断开选中的客户端"""
        selection = self.client_table.selectionModel().selectedRows()
        if not selection or not self.server:
            return
            
        row = selection[0].row()
        if row < len(self.client_model.clients):
            client = self.client_model.clients[row]
            self.server.disconnect_client(client.client_id)
            self.add_log_async("INFO", f"断开客户端: {client.client_id}")
            
    def _broadcast_message(self):
        """广播消息"""
        if not self.server:
            return
            
        message, ok = QInputDialog.getText(self, "广播消息", "请输入要广播的消息:")
        if ok and message:
            self.server.broadcast_message(message)
            self.add_log_async("INFO", f"广播消息: {message}")
            
    def _test_client_connection(self):
        """测试客户端连接"""
        if not self.server or self.server.state != DebugServerState.RUNNING:
            QMessageBox.warning(self, "警告", "服务器未运行，无法测试客户端连接")
            return
            
        # 显示测试开始信息
        self.add_log_async("INFO", "开始测试客户端连接...")
        
        # 创建并启动测试线程
        
        # 创建测试线程
        self.test_thread = TestClientThread(self)
        
        # 连接信号
        def on_test_progress(message):
            self.add_log_async("INFO", message)
            
        def on_test_completed(success, message):
            if success:
                QMessageBox.information(self, "测试完成", message)
            else:
                QMessageBox.critical(self, "测试失败", message)
            self.add_log_async("INFO", "测试客户端连接完成")
            
        self.test_thread.test_progress.connect(on_test_progress)
        self.test_thread.test_completed.connect(on_test_completed)
        
        # 启动测试线程
        self.test_thread.start()
        
    def _auto_test_client_connection(self):
        """自动测试客户端连接（服务器启动后）"""
        if not self.server or self.server.state != DebugServerState.RUNNING:
            return
            
        # 显示测试开始信息
        self.add_log_async("INFO", "开始测试客户端连接...")
        
        # 创建测试线程
        self.test_thread = TestClientThread(self)
        
        # 连接信号（自动测试不显示弹窗）
        def on_test_progress(message):
            self.add_log_async("INFO", message)
            
        def on_test_completed(success, message):
            if success:
                self.add_log_async("INFO", "测试客户端连接成功")
            else:
                self.add_log_async("ERROR", f"测试客户端连接失败: {message}")
            self.add_log_async("INFO", "测试客户端连接完成")
            
        self.test_thread.test_progress.connect(on_test_progress)
        self.test_thread.test_completed.connect(on_test_completed)
        
        # 启动测试线程
        self.test_thread.start()
            
    def _update_performance_display(self, stats: dict):
        """更新性能显示"""
        # 更新统计标签
        for key, label in self.stats_labels.items():
            if key in stats:
                value = stats[key]
                if key == "uptime":
                    hours = int(value // 3600)
                    minutes = int((value % 3600) // 60)
                    seconds = int(value % 60)
                    label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
                elif key == "memory_usage":
                    label.setText(f"{value:.1f} MB")
                elif key == "cpu_usage":
                    label.setText(f"{value:.1f}%")
                else:
                    label.setText(str(value))
                    
        # 更新性能趋势文本
        history = self.performance_monitor.get_stats_history()
        if len(history) > 1:
            recent_stats = history[-10:]  # 最近10条记录
            trend_text = "最近性能趋势:\n"
            for stat in recent_stats:
                timestamp = time.strftime('%H:%M:%S', time.localtime(stat['timestamp']))
                trend_text += f"[{timestamp}] 连接: {stat.get('active_connections', 0)}, "
                trend_text += f"消息: {stat.get('messages_processed', 0)}, "
                trend_text += f"内存: {stat.get('memory_usage', 0):.1f}MB\n"
                
            if hasattr(self, 'performance_display'):
                self.performance_display.setPlainText(trend_text)
                # 自动滚动到底部，确保显示最新的性能数据
                QTimer.singleShot(10, lambda: self.performance_display.verticalScrollBar().setValue(
                    self.performance_display.verticalScrollBar().maximum()))
            
    def _scan_plugins(self):
        """扫描插件"""
        # 优先使用服务器的插件管理器，如果不存在则使用独立的插件管理器
        plugin_manager = None
        if self.server and hasattr(self.server, 'plugin_manager') and self.server.plugin_manager:
            plugin_manager = self.server.plugin_manager
        elif hasattr(self, 'plugin_manager') and self.plugin_manager:
            plugin_manager = self.plugin_manager
            
        if not plugin_manager:
            QMessageBox.warning(self, "警告", "插件系统未启用")
            return
            
        plugins = plugin_manager.scan_plugins()
        self._update_plugin_list()
        self.add_log_async("INFO", f"扫描到 {len(plugins)} 个插件")
        
    def _update_plugin_list(self):
        """更新插件列表"""
        self.plugin_list.clear()
        
        # 优先使用服务器的插件管理器，如果不存在则使用独立的插件管理器
        plugin_manager = None
        if self.server and hasattr(self.server, 'plugin_manager') and self.server.plugin_manager:
            plugin_manager = self.server.plugin_manager
        elif hasattr(self, 'standalone_plugin_manager') and self.standalone_plugin_manager:
            plugin_manager = self.standalone_plugin_manager
            
        if not plugin_manager:
            return
            
        for plugin_info in plugin_manager.get_all_plugins():
            item = QTreeWidgetItem([
                plugin_info.name,
                plugin_info.version,
                "已加载" if plugin_info.loaded else "未加载",
                plugin_info.description
            ])
            
            # 设置颜色
            if plugin_info.loaded:
                item.setForeground(2, QColor(0, 150, 0))
            elif plugin_info.error_message:
                item.setForeground(2, QColor(200, 0, 0))
                item.setToolTip(2, plugin_info.error_message)
                
            self.plugin_list.addTopLevelItem(item)
            
    def _load_selected_plugin(self):
        """加载选中的插件"""
        current = self.plugin_list.currentItem()
        if not current:
            return
            
        # 优先使用服务器的插件管理器，如果不存在则使用独立的插件管理器
        plugin_manager = None
        if self.server and hasattr(self.server, 'plugin_manager') and self.server.plugin_manager:
            plugin_manager = self.server.plugin_manager
        elif hasattr(self, 'standalone_plugin_manager') and self.standalone_plugin_manager:
            plugin_manager = self.standalone_plugin_manager
            
        if not plugin_manager:
            QMessageBox.warning(self, "警告", "插件系统未启用")
            return
            
        plugin_name = current.text(0)
        if plugin_manager.load_plugin(plugin_name):
            self.add_log_async("INFO", f"插件 {plugin_name} 加载成功")
        else:
            self.add_log_async("ERROR", f"插件 {plugin_name} 加载失败")
            
        self._update_plugin_list()
        
    def _unload_selected_plugin(self):
        """卸载选中的插件"""
        current = self.plugin_list.currentItem()
        if not current:
            return
            
        # 优先使用服务器的插件管理器，如果不存在则使用独立的插件管理器
        plugin_manager = None
        if self.server and hasattr(self.server, 'plugin_manager') and self.server.plugin_manager:
            plugin_manager = self.server.plugin_manager
        elif hasattr(self, 'standalone_plugin_manager') and self.standalone_plugin_manager:
            plugin_manager = self.standalone_plugin_manager
            
        if not plugin_manager:
            QMessageBox.warning(self, "警告", "插件系统未启用")
            return
            
        plugin_name = current.text(0)
        if plugin_manager.unload_plugin(plugin_name):
            self.add_log_async("INFO", f"插件 {plugin_name} 卸载成功")
        else:
            self.add_log_async("ERROR", f"插件 {plugin_name} 卸载失败")
            
        self._update_plugin_list()
        
    def _execute_script(self):
        """执行脚本"""
        # 优先使用服务器的脚本执行器，如果不存在则使用独立的脚本执行器
        script_executor = None
        if self.server and hasattr(self.server, 'script_executor') and self.server.script_executor:
            script_executor = self.server.script_executor
        elif hasattr(self, 'script_executor') and self.script_executor:
            script_executor = self.script_executor
            
        if not script_executor:
            QMessageBox.warning(self, "警告", "脚本执行器未启用")
            return
            
        script = self.script_editor.toPlainText()
        if not script.strip():
            return
            
        try:
            result = script_executor.execute_script(script)
            
            # 显示结果
            result_text = f"执行时间: {result['execution_time']:.3f}秒\n"
            result_text += f"时间戳: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result['timestamp']))}\n\n"
            
            if result['success']:
                result_text += f"执行成功:\n{result['result']}"
                self.script_result.setStyleSheet("color: green;")
            else:
                result_text += f"执行失败:\n{result['error']}\n\n"
                result_text += f"详细错误:\n{result['traceback']}"
                self.script_result.setStyleSheet("color: red;")
                
            self.script_result.setPlainText(result_text)
            
        except Exception as e:
            self.script_result.setPlainText(f"脚本执行异常: {str(e)}")
            self.script_result.setStyleSheet("color: red;")
            
    def _create_session(self):
        """创建会话"""
        # 优先使用服务器的会话管理器，如果不存在则使用独立的会话管理器
        session_manager = None
        if self.server and hasattr(self.server, 'session_manager') and self.server.session_manager:
            session_manager = self.server.session_manager
        elif hasattr(self, 'session_manager') and self.session_manager:
            session_manager = self.session_manager
            
        if not session_manager:
            QMessageBox.warning(self, "警告", "会话管理器未启用")
            return
            
        name, ok = QInputDialog.getText(self, "创建会话", "请输入会话名称:")
        if ok and name:
            description, ok2 = QInputDialog.getText(self, "创建会话", "请输入会话描述(可选):")
            if ok2:
                session_id = self.server.session_manager.create_session(name, description)
                self._update_session_list()
                self.add_log_async("INFO", f"创建会话: {name} ({session_id})")
                
    def _switch_session(self):
        """切换会话"""
        if not hasattr(self, 'session_combo') or not self.server or not self.server.session_manager:
            return
            
        current_text = self.session_combo.currentText()
        if not current_text:
            return
            
        # 从组合框文本中提取会话ID（假设格式为 "会话名称 (ID)"）
        session_id = current_text.split('(')[-1].rstrip(')')
        if self.server.session_manager.switch_session(session_id):
            self._update_session_details(session_id)
            self.add_log_async("INFO", f"切换到会话: {session_id}")
            
    def _delete_session(self):
        """删除会话"""
        current = self.session_list.currentItem()
        if not current or not self.server or not self.server.session_manager:
            return
            
        session_id = current.data(Qt.ItemDataRole.UserRole)
        session_name = current.text()
        
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除会话 '{session_name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.server.session_manager.delete_session(session_id):
                self._update_session_list()
                self.session_details.clear()
                self.add_log_async("INFO", f"删除会话: {session_name}")
                
    def _update_session_list(self):
        """更新会话列表"""
        self.session_list.clear()
        
        if not self.server or not self.server.session_manager:
            return
            
        for session_info in self.server.session_manager.get_all_sessions():
            item = QListWidgetItem(f"{session_info['name']} ({session_info['id'][:8]})")
            item.setData(Qt.ItemDataRole.UserRole, session_info['id'])
            
            # 标记当前会话
            if session_info['id'] == self.server.session_manager.current_session_id:
                item.setForeground(QColor(0, 100, 200))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                
            self.session_list.addItem(item)
            
    def _update_session_details(self, session_id: str):
        """更新会话详情"""
        if not self.server or not self.server.session_manager:
            return
            
        session_info = self.server.session_manager.get_session_info(session_id)
        if session_info:
            details = f"""会话ID: {session_info['id']}
创建时间: {session_info['created_at']}
最后活动: {session_info['last_activity']}
状态: {session_info['status']}
客户端数量: {len(session_info['clients'])}
消息数量: {session_info['message_count']}"""
            self.session_details.setText(details)
    
    # ==================== 使用说明对话框 ====================
    
    def _show_help_dialog(self):
        """显示使用说明对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("远程调试控制面板 - 使用说明")
        dialog.resize(900, 700)
        dialog.setMinimumSize(800, 600)
        
        # 窗口居中显示
        dialog.move(self.geometry().center() - dialog.rect().center())
        
        layout = QVBoxLayout(dialog)
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 概述标签页
        overview_tab = self._create_overview_tab()
        tab_widget.addTab(overview_tab, "📋 功能概述")
        
        # 服务器管理标签页
        server_tab = self._create_server_help_tab()
        tab_widget.addTab(server_tab, "🖥️ 服务器管理")
        
        # 客户端管理标签页
        client_tab = self._create_client_help_tab()
        tab_widget.addTab(client_tab, "👥 客户端管理")
        
        # 配置管理标签页
        config_tab = self._create_config_help_tab()
        tab_widget.addTab(config_tab, "⚙️ 配置管理")
        
        # 安全功能标签页
        security_tab = self._create_security_help_tab()
        tab_widget.addTab(security_tab, "🔒 安全功能")
        
        # 高级功能标签页
        advanced_tab = self._create_advanced_help_tab()
        tab_widget.addTab(advanced_tab, "🚀 高级功能")
        
        # 故障排除标签页
        troubleshoot_tab = self._create_troubleshoot_help_tab()
        tab_widget.addTab(troubleshoot_tab, "🔧 故障排除")
        
        layout.addWidget(tab_widget)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.close)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    def _create_overview_tab(self) -> QWidget:
        """创建功能概述标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        content = QTextBrowser()
        content.setStyleSheet("QTextBrowser { font-size: 14px; }")
        content.setHtml("""
        <h2>🎯 远程调试控制面板功能概述</h2>
        
        <h3>📌 主要功能模块</h3>
        <ul>
            <li><b>服务器管理</b> - 启动/停止调试服务器，配置端口和连接参数</li>
            <li><b>客户端管理</b> - 查看连接的客户端，管理客户端连接状态</li>
            <li><b>配置管理</b> - 服务器配置、功能开关、性能参数设置</li>
            <li><b>安全功能</b> - 身份验证、SSL加密、访问控制</li>
            <li><b>日志监控</b> - 实时查看服务器日志和客户端活动</li>
            <li><b>性能监控</b> - 监控服务器性能指标和资源使用情况</li>
            <li><b>高级功能</b> - 插件系统、脚本执行、文件传输等</li>
        </ul>
        
        <h3>🚀 快速开始</h3>
        <ol>
            <li><b>配置服务器</b> - 在"配置管理"模块设置端口、密码等基本参数</li>
            <li><b>启用安全功能</b> - 根据需要启用身份验证和SSL加密</li>
            <li><b>启动服务器</b> - 点击"启动"按钮开始调试服务</li>
            <li><b>连接客户端</b> - 客户端使用配置的地址和端口连接</li>
            <li><b>监控状态</b> - 通过各个模块监控服务器和客户端状态</li>
        </ol>
        
        <h3>💡 使用建议</h3>
        <ul>
            <li><b>安全第一</b> - 生产环境建议启用身份验证和SSL加密</li>
            <li><b>性能优化</b> - 根据实际负载调整连接池和缓冲区大小</li>
            <li><b>日志管理</b> - 定期清理日志文件，避免占用过多磁盘空间</li>
            <li><b>配置备份</b> - 重要配置建议导出备份</li>
        </ul>
        
        <h3>⚠️ 注意事项</h3>
        <ul>
            <li>修改配置后需要点击"应用配置"才能生效</li>
            <li>服务器运行时某些配置无法修改</li>
            <li>SSL证书路径必须正确且证书有效</li>
            <li>防火墙需要开放相应端口</li>
        </ul>
        """)
        
        layout.addWidget(content)
        return widget
    
    def _create_server_help_tab(self) -> QWidget:
        """创建服务器管理帮助标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        content = QTextBrowser()
        content.setStyleSheet("QTextBrowser { font-size: 14px; }")
        content.setHtml("""
        <h2>🖥️ 服务器管理详细说明</h2>
        
        <h3>🎮 基本控制</h3>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr>
                <th>操作</th>
                <th>说明</th>
                <th>注意事项</th>
            </tr>
            <tr>
                <td><b>启动服务器</b></td>
                <td>启动远程调试服务，开始监听客户端连接</td>
                <td>确保端口未被占用，防火墙已开放</td>
            </tr>
            <tr>
                <td><b>停止服务器</b></td>
                <td>停止服务器，断开所有客户端连接</td>
                <td>会强制断开所有客户端</td>
            </tr>
            <tr>
                <td><b>重启服务器</b></td>
                <td>先停止再启动服务器，应用新配置</td>
                <td>配置修改后建议重启</td>
            </tr>
            <tr>
                <td><b>端口配置</b></td>
                <td>设置服务器监听端口（1000-65535）</td>
                <td>避免使用系统保留端口</td>
            </tr>
        </table>
        
        <h3>📊 状态监控</h3>
        <ul>
            <li><b>服务器状态</b> - 显示当前服务器运行状态（已停止/运行中/错误）</li>
            <li><b>连接数量</b> - 显示当前连接的客户端数量</li>
            <li><b>运行时间</b> - 显示服务器连续运行时间</li>
            <li><b>消息统计</b> - 显示消息处理速率和总数</li>
        </ul>
        
        <h3>⚡ 性能优化</h3>
        <ul>
            <li><b>连接池大小</b> - 控制最大并发连接数，默认50</li>
            <li><b>消息缓冲区</b> - 设置消息队列大小，默认100</li>
            <li><b>线程池大小</b> - 控制处理线程数量，默认5</li>
            <li><b>超时设置</b> - 设置客户端连接超时时间</li>
        </ul>
        
        <h3>🔄 自动功能</h3>
        <ul>
            <li><b>自动启动</b> - 程序启动时自动启动调试服务器</li>
            <li><b>自动重连</b> - 客户端断开后自动尝试重连</li>
            <li><b>负载均衡</b> - 自动分配客户端到不同处理线程</li>
        </ul>
        """)
        
        layout.addWidget(content)
        return widget
    
    def _create_client_help_tab(self) -> QWidget:
        """创建客户端管理帮助标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        content = QTextBrowser()
        content.setStyleSheet("QTextBrowser { font-size: 14px; }")
        content.setHtml("""
        <h2>👥 客户端管理详细说明</h2>
        
        <h3>📋 客户端列表</h3>
        <p>客户端表格显示所有连接的客户端信息：</p>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr>
                <th>列名</th>
                <th>说明</th>
            </tr>
            <tr>
                <td><b>客户端ID</b></td>
                <td>唯一标识符，自动生成</td>
            </tr>
            <tr>
                <td><b>IP地址</b></td>
                <td>客户端的网络地址</td>
            </tr>
            <tr>
                <td><b>连接时间</b></td>
                <td>客户端连接的时间戳</td>
            </tr>
            <tr>
                <td><b>状态</b></td>
                <td>连接状态（连接中/已连接/已认证/已断开）</td>
            </tr>
            <tr>
                <td><b>消息数</b></td>
                <td>该客户端发送的消息总数</td>
            </tr>
            <tr>
                <td><b>操作</b></td>
                <td>可执行的操作按钮</td>
            </tr>
        </table>
        
        <h3>🎮 客户端操作</h3>
        <ul>
            <li><b>刷新列表</b> - 更新客户端列表显示</li>
            <li><b>断开选中</b> - 断开当前选中的客户端连接</li>
            <li><b>断开所有</b> - 断开所有客户端连接</li>
            <li><b>广播消息</b> - 向所有客户端发送消息</li>
        </ul>
        
        <h3>📡 连接状态说明</h3>
        <ul>
            <li><b>连接中</b> - 客户端正在建立连接</li>
            <li><b>已连接</b> - 连接建立成功，等待认证</li>
            <li><b>已认证</b> - 通过身份验证，可以正常通信</li>
            <li><b>已断开</b> - 连接已断开或异常</li>
            <li><b>错误</b> - 连接过程中发生错误</li>
        </ul>
        
        <h3>💬 消息通信</h3>
        <ul>
            <li><b>单播消息</b> - 向特定客户端发送消息</li>
            <li><b>广播消息</b> - 向所有客户端发送相同消息</li>
            <li><b>消息格式</b> - 支持JSON格式的结构化消息</li>
            <li><b>消息队列</b> - 自动管理消息发送队列</li>
        </ul>
        
        <h3>🔍 监控功能</h3>
        <ul>
            <li><b>实时更新</b> - 客户端状态实时刷新</li>
            <li><b>连接统计</b> - 显示连接数量和活跃度</li>
            <li><b>流量监控</b> - 监控数据传输量</li>
            <li><b>异常检测</b> - 自动检测异常连接</li>
        </ul>
        """)
        
        layout.addWidget(content)
        return widget
    
    def _create_config_help_tab(self) -> QWidget:
        """创建配置管理帮助标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        content = QTextBrowser()
        content.setStyleSheet("QTextBrowser { font-size: 14px; }")
        content.setHtml("""
        <h2>⚙️ 配置管理详细说明</h2>
        
        <h3>🔧 基础配置</h3>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr>
                <th>配置项</th>
                <th>说明</th>
                <th>默认值</th>
                <th>建议</th>
            </tr>
            <tr>
                <td><b>主机地址</b></td>
                <td>服务器绑定的IP地址</td>
                <td>127.0.0.1</td>
                <td>本地测试用127.0.0.1，远程访问用0.0.0.0</td>
            </tr>
            <tr>
                <td><b>端口号</b></td>
                <td>服务器监听端口</td>
                <td>9009</td>
                <td>避免与其他服务冲突</td>
            </tr>
            <tr>
                <td><b>连接密码</b></td>
                <td>客户端连接验证密码</td>
                <td>xuanwu</td>
                <td>使用强密码提高安全性</td>
            </tr>
            <tr>
                <td><b>最大客户端</b></td>
                <td>允许的最大并发连接数</td>
                <td>10</td>
                <td>根据服务器性能调整</td>
            </tr>
            <tr>
                <td><b>超时时间</b></td>
                <td>客户端连接超时（秒）</td>
                <td>30</td>
                <td>网络较差时可适当增加</td>
            </tr>
        </table>
        
        <h3>🎛️ 功能开关</h3>
        <ul>
            <li><b>基础调试</b> - 核心调试功能，建议始终启用</li>
            <li><b>性能优化</b> - 连接池和缓存优化</li>
            <li><b>高级工具</b> - 高级调试工具集</li>
            <li><b>插件系统</b> - 支持第三方插件扩展</li>
            <li><b>脚本执行</b> - 远程脚本执行功能</li>
            <li><b>会话管理</b> - 调试会话保存和恢复</li>
            <li><b>文件传输</b> - 客户端文件上传下载</li>
        </ul>
        
        <h3>⚡ 性能参数</h3>
        <ul>
            <li><b>连接池大小</b> - 预分配的连接对象数量</li>
            <li><b>消息缓冲区</b> - 消息队列的最大长度</li>
            <li><b>日志缓存</b> - 内存中保存的日志条数</li>
            <li><b>线程池大小</b> - 处理请求的工作线程数</li>
            <li><b>更新间隔</b> - UI刷新间隔（毫秒）</li>
        </ul>
        
        <h3>💾 配置管理</h3>
        <ul>
            <li><b>应用配置</b> - 将当前设置应用到服务器（临时）</li>
            <li><b>保存配置</b> - 将配置保存到文件（永久）</li>
            <li><b>导出配置</b> - 将配置导出为JSON文件</li>
            <li><b>导入配置</b> - 从JSON文件导入配置</li>
            <li><b>重置配置</b> - 恢复默认配置</li>
        </ul>
        
        <h3>🔄 配置生效</h3>
        <p><b>重要：</b>配置修改后的生效方式：</p>
        <ul>
            <li><b>立即生效</b> - 日志级别、UI更新间隔等</li>
            <li><b>应用后生效</b> - 性能参数、功能开关等</li>
            <li><b>重启后生效</b> - 网络配置、SSL设置等</li>
        </ul>
        """)
        
        layout.addWidget(content)
        return widget
    
    def _create_security_help_tab(self) -> QWidget:
        """创建安全功能帮助标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        content = QTextBrowser()
        content.setStyleSheet("QTextBrowser { font-size: 14px; }")
        content.setHtml("""
        <h2>🔒 安全功能详细说明</h2>
        
        <h3>🔐 身份验证</h3>
        <ul>
            <li><b>启用方式</b> - 勾选"启用身份验证"选项</li>
            <li><b>认证Token</b> - 系统自动生成的安全令牌</li>
            <li><b>Token管理</b> - 支持复制、重新生成、查看详情</li>
            <li><b>验证流程</b> - 客户端连接时必须提供正确的Token</li>
        </ul>
        
        <h4>🎫 Token使用说明</h4>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr>
                <th>操作</th>
                <th>说明</th>
                <th>使用场景</th>
            </tr>
            <tr>
                <td><b>复制Token</b></td>
                <td>将Token复制到剪贴板</td>
                <td>分发给客户端开发者</td>
            </tr>
            <tr>
                <td><b>重新生成</b></td>
                <td>生成新的Token，旧Token失效</td>
                <td>Token泄露或定期更换</td>
            </tr>
            <tr>
                <td><b>查看详情</b></td>
                <td>显示Token的详细信息</td>
                <td>查看生成时间、有效期等</td>
            </tr>
        </table>
        
        <h3>🔒 SSL加密</h3>
        <ul>
            <li><b>启用方式</b> - 勾选"启用SSL加密"选项</li>
            <li><b>证书要求</b> - 需要有效的SSL证书和私钥文件</li>
            <li><b>证书路径</b> - 默认在ssl/目录下</li>
            <li><b>加密强度</b> - 使用TLS 1.2+标准加密</li>
        </ul>
        
        <h4>📜 SSL证书管理</h4>
        <ul>
            <li><b>证书文件</b> - ssl_cert.pem（公钥证书）</li>
            <li><b>私钥文件</b> - ssl_key.pem（私钥）</li>
            <li><b>证书验证</b> - 自动检查证书有效性</li>
            <li><b>证书更新</b> - 支持热更新，无需重启</li>
        </ul>
        
        <h4>🔗 SSL客户端连接指南</h4>
        <p><b>重要：</b>启用SSL后，客户端必须使用HTTPS协议连接，否则会出现SSL握手失败错误。</p>
        
        <h5>📋 连接示例代码</h5>
        <p><b>Python客户端示例：</b></p>
        <pre style="padding: 10px; border-radius: 5px;">
import ssl
import socket
import json

# SSL连接示例
def connect_with_ssl(host='127.0.0.1', port=9009, password='your_secure_password'):
    # 创建SSL上下文
    context = ssl.create_default_context()
    context.check_hostname = False  # 开发环境可禁用主机名检查
    context.verify_mode = ssl.CERT_NONE  # 开发环境可禁用证书验证
    
    # 创建套接字并包装SSL
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ssl_sock = context.wrap_socket(sock)
    
    try:
        # 连接到服务器
        ssl_sock.connect((host, port))
        print(f"已连接到 {host}:{port} (SSL)")
        
        # 发送认证信息
        auth_data = {'password': password}
        ssl_sock.send(json.dumps(auth_data).encode('utf-8'))
        
        # 接收响应
        response = ssl_sock.recv(1024).decode('utf-8')
        print(f"服务器响应: {response}")
        
    except ssl.SSLError as e:
        print(f"SSL错误: {e}")
        print("请检查：1) 服务器是否启用SSL 2) 使用正确的端口")
    except Exception as e:
        print(f"连接错误: {e}")
    finally:
        ssl_sock.close()

# 调用示例
connect_with_ssl()
        </pre>
        
        <p><b>JavaScript客户端示例：</b></p>
        <pre style="padding: 10px; border-radius: 5px;">
// 使用WebSocket进行SSL连接
function connectWithSSL(host = '127.0.0.1', port = 9009, password = 'your_secure_password') {
    // 注意：启用SSL时必须使用wss://协议
    const wsUrl = `wss://${host}:${port}`;
    
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = function(event) {
        console.log('已连接到服务器 (SSL)');
        
        // 发送认证信息
        const authData = { password: password };
        ws.send(JSON.stringify(authData));
    };
    
    ws.onmessage = function(event) {
        console.log('服务器响应:', event.data);
    };
    
    ws.onerror = function(error) {
        console.error('连接错误:', error);
        console.log('请检查：1) 使用wss://协议 2) 服务器SSL配置正确');
    };
    
    ws.onclose = function(event) {
        console.log('连接已关闭');
    };
}

// 调用示例
connectWithSSL();
        </pre>
        
        <h5>⚠️ 常见SSL连接问题</h5>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr>
                <th>错误信息</th>
                <th>原因</th>
                <th>解决方案</th>
            </tr>
            <tr>
                <td><b>SSL: HTTP_REQUEST</b></td>
                <td>客户端使用HTTP协议连接SSL服务器</td>
                <td>将连接协议改为HTTPS/WSS</td>
            </tr>
            <tr>
                <td><b>SSL: CERTIFICATE_VERIFY_FAILED</b></td>
                <td>SSL证书验证失败</td>
                <td>检查证书有效性或禁用证书验证</td>
            </tr>
            <tr>
                <td><b>Connection refused</b></td>
                <td>服务器未启动或端口错误</td>
                <td>确认服务器运行状态和端口配置</td>
            </tr>
        </table>
        
        <h3>🛡️ 访问控制</h3>
        <ul>
            <li><b>IP白名单</b> - 限制允许连接的IP地址</li>
            <li><b>连接限制</b> - 限制单个IP的最大连接数</li>
            <li><b>频率限制</b> - 防止恶意频繁连接</li>
            <li><b>黑名单</b> - 自动封禁异常IP</li>
        </ul>
        
        <h3>📊 安全监控</h3>
        <ul>
            <li><b>连接日志</b> - 记录所有连接尝试</li>
            <li><b>认证日志</b> - 记录认证成功/失败</li>
            <li><b>异常检测</b> - 自动检测可疑活动</li>
            <li><b>安全报告</b> - 生成安全状态报告</li>
        </ul>
        
        <h3>⚠️ 安全建议</h3>
        <ul>
            <li><b>生产环境</b> - 强烈建议启用身份验证和SSL</li>
            <li><b>密码策略</b> - 使用复杂密码，定期更换</li>
            <li><b>网络隔离</b> - 在受信任的网络环境中部署</li>
            <li><b>日志审计</b> - 定期检查安全日志</li>
            <li><b>证书管理</b> - 及时更新过期证书</li>
        </ul>
        """)
        
        layout.addWidget(content)
        return widget
    
    def _create_advanced_help_tab(self) -> QWidget:
        """创建高级功能帮助标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        content = QTextBrowser()
        content.setStyleSheet("QTextBrowser { font-size: 14px; }")
        content.setHtml("""
        <h2>🚀 高级功能详细说明</h2>
        
        <h3>🔌 插件系统</h3>
        <ul>
            <li><b>" + t("plugin_directory") + "</b> - " + t("plugins_directory_desc") + "</li>
            <li><b>" + t("plugin_format") + "</b> - " + t("support_python_plugins") + "</li>
            <li><b>" + t("auto_load") + "</b> - " + t("auto_scan_load_plugins") + "</li>
            <li><b>" + t("hot_swap") + "</b> - " + t("runtime_load_unload_plugins") + "</li>
        </ul>
        
        <h4>📦 插件开发</h4>
        <ul>
            <li><b>插件接口</b> - 实现标准的插件接口</li>
            <li><b>生命周期</b> - 支持初始化、执行、清理等阶段</li>
            <li><b>事件系统</b> - 可监听服务器和客户端事件</li>
            <li><b>API访问</b> - 可调用服务器核心API</li>
        </ul>
        
        <h3>📜 脚本执行</h3>
        <ul>
            <li><b>脚本目录</b> - scripts/目录存放脚本文件</li>
            <li><b>支持语言</b> - Python、JavaScript、Shell等</li>
            <li><b>远程执行</b> - 客户端可请求执行服务器脚本</li>
            <li><b>安全沙箱</b> - 脚本在受限环境中执行</li>
        </ul>
        
        <h4>⚡ 脚本功能</h4>
        <ul>
            <li><b>参数传递</b> - 支持向脚本传递参数</li>
            <li><b>结果返回</b> - 脚本执行结果返回给客户端</li>
            <li><b>异步执行</b> - 支持长时间运行的脚本</li>
            <li><b>进度监控</b> - 可监控脚本执行进度</li>
        </ul>
        
        <h3>📁 文件传输</h3>
        <ul>
            <li><b>传输目录</b> - transfers/目录存放传输文件</li>
            <li><b>上传功能</b> - 客户端可上传文件到服务器</li>
            <li><b>下载功能</b> - 客户端可下载服务器文件</li>
            <li><b>断点续传</b> - 支持大文件的断点续传</li>
        </ul>
        
        <h4>🔄 传输管理</h4>
        <ul>
            <li><b>传输队列</b> - 管理多个并发传输任务</li>
            <li><b>进度显示</b> - 实时显示传输进度</li>
            <li><b>完整性校验</b> - 自动验证文件完整性</li>
            <li><b>权限控制</b> - 控制文件访问权限</li>
        </ul>
        
        <h3>💾 会话管理</h3>
        <ul>
            <li><b>会话保存</b> - 自动保存调试会话状态</li>
            <li><b>会话恢复</b> - 可恢复之前的调试会话</li>
            <li><b>会话共享</b> - 多个客户端可共享会话</li>
            <li><b>会话历史</b> - 保存会话操作历史</li>
        </ul>
        
        <h3>📊 性能监控</h3>
        <ul>
            <li><b>实时监控</b> - 监控CPU、内存、网络使用情况</li>
            <li><b>性能图表</b> - 可视化性能数据</li>
            <li><b>性能报告</b> - 生成性能分析报告</li>
            <li><b>性能优化</b> - 根据监控数据自动优化</li>
        </ul>
        
        <h3>🔧 开发工具</h3>
        <ul>
            <li><b>API测试</b> - 内置API测试工具</li>
            <li><b>日志分析</b> - 高级日志分析功能</li>
            <li><b>性能分析</b> - 代码性能分析工具</li>
            <li><b>调试助手</b> - 各种调试辅助工具</li>
        </ul>
        """)
        
        layout.addWidget(content)
        return widget
    
    def _create_troubleshoot_help_tab(self) -> QWidget:
        """创建故障排除帮助标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        content = QTextBrowser()
        content.setStyleSheet("QTextBrowser { font-size: 14px; }")
        content.setHtml("""
        <h2>🔧 故障排除指南</h2>
        
        <h3>🚨 常见问题</h3>
        
        <h4>❌ 服务器启动失败</h4>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr>
                <th>问题</th>
                <th>可能原因</th>
                <th>解决方案</th>
            </tr>
            <tr>
                <td>端口被占用</td>
                <td>其他程序使用了相同端口</td>
                <td>更换端口或关闭占用端口的程序</td>
            </tr>
            <tr>
                <td>权限不足</td>
                <td>没有绑定端口的权限</td>
                <td>以管理员身份运行程序</td>
            </tr>
            <tr>
                <td>防火墙阻止</td>
                <td>防火墙阻止了端口访问</td>
                <td>在防火墙中开放相应端口</td>
            </tr>
            <tr>
                <td>SSL证书错误</td>
                <td>证书文件不存在或无效</td>
                <td>检查证书路径和有效性</td>
            </tr>
        </table>
        
        <h4>🔌 客户端连接问题</h4>
        <ul>
            <li><b>连接超时</b> - 检查网络连接和防火墙设置</li>
            <li><b>认证失败</b> - 确认Token或密码正确</li>
            <li><b>SSL握手失败</b> - 检查SSL证书配置和客户端连接协议</li>
            <li><b>频繁断开</b> - 检查网络稳定性和超时设置</li>
        </ul>
        
        <h4>⚡ 性能问题</h4>
        <ul>
            <li><b>响应缓慢</b> - 增加线程池大小或优化代码</li>
            <li><b>内存占用高</b> - 减少缓冲区大小或清理日志</li>
            <li><b>CPU使用率高</b> - 检查是否有死循环或优化算法</li>
            <li><b>网络拥塞</b> - 调整消息发送频率</li>
        </ul>
        
        <h3>🔍 诊断工具</h3>
        
        <h4>📋 日志分析</h4>
        <ul>
            <li><b>错误日志</b> - 查看ERROR级别的日志信息</li>
            <li><b>警告日志</b> - 查看WARNING级别的日志信息</li>
            <li><b>调试日志</b> - 启用DEBUG级别获取详细信息</li>
            <li><b>日志过滤</b> - 使用关键词过滤相关日志</li>
        </ul>
        
        <h4>🌐 网络测试</h4>
        <ul>
            <li><b>端口扫描</b> - 使用telnet或nc测试端口连通性</li>
            <li><b>防火墙检查</b> - 确认防火墙规则配置</li>
            <li><b>SSL测试</b> - 使用openssl测试SSL连接</li>
            <li><b>网络抓包</b> - 使用Wireshark分析网络流量</li>
        </ul>
        
        <h4>🔐 SSL连接问题解决方案</h4>
        <div style="border: 1px solid #ffeaa7; padding: 10px; border-radius: 5px; margin: 10px 0;">
            <h5>❌ 常见错误：[SSL: HTTP_REQUEST] http request</h5>
            <p><b>问题原因：</b>客户端使用HTTP协议连接启用了SSL的服务器</p>
            <p><b>解决方案：</b></p>
            <ul>
                <li><b>方案1：</b>客户端使用HTTPS协议连接
                    <br>• 将连接地址从 <code>http://127.0.0.1:9009</code> 改为 <code>https://127.0.0.1:9009</code>
                </li>
                <li><b>方案2：</b>服务器端禁用SSL
                    <br>• 在服务器配置中取消勾选"启用SSL加密"
                    <br>• 重启服务器使配置生效
                </li>
                <li><b>方案3：</b>检查SSL证书配置
                    <br>• 确认SSL证书文件路径正确
                    <br>• 验证证书文件有效性
                    <br>• 检查证书是否过期
                </li>
            </ul>
        </div>
        
        <h5>🔧 SSL连接测试命令</h5>
        <div style="border: 1px solid #dee2e6; padding: 10px; border-radius: 5px; font-family: monospace;">
            <p><b>测试SSL连接：</b></p>
            <code>openssl s_client -connect 127.0.0.1:9009 -servername localhost</code>
            <br><br>
            <p><b>测试HTTP连接：</b></p>
            <code>curl -v http://127.0.0.1:9009</code>
            <br><br>
            <p><b>测试HTTPS连接：</b></p>
            <code>curl -v -k https://127.0.0.1:9009</code>
        </div>
        
        <h3>🛠️ 解决步骤</h3>
        
        <h4>1️⃣ 基础检查</h4>
        <ol>
            <li>确认服务器配置正确</li>
            <li>检查网络连接状态</li>
            <li>验证防火墙设置</li>
            <li>查看系统资源使用情况</li>
        </ol>
        
        <h4>2️⃣ 日志分析</h4>
        <ol>
            <li>设置日志级别为DEBUG</li>
            <li>重现问题并收集日志</li>
            <li>分析错误信息和堆栈跟踪</li>
            <li>查找相关的警告信息</li>
        </ol>
        
        <h4>3️⃣ 配置调整</h4>
        <ol>
            <li>根据问题调整相关配置</li>
            <li>重启服务器应用新配置</li>
            <li>测试问题是否解决</li>
            <li>监控系统稳定性</li>
        </ol>
        
        <h3>📞 获取帮助</h3>
        <ul>
            <li><b>查看日志</b> - 详细的错误日志是诊断问题的关键</li>
            <li><b>配置备份</b> - 保存工作配置以便快速恢复</li>
            <li><b>版本信息</b> - 记录软件版本和系统环境</li>
            <li><b>重现步骤</b> - 详细记录问题重现步骤</li>
        </ul>
        
        <h3>🔄 预防措施</h3>
        <ul>
            <li><b>定期备份</b> - 定期备份配置和重要数据</li>
            <li><b>监控告警</b> - 设置系统监控和告警机制</li>
            <li><b>版本管理</b> - 记录配置变更历史</li>
            <li><b>测试环境</b> - 在测试环境中验证配置变更</li>
        </ul>
        """)
        
        layout.addWidget(content)
        return widget
    
    # ==================== 按钮事件处理方法 ====================
    
    def _restart_server(self):
        """重启服务器"""
        if self.is_server_running:
            self._stop_server()
            QTimer.singleShot(1000, self._start_server)  # 延迟1秒后启动
        else:
            self._start_server()
    
    def _clear_logs(self):
        """清空日志"""
        if hasattr(self, 'log_display'):
            self.log_display.clear()
        if hasattr(self, 'log_widget'):
            self.log_widget.clear_logs()
        # 清空存储的日志条目
        if hasattr(self, '_all_log_entries'):
            self._all_log_entries = []
        self.add_log_async("INFO", "日志已清空")
    
    def _export_config(self):
        """导出配置"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出配置", "remote_debug_config.json", "JSON文件 (*.json)"
            )
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config.to_dict(), f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "成功", f"配置已导出到: {file_path}")
                self.add_log_async("INFO", f"配置已导出到: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出配置失败: {str(e)}")
            self.add_log_async("ERROR", f"导出配置失败: {str(e)}")
    
    def _import_config(self):
        """导入配置"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "导入配置", "", "JSON文件 (*.json)"
            )
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.config = IntegratedServerConfig.from_dict(data)
                self._update_config_ui()
                QMessageBox.information(self, "成功", "配置已导入")
                self.add_log_async("INFO", f"配置已从 {file_path} 导入")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入配置失败: {str(e)}")
            self.add_log_async("ERROR", f"导入配置失败: {str(e)}")
    
    def _refresh_clients(self):
        """刷新客户端列表"""
        if self.server:
            clients = self.server.get_all_clients()
            if hasattr(self, 'client_model'):
                self.client_model.update_clients(clients)
            self._update_client_table()
            self.add_log_async("INFO", f"客户端列表已刷新，当前连接数: {len(clients)}")
        else:
            self.add_log_async("WARNING", "服务器未运行，无法刷新客户端列表")
    
    def _disconnect_selected_client(self):
        """断开选中的客户端"""
        if hasattr(self, 'client_table'):
            current_row = self.client_table.currentRow()
            if current_row >= 0:
                client_id_item = self.client_table.item(current_row, 0)
                if client_id_item:
                    client_id = client_id_item.text()
                    if self.server and hasattr(self.server, 'disconnect_client'):
                        self.server.disconnect_client(client_id)
                        self.add_log_async("INFO", f"已断开客户端: {client_id}")
                    else:
                        self.add_log_async("WARNING", "服务器未运行")
            else:
                QMessageBox.information(self, "提示", "请先选择要断开的客户端")
    
    def _disconnect_all_clients(self):
        """断开所有客户端"""
        if self.server and hasattr(self.server, 'get_all_clients'):
            clients = self.server.get_all_clients()
            client_count = len(clients)
            if client_count > 0:
                reply = QMessageBox.question(
                    self, "确认", f"确定要断开所有 {client_count} 个客户端吗？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    for client in clients:
                        self.server.disconnect_client(client.client_id)
                    self.add_log_async("INFO", f"已断开所有 {client_count} 个客户端")
            else:
                QMessageBox.information(self, "提示", "当前没有连接的客户端")
        else:
            self.add_log_async("WARNING", "服务器未运行")
    
    def _broadcast_message(self):
        """广播消息"""
        if self.server and hasattr(self.server, 'get_all_clients'):
            clients = self.server.get_all_clients()
            if len(clients) > 0:
                message, ok = QInputDialog.getText(self, "广播消息", "请输入要广播的消息:")
                if ok and message.strip():
                    try:
                        for client in clients:
                            if hasattr(client, 'send_message'):
                                client.send_message({
                                    'type': 'broadcast',
                                    'message': message.strip(),
                                    'timestamp': time.time()
                                })
                        self.add_log_async("INFO", f"已向 {len(clients)} 个客户端广播消息")
                    except Exception as e:
                        QMessageBox.critical(self, "错误", f"广播消息失败: {str(e)}")
                        self.add_log_async("ERROR", f"广播消息失败: {str(e)}")
            else:
                QMessageBox.information(self, "提示", "当前没有连接的客户端")
        else:
            self.add_log_async("WARNING", "服务器未运行")
    
    def _start_performance_monitor(self):
        """开始性能监控"""
        if hasattr(self, 'performance_monitor'):
            self.performance_monitor.start_monitoring(1000)  # 1秒更新一次，实现实时显示
            self.add_log_async("INFO", "性能监控已启动")
            if hasattr(self, 'start_monitor_btn'):
                self.start_monitor_btn.setEnabled(False)
            if hasattr(self, 'stop_monitor_btn'):
                self.stop_monitor_btn.setEnabled(True)
    
    def _stop_performance_monitor(self):
        """停止性能监控"""
        if hasattr(self, 'performance_monitor'):
            self.performance_monitor.stop_monitoring()
            self.add_log_async("INFO", "性能监控已停止")
            if hasattr(self, 'start_monitor_btn'):
                self.start_monitor_btn.setEnabled(True)
            if hasattr(self, 'stop_monitor_btn'):
                self.stop_monitor_btn.setEnabled(False)
    
    def _clear_performance_stats(self):
        """清空性能统计"""
        if hasattr(self, 'performance_display'):
            self.performance_display.clear()
        if hasattr(self, 'stats_labels'):
            for label in self.stats_labels.values():
                if hasattr(label, 'setText'):
                    label.setText("0")
        self.add_log_async("INFO", "性能统计已清空")
    
    def _save_logs(self):
        """保存日志"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存日志", f"debug_logs_{int(time.time())}.txt", "文本文件 (*.txt)"
            )
            if file_path:
                log_content = ""
                if hasattr(self, 'log_display'):
                    log_content = self.log_display.toPlainText()
                elif hasattr(self, 'log_widget') and hasattr(self.log_widget, 'get_all_logs'):
                    log_content = self.log_widget.get_all_logs()
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                QMessageBox.information(self, "成功", f"日志已保存到: {file_path}")
                self.add_log_async("INFO", f"日志已保存到: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存日志失败: {str(e)}")
            self.add_log_async("ERROR", f"保存日志失败: {str(e)}")
    
    def _on_auto_scroll_toggled(self, checked):
        """处理自动滚动复选框状态变化"""
        if hasattr(self, 'log_widget') and self.log_widget:
            # 更新log_widget内部的复选框状态（阻止信号循环）
            if hasattr(self.log_widget, 'auto_scroll_check'):
                self.log_widget.auto_scroll_check.blockSignals(True)
                self.log_widget.auto_scroll_check.setChecked(checked)
                self.log_widget.auto_scroll_check.blockSignals(False)
            
            # 调用log_widget的处理方法
            if hasattr(self.log_widget, '_on_auto_scroll_toggled'):
                self.log_widget._on_auto_scroll_toggled(checked)
            else:
                # 备用方案：直接保存配置和滚动
                if hasattr(self.log_widget, '_save_auto_scroll_config'):
                    self.log_widget._save_auto_scroll_config(checked)
                if checked:
                    QTimer.singleShot(10, self.log_widget.scroll_to_bottom)
    
    def _save_settings_manually(self):
        """手动保存当前设置"""
        try:
            from core.settings import load_settings, save_settings
            settings = load_settings()
            
            # 获取当前自动滚动状态
            current_auto_scroll = self.auto_scroll_checkbox.isChecked()
            settings['remote_debug.auto_scroll'] = current_auto_scroll
            
            # 同时更新remote_debug节点中的auto_scroll配置
            if 'remote_debug' not in settings:
                settings['remote_debug'] = {}
            settings['remote_debug']['auto_scroll'] = current_auto_scroll
            
            # 更新当前配置对象
            self.config.auto_scroll = current_auto_scroll
            
            # 保存设置
            save_settings(settings)
            
            # 显示成功消息
            QMessageBox.information(self, "保存成功", "设置已成功保存！")
            
        except Exception as e:
            # 显示错误消息
            QMessageBox.critical(self, "保存失败", f"保存设置时发生错误：{str(e)}")
            print(f"手动保存设置失败: {e}")
    
    def _filter_logs(self):
        """过滤日志显示"""
        if not hasattr(self, 'log_display') or not self.log_display:
            return
            
        # 获取过滤条件
        filter_text = ""
        if hasattr(self, 'log_filter_edit'):
            filter_text = self.log_filter_edit.text().lower()
            
        selected_level = "全部"
        if hasattr(self, 'log_level_combo'):
            selected_level = self.log_level_combo.currentText()
            
        # 定义日志级别优先级
        level_priority = {
            "调试": 0,
            "信息": 1,
            "警告": 2,
            "错误": 3,
            "严重": 4
        }
        
        # 如果选择"全部"，则显示所有级别的日志
        if selected_level == "全部":
            min_priority = -1  # 显示所有级别
        else:
            min_priority = level_priority.get(selected_level, 1)
        
        # 获取所有日志内容并重新过滤显示
        if hasattr(self, '_all_log_entries'):
            # 如果有存储的日志条目，使用它们
            filtered_content = ""
            for entry in self._all_log_entries:
                entry_level = entry.get('level', 'INFO')
                entry_message = entry.get('message', '')
                entry_timestamp = entry.get('timestamp', '')
                
                # 检查级别过滤
                entry_priority = level_priority.get(entry_level, 1)
                if entry_priority < min_priority:
                    continue
                    
                # 检查文本过滤
                if filter_text and filter_text not in entry_message.lower():
                    continue
                    
                # 添加到过滤后的内容，使用主题自适应颜色
                color = self._get_level_color(entry_level)
                formatted_message = f'<span style="color: {color}">[{entry_timestamp}] [{entry_level}] {entry_message}</span>'
                filtered_content += formatted_message + "<br>"
                
            self.log_display.setHtml(filtered_content)
            
            # 检查自动滚动设置并滚动到底部
            if hasattr(self, 'auto_scroll_checkbox') and self.auto_scroll_checkbox.isChecked():
                # 使用QTimer确保HTML渲染完成后再滚动
                QTimer.singleShot(10, lambda: self.log_display.verticalScrollBar().setValue(
                    self.log_display.verticalScrollBar().maximum()
                ))
        else:
            # 如果没有存储的日志条目，初始化存储
            self._all_log_entries = []
    
    def _update_client_table(self):
        """更新客户端表格"""
        if not hasattr(self, 'client_table') or not self.server:
            return
            
        clients = self.server.get_all_clients() if hasattr(self.server, 'get_all_clients') else []
        self.client_table.setRowCount(len(clients))
        
        # 客户端状态中文映射
        status_texts = {
            "connecting": "连接中",
            "connected": "已连接",
            "authenticated": "已认证",
            "disconnected": "已断开",
            "error": "错误",
            "Unknown": "未知"
        }
        
        for row, client in enumerate(clients):
            # 客户端ID
            self.client_table.setItem(row, 0, QTableWidgetItem(str(getattr(client, 'client_id', '未知'))))
            # IP地址
            address = getattr(client, 'address', ('未知', 0))
            if isinstance(address, tuple) and len(address) >= 2:
                address_str = f"{address[0]}:{address[1]}"
            else:
                address_str = str(address)
            self.client_table.setItem(row, 1, QTableWidgetItem(address_str))
            # 连接时间
            connect_time = getattr(client, 'connect_time', None)
            if connect_time:
                time_str = time.strftime('%H:%M:%S', time.localtime(connect_time))
            else:
                time_str = '未知'
            self.client_table.setItem(row, 2, QTableWidgetItem(time_str))
            # 状态
            state = getattr(client, 'state', None)
            if hasattr(state, 'value'):
                status = state.value
            else:
                status = str(state) if state else 'Unknown'
            chinese_status = status_texts.get(status, status)
            self.client_table.setItem(row, 3, QTableWidgetItem(str(chinese_status)))
            # 消息数
            msg_count = getattr(client, 'commands_sent', 0)
            self.client_table.setItem(row, 4, QTableWidgetItem(str(msg_count)))
            # 操作按钮
            self.client_table.setItem(row, 5, QTableWidgetItem("断开"))
    
    # ==================== Token管理方法 ====================
    
    def _on_auth_option_changed(self, checked: bool):
        """身份验证选项变化处理"""
        if hasattr(self, 'auth_token_frame'):
            self.auth_token_frame.setVisible(checked)
            
        if checked:
            # 启用身份验证时，确保有Token
            self._update_auth_token_display()
        else:
            # 禁用身份验证时，清空Token显示
            if hasattr(self, 'auth_token_edit'):
                self.auth_token_edit.clear()
    
    def _update_auth_token_display(self):
        """更新Token显示"""
        if not hasattr(self, 'auth_token_edit'):
            return
            
        if self.config.enable_auth:
            if not self.config.auth_token:
                # 如果没有Token，生成一个新的
                if self.server:
                    self.config.auth_token = self.server._generate_secure_token()
                    self.server._save_auth_token()
                else:
                    # 如果服务器未启动，临时生成一个Token
                    import secrets
                    import string
                    alphabet = string.ascii_letters + string.digits + '_-'
                    self.config.auth_token = ''.join(secrets.choice(alphabet) for _ in range(64))
            
            self.auth_token_edit.setText(self.config.auth_token)
        else:
            self.auth_token_edit.clear()
    
    def _copy_auth_token(self):
        """复制认证Token到剪贴板"""
        if hasattr(self, 'auth_token_edit') and self.auth_token_edit.text():
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(self.auth_token_edit.text())
            QMessageBox.information(self, "成功", "认证Token已复制到剪贴板")
            self.add_log_async("INFO", "认证Token已复制到剪贴板")
        else:
            QMessageBox.warning(self, "警告", "没有可复制的Token")
    
    def _regenerate_auth_token(self):
        """重新生成认证Token"""
        reply = QMessageBox.question(
            self, "确认操作", 
            "重新生成Token将使所有已连接的客户端失效，确定要继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.server and self.is_server_running:
                # 服务器运行时，使用服务器的方法
                new_token = self.server.regenerate_auth_token()
                self.config.auth_token = new_token
            else:
                # 服务器未运行时，直接生成新Token
                import secrets
                import string
                alphabet = string.ascii_letters + string.digits + '_-'
                self.config.auth_token = ''.join(secrets.choice(alphabet) for _ in range(64))
                
            self._update_auth_token_display()
            self._save_config()
            QMessageBox.information(self, "成功", "认证Token已重新生成")
            self.add_log_async("INFO", "认证Token已重新生成")
    
    def _show_token_info(self):
        """显示Token详细信息"""
        if self.server and self.is_server_running:
            token_info = self.server.get_auth_token_info()
        else:
            # 服务器未运行时，显示基本信息
            token_info = {
                "status": "valid" if self.config.auth_token else "no_token",
                "message": "服务器未运行，无法获取详细信息"
            }
        
        info_text = f"""认证Token信息：

状态: {token_info.get('status', '未知')}
"""
        
        if 'created_at' in token_info:
            import time
            created_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(token_info['created_at']))
            info_text += f"创建时间: {created_time}\n"
            
        if 'expires_at' in token_info:
            expires_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(token_info['expires_at']))
            info_text += f"过期时间: {expires_time}\n"
            
        if 'days_remaining' in token_info:
            info_text += f"剩余天数: {token_info['days_remaining']:.1f}天\n"
            
        if 'version' in token_info:
            info_text += f"版本: {token_info['version']}\n"
            
        if 'message' in token_info:
            info_text += f"\n说明: {token_info['message']}"
        
        QMessageBox.information(self, "Token信息", info_text)
    
    def _save_config_with_message(self):
        """保存配置并显示友好提示"""
        try:
            # 先从UI控件获取当前配置状态并更新到config对象
            self.config.host = self.host_edit.text()
            self.config.port = self.port_edit.value()
            self.config.password = self.password_edit.text()
            self.config.max_clients = self.max_clients_spin.value()
            
            # 保存基础配置项
            if hasattr(self, 'timeout_spin'):
                self.config.timeout = self.timeout_spin.value()
            if hasattr(self, 'auth_token_edit'):
                self.config.auth_token = self.auth_token_edit.text()
            if hasattr(self, 'ssl_cert_edit'):
                self.config.ssl_cert_path = self.ssl_cert_edit.text()
            if hasattr(self, 'ssl_key_edit'):
                self.config.ssl_key_path = self.ssl_key_edit.text()
            if hasattr(self, 'log_level_combo'):
                self.config.log_level = self.log_level_combo.currentText()
            
            # 保存用户勾选和没勾选的启用身份验证、启用SSL加密、自动启动设置
            self.config.enable_auth = self.auth_check.isChecked()
            self.config.enable_ssl = self.ssl_check.isChecked()
            self.config.auto_start = self.auto_start_check.isChecked()
            
            # 保存Web界面配置选项
            if hasattr(self, 'web_interface_check'):
                self.config.enable_web_interface = self.web_interface_check.isChecked()
            if hasattr(self, 'web_host_edit'):
                self.config.web_host = self.web_host_edit.text()
            if hasattr(self, 'web_port_spin'):
                self.config.web_port = self.web_port_spin.value()
            if hasattr(self, 'web_static_dir_edit'):
                self.config.web_static_dir = self.web_static_dir_edit.text()
            if hasattr(self, 'websocket_check'):
                self.config.enable_websocket = self.websocket_check.isChecked()
            if hasattr(self, 'web_auth_check'):
                self.config.web_auth_required = self.web_auth_check.isChecked()
            if hasattr(self, 'websocket_port_spin'):
                self.config.websocket_port = self.websocket_port_spin.value()
            
            # 检查高级配置控件是否存在并更新
            if hasattr(self, 'pool_size_edit'):
                self.config.connection_pool_size = self.pool_size_edit.value()
            if hasattr(self, 'buffer_size_edit'):
                self.config.message_buffer_size = self.buffer_size_edit.value()
            if hasattr(self, 'log_cache_size_edit'):
                self.config.log_cache_size = self.log_cache_size_edit.value()
            if hasattr(self, 'thread_pool_edit'):
                self.config.thread_pool_size = self.thread_pool_edit.value()
            if hasattr(self, 'update_interval_spin'):
                self.config.update_interval = self.update_interval_spin.value()
            
            # 保存目录配置
            if hasattr(self, 'plugin_dir_edit'):
                self.config.plugin_dir = self.plugin_dir_edit.text()
            if hasattr(self, 'script_dir_edit'):
                self.config.script_dir = self.script_dir_edit.text()
            if hasattr(self, 'transfer_dir_edit'):
                self.config.transfer_dir = self.transfer_dir_edit.text()
            if hasattr(self, 'session_dir_edit'):
                self.config.session_dir = self.session_dir_edit.text()
            
            # 保存UI设置
            if hasattr(self, 'auto_scroll_check'):
                self.config.auto_scroll = self.auto_scroll_check.isChecked()
                
            # 保存功能开关
            if hasattr(self, 'feature_config'):
                self.config.enabled_features = self.feature_config.get_enabled_features()
            
            # 保存配置到文件
            self._save_config()
            
            # 显示成功提示
            QMessageBox.information(
                self, 
                "保存成功", 
                "配置已成功保存到文件！\n\n配置文件位置: settings.json (remote_debug节点)\n\n✅ 已保存的设置包括:\n• 启用身份验证: {}\n• 启用SSL加密: {}\n• 自动启动: {}\n\n注意: 部分配置可能需要重启服务器后生效。".format(
                    "是" if self.config.enable_auth else "否",
                    "是" if self.config.enable_ssl else "否",
                    "是" if self.config.auto_start else "否"
                )
            )
            
            # 记录日志
            self.add_log_async("INFO", f"远程调试配置已手动保存 - 身份验证:{self.config.enable_auth}, SSL:{self.config.enable_ssl}, 自动启动:{self.config.auto_start}")
            
        except Exception as e:
            # 显示错误提示
            QMessageBox.critical(
                self, 
                "保存失败", 
                f"配置保存失败！\n\n错误信息: {str(e)}\n\n请检查文件权限或磁盘空间。"
            )
            
            # 记录错误日志
            self.add_log_async("ERROR", f"配置保存失败: {str(e)}")
    
    def _view_security_logs(self):
        """查看安全日志"""
        try:
            import os
            from datetime import datetime
            
            # 获取今天的安全日志文件
            today = datetime.now().strftime('%Y-%m-%d')
            security_log_path = os.path.join("logs", "security", f"security_{today}.log")
            
            if not os.path.exists(security_log_path):
                QMessageBox.information(self, "提示", "今天还没有安全日志文件")
                return
            
            # 创建安全日志查看对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("安全日志查看器")
            dialog.setModal(True)
            dialog.resize(800, 600)
            
            layout = QVBoxLayout(dialog)
            
            # 添加说明标签
            info_label = QLabel(f"安全日志文件: {security_log_path}")
            info_label.setStyleSheet("QLabel { font-weight: bold; color: #2196F3; }")
            layout.addWidget(info_label)
            
            # 创建文本浏览器显示日志内容
            log_browser = QTextBrowser()
            log_browser.setFont(QFont("Consolas", 9))
            
            # 读取并显示安全日志
            with open(security_log_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 格式化JSON日志以便阅读
            formatted_content = ""
            for line in content.strip().split('\n'):
                if line.strip():
                    try:
                        import json
                        log_data = json.loads(line)
                        
                        # 格式化显示
                        formatted_content += f"时间: {log_data.get('timestamp', 'N/A')}\n"
                        formatted_content += f"级别: {log_data.get('level', 'N/A')}\n"
                        formatted_content += f"消息: {log_data.get('message', 'N/A')}\n"
                        
                        if 'event_id' in log_data:
                            formatted_content += f"事件ID: {log_data['event_id']}\n"
                        
                        if 'server_info' in log_data:
                            server_info = log_data['server_info']
                            formatted_content += f"服务器: {server_info.get('host', 'N/A')}:{server_info.get('port', 'N/A')}\n"
                            formatted_content += f"运行时间: {server_info.get('uptime', 'N/A')}秒\n"
                        
                        if 'client_info' in log_data:
                            client_info = log_data['client_info']
                            formatted_content += f"客户端数量: {client_info.get('total_clients', 0)}\n"
                            formatted_content += f"认证客户端: {client_info.get('authenticated_clients', 0)}\n"
                        
                        if 'system_info' in log_data:
                            system_info = log_data['system_info']
                            formatted_content += f"系统: {system_info.get('platform', 'N/A')} {system_info.get('architecture', 'N/A')}\n"
                        
                        formatted_content += "-" * 80 + "\n\n"
                        
                    except json.JSONDecodeError:
                        # 如果不是JSON格式，直接显示
                        formatted_content += line + "\n\n"
            
            log_browser.setPlainText(formatted_content)
            layout.addWidget(log_browser)
            
            # 添加按钮
            button_layout = QHBoxLayout()
            
            refresh_btn = QPushButton("刷新")
            refresh_btn.clicked.connect(lambda: self._refresh_security_log(log_browser, security_log_path))
            
            export_btn = QPushButton("导出")
            export_btn.clicked.connect(lambda: self._export_security_log(security_log_path))
            
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.close)
            
            button_layout.addWidget(refresh_btn)
            button_layout.addWidget(export_btn)
            button_layout.addStretch()
            button_layout.addWidget(close_btn)
            
            layout.addLayout(button_layout)
            
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"查看安全日志失败: {str(e)}")
            self.add_log_async("ERROR", f"查看安全日志失败: {str(e)}")
    
    def _open_log_management(self):
        """打开日志管理对话框"""
        try:
            from .log_management_dialog import LogManagementDialog
            dialog = LogManagementDialog(self)
            dialog.show()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开日志管理对话框失败: {str(e)}")
            if hasattr(self, 'log_widget'):
                self.log_widget.add_log_async("ERROR", f"打开日志管理对话框失败: {str(e)}")
    
    def _refresh_security_log(self, log_browser, log_path):
        """刷新安全日志显示"""
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 重新格式化内容
            formatted_content = ""
            for line in content.strip().split('\n'):
                if line.strip():
                    try:
                        import json
                        log_data = json.loads(line)
                        
                        formatted_content += f"时间: {log_data.get('timestamp', 'N/A')}\n"
                        formatted_content += f"级别: {log_data.get('level', 'N/A')}\n"
                        formatted_content += f"消息: {log_data.get('message', 'N/A')}\n"
                        
                        if 'event_id' in log_data:
                            formatted_content += f"事件ID: {log_data['event_id']}\n"
                        
                        if 'server_info' in log_data:
                            server_info = log_data['server_info']
                            formatted_content += f"服务器: {server_info.get('host', 'N/A')}:{server_info.get('port', 'N/A')}\n"
                            formatted_content += f"运行时间: {server_info.get('uptime', 'N/A')}秒\n"
                        
                        formatted_content += "-" * 80 + "\n\n"
                        
                    except json.JSONDecodeError:
                        formatted_content += line + "\n\n"
            
            log_browser.setPlainText(formatted_content)
            
        except Exception as e:
            QMessageBox.warning(None, "警告", f"刷新日志失败: {str(e)}")
    
    def _export_security_log(self, log_path):
        """导出安全日志"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出安全日志", f"security_log_export_{int(time.time())}.txt", "文本文件 (*.txt)"
            )
            if file_path:
                import shutil
                shutil.copy2(log_path, file_path)
                QMessageBox.information(self, "成功", f"安全日志已导出到: {file_path}")
                self.add_log_async("INFO", f"安全日志已导出到: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出安全日志失败: {str(e)}")
            self.add_log_async("ERROR", f"导出安全日志失败: {str(e)}")
    
    def _open_web_interface(self):
        """打开Web界面"""
        try:
            self.add_log_async("DEBUG", "=== 开始打开Web界面流程 ===")
            self.add_log_async("DEBUG", "点击了打开Web界面按钮")
            
            # 记录当前时间戳
            import time
            start_time = time.time()
            self.add_log_async("DEBUG", f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")
            
            # 首先检查Web界面是否启用
            self.add_log_async("DEBUG", f"检查Web界面配置状态: enable_web_interface = {self.config.enable_web_interface}")
            if not self.config.enable_web_interface:
                self.add_log_async("WARNING", "Web界面功能未启用")
                QMessageBox.information(self, "提示", "Web界面功能未启用，请在配置中勾选'启用Web界面'选项后重新启动服务器")
                return
            
            self.add_log_async("DEBUG", "✓ Web界面功能已启用")
            
            # 记录详细的配置信息
            self.add_log_async("DEBUG", f"Web配置详情:")
            self.add_log_async("DEBUG", f"  - Web端口: {getattr(self.config, 'web_port', '未设置')}")
            self.add_log_async("DEBUG", f"  - WebSocket端口: {getattr(self.config, 'websocket_port', '未设置')}")
            self.add_log_async("DEBUG", f"  - Web主机: {getattr(self.config, 'web_host', '未设置')}")
            
            # 检查UI控件状态
            if hasattr(self, 'web_interface_check'):
                self.add_log_async("DEBUG", f"UI控件状态: Web界面复选框已勾选 = {self.web_interface_check.isChecked()}")
            if hasattr(self, 'open_web_btn'):
                self.add_log_async("DEBUG", f"UI控件状态: Web界面按钮已启用 = {self.open_web_btn.isEnabled()}")
            
            # 检查服务器状态
            self.add_log_async("DEBUG", f"检查服务器对象: server = {self.server}")
            if not self.server:
                self.add_log_async("ERROR", "✗ 服务器对象不存在")
                QMessageBox.warning(self, "警告", "服务器对象不存在，请先启动远程调试服务器")
                return
                
            self.add_log_async("DEBUG", f"✓ 服务器对象存在: {type(self.server).__name__}")
            
            # 检查服务器是否运行
            self.add_log_async("DEBUG", f"检查服务器运行状态: is_server_running = {self.is_server_running}")
            if not self.is_server_running:
                self.add_log_async("ERROR", "✗ 服务器未运行")
                QMessageBox.warning(self, "警告", "服务器未运行，请先启动远程调试服务器")
                return
            
            self.add_log_async("DEBUG", "✓ 服务器正在运行")
            
            # 检查服务器启动时间
            if hasattr(self, 'start_time') and self.start_time:
                uptime = time.time() - self.start_time.timestamp()
                self.add_log_async("DEBUG", f"服务器运行时长: {uptime:.1f}秒")
            
            # 检查Web服务器属性
            self.add_log_async("DEBUG", f"检查Web服务器属性: hasattr(server, 'web_server') = {hasattr(self.server, 'web_server')}")
            if not hasattr(self.server, 'web_server'):
                self.add_log_async("ERROR", "✗ 服务器没有web_server属性")
                # 列出服务器对象的所有属性
                server_attrs = [attr for attr in dir(self.server) if not attr.startswith('_')]
                self.add_log_async("DEBUG", f"服务器可用属性: {server_attrs}")
                QMessageBox.warning(self, "警告", "Web服务器组件未初始化，请检查服务器配置")
                return
                
            self.add_log_async("DEBUG", f"✓ 服务器具有web_server属性")
            
            # 检查Web服务器对象
            self.add_log_async("DEBUG", f"检查Web服务器对象: web_server = {self.server.web_server}")
            if not self.server.web_server:
                self.add_log_async("ERROR", "✗ web_server对象为None")
                QMessageBox.warning(self, "警告", "Web服务器未创建，请检查Web界面配置")
                return
                
            self.add_log_async("DEBUG", f"✓ Web服务器对象存在: {type(self.server.web_server).__name__}")
            
            # 检查Web服务器的详细信息
            try:
                web_server_attrs = [attr for attr in dir(self.server.web_server) if not attr.startswith('_')]
                self.add_log_async("DEBUG", f"Web服务器可用方法: {web_server_attrs}")
            except Exception as attr_e:
                self.add_log_async("DEBUG", f"无法获取Web服务器属性: {attr_e}")
            
            # 检查Web服务器运行状态
            self.add_log_async("DEBUG", "检查Web服务器运行状态...")
            try:
                is_running = self.server.web_server.is_running
                self.add_log_async("DEBUG", f"Web服务器运行状态检查结果: {is_running}")
            except Exception as status_e:
                self.add_log_async("ERROR", f"检查Web服务器状态时出错: {status_e}")
                is_running = False
            
            if not is_running:
                self.add_log_async("ERROR", "✗ Web服务器未运行")
                QMessageBox.warning(self, "警告", "Web服务器未运行，请检查服务器启动状态和Web界面配置")
                return
            
            self.add_log_async("DEBUG", "✓ Web服务器正在运行")
            
            # 获取URL
            self.add_log_async("DEBUG", "尝试获取Web服务器URL...")
            try:
                web_url = self.server.web_server.get_server_url()
                self.add_log_async("DEBUG", f"URL获取结果: {web_url}")
            except Exception as url_e:
                self.add_log_async("ERROR", f"获取URL时出错: {url_e}")
                web_url = None
            
            if web_url:
                self.add_log_async("DEBUG", f"✓ 成功获取Web URL: {web_url}")
                
                # 检查浏览器可用性
                import webbrowser
                self.add_log_async("DEBUG", "检查系统浏览器...")
                try:
                    # 获取默认浏览器信息
                    browser_name = webbrowser.get().name if hasattr(webbrowser.get(), 'name') else '未知'
                    self.add_log_async("DEBUG", f"默认浏览器: {browser_name}")
                except Exception as browser_e:
                    self.add_log_async("DEBUG", f"无法获取浏览器信息: {browser_e}")
                
                # 尝试打开浏览器
                self.add_log_async("DEBUG", f"尝试打开浏览器访问: {web_url}")
                try:
                    result = webbrowser.open(web_url)
                    self.add_log_async("DEBUG", f"浏览器打开操作结果: {result}")
                    
                    if result:
                        self.add_log_async("INFO", f"✓ 成功打开Web界面: {web_url}")
                        # 记录完成时间
                        end_time = time.time()
                        duration = end_time - start_time
                        self.add_log_async("DEBUG", f"操作完成，耗时: {duration:.3f}秒")
                    else:
                        self.add_log_async("WARNING", "浏览器打开操作返回False，可能未成功打开")
                        
                except Exception as open_e:
                    self.add_log_async("ERROR", f"打开浏览器时出错: {open_e}")
                    QMessageBox.critical(self, "错误", f"无法打开浏览器: {open_e}")
                    
            else:
                self.add_log_async("ERROR", "✗ 无法获取Web服务器URL")
                QMessageBox.warning(self, "警告", "Web服务器未正确启动，无法获取URL")
            
            self.add_log_async("DEBUG", "=== Web界面打开流程结束 ===")
                
        except Exception as e:
            self.add_log_async("ERROR", f"✗ 打开Web界面失败: {e}")
            import traceback
            error_details = traceback.format_exc()
            self.add_log_async("ERROR", f"详细错误堆栈:\n{error_details}")
            
            # 记录系统环境信息
            try:
                import sys
                import platform
                self.add_log_async("DEBUG", f"系统信息: {platform.system()} {platform.release()}")
                self.add_log_async("DEBUG", f"Python版本: {sys.version}")
            except:
                pass
                
            QMessageBox.critical(self, "错误", f"打开Web界面失败: {e}")
    
    def _get_level_color(self, level: str) -> str:
        """获取日志级别对应的颜色（主题自适应）"""
        try:
            is_dark = self._is_dark_theme()
            
            if is_dark:
                # 深色主题颜色
                color_map = {
                    '调试': '#888888',    # 灰色
                    '信息': '#4FC3F7',     # 浅蓝色
                    '警告': '#FFB74D',  # 橙色
                    '错误': '#F44336',    # 红色
                    '严重': '#E91E63'  # 粉红色
                }
            else:
                # 浅色主题颜色
                color_map = {
                    '调试': '#666666',    # 深灰色
                    '信息': '#1976D2',     # 蓝色
                    '警告': '#F57C00',  # 深橙色
                    '错误': '#D32F2F',    # 深红色
                    '严重': '#C2185B'  # 深粉红色
                }
            
            return color_map.get(level, '#000000' if not is_dark else '#FFFFFF')
        except Exception:
            # 发生错误时返回默认颜色
            return '#000000'
    
    def _is_dark_theme(self) -> bool:
        """检测当前是否为深色主题"""
        try:
            # 方法1: 检查应用程序调色板
            app = QApplication.instance()
            if app:
                palette = app.palette()
                window_color = palette.color(QPalette.ColorRole.Window)
                # 如果窗口背景颜色较暗，则认为是深色主题
                if window_color.lightness() < 128:
                    return True
            
            # 方法2: 检查文本颜色
            if app:
                palette = app.palette()
                text_color = palette.color(QPalette.ColorRole.WindowText)
                # 如果文本颜色较亮，则认为是深色主题
                if text_color.lightness() > 128:
                    return True
            
            # 方法3: 检查按钮背景颜色
            if app:
                palette = app.palette()
                button_color = palette.color(QPalette.ColorRole.Button)
                if button_color.lightness() < 128:
                    return True
            
            return False
        except Exception:
            # 发生错误时默认为浅色主题
            return False
    
    def _on_theme_changed(self):
        """主题变化时的处理函数"""
        try:
            # 重新应用日志过滤以更新颜色
            if hasattr(self, 'log_widget') and hasattr(self.log_widget, '_filter_logs'):
                self.log_widget._filter_logs()
        except Exception as e:
            print(f"主题切换处理失败: {e}")
            
    def closeEvent(self, event):
        """关闭事件"""
        if self.is_server_running:
            reply = QMessageBox.question(
                self, "确认关闭", 
                "服务器正在运行，确定要关闭吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self._stop_server()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
    
    def _validate_password(self):
        """验证密码强度"""
        password = self.password_edit.text()
        if not password:
            self.password_edit.setStyleSheet("border: 1px solid gray;")
            return
            
        is_valid, message = validate_password_strength(password)
        if is_valid:
            self.password_edit.setStyleSheet("border: 2px solid green;")
            self.password_edit.setToolTip("密码强度符合要求")
        else:
            self.password_edit.setStyleSheet("border: 2px solid red;")
            self.password_edit.setToolTip(f"密码强度不足: {message}")
    
    def _generate_secure_auth_token(self):
        """生成安全的认证令牌"""
        try:
            token = generate_secure_token(32)
            self.config.auth_token = token
            self.add_log_async("INFO", "已生成新的安全认证令牌")
            QMessageBox.information(self, "令牌生成", "已生成新的安全认证令牌！\n请妥善保管此令牌。")
        except Exception as e:
            self.add_log_async("ERROR", f"生成认证令牌失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"生成认证令牌失败:\n{str(e)}")

    def _open_advanced_test_client(self):
        """打开高级测试客户端"""
        try:
            # 创建测试配置，使用当前服务器配置
            config = TestConfig(
                host=self.config.host,
                port=self.config.port,
                use_ssl=self.config.enable_ssl,
                timeout=5.0,
                retry_count=3,
                retry_delay=1.0,
                concurrent_connections=1,
                test_duration=0,  # 单次测试
                message_interval=1.0,
                custom_commands=["ping", "status", "help"],
                auth_token="",
                user_agent="AdvancedTestClient/1.0"
            )
            
            # 创建并显示高级测试客户端对话框
            dialog = AdvancedTestClientDialog(self, config)
            dialog.exec()
            
        except Exception as e:
            self.add_log_async("ERROR", f"打开高级测试客户端失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"无法打开高级测试客户端:\n{str(e)}")


# ==================== 主函数 ====================

def show_integrated_remote_debug():
    """显示集成远程调试窗口"""
    dialog = IntegratedRemoteDebugWidget()
    dialog.exec()