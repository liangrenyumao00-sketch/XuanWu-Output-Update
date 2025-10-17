# core/input_validator.py
"""
输入验证模块
提供统一的输入验证功能，防止恶意输入和数据注入
"""

import re
import os
import json
import logging
from typing import Dict, List, Tuple, Optional, Any
from urllib.parse import urlparse
import hashlib

logger = logging.getLogger(__name__)

class InputValidator:
    """输入验证器类"""
    
    # 危险字符模式
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # XSS脚本
        r'javascript:',               # JavaScript协议
        r'vbscript:',                # VBScript协议
        r'on\w+\s*=',                # 事件处理器
        r'eval\s*\(',                # eval函数
        r'exec\s*\(',                # exec函数
        r'system\s*\(',              # system调用
        r'__import__\s*\(',          # Python导入
        r'\.\./',                    # 路径遍历
        r'\.\.\\',                   # Windows路径遍历
    ]
    
    # SQL注入模式
    SQL_INJECTION_PATTERNS = [
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)',
        r'(\b(OR|AND)\s+\d+\s*=\s*\d+)',
        r'(\b(OR|AND)\s+[\'"]?\w+[\'"]?\s*=\s*[\'"]?\w+[\'"]?)',
        r'(--|#|/\*|\*/)',
        r'(\bUNION\s+SELECT\b)',
        r'(\bINTO\s+OUTFILE\b)',
    ]
    
    # 文件路径危险模式
    PATH_DANGEROUS_PATTERNS = [
        r'\.\./',
        r'\.\.\\',
        r'/etc/',
        r'\\windows\\',
        r'/proc/',
        r'/sys/',
        r'~/',
        r'\$\{.*\}',  # 环境变量注入
    ]
    
    def __init__(self):
        self.compiled_dangerous = [re.compile(pattern, re.IGNORECASE) for pattern in self.DANGEROUS_PATTERNS]
        self.compiled_sql = [re.compile(pattern, re.IGNORECASE) for pattern in self.SQL_INJECTION_PATTERNS]
        self.compiled_path = [re.compile(pattern, re.IGNORECASE) for pattern in self.PATH_DANGEROUS_PATTERNS]
    
    def validate_text_input(self, text: str, max_length: int = 1000, 
                           allow_html: bool = False) -> Tuple[bool, str]:
        """
        验证文本输入
        
        Args:
            text: 要验证的文本
            max_length: 最大长度限制
            allow_html: 是否允许HTML标签
            
        Returns:
            (是否有效, 错误信息)
        """
        if not isinstance(text, str):
            return False, "输入必须是字符串类型"
        
        # 长度检查
        if len(text) > max_length:
            return False, f"输入长度超过限制（最大{max_length}字符）"
        
        # 检查危险字符
        if not allow_html:
            for pattern in self.compiled_dangerous:
                if pattern.search(text):
                    logger.warning(f"检测到危险输入模式: {pattern.pattern}")
                    return False, "输入包含不安全的内容"
        
        # 检查SQL注入
        for pattern in self.compiled_sql:
            if pattern.search(text):
                logger.warning(f"检测到SQL注入模式: {pattern.pattern}")
                return False, "输入包含可能的SQL注入内容"
        
        return True, ""
    
    def validate_api_key(self, api_key: str) -> Tuple[bool, str]:
        """
        验证API密钥格式
        
        Args:
            api_key: API密钥
            
        Returns:
            (是否有效, 错误信息)
        """
        if not isinstance(api_key, str):
            return False, "API密钥必须是字符串类型"
        
        api_key = api_key.strip()
        
        # 基本长度检查
        if len(api_key) < 10:
            return False, "API密钥长度过短"
        
        if len(api_key) > 200:
            return False, "API密钥长度过长"
        
        # 检查是否包含危险字符
        for pattern in self.compiled_dangerous:
            if pattern.search(api_key):
                logger.warning("API密钥包含危险字符")
                return False, "API密钥格式不正确"
        
        # 检查基本格式（只允许字母、数字、下划线、连字符）
        if not re.match(r'^[a-zA-Z0-9_\-]+$', api_key):
            return False, "API密钥只能包含字母、数字、下划线和连字符"
        
        return True, ""
    
    def validate_file_path(self, file_path: str, allowed_extensions: List[str] = None) -> Tuple[bool, str]:
        """
        验证文件路径
        
        Args:
            file_path: 文件路径
            allowed_extensions: 允许的文件扩展名列表
            
        Returns:
            (是否有效, 错误信息)
        """
        if not isinstance(file_path, str):
            return False, "文件路径必须是字符串类型"
        
        file_path = file_path.strip()
        
        # 检查路径遍历攻击
        for pattern in self.compiled_path:
            if pattern.search(file_path):
                logger.warning(f"检测到危险路径模式: {pattern.pattern}")
                return False, "文件路径包含不安全的内容"
        
        # 检查文件扩展名
        if allowed_extensions:
            _, ext = os.path.splitext(file_path.lower())
            if ext not in [e.lower() for e in allowed_extensions]:
                return False, f"不支持的文件类型，允许的扩展名: {', '.join(allowed_extensions)}"
        
        # 检查路径长度
        if len(file_path) > 260:  # Windows路径长度限制
            return False, "文件路径过长"
        
        return True, ""
    
    def validate_url(self, url: str) -> Tuple[bool, str]:
        """
        验证URL格式
        
        Args:
            url: URL地址
            
        Returns:
            (是否有效, 错误信息)
        """
        if not isinstance(url, str):
            return False, "URL必须是字符串类型"
        
        url = url.strip()
        
        # 基本长度检查
        if len(url) > 2048:
            return False, "URL长度过长"
        
        # 检查危险协议
        dangerous_schemes = ['javascript', 'vbscript', 'data', 'file']
        try:
            parsed = urlparse(url)
            if parsed.scheme.lower() in dangerous_schemes:
                return False, "不支持的URL协议"
            
            if parsed.scheme not in ['http', 'https', 'ftp', 'ftps']:
                return False, "只支持HTTP、HTTPS、FTP、FTPS协议"
                
        except Exception:
            return False, "URL格式不正确"
        
        return True, ""
    
    def validate_json_input(self, json_str: str, max_size: int = 10240) -> Tuple[bool, str, Optional[Dict]]:
        """
        验证JSON输入
        
        Args:
            json_str: JSON字符串
            max_size: 最大大小（字节）
            
        Returns:
            (是否有效, 错误信息, 解析后的数据)
        """
        if not isinstance(json_str, str):
            return False, "JSON输入必须是字符串类型", None
        
        # 大小检查
        if len(json_str.encode('utf-8')) > max_size:
            return False, f"JSON数据过大（最大{max_size}字节）", None
        
        # 检查危险内容
        for pattern in self.compiled_dangerous:
            if pattern.search(json_str):
                logger.warning("JSON输入包含危险内容")
                return False, "JSON输入包含不安全的内容", None
        
        # 解析JSON
        try:
            data = json.loads(json_str)
            return True, "", data
        except json.JSONDecodeError as e:
            return False, f"JSON格式错误: {str(e)}", None
    
    def validate_password(self, password: str) -> Tuple[bool, str, int]:
        """
        验证密码强度
        
        Args:
            password: 密码
            
        Returns:
            (是否有效, 错误信息, 强度等级0-5)
        """
        if not isinstance(password, str):
            return False, "密码必须是字符串类型", 0
        
        if len(password) < 6:
            return False, "密码长度至少6位", 0
        
        if len(password) > 128:
            return False, "密码长度过长", 0
        
        # 计算密码强度
        strength = 0
        
        if len(password) >= 8:
            strength += 1
        
        if re.search(r'[a-z]', password):
            strength += 1
        
        if re.search(r'[A-Z]', password):
            strength += 1
        
        if re.search(r'\d', password):
            strength += 1
        
        if re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
            strength += 1
        
        # 检查常见弱密码
        weak_passwords = [
            '123456', 'password', '123456789', '12345678', '12345',
            '1234567', '1234567890', 'qwerty', 'abc123', 'password123'
        ]
        
        if password.lower() in weak_passwords:
            return False, "密码过于简单，请使用更复杂的密码", 0
        
        return True, "", strength
    
    def sanitize_input(self, text: str) -> str:
        """
        清理输入文本，移除危险字符
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        if not isinstance(text, str):
            return ""
        
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除危险字符
        text = re.sub(r'[<>"\']', '', text)
        
        # 移除控制字符
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        
        return text.strip()
    
    def hash_sensitive_data(self, data: str) -> str:
        """
        对敏感数据进行哈希处理，用于日志记录
        
        Args:
            data: 敏感数据
            
        Returns:
            哈希值
        """
        if not data:
            return "empty"
        
        # 使用SHA256哈希，只保留前8位用于标识
        hash_obj = hashlib.sha256(data.encode('utf-8'))
        return hash_obj.hexdigest()[:8]

# 全局验证器实例
_validator = None

def get_input_validator() -> InputValidator:
    """获取全局输入验证器实例"""
    global _validator
    if _validator is None:
        _validator = InputValidator()
    return _validator

# 便捷函数
def validate_text(text: str, max_length: int = 1000, allow_html: bool = False) -> Tuple[bool, str]:
    """验证文本输入的便捷函数"""
    return get_input_validator().validate_text_input(text, max_length, allow_html)

def validate_api_key(api_key: str) -> Tuple[bool, str]:
    """验证API密钥的便捷函数"""
    return get_input_validator().validate_api_key(api_key)

def validate_file_path(file_path: str, allowed_extensions: List[str] = None) -> Tuple[bool, str]:
    """验证文件路径的便捷函数"""
    return get_input_validator().validate_file_path(file_path, allowed_extensions)

def validate_url(url: str) -> Tuple[bool, str]:
    """验证URL的便捷函数"""
    return get_input_validator().validate_url(url)

def validate_password(password: str) -> Tuple[bool, str, int]:
    """验证密码的便捷函数"""
    return get_input_validator().validate_password(password)

def sanitize_input(text: str) -> str:
    """清理输入的便捷函数"""
    return get_input_validator().sanitize_input(text)

def hash_sensitive_data(data: str) -> str:
    """哈希敏感数据的便捷函数"""
    return get_input_validator().hash_sensitive_data(data)