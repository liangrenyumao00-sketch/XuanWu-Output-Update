# core/config_manager.py
"""
增强的配置管理器

该模块提供统一的配置管理功能：
- 配置验证和类型检查
- 配置热重载
- 配置版本管理
- 配置备份和恢复
- 配置模板和预设
- 配置加密和安全
- 配置监听和回调

作者：XuanWu OCR Team
版本：2.1.7
"""

import os
import json
import time
import threading
import shutil
from typing import Dict, Any, Optional, List, Callable, Union, Type
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import jsonschema
from jsonschema import validate, ValidationError

from core.enhanced_logger import get_enhanced_logger
from core.cache_manager import get_cache_manager


class ConfigType(Enum):
    """配置类型枚举"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    PATH = "path"
    EMAIL = "email"
    URL = "url"
    PASSWORD = "password"


@dataclass
class ConfigField:
    """配置字段定义"""
    name: str
    type: ConfigType
    default: Any
    description: str = ""
    required: bool = False
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    choices: Optional[List[Any]] = None
    pattern: Optional[str] = None
    validator: Optional[Callable[[Any], bool]] = None
    sensitive: bool = False  # 是否为敏感信息
    deprecated: bool = False  # 是否已弃用
    migration_key: Optional[str] = None  # 迁移时的旧键名


@dataclass
class ConfigSection:
    """配置节定义"""
    name: str
    description: str = ""
    fields: Dict[str, ConfigField] = field(default_factory=dict)
    required: bool = False


@dataclass
class ConfigSchema:
    """配置模式定义"""
    version: str
    sections: Dict[str, ConfigSection] = field(default_factory=dict)
    
    def add_section(self, section: ConfigSection):
        """添加配置节"""
        self.sections[section.name] = section
    
    def add_field(self, section_name: str, field: ConfigField):
        """添加配置字段"""
        if section_name not in self.sections:
            self.sections[section_name] = ConfigSection(section_name)
        self.sections[section_name].fields[field.name] = field


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self):
        self.logger = get_enhanced_logger()
    
    def validate_value(self, value: Any, field: ConfigField) -> tuple[bool, str]:
        """验证单个值"""
        try:
            # 类型检查
            if not self._check_type(value, field.type):
                return False, f"类型错误：期望 {field.type.value}，实际 {type(value).__name__}"
            
            # 必填检查
            if field.required and (value is None or value == ""):
                return False, "必填字段不能为空"
            
            # 范围检查
            if field.min_value is not None and value < field.min_value:
                return False, f"值不能小于 {field.min_value}"
            
            if field.max_value is not None and value > field.max_value:
                return False, f"值不能大于 {field.max_value}"
            
            # 长度检查
            if field.min_length is not None and len(str(value)) < field.min_length:
                return False, f"长度不能小于 {field.min_length}"
            
            if field.max_length is not None and len(str(value)) > field.max_length:
                return False, f"长度不能大于 {field.max_length}"
            
            # 选择检查
            if field.choices is not None and value not in field.choices:
                return False, f"值必须是以下之一：{field.choices}"
            
            # 模式检查
            if field.pattern is not None:
                import re
                if not re.match(field.pattern, str(value)):
                    return False, f"值不匹配模式：{field.pattern}"
            
            # 自定义验证器
            if field.validator is not None:
                if not field.validator(value):
                    return False, "自定义验证失败"
            
            # 特殊类型验证
            if field.type == ConfigType.EMAIL:
                if not self._validate_email(value):
                    return False, "无效的邮箱地址"
            
            elif field.type == ConfigType.URL:
                if not self._validate_url(value):
                    return False, "无效的URL地址"
            
            elif field.type == ConfigType.PATH:
                if not self._validate_path(value):
                    return False, "无效的路径"
            
            return True, ""
            
        except Exception as e:
            return False, f"验证异常：{e}"
    
    def validate_config(self, config: Dict[str, Any], schema: ConfigSchema) -> tuple[bool, List[str]]:
        """验证整个配置"""
        errors = []
        
        try:
            for section_name, section in schema.sections.items():
                section_config = config.get(section_name, {})
                
                # 检查必需的节
                if section.required and not section_config:
                    errors.append(f"缺少必需的配置节：{section_name}")
                    continue
                
                # 验证节中的字段
                for field_name, field in section.fields.items():
                    value = section_config.get(field_name, field.default)
                    
                    valid, error = self.validate_value(value, field)
                    if not valid:
                        errors.append(f"{section_name}.{field_name}: {error}")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            errors.append(f"配置验证异常：{e}")
            return False, errors
    
    def _check_type(self, value: Any, config_type: ConfigType) -> bool:
        """检查类型"""
        if value is None:
            return True
        
        type_map = {
            ConfigType.STRING: str,
            ConfigType.INTEGER: int,
            ConfigType.FLOAT: (int, float),
            ConfigType.BOOLEAN: bool,
            ConfigType.LIST: list,
            ConfigType.DICT: dict,
            ConfigType.PATH: str,
            ConfigType.EMAIL: str,
            ConfigType.URL: str,
            ConfigType.PASSWORD: str
        }
        
        expected_type = type_map.get(config_type)
        if expected_type is None:
            return True
        
        return isinstance(value, expected_type)
    
    def _validate_email(self, email: str) -> bool:
        """验证邮箱地址"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _validate_url(self, url: str) -> bool:
        """验证URL地址"""
        import re
        pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        return re.match(pattern, url) is not None
    
    def _validate_path(self, path: str) -> bool:
        """验证路径"""
        try:
            Path(path)
            return True
        except Exception:
            return False


