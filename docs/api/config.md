# 配置管理 API

配置管理系统提供了 XuanWu OCR 应用程序的所有配置选项，包括OCR设置、界面配置、热键设置等。

## 📋 配置分类

- [OCR 配置](#ocr-配置)
- [界面配置](#界面配置)
- [热键配置](#热键配置)
- [性能配置](#性能配置)
- [日志配置](#日志配置)
- [主题配置](#主题配置)
- [语言配置](#语言配置)
- [高级配置](#高级配置)

---

## 配置文件结构

配置文件采用JSON格式存储，位于 `config/settings.json`：

```json
{
    "ocr": {
        "engine": "paddleocr",
        "language": "ch",
        "confidence_threshold": 0.8,
        "preprocessing": true
    },
    "ui": {
        "theme": "dark",
        "font_family": "Microsoft YaHei",
        "font_size": 12,
        "always_on_top": false
    },
    "hotkeys": {
        "capture_screen": "ctrl+shift+s",
        "toggle_window": "ctrl+shift+x",
        "quick_ocr": "ctrl+shift+q"
    },
    "performance": {
        "max_threads": 4,
        "cache_size": 100,
        "auto_cleanup": true
    }
}
```

---

## OCR 配置

### 基础设置

```python
from core.settings import load_settings, save_settings

# 加载配置
settings = load_settings()

# OCR引擎设置
settings["ocr"]["engine"] = "paddleocr"  # "tesseract", "paddleocr", "easyocr"
settings["ocr"]["language"] = "ch"       # "ch", "en", "japan", "korean"
settings["ocr"]["confidence_threshold"] = 0.8  # 置信度阈值 (0.0-1.0)

# 保存配置
save_settings(settings)
```

### 支持的OCR引擎

| 引擎 | 描述 | 优势 | 适用场景 |
|------|------|------|----------|
| `tesseract` | Google开源OCR引擎 | 成熟稳定，支持多语言 | 通用文本识别 |
| `paddleocr` | 百度PaddlePaddle OCR | 中文识别效果好 | 中文文档处理 |
| `easyocr` | 轻量级OCR引擎 | 安装简单，速度快 | 快速识别场景 |

### 语言支持

```python
# 支持的语言代码
SUPPORTED_LANGUAGES = {
    "ch": "中文简体",
    "cht": "中文繁体", 
    "en": "英语",
    "japan": "日语",
    "korean": "韩语",
    "german": "德语",
    "french": "法语",
    "spanish": "西班牙语"
}

# 设置识别语言
settings["ocr"]["language"] = "ch"
```

### 预处理选项

```python
# 图像预处理设置
settings["ocr"]["preprocessing"] = {
    "enabled": True,
    "denoise": True,          # 降噪
    "deskew": True,           # 倾斜校正
    "enhance_contrast": True, # 增强对比度
    "binarization": False     # 二值化
}

# 识别区域设置
settings["ocr"]["detection"] = {
    "min_text_size": 10,      # 最小文本尺寸
    "max_text_size": 1000,    # 最大文本尺寸
    "text_direction": "auto"  # 文本方向: "auto", "horizontal", "vertical"
}
```

---

## 界面配置

### 主题设置

```python
# 主题配置
settings["ui"]["theme"] = {
    "name": "dark",           # 主题名称
    "custom_colors": {
        "primary": "#0078d4",
        "secondary": "#6c757d",
        "success": "#28a745",
        "warning": "#ffc107",
        "danger": "#dc3545"
    }
}

# 可用主题
AVAILABLE_THEMES = [
    "light",    # 浅色主题
    "dark",     # 深色主题
    "auto",     # 跟随系统
    "custom"    # 自定义主题
]
```

### 字体设置

```python
# 字体配置
settings["ui"]["font"] = {
    "family": "Microsoft YaHei",  # 字体族
    "size": 12,                   # 字体大小
    "weight": "normal",           # 字体粗细: "normal", "bold"
    "style": "normal"             # 字体样式: "normal", "italic"
}

# 系统字体检测
from PyQt6.QtGui import QFontDatabase

def get_available_fonts():
    """获取系统可用字体"""
    db = QFontDatabase()
    return db.families()
```

### 窗口设置

```python
# 窗口配置
settings["ui"]["window"] = {
    "always_on_top": False,       # 窗口置顶
    "start_minimized": False,     # 启动时最小化
    "remember_position": True,    # 记住窗口位置
    "remember_size": True,        # 记住窗口大小
    "opacity": 1.0,              # 窗口透明度 (0.0-1.0)
    "position": {"x": 100, "y": 100},
    "size": {"width": 800, "height": 600}
}
```

### 界面布局

```python
# 布局配置
settings["ui"]["layout"] = {
    "toolbar_visible": True,      # 工具栏可见
    "statusbar_visible": True,    # 状态栏可见
    "sidebar_visible": True,      # 侧边栏可见
    "sidebar_width": 250,         # 侧边栏宽度
    "panel_positions": {          # 面板位置
        "history": "right",
        "settings": "center",
        "tools": "bottom"
    }
}
```

---

## 热键配置

### 全局热键

```python
# 热键配置
settings["hotkeys"] = {
    "capture_screen": "ctrl+shift+s",      # 屏幕截图
    "capture_window": "ctrl+shift+w",      # 窗口截图
    "capture_region": "ctrl+shift+r",      # 区域截图
    "toggle_window": "ctrl+shift+x",       # 切换窗口显示
    "quick_ocr": "ctrl+shift+q",          # 快速OCR
    "show_history": "ctrl+shift+h",        # 显示历史记录
    "show_settings": "ctrl+comma"          # 显示设置
}
```

### 热键格式

```python
# 热键组合格式
HOTKEY_MODIFIERS = {
    "ctrl": "Ctrl",
    "alt": "Alt", 
    "shift": "Shift",
    "win": "Win",
    "cmd": "Cmd"  # macOS
}

# 特殊键
SPECIAL_KEYS = {
    "space": "Space",
    "tab": "Tab",
    "enter": "Return",
    "esc": "Escape",
    "f1": "F1", "f2": "F2", # ... f12
    "up": "Up", "down": "Down",
    "left": "Left", "right": "Right"
}

# 热键验证
def validate_hotkey(hotkey_str):
    """验证热键格式是否正确"""
    parts = hotkey_str.lower().split('+')
    if len(parts) < 2:
        return False
    
    modifiers = parts[:-1]
    key = parts[-1]
    
    # 验证修饰键
    for mod in modifiers:
        if mod not in HOTKEY_MODIFIERS:
            return False
    
    # 验证主键
    if key not in SPECIAL_KEYS and len(key) != 1:
        return False
    
    return True
```

### 热键冲突检测

```python
def check_hotkey_conflicts(new_hotkey, existing_hotkeys):
    """检查热键冲突"""
    conflicts = []
    for name, hotkey in existing_hotkeys.items():
        if hotkey == new_hotkey:
            conflicts.append(name)
    return conflicts

# 使用示例
conflicts = check_hotkey_conflicts("ctrl+shift+s", settings["hotkeys"])
if conflicts:
    print(f"热键冲突: {conflicts}")
```

---

## 性能配置

### 线程设置

```python
# 性能配置
settings["performance"] = {
    "max_threads": 4,             # 最大线程数
    "thread_pool_size": 8,        # 线程池大小
    "ocr_timeout": 30,            # OCR超时时间(秒)
    "image_max_size": 4096,       # 图像最大尺寸
    "memory_limit": 512           # 内存限制(MB)
}
```

### 缓存设置

```python
# 缓存配置
settings["performance"]["cache"] = {
    "enabled": True,              # 启用缓存
    "size": 100,                  # 缓存大小(MB)
    "ttl": 3600,                  # 缓存生存时间(秒)
    "auto_cleanup": True,         # 自动清理
    "cleanup_interval": 300       # 清理间隔(秒)
}
```

### 优化选项

```python
# 优化设置
settings["performance"]["optimization"] = {
    "gpu_acceleration": False,    # GPU加速
    "parallel_processing": True,  # 并行处理
    "image_compression": True,    # 图像压缩
    "result_compression": False,  # 结果压缩
    "lazy_loading": True         # 延迟加载
}
```

---

## 日志配置

### 日志级别

```python
# 日志配置
settings["logging"] = {
    "level": "INFO",              # 日志级别
    "file_enabled": True,         # 文件日志
    "console_enabled": True,      # 控制台日志
    "max_file_size": 10,          # 最大文件大小(MB)
    "backup_count": 5,            # 备份文件数量
    "format": "detailed"          # 日志格式
}

# 日志级别
LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50
}
```

### 日志格式

```python
# 日志格式配置
LOG_FORMATS = {
    "simple": "%(levelname)s - %(message)s",
    "standard": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "detailed": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    "json": '{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
}

settings["logging"]["format"] = "detailed"
```

### 日志过滤

```python
# 日志过滤配置
settings["logging"]["filters"] = {
    "exclude_modules": [          # 排除的模块
        "urllib3.connectionpool",
        "PIL.PngImagePlugin"
    ],
    "include_only": [],           # 仅包含的模块
    "min_level_by_module": {      # 按模块设置最小级别
        "core.ocr_worker": "DEBUG",
        "widgets.main_window": "INFO"
    }
}
```

---

## 主题配置

### 内置主题

```python
# 主题定义
THEMES = {
    "light": {
        "name": "浅色主题",
        "colors": {
            "background": "#ffffff",
            "foreground": "#000000",
            "primary": "#0078d4",
            "secondary": "#6c757d",
            "accent": "#0078d4",
            "border": "#dee2e6",
            "hover": "#f8f9fa",
            "selected": "#e3f2fd"
        }
    },
    "dark": {
        "name": "深色主题", 
        "colors": {
            "background": "#2b2b2b",
            "foreground": "#ffffff",
            "primary": "#0078d4",
            "secondary": "#6c757d",
            "accent": "#00bcf2",
            "border": "#404040",
            "hover": "#3c3c3c",
            "selected": "#0078d4"
        }
    }
}
```

### 自定义主题

```python
# 创建自定义主题
def create_custom_theme(name, colors):
    """创建自定义主题"""
    theme = {
        "name": name,
        "colors": colors,
        "custom": True
    }
    
    # 保存到配置
    settings["ui"]["themes"][name] = theme
    save_settings(settings)
    
    return theme

# 使用示例
custom_colors = {
    "background": "#1e1e1e",
    "foreground": "#d4d4d4",
    "primary": "#007acc",
    "secondary": "#6c757d",
    "accent": "#00bcf2",
    "border": "#3c3c3c",
    "hover": "#2d2d30",
    "selected": "#094771"
}

create_custom_theme("vs_code_dark", custom_colors)
```

---

## 语言配置

### 多语言支持

```python
# 语言配置
settings["language"] = {
    "current": "zh_CN",           # 当前语言
    "fallback": "en_US",          # 备用语言
    "auto_detect": True,          # 自动检测系统语言
    "date_format": "yyyy-MM-dd",  # 日期格式
    "time_format": "HH:mm:ss",    # 时间格式
    "number_format": "1,234.56"   # 数字格式
}

# 支持的语言
SUPPORTED_LANGUAGES = {
    "zh_CN": {"name": "简体中文", "flag": "🇨🇳"},
    "zh_TW": {"name": "繁體中文", "flag": "🇹🇼"},
    "en_US": {"name": "English", "flag": "🇺🇸"},
    "ja_JP": {"name": "日本語", "flag": "🇯🇵"},
    "ko_KR": {"name": "한국어", "flag": "🇰🇷"}
}
```

### 本地化设置

```python
# 本地化配置
settings["localization"] = {
    "currency": "CNY",            # 货币代码
    "timezone": "Asia/Shanghai",  # 时区
    "first_day_of_week": 1,      # 一周的第一天 (0=周日, 1=周一)
    "measurement_system": "metric" # 度量系统: "metric", "imperial"
}
```

---

## 高级配置

### 调试选项

```python
# 调试配置
settings["debug"] = {
    "enabled": False,             # 启用调试模式
    "verbose_logging": False,     # 详细日志
    "show_fps": False,           # 显示FPS
    "memory_profiling": False,    # 内存分析
    "performance_metrics": False, # 性能指标
    "crash_reporting": True      # 崩溃报告
}
```

### 实验性功能

```python
# 实验性功能
settings["experimental"] = {
    "ai_enhancement": False,      # AI增强
    "batch_processing": False,    # 批量处理
    "cloud_sync": False,         # 云同步
    "plugin_system": False,      # 插件系统
    "advanced_ocr": False        # 高级OCR
}
```

### 安全设置

```python
# 安全配置
settings["security"] = {
    "auto_save_screenshots": True,    # 自动保存截图
    "encrypt_logs": False,           # 加密日志
    "secure_deletion": False,        # 安全删除
    "privacy_mode": False,           # 隐私模式
    "data_retention_days": 30        # 数据保留天数
}
```

---

## 配置验证

### 验证函数

```python
def validate_config(config):
    """验证配置有效性"""
    errors = []
    
    # 验证OCR配置
    if "ocr" in config:
        ocr_config = config["ocr"]
        
        # 验证引擎
        if ocr_config.get("engine") not in ["tesseract", "paddleocr", "easyocr"]:
            errors.append("无效的OCR引擎")
        
        # 验证置信度阈值
        threshold = ocr_config.get("confidence_threshold", 0.8)
        if not 0.0 <= threshold <= 1.0:
            errors.append("置信度阈值必须在0.0-1.0之间")
    
    # 验证热键配置
    if "hotkeys" in config:
        for name, hotkey in config["hotkeys"].items():
            if not validate_hotkey(hotkey):
                errors.append(f"无效的热键格式: {name} = {hotkey}")
    
    return errors

# 使用示例
errors = validate_config(settings)
if errors:
    print("配置验证失败:")
    for error in errors:
        print(f"  - {error}")
```

### 配置迁移

```python
def migrate_config(old_config, target_version):
    """配置版本迁移"""
    current_version = old_config.get("version", "1.0.0")
    
    if current_version < "2.0.0":
        # 迁移到2.0.0版本
        if "ocr_engine" in old_config:
            old_config["ocr"] = {"engine": old_config.pop("ocr_engine")}
    
    if current_version < "2.1.9":
        # 迁移到2.1.9版本
        if "theme" in old_config:
            old_config["ui"] = {"theme": old_config.pop("theme")}
    
    old_config["version"] = target_version
    return old_config
```

---

## 🔗 相关文档

- [API 概览](overview.md) - API 总体介绍
- [核心模块 API](core.md) - 核心功能API文档
- [界面组件 API](widgets.md) - 界面组件API文档
- [用户手册](../user-guide/configuration.md) - 配置使用指南

---

*下一步：查看 [用户手册](../user-guide/README.md) 了解如何使用这些配置选项*