# core/settings.py
import json
import os
import base64
import logging
import shutil
import threading
import time
import secrets
import hashlib
from typing import Dict, Any, Optional, Callable
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
from pathlib import Path

# 配置文件路径
BASE_DIR = Path(__file__).resolve().parent.parent
# 将所有配置文件路径固定到应用根目录，避免因工作目录不同而回退默认
SETTINGS_FILE = str(BASE_DIR / "settings.json")
SETTINGS_BACKUP_FILE = str(BASE_DIR / "settings.json.backup")
SETTINGS_TEMP_FILE = str(BASE_DIR / "settings.json.tmp")
UNIFIED_CONFIG_FILE = str(BASE_DIR / "unified_config.json")

# 是否使用统一配置文件
USE_UNIFIED_CONFIG = os.path.exists(UNIFIED_CONFIG_FILE)

# 安全的密钥派生参数
_SALT = b"XuanWu_OCR_Tool_2024_Security_Salt"
_ITERATIONS = 100000  # PBKDF2迭代次数
_KEY_LENGTH = 32  # AES-256密钥长度

# 从固定密码派生密钥（实际应用中应使用用户密码或更安全的方式）
_MASTER_PASSWORD = b"XuanWu_OCR_Master_Key_2024"
_AES_KEY = PBKDF2(_MASTER_PASSWORD, _SALT, _KEY_LENGTH, count=_ITERATIONS)

# 配置热重载相关
_settings_cache: Optional[Dict[str, Any]] = None
_settings_mtime: float = 0
_settings_lock = threading.RLock()
_reload_callbacks: list[Callable[[Dict[str, Any]], None]] = []

def secure_zero_memory(data: bytearray) -> None:
    """安全地清零内存中的敏感数据
    
    Args:
        data: 要清零的字节数组
    """
    if isinstance(data, bytearray):
        for i in range(len(data)):
            data[i] = 0

def generate_secure_key() -> bytes:
    """生成安全的随机密钥
    
    Returns:
        32字节的随机密钥
    """
    return secrets.token_bytes(32)

def hash_sensitive_data(data: str) -> str:
    """对敏感数据进行哈希处理（用于日志记录等）
    
    Args:
        data: 敏感数据字符串
        
    Returns:
        SHA-256哈希值的前8位（用于标识）
    """
    if not data:
        return "<empty>"
    return hashlib.sha256(data.encode('utf-8')).hexdigest()[:8] + "..."

def decrypt_api_data(enc_data: bytes) -> Dict[str, Any]:
    """解密API数据，支持新旧加密格式
    
    Args:
        enc_data: 加密的字节数据
        
    Returns:
        解密后的字典数据，失败时返回空字典
        
    Raises:
        不会抛出异常，失败时返回空字典
    """
    try:
        if not isinstance(enc_data, bytes):
            return {}
            
        encrypted = base64.b64decode(enc_data)
        
        # 检查是否为新格式（包含版本标识和IV）
        if encrypted.startswith(b'V2:'):
            # 新格式：V2:IV(16字节)+加密数据
            iv = encrypted[3:19]  # 跳过"V2:"标识，取16字节IV
            ciphertext = encrypted[19:]
            
            cipher = AES.new(_AES_KEY, AES.MODE_CBC, iv)
            decrypted = cipher.decrypt(ciphertext)
            
            # PKCS7填充移除
            pad_len = decrypted[-1]
            if pad_len > 16 or pad_len == 0:
                raise ValueError("无效的填充")
            decrypted = decrypted[:-pad_len]
            
        else:
            # 旧格式兼容（使用固定IV）
            old_iv = b"4M1vB@kjPS02e!F#"
            old_key = b"4M1vB@kjPS02e!F#"
            cipher = AES.new(old_key, AES.MODE_CBC, old_iv)
            decrypted = cipher.decrypt(encrypted)
            pad_len = decrypted[-1]
            decrypted = decrypted[:-pad_len]
            
        return json.loads(decrypted.decode("utf-8"))
        
    except Exception as e:
        logging.warning(f"解密API数据失败: {e}")
        return {}

