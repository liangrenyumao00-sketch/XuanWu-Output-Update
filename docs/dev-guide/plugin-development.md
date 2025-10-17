# 插件开发指南

本指南将帮助开发者了解如何为 XuanWu OCR 开发自定义插件，扩展程序功能。

## 🔌 插件系统概述

### 插件架构
XuanWu OCR 采用模块化插件架构，支持以下类型的插件：
- **OCR引擎插件**: 添加新的OCR识别引擎
- **通知插件**: 扩展通知方式
- **数据处理器插件**: 自定义数据处理逻辑
- **UI组件插件**: 添加新的界面组件
- **工作流插件**: 自定义工作流程

### 插件目录结构
```
plugins/
├── __init__.py
├── base/
│   ├── __init__.py
│   ├── plugin_base.py      # 插件基类
│   ├── ocr_plugin.py       # OCR插件基类
│   ├── notification_plugin.py  # 通知插件基类
│   └── data_processor_plugin.py # 数据处理器插件基类
├── ocr/
│   ├── __init__.py
│   ├── google_ocr.py       # Google OCR插件
│   └── azure_ocr.py        # Azure OCR插件
├── notifications/
│   ├── __init__.py
│   ├── telegram_notifier.py # Telegram通知插件
│   └── slack_notifier.py   # Slack通知插件
└── config/
    └── plugin_config.json  # 插件配置文件
```

## 🏗️ 插件开发基础

### 插件基类
```python
# plugins/base/plugin_base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

class PluginBase(ABC):
    """插件基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.is_enabled = True
        
    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        pass
        
    @property
    @abstractmethod
    def version(self) -> str:
        """插件版本"""
        pass
        
    @property
    @abstractmethod
    def description(self) -> str:
        """插件描述"""
        pass
        
    @abstractmethod
    def initialize(self) -> bool:
        """初始化插件"""
        pass
        
    @abstractmethod
    def cleanup(self) -> None:
        """清理插件资源"""
        pass
        
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self.config.get(key, default)
        
    def set_config(self, key: str, value: Any) -> None:
        """设置配置值"""
        self.config[key] = value
```

### OCR插件基类
```python
# plugins/base/ocr_plugin.py
from .plugin_base import PluginBase
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

@dataclass
class OCRResult:
    """OCR识别结果"""
    text: str
    confidence: float
    language: str
    words: List[Dict[str, Any]] = None
    raw_response: Dict[str, Any] = None

class OCRPluginBase(PluginBase):
    """OCR插件基类"""
    
    @abstractmethod
    async def recognize_text(self, image_data: bytes, options: Dict[str, Any] = None) -> OCRResult:
        """识别图像中的文字"""
        pass
        
    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """获取支持的语言列表"""
        pass
        
    @abstractmethod
    def get_max_image_size(self) -> tuple:
        """获取最大支持的图像尺寸"""
        pass
        
    def preprocess_image(self, image_data: bytes) -> bytes:
        """图像预处理（可选重写）"""
        return image_data
        
    def postprocess_result(self, result: OCRResult) -> OCRResult:
        """结果后处理（可选重写）"""
        return result
```

## 🔧 OCR引擎插件开发

