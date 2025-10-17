#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
远程调试Web服务器模块

提供HTTP web界面来管理远程调试服务器：
- 客户端连接管理
- 实时日志查看
- 服务器配置
- 性能监控
"""

import json
import threading
import time
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import socketserver
import websockets
import asyncio
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import QObject, pyqtSignal


class WebServerConfig:
    """Web服务器配置"""
    def __init__(self):
        self.enabled = False
        self.host = "127.0.0.1"
        self.port = 8080
        self.websocket_port = 8081
        self.enable_cors = True
        self.static_dir = "web_static"
        self.template_dir = "web_templates"
        self.max_connections = 50
        self.auth_required = False
        self.auth_token = ""

    def to_dict(self) -> dict:
        return {
            'enabled': self.enabled,
            'host': self.host,
            'port': self.port,
            'websocket_port': self.websocket_port,
            'enable_cors': self.enable_cors,
            'static_dir': self.static_dir,
            'template_dir': self.template_dir,
            'max_connections': self.max_connections,
            'auth_required': self.auth_required,
            'auth_token': self.auth_token
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'WebServerConfig':
        config = cls()
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return config


class DebugWebHandler(BaseHTTPRequestHandler):
    """Web请求处理器"""
    
    def __init__(self, *args, debug_server=None, dev_tools_panel=None, **kwargs):
        self.debug_server = debug_server
        self.dev_tools_panel = dev_tools_panel
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """处理GET请求"""
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            query_params = parse_qs(parsed_path.query)
            
            # 路由处理
            if path == '/' or path == '/index.html':
                self._serve_main_page()
            elif path == '/client_management':
                self._serve_client_management_page()
            elif path == '/client':
                self._serve_client_detail_page()
            elif path == '/websocket_test':
                self._serve_websocket_test_page()
            elif path == '/api/clients':
                self._api_get_clients()
            elif path.startswith('/api/client/'):
                client_id = path.split('/')[-1]
                self._api_get_client_detail(client_id)
            elif path == '/api/server/status':
                self._api_get_server_status()
            elif path == '/api/server/stats':
                self._api_get_server_stats()
            elif path == '/api/logs':
                self._api_get_logs(query_params)
            elif path == '/api/system':
                self._api_get_system_info()
            elif path.startswith('/static/'):
                self._serve_static_file(path)
            else:
                self._send_404()
                
        except Exception as e:
            self._send_error_response(500, f"内部服务器错误: {str(e)}")
    
    def do_POST(self):
        """处理POST请求"""
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            
            # 设置CORS头
            self._set_cors_headers()
            
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            try:
                request_data = json.loads(post_data) if post_data else {}
            except json.JSONDecodeError:
                self._send_error_response(400, "无效的JSON数据")
                return
            
            # 路由处理
            if path == '/api/clients/disconnect':
                self._api_disconnect_client(request_data)
            elif path == '/api/server/start':
                self._api_start_server()
            elif path == '/api/server/stop':
                self._api_stop_server()
            elif path == '/api/server/restart':
                self._api_restart_server()
            elif path == '/api/server/config':
                self._api_update_config(request_data)
            elif path == '/api/command/send':
                self._api_send_command(request_data)
            elif path == '/api/logs/clear':
                self._api_clear_logs()
            else:
                self._send_404()
                
        except Exception as e:
            self._send_error_response(500, f"内部服务器错误: {str(e)}")
    
    def do_OPTIONS(self):
        """处理OPTIONS请求（CORS预检）"""
        self._set_cors_headers()
        self.send_response(200)
        self.end_headers()
    
    def _set_cors_headers(self):
        """设置CORS头"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    
    def _serve_main_page(self):
        """提供主页面"""
        html_content = self._get_main_page_html()
        content_bytes = html_content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content_bytes)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(content_bytes)
    
    def _serve_client_detail_page(self):
        """提供客户端详情页面"""
        html_content = self._get_client_detail_page_html()
        content_bytes = html_content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content_bytes)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(content_bytes)
    
    def _serve_client_management_page(self):
        """提供客户端管理页面"""
        html_content = self._get_client_management_page_html()
        content_bytes = html_content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content_bytes)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(content_bytes)
    
    def _serve_websocket_test_page(self):
        """提供WebSocket测试页面"""
        html_content = self._get_websocket_test_page_html()
        content_bytes = html_content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content_bytes)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(content_bytes)
    
    def _serve_static_file(self, path: str):
        """提供静态文件"""
        # 简单的静态文件服务（生产环境应使用专门的静态文件服务器）
        # 构建正确的文件路径
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录
        file_path = os.path.join(base_dir, path[1:])  # 移除开头的'/'
        if os.path.exists(file_path) and os.path.isfile(file_path):
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # 根据文件扩展名设置Content-Type
            content_type = 'text/plain'
            if path.endswith('.css'):
                content_type = 'text/css'
            elif path.endswith('.js'):
                content_type = 'application/javascript'
            elif path.endswith('.png'):
                content_type = 'image/png'
            elif path.endswith('.jpg') or path.endswith('.jpeg'):
                content_type = 'image/jpeg'
            
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.end_headers()
            self.wfile.write(content)
        else:
            self._send_404()
    
    def _api_get_clients(self):
        """获取客户端列表API"""
        try:
            if not self.debug_server:
                # 返回空的客户端列表用于演示
                self._send_json_response({'clients': []})
                return
            
            # 尝试多种方式获取客户端列表
            clients = []
            if hasattr(self.debug_server, 'get_all_clients'):
                clients = self.debug_server.get_all_clients()
            elif hasattr(self.debug_server, 'connection_pool') and self.debug_server.connection_pool:
                clients = list(self.debug_server.connection_pool.active_connections.values())
            elif hasattr(self.debug_server, 'clients'):
                clients = list(self.debug_server.clients.values())
            
            client_data = []
            
            for client in clients:
                try:
                    # 安全地获取客户端信息，处理可能缺失的属性
                    client_id = getattr(client, 'client_id', getattr(client, 'id', 'unknown'))
                    address = getattr(client, 'address', ('unknown', 0))
                    if isinstance(address, tuple) and len(address) >= 2:
                        address_str = f"{address[0]}:{address[1]}"
                    else:
                        address_str = str(address)
                    
                    connect_time = getattr(client, 'connect_time', time.time())
                    if isinstance(connect_time, (int, float)):
                        connect_time_str = datetime.fromtimestamp(connect_time).isoformat()
                    else:
                        connect_time_str = str(connect_time)
                    
                    # 获取状态信息
                    state = getattr(client, 'state', None)
                    if hasattr(state, 'value'):
                        state_str = state.value
                    else:
                        state_str = str(state) if state else 'unknown'
                    
                    # 获取最后活动时间
                    last_activity = getattr(client, 'last_activity', connect_time)
                    if isinstance(last_activity, (int, float)):
                        last_activity_str = datetime.fromtimestamp(last_activity).isoformat()
                    else:
                        last_activity_str = str(last_activity)
                    
                    # 获取响应时间
                    avg_response_time = 0
                    if hasattr(client, 'get_avg_response_time'):
                        try:
                            avg_response_time = client.get_avg_response_time()
                        except:
                            avg_response_time = 0
                    
                    client_info = {
                        'id': str(client_id),
                        'address': address_str,
                        'connect_time': connect_time_str,
                        'state': state_str,
                        'authenticated': getattr(client, 'authenticated', False),
                        'commands_sent': getattr(client, 'commands_sent', 0),
                        'bytes_received': getattr(client, 'bytes_received', 0),
                        'bytes_sent': getattr(client, 'bytes_sent', 0),
                        'last_activity': last_activity_str,
                        'avg_response_time': avg_response_time
                    }
                    client_data.append(client_info)
                    
                except Exception as client_error:
                    # 如果单个客户端信息获取失败，记录错误但继续处理其他客户端
                    print(f"处理客户端错误: {client_error}")
                    continue
            
            self._send_json_response({'clients': client_data})
            
        except Exception as e:
            self._send_error_response(500, f"获取客户端失败: {str(e)}")
    
    def _api_get_client_detail(self, client_id: str):
        """获取单个客户端详细信息API"""
        if not self.debug_server:
            self._send_error_response(503, "调试服务器不可用")
            return
        
        try:
            clients = self.debug_server.get_all_clients()
            client = None
            
            for c in clients:
                if c.client_id == client_id:
                    client = c
                    break
            
            if not client:
                self._send_error_response(404, "客户端未找到")
                return
            
            # 获取详细信息
            client_detail = {
                'id': client.client_id,
                'address': f"{client.address[0]}:{client.address[1]}",
                'connect_time': datetime.fromtimestamp(client.connect_time).isoformat(),
                'state': client.state.value,
                'authenticated': client.authenticated,
                'commands_sent': client.commands_sent,
                'bytes_received': client.bytes_received,
                'bytes_sent': client.bytes_sent,
                'last_activity': datetime.fromtimestamp(client.last_activity).isoformat(),
                'avg_response_time': client.get_avg_response_time(),
                'uptime': time.time() - client.connect_time,
                'command_history': getattr(client, 'command_history', [])[-10:],  # 最近10条命令
                'performance_metrics': {
                    'cpu_usage': getattr(client, 'cpu_usage', 0),
                    'memory_usage': getattr(client, 'memory_usage', 0),
                    'network_latency': client.get_avg_response_time()
                }
            }
            
            self._send_json_response({'client': client_detail})
            
        except Exception as e:
            self._send_error_response(500, f"获取客户端详情失败: {str(e)}")
    
    def _api_get_server_status(self):
        """获取服务器状态API"""
        try:
            if not self.debug_server:
                # 返回模拟的服务器状态
                status = {
                    'running': False,
                    'state': 'stopped',
                    'host': '127.0.0.1',
                    'port': 8080,
                    'ssl_enabled': False,
                    'auth_enabled': False,
                    'max_clients': 100,
                    'uptime': 0,
                    'connections': 0,
                    'memory_usage': '--',
                    'cpu_usage': '--',
                    'network_traffic': '--',
                    'response_time': '--',
                    'client_count': 0
                }
                self._send_json_response(status)
                return
            
            # 获取客户端连接数
            client_count = 0
            if hasattr(self.debug_server, 'connection_pool') and self.debug_server.connection_pool:
                client_count = len(self.debug_server.connection_pool.active_connections)
            elif hasattr(self.debug_server, 'clients'):
                client_count = len(self.debug_server.clients)
            
            # 获取性能统计
            stats = getattr(self.debug_server, 'stats', {})
            
            # 实时获取CPU使用率（与_api_get_server_stats保持一致）
            cpu_percent = 0
            try:
                import psutil
                cpu_percent = psutil.cpu_percent(interval=0.1)
            except Exception:
                cpu_percent = 0
            
            # 计算运行时间 - 优先从DevToolsPanel获取真实数据
            uptime = 0
            if self.dev_tools_panel and hasattr(self.dev_tools_panel, '_debug_server_start_time') and self.dev_tools_panel._debug_server_start_time:
                uptime = time.time() - self.dev_tools_panel._debug_server_start_time
            elif hasattr(self.debug_server, 'start_time') and self.debug_server.start_time:
                uptime = time.time() - self.debug_server.start_time
            
            # 计算错误率
            total_requests = stats.get('messages_processed', 0)
            errors = stats.get('errors', 0)
            error_rate = (errors / total_requests) if total_requests > 0 else 0.0
            
            status = {
                'running': self.debug_server.state.value == 'running',
                'state': self.debug_server.state.value,
                'host': self.debug_server.config.host,
                'port': self.debug_server.config.port,
                'ssl_enabled': self.debug_server.config.enable_ssl,
                'auth_enabled': self.debug_server.config.enable_auth,
                'max_clients': self.debug_server.config.max_clients,
                'uptime': uptime,
                'connections': client_count,
                'memory_usage': stats.get('memory_usage', '--'),
                'cpu_usage': cpu_percent,  # 使用实时CPU数据
                'network_traffic': stats.get('network_traffic', '--'),
                'response_time': f"{stats.get('avg_response_time', 0):.2f}ms" if stats.get('avg_response_time') else '--',
                'client_count': client_count,
                'total_requests': total_requests,
                'error_rate': error_rate
            }
            self._send_json_response(status)
            
        except Exception as e:
            self._send_error_response(500, f"获取服务器状态失败: {str(e)}")
    
    def _api_get_server_stats(self):
        """获取服务器统计信息API"""
        try:
            import psutil
            
            if not self.debug_server:
                # 返回模拟的统计数据
                stats = {
                    'total_connections': 0,
                    'active_connections': 0,
                    'messages_processed': 0,
                    'errors': 0,
                    'avg_response_time': 0.0,
                    'memory_usage': '0 MB',
                    'cpu_usage': '0%',
                    'network_usage': '0 KB/s',
                    'disk_usage': '0%',
                    'uptime': 0,
                    'threads': 0
                }
                self._send_json_response(stats)
                return
            
            # 获取基础统计信息
            base_stats = getattr(self.debug_server, 'stats', {})
            
            # 获取系统性能信息
            try:
                # CPU使用率
                cpu_percent = psutil.cpu_percent(interval=0.1)
                
                # 内存使用情况
                memory = psutil.virtual_memory()
                memory_mb = memory.used / (1024 * 1024)
                memory_percent = memory.percent
                
                # 网络使用情况 - 获取当前网络IO统计
                net_io = psutil.net_io_counters()
                # 存储上次的网络统计用于计算速率
                if not hasattr(self, '_last_net_io'):
                    self._last_net_io = net_io
                    self._last_net_time = time.time()
                    network_speed = 0
                else:
                    current_time = time.time()
                    time_diff = current_time - self._last_net_time
                    if time_diff > 0:
                        bytes_diff = (net_io.bytes_sent + net_io.bytes_recv) - (self._last_net_io.bytes_sent + self._last_net_io.bytes_recv)
                        network_speed = (bytes_diff / time_diff) / 1024  # KB/s
                        self._last_net_io = net_io
                        self._last_net_time = current_time
                    else:
                        network_speed = 0
                
                # 磁盘使用情况 - Windows系统使用C盘
                try:
                    import platform
                    if platform.system() == 'Windows':
                        disk = psutil.disk_usage('C:\\')
                    else:
                        disk = psutil.disk_usage('/')
                    disk_percent = disk.percent
                    disk_used_gb = disk.used / (1024 ** 3)
                    disk_total_gb = disk.total / (1024 ** 3)
                except Exception:
                    disk_percent = 0
                    disk_used_gb = 0
                    disk_total_gb = 0
                
                # 线程数
                process = psutil.Process()
                thread_count = process.num_threads()
                
            except Exception as e:
                # 如果psutil不可用，使用默认值
                cpu_percent = 0
                memory_mb = 0
                memory_percent = 0
                network_speed = 0
                disk_percent = 0
                disk_used_gb = 0
                disk_total_gb = 0
                thread_count = 0
            
            # 获取客户端连接数
            active_connections = 0
            if hasattr(self.debug_server, 'connection_pool') and self.debug_server.connection_pool:
                active_connections = len(self.debug_server.connection_pool.active_connections)
            elif hasattr(self.debug_server, 'clients'):
                active_connections = len(self.debug_server.clients)
            
            # 计算运行时间 - 优先从DevToolsPanel获取真实数据
            uptime = 0
            if self.dev_tools_panel and hasattr(self.dev_tools_panel, '_debug_server_start_time') and self.dev_tools_panel._debug_server_start_time:
                uptime = time.time() - self.dev_tools_panel._debug_server_start_time
            elif hasattr(self.debug_server, 'start_time') and self.debug_server.start_time:
                uptime = time.time() - self.debug_server.start_time
            
            stats = {
                'total_connections': base_stats.get('total_connections', 0),
                'active_connections': active_connections,
                'messages_processed': base_stats.get('messages_processed', 0),
                'errors': base_stats.get('errors', 0),
                'avg_response_time': base_stats.get('avg_response_time', 0.0),
                'memory_usage': {
                    'used': memory_mb * 1024 * 1024,  # 转换为字节
                    'total': memory.total if 'memory' in locals() else 0,
                    'percent': memory_percent
                },
                'cpu_usage': cpu_percent,
                'network_usage': f'{network_speed:.1f} KB/s',
                'disk_usage': {
                    'used': disk_used_gb,
                    'total': disk_total_gb,
                    'percent': disk_percent
                },
                'uptime': uptime,
                'threads': thread_count,
                'thread_count': thread_count  # 添加thread_count字段以兼容前端
            }
            
            self._send_json_response(stats)
            
        except Exception as e:
            self._send_error_response(500, f"获取服务器统计失败: {str(e)}")
    
    def _api_get_logs(self, query_params: dict):
        """获取日志API"""
        try:
            count = int(query_params.get('count', ['100'])[0])
            level = query_params.get('level', [''])[0]
            
            if hasattr(self.debug_server, 'log_manager'):
                logs = self.debug_server.log_manager.get_recent_logs(count)
                if level:
                    logs = [log for log in logs if log.get('level', '').upper() == level.upper()]
            else:
                logs = []
            
            self._send_json_response({'logs': logs})
            
        except Exception as e:
            self._send_error_response(500, f"获取日志失败: {str(e)}")
    
    def _api_disconnect_client(self, request_data: dict):
        """断开客户端连接API"""
        if not self.debug_server:
            self._send_error_response(503, "Debug server not available")
            return
        
        client_id = request_data.get('client_id')
        if not client_id:
            self._send_error_response(400, "缺少客户端ID")
            return
        
        try:
            success = self.debug_server.disconnect_client(client_id)
            if success:
                self._send_json_response({'success': True, 'message': '客户端已断开连接'})
            else:
                self._send_error_response(404, "客户端未找到")
                
        except Exception as e:
            self._send_error_response(500, f"断开客户端连接失败: {str(e)}")
    
    def _api_start_server(self):
        """启动服务器API"""
        if not self.debug_server:
            self._send_error_response(503, "调试服务器不可用")
            return
        
        try:
            success = self.debug_server.start_server()
            if success:
                self._send_json_response({'success': True, 'message': '服务器已启动'})
            else:
                self._send_error_response(500, "服务器启动失败")
                
        except Exception as e:
            self._send_error_response(500, f"服务器启动失败: {str(e)}")
    
    def _api_stop_server(self):
        """停止服务器API"""
        if not self.debug_server:
            self._send_error_response(503, "调试服务器不可用")
            return
        
        try:
            self.debug_server.stop_server()
            self._send_json_response({'success': True, 'message': '服务器已停止'})
            
        except Exception as e:
            self._send_error_response(500, f"服务器停止失败: {str(e)}")
    
    def _api_restart_server(self):
        """重启Web服务器API"""
        if not self.debug_server:
            self._send_error_response(503, "调试服务器不可用")
            return
        
        try:
            # 检查是否有restart_web_server方法
            if hasattr(self.debug_server, 'restart_web_server'):
                success = self.debug_server.restart_web_server()
                if success:
                    self._send_json_response({'success': True, 'message': 'Web服务器重启成功'})
                else:
                    self._send_error_response(500, "Web服务器重启失败")
            else:
                self._send_error_response(501, "重启功能不可用")
            
        except Exception as e:
            self._send_error_response(500, f"服务器重启失败: {str(e)}")
    
    def _api_update_config(self, request_data: dict):
        """更新配置API"""
        if not self.debug_server:
            self._send_error_response(503, "调试服务器不可用")
            return
        
        try:
            # 这里应该实现配置更新逻辑
            # 为了安全，只允许更新特定的配置项
            allowed_configs = ['max_clients', 'timeout', 'log_level']
            updated = {}
            
            for key, value in request_data.items():
                if key in allowed_configs:
                    setattr(self.debug_server.config, key, value)
                    updated[key] = value
            
            self._send_json_response({'success': True, 'updated': updated})
            
        except Exception as e:
            self._send_error_response(500, f"配置更新失败: {str(e)}")
    
    def _api_send_command(self, request_data: dict):
        """发送命令API"""
        if not self.debug_server:
            self._send_error_response(503, "调试服务器不可用")
            return
        
        client_id = request_data.get('client_id')
        command = request_data.get('command')
        
        if not client_id or not command:
            self._send_error_response(400, "缺少客户端ID或命令")
            return
        
        try:
            # 这里应该实现向客户端发送命令的逻辑
            # 目前返回成功响应
            self._send_json_response({'success': True, 'message': '命令已发送'})
            
        except Exception as e:
            self._send_error_response(500, f"发送命令失败: {str(e)}")
    
    def _api_clear_logs(self):
        """清空日志API"""
        try:
            if hasattr(self.debug_server, 'log_manager') and self.debug_server.log_manager:
                # 清空日志管理器中的日志
                self.debug_server.log_manager.clear_logs()
                self._send_json_response({'success': True, 'message': '日志清除成功'})
            else:
                self._send_error_response(503, "日志管理器不可用")
                
        except Exception as e:
            self._send_error_response(500, f"清除日志失败: {str(e)}")
    
    def _api_get_system_info(self):
        """获取系统信息API"""
        try:
            import platform
            import psutil
            from datetime import datetime
            
            # 获取基本系统信息
            system_info = {
                "osInfo": f"{platform.system()} {platform.release()}",
                "pythonVersion": platform.python_version(),
                "workingDir": os.getcwd(),
                "hostname": platform.node(),
                "architecture": platform.architecture()[0],
                "processor": platform.processor(),
                "timestamp": datetime.now().isoformat()
            }
            
            # 计算运行时间
            if hasattr(self.debug_server, 'start_time') and self.debug_server.start_time:
                uptime_seconds = time.time() - self.debug_server.start_time
                hours = int(uptime_seconds // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                seconds = int(uptime_seconds % 60)
                system_info["uptime"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                system_info["uptime"] = "00:00:00"
            
            # 添加psutil系统信息（如果可用）
            if psutil:
                try:
                    memory = psutil.virtual_memory()
                    disk = psutil.disk_usage('.')
                    system_info.update({
                        "totalMemory": f"{memory.total / (1024**3):.2f} GB",
                        "availableMemory": f"{memory.available / (1024**3):.2f} GB",
                        "memoryUsage": f"{memory.percent}%",
                        "diskTotal": f"{disk.total / (1024**3):.2f} GB",
                        "diskFree": f"{disk.free / (1024**3):.2f} GB",
                        "diskUsage": f"{(disk.used / disk.total) * 100:.1f}%",
                        "cpuCores": psutil.cpu_count(),
                        "cpuUsage": f"{psutil.cpu_percent(interval=0.1)}%"
                    })
                except Exception as e:
                    system_info["psutil_error"] = str(e)
            
            self._send_json_response({
                'success': True,
                'data': system_info
            })
            
        except Exception as e:
            self._send_error_response(500, f"获取系统信息失败: {str(e)}")
    
    def _send_json_response(self, data: dict):
        """发送JSON响应"""
        response = json.dumps(data, ensure_ascii=False, indent=2)
        content_bytes = response.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(content_bytes)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(content_bytes)
    
    def _send_error_response(self, status_code: int, message: str):
        """发送错误响应"""
        error_data = {'error': message, 'status': status_code}
        response = json.dumps(error_data, ensure_ascii=False)
        content_bytes = response.encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(content_bytes)))
        self.end_headers()
        self.wfile.write(content_bytes)
    
    def _send_404(self):
        """发送404响应"""
        self._send_error_response(404, "Not Found")
    
    def _get_main_page_html(self) -> str:
        """获取主页面HTML内容"""
        return """<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>远程调试服务器 - Web管理界面</title>
    <style>
        :root {
            --primary-color: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --primary-hover: linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%);
            --success-color: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            --success-hover: linear-gradient(135deg, #0e8678 0%, #2dd46b 100%);
            --warning-color: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            --warning-hover: linear-gradient(135deg, #e081e9 0%, #e3455a 100%);
            --danger-color: linear-gradient(135deg, #fc466b 0%, #3f5efb 100%);
            --danger-hover: linear-gradient(135deg, #ea3459 0%, #354ce9 100%);
            --accent-color: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
            --info-color: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
            --bg-primary: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --bg-secondary: rgba(255, 255, 255, 0.95);
            --bg-tertiary: rgba(255, 255, 255, 0.8);
            --bg-card: rgba(255, 255, 255, 0.9);
            --text-primary: #2d3748;
            --text-secondary: #4a5568;
            --text-muted: #718096;
            --border-color: rgba(226, 232, 240, 0.8);
            --shadow-sm: 0 2px 4px rgba(0, 0, 0, 0.1);
            --shadow-md: 0 8px 25px rgba(0, 0, 0, 0.15);
            --shadow-lg: 0 20px 40px rgba(0, 0, 0, 0.2);
            --shadow-xl: 0 25px 50px rgba(0, 0, 0, 0.25);
            --radius-sm: 0.5rem;
            --radius-md: 0.75rem;
            --radius-lg: 1rem;
            --radius-xl: 1.5rem;
        }
        
        [data-theme="dark"] {
            --bg-primary: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            --bg-secondary: rgba(30, 41, 59, 0.95);
            --bg-tertiary: rgba(51, 65, 85, 0.8);
            --bg-card: rgba(30, 41, 59, 0.9);
            --text-primary: #f8fafc;
            --text-secondary: #cbd5e1;
            --text-muted: #94a3b8;
            --border-color: rgba(71, 85, 105, 0.8);
            --shadow-sm: 0 2px 4px rgba(0, 0, 0, 0.3);
            --shadow-md: 0 8px 25px rgba(0, 0, 0, 0.4);
            --shadow-lg: 0 20px 40px rgba(0, 0, 0, 0.5);
            --shadow-xl: 0 25px 50px rgba(0, 0, 0, 0.6);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            transition: all 0.3s ease;
            min-height: 100vh;
            position: relative;
        }
        
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                radial-gradient(circle at 20% 80%, rgba(120, 119, 198, 0.3) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(255, 119, 198, 0.3) 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, rgba(120, 219, 255, 0.2) 0%, transparent 50%);
            z-index: -1;
            animation: backgroundShift 20s ease-in-out infinite;
        }
        
        [data-theme="dark"] body::before {
            background: 
                radial-gradient(circle at 20% 80%, rgba(59, 130, 246, 0.2) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(139, 92, 246, 0.2) 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, rgba(16, 185, 129, 0.15) 0%, transparent 50%);
        }
        
        @keyframes backgroundShift {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.8; }
        }
        
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        @keyframes slideInLeft {
            from {
                opacity: 0;
                transform: translateX(-30px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        @keyframes pulse {
            0%, 100% {
                transform: scale(1);
            }
            50% {
                transform: scale(1.05);
            }
        }
        
        @keyframes shimmer {
            0% {
                background-position: -200px 0;
            }
            100% {
                background-position: calc(200px + 100%) 0;
            }
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 1rem;
        }
        
        .header {
            background: var(--bg-card);
            border-radius: var(--radius-xl);
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: var(--shadow-lg);
            border: 1px solid var(--border-color);
            backdrop-filter: blur(20px);
            position: relative;
            overflow: hidden;
        }
        
        .header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: var(--primary-color);
        }
        
        .navigation-bar {
            padding: 0 2rem;
            border-bottom: 1px solid var(--border-color);
            background: rgba(255,255,255,0.8);
            margin: -1rem -2rem 1rem -2rem;
        }
        
        .nav-menu {
            display: flex;
            gap: 0;
            align-items: center;
        }
        
        .nav-item {
            padding: 1rem 1.5rem;
            text-decoration: none;
            color: var(--text-secondary);
            font-weight: 500;
            border-bottom: 3px solid transparent;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .nav-item::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.1), transparent);
            transition: left 0.5s ease;
        }
        
        .nav-item:hover::before {
            left: 100%;
        }
        
        .nav-item:hover {
            color: var(--primary-color);
            background: rgba(102, 126, 234, 0.05);
        }
        
        .nav-item.active {
            color: var(--primary-color);
            border-bottom-color: var(--primary-color);
            background: rgba(102, 126, 234, 0.1);
        }
        
        [data-theme="dark"] .navigation-bar {
            background: rgba(30, 41, 59, 0.8);
        }
        
        [data-theme="dark"] .nav-item {
            color: var(--text-secondary);
        }
        
        [data-theme="dark"] .nav-item:hover {
            background: rgba(102, 126, 234, 0.15);
        }
        
        [data-theme="dark"] .nav-item.active {
            background: rgba(102, 126, 234, 0.2);
        }
        
        .header-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        .header h1 {
            font-size: 1.875rem;
            font-weight: 700;
            color: var(--text-primary);
            margin: 0;
        }
        
        .theme-selector {
            background: linear-gradient(135deg, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0.7) 100%);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 0.75rem 1.5rem;
            cursor: pointer;
            transition: all 0.3s ease;
            color: var(--text-primary);
            font-weight: 600;
            backdrop-filter: blur(10px);
            position: relative;
            overflow: hidden;
            min-width: 120px;
            font-size: 0.9rem;
        }
        
        [data-theme="dark"] .theme-selector {
            background: linear-gradient(135deg, rgba(51, 65, 85, 0.9) 0%, rgba(71, 85, 105, 0.7) 100%);
            border: 1px solid rgba(148, 163, 184, 0.3);
            color: #f8fafc;
        }
        
        [data-theme="dark"] .theme-selector:hover {
            background: var(--primary-color);
            border-color: rgba(102, 126, 234, 0.5);
        }
        
        .theme-selector:hover {
            background: var(--primary-color);
            color: white;
            transform: translateY(-2px);
        }
        
        .theme-selector option {
            background: var(--bg-primary);
            color: var(--text-primary);
            padding: 0.5rem;
        }
        
        [data-theme="dark"] .theme-selector option {
            background: #374151;
            color: #f8fafc;
            box-shadow: var(--shadow-lg);
        }
        
        .status-bar {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem;
            background: var(--bg-tertiary);
            border-radius: var(--radius-md);
            border: 1px solid var(--border-color);
        }
        
        [data-theme="dark"] .status-item {
            background: rgba(51, 65, 85, 0.6);
            border: 1px solid rgba(71, 85, 105, 0.5);
            backdrop-filter: blur(10px);
            color: #f1f5f9 !important;
        }
        
        [data-theme="dark"] .status-item span {
            color: #f1f5f9 !important;
        }
        
        [data-theme="dark"] .status-item strong {
            color: #ffffff !important;
        }
        
        .status-indicator {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: var(--danger-color);
            animation: pulse 2s infinite;
            position: relative;
            box-shadow: 0 0 10px rgba(239, 68, 68, 0.5);
        }
        
        .status-indicator::before {
            content: '';
            position: absolute;
            top: -2px;
            left: -2px;
            right: -2px;
            bottom: -2px;
            border-radius: 50%;
            background: inherit;
            opacity: 0.3;
            animation: ripple 2s infinite;
        }
        
        .status-indicator.online {
            background: var(--success-color);
            box-shadow: 0 0 10px rgba(16, 185, 129, 0.5);
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(1.1); }
        }
        
        @keyframes ripple {
            0% { transform: scale(1); opacity: 0.3; }
            100% { transform: scale(2); opacity: 0; }
        }
        
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            animation: fadeInUp 0.8s ease-out;
        }
        
        .section {
            background: var(--bg-card);
            border-radius: var(--radius-xl);
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow-lg);
            overflow: hidden;
            backdrop-filter: blur(20px);
            transition: all 0.3s ease;
            position: relative;
            animation: slideInLeft 0.6s ease-out;
        }
        
        .section:nth-child(even) {
            animation: slideInLeft 0.6s ease-out 0.2s both;
        }
        
        .section:hover {
            transform: translateY(-5px);
            box-shadow: var(--shadow-xl);
        }
        
        .section::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--accent-color);
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        
        .section:hover::before {
            opacity: 1;
        }
        
        .section.full-width {
            grid-column: 1 / -1;
        }
        
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.5rem 2rem;
            background: linear-gradient(135deg, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0.7) 100%);
            border-bottom: 1px solid var(--border-color);
            backdrop-filter: blur(10px);
        }
        
        .section-header h2 {
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary);
            margin: 0;
        }
        
        .controls {
            display: flex;
            gap: 0.5rem;
        }
        
        .btn {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: var(--radius-lg);
            font-size: 0.875rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            position: relative;
            overflow: hidden;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            transition: left 0.5s ease;
        }
        
        .btn:hover::before {
            left: 100%;
        }
        
        .btn:hover {
            transform: translateY(-3px) scale(1.05);
            box-shadow: var(--shadow-xl);
        }
        
        .btn.primary {
            background: var(--primary-color);
            color: white;
        }
        
        .btn.primary:hover {
            background: var(--primary-hover);
        }
        
        .btn.success {
            background: var(--success-color);
            color: white;
        }
        
        .btn.success:hover {
            background: var(--success-hover);
        }
        
        .btn.warning {
            background: var(--warning-color);
            color: white;
        }
        
        .btn.warning:hover {
            background: var(--warning-hover);
        }
        
        .btn.danger {
            background: var(--danger-color);
            color: white;
        }
        
        .btn.danger:hover {
            background: var(--danger-hover);
        }
        
        .btn:not(.primary):not(.success):not(.warning):not(.danger) {
            background: var(--bg-tertiary);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
        }
        
        .btn:not(.primary):not(.success):not(.warning):not(.danger):hover {
            background: var(--primary-color);
            color: white;
        }
        
        [data-theme="dark"] .btn:not(.primary):not(.success):not(.warning):not(.danger) {
            background: rgba(51, 65, 85, 0.8);
            border: 1px solid rgba(71, 85, 105, 0.5);
            color: #f8fafc;
        }
        
        /* 深色模式下的表单元素样式 */
        [data-theme="dark"] select,
        [data-theme="dark"] input {
            background-color: rgba(51, 65, 85, 0.8) !important;
            color: #f8fafc !important;
            border-color: rgba(71, 85, 105, 0.6) !important;
        }
        
        [data-theme="dark"] select option {
            background-color: #334155;
            color: #f8fafc;
        }
        
        [data-theme="dark"] .stat-label {
            color: #e2e8f0 !important;
        }
        
        [data-theme="dark"] .client-details {
            color: #cbd5e1 !important;
        }
        
        [data-theme="dark"] .loading {
            color: #cbd5e1 !important;
        }
        
        [data-theme="dark"] .log-entry {
            color: #f8fafc !important;
        }
        
        [data-theme="dark"] .client-id {
            color: #f8fafc !important;
        }
        
        [data-theme="dark"] .section-header {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(51, 65, 85, 0.9) 100%) !important;
            border-bottom: 1px solid rgba(71, 85, 105, 0.6) !important;
        }
        
        [data-theme="dark"] .section-header h2 {
            color: #f1f5f9 !important;
        }
        
        [data-theme="dark"] .header h1 {
            color: #f1f5f9 !important;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            padding: 1.5rem;
        }
        
        .stat-item {
            text-align: center;
            padding: 1.5rem;
            background: linear-gradient(135deg, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0.6) 100%);
            border-radius: var(--radius-lg);
            border: 1px solid var(--border-color);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(10px);
        }
        
        [data-theme="dark"] .stat-item {
            background: linear-gradient(135deg, rgba(51, 65, 85, 0.8) 0%, rgba(71, 85, 105, 0.6) 100%);
            border: 1px solid rgba(71, 85, 105, 0.4);
        }
        
        .stat-item::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--info-color);
            transform: scaleX(0);
            transition: transform 0.3s ease;
        }
        
        .stat-item:hover::before {
            transform: scaleX(1);
        }
        
        .stat-item:hover {
            transform: translateY(-8px) scale(1.02);
            box-shadow: var(--shadow-xl);
        }
        
        .stat-label {
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }
        
        .stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        
        .performance-chart {
            padding: 1.5rem;
            min-height: 300px;
            position: relative;
        }
        
        .chart-container {
            width: 100%;
            min-height: 100%;
            background: var(--bg-tertiary);
            border-radius: var(--radius-md);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-muted);
        }
        
        [data-theme="dark"] .chart-container {
            background: rgba(51, 65, 85, 0.6);
            border: 1px solid rgba(71, 85, 105, 0.3);
        }
        
        /* 当chart-container包含performance-monitor-container时的样式重置 */
        .chart-container .performance-monitor-container {
            width: 100%;
            background: transparent;
            border: none;
            box-shadow: none;
            backdrop-filter: none;
            padding: 0;
        }
        
        .chart-container .performance-header {
            border-bottom: 2px solid var(--border-color);
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
        }
        
        [data-theme="dark"] .chart-container .performance-header {
            border-bottom-color: rgba(71, 85, 105, 0.6);
        }
        
        .performance-monitor-container {
            width: 100%;
        }
        
        .performance-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
        }
        
        .performance-card {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            align-items: center;
            gap: 16px;
            transition: all 0.3s ease;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .performance-card:hover {
            background: rgba(255, 255, 255, 0.12);
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
        }
        
        .performance-icon {
            font-size: 32px;
            width: 50px;
            height: 50px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            flex-shrink: 0;
        }
        
        .performance-info {
            flex: 1;
            min-width: 0;
        }
        
        .performance-label {
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 4px;
            font-weight: 500;
        }
        
        .performance-value {
            font-size: 16px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 8px;
            line-height: 1.2;
        }
        
        .performance-bar {
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
            overflow: hidden;
        }
        
        .performance-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary-color), var(--accent-color));
            border-radius: 3px;
            transition: width 0.5s ease;
        }
        
        .performance-trend {
            font-size: 12px;
            color: var(--success-color);
            font-weight: 500;
            margin-top: 4px;
        }
        
        .client-placeholder {
            text-align: center;
            padding: 40px 20px;
            color: var(--text-secondary);
        }
        
        .placeholder-icon {
            font-size: 48px;
            margin-bottom: 16px;
            opacity: 0.6;
        }
        
        .placeholder-text {
            font-size: 18px;
            font-weight: 500;
            margin-bottom: 8px;
            color: var(--text-primary);
        }
        
        .placeholder-subtitle {
            font-size: 14px;
            opacity: 0.7;
        }
        
        .system-info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 16px;
        }
        
        .system-info-card {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            align-items: center;
            gap: 16px;
            transition: all 0.3s ease;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .system-info-card:hover {
            background: rgba(255, 255, 255, 0.12);
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
        }
        
        .system-info-icon {
            font-size: 28px;
            width: 45px;
            height: 45px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            flex-shrink: 0;
        }
        
        .system-info-content {
            flex: 1;
            min-width: 0;
        }
        
        .system-info-label {
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 4px;
            font-weight: 500;
        }
        
        .system-info-value {
            font-size: 15px;
            font-weight: 600;
            color: var(--text-primary);
            word-break: break-all;
        }
        
        .quick-actions-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
        }
        
        .quick-action-card {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            align-items: center;
            gap: 16px;
            transition: all 0.3s ease;
            border: 1px solid rgba(255, 255, 255, 0.1);
            cursor: pointer;
        }
        
        .quick-action-card:hover {
            background: rgba(255, 255, 255, 0.15);
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
        }
        
        .quick-action-icon {
            font-size: 24px;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, var(--primary-color), var(--accent-color));
            border-radius: 8px;
            flex-shrink: 0;
        }
        
        .quick-action-content {
            flex: 1;
            min-width: 0;
        }
        
        .quick-action-title {
            font-size: 14px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 4px;
        }
        
        .quick-action-desc {
            font-size: 12px;
            color: var(--text-secondary);
            opacity: 0.8;
        }
        
        .client-list {
            padding: 1.5rem;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .client-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.5rem;
            background: linear-gradient(135deg, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.8) 100%);
            border-radius: var(--radius-lg);
            border: 1px solid var(--border-color);
            margin-bottom: 1rem;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(15px);
            transform: translateZ(0);
        }
        
        .client-item::after {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.6s ease;
        }
        
        .client-item:hover::after {
            left: 100%;
        }
        
        [data-theme="dark"] .client-item {
            background: linear-gradient(135deg, rgba(51, 65, 85, 0.9) 0%, rgba(71, 85, 105, 0.7) 100%);
            border: 1px solid rgba(71, 85, 105, 0.4);
        }
        
        .client-item::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 4px;
            background: var(--success-color);
            transform: scaleY(0);
            transition: transform 0.3s ease;
        }
        
        .client-item:hover::before {
            transform: scaleY(1);
        }
        
        .client-item:hover {
            transform: translateX(8px) translateY(-2px);
            box-shadow: var(--shadow-xl);
        }
        
        .client-info {
            flex: 1;
        }
        
        .client-id {
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 0.25rem;
        }
        
        .client-details {
            font-size: 0.875rem;
            color: var(--text-secondary);
        }
        
        .client-actions {
            display: flex;
            gap: 0.5rem;
        }
        
        .log-container {
            padding: 1.5rem;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
        }
        
        .log-entry {
            padding: 1rem;
            margin-bottom: 0.5rem;
            border-radius: var(--radius-md);
            font-size: 0.875rem;
            line-height: 1.5;
            transition: all 0.3s ease;
            position: relative;
            backdrop-filter: blur(10px);
        }
        
        .log-entry:hover {
            transform: translateX(4px);
            box-shadow: var(--shadow-md);
        }
        
        .log-entry.info {
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(59, 130, 246, 0.05) 100%);
            border-left: 4px solid #3b82f6;
            border-radius: var(--radius-md) var(--radius-md) var(--radius-md) 0;
        }
        
        .log-entry.warning {
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(245, 158, 11, 0.05) 100%);
            border-left: 4px solid #f59e0b;
            border-radius: var(--radius-md) var(--radius-md) var(--radius-md) 0;
        }
        
        .log-entry.error {
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(239, 68, 68, 0.05) 100%);
            border-left: 4px solid #ef4444;
            border-radius: var(--radius-md) var(--radius-md) var(--radius-md) 0;
        }
        
        .loading {
            text-align: center;
            color: var(--text-muted);
            padding: 2rem;
            font-style: italic;
        }
        
        .loading::after {
            content: '';
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid var(--text-muted);
            border-radius: 50%;
            border-top-color: transparent;
            animation: spin 1s linear infinite;
            margin-left: 0.5rem;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* 性能监控卡片样式 */
        .performance-monitor-container {
            padding: 1.5rem;
            background: var(--card-bg);
            border-radius: var(--radius-xl);
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow-md);
            backdrop-filter: blur(20px);
        }
        
        .performance-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid var(--border-color);
        }
        
        .performance-header h3 {
            margin: 0;
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-primary);
            background: var(--primary-color);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .update-time {
            font-size: 0.875rem;
            color: var(--text-secondary);
            font-weight: 500;
        }
        
        .performance-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.25rem;
            margin-bottom: 0;
        }
        
        .performance-card {
            display: flex;
            align-items: center;
            gap: 1rem;
            padding: 1.25rem;
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-tertiary) 100%);
            border-radius: var(--radius-lg);
            border: 1px solid var(--border-color);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(10px);
            min-height: 80px;
        }
        
        .performance-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--accent-color);
            transform: scaleX(0);
            transition: transform 0.3s ease;
        }
        
        .performance-card:hover::before {
            transform: scaleX(1);
        }
        
        .performance-card:hover {
            transform: translateY(-4px) scale(1.02);
            box-shadow: var(--shadow-xl);
            border-color: rgba(102, 126, 234, 0.3);
        }
        
        .card-icon {
            font-size: 2rem;
            line-height: 1;
            flex-shrink: 0;
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
            border-radius: var(--radius-md);
            border: 1px solid rgba(102, 126, 234, 0.2);
        }
        
        .card-content {
            flex: 1;
            min-width: 0;
        }
        
        .card-label {
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .card-value {
            font-size: 1.125rem;
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1.2;
            word-break: break-word;
            overflow: hidden;
            text-overflow: ellipsis;
            transition: all 0.3s ease-in-out;
            transform: translateZ(0);
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
        }
        
        /* 深色模式下的性能监控卡片 */
        [data-theme="dark"] .performance-monitor-container {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(51, 65, 85, 0.9) 100%);
            border: 1px solid rgba(71, 85, 105, 0.6);
        }
        
        [data-theme="dark"] .performance-header {
            border-bottom-color: rgba(71, 85, 105, 0.6);
        }
        
        [data-theme="dark"] .performance-header h3 {
            color: #f1f5f9;
        }
        
        [data-theme="dark"] .update-time {
            color: #cbd5e1;
        }
        
        [data-theme="dark"] .performance-card {
            background: linear-gradient(135deg, rgba(51, 65, 85, 0.8) 0%, rgba(71, 85, 105, 0.6) 100%);
            border: 1px solid rgba(71, 85, 105, 0.4);
        }
        
        [data-theme="dark"] .performance-card:hover {
            border-color: rgba(139, 92, 246, 0.4);
        }
        
        [data-theme="dark"] .card-icon {
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.15) 0%, rgba(59, 130, 246, 0.15) 100%);
            border-color: rgba(139, 92, 246, 0.3);
        }
        
        [data-theme="dark"] .card-label {
            color: #e2e8f0;
        }
        
        [data-theme="dark"] .card-value {
            color: #f8fafc;
        }
        
        /* 特定卡片的颜色主题 */
        .cpu-card .card-icon {
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(220, 38, 38, 0.1) 100%);
            border-color: rgba(239, 68, 68, 0.2);
        }
        
        .memory-card .card-icon {
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(37, 99, 235, 0.1) 100%);
            border-color: rgba(59, 130, 246, 0.2);
        }
        
        .network-card .card-icon {
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(5, 150, 105, 0.1) 100%);
            border-color: rgba(16, 185, 129, 0.2);
        }
        
        .disk-card .card-icon {
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(217, 119, 6, 0.1) 100%);
            border-color: rgba(245, 158, 11, 0.2);
        }
        
        .connection-card .card-icon {
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.1) 0%, rgba(124, 58, 237, 0.1) 100%);
            border-color: rgba(139, 92, 246, 0.2);
        }
        
        .thread-card .card-icon {
            background: linear-gradient(135deg, rgba(236, 72, 153, 0.1) 0%, rgba(219, 39, 119, 0.1) 100%);
            border-color: rgba(236, 72, 153, 0.2);
        }
        
        @media (max-width: 1200px) {
            .main-content {
                grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            }
        }
        
        @media (max-width: 768px) {
            .main-content {
                grid-template-columns: 1fr;
            }
            
            .status-bar {
                grid-template-columns: 1fr;
            }
            
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .header-top {
                flex-direction: column;
                gap: 1rem;
            }
            
            .performance-grid {
                grid-template-columns: 1fr;
                gap: 1rem;
            }
            
            .performance-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 0.5rem;
            }
            
            .performance-card {
                min-height: 70px;
                padding: 1rem;
            }
            
            .card-icon {
                width: 40px;
                height: 40px;
                font-size: 1.5rem;
            }
            
            .card-value {
                font-size: 1rem;
            }
        }
        
        @media (max-width: 480px) {
            .performance-monitor-container {
                padding: 1rem;
            }
            
            .performance-grid {
                gap: 0.75rem;
            }
            
            .performance-card {
                padding: 0.875rem;
                gap: 0.75rem;
            }
            
            .card-icon {
                width: 36px;
                height: 36px;
                font-size: 1.25rem;
            }
            
            .card-label {
                font-size: 0.75rem;
            }
            
            .card-value {
                font-size: 0.875rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-top">
                <h1>🔧 远程调试服务器 - Web管理界面</h1>
                <select class="theme-selector" id="themeSelector" onchange="app.changeTheme(this.value)">
                    <option value="auto">🔄 自动</option>
                    <option value="light">☀️ 浅色</option>
                    <option value="dark">🌙 深色</option>
                </select>
            </div>
            <div class="navigation-bar">
                <nav class="nav-menu">
                    <a href="/" class="nav-item active">🏠 主页</a>
                    <a href="/websocket_test" class="nav-item">🔌 WebSocket测试</a>
                    <a href="/client_management" class="nav-item">👥 客户端管理</a>
                </nav>
            </div>
            <div class="status-bar">
                <div class="status-item">
                    <div class="status-indicator" id="serverStatus"></div>
                    <span id="serverStatusText">检查中...</span>
                </div>
                <div class="status-item">
                    <span>客户端: <strong id="clientCount">0</strong></span>
                </div>
                <div class="status-item">
                    <span>运行时间: <strong id="uptime">--</strong></span>
                </div>
                <div class="status-item">
                    <span>CPU使用率: <strong id="cpuUsage">--</strong></span>
                </div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="section">
                <div class="section-header">
                    <h2>📊 服务器状态</h2>
                    <div class="controls">
                        <button class="btn success" onclick="app.startServer()">启动服务器</button>
                        <button class="btn danger" onclick="app.stopServer()">停止服务器</button>
                        <button class="btn" onclick="app.restartServer()">🔄 重启</button>
                    </div>
                </div>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-label">状态</div>
                        <div class="stat-value" id="serverState">检查中...</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">端口</div>
                        <div class="stat-value" id="serverPort">--</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">连接数</div>
                        <div class="stat-value" id="connectionCount">0</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">运行时间</div>
                        <div class="stat-value" id="serverUptime">--</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">请求总数</div>
                        <div class="stat-value" id="totalRequests">--</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">错误率</div>
                        <div class="stat-value" id="errorRate">--</div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-header">
                    <h2>📈 性能监控</h2>
                    <div class="controls">
                        <button class="btn" onclick="app.refreshPerformance()">🔄 刷新</button>
                        <button class="btn" onclick="app.exportPerformanceData()">📊 导出数据</button>
                    </div>
                </div>
                <div class="performance-chart">
                    <div class="chart-container" id="performanceChart">
                        <div class="performance-monitor-container">
                            <div class="performance-grid">
                                <div class="performance-card">
                                    <div class="performance-icon">💻</div>
                                    <div class="performance-info">
                                        <div class="performance-label">CPU使用率</div>
                                        <div class="performance-value" id="cpuUsageChart">50.0%</div>
                                        <div class="performance-bar">
                                            <div class="performance-fill" style="width: 50%"></div>
                                        </div>
                                    </div>
                                </div>
                                <div class="performance-card">
                                    <div class="performance-icon">💾</div>
                                    <div class="performance-info">
                                        <div class="performance-label">内存使用</div>
                                        <div class="performance-value" id="memoryUsageChart">0.00GB / 0.00GB<br>(0.0%)</div>
                                        <div class="performance-bar">
                                            <div class="performance-fill" style="width: 0%"></div>
                                        </div>
                                    </div>
                                </div>
                                <div class="performance-card">
                                    <div class="performance-icon">🌐</div>
                                    <div class="performance-info">
                                        <div class="performance-label">网络流量</div>
                                        <div class="performance-value" id="networkUsageChart">↑0.00MB ↓0.00MB</div>
                                        <div class="performance-bar">
                                            <div class="performance-fill" style="width: 0%"></div>
                                        </div>
                                    </div>
                                </div>
                                <div class="performance-card">
                                    <div class="performance-icon">💽</div>
                                    <div class="performance-info">
                                        <div class="performance-label">磁盘使用</div>
                                        <div class="performance-value" id="diskUsageChart">0.00GB / 0.00GB<br>(0.0%)</div>
                                        <div class="performance-bar">
                                            <div class="performance-fill" style="width: 0%"></div>
                                        </div>
                                    </div>
                                </div>
                                <div class="performance-card">
                                    <div class="performance-icon">🔗</div>
                                    <div class="performance-info">
                                        <div class="performance-label">活跃连接</div>
                                        <div class="performance-value" id="connectionsChart">0</div>
                                        <div class="performance-trend">稳定</div>
                                    </div>
                                </div>
                                <div class="performance-card">
                                    <div class="performance-icon">⏱️</div>
                                    <div class="performance-info">
                                        <div class="performance-label">平均响应时间</div>
                                        <div class="performance-value" id="responseTimeChart">--ms</div>
                                        <div class="performance-trend">正常</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-header">
                    <h2>👥 客户端管理</h2>
                    <div class="controls">
                        <button class="btn" onclick="app.refreshClients()">🔄 刷新</button>
                        <button class="btn warning" onclick="app.disconnectAllClients()">⚠️ 断开所有</button>
                    </div>
                </div>
                <div id="clientList" class="client-list">
                    <div class="client-placeholder">
                        <div class="placeholder-icon">👥</div>
                        <div class="placeholder-text">暂无客户端连接</div>
                        <div class="placeholder-subtitle">客户端连接后将在此处显示</div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-header">
                    <h2>⚙️ 服务器配置</h2>
                    <div class="controls">
                        <button class="btn primary" onclick="app.saveConfig()">💾 保存配置</button>
                        <button class="btn" onclick="app.resetConfig()">🔄 重置</button>
                    </div>
                </div>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-label">最大连接数</div>
                        <div class="stat-value">
                            <input type="number" id="maxConnections" value="10" min="1" max="100" 
                                   style="background: transparent; border: none; color: inherit; font-size: inherit; font-weight: inherit; text-align: center; width: 60px;">
                        </div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">超时时间(秒)</div>
                        <div class="stat-value">
                            <input type="number" id="timeout" value="30" min="5" max="300" 
                                   style="background: transparent; border: none; color: inherit; font-size: inherit; font-weight: inherit; text-align: center; width: 60px;">
                        </div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">日志级别</div>
                        <div class="stat-value">
                            <select id="logLevel" style="background: transparent; border: none; color: inherit; font-size: inherit; font-weight: inherit;">
                                <option value="调试">调试</option>
                                <option value="信息" selected>信息</option>
                                <option value="警告">警告</option>
                                <option value="错误">错误</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-header">
                    <h2>🖥️ 系统信息</h2>
                    <div class="controls">
                        <button class="btn" onclick="app.refreshSystemInfo()">🔄 刷新</button>
                        <button class="btn" onclick="app.exportSystemInfo()">📊 导出信息</button>
                    </div>
                </div>
                <div class="system-info-grid">
                    <div class="system-info-card">
                        <div class="system-info-icon">🖥️</div>
                        <div class="system-info-content">
                            <div class="system-info-label">操作系统</div>
                            <div class="system-info-value" id="osInfo">--</div>
                        </div>
                    </div>
                    <div class="system-info-card">
                        <div class="system-info-icon">🐍</div>
                        <div class="system-info-content">
                            <div class="system-info-label">Python版本</div>
                            <div class="system-info-value" id="pythonVersion">--</div>
                        </div>
                    </div>
                    <div class="system-info-card">
                        <div class="system-info-icon">⏰</div>
                        <div class="system-info-content">
                            <div class="system-info-label">运行时间</div>
                            <div class="system-info-value" id="systemUptime">--</div>
                        </div>
                    </div>
                    <div class="system-info-card">
                        <div class="system-info-icon">📁</div>
                        <div class="system-info-content">
                            <div class="system-info-label">工作目录</div>
                            <div class="system-info-value" id="workingDir">--</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-header">
                    <h2>⚡ 快捷操作</h2>
                    <div class="controls">
                        <button class="btn" onclick="app.refreshQuickActions()">🔄 刷新</button>
                    </div>
                </div>
                <div class="quick-actions-grid">
                    <div class="quick-action-card" onclick="app.openLogFolder()">
                        <div class="quick-action-icon">📁</div>
                        <div class="quick-action-content">
                            <div class="quick-action-title">打开日志文件夹</div>
                            <div class="quick-action-desc">查看系统日志文件</div>
                        </div>
                    </div>
                    <div class="quick-action-card" onclick="app.openConfigFolder()">
                        <div class="quick-action-icon">⚙️</div>
                        <div class="quick-action-content">
                            <div class="quick-action-title">打开配置文件夹</div>
                            <div class="quick-action-desc">编辑配置文件</div>
                        </div>
                    </div>
                    <div class="quick-action-card" onclick="app.backupConfig()">
                        <div class="quick-action-icon">💾</div>
                        <div class="quick-action-content">
                            <div class="quick-action-title">备份配置</div>
                            <div class="quick-action-desc">创建配置备份</div>
                        </div>
                    </div>
                    <div class="quick-action-card" onclick="app.restoreConfig()">
                        <div class="quick-action-icon">🔄</div>
                        <div class="quick-action-content">
                            <div class="quick-action-title">恢复配置</div>
                            <div class="quick-action-desc">从备份恢复配置</div>
                        </div>
                    </div>
                    <div class="quick-action-card" onclick="app.checkUpdates()">
                        <div class="quick-action-icon">🔍</div>
                        <div class="quick-action-content">
                            <div class="quick-action-title">检查更新</div>
                            <div class="quick-action-desc">检查软件更新</div>
                        </div>
                    </div>
                    <div class="quick-action-card" onclick="app.exportData()">
                        <div class="quick-action-icon">📊</div>
                        <div class="quick-action-content">
                            <div class="quick-action-title">导出数据</div>
                            <div class="quick-action-desc">导出系统数据</div>
                        </div>
                    </div>
                    <div class="quick-action-card" onclick="app.systemDiagnostic()">
                        <div class="quick-action-icon">🔧</div>
                        <div class="quick-action-content">
                            <div class="quick-action-title">系统诊断</div>
                            <div class="quick-action-desc">运行系统诊断</div>
                        </div>
                    </div>
                    <div class="quick-action-card" onclick="app.showAbout()">
                        <div class="quick-action-icon">ℹ️</div>
                        <div class="quick-action-content">
                            <div class="quick-action-title">关于系统</div>
                            <div class="quick-action-desc">查看系统信息</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="section full-width">
                <div class="section-header">
                    <h2>📝 系统日志</h2>
                    <div class="controls">
                        <button class="btn" onclick="app.refreshLogs()">🔄 刷新</button>
                        <button class="btn warning" onclick="app.clearLogs()">🗑️ 清空</button>
                        <button class="btn" onclick="app.downloadLogs()">📥 下载日志</button>
                        <select id="logFilter" onchange="app.filterLogs()" style="margin-left: 0.5rem; padding: 0.25rem;">
                            <option value="all">所有日志</option>
                            <option value="info">信息</option>
                            <option value="warning">警告</option>
                            <option value="error">错误</option>
                        </select>
                    </div>
                </div>
                <div id="logContainer" class="log-container">
                    <div class="loading">正在加载日志</div>
                </div>
            </div>
        </div>
     </div>
     
     <script>
        // 应用程序主对象
        const app = {
            // 当前主题模式
            currentThemeMode: 'auto', // auto, light, dark
            // 实际应用的主题
            currentTheme: 'light',
            // 系统主题监听器
            systemThemeListener: null,
            
            // WebSocket连接
            ws: null,
            
            // 初始化
            init() {
                this.loadTheme();
                this.setupSystemThemeListener();
                try {
                    fetch('/api/server/status')
                        .then(r => r.json())
                        .then(s => { window.__sslEnabled = !!s.ssl_enabled; })
                        .catch(() => {});
                } catch (e) {}
                this.connectWebSocket();
                this.startPeriodicUpdates();
                this.loadInitialData();
            },
            
            // 加载主题
            loadTheme() {
                const savedThemeMode = localStorage.getItem('themeMode') || 'auto';
                this.currentThemeMode = savedThemeMode;
                this.updateThemeSelector();
                this.applyTheme();
            },
            
            // 设置主题模式
            changeTheme(themeMode) {
                this.currentThemeMode = themeMode;
                localStorage.setItem('themeMode', themeMode);
                this.updateThemeSelector();
                this.applyTheme();
            },
            
            // 应用主题
            applyTheme() {
                let actualTheme;
                if (this.currentThemeMode === 'auto') {
                    actualTheme = this.getSystemTheme();
                } else {
                    actualTheme = this.currentThemeMode;
                }
                
                this.currentTheme = actualTheme;
                document.documentElement.setAttribute('data-theme', actualTheme);
            },
            
            // 获取系统主题
            getSystemTheme() {
                if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                    return 'dark';
                }
                return 'light';
            },
            
            // 设置系统主题监听器
            setupSystemThemeListener() {
                if (window.matchMedia) {
                    this.systemThemeListener = window.matchMedia('(prefers-color-scheme: dark)');
                    this.systemThemeListener.addEventListener('change', (e) => {
                        if (this.currentThemeMode === 'auto') {
                            this.applyTheme();
                        }
                    });
                }
            },
            
            // 更新主题选择器
            updateThemeSelector() {
                const selector = document.querySelector('#themeSelector');
                if (selector) {
                    selector.value = this.currentThemeMode;
                }
            },
            
            // 兼容旧的切换主题方法
            toggleTheme() {
                const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
                this.changeTheme(newTheme);
            },
            
            // 连接WebSocket
            connectWebSocket() {
                try {
                    // 检查WebSocket是否已经连接
                    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                        return;
                    }
                    
                    // 动态获取WebSocket URL
                    const protocol = (window.location.protocol === 'https:' || window.__sslEnabled) ? 'wss:' : 'ws:';
                    const host = window.location.hostname;
                    const port = '8081'; // WebSocket端口
                    const wsUrl = `${protocol}//${host}:${port}`;
                    
                    console.log(`尝试连接WebSocket: ${wsUrl}`);
                    this.ws = new WebSocket(wsUrl);
                    
                    this.ws.onopen = () => {
                        console.log('WebSocket连接已建立');
                        this.showNotification('WebSocket连接成功', 'success');
                        this.reconnectAttempts = 0; // 重置重连计数
                    };
                    
                    this.ws.onmessage = (event) => {
                        try {
                            const data = JSON.parse(event.data);
                            this.handleWebSocketMessage(data);
                        } catch (e) {
                            console.error('解析WebSocket消息失败:', e);
                        }
                    };
                    
                    this.ws.onclose = (event) => {
                        console.log(`WebSocket连接已关闭 (代码: ${event.code}, 原因: ${event.reason})`);
                        this.handleWebSocketReconnect();
                    };
                    
                    this.ws.onerror = (error) => {
                        console.error('WebSocket错误:', error);
                        this.showNotification('WebSocket连接错误', 'error');
                    };
                } catch (error) {
                    console.error('WebSocket连接失败:', error);
                    this.showNotification('WebSocket连接失败', 'error');
                }
            },
            
            // 处理WebSocket重连
            handleWebSocketReconnect() {
                if (!this.reconnectAttempts) {
                    this.reconnectAttempts = 0;
                }
                
                this.reconnectAttempts++;
                const maxAttempts = 10;
                const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000); // 指数退避，最大30秒
                
                if (this.reconnectAttempts <= maxAttempts) {
                    console.log(`WebSocket将在${delay/1000}秒后重连 (第${this.reconnectAttempts}次尝试)`);
                    setTimeout(() => this.connectWebSocket(), delay);
                } else {
                    console.error('WebSocket重连次数已达上限，停止重连');
                    this.showNotification('WebSocket连接失败，请检查服务器状态', 'error');
                }
            },
            
            // 处理WebSocket消息
            handleWebSocketMessage(data) {
                if (data.type === 'log') {
                    this.addLogEntry(data.data);
                } else if (data.type === 'status') {
                    this.updateServerStatus(data.data);
                } else if (data.type === 'clients') {
                    this.updateClientList(data.data);
                } else {
                    // 处理直接的日志数据（没有type字段的情况）
                    if (data.timestamp && data.level && data.message) {
                        this.addLogEntry(data);
                    }
                }
            },
            
            // 开始定期更新
            startPeriodicUpdates() {
                // 每2秒更新一次状态和性能数据（保持一致的更新频率）
                setInterval(() => {
                    this.refreshServerStatus();
                    this.refreshPerformance();
                }, 2000);
                
                // 每1秒更新一次客户端列表（保持实时性）
                setInterval(() => {
                    this.refreshClients();
                }, 1000);
            },
            
            // 加载初始数据
            loadInitialData() {
                this.refreshServerStatus();
                this.refreshClients();
                // 移除refreshLogs调用，日志现在通过WebSocket实时推送
                this.refreshPerformance();
                this.refreshSystemInfo();
            },
            
            // 刷新服务器状态
            async refreshServerStatus() {
                try {
                    const response = await fetch('/api/server/status');
                    const data = await response.json();
                    this.updateServerStatus(data);
                } catch (error) {
                    console.error('获取服务器状态失败:', error);
                }
            },
            
            // 更新服务器状态
            updateServerStatus(data) {
                const statusIndicator = document.getElementById('serverStatus');
                const statusText = document.getElementById('serverStatusText');
                const serverState = document.getElementById('serverState');
                const serverPort = document.getElementById('serverPort');
                const connectionCount = document.getElementById('connectionCount');
                const memoryUsage = document.getElementById('memoryUsage');
                const cpuUsage = document.getElementById('cpuUsage');
                const networkTraffic = document.getElementById('networkTraffic');
                const responseTime = document.getElementById('responseTime');
                const uptime = document.getElementById('uptime');
                const clientCount = document.getElementById('clientCount');
                
                if (data.running) {
                    statusIndicator.classList.add('online');
                    statusText.textContent = '服务器运行中';
                    serverState.textContent = '运行中';
                } else {
                    statusIndicator.classList.remove('online');
                    statusText.textContent = '服务器已停止';
                    serverState.textContent = '已停止';
                }
                
                if (serverPort) serverPort.textContent = data.port || '--';
                if (connectionCount) connectionCount.textContent = data.connections || 0;
                if (memoryUsage) memoryUsage.textContent = data.memory_usage || '--';
                if (cpuUsage) {
                    if (data.cpu_usage !== undefined && data.cpu_usage !== '--' && data.cpu_usage !== null) {
                        const numericValue = typeof data.cpu_usage === 'string' ? parseFloat(data.cpu_usage) : data.cpu_usage;
                        if (!isNaN(numericValue) && numericValue >= 0) {
                            // 使用与性能监控卡片相同的平滑处理
                            const smoothedValue = this.smoothCpuData(numericValue);
                            cpuUsage.textContent = `${smoothedValue.toFixed(1)}%`;
                        } else {
                            cpuUsage.textContent = '0.0%';
                        }
                    } else {
                        cpuUsage.textContent = '0.0%';
                    }
                }
                if (networkTraffic) networkTraffic.textContent = data.network_traffic || '--';
                if (responseTime) responseTime.textContent = data.response_time || '--';
                if (uptime) uptime.textContent = this.formatUptime(data.uptime) || '--';
                if (clientCount) clientCount.textContent = data.client_count || 0;
                
                // 更新请求总数和错误率
                const totalRequests = document.getElementById('totalRequests');
                const errorRate = document.getElementById('errorRate');
                if (totalRequests) totalRequests.textContent = data.total_requests || 0;
                if (errorRate) {
                    if (data.error_rate !== undefined && data.error_rate !== null) {
                        errorRate.textContent = `${(data.error_rate * 100).toFixed(1)}%`;
                    } else {
                        errorRate.textContent = '0.0%';
                    }
                }
                
                // 同步更新性能监控卡片中的CPU使用率
                this.syncCpuUsageToPerformanceCard(data.cpu_usage);
            },
            
            // 格式化运行时间
            formatUptime(seconds) {
                if (!seconds || seconds < 0) return '--';
                
                const hours = Math.floor(seconds / 3600);
                const minutes = Math.floor((seconds % 3600) / 60);
                const secs = Math.floor(seconds % 60);
                
                return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
            },
            
            // 同步CPU使用率显示到性能监控卡片（使用平滑数据）
            syncCpuUsageToPerformanceCard(cpuUsage) {
                const cpuUsageChart = document.getElementById('cpuUsageChart');
                if (cpuUsageChart && cpuUsage !== undefined && cpuUsage !== '--' && cpuUsage !== null) {
                    // 对CPU数据进行平滑处理
                    const numericValue = typeof cpuUsage === 'string' ? parseFloat(cpuUsage) : cpuUsage;
                    if (!isNaN(numericValue) && numericValue >= 0) {
                        const smoothedValue = this.smoothCpuData(numericValue);
                        const formattedCpuUsage = `${smoothedValue.toFixed(1)}%`;
                        cpuUsageChart.textContent = formattedCpuUsage;
                    } else {
                        cpuUsageChart.textContent = '0.0%';
                    }
                } else {
                    cpuUsageChart.textContent = '0.0%';
                }
            },
            
            // 同步CPU使用率显示（从性能数据到服务器状态，使用平滑数据）
            syncCpuUsageDisplay(data) {
                const cpuUsage = document.getElementById('cpuUsage');
                if (cpuUsage && data.cpu_usage !== undefined && data.cpu_usage !== '--' && data.cpu_usage !== null) {
                    // 对CPU数据进行平滑处理
                    const numericValue = typeof data.cpu_usage === 'string' ? parseFloat(data.cpu_usage) : data.cpu_usage;
                    if (!isNaN(numericValue) && numericValue >= 0) {
                        const smoothedValue = this.smoothCpuData(numericValue);
                        const formattedCpuUsage = `${smoothedValue.toFixed(1)}%`;
                        cpuUsage.textContent = formattedCpuUsage;
                    } else {
                        cpuUsage.textContent = '0.0%';
                    }
                } else {
                    cpuUsage.textContent = '0.0%';
                }
                
                // 同时更新性能监控卡片（使用相同的平滑处理逻辑）
                this.syncCpuUsageToPerformanceCard(data.cpu_usage);
            },
            
            // 启动服务器
            async startServer() {
                try {
                    const response = await fetch('/api/server/start', { method: 'POST' });
                    const data = await response.json();
                    if (data.success) {
                        this.showNotification('服务器启动成功', 'success');
                        this.refreshServerStatus();
                    } else {
                        this.showNotification('服务器启动失败: ' + data.message, 'error');
                    }
                } catch (error) {
                    this.showNotification('启动服务器时发生错误', 'error');
                }
            },
            
            // 停止服务器
            async stopServer() {
                try {
                    const response = await fetch('/api/server/stop', { method: 'POST' });
                    const data = await response.json();
                    if (data.success) {
                        this.showNotification('服务器已停止', 'success');
                        this.refreshServerStatus();
                    } else {
                        this.showNotification('停止服务器失败: ' + data.message, 'error');
                    }
                } catch (error) {
                    this.showNotification('停止服务器时发生错误', 'error');
                }
            },
            
            // 重启服务器
            async restartServer() {
                try {
                    const response = await fetch('/api/server/restart', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        this.showNotification('Web服务器重启成功', 'success');
                        // 延迟刷新状态，给服务器时间重启
                        setTimeout(() => {
                            this.refreshServerStatus();
                        }, 2000);
                    } else {
                        this.showNotification('重启Web服务器失败: ' + (data.error || '未知错误'), 'error');
                    }
                } catch (error) {
                    console.error('重启Web服务器失败:', error);
                    this.showNotification('重启Web服务器时发生错误', 'error');
                }
            },
            
            // 刷新客户端列表
            async refreshClients() {
                try {
                    const response = await fetch('/api/clients');
                    const data = await response.json();
                    this.updateClientList(data.clients || []);
                } catch (error) {
                    console.error('获取客户端列表失败:', error);
                }
            },
            
            // 更新客户端列表
            updateClientList(clients) {
                const container = document.getElementById('clientList');
                
                if (clients.length === 0) {
                    container.innerHTML = '<div class="loading">暂无客户端连接</div>';
                    return;
                }
                
                const html = clients.map(client => `
                    <div class="client-item">
                        <div class="client-info">
                            <div class="client-id">${client.id}</div>
                            <div class="client-details">
                                ${client.address} | 连接时间: ${new Date(client.connect_time).toLocaleString()}
                                | 状态: ${client.state} | 认证: ${client.authenticated ? '是' : '否'}
                            </div>
                        </div>
                        <div class="client-actions">
                            <button class="btn" onclick="app.viewClientDetail('${client.id}')">详情</button>
                            <button class="btn warning" onclick="app.disconnectClient('${client.id}')">断开</button>
                        </div>
                    </div>
                `).join('');
                
                container.innerHTML = html;
            },
            
            // 查看客户端详情
            viewClientDetail(clientId) {
                window.open(`/client/${clientId}`, '_blank');
            },
            
            // 断开客户端
            async disconnectClient(clientId) {
                if (!confirm('确定要断开此客户端连接吗？')) return;
                
                try {
                    const response = await fetch('/api/clients/disconnect', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ client_id: clientId })
                    });
                    
                    const data = await response.json();
                    if (data.success) {
                        this.showNotification('客户端已断开', 'success');
                        this.refreshClients();
                    } else {
                        this.showNotification('断开客户端失败: ' + data.message, 'error');
                    }
                } catch (error) {
                    this.showNotification('断开客户端时发生错误', 'error');
                }
            },
            
            // 断开所有客户端
            async disconnectAllClients() {
                if (!confirm('确定要断开所有客户端连接吗？')) return;
                
                try {
                    const response = await fetch('/api/clients/disconnect-all', { method: 'POST' });
                    const data = await response.json();
                    if (data.success) {
                        this.showNotification('所有客户端已断开', 'success');
                        this.refreshClients();
                    }
                } catch (error) {
                    this.showNotification('断开所有客户端时发生错误', 'error');
                }
            },
            
            // 刷新日志
            async refreshLogs() {
                try {
                    const response = await fetch('/api/logs');
                    const data = await response.json();
                    this.updateLogs(data.logs || []);
                } catch (error) {
                    console.error('获取日志失败:', error);
                }
            },
            
            // 更新日志
            updateLogs(logs) {
                const container = document.getElementById('logContainer');
                
                if (logs.length === 0) {
                    // 只有在容器中没有实际日志条目时才显示"暂无日志记录"
                    const existingEntries = container.querySelectorAll('.log-entry');
                    if (existingEntries.length === 0) {
                        container.innerHTML = '<div class="loading">暂无日志记录</div>';
                    }
                    return;
                }
                
                const html = logs.map(log => `
                    <div class="log-entry ${log.level.toLowerCase()}">
                        <strong>[${new Date(log.timestamp).toLocaleString()}]</strong> 
                        <span class="log-level">[${log.level}]</span> 
                        ${log.message}
                    </div>
                `).join('');
                
                container.innerHTML = html;
                container.scrollTop = container.scrollHeight;
            },
            
            // 添加日志条目
            addLogEntry(log) {
                const container = document.getElementById('logContainer');
                
                // 检查是否还有loading元素，如果有则清除
                const loadingElement = container.querySelector('.loading');
                if (loadingElement) {
                    container.innerHTML = ''; // 清空容器，移除loading元素
                }
                
                const entry = document.createElement('div');
                entry.className = `log-entry ${log.level.toLowerCase()}`;
                
                // 处理时间戳格式（可能是秒或毫秒）
                let timestamp = log.timestamp;
                
                // 如果时间戳异常小（小于2020年1月1日的时间戳），使用当前时间
                if (timestamp < 1577836800) { // 2020年1月1日的时间戳
                    console.warn('检测到异常时间戳:', timestamp, '使用当前时间替代');
                    timestamp = Date.now() / 1000; // 当前时间的秒时间戳
                }
                
                // 如果是秒时间戳，转换为毫秒
                if (timestamp < 1000000000000) {
                    timestamp = timestamp * 1000;
                }
                
                entry.innerHTML = `
                    <strong>[${new Date(timestamp).toLocaleString()}]</strong> 
                    <span class="log-level">[${log.level}]</span> 
                    ${log.message}
                `;
                
                container.appendChild(entry);
                container.scrollTop = container.scrollHeight;
                
                // 限制日志条目数量
                const entries = container.querySelectorAll('.log-entry');
                if (entries.length > 1000) {
                    entries[0].remove();
                }
            },
            
            // 清空日志
            async clearLogs() {
                if (!confirm('确定要清空所有日志吗？')) return;
                
                try {
                    const response = await fetch('/api/logs/clear', { method: 'POST' });
                    const data = await response.json();
                    if (data.success) {
                        document.getElementById('logContainer').innerHTML = '<div class="loading">日志已清空</div>';
                        this.showNotification('日志已清空', 'success');
                    }
                } catch (error) {
                    this.showNotification('清空日志时发生错误', 'error');
                }
            },
            
            // 下载日志
            downloadLogs() {
                const link = document.createElement('a');
                link.href = '/api/logs/download';
                link.download = `debug-logs-${new Date().toISOString().split('T')[0]}.txt`;
                link.click();
            },
            
            // 过滤日志
            filterLogs() {
                const filter = document.getElementById('logFilter').value;
                const entries = document.querySelectorAll('.log-entry');
                
                entries.forEach(entry => {
                    if (filter === 'all' || entry.classList.contains(filter)) {
                        entry.style.display = 'block';
                    } else {
                        entry.style.display = 'none';
                    }
                });
            },
            
            // 刷新性能数据
            // CPU数据平滑处理
            cpuHistory: [],
            maxHistoryLength: 5,
            
            // 平滑CPU数据
            smoothCpuData(newValue) {
                this.cpuHistory.push(newValue);
                if (this.cpuHistory.length > this.maxHistoryLength) {
                    this.cpuHistory.shift();
                }
                // 计算移动平均值
                const sum = this.cpuHistory.reduce((a, b) => a + b, 0);
                return sum / this.cpuHistory.length;
            },
            
            async refreshPerformance() {
                try {
                    const response = await fetch('/api/server/stats');
                    const data = await response.json();
                    
                    // 对CPU数据进行平滑处理
                    if (data.cpu_usage !== undefined) {
                        data.cpu_usage = this.smoothCpuData(data.cpu_usage);
                    }
                    
                    this.updatePerformanceChart(data);
                    // 同步更新服务器状态中的CPU使用率显示
                    this.syncCpuUsageDisplay(data);
                } catch (error) {
                    console.error('获取性能数据失败:', error);
                }
            },
            
            // 更新性能图表
            updatePerformanceChart(data) {
                const container = document.getElementById('performanceChart');
                
                // 安全地处理数值类型转换
                const safeNumber = (value) => {
                    const num = parseFloat(value);
                    return isNaN(num) ? 0 : num;
                };
                
                // 更新性能监控显示，处理新的API数据结构
                const cpuUsage = data.cpu_usage !== undefined ? `${safeNumber(data.cpu_usage).toFixed(1)}%` : 'N/A';
                const memoryUsage = data.memory_usage ? 
                    `${(safeNumber(data.memory_usage.used) / 1024 / 1024 / 1024).toFixed(2)}GB / ${(safeNumber(data.memory_usage.total) / 1024 / 1024 / 1024).toFixed(2)}GB (${safeNumber(data.memory_usage.percent).toFixed(1)}%)` : 'N/A';
                const networkUsage = data.network_usage ? 
                    (typeof data.network_usage === 'string' ? data.network_usage : 
                     `↑${(safeNumber(data.network_usage.bytes_sent) / 1024 / 1024).toFixed(2)}MB ↓${(safeNumber(data.network_usage.bytes_recv) / 1024 / 1024).toFixed(2)}MB`) : 'N/A';
                const diskUsage = data.disk_usage ? 
                    `${safeNumber(data.disk_usage.used).toFixed(2)}GB / ${safeNumber(data.disk_usage.total).toFixed(2)}GB (${safeNumber(data.disk_usage.percent).toFixed(1)}%)` : 'N/A';
                
                container.innerHTML = `
                    <div class="performance-monitor-container">
                        <div class="performance-header">
                            <h3>📊 性能监控数据</h3>
                            <div class="update-time">最后更新: ${new Date().toLocaleTimeString()}</div>
                        </div>
                        <div class="performance-grid">
                            <div class="performance-card cpu-card">
                                <div class="card-icon">🖥️</div>
                                <div class="card-content">
                                    <div class="card-label">CPU使用率</div>
                                    <div class="card-value">${cpuUsage}</div>
                                </div>
                            </div>
                            <div class="performance-card memory-card">
                                <div class="card-icon">💾</div>
                                <div class="card-content">
                                    <div class="card-label">内存使用</div>
                                    <div class="card-value" title="${memoryUsage}">${memoryUsage}</div>
                                </div>
                            </div>
                            <div class="performance-card network-card">
                                <div class="card-icon">🌐</div>
                                <div class="card-content">
                                    <div class="card-label">网络流量</div>
                                    <div class="card-value" title="${networkUsage}">${networkUsage}</div>
                                </div>
                            </div>
                            <div class="performance-card disk-card">
                                <div class="card-icon">💿</div>
                                <div class="card-content">
                                    <div class="card-label">磁盘使用</div>
                                    <div class="card-value" title="${diskUsage}">${diskUsage}</div>
                                </div>
                            </div>
                            <div class="performance-card connection-card">
                                <div class="card-icon">🔗</div>
                                <div class="card-content">
                                    <div class="card-label">活跃连接</div>
                                    <div class="card-value">${data.active_connections || 0}</div>
                                </div>
                            </div>
                            <div class="performance-card thread-card">
                                <div class="card-icon">🧵</div>
                                <div class="card-content">
                                    <div class="card-label">线程数</div>
                                    <div class="card-value">${data.thread_count || 0}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            },
            
            // 导出性能数据
            exportPerformanceData() {
                const link = document.createElement('a');
                link.href = '/api/server/stats/export';
                link.download = `performance-data-${new Date().toISOString().split('T')[0]}.json`;
                link.click();
            },
            
            // 保存配置
            async saveConfig() {
                const config = {
                    max_connections: parseInt(document.getElementById('maxConnections').value),
                    timeout: parseInt(document.getElementById('timeout').value),
                    log_level: document.getElementById('logLevel').value
                };
                
                try {
                    const response = await fetch('/api/config/update', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(config)
                    });
                    
                    const data = await response.json();
                    if (data.success) {
                        this.showNotification('配置已保存', 'success');
                    } else {
                        this.showNotification('保存配置失败: ' + data.message, 'error');
                    }
                } catch (error) {
                    this.showNotification('保存配置时发生错误', 'error');
                }
            },
            
            // 重置配置
            resetConfig() {
                if (!confirm('确定要重置配置到默认值吗？')) return;
                
                document.getElementById('maxConnections').value = 10;
                document.getElementById('timeout').value = 30;
                document.getElementById('logLevel').value = '信息';
                
                this.showNotification('配置已重置', 'success');
            },
            
            // 刷新系统信息
            async refreshSystemInfo() {
                try {
                    const response = await fetch('/api/system');
                    const data = await response.json();
                    
                    if (data.success) {
                        // 更新系统信息显示
                        document.getElementById('osInfo').textContent = data.data.osInfo || '--';
                        document.getElementById('pythonVersion').textContent = data.data.pythonVersion || '--';
                        document.getElementById('systemUptime').textContent = data.data.uptime || '--';
                        document.getElementById('workingDir').textContent = data.data.workingDir || '--';
                        
                        this.showNotification('系统信息已刷新', 'success');
                    } else {
                        this.showNotification('刷新系统信息失败: ' + data.message, 'error');
                    }
                } catch (error) {
                    console.error('刷新系统信息失败:', error);
                    this.showNotification('刷新系统信息时发生错误', 'error');
                }
            },
            
            // 导出系统信息
            async exportSystemInfo() {
                try {
                    const response = await fetch('/api/system');
                    const data = await response.json();
                    
                    if (data.success) {
                        const systemInfo = data.data;
                        const exportData = {
                            exportTime: new Date().toISOString(),
                            systemInfo: systemInfo
                        };
                        
                        const blob = new Blob([JSON.stringify(exportData, null, 2)], {
                            type: 'application/json'
                        });
                        
                        const link = document.createElement('a');
                        link.href = URL.createObjectURL(blob);
                        link.download = `system-info-${new Date().toISOString().split('T')[0]}.json`;
                        link.click();
                        
                        this.showNotification('系统信息已导出', 'success');
                    } else {
                        this.showNotification('导出系统信息失败: ' + data.message, 'error');
                    }
                } catch (error) {
                    console.error('导出系统信息失败:', error);
                    this.showNotification('导出系统信息时发生错误', 'error');
                }
            },
            
            // 显示通知
            showNotification(message, type = 'info') {
                // 确保通知容器存在
                let notificationContainer = document.getElementById('notification-container');
                if (!notificationContainer) {
                    notificationContainer = document.createElement('div');
                    notificationContainer.id = 'notification-container';
                    notificationContainer.style.cssText = `
                        position: fixed;
                        top: 20px;
                        right: 20px;
                        z-index: 1000;
                        pointer-events: none;
                    `;
                    document.body.appendChild(notificationContainer);
                }
                
                const notification = document.createElement('div');
                notification.style.cssText = `
                    padding: 1rem 1.5rem;
                    border-radius: 0.5rem;
                    color: white;
                    font-weight: 500;
                    margin-bottom: 10px;
                    animation: slideIn 0.3s ease;
                    pointer-events: auto;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                `;
                
                switch (type) {
                    case 'success':
                        notification.style.background = 'var(--success-color)';
                        break;
                    case 'error':
                        notification.style.background = 'var(--danger-color)';
                        break;
                    case 'warning':
                        notification.style.background = 'var(--warning-color)';
                        break;
                    default:
                        notification.style.background = 'var(--primary-color)';
                }
                
                notification.textContent = message;
                notificationContainer.appendChild(notification);
                
                setTimeout(() => {
                    notification.style.animation = 'slideOut 0.3s ease';
                    setTimeout(() => {
                        if (notification.parentNode) {
                            notification.parentNode.removeChild(notification);
                        }
                    }, 300);
                }, 3000);
            }
        };
        
        // 添加动画样式
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
        
        // 页面加载完成后初始化应用
        document.addEventListener('DOMContentLoaded', () => {
            app.init();
        });
     </script>
 </body>
 </html>"""

    def _serve_client_detail_page(self):
        """提供客户端详情页面"""
        self._set_cors_headers()
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        html_content = self._get_client_detail_page_html()
        self.wfile.write(html_content.encode('utf-8'))

    
    def _get_client_detail_page_html(self) -> str:
        """获取客户端详情页面HTML内容"""
        return """
<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>客户端详情 - 远程调试服务器</title>
    <link rel="stylesheet" href="/static/css/style.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .client-detail {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        .detail-section {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            border: 1px solid var(--border-color);
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }
        .detail-section:hover {
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-top: 16px;
        }
        .metric-item {
            background: var(--bg-primary);
            padding: 20px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }
        .metric-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .metric-item::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: linear-gradient(45deg, #3498db, #2ecc71);
        }
        .metric-label {
            font-size: 0.9em;
            color: var(--text-muted);
            margin-bottom: 8px;
            font-weight: 500;
        }
        .metric-value {
            font-size: 1.4em;
            font-weight: bold;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .metric-icon {
            font-size: 1.2em;
            opacity: 0.7;
        }
        .command-history {
            max-height: 400px;
            overflow-y: auto;
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 16px;
        }
        .command-item {
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.9em;
            border-radius: 4px;
            margin-bottom: 8px;
            background: rgba(52, 152, 219, 0.05);
        }
        .command-item:last-child {
            border-bottom: none;
            margin-bottom: 0;
        }
        .back-btn {
            margin-bottom: 24px;
            display: flex;
            gap: 12px;
            align-items: center;
        }
        .chart-container {
            position: relative;
            height: 300px;
            margin-top: 16px;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        .status-connected { background: #2ecc71; }
        .status-disconnected { background: #e74c3c; }
        .status-connecting { background: #f39c12; }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .progress-bar {
            width: 100%;
            height: 8px;
            background: var(--border-color);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 8px;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #3498db, #2ecc71);
            border-radius: 4px;
            transition: width 0.3s ease;
        }
        .real-time-data {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-top: 24px;
        }
        .terminal-container {
            background: #1a1a1a;
            border-radius: 8px;
            padding: 16px;
            font-family: 'Consolas', 'Monaco', monospace;
            color: #00ff00;
            max-height: 300px;
            overflow-y: auto;
            border: 1px solid var(--border-color);
        }
        .terminal-line {
            margin-bottom: 4px;
            word-wrap: break-word;
        }
        .alert-panel {
            background: linear-gradient(135deg, #ff6b6b, #ee5a24);
            color: white;
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 16px;
            display: none;
        }
        .alert-panel.show {
            display: block;
            animation: slideIn 0.3s ease;
        }
        @keyframes slideIn {
            from { transform: translateY(-20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="client-detail">
        <div class="alert-panel" id="alertPanel">
            <strong>⚠️ 警告:</strong> <span id="alertMessage"></span>
        </div>
        
        <div class="back-btn">
            <button class="btn" onclick="history.back()">← 返回</button>
            <button class="btn" onclick="refreshClientDetail()">🔄 刷新</button>
            <button class="btn" onclick="toggleAutoRefresh()" id="autoRefreshBtn">⏱️ 自动刷新</button>
            <button class="btn" onclick="exportClientData()">📊 导出数据</button>
        </div>
        
        <div class="detail-section">
            <h2>📱 客户端基本信息</h2>
            <div id="clientBasicInfo">
                <div class="loading">正在加载客户端信息...</div>
            </div>
        </div>
        
        <div class="detail-section">
            <h2>📊 实时性能监控</h2>
            <div class="metric-grid" id="performanceMetrics">
                <div class="loading">正在加载性能数据...</div>
            </div>
            <div class="real-time-data">
                <div>
                    <h3>📈 性能趋势图</h3>
                    <div class="chart-container">
                        <canvas id="performanceChart"></canvas>
                    </div>
                </div>
                <div>
                    <h3>💻 系统资源</h3>
                    <div class="chart-container">
                        <canvas id="resourceChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="detail-section">
            <h2>📋 命令历史与终端</h2>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
                <div>
                    <h3>📜 历史命令</h3>
                    <div class="command-history" id="commandHistory">
                        <div class="loading">正在加载命令历史...</div>
                    </div>
                </div>
                <div>
                    <h3>🖥️ 实时终端输出</h3>
                    <div class="terminal-container" id="terminalOutput">
                        <div class="terminal-line">等待终端输出...</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="detail-section">
            <h2>🎛️ 客户端控制中心</h2>
            <div class="controls" style="margin-bottom: 20px;">
                <button class="btn success" onclick="sendCommand()">📤 发送命令</button>
                <button class="btn warning" onclick="restartClient()">🔄 重启客户端</button>
                <button class="btn danger" onclick="disconnectClient()">🔌 断开连接</button>
                <button class="btn" onclick="pingClient()">📡 测试连接</button>
                <button class="btn" onclick="getSystemInfo()">💻 系统信息</button>
            </div>
            <div style="display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: center;">
                <input type="text" id="commandInput" placeholder="输入命令 (支持Tab补全)..." 
                       style="padding: 12px; border-radius: 6px; border: 1px solid var(--border-color);">
                <button class="btn" onclick="sendCustomCommand()">📤 发送</button>
            </div>
            <div style="margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap;">
                <button class="btn small" onclick="insertCommand('ls -la')">📁 列出文件</button>
                <button class="btn small" onclick="insertCommand('ps aux')">🔍 进程列表</button>
                <button class="btn small" onclick="insertCommand('df -h')">💾 磁盘使用</button>
                <button class="btn small" onclick="insertCommand('top')">📊 系统监控</button>
                <button class="btn small" onclick="insertCommand('netstat -an')">🌐 网络连接</button>
            </div>
        </div>
        
        <div class="detail-section">
            <h2>🔧 高级功能</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;">
                <div>
                    <h3>📁 文件管理</h3>
                    <div style="display: flex; gap: 8px; margin-bottom: 12px;">
                        <input type="text" id="filePathInput" placeholder="文件路径..." style="flex: 1; padding: 8px; border-radius: 4px; border: 1px solid var(--border-color);">
                        <button class="btn small" onclick="downloadFile()">⬇️ 下载</button>
                        <button class="btn small" onclick="uploadFile()">⬆️ 上传</button>
                    </div>
                    <div id="fileList" style="max-height: 200px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 4px; padding: 8px;">
                        <div style="color: var(--text-muted); text-align: center;">输入路径查看文件</div>
                    </div>
                </div>
                <div>
                    <h3>🔍 日志监控</h3>
                    <div style="display: flex; gap: 8px; margin-bottom: 12px;">
                        <select id="logLevelFilter" style="padding: 8px; border-radius: 4px; border: 1px solid var(--border-color);">
                            <option value="all">所有级别</option>
                            <option value="error">错误</option>
                            <option value="warning">警告</option>
                            <option value="info">信息</option>
                            <option value="debug">调试</option>
                        </select>
                        <button class="btn small" onclick="refreshLogs()">🔄 刷新日志</button>
                        <button class="btn small" onclick="clearLogs()">🗑️ 清空</button>
                    </div>
                    <div id="logOutput" style="max-height: 200px; overflow-y: auto; background: #1a1a1a; color: #00ff00; padding: 8px; border-radius: 4px; font-family: monospace; font-size: 0.85em;">
                        <div>等待日志输出...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // 获取URL参数中的客户端ID
        const urlParams = new URLSearchParams(window.location.search);
        const clientId = urlParams.get('id');
        
        if (!clientId) {
            alert('缺少客户端ID参数');
            history.back();
        }
        
        // 页面加载时获取客户端详情
        document.addEventListener('DOMContentLoaded', function() {
            initCharts();
            refreshClientDetail();
            
            // 键盘事件监听
            document.getElementById('commandInput').addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    sendCustomCommand();
                } else if (e.key === 'Tab') {
                    e.preventDefault();
                    // 简单的命令补全
                    const input = e.target;
                    const value = input.value;
                    const commands = ['ls', 'cd', 'pwd', 'ps', 'top', 'df', 'free', 'uname', 'cat', 'grep', 'find'];
                    const match = commands.find(cmd => cmd.startsWith(value));
                    if (match && value !== match) {
                        input.value = match + ' ';
                    }
                }
            });
            
            // 文件路径输入监听
            document.getElementById('filePathInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    downloadFile();
                }
            });
        });
        
        // 刷新客户端详情
        async function refreshClientDetail() {
            if (!clientId) return;
            
            try {
                const response = await fetch(`/api/client/${clientId}`);
                const data = await response.json();
                
                if (data.client) {
                    updateClientBasicInfo(data.client);
                    updatePerformanceMetrics(data.client);
                    updateCommandHistory(data.client);
                } else {
                    alert('客户端不存在或已断开连接');
                    history.back();
                }
                
            } catch (error) {
                console.error('获取客户端详情失败:', error);
                document.getElementById('clientBasicInfo').innerHTML = '<div style="color: #e74c3c;">加载失败</div>';
            }
        }
        
        // 全局变量
        let performanceChart = null;
        let resourceChart = null;
        let autoRefreshInterval = null;
        let isAutoRefreshEnabled = false;
        let performanceData = {
            labels: [],
            cpu: [],
            memory: [],
            network: []
        };
        
        // 更新基本信息
        function updateClientBasicInfo(client) {
            const container = document.getElementById('clientBasicInfo');
            const statusClass = getStatusClass(client.state);
            container.innerHTML = `
                <div class="metric-grid">
                    <div class="metric-item">
                        <div class="metric-label">客户端ID</div>
                        <div class="metric-value"><span class="metric-icon">🆔</span>${client.id}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">连接地址</div>
                        <div class="metric-value"><span class="metric-icon">🌐</span>${client.address}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">连接状态</div>
                        <div class="metric-value">
                            <span class="status-indicator ${statusClass}"></span>
                            ${getStatusText(client.state)}
                        </div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">认证状态</div>
                        <div class="metric-value">
                            <span class="metric-icon">${client.authenticated ? '✅' : '❌'}</span>
                            ${client.authenticated ? '已认证' : '未认证'}
                        </div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">连接时间</div>
                        <div class="metric-value"><span class="metric-icon">⏰</span>${new Date(client.connect_time).toLocaleString()}</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">运行时长</div>
                        <div class="metric-value"><span class="metric-icon">⏱️</span>${formatDuration(client.uptime)}</div>
                    </div>
                </div>
            `;
        }
        
        // 更新性能指标
        function updatePerformanceMetrics(client) {
            const container = document.getElementById('performanceMetrics');
            const cpuUsage = client.performance_metrics?.cpu_usage || 0;
            const memoryUsage = client.performance_metrics?.memory_usage || 0;
            const networkLatency = client.performance_metrics?.network_latency || 0;
            
            container.innerHTML = `
                <div class="metric-item">
                    <div class="metric-label">📤 发送命令数</div>
                    <div class="metric-value">${client.commands_sent || 0}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">📥 接收字节数</div>
                    <div class="metric-value">${formatBytes(client.bytes_received || 0)}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">📤 发送字节数</div>
                    <div class="metric-value">${formatBytes(client.bytes_sent || 0)}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">⚡ 平均响应时间</div>
                    <div class="metric-value">${(client.avg_response_time || 0).toFixed(2)}ms</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">🖥️ CPU使用率</div>
                    <div class="metric-value">${cpuUsage.toFixed(1)}%</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${cpuUsage}%"></div>
                    </div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">💾 内存使用率</div>
                    <div class="metric-value">${memoryUsage.toFixed(1)}%</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${memoryUsage}%"></div>
                    </div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">🌐 网络延迟</div>
                    <div class="metric-value">${networkLatency.toFixed(2)}ms</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">🕐 最后活动</div>
                    <div class="metric-value">${new Date(client.last_activity).toLocaleString()}</div>
                </div>
            `;
            
            // 更新图表数据
            updateChartData(client);
        }
        
        // 更新命令历史
        function updateCommandHistory(client) {
            const container = document.getElementById('commandHistory');
            
            if (!client.command_history || client.command_history.length === 0) {
                container.innerHTML = '<div style="text-align: center; color: #7f8c8d; padding: 20px;">暂无命令历史</div>';
                return;
            }
            
            container.innerHTML = client.command_history.map(cmd => `
                <div class="command-item">
                    [${new Date(cmd.timestamp).toLocaleTimeString()}] ${cmd.command}
                    ${cmd.response ? `<br><span style="color: #27ae60;">→ ${cmd.response}</span>` : ''}
                </div>
            `).join('');
        }
        
        // 发送命令
        function sendCommand() {
            const command = prompt('请输入要发送的命令:');
            if (command) {
                sendCustomCommand(command);
            }
        }
        
        // 发送自定义命令
        async function sendCustomCommand(command) {
            if (!command) {
                command = document.getElementById('commandInput').value.trim();
            }
            
            if (!command) {
                alert('请输入命令');
                return;
            }
            
            try {
                const response = await fetch('/api/command/send', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        client_id: clientId,
                        command: command
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('命令发送成功');
                    document.getElementById('commandInput').value = '';
                    // 刷新命令历史
                    setTimeout(refreshClientDetail, 1000);
                } else {
                    alert('命令发送失败: ' + data.error);
                }
                
            } catch (error) {
                console.error('发送命令失败:', error);
                alert('发送命令失败');
            }
        }
        
        // 重启客户端
        async function restartClient() {
            if (!confirm('确定要重启客户端吗？')) {
                return;
            }
            
            try {
                await sendCustomCommand('restart');
            } catch (error) {
                console.error('重启客户端失败:', error);
                alert('重启客户端失败');
            }
        }
        
        // 断开客户端
        async function disconnectClient() {
            if (!confirm('确定要断开客户端连接吗？')) {
                return;
            }
            
            try {
                const response = await fetch('/api/clients/disconnect', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ client_id: clientId })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('客户端已断开连接');
                    history.back();
                } else {
                    alert('断开连接失败: ' + data.error);
                }
                
            } catch (error) {
                console.error('断开客户端失败:', error);
                alert('断开连接失败');
            }
        }
        
        // 图表初始化和更新
        function initCharts() {
            // 性能趋势图
            const performanceCtx = document.getElementById('performanceChart').getContext('2d');
            performanceChart = new Chart(performanceCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'CPU使用率 (%)',
                        data: [],
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        tension: 0.4
                    }, {
                        label: '内存使用率 (%)',
                        data: [],
                        borderColor: '#2ecc71',
                        backgroundColor: 'rgba(46, 204, 113, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'top'
                        }
                    }
                }
            });
            
            // 系统资源图
            const resourceCtx = document.getElementById('resourceChart').getContext('2d');
            resourceChart = new Chart(resourceCtx, {
                type: 'doughnut',
                data: {
                    labels: ['已使用CPU', '空闲CPU', '已使用内存', '空闲内存'],
                    datasets: [{
                        data: [0, 100, 0, 100],
                        backgroundColor: ['#e74c3c', '#ecf0f1', '#f39c12', '#ecf0f1'],
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        }
        
        function updateChartData(client) {
            const now = new Date().toLocaleTimeString();
            const cpuUsage = client.performance_metrics?.cpu_usage || 0;
            const memoryUsage = client.performance_metrics?.memory_usage || 0;
            
            // 更新性能趋势图
            if (performanceChart) {
                performanceData.labels.push(now);
                performanceData.cpu.push(cpuUsage);
                performanceData.memory.push(memoryUsage);
                
                // 保持最近20个数据点
                if (performanceData.labels.length > 20) {
                    performanceData.labels.shift();
                    performanceData.cpu.shift();
                    performanceData.memory.shift();
                }
                
                performanceChart.data.labels = performanceData.labels;
                performanceChart.data.datasets[0].data = performanceData.cpu;
                performanceChart.data.datasets[1].data = performanceData.memory;
                performanceChart.update('none');
            }
            
            // 更新资源图
            if (resourceChart) {
                resourceChart.data.datasets[0].data = [
                    cpuUsage, 100 - cpuUsage,
                    memoryUsage, 100 - memoryUsage
                ];
                resourceChart.update('none');
            }
        }
        
        // 自动刷新功能
        function toggleAutoRefresh() {
            const btn = document.getElementById('autoRefreshBtn');
            if (isAutoRefreshEnabled) {
                clearInterval(autoRefreshInterval);
                isAutoRefreshEnabled = false;
                btn.textContent = '⏱️ 自动刷新';
                btn.style.background = '';
            } else {
                autoRefreshInterval = setInterval(refreshClientDetail, 5000);
                isAutoRefreshEnabled = true;
                btn.textContent = '⏹️ 停止刷新';
                btn.style.background = '#2ecc71';
            }
        }
        
        // 导出数据功能
        function exportClientData() {
            const data = {
                timestamp: new Date().toISOString(),
                clientId: clientId,
                performanceData: performanceData,
                // 可以添加更多数据
            };
            
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `client_${clientId}_data_${new Date().toISOString().slice(0, 10)}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }
        
        // 新增功能函数
        function insertCommand(command) {
            document.getElementById('commandInput').value = command;
        }
        
        function pingClient() {
            sendCustomCommand('ping');
        }
        
        function getSystemInfo() {
            sendCustomCommand('uname -a && cat /proc/cpuinfo | head -20');
        }
        
        function showAlert(message, type = 'warning') {
            const alertPanel = document.getElementById('alertPanel');
            const alertMessage = document.getElementById('alertMessage');
            alertMessage.textContent = message;
            alertPanel.className = `alert-panel show ${type}`;
            
            setTimeout(() => {
                alertPanel.classList.remove('show');
            }, 5000);
        }
        
        // 文件管理功能
        function downloadFile() {
            const filePath = document.getElementById('filePathInput').value.trim();
            if (!filePath) {
                alert('请输入文件路径');
                return;
            }
            sendCustomCommand(`cat "${filePath}"`);
        }
        
        function uploadFile() {
            const input = document.createElement('input');
            input.type = 'file';
            input.onchange = function(e) {
                const file = e.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        const content = e.target.result;
                        const filePath = document.getElementById('filePathInput').value.trim() || `/tmp/${file.name}`;
                        sendCustomCommand(`echo '${content}' > "${filePath}"`);
                    };
                    reader.readAsText(file);
                }
            };
            input.click();
        }
        
        // 日志功能
        function refreshLogs() {
            const level = document.getElementById('logLevelFilter').value;
            sendCustomCommand(`journalctl -n 50 ${level !== 'all' ? '-p ' + level : ''}`);
        }
        
        function clearLogs() {
            document.getElementById('logOutput').innerHTML = '<div>日志已清空</div>';
        }
        
        // 工具函数
        function getStatusText(state) {
            const statusMap = {
                'connecting': '连接中',
                'connected': '已连接',
                'authenticated': '已认证',
                'disconnected': '已断开',
                'error': '错误'
            };
            return statusMap[state] || state;
        }
        
        function getStatusClass(state) {
            const classMap = {
                'connecting': 'status-connecting',
                'connected': 'status-connected',
                'authenticated': 'status-connected',
                'disconnected': 'status-disconnected',
                'error': 'status-disconnected'
            };
            return classMap[state] || 'status-disconnected';
        }
        
        function formatBytes(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }
        
        function formatDuration(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);
            return `${hours}h ${minutes}m ${secs}s`;
        }
        
        // 页面初始化完成
        console.log('客户端详情页面已加载完成');
    </script>
</body>
</html>
        """
    
    def _get_client_management_page_html(self) -> str:
        """获取客户端管理页面HTML内容"""
        return """
<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>客户端管理 - 远程调试服务器</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.1);
            position: relative;
        }
        
        .nav-links {
            position: absolute;
            top: 20px;
            right: 20px;
            display: flex;
            gap: 15px;
        }
        
        .nav-link {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 500;
            font-size: 14px;
            transition: all 0.3s ease;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
        }
        
        .nav-link:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        .header h1 {
            color: #2d3748;
            margin-bottom: 8px;
            font-size: 28px;
            font-weight: 600;
        }
        
        .status-bar {
            display: flex;
            gap: 24px;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
        }
        
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #10b981;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .main-content {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.1);
        }
        
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 2px solid #e2e8f0;
        }
        
        .section-header h2 {
            color: #2d3748;
            font-size: 20px;
            font-weight: 600;
        }
        
        .controls {
            display: flex;
            gap: 12px;
        }
        
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        
        .btn.primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn.primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        .btn.danger {
            background: linear-gradient(135deg, #fc466b 0%, #3f5efb 100%);
            color: white;
        }
        
        .btn.danger:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(252, 70, 107, 0.4);
        }
        
        .clients-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 16px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .clients-table th,
        .clients-table td {
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }
        
        .clients-table th {
            background: #f8fafc;
            font-weight: 600;
            color: #4a5568;
            font-size: 14px;
        }
        
        .clients-table td {
            font-size: 14px;
            color: #2d3748;
        }
        
        .clients-table tr:hover {
            background: #f8fafc;
        }
        
        .status-badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }
        
        .status-connected {
            background: #d1fae5;
            color: #065f46;
        }
        
        .status-disconnected {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #6b7280;
        }
        
        .loading::after {
            content: '';
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #d1d5db;
            border-radius: 50%;
            border-top-color: #667eea;
            animation: spin 1s linear infinite;
            margin-left: 8px;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #6b7280;
        }
        
        .empty-state h3 {
            margin-bottom: 8px;
            color: #4b5563;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="nav-links">
                <a href="/" class="nav-link">🏠 主页</a>
                <a href="/websocket_test" class="nav-link">🔌 WebSocket测试</a>
            </div>
            <h1>🔧 客户端管理</h1>
            <div class="status-bar">
                <div class="status-item">
                    <div class="status-indicator" id="serverStatus"></div>
                    <span id="serverStatusText">检查中...</span>
                </div>
                <div class="status-item">
                    <span>客户端: <strong id="clientCount">0</strong></span>
                </div>
                <div class="status-item">
                    <span>最后更新: <strong id="lastUpdate">--</strong></span>
                </div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="section-header">
                <h2>📱 连接的客户端</h2>
                <div class="controls">
                    <button class="btn primary" onclick="refreshClients()">🔄 刷新</button>
                    <button class="btn danger" onclick="disconnectAll()">❌ 断开所有</button>
                </div>
            </div>
            
            <div id="clientsContainer">
                <div class="loading">正在加载客户端信息...</div>
            </div>
        </div>
    </div>
    
    <script>
        let clients = [];
        let refreshInterval;
        
        // 页面加载完成后初始化
        document.addEventListener('DOMContentLoaded', function() {
            checkServerStatus();
            loadClients();
            startAutoRefresh();
        });
        
        // 检查服务器状态
        async function checkServerStatus() {
            try {
                const response = await fetch('/api/server/status');
                const data = await response.json();
                
                const statusElement = document.getElementById('serverStatus');
                const statusTextElement = document.getElementById('serverStatusText');
                
                if (data.running) {
                    statusElement.style.background = '#10b981';
                    statusTextElement.textContent = '服务器运行中';
                } else {
                    statusElement.style.background = '#ef4444';
                    statusTextElement.textContent = '服务器已停止';
                }
            } catch (error) {
                console.error('检查服务器状态失败:', error);
                document.getElementById('serverStatusText').textContent = '状态未知';
            }
        }
        
        // 加载客户端列表
        async function loadClients() {
            try {
                const response = await fetch('/api/clients');
                const data = await response.json();
                
                clients = data.clients || [];
                updateClientCount();
                renderClientsTable();
                updateLastUpdate();
            } catch (error) {
                console.error('加载客户端失败:', error);
                showError('加载客户端信息失败');
            }
        }
        
        // 更新客户端数量
        function updateClientCount() {
            document.getElementById('clientCount').textContent = clients.length;
        }
        
        // 更新最后更新时间
        function updateLastUpdate() {
            const now = new Date();
            const timeString = now.toLocaleTimeString('zh-CN');
            document.getElementById('lastUpdate').textContent = timeString;
        }
        
        // 渲染客户端表格
        function renderClientsTable() {
            const container = document.getElementById('clientsContainer');
            
            if (clients.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <h3>暂无客户端连接</h3>
                        <p>等待客户端连接到服务器...</p>
                    </div>
                `;
                return;
            }
            
            const tableHTML = `
                <table class="clients-table">
                    <thead>
                        <tr>
                            <th>客户端ID</th>
                            <th>IP地址</th>
                            <th>连接时间</th>
                            <th>状态</th>
                            <th>消息数</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${clients.map(client => `
                            <tr>
                                <td>${client.id || '未知'}</td>
                                <td>${client.address || '未知'}</td>
                                <td>${formatTime(client.connect_time)}</td>
                                <td>
                                    <span class="status-badge ${getStatusClass(client.status)}">
                                        ${getStatusText(client.status)}
                                    </span>
                                </td>
                                <td>${client.message_count || 0}</td>
                                <td>
                                    <button class="btn danger" onclick="disconnectClient('${client.id}')">
                                        断开
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            
            container.innerHTML = tableHTML;
        }
        
        // 格式化时间
        function formatTime(timestamp) {
            if (!timestamp) return '未知';
            const date = new Date(timestamp * 1000);
            return date.toLocaleTimeString('zh-CN');
        }
        
        // 获取状态样式类
        function getStatusClass(status) {
            switch (status) {
                case 'connected':
                case 'authenticated':
                    return 'status-connected';
                case 'disconnected':
                case 'error':
                    return 'status-disconnected';
                default:
                    return 'status-disconnected';
            }
        }
        
        // 获取状态文本
        function getStatusText(status) {
            const statusMap = {
                'connecting': '连接中',
                'connected': '已连接',
                'authenticated': '已认证',
                'disconnected': '已断开',
                'error': '错误'
            };
            return statusMap[status] || '未知';
        }
        
        // 刷新客户端列表
        async function refreshClients() {
            await loadClients();
        }
        
        // 断开指定客户端
        async function disconnectClient(clientId) {
            if (!confirm(`确定要断开客户端 ${clientId} 吗？`)) {
                return;
            }
            
            try {
                const response = await fetch('/api/clients/disconnect', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ client_id: clientId })
                });
                
                if (response.ok) {
                    await loadClients();
                } else {
                    showError('断开客户端失败');
                }
            } catch (error) {
                console.error('断开客户端失败:', error);
                showError('断开客户端失败');
            }
        }
        
        // 断开所有客户端
        async function disconnectAll() {
            if (!confirm('确定要断开所有客户端吗？')) {
                return;
            }
            
            try {
                const promises = clients.map(client => 
                    fetch('/api/clients/disconnect', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ client_id: client.id })
                    })
                );
                
                await Promise.all(promises);
                await loadClients();
            } catch (error) {
                console.error('断开所有客户端失败:', error);
                showError('断开所有客户端失败');
            }
        }
        
        // 显示错误信息
        function showError(message) {
            const container = document.getElementById('clientsContainer');
            container.innerHTML = `
                <div class="empty-state">
                    <h3>❌ 错误</h3>
                    <p>${message}</p>
                    <button class="btn primary" onclick="loadClients()">重试</button>
                </div>
            `;
        }
        
        // 开始自动刷新
        function startAutoRefresh() {
            refreshInterval = setInterval(() => {
                loadClients();
                checkServerStatus();
            }, 5000); // 每5秒刷新一次
        }
        
        // 页面卸载时清理定时器
        window.addEventListener('beforeunload', function() {
            if (refreshInterval) {
                clearInterval(refreshInterval);
            }
        });
    </script>
</body>
</html>
        """
    
    def _get_websocket_test_page_html(self) -> str:
        """获取WebSocket测试页面HTML"""
        return '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebSocket 连接测试 - XuanWu Debug</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 30px;
            text-align: center;
            position: relative;
        }
        
        .nav-back {
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            text-decoration: none;
            padding: 10px 20px;
            border-radius: 25px;
            font-weight: 600;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
        }
        
        .nav-back:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        }
        
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        .content {
            padding: 30px;
        }
        
        .test-section {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 25px;
            border-left: 4px solid #4facfe;
        }
        
        .test-section h2 {
            color: #333;
            margin-bottom: 15px;
            font-size: 1.4em;
        }
        
        .connection-status {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 20px;
            padding: 15px;
            border-radius: 8px;
            font-weight: bold;
        }
        
        .status-disconnected {
            background: #fee;
            color: #c53030;
            border: 1px solid #feb2b2;
        }
        
        .status-connecting {
            background: #fef5e7;
            color: #d69e2e;
            border: 1px solid #fbd38d;
        }
        
        .status-connected {
            background: #f0fff4;
            color: #38a169;
            border: 1px solid #9ae6b4;
        }
        
        .controls {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(79, 172, 254, 0.4);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%);
            color: white;
        }
        
        .btn-danger:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255, 107, 107, 0.4);
        }
        
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none !important;
            box-shadow: none !important;
        }
        
        .input-group {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
            align-items: center;
        }
        
        .input-group label {
            min-width: 100px;
            font-weight: 600;
            color: #555;
        }
        
        .input-group input {
            flex: 1;
            padding: 10px;
            border: 2px solid #e2e8f0;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.3s ease;
        }
        
        .input-group input:focus {
            outline: none;
            border-color: #4facfe;
        }
        
        .message-area {
            background: #1a202c;
            color: #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            line-height: 1.5;
            max-height: 400px;
            overflow-y: auto;
            margin-bottom: 15px;
        }
        
        .message-item {
            margin-bottom: 8px;
            padding: 5px 0;
            border-bottom: 1px solid #2d3748;
        }
        
        .message-time {
            color: #a0aec0;
            font-size: 11px;
        }
        
        .message-type-info {
            color: #63b3ed;
        }
        
        .message-type-success {
            color: #68d391;
        }
        
        .message-type-error {
            color: #fc8181;
        }
        
        .message-type-warning {
            color: #f6e05e;
        }
        
        .send-message {
            display: flex;
            gap: 10px;
        }
        
        .send-message input {
            flex: 1;
            padding: 12px;
            border: 2px solid #e2e8f0;
            border-radius: 6px;
            font-size: 14px;
        }
        
        .navigation {
            text-align: center;
            margin-top: 20px;
        }
        
        .nav-link {
            color: #4facfe;
            text-decoration: none;
            font-weight: 600;
            margin: 0 15px;
            transition: color 0.3s ease;
        }
        
        .nav-link:hover {
            color: #2b6cb0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <a href="/" class="nav-back">← 返回主页</a>
            <h1>🔌 WebSocket 连接测试</h1>
            <p>测试和调试 WebSocket 连接状态</p>
        </div>
        
        <div class="content">
            <div class="test-section">
                <h2>📡 连接状态</h2>
                <div id="connectionStatus" class="connection-status status-disconnected">
                    <span>🔴</span>
                    <span>未连接</span>
                </div>
                
                <div class="input-group">
                    <label>WebSocket URL:</label>
                    <input type="text" id="wsUrl" placeholder="ws://localhost:8081">
                </div>
                
                <div class="controls">
                    <button id="connectBtn" class="btn btn-primary">🔗 连接</button>
                    <button id="disconnectBtn" class="btn btn-danger" disabled>❌ 断开</button>
                    <button id="clearBtn" class="btn btn-primary">🗑️ 清空日志</button>
                </div>
            </div>
            
            <div class="test-section">
                <h2>📝 消息日志</h2>
                <div id="messageArea" class="message-area">
                    <div class="message-item">
                        <span class="message-time">[等待连接...]</span>
                        <span class="message-type-info">准备就绪，请点击连接按钮开始测试</span>
                    </div>
                </div>
            </div>
            
            <div class="test-section">
                <h2>💬 发送消息</h2>
                <div class="send-message">
                    <input type="text" id="messageInput" placeholder="输入要发送的消息..." disabled>
                    <button id="sendBtn" class="btn btn-primary" disabled>📤 发送</button>
                </div>
            </div>
            
            <div class="navigation">
                <a href="/" class="nav-link">🏠 返回主页</a>
                <a href="/client_management" class="nav-link">👥 客户端管理</a>
            </div>
        </div>
    </div>
    
    <script>
        class WebSocketTester {
            constructor() {
                this.ws = null;
                this.reconnectAttempts = 0;
                this.maxReconnectAttempts = 5;
                this.init();
            }
            
            init() {
                // 设置默认URL
                const protocol = (window.location.protocol === 'https:' || window.__sslEnabled) ? 'wss:' : 'ws:';
                const host = window.location.hostname;
                const port = '8081';
                document.getElementById('wsUrl').value = `${protocol}//${host}:${port}`;
                try {
                    fetch('/api/server/status')
                        .then(r => r.json())
                        .then(s => {
                            window.__sslEnabled = !!s.ssl_enabled;
                            const proto2 = window.__sslEnabled ? 'wss:' : 'ws:';
                            document.getElementById('wsUrl').value = `${proto2}//${host}:${port}`;
                        })
                        .catch(() => {});
                } catch (e) {}
                
                // 绑定事件
                document.getElementById('connectBtn').addEventListener('click', () => this.connect());
                document.getElementById('disconnectBtn').addEventListener('click', () => this.disconnect());
                document.getElementById('clearBtn').addEventListener('click', () => this.clearMessages());
                document.getElementById('sendBtn').addEventListener('click', () => this.sendMessage());
                
                // 回车发送消息
                document.getElementById('messageInput').addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') {
                        this.sendMessage();
                    }
                });
            }
            
            connect() {
                const url = document.getElementById('wsUrl').value.trim();
                if (!url) {
                    this.addMessage('请输入有效的WebSocket URL', 'error');
                    return;
                }
                
                this.updateStatus('connecting', '🟡 连接中...');
                this.addMessage(`尝试连接到: ${url}`, 'info');
                
                try {
                    this.ws = new WebSocket(url);
                    
                    this.ws.onopen = () => {
                        this.updateStatus('connected', '🟢 已连接');
                        this.addMessage('WebSocket连接成功建立', 'success');
                        this.reconnectAttempts = 0;
                        
                        document.getElementById('connectBtn').disabled = true;
                        document.getElementById('disconnectBtn').disabled = false;
                        document.getElementById('messageInput').disabled = false;
                        document.getElementById('sendBtn').disabled = false;
                    };
                    
                    this.ws.onmessage = (event) => {
                        this.addMessage(`收到消息: ${event.data}`, 'success');
                    };
                    
                    this.ws.onclose = (event) => {
                        this.updateStatus('disconnected', '🔴 未连接');
                        this.addMessage(`连接已关闭 (代码: ${event.code}, 原因: ${event.reason || '未知'})`, 'warning');
                        
                        document.getElementById('connectBtn').disabled = false;
                        document.getElementById('disconnectBtn').disabled = true;
                        document.getElementById('messageInput').disabled = true;
                        document.getElementById('sendBtn').disabled = true;
                    };
                    
                    this.ws.onerror = (error) => {
                        this.addMessage('WebSocket连接错误', 'error');
                        console.error('WebSocket error:', error);
                    };
                    
                } catch (error) {
                    this.updateStatus('disconnected', '🔴 连接失败');
                    this.addMessage(`连接失败: ${error.message}`, 'error');
                }
            }
            
            disconnect() {
                if (this.ws) {
                    this.ws.close();
                    this.addMessage('主动断开连接', 'info');
                }
            }
            
            sendMessage() {
                const input = document.getElementById('messageInput');
                const message = input.value.trim();
                
                if (!message) {
                    this.addMessage('请输入要发送的消息', 'warning');
                    return;
                }
                
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    try {
                        this.ws.send(message);
                        this.addMessage(`发送消息: ${message}`, 'info');
                        input.value = '';
                    } catch (error) {
                        this.addMessage(`发送失败: ${error.message}`, 'error');
                    }
                } else {
                    this.addMessage('WebSocket未连接，无法发送消息', 'error');
                }
            }
            
            updateStatus(status, text) {
                const statusEl = document.getElementById('connectionStatus');
                statusEl.className = `connection-status status-${status}`;
                statusEl.innerHTML = `<span>${text.split(' ')[0]}</span><span>${text.split(' ').slice(1).join(' ')}</span>`;
            }
            
            addMessage(message, type = 'info') {
                const messageArea = document.getElementById('messageArea');
                const messageEl = document.createElement('div');
                messageEl.className = 'message-item';
                
                const time = new Date().toLocaleTimeString();
                messageEl.innerHTML = `
                    <span class="message-time">[${time}]</span>
                    <span class="message-type-${type}">${message}</span>
                `;
                
                messageArea.appendChild(messageEl);
                messageArea.scrollTop = messageArea.scrollHeight;
            }
            
            clearMessages() {
                const messageArea = document.getElementById('messageArea');
                messageArea.innerHTML = `
                    <div class="message-item">
                        <span class="message-time">[${new Date().toLocaleTimeString()}]</span>
                        <span class="message-type-info">日志已清空</span>
                    </div>
                `;
            }
        }
        
        // 初始化测试器
        document.addEventListener('DOMContentLoaded', () => {
            new WebSocketTester();
        });
    </script>