def encrypt_api_data(data: Dict[str, Any]) -> bytes:
    """使用增强安全性加密API数据
    
    Args:
        data: 要加密的字典数据
        
    Returns:
        加密后的base64编码字节数据（新格式：V2:IV+密文）
        
    Raises:
        ValueError: 如果输入数据无效
        Exception: 加密过程中的其他错误
    """
    if not isinstance(data, dict):
        raise ValueError("输入数据必须是字典类型")
        
    try:
        # 序列化数据
        raw = json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode("utf-8")
        
        # PKCS7填充
        pad_len = 16 - (len(raw) % 16)
        raw += bytes([pad_len]) * pad_len
        
        # 生成随机IV
        iv = get_random_bytes(16)
        
        # 使用AES-256-CBC加密
        cipher = AES.new(_AES_KEY, AES.MODE_CBC, iv)
        encrypted = cipher.encrypt(raw)
        
        # 新格式：版本标识 + IV + 密文
        result = b'V2:' + iv + encrypted
        
        return base64.b64encode(result)
        
    except Exception as e:
        logging.error(f"加密API数据失败: {e}")
        raise

# ✅ 默认设置，包含原始设定和所有通用设置面板字段
DEFAULT_SETTINGS = {
    # ========== 原始基础字段 ==========
    "interval": 1.0,  # 截图/识别间隔时间（单位：秒）
    "region": None,  # 默认截图区域（None 表示未设置）
    "beep_path": "assets/7499.wav",  # 识别成功后提示音路径
    "match_mode": "exact",  # 匹配模式（exact 精确匹配 / fuzzy 模糊匹配）
    "fuzzy_threshold": 0.85,  # 模糊匹配阈值（仅在模糊模式下使用）
    "ocr_version": "general",  # OCR版本（例如：通用、精度、极速）

    # ========== 通用设置模块（UI 设置面板） ==========

    # 功能开关类
    "enable_desktop_notify": False,  # 是否启用桌面通知
    "enable_error_popup": True,  # 是否启用错误弹窗提示
    "email_notify_enabled": False,  # 是否启用邮件通知
    "auto_backup_log": False,  # 是否启用自动备份日志
    "auto_upload_log": False,  # 是否启用自动上传日志
    "log_server_url": "https://httpbin.org/post",  # 日志服务器地址
    "cloud_sync_enabled": False,  # 是否启用云同步
    "proxy_enabled": False,  # 是否启用代理

    # 邮件通知配置
    "email_smtp_server": "",  # SMTP服务器地址
    "email_smtp_port": 587,  # SMTP端口
    "email_account": "",  # 邮箱账号
    "email_password": "",  # 邮箱密码
    "email_use_ssl": False,  # 是否使用SSL
    "email_use_tls": True,  # 是否使用TLS

    # 外观与语言
    "theme": "浅色",  # 主题（浅色/深色）
    "font_size": 9,  # 字体大小
    "language": "简体中文",  # 界面语言

    # 日志相关配置
    "log_level": "INFO",  # 日志等级（DEBUG/INFO/WARNING/ERROR）
    "max_log_size": 10,  # 日志文件最大大小（单位：MB）
    "log_backup_count": 5,  # 日志备份文件个数

    # 存储 & 路径
    "default_save_path": "",  # 默认数据导出/保存路径
    "external_hook_path": "",  # 外部工具脚本钩子路径

    # 快捷键 & 启动
    "shortcut_key": "Ctrl+Shift+S",  # 启动/截图快捷键（默认组合键）
    # 热键高级配置
    "global_hotkeys_enabled": True,  # 是否启用全局快捷键批量注册
    "hotkey_conflict_detection": True,  # 是否进行常见冲突检测提示
    "enabled_hotkeys": {
        "region_select": True,
        "fullscreen_ocr": True,
        "clipboard_ocr": True,
        "quick_ocr": True,
        "open_settings": True,
        "toggle_visibility": True,
        "always_on_top": True,
        "open_history": True,
        "perf_panel": True,
        "help_window": True,
        "help_batch": True,
        "refresh_ui": True,
        "minimize_tray": True,
        "close_tab": True
    },
    "custom_hotkeys": {
        "region_select": "Ctrl+F2",
        "fullscreen_ocr": "Ctrl+F3",
        "clipboard_ocr": ["F3", "Ctrl+Shift+V"],
        "quick_ocr": "Ctrl+Shift+C",
        "open_settings": "Ctrl+,",
        "toggle_visibility": "Ctrl+Alt+H",
        "always_on_top": "Ctrl+T",
        "open_history": "Ctrl+Shift+H",
        "perf_panel": "Ctrl+P",
        "help_window": "F1",
        "help_batch": "Ctrl+B",
        "refresh_ui": "F5",
        "minimize_tray": "Ctrl+M",
        "close_tab": "Ctrl+W"
    },
    "startup_password": "",  # 启动密码（为空则不启用）

    # 网络 & 连接
    "proxy_host": "",  # 代理主机地址
    "proxy_port": 1080,  # 代理端口
    "proxy_user": "",  # 代理用户名
    "proxy_password": "",  # 代理密码
    "timeout_seconds": 30,  # 连接超时（秒）
    "retry_attempts": 3,  # 重试次数

    # 历史记录管理
    "auto_clear_history_days": 30,  # 自动清除历史记录的天数（0 表示不清除）
    "auto_clear_history": False,  # 是否自动清除历史记录
    "auto_theme": True,  # 是否自动主题
    "desktop_notify": True,  # 桌面通知（兼容字段）
    "error_popup": True,  # 错误弹窗（兼容字段）
    "email_notify": False,  # 邮件通知（兼容字段）
    "cache_size": 100,  # 缓存大小
    "cache_size_mb": 100,  # 缓存大小（MB）
    "enable_external_hook": False,  # 是否启用外部钩子
    "connection_timeout": 10,  # 连接超时
    "retry_count": 3,  # 重试次数
    "auto_upload": False,  # 自动上传
    "cloud_account": "",  # 云账户
    "cloud_token": "",  # 云令牌
    "enable_startup_password": False,  # 是否启用启动密码
    "password_max_attempts": 3,  # 密码最大尝试次数
    "password_lockout_duration": 300,  # 密码锁定时长
    "password_min_length": 6,  # 密码最小长度
    "password_require_special": False,  # 密码是否需要特殊字符
    "password_require_number": False,  # 密码是否需要数字
    "password_require_uppercase": False,  # 密码是否需要大写字母

    # 备份配置
    "backup": {
        "auto_backup": False,  # 自动备份
        "backup_interval": 24,  # 备份间隔（小时）
        "max_backups": 10,  # 最大备份数
        "backup_logs": True,  # 备份日志
        "backup_screenshots": True,  # 备份截图
        "backup_settings": True,  # 备份设置
        "backup_keywords": True  # 备份关键词
    },

    # 启动密码安全设置
    "startup_password_max_attempts": 3,  # 启动密码最大尝试次数
    "startup_password_lockout_time": 5,  # 启动密码锁定时间
    "startup_password_log_attempts": True,  # 记录启动密码尝试
    "startup_password_auto_lock": False,  # 启动密码自动锁定

    # 邮件通知详细配置
    "email_notification_enabled": False,  # 邮件通知启用
    "smtp_server": "",  # SMTP服务器
    "smtp_port": 587,  # SMTP端口
    "use_tls": True,  # 使用TLS
    "use_ssl": False,  # 使用SSL
    "sender_email": "",  # 发送者邮箱
    "sender_password": "",  # 发送者密码
    "recipient_email": "",  # 接收者邮箱
    "notification_cooldown": 60,  # 通知冷却时间
    "notification_keywords": [],  # 通知关键词

    # 邮件模板配置
    "email_template": {
        "layout_style": "现代卡片",  # 布局样式
        "font_family": "Arial",  # 字体
        "font_size": 14,  # 字体大小
        "content_density": "紧凑",  # 内容密度
        "border_radius": 10,  # 边框圆角
        "shadow_enabled": True,  # 阴影启用
        "enabled": True  # 模板启用
    },

    # 动态主题配置
    "dynamic_theme_enabled": True,  # 动态主题启用
    "theme_scheme": "自动检测",  # 主题方案
    "theme_color": "#007bff",  # 主题颜色
    "gradient_intensity": 50,  # 渐变强度

    # AI摘要配置
    "ai_summary_enabled": True,  # AI摘要启用
    "summary_length": "中等(100字)",  # 摘要长度
    "summary_style": "正式商务",  # 摘要风格
    "highlight_keywords": True,  # 高亮关键词

    # 数据可视化配置
    "data_visualization_enabled": True,  # 数据可视化启用
    "chart_type": "柱状图",  # 图表类型
    "data_range": "最近7天",  # 数据范围
    "chart_size": "中(500x300)",  # 图表大小
    "show_data_labels": True,  # 显示数据标签

    # 多语言配置
    "multilingual_enabled": True,  # 多语言启用
    "default_language": "中文(简体)",  # 默认语言
    "auto_detect_language": True,  # 自动检测语言
    "translation_service": "谷歌翻译",  # 翻译服务

    # 交互元素配置
    "interactive_elements_enabled": True,  # 交互元素启用
    "button_style": "现代扁平",  # 按钮样式
    "quick_reply": True,  # 快速回复
    "action_buttons": True,  # 操作按钮
    "feedback_buttons": True,  # 反馈按钮
    "button_color": "#28a745",  # 按钮颜色

    # 模板个性化配置
    "template_personalization_enabled": True,  # 模板个性化启用
    "last_notification_time": 0,  # 最后通知时间
    "language_code": "zh_CN",  # 语言代码

    # 最近语言列表（供语言面板使用）
    "recent_languages": [],

    # 开发工具调试状态（替代 debug_config.json）
    "debug_config": {
        "enabled": False,
        "session_history": [],
        "last_session_id": None
    },

    # 自动刷新配置
    "auto_refresh": {
        "enabled": True,  # 自动刷新启用
        "interval": 10  # 刷新间隔
    },

    # 远程调试配置
    "remote_debug": {
        "host": "127.0.0.1",  # 主机地址
        "port": 9009,  # 端口
        "password": "xuanwu",  # 密码
        "max_clients": 10,  # 最大客户端数
        "timeout": 30,  # 超时时间
        "enable_auth": True,  # 启用认证
        "auth_token": "",  # 认证令牌
        "enable_ssl": True,  # 启用SSL
        "ssl_cert_path": "ssl\\ssl_cert.pem",  # SSL证书路径
        "ssl_key_path": "ssl\\ssl_key.pem",  # SSL密钥路径
        "log_level": "全部",  # 日志级别
        "auto_start": False,  # 自动启动
        "enable_web_interface": True,  # 启用Web界面
        "web_host": "127.0.0.1",  # Web主机
        "web_port": 8080,  # Web端口
        "websocket_port": 8081,  # WebSocket端口
        "web_static_dir": "web_static",  # Web静态目录
        "enable_websocket": True,  # 启用WebSocket
        "web_auth_required": True,  # Web认证必需
        "connection_pool_size": 50,  # 连接池大小
        "message_buffer_size": 100,  # 消息缓冲区大小
        "log_cache_size": 1000,  # 日志缓存大小
        "thread_pool_size": 5,  # 线程池大小
        "update_interval": 1000,  # 更新间隔
        "plugin_dir": "plugins",  # 插件目录
        "script_dir": "scripts",  # 脚本目录
        "transfer_dir": "transfers",  # 传输目录
        "session_dir": "sessions",  # 会话目录
        "enabled_features": [  # 启用的功能
            "plugin_system",
            "basic_debug",
            "session_manager",
            "advanced_tools",
            "file_transfer",
            "script_executor",
            "performance_opt"
        ],
        "auto_scroll": True  # 自动滚动
    },

    # 远程调试自动滚动（兼容字段）
    "remote_debug.auto_scroll": True
}


