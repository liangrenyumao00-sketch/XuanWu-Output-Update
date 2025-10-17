# core/log_desensitizer.py
"""
日志脱敏处理模块
自动识别和脱敏日志中的敏感信息，保护用户隐私和系统安全
"""

import re
import hashlib
import logging
from typing import Dict, List, Tuple, Optional, Pattern
from pathlib import Path

logger = logging.getLogger(__name__)

class LogDesensitizer:
    """日志脱敏处理器"""
    
    def __init__(self):
        # 敏感信息模式定义
        self.sensitive_patterns = {
            # API密钥模式
            'api_key': [
                r'(?i)(api[_\-]?key|access[_\-]?key|secret[_\-]?key|client[_\-]?secret)[\s]*[:=][\s]*["\']?([a-zA-Z0-9_\-]{10,})["\']?',
                r'(?i)(token|bearer)[\s]*[:=][\s]*["\']?([a-zA-Z0-9_\-\.]{20,})["\']?',
                r'(?i)(authorization)[\s]*[:=][\s]*["\']?(bearer\s+)?([a-zA-Z0-9_\-\.]{20,})["\']?',
            ],
            
            # 密码模式
            'password': [
                r'(?i)(password|passwd|pwd)[\s]*[:=][\s]*["\']?([^\s"\']{6,})["\']?',
                r'(?i)(密码|口令)[\s]*[:=：][\s]*["\']?([^\s"\']{6,})["\']?',
            ],
            
            # 邮箱地址
            'email': [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            ],
            
            # 手机号码
            'phone': [
                r'(?:\+86)?[\s\-]?1[3-9]\d{9}',  # 中国手机号
                r'\b\d{3}[\-\.\s]?\d{3}[\-\.\s]?\d{4}\b',  # 美国电话号码格式
            ],
            
            # 身份证号
            'id_card': [
                r'\b[1-9]\d{5}(18|19|20)\d{2}((0[1-9])|(1[0-2]))(([0-2][1-9])|10|20|30|31)\d{3}[0-9Xx]\b',  # 18位身份证
                r'\b[1-9]\d{7}((0[1-9])|(1[0-2]))(([0-2][1-9])|10|20|30|31)\d{3}\b',  # 15位身份证
            ],
            
            # 银行卡号
            'bank_card': [
                r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b',  # 16位银行卡
                r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{3}\b',  # 19位银行卡
            ],
            
            # IP地址
            'ip_address': [
                r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',  # IPv4
                r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b',  # IPv6
            ],
            
            # 文件路径（可能包含用户名）
            'file_path': [
                r'[C-Z]:\\Users\\[^\\]+\\[^\s]*',  # Windows用户路径
                r'/home/[^/\s]+/[^\s]*',  # Linux用户路径
                r'/Users/[^/\s]+/[^\s]*',  # macOS用户路径
            ],
            
            # URL中的敏感参数
            'url_params': [
                r'(?i)(token|key|secret|password|pwd)=([^&\s]+)',
            ],
            
            # 数据库连接字符串
            'db_connection': [
                r'(?i)(mongodb|mysql|postgresql|oracle|sqlserver)://[^:\s]+:[^@\s]+@[^\s]+',
            ],
            
            # JWT Token
            'jwt_token': [
                r'eyJ[A-Za-z0-9_\-]*\.eyJ[A-Za-z0-9_\-]*\.[A-Za-z0-9_\-]*',
            ],
            
            # 哈希值（可能是敏感数据的哈希）
            'hash_values': [
                r'\b[a-fA-F0-9]{32}\b',  # MD5
                r'\b[a-fA-F0-9]{40}\b',  # SHA1
                r'\b[a-fA-F0-9]{64}\b',  # SHA256
            ],
        }
        
        # 编译正则表达式
        self.compiled_patterns = {}
        for category, patterns in self.sensitive_patterns.items():
            self.compiled_patterns[category] = [re.compile(pattern) for pattern in patterns]
        
        # 脱敏策略配置
        self.desensitize_config = {
            'api_key': {'method': 'hash', 'show_prefix': 4, 'show_suffix': 4},
            'password': {'method': 'mask', 'mask_char': '*'},
            'email': {'method': 'partial', 'show_prefix': 2, 'show_suffix': 0, 'show_domain': True},
            'phone': {'method': 'partial', 'show_prefix': 3, 'show_suffix': 4},
            'id_card': {'method': 'partial', 'show_prefix': 6, 'show_suffix': 4},
            'bank_card': {'method': 'partial', 'show_prefix': 4, 'show_suffix': 4},
            'ip_address': {'method': 'partial', 'show_prefix': 0, 'show_suffix': 0},
            'file_path': {'method': 'path', 'show_filename': True},
            'url_params': {'method': 'hash', 'show_prefix': 2, 'show_suffix': 2},
            'db_connection': {'method': 'mask', 'mask_char': '*'},
            'jwt_token': {'method': 'hash', 'show_prefix': 8, 'show_suffix': 8},
            'hash_values': {'method': 'partial', 'show_prefix': 8, 'show_suffix': 0},
        }
        
        # 白名单：不需要脱敏的内容
        self.whitelist_patterns = [
            r'127\.0\.0\.1',  # 本地IP
            r'localhost',     # 本地主机
            r'0\.0\.0\.0',    # 通配IP
            r'example\.com',  # 示例域名
            r'test@test\.com', # 测试邮箱
        ]
        self.compiled_whitelist = [re.compile(pattern) for pattern in self.whitelist_patterns]
    
    def is_whitelisted(self, text: str) -> bool:
        """检查文本是否在白名单中"""
        for pattern in self.compiled_whitelist:
            if pattern.search(text):
                return True
        return False
    
    def generate_hash(self, data: str, length: int = 8) -> str:
        """生成数据的哈希值"""
        if not data:
            return "empty"
        hash_obj = hashlib.sha256(data.encode('utf-8'))
        return hash_obj.hexdigest()[:length]
    
    def mask_string(self, text: str, mask_char: str = '*') -> str:
        """用指定字符掩码字符串"""
        return mask_char * len(text)
    
    def partial_mask(self, text: str, show_prefix: int = 0, show_suffix: int = 0, mask_char: str = '*') -> str:
        """部分掩码，保留前缀和后缀"""
        if len(text) <= show_prefix + show_suffix:
            return mask_char * len(text)
        
        prefix = text[:show_prefix] if show_prefix > 0 else ""
        suffix = text[-show_suffix:] if show_suffix > 0 else ""
        middle_length = len(text) - show_prefix - show_suffix
        middle = mask_char * middle_length
        
        return prefix + middle + suffix
    
    def desensitize_email(self, email: str) -> str:
        """脱敏邮箱地址"""
        if '@' not in email:
            return self.mask_string(email)
        
        local, domain = email.split('@', 1)
        if len(local) <= 2:
            masked_local = '*' * len(local)
        else:
            masked_local = local[:2] + '*' * (len(local) - 2)
        
        return f"{masked_local}@{domain}"
    
    def desensitize_file_path(self, path: str) -> str:
        """脱敏文件路径，保留文件名但隐藏用户信息"""
        try:
            path_obj = Path(path)
            parts = path_obj.parts
            
            # 查找用户目录
            user_dir_indices = []
            for i, part in enumerate(parts):
                if part.lower() in ['users', 'home', 'user']:
                    if i + 1 < len(parts):
                        user_dir_indices.append(i + 1)
            
            # 替换用户名
            new_parts = list(parts)
            for idx in user_dir_indices:
                if idx < len(new_parts):
                    new_parts[idx] = '[USER]'
            
            return str(Path(*new_parts))
        except Exception:
            # 如果路径解析失败，使用简单的替换
            return re.sub(r'(Users|home|user)[/\\][^/\\]+', r'\1/[USER]', path, flags=re.IGNORECASE)
    
    def desensitize_value(self, value: str, category: str) -> str:
        """根据类别脱敏值"""
        if self.is_whitelisted(value):
            return value
        
        config = self.desensitize_config.get(category, {})
        method = config.get('method', 'mask')
        
        if method == 'hash':
            prefix_len = config.get('show_prefix', 0)
            suffix_len = config.get('show_suffix', 0)
            hash_val = self.generate_hash(value)
            
            if prefix_len > 0 or suffix_len > 0:
                prefix = value[:prefix_len] if prefix_len > 0 else ""
                suffix = value[-suffix_len:] if suffix_len > 0 else ""
                return f"{prefix}[HASH:{hash_val}]{suffix}"
            else:
                return f"[HASH:{hash_val}]"
        
        elif method == 'mask':
            mask_char = config.get('mask_char', '*')
            return self.mask_string(value, mask_char)
        
        elif method == 'partial':
            prefix_len = config.get('show_prefix', 0)
            suffix_len = config.get('show_suffix', 0)
            return self.partial_mask(value, prefix_len, suffix_len)
        
        elif method == 'path':
            return self.desensitize_file_path(value)
        
        else:
            return self.mask_string(value)
    
    def desensitize_text(self, text: str) -> Tuple[str, List[Dict]]:
        """
        脱敏文本中的敏感信息
        
        Args:
            text: 原始文本
            
        Returns:
            (脱敏后的文本, 检测到的敏感信息列表)
        """
        if not text:
            return text, []
        
        desensitized_text = text
        detected_items = []
        
        # 按类别检测和脱敏
        for category, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                matches = pattern.finditer(desensitized_text)
                for match in matches:
                    full_match = match.group(0)
                    
                    # 对于有分组的模式，取最后一个分组作为敏感值
                    if match.groups():
                        sensitive_value = match.group(-1)
                        # 找到敏感值在完整匹配中的位置
                        start_offset = full_match.find(sensitive_value)
                        if start_offset == -1:
                            sensitive_value = full_match
                            start_offset = 0
                    else:
                        sensitive_value = full_match
                        start_offset = 0
                    
                    # 脱敏处理
                    if category == 'email':
                        desensitized_value = self.desensitize_email(sensitive_value)
                    else:
                        desensitized_value = self.desensitize_value(sensitive_value, category)
                    
                    # 替换原文本中的敏感信息
                    if start_offset > 0:
                        # 保留前缀，只替换敏感部分
                        prefix = full_match[:start_offset]
                        suffix = full_match[start_offset + len(sensitive_value):]
                        replacement = prefix + desensitized_value + suffix
                    else:
                        replacement = desensitized_value
                    
                    desensitized_text = desensitized_text.replace(full_match, replacement, 1)
                    
                    # 记录检测到的敏感信息
                    detected_items.append({
                        'category': category,
                        'original': sensitive_value,
                        'desensitized': desensitized_value,
                        'position': match.start(),
                        'pattern': pattern.pattern
                    })
        
        return desensitized_text, detected_items
    
    def desensitize_log_record(self, record: logging.LogRecord) -> logging.LogRecord:
        """
        脱敏日志记录
        
        Args:
            record: 原始日志记录
            
        Returns:
            脱敏后的日志记录
        """
        # 脱敏消息内容
        if hasattr(record, 'msg') and record.msg:
            desensitized_msg, detected = self.desensitize_text(str(record.msg))
            record.msg = desensitized_msg
            
            # 如果检测到敏感信息，添加标记
            if detected:
                record.desensitized = True
                record.sensitive_count = len(detected)
        
        # 脱敏参数
        if hasattr(record, 'args') and record.args:
            desensitized_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    desensitized_arg, _ = self.desensitize_text(arg)
                    desensitized_args.append(desensitized_arg)
                else:
                    desensitized_args.append(arg)
            record.args = tuple(desensitized_args)
        
        return record
    
    def create_desensitizing_filter(self) -> logging.Filter:
        """创建脱敏日志过滤器"""
        class DesensitizingFilter(logging.Filter):
            def __init__(self, desensitizer):
                super().__init__()
                self.desensitizer = desensitizer
            
            def filter(self, record):
                self.desensitizer.desensitize_log_record(record)
                return True
        
        return DesensitizingFilter(self)
    
    def get_statistics(self) -> Dict:
        """获取脱敏统计信息"""
        return {
            'total_patterns': sum(len(patterns) for patterns in self.compiled_patterns.values()),
            'categories': list(self.compiled_patterns.keys()),
            'whitelist_patterns': len(self.compiled_whitelist),
            'desensitize_methods': list(set(config.get('method', 'mask') for config in self.desensitize_config.values()))
        }

# 全局脱敏器实例
_desensitizer = None

def get_log_desensitizer() -> LogDesensitizer:
    """获取全局日志脱敏器实例"""
    global _desensitizer
    if _desensitizer is None:
        _desensitizer = LogDesensitizer()
    return _desensitizer

def desensitize_text(text: str) -> Tuple[str, List[Dict]]:
    """脱敏文本的便捷函数"""
    return get_log_desensitizer().desensitize_text(text)

def create_desensitizing_filter() -> logging.Filter:
    """创建脱敏过滤器的便捷函数"""
    return get_log_desensitizer().create_desensitizing_filter()

def install_desensitizer_to_logger(logger_name: str = None):
    """为指定的logger安装脱敏过滤器"""
    target_logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    desensitizing_filter = create_desensitizing_filter()
    target_logger.addFilter(desensitizing_filter)
    return target_logger