### Google OCR插件示例
```python
# plugins/ocr/google_ocr.py
import asyncio
import base64
from typing import Dict, Any, List
from google.cloud import vision
from .ocr_plugin import OCRPluginBase, OCRResult

class GoogleOCRPlugin(OCRPluginBase):
    """Google Vision OCR插件"""
    
    @property
    def name(self) -> str:
        return "Google Vision OCR"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Google Cloud Vision API OCR识别插件"
        
    def initialize(self) -> bool:
        """初始化Google Vision客户端"""
        try:
            # 从配置中获取认证信息
            credentials_path = self.get_config('credentials_path')
            if credentials_path:
                self.client = vision.ImageAnnotatorClient.from_service_account_file(
                    credentials_path
                )
            else:
                # 使用默认认证
                self.client = vision.ImageAnnotatorClient()
                
            self.logger.info("Google Vision OCR插件初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"Google Vision OCR插件初始化失败: {e}")
            return False
            
    async def recognize_text(self, image_data: bytes, options: Dict[str, Any] = None) -> OCRResult:
        """识别图像中的文字"""
        try:
            # 预处理图像
            processed_image = self.preprocess_image(image_data)
            
            # 创建图像对象
            image = vision.Image(content=processed_image)
            
            # 配置识别参数
            image_context = vision.ImageContext()
            if options and 'language_hints' in options:
                image_context.language_hints = options['language_hints']
                
            # 执行文字检测
            response = self.client.text_detection(
                image=image, 
                image_context=image_context
            )
            
            if response.error.message:
                raise Exception(f"Google Vision API错误: {response.error.message}")
                
            # 解析结果
            texts = response.text_annotations
            if not texts:
                return OCRResult(
                    text="",
                    confidence=0.0,
                    language="unknown",
                    words=[]
                )
                
            # 提取主要文字
            main_text = texts[0].description
            
            # 提取单词信息
            words = []
            for text in texts[1:]:  # 跳过第一个（完整文本）
                words.append({
                    'text': text.description,
                    'confidence': text.score if hasattr(text, 'score') else 1.0,
                    'bounding_box': [
                        (vertex.x, vertex.y) for vertex in text.bounding_poly.vertices
                    ]
                })
                
            # 计算平均置信度
            avg_confidence = sum(word.get('confidence', 1.0) for word in words) / len(words) if words else 1.0
            
            result = OCRResult(
                text=main_text,
                confidence=avg_confidence,
                language=options.get('language', 'unknown') if options else 'unknown',
                words=words,
                raw_response=response
            )
            
            # 后处理结果
            return self.postprocess_result(result)
            
        except Exception as e:
            self.logger.error(f"Google OCR识别失败: {e}")
            raise
            
    def get_supported_languages(self) -> List[str]:
        """获取支持的语言列表"""
        return [
            'zh', 'zh-CN', 'zh-TW',  # 中文
            'en', 'en-US', 'en-GB',  # 英文
            'ja', 'ja-JP',           # 日文
            'ko', 'ko-KR',           # 韩文
            'fr', 'de', 'es', 'it', 'pt', 'ru', 'ar'  # 其他语言
        ]
        
    def get_max_image_size(self) -> tuple:
        """获取最大支持的图像尺寸"""
        return (2048, 2048)  # Google Vision API限制
        
    def cleanup(self) -> None:
        """清理资源"""
        if hasattr(self, 'client'):
            self.client = None
        self.logger.info("Google Vision OCR插件已清理")
```

### 插件配置
```json
// plugins/config/plugin_config.json
{
  "google_ocr": {
    "enabled": true,
    "credentials_path": "path/to/service-account.json",
    "language_hints": ["zh", "en"],
    "confidence_threshold": 0.8,
    "timeout": 30
  },
  "azure_ocr": {
    "enabled": false,
    "endpoint": "https://your-region.cognitiveservices.azure.com/",
    "subscription_key": "your-subscription-key",
    "language": "zh-Hans"
  }
}
```

## 📢 通知插件开发

### 通知插件基类
```python
# plugins/base/notification_plugin.py
from .plugin_base import PluginBase
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class NotificationMessage:
    """通知消息"""
    title: str
    content: str
    priority: str = "normal"  # low, normal, high, urgent
    attachments: Optional[Dict[str, Any]] = None

class NotificationPluginBase(PluginBase):
    """通知插件基类"""
    
    @abstractmethod
    async def send_notification(self, message: NotificationMessage) -> bool:
        """发送通知"""
        pass
        
    @abstractmethod
    def test_connection(self) -> bool:
        """测试连接"""
        pass
        
    def format_message(self, message: NotificationMessage) -> str:
        """格式化消息（可选重写）"""
        return f"{message.title}\n{message.content}"
```