def register_settings_callback(callback: Callable[[Dict[str, Any]], None]):
    """注册配置变更回调函数"""
    with _settings_lock:
        _reload_callbacks.append(callback)

def _create_backup():
    """创建配置文件备份"""
    if os.path.exists(SETTINGS_FILE):
        try:
            shutil.copy2(SETTINGS_FILE, SETTINGS_BACKUP_FILE)
            logging.debug("配置文件备份创建成功")
        except Exception as e:
            logging.warning(f"创建配置文件备份失败: {e}")

def _restore_from_backup() -> bool:
    """从备份恢复配置文件
    
    Returns:
        恢复成功返回True，否则返回False
    """
    if os.path.exists(SETTINGS_BACKUP_FILE):
        try:
            shutil.copy2(SETTINGS_BACKUP_FILE, SETTINGS_FILE)
            logging.info("从备份恢复配置文件成功")
            return True
        except Exception as e:
            logging.error(f"从备份恢复配置文件失败: {e}")
    return False

def _validate_settings(settings: Dict[str, Any]) -> bool:
    """验证配置文件的有效性"""
    if not isinstance(settings, dict):
        return False
    
    # 检查必要的字段类型
    required_fields = {
        "interval": (int, float),
        "match_mode": str,
        "fuzzy_threshold": (int, float),
        "ocr_version": str
    }
    
    for field, expected_type in required_fields.items():
        if field in settings and not isinstance(settings[field], expected_type):
            logging.warning(f"配置字段 {field} 类型错误")
            return False
    
    return True

