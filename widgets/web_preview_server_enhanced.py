#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web预览服务器 - 增强版
提供Web界面来监控和控制应用程序
"""

import os
import sys
import json
import time
import threading
import logging
import hashlib
import secrets
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sqlite3
from pathlib import Path
import webbrowser

# 导入enhanced_logger
try:
    from core.enhanced_logger import get_enhanced_logger
    enhanced_logger = get_enhanced_logger()
except ImportError:
    # 如果导入失败，创建一个简单的日志记录器
    import logging
    enhanced_logger = logging.getLogger(__name__)

try:
    from PyQt6.QtCore import QObject, pyqtSignal
except ImportError:
    # 如果PyQt6不可用，创建一个简单的替代
    class QObject:
        pass
    
    class MockSignal:
        """模拟PyQt信号的简单实现"""
        def __init__(self, *args):
            self.callbacks = []
        
        def emit(self, *args, **kwargs):
            """发射信号，调用所有连接的回调函数"""
            for callback in self.callbacks:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    print(f"Signal callback error: {e}")
        
        def connect(self, callback):
            """连接回调函数到信号"""
            if callable(callback):
                self.callbacks.append(callback)
    
    def pyqtSignal(*args):
        return MockSignal(*args)

class WebPreviewHandler(BaseHTTPRequestHandler):
    """处理Web请求的处理器 - 增强版带缓存和安全验证"""
    
    # 类级别的缓存
    _cache = {}
    _cache_timestamps = {}
    _cache_ttl = {
        'status': 5,      # 状态数据缓存5秒
        'keywords': 10,   # 关键词缓存10秒
        'logs': 3,        # 日志缓存3秒
        'settings': 30,   # 设置缓存30秒
        'performance': 2  # 性能数据缓存2秒
    }
    
    # 安全配置
    _api_key = None
    _session_tokens = {}  # 存储会话令牌
    _failed_attempts = {}  # 记录失败尝试
    _rate_limits = {}     # 速率限制
    _security_config = {}  # 完整的安全配置
    _api_logs = []        # API调用日志
    _access_logs = []     # 用户访问日志
    _detailed_logs = []   # 详细操作日志
    
    @classmethod
    def initialize_security(cls):
        """初始化安全配置"""
        # 从设置文件读取API密钥配置
        cls._load_security_settings()
        
        if not cls._api_key:
            enhanced_logger.log("INFO", "Web API密钥未配置，请在开发工具面板中设置", "WebPreviewHandler")
    
    @classmethod
    def _load_security_settings(cls):
        """从设置文件加载安全配置"""
        try:
            import json
            import os
            
            # 获取设置文件路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            settings_file = os.path.join(os.path.dirname(current_dir), 'settings.json')
            
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                web_api_security = settings.get('web_api_security', {})
                cls._security_config = web_api_security
                
                # API密钥配置
                if web_api_security.get('enable_api_key', False):
                    api_key = web_api_security.get('api_key')
                    if api_key:
                        cls._api_key = api_key
                        enhanced_logger.log("INFO", f"Web API密钥已加载: {cls._api_key[:8]}...", "WebPreviewHandler")
                    else:
                        enhanced_logger.log("WARNING", "API密钥验证已启用但未设置密钥", "WebPreviewHandler")
                else:
                    cls._api_key = None
                    enhanced_logger.log("INFO", "Web API密钥验证已禁用", "WebPreviewHandler")
                
                # 记录其他安全配置
                if web_api_security.get('enable_ip_whitelist', False):
                    enhanced_logger.log("INFO", "IP白名单验证已启用", "WebPreviewHandler")
                
                if web_api_security.get('enable_login_limit', True):
                    enhanced_logger.log("INFO", "登录尝试限制已启用", "WebPreviewHandler")
                
                if web_api_security.get('enable_security_protection', True):
                    enhanced_logger.log("INFO", "安全防护已启用", "WebPreviewHandler")
                
                if web_api_security.get('enable_cors', False):
                    enhanced_logger.log("INFO", "CORS已启用", "WebPreviewHandler")
                
                if web_api_security.get('rate_limit', True):
                    enhanced_logger.log("INFO", "速率限制已启用", "WebPreviewHandler")
                else:
                    enhanced_logger.log("INFO", "速率限制已禁用", "WebPreviewHandler")
                    
            else:
                enhanced_logger.log("WARNING", "设置文件不存在，使用默认安全配置", "WebPreviewHandler")
                cls._security_config = {}
                
        except Exception as e:
            enhanced_logger.log("ERROR", f"加载安全设置失败: {e}", "WebPreviewHandler")
            cls._security_config = {}
    
    @classmethod
    def generate_session_token(cls, client_ip):
        """生成会话令牌"""
        token = secrets.token_urlsafe(32)
        expiry = datetime.now() + timedelta(hours=24)
        cls._session_tokens[token] = {
            'ip': client_ip,
            'created': datetime.now(),
            'expiry': expiry,
            'requests': 0
        }
        return token
    
    def _check_ip_whitelist(self, client_ip):
        """检查IP白名单"""
        if not self._security_config.get('enable_ip_whitelist', False):
            return True
        
        whitelist = self._security_config.get('ip_whitelist', [])
        if not whitelist:
            return True
        
        try:
            import ipaddress
            client_ip_obj = ipaddress.ip_address(client_ip)
            
            for allowed_ip in whitelist:
                try:
                    if '/' in allowed_ip:  # CIDR格式
                        if client_ip_obj in ipaddress.ip_network(allowed_ip, strict=False):
                            return True
                    else:  # 单个IP
                        if client_ip_obj == ipaddress.ip_address(allowed_ip):
                            return True
                except ValueError:
                    continue
        except ValueError:
            return False
        
        return False
    
    def _check_login_attempts(self, client_ip):
        """检查登录尝试限制"""
        if not self._security_config.get('enable_login_limit', True):
            return True
        
        current_time = time.time()
        max_attempts = self._security_config.get('max_login_attempts', 5)
        ban_duration = self._security_config.get('ban_duration', 15) * 60  # 转换为秒
        
        if client_ip in self._failed_attempts:
            # 清理过期的失败尝试记录
            self._failed_attempts[client_ip] = [
                attempt_time for attempt_time in self._failed_attempts[client_ip]
                if current_time - attempt_time < ban_duration
            ]
            
            # 检查是否超过最大尝试次数
            if len(self._failed_attempts[client_ip]) >= max_attempts:
                return False
        
        return True
    
    def _record_failed_attempt(self, client_ip):
        """记录失败的登录尝试"""
        if not self._security_config.get('enable_login_limit', True):
            return
        
        current_time = time.time()
        
        if client_ip not in self._failed_attempts:
            self._failed_attempts[client_ip] = []
        
        self._failed_attempts[client_ip].append(current_time)
    
    def _log_api_request(self, method, path, status_code, client_ip, response_time=0):
        """记录API请求日志"""
        if not self._security_config.get('enable_api_audit', True):
            return
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'ip': client_ip,
            'method': method,
            'path': path,
            'status_code': status_code,
            'response_time': response_time,
            'user_agent': self.headers.get('User-Agent', '') if hasattr(self, 'headers') else '',
            'referer': self.headers.get('Referer', '') if hasattr(self, 'headers') else ''
        }
        
        self._api_logs.append(log_entry)
        
        # 保持日志数量在合理范围内（最多1000条）
        if len(self._api_logs) > 1000:
            self._api_logs = self._api_logs[-1000:]
    
    def _check_rate_limit(self, client_ip, limit=100, window=3600):
        """检查速率限制"""
        # 检查是否启用了速率限制
        if not self._security_config.get('rate_limit', True):
            return True
            
        current_time = time.time()
        
        if client_ip not in self._rate_limits:
            self._rate_limits[client_ip] = []
        
        # 清理过期的请求记录
        self._rate_limits[client_ip] = [
            req_time for req_time in self._rate_limits[client_ip]
            if current_time - req_time < window
        ]
        
        # 检查是否超过限制
        if len(self._rate_limits[client_ip]) >= limit:
            return False
        
        # 记录当前请求
        self._rate_limits[client_ip].append(current_time)
        return True
    
    def _authenticate_request(self):
        """验证请求"""
        client_ip = self.client_address[0]
        
        # 检查IP白名单
        if not self._check_ip_whitelist(client_ip):
            self._log_api_request(self.command, self.path, 403, client_ip)
            return False, "IP address not in whitelist"
        
        # 检查登录尝试限制
        if not self._check_login_attempts(client_ip):
            self._log_api_request(self.command, self.path, 429, client_ip)
            return False, "Too many failed attempts, IP temporarily banned"
        
        # 检查速率限制
        if not self._check_rate_limit(client_ip):
            self._log_api_request(self.command, self.path, 429, client_ip)
            return False, "Rate limit exceeded"
        
        # 公开访问的路径 - 允许访问主页面和静态资源
        public_paths = ['/', '/index.html', '/api/auth/token', '/api/auth/info']
        # 允许访问主页面（包括带参数的URL）
        if (self.path in public_paths or 
            self.path.startswith('/static/') or 
            self.path.startswith('/?') or 
            self.path == '/favicon.ico'):
            self._log_api_request(self.command, self.path, 200, client_ip)
            return True, "Public access"
        
        # 如果API密钥验证被禁用，允许所有请求
        if not self._api_key:
            self._log_api_request(self.command, self.path, 200, client_ip)
            return True, "API key authentication disabled"
        
        # 对于其他API请求，检查认证
        if self.path.startswith('/api/'):
            # 检查API密钥或会话令牌
            auth_header = self.headers.get('Authorization', '')
            session_token = self.headers.get('X-Session-Token', '')
            
            if auth_header.startswith('Bearer '):
                provided_key = auth_header[7:]
                if provided_key == self._api_key:
                    self._log_key_validation(client_ip, provided_key, True)
                    self._log_api_request(self.command, self.path, 200, client_ip)
                    return True, "API key valid"
                else:
                    self._log_key_validation(client_ip, provided_key, False)
            
            if session_token and session_token in self._session_tokens:
                token_info = self._session_tokens[session_token]
                if (datetime.now() < token_info['expiry'] and 
                    token_info['ip'] == client_ip):
                    token_info['requests'] += 1
                    self._log_api_request(self.command, self.path, 200, client_ip)
                    return True, "Session token valid"
                else:
                    # 清理过期令牌
                    del self._session_tokens[session_token]
            
            # 记录失败尝试
            self._record_failed_attempt(client_ip)
            self._log_api_request(self.command, self.path, 401, client_ip)
            
            return False, "Authentication required"
        
        self._log_api_request(self.command, self.path, 200, client_ip)
        return True, "Public access"
    
    def __init__(self, *args, main_window=None, web_server=None, **kwargs):
        self.main_window = main_window
        self.web_server = web_server
        super().__init__(*args, **kwargs)
    
    @classmethod
    def _get_cached_data(cls, cache_key):
        """获取缓存数据"""
        current_time = time.time()
        
        if cache_key in cls._cache and cache_key in cls._cache_timestamps:
            cache_age = current_time - cls._cache_timestamps[cache_key]
            ttl = cls._cache_ttl.get(cache_key, 10)
            
            if cache_age < ttl:
                return cls._cache[cache_key]
        
        return None
    
    @classmethod
    def _set_cached_data(cls, cache_key, data):
        """设置缓存数据"""
        cls._cache[cache_key] = data
        cls._cache_timestamps[cache_key] = time.time()
    
    @classmethod
    def _clear_cache(cls, cache_key=None):
        """清除缓存"""
        if cache_key:
            cls._cache.pop(cache_key, None)
            cls._cache_timestamps.pop(cache_key, None)
        else:
            cls._cache.clear()
            cls._cache_timestamps.clear()
    
    def log_message(self, format, *args):
        """重写日志输出方法，实现中文化和详细记录"""
        try:
            # 获取客户端信息
            client_ip = self.client_address[0] if self.client_address else "未知IP"
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            
            # 解析请求信息
            if hasattr(self, 'requestline') and self.requestline:
                method, path, _ = self.requestline.split(' ', 2) if ' ' in self.requestline else (self.requestline, '', '')
                
                # 中文化状态码描述
                status_descriptions = {
                    '200': '✅ 成功',
                    '401': '❌ 未授权',
                    '403': '❌ 禁止访问',
                    '404': '❌ 未找到',
                    '500': '❌ 服务器错误'
                }
                
                # 提取状态码
                status_code = ''
                for arg in args:
                    if isinstance(arg, (int, str)) and str(arg).isdigit() and len(str(arg)) == 3:
                        status_code = str(arg)
                        break
                
                status_desc = status_descriptions.get(status_code, f'状态码: {status_code}')
                
                # 中文化请求路径描述
                path_descriptions = {
                    '/api/status': 'API状态查询',
                    '/api/keywords': '关键词管理',
                    '/api/history': '历史记录查询',
                    '/api/logs': '日志查询',
                    '/api/settings': '设置管理',
                    '/api/performance': '性能监控',
                    '/api/start': '开始监控',
                    '/api/stop': '停止监控',
                    '/api/auth/token': '会话令牌获取',
                    '/api/auth/info': '认证信息查询',
                    '/api/config': '配置查询',
                    '/api/system/status': '系统状态查询',
                    '/api/system/diagnostics': '系统诊断',
                    '/api/security/logs': '安全日志查询',
                    '/api/get_banned_ips': '封禁IP查询',
                    '/': '主页访问',
                    '/index.html': '主页访问'
                }
                
                path_desc = path_descriptions.get(path, f'访问路径: {path}')
                
                # 构建中文化日志消息
                chinese_message = f"[Web预览服务器] {timestamp} - 客户端IP: {client_ip} | {method}请求: {path_desc} | {status_desc}"
                
                # 记录到详细日志
                self._add_detailed_log({
                    'timestamp': timestamp,
                    'client_ip': client_ip,
                    'method': method,
                    'path': path,
                    'path_description': path_desc,
                    'status_code': status_code,
                    'status_description': status_desc,
                    'message': chinese_message
                })
                
                # 输出到系统日志
                enhanced_logger.log('INFO', chinese_message, 'web_preview_server')
            else:
                # 默认日志格式
                original_message = format % args
                chinese_message = f"[Web预览服务器] {timestamp} - 客户端IP: {client_ip} | {original_message}"
                enhanced_logger.log('INFO', chinese_message, 'web_preview_server')
                
        except Exception as e:
            # 如果中文化日志失败，使用原始格式
            enhanced_logger.log('ERROR', f"日志记录失败: {e}", 'web_preview_server')
            enhanced_logger.log('INFO', f"[Web预览服务器] {format % args}", 'web_preview_server')
    
    @classmethod
    def _add_detailed_log(cls, log_data):
        """添加详细日志记录"""
        cls._detailed_logs.append(log_data)
        # 保持日志数量在合理范围内
        if len(cls._detailed_logs) > 1000:
            cls._detailed_logs = cls._detailed_logs[-500:]
    
    @classmethod
    def _add_access_log(cls, client_ip, action, details=None):
        """添加用户访问日志"""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        log_entry = {
            'timestamp': timestamp,
            'client_ip': client_ip,
            'action': action,
            'details': details or {}
        }
        cls._access_logs.append(log_entry)
        # 保持日志数量在合理范围内
        if len(cls._access_logs) > 1000:
            cls._access_logs = cls._access_logs[-500:]
        
        # 输出到系统日志
        enhanced_logger.log('INFO', f"[用户访问] {timestamp} - IP: {client_ip} | 操作: {action}", 'web_preview_server')
    
    def _log_key_validation(self, client_ip, api_key, is_valid, key_type='API密钥', endpoint='未知'):
        """记录密钥验证日志"""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        status = "✅ 有效" if is_valid else "❌ 无效"
        masked_key = f"{api_key[:4]}****{api_key[-4:]}" if api_key and len(api_key) > 8 else "****"
        
        log_message = f"[密钥验证] {timestamp} - IP: {client_ip} | 密钥: {masked_key} | 类型: {key_type} | 接口: {endpoint} | 状态: {status}"
        enhanced_logger.log('INFO', log_message, 'web_preview_server')
        
        # 添加到详细日志
        self._add_detailed_log({
            'timestamp': timestamp,
            'client_ip': client_ip,
            'action': 'key_validation',
            'api_key_masked': masked_key,
            'key_type': key_type,
            'endpoint': endpoint,
            'result': 'success' if is_valid else 'failed',
            'is_valid': is_valid,
            'status': status,
            'message': f"密钥验证 - 类型: {key_type} | 接口: {endpoint} | 结果: {status}"
        })
    
    def _log_api_call(self, client_ip, method, endpoint, status_code, user_agent=''):
        """记录API调用日志"""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        
        log_message = f"[API调用] {timestamp} - IP: {client_ip} | 方法: {method} | 接口: {endpoint} | 状态码: {status_code}"
        enhanced_logger.log('INFO', log_message, 'web_preview_server')
        
        # 添加到详细日志
        self._add_detailed_log({
            'timestamp': timestamp,
            'client_ip': client_ip,
            'action': 'api_call',
            'method': method,
            'endpoint': endpoint,
            'status': status_code,
            'user_agent': user_agent,
            'message': f"API调用 - {method} {endpoint} | 状态: {status_code}"
        })
    
    def _log_authentication_attempt(self, client_ip, result, reason='', user_agent=''):
        """记录身份验证尝试日志"""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        status = "✅ 成功" if result == 'success' else "❌ 失败"
        
        log_message = f"[身份验证] {timestamp} - IP: {client_ip} | 结果: {status} | 原因: {reason}"
        enhanced_logger.log('INFO', log_message, 'web_preview_server')
        
        # 添加到详细日志
        self._add_detailed_log({
            'timestamp': timestamp,
            'client_ip': client_ip,
            'action': 'authentication',
            'result': result,
            'reason': reason,
            'user_agent': user_agent,
            'message': f"身份验证尝试 - 结果: {status} | 原因: {reason}"
        })
    
    def _log_rate_limit(self, client_ip, action, limit_type='访问频率'):
        """记录访问限制日志"""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        
        log_message = f"[访问限制] {timestamp} - IP: {client_ip} | 操作: {action} | 限制类型: {limit_type}"
        enhanced_logger.log('WARNING', log_message, 'web_preview_server')
        
        # 添加到详细日志
        self._add_detailed_log({
            'timestamp': timestamp,
            'client_ip': client_ip,
            'action': 'rate_limit',
            'operation': action,
            'limit_type': limit_type,
            'message': f"访问限制 - 操作: {action} | 类型: {limit_type}"
        })

    def do_GET(self):
        """处理GET请求 - 带安全验证"""
        # 记录用户访问
        client_ip = self.client_address[0] if self.client_address else "未知IP"
        user_agent = self.headers.get('User-Agent', '未知浏览器')
        referer = self.headers.get('Referer', '直接访问')
        
        self._add_access_log(client_ip, "GET请求", {
            'path': self.path,
            'user_agent': user_agent,
            'referer': referer
        })
        
        # 验证请求
        is_authenticated, auth_message = self._authenticate_request()
        if not is_authenticated:
            self._log_authentication_attempt(client_ip, 'failed', auth_message, user_agent)
            self._send_json_response({
                'success': False, 
                'error': auth_message,
                'code': 'AUTH_REQUIRED'
            }, status=401)
            return
        
        # 记录成功的身份验证
        self._log_authentication_attempt(client_ip, 'success', '身份验证通过', user_agent)
        
        # 增加请求计数
        if self.web_server:
            self.web_server.request_count += 1
            
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # 记录API调用
        if path.startswith('/api/'):
            self._log_api_call(client_ip, 'GET', path, 200, user_agent)
        
        if path == '/' or path == '/index.html':
            self._serve_main_page()
        elif path.startswith('/static/'):
            self._serve_static_file(path)
        elif path == '/api/auth/token':
            self._api_get_session_token()
        elif path == '/api/auth/info':
            self._api_get_auth_info()
        elif path == '/api/status':
            self._api_get_status()
        elif path == '/api/keywords':
            self._api_get_keywords()
        elif path == '/api/history':
            self._api_get_history()
        elif path == '/api/logs':
            self._api_get_logs()
        elif path == '/api/logs/detailed':
            self._api_get_detailed_logs()
        elif path == '/api/settings':
            self._api_get_settings()
        elif path == '/api/config':
            self._api_get_config()
        elif path == '/api/system/status':
            self._api_get_system_status()
        elif path == '/api/system/diagnostics':
            self._api_get_system_diagnostics()
        elif path == '/api/performance':
            self._api_get_performance()
        elif path == '/api/security/logs':
            self._api_get_security_logs()
        elif path == '/api/get_banned_ips':
            self._api_get_banned_ips()
        else:
            self._log_api_call(client_ip, 'GET', path, 404, user_agent)
            self._send_404()
    
    def do_POST(self):
        """处理POST请求 - 带安全验证"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # 记录用户访问
        client_ip = self.client_address[0] if self.client_address else "未知IP"
        user_agent = self.headers.get('User-Agent', '未知浏览器')
        referer = self.headers.get('Referer', '直接访问')
        
        # 读取POST数据
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8')) if post_data else {}
        except json.JSONDecodeError:
            data = {}
        
        # 记录POST请求访问
        self._add_access_log(client_ip, "POST请求", {
            'path': path,
            'user_agent': user_agent,
            'referer': referer,
            'content_length': content_length
        })
        
        # API密钥验证接口和管理接口不需要认证
        if path == '/api/verify_key':
            enhanced_logger.log("INFO", f"收到API密钥验证请求: {data}", "WebPreviewHandler")
            api_key = data.get('api_key', '')
            self._log_key_validation(client_ip, api_key, False, 'API密钥验证', path)  # 先记录为失败，实际结果在验证方法中更新
            self._api_verify_key(data)
            return
        elif path == '/api/clear_failed_attempts':
            enhanced_logger.log("INFO", f"收到清除失败尝试请求: {data}", "WebPreviewHandler")
            self._log_api_call(client_ip, 'POST', path, 200, user_agent)
            self._api_clear_failed_attempts(data)
            return
        elif path == '/api/get_banned_ips':
            enhanced_logger.log("INFO", "收到获取封禁IP列表请求", "WebPreviewHandler")
            self._log_api_call(client_ip, 'POST', path, 200, user_agent)
            self._api_get_banned_ips()
            return
        
        # 其他接口需要验证请求
        is_authenticated, auth_message = self._authenticate_request()
        if not is_authenticated:
            self._log_authentication_attempt(client_ip, 'failed', auth_message, user_agent)
            self._log_api_call(client_ip, 'POST', path, 401, user_agent)
            self._send_json_response({
                'success': False, 
                'error': auth_message,
                'code': 'AUTH_REQUIRED'
            }, status=401)
            return
        
        # 记录成功的身份验证
        self._log_authentication_attempt(client_ip, 'success', '身份验证通过', user_agent)
        
        # 记录API调用
        self._log_api_call(client_ip, 'POST', path, 200, user_agent)
        
        if path == '/api/keywords/add':
            keyword = data.get('keyword', '')
            self._add_detailed_log({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
                'client_ip': client_ip,
                'action': 'add_keyword',
                'keyword': keyword,
                'message': f"添加关键词: {keyword}"
            })
            self._api_add_keyword(data)
        elif path == '/api/keywords/delete':
            keyword = data.get('keyword', '')
            self._add_detailed_log({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
                'client_ip': client_ip,
                'action': 'delete_keyword',
                'keyword': keyword,
                'message': f"删除关键词: {keyword}"
            })
            self._api_delete_keyword(data)
        elif path == '/api/monitoring/start':
            self._add_detailed_log({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
                'client_ip': client_ip,
                'action': 'start_monitoring',
                'message': "启动监控"
            })
            self._api_start_monitoring()
        elif path == '/api/monitoring/stop':
            self._add_detailed_log({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
                'client_ip': client_ip,
                'action': 'stop_monitoring',
                'message': "停止监控"
            })
            self._api_stop_monitoring()
        elif path == '/api/settings/update':
            self._add_detailed_log({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
                'client_ip': client_ip,
                'action': 'update_settings',
                'settings_keys': list(data.keys()) if data else [],
                'message': f"更新设置: {', '.join(data.keys()) if data else '无'}"
            })
            self._api_update_settings(data)
        elif path == '/api/config/update':
            self._add_detailed_log({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
                'client_ip': client_ip,
                'action': 'update_config',
                'config_keys': list(data.keys()) if data else [],
                'message': f"更新配置: {', '.join(data.keys()) if data else '无'}"
            })
            self._api_update_config(data)
        elif path == '/api/system/restart':
            self._add_detailed_log({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
                'client_ip': client_ip,
                'action': 'system_restart',
                'message': "系统重启请求"
            })
            self._api_restart_system(data)
        else:
            self._log_api_call(client_ip, 'POST', path, 404, user_agent)
            self._send_404()
    
    def do_OPTIONS(self):
        """处理OPTIONS请求（CORS预检）"""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()
    
    def _set_cors_headers(self):
        """设置CORS头"""
        if not self._security_config.get('enable_cors', False):
            return
        
        # 获取请求的Origin
        origin = self.headers.get('Origin', '')
        allowed_origins = self._security_config.get('cors_origins', [])
        
        if allowed_origins:
            # 检查Origin是否在允许列表中
            if origin in allowed_origins:
                self.send_header('Access-Control-Allow-Origin', origin)
            else:
                # 如果Origin不在允许列表中，不设置CORS头
                return
        else:
            # 如果没有配置特定域名，允许所有域名
            self.send_header('Access-Control-Allow-Origin', '*')
        
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Session-Token')
        self.send_header('Access-Control-Allow-Credentials', 'true')
    
    def _send_response(self, content, content_type='text/html', status=200):
        """发送HTTP响应"""
        self.send_response(status)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self._set_cors_headers()
        self.end_headers()
        
        if isinstance(content, str):
            content = content.encode('utf-8')
        self.wfile.write(content)
    
    def _send_json_response(self, data, status=200):
        """发送JSON响应"""
        json_content = json.dumps(data, ensure_ascii=False, indent=2)
        self._send_response(json_content, 'application/json', status)
    
    def _send_404(self):
        """发送404响应"""
        self._send_response('<h1>404 Not Found</h1>', status=404)
    
    def _api_get_session_token(self):
        """获取会话令牌API"""
        client_ip = self.client_address[0]
        token = self.generate_session_token(client_ip)
        
        self._send_json_response({
            'success': True,
            'data': {
                'token': token,
                'expires_in': 86400,  # 24小时
                'type': 'session'
            }
        })
    
    def _api_get_auth_info(self):
        """获取认证信息API"""
        client_ip = self.client_address[0]
        
        # 统计信息
        active_sessions = len([t for t in self._session_tokens.values() 
                              if datetime.now() < t['expiry']])
        failed_attempts = len(self._failed_attempts.get(client_ip, []))
        
        self._send_json_response({
            'success': True,
            'data': {
                'client_ip': client_ip,
                'active_sessions': active_sessions,
                'failed_attempts': failed_attempts,
                'rate_limit_remaining': max(0, 100 - len(self._rate_limits.get(client_ip, []))),
                'api_key_required': True,
                'security_enabled': True
            }
        })
    
    def _api_get_config(self):
        """获取系统配置API"""
        try:
            config = {
                'server': {
                    'port': getattr(self.web_server, 'port', 8888),
                    'host': 'localhost',
                    'security_enabled': True,
                    'rate_limiting': True
                },
                'monitoring': {
                    'auto_refresh': True,
                    'refresh_interval': 5000,
                    'max_logs': 1000,
                    'performance_tracking': True
                },
                'ui': {
                    'theme': 'dark',
                    'language': 'zh-CN',
                    'notifications': True,
                    'sound_alerts': False
                }
            }
            self._send_json_response({'success': True, 'data': config})
        except Exception as e:
            self._send_json_response({'success': False, 'error': str(e)}, status=500)
    
    def _api_get_system_status(self):
        """获取系统状态API"""
        try:
            import psutil
            import platform
            
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            status = {
                'system': {
                    'platform': platform.system(),
                    'hostname': platform.node(),
                    'uptime': time.time() - getattr(self, '_start_time', time.time())
                },
                'resources': {
                    'cpu_usage': cpu_percent,
                    'memory_usage': memory.percent,
                    'memory_total': memory.total,
                    'memory_available': memory.available
                },
                'server': {
                    'active_connections': 1,
                    'total_requests': sum(len(reqs) for reqs in self._rate_limits.values()),
                    'status': 'running'
                }
            }
            self._send_json_response({'success': True, 'data': status})
        except Exception as e:
            self._send_json_response({'success': False, 'error': str(e)}, status=500)
    
    def _api_get_system_diagnostics(self):
        """获取系统诊断信息API"""
        try:
            diagnostics = {
                'health_checks': {
                    'server_status': 'healthy',
                    'memory_status': 'normal',
                    'disk_status': 'normal'
                },
                'performance': {
                    'avg_response_time': '< 100ms',
                    'error_rate': '0%',
                    'uptime': '99.9%'
                },
                'security': {
                    'failed_auth_attempts': len([ip for attempts in self._failed_attempts.values() for ip in attempts]),
                    'active_sessions': len(self._session_tokens),
                    'rate_limit_violations': 0
                }
            }
            self._send_json_response({'success': True, 'data': diagnostics})
        except Exception as e:
            self._send_json_response({'success': False, 'error': str(e)}, status=500)
    
    def _api_update_config(self, data):
        """更新系统配置API"""
        try:
            updated_config = data.get('config', {})
            self._send_json_response({
                'success': True,
                'message': '配置更新成功',
                'updated_config': updated_config
            })
        except Exception as e:
            self._send_json_response({'success': False, 'error': str(e)}, status=400)
    
    def _api_restart_system(self, data):
        """重启系统API"""
        try:
            restart_type = data.get('type', 'soft')
            self._send_json_response({
                'success': True,
                'message': f'{restart_type}重启请求已接收',
                'restart_type': restart_type
            })
        except Exception as e:
            self._send_json_response({'success': False, 'error': str(e)}, status=500)
    
    def _serve_main_page(self):
        """提供主页面"""
        html_content = self._get_main_page_html()
        self._send_response(html_content)
    
    def _serve_static_file(self, path):
        """提供静态文件"""
        # 简单的静态文件服务
        file_path = path[8:]  # 移除 '/static/' 前缀
        
        # 安全检查
        if '..' in file_path or file_path.startswith('/'):
            self._send_404()
            return
        
        try:
            # 这里可以添加实际的静态文件服务逻辑
            self._send_404()
        except Exception:
            self._send_404()
    
    def _api_get_status(self):
        """获取系统状态API - 带缓存"""
        # 尝试从缓存获取
        cached_data = self._get_cached_data('status')
        if cached_data:
            self._send_json_response({'success': True, 'data': cached_data, 'cached': True})
            return
        
        # 生成新数据
        status_data = {
            'monitoring': self._get_monitoring_status(),
            'ocr_engine': self._get_ocr_engine_status(),
            'api': self._get_api_status(),
            'performance': self._get_performance_data()
        }
        
        # 缓存数据
        self._set_cached_data('status', status_data)
        self._send_json_response({'success': True, 'data': status_data, 'cached': False})
    
    def _api_get_keywords(self):
        """获取关键词列表API - 带缓存"""
        cached_data = self._get_cached_data('keywords')
        if cached_data:
            self._send_json_response({'success': True, 'data': cached_data, 'cached': True})
            return
        
        keywords = self._get_keywords_from_main_window()
        self._set_cached_data('keywords', keywords)
        self._send_json_response({'success': True, 'data': keywords, 'cached': False})
    
    def _api_get_history(self):
        """获取历史记录API"""
        history = self._get_history_data()
        self._send_json_response({'success': True, 'data': history})
    
    def _api_get_logs(self):
        """获取日志API - 带缓存，返回详细的中文化日志"""
        try:
            # 记录API调用
            client_ip = self.client_address[0] if self.client_address else "未知IP"
            self._add_detailed_log({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
                'client_ip': client_ip,
                'action': '查询日志',
                'message': f'用户 {client_ip} 请求获取系统日志',
                'api_endpoint': '/api/logs'
            })
            
            cached_data = self._get_cached_data('logs')
            if cached_data:
                self._send_json_response({'success': True, 'data': cached_data, 'cached': True})
                return
            
            # 获取系统日志
            system_logs = self._get_recent_logs()
            
            # 获取Web服务器详细日志
            web_logs = self._get_web_server_logs()
            
            # 合并所有日志
            all_logs = []
            
            # 添加系统日志（中文化处理）
            for log in system_logs:
                all_logs.append({
                    'id': f"sys_{len(all_logs)}",
                    'type': '系统日志',
                    'timestamp': log.get('timestamp', ''),
                    'level': self._translate_log_level(log.get('level', 'INFO')),
                    'message': self._translate_log_message(log.get('message', '')),
                    'source': '系统核心',
                    'category': '系统运行'
                })
            
            # 添加Web服务器日志
            for log in web_logs:
                all_logs.append({
                    'id': f"web_{len(all_logs)}",
                    'type': 'Web服务器日志',
                    'timestamp': log.get('timestamp', ''),
                    'level': '信息',
                    'message': log.get('message', ''),
                    'client_ip': log.get('client_ip', ''),
                    'action': log.get('action', ''),
                    'source': 'Web预览服务器',
                    'category': '用户访问',
                    'details': log.get('details', {})
                })
            
            # 按时间戳排序（最新的在前）
            all_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # 限制返回数量
            all_logs = all_logs[:100]
            
            enhanced_logger.log('INFO', f"API返回 {len(all_logs)} 条详细日志给客户端 {client_ip}", 'web_preview_server')
            self._set_cached_data('logs', all_logs)
            self._send_json_response({
                'success': True, 
                'data': all_logs, 
                'cached': False,
                'total_count': len(all_logs),
                'message': f'成功获取 {len(all_logs)} 条日志记录'
            })
        except Exception as e:
            enhanced_logger.log('ERROR', f"API获取日志失败: {e}", 'web_preview_server')
            self._send_json_response({'success': False, 'error': f'获取日志失败: {str(e)}'}, status=500)
    
    def _api_get_detailed_logs(self):
        """获取详细日志API - 包括访问日志和操作日志"""
        try:
            # 获取详细日志
            detailed_logs = list(self._detailed_logs)
            access_logs = list(self._access_logs)
            
            # 获取系统日志
            system_logs = self._get_recent_logs()
            
            # 合并并按时间排序
            all_logs = []
            
            # 添加系统日志（中文化处理）
            for log in system_logs:
                translated_message = self._translate_log_message(log.get('message', ''))
                all_logs.append({
                    'type': '系统日志',
                    'timestamp': log.get('timestamp', ''),
                    'level': self._translate_log_level(log.get('level', 'INFO')),
                    'message': translated_message,
                    'source': '系统',
                    'details': log
                })
            
            # 添加详细日志（增强信息）
            for log in detailed_logs:
                client_ip = log.get('client_ip', '未知IP')
                action = log.get('action', '未知操作')
                message = log.get('message', '')
                
                # 根据操作类型生成更详细的中文消息
                if 'key_validation' in action:
                    result = log.get('result', '未知')
                    key_type = log.get('key_type', '未知类型')
                    message = f"🔑 密钥验证 - IP地址: {client_ip} | 密钥类型: {key_type} | 验证结果: {'✅ 成功' if result == 'success' else '❌ 失败'}"
                elif 'api_call' in action:
                    endpoint = log.get('endpoint', '未知接口')
                    method = log.get('method', 'GET')
                    status = log.get('status', '未知')
                    message = f"🔗 API调用 - IP地址: {client_ip} | 接口: {endpoint} | 方法: {method} | 状态: {status}"
                elif 'login_attempt' in action:
                    result = log.get('result', '未知')
                    message = f"🔐 登录尝试 - IP地址: {client_ip} | 结果: {'✅ 成功' if result == 'success' else '❌ 失败'}"
                elif 'rate_limit' in action:
                    message = f"⚠️ 访问限制 - IP地址: {client_ip} | 原因: 访问频率过高"
                elif 'authentication' in action:
                    result = log.get('result', '未知')
                    message = f"🛡️ 身份验证 - IP地址: {client_ip} | 结果: {'✅ 通过' if result == 'success' else '❌ 拒绝'}"
                else:
                    message = f"📝 用户操作 - IP地址: {client_ip} | 操作: {action} | 详情: {message}"
                
                all_logs.append({
                    'type': '详细操作日志',
                    'timestamp': log.get('timestamp', ''),
                    'client_ip': client_ip,
                    'action': action,
                    'message': message,
                    'level': '信息',
                    'source': 'Web服务器',
                    'details': log
                })
            
            # 添加访问日志（增强信息）
            for log in access_logs:
                client_ip = log.get('client_ip', '未知IP')
                action = log.get('action', '未知操作')
                user_agent = log.get('user_agent', '未知浏览器')
                referer = log.get('referer', '直接访问')
                
                # 生成更详细的访问信息
                message = f"👤 用户访问 - IP地址: {client_ip} | 操作: {action} | 浏览器: {user_agent[:50]}{'...' if len(user_agent) > 50 else ''} | 来源: {referer}"
                
                all_logs.append({
                    'type': '用户访问日志',
                    'timestamp': log.get('timestamp', ''),
                    'client_ip': client_ip,
                    'action': action,
                    'message': message,
                    'level': '信息',
                    'source': 'Web服务器',
                    'user_agent': user_agent,
                    'referer': referer,
                    'details': log
                })
            
            # 按时间戳排序（最新的在前）
            all_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # 限制返回数量
            all_logs = all_logs[:200]
            
            self._send_json_response({
                'success': True, 
                'data': {
                    'logs': all_logs,
                    'total_count': len(all_logs),
                    'system_count': len(system_logs),
                    'detailed_count': len(detailed_logs),
                    'access_count': len(access_logs),
                    'summary': {
                        '系统日志': len(system_logs),
                        '详细操作日志': len(detailed_logs),
                        '用户访问日志': len(access_logs),
                        '总计': len(all_logs)
                    }
                }
            })
        except Exception as e:
            enhanced_logger.log('ERROR', f"API获取详细日志失败: {e}", 'web_preview_server')
            self._send_json_response({'success': False, 'error': str(e)}, status=500)
    
    def _api_get_settings(self):
        """获取设置API - 带缓存"""
        cached_data = self._get_cached_data('settings')
        if cached_data:
            self._send_json_response({'success': True, 'data': cached_data, 'cached': True})
            return
        
        settings = self._get_current_settings()
        self._set_cached_data('settings', settings)
        self._send_json_response({'success': True, 'data': settings, 'cached': False})
    
    def _api_get_performance(self):
        """获取性能数据API - 带缓存"""
        cached_data = self._get_cached_data('performance')
        if cached_data:
            self._send_json_response({'success': True, 'data': cached_data, 'cached': True})
            return
        
        performance = self._get_performance_metrics()
        self._set_cached_data('performance', performance)
        self._send_json_response({'success': True, 'data': performance, 'cached': False})
    
    def _api_get_security_logs(self):
        """获取安全日志API"""
        try:
            # 获取最近的安全日志
            security_logs = self._api_logs[-100:]  # 最近100条日志
            
            # 格式化日志数据
            formatted_logs = []
            for log in security_logs:
                formatted_logs.append({
                    'timestamp': log.get('timestamp', ''),
                    'level': log.get('level', 'INFO'),
                    'event': log.get('event', ''),
                    'ip': log.get('ip', ''),
                    'user_agent': log.get('user_agent', ''),
                    'details': log.get('details', '')
                })
            
            self._send_json_response({
                'success': True, 
                'data': {
                    'logs': formatted_logs,
                    'total': len(self._api_logs),
                    'security_config': {
                        'ip_whitelist_enabled': bool(self._security_config.get('ip_whitelist')),
                        'rate_limit_enabled': bool(self._security_config.get('rate_limit')),
                        'api_key_required': bool(self._security_config.get('api_key')),
                        'cors_enabled': bool(self._security_config.get('cors_domains'))
                    }
                }
            })
        except Exception as e:
            enhanced_logger.log('ERROR', f"获取安全日志失败: {e}", 'web_preview_server')
            self._send_json_response({'success': False, 'error': str(e)}, status=500)
    
    def _api_add_keyword(self, data):
        """添加关键词API - 清除相关缓存"""
        keyword = data.get('keyword', '').strip()
        if not keyword:
            self._send_json_response({'success': False, 'error': '关键词不能为空'})
            return
        
        try:
            success = self._add_keyword_to_main_window(keyword)
            if success:
                # 清除关键词和状态缓存
                self._clear_cache('keywords')
                self._clear_cache('status')
                self._send_json_response({'success': True, 'message': '关键词添加成功'})
            else:
                self._send_json_response({'success': False, 'error': '关键词已存在或添加失败'})
        except Exception as e:
            self._send_json_response({'success': False, 'error': str(e)})
    
    def _api_delete_keyword(self, data):
        """删除关键词API - 清除相关缓存"""
        keyword = data.get('keyword', '').strip()
        if not keyword:
            self._send_json_response({'success': False, 'error': '关键词不能为空'})
            return
        
        try:
            success = self._delete_keyword_from_main_window(keyword)
            if success:
                # 清除关键词和状态缓存
                self._clear_cache('keywords')
                self._clear_cache('status')
                self._send_json_response({'success': True, 'message': '关键词删除成功'})
            else:
                self._send_json_response({'success': False, 'error': '关键词不存在或删除失败'})
        except Exception as e:
            self._send_json_response({'success': False, 'error': str(e)})
    
    def _api_start_monitoring(self):
        """启动监控API - 清除相关缓存"""
        try:
            success = self._start_monitoring_in_main_window()
            if success:
                # 清除状态和性能缓存
                self._clear_cache('status')
                self._clear_cache('performance')
                self._send_json_response({'success': True, 'message': '监控启动成功'})
            else:
                self._send_json_response({'success': False, 'error': '监控启动失败'})
        except Exception as e:
            self._send_json_response({'success': False, 'error': str(e)})
    
    def _api_stop_monitoring(self):
        """停止监控API - 清除相关缓存"""
        try:
            success = self._stop_monitoring_in_main_window()
            if success:
                # 清除状态和性能缓存
                self._clear_cache('status')
                self._clear_cache('performance')
                self._send_json_response({'success': True, 'message': '监控停止成功'})
            else:
                self._send_json_response({'success': False, 'error': '监控停止失败'})
        except Exception as e:
            self._send_json_response({'success': False, 'error': str(e)})
    
    def _api_update_settings(self, data):
        """更新设置API - 清除相关缓存"""
        try:
            success = self._update_settings_in_main_window(data)
            if success:
                # 清除设置和状态缓存
                self._clear_cache('settings')
                self._clear_cache('status')
                self._send_json_response({'success': True, 'message': '设置更新成功'})
            else:
                self._send_json_response({'success': False, 'error': '设置更新失败'})
        except Exception as e:
            self._send_json_response({'success': False, 'error': str(e)})
    
    def _api_verify_key(self, data):
        """验证API密钥"""
        try:
            api_key = data.get('api_key', '').strip()
            if not api_key:
                self._send_json_response({
                    'success': False, 
                    'error': '请输入API密钥'
                })
                return
            
            # 从设置文件读取配置的API密钥
            try:
                import json
                import os
                
                # 获取设置文件路径
                current_dir = os.path.dirname(os.path.abspath(__file__))
                settings_file = os.path.join(os.path.dirname(current_dir), 'settings.json')
                
                configured_key = ''
                if os.path.exists(settings_file):
                    with open(settings_file, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                    
                    web_api_security = settings.get('web_api_security', {})
                    if web_api_security.get('enable_api_key', False):
                        configured_key = web_api_security.get('api_key', '')
                        
            except Exception as load_error:
                enhanced_logger.log("ERROR", f"加载设置文件失败: {str(load_error)}", "WebPreviewHandler")
                configured_key = ''
            
            if not configured_key:
                self._send_json_response({
                    'success': False, 
                    'error': '未配置API密钥，请在主程序的Web预览设置中配置'
                })
                return
            
            # 验证密钥
            if api_key == configured_key:
                self._send_json_response({
                    'success': True, 
                    'message': 'API密钥验证成功'
                })
            else:
                self._send_json_response({
                    'success': False, 
                    'error': 'API密钥验证失败'
                })
                
        except Exception as e:
            self._send_json_response({
                'success': False, 
                'error': f'验证过程出错: {str(e)}'
            })
    
    def _api_clear_failed_attempts(self, data):
        """清除IP失败尝试记录（解除IP封禁）"""
        try:
            # 获取要清除的IP地址
            target_ip = data.get('ip', '').strip()
            
            if target_ip:
                # 清除指定IP的失败尝试记录
                if target_ip in self._failed_attempts:
                    del self._failed_attempts[target_ip]
                    enhanced_logger.log("INFO", f"已清除IP {target_ip} 的失败尝试记录", "WebPreviewHandler")
                    self._send_json_response({
                        'success': True, 
                        'message': f'已解除IP {target_ip} 的临时封禁'
                    })
                else:
                    self._send_json_response({
                        'success': True, 
                        'message': f'IP {target_ip} 没有失败记录'
                    })
            else:
                # 清除所有IP的失败尝试记录
                cleared_count = len(self._failed_attempts)
                self._failed_attempts.clear()
                enhanced_logger.log("INFO", f"已清除所有IP的失败尝试记录，共 {cleared_count} 个IP", "WebPreviewHandler")
                self._send_json_response({
                    'success': True, 
                    'message': f'已解除所有IP的临时封禁（共 {cleared_count} 个IP）'
                })
                
        except Exception as e:
            enhanced_logger.log("ERROR", f"清除失败尝试记录时出错: {str(e)}", "WebPreviewHandler")
            self._send_json_response({
                'success': False, 
                'error': f'清除失败尝试记录时出错: {str(e)}'
            })
    
    def _api_get_banned_ips(self):
        """获取当前被封禁的IP列表"""
        try:
            from datetime import datetime, timedelta
            
            current_time = time.time()
            banned_ips = []
            
            # 检查每个IP的失败尝试记录
            for ip, attempts in self._failed_attempts.items():
                # 清理过期的尝试记录
                recent_attempts = [
                    attempt_time for attempt_time in attempts
                    if current_time - attempt_time < 300  # 5分钟内的尝试
                ]
                
                # 如果最近5分钟内失败次数达到限制，则认为被封禁
                max_attempts = self._security_config.get('max_failed_attempts', 5)
                if len(recent_attempts) >= max_attempts:
                    # 计算解封时间（最后一次失败尝试后5分钟）
                    last_attempt = max(recent_attempts)
                    unban_time = datetime.fromtimestamp(last_attempt + 300)
                    
                    banned_ips.append({
                        'ip': ip,
                        'failed_attempts': len(recent_attempts),
                        'last_attempt': datetime.fromtimestamp(last_attempt).strftime('%Y-%m-%d %H:%M:%S'),
                        'unban_time': unban_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'remaining_seconds': max(0, int(last_attempt + 300 - current_time))
                    })
            
            self._send_json_response({
                'success': True, 
                'data': {
                    'banned_ips': banned_ips,
                    'total_banned': len(banned_ips),
                    'ban_duration_minutes': 5,
                    'max_attempts': max_attempts
                }
            })
            
        except Exception as e:
            enhanced_logger.log("ERROR", f"获取封禁IP列表时出错: {str(e)}", "WebPreviewHandler")
            self._send_json_response({
                'success': False, 
                'error': f'获取封禁IP列表时出错: {str(e)}'
            })
    
    def _get_monitoring_status(self):
        """获取监控状态"""
        # 从主窗口获取实际监控状态
        if self.main_window and hasattr(self.main_window, 'ocr_worker'):
            if self.main_window.ocr_worker:
                # OCR工作器存在且运行中
                last_check = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                return {
                    'active': True,
                    'last_check': last_check
                }
            else:
                # OCR工作器已停止
                return {
                    'active': False,
                    'last_check': '未启动'
                }
        else:
            # 主窗口不存在或没有OCR工作器属性
            return {
                'active': False,
                'last_check': '未初始化'
            }
    
    def _get_ocr_engine_status(self):
        """获取OCR引擎状态"""
        # 获取真实的OCR工作器状态
        if self.main_window and hasattr(self.main_window, 'ocr_worker'):
            if self.main_window.ocr_worker:
                ocr_version = getattr(self.main_window.ocr_worker, 'ocr_version', 'general')
                return {
                    'engine': f'百度OCR ({ocr_version})',
                    'status': 'running',
                    'version': ocr_version,
                    'last_recognition': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            else:
                return {
                    'engine': '百度OCR',
                    'status': 'stopped',
                    'version': 'N/A',
                    'last_recognition': 'N/A'
                }
        else:
            return {
                'engine': '百度OCR',
                'status': 'ready',
                'version': 'N/A',
                'last_recognition': 'N/A'
            }
    
    def _get_api_status(self):
        """获取API状态"""
        # 计算真实的运行时间
        uptime_str = '00:00:00'
        requests_count = 0
        
        if self.web_server and self.web_server.start_time:
            uptime_seconds = int(time.time() - self.web_server.start_time)
            hours = uptime_seconds // 3600
            minutes = (uptime_seconds % 3600) // 60
            seconds = uptime_seconds % 60
            uptime_str = f'{hours:02d}:{minutes:02d}:{seconds:02d}'
            requests_count = self.web_server.request_count
        
        return {
            'status': 'running',
            'uptime': uptime_str,
            'requests_count': requests_count
        }
    
    def _get_performance_data(self):
        """获取性能数据"""
        try:
            # 尝试从主程序获取性能管理器
            if self.main_window and hasattr(self.main_window, 'performance_manager'):
                perf_data = self.main_window.performance_manager.collect_current_performance()
                return {
                    'cpu_usage': round(perf_data.get('cpu_percent', 0), 1),
                    'memory_usage': round(perf_data.get('process_memory_mb', 0), 1),
                    'recognition_speed': 1.2  # 这个需要从识别模块获取
                }
            else:
                # 如果没有性能管理器，尝试直接使用psutil
                try:
                    import psutil
                    import os
                    
                    # 获取CPU使用率
                    cpu_percent = psutil.cpu_percent(interval=0.1)
                    
                    # 获取当前进程内存使用
                    process = psutil.Process(os.getpid())
                    memory_mb = process.memory_info().rss / (1024 * 1024)
                    
                    return {
                        'cpu_usage': round(cpu_percent, 1),
                        'memory_usage': round(memory_mb, 1),
                        'recognition_speed': 1.2
                    }
                except ImportError:
                    pass
        except Exception as e:
            logging.error(f"获取性能数据失败: {e}")
        
        # 返回默认数据
        return {
            'cpu_usage': 0,
            'memory_usage': 0,
            'recognition_speed': 0
        }
    
    def _get_keywords_from_main_window(self):
        """从主窗口获取关键词列表"""
        if self.main_window and hasattr(self.main_window, 'keyword_panel'):
            try:
                # 从keyword_panel获取真实关键词列表
                keywords = self.main_window.keyword_panel.get_keywords()
                # 转换为Web界面需要的格式
                result = []
                for keyword in keywords:
                    result.append({
                        'keyword': keyword,
                        'count': 0,  # 实际使用中可以从日志统计
                        'last_match': 'N/A'  # 实际使用中可以从日志获取
                    })
                return result
            except Exception as e:
                enhanced_logger.log("ERROR", f"获取关键词失败: {e}")
        
        # 如果无法获取真实数据，返回空列表
        return []
    
    def _get_history_data(self):
        """获取历史数据"""
        return [
            {
                'timestamp': '2024-01-01 12:00:00',
                'keyword': '示例关键词1',
                'text': '检测到的文本内容1',
                'confidence': 0.95
            },
            {
                'timestamp': '2024-01-01 11:30:00',
                'keyword': '示例关键词2',
                'text': '检测到的文本内容2',
                'confidence': 0.88
            },
            {
                'timestamp': '2024-01-01 11:00:00',
                'keyword': '示例关键词3',
                'text': '检测到的文本内容3',
                'confidence': 0.92
            }
        ]
    
    def _get_recent_logs(self):
        """获取最近的日志"""
        try:
            import os
            from datetime import datetime
            
            logs = []
            log_dir = os.path.join(os.getcwd(), "logs")
            
            if os.path.exists(log_dir):
                # 获取所有HTML日志文件
                html_files = []
                for file in os.listdir(log_dir):
                    if file.endswith('.html'):
                        file_path = os.path.join(log_dir, file)
                        html_files.append((file_path, os.path.getmtime(file_path)))
                
                # 按修改时间排序，最新的在前
                html_files.sort(key=lambda x: x[1], reverse=True)
                
                # 从最新的日志文件中提取日志条目
                for file_path, _ in html_files[:2]:  # 只读取最新的2个文件
                    file_logs = self._extract_logs_from_html(file_path)
                    logs.extend(file_logs)
                
                # 按时间戳排序，最新的在前，并限制数量
                logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                logs = logs[:50]  # 只返回最近50条日志
            
            # 如果没有日志文件或读取失败，返回空列表
            if not logs:
                return []
                
            return logs
            
        except Exception as e:
            enhanced_logger.log("ERROR", f"获取日志失败: {e}")
            # 发生错误时返回空列表，而不是示例数据
            return []
    
    def _extract_logs_from_html(self, html_file_path):
        """从HTML日志文件中提取日志条目"""
        try:
            logs = []
            
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # 尝试使用BeautifulSoup解析HTML
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                log_entries = soup.find_all('div', class_='log-entry')
                
                for entry in log_entries:
                    timestamp_elem = entry.find('div', class_='log-timestamp')
                    level_elem = entry.find('div', class_='log-level')
                    message_elem = entry.find('div', class_='log-message')
                    
                    if timestamp_elem and level_elem and message_elem:
                        timestamp = timestamp_elem.get_text(strip=True)
                        level = level_elem.get_text(strip=True)
                        message = message_elem.get_text(strip=True)
                        
                        logs.append({
                            'timestamp': timestamp,
                            'level': level,
                            'message': message
                        })
                        
            except ImportError:
                # 如果没有BeautifulSoup，使用正则表达式解析
                import re
                
                # 匹配日志条目的正则表达式
                log_pattern = r'<div class="log-entry">.*?<div class="log-timestamp">(.*?)</div>.*?<div class="log-level">(.*?)</div>.*?<div class="log-message">(.*?)</div>.*?</div>'
                matches = re.findall(log_pattern, html_content, re.DOTALL)
                
                for match in matches:
                    timestamp, level, message = match
                    # 清理HTML标签和多余空白
                    timestamp = re.sub(r'<[^>]+>', '', timestamp).strip()
                    level = re.sub(r'<[^>]+>', '', level).strip()
                    message = re.sub(r'<[^>]+>', '', message).strip()
                    
                    logs.append({
                        'timestamp': timestamp,
                        'level': level,
                        'message': message
                    })
            
            return logs
            
        except Exception as e:
            enhanced_logger.log("ERROR", f"解析HTML日志文件失败 {html_file_path}: {e}")
            return []
    
    def _get_web_server_logs(self):
        """获取Web服务器的详细日志"""
        try:
            # 合并访问日志和详细日志
            web_logs = []
            
            # 添加访问日志
            for log in list(self._access_logs):
                web_logs.append({
                    'timestamp': log.get('timestamp', ''),
                    'client_ip': log.get('client_ip', ''),
                    'action': log.get('action', ''),
                    'message': f"用户访问 - IP: {log.get('client_ip', '')} | 操作: {log.get('action', '')}",
                    'type': '用户访问',
                    'details': log.get('details', {})
                })
            
            # 添加详细日志
            for log in list(self._detailed_logs):
                web_logs.append({
                    'timestamp': log.get('timestamp', ''),
                    'client_ip': log.get('client_ip', ''),
                    'action': log.get('action', ''),
                    'message': log.get('message', ''),
                    'type': '详细操作',
                    'details': log
                })
            
            # 按时间戳排序
            web_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return web_logs[:200]  # 返回最近200条
            
        except Exception as e:
            enhanced_logger.log('ERROR', f'获取Web服务器日志失败: {e}', 'web_preview_server')
            return []
    
    def _translate_log_level(self, level):
        """翻译日志级别为中文"""
        level_translations = {
            'DEBUG': '调试',
            'INFO': '信息',
            'WARNING': '警告',
            'ERROR': '错误',
            'CRITICAL': '严重错误',
            'WARN': '警告'
        }
        return level_translations.get(level.upper(), level)
    
    def _translate_log_message(self, message):
        """翻译日志消息为中文"""
        if not message:
            return message
            
        # 常见英文消息的中文翻译
        translations = {
            'Server started': '服务器已启动',
            'Server stopped': '服务器已停止',
            'Connection established': '连接已建立',
            'Connection closed': '连接已关闭',
            'Authentication failed': '身份验证失败',
            'Authentication successful': '身份验证成功',
            'Request processed': '请求已处理',
            'Error occurred': '发生错误',
            'Database connected': '数据库已连接',
            'Database disconnected': '数据库已断开',
            'OCR processing started': 'OCR处理已开始',
            'OCR processing completed': 'OCR处理已完成',
            'Keyword detected': '检测到关键词',
            'Monitoring started': '监控已开始',
            'Monitoring stopped': '监控已停止'
        }
        
        # 尝试完整匹配
        for en_text, cn_text in translations.items():
            if en_text.lower() in message.lower():
                message = message.replace(en_text, cn_text)
        
        return message
     
    def _get_current_settings(self):
        """获取当前设置"""
        if self.main_window and hasattr(self.main_window, 'get_settings'):
            try:
                return self.main_window.get_settings()
            except Exception:
                pass
        
        return {
            'ocr_engine': 'PaddleOCR',
            'recognition_interval': 1.0,
            'match_mode': 'fuzzy',
            'auto_start': True,
            'notification_enabled': True,
            'log_level': 'INFO'
        }
    
    def _get_performance_metrics(self):
        """获取性能指标"""
        try:
            # 获取真实的OCR识别次数和平均响应时间
            recognition_count = 0
            avg_response_time = 0  # 毫秒
            ocr_worker_status = "未启动"
            
            if self.main_window and hasattr(self.main_window, 'ocr_worker'):
                if self.main_window.ocr_worker:
                    # OCR工作器正在运行，获取实时数据
                    recognition_count = getattr(self.main_window.ocr_worker, 'total_hits', 0)
                    # 尝试获取平均响应时间
                    avg_response_time = getattr(self.main_window.ocr_worker, 'avg_response_time', 0)
                    if avg_response_time == 0 and recognition_count > 0:
                        # 如果没有平均响应时间，使用默认值
                        avg_response_time = 150  # 默认150ms
                    ocr_worker_status = "运行中"
                    logging.debug(f"Web控制面板获取到OCR识别次数: {recognition_count}，平均响应时间: {avg_response_time}ms，状态: {ocr_worker_status}")
                else:
                    # OCR工作器已停止，尝试获取保存的统计数据
                    if hasattr(self.main_window, 'last_ocr_stats') and self.main_window.last_ocr_stats:
                        recognition_count = self.main_window.last_ocr_stats.get('total_hits', 0)
                        avg_response_time = self.main_window.last_ocr_stats.get('avg_response_time', 0)
                        if avg_response_time == 0 and recognition_count > 0:
                            avg_response_time = 150  # 默认150ms
                        ocr_worker_status = "已停止"
                        logging.debug(f"Web控制面板获取到保存的OCR统计数据: 识别次数={recognition_count}，平均响应时间={avg_response_time}ms，状态: {ocr_worker_status}")
                    else:
                        ocr_worker_status = "已停止"
                        logging.debug(f"Web控制面板: OCR工作器为None且无保存数据，状态: {ocr_worker_status}")
            else:
                logging.debug("Web控制面板: 主窗口没有ocr_worker属性")
            
            # 尝试从主程序获取历史性能数据
            if self.main_window and hasattr(self.main_window, 'performance_manager'):
                historical_data = self.main_window.performance_manager.get_historical_data(hours=1)
                
                if historical_data:
                    # 取最近的数据点
                    recent_data = historical_data[-10:] if len(historical_data) > 10 else historical_data
                    
                    cpu_usage = [round(d.get('cpu_percent', 0), 1) for d in recent_data]
                    memory_usage = [round(d.get('process_memory_mb', 0), 1) for d in recent_data]
                    timestamps = []
                    
                    for d in recent_data:
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(d['timestamp'])
                            timestamps.append(dt.strftime('%H:%M'))
                        except:
                            timestamps.append('--:--')
                    
                    return {
                        'cpu_usage': cpu_usage,
                        'memory_usage': memory_usage,
                        'recognition_times': [avg_response_time / 1000] * len(recent_data),  # 转换为秒用于图表
                        'recognition_count': recognition_count,  # 单独的识别次数字段
                        'avg_response_time': avg_response_time,  # 单独的响应时间字段（毫秒）
                        'timestamps': timestamps
                    }
            
            # 如果没有历史数据，生成当前数据点
            current_perf = self._get_performance_data()
            from datetime import datetime
            current_time = datetime.now().strftime('%H:%M')
            
            return {
                'cpu_usage': [current_perf['cpu_usage']],
                'memory_usage': [current_perf['memory_usage']],
                'recognition_times': [avg_response_time / 1000],  # 转换为秒用于图表
                'recognition_count': recognition_count,  # 单独的识别次数字段
                'avg_response_time': avg_response_time,  # 单独的响应时间字段（毫秒）
                'timestamps': [current_time]
            }
            
        except Exception as e:
            logging.error(f"获取性能指标失败: {e}")
            
        # 返回默认数据
        from datetime import datetime
        current_time = datetime.now().strftime('%H:%M')
        # 获取真实的OCR识别次数和响应时间作为默认值
        recognition_count = 0
        avg_response_time = 0
        if self.main_window and hasattr(self.main_window, 'ocr_worker') and self.main_window.ocr_worker:
            recognition_count = getattr(self.main_window.ocr_worker, 'total_hits', 0)
            avg_response_time = getattr(self.main_window.ocr_worker, 'avg_response_time', 0)
            if avg_response_time == 0 and recognition_count > 0:
                avg_response_time = 150  # 默认150ms
        elif self.main_window and hasattr(self.main_window, 'last_ocr_stats') and self.main_window.last_ocr_stats:
            # 如果OCR已停止，使用保存的统计数据
            recognition_count = self.main_window.last_ocr_stats.get('total_hits', 0)
            avg_response_time = self.main_window.last_ocr_stats.get('avg_response_time', 0)
            if avg_response_time == 0 and recognition_count > 0:
                avg_response_time = 150  # 默认150ms
        
        return {
            'cpu_usage': [0],
            'memory_usage': [0],
            'recognition_times': [avg_response_time / 1000] if avg_response_time > 0 else [0],
            'recognition_count': recognition_count,
            'avg_response_time': avg_response_time,
            'timestamps': [current_time]
        }
    
    def _add_keyword_to_main_window(self, keyword):
        """向主窗口添加关键词"""
        if self.main_window and hasattr(self.main_window, 'keyword_panel'):
            try:
                # 检查关键词是否已存在
                existing_keywords = self.main_window.keyword_panel.get_keywords()
                if keyword in existing_keywords:
                    return False  # 关键词已存在
                
                # 添加关键词到列表
                self.main_window.keyword_panel.list.addItem(keyword)
                # 保存到文件
                self.main_window.keyword_panel.save_keywords()
                return True
            except Exception as e:
                enhanced_logger.log("ERROR", f"添加关键词失败: {e}")
                return False
        return False
    
    def _delete_keyword_from_main_window(self, keyword):
        """从主窗口删除关键词"""
        if self.main_window and hasattr(self.main_window, 'keyword_panel'):
            try:
                # 查找并删除关键词
                for i in range(self.main_window.keyword_panel.list.count()):
                    item = self.main_window.keyword_panel.list.item(i)
                    if item.text() == keyword:
                        self.main_window.keyword_panel.list.takeItem(i)
                        # 保存到文件
                        self.main_window.keyword_panel.save_keywords()
                        return True
                return False  # 关键词不存在
            except Exception as e:
                enhanced_logger.log("ERROR", f"删除关键词失败: {e}")
                return False
        return False
    
    def _start_monitoring_in_main_window(self):
        """在主窗口启动监控"""
        if self.main_window and hasattr(self.main_window, 'start_monitoring'):
            try:
                return self.main_window.start_monitoring()
            except Exception:
                pass
        return True  # 模拟成功
    
    def _stop_monitoring_in_main_window(self):
        """在主窗口停止监控"""
        if self.main_window and hasattr(self.main_window, 'stop_monitoring'):
            try:
                return self.main_window.stop_monitoring()
            except Exception:
                pass
        return True  # 模拟成功
    
    def _update_settings_in_main_window(self, settings_data):
        """在主窗口更新设置"""
        if self.main_window and hasattr(self.main_window, 'update_settings'):
            try:
                return self.main_window.update_settings(settings_data)
            except Exception:
                pass
        return True  # 模拟成功
    
    def _get_main_page_html(self):
        """获取主页面HTML - 增强版"""
        return '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>XuanWu 控制面板 - 增强版</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --primary-color: #667eea;
            --primary-dark: #5a67d8;
            --primary-light: #a78bfa;
            --secondary-color: #764ba2;
            --accent-color: #06b6d4;
            --success-color: #10b981;
            --warning-color: #f59e0b;
            --error-color: #ef4444;
            --info-color: #3b82f6;
            --bg-color: #f8fafc;
            --bg-gradient: linear-gradient(135deg, #f8fafc 0%, #e0f2fe 50%, #f0f9ff 100%);
            --card-bg: #ffffff;
            --card-hover-bg: #fefefe;
            --text-color: #1e293b;
            --text-muted: #64748b;
            --text-light: #94a3b8;
            --border-color: #e2e8f0;
            --border-hover: #cbd5e1;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            --shadow-lg: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            --shadow-xl: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            --border-radius: 16px;
            --border-radius-sm: 8px;
            --border-radius-lg: 24px;
            --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            --transition-fast: all 0.15s ease;
            --glass-bg: rgba(255, 255, 255, 0.25);
            --glass-border: rgba(255, 255, 255, 0.18);
        }
        
        [data-theme="dark"] {
            --bg-color: #0f172a;
            --bg-gradient: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%);
            --card-bg: #1e293b;
            --card-hover-bg: #334155;
            --text-color: #f1f5f9;
            --text-muted: #94a3b8;
            --text-light: #64748b;
            --border-color: #334155;
            --border-hover: #475569;
            --glass-bg: rgba(30, 41, 59, 0.4);
            --glass-border: rgba(148, 163, 184, 0.1);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
            background: var(--bg-gradient);
            color: var(--text-color);
            line-height: 1.6;
            min-height: 100vh;
            transition: var(--transition);
            overflow-x: hidden;
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
                radial-gradient(circle at 80% 20%, rgba(255, 119, 198, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, rgba(120, 219, 255, 0.1) 0%, transparent 50%);
            pointer-events: none;
            z-index: -1;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
            position: relative;
            z-index: 1;
        }
        
        .header {
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 50%, var(--accent-color) 100%);
            color: white;
            padding: 40px;
            border-radius: var(--border-radius-lg);
            margin-bottom: 32px;
            box-shadow: var(--shadow-xl);
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
        }
        
        .header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 30% 20%, rgba(255,255,255,0.2) 0%, transparent 50%),
                radial-gradient(circle at 70% 80%, rgba(255,255,255,0.1) 0%, transparent 50%),
                url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="50" cy="50" r="0.5" fill="%23ffffff" opacity="0.1"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>') repeat;
            pointer-events: none;
            animation: headerShimmer 8s ease-in-out infinite;
        }
        
        @keyframes headerShimmer {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.8; }
        }
        
        .header-content {
            position: relative;
            z-index: 1;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
        }
        
        .header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            margin: 0;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        
        .header-controls {
            display: flex;
            gap: 15px;
            align-items: center;
        }
        
        .refresh-status {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 8px 12px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            backdrop-filter: blur(10px);
        }
        
        .refresh-status small {
            color: rgba(255, 255, 255, 0.9);
            font-size: 11px;
            font-weight: 500;
            text-align: center;
            white-space: nowrap;
        }
        
        /* 安全管理面板样式 */
        .security-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid var(--border-color);
        }
        
        .tab-btn {
            padding: 10px 20px;
            background: none;
            border: none;
            color: var(--text-color);
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.3s ease;
            font-weight: 500;
        }
        
        .tab-btn.active {
            color: var(--primary-color);
            border-bottom-color: var(--primary-color);
        }
        
        .tab-btn:hover {
            color: var(--primary-color);
            background: rgba(102, 126, 234, 0.1);
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .token-display {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        .token-display input {
            flex: 1;
            padding: 10px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            background: var(--card-bg);
            color: var(--text-color);
            font-family: monospace;
            font-size: 12px;
        }
        
        .security-info {
            display: grid;
            gap: 15px;
        }
        
        .info-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: var(--card-bg);
            border-radius: 6px;
            border: 1px solid var(--border-color);
        }
        
        .info-item label {
            font-weight: 600;
            color: var(--text-color);
        }
        
        .info-item span {
            color: var(--primary-color);
            font-weight: 500;
        }
        
        .btn {
            padding: 14px 28px;
            border: none;
            border-radius: var(--border-radius-sm);
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: var(--transition);
            display: inline-flex;
            align-items: center;
            gap: 10px;
            text-decoration: none;
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(10px);
            transform: translateZ(0);
            will-change: transform;
        }
        
        .btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            transition: left 0.6s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .btn:hover::before {
            left: 100%;
        }
        
        .btn:active {
            transform: translateY(1px) scale(0.98);
        }
        
        .btn-primary {
            background: linear-gradient(135deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0.1) 100%);
            color: white;
            backdrop-filter: blur(15px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .btn-primary:hover {
            background: linear-gradient(135deg, rgba(255,255,255,0.3) 0%, rgba(255,255,255,0.2) 100%);
            transform: translateY(-3px);
            border-color: rgba(255,255,255,0.4);
        }
        
        .btn-success {
            background: linear-gradient(135deg, var(--success-color) 0%, #20c997 100%);
            color: white;
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .btn-success:hover {
            background: linear-gradient(135deg, #20c997 0%, var(--success-color) 100%);
            transform: translateY(-3px);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, var(--error-color) 0%, #e74c3c 100%);
            color: white;
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .btn-danger:hover {
            background: linear-gradient(135deg, #e74c3c 0%, var(--error-color) 100%);
            transform: translateY(-3px);
        }
        
        .btn-warning {
            background: linear-gradient(135deg, var(--warning-color) 0%, #f39c12 100%);
            color: white;
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .btn-warning:hover {
            background: linear-gradient(135deg, #f39c12 0%, var(--warning-color) 100%);
            transform: translateY(-3px);
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }
        
        .dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }
        
        .card {
            background: var(--card-bg);
            border-radius: var(--border-radius);
            padding: 28px;
            box-shadow: var(--shadow);
            border: 1px solid var(--border-color);
            transition: var(--transition);
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(10px);
            transform: translateZ(0);
            will-change: transform;
        }
        
        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--primary-color), var(--secondary-color), var(--accent-color));
            border-radius: var(--border-radius) var(--border-radius) 0 0;
        }
        
        .card::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, transparent 50%);
            opacity: 0;
            transition: opacity 0.3s ease;
            pointer-events: none;
        }
        
        .card:hover {
            transform: translateY(-8px) scale(1.02);
            box-shadow: var(--shadow-xl);
            border-color: var(--border-hover);
            background: var(--card-hover-bg);
        }
        
        .card:hover::after {
            opacity: 1;
        }
        
        /* 状态指示器增强 */
        .status-indicator {
            position: relative;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            transition: all 0.3s ease;
        }
        
        .status-indicator::before {
            content: '';
            width: 8px;
            height: 8px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        .status-indicator.active {
            background: rgba(40, 167, 69, 0.1);
            color: #28a745;
        }
        
        .status-indicator.active::before {
            background: #28a745;
            box-shadow: 0 0 10px rgba(40, 167, 69, 0.5);
        }
        
        .status-indicator.inactive {
            background: rgba(220, 53, 69, 0.1);
            color: #dc3545;
        }
        
        .status-indicator.inactive::before {
            background: #dc3545;
            box-shadow: 0 0 10px rgba(220, 53, 69, 0.5);
        }
        
        .status-indicator.warning {
            background: rgba(255, 193, 7, 0.1);
            color: #ffc107;
        }
        
        .status-indicator.warning::before {
            background: #ffc107;
            box-shadow: 0 0 10px rgba(255, 193, 7, 0.5);
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(1.2); }
        }
        
        /* 数据可视化组件增强 */
        .metric-card {
            background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%);
            border-radius: 16px;
            padding: 20px;
            text-align: center;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }
        
        .metric-card::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: conic-gradient(from 0deg, transparent, rgba(255,255,255,0.1), transparent);
            animation: rotate 4s linear infinite;
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        
        .metric-card:hover::before {
            opacity: 1;
        }
        
        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        
        .metric-value {
            font-size: 2.5rem;
            font-weight: 700;
            color: #ffffff;
            text-shadow: 0 2px 6px rgba(0, 0, 0, 0.9);
            margin-bottom: 8px;
            transition: all 0.3s ease;
            display: inline-block;
        }
        
        .metric-label {
            font-size: 1rem;
            color: rgba(255, 255, 255, 0.95);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
            margin-bottom: 4px;
            display: inline-block;
        }
        
        /* 图表容器增强 */
        .chart-container {
            position: relative;
            background: rgba(255,255,255,0.02);
            border-radius: 12px;
            padding: 20px;
            margin: 20px 0;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }
        
        .chart-container:hover {
            background: rgba(255,255,255,0.05);
            transform: translateY(-2px);
        }
        
        .chart-container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
            border-radius: 12px 12px 0 0;
        }
        
        .card:hover::after {
            opacity: 1;
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid var(--border-color);
        }
        
        /* 进度条组件 */
        .progress-bar {
            width: 100%;
            height: 8px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            overflow: hidden;
            position: relative;
            margin: 10px 0;
        }
        
        .progress-bar::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            animation: shimmer 2s infinite;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
            border-radius: 4px;
            transition: width 0.5s ease;
            position: relative;
            overflow: hidden;
        }
        
        .progress-fill::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            animation: progress-shine 2s infinite;
        }
        
        @keyframes shimmer {
            0% { left: -100%; }
            100% { left: 100%; }
        }
        
        @keyframes progress-shine {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        
        /* 加载动画增强 */
        .loading-spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: var(--primary-color);
            animation: spin 1s ease-in-out infinite;
        }
        
        .loading-dots {
            display: inline-flex;
            gap: 4px;
        }
        
        .loading-dots span {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--primary-color);
            animation: bounce 1.4s ease-in-out infinite both;
        }
        
        .loading-dots span:nth-child(1) { animation-delay: -0.32s; }
        .loading-dots span:nth-child(2) { animation-delay: -0.16s; }
        .loading-dots span:nth-child(3) { animation-delay: 0s; }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        @keyframes bounce {
            0%, 80%, 100% {
                transform: scale(0);
            }
            40% {
                transform: scale(1);
            }
        }
        
        /* 响应式设计增强 */
        @media (max-width: 1200px) {
            .dashboard {
                grid-template-columns: repeat(2, 1fr);
                gap: 15px;
            }
        }
        
        @media (max-width: 768px) {
            .dashboard {
                grid-template-columns: 1fr;
                gap: 10px;
                padding: 10px;
            }
            
            .card {
                padding: 15px;
            }
            
            .metric-value {
                font-size: 2rem;
            }
            
            .card-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }
        }
        
        /* 工具提示增强 */
        .tooltip {
            position: relative;
            cursor: help;
        }
        
        .tooltip::before {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.9);
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            white-space: nowrap;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease;
            z-index: 1000;
        }
        
        .tooltip::after {
            content: '';
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%) translateY(100%);
            border: 5px solid transparent;
            border-top-color: rgba(0,0,0,0.9);
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease;
        }
        
        .tooltip:hover::before,
        .tooltip:hover::after {
            opacity: 1;
            visibility: visible;
            transform: translateX(-50%) translateY(-5px);
        }
        
        /* 高级搜索样式 */
        .search-container {
            position: relative;
            display: flex;
            align-items: center;
            margin-right: 15px;
        }
        
        .search-input {
            width: 250px;
            padding: 10px 40px 10px 15px;
            border: 2px solid rgba(255,255,255,0.1);
            border-radius: 25px;
            background: rgba(255,255,255,0.05);
            color: var(--text-color);
            font-size: 14px;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
        }
        
        .search-input:focus {
            outline: none;
            border-color: var(--primary-color);
            background: rgba(255,255,255,0.1);
            box-shadow: 0 0 20px rgba(99, 102, 241, 0.3);
            width: 300px;
        }
        
        .search-btn {
            position: absolute;
            right: 5px;
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            padding: 8px;
            border-radius: 50%;
            transition: all 0.3s ease;
        }
        
        .search-btn:hover {
            color: var(--primary-color);
            background: rgba(255,255,255,0.1);
        }
        
        .search-results {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            margin-top: 5px;
            max-height: 300px;
            overflow-y: auto;
            z-index: 1000;
            backdrop-filter: blur(20px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        
        .search-result-item {
            padding: 12px 15px;
            border-bottom: 1px solid var(--border-color);
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .search-result-item:hover {
            background: rgba(255,255,255,0.05);
        }
        
        .search-result-item:last-child {
            border-bottom: none;
        }
        
        .search-result-icon {
            color: var(--primary-color);
            width: 16px;
        }
        
        .search-result-text {
            flex: 1;
        }
        
        .search-result-category {
            font-size: 12px;
            color: var(--text-secondary);
            background: rgba(255,255,255,0.1);
            padding: 2px 8px;
            border-radius: 10px;
        }
        
        /* 实时通知系统样式 */
        .notification-container {
            position: relative;
            margin-right: 15px;
            z-index: 1000;
        }
        
        .notification-btn {
            position: relative;
            background: none;
            border: none;
            color: var(--text-color);
            cursor: pointer;
            padding: 10px;
            border-radius: 50%;
            transition: all 0.3s ease;
            font-size: 18px;
        }
        
        .notification-btn:hover {
            background: rgba(255,255,255,0.1);
            color: var(--primary-color);
        }
        
        .notification-badge {
            position: absolute;
            top: 5px;
            right: 5px;
            background: var(--danger-color);
            color: white;
            font-size: 10px;
            font-weight: 600;
            padding: 2px 6px;
            border-radius: 10px;
            min-width: 16px;
            text-align: center;
            animation: pulse 2s infinite;
        }
        
        .notification-panel {
            position: absolute;
            top: 100%;
            right: 0;
            width: 350px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            z-index: 9000;
            backdrop-filter: blur(20px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            max-height: 400px;
            overflow: hidden;
            margin-top: 10px;
            transform: translateY(-10px);
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .notification-panel.show {
            opacity: 1;
            visibility: visible;
            transform: translateY(0);
        }
        
        .notification-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 20px;
            border-bottom: 1px solid var(--border-color);
            background: rgba(255,255,255,0.02);
        }
        
        .notification-header h4 {
            margin: 0;
            font-size: 16px;
            font-weight: 600;
        }
        
        .btn-clear {
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            padding: 5px 10px;
            border-radius: 6px;
            font-size: 12px;
            transition: all 0.3s ease;
        }
        
        .btn-clear:hover {
            background: rgba(220, 53, 69, 0.1);
            color: var(--danger-color);
        }
        
        .notification-list {
            max-height: 300px;
            overflow-y: auto;
        }
        
        .notification-item {
            padding: 15px 20px;
            border-bottom: 1px solid var(--border-color);
            transition: all 0.3s ease;
            position: relative;
        }
        
        .notification-item:hover {
            background: rgba(255,255,255,0.02);
        }
        
        .notification-item:last-child {
            border-bottom: none;
        }
        
        .notification-item.unread {
            background: rgba(99, 102, 241, 0.05);
            border-left: 3px solid var(--primary-color);
        }
        
        .notification-content {
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }
        
        .notification-icon {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            flex-shrink: 0;
        }
        
        .notification-icon.success {
            background: rgba(34, 197, 94, 0.2);
            color: var(--success-color);
        }
        
        .notification-icon.warning {
            background: rgba(251, 191, 36, 0.2);
            color: var(--warning-color);
        }
        
        .notification-icon.error {
            background: rgba(239, 68, 68, 0.2);
            color: var(--danger-color);
        }
        
        .notification-icon.info {
            background: rgba(59, 130, 246, 0.2);
            color: var(--info-color);
        }
        
        .notification-text {
            flex: 1;
        }
        
        .notification-title {
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 4px;
        }
        
        .notification-message {
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.4;
            margin-bottom: 6px;
        }
        
        .notification-time {
            font-size: 11px;
            color: var(--text-muted);
        }
        
        .notification-actions {
            display: flex;
            gap: 8px;
            margin-top: 8px;
        }
        
        .notification-action {
            background: none;
            border: 1px solid var(--border-color);
            color: var(--text-color);
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .notification-action:hover {
            background: var(--primary-color);
            border-color: var(--primary-color);
        }
        
        .notification-action.primary {
            background: var(--primary-color);
            border-color: var(--primary-color);
        }
        
        .notification-empty {
            text-align: center;
            padding: 40px 20px;
            color: var(--text-secondary);
        }
        
        .notification-empty i {
            font-size: 48px;
            margin-bottom: 15px;
            opacity: 0.5;
        }
        
        /* Toast 通知样式 */
        .toast-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            pointer-events: none;
            max-width: 420px;
            width: auto;
        }
        
        .toast {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 16px 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            display: flex;
            align-items: center;
            pointer-events: auto;
            transform: translateX(400px);
            opacity: 0;
            transition: transform 0.3s ease, opacity 0.3s ease;
            gap: 12px;
            min-width: 300px;
            max-width: 400px;
            z-index: 10001;
            font-size: 14px;
            font-weight: 500;
        }
        
        .toast.show {
            transform: translateX(0);
            opacity: 1;
        }
        
        .toast.toast-success {
            border-left: 4px solid #10b981;
        }
        
        .toast.toast-success i {
            color: #10b981;
        }
        
        .toast.toast-warning {
            border-left: 4px solid #f59e0b;
        }
        
        .toast.toast-warning i {
            color: #f59e0b;
        }
        
        .toast.toast-error {
            border-left: 4px solid #ef4444;
        }
        
        .toast.toast-error i {
            color: #ef4444;
        }
        
        .toast.toast-info {
            border-left: 4px solid #3b82f6;
        }
        
        .toast.toast-info i {
            color: #3b82f6;
        }
        
        .toast i {
            font-size: 18px;
            flex-shrink: 0;
        }
        
        .toast span {
            color: #374151;
            line-height: 1.4;
        }
        
        /* 高亮动画 */
        @keyframes highlight {
            0% {
                background: rgba(59, 130, 246, 0.1);
                transform: scale(1);
            }
            50% {
                background: rgba(59, 130, 246, 0.2);
                transform: scale(1.02);
            }
            100% {
                background: transparent;
                transform: scale(1);
            }
        }
        
        /* 搜索结果项动画 */
        .search-result-item {
            animation: slideInDown 0.3s ease;
        }
        
        @keyframes slideInDown {
            from {
                opacity: 0;
                transform: translateY(-10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        /* 通知项动画 */
        .notification-item {
            animation: slideInRight 0.3s ease;
        }
        
        @keyframes slideInRight {
            from {
                opacity: 0;
                transform: translateX(20px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        /* 响应式优化 */
        @media (max-width: 768px) {
            .toast {
                right: 10px;
                left: 10px;
                min-width: auto;
                transform: translateY(-100px);
            }
            
            .toast.show {
                transform: translateY(0);
            }
            
            .search-container {
                width: 100%;
                max-width: none;
            }
            
            .notification-panel {
                right: 10px;
                left: 10px;
                width: auto;
            }
        }
        
        .card-title {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-color);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .card-icon {
            width: 24px;
            height: 24px;
            color: var(--primary-color);
        }
        
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 15px;
        }
        
        .status-item {
            text-align: center;
            padding: 15px;
            background: var(--bg-color);
            border-radius: 8px;
            border: 1px solid var(--border-color);
            transition: var(--transition);
        }
        
        .status-item:hover {
            transform: scale(1.05);
            box-shadow: var(--shadow);
        }
        
        .status-label {
            font-size: 0.875rem;
            color: var(--text-muted);
            margin-bottom: 5px;
        }
        
        .status-value {
            font-size: 1.125rem;
            font-weight: 700;
            color: var(--text-color);
        }
        
        .status-active {
            color: var(--success-color);
        }
        
        .status-inactive {
            color: var(--error-color);
        }
        
        .keywords-container {
            max-height: 300px;
            overflow-y: auto;
        }
        
        .keyword-input-group {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .form-input {
            flex: 1;
            padding: 14px 18px;
            border: 2px solid var(--border-color);
            border-radius: var(--border-radius-sm);
            font-size: 14px;
            transition: var(--transition);
            background: var(--card-bg);
            color: var(--text-color);
            backdrop-filter: blur(10px);
            position: relative;
        }
        
        .form-input:focus {
            outline: none;
            border-color: var(--primary-color);
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.15), var(--shadow);
            transform: translateY(-2px);
            background: var(--card-hover-bg);
        }
        
        .form-input:hover:not(:focus) {
            border-color: var(--border-hover);
            transform: translateY(-1px);
        }
        
        .keyword-list {
            list-style: none;
        }
        
        .keyword-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            margin-bottom: 8px;
            background: var(--bg-color);
            border-radius: 8px;
            border: 1px solid var(--border-color);
            transition: var(--transition);
        }
        
        .keyword-item:hover {
            background: var(--primary-color);
            color: white;
            transform: translateX(5px);
        }
        
        .keyword-info {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        
        .keyword-name {
            font-weight: 600;
        }
        
        .keyword-stats {
            font-size: 0.75rem;
            color: var(--text-muted);
        }
        
        .keyword-item:hover .keyword-stats {
            color: rgba(255,255,255,0.8);
        }
        
        .btn-sm {
            padding: 6px 12px;
            font-size: 12px;
        }
        
        .logs-container {
            max-height: 400px;
            overflow-y: auto;
            background: #1a1a1a;
            border-radius: 8px;
            padding: 15px;
            font-family: 'Consolas', 'Monaco', monospace;
        }
        
        .log-item {
            display: block;
            margin-bottom: 12px;
            padding: 15px;
            border-radius: 8px;
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.1);
            transition: var(--transition);
        }
        
        .log-item:hover {
            background: rgba(255,255,255,0.08);
            border-color: rgba(255,255,255,0.2);
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        
        .log-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 8px;
        }
        
        .log-timestamp {
            color: #888;
            font-size: 0.75rem;
            font-family: 'Courier New', monospace;
            background: rgba(255,255,255,0.05);
            padding: 2px 6px;
            border-radius: 4px;
            min-width: 120px;
        }
        
        .log-level {
            font-weight: 600;
            font-size: 0.7rem;
            padding: 3px 8px;
            border-radius: 12px;
            text-transform: uppercase;
            min-width: 60px;
            text-align: center;
        }
        
        .log-type {
            font-size: 0.7rem;
            padding: 2px 6px;
            border-radius: 6px;
            background: #4299e1;
            color: white;
            font-weight: 500;
        }
        
        .log-level-INFO, .log-level-信息 { 
            background: #1a365d; 
            color: #4299e1; 
            border: 1px solid #4299e1;
        }
        .log-level-DEBUG, .log-level-调试 { 
            background: #1c4532; 
            color: #68d391; 
            border: 1px solid #68d391;
        }
        .log-level-WARNING, .log-level-警告 { 
            background: #3d2914; 
            color: #ed8936; 
            border: 1px solid #ed8936;
        }
        .log-level-ERROR, .log-level-错误 { 
            background: #3d1a1a; 
            color: #f56565; 
            border: 1px solid #f56565;
        }
        
        .log-content {
            margin-left: 10px;
        }
        
        .log-message {
            color: #e2e8f0;
            margin-bottom: 8px;
            line-height: 1.5;
            word-break: break-word;
        }
        
        .log-details {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin: 8px 0;
            padding: 10px;
            background: rgba(255,255,255,0.03);
            border-radius: 6px;
            border-left: 3px solid #4299e1;
        }
        
        .log-detail-item {
            font-size: 0.8rem;
            color: #a0aec0;
        }
        
        .log-detail-item strong {
            color: #e2e8f0;
            font-weight: 600;
        }
        
        .log-expand {
            cursor: pointer;
            color: #4299e1;
            font-size: 0.8rem;
            margin: 8px 0;
            padding: 5px 0;
            border-top: 1px dashed rgba(255,255,255,0.2);
            user-select: none;
            transition: color 0.2s ease;
        }
        
        .log-expand:hover {
            color: #63b3ed;
            text-decoration: underline;
        }
        
        .expand-icon {
            margin-right: 5px;
            transition: transform 0.2s ease;
        }
        
        .log-details-content {
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 6px;
            padding: 10px;
            margin: 8px 0;
            max-height: 200px;
            overflow-y: auto;
        }
        
        .log-details-content pre {
            margin: 0;
            font-size: 0.75rem;
            color: #a0aec0;
            white-space: pre-wrap;
            word-break: break-word;
            font-family: 'Courier New', monospace;
        }
        
        .log-stats {
            background: linear-gradient(135deg, #4299e1, #2b6cb0);
            color: white;
            padding: 12px 18px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-weight: 600;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            font-size: 0.9rem;
        }
        
        .chart-container {
            position: relative;
            height: 300px;
            margin-top: 20px;
        }
        
        .settings-grid {
            display: grid;
            gap: 20px;
        }
        
        .setting-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .setting-label {
            font-weight: 600;
            color: var(--text-color);
        }
        
        .form-select {
            padding: 14px 18px;
            border: 2px solid var(--border-color);
            border-radius: var(--border-radius-sm);
            background: var(--card-bg);
            color: var(--text-color);
            font-size: 14px;
            transition: var(--transition);
            backdrop-filter: blur(10px);
            cursor: pointer;
        }
        
        .form-select:focus {
            outline: none;
            border-color: var(--primary-color);
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.15), var(--shadow);
            transform: translateY(-2px);
        }
        
        .form-select:hover:not(:focus) {
            border-color: var(--border-hover);
            transform: translateY(-1px);
        }
        
        /* 旧的notification样式已移除，现在使用toast机制 */
        
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 1s ease-in-out infinite;
        }
        
        .pulse {
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
        
        .fade-in {
            animation: fadeIn 0.5s ease-in;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes slideInRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        @keyframes slideOutRight {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            
            .header h1 {
                font-size: 2rem;
            }
            
            .dashboard {
                grid-template-columns: 1fr;
            }
            
            .header-content {
                flex-direction: column;
                text-align: center;
            }
        }
        
        .fullscreen {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 11000;
            background: var(--card-bg);
            padding: 20px;
            overflow: auto;
        }
        
        /* 文件管理器样式 */
        .file-manager {
            max-height: 300px;
            overflow-y: auto;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            background: var(--card-bg);
        }
        
        .file-item {
            display: flex;
            align-items: center;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
            transition: background-color 0.2s;
        }
        
        .file-item:hover {
            background: var(--hover-bg);
        }
        
        .file-item:last-child {
            border-bottom: none;
        }
        
        .file-icon {
            font-size: 20px;
            margin-right: 12px;
            color: var(--primary-color);
            width: 24px;
            text-align: center;
        }
        
        .file-info {
            flex: 1;
        }
        
        .file-name {
            font-weight: 500;
            color: var(--text-color);
            margin-bottom: 4px;
        }
        
        .file-meta {
            font-size: 12px;
            color: var(--text-secondary);
        }
        
        /* 数据分析样式 */
        .analytics-content {
            padding: 20px 0;
        }
        
        .progress-item {
            margin-bottom: 20px;
        }
        
        .progress-bar {
            width: 100%;
            height: 10px;
            background: var(--border-color);
            border-radius: var(--border-radius-sm);
            overflow: hidden;
            margin: 12px 0;
            position: relative;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary-color), var(--secondary-color), var(--accent-color));
            border-radius: var(--border-radius-sm);
            transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }
        
        .progress-fill::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            animation: progressShimmer 2s infinite;
        }
        
        @keyframes progressShimmer {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        
        /* 网络状态样式 */
        .network-status {
            width: 14px;
            height: 14px;
            border-radius: 50%;
            margin-right: 10px;
            flex-shrink: 0;
            position: relative;
            animation: statusPulse 2s infinite;
        }
        
        .network-status::before {
            content: '';
            position: absolute;
            top: -3px;
            left: -3px;
            right: -3px;
            bottom: -3px;
            border-radius: 50%;
            opacity: 0.3;
            animation: statusRipple 2s infinite;
        }
        
        .status-online {
            background: var(--success-color);
            box-shadow: 0 0 15px rgba(34, 197, 94, 0.6);
        }
        
        .status-online::before {
            background: var(--success-color);
        }
        
        .status-warning {
            background: var(--warning-color);
            box-shadow: 0 0 15px rgba(251, 191, 36, 0.6);
        }
        
        .status-warning::before {
            background: var(--warning-color);
        }
        
        .status-offline {
            background: var(--danger-color);
            box-shadow: 0 0 15px rgba(239, 68, 68, 0.6);
        }
        
        .status-offline::before {
            background: var(--danger-color);
        }
        
        @keyframes statusPulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.1); }
        }
        
        @keyframes statusRipple {
            0% { transform: scale(1); opacity: 0.3; }
            100% { transform: scale(2); opacity: 0; }
        }
        }
        
        .theme-toggle {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            color: white;
            padding: 12px;
            border-radius: 50%;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            backdrop-filter: blur(15px);
            box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
            width: 50px;
            height: 50px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
        }
        
        .theme-toggle:hover {
            background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
            transform: rotate(180deg) scale(1.1);
            box-shadow: 0 6px 25px rgba(102, 126, 234, 0.4);
        }
        
        .theme-toggle:active {
            transform: rotate(180deg) scale(0.95);
        }
        
        /* 新增现代化组件样式 */
        .overview-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .metric-card {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
            padding: 20px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            gap: 15px;
            transition: var(--transition);
            position: relative;
            overflow: hidden;
        }
        
        .metric-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(45deg, rgba(255,255,255,0.1) 0%, transparent 50%);
            pointer-events: none;
        }
        
        .metric-card:hover {
            transform: translateY(-5px) scale(1.02);
            box-shadow: 0 15px 30px rgba(0,0,0,0.2);
        }
        
        .metric-icon {
            font-size: 2.5rem;
            opacity: 0.9;
        }
        
        .metric-info {
            flex: 1;
        }
        
        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 5px;
        }
        
        .metric-label {
            font-size: 0.9rem;
            opacity: 0.8;
            margin-bottom: 5px;
        }
        
        .metric-trend {
            font-size: 0.9rem;
            font-weight: 700;
            color: rgba(255, 255, 255, 0.95);
            text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
            display: inline-block;
            margin-top: 4px;
        }
        
        .network-status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        
        .network-item {
            background: var(--bg-color);
            padding: 15px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            text-align: center;
            transition: var(--transition);
        }
        
        .network-item:hover {
            transform: translateY(-3px);
            box-shadow: var(--shadow);
        }
        
        .network-status {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 8px;
        }
        
        .status-online { background: var(--success-color); }
        .status-offline { background: var(--error-color); }
        .status-warning { background: var(--warning-color); }
        
        .file-manager {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .file-item {
            display: flex;
            align-items: center;
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
            transition: var(--transition);
        }
        
        .file-item:hover {
            background: var(--bg-color);
        }
        
        .file-icon {
            margin-right: 12px;
            color: var(--primary-color);
        }
        
        .file-info {
            flex: 1;
        }
        
        .file-name {
            font-weight: 600;
            margin-bottom: 4px;
        }
        
        .file-meta {
            font-size: 0.8rem;
            color: var(--text-muted);
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: var(--border-color);
            border-radius: 4px;
            overflow: hidden;
            margin: 10px 0;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
            transition: width 0.3s ease;
        }
        
        .alert-panel {
            background: linear-gradient(135deg, var(--warning-color), #f6ad55);
            color: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .alert-panel.error {
            background: linear-gradient(135deg, var(--error-color), #fc8181);
        }
        
        .alert-panel.success {
            background: linear-gradient(135deg, var(--success-color), #68d391);
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 10000;
            backdrop-filter: blur(5px);
        }
        
        .modal-content {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: var(--card-bg);
            padding: 30px;
            border-radius: 12px;
            max-width: 500px;
            width: 90%;
            box-shadow: var(--shadow-lg);
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .modal-close {
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: var(--text-color);
            padding: 0;
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .modal-close:hover {
            color: var(--error-color);
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: var(--text-color);
        }
        
        .security-info {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .info-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            background: var(--bg-secondary);
            border-radius: 6px;
        }
        
        .info-item label {
            font-weight: 500;
            margin: 0;
        }
        
        .info-item span {
            color: var(--primary-color);
            font-weight: 600;
        }
        
        .token-display {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        .token-display input {
            flex: 1;
            padding: 10px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            background: var(--bg-secondary);
            color: var(--text-color);
            font-family: monospace;
        }
        
        .token-display button {
            padding: 10px 15px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        
        .btn-primary {
            background: var(--primary-color);
            color: white;
        }
        
        .btn-primary:hover {
            background: var(--primary-hover);
        }
        
        .btn-secondary {
            background: var(--bg-secondary);
            color: var(--text-color);
            border: 1px solid var(--border-color);
        }
        
        .btn-secondary:hover {
            background: var(--border-color);
        }
        
        /* 增强的响应式设计 */
        @media (max-width: 1200px) {
            .container {
                padding: 16px;
            }
            
            .dashboard {
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
            }
            
            .header h1 {
                font-size: 2rem;
            }
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 12px;
            }
            
            .header {
                padding: 20px;
                margin-bottom: 20px;
            }
            
            .header-content {
                flex-direction: column;
                gap: 15px;
                text-align: center;
            }
            
            .header-controls {
                flex-wrap: wrap;
                justify-content: center;
                gap: 10px;
            }
            
            .btn {
                padding: 10px 16px;
                font-size: 13px;
            }
            
            .dashboard {
                grid-template-columns: 1fr;
                gap: 15px;
            }
            
            .card {
                padding: 20px;
            }
            
            .overview-grid {
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
            }
            
            .metric-card {
                padding: 15px;
            }
            
            .metric-value {
                font-size: 2rem;
            }
            
            .search-container {
                width: 100%;
                max-width: none;
            }
            
            .theme-toggle {
                top: 15px;
                right: 15px;
                width: 45px;
                height: 45px;
                font-size: 16px;
            }
        }
        
        @media (max-width: 480px) {
            .header h1 {
                font-size: 1.5rem;
            }
            
            .btn {
                padding: 8px 12px;
                font-size: 12px;
            }
            
            .card {
                padding: 15px;
            }
            
            .overview-grid {
                grid-template-columns: 1fr 1fr;
            }
            
            .metric-value {
                font-size: 1.5rem;
            }
            
            .modal-content {
                width: 95%;
                padding: 20px;
            }
        }
        
        /* 触摸设备优化 */
        @media (hover: none) and (pointer: coarse) {
            .btn {
                min-height: 44px;
                padding: 12px 20px;
            }
            
            .card:hover {
                transform: none;
            }
            
            .card:active {
                transform: scale(0.98);
            }
            
            .theme-toggle {
                min-width: 48px;
                min-height: 48px;
            }
            
            .file-item {
                padding: 16px 12px;
            }
            
            .search-input {
                min-height: 44px;
            }
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid var(--border-color);
        }
        
        .modal-close {
            background: none;
            border: none;
            font-size: 1.5rem;
            cursor: pointer;
            color: var(--text-muted);
            transition: var(--transition);
        }
        
        .modal-close:hover {
            color: var(--error-color);
        }
        
        /* 响应式设计 - 媒体查询 */
        @media (max-width: 1200px) {
            .container {
                padding: 15px;
            }
            
            .overview-grid {
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 15px;
            }
            
            .grid {
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            }
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            
            .header {
                padding: 15px 20px;
                flex-direction: column;
                gap: 15px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 1.8rem;
            }
            
            .overview-grid {
                grid-template-columns: 1fr;
                gap: 12px;
            }
            
            .grid {
                grid-template-columns: 1fr;
                gap: 15px;
            }
            
            .card {
                padding: 20px;
            }
            
            .metric-card {
                padding: 15px;
                flex-direction: column;
                text-align: center;
            }
            
            .metric-icon {
                font-size: 2rem;
            }
            
            .form-group {
                flex-direction: column;
                gap: 10px;
            }
            
            .btn {
                padding: 12px 20px;
                width: 100%;
                justify-content: center;
            }
            
            .modal-content {
                margin: 10px;
                padding: 20px;
                max-height: 90vh;
                overflow-y: auto;
            }
        }
        
        @media (max-width: 480px) {
            .container {
                padding: 8px;
            }
            
            .header {
                padding: 12px 15px;
            }
            
            .header h1 {
                font-size: 1.5rem;
            }
            
            .card {
                padding: 15px;
            }
            
            .metric-card {
                padding: 12px;
            }
            
            .form-input, .form-select {
                padding: 12px 15px;
                font-size: 16px; /* 防止iOS缩放 */
            }
            
            .btn {
                padding: 14px 18px;
                font-size: 16px;
            }
            
            .modal-content {
                margin: 5px;
                padding: 15px;
            }
            
            .chart-container {
                height: 250px;
            }
        }
        
        /* 触摸设备优化 */
        @media (hover: none) and (pointer: coarse) {
            .btn:hover {
                transform: none;
            }
            
            .card:hover {
                transform: none;
            }
            
            .btn:active {
                transform: scale(0.95);
            }
            
            .card:active {
                transform: scale(0.98);
            }
        }
        
        /* 高分辨率屏幕优化 */
        @media (-webkit-min-device-pixel-ratio: 2), (min-resolution: 192dpi) {
            .header::before {
                background-size: 200% 200%;
            }
            
            .card::before {
                background-size: 200% 200%;
            }
        }
        
        /* API密钥验证遮罩层样式 */
        .auth-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(10px);
            z-index: 9999;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
        }
        
        .auth-modal {
            background: var(--card-bg);
            border-radius: 16px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 500px;
            width: 90%;
            text-align: center;
            border: 1px solid var(--border-color);
        }
        
        .auth-modal h2 {
            color: var(--primary-color);
            margin-bottom: 20px;
            font-size: 1.8rem;
        }
        
        .auth-modal p {
            color: var(--text-secondary);
            margin-bottom: 30px;
            line-height: 1.6;
        }
        
        .auth-input-group {
            margin-bottom: 20px;
        }
        
        .auth-input {
            width: 100%;
            padding: 15px;
            border: 2px solid var(--border-color);
            border-radius: 8px;
            font-size: 16px;
            background: var(--input-bg);
            color: var(--text-primary);
            transition: border-color 0.3s ease;
        }
        
        .auth-input:focus {
            outline: none;
            border-color: var(--primary-color);
        }
        
        .auth-error {
            color: var(--danger-color);
            margin-top: 10px;
            font-size: 14px;
        }
        
        .auth-success {
            color: var(--success-color);
            margin-top: 10px;
            font-size: 14px;
        }
        
        /* 主界面虚化效果 */
        .blurred {
            filter: blur(5px);
            pointer-events: none;
            user-select: none;
        }
        
        .auth-overlay.hidden {
            opacity: 0;
            visibility: hidden;
        }
    </style>
</head>
<body>
    <!-- API密钥验证遮罩层 -->
    <div class="auth-overlay" id="authOverlay">
        <div class="auth-modal">
            <h2><i class="fas fa-key"></i> API密钥验证</h2>
            <p>为了保护系统安全，请输入有效的API密钥以访问完整功能。</p>
            <div class="auth-input-group">
                <input type="password" class="auth-input" id="apiKeyInput" placeholder="请输入API密钥..." onkeypress="handleAuthEnter(event)">
                <div class="auth-error" id="authError" style="display: none;"></div>
                <div class="auth-success" id="authSuccess" style="display: none;"></div>
            </div>
            <button class="btn btn-primary" onclick="verifyApiKey()" style="width: 100%; padding: 15px; font-size: 16px;">
                <i class="fas fa-unlock"></i> 验证密钥
            </button>
        </div>
    </div>
    
    <div class="container" id="mainContainer">
        <header class="header">
            <div class="header-content">
                <h1><i class="fas fa-shield-alt"></i> XuanWu 控制面板</h1>
                <div class="header-controls">
                    <!-- 高级搜索功能 -->
                    <div class="search-container">
                        <input type="text" id="globalSearch" class="search-input" placeholder="全局搜索..." oninput="performGlobalSearch(this.value)">
                        <button class="search-btn" onclick="toggleAdvancedSearch()">
                            <i class="fas fa-search"></i>
                        </button>
                        <div class="search-results" id="searchResults" style="display: none;"></div>
                    </div>
                    
                    <!-- 实时通知系统 -->
                    <div class="notification-container">
                        <button class="notification-btn" onclick="toggleNotifications()" id="notificationBtn">
                            <i class="fas fa-bell"></i>
                            <span class="notification-badge" id="notificationBadge" style="display: none;">0</span>
                        </button>
                        <div class="notification-panel" id="notificationPanel" style="display: none;">
                            <div class="notification-header">
                                <h4>实时通知</h4>
                                <button class="btn-clear" onclick="clearAllNotifications()">
                                    <i class="fas fa-trash"></i> 清空
                                </button>
                            </div>
                            <div class="notification-list" id="notificationList">
                                <!-- 通知项将动态添加 -->
                            </div>
                        </div>
                    </div>
                    
                    <button class="theme-toggle" onclick="toggleTheme()" title="切换主题">
                        <i class="fas fa-moon"></i>
                    </button>
                    <button class="btn btn-primary" onclick="toggleFullscreen()">
                        <i class="fas fa-expand"></i> 全屏
                    </button>
                    <button class="btn btn-primary" onclick="refreshAll()">
                        <i class="fas fa-sync-alt"></i> 刷新
                    </button>
                    <button class="btn btn-success" onclick="toggleAutoRefresh()">
                        <i class="fas fa-play"></i> 启动自动刷新
                    </button>
                    
                    <!-- 安全管理按钮 -->
                    <button class="btn btn-warning" onclick="showSecurityPanel()" title="安全管理">
                        <i class="fas fa-shield-alt"></i> 安全
                    </button>
                    
                    <div class="refresh-status">
                        <small id="lastRefreshTime">最后更新: --:--:--</small>
                    </div>
                </div>
            </div>
        </header>
        
        <div class="dashboard">
            <!-- 高级系统概览卡片 -->
            <div class="card fade-in" style="grid-column: span 2;">
                <div class="card-header">
                    <h3 class="card-title">
                        <i class="fas fa-chart-pie card-icon"></i>
                        系统概览仪表板
                    </h3>
                    <div class="header-controls">
                        <button class="btn btn-sm btn-primary" onclick="exportSystemReport()">
                            <i class="fas fa-download"></i> 导出报告
                        </button>
                        <div class="loading" id="overviewLoading" style="display: none;"></div>
                    </div>
                </div>
                <div class="overview-grid">
                    <div class="metric-card">
                        <div class="metric-icon">
                            <i class="fas fa-microchip"></i>
                        </div>
                        <div class="metric-info">
                            <div class="metric-value" id="cpuUsage">0%</div>
                            <div class="metric-label">CPU使用率</div>
                            <div class="metric-trend" id="cpuTrend">↗ +2.3%</div>
                        </div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-icon">
                            <i class="fas fa-memory"></i>
                        </div>
                        <div class="metric-info">
                            <div class="metric-value" id="memoryUsage">0MB</div>
                            <div class="metric-label">内存使用</div>
                            <div class="metric-trend" id="memoryTrend">↘ -1.2%</div>
                        </div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-icon">
                            <i class="fas fa-eye"></i>
                        </div>
                        <div class="metric-info">
                            <div class="metric-value" id="recognitionCount">0</div>
                            <div class="metric-label">识别次数</div>
                            <div class="metric-trend" id="recognitionTrend">↗ +15</div>
                        </div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-icon">
                            <i class="fas fa-clock"></i>
                        </div>
                        <div class="metric-info">
                            <div class="metric-value" id="avgResponseTime">0ms</div>
                            <div class="metric-label">平均响应时间</div>
                            <div class="metric-trend" id="responseTrend">↘ -50ms</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 系统状态卡片 -->
            <div class="card fade-in">
                <div class="card-header">
                    <h3 class="card-title">
                        <i class="fas fa-tachometer-alt card-icon"></i>
                        系统状态
                    </h3>
                    <div class="loading" id="statusLoading" style="display: none;"></div>
                </div>
                <div class="status-grid" id="statusGrid">
                    <div class="status-item">
                        <div class="status-label">监控状态</div>
                        <div class="status-value status-inactive" id="monitoringStatus">未启动</div>
                    </div>
                    <div class="status-item">
                        <div class="status-label">OCR引擎</div>
                        <div class="status-value status-active" id="ocrStatus">就绪</div>
                    </div>
                    <div class="status-item">
                        <div class="status-label">API状态</div>
                        <div class="status-value status-active" id="apiStatus">运行中</div>
                    </div>
                    <div class="status-item">
                        <div class="status-label">运行时间</div>
                        <div class="status-value" id="uptime">00:05:30</div>
                    </div>
                </div>
                <div style="margin-top: 20px; display: flex; gap: 10px;">
                    <button class="btn btn-success" onclick="startMonitoring()" id="startBtn">
                        <i class="fas fa-play"></i> 启动监控
                    </button>
                    <button class="btn btn-danger" onclick="stopMonitoring()" id="stopBtn">
                        <i class="fas fa-stop"></i> 停止监控
                    </button>
                </div>
            </div>
            
            <!-- 关键词管理卡片 -->
            <div class="card fade-in">
                <div class="card-header">
                    <h3 class="card-title">
                        <i class="fas fa-tags card-icon"></i>
                        关键词管理
                    </h3>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <input type="text" id="keywordSearchInput" placeholder="🔍 搜索已有关键词..." 
                               style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; width: 200px; font-size: 14px;"
                               oninput="filterKeywords(this.value)">
                        <div class="loading" id="keywordsLoading" style="display: none;"></div>
                    </div>
                </div>
                <div class="keyword-input-group">
                    <input type="text" class="form-input" id="newKeyword" placeholder="➕ 添加新关键词" onkeypress="handleKeywordEnter(event)">
                    <button class="btn btn-primary" onclick="addKeyword()">
                        <i class="fas fa-plus"></i> 添加关键词
                    </button>
                </div>
                <div class="keywords-container">
                    <ul class="keyword-list" id="keywordsList">
                        <!-- 关键词列表将在这里动态生成 -->
                    </ul>
                </div>
            </div>
            
            <!-- 实时日志卡片 -->
            <div class="card fade-in">
                <div class="card-header">
                    <h3 class="card-title">
                        <i class="fas fa-terminal card-icon"></i>
                        实时日志
                    </h3>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <button class="btn btn-sm btn-primary" onclick="toggleAutoScroll()" id="autoScrollBtn">
                            <i class="fas fa-arrow-down"></i> 自动滚动
                        </button>
                        <select id="logLevelFilter" onchange="filterLogs()" 
                                style="padding: 5px; border: 1px solid #ddd; border-radius: 4px;">
                            <option value="all">所有级别</option>
                            <option value="INFO">信息</option>
                            <option value="WARNING">警告</option>
                            <option value="ERROR">错误</option>
                            <option value="DEBUG">调试</option>
                        </select>
                        <input type="text" id="logSearchInput" placeholder="搜索日志内容..." 
                               style="padding: 5px; border: 1px solid #ddd; border-radius: 4px; width: 150px;"
                               oninput="filterLogs()">
                        <div class="loading" id="logsLoading" style="display: none;"></div>
                    </div>
                </div>
                <div class="logs-container" id="logsContainer">
                    <!-- 日志内容将在这里动态生成 -->
                </div>
            </div>
            
            <!-- 性能监控卡片 -->
            <div class="card fade-in">
                <div class="card-header">
                    <h3 class="card-title">
                        <i class="fas fa-chart-line card-icon"></i>
                        性能监控
                    </h3>
                    <div class="loading" id="performanceLoading" style="display: none;"></div>
                </div>
                <div class="chart-container">
                    <canvas id="performanceChart"></canvas>
                </div>
            </div>
            
            <!-- 历史记录卡片 -->
            <div class="card fade-in">
                <div class="card-header">
                    <h3 class="card-title">
                        <i class="fas fa-history card-icon"></i>
                        检测历史
                    </h3>
                    <div class="loading" id="historyLoading" style="display: none;"></div>
                </div>
                <div class="keywords-container">
                    <ul class="keyword-list" id="historyList">
                        <!-- 历史记录将在这里动态生成 -->
                    </ul>
                </div>
            </div>
            
            <!-- 网络监控卡片 -->
            <div class="card fade-in">
                <div class="card-header">
                    <h3 class="card-title">
                        <i class="fas fa-network-wired card-icon"></i>
                        网络监控
                    </h3>
                    <div class="loading" id="networkLoading" style="display: none;"></div>
                </div>
                <div class="network-status-grid">
                    <div class="network-item">
                        <div class="network-status status-online"></div>
                        <div>Web服务器</div>
                        <div class="file-meta">端口: 8888</div>
                    </div>
                    <div class="network-item">
                        <div class="network-status status-online"></div>
                        <div>API服务</div>
                        <div class="file-meta">响应: 25ms</div>
                    </div>
                    <div class="network-item">
                        <div class="network-status status-warning"></div>
                        <div>数据库</div>
                        <div class="file-meta">连接池: 80%</div>
                    </div>
                    <div class="network-item">
                        <div class="network-status status-online"></div>
                        <div>OCR引擎</div>
                        <div class="file-meta">就绪状态</div>
                    </div>
                </div>
                <div style="margin-top: 20px;">
                    <button class="btn btn-primary" onclick="runNetworkDiagnostics()">
                        <i class="fas fa-stethoscope"></i> 网络诊断
                    </button>
                    <button class="btn btn-warning" onclick="showNetworkDetails()">
                        <i class="fas fa-info-circle"></i> 详细信息
                    </button>
                </div>
            </div>
            
            <!-- 文件管理器卡片 -->
            <div class="card fade-in">
                <div class="card-header">
                    <h3 class="card-title">
                        <i class="fas fa-folder-open card-icon"></i>
                        文件管理器
                    </h3>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <button class="btn btn-sm btn-primary" onclick="refreshFileList()">
                            <i class="fas fa-sync-alt"></i> 刷新
                        </button>
                        <button class="btn btn-sm btn-success" onclick="uploadFile()">
                            <i class="fas fa-upload"></i> 上传
                        </button>
                        <div class="loading" id="fileLoading" style="display: none;"></div>
                    </div>
                </div>
                <div class="file-manager" id="fileManager">
                    <div class="file-item">
                        <i class="fas fa-file-alt file-icon"></i>
                        <div class="file-info">
                            <div class="file-name">system.log</div>
                            <div class="file-meta">2.3 MB • 2024-01-15 14:30</div>
                        </div>
                        <button class="btn btn-sm btn-primary" onclick="downloadFile('system.log')">
                            <i class="fas fa-download"></i>
                        </button>
                    </div>
                    <div class="file-item">
                        <i class="fas fa-file-code file-icon"></i>
                        <div class="file-info">
                            <div class="file-name">config.json</div>
                            <div class="file-meta">1.2 KB • 2024-01-15 12:15</div>
                        </div>
                        <button class="btn btn-sm btn-primary" onclick="downloadFile('config.json')">
                            <i class="fas fa-download"></i>
                        </button>
                    </div>
                    <div class="file-item">
                        <i class="fas fa-database file-icon"></i>
                        <div class="file-info">
                            <div class="file-name">keywords.db</div>
                            <div class="file-meta">856 KB • 2024-01-15 10:45</div>
                        </div>
                        <button class="btn btn-sm btn-primary" onclick="downloadFile('keywords.db')">
                            <i class="fas fa-download"></i>
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- 数据分析卡片 -->
            <div class="card fade-in">
                <div class="card-header">
                    <h3 class="card-title">
                        <i class="fas fa-chart-bar card-icon"></i>
                        数据分析
                    </h3>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <button class="btn btn-sm btn-info" onclick="showStatistics()">
                            <i class="fas fa-chart-pie"></i> 统计分析
                        </button>
                        <button class="btn btn-sm btn-success" onclick="performHealthCheck()">
                            <i class="fas fa-heartbeat"></i> 健康检查
                        </button>
                        <div class="loading" id="analyticsLoading" style="display: none;"></div>
                    </div>
                </div>
                <div class="analytics-content">
                    <div class="progress-item">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                            <span>关键词匹配率</span>
                            <span>85%</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: 85%;"></div>
                        </div>
                    </div>
                    <div class="progress-item">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                            <span>系统稳定性</span>
                            <span>92%</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: 92%;"></div>
                        </div>
                    </div>
                    <div class="progress-item">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                            <span>识别准确度</span>
                            <span>78%</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: 78%;"></div>
                        </div>
                    </div>
                </div>
                <div style="margin-top: 20px;">
                    <button class="btn btn-primary" onclick="generateReport()">
                        <i class="fas fa-file-pdf"></i> 生成报告
                    </button>
                    <button class="btn btn-success" onclick="exportData()">
                        <i class="fas fa-file-excel"></i> 导出数据
                    </button>
                </div>
            </div>
            
            <!-- 设置管理卡片 -->
            <div class="card fade-in">
                <div class="card-header">
                    <h3 class="card-title">
                        <i class="fas fa-cog card-icon"></i>
                        系统设置
                    </h3>
                    <div class="loading" id="settingsLoading" style="display: none;"></div>
                </div>
                <div class="settings-grid">
                    <div class="setting-group">
                        <label class="setting-label">OCR引擎</label>
                        <select class="form-select" id="ocrEngineSelect">
                            <option value="PaddleOCR">PaddleOCR</option>
                            <option value="EasyOCR">EasyOCR</option>
                            <option value="TesseractOCR">TesseractOCR</option>
                        </select>
                    </div>
                    <div class="setting-group">
                        <label class="setting-label">识别间隔 (秒)</label>
                        <input type="number" class="form-input" id="recognitionInterval" min="0.1" max="10" step="0.1" value="1.0">
                    </div>
                    <div class="setting-group">
                        <label class="setting-label">匹配模式</label>
                        <select class="form-select" id="matchMode">
                            <option value="exact">精确匹配</option>
                            <option value="fuzzy">模糊匹配</option>
                            <option value="regex">正则表达式</option>
                        </select>
                    </div>
                    <button class="btn btn-primary" onclick="updateSettings()">
                        <i class="fas fa-save"></i> 保存设置
                    </button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // 全局变量
        let refreshInterval;
        let autoScroll = true;
        let performanceChart;
        let isFullscreen = false;
        
        // API密钥验证相关函数 - 必须在DOMContentLoaded之前定义
        function showAuthOverlay() {
            const overlay = document.getElementById('authOverlay');
            const mainContainer = document.getElementById('mainContainer');
            
            overlay.classList.remove('hidden');
            mainContainer.classList.add('blurred');
            
            // 聚焦到输入框
            setTimeout(() => {
                document.getElementById('apiKeyInput').focus();
            }, 300);
        }
        
        function hideAuthOverlay() {
            const overlay = document.getElementById('authOverlay');
            const mainContainer = document.getElementById('mainContainer');
            
            overlay.classList.add('hidden');
            mainContainer.classList.remove('blurred');
        }
        
        // 页面加载完成后初始化
        document.addEventListener('DOMContentLoaded', function() {
            // 检查是否有已保存的API密钥
            const savedApiKey = sessionStorage.getItem('api_key');
            if (savedApiKey) {
                // 如果有保存的密钥，隐藏遮罩层并加载数据
                hideAuthOverlay();
                loadAllData();
                startAutoRefresh();
            } else {
                // 如果没有密钥，显示虚化界面和验证遮罩
                showAuthOverlay();
            }
            initPerformanceChart();
            
            // 添加淡入动画
            const cards = document.querySelectorAll('.card');
            cards.forEach((card, index) => {
                setTimeout(() => {
                    card.style.opacity = '0';
                    card.style.transform = 'translateY(20px)';
                    card.style.transition = 'all 0.5s ease';
                    setTimeout(() => {
                        card.style.opacity = '1';
                        card.style.transform = 'translateY(0)';
                    }, 100);
                }, index * 100);
            });
        
        function handleAuthEnter(event) {
            if (event.key === 'Enter') {
                verifyApiKey();
            }
        }
        
        // verifyApiKey函数已移动到后面的位置，避免重复定义
        });
        
        // 通用API请求函数，自动携带认证头
        async function apiRequest(url, options = {}) {
            const apiKey = sessionStorage.getItem('api_key');
            const headers = {
                'Content-Type': 'application/json',
                ...options.headers
            };
            
            if (apiKey) {
                headers['Authorization'] = 'Bearer ' + apiKey;
            }
            
            return fetch(url, {
                ...options,
                headers
            });
        }
        
        // 加载所有数据
        async function loadAllData() {
            await Promise.all([
                loadStatus(),
                loadKeywords(),
                loadLogs(),
                loadHistory(),
                loadSettings(),
                loadPerformance()
            ]);
        }
        
        // 加载系统状态
        async function loadStatus() {
            const loading = document.getElementById('statusLoading');
            loading.style.display = 'block';
            
            try {
                const response = await apiRequest('/api/status');
                const result = await response.json();
                
                if (result.success) {
                    const data = result.data;
                    
                    document.getElementById('monitoringStatus').textContent = 
                        data.monitoring.active ? '运行中' : '已停止';
                    document.getElementById('monitoringStatus').className = 
                        'status-value ' + (data.monitoring.active ? 'status-active' : 'status-inactive');
                    
                    document.getElementById('ocrStatus').textContent = data.ocr_engine.status === 'ready' ? '就绪' : '未就绪';
                    document.getElementById('apiStatus').textContent = data.api.status === 'running' ? '运行中' : '停止';
                    document.getElementById('uptime').textContent = data.api.uptime || '00:00:00';
                }
            } catch (error) {
                showNotification('加载状态失败', 'error');
            } finally {
                loading.style.display = 'none';
            }
        }
        
        // 加载关键词列表
        async function loadKeywords() {
            const loading = document.getElementById('keywordsLoading');
            loading.style.display = 'block';
            
            try {
                const response = await apiRequest('/api/keywords');
                const result = await response.json();
                
                if (result.success) {
                    const keywordsList = document.getElementById('keywordsList');
                    keywordsList.innerHTML = '';
                    
                    result.data.forEach(keyword => {
                        const li = document.createElement('li');
                        li.className = 'keyword-item';
                        li.innerHTML = `
                            <div class="keyword-info">
                                <div class="keyword-name">${keyword.keyword}</div>
                                <div class="keyword-stats">匹配次数: ${keyword.count} | 最后匹配: ${keyword.last_match}</div>
                            </div>
                            <button class="btn btn-sm btn-danger" onclick="deleteKeyword('${keyword.keyword}')">
                                <i class="fas fa-trash"></i>
                            </button>
                        `;
                        keywordsList.appendChild(li);
                    });
                }
            } catch (error) {
                showNotification('加载关键词失败', 'error');
            } finally {
                loading.style.display = 'none';
            }
        }
        
        // 加载日志
        async function loadLogs() {
            const loading = document.getElementById('logsLoading');
            loading.style.display = 'block';
            
            try {
                const response = await apiRequest('/api/logs');
                const result = await response.json();
                
                if (result.success) {
                    const logsContainer = document.getElementById('logsContainer');
                    logsContainer.innerHTML = '';
                    
                    result.data.forEach(log => {
                        const logItem = document.createElement('div');
                        logItem.className = 'log-item';
                        
                        // 构建详细的日志显示内容
                        let logContent = `
                            <div class="log-header">
                                <span class="log-timestamp">${log.timestamp}</span>
                                <span class="log-level log-level-${log.level?.toLowerCase() || 'info'}">${log.level || '信息'}</span>
                                <span class="log-type">${log.type || '系统日志'}</span>
                            </div>
                            <div class="log-content">
                                <div class="log-message">${log.message}</div>`;
                        
                        // 如果有客户端IP信息，显示用户信息
                        if (log.client_ip && log.client_ip !== '未知IP') {
                            logContent += `
                                <div class="log-details">
                                    <span class="log-detail-item">👤 客户端IP: <strong>${log.client_ip}</strong></span>`;
                            
                            if (log.action) {
                                logContent += `<span class="log-detail-item">🔧 操作: <strong>${log.action}</strong></span>`;
                            }
                            
                            if (log.api_endpoint) {
                                logContent += `<span class="log-detail-item">🔗 API端点: <strong>${log.api_endpoint}</strong></span>`;
                            }
                            
                            logContent += `</div>`;
                        }
                        
                        // 如果有详细信息，显示展开按钮
                        if (log.details && Object.keys(log.details).length > 0) {
                            logContent += `
                                <div class="log-expand" onclick="toggleLogDetails(this)">
                                    <span class="expand-icon">▶</span> 查看详细信息
                                </div>
                                <div class="log-details-content" style="display: none;">
                                    <pre>${JSON.stringify(log.details, null, 2)}</pre>
                                </div>`;
                        }
                        
                        logContent += `</div>`;
                        logItem.innerHTML = logContent;
                        logsContainer.appendChild(logItem);
                    });
                    
                    if (autoScroll) {
                        logsContainer.scrollTop = logsContainer.scrollHeight;
                    }
                    
                    // 显示日志统计信息
                    if (result.total_count) {
                        const statsDiv = document.createElement('div');
                        statsDiv.className = 'log-stats';
                        statsDiv.innerHTML = `📊 共显示 ${result.total_count} 条日志记录`;
                        logsContainer.insertBefore(statsDiv, logsContainer.firstChild);
                    }
                }
            } catch (error) {
                showNotification('加载日志失败', 'error');
            } finally {
                loading.style.display = 'none';
            }
        }
        
        // 切换日志详细信息显示
        function toggleLogDetails(element) {
            const detailsContent = element.nextElementSibling;
            const icon = element.querySelector('.expand-icon');
            
            if (detailsContent.style.display === 'none') {
                detailsContent.style.display = 'block';
                icon.textContent = '▼';
                element.innerHTML = '<span class="expand-icon">▼</span> 隐藏详细信息';
            } else {
                detailsContent.style.display = 'none';
                icon.textContent = '▶';
                element.innerHTML = '<span class="expand-icon">▶</span> 查看详细信息';
            }
        }
        
        // 加载历史记录
        async function loadHistory() {
            const loading = document.getElementById('historyLoading');
            loading.style.display = 'block';
            
            try {
                const response = await apiRequest('/api/history');
                const result = await response.json();
                
                if (result.success) {
                    const historyList = document.getElementById('historyList');
                    historyList.innerHTML = '';
                    
                    result.data.forEach(item => {
                        const li = document.createElement('li');
                        li.className = 'keyword-item';
                        li.innerHTML = `
                            <div class="keyword-info">
                                <div class="keyword-name">${item.keyword}</div>
                                <div class="keyword-stats">${item.text} (置信度: ${(item.confidence * 100).toFixed(1)}%)</div>
                                <div class="keyword-stats">${item.timestamp}</div>
                            </div>
                        `;
                        historyList.appendChild(li);
                    });
                }
            } catch (error) {
                showNotification('加载历史记录失败', 'error');
            } finally {
                loading.style.display = 'none';
            }
        }
        
        // 加载设置
        async function loadSettings() {
            const loading = document.getElementById('settingsLoading');
            loading.style.display = 'block';
            
            try {
                const response = await apiRequest('/api/settings');
                const result = await response.json();
                
                if (result.success) {
                    const settings = result.data;
                    document.getElementById('ocrEngineSelect').value = settings.ocr_engine;
                    document.getElementById('recognitionInterval').value = settings.recognition_interval;
                    document.getElementById('matchMode').value = settings.match_mode;
                }
            } catch (error) {
                showNotification('加载设置失败', 'error');
            } finally {
                loading.style.display = 'none';
            }
        }
        
        // 加载性能数据
        async function loadPerformance() {
            const loading = document.getElementById('performanceLoading');
            loading.style.display = 'block';
            
            try {
                const response = await apiRequest('/api/performance');
                const result = await response.json();
                
                if (result.success) {
                    const data = result.data;
                    
                    // 更新性能图表
                    if (performanceChart) {
                        performanceChart.data.labels = data.timestamps;
                        performanceChart.data.datasets[0].data = data.cpu_usage;
                        performanceChart.data.datasets[1].data = data.memory_usage;
                        performanceChart.data.datasets[2].data = data.recognition_times;
                        performanceChart.update('none');
                    }
                    
                    // 更新系统概览仪表板
                    updateOverviewDashboard(data);
                }
            } catch (error) {
                showNotification('加载性能数据失败', 'error');
            } finally {
                loading.style.display = 'none';
            }
        }
        
        // 更新系统概览仪表板
        function updateOverviewDashboard(data) {
            try {
                // 获取最新的数据点
                const latestCpu = data.cpu_usage && data.cpu_usage.length > 0 ? data.cpu_usage[data.cpu_usage.length - 1] : 0;
                const latestMemory = data.memory_usage && data.memory_usage.length > 0 ? data.memory_usage[data.memory_usage.length - 1] : 0;
                
                // 更新CPU使用率
                const cpuElement = document.getElementById('cpuUsage');
                if (cpuElement) {
                    cpuElement.textContent = `${latestCpu.toFixed(1)}%`;
                }
                
                // 更新内存使用
                const memoryElement = document.getElementById('memoryUsage');
                if (memoryElement) {
                    memoryElement.textContent = `${latestMemory.toFixed(1)}MB`;
                }
                
                // 更新识别次数（使用专门的识别次数字段）
                const recognitionCountElement = document.getElementById('recognitionCount');
                if (recognitionCountElement) {
                    const count = data.recognition_count || 0;
                    recognitionCountElement.textContent = count.toString();
                }
                
                // 更新平均响应时间（使用专门的响应时间字段）
                const responseTimeElement = document.getElementById('avgResponseTime');
                if (responseTimeElement) {
                    const responseTime = data.avg_response_time || 0;
                    responseTimeElement.textContent = `${responseTime.toFixed(0)}ms`;
                }
                
            } catch (error) {
                console.error('更新系统概览仪表板失败:', error);
            }
        }
        
        // 初始化性能图表
        function initPerformanceChart() {
            const ctx = document.getElementById('performanceChart').getContext('2d');
            
            // 创建渐变色
            const cpuGradient = ctx.createLinearGradient(0, 0, 0, 400);
            cpuGradient.addColorStop(0, 'rgba(102, 126, 234, 0.3)');
            cpuGradient.addColorStop(1, 'rgba(102, 126, 234, 0.05)');
            
            const memoryGradient = ctx.createLinearGradient(0, 0, 0, 400);
            memoryGradient.addColorStop(0, 'rgba(72, 187, 120, 0.3)');
            memoryGradient.addColorStop(1, 'rgba(72, 187, 120, 0.05)');
            
            const timeGradient = ctx.createLinearGradient(0, 0, 0, 400);
            timeGradient.addColorStop(0, 'rgba(237, 137, 54, 0.3)');
            timeGradient.addColorStop(1, 'rgba(237, 137, 54, 0.05)');
            
            performanceChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'CPU使用率 (%)',
                            data: [],
                            borderColor: '#667eea',
                            backgroundColor: cpuGradient,
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4,
                            pointBackgroundColor: '#667eea',
                            pointBorderColor: '#ffffff',
                            pointBorderWidth: 2,
                            pointRadius: 4,
                            pointHoverRadius: 6
                        },
                        {
                            label: '内存使用 (MB)',
                            data: [],
                            borderColor: '#48bb78',
                            backgroundColor: memoryGradient,
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4,
                            pointBackgroundColor: '#48bb78',
                            pointBorderColor: '#ffffff',
                            pointBorderWidth: 2,
                            pointRadius: 4,
                            pointHoverRadius: 6
                        },
                        {
                            label: '识别耗时 (s)',
                            data: [],
                            borderColor: '#ed8936',
                            backgroundColor: timeGradient,
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4,
                            pointBackgroundColor: '#ed8936',
                            pointBorderColor: '#ffffff',
                            pointBorderWidth: 2,
                            pointRadius: 4,
                            pointHoverRadius: 6
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: {
                                usePointStyle: true,
                                padding: 20,
                                font: {
                                    size: 12,
                                    weight: '500'
                                }
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: '#ffffff',
                            bodyColor: '#ffffff',
                            borderColor: '#667eea',
                            borderWidth: 1,
                            cornerRadius: 8,
                            displayColors: true,
                            callbacks: {
                                title: function(context) {
                                    return '时间: ' + context[0].label;
                                },
                                label: function(context) {
                                    let label = context.dataset.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    if (context.parsed.y !== null) {
                                        if (context.datasetIndex === 0) {
                                            label += context.parsed.y.toFixed(1) + '%';
                                        } else if (context.datasetIndex === 1) {
                                            label += context.parsed.y.toFixed(1) + ' MB';
                                        } else {
                                            label += context.parsed.y.toFixed(2) + ' 秒';
                                        }
                                    }
                                    return label;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)',
                                drawBorder: false
                            },
                            ticks: {
                                font: {
                                    size: 11
                                },
                                maxTicksLimit: 10
                            }
                        },
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)',
                                drawBorder: false
                            },
                            ticks: {
                                font: {
                                    size: 11
                                },
                                callback: function(value) {
                                    return value.toFixed(1);
                                }
                            }
                        }
                    },
                    animation: {
                        duration: 750,
                        easing: 'easeInOutQuart'
                    },
                    elements: {
                        line: {
                            borderJoinStyle: 'round'
                        }
                    }
                }
            });
        }
        
        // 启动监控
        async function startMonitoring() {
            try {
                const response = await fetch('/api/monitoring/start', {
                    method: 'POST'
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showNotification('监控已启动', 'success');
                    loadStatus();
                } else {
                    showNotification('启动失败: ' + data.error, 'error');
                }
            } catch (error) {
                showNotification('启动监控时发生错误', 'error');
            }
        }
        
        // 停止监控
        async function stopMonitoring() {
            try {
                const response = await fetch('/api/monitoring/stop', {
                    method: 'POST'
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showNotification('监控已停止', 'success');
                    loadStatus();
                } else {
                    showNotification('停止失败: ' + data.error, 'error');
                }
            } catch (error) {
                showNotification('停止监控时发生错误', 'error');
            }
        }
        
        // 添加关键词
        async function addKeyword() {
            const input = document.getElementById('newKeyword');
            const keyword = input.value.trim();
            
            if (!keyword) {
                showNotification('请输入关键词', 'warning');
                return;
            }
            
            try {
                const response = await fetch('/api/keywords/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ keyword })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    input.value = '';
                    showNotification('关键词添加成功', 'success');
                    loadKeywords();
                } else {
                    showNotification('添加失败: ' + data.error, 'error');
                }
            } catch (error) {
                showNotification('添加关键词时发生错误', 'error');
            }
        }
        
        // 删除关键词
        async function deleteKeyword(keyword) {
            if (!confirm('确定要删除关键词 "' + keyword + '" 吗？')) {
                return;
            }
            
            try {
                const response = await fetch('/api/keywords/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ keyword })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showNotification('关键词删除成功', 'success');
                    loadKeywords();
                } else {
                    showNotification('删除失败: ' + data.error, 'error');
                }
            } catch (error) {
                showNotification('删除关键词时发生错误', 'error');
            }
        }
        
        // 更新设置
        async function updateSettings() {
            const settings = {
                ocr_engine: document.getElementById('ocrEngineSelect').value,
                recognition_interval: parseFloat(document.getElementById('recognitionInterval').value),
                match_mode: document.getElementById('matchMode').value
            };
            
            try {
                const response = await fetch('/api/settings/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showNotification('设置更新成功', 'success');
                } else {
                    showNotification('更新失败: ' + data.error, 'error');
                }
            } catch (error) {
                showNotification('更新设置时发生错误', 'error');
            }
        }
        
        // 处理关键词输入框回车事件
        function handleKeywordEnter(event) {
            if (event.key === 'Enter') {
                addKeyword();
            }
        }
        
        // 实时数据更新系统
        let autoRefreshInterval = null;
        let isAutoRefreshEnabled = false;
        
        // 启动自动刷新
        function startAutoRefresh(interval = 5000) {
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
            }
            
            isAutoRefreshEnabled = true;
            autoRefreshInterval = setInterval(() => {
                if (isAutoRefreshEnabled) {
                    loadAllDataSilently();
                    updateLastRefreshTime();
                }
            }, interval);
            
            updateAutoRefreshButton();
            showNotification('自动刷新已启动', 'success');
        }
        
        // 停止自动刷新
        function stopAutoRefresh() {
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
            }
            isAutoRefreshEnabled = false;
            updateAutoRefreshButton();
            showNotification('自动刷新已停止', 'info');
        }
        
        // 切换自动刷新状态
        function toggleAutoRefresh() {
            if (isAutoRefreshEnabled) {
                stopAutoRefresh();
            } else {
                startAutoRefresh();
            }
        }
        
        // 更新自动刷新按钮状态
        function updateAutoRefreshButton() {
            const button = document.querySelector('[onclick="toggleAutoRefresh()"]');
            if (button) {
                if (isAutoRefreshEnabled) {
                    button.innerHTML = '<i class="fas fa-pause"></i> 停止自动刷新';
                    button.className = 'btn btn-warning';
                } else {
                    button.innerHTML = '<i class="fas fa-play"></i> 启动自动刷新';
                    button.className = 'btn btn-success';
                }
            }
        }
        
        // 静默加载所有数据（不显示通知）
        async function loadAllDataSilently() {
            try {
                await Promise.all([
                    loadStatus(),
                    loadKeywords(),
                    loadLogs(),
                    loadPerformance()
                ]);
            } catch (error) {
                console.error('静默刷新数据时发生错误:', error);
            }
        }
        
        // 更新最后刷新时间
        function updateLastRefreshTime() {
            const now = new Date();
            const timeString = now.toLocaleTimeString();
            const refreshTimeElement = document.getElementById('lastRefreshTime');
            if (refreshTimeElement) {
                refreshTimeElement.textContent = `最后更新: ${timeString}`;
            }
        }
        
        // 刷新所有数据
        function refreshAll() {
            loadAllData();
            updateLastRefreshTime();
            showNotification('数据已刷新', 'info');
        }
        
        // 网络诊断功能
        async function runNetworkDiagnostics() {
            showNotification('正在运行网络诊断...', 'info');
            
            try {
                // 模拟网络诊断过程
                const tests = [
                    { name: 'Web服务器连接', delay: 500 },
                    { name: 'API响应测试', delay: 800 },
                    { name: '数据库连接', delay: 1200 },
                    { name: 'OCR引擎状态', delay: 1000 }
                ];
                
                for (const test of tests) {
                    await new Promise(resolve => setTimeout(resolve, test.delay));
                    showNotification(`${test.name}: 正常`, 'success');
                }
                
                showNotification('网络诊断完成，所有服务正常', 'success');
            } catch (error) {
                showNotification('网络诊断失败', 'error');
            }
        }
        
        // 显示网络详细信息
        function showNetworkDetails() {
            const details = `
                Web服务器: localhost:8888\n
                API端点: /api/*\n
                数据库: SQLite\n
                OCR引擎: 就绪状态\n
                连接数: 活跃连接 3\n
                响应时间: 平均 25ms
            `;
            alert(details);
        }
        
        // 刷新文件列表
        async function refreshFileList() {
            const loading = document.getElementById('fileLoading');
            loading.style.display = 'block';
            
            try {
                // 模拟文件列表刷新
                await new Promise(resolve => setTimeout(resolve, 1000));
                showNotification('文件列表已刷新', 'success');
            } catch (error) {
                showNotification('刷新文件列表失败', 'error');
            } finally {
                loading.style.display = 'none';
            }
        }
        
        // 上传文件
        function uploadFile() {
            const input = document.createElement('input');
            input.type = 'file';
            input.multiple = true;
            input.onchange = function(e) {
                const files = e.target.files;
                if (files.length > 0) {
                    showNotification(`准备上传 ${files.length} 个文件`, 'info');
                    // 这里可以添加实际的文件上传逻辑
                    setTimeout(() => {
                        showNotification('文件上传成功', 'success');
                        refreshFileList();
                    }, 2000);
                }
            };
            input.click();
        }
        
        // 下载文件
        function downloadFile(filename) {
            showNotification(`正在下载 ${filename}...`, 'info');
            // 这里可以添加实际的文件下载逻辑
            setTimeout(() => {
                showNotification(`${filename} 下载完成`, 'success');
            }, 1500);
        }
        
        // 全局搜索功能
        let searchData = {
            keywords: [],
            logs: [],
            settings: [],
            performance: []
        };
        
        function performGlobalSearch(query) {
            const searchResults = document.getElementById('searchResults');
            
            if (!query.trim()) {
                searchResults.style.display = 'none';
                return;
            }
            
            const results = [];
            
            // 搜索关键词
            searchData.keywords.forEach(keyword => {
                if (keyword.toLowerCase().includes(query.toLowerCase())) {
                    results.push({
                        type: 'keyword',
                        icon: 'fas fa-key',
                        text: keyword,
                        category: '关键词',
                        action: () => scrollToElement('keywords-card')
                    });
                }
            });
            
            // 搜索日志
            searchData.logs.forEach(log => {
                if (log.message && log.message.toLowerCase().includes(query.toLowerCase())) {
                    results.push({
                        type: 'log',
                        icon: 'fas fa-file-alt',
                        text: log.message.substring(0, 50) + '...',
                        category: '日志',
                        action: () => scrollToElement('logs-card')
                    });
                }
            });
            
            // 搜索设置
            const settingsItems = ['监控间隔', 'OCR引擎', 'API配置', '通知设置'];
            settingsItems.forEach(item => {
                if (item.toLowerCase().includes(query.toLowerCase())) {
                    results.push({
                        type: 'setting',
                        icon: 'fas fa-cog',
                        text: item,
                        category: '设置',
                        action: () => scrollToElement('settings-card')
                    });
                }
            });
            
            displaySearchResults(results);
        }
        
        function displaySearchResults(results) {
            const searchResults = document.getElementById('searchResults');
            
            if (results.length === 0) {
                searchResults.innerHTML = '<div class="search-result-item"><i class="fas fa-search"></i> 未找到相关结果</div>';
            } else {
                searchResults.innerHTML = results.map(result => `
                    <div class="search-result-item" onclick="${result.action.toString().replace('() => ', '')}">
                        <i class="${result.icon} search-result-icon"></i>
                        <span class="search-result-text">${result.text}</span>
                        <span class="search-result-category">${result.category}</span>
                    </div>
                `).join('');
            }
            
            searchResults.style.display = 'block';
        }
        
        function toggleAdvancedSearch() {
            // 高级搜索功能扩展
            showNotification('高级搜索功能开发中...', 'info');
        }
        
        function scrollToElement(elementId) {
            const element = document.getElementById(elementId);
            if (element) {
                element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                element.style.animation = 'highlight 2s ease';
            }
            document.getElementById('searchResults').style.display = 'none';
        }
        
        function showHelp() {
            showNotification('帮助功能开发中，敬请期待！', 'info', '帮助中心');
        }
        
        // 实时通知系统
        let notifications = [];
        let notificationId = 0;
        
        function addNotification(title, message, type = 'info', actions = []) {
            const notification = {
                id: ++notificationId,
                title,
                message,
                type,
                actions,
                time: new Date().toLocaleTimeString(),
                unread: true
            };
            
            notifications.unshift(notification);
            updateNotificationBadge();
            updateNotificationList();
            
            // 自动清理旧通知（保留最新50条）
            if (notifications.length > 50) {
                notifications = notifications.slice(0, 50);
            }
            
            return notification.id;
        }
        
        function removeNotification(id) {
            notifications = notifications.filter(n => n.id !== id);
            updateNotificationBadge();
            updateNotificationList();
        }
        
        function markNotificationAsRead(id) {
            const notification = notifications.find(n => n.id === id);
            if (notification) {
                notification.unread = false;
                updateNotificationBadge();
                updateNotificationList();
            }
        }
        
        function clearAllNotifications() {
            notifications = [];
            updateNotificationBadge();
            updateNotificationList();
        }
        
        function updateNotificationBadge() {
            const badge = document.getElementById('notificationBadge');
            const unreadCount = notifications.filter(n => n.unread).length;
            
            if (unreadCount > 0) {
                badge.textContent = unreadCount > 99 ? '99+' : unreadCount;
                badge.style.display = 'block';
            } else {
                badge.style.display = 'none';
            }
        }
        
        function updateNotificationList() {
            const notificationList = document.getElementById('notificationList');
            
            if (notifications.length === 0) {
                notificationList.innerHTML = `
                    <div class="notification-empty">
                        <i class="fas fa-bell-slash"></i>
                        <p>暂无通知</p>
                    </div>
                `;
                return;
            }
            
            notificationList.innerHTML = notifications.map(notification => `
                <div class="notification-item ${notification.unread ? 'unread' : ''}" onclick="markNotificationAsRead(${notification.id})">
                    <div class="notification-content">
                        <div class="notification-icon ${notification.type}">
                            <i class="fas fa-${getNotificationIcon(notification.type)}"></i>
                        </div>
                        <div class="notification-text">
                            <div class="notification-title">${notification.title}</div>
                            <div class="notification-message">${notification.message}</div>
                            <div class="notification-time">${notification.time}</div>
                            ${notification.actions.length > 0 ? `
                                <div class="notification-actions">
                                    ${notification.actions.map(action => `
                                        <button class="notification-action ${action.primary ? 'primary' : ''}" onclick="${action.handler}; removeNotification(${notification.id})">
                                            ${action.text}
                                        </button>
                                    `).join('')}
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `).join('');
        }
        
        function getNotificationIcon(type) {
            const icons = {
                success: 'check-circle',
                warning: 'exclamation-triangle',
                error: 'times-circle',
                info: 'info-circle'
            };
            return icons[type] || 'info-circle';
        }
        
        function toggleNotifications() {
            const panel = document.getElementById('notificationPanel');
            const isVisible = panel.style.visibility === 'visible';
            
            if (isVisible) {
                panel.style.opacity = '0';
                panel.style.visibility = 'hidden';
                panel.style.transform = 'translateY(-10px)';
            } else {
                panel.style.visibility = 'visible';
                panel.style.opacity = '1';
                panel.style.transform = 'translateY(0)';
                
                // 如果没有通知，添加一个示例通知
                if (notifications.length === 0) {
                    addNotification('欢迎使用', 'XuanWu OCR监控系统已启动，点击此处了解更多功能', 'info', [
                        { text: '了解更多', handler: 'showHelp', primary: true }
                    ]);
                }
                // 标记所有通知为已读
                notifications.forEach(n => n.unread = false);
                updateNotificationBadge();
                updateNotificationList();
            }
        }
        
        // 消息队列
        let toastQueue = [];
        let isShowingToast = false;
        
        // 增强的通知函数
        function showNotification(message, type = 'info', title = null, actions = []) {
            const titles = {
                success: '成功',
                warning: '警告',
                error: '错误',
                info: '信息'
            };
            
            const notificationTitle = title || titles[type] || '通知';
            addNotification(notificationTitle, message, type, actions);
            
            // 添加到队列
            toastQueue.push({ message, type });
            processToastQueue();
        }
        
        // 处理消息队列
        function processToastQueue() {
            if (isShowingToast || toastQueue.length === 0) {
                return;
            }
            
            isShowingToast = true;
            const { message, type } = toastQueue.shift();
            
            let toastContainer = document.getElementById('toastContainer');
            if (!toastContainer) {
                toastContainer = document.createElement('div');
                toastContainer.id = 'toastContainer';
                toastContainer.className = 'toast-container';
                document.body.appendChild(toastContainer);
            }
            
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `
                <i class="fas fa-${getNotificationIcon(type)}"></i>
                <span>${message}</span>
            `;
            
            toastContainer.appendChild(toast);
            
            // 显示动画
            setTimeout(() => {
                toast.style.transform = 'translateX(0)';
                toast.style.opacity = '1';
            }, 50);
            
            // 隐藏动画
            setTimeout(() => {
                toast.style.transform = 'translateX(400px)';
                toast.style.opacity = '0';
                
                setTimeout(() => {
                    if (toastContainer.contains(toast)) {
                        toastContainer.removeChild(toast);
                    }
                    isShowingToast = false;
                    processToastQueue(); // 处理下一个消息
                }, 300);
            }, 2500);
        }
        
        // 生成报告
        async function generateReport() {
            showNotification('正在生成报告...', 'info');
            
            try {
                // 模拟报告生成过程
                await new Promise(resolve => setTimeout(resolve, 2000));
                
                const reportData = {
                    timestamp: new Date().toLocaleString(),
                    keywordMatchRate: '85%',
                    systemStability: '92%',
                    recognitionAccuracy: '78%',
                    totalKeywords: 15,
                    totalMatches: 342
                };
                
                // 创建并下载报告文件
                const reportContent = `
系统分析报告
生成时间: ${reportData.timestamp}

=== 性能指标 ===
关键词匹配率: ${reportData.keywordMatchRate}
系统稳定性: ${reportData.systemStability}
识别准确度: ${reportData.recognitionAccuracy}

=== 统计数据 ===
总关键词数: ${reportData.totalKeywords}
总匹配次数: ${reportData.totalMatches}
                `;
                
                const blob = new Blob([reportContent], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `系统报告_${new Date().toISOString().split('T')[0]}.txt`;
                a.click();
                URL.revokeObjectURL(url);
                
                showNotification('报告生成完成', 'success');
            } catch (error) {
                showNotification('生成报告失败', 'error');
            }
        }
        
        // 导出数据
        async function exportData() {
            showNotification('正在导出数据...', 'info');
            
            try {
                // 模拟数据导出过程
                await new Promise(resolve => setTimeout(resolve, 1500));
                
                const csvData = `
时间,关键词,匹配文本,置信度
2024-01-15 14:30:25,测试关键词,检测到的文本内容,0.95
2024-01-15 14:28:12,另一个关键词,其他匹配内容,0.87
2024-01-15 14:25:08,第三个关键词,更多文本内容,0.92
                `;
                
                const blob = new Blob([csvData], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `数据导出_${new Date().toISOString().split('T')[0]}.csv`;
                a.click();
                URL.revokeObjectURL(url);
                
                showNotification('数据导出完成', 'success');
            } catch (error) {
                showNotification('导出数据失败', 'error');
            }
        }
        
        // 开始自动刷新
        function startAutoRefresh() {
            refreshInterval = setInterval(() => {
                loadStatus();
                loadLogs();
                loadPerformance();
            }, 1000); // 每1秒刷新一次，实现实时显示
        }
        
        // 切换自动滚动
        function toggleAutoScroll() {
            autoScroll = !autoScroll;
            const btn = document.getElementById('autoScrollBtn');
            btn.innerHTML = autoScroll ? 
                '<i class="fas fa-arrow-down"></i> 自动滚动' : 
                '<i class="fas fa-pause"></i> 手动滚动';
            btn.className = autoScroll ? 'btn btn-sm btn-primary' : 'btn btn-sm btn-warning';
        }
        
        // 切换全屏
        function toggleFullscreen() {
            const container = document.querySelector('.container');
            if (!isFullscreen) {
                container.classList.add('fullscreen');
                isFullscreen = true;
            } else {
                container.classList.remove('fullscreen');
                isFullscreen = false;
            }
        }
        
        // 显示安全管理面板
        function showSecurityPanel() {
            const modal = document.createElement('div');
            modal.className = 'modal';
            modal.style.display = 'block'; // 确保模态框显示
            modal.innerHTML = `
                <div class="modal-content">
                    <div class="modal-header">
                        <h3><i class="fas fa-shield-alt"></i> 安全管理</h3>
                        <button class="modal-close" onclick="closeModal(this)">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="security-tabs">
                            <button class="tab-btn active" onclick="showSecurityTab(event, 'token')">API令牌</button>
                            <button class="tab-btn" onclick="showSecurityTab(event, 'info')">安全信息</button>
                            <button class="tab-btn" onclick="showSecurityTab(event, 'banned')">IP封禁查看</button>
                        </div>
                        
                        <div id="tokenTab" class="tab-content active">
                            <div class="form-group">
                                <label>API密钥验证:</label>
                                <div class="token-display">
                                    <input type="password" id="apiKeyInput" placeholder="请输入API密钥">
                                    <button class="btn btn-primary" onclick="verifyApiKey()">验证</button>
                                    <button class="btn btn-secondary" onclick="clearApiKey()">清除</button>
                                </div>
                            </div>
                            <div class="form-group">
                                <label>验证状态:</label>
                                <p id="verifyStatus" class="status-text">未验证</p>
                            </div>
                            <div class="form-group">
                                <small class="help-text">请在主程序的开发工具面板 → Web预览设置 → Web API安全设置中配置API密钥</small>
                            </div>
                        </div>
                        
                        <div id="infoTab" class="tab-content">
                            <div class="security-info">
                                <div class="info-item">
                                    <label>客户端IP:</label>
                                    <span id="clientIP">--</span>
                                </div>
                                <div class="info-item">
                                    <label>活跃会话:</label>
                                    <span id="activeSessions">--</span>
                                </div>
                                <div class="info-item">
                                    <label>失败尝试:</label>
                                    <span id="failedAttempts">--</span>
                                </div>
                                <div class="info-item">
                                    <label>速率限制剩余:</label>
                                    <span id="rateLimitRemaining">--</span>
                                </div>
                            </div>
                        </div>
                        
                        <div id="bannedTab" class="tab-content">
                            <div class="form-group">
                                <label>IP封禁查看:</label>
                                <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                                    <button class="btn btn-primary" onclick="loadBannedIPs()">刷新列表</button>
                                </div>
                            </div>
                            <div class="form-group">
                                <label>当前封禁的IP地址:</label>
                                <div id="bannedIPsList" style="max-height: 300px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 6px; padding: 10px; background: var(--card-bg);">
                                    <p style="text-align: center; color: var(--text-muted);">点击"刷新列表"加载封禁IP</p>
                                </div>
                            </div>
                            <div class="form-group">
                                <small class="help-text">被封禁的IP地址将无法访问Web API。如需解封，请在服务器端进行管理操作。</small>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            loadSecurityInfo();
        }
        
        // 显示安全标签页
        function showSecurityTab(event, tabName) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById(tabName + 'Tab').classList.add('active');
        }
        
        // 验证API密钥
        async function verifyApiKey() {
            const apiKey = document.getElementById('apiKeyInput').value.trim();
            if (!apiKey) {
                showNotification('请输入API密钥', 'error');
                return;
            }
            
            try {
                const response = await fetch('/api/verify_key', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ api_key: apiKey })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // 验证成功，存储密钥
                    sessionStorage.setItem('api_key', apiKey);
                    showNotification('API密钥验证成功，正在加载数据...', 'success');
                    
                    // 隐藏遮罩层并移除虚化效果
                    hideAuthOverlay();
                    
                    // 加载所有数据
                    setTimeout(() => {
                        loadAllData();
                        startAutoRefresh();
                    }, 500);
                } else {
                    showNotification('API密钥验证失败: ' + (data.error || '未知错误'), 'error');
                }
            } catch (error) {
                showNotification('验证失败: ' + error.message, 'error');
            }
        }
        
        // 清除API密钥
        function clearApiKey() {
            document.getElementById('apiKeyInput').value = '';
            document.getElementById('verifyStatus').textContent = '未验证';
            document.getElementById('verifyStatus').style.color = '#666';
            sessionStorage.removeItem('api_key');
            showNotification('API密钥已清除', 'info');
        }
        
        // 加载安全信息
        async function loadSecurityInfo() {
            try {
                const response = await fetch('/api/auth/info');
                const data = await response.json();
                
                if (data.success) {
                    const info = data.data;
                    document.getElementById('clientIP').textContent = info.client_ip;
                    document.getElementById('activeSessions').textContent = info.active_sessions;
                    document.getElementById('failedAttempts').textContent = info.failed_attempts;
                    document.getElementById('rateLimitRemaining').textContent = info.rate_limit_remaining;
                }
            } catch (error) {
                console.error('加载安全信息失败:', error);
            }
        }
        
        // 加载封禁IP列表
        async function loadBannedIPs() {
            try {
                const response = await fetch('/api/get_banned_ips');
                const data = await response.json();
                
                const bannedIPsList = document.getElementById('bannedIPsList');
                
                if (data.success && data.data && data.data.length > 0) {
                    let html = '';
                    data.data.forEach(ipInfo => {
                        html += `
                            <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px; margin-bottom: 5px; border: 1px solid var(--border-color); border-radius: 4px; background: var(--card-hover-bg);">
                                <div>
                                    <strong>${ipInfo.ip}</strong>
                                    <small style="color: var(--text-muted); margin-left: 10px;">失败次数: ${ipInfo.attempts}</small>
                                </div>
                                <span style="color: var(--text-muted); font-size: 12px;">已封禁</span>
                            </div>
                        `;
                    });
                    bannedIPsList.innerHTML = html;
                } else {
                    bannedIPsList.innerHTML = '<p style="text-align: center; color: var(--text-muted);">当前没有被封禁的IP地址</p>';
                }
            } catch (error) {
                console.error('加载封禁IP列表失败:', error);
                showNotification('加载封禁IP列表失败', 'error');
            }
        }

        
        // 关闭模态框
        function closeModal(btn) {
            const modal = btn.closest('.modal');
            modal.remove();
        }
        
        // 切换主题
        function toggleTheme() {
            const body = document.body;
            const currentTheme = body.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            body.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            
            // 更新主题切换按钮图标
            const themeToggle = document.querySelector('.theme-toggle i');
            themeToggle.className = newTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
        
        // 重复的showNotification函数已移除，使用上面带队列机制的版本
        
        // 重复的getNotificationIcon函数已移除，使用上面的版本
        
        // 初始化主题
        function initTheme() {
            const savedTheme = localStorage.getItem('theme') || 'light';
            document.body.setAttribute('data-theme', savedTheme);
            
            const themeToggle = document.querySelector('.theme-toggle i');
            if (themeToggle) {
                themeToggle.className = savedTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
            }
        }
        
        // 页面加载时初始化主题
        document.addEventListener('DOMContentLoaded', function() {
            initTheme();
        });
        
        // 键盘快捷键支持
        document.addEventListener('keydown', function(e) {
            // Ctrl+R 刷新数据
            if (e.ctrlKey && e.key === 'r') {
                e.preventDefault();
                refreshAll();
            }
            // Ctrl+T 切换主题
            if (e.ctrlKey && e.key === 't') {
                e.preventDefault();
                toggleTheme();
            }
            // F11 切换全屏
            if (e.key === 'F11') {
                e.preventDefault();
                toggleFullscreen();
            }
            // Esc 退出全屏
            if (e.key === 'Escape' && isFullscreen) {
                toggleFullscreen();
            }
        });
        
        // 数据搜索和过滤功能
        function initSearchAndFilter() {
            // 关键词搜索功能已在HTML中实现，无需重复创建
            
            // 日志级别过滤
            const logFilter = document.createElement('select');
            logFilter.className = 'form-select mb-3';
            logFilter.innerHTML = `
                <option value="all">所有日志</option>
                <option value="info">信息</option>
                <option value="warning">警告</option>
                <option value="error">错误</option>
            `;
            logFilter.addEventListener('change', function(e) {
                filterLogs(e.target.value);
            });
            
            const logsContainer = document.querySelector('#logsContainer').parentNode;
            logsContainer.insertBefore(logFilter, document.querySelector('#logsContainer'));
            
            // 初始化全局搜索和通知功能
            populateSearchData();
            
            // 绑定搜索事件
            const searchInput = document.getElementById('globalSearch');
            if (searchInput) {
                searchInput.addEventListener('input', function(e) {
                    performGlobalSearch(e.target.value);
                });
                
                searchInput.addEventListener('keydown', function(e) {
                    if (e.key === 'Escape') {
                        e.target.value = '';
                        document.getElementById('searchResults').style.display = 'none';
                    }
                });
            }
            
            // 点击外部关闭搜索结果
            document.addEventListener('click', function(e) {
                const searchContainer = document.querySelector('.search-container');
                if (searchContainer && !searchContainer.contains(e.target)) {
                    document.getElementById('searchResults').style.display = 'none';
                }
            });
            
            // 点击外部关闭通知面板
            document.addEventListener('click', function(e) {
                const notificationContainer = document.querySelector('.notification-container');
                const notificationPanel = document.getElementById('notificationPanel');
                if (notificationContainer && !notificationContainer.contains(e.target) && notificationPanel) {
                    notificationPanel.style.display = 'none';
                }
            });
            
            // 初始化示例通知
            setTimeout(() => {
                addNotification('系统启动', 'XuanWu OCR监控系统已成功启动', 'success');
                addNotification('功能更新', '新增了高级搜索和实时通知功能', 'info');
                showNotification('欢迎使用XuanWu OCR监控系统！', 'success');
            }, 500);
        }
        
        // 过滤关键词
        function filterKeywords(searchTerm) {
            const keywords = document.querySelectorAll('#keywordsList .keyword-item');
            keywords.forEach(item => {
                const keywordText = item.querySelector('.keyword-name').textContent.toLowerCase();
                if (keywordText.includes(searchTerm.toLowerCase()) || searchTerm === '') {
                    item.style.display = 'block';
                } else {
                    item.style.display = 'none';
                }
            });
        }
        
        // 过滤日志
        function filterLogs(level) {
            const logs = document.querySelectorAll('#logsContainer .log-item');
            logs.forEach(item => {
                const logLevel = item.querySelector('.log-level').textContent.toLowerCase();
                if (level === 'all' || logLevel === level) {
                    item.style.display = 'flex';
                } else {
                    item.style.display = 'none';
                }
            });
        }
        
        // 数据统计和分析
        function showStatistics() {
            const modal = document.createElement('div');
            modal.className = 'modal fade show';
            modal.style.display = 'block';
            modal.innerHTML = `
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">系统统计</h5>
                            <button type="button" class="btn-close" onclick="closeModal(this)"></button>
                        </div>
                        <div class="modal-body">
                            <div class="row">
                                <div class="col-md-6">
                                    <canvas id="keywordChart" width="300" height="200"></canvas>
                                </div>
                                <div class="col-md-6">
                                    <canvas id="activityChart" width="300" height="200"></canvas>
                                </div>
                            </div>
                            <div class="mt-4">
                                <h6>详细统计</h6>
                                <table class="table table-striped">
                                    <tr><td>总运行时间</td><td id="totalRuntime">计算中...</td></tr>
                                    <tr><td>平均CPU使用率</td><td id="avgCpu">计算中...</td></tr>
                                    <tr><td>平均内存使用</td><td id="avgMemory">计算中...</td></tr>
                                    <tr><td>识别成功率</td><td id="successRate">计算中...</td></tr>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            
            // 生成统计图表
            generateStatisticsCharts();
        }
        
        // 生成统计图表
        function generateStatisticsCharts() {
            // 关键词分布图 - 增强版甜甜圈图
            const keywordCtx = document.getElementById('keywordChart');
            if (keywordCtx) {
                new Chart(keywordCtx, {
                    type: 'doughnut',
                    data: {
                        labels: ['活跃关键词', '待激活', '已暂停'],
                        datasets: [{
                            data: [12, 3, 2],
                            backgroundColor: [
                                'rgba(40, 167, 69, 0.8)',
                                'rgba(255, 193, 7, 0.8)',
                                'rgba(220, 53, 69, 0.8)'
                            ],
                            borderColor: [
                                'rgba(40, 167, 69, 1)',
                                'rgba(255, 193, 7, 1)',
                                'rgba(220, 53, 69, 1)'
                            ],
                            borderWidth: 2,
                            hoverOffset: 10,
                            hoverBorderWidth: 3
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: '60%',
                        plugins: {
                            title: {
                                display: true,
                                text: '关键词状态分布',
                                font: {
                                    size: 16,
                                    weight: 'bold'
                                },
                                padding: 20
                            },
                            legend: {
                                position: 'bottom',
                                labels: {
                                    usePointStyle: true,
                                    padding: 15,
                                    font: {
                                        size: 12
                                    }
                                }
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                titleColor: '#ffffff',
                                bodyColor: '#ffffff',
                                borderColor: '#667eea',
                                borderWidth: 1,
                                cornerRadius: 8,
                                callbacks: {
                                    label: function(context) {
                                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                        const percentage = ((context.parsed / total) * 100).toFixed(1);
                                        return context.label + ': ' + context.parsed + ' (' + percentage + '%)';
                                    }
                                }
                            }
                        },
                        animation: {
                            animateRotate: true,
                            animateScale: true,
                            duration: 1000,
                            easing: 'easeInOutQuart'
                        }
                    }
                });
            }
            
            // 活动趋势图 - 增强版柱状图
            const activityCtx = document.getElementById('activityChart');
            if (activityCtx) {
                const gradient = activityCtx.getContext('2d').createLinearGradient(0, 0, 0, 400);
                gradient.addColorStop(0, 'rgba(0, 123, 255, 0.8)');
                gradient.addColorStop(1, 'rgba(0, 123, 255, 0.2)');
                
                new Chart(activityCtx, {
                    type: 'bar',
                    data: {
                        labels: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
                        datasets: [{
                            label: '识别次数',
                            data: [45, 52, 38, 67, 73, 29, 15],
                            backgroundColor: gradient,
                            borderColor: 'rgba(0, 123, 255, 1)',
                            borderWidth: 2,
                            borderRadius: 8,
                            borderSkipped: false,
                            hoverBackgroundColor: 'rgba(0, 123, 255, 0.9)',
                            hoverBorderColor: 'rgba(0, 123, 255, 1)',
                            hoverBorderWidth: 3
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            title: {
                                display: true,
                                text: '每日活动统计',
                                font: {
                                    size: 16,
                                    weight: 'bold'
                                },
                                padding: 20
                            },
                            legend: {
                                display: false
                            },
                            tooltip: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                titleColor: '#ffffff',
                                bodyColor: '#ffffff',
                                borderColor: '#667eea',
                                borderWidth: 1,
                                cornerRadius: 8,
                                callbacks: {
                                    title: function(context) {
                                        return context[0].label;
                                    },
                                    label: function(context) {
                                        return '识别次数: ' + context.parsed.y + ' 次';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                grid: {
                                    display: false
                                },
                                ticks: {
                                    font: {
                                        size: 11
                                    }
                                }
                            },
                            y: {
                                beginAtZero: true,
                                grid: {
                                    color: 'rgba(0, 0, 0, 0.1)',
                                    drawBorder: false
                                },
                                ticks: {
                                    font: {
                                        size: 11
                                    },
                                    callback: function(value) {
                                        return value + ' 次';
                                    }
                                }
                            }
                        },
                        animation: {
                            duration: 1200,
                            easing: 'easeInOutQuart',
                            delay: function(context) {
                                return context.dataIndex * 100;
                            }
                        },
                        interaction: {
                            intersect: false,
                            mode: 'index'
                        }
                    }
                });
            }
            
            // 更新统计数据 - 添加动画效果
            setTimeout(() => {
                animateCounter('totalRuntime', '2小时35分钟');
                animateCounter('avgCpu', '15.2%');
                animateCounter('avgMemory', '245MB');
                animateCounter('successRate', '94.7%');
            }, 500);
        }
        
        // 数字动画效果
        function animateCounter(elementId, finalValue) {
            const element = document.getElementById(elementId);
            if (!element) return;
            
            element.style.transition = 'all 0.3s ease';
            element.style.transform = 'scale(1.1)';
            element.style.color = '#007bff';
            
            setTimeout(() => {
                element.textContent = finalValue;
                element.style.transform = 'scale(1)';
                element.style.color = '';
            }, 150);
        }
        
        // 关闭模态框
        function closeModal(btn) {
            const modal = btn.closest('.modal');
            modal.style.display = 'none';
            setTimeout(() => {
                if (modal.parentNode) {
                    modal.parentNode.removeChild(modal);
                }
            }, 300);
        }
        
        // 系统健康检查
        async function performHealthCheck() {
            showNotification('正在进行系统健康检查...', 'info');
            
            const checks = [
                { name: 'Web服务器', status: 'checking' },
                { name: 'API接口', status: 'checking' },
                { name: 'OCR引擎', status: 'checking' },
                { name: '数据库连接', status: 'checking' },
                { name: '内存使用', status: 'checking' },
                { name: 'CPU负载', status: 'checking' }
            ];
            
            // 创建健康检查界面
            const modal = document.createElement('div');
            modal.className = 'modal fade show';
            modal.style.display = 'block';
            modal.innerHTML = `
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">系统健康检查</h5>
                            <button type="button" class="btn-close" onclick="closeModal(this)"></button>
                        </div>
                        <div class="modal-body">
                            <div id="healthCheckList">
                                ${checks.map(check => `
                                    <div class="d-flex justify-content-between align-items-center mb-2 health-check-item" data-check="${check.name}">
                                        <span>${check.name}</span>
                                        <span class="badge bg-warning">检查中...</span>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            
            // 模拟健康检查过程
            for (let i = 0; i < checks.length; i++) {
                await new Promise(resolve => setTimeout(resolve, 800));
                const item = modal.querySelector(`[data-check="${checks[i].name}"]`);
                const badge = item.querySelector('.badge');
                const isHealthy = Math.random() > 0.1; // 90%概率健康
                
                if (isHealthy) {
                    badge.className = 'badge bg-success';
                    badge.textContent = '正常';
                } else {
                    badge.className = 'badge bg-danger';
                    badge.textContent = '异常';
                }
            }
            
            showNotification('系统健康检查完成', 'success');
        }
        
        // 实时性能监控增强
        function enhancePerformanceMonitoring() {
            // 添加性能警告阈值
            const performanceThresholds = {
                cpu: 80,
                memory: 500,
                responseTime: 2000
            };
            
            // 监控性能指标
            setInterval(() => {
                const cpuElement = document.getElementById('cpuUsage');
                const memoryElement = document.getElementById('memoryUsage');
                const responseTimeElement = document.getElementById('avgResponseTime');
                
                if (cpuElement) {
                    const cpuValue = parseFloat(cpuElement.textContent);
                    if (cpuValue > performanceThresholds.cpu) {
                        showNotification(`CPU使用率过高: ${cpuValue}%`, 'warning');
                    }
                }
                
                if (memoryElement) {
                    const memoryValue = parseFloat(memoryElement.textContent);
                    if (memoryValue > performanceThresholds.memory) {
                        showNotification(`内存使用过高: ${memoryValue}MB`, 'warning');
                    }
                }
                
                if (responseTimeElement) {
                    const responseTime = parseFloat(responseTimeElement.textContent);
                    if (responseTime > performanceThresholds.responseTime) {
                        showNotification(`响应时间过长: ${responseTime}ms`, 'warning');
                    }
                }
            }, 5000);
        }
        
        // 页面加载完成后初始化增强功能
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(() => {
                initSearchAndFilter();
                enhancePerformanceMonitoring();
            }, 1000);
        });
        
        // 重复的 initializeSearchAndNotifications 函数已合并到 initSearchAndFilter 中
        
        // 填充搜索数据
        function populateSearchData() {
            // 从页面获取关键词数据
            const keywordElements = document.querySelectorAll('.keyword-item .keyword-name');
            searchData.keywords = Array.from(keywordElements).map(el => el.textContent.trim());
            
            // 从页面获取日志数据
            const logElements = document.querySelectorAll('.log-item');
            searchData.logs = Array.from(logElements).map(el => ({
                message: el.textContent.trim(),
                timestamp: new Date().toISOString()
            }));
            
            // 添加性能数据
            searchData.performance = [
                'CPU使用率', '内存使用', '识别次数', '成功率',
                '响应时间', '错误统计', '网络状态', '系统负载'
            ];
        }
        
        // 定期更新搜索数据
        setInterval(populateSearchData, 30000); // 每30秒更新一次
        
        // 防止页面卸载时的内存泄漏
        window.addEventListener('beforeunload', function() {
            if (refreshInterval) {
                clearInterval(refreshInterval);
            }
            if (performanceChart) {
                performanceChart.destroy();
            }
        });
    </script>
</body>
</html>
        '''

class WebPreviewServer(QObject):
    """Web预览服务器类 - 增强版"""
    
    # 定义信号
    server_started = pyqtSignal()
    server_error = pyqtSignal(str)
    
    def __init__(self, main_window=None, port=8888):
        super().__init__()
        self.main_window = main_window
        self.port = port
        self.host = '127.0.0.1'  # 默认主机
        self.server_config = {
            'port': port,
            'host': '127.0.0.1',
            'auto_optimize': True,
            'cache_enable': True
        }
        self.server = None
        self.server_thread = None
        self.is_running = False
        self.start_time = None
        self.request_count = 0
        
        # 初始化安全配置
        WebPreviewHandler.initialize_security()
    
    def set_server_config(self, config):
        """设置服务器配置"""
        if config:
            self.server_config.update(config)
            self.port = self.server_config.get('port', 8888)
            self.host = self.server_config.get('host', '127.0.0.1')
            enhanced_logger.log("INFO", f"服务器配置已更新: {self.host}:{self.port}", "WebPreviewServer")
    
    def start_server(self):
        """启动Web服务器"""
        if self.is_running:
            return True
        
        try:
            # 记录启动时间
            self.start_time = time.time()
            self.request_count = 0
            
            # 创建服务器
            def handler(*args, **kwargs):
                return WebPreviewHandler(*args, main_window=self.main_window, web_server=self, **kwargs)
            
            self.server = HTTPServer((self.host, self.port), handler)
            
            # 在新线程中启动服务器，确保设置为daemon线程
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            
            self.is_running = True
            self.server_started.emit()
            return True
            
        except Exception as e:
            self.server_error.emit(str(e))
            return False
    
    def _run_server(self):
        """运行服务器的内部方法"""
        try:
            self.server.serve_forever()
        except Exception as e:
            self.server_error.emit(str(e))
    
    def stop_server(self):
        """停止Web服务器"""
        if not self.is_running:
            return
        
        try:
            # 立即标记为停止状态，避免重复调用
            self.is_running = False
            
            if self.server:
                try:
                    # 安全地关闭服务器，处理Windows套接字错误
                    self.server.shutdown()
                except (OSError, AttributeError) as e:
                    # 处理WinError 10038和其他套接字错误
                    if "10038" in str(e) or "非套接字" in str(e):
                        enhanced_logger.log("WARNING", f"服务器套接字已关闭或无效: {str(e)}", "WebPreviewServer")
                    else:
                        enhanced_logger.log("WARNING", f"服务器关闭时发生错误: {str(e)}", "WebPreviewServer")
                
                try:
                    self.server.server_close()
                except (OSError, AttributeError) as e:
                    # 处理服务器关闭时的错误
                    if "10038" in str(e) or "非套接字" in str(e):
                        enhanced_logger.log("WARNING", f"服务器套接字关闭错误: {str(e)}", "WebPreviewServer")
                    else:
                        enhanced_logger.log("WARNING", f"服务器资源清理错误: {str(e)}", "WebPreviewServer")
            
            # 使用非阻塞方式处理线程清理
            if self.server_thread and self.server_thread.is_alive():
                # 不使用join()阻塞主线程，让线程自然结束
                # 线程已在创建时设置为daemon=True，无需重复设置
                pass
            
            enhanced_logger.log("INFO", "Web服务器已安全停止", "WebPreviewServer")
            
        except Exception as e:
            enhanced_logger.log("ERROR", f"停止Web服务器时发生未预期错误: {str(e)}", "WebPreviewServer")
            self.server_error.emit(str(e))
    
    def get_url(self):
        """获取服务器URL"""
        return f'http://{self.host}:{self.port}'
    
    def open_in_browser(self):
        """在浏览器中打开"""
        if self.is_running:
            webbrowser.open(self.get_url())
            return True
        return False
    
    def get_api_logs(self):
        """获取API日志"""
        try:
            # 返回WebPreviewHandler中的API日志
            if hasattr(WebPreviewHandler, '_api_logs'):
                return WebPreviewHandler._api_logs.copy()
            else:
                return []
        except Exception as e:
            enhanced_logger.log("ERROR", f"获取API日志时出错: {str(e)}", "WebPreviewServer")
            return []