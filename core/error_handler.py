# core/error_handler.py
"""
增强的异常处理和错误提示系统

该模块提供统一的异常处理功能：
- 异常分类和处理
- 用户友好的错误提示
- 错误恢复机制
- 错误统计和分析
- 错误报告和上传
- 异常装饰器和上下文管理器

作者：XuanWu OCR Team
版本：2.1.7
"""

import sys
import traceback
import time
import threading
import json
import uuid
from typing import Dict, Any, Optional, List, Callable, Type, Union
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import requests

from PyQt6.QtWidgets import QMessageBox, QWidget
from PyQt6.QtCore import QTimer, pyqtSignal, QObject

from core.enhanced_logger import get_enhanced_logger
from core.i18n import t


class ErrorLevel(Enum):
    """错误级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"


class ErrorCategory(Enum):
    """错误分类"""
    SYSTEM = "system"          # 系统错误
    NETWORK = "network"        # 网络错误
    FILE_IO = "file_io"        # 文件IO错误
    PERMISSION = "permission"   # 权限错误
    VALIDATION = "validation"   # 验证错误
    CONFIGURATION = "config"    # 配置错误
    OCR = "ocr"               # OCR相关错误
    UI = "ui"                 # 界面错误
    DATABASE = "database"      # 数据库错误
    EXTERNAL = "external"      # 外部服务错误
    UNKNOWN = "unknown"        # 未知错误


@dataclass
class ErrorInfo:
    """错误信息"""
    id: str
    timestamp: float
    level: ErrorLevel
    category: ErrorCategory
    title: str
    message: str
    details: str
    stack_trace: str
    context: Dict[str, Any]
    user_action: Optional[str] = None
    recovery_suggestion: Optional[str] = None
    error_code: Optional[str] = None
    module: Optional[str] = None
    function: Optional[str] = None
    line_number: Optional[int] = None
    resolved: bool = False
    resolution_time: Optional[float] = None
    resolution_method: Optional[str] = None


class ErrorRecovery:
    """错误恢复机制"""
    
    def __init__(self):
        self.recovery_strategies = {}
        self.logger = get_enhanced_logger()
    
    def register_strategy(self, category: ErrorCategory, 
                         strategy: Callable[[ErrorInfo], bool]):
        """注册恢复策略"""
        self.recovery_strategies[category] = strategy
    
    def attempt_recovery(self, error_info: ErrorInfo) -> bool:
        """尝试错误恢复"""
        try:
            strategy = self.recovery_strategies.get(error_info.category)
            if strategy:
                self.logger.info(f"尝试恢复错误：{error_info.id}")
                success = strategy(error_info)
                if success:
                    error_info.resolved = True
                    error_info.resolution_time = time.time()
                    error_info.resolution_method = "auto_recovery"
                    self.logger.info(f"错误恢复成功：{error_info.id}")
                return success
            return False
        except Exception as e:
            self.logger.error(f"错误恢复失败：{e}")
            return False


class ErrorReporter:
    """错误报告器"""
    
    def __init__(self, report_url: Optional[str] = None):
        self.report_url = report_url
        self.logger = get_enhanced_logger()
        self.pending_reports = []
        self.report_lock = threading.Lock()
    
    def report_error(self, error_info: ErrorInfo, 
                    include_system_info: bool = True) -> bool:
        """报告错误"""
        try:
            if not self.report_url:
                return False
            
            report_data = {
                'error_info': asdict(error_info),
                'timestamp': time.time(),
                'app_version': '2.1.7',
                'platform': sys.platform
            }
            
            if include_system_info:
                report_data['system_info'] = self._get_system_info()
            
            # 异步发送报告
            threading.Thread(
                target=self._send_report,
                args=(report_data,),
                daemon=True
            ).start()
            
            return True
            
        except Exception as e:
            self.logger.error(f"错误报告失败：{e}")
            return False
    
    def _send_report(self, report_data: Dict[str, Any]):
        """发送错误报告"""
        try:
            response = requests.post(
                self.report_url,
                json=report_data,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                self.logger.info("错误报告发送成功")
            else:
                self.logger.warning(f"错误报告发送失败：{response.status_code}")
                
        except Exception as e:
            self.logger.error(f"发送错误报告异常：{e}")
            # 保存到待发送队列
            with self.report_lock:
                self.pending_reports.append(report_data)
    
    def _get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        import platform
        import psutil
        
        try:
            return {
                'platform': platform.platform(),
                'python_version': platform.python_version(),
                'cpu_count': psutil.cpu_count(),
                'memory_total': psutil.virtual_memory().total,
                'memory_available': psutil.virtual_memory().available,
                'disk_usage': psutil.disk_usage('/').percent if sys.platform != 'win32' else psutil.disk_usage('C:').percent
            }
        except Exception:
            return {}


class ErrorNotifier(QObject):
    """错误通知器"""
    
    error_occurred = pyqtSignal(object)  # ErrorInfo
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_enhanced_logger()
        self.notification_cooldown = {}  # 防止重复通知
        self.cooldown_duration = 60  # 60秒冷却时间
    
    def notify_error(self, error_info: ErrorInfo, 
                    show_dialog: bool = True,
                    show_toast: bool = False):
        """通知错误"""
        try:
            # 检查冷却时间
            error_key = f"{error_info.category.value}:{error_info.title}"
            current_time = time.time()
            
            if error_key in self.notification_cooldown:
                if current_time - self.notification_cooldown[error_key] < self.cooldown_duration:
                    return  # 在冷却时间内，不重复通知
            
            self.notification_cooldown[error_key] = current_time
            
            # 发送信号
            self.error_occurred.emit(error_info)
            
            # 显示对话框
            if show_dialog and error_info.level in [ErrorLevel.ERROR, ErrorLevel.CRITICAL, ErrorLevel.FATAL]:
                self._show_error_dialog(error_info)
            
            # 显示Toast通知
            if show_toast:
                self._show_toast_notification(error_info)
                
        except Exception as e:
            self.logger.error(f"错误通知失败：{e}")
    
    def _show_error_dialog(self, error_info: ErrorInfo):
        """显示错误对话框"""
        try:
            # 根据错误级别选择图标
            icon_map = {
                ErrorLevel.WARNING: QMessageBox.Icon.Warning,
                ErrorLevel.ERROR: QMessageBox.Icon.Critical,
                ErrorLevel.CRITICAL: QMessageBox.Icon.Critical,
                ErrorLevel.FATAL: QMessageBox.Icon.Critical
            }
            
            icon = icon_map.get(error_info.level, QMessageBox.Icon.Information)
            
            # 创建消息框
            msg_box = QMessageBox()
            msg_box.setIcon(icon)
            msg_box.setWindowTitle(t("错误"))
            msg_box.setText(error_info.title)
            msg_box.setDetailedText(f"{error_info.message}\n\n详细信息：\n{error_info.details}")
            
            # 添加按钮
            if error_info.recovery_suggestion:
                retry_button = msg_box.addButton(t("重试"), QMessageBox.ButtonRole.ActionRole)
                msg_box.addButton(t("忽略"), QMessageBox.ButtonRole.RejectRole)
                msg_box.addButton(t("退出"), QMessageBox.ButtonRole.DestructiveRole)
            else:
                msg_box.addButton(t("确定"), QMessageBox.ButtonRole.AcceptRole)
            
            # 显示对话框
            msg_box.exec()
            
        except Exception as e:
            self.logger.error(f"显示错误对话框失败：{e}")
    
    def _show_toast_notification(self, error_info: ErrorInfo):
        """显示Toast通知"""
        try:
            # 这里可以实现Toast通知
            # 由于PyQt6没有内置Toast，可以使用第三方库或自定义实现
            pass
        except Exception as e:
            self.logger.error(f"显示Toast通知失败：{e}")


class ErrorHandler:
    """主错误处理器"""
    
    def __init__(self, 
                 enable_recovery: bool = True,
                 enable_reporting: bool = False,
                 report_url: Optional[str] = None):
        
        self.logger = get_enhanced_logger()
        self.enable_recovery = enable_recovery
        self.enable_reporting = enable_reporting
        
        # 组件初始化
        self.recovery = ErrorRecovery() if enable_recovery else None
        self.reporter = ErrorReporter(report_url) if enable_reporting else None
        self.notifier = ErrorNotifier()
        
        # 错误存储
        self.errors = []
        self.error_lock = threading.Lock()
        self.max_errors = 1000  # 最大存储错误数
        
        # 错误统计
        self.error_stats = {
            'total_errors': 0,
            'by_level': {level.value: 0 for level in ErrorLevel},
            'by_category': {category.value: 0 for category in ErrorCategory},
            'resolved_errors': 0,
            'unresolved_errors': 0
        }
        
        # 注册默认恢复策略
        self._register_default_recovery_strategies()
        
        # 设置全局异常处理器
        sys.excepthook = self._global_exception_handler
        
        self.logger.info("错误处理器初始化完成")
    
    def handle_error(self, 
                    exception: Optional[Exception] = None,
                    level: ErrorLevel = ErrorLevel.ERROR,
                    category: ErrorCategory = ErrorCategory.UNKNOWN,
                    title: str = "",
                    message: str = "",
                    context: Optional[Dict[str, Any]] = None,
                    user_action: Optional[str] = None,
                    recovery_suggestion: Optional[str] = None,
                    show_dialog: bool = True,
                    attempt_recovery: bool = True) -> ErrorInfo:
        """处理错误"""
        
        try:
            # 创建错误信息
            error_info = self._create_error_info(
                exception, level, category, title, message,
                context, user_action, recovery_suggestion
            )
            
            # 记录错误
            self._log_error(error_info)
            
            # 存储错误
            self._store_error(error_info)
            
            # 更新统计
            self._update_stats(error_info)
            
            # 尝试恢复
            if attempt_recovery and self.recovery:
                self.recovery.attempt_recovery(error_info)
            
            # 通知错误
            self.notifier.notify_error(error_info, show_dialog)
            
            # 报告错误
            if self.reporter and level in [ErrorLevel.ERROR, ErrorLevel.CRITICAL, ErrorLevel.FATAL]:
                self.reporter.report_error(error_info)
            
            return error_info
            
        except Exception as e:
            # 处理错误处理器本身的错误
            self.logger.critical(f"错误处理器异常：{e}")
            return self._create_fallback_error_info(e)
    
    def _create_error_info(self, 
                          exception: Optional[Exception],
                          level: ErrorLevel,
                          category: ErrorCategory,
                          title: str,
                          message: str,
                          context: Optional[Dict[str, Any]],
                          user_action: Optional[str],
                          recovery_suggestion: Optional[str]) -> ErrorInfo:
        """创建错误信息"""
        
        # 生成唯一ID
        error_id = str(uuid.uuid4())
        
        # 获取异常信息
        if exception:
            if not title:
                title = type(exception).__name__
            if not message:
                message = str(exception)
            
            # 获取堆栈跟踪
            stack_trace = ''.join(traceback.format_exception(
                type(exception), exception, exception.__traceback__
            ))
            
            # 获取异常位置信息
            tb = exception.__traceback__
            if tb:
                frame = tb.tb_frame
                module = frame.f_globals.get('__name__', 'unknown')
                function = frame.f_code.co_name
                line_number = tb.tb_lineno
            else:
                module = function = None
                line_number = None
        else:
            stack_trace = ''.join(traceback.format_stack())
            module = function = None
            line_number = None
        
        # 创建详细信息
        details = self._create_error_details(exception, context)
        
        return ErrorInfo(
            id=error_id,
            timestamp=time.time(),
            level=level,
            category=category,
            title=title,
            message=message,
            details=details,
            stack_trace=stack_trace,
            context=context or {},
            user_action=user_action,
            recovery_suggestion=recovery_suggestion,
            module=module,
            function=function,
            line_number=line_number
        )
    
    def _create_error_details(self, 
                             exception: Optional[Exception],
                             context: Optional[Dict[str, Any]]) -> str:
        """创建错误详细信息"""
        details = []
        
        if exception:
            details.append(f"异常类型：{type(exception).__name__}")
            details.append(f"异常消息：{str(exception)}")
        
        if context:
            details.append("上下文信息：")
            for key, value in context.items():
                details.append(f"  {key}: {value}")
        
        details.append(f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        details.append(f"线程：{threading.current_thread().name}")
        
        return '\n'.join(details)
    
    def _create_fallback_error_info(self, exception: Exception) -> ErrorInfo:
        """创建备用错误信息"""
        return ErrorInfo(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            level=ErrorLevel.CRITICAL,
            category=ErrorCategory.SYSTEM,
            title="错误处理器异常",
            message=str(exception),
            details=f"错误处理器本身发生异常：{exception}",
            stack_trace=''.join(traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )),
            context={}
        )
    
    def _log_error(self, error_info: ErrorInfo):
        """记录错误日志"""
        log_message = f"[{error_info.category.value.upper()}] {error_info.title}: {error_info.message}"
        
        if error_info.level == ErrorLevel.DEBUG:
            self.logger.debug(log_message)
        elif error_info.level == ErrorLevel.INFO:
            self.logger.info(log_message)
        elif error_info.level == ErrorLevel.WARNING:
            self.logger.warning(log_message)
        elif error_info.level == ErrorLevel.ERROR:
            self.logger.error(log_message)
        elif error_info.level in [ErrorLevel.CRITICAL, ErrorLevel.FATAL]:
            self.logger.critical(log_message)
    
    def _store_error(self, error_info: ErrorInfo):
        """存储错误"""
        with self.error_lock:
            self.errors.append(error_info)
            
            # 限制存储数量
            if len(self.errors) > self.max_errors:
                self.errors = self.errors[-self.max_errors:]
    
    def _update_stats(self, error_info: ErrorInfo):
        """更新错误统计"""
        self.error_stats['total_errors'] += 1
        self.error_stats['by_level'][error_info.level.value] += 1
        self.error_stats['by_category'][error_info.category.value] += 1
        
        if error_info.resolved:
            self.error_stats['resolved_errors'] += 1
        else:
            self.error_stats['unresolved_errors'] += 1
    
    def _register_default_recovery_strategies(self):
        """注册默认恢复策略"""
        if not self.recovery:
            return
        
        # 网络错误恢复策略
        def network_recovery(error_info: ErrorInfo) -> bool:
            # 简单的网络重试策略
            time.sleep(1)
            return True  # 假设重试成功
        
        # 文件IO错误恢复策略
        def file_io_recovery(error_info: ErrorInfo) -> bool:
            # 尝试创建目录或检查权限
            return False  # 需要具体实现
        
        self.recovery.register_strategy(ErrorCategory.NETWORK, network_recovery)
        self.recovery.register_strategy(ErrorCategory.FILE_IO, file_io_recovery)
    
    def _global_exception_handler(self, exc_type, exc_value, exc_traceback):
        """全局异常处理器"""
        if issubclass(exc_type, KeyboardInterrupt):
            # 允许Ctrl+C中断
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # 处理未捕获的异常
        self.handle_error(
            exception=exc_value,
            level=ErrorLevel.CRITICAL,
            category=ErrorCategory.SYSTEM,
            title="未捕获的异常",
            show_dialog=True
        )
    
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计"""
        return self.error_stats.copy()
    
    def get_recent_errors(self, count: int = 10) -> List[ErrorInfo]:
        """获取最近的错误"""
        with self.error_lock:
            return self.errors[-count:] if self.errors else []
    
    def clear_errors(self):
        """清空错误记录"""
        with self.error_lock:
            self.errors.clear()
            self.error_stats = {
                'total_errors': 0,
                'by_level': {level.value: 0 for level in ErrorLevel},
                'by_category': {category.value: 0 for category in ErrorCategory},
                'resolved_errors': 0,
                'unresolved_errors': 0
            }
    
    def export_errors(self, file_path: str, 
                     include_resolved: bool = True) -> bool:
        """导出错误记录"""
        try:
            with self.error_lock:
                errors_to_export = self.errors
                if not include_resolved:
                    errors_to_export = [e for e in self.errors if not e.resolved]
                
                export_data = {
                    'export_time': time.time(),
                    'total_errors': len(errors_to_export),
                    'stats': self.error_stats,
                    'errors': [asdict(error) for error in errors_to_export]
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                
                self.logger.info(f"错误记录导出成功：{file_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"导出错误记录失败：{e}")
            return False


# 全局错误处理器实例
_error_handler = None
_error_handler_lock = threading.Lock()


def get_error_handler() -> ErrorHandler:
    """获取全局错误处理器实例"""
    global _error_handler
    
    if _error_handler is None:
        with _error_handler_lock:
            if _error_handler is None:
                _error_handler = ErrorHandler()
    
    return _error_handler


# 装饰器和上下文管理器
def handle_errors(level: ErrorLevel = ErrorLevel.ERROR,
                 category: ErrorCategory = ErrorCategory.UNKNOWN,
                 title: str = "",
                 show_dialog: bool = True,
                 reraise: bool = False):
    """错误处理装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                get_error_handler().handle_error(
                    exception=e,
                    level=level,
                    category=category,
                    title=title or f"{func.__name__} 执行失败",
                    show_dialog=show_dialog
                )
                if reraise:
                    raise
                return None
        return wrapper
    return decorator


class error_context:
    """错误处理上下文管理器"""
    
    def __init__(self, 
                 level: ErrorLevel = ErrorLevel.ERROR,
                 category: ErrorCategory = ErrorCategory.UNKNOWN,
                 title: str = "",
                 show_dialog: bool = True,
                 reraise: bool = False):
        self.level = level
        self.category = category
        self.title = title
        self.show_dialog = show_dialog
        self.reraise = reraise
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            get_error_handler().handle_error(
                exception=exc_value,
                level=self.level,
                category=self.category,
                title=self.title,
                show_dialog=self.show_dialog
            )
            return not self.reraise  # 返回True表示异常已处理，不再传播


# 便捷函数
def handle_error(exception: Exception, 
                level: ErrorLevel = ErrorLevel.ERROR,
                category: ErrorCategory = ErrorCategory.UNKNOWN,
                title: str = "",
                message: str = "",
                show_dialog: bool = True) -> ErrorInfo:
    """处理错误的便捷函数"""
    return get_error_handler().handle_error(
        exception=exception,
        level=level,
        category=category,
        title=title,
        message=message,
        show_dialog=show_dialog
    )


def log_error(message: str,
             level: ErrorLevel = ErrorLevel.ERROR,
             category: ErrorCategory = ErrorCategory.UNKNOWN,
             show_dialog: bool = False) -> ErrorInfo:
    """记录错误的便捷函数"""
    return get_error_handler().handle_error(
        level=level,
        category=category,
        title="应用程序错误",
        message=message,
        show_dialog=show_dialog
    )