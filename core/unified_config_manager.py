#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
统一配置管理器
用于将多个配置文件合并到一个统一的配置文件中
"""

import os
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

class UnifiedConfigManager:
    """统一配置管理器"""
    
    def __init__(self, app_dir: str = None):
        """
        初始化统一配置管理器
        
        Args:
            app_dir: 应用程序目录，默认为当前目录的上一级
        """
        if app_dir is None:
            self.app_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        else:
            self.app_dir = Path(app_dir)
            
        self.unified_config_path = self.app_dir / "unified_config.json"
        self.config_files = {
            "settings": self.app_dir / "settings.json",
            "config": self.app_dir / "config.json",
            "cloud_sync_config": self.app_dir / "cloud_sync_config.json",
            "debug_config": self.app_dir / "debug_config.json",
            "recent_languages": self.app_dir / "recent_languages.json",
            "log_config": self.app_dir / "logs" / "log_config.json",
            "logger_config": self.app_dir / "logs" / "logger_config.json",
            "optimization_config": self.app_dir / "config" / "optimization_config.json",
            "auth_token": self.app_dir / "config" / "auth_token.json",
        }
        
        # 创建备份目录
        self.backup_dir = self.app_dir / "backups" / "config_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化统一配置
        self.unified_config = {}
        
    def backup_config_files(self) -> bool:
        """
        备份所有配置文件
        
        Returns:
            bool: 备份是否成功
        """
        try:
            timestamp = import_time().strftime("%Y%m%d_%H%M%S")
            backup_folder = self.backup_dir / f"backup_{timestamp}"
            backup_folder.mkdir(parents=True, exist_ok=True)
            
            for config_name, config_path in self.config_files.items():
                if config_path.exists():
                    shutil.copy2(config_path, backup_folder / config_path.name)
                    
            return True
        except Exception as e:
            logging.error(f"备份配置文件失败: {e}")
            return False
            
    def merge_configs(self) -> Dict[str, Any]:
        """
        合并所有配置文件到统一配置
        
        Returns:
            Dict[str, Any]: 合并后的统一配置
        """
        unified = {}
        
        # 读取所有配置文件
        for config_name, config_path in self.config_files.items():
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        unified[config_name] = config_data
                except Exception as e:
                    logging.error(f"读取配置文件 {config_path} 失败: {e}")
                    unified[config_name] = {}
            else:
                unified[config_name] = {}
                
        return unified
        
    def save_unified_config(self, config: Dict[str, Any] = None) -> bool:
        """
        保存统一配置到文件
        
        Args:
            config: 要保存的配置，默认为当前统一配置
            
        Returns:
            bool: 保存是否成功
        """
        if config is None:
            config = self.unified_config
            
        try:
            with open(self.unified_config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"保存统一配置失败: {e}")
            return False
            
    def load_unified_config(self) -> Dict[str, Any]:
        """
        从文件加载统一配置
        
        Returns:
            Dict[str, Any]: 加载的统一配置
        """
        if self.unified_config_path.exists():
            try:
                with open(self.unified_config_path, 'r', encoding='utf-8') as f:
                    self.unified_config = json.load(f)
            except Exception as e:
                logging.error(f"加载统一配置失败: {e}")
                self.unified_config = {}
        else:
            self.unified_config = {}
            
        return self.unified_config
        
    def extract_config(self, config_name: str) -> Dict[str, Any]:
        """
        从统一配置中提取特定配置
        
        Args:
            config_name: 配置名称
            
        Returns:
            Dict[str, Any]: 提取的配置
        """
        return self.unified_config.get(config_name, {})
        
    def update_config(self, config_name: str, config_data: Dict[str, Any]) -> bool:
        """
        更新统一配置中的特定配置
        
        Args:
            config_name: 配置名称
            config_data: 配置数据
            
        Returns:
            bool: 更新是否成功
        """
        try:
            self.unified_config[config_name] = config_data
            return self.save_unified_config()
        except Exception as e:
            logging.error(f"更新配置 {config_name} 失败: {e}")
            return False
            
    def migrate_to_unified_config(self) -> bool:
        """
        将所有配置文件迁移到统一配置
        
        Returns:
            bool: 迁移是否成功
        """
        try:
            # 备份现有配置
            self.backup_config_files()
            
            # 合并配置
            self.unified_config = self.merge_configs()
            
            # 保存统一配置
            return self.save_unified_config()
        except Exception as e:
            logging.error(f"迁移到统一配置失败: {e}")
            return False
            
    def migrate_from_unified_config(self) -> bool:
        """
        从统一配置迁移回多个配置文件
        
        Returns:
            bool: 迁移是否成功
        """
        try:
            # 加载统一配置
            self.load_unified_config()
            
            # 将各部分配置写回原文件
            for config_name, config_path in self.config_files.items():
                config_data = self.extract_config(config_name)
                if config_data:
                    config_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(config_data, f, indent=2, ensure_ascii=False)
                        
            return True
        except Exception as e:
            logging.error(f"从统一配置迁移失败: {e}")
            return False
            
    def get_config_value(self, config_name: str, key_path: str, default=None) -> Any:
        """
        获取配置值
        
        Args:
            config_name: 配置名称
            key_path: 键路径，使用.分隔，如 "ui.theme.name"
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        config = self.extract_config(config_name)
        keys = key_path.split('.')
        
        for key in keys[:-1]:
            config = config.get(key, {})
            
        return config.get(keys[-1], default)
        
    def set_config_value(self, config_name: str, key_path: str, value: Any) -> bool:
        """
        设置配置值
        
        Args:
            config_name: 配置名称
            key_path: 键路径，使用.分隔，如 "ui.theme.name"
            value: 配置值
            
        Returns:
            bool: 设置是否成功
        """
        config = self.extract_config(config_name)
        keys = key_path.split('.')
        
        # 创建嵌套字典
        current = config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
            
        # 设置值
        current[keys[-1]] = value
        
        # 更新配置
        return self.update_config(config_name, config)

def import_time():
    """导入时间模块"""
    import datetime
    return datetime.datetime.now()

# 创建单例实例
_instance = None

def get_unified_config_manager() -> UnifiedConfigManager:
    """
    获取统一配置管理器实例
    
    Returns:
        UnifiedConfigManager: 统一配置管理器实例
    """
    global _instance
    if _instance is None:
        _instance = UnifiedConfigManager()
    return _instance

# 便捷函数
def migrate_to_unified_config() -> bool:
    """
    将所有配置文件迁移到统一配置
    
    Returns:
        bool: 迁移是否成功
    """
    return get_unified_config_manager().migrate_to_unified_config()

def get_config_value(config_name: str, key_path: str, default=None) -> Any:
    """
    获取配置值
    
    Args:
        config_name: 配置名称
        key_path: 键路径，使用.分隔，如 "ui.theme.name"
        default: 默认值
        
    Returns:
        Any: 配置值
    """
    return get_unified_config_manager().get_config_value(config_name, key_path, default)

def set_config_value(config_name: str, key_path: str, value: Any) -> bool:
    """
    设置配置值
    
    Args:
        config_name: 配置名称
        key_path: 键路径，使用.分隔，如 "ui.theme.name"
        value: 配置值
        
    Returns:
        bool: 设置是否成功
    """
    return get_unified_config_manager().set_config_value(config_name, key_path, value)