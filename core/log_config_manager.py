# core/log_config_manager.py
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

class LogFormat(Enum):
    """日志格式枚举"""
    SIMPLE = "%(levelname)s: %(message)s"
    DETAILED = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    HTML = '<span class="{level}">[{timestamp}] {level}: {message}</span>'
    JSON = '{"timestamp": "{timestamp}", "level": "{level}", "message": "{message}", "module": "{module}"}'

@dataclass
class LogConfig:
    """日志配置数据类"""
    # 基础配置
    level: str = "INFO"
    format_type: str = "DETAILED"
    enable_console: bool = True
    enable_file: bool = True
    
    # 文件配置
    log_dir: str = "logs"
    debug_file: str = "debug.html"
    error_file: str = "error.log"
    access_file: str = "access.log"
    
    # 轮转配置
    enable_rotation: bool = True
    max_file_size_mb: int = 10
    max_backup_files: int = 5
    rotation_interval: str = "daily"  # daily, weekly, monthly
    
    # 性能配置
    enable_async: bool = True
    buffer_size: int = 1000
    flush_interval: float = 1.0
    
    # 过滤配置
    enable_filtering: bool = False
    keyword_filters: list = None
    exclude_patterns: list = None
    module_filters: dict = None
    
    # 压缩配置
    enable_compression: bool = True
    compression_level: int = 6
    
    # 清理配置
    auto_cleanup: bool = True
    cleanup_days: int = 30
    
    # 监控配置
    enable_monitoring: bool = True
    stats_interval: int = 300  # 5分钟
    
    # 邮件通知配置
    enable_email_alerts: bool = False
    alert_levels: list = None
    email_config: dict = None
    
    def __post_init__(self):
        """初始化后处理"""
        if self.keyword_filters is None:
            self.keyword_filters = []
        if self.exclude_patterns is None:
            self.exclude_patterns = []
        if self.module_filters is None:
            self.module_filters = {}
        if self.alert_levels is None:
            self.alert_levels = ["ERROR", "CRITICAL"]
        if self.email_config is None:
            self.email_config = {}

