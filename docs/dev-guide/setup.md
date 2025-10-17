# 开发环境搭建

本指南将帮助开发者搭建 XuanWu OCR 的开发环境，包括环境配置、依赖安装、调试设置等。

## 📋 开发环境要求

### 系统要求
- **操作系统**: Windows 10/11, macOS 10.15+, Ubuntu 18.04+
- **Python版本**: Python 3.8 或更高版本
- **内存**: 8GB RAM（推荐 16GB）
- **存储空间**: 5GB 可用磁盘空间
- **网络**: 稳定的互联网连接

### 推荐工具
- **代码编辑器**: VS Code, PyCharm, Sublime Text
- **版本控制**: Git
- **包管理**: pip, conda（可选）
- **调试工具**: Python Debugger (pdb), VS Code Debugger

## 🚀 快速搭建

### 1. 克隆项目
```bash
# 克隆主仓库
git clone https://github.com/liangrenyumao00-sketch/XuanWu-Output-Update.git
cd XuanWu-Output-Update

# 添加上游仓库（如果是fork）
git remote add upstream https://github.com/liangrenyumao00-sketch/XuanWu-Output-Update.git
```

### 2. 创建虚拟环境
```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. 安装依赖
```bash
# 安装基础依赖
pip install -r requirements.txt

# 安装开发依赖
pip install -r requirements-dev.txt
```

### 4. 配置环境
```bash
# 复制配置文件模板
cp config/config.template.json config/config.json

# 编辑配置文件
# 填入你的API密钥和其他配置
```

### 5. 运行程序
```bash
# 启动开发模式
python main.py --dev

# 或者直接运行
python main.py
```

## 🔧 详细配置

### Python环境配置

#### 使用pyenv管理Python版本
```bash
# 安装pyenv
curl https://pyenv.run | bash

# 安装Python 3.9
pyenv install 3.9.16
pyenv global 3.9.16

# 验证安装
python --version
```

#### 使用conda管理环境
```bash
# 创建conda环境
conda create -n xuanwu python=3.9

# 激活环境
conda activate xuanwu

# 安装依赖
conda install pip
pip install -r requirements.txt
```

### 开发工具配置

#### VS Code配置
```json
{
  "python.defaultInterpreterPath": "./venv/Scripts/python.exe",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true
  }
}
```

#### PyCharm配置
1. 打开项目
2. 配置Python解释器：File → Settings → Project → Python Interpreter
3. 选择虚拟环境中的Python解释器
4. 配置代码检查：File → Settings → Editor → Inspections

### 依赖管理

#### requirements.txt结构
```
# 核心依赖
PyQt6>=6.4.0
requests>=2.28.0
Pillow>=9.0.0
opencv-python>=4.6.0

# OCR相关
baidu-aip>=4.16.0
tencentcloud-sdk-python>=3.0.0

# 数据处理
pandas>=1.5.0
numpy>=1.21.0
matplotlib>=3.5.0

# 开发工具
pytest>=7.0.0
black>=22.0.0
flake8>=5.0.0
mypy>=0.991
```

#### requirements-dev.txt
```
# 开发依赖
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0
black>=22.0.0
flake8>=5.0.0
mypy>=0.991
pre-commit>=2.20.0

