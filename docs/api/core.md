# 核心模块 API

核心模块提供了 XuanWu OCR 的基础功能，包括 OCR 识别、配置管理、性能监控等核心能力。

## 📋 模块列表

- [OCR 识别引擎](#ocr-识别引擎)
- [配置管理](#配置管理)
- [关键词管理](#关键词管理)
- [性能监控](#性能监控)
- [日志系统](#日志系统)
- [主题管理](#主题管理)
- [热键管理](#热键管理)
- [国际化支持](#国际化支持)

---

## OCR 识别引擎

### `core.ocr_worker_threaded`

多线程 OCR 识别引擎，支持异步图像识别和文本提取。

#### 类：`OCRWorker`

OCR 工作线程类，提供图像识别功能。

```python
from core.ocr_worker_threaded import OCRWorker

# 创建 OCR 工作器
worker = OCRWorker()

# 识别图像文件
result = worker.recognize_image("path/to/image.png")

# 识别屏幕区域
result = worker.recognize_screen_region(x, y, width, height)
```

**主要方法：**

- `recognize_image(image_path: str) -> OCRResult`
  - 识别指定路径的图像文件
  - 参数：图像文件路径
  - 返回：OCR识别结果对象

- `recognize_screen_region(x: int, y: int, w: int, h: int) -> OCRResult`
  - 识别屏幕指定区域
  - 参数：区域坐标和尺寸
  - 返回：OCR识别结果对象

- `set_ocr_engine(engine: str) -> None`
  - 设置OCR引擎类型
  - 参数：引擎名称 ("tesseract", "paddleocr", "easyocr")

**信号：**

- `result_ready` - 识别完成信号
- `error_occurred` - 错误发生信号
- `progress_updated` - 进度更新信号

---

## 配置管理

### `core.settings`

应用程序配置管理模块，提供设置的加载、保存和验证功能。

#### 函数

```python
from core.settings import load_settings, save_settings, get_default_settings

# 加载配置
settings = load_settings()

# 保存配置
save_settings(settings)

# 获取默认配置
defaults = get_default_settings()
```

**主要函数：**

- `load_settings() -> dict`
  - 加载应用程序配置
  - 返回：配置字典

- `save_settings(settings: dict) -> bool`
  - 保存配置到文件
  - 参数：配置字典
  - 返回：保存是否成功

- `get_default_settings() -> dict`
  - 获取默认配置
  - 返回：默认配置字典

- `validate_settings(settings: dict) -> bool`
  - 验证配置有效性
  - 参数：配置字典
  - 返回：验证结果

### `core.config`

全局配置常量和路径定义。

```python
from core.config import LOG_DIR, SCREENSHOT_DIR, CONFIG_FILE

# 使用预定义路径
log_path = LOG_DIR / "app.log"
screenshot_path = SCREENSHOT_DIR / "capture.png"
```

**常量：**

- `LOG_DIR` - 日志目录路径
- `SCREENSHOT_DIR` - 截图目录路径
- `CONFIG_FILE` - 配置文件路径
- `BACKUP_DIR` - 备份目录路径

---

## 关键词管理

### `core.keyword_manager`

关键词匹配和管理系统，支持关键词的添加、删除、匹配等操作。

#### 类：`KeywordManager`

```python
from core.keyword_manager import KeywordManager

# 创建关键词管理器
km = KeywordManager()

# 添加关键词
km.add_keyword("重要文本")

# 匹配文本
matches = km.match_text("这是重要文本内容")

# 获取所有关键词
keywords = km.get_all_keywords()
```

**主要方法：**

- `add_keyword(keyword: str, category: str = "default") -> bool`
  - 添加关键词
  - 参数：关键词文本，分类（可选）
  - 返回：添加是否成功

- `remove_keyword(keyword: str) -> bool`
  - 删除关键词
  - 参数：关键词文本
  - 返回：删除是否成功

- `match_text(text: str) -> List[Match]`
  - 匹配文本中的关键词
  - 参数：待匹配文本
  - 返回：匹配结果列表

- `get_all_keywords() -> List[str]`
  - 获取所有关键词
  - 返回：关键词列表

- `import_keywords(file_path: str) -> bool`
  - 从文件导入关键词
  - 参数：文件路径
  - 返回：导入是否成功

---

## 性能监控

### `core.performance_manager`

系统性能监控和优化管理器，提供CPU、内存、磁盘等系统资源的监控。

#### 类：`PerformanceManager`

```python
from core.performance_manager import PerformanceManager

# 创建性能管理器
pm = PerformanceManager()

# 获取系统指标
metrics = pm.get_system_metrics()

# 开始监控
pm.start_monitoring()

# 获取性能报告
report = pm.generate_report()
```

**主要方法：**

- `get_system_metrics() -> SystemMetrics`
  - 获取当前系统性能指标
  - 返回：系统指标对象

- `start_monitoring(interval: int = 5) -> None`
  - 开始性能监控
  - 参数：监控间隔（秒）

- `stop_monitoring() -> None`
  - 停止性能监控

- `generate_report() -> PerformanceReport`
  - 生成性能报告
  - 返回：性能报告对象

- `optimize_performance() -> None`
  - 执行性能优化
  - 包括内存清理、缓存优化等

**数据类：**

```python
@dataclass
class SystemMetrics:
    cpu_percent: float
    memory_percent: float
    disk_usage: float
    network_io: dict
    timestamp: datetime
```

---

## 日志系统

### `core.enhanced_logger`

增强的日志记录系统，支持多种输出格式和日志级别。

#### 函数

```python
from core.enhanced_logger import get_enhanced_logger, setup_logging

# 获取日志记录器
logger = get_enhanced_logger("MyModule")

# 记录不同级别的日志
logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")

# 设置日志系统
setup_logging(level="INFO", format="detailed")
```

**主要函数：**

- `get_enhanced_logger(name: str) -> Logger`
  - 获取增强日志记录器
  - 参数：日志记录器名称
  - 返回：配置好的日志记录器

- `setup_logging(level: str = "INFO", format: str = "standard") -> None`
  - 设置日志系统
  - 参数：日志级别，输出格式

- `log_performance(func: callable) -> callable`
  - 性能日志装饰器
  - 参数：被装饰的函数
  - 返回：装饰后的函数

**日志格式：**

- `standard` - 标准格式：时间 | 级别 | 模块 | 消息
- `detailed` - 详细格式：包含文件名和行号
- `json` - JSON格式：结构化日志输出

---

## 主题管理

### `core.theme`

界面主题和样式管理系统。

```python
from core.theme import apply_theme, get_available_themes, ThemeManager

# 应用主题
apply_theme("dark")

# 获取可用主题
themes = get_available_themes()

# 使用主题管理器
tm = ThemeManager()
tm.set_theme("light")
tm.apply_custom_styles(widget)
```

**主要函数：**

- `apply_theme(theme_name: str) -> bool`
  - 应用指定主题
  - 参数：主题名称
  - 返回：应用是否成功

- `get_available_themes() -> List[str]`
  - 获取可用主题列表
  - 返回：主题名称列表

- `get_current_theme() -> str`
  - 获取当前主题
  - 返回：当前主题名称

#### 类：`ThemeManager`

```python
# 创建主题管理器
tm = ThemeManager()

# 设置主题
tm.set_theme("dark")

# 应用自定义样式
tm.apply_custom_styles(widget)

# 监听系统主题变化
tm.follow_system_theme(True)
```

---

## 热键管理

### `core.hotkey_manager`

全局热键注册和管理系统。

#### 类：`HotkeyListener`

```python
from core.hotkey_manager import HotkeyListener

# 创建热键监听器
listener = HotkeyListener()

# 注册热键
def on_screenshot():
    print("截图热键被按下")

listener.register_hotkey("ctrl+shift+s", on_screenshot)

# 开始监听
listener.start()

# 停止监听
listener.stop()
```

**主要方法：**

- `register_hotkey(hotkey: str, callback: callable) -> bool`
  - 注册热键
  - 参数：热键组合，回调函数
  - 返回：注册是否成功

- `unregister_hotkey(hotkey: str) -> bool`
  - 取消注册热键
  - 参数：热键组合
  - 返回：取消是否成功

- `start() -> None`
  - 开始热键监听

- `stop() -> None`
  - 停止热键监听

**热键格式：**

- 单键：`"a"`, `"f1"`, `"space"`
- 组合键：`"ctrl+c"`, `"alt+tab"`, `"ctrl+shift+s"`
- 修饰键：`ctrl`, `alt`, `shift`, `win`

---

## 国际化支持

### `core.i18n`

多语言支持和本地化功能。

```python
from core.i18n import t, set_language, get_available_languages

# 翻译文本
text = t("hello_world")

# 设置语言
set_language("zh_CN")

# 获取可用语言
languages = get_available_languages()
```

**主要函数：**

- `t(key: str, **kwargs) -> str`
  - 翻译文本
  - 参数：翻译键，格式化参数
  - 返回：翻译后的文本

- `set_language(lang_code: str) -> bool`
  - 设置当前语言
  - 参数：语言代码
  - 返回：设置是否成功

- `get_available_languages() -> List[str]`
  - 获取可用语言列表
  - 返回：语言代码列表

- `load_language_pack(lang_code: str) -> bool`
  - 加载语言包
  - 参数：语言代码
  - 返回：加载是否成功

**支持的语言：**

- `zh_CN` - 简体中文
- `zh_TW` - 繁体中文
- `en_US` - 英语
- `ja_JP` - 日语

---

## 🔗 相关文档

- [API 概览](overview.md) - API 总体介绍
- [界面组件 API](widgets.md) - 界面组件API文档
- [配置管理 API](config.md) - 配置系统详细说明
- [开发指南](../dev-guide/setup.md) - 开发环境搭建

---

*下一步：查看 [界面组件 API](widgets.md) 了解界面相关的API*