class LogConfigManager:
    """日志配置管理器"""
    
    def __init__(self, config_file: str = "logs/log_config.json"):
        self.config_file = Path(config_file)
        self.config = LogConfig()
        self._load_config()
    
    def _load_config(self) -> None:
        """加载配置文件"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 更新配置对象
                    for key, value in data.items():
                        if hasattr(self.config, key):
                            setattr(self.config, key, value)
                print(f"日志配置已加载: {self.config_file}")
            except Exception as e:
                print(f"加载日志配置失败: {e}，使用默认配置")
        else:
            # 创建默认配置文件
            self.save_config()
    
    def save_config(self) -> None:
        """保存配置文件"""
        try:
            # 确保目录存在
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(self.config), f, indent=2, ensure_ascii=False)
            print(f"日志配置已保存: {self.config_file}")
        except Exception as e:
            print(f"保存日志配置失败: {e}")
    
    def get_config(self) -> LogConfig:
        """获取配置对象"""
        return self.config
    
    def update_config(self, **kwargs) -> None:
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
            else:
                print(f"未知配置项: {key}")
        self.save_config()
    
    def get_log_level(self) -> int:
        """获取日志级别"""
        return getattr(logging, self.config.level.upper(), logging.INFO)
    
    def get_log_format(self) -> str:
        """获取日志格式"""
        format_map = {
            "SIMPLE": LogFormat.SIMPLE.value,
            "DETAILED": LogFormat.DETAILED.value,
            "HTML": LogFormat.HTML.value,
            "JSON": LogFormat.JSON.value
        }
        return format_map.get(self.config.format_type, LogFormat.DETAILED.value)
    
    def get_file_paths(self) -> Dict[str, str]:
        """获取日志文件路径"""
        log_dir = Path(self.config.log_dir)
        return {
            'debug': str(log_dir / self.config.debug_file),
            'error': str(log_dir / self.config.error_file),
            'access': str(log_dir / self.config.access_file)
        }
    
    def should_enable_feature(self, feature: str) -> bool:
        """检查是否启用某个功能"""
        feature_map = {
            'rotation': self.config.enable_rotation,
            'async': self.config.enable_async,
            'filtering': self.config.enable_filtering,
            'compression': self.config.enable_compression,
            'cleanup': self.config.auto_cleanup,
            'monitoring': self.config.enable_monitoring,
            'email_alerts': self.config.enable_email_alerts
        }
        return feature_map.get(feature, False)
    
    def get_rotation_config(self) -> Dict[str, Any]:
        """获取轮转配置"""
        return {
            'max_size_mb': self.config.max_file_size_mb,
            'max_files': self.config.max_backup_files,
            'interval': self.config.rotation_interval
        }
    
    def get_performance_config(self) -> Dict[str, Any]:
        """获取性能配置"""
        return {
            'buffer_size': self.config.buffer_size,
            'flush_interval': self.config.flush_interval,
            'enable_async': self.config.enable_async
        }
    
    def get_filter_config(self) -> Dict[str, Any]:
        """获取过滤配置"""
        return {
            'keyword_filters': self.config.keyword_filters,
            'exclude_patterns': self.config.exclude_patterns,
            'module_filters': self.config.module_filters
        }
    
    def add_keyword_filter(self, keyword: str) -> None:
        """添加关键词过滤"""
        if keyword not in self.config.keyword_filters:
            self.config.keyword_filters.append(keyword)
            self.save_config()
    
    def remove_keyword_filter(self, keyword: str) -> None:
        """移除关键词过滤"""
        if keyword in self.config.keyword_filters:
            self.config.keyword_filters.remove(keyword)
            self.save_config()
    
    def add_exclude_pattern(self, pattern: str) -> None:
        """添加排除模式"""
        if pattern not in self.config.exclude_patterns:
            self.config.exclude_patterns.append(pattern)
            self.save_config()
    
    def remove_exclude_pattern(self, pattern: str) -> None:
        """移除排除模式"""
        if pattern in self.config.exclude_patterns:
            self.config.exclude_patterns.remove(pattern)
            self.save_config()
    
    def set_module_filter(self, module: str, enabled: bool) -> None:
        """设置模块过滤"""
        self.config.module_filters[module] = enabled
        self.save_config()
    
    def reset_to_defaults(self) -> None:
        """重置为默认配置"""
        self.config = LogConfig()
        self.save_config()
    
    def export_config(self, export_path: str) -> None:
        """导出配置"""
        try:
            export_file = Path(export_path)
            export_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(self.config), f, indent=2, ensure_ascii=False)
            print(f"配置已导出到: {export_file}")
        except Exception as e:
            print(f"导出配置失败: {e}")
    
    def import_config(self, import_path: str) -> None:
        """导入配置"""
        try:
            import_file = Path(import_path)
            if not import_file.exists():
                raise FileNotFoundError(f"配置文件不存在: {import_file}")
            
            with open(import_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 验证配置数据
            temp_config = LogConfig()
            for key, value in data.items():
                if hasattr(temp_config, key):
                    setattr(temp_config, key, value)
            
            self.config = temp_config
            self.save_config()
            print(f"配置已从 {import_file} 导入")
        except Exception as e:
            print(f"导入配置失败: {e}")
    
    def validate_config(self) -> Dict[str, Any]:
        """验证配置"""
        issues = []
        warnings = []
        
        # 检查日志级别
        if self.config.level.upper() not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            issues.append(f"无效的日志级别: {self.config.level}")
        
        # 检查文件大小
        if self.config.max_file_size_mb <= 0:
            issues.append("最大文件大小必须大于0")
        
        # 检查缓冲区大小
        if self.config.buffer_size <= 0:
            issues.append("缓冲区大小必须大于0")
        
        # 检查刷新间隔
        if self.config.flush_interval <= 0:
            warnings.append("刷新间隔过小可能影响性能")
        
        # 检查清理天数
        if self.config.cleanup_days <= 0:
            warnings.append("清理天数设置可能导致日志立即删除")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }
    
    def get_config_summary(self) -> str:
        """获取配置摘要"""
        return f"""
日志配置摘要:
- 日志级别: {self.config.level}
- 格式类型: {self.config.format_type}
- 文件输出: {'启用' if self.config.enable_file else '禁用'}
- 控制台输出: {'启用' if self.config.enable_console else '禁用'}
- 异步写入: {'启用' if self.config.enable_async else '禁用'}
- 日志轮转: {'启用' if self.config.enable_rotation else '禁用'}
- 自动清理: {'启用' if self.config.auto_cleanup else '禁用'}
- 最大文件大小: {self.config.max_file_size_mb}MB
- 备份文件数: {self.config.max_backup_files}
- 缓冲区大小: {self.config.buffer_size}
- 刷新间隔: {self.config.flush_interval}秒
"""

# 全局配置管理器实例
_config_manager = None

def get_log_config_manager() -> LogConfigManager:
    """获取全局日志配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = LogConfigManager()
    return _config_manager

def init_log_config(config_file: str = "logs/log_config.json") -> LogConfigManager:
    """初始化日志配置管理器"""
    global _config_manager
    _config_manager = LogConfigManager(config_file)
    return _config_manager