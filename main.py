# main.py
import sys
import os
import ctypes
import logging
import coloredlogs
import atexit
import platform
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

# 控制台输出过滤器 - 隐藏Windows系统错误
class ConsoleFilter:
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr
        self.filtered_patterns = [
            "UpdateLayeredWindowIndirect failed"
        ]
    
    def write(self, text):
        # 检查是否包含需要过滤的模式
        should_filter = any(pattern in text for pattern in self.filtered_patterns)
        if not should_filter:
            self.original_stderr.write(text)
    
    def flush(self):
        self.original_stderr.flush()

# 安装控制台过滤器
if hasattr(sys, 'stderr'):
    sys.stderr = ConsoleFilter(sys.stderr)

# 设置Qt日志过滤环境变量
os.environ['QT_LOGGING_RULES'] = 'qt.qpa.windows.debug=false'

# Windows平台特定的控制台输出隐藏
if platform.system() == 'Windows':
    try:
        import ctypes
        from ctypes import wintypes
        
        # 获取控制台句柄
        kernel32 = ctypes.windll.kernel32
        
        # 重定向stderr到NUL设备来隐藏Windows系统错误
        class WindowsConsoleFilter:
            def __init__(self):
                self.original_stderr = sys.stderr
                self.filtered_patterns = [
                    "UpdateLayeredWindowIndirect failed"
                ]
            
            def write(self, text):
                # 检查是否包含需要过滤的模式
                should_filter = any(pattern in text for pattern in self.filtered_patterns)
                if not should_filter:
                    self.original_stderr.write(text)
                    self.original_stderr.flush()
            
            def flush(self):
                self.original_stderr.flush()
        
        # 替换stderr
        sys.stderr = WindowsConsoleFilter()
        
    except Exception as e:
        print(f"Windows控制台过滤器初始化失败: {e}")

from PyQt6.QtGui import QAction, QColor, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QMessageBox, QDialog, QLineEdit, QCheckBox, QSpinBox, QComboBox
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer

# 导入新的应用初始化器
from core.app_initializer import initialize_application, get_app_initializer

from widgets.control_panel import ControlPanel
from widgets.keyword_panel import KeywordPanel
from widgets.log_panel import LogPanel
from widgets.region_selector import RegionSelector
from widgets.status_panel import StatusPanel
from widgets.dev_tools_panel import DevToolsPanel
from widgets.apikey_dialog import ApiKeyDialog
from widgets.history_panel import HistoryPanel, HistoryDialog
from widgets.analytics_panel import AnalyticsPanel
from widgets.email_settings_dialog import EmailSettingsDialog
from widgets.help_window import HelpWindow
from widgets.dynamic_island import DynamicIsland, dynamic_island_manager

# 移除不再使用的导入
from widgets.settings_panel import create_setting_dialog
from core.ocr_worker_threaded import OCRWorker, OCRThread, SingleImageOCRThread
from core.index_builder import build_log_index
from core.config import SCREENSHOT_DIR
from core.theme import apply_theme
from core.settings import load_settings, save_settings, register_settings_callback
from core.backup_manager import BackupManager
from core.enhanced_logger import init_enhanced_logging, get_enhanced_logger
from core.log_config_manager import init_log_config, get_log_config_manager
from core.log_desensitizer import get_log_desensitizer
from core.i18n import t