def _notify_callbacks(settings: Dict[str, Any]) -> None:
    """通知所有注册的回调函数
    
    Args:
        settings: 配置数据字典
    """
    for callback in _reload_callbacks:
        try:
            callback(settings.copy())
        except Exception as e:
            logging.error(f"配置变更回调执行失败: {e}")

def load_settings(force_reload: bool = False) -> Dict[str, Any]:
    """加载设置，支持热重载和错误恢复"""
    global _settings_cache, _settings_mtime
    
    with _settings_lock:
        # 检查是否需要重新加载
        current_mtime = 0
        config_file = UNIFIED_CONFIG_FILE if USE_UNIFIED_CONFIG else SETTINGS_FILE
        
        if os.path.exists(config_file):
            current_mtime = os.path.getmtime(config_file)
        
        if not force_reload and _settings_cache is not None and current_mtime == _settings_mtime:
            return _settings_cache.copy()
        
        # 如果配置文件不存在，创建默认配置
        if not os.path.exists(config_file):
            logging.info(f"{config_file} 不存在，创建默认设置")
            if USE_UNIFIED_CONFIG:
                # 创建统一配置文件
                unified_config = {"settings": DEFAULT_SETTINGS.copy()}
                try:
                    with open(UNIFIED_CONFIG_FILE, "w", encoding="utf-8") as f:
                        json.dump(unified_config, f, indent=4, ensure_ascii=False)
                except Exception as e:
                    logging.error(f"创建统一配置文件失败: {e}")
            else:
                save_settings(DEFAULT_SETTINGS)
            
            _settings_cache = DEFAULT_SETTINGS.copy()
            _settings_mtime = os.path.getmtime(config_file) if os.path.exists(config_file) else 0
            return _settings_cache.copy()
        
        # 尝试加载配置文件
        settings = None
        try:
            if USE_UNIFIED_CONFIG:
                with open(UNIFIED_CONFIG_FILE, "r", encoding="utf-8") as f:
                    unified_config = json.load(f)
                    settings = unified_config.get("settings", {})
            else:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            
            # 验证配置文件
            if not _validate_settings(settings):
                raise ValueError("配置文件验证失败")
                
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            
            # 尝试从备份恢复 (仅适用于非统一配置)
            if not USE_UNIFIED_CONFIG and _restore_from_backup():
                try:
                    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                        settings = json.load(f)
                    if not _validate_settings(settings):
                        raise ValueError("备份配置文件验证失败")
                    logging.info("成功从备份恢复配置")
                except Exception as backup_e:
                    logging.error(f"备份恢复也失败: {backup_e}")
                    settings = None
            
            # 如果备份也失败，使用默认配置
            if settings is None:
                logging.warning("使用默认配置")
                settings = DEFAULT_SETTINGS.copy()
                if USE_UNIFIED_CONFIG:
                    unified_config = {"settings": settings}
                    try:
                        with open(UNIFIED_CONFIG_FILE, "w", encoding="utf-8") as f:
                            json.dump(unified_config, f, indent=4, ensure_ascii=False)
                    except Exception as e:
                        logging.error(f"保存统一配置文件失败: {e}")
                else:
                    save_settings(settings)
        
        # 补全缺失的字段
        updated = False
        for key, default_value in DEFAULT_SETTINGS.items():
            if key not in settings:
                settings[key] = default_value
                updated = True
                logging.info(f"补全缺失配置字段: {key}")
        
        # 如果有更新，保存配置
        if updated:
            if USE_UNIFIED_CONFIG:
                unified_config = {"settings": settings}
                try:
                    with open(UNIFIED_CONFIG_FILE, "w", encoding="utf-8") as f:
                        json.dump(unified_config, f, indent=4, ensure_ascii=False)
                except Exception as e:
                    logging.error(f"更新统一配置文件失败: {e}")
            else:
                save_settings(settings)
        
        # 更新缓存
        old_settings = _settings_cache
        _settings_cache = settings.copy()
        _settings_mtime = current_mtime
        
        # 如果配置有变化，通知回调
        if old_settings != _settings_cache:
            _notify_callbacks(_settings_cache)
        
        return _settings_cache.copy()