# 调试工具
ipdb>=0.13.0
memory-profiler>=0.60.0
line-profiler>=4.0.0
```

## 🛠️ 开发工具配置

### 代码格式化

#### Black配置
```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py38']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | build
  | dist
)/
'''
```

#### Pre-commit配置
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 22.10.0
    hooks:
      - id: black
        language_version: python3.9

  - repo: https://github.com/pycqa/flake8
    rev: 5.0.4
    hooks:
      - id: flake8

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v0.991
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-Pillow]
```

### 代码检查

#### Flake8配置
```ini
# .flake8
[flake8]
max-line-length = 88
extend-ignore = E203, W503
exclude = 
    .git,
    __pycache__,
    .venv,
    venv,
    build,
    dist
```

#### MyPy配置
```ini
# mypy.ini
[mypy]
python_version = 3.9
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
disallow_untyped_decorators = True
no_implicit_optional = True
warn_redundant_casts = True
warn_unused_ignores = True
warn_no_return = True
warn_unreachable = True
strict_equality = True
```

### 测试配置

#### Pytest配置
```ini
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --verbose
    --tb=short
    --cov=.
    --cov-report=html
    --cov-report=term-missing
```

#### 测试目录结构
```
tests/
├── unit/
│   ├── test_core/
│   ├── test_widgets/
│   └── test_utils/
├── integration/
│   ├── test_api/
│   └── test_ui/
├── fixtures/
│   ├── test_data.json
│   └── sample_images/
└── conftest.py
```

## 🐛 调试配置

### 调试环境变量
```bash
# 开发模式
export XUANWU_DEV=1
export XUANWU_LOG_LEVEL=DEBUG

# 调试模式
export XUANWU_DEBUG=1
export XUANWU_PROFILE=1

# 测试模式
export XUANWU_TEST=1
```

### VS Code调试配置
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: XuanWu OCR",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/main.py",
      "console": "integratedTerminal",
      "env": {
        "XUANWU_DEV": "1",
        "XUANWU_LOG_LEVEL": "DEBUG"
      },
      "args": ["--dev"]
    },
    {
      "name": "Python: Current File",
      "type": "python",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal"
    }
  ]
}
```

### 性能调试工具

#### 内存分析
```python
# 使用memory_profiler
from memory_profiler import profile

@profile
def your_function():
    # 你的代码
    pass

# 使用tracemalloc
import tracemalloc

tracemalloc.start()
# 你的代码
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')
```

#### 性能分析
```python
# 使用cProfile
import cProfile
import pstats

def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # 你的代码
    your_function()
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats()
```

## 📦 构建和打包

### 构建配置

#### PyInstaller配置
```python
# build.py
import PyInstaller.__main__

PyInstaller.__main__.run([
    'main.py',
    '--onefile',
    '--windowed',
    '--name=XuanWu_OCR',
    '--icon=285.ico',
    '--add-data=locales;locales',
    '--add-data=assets;assets',
    '--hidden-import=PyQt6',
    '--hidden-import=requests',
])
```

#### 自动化构建脚本
```bash
#!/bin/bash
# build.sh

# 清理旧的构建文件
rm -rf build/ dist/

# 创建虚拟环境
python -m venv build_env
source build_env/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install pyinstaller

# 构建可执行文件
python build.py

# 打包发布
zip -r XuanWu_OCR_v2.1.9.zip dist/

# 清理
deactivate
rm -rf build_env/
```

## 🧪 测试环境

### 单元测试
```python
# tests/unit/test_core/test_ocr.py
import pytest
from unittest.mock import Mock, patch
from core.ocr_worker import OCRWorker

class TestOCRWorker:
    def test_ocr_initialization(self):
        worker = OCRWorker()
        assert worker.is_running == False
    
    @patch('core.ocr_worker.requests.post')
    def test_api_call(self, mock_post):
        mock_post.return_value.json.return_value = {
            'words_result': [{'words': 'test'}]
        }
        
        worker = OCRWorker()
        result = worker.recognize_text('test_image')
        
        assert result == 'test'
        mock_post.assert_called_once()
```

### 集成测试
```python
# tests/integration/test_api/test_baidu_api.py
import pytest
from core.api.baidu_api import BaiduAPI

class TestBaiduAPI:
    @pytest.fixture
    def api(self):
        return BaiduAPI('test_key', 'test_secret')
    
    def test_api_initialization(self, api):
        assert api.api_key == 'test_key'
        assert api.secret_key == 'test_secret'
    
    @pytest.mark.asyncio
    async def test_async_recognition(self, api):
        # 异步测试
        result = await api.recognize_async('test_image')
        assert result is not None
```

### UI测试
```python
# tests/integration/test_ui/test_main_window.py
import pytest
from PyQt6.QtWidgets import QApplication
from widgets.main_window import MainWindow

@pytest.fixture
def app():
    return QApplication([])

@pytest.fixture
def window(app):
    return MainWindow()

def test_window_creation(window):
    assert window.isVisible() == False
    
def test_menu_bar(window):
    assert window.menuBar() is not None
    
def test_status_bar(window):
    assert window.statusBar() is not None
```

## 📚 文档开发

### API文档生成
```python
# 使用Sphinx生成API文档
# docs/source/conf.py
import os
import sys
sys.path.insert(0, os.path.abspath('../..'))

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
]

# 自动生成API文档
# sphinx-apidoc -o docs/source/api . --separate
```

### 文档构建
```bash
# 构建文档
cd docs
sphinx-build -b html source build

# 或者使用Makefile
make html
```

## 🔄 CI/CD配置

### GitHub Actions
```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, "3.10"]

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Lint with flake8
      run: |
        flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
    
    - name: Type check with mypy
      run: |
        mypy . --ignore-missing-imports
    
    - name: Test with pytest
      run: |
        pytest --cov=. --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

## 🚀 部署配置

### Docker配置
```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

### Docker Compose
```yaml
# docker-compose.yml
version: '3.8'

services:
  xuanwu:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    environment:
      - XUANWU_DEV=0
      - XUANWU_LOG_LEVEL=INFO
```

## 📋 开发检查清单

### 提交前检查
- [ ] 代码通过所有测试
- [ ] 代码通过linting检查
- [ ] 代码通过类型检查
- [ ] 更新相关文档
- [ ] 添加必要的注释
- [ ] 检查API兼容性

### 发布前检查
- [ ] 更新版本号
- [ ] 更新CHANGELOG
- [ ] 运行完整测试套件
- [ ] 构建发布包
- [ ] 测试安装包
- [ ] 更新文档

---

*开发环境搭建完成后，建议先阅读 [代码规范](coding-standards.md) 了解项目的编码标准。*