# ================= 日志初始化代码 =======================
# Debug日志HTML模板 - 橙色主题
DEBUG_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'JetBrains Mono', 'Consolas', 'Monaco', monospace;
            background: linear-gradient(135deg, #1a1a1a 0%, #2d1810 100%);
            color: #f0f0f0;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .header {{
            background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);
            color: white;
            padding: 20px;
            margin-bottom: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(255, 107, 53, 0.3);
            border: 1px solid #ff8c42;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 24px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .header p {{
            margin: 0;
            opacity: 0.9;
            font-size: 14px;
        }}
        .filter-controls {{
            background: rgba(255, 255, 255, 0.05);
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 8px;
            border: 1px solid rgba(255, 140, 66, 0.3);
        }}
        .filter-controls h3 {{
            margin: 0 0 10px 0;
            color: #ff8c42;
            font-size: 14px;
        }}
        .filter-buttons {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .filter-btn {{
            padding: 6px 12px;
            border: 1px solid #555;
            background: rgba(255, 255, 255, 0.1);
            color: #f0f0f0;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s ease;
        }}
        .filter-btn:hover {{
            background: rgba(255, 140, 66, 0.2);
            border-color: #ff8c42;
        }}
        .filter-btn.active {{
            background: #ff8c42;
            color: #000;
            border-color: #ff8c42;
        }}
        .log-entry {{
            margin: 8px 0;
            padding: 12px;
            border-radius: 6px;
            border-left: 4px solid #555;
            background: rgba(255, 255, 255, 0.02);
            transition: all 0.2s ease;
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }}
        .log-entry:hover {{
            background: rgba(255, 255, 255, 0.05);
            transform: translateX(2px);
        }}
        .log-entry.hidden {{
            display: none;
        }}
        .debug {{ border-left-color: #4fc3f7; background: rgba(79, 195, 247, 0.08); }}
        .info {{ border-left-color: #66bb6a; background: rgba(102, 187, 106, 0.08); }}
        .warning {{ border-left-color: #ffb74d; background: rgba(255, 183, 77, 0.12); }}
        .error {{ border-left-color: #ef5350; background: rgba(239, 83, 80, 0.12); }}
        .critical {{ border-left-color: #e91e63; background: rgba(233, 30, 99, 0.15); }}
        .log-timestamp {{
            color: #ff8c42;
            font-weight: 500;
            min-width: 140px;
            font-size: 12px;
        }}
        .log-level {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
            min-width: 60px;
            text-align: center;
            text-transform: uppercase;
        }}
        .debug .log-level {{ background: #4fc3f7; color: #000; }}
        .info .log-level {{ background: #66bb6a; color: #fff; }}
        .warning .log-level {{ background: #ffb74d; color: #000; }}
        .error .log-level {{ background: #ef5350; color: #fff; }}
        .critical .log-level {{ background: #e91e63; color: #fff; }}
        .log-message {{
            flex: 1;
            word-break: break-word;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔧 {title}</h1>
        <p>📅 生成时间: {timestamp} | 🐛 调试模式</p>
    </div>
    <div class="filter-controls">
        <h3>🔍 日志级别过滤</h3>
        <div class="filter-buttons">
            <button class="filter-btn active" onclick="filterLogs('all', this)">全部</button>
            <button class="filter-btn" onclick="filterLogs('debug', this)">DEBUG</button>
            <button class="filter-btn" onclick="filterLogs('info', this)">INFO</button>
            <button class="filter-btn" onclick="filterLogs('warning', this)">WARNING</button>
            <button class="filter-btn" onclick="filterLogs('error', this)">ERROR</button>
            <button class="filter-btn" onclick="filterLogs('critical', this)">CRITICAL</button>
        </div>
    </div>
    <div id="logs">
"""

# 系统日志HTML模板 - 蓝色主题
SYSTEM_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'JetBrains Mono', 'Consolas', 'Monaco', monospace;
            background: linear-gradient(135deg, #0f1419 0%, #1a2332 100%);
            color: #e8f4fd;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .header {{
            background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%);
            color: white;
            padding: 20px;
            margin-bottom: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(25, 118, 210, 0.3);
            border: 1px solid #42a5f5;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 24px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .header p {{
            margin: 0;
            opacity: 0.9;
            font-size: 14px;
        }}
        .filter-controls {{
            background: rgba(255, 255, 255, 0.05);
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 8px;
            border: 1px solid rgba(66, 165, 245, 0.3);
        }}
        .filter-controls h3 {{
            margin: 0 0 10px 0;
            color: #64b5f6;
            font-size: 14px;
        }}
        .filter-buttons {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .filter-btn {{
            padding: 6px 12px;
            border: 1px solid #555;
            background: rgba(255, 255, 255, 0.1);
            color: #e8f4fd;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s ease;
        }}
        .filter-btn:hover {{
            background: rgba(100, 181, 246, 0.2);
            border-color: #64b5f6;
        }}
        .filter-btn.active {{
            background: #64b5f6;
            color: #000;
            border-color: #64b5f6;
        }}
        .log-entry {{
            margin: 8px 0;
            padding: 12px;
            border-radius: 6px;
            border-left: 4px solid #555;
            background: rgba(255, 255, 255, 0.02);
            transition: all 0.2s ease;
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }}
        .log-entry:hover {{
            background: rgba(255, 255, 255, 0.05);
            transform: translateX(2px);
        }}
        .log-entry.hidden {{
            display: none;
        }}
        .debug {{ border-left-color: #81c784; background: rgba(129, 199, 132, 0.08); }}
        .info {{ border-left-color: #64b5f6; background: rgba(100, 181, 246, 0.08); }}
        .warning {{ border-left-color: #ffb74d; background: rgba(255, 183, 77, 0.12); }}
        .error {{ border-left-color: #e57373; background: rgba(229, 115, 115, 0.12); }}
        .critical {{ border-left-color: #f06292; background: rgba(240, 98, 146, 0.15); }}
        .log-timestamp {{
            color: #64b5f6;
            font-weight: 500;
            min-width: 140px;
            font-size: 12px;
        }}
        .log-level {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
            min-width: 60px;
            text-align: center;
            text-transform: uppercase;
        }}
        .debug .log-level {{ background: #81c784; color: #000; }}
        .info .log-level {{ background: #64b5f6; color: #fff; }}
        .warning .log-level {{ background: #ffb74d; color: #000; }}
        .error .log-level {{ background: #e57373; color: #fff; }}
        .critical .log-level {{ background: #f06292; color: #fff; }}
        .log-message {{
            flex: 1;
            word-break: break-word;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 {title}</h1>
        <p>📅 生成时间: {timestamp} | ⚙️ 系统日志</p>
    </div>
    <div class="filter-controls">
        <h3>🔍 日志级别过滤</h3>
        <div class="filter-buttons">
            <button class="filter-btn active" onclick="filterLogs('all', this)">全部</button>
            <button class="filter-btn" onclick="filterLogs('debug', this)">DEBUG</button>
            <button class="filter-btn" onclick="filterLogs('info', this)">INFO</button>
            <button class="filter-btn" onclick="filterLogs('warning', this)">WARNING</button>
            <button class="filter-btn" onclick="filterLogs('error', this)">ERROR</button>
            <button class="filter-btn" onclick="filterLogs('critical', this)">CRITICAL</button>
        </div>
    </div>
    <div id="logs">
"""
HTML_FOOTER = """    </div>
    <script>
        function filterLogs(level, buttonElement) {
            // 移除所有按钮的active状态
            const buttons = document.querySelectorAll('.filter-btn');
            buttons.forEach(btn => btn.classList.remove('active'));
            
            // 设置当前按钮为active
            if (buttonElement) {
                buttonElement.classList.add('active');
            } else {
                // 如果没有传入按钮元素，找到对应的按钮
                const targetButton = Array.from(buttons).find(btn => {
                    const text = btn.textContent.toLowerCase();
                    return (level === 'all' && text === '全部') || text === level.toUpperCase();
                });
                if (targetButton) {
                    targetButton.classList.add('active');
                }
            }
            
            // 获取所有日志条目
            const logEntries = document.querySelectorAll('.log-entry');
            
            if (level === 'all') {
                // 显示所有日志
                logEntries.forEach(entry => {
                    entry.classList.remove('hidden');
                });
            } else {
                // 根据级别过滤
                logEntries.forEach(entry => {
                    if (entry.classList.contains(level)) {
                        entry.classList.remove('hidden');
                    } else {
                        entry.classList.add('hidden');
                    }
                });
            }
        }
        
        // 页面加载完成后的初始化
        document.addEventListener('DOMContentLoaded', function() {
            // 默认显示所有日志
            filterLogs('all');
        });
    </script>
</body>
</html>
"""

class HtmlFileHandler(logging.FileHandler):
    """增强的HTML格式日志文件处理器 - 支持不同主题"""
    
    def __init__(self, filename: str, title: str = 'Log', mode: str = 'w', 
                 encoding: Optional[str] = None, delay: bool = False) -> None:
        """初始化HTML文件处理器"""
        if encoding is None:
            encoding = 'utf-8'
        
        # 确保目录存在
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        super().__init__(filename, mode, encoding, delay)
        self.title = title
        self.header_written = False
        
        # 根据文件名选择模板
        if 'debug' in filename.lower():
            self.template = DEBUG_HTML_TEMPLATE
        else:
            self.template = SYSTEM_HTML_TEMPLATE
        
        # 如果是写模式且不延迟，创建空的HTML结构
        if not delay and mode == 'w' and self.stream:
            self._write_initial_structure()
    
    def _write_initial_structure(self):
        """写入完整的初始HTML结构"""
        if not self.stream:
            return
            
        import time
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        header = self.template.format(title=self.title, timestamp=timestamp)
        # 写入完整的HTML结构，包括空的日志区域和结尾
        full_html = header + HTML_FOOTER
        self.stream.write(full_html)
        self.stream.flush()
        self.header_written = True
        
    def _write_header(self):
        """写入HTML头部"""
        if not self.stream:
            return
            
        import time
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        header = HTML_TEMPLATE.format(title=self.title, timestamp=timestamp)
        self.stream.write(header)
        self.stream.flush()
        self.header_written = True

    def emit(self, record):
        """发出日志记录 - 插入到HTML结构中"""
        try:
            # 检查stream是否可用
            if not self.stream:
                return
                
            # 格式化时间戳
            import time
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record.created))
            level = record.levelname
            level_class = level.lower()
            
            # 获取并转义消息内容
            if hasattr(record, 'getMessage'):
                msg = record.getMessage()
            else:
                msg = str(record.msg)
            
            # 转义HTML特殊字符
            escaped_msg = (str(msg).replace('&', '&amp;')
                             .replace('<', '&lt;')
                             .replace('>', '&gt;')
                             .replace('"', '&quot;')
                             .replace("'", '&#x27;'))
            
            # 构建日志条目
            html_entry = f'''        <div class="log-entry {level_class}">\n            <div class="log-timestamp">{timestamp}</div>\n            <div class="log-level">{level}</div>\n            <div class="log-message">{escaped_msg}</div>\n        </div>\n'''
            
            # 读取现有文件内容
            if self.stream:
                self.stream.close()
            with open(self.baseFilename, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找logs容器的结束标签
            logs_marker = '<div id="logs">'
            logs_start = content.find(logs_marker)
            if logs_start != -1:
                # 找到logs容器开始位置后的内容
                logs_content_start = logs_start + len(logs_marker)
                # 查找对应的结束div标签
                script_start = content.find('<script>', logs_content_start)
                if script_start != -1:
                    # 在script标签前插入日志条目
                    insert_pos = content.rfind('</div>', logs_content_start, script_start)
                    if insert_pos != -1:
                        new_content = content[:insert_pos] + html_entry + content[insert_pos:]
                    else:
                        # 直接在script前插入
                        new_content = content[:script_start] + html_entry + '    </div>\n    ' + content[script_start:]
                else:
                    # 如果找不到script，重新创建文件
                    self._write_initial_structure()
                    return
            else:
                # 如果找不到logs容器，重新创建文件
                self._write_initial_structure()
                return
            
            # 重写文件
            with open(self.baseFilename, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # 重新打开流
            self.stream = open(self.baseFilename, 'a', encoding='utf-8')
            
        except Exception as e:
            # 如果出错，尝试重新初始化
            try:
                self._write_initial_structure()
            except (OSError, IOError):
                pass
    
    def close(self) -> None:
        """关闭文件处理器并写入HTML结尾"""
        try:
            if not self.stream.closed:
                # 写入HTML结尾
                self.stream.write(HTML_FOOTER)
                self.stream.flush()
        except Exception:
            pass
        super().close()

# 初始化增强日志系统
init_log_config()
init_enhanced_logging()
enhanced_logger = get_enhanced_logger()
log_config_manager = get_log_config_manager()

LOG_DEBUG_PATH = os.path.join("logs", "debug.html")
LOG_XUANWU_PATH = os.path.join("logs", "xuanwu_log.html")
os.makedirs("logs", exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

LOGS_DIR = "XuanWu_Logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)
    logging.info(f"创建日志文件夹: {LOGS_DIR}")

startup = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 清理现有的HTML日志文件，确保每次启动都是干净的状态
for log_path in [LOG_DEBUG_PATH, LOG_XUANWU_PATH]:
    if os.path.exists(log_path):
        try:
            os.remove(log_path)
        except Exception:
            pass

# 初始化debug.html文件 - 记录调试和技术相关日志
debug_handler = HtmlFileHandler(LOG_DEBUG_PATH, title="XuanWu Debug Log", mode='w')

# 初始化xuanwu_log.html文件 - 记录用户操作和系统状态日志
xuanwu_handler = HtmlFileHandler(LOG_XUANWU_PATH, title="XuanWu System Log", mode='w')
xuanwu_logger = logging.getLogger('xuanwu_log')
xuanwu_logger.addHandler(xuanwu_handler)
xuanwu_logger.setLevel(logging.DEBUG)
xuanwu_logger.propagate = False  # 防止传播到root logger，避免重复记录

# 配置各模块的专用logger，避免重复记录
def setup_module_loggers():
    """配置各模块的专用logger，按功能分类到不同的HTML文件"""
    
    # 调试相关模块 -> debug.html
    debug_modules = [
        'DevToolsLogger',  # 开发者工具
        'enhanced_logger',  # 增强日志器
        'performance_manager',  # 性能管理
        'ocr_worker'  # OCR工作线程调试
    ]
    
    # 系统操作相关模块 -> xuanwu_log.html  
    system_modules = [
        'backup_manager',  # 备份管理
        'cloud_sync',  # 云同步
        'hotkey_manager',  # 快捷键管理
        'email_notifier',  # 邮件通知
        'apikey_dialog',  # API密钥管理
        'settings_manager',  # 设置管理
        'keyword_manager',  # 关键词管理
        'i18n_manager',  # 国际化管理
        'web_preview_server'  # Web预览服务器
    ]
    
    # 为调试模块配置debug_handler
    for module_name in debug_modules:
        module_logger = logging.getLogger(module_name)
        module_logger.addHandler(debug_handler)
        module_logger.setLevel(logging.DEBUG)
        module_logger.propagate = False
    
    # 为系统模块配置xuanwu_handler
    for module_name in system_modules:
        module_logger = logging.getLogger(module_name)
        module_logger.addHandler(xuanwu_handler)
        module_logger.setLevel(logging.INFO)
        module_logger.propagate = False
    
    # root logger只添加debug_handler，用于捕获未分类的日志
    root_logger = logging.getLogger()
    root_logger.addHandler(debug_handler)
    root_logger.setLevel(logging.DEBUG)

# 执行模块logger配置
setup_module_loggers()

# 记录启动信息到系统日志
xuanwu_logger.info(f"🚀 XuanWu v{open('version.txt').read().strip()} 启动: {startup}")
xuanwu_logger.info(f"💻 系统环境: {platform.system()} {platform.release()} | Python: {platform.python_version()}")
xuanwu_logger.info(f"📁 工作目录: {os.getcwd()}")

# 记录系统配置信息
try:
    from core.settings import load_settings
    settings = load_settings()
    xuanwu_logger.info(f"⚙️ 配置加载完成 - 主题: {settings.get('theme', '未知')} | 语言: {settings.get('language', '未知')}")
    xuanwu_logger.info(f"📊 日志级别: {settings.get('log_level', 'INFO')} | OCR版本: {settings.get('ocr_version', 'general')}")
except Exception as e:
    logging.error(f"配置信息读取失败: {e}")

# 记录性能监控初始化
try:
    from core.performance_manager import PerformanceManager
    perf_manager = PerformanceManager()
    current_perf = perf_manager.collect_current_performance()
    xuanwu_logger.info(f"📈 性能监控启动 - CPU: {current_perf.get('cpu_percent', 0):.1f}% | 内存: {current_perf.get('memory_percent', 0):.1f}%")
except Exception as e:
    logging.debug(f"性能监控初始化失败: {e}")

# 记录调试启动信息
logging.debug(f"🔧 调试模式启动: {startup}")

@atexit.register
def _close() -> None:
    """程序退出时关闭日志文件"""
    try:
        debug_handler.close()
        xuanwu_handler.close()
        enhanced_logger.shutdown()
    except Exception:
        pass

# 设置日志格式
fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
debug_handler.setFormatter(fmt)
debug_handler.setLevel(logging.DEBUG)  # 确保HTML处理器接收所有级别的日志
logging.getLogger().setLevel(log_config_manager.get_log_level())
coloredlogs.install(level='DEBUG', fmt='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# 重新添加HTML处理器（coloredlogs可能会清除处理器）
root_logger = logging.getLogger()
root_logger.addHandler(debug_handler)
debug_handler.setLevel(logging.DEBUG)  # 再次确保级别设置

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    pass
    
def detect_system_theme() -> str:
    """
    检测 Windows 系统主题，返回 'light' 或 'dark'
    
    Returns:
        系统主题类型，'light' 或 'dark'
    """
    try:
        registry = ctypes.windll.advapi32
        hKey = ctypes.c_void_p()
        result = registry.RegOpenKeyExW(
            0x80000001,  # HKEY_CURRENT_USER
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            0,
            0x20019,  # KEY_READ
            ctypes.byref(hKey)
        )
        if result != 0:
            return 'light'  # 无法访问注册表默认使用 light

        # 读取 AppsUseLightTheme 的值
        value = ctypes.c_int()
        size = ctypes.c_uint(4)
        registry.RegQueryValueExW(hKey, "AppsUseLightTheme", 0, None, ctypes.byref(value), ctypes.byref(size))

        return 'light' if value.value == 1 else 'dark'
    except Exception as e:
        logging.warning(f"系统主题检测失败: {e}")
        return 'light'  # 出错默认使用浅色


# ====================== 密钥检测 ======================
def ensure_api_key() -> tuple[bool, bool]:
    """确保API密钥已配置
    
    Returns:
        元组(has_std, has_acc)，分别表示是否有标准版和高精度版密钥
    """
    from core.settings import decrypt_api_data, hash_sensitive_data

    has_std = False
    has_acc = False

    if os.path.exists("apikey.enc"):
        try:
            with open("apikey.enc", "rb") as f:
                content = decrypt_api_data(f.read())
            std = content.get("general", {})
            if std.get("API_KEY") and std.get("SECRET_KEY"):
                has_std = True
                desensitizer = get_log_desensitizer()
                safe_std_key = desensitizer.desensitize_text(std.get("API_KEY", ""))
                xuanwu_logger.info(f"🔑 标准版API密钥已配置: {safe_std_key}")
                logging.debug(f"标准版API密钥验证通过: {safe_std_key}")
            acc = content.get("accurate", {})
            if acc.get("API_KEY") and acc.get("SECRET_KEY"):
                has_acc = True
                desensitizer = get_log_desensitizer()
                safe_acc_key = desensitizer.desensitize_text(acc.get("API_KEY", ""))
                xuanwu_logger.info(f"🔑 高精度版API密钥已配置: {safe_acc_key}")
                logging.debug(f"高精度版API密钥验证通过: {safe_acc_key}")
            
            # 检查 accurate_enhanced 配置；若被显式禁用则跳过自动补充
            acc_enhanced = content.get("accurate_enhanced", {})
            if acc_enhanced.get("DISABLED", False):
                logging.debug("accurate_enhanced 已被用户禁用，跳过自动复制配置")
            elif not (acc_enhanced.get("API_KEY") and acc_enhanced.get("SECRET_KEY")):
                if has_acc:
                    # 如果有 accurate 配置但没有 accurate_enhanced，自动复制配置
                    content["accurate_enhanced"] = content["accurate"].copy()
                    try:
                        from core.settings import encrypt_api_data
                        with open("apikey.enc", "wb") as f:
                            f.write(encrypt_api_data(content))
                        xuanwu_logger.info("🔄 已自动为 accurate_enhanced 配置密钥")
                        logging.debug("accurate_enhanced 配置已从 accurate 复制")
                    except Exception as e:
                        logging.error(f"保存 accurate_enhanced 配置失败: {e}")
            else:
                desensitizer = get_log_desensitizer()
                safe_acc_enhanced_key = desensitizer.desensitize_text(acc_enhanced.get("API_KEY", ""))
                xuanwu_logger.info(f"🔑 高精度增强版API密钥已配置: {safe_acc_enhanced_key}")
                logging.debug(f"高精度增强版API密钥验证通过: {safe_acc_enhanced_key}")
        except Exception as e:
            logging.error(f"apikey.enc读取失败: {e}")

    if not has_std:
        app = QApplication(sys.argv)
        while True:
            dlg = ApiKeyDialog(load_keys=False)
            res = dlg.exec()
            if res != QDialog.DialogCode.Accepted:
                QMessageBox.critical(None, "系统错误提示", "必须输入标准版密钥，程序即将退出")
                sys.exit(0)
            try:
                with open("apikey.enc", "rb") as f:
                    content = decrypt_api_data(f.read())
                std = content.get("general", {})
                if std.get("API_KEY") and std.get("SECRET_KEY"):
                    has_std = True
                    desensitizer = get_log_desensitizer()
                    safe_std_key = desensitizer.desensitize_text(std.get("API_KEY", ""))
                    xuanwu_logger.info(f"✅ 标准版API密钥验证成功: {safe_std_key}")
                    logging.debug(f"标准版API密钥重新验证通过: {safe_std_key}")
                    acc = content.get("accurate", {})
                    if acc.get("API_KEY") and acc.get("SECRET_KEY"):
                        has_acc = True
                        desensitizer = get_log_desensitizer()
                        safe_acc_key = desensitizer.desensitize_text(acc.get("API_KEY", ""))
                        xuanwu_logger.info(f"✅ 高精度版API密钥验证成功: {safe_acc_key}")
                        logging.debug(f"高精度版API密钥重新验证通过: {safe_acc_key}")
                    break
                else:
                    QMessageBox.warning(None, "输入提示", "必须至少输入标准版密钥才能继续")
            except Exception:
                QMessageBox.warning(None, "输入提示", "读取密钥失败，请重新输入")
        os.execl(sys.executable, sys.executable, *sys.argv)
    return has_std, has_acc

def log_startup_info() -> None:
    """记录启动信息到日志"""
    import platform
    logging.info(f"启动:{startup}")
    logging.info(f"系统:{platform.system()} {platform.release()} Python:{platform.python_version()} 目录:{os.getcwd()}")

# ======================= 主窗口 ========================

class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self, has_accurate_key: bool) -> None:
        """初始化主窗口
        
        Args:
            has_accurate_key: 是否有高精度版API密钥
        """
        super().__init__()
        
        # 初始化logger属性
        from core.enhanced_logger import get_enhanced_logger
        self.logger = get_enhanced_logger()
        
        # 记录主窗口初始化开始
        init_start_time = time.time()
        enhanced_logger.debug_function_call("__init__", "MainWindow", (has_accurate_key,), context="主窗口初始化开始")
        enhanced_logger.debug_memory_snapshot("MainWindow初始化前")
        
        self.error_popup_active: bool = False
        try:
            enhanced_logger.debug_function_call("DevToolsPanel", "widgets.dev_tools_panel", context="开发工具面板初始化")
            self.dev_tools_panel = DevToolsPanel(self)

            # 加载设置配置
            enhanced_logger.debug_function_call("load_settings", "core.settings", context="加载应用设置")
            self.settings = load_settings()
            if "ocr_version" not in self.settings:
                self.settings["ocr_version"] = "general"
                enhanced_logger.debug_function_call("save_settings", "core.settings", context="保存默认OCR版本设置")
                save_settings(self.settings)
            enhanced_logger.log("DEBUG", f"🔧 设置加载完成: 主题={self.settings.get('theme', '未知')}, 语言={self.settings.get('language', '未知')}, OCR版本={self.settings.get('ocr_version', 'general')}")

            # 初始化核心属性
            self.region = None
            self.ocr_worker = None
            self.ocr_thread = None
            
            # 初始化UI面板组件
            enhanced_logger.debug_function_call("KeywordPanel", "widgets.keyword_panel", context="关键词面板初始化")
            self.keyword_panel = KeywordPanel()
            enhanced_logger.debug_function_call("ControlPanel", "widgets.control_panel", context="控制面板初始化")
            self.control_panel = ControlPanel()
            enhanced_logger.debug_function_call("LogPanel", "widgets.log_panel", context="日志面板初始化")
            self.log_panel = LogPanel()
            enhanced_logger.debug_function_call("StatusPanel", "widgets.status_panel", context="状态面板初始化")
            self.status_panel = StatusPanel()
            enhanced_logger.debug_function_call("HistoryPanel", "widgets.history_panel", context="历史面板初始化")
            self.history_panel = HistoryPanel()
            # 历史记录独立弹窗（按需创建）
            self.history_dialog = None
            enhanced_logger.debug_function_call("AnalyticsPanel", "widgets.analytics_panel", context="分析面板初始化")
            self.analytics_panel = AnalyticsPanel()
            
            # 初始化灵动岛组件 - 现在作为独立的顶层窗口
            enhanced_logger.debug_function_call("DynamicIsland", "widgets.dynamic_island", context="灵动岛组件初始化")
            self.dynamic_island = DynamicIsland(self)  # 传递主窗口引用
            dynamic_island_manager.set_current_island(self.dynamic_island)
            
            # 同步当前主题设置到灵动岛
            current_theme = self.settings.get("theme", "auto")
            self.dynamic_island.current_theme = current_theme
            if current_theme == "auto":
                self.dynamic_island.is_dark_theme = self.dynamic_island.detect_system_theme()
            else:
                self.dynamic_island.is_dark_theme = current_theme == "dark"
            self.dynamic_island.update_theme_colors()
            logging.info(f"[INIT] 灵动岛主题已同步: {current_theme}, 暗色模式: {self.dynamic_island.is_dark_theme}")
            
            # 初始化灵动岛状态，避免显示"检测中"
            dynamic_island_manager.update_monitoring_data(
                api_status="待检测",
                network_status="待检测",
                total_hits=0,
                hits_per_keyword={}
            )
            # 不再需要设置固定高度，因为现在是独立窗口
            
            enhanced_logger.log("DEBUG", "🎨 所有UI面板组件初始化完成")
            
            # 初始化备份管理器
            enhanced_logger.debug_function_call("BackupManager", "core.backup_manager", context="备份管理器初始化")
            self.backup_manager = BackupManager()
            enhanced_logger.debug_function_call("start_auto_backup", "BackupManager", context="启动自动备份")
            self.backup_manager.start_auto_backup()
            # 设置变更时重启自动备份，确保新配置即时生效
            try:
                register_settings_callback(lambda s: self.backup_manager.start_auto_backup())
            except Exception as e:
                logging.debug(f"注册自动备份设置回调失败: {e}")
            enhanced_logger.log("DEBUG", "💾 备份管理器初始化并启动自动备份完成")
            
            # 初始化性能管理器
            try:
                enhanced_logger.debug_function_call("PerformanceManager", "core.performance_manager", context="性能管理器初始化")
                from core.performance_manager import PerformanceManager
                self.performance_manager = PerformanceManager()
                enhanced_logger.log("DEBUG", "📈 性能管理器初始化完成")
            except Exception as e:
                enhanced_logger.debug_error(e, "性能管理器初始化")
                logging.error(f"性能管理器初始化失败: {e}")
                self.performance_manager = None
            
            # 初始化云同步管理器
            try:
                enhanced_logger.debug_function_call("CloudSyncManager", "core.cloud_sync", context="云同步管理器初始化")
                from core.cloud_sync import CloudSyncManager
                self.cloud_sync_manager = CloudSyncManager()
                enhanced_logger.debug_function_call("start_auto_sync", "CloudSyncManager", context="启动自动同步")
                self.cloud_sync_manager.start_auto_sync()
                xuanwu_logger.info("☁️ 云同步管理器初始化成功")
                enhanced_logger.log("DEBUG", "☁️ 云同步管理器组件加载完成")
            except Exception as e:
                enhanced_logger.debug_error(e, "云同步管理器初始化")
                logging.error(f"云同步管理器初始化失败: {e}")
            
            # 初始化系统主题监听器
            enhanced_logger.debug_function_call("QTimer", "PyQt6.QtCore", context="系统主题监听器初始化")
            self.current_system_theme = None
            self.theme_timer = QTimer(self)
            self.theme_timer.timeout.connect(self.check_system_theme_change)
            enhanced_logger.log("DEBUG", "🎨 系统主题监听器初始化完成")
            
            # 初始化快捷键管理器
            try:
                enhanced_logger.debug_function_call("get_hotkey_manager", "core.hotkey_manager", context="快捷键管理器初始化")
                from core.hotkey_manager import get_hotkey_manager
                self.hotkey_manager = get_hotkey_manager()
                self.hotkey_manager.hotkey_triggered.connect(self.on_hotkey_triggered)
                enhanced_logger.debug_function_call("setup_global_hotkeys", "MainWindow", context="批量设置全局快捷键")
                self.setup_global_hotkeys()
                xuanwu_logger.info("⌨️ 快捷键管理器初始化成功")
                enhanced_logger.log("DEBUG", "⌨️ 快捷键管理器组件加载完成")
            except Exception as e:
                enhanced_logger.debug_error(e, "快捷键管理器初始化")
                logging.error(f"快捷键管理器初始化失败: {e}")
            enhanced_logger.debug_function_call("start", "QTimer", (2000,), context="启动主题监听器定时器")
            self.theme_timer.start(2000)  # 每2秒检查一次系统主题变化

            self.control_panel.set_interval(self.settings.get("interval", 0.6))
            self.control_panel.select_region.connect(self.open_region_selector)
            self.control_panel.start_capture.connect(self.start_capture)
            self.control_panel.stop_capture.connect(self.stop_capture)
            self.control_panel.refresh_index.connect(lambda: (build_log_index(), self.history_panel.refresh()))
            
            # 连接灵动岛的信号
            self.dynamic_island.action_triggered.connect(self.handle_dynamic_island_action)
            self.dynamic_island.clicked.connect(self.handle_dynamic_island_clicked)

            if not has_accurate_key:
                self.control_panel.disable_accurate_option(True)
                self.control_panel.set_status("当前仅检测到标准版密钥，高精度版功能不可用", "orange")

            layout_left = QVBoxLayout()
            layout_left.setSpacing(3)  # 减小组件间距
            layout_left.setContentsMargins(3, 3, 3, 3)  # 减小边距
            layout_left.addWidget(self.keyword_panel)
            layout_left.addWidget(self.control_panel)
            layout_left.addWidget(self.status_panel)

            layout_right = QVBoxLayout()
            layout_right.setSpacing(3)  # 减小组件间距
            layout_right.setContentsMargins(3, 3, 3, 3)  # 减小边距
            
            layout_right.addWidget(self.log_panel)
            layout_right.addWidget(self.history_panel)
            # 移除分析面板，保持界面简洁
            # layout_right.addWidget(self.analytics_panel)

            left = QWidget()
            left.setLayout(layout_left)
            
            # 创建右侧面板（灵动岛现在作为独立窗口显示）
            right_container = QWidget()
            right_container.setLayout(layout_right)

            # 使用分割器替代简单布局，允许用户调整面板大小
            enhanced_logger.debug_function_call("MainWindow.__init__", "创建UI布局和分割器")
            from PyQt6.QtWidgets import QSplitter
            
            center = QWidget()
            main_layout = QVBoxLayout(center)  # 改为垂直布局
            main_layout.setContentsMargins(3, 3, 3, 3)  # 进一步减小边距
            main_layout.setSpacing(2)  # 减小间距
            

            
            # 创建分割器
            splitter = QSplitter(Qt.Orientation.Horizontal)
            splitter.addWidget(left)
            splitter.addWidget(right_container)
            splitter.setStretchFactor(0, 3)  # 左侧面板适当增加比重
            splitter.setStretchFactor(1, 5)  # 右侧面板保持较大比重
            splitter.setHandleWidth(1)  # 设置更细的分隔条宽度
            
            main_layout.addWidget(splitter)
            logging.debug("UI布局和分割器创建完成")

            enhanced_logger.debug_function_call("MainWindow.__init__", "设置主窗口属性")
            self.setCentralWidget(center)
            self.setWindowTitle(t("炫舞OCR - 文字识别工具"))
            self.resize(900, 650)  # 调整窗口宽度为900，保持高度650
            
            # 窗口居中显示
            screen = QApplication.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()
                window_geometry = self.frameGeometry()
                center_point = screen_geometry.center()
                window_geometry.moveCenter(center_point)
                self.move(window_geometry.topLeft())
                logging.debug("主窗口已居中显示")
            
            # 添加状态栏
            self.statusBar().showMessage("就绪")
            logging.debug("主窗口属性设置完成 - 标题、大小、状态栏、居中")
            
            # 设置窗口图标
            enhanced_logger.debug_function_call("MainWindow.__init__", "设置窗口图标")
            if os.path.exists("285.ico"):
                from PyQt6.QtGui import QIcon
                self.setWindowIcon(QIcon("285.ico"))
                logging.debug("窗口图标设置成功")
            else:
                logging.debug("窗口图标文件不存在，跳过设置")

            enhanced_logger.debug_function_call("MainWindow.__init__", "加载区域设置")
            region = self.settings.get("region")
            if region and len(region) == 4:
                self.region = tuple(region)
                self.control_panel.set_status(f"已加载区域:{self.region}", "green")
                self.status_panel.update_status(region=self.region)
                logging.debug(f"区域设置加载成功: {self.region}")
            else:
                logging.debug("未找到有效的区域设置")

            enhanced_logger.debug_function_call("MainWindow.__init__", "构建日志索引")
            build_log_index()
            logging.debug("日志索引构建完成")
            
            enhanced_logger.debug_function_call("MainWindow.__init__", "刷新历史面板")
            self.history_panel.refresh()
            logging.debug("历史面板刷新完成")

            # Initialize the menu UI
            enhanced_logger.debug_function_call("MainWindow.__init__", "初始化菜单UI")
            self.init_ui()
            logging.debug("菜单UI初始化完成")
            
            # Apply current language settings to UI
            enhanced_logger.debug_function_call("MainWindow.__init__", "应用语言设置")
            self.refresh_all_ui_text()
            logging.debug("语言设置应用完成")
            
            # 记录初始化完成时间和性能
            init_end_time = time.time()
            init_duration = init_end_time - init_start_time
            enhanced_logger.debug_performance("MainWindow.__init__", init_start_time, context=f"duration_ms: {init_duration * 1000:.2f}")
            enhanced_logger.debug_memory_snapshot("MainWindow初始化完成")
            logging.debug(f"MainWindow初始化完成，耗时: {init_duration:.3f}秒")

        except Exception as e:
            enhanced_logger.debug_error("MainWindow.__init__", e, {"error_type": type(e).__name__})
            logging.exception("MainWindow初始化错误")
            QMessageBox.critical(None, "系统错误提示", f"主界面加载失败:{e}")

    # 添加 update_settings 方法
    def update_settings(self, new_settings):
        self.settings.update(new_settings)
        save_settings(self.settings)
        logging.info(f"设置已更新: {new_settings}")
    
    def check_system_theme_change(self):
        """检查系统主题变化并自动切换程序主题"""
        try:
            # 只有在启用自动主题切换时才检查
            if not self.settings.get("auto_theme", False):
                return
            
            # 检测当前系统主题
            current_theme = detect_system_theme()
            
            # 如果是第一次检查，记录当前主题
            if self.current_system_theme is None:
                self.current_system_theme = current_theme
                return
            
            # 如果系统主题发生变化
            if current_theme != self.current_system_theme:
                self.current_system_theme = current_theme
                
                # 转换主题格式（从 'light'/'dark' 到 '浅色'/'深色'）
                theme_map = {'light': '浅色', 'dark': '深色'}
                new_theme = theme_map.get(current_theme, '浅色')
                
                # 更新设置并应用主题
                self.settings["theme"] = new_theme
                save_settings(self.settings)
                apply_theme(QApplication.instance(), new_theme)
                
                # 同步更新灵动岛主题
                if hasattr(self, 'dynamic_island') and self.dynamic_island:
                    self.dynamic_island.current_theme = new_theme
                    # 根据主题设置暗色模式
                    self.dynamic_island.is_dark_theme = new_theme == "深色"
                    self.dynamic_island.update_theme_colors()
                    logging.debug(f"[AUTO_THEME] 灵动岛主题已自动同步更新为: {new_theme}, 暗色模式: {self.dynamic_island.is_dark_theme}")
                
                logging.info(f"系统主题已变化，自动切换到: {new_theme}")
                self.statusBar().showMessage(f"已自动切换到{new_theme}主题", 3000)
                
        except Exception as e:
            logging.warning(f"检查系统主题变化失败: {e}")

    def open_setting_dialog(self, setting_type):
        """打开设置对话框"""
        try:
            dialog = create_setting_dialog(setting_type, self)
            if dialog:
                # 连接设置变更信号
                dialog.settings_changed.connect(self.on_settings_changed)
                dialog.exec()
        except Exception as e:
            logging.exception(f"打开设置对话框失败: {e}")
            QMessageBox.critical(self, "错误", f"打开设置对话框失败: {e}")
    
    def on_settings_changed(self, new_settings):
        """处理设置变更"""
        start_time = time.time()
        logging.info(f"[SETTINGS_CHANGE] 开始处理设置变更，变更项数量: {len(new_settings)}")
        logging.debug(f"[SETTINGS_CHANGE] 变更内容: {list(new_settings.keys())}")
        
        try:
            # 更新本地设置
            update_start = time.time()
            self.settings.update(new_settings)
            update_time = (time.time() - update_start) * 1000
            logging.debug(f"[SETTINGS_CHANGE] 本地设置更新耗时: {update_time:.2f}ms")
            
            # 如果字体大小发生变化，立即应用
            if "font_size" in new_settings:
                font_start = time.time()
                font_size = new_settings["font_size"]
                from PyQt6.QtGui import QFont
                font = QFont()
                font.setPointSize(font_size)
                QApplication.instance().setFont(font)
                font_time = (time.time() - font_start) * 1000
                logging.info(f"[SETTINGS_CHANGE] 字体大小已更新为: {font_size}px，耗时: {font_time:.2f}ms")
            
            # 如果主题发生变化，立即应用
            if "theme" in new_settings:
                theme_start = time.time()
                try:
                    apply_theme(QApplication.instance(), new_settings["theme"])
                    
                    # 通知灵动岛更新主题
                    if hasattr(self, 'dynamic_island') and self.dynamic_island:
                        self.dynamic_island.current_theme = new_settings["theme"]
                        # 根据用户选择的主题设置暗色模式，而不是检测系统主题
                        self.dynamic_island.is_dark_theme = new_settings["theme"] == "dark"
                        self.dynamic_island.update_theme_colors()
                        logging.debug(f"[SETTINGS_CHANGE] 灵动岛主题已同步更新为: {new_settings['theme']}, 暗色模式: {self.dynamic_island.is_dark_theme}")
                    
                    theme_time = (time.time() - theme_start) * 1000
                    logging.info(f"[SETTINGS_CHANGE] 主题已更新为: {new_settings['theme']}，耗时: {theme_time:.2f}ms")
                except Exception as theme_error:
                    logging.error(f"[SETTINGS_CHANGE] 主题应用失败: {theme_error}")
            
            # 如果快捷键发生变化，重新批量设置全局快捷键
            if "shortcut_key" in new_settings:
                hotkey_start = time.time()
                try:
                    self.setup_global_hotkeys()
                    hotkey_time = (time.time() - hotkey_start) * 1000
                    logging.info(f"[SETTINGS_CHANGE] 快捷键已更新为: {new_settings.get('shortcut_key', '无')}，耗时: {hotkey_time:.2f}ms")
                except Exception as hotkey_error:
                    logging.error(f"[SETTINGS_CHANGE] 快捷键设置失败: {hotkey_error}")
            
            # 如果语言发生变化，立即应用并刷新UI
            if "language" in new_settings:
                lang_start = time.time()
                old_language = self.settings.get('language', '未知')
                new_language = new_settings["language"]
                
                logging.info(f"[LANGUAGE_SWITCH] 开始语言切换: {old_language} -> {new_language}")
                
                try:
                    # 设置语言
                    i18n_start = time.time()
                    from core.i18n import set_language
                    set_language(new_language)
                    i18n_time = (time.time() - i18n_start) * 1000
                    logging.debug(f"[LANGUAGE_SWITCH] i18n语言设置耗时: {i18n_time:.2f}ms")
                    
                    # 刷新UI
                    ui_start = time.time()
                    self.refresh_all_ui_text()
                    ui_time = (time.time() - ui_start) * 1000
                    logging.debug(f"[LANGUAGE_SWITCH] UI刷新耗时: {ui_time:.2f}ms")
                    
                    lang_time = (time.time() - lang_start) * 1000
                    logging.info(f"[LANGUAGE_SWITCH] 语言切换完成: {new_language}，总耗时: {lang_time:.2f}ms")
                    
                except Exception as lang_error:
                    logging.error(f"[LANGUAGE_SWITCH] 语言切换失败: {lang_error}")
                    # 尝试回滚到原语言
                    try:
                        from core.i18n import set_language
                        set_language(old_language)
                        logging.warning(f"[LANGUAGE_SWITCH] 已回滚到原语言: {old_language}")
                    except Exception as rollback_error:
                        logging.error(f"[LANGUAGE_SWITCH] 语言回滚失败: {rollback_error}")
            
            total_time = (time.time() - start_time) * 1000
            logging.info(f"[SETTINGS_CHANGE] 设置变更处理完成，总耗时: {total_time:.2f}ms")
                
        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            logging.exception(f"[SETTINGS_CHANGE] 应用设置变更失败，耗时: {total_time:.2f}ms，错误: {e}")

    def refresh_all_ui_text(self):
        """刷新所有UI文本元素"""
        start_time = time.time()
        
        try:
            from core.i18n import t, get_current_language
            
            current_lang = get_current_language()
            logging.info(f"[UI_REFRESH] 开始刷新UI文本，当前语言: {current_lang}")
            
            # 刷新主窗口标题
            title_start = time.time()
            title = t("炫舞OCR - 文字识别工具", "炫舞OCR - 文字识别工具")
            self.setWindowTitle(title)
            title_time = (time.time() - title_start) * 1000
            logging.debug(f"[UI_REFRESH] 窗口标题刷新耗时: {title_time:.2f}ms，标题: {title}")
            
            # 刷新菜单栏文本
            menu_start = time.time()
            try:
                # 刷新设置菜单
                if hasattr(self, 'settings_menu'):
                    self.settings_menu.setTitle(t("menu_settings"))
                    
                    # 刷新设置菜单项
                    if hasattr(self, 'api_action'):
                        self.api_action.setText(t("menu_api_key_settings"))
                    if hasattr(self, 'email_action'):
                        self.email_action.setText(t("menu_email_settings"))
                    if hasattr(self, 'backup_action'):
                        self.backup_action.setText(t("menu_backup_management"))
                    if hasattr(self, 'keyword_action'):
                        self.keyword_action.setText(t("menu_keyword_import_export"))
                    if hasattr(self, 'cloud_sync_action'):
                        self.cloud_sync_action.setText(t("menu_cloud_sync_settings"))
                    if hasattr(self, 'desktop_notify_action'):
                        self.desktop_notify_action.setText(t("menu_desktop_notify"))
                    if hasattr(self, 'error_popup_action'):
                        self.error_popup_action.setText(t("menu_error_popup"))
                    if hasattr(self, 'theme_switch_action'):
                        self.theme_switch_action.setText(t("menu_theme_switch"))
                    if hasattr(self, 'font_size_action'):
                        self.font_size_action.setText(t("menu_font_size"))
                    if hasattr(self, 'language_switch_action'):
                        self.language_switch_action.setText(t("menu_language_switch"))
                    if hasattr(self, 'log_management_action'):
                        self.log_management_action.setText(t("menu_log_management"))
                    if hasattr(self, 'startup_password_action'):
                        self.startup_password_action.setText(t("menu_startup_password"))
                    if hasattr(self, 'proxy_action'):
                        self.proxy_action.setText(t("menu_proxy_settings"))
                    if hasattr(self, 'timeout_retry_action'):
                        self.timeout_retry_action.setText(t("menu_timeout_retry"))
                    if hasattr(self, 'cache_size_action'):
                        self.cache_size_action.setText(t("menu_cache_size"))
                    if hasattr(self, 'external_hook_action'):
                        self.external_hook_action.setText(t("menu_external_hook"))
                    if hasattr(self, 'shortcut_key_action'):
                        self.shortcut_key_action.setText(t("menu_shortcut_key"))
                
                # 刷新帮助菜单
                if hasattr(self, 'help_menu'):
                    self.help_menu.setTitle(t("menu_help"))
                    
                    # 刷新帮助菜单项
                    if hasattr(self, 'help_action'):
                        self.help_action.setText(t("menu_user_manual"))
                    if hasattr(self, 'shortcuts_action'):
                        self.shortcuts_action.setText(t("menu_shortcuts_help"))
                    if hasattr(self, 'troubleshooting_action'):
                        self.troubleshooting_action.setText(t("menu_troubleshooting"))
                    if hasattr(self, 'feature_tour_action'):
                        self.feature_tour_action.setText(t("menu_feature_tour"))
                    if hasattr(self, 'update_log_action'):
                        self.update_log_action.setText(t("menu_update_log"))
                    if hasattr(self, 'support_action'):
                        self.support_action.setText(t("menu_official_support"))
                    if hasattr(self, 'license_action'):
                        self.license_action.setText(t("menu_license"))
                    if hasattr(self, 'about_action'):
                        self.about_action.setText(t("menu_about"))
                
                # 刷新开发者工具菜单
                if hasattr(self, 'dev_tools_menu'):
                    self.dev_tools_menu.setTitle(t("menu_dev_tools"))
                
            except Exception as menu_error:
                logging.warning(f"[UI_REFRESH] 菜单栏刷新失败: {menu_error}")
            
            menu_time = (time.time() - menu_start) * 1000
            logging.debug(f"[UI_REFRESH] 菜单栏刷新完成，耗时: {menu_time:.2f}ms")
            
            # 刷新各个面板的UI文本
            panels_start = time.time()
            panel_results = []
            
            panels = [
                ('control_panel', '控制面板'),
                ('keyword_panel', '关键词面板'),
                ('log_panel', '日志面板'),
                ('status_panel', '状态面板'),
                ('history_panel', '历史面板'),
                ('analytics_panel', '分析面板'),
                ('dev_tools_panel', '开发工具面板'),
                ('settings_panel', '设置面板'),
                ('language_panel', '语言面板')
            ]
            
            for panel_attr, panel_name in panels:
                panel_start = time.time()
                try:
                    if hasattr(self, panel_attr):
                        panel = getattr(self, panel_attr)
                        if panel and hasattr(panel, 'refresh_ui_text'):
                            panel.refresh_ui_text()
                            panel_time = (time.time() - panel_start) * 1000
                            panel_results.append(f"{panel_name}: {panel_time:.2f}ms")
                            logging.debug(f"[UI_REFRESH] {panel_name}刷新耗时: {panel_time:.2f}ms")
                        else:
                            panel_results.append(f"{panel_name}: 跳过(无刷新方法)")
                    else:
                        panel_results.append(f"{panel_name}: 跳过(不存在)")
                except Exception as panel_error:
                    panel_time = (time.time() - panel_start) * 1000
                    panel_results.append(f"{panel_name}: 失败({panel_time:.2f}ms)")
                    logging.warning(f"[UI_REFRESH] {panel_name}刷新失败: {panel_error}")
            
            panels_time = (time.time() - panels_start) * 1000
            total_time = (time.time() - start_time) * 1000
            
            logging.info(f"[UI_REFRESH] UI文本刷新完成，总耗时: {total_time:.2f}ms")
            logging.debug(f"[UI_REFRESH] 面板刷新详情 (总耗时: {panels_time:.2f}ms): {', '.join(panel_results)}")
            
        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            logging.exception(f"[UI_REFRESH] 刷新UI文本失败，耗时: {total_time:.2f}ms，错误: {e}")

    def mousePressEvent(self, event):
        """鼠标点击事件 - 点击时将窗口置顶"""
        try:
            self.raise_()
            self.activateWindow()
            super().mousePressEvent(event)
        except Exception as e:
            logging.exception(f"窗口置顶失败: {e}")
            super().mousePressEvent(event)

    def init_ui(self):
        menubar = self.menuBar()

        # 设置菜单（第一位）
        self.settings_menu = menubar.addMenu(t("menu_settings"))

        # 添加API密钥设置
        self.api_action = self.settings_menu.addAction(t("menu_api_key_settings"))
        self.api_action.triggered.connect(self.open_apikey_dialog)
        
        # 添加邮件通知设置
        self.email_action = self.settings_menu.addAction(t("menu_email_settings"))
        self.email_action.triggered.connect(self.open_email_settings_dialog)
        
        # 备份管理
        self.backup_action = self.settings_menu.addAction(t("menu_backup_management"))
        self.backup_action.triggered.connect(self.open_backup_dialog)
        
        # 关键词导入导出
        self.keyword_action = self.settings_menu.addAction(t("menu_keyword_import_export"))
        self.keyword_action.triggered.connect(self.open_keyword_import_export_dialog)
        
        # 云同步设置
        self.cloud_sync_action = self.settings_menu.addAction(t("menu_cloud_sync_settings"))
        self.cloud_sync_action.triggered.connect(self.open_cloud_sync_dialog)
        
        self.settings_menu.addSeparator()
        
        # 通知设置
        self.desktop_notify_action = self.settings_menu.addAction(t("menu_desktop_notify"))
        self.desktop_notify_action.triggered.connect(lambda: self.open_setting_dialog("desktop_notify"))
        self.error_popup_action = self.settings_menu.addAction(t("menu_error_popup"))
        self.error_popup_action.triggered.connect(lambda: self.open_setting_dialog("error_popup"))

        
        self.settings_menu.addSeparator()
        
        # 外观设置
        self.theme_switch_action = self.settings_menu.addAction(t("menu_theme_switch"))
        self.theme_switch_action.triggered.connect(lambda: self.open_setting_dialog("theme_switch"))
        self.font_size_action = self.settings_menu.addAction(t("menu_font_size"))
        self.font_size_action.triggered.connect(lambda: self.open_setting_dialog("font_size"))
        self.language_switch_action = self.settings_menu.addAction(t("menu_language_switch"))
        self.language_switch_action.triggered.connect(lambda: self.open_setting_dialog("language_switch"))
        
        self.settings_menu.addSeparator()
        
        # 系统设置
        # 自动上传日志到服务器和历史数据导出功能已整合到备份管理对话框中
        self.log_management_action = self.settings_menu.addAction(t("menu_log_management"))
        self.log_management_action.triggered.connect(self.open_log_management_dialog)
        self.startup_password_action = self.settings_menu.addAction(t("menu_startup_password"))
        self.startup_password_action.triggered.connect(lambda: self.open_setting_dialog("startup_password"))
        
        self.settings_menu.addSeparator()
        
        # 网络设置
        self.proxy_action = self.settings_menu.addAction(t("menu_proxy_settings"))
        self.proxy_action.triggered.connect(lambda: self.open_setting_dialog("proxy"))
        self.timeout_retry_action = self.settings_menu.addAction(t("menu_timeout_retry"))
        self.timeout_retry_action.triggered.connect(lambda: self.open_setting_dialog("timeout_retry"))
        
        self.settings_menu.addSeparator()
        
        # 高级设置
        self.cache_size_action = self.settings_menu.addAction(t("menu_cache_size"))
        self.cache_size_action.triggered.connect(lambda: self.open_setting_dialog("cache_size"))
        self.external_hook_action = self.settings_menu.addAction(t("menu_external_hook"))
        self.external_hook_action.triggered.connect(lambda: self.open_setting_dialog("external_hook"))
        self.shortcut_key_action = self.settings_menu.addAction(t("menu_shortcut_key"))
        self.shortcut_key_action.triggered.connect(lambda: self.open_setting_dialog("shortcut_key"))

        # 帮助菜单（第二位）
        self.help_menu = menubar.addMenu(t("menu_help"))
        self.help_action = QAction(t("menu_user_manual"), self)
        self.help_action.triggered.connect(self.show_help_window)
        self.help_menu.addAction(self.help_action)

# 快捷键帮助
        self.shortcuts_action = QAction(t("menu_shortcuts_help"), self)
        self.shortcuts_action.triggered.connect(self.show_shortcuts_window)
        self.help_menu.addAction(self.shortcuts_action)
        
        # 故障排除
        self.troubleshooting_action = QAction(t("menu_troubleshooting"), self)
        self.troubleshooting_action.triggered.connect(self.show_troubleshooting_wizard)
        self.help_menu.addAction(self.troubleshooting_action)
        
        # 功能导览
        self.feature_tour_action = QAction(t("menu_feature_tour"), self)
        self.feature_tour_action.triggered.connect(self.show_feature_tour)
        self.help_menu.addAction(self.feature_tour_action)

        self.update_log_action = QAction(t("menu_update_log"), self)
        self.update_log_action.triggered.connect(self.show_update_log_window)
        self.help_menu.addAction(self.update_log_action)

        self.support_action = QAction(t("menu_official_support"), self)
        self.support_action.triggered.connect(self.show_support_info)
        self.help_menu.addAction(self.support_action)

        self.license_action = QAction(t("menu_license"), self)
        self.license_action.triggered.connect(self.show_license_info)
        self.help_menu.addAction(self.license_action)

        self.about_action = QAction(t("menu_about"), self)
        self.about_action.triggered.connect(self.show_about_info)
        self.help_menu.addAction(self.about_action)

        # 开发者工具菜单（最后）
        self.dev_tools_menu = menubar.addMenu(t("menu_dev_tools"))

        # 添加优化状态监控
        self.optimization_status_action = QAction("优化状态监控", self)
        self.optimization_status_action.triggered.connect(self.show_optimization_status)
        self.dev_tools_menu.addAction(self.optimization_status_action)
        
        self.dev_tools_menu.addSeparator()

        # 将 DevToolsPanel 的菜单项添加到开发者工具菜单
        self.dev_tools_menu.addActions(self.dev_tools_panel.dev_tools_menu.actions())

    def open_apikey_dialog(self):
        """打开API密钥设置对话框"""
        from widgets.settings_panel import ApiKeySettingsDialog
        dialog = ApiKeySettingsDialog(self)
        dialog.exec()
        
    def open_email_settings_dialog(self):
        """打开邮件通知设置对话框"""
        dialog = EmailSettingsDialog(self)
        dialog.exec()
        
    def open_backup_dialog(self):
        """打开备份管理对话框"""
        try:
            from widgets.backup_dialog import BackupDialog
            dialog = BackupDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开备份管理对话框: {e}")
            
    def open_keyword_import_export_dialog(self):
        """打开关键词导入导出对话框"""
        try:
            from widgets.keyword_import_export_dialog import KeywordImportExportDialog
            dialog = KeywordImportExportDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开关键词导入导出对话框: {e}")
            
    def open_cloud_sync_dialog(self):
        """打开云同步设置对话框"""
        try:
            from widgets.cloud_sync_dialog import CloudSyncDialog
            dialog = CloudSyncDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开云同步设置对话框失败: {e}")
            
    def open_log_management_dialog(self):
        """打开日志管理对话框"""
        try:
            from widgets.log_management_dialog import LogManagementDialog
            # 保存对话框引用，防止被垃圾回收
            if not hasattr(self, 'log_dialog') or self.log_dialog is None or not self.log_dialog.isVisible():
                self.log_dialog = LogManagementDialog(self)  # 设置父窗口确保正确的生命周期管理
            
            # 确保窗口不是模态的
            self.log_dialog.setWindowModality(Qt.WindowModality.NonModal)
            # 设置窗口属性，确保窗口保持显示
            self.log_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
            self.log_dialog.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowMinMaxButtonsHint)
            
            # 居中显示
            self.log_dialog.move(self.geometry().center() - self.log_dialog.rect().center())
            
            # 显示并激活窗口
            self.log_dialog.show()
            self.log_dialog.raise_()
            self.log_dialog.activateWindow()
            
            # 确保窗口获得焦点
            self.log_dialog.setFocus()
            
        except Exception as e:
            logging.exception("打开日志管理对话框异常")
            QMessageBox.critical(self, "错误", f"打开日志管理失败: {e}")

    def show_unimplemented(self, feature_name):
        QMessageBox.information(self, "未实现", f"{feature_name} 功能尚未实现。")

    def show_help_window(self):
        help_window = HelpWindow()
        help_window.move(self.geometry().center() - help_window.rect().center())
        help_window.exec()

    def show_help_topic(self, item_name: str):
        """打开帮助窗口并直接显示指定主题内容"""
        try:
            help_window = HelpWindow()
            help_window.move(self.geometry().center() - help_window.rect().center())
            try:
                help_window.show_content(item_name)
            except Exception:
                # 如果指定内容未找到，则显示默认页面
                pass
            help_window.exec()
        except Exception as e:
            logging.error(f"打开指定帮助主题失败: {e}")

    def show_shortcuts_window(self):
        from widgets.shortcuts_window import ShortcutsWindow
        shortcuts_window = ShortcutsWindow()
        shortcuts_window.move(self.geometry().center() - shortcuts_window.rect().center())
        shortcuts_window.exec()

    def show_troubleshooting_wizard(self):
        """显示故障排除向导"""
        from widgets.troubleshooting_wizard import TroubleshootingWizard
        wizard = TroubleshootingWizard(self)
        wizard.move(self.geometry().center() - wizard.rect().center())
        wizard.exec()
    
    def show_feature_tour(self):
        """显示功能导览"""
        from widgets.feature_tour import FeatureTour
        tour = FeatureTour(self)
        tour.move(self.geometry().center() - tour.rect().center())
        tour.exec()
    
    def show_optimization_status(self):
        """显示优化状态监控窗口"""
        try:
            from widgets.optimization_status_widget import OptimizationStatusWidget
            
            # 检查是否已经有窗口打开
            if hasattr(self, 'optimization_status_window') and self.optimization_status_window is not None:
                # 如果窗口已存在，将其激活并置于前台
                self.optimization_status_window.raise_()
                self.optimization_status_window.activateWindow()
                return
            
            # 创建并显示优化状态监控窗口
            self.optimization_status_window = OptimizationStatusWidget(self)
            
            # 居中显示窗口
            main_geometry = self.geometry()
            window_geometry = self.optimization_status_window.geometry()
            x = main_geometry.x() + (main_geometry.width() - window_geometry.width()) // 2
            y = main_geometry.y() + (main_geometry.height() - window_geometry.height()) // 2
            self.optimization_status_window.move(x, y)
            
            # 显示窗口
            self.optimization_status_window.show()
            self.optimization_status_window.raise_()
            self.optimization_status_window.activateWindow()
            
            # 连接窗口关闭信号，清理引用
            self.optimization_status_window.finished.connect(lambda: setattr(self, 'optimization_status_window', None))
            
        except Exception as e:
            self.logger.error(f"显示优化状态监控窗口失败: {e}")
            QMessageBox.warning(self, "错误", f"无法打开优化状态监控窗口: {str(e)}")

    def show_update_log_window(self):
        """显示更新日志窗口"""
        try:
            from widgets.update_log_window import UpdateLogWindow
            
            # 创建并显示更新日志窗口
            update_log_window = UpdateLogWindow(self)
            update_log_window.move(self.geometry().center() - update_log_window.rect().center())
            update_log_window.exec()
            
        except Exception as e:
            print(f"显示更新日志窗口失败: {e}")
            # 如果新窗口加载失败，使用简单的备用方案
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton
            import os
            
            # 查找更新日志文件
            html_log_path = os.path.join(os.getcwd(), "update_log.html")
            txt_log_path = os.path.join(os.getcwd(), "update_log.txt")
            
            log_path = None
            is_html = False
            
            if os.path.exists(html_log_path):
                log_path = html_log_path
                is_html = True
            elif os.path.exists(txt_log_path):
                log_path = txt_log_path
                is_html = False
            else:
                QMessageBox.information(self, "更新日志", "更新日志文件不存在。")
                return
            
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                QMessageBox.warning(self, "更新日志", f"读取失败：{e}")
                return
            
            # 创建简单的更新日志窗口
            dlg = QDialog(self)
            dlg.setWindowTitle("炫舞OCR - 更新日志")
            dlg.resize(800, 600)
            dlg.setModal(True)
            
            # 创建文本浏览器
            tb = QTextBrowser(dlg)
            if is_html:
                tb.setHtml(content)
            else:
                tb.setPlainText(content)
            
            # 创建关闭按钮
            btn_close = QPushButton("关闭")
            btn_close.clicked.connect(dlg.close)
            
            # 布局
            layout = QVBoxLayout()
            layout.addWidget(tb)
            layout.addWidget(btn_close)
            dlg.setLayout(layout)
            
            dlg.exec()

    def show_support_info(self):
        """显示官方支持信息"""
        from widgets.support_dialog import SupportDialog
        support_dialog = SupportDialog(self)
        support_dialog.exec()

    def show_license_info(self):
        QMessageBox.information(self, "软件许可证", "MIT许可证")

    def show_about_info(self):
        from widgets.about_dialog import AboutDialog
        about_dialog = AboutDialog(self)
        about_dialog.exec()

    def open_region_selector(self):
        try:
            self.selector = RegionSelector()
            self.selector.region_selected.connect(self.set_region)
            self.selector.selection_canceled.connect(lambda: self.control_panel.set_status("取消选择", "gray"))
            self.selector.show()
            self.selector.raise_()
            self.selector.activateWindow()
        except Exception as e:
            logging.exception("open_region_selector错误")
            QMessageBox.critical(None, "系统错误提示", f"选择区域失败:{e}")

    def set_region(self, region):
        try:
            self.region = region
            self.settings["region"] = list(region)
            save_settings(self.settings)
            self.control_panel.set_status(f"已选择区域:{region}", "green")
            self.status_panel.update_status(region=region, keywords_count=len(self.keyword_panel.get_keywords()))
        except Exception as e:
            logging.exception("set_region异常")
            QMessageBox.critical(None, "系统错误提示", f"区域保存失败:{e}")

    def start_capture(self):
        try:
            self.settings = load_settings()
            kws = self.keyword_panel.get_keywords()
            if not kws:
                QMessageBox.warning(self, "输入提示", "请添加关键词")
                return
            if not self.region:
                QMessageBox.warning(self, "输入提示", "请先选择区域")
                return

            if self.control_panel.is_accurate_option_disabled():
                version = "general"
            else:
                version = self.settings.get("ocr_version", "general")

            interval = self.control_panel.get_interval()
            mode = self.settings.get("match_mode", "exact")
            fthr = self.settings.get("fuzzy_threshold", 0.85)
            self.settings["interval"] = interval
            save_settings(self.settings)

            logging.info(f"启动OCR(version={version}, mode={mode}, thr={fthr})")

            self.ocr_worker = OCRWorker(kws, self.region, interval, match_mode=mode,
                                        fuzzy_threshold=fthr, ocr_version=version)
            self.ocr_thread = OCRThread(self.ocr_worker)

            # 信号链接
            self.ocr_worker.log_signal.connect(self.log_panel.append_log)
            self.ocr_worker.stat_signal.connect(self.log_panel.update_statistics)
            self.ocr_worker.status_signal.connect(self.status_panel.update_worker_status)
            self.ocr_worker.status_signal.connect(self.on_ocr_status_update)
            self.ocr_worker.save_signal.connect(lambda *_: (build_log_index(), self.history_panel.refresh(), self.analytics_panel.refresh_data()))
            self.ocr_worker.save_signal.connect(self.on_ocr_match_found)
            self.ocr_worker.error_popup_signal.connect(self.show_error_popup)
            self.ocr_worker.finished_signal.connect(self.stop_capture)

            self.ocr_thread.start()
            self.control_panel.set_status("捕获中...", "green")
            self.control_panel.enable_buttons(False, True)
            self.status_panel.update_status(running=True, keywords_count=len(kws), interval=interval, region=self.region)
            

        except Exception as e:
            logging.exception("start_capture异常")
            QMessageBox.critical(None, "系统错误提示", f"OCR启动失败:{e}")

    def stop_capture(self):
        try:
            # 在停止OCR前保存统计数据
            if self.ocr_worker:
                # 保存OCR工作器的统计数据
                self.last_ocr_stats = {
                    'total_hits': getattr(self.ocr_worker, 'total_hits', 0),
                    'avg_response_time': getattr(self.ocr_worker, 'avg_response_time', 0),
                    'last_time': getattr(self.ocr_worker, 'last_time', None),
                    'stats': getattr(self.ocr_worker, 'stats', {}),
                    'cache_hits': getattr(self.ocr_worker, 'cache_hits', 0),
                    'cache_misses': getattr(self.ocr_worker, 'cache_misses', 0)
                }
                logging.debug(f"保存OCR统计数据: 识别次数={self.last_ocr_stats['total_hits']}, 响应时间={self.last_ocr_stats['avg_response_time']}ms")
                self.ocr_worker.stop()
            if self.ocr_thread:
                self.ocr_thread.quit()
                self.ocr_thread.wait()
            self.ocr_worker = None
            self.ocr_thread = None
            self.control_panel.set_status("已停止", "gray")
            try:
                dynamic_island_manager.show_status("已停止", QColor("gray"))
            except Exception as _e:
                logging.debug(f"动态岛状态通知失败: {_e}")
            self.control_panel.enable_buttons(True, False)
            self.status_panel.update_status(running=False)
            

        except Exception as e:
            logging.exception("stop_capture异常")
            QMessageBox.critical(None, "系统错误提示", f"OCR停止失败:{e}")
    
    def setup_global_hotkey(self):
        """设置全局快捷键"""
        try:
            if not hasattr(self, 'hotkey_manager'):
                return
                
            # 取消之前的快捷键注册
            self.hotkey_manager.unregister_current_hotkey()
            
            # 获取当前设置的快捷键
            hotkey_str = self.settings.get("shortcut_key", "").strip()
            
            if hotkey_str and self.hotkey_manager.is_available():
                # 注册新的快捷键
                success, error_msg = self.hotkey_manager.register_hotkey(hotkey_str, self.trigger_ocr_capture)
                if success:
                    logging.info(f"全局快捷键已注册: {hotkey_str}")
                else:
                    logging.warning(f"全局快捷键注册失败: {hotkey_str} - {error_msg}")
            elif hotkey_str:
                logging.warning("快捷键功能不可用，请安装 pynput 库")
                
        except Exception as e:
            logging.error(f"设置全局快捷键失败: {e}")

    def setup_global_hotkeys(self):
        """批量设置全局快捷键"""
        try:
            if not hasattr(self, 'hotkey_manager'):
                return

            # 取消之前的快捷键注册（单/多均使用同一入口）
            self.hotkey_manager.unregister_current_hotkey()

            settings = getattr(self, 'settings', {}) or {}

            # 全局开关
            if not settings.get("global_hotkeys_enabled", True):
                logging.info("全局快捷键已禁用，跳过注册")
                return

            # 主快捷键（来自设置）
            main_hotkey = settings.get("shortcut_key", "").strip()

            hotkey_map = {}
            if main_hotkey:
                hotkey_map[main_hotkey] = lambda: None

            # 默认自定义映射
            default_custom = {
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
                "close_tab": "Ctrl+W",
            }

            enabled_hotkeys = settings.get("enabled_hotkeys", {})
            custom_hotkeys = settings.get("custom_hotkeys", {})

            # 是否提示常见冲突（仅日志提示）
            conflict_hint = settings.get("hotkey_conflict_detection", True)

            def iter_combos(val):
                if isinstance(val, list):
                    return [s.strip() for s in val if isinstance(s, str) and s.strip()]
                elif isinstance(val, str):
                    s = val.strip()
                    return [s] if s else []
                else:
                    return []

            for action, default_combo in default_custom.items():
                if not enabled_hotkeys.get(action, True):
                    continue
                combos = iter_combos(custom_hotkeys.get(action, default_combo))
                for hk in combos:
                    hotkey_map[hk] = lambda: None
                    # 冲突提示（不阻塞注册）
                    if conflict_hint and hasattr(self.hotkey_manager, "_check_system_conflicts"):
                        ok, msg = self.hotkey_manager._check_system_conflicts(hk)
                        if ok and msg:
                            logging.warning(f"可能与常见应用快捷键冲突：{msg}")
                        elif not ok:
                            logging.warning(f"检测到系统快捷键冲突：{msg}")

            if not hotkey_map:
                logging.debug("未配置任何热键，跳过注册")
                return

            if self.hotkey_manager.is_available():
                success, error_msg = self.hotkey_manager.register_hotkeys(hotkey_map)
                if success:
                    logging.info(f"批量全局快捷键已注册，共 {len(self.hotkey_manager.get_current_hotkeys())} 个")
                else:
                    logging.warning(f"批量全局快捷键注册失败: {error_msg}")
            else:
                logging.warning("快捷键功能不可用，请安装 pynput 库")

        except Exception as e:
            logging.error(f"批量设置全局快捷键失败: {e}")
    
    def trigger_ocr_capture(self):
        """快捷键触发OCR截图"""
        try:
            # 检查是否已经在运行
            if self.ocr_worker and self.ocr_thread and self.ocr_thread.isRunning():
                logging.info("OCR已在运行中，忽略快捷键触发")
                return
            
            # 检查必要条件
            kws = self.keyword_panel.get_keywords()
            if not kws:
                logging.warning("快捷键触发失败：未设置关键词")
                # 可以选择显示提示或自动打开关键词设置
                return
            
            if not self.region:
                logging.warning("快捷键触发失败：未选择区域")
                # 可以选择显示提示或自动打开区域选择
                return
            
            # 触发OCR截图
            logging.info("🎯 快捷键触发OCR截图")
            self.start_capture()
            
        except Exception as e:
            logging.error(f"快捷键触发OCR失败: {e}")

    def trigger_fullscreen_ocr(self):
        """通过快捷键触发全屏截图OCR"""
        try:
            # 检查是否已经在运行
            if self.ocr_worker and self.ocr_thread and self.ocr_thread.isRunning():
                logging.info("OCR已在运行中，忽略全屏快捷键触发")
                return

            kws = self.keyword_panel.get_keywords()
            if not kws:
                logging.warning("全屏快捷键触发失败：未设置关键词")
                return

            screen = QApplication.primaryScreen()
            if not screen:
                logging.warning("无法获取主屏幕信息，终止全屏OCR触发")
                return
            rect = screen.geometry()
            self.region = (rect.left(), rect.top(), rect.width(), rect.height())
            self.status_panel.update_status(region=self.region, keywords_count=len(kws))
            self.control_panel.set_status("使用全屏区域进行识别", "green")
            logging.info(f"🎯 全屏OCR快捷键触发，区域: {self.region}")
            self.start_capture()
        except Exception as e:
            logging.error(f"全屏OCR快捷键触发失败: {e}")

    def start_clipboard_ocr(self):
        """启动剪贴板图片单次OCR识别"""
        try:
            self.settings = load_settings()
            kws = self.keyword_panel.get_keywords()
            if not kws:
                QMessageBox.warning(self, "输入提示", "请添加关键词")
                return

            if self.control_panel.is_accurate_option_disabled():
                version = "general"
            else:
                version = self.settings.get("ocr_version", "general")

            interval = self.control_panel.get_interval()
            mode = self.settings.get("match_mode", "exact")
            fthr = self.settings.get("fuzzy_threshold", 0.85)

            logging.info(f"启动剪贴板OCR(version={version}, mode={mode}, thr={fthr})")

            # 仅用于配置初始化，区域占位即可
            self.clipboard_worker = OCRWorker(kws, (0, 0, 1, 1), interval, match_mode=mode,
                                              fuzzy_threshold=fthr, ocr_version=version)
            self.clipboard_thread = SingleImageOCRThread(self.clipboard_worker)

            # 信号链接（与连续识别保持一致）
            self.clipboard_worker.log_signal.connect(self.log_panel.append_log)
            self.clipboard_worker.stat_signal.connect(self.log_panel.update_statistics)
            self.clipboard_worker.status_signal.connect(self.status_panel.update_worker_status)
            self.clipboard_worker.status_signal.connect(self.on_ocr_status_update)
            self.clipboard_worker.save_signal.connect(lambda *_: (build_log_index(), self.history_panel.refresh(), self.analytics_panel.refresh_data()))
            self.clipboard_worker.save_signal.connect(self.on_ocr_match_found)
            self.clipboard_worker.error_popup_signal.connect(self.show_error_popup)
            self.clipboard_worker.finished_signal.connect(self.on_clipboard_ocr_finished)

            self.clipboard_thread.start()
            self.control_panel.set_status("剪贴板识别中...", "green")
            self.control_panel.enable_buttons(False, False)
        except Exception as e:
            logging.exception("start_clipboard_ocr异常")
            QMessageBox.critical(None, "系统错误提示", f"剪贴板OCR启动失败:{e}")

    def on_clipboard_ocr_finished(self):
        """剪贴板单次OCR识别完成后的清理与状态更新"""
        try:
            self.control_panel.set_status("就绪", "blue")
            self.control_panel.enable_buttons(True, False)
        except Exception:
            pass

    def trigger_clipboard_ocr(self):
        """通过快捷键触发剪贴板图片识别（单次）"""
        try:
            if self.ocr_worker and self.ocr_thread and self.ocr_thread.isRunning():
                logging.info("OCR已在运行中，忽略剪贴板快捷键触发")
                return
            kws = self.keyword_panel.get_keywords()
            if not kws:
                logging.warning("剪贴板快捷键触发失败：未设置关键词")
                return
            logging.info("🎯 快捷键触发剪贴板图片识别")
            self.start_clipboard_ocr()
        except Exception as e:
            logging.error(f"剪贴板OCR快捷键触发失败: {e}")

    def toggle_always_on_top(self):
        """切换窗口置顶状态并写回设置"""
        try:
            # 确保设置结构存在
            self.settings.setdefault("ui", {}).setdefault("window", {}).setdefault("always_on_top", False)
            current = self.settings["ui"]["window"]["always_on_top"]
            new_state = not current
            self.settings["ui"]["window"]["always_on_top"] = new_state
            save_settings(self.settings)

            # 应用窗口置顶标志
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, new_state)
            # 重新显示以应用标志
            self.show(); self.raise_(); self.activateWindow()

            tip = "已置顶" if new_state else "已取消置顶"
            logging.info(f"窗口置顶状态切换: {tip}")
            try:
                dynamic_island_manager.show_status(tip, QColor("green") if new_state else QColor("gray"))
            except Exception:
                pass
        except Exception as e:
            logging.error(f"切换窗口置顶失败: {e}")

    def toggle_window_visibility(self):
        """显示/隐藏主窗口"""
        try:
            if self.isVisible():
                self.hide()
                logging.info("主窗口已隐藏")
            else:
                self.show(); self.raise_(); self.activateWindow()
                logging.info("主窗口已显示并置顶")
        except Exception as e:
            logging.error(f"切换窗口可见性失败: {e}")

    def ensure_tray_icon(self):
        """确保系统托盘图标已创建"""
        try:
            from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
            from PyQt6.QtGui import QIcon
            if hasattr(self, 'tray_icon') and self.tray_icon is not None:
                return
            icon = self.windowIcon()
            if not icon and os.path.exists("285.ico"):
                icon = QIcon("285.ico")
            self.tray_icon = QSystemTrayIcon(icon if icon else QIcon(), self)
            menu = QMenu()
            restore_action = menu.addAction("显示主窗口")
            quit_action = menu.addAction("退出程序")
            restore_action.triggered.connect(self.restore_from_tray)
            quit_action.triggered.connect(QApplication.quit)
            self.tray_icon.setContextMenu(menu)
            self.tray_icon.activated.connect(lambda reason: self.restore_from_tray() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
            self.tray_icon.setToolTip("炫舞OCR")
            self.tray_icon.show()
        except Exception as e:
            logging.error(f"创建系统托盘图标失败: {e}")

    def minimize_to_tray(self):
        """最小化到系统托盘"""
        try:
            self.ensure_tray_icon()
            self.hide()
            logging.info("主窗口已最小化到系统托盘")
        except Exception as e:
            logging.error(f"最小化到系统托盘失败: {e}")

    def restore_from_tray(self):
        """从托盘恢复主窗口"""
        try:
            self.show(); self.raise_(); self.activateWindow()
            logging.info("主窗口已从系统托盘恢复显示")
        except Exception as e:
            logging.error(f"从系统托盘恢复失败: {e}")

    def close_current_tab(self):
        """关闭当前活动标签页（若存在）"""
        try:
            from PyQt6.QtWidgets import QTabWidget
            w = QApplication.focusWidget()
            # 向上查找最近的QTabWidget
            tab = None
            while w is not None:
                if isinstance(w, QTabWidget):
                    tab = w
                    break
                w = w.parent()
            if tab is not None and tab.count() > 0:
                idx = tab.currentIndex()
                tab.removeTab(idx)
                logging.info("已关闭当前标签页")
            else:
                logging.debug("未找到可关闭的标签页")
        except Exception as e:
            logging.error(f"关闭当前标签页失败: {e}")

    def open_history_dialog(self):
        """以独立弹窗形式打开历史记录"""
        try:
            if not hasattr(self, 'history_dialog') or self.history_dialog is None:
                self.history_dialog = HistoryDialog(self)
            self.history_dialog.show_dialog()
            logging.info("✅ 历史记录弹窗已打开（快捷键）")
        except Exception as e:
            logging.error(f"历史记录弹窗打开失败: {e}")
    
    def on_hotkey_triggered(self, hotkey_str):
        """快捷键触发信号处理（在主线程安全执行UI动作）"""
        try:
            logging.debug(f"🔍 检测到快捷键触发: {hotkey_str}")
            hk = (hotkey_str or "").strip()

            settings = getattr(self, 'settings', {}) or {}
            actions_map = {}

            # 主快捷键（来自设置）
            main_hotkey = settings.get("shortcut_key", "").strip()
            if main_hotkey:
                actions_map[main_hotkey] = self.trigger_ocr_capture

            # 默认自定义映射
            default_custom = {
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
                "close_tab": "Ctrl+W",
            }
            enabled_hotkeys = settings.get("enabled_hotkeys", {})
            custom_hotkeys = settings.get("custom_hotkeys", {})

            def iter_combos(val):
                if isinstance(val, list):
                    return [s.strip() for s in val if isinstance(s, str) and s.strip()]
                elif isinstance(val, str):
                    s = val.strip()
                    return [s] if s else []
                else:
                    return []

            # 动作映射
            action_exec = {
                "region_select": self.open_region_selector,
                "fullscreen_ocr": self.trigger_fullscreen_ocr,
                "clipboard_ocr": self.trigger_clipboard_ocr,
                "quick_ocr": self.trigger_ocr_capture,
                "open_settings": lambda: self.open_setting_dialog("unified_settings"),
                "toggle_visibility": self.toggle_window_visibility,
                "always_on_top": self.toggle_always_on_top,
                "open_history": self.open_history_dialog,
                "perf_panel": self.show_optimization_status,
                "help_window": self.show_help_window,
                "help_batch": lambda: self.show_help_topic("批量处理"),
                "refresh_ui": self.refresh_all_ui_text,
                "minimize_tray": self.minimize_to_tray,
                "close_tab": self.close_current_tab,
            }

            for action, default_combo in default_custom.items():
                if not enabled_hotkeys.get(action, True):
                    continue
                combos = iter_combos(custom_hotkeys.get(action, default_combo))
                for combo in combos:
                    actions_map[combo] = action_exec[action]

            # 兜底：固定映射（避免旧设置缺省时无法触发）
            fallback = {
                "Ctrl+F2": self.open_region_selector,
                "Ctrl+F3": self.trigger_fullscreen_ocr,
                "F3": self.trigger_clipboard_ocr,
                "Ctrl+Shift+V": self.trigger_clipboard_ocr,
                "Ctrl+Shift+C": self.trigger_ocr_capture,
                "Ctrl+,": lambda: self.open_setting_dialog("unified_settings"),
                "Ctrl+Alt+H": self.toggle_window_visibility,
                "Ctrl+T": self.toggle_always_on_top,
                "Ctrl+Shift+H": self.open_history_dialog,
                "Ctrl+P": self.show_optimization_status,
                "F1": self.show_help_window,
                "Ctrl+B": lambda: self.show_help_topic("批量处理"),
                "F5": self.refresh_all_ui_text,
                "Ctrl+M": self.minimize_to_tray,
                "Ctrl+W": self.close_current_tab,
            }
            for k, v in fallback.items():
                actions_map.setdefault(k, v)

            action = actions_map.get(hk)
            if action:
                action()
            else:
                logging.debug(f"未匹配的快捷键: {hotkey_str}")
        except Exception as e:
            logging.error(f"快捷键动作执行失败: {e}")
    
    def handle_dynamic_island_action(self, action):
        """处理灵动岛动作信号"""
        try:
            logging.debug(f"🏝️ 灵动岛动作触发: {action}")
            
            if action == "quick_ocr":
                # 快速OCR - 触发截图识别
                logging.info("🎯 灵动岛触发快速OCR")
                self.start_capture()
                
            elif action == "settings":
                # 打开设置面板
                logging.info("⚙️ 灵动岛触发设置面板")
                # 使用统一设置对话框工厂方法，确保兼容性
                try:
                    self.open_setting_dialog("unified_settings")
                except Exception:
                    # 回退到API密钥设置，避免完全失败
                    self.open_setting_dialog("api_key_settings")
                
            elif action == "history":
                # 以独立弹窗形式打开历史记录
                logging.info("📜 灵动岛触发历史记录弹窗")
                try:
                    # 懒加载弹窗
                    if not hasattr(self, 'history_dialog') or self.history_dialog is None:
                        self.history_dialog = HistoryDialog(self)

                    # 打开弹窗并聚焦
                    self.history_dialog.show_dialog()
                    logging.info("✅ 历史记录弹窗已打开")
                except Exception as e:
                    logging.error(f"打开历史记录弹窗失败: {e}")
                    # 回退到嵌入式面板，保证功能可达
                    try:
                        if hasattr(self, 'history_panel') and self.history_panel is not None:
                            self.show(); self.raise_(); self.activateWindow()
                            self.history_panel.refresh()
                            self.history_panel.show(); self.history_panel.setVisible(True)
                    except Exception:
                        pass
                    
        except Exception as e:
            logging.error(f"处理灵动岛动作失败: {e}")
    
    def handle_dynamic_island_clicked(self):
        """处理灵动岛点击事件"""
        try:
            logging.debug("🏝️ 灵动岛被点击")
            # 点击事件已处理，不执行任何默认动作
            logging.info("🏝️ 灵动岛点击事件已处理")
        except Exception as e:
            logging.error(f"处理灵动岛点击失败: {e}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            # 停止OCR工作
            self.stop_capture()
            
            # 取消快捷键注册
            if hasattr(self, 'hotkey_manager'):
                self.hotkey_manager.unregister_current_hotkey()
            
            # 停止备份管理器
            if hasattr(self, 'backup_manager'):
                self.backup_manager.stop_auto_backup()
            
            # 停止云同步管理器
            if hasattr(self, 'cloud_sync_manager'):
                self.cloud_sync_manager.stop_auto_sync()
            
            # 停止主题监听器
            if hasattr(self, 'theme_timer'):
                self.theme_timer.stop()
            
            xuanwu_logger.info("🔚 应用程序正常关闭")
            logging.debug("程序退出流程完成")
            event.accept()
            
        except Exception as e:
            logging.error(f"关闭应用程序时出错: {e}")
            event.accept()

    def on_ocr_match_found(self, *args):
        """OCR匹配成功时的处理"""


    def on_ocr_status_update(self, type_str, payload: dict):
        try:
            if type_str == "status":
                api_ok = bool(payload.get("api_ok", False))
                if api_ok:
                    dynamic_island_manager.show_status("API正常", QColor("#4caf50"))
                    # 更新灵动岛内部的监控数据
                    dynamic_island_manager.update_monitoring_data(
                        api_status="正常",
                        network_status="正常"
                    )
                else:
                    dynamic_island_manager.show_status("API异常", QColor("#ef5350"))
                    # 更新灵动岛内部的监控数据
                    dynamic_island_manager.update_monitoring_data(
                        api_status="异常",
                        network_status="异常"
                    )
            elif type_str == "trend":
                total = payload.get("total_hits", 0)
                hits_per_keyword = payload.get("hits_per_keyword", {}) or {}
                top_keyword = None
                if isinstance(hits_per_keyword, dict) and hits_per_keyword:
                    top_keyword = max(hits_per_keyword.items(), key=lambda kv: kv[1])[0]
                subtitle = f"总命中 {total} 次" + (f" | Top: {top_keyword}" if top_keyword else "")
                dynamic_island_manager.show_notification("关键词趋势", subtitle, None, QColor("#1976d2"))
                # 更新灵动岛内部的统计数据
                dynamic_island_manager.update_monitoring_data(
                    total_hits=total,
                    hits_per_keyword=hits_per_keyword
                )
        except Exception as e:
            logging.debug(f"on_ocr_status_update处理异常: {e}")


    def show_error_popup(self, msg: str):
        # 始终在状态栏显示错误信息
        self.statusBar().showMessage(f"错误: {msg}", 5000)  # 显示5秒
        # 通过灵动岛显示错误通知
        try:
            dynamic_island_manager.show_notification("错误", msg, None, QColor("#e57373"))
        except Exception as _e:
            logging.debug(f"动态岛错误通知失败: {_e}")
        
        # 根据设置决定是否弹窗
        if self.settings.get("enable_error_popup", True) and not self.error_popup_active:
            self.error_popup_active = True
            QMessageBox.warning(self, "识别提示", msg)
            self.error_popup_active = False
            
            # 只有在严重错误时才停止捕获，避免正常识别过程中的错误导致OCR停止
            critical_errors = [
                "程序运行异常",
                "无法获取token",
                "OCR启动失败",
                "严重错误",
                "内存不足",
                "系统错误"
            ]
            
            # 检查是否为严重错误
            is_critical = any(critical_keyword in msg for critical_keyword in critical_errors)
            if is_critical:
                logging.warning(f"检测到严重错误，停止OCR捕获: {msg}")
                self.stop_capture()
            else:
                logging.debug(f"非严重错误，继续OCR捕获: {msg}")

    def moveEvent(self, event):
        """窗口移动事件处理"""
        super().moveEvent(event)
        # 更新灵动岛位置
        if hasattr(self, 'dynamic_island') and self.dynamic_island:
            self.dynamic_island.update_position()

    def resizeEvent(self, event):
        """窗口大小调整事件处理"""
        super().resizeEvent(event)
        # 更新灵动岛位置
        if hasattr(self, 'dynamic_island') and self.dynamic_island:
            self.dynamic_island.update_position()

    def showEvent(self, event):
        """窗口显示事件处理"""
        super().showEvent(event)
        # 只更新灵动岛位置，不强制显示
        if hasattr(self, 'dynamic_island') and self.dynamic_island:
            self.dynamic_island.update_position()

    def changeEvent(self, event):
        """窗口状态变化事件处理"""
        super().changeEvent(event)
        if hasattr(self, 'dynamic_island') and self.dynamic_island:
            if event.type() == event.Type.WindowStateChange:
                # 检查窗口是否被最小化
                if self.isMinimized():
                    # 主窗口最小化时，设置灵动岛为独立模式
                    self.dynamic_island.set_independent_mode(True)
                    logging.info("主窗口最小化，灵动岛切换到独立模式")
                else:
                    # 主窗口恢复时，恢复灵动岛的正常模式
                    self.dynamic_island.set_independent_mode(False)
                    logging.info("主窗口恢复，灵动岛恢复正常模式")

# ====================== 启动密码验证 ========================
def check_startup_password() -> bool:
    """增强版启动密码验证
    
    Returns:
        bool: 密码验证通过返回True，否则返回False
    """
    import logging
    import time
    import os
    from datetime import datetime, timedelta
    from core.settings import load_settings, save_settings
    from PyQt6.QtWidgets import QInputDialog, QMessageBox, QLineEdit
    
    settings = load_settings()
    
    # 如果未启用启动密码保护，直接通过
    if not settings.get("enable_startup_password", False):
        return True
    
    # 获取设置的密码
    stored_password = settings.get("startup_password", "")
    if not stored_password:
        # 启用了密码保护但未设置密码，提示用户
        QMessageBox.warning(None, "启动密码保护", "已启用启动密码保护但未设置密码，请先在设置中配置密码。")
        return True
    
    # 获取安全设置
    max_attempts = settings.get("startup_password_max_attempts", 3)
    lockout_time = settings.get("startup_password_lockout_time", 5)  # 分钟
    log_attempts = settings.get("startup_password_log_attempts", True)
    
    # 检查是否处于锁定状态
    lockout_file = "password_lockout.tmp"
    if lockout_time > 0 and os.path.exists(lockout_file):
        try:
            with open(lockout_file, 'r') as f:
                lockout_until = datetime.fromisoformat(f.read().strip())
            
            if datetime.now() < lockout_until:
                remaining = lockout_until - datetime.now()
                minutes = int(remaining.total_seconds() / 60)
                seconds = int(remaining.total_seconds() % 60)
                QMessageBox.critical(
                    None, 
                    "账户已锁定", 
                    f"由于多次密码验证失败，账户已被锁定。\n剩余锁定时间: {minutes}分{seconds}秒"
                )
                if log_attempts:
                    logging.warning(f"启动密码验证被拒绝 - 账户锁定中，剩余时间: {minutes}分{seconds}秒")
                return False
            else:
                # 锁定时间已过，删除锁定文件
                os.remove(lockout_file)
        except Exception as e:
            logging.error(f"读取锁定文件失败: {e}")
            # 如果读取失败，删除可能损坏的锁定文件
            try:
                os.remove(lockout_file)
            except (OSError, FileNotFoundError):
                pass
    
    # 密码验证循环
    failed_attempts = 0
    for attempt in range(max_attempts):
        password, ok = QInputDialog.getText(
            None, 
            "🔐 启动密码验证", 
            f"请输入启动密码（剩余尝试次数：{max_attempts - attempt}）：",
            QLineEdit.EchoMode.Password
        )
        
        if not ok:
            # 用户取消输入
            if log_attempts:
                logging.info("用户取消启动密码验证")
            QMessageBox.information(None, "启动密码保护", "程序启动已取消。")
            return False
        
        if password == stored_password:
            # 密码正确，清除可能存在的锁定文件
            if os.path.exists(lockout_file):
                try:
                    os.remove(lockout_file)
                except (OSError, FileNotFoundError):
                    pass
            
            if log_attempts:
                logging.info("启动密码验证成功")
            return True
        else:
            failed_attempts += 1
            
            if log_attempts:
                logging.warning(f"启动密码验证失败，尝试次数：{failed_attempts}/{max_attempts}")
            
            if attempt < max_attempts - 1:
                QMessageBox.warning(
                    None, 
                    "密码错误", 
                    f"密码错误，还有 {max_attempts - attempt - 1} 次机会。"
                )
            else:
                # 达到最大尝试次数
                if lockout_time > 0:
                    # 创建锁定文件
                    lockout_until = datetime.now() + timedelta(minutes=lockout_time)
                    try:
                        with open(lockout_file, 'w') as f:
                            f.write(lockout_until.isoformat())
                        
                        QMessageBox.critical(
                            None, 
                            "账户已锁定", 
                            f"密码错误次数过多，账户已被锁定 {lockout_time} 分钟。\n程序将退出。"
                        )
                        
                        if log_attempts:
                            logging.critical(f"启动密码验证失败次数过多，账户已锁定 {lockout_time} 分钟")
                    except Exception as e:
                        logging.error(f"创建锁定文件失败: {e}")
                        QMessageBox.critical(None, "密码错误", "密码错误次数过多，程序将退出。")
                else:
                    QMessageBox.critical(None, "密码错误", "密码错误次数过多，程序将退出。")
                    
                    if log_attempts:
                        logging.critical("启动密码验证失败次数过多，程序退出")
    
    return False

def reset_password_lockout():
    """重置密码锁定状态（用于管理员或紧急情况）"""
    lockout_file = "password_lockout.tmp"
    if os.path.exists(lockout_file):
        try:
            os.remove(lockout_file)
            return True
        except Exception as e:
            logging.error(f"重置密码锁定失败: {e}")
            return False
    return True

# ====================== 启动入口 ========================
if __name__ == "__main__":
    try:
        # 使用新的应用初始化器
        if not initialize_application():
            QMessageBox.critical(None, "初始化失败", "应用程序初始化失败，程序退出")
            sys.exit(1)
        
        # 获取初始化器实例
        initializer = get_app_initializer()
        settings = initializer.get_settings()
        logger = initializer.get_logger()
        
        # API密钥验证
        has_std, has_acc = ensure_api_key()
        if not has_std:
            QMessageBox.critical(None, "系统错误提示", "必须输入标准版密钥，程序退出")
            sys.exit(0)

        logger.info("API密钥验证完成")

        app = QApplication(sys.argv)
        
        # 设置Qt消息处理器来过滤Windows系统错误
        def qt_message_handler(mode, context, message):
            # 过滤掉UpdateLayeredWindowIndirect failed错误
            if "UpdateLayeredWindowIndirect failed" in message:
                return
            # 其他消息正常输出
            if mode == 0:  # QtDebugMsg
                print(f"Qt Debug: {message}")
            elif mode == 1:  # QtWarningMsg
                print(f"Qt Warning: {message}")
            elif mode == 2:  # QtCriticalMsg
                print(f"Qt Critical: {message}")
            elif mode == 3:  # QtFatalMsg
                print(f"Qt Fatal: {message}")
        
        # 安装Qt消息处理器
        from PyQt6.QtCore import qInstallMessageHandler
        qInstallMessageHandler(qt_message_handler)
        
        # 启动密码验证
        if not check_startup_password():
            logger.info("启动密码验证失败，程序退出")
            sys.exit(0)
        
        # 初始化国际化系统并设置语言
        from core.i18n import set_language, get_current_language
        current_language = settings.get('language', 'zh_CN')
        
        # 将显示名称映射为语言代码
        language_display_to_code = {
            '简体中文': 'zh_CN',
            '繁體中文': 'zh_TW', 
            'English': 'en_US',
            '日本語': 'ja_JP'
        }
        
        # 如果是显示名称，转换为语言代码
        if current_language in language_display_to_code:
            current_language = language_display_to_code[current_language]
        
        logging.info(f"设置程序语言为: {current_language}")
        set_language(current_language)
        logging.info(f"当前语言已设置为: {get_current_language()}")
        
        if settings.get("auto_theme", False):
            # 检测系统主题并转换格式
            system_theme = detect_system_theme()
            theme_map = {'light': '浅色', 'dark': '深色'}
            settings["theme"] = theme_map.get(system_theme, '浅色')
            save_settings(settings)  # 保存更新后的主题设置
        apply_theme(QApplication.instance(), settings["theme"])
        
        # 应用字体设置
        font_size = settings.get("font_size", 12)
        from PyQt6.QtGui import QFont
        font = QFont()
        font.setPointSize(font_size)
        app.setFont(font)

        # 根据配置自动启动优化功能
        optimization_config = {}
        try:
            import json
            config_path = os.path.join(os.path.dirname(__file__), 'config', 'optimization_config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    optimization_config = json.load(f).get('optimization_settings', {}).get('auto_start', {})
        except Exception as e:
            logger.warning(f"读取优化配置失败，使用默认设置: {e}")
            optimization_config = {
                "performance_monitoring": True,
                "thread_pool_manager": True,
                "cache_manager": True,
                "error_handler": True
            }
        
        # 自动启动性能监控
        if optimization_config.get("performance_monitoring", True):
            from core.performance_monitor import start_performance_monitoring
            start_performance_monitoring()
            logger.info("✅ 性能监控已自动启动")
        
        # 初始化线程池管理器（自动运行）
        if optimization_config.get("thread_pool_manager", True):
            from core.thread_pool_manager import get_thread_pool_manager
            thread_manager = get_thread_pool_manager()
            logger.info("✅ 线程池管理器已自动初始化")
        
        # 初始化缓存管理器（自动运行）
        if optimization_config.get("cache_manager", True):
            from core.cache_manager import get_cache_manager
            cache_manager = get_cache_manager()
            logger.info("✅ 缓存管理器已自动初始化")
        
        # 初始化错误处理器（自动运行）
        if optimization_config.get("error_handler", True):
            from core.error_handler import get_error_handler
            error_handler = get_error_handler()
            logger.info("✅ 错误处理器已自动初始化")

        w = MainWindow(has_accurate_key=has_acc)
        w.settings = settings  # 把设置传入主窗口
        w.show()
        
        logger.info("应用程序启动完成 - 所有优化功能已自动启用")
        
        # 注册清理函数
        def cleanup():
            try:
                # 停止性能监控
                from core.performance_monitor import stop_performance_monitoring
                try:
                    stop_performance_monitoring()
                except KeyboardInterrupt:
                    # 避免退出阶段被用户中断导致异常
                    logging.warning("停止性能监控被中断，跳过等待")
                except Exception as e:
                    logging.debug(f"停止性能监控异常: {e}")
                
                # 清理其他资源
                try:
                    initializer.cleanup()
                except KeyboardInterrupt:
                    logging.warning("应用清理被中断，继续退出")
                except Exception as e:
                    logging.debug(f"应用清理异常: {e}")
                
                logger.info("所有优化功能已自动清理")
            except Exception:
                # 退出阶段不传播异常，确保进程顺利结束
                pass
        atexit.register(cleanup)
        
        sys.exit(app.exec())
    except Exception as e:
        error_msg = f"程序异常退出: {e}"
        logging.exception("主入口异常")
        QMessageBox.critical(None, "系统错误提示", error_msg)
        sys.exit(1)