def load_settings_legacy() -> Dict[str, Any]:
    """原始的加载设置方法（保持向后兼容）
    
    Returns:
        配置数据字典
    """
    if not os.path.exists(SETTINGS_FILE):
        logging.info("settings.json 不存在，创建默认设置")
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)

        # 补全缺失字段（适用于旧版本升级）
        updated = False
        for key, default_value in DEFAULT_SETTINGS.items():
            if key not in settings:
                settings[key] = default_value
                updated = True

        if updated:
            save_settings(settings)

        return settings
    except Exception as e:
        logging.exception("加载设置文件失败，恢复默认设置")
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

def save_settings(settings: Dict[str, Any], create_backup: bool = True) -> bool:
    """安全保存设置到文件，支持原子写入和备份
    
    如果使用统一配置文件，则更新unified_config.json中的settings部分
    否则将设置保存到settings.json文件，并创建备份。
    
    Args:
        settings: 要保存的设置字典
        create_backup: 是否创建备份文件
        
    Returns:
        bool: 保存是否成功
    """
    global _settings_cache, _settings_mtime
    
    # 使用统一配置文件
    if USE_UNIFIED_CONFIG:
        try:
            # 读取当前统一配置
            unified_config = {}
            if os.path.exists(UNIFIED_CONFIG_FILE):
                with open(UNIFIED_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    unified_config = json.load(f)
            
            # 更新settings部分
            unified_config['settings'] = settings
            
            # 保存统一配置
            with open(UNIFIED_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(unified_config, f, indent=4, ensure_ascii=False)
            
            # 更新缓存
            with _settings_lock:
                _settings_cache = settings.copy()
                _settings_mtime = os.path.getmtime(UNIFIED_CONFIG_FILE)
            
            # 触发回调
            _notify_callbacks(settings)
            
            logging.debug("设置已安全保存到统一配置文件")
            return True
        except Exception as e:
            logging.error(f"保存统一配置失败: {e}")
            return False
    
    # 使用传统配置文件
    try:
        # 创建备份（如果需要）
        if create_backup:
            _create_backup()
        
        # 原子写入：先写入临时文件，然后重命名
        with open(SETTINGS_TEMP_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        
        # 验证临时文件
        try:
            with open(SETTINGS_TEMP_FILE, "r", encoding="utf-8") as f:
                test_settings = json.load(f)
            if not _validate_settings(test_settings):
                raise ValueError("保存的配置文件验证失败")
        except Exception as e:
            os.remove(SETTINGS_TEMP_FILE)
            raise e
        
        # 原子替换
        if os.path.exists(SETTINGS_FILE):
            if os.name == 'nt':  # Windows
                os.replace(SETTINGS_TEMP_FILE, SETTINGS_FILE)
            else:  # Unix-like
                os.rename(SETTINGS_TEMP_FILE, SETTINGS_FILE)
        else:
            os.rename(SETTINGS_TEMP_FILE, SETTINGS_FILE)
        
        # 更新缓存
        with _settings_lock:
            _settings_cache = settings.copy()
            _settings_mtime = os.path.getmtime(SETTINGS_FILE)
        
        # 触发回调
        _notify_callbacks(settings)
        
        logging.debug("设置已安全保存")
        return True
        
    except Exception as e:
        logging.error(f"保存设置失败: {e}")
        # 清理临时文件
        if os.path.exists(SETTINGS_TEMP_FILE):
            try:
                os.remove(SETTINGS_TEMP_FILE)
            except:
                pass
        return False

def get_default_settings() -> Dict[str, Any]:
    """获取默认设置
    
    Returns:
        默认设置字典
    """
    return DEFAULT_SETTINGS.copy()

def save_settings_legacy(settings):
    """原始的保存设置方法（保持向后兼容）"""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.exception("保存设置失败")