</body>
</html>
        '''


class WebSocketLogHandler:
    """WebSocket日志处理器"""
    
    def __init__(self):
        self.clients = set()
        self.server = None
        self.running = False
    
    async def register_client(self, websocket):
        """注册WebSocket客户端"""
        self.clients.add(websocket)
        print(f"WebSocket客户端已连接，当前连接数: {len(self.clients)}")
    
    async def unregister_client(self, websocket):
        """注销WebSocket客户端"""
        self.clients.discard(websocket)
        print(f"WebSocket客户端已断开，当前连接数: {len(self.clients)}")
    
    async def broadcast_log(self, log_data: dict):
        """广播日志到所有WebSocket客户端"""
        if not self.clients:
            return
        
        message = json.dumps(log_data, ensure_ascii=False)
        disconnected = set()
        
        for client in self.clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
            except Exception as e:
                print(f"发送WebSocket消息失败: {e}")
                disconnected.add(client)
        
        # 移除断开的客户端
        for client in disconnected:
            self.clients.discard(client)
    
    async def handle_websocket(self, websocket, path=None):
        """处理WebSocket连接"""
        await self.register_client(websocket)
        try:
            async for message in websocket:
                # 处理客户端消息（如果需要）
                pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister_client(websocket)
    
    def start_websocket_server(self, host: str = "127.0.0.1", port: int = 8081, ssl_context=None):
        """启动WebSocket服务器"""
        if self.running:
            return
        
        self.running = True
        
        def run_server():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                async def start_server_async():
                    # 添加自定义的process_request函数来处理连接验证
                    async def process_request(connection, request):
                        # 检查是否为有效的WebSocket请求
                        try:
                            # request是Request对象，headers是Headers对象
                            headers = request.headers
                            connection_header = headers.get('Connection', '').lower()
                            upgrade_header = headers.get('Upgrade', '').lower()
                            
                            if 'upgrade' not in connection_header or upgrade_header != 'websocket':
                                return (400, [], b'\xe9\x94\x99\xe8\xaf\xaf\xe8\xaf\xb7\xe6\xb1\x82: \xe6\xad\xa4\xe7\xab\xaf\xe7\x82\xb9\xe4\xbb\x85\xe6\x8e\xa5\xe5\x8f\x97WebSocket\xe8\xbf\x9e\xe6\x8e\xa5\xe3\x80\x82\xe8\xaf\xb7\xe4\xbd\xbf\xe7\x94\xa8WebSocket\xe5\xae\xa2\xe6\x88\xb7\xe7\xab\xaf\xe8\xbf\x9b\xe8\xa1\x8c\xe8\xbf\x9e\xe6\x8e\xa5\xe3\x80\x82')
                        except Exception as e:
                            # 如果无法获取头部信息，允许连接继续
                            print(f"WebSocket头部检查错误: {e}")
                            # 对于无法解析的请求，直接允许连接
                            pass
                        
                        return None  # 允许连接
                    
                    self.server = await websockets.serve(
                        self.handle_websocket, host, port,
                        process_request=process_request,
                        ssl=ssl_context
                    )
                    print(f"WebSocket服务器已启动在 {'wss' if ssl_context else 'ws'}://{host}:{port}")
                    await self.server.wait_closed()
                
                loop.run_until_complete(start_server_async())
            except Exception as e:
                print(f"WebSocket服务器启动失败: {e}")
            finally:
                loop.close()
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
    
    def stop_websocket_server(self):
        """停止WebSocket服务器"""
        self.running = False
        if hasattr(self, 'server') and self.server:
            try:
                self.server.close()
                print("WebSocket服务器已停止")
            except (OSError, AttributeError) as e:
                # 处理WinError 10038和其他套接字错误
                if "10038" in str(e) or "非套接字" in str(e):
                    print(f"警告: WebSocket服务器套接字已关闭或无效: {str(e)}")
                else:
                    print(f"警告: 停止WebSocket服务器时发生错误: {str(e)}")
            except Exception as e:
                print(f"停止WebSocket服务器时出错: {e}")


class DebugWebServer(QObject):
    """调试Web服务器"""
    
    # 信号
    server_started = pyqtSignal()
    server_stopped = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, config: WebServerConfig, debug_server=None, dev_tools_panel=None):
        super().__init__()
        self.config = config
        self.debug_server = debug_server
        self.dev_tools_panel = dev_tools_panel
        self.http_server = None
        self.websocket_handler = WebSocketLogHandler()
        self.running = False
        self.server_thread = None
    
    def start_server(self) -> bool:
        """启动Web服务器"""
        if self.running:
            return True
        
        try:
            # 创建HTTP服务器
            def handler_factory(*args, **kwargs):
                return DebugWebHandler(*args, debug_server=self.debug_server, dev_tools_panel=self.dev_tools_panel, **kwargs)
            
            self.http_server = HTTPServer((self.config.host, self.config.port), handler_factory)
            
            # 启动HTTP服务器线程
            self.server_thread = threading.Thread(target=self._run_http_server, daemon=True)
            self.server_thread.start()
            
            # 启动WebSocket服务器
            if self.config.websocket_port:
                ssl_ctx = None
                try:
                    if self.debug_server and getattr(self.debug_server.config, 'enable_ssl', False):
                        ssl_ctx = getattr(self.debug_server, 'ssl_context', None)
                except Exception:
                    ssl_ctx = None
                
                self.websocket_handler.start_websocket_server(
                    self.config.host, self.config.websocket_port, ssl_ctx
                )
            
            self.running = True
            self.server_started.emit()
            
            print(f"Web服务器已启动在 http://{self.config.host}:{self.config.port}")
            if self.config.websocket_port:
                scheme = 'wss' if (self.debug_server and getattr(self.debug_server.config, 'enable_ssl', False)) else 'ws'
                print(f"WebSocket服务器已启动在 {scheme}://{self.config.host}:{self.config.websocket_port}")
            
            return True
            
        except Exception as e:
            error_msg = f"启动Web服务器失败: {str(e)}"
            print(error_msg)
            self.error_occurred.emit(error_msg)
            return False
    
    def stop_server(self):
        """停止Web服务器"""
        if not self.running:
            return
        
        try:
            self.running = False
            
            # 停止HTTP服务器
            if self.http_server:
                try:
                    self.http_server.shutdown()
                except (OSError, AttributeError) as e:
                    # 处理WinError 10038和其他套接字错误
                    if "10038" in str(e) or "非套接字" in str(e):
                        print(f"警告: HTTP服务器套接字已关闭或无效: {str(e)}")
                    else:
                        print(f"警告: HTTP服务器关闭时发生错误: {str(e)}")
                
                try:
                    self.http_server.server_close()
                except (OSError, AttributeError) as e:
                    # 处理服务器关闭时的错误
                    if "10038" in str(e) or "非套接字" in str(e):
                        print(f"警告: HTTP服务器套接字关闭错误: {str(e)}")
                    else:
                        print(f"警告: HTTP服务器资源清理错误: {str(e)}")
                
                self.http_server = None
            
            # 停止WebSocket服务器
            try:
                self.websocket_handler.stop_websocket_server()
            except (OSError, AttributeError) as e:
                # 处理WebSocket服务器停止时的错误
                if "10038" in str(e) or "非套接字" in str(e):
                    print(f"警告: WebSocket服务器套接字已关闭或无效: {str(e)}")
                else:
                    print(f"警告: WebSocket服务器停止时发生错误: {str(e)}")
            
            self.server_stopped.emit()
            print("Web服务器已停止")
            
        except Exception as e:
            # 检查是否为已知的套接字错误
            if "10038" in str(e) or "非套接字" in str(e):
                print(f"警告: Web服务器套接字错误已处理: {str(e)}")
                self.server_stopped.emit()  # 仍然发出停止信号
            else:
                error_msg = f"停止Web服务器失败: {str(e)}"
                print(error_msg)
                self.error_occurred.emit(error_msg)
    
    def _run_http_server(self):
        """运行HTTP服务器"""
        try:
            self.http_server.serve_forever()
        except Exception as e:
            if self.running:  # 只有在运行状态下才报告错误
                error_msg = f"HTTP服务器错误: {str(e)}"
                print(error_msg)
                self.error_occurred.emit(error_msg)
    
    def broadcast_log(self, log_data: dict):
        """广播日志到WebSocket客户端"""
        if self.websocket_handler and self.running:
            # 在异步环境中广播日志
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.websocket_handler.broadcast_log(log_data))
            except RuntimeError:
                # 如果没有运行的事件循环，使用线程池执行
                import threading
                def run_async():
                    try:
                        asyncio.run(self.websocket_handler.broadcast_log(log_data))
                    except Exception as e:
                        print(f"广播日志失败: {e}")
                
                thread = threading.Thread(target=run_async, daemon=True)
                thread.start()
    
    def is_running(self) -> bool:
        """检查服务器是否运行中"""
        return self.running
    
    def get_server_url(self) -> str:
        """获取服务器URL"""
        return f"http://{self.config.host}:{self.config.port}"
    
    def get_websocket_url(self) -> str:
        """获取WebSocket URL"""
        if self.config.websocket_port:
            scheme = 'wss' if (self.debug_server and getattr(self.debug_server.config, 'enable_ssl', False)) else 'ws'
            return f"{scheme}://{self.config.host}:{self.config.websocket_port}"
        return ""
    
    def restart_web_server(self) -> bool:
        """重启Web服务器"""
        try:
            # 先停止服务器
            self.stop_server()
            
            # 等待一小段时间确保资源释放
            import time
            time.sleep(1)
            
            # 重新启动服务器
            return self.start_server()
            
        except Exception as e:
            error_msg = f"重启Web服务器失败: {str(e)}"
            print(error_msg)
            self.error_occurred.emit(error_msg)
            return False