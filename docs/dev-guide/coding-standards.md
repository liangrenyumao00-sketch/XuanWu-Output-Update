# 代码规范

本文档定义了 XuanWu OCR 项目的代码编写规范，包括命名约定、代码风格、注释规范等。

## 📝 通用规范

### 代码风格
- 遵循 PEP 8 规范
- 使用 Black 进行代码格式化
- 行长度限制为 88 字符
- 使用 4 个空格缩进

### 命名约定
- **变量名**: 使用 snake_case
- **函数名**: 使用 snake_case
- **类名**: 使用 PascalCase
- **常量**: 使用 UPPER_SNAKE_CASE
- **模块名**: 使用 snake_case

## 🐍 Python 规范

### 导入规范
```python
# 标准库导入
import os
import sys
from typing import List, Dict, Optional

# 第三方库导入
import requests
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QThread

# 本地导入
from core.config import Config
from widgets.base_widget import BaseWidget
```

### 函数定义
```python
def process_ocr_result(
    image_data: bytes,
    api_key: str,
    confidence_threshold: float = 0.8
) -> Optional[str]:
    """
    处理OCR识别结果
    
    Args:
        image_data: 图像数据
        api_key: API密钥
        confidence_threshold: 置信度阈值
        
    Returns:
        识别结果字符串，失败时返回None
        
    Raises:
        ValueError: 当参数无效时
        APIError: 当API调用失败时
    """
    if not image_data:
        raise ValueError("图像数据不能为空")
    
    try:
        result = call_ocr_api(image_data, api_key)
        if result.confidence >= confidence_threshold:
            return result.text
        return None
    except Exception as e:
        raise APIError(f"OCR识别失败: {e}") from e
```

### 类定义
```python
class OCRWorker(QThread):
    """OCR识别工作线程
    
    负责在后台线程中执行OCR识别任务，避免阻塞主界面
    """
    
    def __init__(self, api_config: Dict[str, str]):
        super().__init__()
        self.api_config = api_config
        self.is_running = False
        
    def run(self):
        """线程主函数"""
        self.is_running = True
        try:
            while self.is_running:
                self.process_recognition()
                self.msleep(1000)  # 1秒间隔
        finally:
            self.is_running = False
```

## 🎨 UI 规范

### Qt 组件命名
```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        """设置用户界面"""
        # 主控件使用描述性名称
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 按钮命名：动作_对象_按钮
        self.start_monitor_button = QPushButton("开始监控")
        self.stop_monitor_button = QPushButton("停止监控")
        
        # 输入框命名：对象_输入框
        self.api_key_input = QLineEdit()
        self.keyword_input = QLineEdit()
        
        # 标签命名：对象_标签
        self.status_label = QLabel("就绪")
        self.result_label = QLabel("")
```

### 信号和槽
```python
class KeywordPanel(QWidget):
    """关键词管理面板"""
    
    # 信号定义
    keyword_added = pyqtSignal(str)
    keyword_removed = pyqtSignal(str)
    keyword_updated = pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.connect_signals()
        
    def connect_signals(self):
        """连接信号和槽"""
        self.add_button.clicked.connect(self.on_add_keyword)
        self.remove_button.clicked.connect(self.on_remove_keyword)
        self.keyword_list.itemChanged.connect(self.on_keyword_changed)
        
    def on_add_keyword(self):
        """添加关键词槽函数"""
        keyword = self.keyword_input.text().strip()
        if keyword:
            self.keyword_added.emit(keyword)
            self.keyword_input.clear()
```

## 📁 文件组织

