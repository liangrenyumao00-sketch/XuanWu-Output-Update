# API 概览

XuanWu OCR 提供了一套完整的 Python API，用于 OCR 识别、图像处理、配置管理等功能。

## 🏗️ 架构概述

XuanWu OCR 采用模块化架构设计，主要包含以下几个核心模块：

### 核心模块 (core)
负责应用程序的核心功能实现：

- **OCR 引擎** (`ocr_worker_threaded.py`) - 多线程 OCR 识别引擎
- **配置管理** (`settings.py`, `config.py`) - 应用程序配置和设置管理
- **关键词管理** (`keyword_manager.py`) - 关键词匹配和管理
- **性能监控** (`performance_manager.py`) - 系统性能监控和优化
- **日志系统** (`enhanced_logger.py`) - 增强的日志记录系统
- **主题管理** (`theme.py`) - 界面主题和样式管理
- **国际化** (`i18n.py`) - 多语言支持
- **热键管理** (`hotkey_manager.py`) - 全局热键注册和管理

### 界面组件 (widgets)
提供丰富的用户界面组件：

- **设置面板** (`settings_panel.py`) - 应用程序设置界面
- **分析面板** (`analytics_panel.py`) - 数据分析和统计界面
- **历史记录** (`history_panel.py`) - OCR 历史记录管理
- **开发者工具** (`dev_tools_panel.py`) - 开发调试工具集
- **图表组件** (`chart_widget.py`) - 数据可视化图表
- **主题面板** (`theme_panel.py`) - 主题设置界面

## 📋 API 分类

### 1. 核心 API
```python
# OCR 识别
from core.ocr_worker_threaded import OCRWorker
worker = OCRWorker()
result = worker.recognize_image(image_path)

# 配置管理
from core.settings import load_settings, save_settings
settings = load_settings()
save_settings(settings)

# 关键词管理
from core.keyword_manager import KeywordManager
km = KeywordManager()
km.add_keyword("重要文本")
```

### 2. 界面组件 API
```python
# 设置面板
from widgets.settings_panel import BaseSettingDialog
dialog = BaseSettingDialog()
dialog.show()

# 分析面板
from widgets.analytics_panel import AnalyticsPanel
panel = AnalyticsPanel()
panel.refresh_data()
```

### 3. 工具类 API
```python
# 性能监控
from core.performance_manager import PerformanceManager
pm = PerformanceManager()
metrics = pm.get_system_metrics()

# 日志记录
from core.enhanced_logger import get_enhanced_logger
logger = get_enhanced_logger("MyModule")
logger.info("操作完成")
```

## 🔧 使用模式

### 同步模式
适用于简单的单次操作：

```python
from core.ocr_worker_threaded import OCRWorker

worker = OCRWorker()
result = worker.recognize_text("image.png")
print(result)
```

### 异步模式
适用于需要响应式界面的场景：

```python
from PyQt6.QtCore import QThread
from core.ocr_worker_threaded import OCRWorker

class OCRThread(QThread):
    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path
        self.worker = OCRWorker()
    
    def run(self):
        result = self.worker.recognize_text(self.image_path)
        # 处理结果...
```

### 事件驱动模式
适用于需要监听系统事件的场景：

```python
from core.hotkey_manager import HotkeyListener

def on_hotkey_pressed():
    print("热键被按下")

listener = HotkeyListener()
listener.register_hotkey("ctrl+shift+x", on_hotkey_pressed)
listener.start()
```

## 📊 数据流

```
用户输入 → 热键监听 → OCR识别 → 关键词匹配 → 结果处理 → 界面更新
    ↓           ↓         ↓         ↓         ↓         ↓
  配置管理   性能监控   日志记录   数据分析   主题应用   通知发送
```

## 🔒 错误处理

所有 API 都遵循统一的错误处理模式：

```python
try:
    result = api_function()
    if result.success:
        # 处理成功结果
        data = result.data
    else:
        # 处理业务错误
        error_msg = result.error_message
except Exception as e:
    # 处理系统异常
    logger.error(f"API调用失败: {e}")
```

## 📈 性能考虑

- **内存管理**: 大图像处理时注意内存释放
- **线程安全**: 多线程环境下使用线程安全的API
- **缓存策略**: 合理使用缓存提高性能
- **资源清理**: 及时释放不再使用的资源

## 🔗 相关文档

- [核心模块 API](core.md) - 详细的核心模块API文档
- [界面组件 API](widgets.md) - 界面组件的完整API参考
- [配置管理 API](config.md) - 配置系统的详细说明
- [开发指南](../dev-guide/setup.md) - 开发环境搭建指南

---

*下一步：查看 [核心模块 API](core.md) 了解详细的API使用方法*