class ConfigMigrator:
    """配置迁移器"""
    
    def __init__(self):
        self.logger = get_enhanced_logger()
        self.migrations = {}
    
    def register_migration(self, from_version: str, to_version: str, 
                          migration_func: Callable[[Dict[str, Any]], Dict[str, Any]]):
        """注册迁移函数"""
        key = f"{from_version}->{to_version}"
        self.migrations[key] = migration_func
    
    def migrate(self, config: Dict[str, Any], from_version: str, to_version: str) -> Dict[str, Any]:
        """执行配置迁移"""
        try:
            key = f"{from_version}->{to_version}"
            if key in self.migrations:
                self.logger.info(f"执行配置迁移：{from_version} -> {to_version}")
                return self.migrations[key](config)
            else:
                self.logger.warning(f"未找到迁移路径：{from_version} -> {to_version}")
                return config
        except Exception as e:
            self.logger.error(f"配置迁移失败：{e}")
            return config


class ConfigManager:
    """增强的配置管理器"""
    
    def __init__(self, 
                 config_file: str = "config.json",
                 schema: Optional[ConfigSchema] = None,
                 auto_save: bool = True,
                 backup_count: int = 5,
                 watch_changes: bool = True):
        
        self.config_file = Path(config_file)
        self.schema = schema
        self.auto_save = auto_save
        self.backup_count = backup_count
        self.watch_changes = watch_changes
        
        self.logger = get_enhanced_logger()
        self.cache_manager = get_cache_manager()
        self.validator = ConfigValidator()
        self.migrator = ConfigMigrator()
        
        # 配置数据
        self._config = {}
        self._config_lock = threading.RLock()
        self._last_modified = 0
        
        # 回调函数
        self._change_callbacks = []
        self._validation_callbacks = []
        
        # 文件监控
        self._file_watcher = None
        self._watch_thread = None
        
        # 初始化
        self._init_config()
        if self.watch_changes:
            self._start_file_watcher()
    
    def _init_config(self):
        """初始化配置"""
        try:
            if self.config_file.exists():
                self.load_config()
            else:
                self._config = self._get_default_config()
                self.save_config()
            
            self.logger.info(f"配置管理器初始化完成：{self.config_file}")
            
        except Exception as e:
            self.logger.error(f"配置初始化失败：{e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        if self.schema:
            config = {}
            for section_name, section in self.schema.sections.items():
                section_config = {}
                for field_name, field in section.fields.items():
                    section_config[field_name] = field.default
                config[section_name] = section_config
            return config
        return {}
    
    def load_config(self) -> bool:
        """加载配置"""
        try:
            with self._config_lock:
                if not self.config_file.exists():
                    self.logger.warning(f"配置文件不存在：{self.config_file}")
                    return False
                
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # 验证配置
                if self.schema:
                    valid, errors = self.validator.validate_config(config_data, self.schema)
                    if not valid:
                        self.logger.warning(f"配置验证失败：{errors}")
                        # 可以选择使用默认值或修复配置
                        config_data = self._fix_config(config_data, errors)
                
                self._config = config_data
                self._last_modified = self.config_file.stat().st_mtime
                
                # 触发变更回调
                self._trigger_change_callbacks()
                
                self.logger.info("配置加载成功")
                return True
                
        except Exception as e:
            self.logger.error(f"加载配置失败：{e}")
            return False
    
    def save_config(self) -> bool:
        """保存配置"""
        try:
            with self._config_lock:
                # 创建备份
                if self.config_file.exists():
                    self._create_backup()
                
                # 创建临时文件
                temp_file = self.config_file.with_suffix('.tmp')
                
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self._config, f, ensure_ascii=False, indent=2)
                
                # 原子性替换
                temp_file.replace(self.config_file)
                
                self._last_modified = self.config_file.stat().st_mtime
                
                self.logger.info("配置保存成功")
                return True
                
        except Exception as e:
            self.logger.error(f"保存配置失败：{e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        try:
            with self._config_lock:
                keys = key.split('.')
                value = self._config
                
                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        return default
                
                return value
                
        except Exception as e:
            self.logger.error(f"获取配置失败：{key}, 错误：{e}")
            return default
    
    def set(self, key: str, value: Any, validate: bool = True) -> bool:
        """设置配置值"""
        try:
            with self._config_lock:
                # 验证值
                if validate and self.schema:
                    field = self._find_field(key)
                    if field:
                        valid, error = self.validator.validate_value(value, field)
                        if not valid:
                            self.logger.error(f"配置验证失败：{key} = {value}, 错误：{error}")
                            return False
                
                # 设置值
                keys = key.split('.')
                config = self._config
                
                for k in keys[:-1]:
                    if k not in config:
                        config[k] = {}
                    config = config[k]
                
                old_value = config.get(keys[-1])
                config[keys[-1]] = value
                
                # 自动保存
                if self.auto_save:
                    self.save_config()
                
                # 触发变更回调
                self._trigger_change_callbacks(key, old_value, value)
                
                self.logger.debug(f"配置已更新：{key} = {value}")
                return True
                
        except Exception as e:
            self.logger.error(f"设置配置失败：{key} = {value}, 错误：{e}")
            return False
    
    def delete(self, key: str) -> bool:
        """删除配置项"""
        try:
            with self._config_lock:
                keys = key.split('.')
                config = self._config
                
                for k in keys[:-1]:
                    if k not in config:
                        return False
                    config = config[k]
                
                if keys[-1] in config:
                    old_value = config.pop(keys[-1])
                    
                    # 自动保存
                    if self.auto_save:
                        self.save_config()
                    
                    # 触发变更回调
                    self._trigger_change_callbacks(key, old_value, None)
                    
                    self.logger.debug(f"配置已删除：{key}")
                    return True
                
                return False
                
        except Exception as e:
            self.logger.error(f"删除配置失败：{key}, 错误：{e}")
            return False
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """获取配置节"""
        return self.get(section, {})
    
    def set_section(self, section: str, config: Dict[str, Any]) -> bool:
        """设置配置节"""
        return self.set(section, config)
    
    def has(self, key: str) -> bool:
        """检查配置项是否存在"""
        return self.get(key) is not None
    
    def reset_to_default(self, key: Optional[str] = None) -> bool:
        """重置为默认值"""
        try:
            with self._config_lock:
                if key is None:
                    # 重置整个配置
                    self._config = self._get_default_config()
                else:
                    # 重置特定配置项
                    field = self._find_field(key)
                    if field:
                        self.set(key, field.default, validate=False)
                
                if self.auto_save:
                    self.save_config()
                
                self.logger.info(f"配置已重置：{key or '全部'}")
                return True
                
        except Exception as e:
            self.logger.error(f"重置配置失败：{e}")
            return False
    
    def export_config(self, file_path: str, sections: Optional[List[str]] = None) -> bool:
        """导出配置"""
        try:
            export_data = {}
            
            if sections:
                for section in sections:
                    if section in self._config:
                        export_data[section] = self._config[section]
            else:
                export_data = self._config.copy()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"配置导出成功：{file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"导出配置失败：{e}")
            return False
    
    def import_config(self, file_path: str, merge: bool = True) -> bool:
        """导入配置"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            with self._config_lock:
                if merge:
                    # 合并配置
                    self._merge_config(self._config, import_data)
                else:
                    # 替换配置
                    self._config = import_data
                
                if self.auto_save:
                    self.save_config()
            
            self.logger.info(f"配置导入成功：{file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"导入配置失败：{e}")
            return False
    
    def add_change_callback(self, callback: Callable):
        """添加变更回调"""
        self._change_callbacks.append(callback)
    
    def remove_change_callback(self, callback: Callable):
        """移除变更回调"""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)
    
    def get_config_info(self) -> Dict[str, Any]:
        """获取配置信息"""
        return {
            'file_path': str(self.config_file),
            'file_size': self.config_file.stat().st_size if self.config_file.exists() else 0,
            'last_modified': self._last_modified,
            'sections_count': len(self._config),
            'total_fields': sum(len(section) if isinstance(section, dict) else 1 
                              for section in self._config.values()),
            'schema_version': self.schema.version if self.schema else None,
            'auto_save': self.auto_save,
            'watch_changes': self.watch_changes
        }
    
    def _find_field(self, key: str) -> Optional[ConfigField]:
        """查找字段定义"""
        if not self.schema:
            return None
        
        keys = key.split('.')
        if len(keys) >= 2:
            section_name, field_name = keys[0], keys[1]
            section = self.schema.sections.get(section_name)
            if section:
                return section.fields.get(field_name)
        
        return None
    
    def _fix_config(self, config: Dict[str, Any], errors: List[str]) -> Dict[str, Any]:
        """修复配置错误"""
        # 简单的修复策略：使用默认值
        fixed_config = config.copy()
        
        if self.schema:
            for section_name, section in self.schema.sections.items():
                if section_name not in fixed_config:
                    fixed_config[section_name] = {}
                
                for field_name, field in section.fields.items():
                    if field_name not in fixed_config[section_name]:
                        fixed_config[section_name][field_name] = field.default
        
        return fixed_config
    
    def _create_backup(self):
        """创建配置备份"""
        try:
            backup_dir = self.config_file.parent / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = int(time.time())
            backup_file = backup_dir / f"{self.config_file.stem}_{timestamp}.json"
            
            shutil.copy2(self.config_file, backup_file)
            
            # 清理旧备份
            self._cleanup_old_backups(backup_dir)
            
        except Exception as e:
            self.logger.error(f"创建配置备份失败：{e}")
    
    def _cleanup_old_backups(self, backup_dir: Path):
        """清理旧备份"""
        try:
            backups = list(backup_dir.glob(f"{self.config_file.stem}_*.json"))
            backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            for backup in backups[self.backup_count:]:
                backup.unlink()
                
        except Exception as e:
            self.logger.error(f"清理旧备份失败：{e}")
    
    def _merge_config(self, target: Dict[str, Any], source: Dict[str, Any]):
        """合并配置"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._merge_config(target[key], value)
            else:
                target[key] = value
    
    def _trigger_change_callbacks(self, key: str = None, old_value: Any = None, new_value: Any = None):
        """触发变更回调"""
        for callback in self._change_callbacks:
            try:
                callback(key, old_value, new_value)
            except Exception as e:
                self.logger.error(f"变更回调执行失败：{e}")
    
    def _start_file_watcher(self):
        """启动文件监控"""
        def watch_file():
            while True:
                try:
                    if self.config_file.exists():
                        current_mtime = self.config_file.stat().st_mtime
                        if current_mtime > self._last_modified:
                            self.logger.info("检测到配置文件变更，重新加载")
                            self.load_config()
                    
                    time.sleep(1)  # 每秒检查一次
                    
                except Exception as e:
                    self.logger.error(f"文件监控异常：{e}")
                    time.sleep(5)
        
        self._watch_thread = threading.Thread(target=watch_file, daemon=True)
        self._watch_thread.start()
    
    def shutdown(self):
        """关闭配置管理器"""
        try:
            if self.auto_save:
                self.save_config()
            
            self.logger.info("配置管理器已关闭")
            
        except Exception as e:
            self.logger.error(f"关闭配置管理器失败：{e}")


# 全局配置管理器实例
_config_manager = None
_config_manager_lock = threading.Lock()


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    
    if _config_manager is None:
        with _config_manager_lock:
            if _config_manager is None:
                _config_manager = ConfigManager()
    
    return _config_manager


# 便捷函数
def get_config(key: str, default: Any = None) -> Any:
    """获取配置"""
    return get_config_manager().get(key, default)


def set_config(key: str, value: Any) -> bool:
    """设置配置"""
    return get_config_manager().set(key, value)


def has_config(key: str) -> bool:
    """检查配置是否存在"""
    return get_config_manager().has(key)