### Telegram通知插件示例
```python
# plugins/notifications/telegram_notifier.py
import asyncio
import aiohttp
from typing import Dict, Any
from .notification_plugin import NotificationPluginBase, NotificationMessage

class TelegramNotifierPlugin(NotificationPluginBase):
    """Telegram通知插件"""
    
    @property
    def name(self) -> str:
        return "Telegram Notifier"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "通过Telegram Bot发送通知"
        
    def initialize(self) -> bool:
        """初始化Telegram Bot"""
        try:
            self.bot_token = self.get_config('bot_token')
            self.chat_id = self.get_config('chat_id')
            
            if not self.bot_token or not self.chat_id:
                self.logger.error("Telegram配置不完整：缺少bot_token或chat_id")
                return False
                
            self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
            self.logger.info("Telegram通知插件初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"Telegram通知插件初始化失败: {e}")
            return False
            
    async def send_notification(self, message: NotificationMessage) -> bool:
        """发送Telegram通知"""
        try:
            # 格式化消息
            text = self.format_message(message)
            
            # 构建请求数据
            data = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': 'Markdown'
            }
            
            # 添加优先级标识
            if message.priority == 'urgent':
                data['text'] = f"🚨 *紧急* {text}"
            elif message.priority == 'high':
                data['text'] = f"⚠️ *重要* {text}"
                
            # 发送请求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/sendMessage",
                    json=data,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('ok'):
                            self.logger.info("Telegram通知发送成功")
                            return True
                        else:
                            self.logger.error(f"Telegram API错误: {result.get('description')}")
                            return False
                    else:
                        self.logger.error(f"HTTP错误: {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"发送Telegram通知失败: {e}")
            return False
            
    def test_connection(self) -> bool:
        """测试Telegram连接"""
        try:
            import requests
            
            response = requests.get(
                f"{self.api_url}/getMe",
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    bot_info = result.get('result', {})
                    self.logger.info(f"Telegram Bot连接成功: {bot_info.get('username')}")
                    return True
                    
            self.logger.error(f"Telegram连接测试失败: {response.text}")
            return False
            
        except Exception as e:
            self.logger.error(f"Telegram连接测试异常: {e}")
            return False
            
    def cleanup(self) -> None:
        """清理资源"""
        self.bot_token = None
        self.chat_id = None
        self.api_url = None
        self.logger.info("Telegram通知插件已清理")
```

## 🔄 数据处理器插件开发

### 数据处理器插件基类
```python
# plugins/base/data_processor_plugin.py
from .plugin_base import PluginBase
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class ProcessedData:
    """处理后的数据"""
    original_data: Any
    processed_data: Any
    metadata: Dict[str, Any] = None

class DataProcessorPluginBase(PluginBase):
    """数据处理器插件基类"""
    
    @abstractmethod
    def process(self, data: Any, options: Dict[str, Any] = None) -> ProcessedData:
        """处理数据"""
        pass
        
    @abstractmethod
    def get_supported_types(self) -> List[str]:
        """获取支持的数据类型"""
        pass
        
    def validate_data(self, data: Any) -> bool:
        """验证数据格式（可选重写）"""
        return True
```

### 文本后处理插件示例
```python
# plugins/processors/text_processor.py
import re
from typing import Dict, Any, List
from .data_processor_plugin import DataProcessorPluginBase, ProcessedData

class TextProcessorPlugin(DataProcessorPluginBase):
    """文本后处理插件"""
    
    @property
    def name(self) -> str:
        return "Text Processor"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "文本清理和格式化处理"
        
    def initialize(self) -> bool:
        """初始化文本处理规则"""
        try:
            # 加载配置的处理规则
            self.rules = self.get_config('processing_rules', {
                'remove_extra_spaces': True,
                'remove_special_chars': False,
                'normalize_punctuation': True,
                'remove_line_breaks': False
            })
            
            # 编译正则表达式
            self.compiled_patterns = {
                'extra_spaces': re.compile(r'\s+'),
                'special_chars': re.compile(r'[^\w\s\u4e00-\u9fff]'),
                'line_breaks': re.compile(r'[\r\n]+')
            }
            
            self.logger.info("文本处理插件初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"文本处理插件初始化失败: {e}")
            return False
            
    def process(self, data: str, options: Dict[str, Any] = None) -> ProcessedData:
        """处理文本数据"""
        try:
            if not isinstance(data, str):
                raise ValueError("输入数据必须是字符串类型")
                
            processed_text = data
            
            # 应用处理规则
            if self.rules.get('remove_extra_spaces', True):
                processed_text = self.compiled_patterns['extra_spaces'].sub(' ', processed_text)
                
            if self.rules.get('remove_special_chars', False):
                processed_text = self.compiled_patterns['special_chars'].sub('', processed_text)
                
            if self.rules.get('normalize_punctuation', True):
                # 标准化标点符号
                processed_text = self._normalize_punctuation(processed_text)
                
            if self.rules.get('remove_line_breaks', False):
                processed_text = self.compiled_patterns['line_breaks'].sub(' ', processed_text)
                
            # 去除首尾空白
            processed_text = processed_text.strip()
            
            # 创建处理结果
            result = ProcessedData(
                original_data=data,
                processed_data=processed_text,
                metadata={
                    'processing_rules': self.rules,
                    'original_length': len(data),
                    'processed_length': len(processed_text),
                    'changes_made': data != processed_text
                }
            )
            
            self.logger.debug(f"文本处理完成: {len(data)} -> {len(processed_text)} 字符")
            return result
            
        except Exception as e:
            self.logger.error(f"文本处理失败: {e}")
            raise
            
    def _normalize_punctuation(self, text: str) -> str:
        """标准化标点符号"""
        # 全角转半角
        punctuation_map = {
            '，': ',', '。': '.', '！': '!', '？': '?',
            '；': ';', '：': ':', '（': '(', '）': ')',
            '【': '[', '】': ']', '《': '<', '》': '>'
        }
        
        for full, half in punctuation_map.items():
            text = text.replace(full, half)
            
        return text
        
    def get_supported_types(self) -> List[str]:
        """获取支持的数据类型"""
        return ['text', 'string']
        
    def cleanup(self) -> None:
        """清理资源"""
        self.rules = None
        self.compiled_patterns = None
        self.logger.info("文本处理插件已清理")
```