### 目录结构
```
project/
├── core/                    # 核心功能模块
│   ├── __init__.py
│   ├── config.py           # 配置管理
│   ├── ocr_worker.py       # OCR工作线程
│   └── api/                # API相关
│       ├── __init__.py
│       ├── base_api.py
│       └── baidu_api.py
├── widgets/                 # UI组件
│   ├── __init__.py
│   ├── base_widget.py      # 基础组件
│   ├── main_window.py      # 主窗口
│   └── panels/             # 面板组件
│       ├── __init__.py
│       ├── keyword_panel.py
│       └── status_panel.py
├── utils/                   # 工具函数
│   ├── __init__.py
│   ├── file_utils.py
│   └── image_utils.py
└── tests/                   # 测试文件
    ├── __init__.py
    ├── unit/
    └── integration/
```

### 模块导入
```python
# 使用相对导入
from .base_widget import BaseWidget
from ..core.config import Config
from ...utils.file_utils import read_config
```

## 💬 注释规范

### 文档字符串
```python
def recognize_text(
    image_path: str,
    api_config: Dict[str, str],
    options: Optional[Dict[str, Any]] = None
) -> RecognitionResult:
    """识别图像中的文字
    
    使用指定的OCR引擎识别图像中的文字内容。
    
    Args:
        image_path: 图像文件路径
        api_config: API配置字典，包含密钥等信息
        options: 可选参数，如识别语言、置信度等
        
    Returns:
        RecognitionResult: 包含识别结果的对象
        
    Raises:
        FileNotFoundError: 当图像文件不存在时
        APIError: 当API调用失败时
        ValueError: 当参数无效时
        
    Example:
        >>> config = {"api_key": "your_key", "secret_key": "your_secret"}
        >>> result = recognize_text("image.jpg", config)
        >>> print(result.text)
        'Hello World'
        
    Note:
        支持的图像格式：JPEG, PNG, BMP, TIFF
        最大图像大小：10MB
    """
    pass
```

### 行内注释
```python
def process_image(image_data: bytes) -> bytes:
    """处理图像数据"""
    # 转换为PIL图像对象
    image = Image.open(BytesIO(image_data))
    
    # 调整图像大小，OCR API要求最大2048像素
    if max(image.size) > 2048:
        ratio = 2048 / max(image.size)
        new_size = tuple(int(dim * ratio) for dim in image.size)
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # 转换为RGB格式（如果需要）
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # 转换回字节数据
    output = BytesIO()
    image.save(output, format='JPEG', quality=95)
    return output.getvalue()
```

### TODO 注释
```python
def optimize_recognition_speed():
    """优化识别速度"""
    # TODO: 实现图像预处理优化
    # TODO: 添加多线程并行处理
    # FIXME: 修复内存泄漏问题
    # NOTE: 这个函数需要重构以提高性能
    pass
```

## 🧪 测试规范

### 测试文件命名
```
test_module_name.py          # 单元测试
test_integration_module.py   # 集成测试
conftest.py                  # pytest配置
```

### 测试函数命名
```python
def test_function_name_with_valid_input():
    """测试函数在有效输入下的行为"""
    pass

def test_function_name_with_invalid_input():
    """测试函数在无效输入下的行为"""
    pass

def test_function_name_raises_exception():
    """测试函数在异常情况下的行为"""
    pass
```

### 测试类命名
```python
class TestOCRWorker:
    """测试OCRWorker类"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.worker = OCRWorker()
        
    def teardown_method(self):
        """每个测试方法后的清理"""
        self.worker.quit()
        
    def test_initialization(self):
        """测试初始化"""
        assert not self.worker.is_running
        assert self.worker.api_config is None
```

## 🔧 配置规范

### 配置文件格式
```python
# config/settings.py
"""应用程序配置"""

import os
from typing import Dict, Any

class Settings:
    """应用程序设置类"""
    
    # 默认配置
    DEFAULT_CONFIG = {
        'ocr': {
            'interval': 1.0,
            'confidence_threshold': 0.8,
            'max_image_size': 2048
        },
        'ui': {
            'theme': 'light',
            'language': 'zh_CN',
            'window_size': [1200, 800]
        },
        'logging': {
            'level': 'INFO',
            'file_path': 'logs/app.log',
            'max_size': '10MB'
        }
    }
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file or 'config.json'
        self.config = self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        # 实现配置加载逻辑
        pass
```

