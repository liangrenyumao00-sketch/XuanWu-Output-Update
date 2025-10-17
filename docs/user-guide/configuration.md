# 配置参数详细说明

XuanWu OCR 提供了丰富的配置选项，允许用户根据自己的需求定制软件的行为和外观。本文档详细介绍了所有可用的配置参数。

## 📋 配置文件位置

配置文件存储在以下位置：

- **Windows**: `%APPDATA%\XuanWu OCR\config\settings.json`
- **macOS**: `~/Library/Application Support/XuanWu OCR/config/settings.json`
- **Linux**: `~/.config/XuanWu OCR/config/settings.json`

## 🔧 配置参数分类

### 1. OCR 识别配置

#### 1.1 基础引擎设置

```json
{
  "ocr": {
    "engine": "paddleocr",
    "language": "ch",
    "confidence_threshold": 0.8,
    "max_image_size": 4096,
    "timeout": 30
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `engine` | string | "paddleocr" | OCR引擎类型：`tesseract`、`paddleocr`、`easyocr` |
| `language` | string | "ch" | 识别语言代码 |
| `confidence_threshold` | float | 0.8 | 置信度阈值，范围 0.0-1.0 |
| `max_image_size` | int | 4096 | 最大图像尺寸（像素） |
| `timeout` | int | 30 | 识别超时时间（秒） |

#### 1.2 语言支持

```json
{
  "ocr": {
    "supported_languages": {
      "ch": "中文简体",
      "cht": "中文繁体",
      "en": "English",
      "japan": "日本語",
      "korean": "한국어",
      "german": "Deutsch",
      "french": "Français",
      "spanish": "Español",
      "russian": "Русский",
      "arabic": "العربية"
    },
    "multi_language": false,
    "language_detection": true
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `multi_language` | boolean | false | 是否启用多语言混合识别 |
| `language_detection` | boolean | true | 是否启用自动语言检测 |

#### 1.3 图像预处理

```json
{
  "ocr": {
    "preprocessing": {
      "enabled": true,
      "denoise": true,
      "deskew": true,
      "enhance_contrast": true,
      "binarization": false,
      "resize_factor": 1.0,
      "blur_removal": false
    }
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | boolean | true | 是否启用预处理 |
| `denoise` | boolean | true | 降噪处理 |
| `deskew` | boolean | true | 倾斜校正 |
| `enhance_contrast` | boolean | true | 增强对比度 |
| `binarization` | boolean | false | 二值化处理 |
| `resize_factor` | float | 1.0 | 图像缩放因子 |
| `blur_removal` | boolean | false | 模糊去除 |

#### 1.4 文本检测

```json
{
  "ocr": {
    "detection": {
      "min_text_size": 10,
      "max_text_size": 1000,
      "text_direction": "auto",
      "merge_lines": true,
      "filter_small_text": true,
      "text_line_threshold": 0.7
    }
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `min_text_size` | int | 10 | 最小文本尺寸（像素） |
| `max_text_size` | int | 1000 | 最大文本尺寸（像素） |
| `text_direction` | string | "auto" | 文本方向：`auto`、`horizontal`、`vertical` |
| `merge_lines` | boolean | true | 是否合并文本行 |
| `filter_small_text` | boolean | true | 过滤小文本 |
| `text_line_threshold` | float | 0.7 | 文本行检测阈值 |

---

### 2. 界面配置

#### 2.1 主题设置

```json
{
  "ui": {
    "theme": {
      "name": "dark",
      "follow_system": false,
      "custom_colors": {
        "primary": "#0078d4",
        "secondary": "#6c757d",
        "success": "#28a745",
        "warning": "#ffc107",
        "danger": "#dc3545",
        "background": "#2b2b2b",
        "foreground": "#ffffff",
        "border": "#404040"
      }
    }
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | string | "dark" | 主题名称：`light`、`dark`、`auto`、`custom` |
| `follow_system` | boolean | false | 跟随系统主题 |
| `custom_colors` | object | {} | 自定义颜色配置 |

#### 2.2 字体设置

```json
{
  "ui": {
    "font": {
      "family": "Microsoft YaHei",
      "size": 12,
      "weight": "normal",
      "style": "normal",
      "anti_aliasing": true,
      "subpixel_rendering": true
    }
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `family` | string | "Microsoft YaHei" | 字体族名称 |
| `size` | int | 12 | 字体大小（磅） |
| `weight` | string | "normal" | 字体粗细：`normal`、`bold`、`light` |
| `style` | string | "normal" | 字体样式：`normal`、`italic` |
| `anti_aliasing` | boolean | true | 抗锯齿 |
| `subpixel_rendering` | boolean | true | 子像素渲染 |

#### 2.3 窗口设置

```json
{
  "ui": {
    "window": {
      "always_on_top": false,
      "start_minimized": false,
      "minimize_to_tray": true,
      "close_to_tray": true,
      "remember_position": true,
      "remember_size": true,
      "opacity": 1.0,
      "animation_enabled": true,
      "position": {"x": 100, "y": 100},
      "size": {"width": 800, "height": 600},
      "min_size": {"width": 600, "height": 400}
    }
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `always_on_top` | boolean | false | 窗口置顶 |
| `start_minimized` | boolean | false | 启动时最小化 |
| `minimize_to_tray` | boolean | true | 最小化到系统托盘 |
| `close_to_tray` | boolean | true | 关闭到系统托盘 |
| `remember_position` | boolean | true | 记住窗口位置 |
| `remember_size` | boolean | true | 记住窗口大小 |
| `opacity` | float | 1.0 | 窗口透明度（0.0-1.0） |
| `animation_enabled` | boolean | true | 启用动画效果 |

#### 2.4 布局设置

```json
{
  "ui": {
    "layout": {
      "toolbar_visible": true,
      "statusbar_visible": true,
      "sidebar_visible": true,
      "sidebar_width": 250,
      "sidebar_position": "left",
      "panel_docking": true,
      "tab_position": "top",
      "icon_size": "medium"
    }
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `toolbar_visible` | boolean | true | 工具栏可见 |
| `statusbar_visible` | boolean | true | 状态栏可见 |
| `sidebar_visible` | boolean | true | 侧边栏可见 |
| `sidebar_width` | int | 250 | 侧边栏宽度（像素） |
| `sidebar_position` | string | "left" | 侧边栏位置：`left`、`right` |
| `panel_docking` | boolean | true | 面板停靠 |
| `tab_position` | string | "top" | 标签页位置：`top`、`bottom`、`left`、`right` |
| `icon_size` | string | "medium" | 图标大小：`small`、`medium`、`large` |

---

### 3. 热键配置

#### 3.1 全局热键

```json
{
  "hotkeys": {
    "global": {
      "capture_screen": "ctrl+shift+s",
      "capture_window": "ctrl+shift+w",
      "capture_region": "ctrl+shift+r",
      "toggle_window": "ctrl+shift+x",
      "quick_ocr": "ctrl+shift+q",
      "show_history": "ctrl+shift+h",
      "show_settings": "ctrl+comma"
    }
  }
}
```

#### 3.2 应用内热键

```json
{
  "hotkeys": {
    "local": {
      "copy_result": "ctrl+c",
      "save_result": "ctrl+s",
      "clear_result": "ctrl+l",
      "zoom_in": "ctrl+plus",
      "zoom_out": "ctrl+minus",
      "reset_zoom": "ctrl+0",
      "toggle_fullscreen": "f11"
    }
  }
}
```

#### 3.3 热键设置

```json
{
  "hotkeys": {
    "settings": {
      "enabled": true,
      "global_enabled": true,
      "conflict_detection": true,
      "modifier_timeout": 1000,
      "repeat_delay": 500
    }
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | boolean | true | 启用热键 |
| `global_enabled` | boolean | true | 启用全局热键 |
| `conflict_detection` | boolean | true | 热键冲突检测 |
| `modifier_timeout` | int | 1000 | 修饰键超时时间（毫秒） |
| `repeat_delay` | int | 500 | 重复延迟时间（毫秒） |

---

### 4. 性能配置

#### 4.1 线程设置

```json
{
  "performance": {
    "threading": {
      "max_threads": 4,
      "thread_pool_size": 8,
      "ocr_worker_threads": 2,
      "io_worker_threads": 2,
      "ui_update_interval": 100
    }
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_threads` | int | 4 | 最大线程数 |
| `thread_pool_size` | int | 8 | 线程池大小 |
| `ocr_worker_threads` | int | 2 | OCR工作线程数 |
| `io_worker_threads` | int | 2 | IO工作线程数 |
| `ui_update_interval` | int | 100 | UI更新间隔（毫秒） |

#### 4.2 内存管理

```json
{
  "performance": {
    "memory": {
      "max_memory_usage": 512,
      "cache_size": 100,
      "image_cache_size": 50,
      "result_cache_size": 200,
      "auto_cleanup": true,
      "cleanup_interval": 300,
      "gc_threshold": 0.8
    }
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_memory_usage` | int | 512 | 最大内存使用量（MB） |
| `cache_size` | int | 100 | 总缓存大小（MB） |
| `image_cache_size` | int | 50 | 图像缓存大小（MB） |
| `result_cache_size` | int | 200 | 结果缓存大小（条目数） |
| `auto_cleanup` | boolean | true | 自动清理 |
| `cleanup_interval` | int | 300 | 清理间隔（秒） |
| `gc_threshold` | float | 0.8 | 垃圾回收阈值 |

#### 4.3 优化选项

```json
{
  "performance": {
    "optimization": {
      "gpu_acceleration": false,
      "parallel_processing": true,
      "image_compression": true,
      "result_compression": false,
      "lazy_loading": true,
      "preload_models": false,
      "batch_processing": false
    }
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `gpu_acceleration` | boolean | false | GPU加速 |
| `parallel_processing` | boolean | true | 并行处理 |
| `image_compression` | boolean | true | 图像压缩 |
| `result_compression` | boolean | false | 结果压缩 |
| `lazy_loading` | boolean | true | 延迟加载 |
| `preload_models` | boolean | false | 预加载模型 |
| `batch_processing` | boolean | false | 批量处理 |

---

### 5. 日志配置

#### 5.1 基础日志设置

```json
{
  "logging": {
    "level": "INFO",
    "file_enabled": true,
    "console_enabled": true,
    "format": "detailed",
    "encoding": "utf-8",
    "buffer_size": 1024
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `level` | string | "INFO" | 日志级别：`DEBUG`、`INFO`、`WARNING`、`ERROR`、`CRITICAL` |
| `file_enabled` | boolean | true | 启用文件日志 |
| `console_enabled` | boolean | true | 启用控制台日志 |
| `format` | string | "detailed" | 日志格式：`simple`、`standard`、`detailed`、`json` |
| `encoding` | string | "utf-8" | 文件编码 |
| `buffer_size` | int | 1024 | 缓冲区大小（字节） |

#### 5.2 文件日志设置

```json
{
  "logging": {
    "file": {
      "path": "logs/xuanwu.log",
      "max_size": 10,
      "backup_count": 5,
      "rotation": "size",
      "compression": false,
      "auto_delete": true,
      "retention_days": 30
    }
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `path` | string | "logs/xuanwu.log" | 日志文件路径 |
| `max_size` | int | 10 | 最大文件大小（MB） |
| `backup_count` | int | 5 | 备份文件数量 |
| `rotation` | string | "size" | 轮转方式：`size`、`time`、`both` |
| `compression` | boolean | false | 压缩备份文件 |
| `auto_delete` | boolean | true | 自动删除过期日志 |
| `retention_days` | int | 30 | 日志保留天数 |

#### 5.3 日志过滤

```json
{
  "logging": {
    "filters": {
      "exclude_modules": [
        "urllib3.connectionpool",
        "PIL.PngImagePlugin",
        "matplotlib.font_manager"
      ],
      "include_only": [],
      "min_level_by_module": {
        "core.ocr_worker": "DEBUG",
        "widgets.main_window": "INFO",
        "core.performance": "WARNING"
      },
      "exclude_patterns": [
        ".*font.*",
        ".*cache.*"
      ]
    }
  }
}
```

---

### 6. 数据存储配置

#### 6.1 历史记录

```json
{
  "storage": {
    "history": {
      "enabled": true,
      "max_entries": 1000,
      "auto_cleanup": true,
      "retention_days": 90,
      "save_screenshots": true,
      "screenshot_quality": 85,
      "compress_data": true
    }
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | boolean | true | 启用历史记录 |
| `max_entries` | int | 1000 | 最大记录条数 |
| `auto_cleanup` | boolean | true | 自动清理 |
| `retention_days` | int | 90 | 保留天数 |
| `save_screenshots` | boolean | true | 保存截图 |
| `screenshot_quality` | int | 85 | 截图质量（1-100） |
| `compress_data` | boolean | true | 压缩数据 |

#### 6.2 备份设置

```json
{
  "storage": {
    "backup": {
      "enabled": true,
      "auto_backup": true,
      "backup_interval": 24,
      "max_backups": 7,
      "backup_location": "backups/",
      "include_screenshots": false,
      "compression": true
    }
  }
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | boolean | true | 启用备份 |
| `auto_backup` | boolean | true | 自动备份 |
| `backup_interval` | int | 24 | 备份间隔（小时） |
| `max_backups` | int | 7 | 最大备份数量 |
| `backup_location` | string | "backups/" | 备份位置 |
| `include_screenshots` | boolean | false | 包含截图 |
| `compression` | boolean | true | 压缩备份 |

---

### 7. 网络配置

#### 7.1 代理设置

```json
{
  "network": {
    "proxy": {
      "enabled": false,
      "type": "http",
      "host": "",
      "port": 8080,
      "username": "",
      "password": "",
      "bypass_list": [
        "localhost",
        "127.0.0.1",
        "*.local"
      ]
    }
  }
}
```

#### 7.2 更新检查

```json
{
  "network": {
    "updates": {
      "auto_check": true,
      "check_interval": 24,
      "check_beta": false,
      "download_auto": false,
      "update_url": "https://api.xuanwu-ocr.com/updates",
      "timeout": 30
    }
  }
}
```

---

### 8. 安全配置

#### 8.1 隐私设置

```json
{
  "security": {
    "privacy": {
      "anonymous_usage": false,
      "crash_reporting": true,
      "telemetry": false,
      "auto_save_screenshots": true,
      "encrypt_sensitive_data": false,
      "secure_deletion": false
    }
  }
}
```

#### 8.2 访问控制

```json
{
  "security": {
    "access": {
      "require_password": false,
      "password_hash": "",
      "session_timeout": 3600,
      "max_login_attempts": 3,
      "lockout_duration": 300
    }
  }
}
```

---

## 🔧 配置管理工具

### 统一配置文件

从版本2.1.7开始，玄武支持统一配置文件模式，将所有配置整合到一个`unified_config.json`文件中。这种方式有以下优点：

- **简化管理**：所有配置集中在一个文件中，便于备份和恢复
- **减少冗余**：避免多个配置文件中存在重复设置
- **提高一致性**：防止配置文件之间的不一致问题
- **简化代码**：应用程序只需读取一个配置文件

#### 迁移到统一配置

使用`config_migration_tool.py`工具可以将现有的多个配置文件合并到统一配置文件中：

```bash
python config_migration_tool.py
```

此工具会：
1. 自动备份所有现有配置文件
2. 合并所有配置到`unified_config.json`
3. 可选择是否删除原配置文件

如需恢复原配置，可以使用备份文件夹中的配置文件。

#### 统一配置结构

统一配置文件的结构如下：

```json
{
  "settings": {
    // 原 settings.json 的内容（现包含 cloud_sync 云同步配置）
    "cloud_sync": {
      // 云同步配置，替代原 cloud_sync_config.json
      "enabled": false,
      "service_type": "webdav",
      "server_url": "",
      "username": "",
      "password": "",
      "sync_interval": 30,
      "auto_sync": true,
      "sync_items": {
        "keywords": true,
        "settings": true,
        "logs": false,
        "screenshots": false
      },
      "conflict_resolution": "ask",
      "encryption_enabled": true,
      "device_id": "xuanwu_xxxxxxxxxxxxxxxx"
    }
  },
  "config": {
    // 原 config.json 的内容
  },
  "debug_config": {
    // 原 debug_config.json 的内容
  },
  "recent_languages": [
    // 原 recent_languages.json 的内容
  ]
}
```

从本版本起，云同步设置统一存放于 `settings.json` 的 `cloud_sync` 字段中，不再使用独立的 `cloud_sync_config.json` 文件。若存在旧文件，程序会优先使用 `settings.json` 中的 `cloud_sync` 设置。

### 配置验证

```python
def validate_config(config_path):
    """验证配置文件有效性"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 验证必需字段
        required_fields = ['ocr', 'ui', 'hotkeys', 'performance']
        for field in required_fields:
            if field not in config:
                return False, f"缺少必需字段: {field}"
        
        # 验证数据类型
        if not isinstance(config['ocr']['confidence_threshold'], (int, float)):
            return False, "置信度阈值必须是数字"
        
        if not 0.0 <= config['ocr']['confidence_threshold'] <= 1.0:
            return False, "置信度阈值必须在0.0-1.0之间"
        
        return True, "配置验证通过"
    
    except Exception as e:
        return False, f"配置验证失败: {str(e)}"
```

### 配置重置

```python
def reset_config_to_defaults():
    """重置配置为默认值"""
    default_config = {
        "version": "2.1.7",
        "ocr": {
            "engine": "paddleocr",
            "language": "ch",
            "confidence_threshold": 0.8
        },
        "ui": {
            "theme": {"name": "dark"},
            "font": {"family": "Microsoft YaHei", "size": 12}
        },
        "hotkeys": {
            "global": {
                "capture_screen": "ctrl+shift+s",
                "toggle_window": "ctrl+shift+x"
            }
        },
        "performance": {
            "max_threads": 4,
            "cache_size": 100
        }
    }
    
    return default_config
```

### 配置导入导出

```python
def export_config(config, export_path):
    """导出配置到文件"""
    try:
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True, "配置导出成功"
    except Exception as e:
        return False, f"配置导出失败: {str(e)}"

def import_config(import_path):
    """从文件导入配置"""
    try:
        with open(import_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 验证导入的配置
        is_valid, message = validate_config_dict(config)
        if not is_valid:
            return None, f"导入的配置无效: {message}"
        
        return config, "配置导入成功"
    except Exception as e:
        return None, f"配置导入失败: {str(e)}"
```

---

## 📝 配置最佳实践

### 1. 性能优化建议

- **内存充足时**：增加 `cache_size` 和 `max_threads`
- **低配置设备**：减少 `max_threads`，禁用 `gpu_acceleration`
- **批量处理**：启用 `batch_processing` 和 `parallel_processing`

### 2. 识别精度优化

- **文档扫描**：启用 `preprocessing` 所有选项
- **屏幕截图**：禁用 `binarization`，启用 `enhance_contrast`
- **手写文字**：降低 `confidence_threshold` 到 0.6

### 3. 界面体验优化

- **高分辨率屏幕**：增加 `font.size` 到 14-16
- **多显示器**：启用 `remember_position` 和 `remember_size`
- **触摸屏设备**：设置 `icon_size` 为 "large"

### 4. 安全性建议

- **企业环境**：启用 `encrypt_sensitive_data` 和 `secure_deletion`
- **公共设备**：禁用 `auto_save_screenshots` 和历史记录
- **隐私保护**：禁用所有遥测和使用统计

---

## 🔗 相关文档

- [用户手册主页](README.md) - 用户手册总览
- [快速入门](quick-start.md) - 快速上手指南
- [OCR设置](ocr-settings.md) - OCR引擎详细配置
- [界面设置](ui-settings.md) - 界面定制指南
- [故障排除](troubleshooting.md) - 常见问题解决

---

*配置参数的详细说明到此结束。如需更多帮助，请参考其他相关文档或联系技术支持。*