## 🔌 插件管理

### 插件管理器
```python
# core/plugin_manager.py
import importlib
import inspect
from typing import Dict, List, Type, Any
from pathlib import Path
import json

class PluginManager:
    """插件管理器"""
    
    def __init__(self):
        self.plugins: Dict[str, PluginBase] = {}
        self.plugin_config = {}
        self.load_plugin_config()
        
    def load_plugin_config(self):
        """加载插件配置"""
        config_path = Path("plugins/config/plugin_config.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                self.plugin_config = json.load(f)
                
    def discover_plugins(self, plugin_dir: str = "plugins") -> List[Type[PluginBase]]:
        """发现插件"""
        plugin_classes = []
        plugin_path = Path(plugin_dir)
        
        for plugin_file in plugin_path.rglob("*.py"):
            if plugin_file.name.startswith("__"):
                continue
                
            try:
                # 动态导入模块
                module_name = str(plugin_file.relative_to(plugin_path.parent)).replace("/", ".").replace("\\", ".")[:-3]
                module = importlib.import_module(module_name)
                
                # 查找插件类
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, PluginBase) and 
                        obj != PluginBase and 
                        not inspect.isabstract(obj)):
                        plugin_classes.append(obj)
                        
            except Exception as e:
                print(f"加载插件失败 {plugin_file}: {e}")
                
        return plugin_classes
        
    def load_plugin(self, plugin_class: Type[PluginBase], plugin_id: str) -> bool:
        """加载插件"""
        try:
            # 获取插件配置
            config = self.plugin_config.get(plugin_id, {})
            
            # 检查是否启用
            if not config.get('enabled', False):
                return False
                
            # 创建插件实例
            plugin_instance = plugin_class(config)
            
            # 初始化插件
            if plugin_instance.initialize():
                self.plugins[plugin_id] = plugin_instance
                print(f"插件加载成功: {plugin_id}")
                return True
            else:
                print(f"插件初始化失败: {plugin_id}")
                return False
                
        except Exception as e:
            print(f"加载插件异常 {plugin_id}: {e}")
            return False
            
    def unload_plugin(self, plugin_id: str):
        """卸载插件"""
        if plugin_id in self.plugins:
            plugin = self.plugins[plugin_id]
            plugin.cleanup()
            del self.plugins[plugin_id]
            print(f"插件卸载成功: {plugin_id}")
            
    def get_plugin(self, plugin_id: str) -> PluginBase:
        """获取插件实例"""
        return self.plugins.get(plugin_id)
        
    def get_plugins_by_type(self, plugin_type: Type[PluginBase]) -> List[PluginBase]:
        """根据类型获取插件"""
        return [plugin for plugin in self.plugins.values() 
                if isinstance(plugin, plugin_type)]
```

## 📦 插件打包和分发