### 环境变量
```python
# 使用环境变量配置敏感信息
import os

API_KEY = os.getenv('XUANWU_API_KEY', '')
SECRET_KEY = os.getenv('XUANWU_SECRET_KEY', '')
DEBUG_MODE = os.getenv('XUANWU_DEBUG', 'false').lower() == 'true'
```

## 📊 日志规范

### 日志级别使用
```python
import logging

logger = logging.getLogger(__name__)

def process_recognition():
    """处理识别任务"""
    logger.debug("开始处理识别任务")  # 详细的调试信息
    
    try:
        result = call_api()
        logger.info(f"识别成功，结果: {result}")  # 一般信息
        return result
        
    except APIError as e:
        logger.warning(f"API调用失败，重试中: {e}")  # 警告信息
        # 重试逻辑
        
    except Exception as e:
        logger.error(f"识别处理失败: {e}", exc_info=True)  # 错误信息
        raise
```

### 日志格式
```python
# logging_config.py
import logging

def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/app.log'),
            logging.StreamHandler()
        ]
    )
```

## 🔒 安全规范

### 敏感信息处理
```python
import os
from typing import Dict

def load_api_config() -> Dict[str, str]:
    """加载API配置，保护敏感信息"""
    config = {}
    
    # 从环境变量读取（推荐）
    config['api_key'] = os.getenv('API_KEY')
    config['secret_key'] = os.getenv('SECRET_KEY')
    
    # 如果环境变量不存在，从配置文件读取
    if not config['api_key']:
        config_file = load_config_file()
        config.update(config_file.get('api', {}))
    
    return config

def mask_sensitive_data(data: str) -> str:
    """遮蔽敏感数据"""
    if len(data) <= 8:
        return '*' * len(data)
    return data[:4] + '*' * (len(data) - 8) + data[-4:]
```

### 输入验证
```python
def validate_api_key(api_key: str) -> bool:
    """验证API密钥格式"""
    if not api_key:
        raise ValueError("API密钥不能为空")
    
    if len(api_key) < 20:
        raise ValueError("API密钥长度不足")
    
    if not api_key.isalnum():
        raise ValueError("API密钥只能包含字母和数字")
    
    return True
```

## 📈 性能规范

### 内存管理
```python
import weakref
from typing import Optional

class ImageCache:
    """图像缓存，使用弱引用避免内存泄漏"""
    
    def __init__(self, max_size: int = 100):
        self.cache = weakref.WeakValueDictionary()
        self.max_size = max_size
        
    def get(self, key: str) -> Optional[bytes]:
        """获取缓存的图像"""
        return self.cache.get(key)
        
    def put(self, key: str, value: bytes):
        """存储图像到缓存"""
        if len(self.cache) >= self.max_size:
            self.cleanup()
        self.cache[key] = value
```

### 异步处理
```python
import asyncio
from typing import List

async def process_multiple_images(image_paths: List[str]) -> List[str]:
    """异步处理多个图像"""
    tasks = [recognize_image_async(path) for path in image_paths]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 处理异常结果
    processed_results = []
    for result in results:
        if isinstance(result, Exception):
            processed_results.append(None)
        else:
            processed_results.append(result)
    
    return processed_results
```

## 📋 代码审查清单

### 提交前检查
- [ ] 代码遵循命名规范
- [ ] 函数和类有完整的文档字符串
- [ ] 复杂逻辑有适当的注释
- [ ] 异常处理完整
- [ ] 没有硬编码的敏感信息
- [ ] 性能关键代码有优化
- [ ] 测试覆盖率满足要求

### 代码审查要点
- [ ] 代码逻辑清晰易懂
- [ ] 错误处理适当
- [ ] 性能考虑充分
- [ ] 安全性检查到位
- [ ] 可维护性良好
- [ ] 符合项目架构设计

---

*遵循这些代码规范有助于保持代码质量和项目的长期可维护性。*
