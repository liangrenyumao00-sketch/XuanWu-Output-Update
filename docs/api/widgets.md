# 界面组件 API

界面组件模块提供了 XuanWu OCR 的所有用户界面元素，包括主窗口、设置面板、图表组件等。

## 📋 组件列表

- [主窗口组件](#主窗口组件)
- [设置面板](#设置面板)
- [图表组件](#图表组件)
- [历史记录面板](#历史记录面板)
- [开发者工具面板](#开发者工具面板)
- [主题面板](#主题面板)
- [语言面板](#语言面板)
- [分析面板](#分析面板)
- [字体面板](#字体面板)
- [Web预览服务器](#web预览服务器)

---

## 主窗口组件

### `widgets.main_window`

应用程序主窗口，提供核心界面和功能入口。

#### 类：`MainWindow`

```python
from widgets.main_window import MainWindow
from PyQt6.QtWidgets import QApplication

# 创建应用程序
app = QApplication([])

# 创建主窗口
window = MainWindow()
window.show()

# 运行应用程序
app.exec()
```

**主要方法：**

- `setup_ui() -> None`
  - 初始化用户界面
  - 设置菜单栏、工具栏、状态栏等

- `setup_ocr_worker() -> None`
  - 初始化OCR工作线程
  - 配置OCR识别引擎

- `capture_screen() -> None`
  - 执行屏幕截图
  - 触发OCR识别流程

- `show_settings() -> None`
  - 显示设置对话框

- `toggle_always_on_top() -> None`
  - 切换窗口置顶状态

**信号：**

- `ocr_completed` - OCR识别完成信号
- `settings_changed` - 设置变更信号
- `window_state_changed` - 窗口状态变更信号

---

## 设置面板

### `widgets.settings_panel`

应用程序设置管理面板，提供各种配置选项的界面。

#### 类：`SettingsPanel`

```python
from widgets.settings_panel import SettingsPanel

# 创建设置面板
panel = SettingsPanel()

# 显示面板
panel.show()

# 获取当前设置
settings = panel.get_current_settings()

# 应用设置
panel.apply_settings(settings)
```

**主要方法：**

- `get_current_settings() -> dict`
  - 获取当前设置值
  - 返回：设置字典

- `apply_settings(settings: dict) -> None`
  - 应用设置
  - 参数：设置字典

- `reset_to_defaults() -> None`
  - 重置为默认设置

- `validate_settings() -> bool`
  - 验证设置有效性
  - 返回：验证结果

- `export_settings(file_path: str) -> bool`
  - 导出设置到文件
  - 参数：文件路径
  - 返回：导出是否成功

- `import_settings(file_path: str) -> bool`
  - 从文件导入设置
  - 参数：文件路径
  - 返回：导入是否成功

**设置分类：**

- **OCR设置** - 识别引擎、语言、精度等
- **界面设置** - 主题、字体、布局等
- **热键设置** - 快捷键配置
- **高级设置** - 性能优化、调试选项等

---

## 图表组件

### `widgets.chart_widget`

数据可视化图表组件，支持多种图表类型。

#### 类：`SimpleBarChart`

简单的柱状图组件，用于显示分类数据的数值比较。

```python
from widgets.chart_widget import SimpleBarChart

# 创建柱状图
chart = SimpleBarChart()

# 设置数据
data = [10, 20, 15, 25, 30]
labels = ["A", "B", "C", "D", "E"]
chart.set_data(data, labels)

# 设置标题
chart.set_title("销售数据")

# 显示图表
chart.show()
```

**主要方法：**

- `set_data(data: List[float], labels: List[str] = None) -> None`
  - 设置图表数据
  - 参数：数据列表，标签列表（可选）

- `set_title(title: str) -> None`
  - 设置图表标题
  - 参数：标题文本

- `set_colors(colors: List[str]) -> None`
  - 设置柱状图颜色
  - 参数：颜色列表（十六进制格式）

#### 类：`SimplePieChart`

简单的饼图组件，用于显示数据的比例关系。

```python
from widgets.chart_widget import SimplePieChart

# 创建饼图
chart = SimplePieChart()

# 设置数据
data = [30, 25, 20, 15, 10]
labels = ["类型A", "类型B", "类型C", "类型D", "类型E"]
chart.set_data(data, labels)

# 设置标题
chart.set_title("数据分布")

# 显示图表
chart.show()
```

**主要方法：**

- `set_data(data: List[float], labels: List[str] = None) -> None`
  - 设置饼图数据
  - 参数：数据列表，标签列表（可选）

- `set_title(title: str) -> None`
  - 设置图表标题
  - 参数：标题文本

#### 类：`SimpleLineChart`

简单的折线图组件，用于显示数据随时间或其他连续变量的变化趋势。

```python
from widgets.chart_widget import SimpleLineChart

# 创建折线图
chart = SimpleLineChart()

# 设置数据
data = [10, 15, 12, 18, 22, 20, 25]
labels = ["1月", "2月", "3月", "4月", "5月", "6月", "7月"]
chart.set_data(data, labels)

# 设置标题
chart.set_title("月度趋势")

# 显示图表
chart.show()
```

**主要方法：**

- `set_data(data: List[float], labels: List[str] = None) -> None`
  - 设置折线图数据
  - 参数：数据列表，标签列表（可选）

- `set_title(title: str) -> None`
  - 设置图表标题
  - 参数：标题文本

---

## 历史记录面板

### `widgets.history_panel`

OCR识别历史记录管理面板，提供历史记录的查看、搜索和管理功能。

#### 类：`HistoryPanel`

```python
from widgets.history_panel import HistoryPanel

# 创建历史记录面板
panel = HistoryPanel()

# 显示面板
panel.show()

# 刷新历史记录
panel.refresh()

# 搜索历史记录
panel.search_history("关键词")

# 清空历史记录
panel.clear_history()
```

**主要方法：**

- `refresh() -> None`
  - 刷新历史记录列表
  - 重新加载所有历史数据

- `search_history(keyword: str) -> None`
  - 搜索历史记录
  - 参数：搜索关键词

- `clear_history() -> None`
  - 清空所有历史记录

- `export_history(file_path: str) -> bool`
  - 导出历史记录
  - 参数：导出文件路径
  - 返回：导出是否成功

- `delete_selected() -> None`
  - 删除选中的历史记录

**属性：**

- `LOG_FOLDER` - 日志文件夹路径
- `SCREENSHOT_FOLDER` - 截图文件夹路径

---

## 开发者工具面板

### `widgets.dev_tools_panel`

开发者工具集合面板，提供系统监控、日志管理、调试等功能。

#### 类：`DevToolsPanel`

```python
from widgets.dev_tools_panel import DevToolsPanel

# 创建开发者工具面板
panel = DevToolsPanel()

# 显示面板
panel.show()

# 检查更新
panel.check_for_updates()

# 查看系统信息
panel.view_system_info()

# 分析代码
panel.analyze_code()
```

**主要方法：**

- `check_for_updates() -> None`
  - 检查应用程序更新
  - 异步检查最新版本

- `view_system_info() -> None`
  - 查看系统信息
  - 显示硬件、软件环境信息

- `view_environment_variables() -> None`
  - 查看环境变量
  - 显示系统和应用程序环境变量

- `check_dependencies() -> None`
  - 检查依赖项
  - 验证所需库和组件的安装状态

- `static_code_analysis() -> None`
  - 静态代码分析
  - 检查代码质量和潜在问题

- `view_logs() -> None`
  - 查看应用程序日志
  - 打开日志查看器

**属性：**

- `current_version` - 当前应用程序版本
- `UPDATE_CHECK_URL` - 更新检查URL

---

## 主题面板

### `widgets.theme_panel`

主题和外观设置面板。

#### 类：`ThemePanel`

```python
from widgets.theme_panel import ThemePanel

# 创建主题面板
panel = ThemePanel()

# 应用主题
panel.apply_theme("dark")

# 获取当前主题
current = panel.get_current_theme()
```

---

## 语言面板

### `widgets.modern_language_panel`

现代化的语言设置面板。

#### 类：`ModernLanguagePanel`

```python
from widgets.modern_language_panel import ModernLanguagePanel

# 创建语言面板
panel = ModernLanguagePanel()

# 设置语言
panel.set_language("zh_CN")

# 获取可用语言
languages = panel.get_available_languages()
```

---

## 分析面板

### `widgets.analytics_panel`

数据分析和统计面板。

#### 类：`AnalyticsPanel`

```python
from widgets.analytics_panel import AnalyticsPanel

# 创建分析面板
panel = AnalyticsPanel()

# 生成报告
panel.generate_report()

# 导出数据
panel.export_data("report.csv")
```

---

## 字体面板

### `widgets.enhanced_font_panel`

增强的字体设置面板。

#### 类：`EnhancedFontPanel`

```python
from widgets.enhanced_font_panel import EnhancedFontPanel

# 创建字体面板
panel = EnhancedFontPanel()

# 设置字体
panel.set_font_family("Microsoft YaHei")
panel.set_font_size(12)

# 应用字体设置
panel.apply_font_settings()
```

---

## Web预览服务器

### `widgets.web_preview_server_enhanced`

增强的Web预览服务器，用于在浏览器中预览内容。

#### 类：`WebPreviewServer`

```python
from widgets.web_preview_server_enhanced import WebPreviewServer

# 创建Web服务器
server = WebPreviewServer()

# 启动服务器
server.start(port=8080)

# 设置预览内容
server.set_content("<h1>Hello World</h1>")

# 停止服务器
server.stop()
```

**主要方法：**

- `start(port: int = 8080) -> bool`
  - 启动Web服务器
  - 参数：端口号
  - 返回：启动是否成功

- `stop() -> None`
  - 停止Web服务器

- `set_content(content: str) -> None`
  - 设置预览内容
  - 参数：HTML内容

- `get_server_url() -> str`
  - 获取服务器URL
  - 返回：服务器访问地址

---

## 🎨 样式和主题

### 主题系统

所有界面组件都支持主题系统，可以通过以下方式应用主题：

```python
from core.theme import apply_theme

# 应用深色主题
apply_theme("dark")

# 应用浅色主题
apply_theme("light")

# 应用自定义主题
apply_theme("custom")
```

### 样式定制

组件支持CSS样式定制：

```python
# 设置自定义样式
widget.setStyleSheet("""
    QWidget {
        background-color: #2b2b2b;
        color: #ffffff;
        font-family: 'Microsoft YaHei';
    }
    QPushButton {
        background-color: #0078d4;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
    }
    QPushButton:hover {
        background-color: #106ebe;
    }
""")
```

---

## 🔧 事件处理

### 信号和槽

界面组件使用Qt的信号槽机制进行事件处理：

```python
from PyQt6.QtCore import pyqtSignal

class CustomWidget(QWidget):
    # 定义信号
    data_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
        # 连接信号和槽
        self.data_changed.connect(self.on_data_changed)
    
    def on_data_changed(self, data):
        print(f"数据已更改: {data}")
    
    def update_data(self, new_data):
        # 发射信号
        self.data_changed.emit(new_data)
```

### 常用事件

- `mousePressEvent` - 鼠标按下事件
- `keyPressEvent` - 键盘按下事件
- `paintEvent` - 绘制事件
- `resizeEvent` - 窗口大小改变事件
- `closeEvent` - 窗口关闭事件

---

## 🔗 相关文档

- [API 概览](overview.md) - API 总体介绍
- [核心模块 API](core.md) - 核心功能API文档
- [配置管理](config.md) - 配置系统详细说明
- [开发指南](../dev-guide/components.md) - 组件开发指南

---

*下一步：查看 [配置管理 API](config.md) 了解配置系统的详细使用方法*