# core/app_initializer.py
"""
应用初始化管理器

该模块负责应用程序的初始化流程，包括：
- 日志系统初始化
- 配置加载和验证
- 性能监控启动
- 系统环境检查
- 资源预加载

作者：XuanWu OCR Team
版本：2.1.7
"""

import os
import sys
import logging
import platform
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

from core.enhanced_logger import get_enhanced_logger
from core.settings import load_settings, save_settings, get_default_settings
from core.performance_manager import PerformanceManager
from core.log_desensitizer import get_log_desensitizer
from core.i18n import set_language, t


class AppInitializer:
    """应用初始化管理器"""
    
    def __init__(self):
        self.logger = None
        self.settings = {}
        self.performance_manager = None
        self.initialization_start_time = time.time()
        
    def initialize(self) -> bool:
        """
        执行完整的应用初始化流程
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 1. 基础环境检查
            if not self._check_system_requirements():
                return False
                
            # 2. 创建必要目录
            self._create_directories()
            
            # 3. 初始化日志系统
            self._initialize_logging()
            
            # 4. 加载配置
            self._load_configuration()
            
            # 5. 初始化性能监控
            self._initialize_performance_monitoring()
            
            # 6. 加载语言包
            self._initialize_localization()
            
            # 7. 记录启动信息
            self._log_startup_info()
            
            return True
            
        except Exception as e:
            print(f"应用初始化失败: {e}")
            return False
    
    def _check_system_requirements(self) -> bool:
        """检查系统要求"""
        try:
            # 检查Python版本
            if sys.version_info < (3, 8):
                print("错误: 需要Python 3.8或更高版本")
                return False
                
            # 检查操作系统
            if platform.system() not in ['Windows', 'Linux', 'Darwin']:
                print("警告: 未测试的操作系统")
                
            # 检查内存
            try:
                import psutil
                memory = psutil.virtual_memory()
                if memory.total < 2 * 1024 * 1024 * 1024:  # 2GB
                    print("警告: 系统内存可能不足")
            except ImportError:
                pass
                
            return True
            
        except Exception as e:
            print(f"系统要求检查失败: {e}")
            return False
    
    def _create_directories(self):
        """创建必要的目录结构"""
        directories = [
            "logs",
            "logs/security",
            "logs/control_panel",
            "XuanWu_Screenshots",
            "XuanWu_Logs",
            "backups",
            "config",
            "sessions",
            "sync_data",
            "transfers"
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def _initialize_logging(self):
        """初始化日志系统"""
        try:
            # 获取增强日志器
            self.logger = get_enhanced_logger()
            
            # 配置日志级别
            log_level = getattr(logging, self.settings.get('log_level', 'INFO').upper(), logging.INFO)
            self.logger.setLevel(log_level)
            
            # 启用日志脱敏
            desensitizer = get_log_desensitizer()
            if desensitizer:
                self.logger.info("日志脱敏功能已启用")
            
            self.logger.info("日志系统初始化完成")
            
        except Exception as e:
            print(f"日志系统初始化失败: {e}")
            # 创建基础日志器作为备用
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            self.logger = logging.getLogger(__name__)
    
    def _load_configuration(self):
        """加载和验证配置"""
        try:
            # 加载设置
            self.settings = load_settings()
            
            # 如果配置为空，使用默认配置
            if not self.settings:
                self.logger.warning("配置文件为空，使用默认配置")
                self.settings = get_default_settings()
                save_settings(self.settings)
            
            # 验证关键配置项
            self._validate_configuration()
            
            self.logger.info("配置加载完成")
            
        except Exception as e:
            self.logger.error(f"配置加载失败: {e}")
            # 使用默认配置
            self.settings = get_default_settings()
    
    def _validate_configuration(self):
        """验证配置的有效性"""
        required_keys = [
            'theme', 'language', 'log_level', 'font_size',
            'shortcut_key', 'ocr_version', 'timeout_seconds'
        ]
        
        for key in required_keys:
            if key not in self.settings:
                default_value = self._get_default_value(key)
                self.settings[key] = default_value
                self.logger.warning(f"配置项 {key} 缺失，使用默认值: {default_value}")
    
    def _get_default_value(self, key: str) -> Any:
        """获取配置项的默认值"""
        defaults = {
            'theme': '深色',
            'language': '简体中文',
            'log_level': 'INFO',
            'font_size': 9,
            'shortcut_key': 'Ctrl+Shift+S',
            'ocr_version': 'general',
            'timeout_seconds': 30
        }
        return defaults.get(key, '')
    
    def _initialize_performance_monitoring(self):
        """初始化性能监控"""
        try:
            self.performance_manager = PerformanceManager()
            self.performance_manager.start_monitoring()
            self.logger.info("性能监控已启动")
            
        except Exception as e:
            self.logger.error(f"性能监控初始化失败: {e}")
    
    def _initialize_localization(self):
        """初始化本地化"""
        try:
            language = self.settings.get('language', '简体中文')
            # 将显示名称转换为语言代码
            language_map = {
                '简体中文': 'zh_CN',
                '繁體中文': 'zh_TW',
                'English': 'en_US',
                '日本語': 'ja_JP'
            }
            language_code = language_map.get(language, 'zh_CN')
            set_language(language_code)
            self.logger.info(f"语言包加载完成: {language} ({language_code})")
            
        except Exception as e:
            self.logger.error(f"语言包加载失败: {e}")
    
    def _log_startup_info(self):
        """记录启动信息"""
        try:
            initialization_time = time.time() - self.initialization_start_time
            
            startup_info = {
                "应用版本": "2.1.7",
                "Python版本": sys.version,
                "操作系统": f"{platform.system()} {platform.release()}",
                "启动时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "初始化耗时": f"{initialization_time:.2f}秒",
                "工作目录": os.getcwd(),
                "配置文件": "settings.json"
            }
            
            self.logger.info("=== 应用启动信息 ===")
            for key, value in startup_info.items():
                self.logger.info(f"{key}: {value}")
            self.logger.info("==================")
            
        except Exception as e:
            self.logger.error(f"启动信息记录失败: {e}")
    
    def get_settings(self) -> Dict[str, Any]:
        """获取配置"""
        return self.settings
    
    def get_logger(self):
        """获取日志器"""
        return self.logger
    
    def get_performance_manager(self):
        """获取性能管理器"""
        return self.performance_manager
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.performance_manager:
                try:
                    self.performance_manager.stop_monitoring()
                except KeyboardInterrupt:
                    # 在退出阶段被用户中断时，跳过等待，继续退出
                    self.logger.warning("停止性能监控被中断，跳过等待")
                except Exception as e:
                    self.logger.error(f"停止性能监控失败: {e}")
                
            if self.logger:
                self.logger.info("应用正在关闭...")
                
        except Exception as e:
            print(f"清理资源时出错: {e}")


# 全局初始化器实例
_app_initializer = None


def get_app_initializer() -> AppInitializer:
    """获取应用初始化器实例"""
    global _app_initializer
    if _app_initializer is None:
        _app_initializer = AppInitializer()
    return _app_initializer


def initialize_application() -> bool:
    """初始化应用程序"""
    initializer = get_app_initializer()
    return initializer.initialize()