### 插件包结构
```
my_custom_plugin/
├── __init__.py
├── plugin.py              # 主插件文件
├── requirements.txt       # 依赖包
├── config.json           # 默认配置
├── README.md             # 插件说明
└── setup.py              # 安装脚本
```

### 插件安装脚本
```python
# setup.py
from setuptools import setup, find_packages

setup(
    name="xuanwu-custom-ocr-plugin",
    version="1.0.0",
    description="自定义OCR插件",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
        "aiohttp>=3.8.0"
    ],
    entry_points={
        'xuanwu.plugins': [
            'custom_ocr = my_plugin:CustomOCRPlugin',
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
)
```

## 🧪 插件测试

### 插件测试示例
```python
# tests/plugins/test_google_ocr.py
import pytest
from unittest.mock import Mock, patch
from plugins.ocr.google_ocr import GoogleOCRPlugin

class TestGoogleOCRPlugin:
    
    @pytest.fixture
    def plugin_config(self):
        return {
            'credentials_path': 'test_credentials.json',
            'confidence_threshold': 0.8
        }
        
    @pytest.fixture
    def plugin(self, plugin_config):
        return GoogleOCRPlugin(plugin_config)
        
    def test_plugin_initialization(self, plugin):
        with patch('plugins.ocr.google_ocr.vision.ImageAnnotatorClient'):
            assert plugin.initialize() == True
            assert plugin.name == "Google Vision OCR"
            assert plugin.version == "1.0.0"
            
    def test_get_supported_languages(self, plugin):
        languages = plugin.get_supported_languages()
        assert 'zh' in languages
        assert 'en' in languages
        assert 'ja' in languages
        
    def test_get_max_image_size(self, plugin):
        max_size = plugin.get_max_image_size()
        assert max_size == (2048, 2048)
        
    @pytest.mark.asyncio
    async def test_recognize_text(self, plugin):
        with patch('plugins.ocr.google_ocr.vision.ImageAnnotatorClient') as mock_client:
            # 模拟API响应
            mock_response = Mock()
            mock_response.error.message = ""
            mock_response.text_annotations = [
                Mock(description="Hello World"),
                Mock(description="Hello", score=0.9),
                Mock(description="World", score=0.8)
            ]
            
            mock_client.return_value.text_detection.return_value = mock_response
            
            plugin.initialize()
            
            # 测试识别
            result = await plugin.recognize_text(b"fake_image_data")
            
            assert result.text == "Hello World"
            assert result.confidence > 0
            assert result.language == "unknown"
```

## 📚 插件开发最佳实践

### 错误处理
```python
class RobustPlugin(PluginBase):
    """健壮的插件示例"""
    
    def initialize(self) -> bool:
        try:
            # 初始化逻辑
            self.setup_components()
            return True
        except Exception as e:
            self.logger.error(f"插件初始化失败: {e}", exc_info=True)
            # 清理已创建的资源
            self.cleanup_partial_init()
            return False
            
    def cleanup_partial_init(self):
        """清理部分初始化的资源"""
        pass
```

### 配置验证
```python
def validate_config(self, config: Dict[str, Any]) -> List[str]:
    """验证插件配置"""
    errors = []
    
    required_fields = ['api_key', 'endpoint']
    for field in required_fields:
        if field not in config:
            errors.append(f"缺少必需配置: {field}")
            
    if 'timeout' in config:
        try:
            timeout = int(config['timeout'])
            if timeout <= 0:
                errors.append("超时时间必须大于0")
        except ValueError:
            errors.append("超时时间必须是数字")
            
    return errors
```

### 性能优化
```python
class OptimizedPlugin(PluginBase):
    """性能优化的插件"""
    
    def __init__(self, config):
        super().__init__(config)
        self.connection_pool = None
        self.cache = {}
        
    def initialize(self) -> bool:
        # 创建连接池
        self.connection_pool = aiohttp.ClientSession()
        return True
        
    async def process_with_cache(self, data: str) -> Any:
        """带缓存的处理"""
        cache_key = hashlib.md5(data.encode()).hexdigest()
        
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        result = await self.expensive_operation(data)
        self.cache[cache_key] = result
        
        # 限制缓存大小
        if len(self.cache) > 1000:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            
        return result
```

---

*插件开发完成后，建议进行充分的测试并编写详细的文档说明。*
