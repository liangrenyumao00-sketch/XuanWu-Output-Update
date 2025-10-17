# core/enhanced_logger.py
"""
增强日志模块

该模块提供高级日志功能，包括：
- 异步日志写入和缓冲
- 自动日志轮转和压缩
- 性能监控和内存跟踪
- 函数调用追踪
- 错误堆栈记录
- 灵活的日志过滤
- HTML格式日志输出

主要类:
    LogRotationHandler: 日志轮转处理器
    AsyncLogWriter: 异步日志写入器
    LogFilter: 日志过滤器
    DebugTracker: 调试追踪器
    EnhancedLogger: 增强日志记录器

依赖:
    - psutil: 系统性能监控
    - pathlib: 路径处理
    - threading: 多线程支持
    - gzip: 日志压缩

作者: XuanWu Team
版本: 2.1.7
"""

import os
import json
import logging
import threading
import time
import traceback
import functools
import psutil
import gc
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from collections import deque
from pathlib import Path
import gzip
import shutil
import sys
import importlib.util
import inspect

# 导入脱敏功能
try:
    from .log_desensitizer import get_log_desensitizer
except ImportError:
    # 如果脱敏模块不可用，提供一个简单的替代函数
    def get_log_desensitizer():
        class DummyDesensitizer:
            def desensitize_text(self, text):
                return text
        return DummyDesensitizer()

class LogRotationHandler:
    """
    日志轮转处理器
    
    负责管理日志文件的大小和数量，当日志文件超过指定大小时自动进行轮转。
    支持日志压缩以节省磁盘空间。
    
    Attributes:
        base_path (Path): 日志文件基础路径
        max_size_bytes (int): 最大文件大小（字节）
        max_files (int): 最大保留文件数量
        
    Example:
        >>> handler = LogRotationHandler("app.log", max_size_mb=10, max_files=5)
        >>> if handler.should_rotate():
        ...     handler.rotate()
    """
    
    def __init__(self, base_path: str, max_size_mb: int = 10, max_files: int = 5):
        """
        初始化日志轮转处理器
        
        Args:
            base_path (str): 日志文件路径
            max_size_mb (int, optional): 最大文件大小（MB），默认10MB
            max_files (int, optional): 最大保留文件数量，默认5个
        """
        self.base_path = Path(base_path)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_files = max_files
        
    def should_rotate(self) -> bool:
        """检查是否需要轮转"""
        if not self.base_path.exists():
            return False
        return self.base_path.stat().st_size > self.max_size_bytes
    
    def rotate(self) -> None:
        """执行日志轮转"""
        if not self.base_path.exists():
            return
            
        # 移动现有文件
        for i in range(self.max_files - 1, 0, -1):
            old_file = self.base_path.with_suffix(f".{i}.gz")
            new_file = self.base_path.with_suffix(f".{i + 1}.gz")
            if old_file.exists():
                if new_file.exists():
                    new_file.unlink()
                old_file.rename(new_file)
        
        # 压缩当前文件
        rotated_file = self.base_path.with_suffix(".1.gz")
        with open(self.base_path, 'rb') as f_in:
            with gzip.open(rotated_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # 清空当前文件
        self.base_path.unlink()

class AsyncLogWriter:
    """
    异步日志写入器
    
    提供异步、缓冲的日志写入功能，提高日志记录性能。
    支持批量写入和定时刷新，避免频繁的磁盘I/O操作。
    
    Attributes:
        flush_interval (float): 刷新间隔时间（秒）
        max_buffer_size (int): 最大缓冲区大小
        buffer (deque): 日志缓冲区
        
    Example:
        >>> writer = AsyncLogWriter(flush_interval=1.0, max_buffer_size=1000)
        >>> writer.start()
        >>> writer.add_log_entry("app.log", "测试日志", "INFO")
        >>> writer.stop()
    """
    
    def __init__(self, flush_interval: float = 1.0, max_buffer_size: int = 1000):
        """
        初始化异步日志写入器
        
        Args:
            flush_interval (float, optional): 刷新间隔时间（秒），默认1.0秒
            max_buffer_size (int, optional): 最大缓冲区大小，默认1000条
        """
        self.flush_interval = flush_interval
        self.max_buffer_size = max_buffer_size
        self.buffer = deque()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.writer_thread = None
        self.file_handles: Dict[str, Any] = {}
        
    def start(self):
        """启动异步写入线程"""
        if self.writer_thread is None or not self.writer_thread.is_alive():
            self.stop_event.clear()
            self.writer_thread = threading.Thread(target=self._write_loop, daemon=True)
            self.writer_thread.start()
    
    def stop(self):
        """停止异步写入线程"""
        self.stop_event.set()
        if self.writer_thread and self.writer_thread.is_alive():
            self.writer_thread.join(timeout=5.0)
        self._flush_all()
        self._close_all_handles()
    
    def add_log_entry(self, file_path: str, content: str, log_level: str = "INFO"):
        """添加日志条目到缓冲区"""
        with self.lock:
            self.buffer.append({
                'file_path': file_path,
                'content': content,
                'level': log_level,
                'timestamp': datetime.now()
            })
            
            # 如果缓冲区满了，强制刷新
            if len(self.buffer) >= self.max_buffer_size:
                self._flush_buffer()
    
    def _write_loop(self):
        """写入循环"""
        while not self.stop_event.is_set():
            time.sleep(self.flush_interval)
            with self.lock:
                if self.buffer:
                    self._flush_buffer()
    
    def _flush_buffer(self):
        """刷新缓冲区"""
        if not self.buffer:
            return
            
        # 按文件路径分组
        file_groups = {}
        while self.buffer:
            entry = self.buffer.popleft()
            file_path = entry['file_path']
            if file_path not in file_groups:
                file_groups[file_path] = []
            file_groups[file_path].append(entry)
        
        # 写入各个文件
        for file_path, entries in file_groups.items():
            self._write_to_file(file_path, entries)
    
    def _write_to_file(self, file_path: str, entries: List[Dict]):
        """写入文件"""
        try:
            # 确保目录存在
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            if file_path.endswith('.html'):
                # HTML文件通过标准logging系统处理，不在这里创建额外的处理器
                # 使用标准logging来记录，让main.py中的HtmlFileHandler处理
                for entry in entries:
                    level = getattr(logging, entry['level'].upper(), logging.INFO)
                    logger = logging.getLogger('enhanced_logger')
                    logger.log(level, entry['content'])
            else:
                # 纯文本文件
                if file_path not in self.file_handles:
                    self.file_handles[file_path] = open(file_path, 'a', encoding='utf-8')
                
                handle = self.file_handles[file_path]
                for entry in entries:
                    timestamp = entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                    handle.write(f"[{timestamp}] {entry['level']}: {entry['content']}\n")
                handle.flush()
            
        except Exception as e:
            print(f"写入日志文件失败 {file_path}: {e}")
    
    def _flush_all(self):
        """刷新所有缓冲区"""
        with self.lock:
            self._flush_buffer()
    
    def _close_all_handles(self):
        """关闭所有文件句柄"""
        for handle in self.file_handles.values():
            try:
                handle.close()
            except:
                pass
        self.file_handles.clear()

class LogFilter:
    """
    日志过滤器
    
    提供多种日志过滤功能，包括级别过滤、关键词过滤、排除模式和模块过滤。
    可以根据不同条件决定是否记录特定的日志消息。
    
    Attributes:
        level_filter (int): 最小日志级别
        keyword_filters (List[str]): 关键词过滤列表
        exclude_patterns (List[str]): 排除模式列表
        module_filters (Dict[str, bool]): 模块过滤字典
        
    Example:
        >>> filter = LogFilter()
        >>> filter.set_level_filter(logging.INFO)
        >>> filter.add_keyword_filter("error")
        >>> filter.add_exclude_pattern("debug")
        >>> if filter.should_log(logging.ERROR, "error occurred", "main"):
        ...     print("记录日志")
    """
    
    def __init__(self):
        """
        初始化日志过滤器
        
        设置默认的过滤条件，包括最小日志级别为INFO。
        """
        self.level_filter = logging.INFO
        self.keyword_filters: List[str] = []
        self.exclude_patterns: List[str] = []
        self.module_filters: Dict[str, bool] = {}
    
    def set_level_filter(self, level: int):
        """
        设置日志级别过滤
        
        Args:
            level (int): 最小日志级别，低于此级别的日志将被过滤
            
        Example:
            >>> filter.set_level_filter(logging.WARNING)  # 只记录WARNING及以上级别
        """
        self.level_filter = level
    
    def add_keyword_filter(self, keyword: str):
        """
        添加关键词过滤
        
        当设置了关键词过滤后，只有包含指定关键词的日志才会被记录。
        
        Args:
            keyword (str): 要过滤的关键词
            
        Example:
            >>> filter.add_keyword_filter("error")
            >>> filter.add_keyword_filter("warning")
        """
        if keyword not in self.keyword_filters:
            self.keyword_filters.append(keyword)
    
    def add_exclude_pattern(self, pattern: str):
        """
        添加排除模式
        
        包含指定模式的日志消息将被排除，不会被记录。
        
        Args:
            pattern (str): 要排除的模式字符串
            
        Example:
            >>> filter.add_exclude_pattern("debug")
            >>> filter.add_exclude_pattern("temp")
        """
        if pattern not in self.exclude_patterns:
            self.exclude_patterns.append(pattern)
    
    def set_module_filter(self, module: str, enabled: bool):
        """
        设置模块过滤
        
        控制特定模块的日志是否被记录。
        
        Args:
            module (str): 模块名称
            enabled (bool): 是否启用该模块的日志记录
            
        Example:
            >>> filter.set_module_filter("database", False)  # 禁用数据库模块日志
            >>> filter.set_module_filter("api", True)        # 启用API模块日志
        """
        self.module_filters[module] = enabled
    
    def should_log(self, level: int, message: str, module: str = "") -> bool:
        """
        判断是否应该记录日志
        
        根据设置的过滤条件判断是否应该记录指定的日志消息。
        
        Args:
            level (int): 日志级别
            message (str): 日志消息内容
            module (str, optional): 模块名称，默认为空
            
        Returns:
            bool: True表示应该记录，False表示应该过滤
            
        Example:
            >>> should_record = filter.should_log(logging.ERROR, "数据库连接失败", "database")
            >>> if should_record:
            ...     logger.error("数据库连接失败")
        """
        # 级别过滤
        if level < self.level_filter:
            return False
        
        # 模块过滤
        if module and module in self.module_filters:
            if not self.module_filters[module]:
                return False
        
        # 排除模式
        for pattern in self.exclude_patterns:
            if pattern in message:
                return False
        
        # 关键词过滤（如果设置了关键词，必须包含其中之一）
        if self.keyword_filters:
            return any(keyword in message for keyword in self.keyword_filters)
        
        return True

class DebugTracker:
    """
    调试追踪器
    
    用于记录函数调用、性能监控、内存使用等调试信息。
    提供全面的应用程序运行时状态追踪功能。
    
    Attributes:
        function_calls (deque): 最近的函数调用记录（最多1000条）
        performance_records (deque): 性能记录（最多500条）
        memory_snapshots (deque): 内存快照（最多100条）
        error_traces (deque): 错误追踪记录（最多200条）
        start_time (float): 追踪器启动时间
        
    Example:
        >>> tracker = DebugTracker()
        >>> tracker.trace_function_call("process_data", "main", (arg1, arg2))
        >>> tracker.record_performance("data_processing", 0.5, 100.0, 120.0)
        >>> snapshot = tracker.take_memory_snapshot("after_processing")
    """
    
    def __init__(self):
        """
        初始化调试追踪器
        
        创建各种追踪记录的队列，设置最大长度以控制内存使用。
        """
        self.function_calls = deque(maxlen=1000)  # 最近1000次函数调用
        self.performance_records = deque(maxlen=500)  # 最近500次性能记录
        self.memory_snapshots = deque(maxlen=100)  # 最近100次内存快照
        self.error_traces = deque(maxlen=200)  # 最近200次错误追踪
        self.start_time = time.time()
    
    def trace_function_call(self, func_name: str, module: str = "", args: tuple = (), kwargs: dict = None):
        """
        追踪函数调用
        
        记录函数调用的详细信息，包括函数名、模块、参数数量等。
        
        Args:
            func_name (str): 函数名称
            module (str, optional): 模块名称，默认为空
            args (tuple, optional): 位置参数，默认为空元组
            kwargs (dict, optional): 关键字参数，默认为None
            
        Example:
            >>> tracker.trace_function_call("calculate_sum", "math_utils", (1, 2, 3))
            >>> tracker.trace_function_call("save_data", "database", kwargs={"table": "users"})
        """
        call_info = {
            'timestamp': time.time(),
            'function': func_name,
            'module': module,
            'args_count': len(args) if args else 0,
            'kwargs_count': len(kwargs) if kwargs else 0,
            'thread_id': threading.current_thread().ident
        }
        self.function_calls.append(call_info)
    
    def record_performance(self, operation: str, duration: float, memory_before: float = None, memory_after: float = None):
        """
        记录性能数据
        
        记录操作的执行时间和内存使用变化。
        
        Args:
            operation (str): 操作名称
            duration (float): 执行时间（秒）
            memory_before (float, optional): 操作前内存使用（MB），默认为None
            memory_after (float, optional): 操作后内存使用（MB），默认为None
            
        Example:
            >>> tracker.record_performance("file_processing", 2.5, 100.0, 150.0)
            >>> tracker.record_performance("api_call", 0.3)
        """
        # 确保内存值是数字类型
        memory_delta = None
        if (memory_before is not None and memory_after is not None and 
            isinstance(memory_before, (int, float)) and isinstance(memory_after, (int, float))):
            memory_delta = memory_after - memory_before
            
        perf_record = {
            'timestamp': time.time(),
            'operation': operation,
            'duration': duration,
            'memory_before': memory_before,
            'memory_after': memory_after,
            'memory_delta': memory_delta
        }
        self.performance_records.append(perf_record)
    
    def take_memory_snapshot(self, label: str = "") -> Dict[str, Any]:
        """
        获取内存快照
        
        获取当前进程的内存使用情况和系统资源状态。
        
        Args:
            label (str, optional): 快照标签，用于标识快照的用途，默认为空
            
        Returns:
            Dict[str, Any]: 包含内存和系统信息的字典，包括：
                - timestamp: 快照时间戳
                - label: 快照标签
                - rss_mb: 物理内存使用（MB）
                - vms_mb: 虚拟内存使用（MB）
                - cpu_percent: CPU使用率
                - num_threads: 线程数量
                - gc_objects: 垃圾回收对象数量
                
        Example:
            >>> snapshot = tracker.take_memory_snapshot("startup")
            >>> print(f"内存使用: {snapshot['rss_mb']:.1f}MB")
            
        Raises:
            Exception: 当无法获取系统信息时，返回包含错误信息的字典
        """
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            # 获取垃圾回收信息
            gc_objects = len(gc.get_objects()) if hasattr(gc, 'get_objects') else 0
            
            snapshot = {
                'timestamp': time.time(),
                'label': label,
                'rss_mb': memory_info.rss / 1024 / 1024,  # 物理内存 MB
                'vms_mb': memory_info.vms / 1024 / 1024,  # 虚拟内存 MB
                'cpu_percent': process.cpu_percent(),
                'num_threads': process.num_threads(),
                'gc_objects': gc_objects
            }
            
            self.memory_snapshots.append(snapshot)
            return snapshot
            
        except Exception as e:
            error_snapshot = {
                'timestamp': time.time(),
                'label': label,
                'error': str(e)
            }
            self.memory_snapshots.append(error_snapshot)
            return error_snapshot
    
    def record_error_trace(self, error: Exception, context: str = ""):
        """
        记录错误追踪
        
        记录异常的详细信息，包括错误类型、消息、上下文和堆栈追踪。
        
        Args:
            error (Exception): 异常对象
            context (str, optional): 错误发生的上下文信息，默认为空
            
        Example:
            >>> try:
            ...     risky_operation()
            ... except ValueError as e:
            ...     tracker.record_error_trace(e, "处理用户输入时")
        """
        error_info = {
            'timestamp': time.time(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context,
            'traceback': traceback.format_exc(),
            'thread_id': threading.current_thread().ident
        }
        self.error_traces.append(error_info)
    
    def get_recent_calls(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的函数调用
        
        返回最近记录的函数调用信息。
        
        Args:
            count (int, optional): 返回的调用记录数量，默认为10
            
        Returns:
            List[Dict[str, Any]]: 最近的函数调用记录列表
            
        Example:
            >>> recent_calls = tracker.get_recent_calls(5)
            >>> for call in recent_calls:
            ...     print(f"{call['module']}.{call['function']}")
        """
        return list(self.function_calls)[-count:] if self.function_calls else []
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        获取性能摘要
        
        分析性能记录并返回统计摘要信息。
        
        Returns:
            Dict[str, Any]: 性能摘要字典，包括：
                - total_operations: 总操作数
                - avg_duration: 平均执行时间
                - max_duration: 最大执行时间
                - min_duration: 最小执行时间
                - slow_operations: 慢操作数量（>0.5秒）
                - avg_memory_delta: 平均内存变化（如果有内存数据）
                - max_memory_delta: 最大内存变化
                - min_memory_delta: 最小内存变化
                
        Example:
            >>> summary = tracker.get_performance_summary()
            >>> print(f"平均执行时间: {summary['avg_duration']:.3f}秒")
            >>> print(f"慢操作数量: {summary['slow_operations']}")
        """
        if not self.performance_records:
            return {
                'total_operations': 0,
                'avg_duration': 0,
                'max_duration': 0,
                'min_duration': 0,
                'slow_operations': 0,
                'avg_memory_delta': 0,
                'max_memory_delta': 0,
                'min_memory_delta': 0
            }
            
        durations = [record['duration'] for record in self.performance_records]
        memory_deltas = [record['memory_delta'] for record in self.performance_records 
                        if record['memory_delta'] is not None]
        
        summary = {
            'total_operations': len(self.performance_records),
            'avg_duration': sum(durations) / len(durations),
            'max_duration': max(durations),
            'min_duration': min(durations),
            'slow_operations': len([d for d in durations if d > 0.5])
        }
        
        if memory_deltas:
            summary.update({
                'avg_memory_delta': sum(memory_deltas) / len(memory_deltas),
                'max_memory_delta': max(memory_deltas),
                'min_memory_delta': min(memory_deltas)
            })
        else:
            summary.update({
                'avg_memory_delta': 0,
                'max_memory_delta': 0,
                'min_memory_delta': 0
            })
            
        return summary
    
class EnhancedLogger:
    """
    增强的日志管理器
    
    提供高级日志功能，包括异步写入, 日志轮转, 过滤, 调试追踪和性能监控。
    支持HTML格式输出, 内存监控, 错误追踪等功能。
    
    Attributes:
        logs_dir (Path): 日志文件目录
        async_writer (AsyncLogWriter): 异步日志写入器
        log_filter (LogFilter): 日志过滤器
        rotation_handlers (Dict[str, LogRotationHandler]): 日志轮转处理器字典
        debug_tracker (DebugTracker): 调试追踪器
        config (Dict[str, Any]): 配置参数
        stats (Dict[str, Any]): 统计信息
        
    Example:
        >>> logger = EnhancedLogger("logs")
        >>> logger.log("INFO", "应用程序启动", "main")
        >>> logger.debug("处理用户请求", "api", {"user_id": 123})
        >>> logger.performance_log("数据处理", 2.5, 100.0, 150.0)
        >>> summary = logger.get_stats()
    """
    
    def __init__(self, logs_dir: str = "logs"):
        """
        初始化增强日志管理器
        
        创建日志目录, 初始化各个组件, 加载配置并启动异步写入器。
        
        Args:
            logs_dir (str, optional): 日志文件目录路径，默认为"logs"
            
        Example:
            >>> logger = EnhancedLogger("app_logs")
            >>> logger = EnhancedLogger()  # 使用默认目录
        """
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)
        
        # 组件初始化
        self.async_writer = AsyncLogWriter()
        self.log_filter = LogFilter()
        # 添加Windows系统错误过滤
        self.log_filter.add_exclude_pattern("UpdateLayeredWindowIndirect failed")
        self.rotation_handlers: Dict[str, LogRotationHandler] = {}
        self.debug_tracker = DebugTracker()  # 新增调试追踪器
        
        # 日志去重缓存
        self.log_deduplication_cache = {}
        self.log_deduplication_count = {}
        self.log_deduplication_timeout = 5  # 默认5秒内相同日志只记录一次
        
        # 配置
        self.config = {
            'max_file_size_mb': 10,
            'max_backup_files': 5,
            'flush_interval': 1.0,
            'buffer_size': 1000,
            'enable_compression': True,
            'enable_async': True,
            'enable_debug_tracking': True,  # 新增调试追踪开关
            'enable_performance_monitoring': True,  # 新增性能监控开关
            'enable_memory_tracking': True,  # 新增内存追踪开关
            'enable_log_deduplication': True,  # 日志去重开关
            'log_deduplication_timeout': 5  # 日志去重超时时间（秒）
        }
        
        # 统计信息
        self.stats = {
            'total_logs': 0,
            'logs_by_level': {'DEBUG': 0, 'INFO': 0, 'WARNING': 0, 'ERROR': 0, 'CRITICAL': 0},
            'logs_by_module': {},
            'start_time': datetime.now(),
            'debug_calls': 0,  # 新增调试调用统计
            'performance_records': 0,  # 新增性能记录统计
            'memory_snapshots': 0  # 新增内存快照统计
        }
        
        self._load_config()
        self.async_writer.start()
        
        # 初始内存快照
        if self.config['enable_memory_tracking']:
            self.debug_tracker.take_memory_snapshot("logger_init")
    
    def _load_config(self):
        """
        加载配置文件
        
        从logger_config.json文件中加载配置参数，如果文件不存在或加载失败，
        则使用默认配置。
        
        Example:
            配置文件格式:
            {
                "max_file_size_mb": 10,
                "max_backup_files": 5,
                "enable_async": true,
                "enable_debug_tracking": true
            }
        """
        config_file = self.logs_dir / "logger_config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
            except Exception as e:
                print(f"加载日志配置失败: {e}")
    
    def save_config(self):
        """
        保存当前配置到文件
        
        将当前的配置参数保存到logger_config.json文件中，
        以便下次启动时加载。
        
        Example:
            >>> logger.config['max_file_size_mb'] = 20
            >>> logger.save_config()  # 保存修改后的配置
        """
        config_file = self.logs_dir / "logger_config.json"
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存日志配置失败: {e}")
    
    def log(self, level: str, message: str, module: str = "", file_name: str = "debug.html"):
        """
        记录日志
        
        根据指定的级别和模块记录日志消息，支持过滤和统计功能。
        
        Args:
            level (str): 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message (str): 日志消息内容
            module (str, optional): 模块名称，默认为空
            file_name (str, optional): 输出文件名，默认为"debug.html"
            
        Example:
            >>> logger.log("INFO", "用户登录成功", "auth", "app.html")
            >>> logger.log("ERROR", "数据库连接失败", "database")
            >>> logger.log("DEBUG", "处理请求开始")
        """
        level_num = getattr(logging, level.upper(), logging.INFO)
        
        # 过滤检查
        if not self.log_filter.should_log(level_num, message, module):
            return
        
        # 日志去重检查
        if self.config.get('enable_log_deduplication', True):
            # 创建日志唯一标识
            log_key = f"{level}:{module}:{message}"
            current_time = time.time()
            dedup_timeout = self.config.get('log_deduplication_timeout', 5)
            
            # 检查是否是重复日志
            if log_key in self.log_deduplication_cache:
                last_time, count = self.log_deduplication_cache[log_key]
                # 如果在去重超时时间内
                if current_time - last_time < dedup_timeout:
                    # 更新计数并跳过此次记录
                    self.log_deduplication_cache[log_key] = (last_time, count + 1)
                    return
                else:
                    # 超时了，记录之前累积的次数
                    if count > 1:
                        # 添加一条汇总日志
                        summary_message = f"上条日志重复出现 {count} 次"
                        if self.config['enable_async']:
                            self.async_writer.add_log_entry(str(self.logs_dir / file_name), summary_message, level)
                        else:
                            self._write_sync(str(self.logs_dir / file_name), summary_message, level)
            
            # 更新或添加到去重缓存
            self.log_deduplication_cache[log_key] = (current_time, 1)
            
            # 清理过期的缓存项
            self._clean_deduplication_cache(current_time)
        
        # 脱敏处理
        try:
            desensitizer = get_log_desensitizer()
            safe_message = desensitizer.desensitize_text(message)
        except Exception:
            # 如果脱敏失败，使用原始消息
            safe_message = message
        
        # 更新统计
        self._update_stats(level, module)
        
        # 构建文件路径
        file_path = str(self.logs_dir / file_name)
        
        # 检查轮转
        self._check_rotation(file_path)
        
        # 写入日志
        if self.config['enable_async']:
            self.async_writer.add_log_entry(file_path, safe_message, level)
        else:
            self._write_sync(file_path, safe_message, level)
    
    def _check_rotation(self, file_path: str):
        """检查并执行日志轮转"""
        if file_path not in self.rotation_handlers:
            self.rotation_handlers[file_path] = LogRotationHandler(
                file_path, 
                self.config['max_file_size_mb'], 
                self.config['max_backup_files']
            )
        
        handler = self.rotation_handlers[file_path]
        if handler.should_rotate():
            handler.rotate()
    
    def _write_sync(self, file_path: str, message: str, level: str):
        """同步写入"""
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            if file_path.endswith('.html'):
                # HTML文件通过标准logging系统处理，不在这里创建额外的处理器
                # 使用根logger来记录，让main.py中的HtmlFileHandler处理
                log_level = getattr(logging, level.upper(), logging.INFO)
                if 'xuanwu_log.html' in file_path:
                    # 使用专门的xuanwu_logger
                    logger = logging.getLogger('xuanwu_log')
                else:
                    # 使用根logger处理debug.html
                    logger = logging.getLogger()
                logger.log(log_level, message)
            else:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write(f'[{timestamp}] {level}: {message}\n')
                    
        except Exception as e:
            print(f"同步写入日志失败: {e}")
    

    
    def _update_stats(self, level: str, module: str):
        """更新统计信息"""
        self.stats['total_logs'] += 1
        
        if level in self.stats['logs_by_level']:
            self.stats['logs_by_level'][level] += 1
        
        if module:
            if module not in self.stats['logs_by_module']:
                self.stats['logs_by_module'][module] = 0
            self.stats['logs_by_module'][module] += 1
            
    def _clean_deduplication_cache(self, current_time):
        """清理过期的日志去重缓存"""
        if len(self.log_deduplication_cache) > 1000:  # 缓存项过多时进行清理
            dedup_timeout = self.config.get('log_deduplication_timeout', 5)
            # 找出过期的缓存项
            expired_keys = [
                key for key, (timestamp, _) in self.log_deduplication_cache.items()
                if current_time - timestamp > dedup_timeout
            ]
            # 删除过期项
            for key in expired_keys:
                del self.log_deduplication_cache[key]
    
    def add_keyword_filter(self, keyword: str):
        """添加关键词过滤"""
        self.log_filter.add_keyword_filter(keyword)
    
    def remove_keyword_filter(self, keyword: str):
        """移除关键词过滤"""
        self.log_filter.remove_keyword_filter(keyword)
    
    def add_exclude_pattern(self, pattern: str):
        """添加排除模式"""
        self.log_filter.add_exclude_pattern(pattern)
    
    def remove_exclude_pattern(self, pattern: str):
        """移除排除模式"""
        self.log_filter.remove_exclude_pattern(pattern)
    
    def set_level_filter(self, min_level: int):
        """设置最小日志级别"""
        self.log_filter.set_level_filter(min_level)
    
    def write_to_html(self, message: str, level: str):
        """写入HTML格式日志"""
        self.log(level, message, file_name="xuanwu_log.html")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        runtime = datetime.now() - self.stats['start_time']
        return {
            **self.stats,
            'runtime_seconds': runtime.total_seconds(),
            'logs_per_second': self.stats['total_logs'] / max(runtime.total_seconds(), 1)
        }
    
    def cleanup_old_logs(self, days: int = 30):
        """清理旧日志"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for file_path in self.logs_dir.rglob("*"):
            if file_path.is_file():
                try:
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_date:
                        file_path.unlink()
                        print(f"已删除旧日志文件: {file_path}")
                except Exception as e:
                    print(f"删除旧日志文件失败 {file_path}: {e}")
    
    def export_logs(self, start_date: Optional[datetime] = None, 
                   end_date: Optional[datetime] = None, 
                   output_format: str = "json") -> str:
        """导出日志"""
        # 这里可以实现日志导出功能
        pass
    
    def debug_function_call(self, func_name: str, module: str = "", args: tuple = (), kwargs: dict = None, context: str = "", **extra_kwargs):
        """记录函数调用调试信息"""
        if not self.config['enable_debug_tracking']:
            return
            
        # 合并kwargs和extra_kwargs
        all_kwargs = kwargs or {}
        if extra_kwargs:
            all_kwargs.update(extra_kwargs)
            
        # 追踪函数调用
        self.debug_tracker.trace_function_call(func_name, module, args, all_kwargs)
        self.stats['debug_calls'] += 1
        
        # 记录调试日志
        debug_msg = f"🔍 函数调用: {module}.{func_name}" if module else f"🔍 函数调用: {func_name}"
        if args or all_kwargs:
            debug_msg += f" | 参数: args={len(args) if args else 0}, kwargs={len(all_kwargs) if all_kwargs else 0}"
        if context:
            debug_msg += f" | 上下文: {context}"
        if extra_kwargs:
            extra_str = ", ".join([f"{k}={v}" for k, v in extra_kwargs.items()])
            debug_msg += f" | 额外参数: {extra_str}"
            
        self.log("DEBUG", debug_msg, module)
    
    def debug_performance(self, operation: str, start_time: float = None, memory_before: float = None, context: str = "", description: str = "", stats: dict = None, **kwargs):
        """记录性能调试信息"""
        if not self.config['enable_performance_monitoring']:
            return
            
        end_time = time.time()
        
        # 处理参数类型问题
        if start_time is None:
            start_time = end_time
        elif isinstance(start_time, str):
            # 如果start_time是字符串，将其作为描述信息处理
            if not description:
                description = start_time
            start_time = end_time
        elif isinstance(start_time, dict):
            # 如果start_time是字典，将其作为stats处理
            if stats is None:
                stats = start_time
            start_time = end_time
        elif not isinstance(start_time, (int, float)):
            # 如果start_time不是数字类型，重置为当前时间
            start_time = end_time
            
        # 确保memory_before是数字类型或None
        if memory_before is not None and not isinstance(memory_before, (int, float)):
            if isinstance(memory_before, str) and not description:
                description = memory_before
            elif isinstance(memory_before, dict) and stats is None:
                stats = memory_before
            memory_before = None
            
        duration = end_time - start_time
        
        # 获取当前内存使用
        memory_after = None
        if memory_before is not None and self.config['enable_memory_tracking']:
            try:
                process = psutil.Process()
                memory_after = process.memory_info().rss / 1024 / 1024
                self.debug_tracker.record_performance(operation, duration, memory_before, memory_after)
                self.stats['performance_records'] += 1
            except Exception:
                pass
        
        # 记录性能日志
        perf_msg = f"⏱️ 性能监控: {operation} | 耗时: {duration*1000:.2f}ms"
        if (memory_before is not None and memory_after is not None and 
            isinstance(memory_before, (int, float)) and isinstance(memory_after, (int, float))):
            memory_delta = memory_after - memory_before
            perf_msg += f" | 内存变化: {memory_delta:+.2f}MB ({memory_before:.1f}→{memory_after:.1f})"
        if context:
            perf_msg += f" | 上下文: {context}"
        if description:
            perf_msg += f" | 描述: {description}"
        if stats:
            stats_str = ", ".join([f"{k}={v}" for k, v in stats.items()])
            perf_msg += f" | 统计: {stats_str}"
            
        # 根据性能情况选择日志级别
        if duration > 1.0:  # 超过1秒
            self.log("WARNING", perf_msg)
        elif duration > 0.5:  # 超过0.5秒
            self.log("INFO", perf_msg)
        else:
            self.log("DEBUG", perf_msg)
    
    def debug_memory_snapshot(self, label: str = "", log_details: bool = True):
        """获取并记录内存快照"""
        if not self.config['enable_memory_tracking']:
            return None
            
        snapshot = self.debug_tracker.take_memory_snapshot(label)
        self.stats['memory_snapshots'] += 1
        
        if log_details and 'error' not in snapshot:
            memory_msg = f"📊 内存快照: {label} | 物理内存: {snapshot['rss_mb']:.1f}MB | 虚拟内存: {snapshot['vms_mb']:.1f}MB | CPU: {snapshot['cpu_percent']:.1f}% | 线程数: {snapshot['num_threads']} | GC对象: {snapshot['gc_objects']}"
            self.log("DEBUG", memory_msg)
        elif 'error' in snapshot:
            self.log("ERROR", f"📊 内存快照失败: {label} | 错误: {snapshot['error']}")
            
        return snapshot
    
    def debug_error(self, error: Exception, context: str = "", include_traceback: bool = True):
        """记录错误调试信息"""
        # 记录错误追踪
        self.debug_tracker.record_error_trace(error, context)
        
        # 构建错误消息
        error_msg = f"❌ 错误追踪: {type(error).__name__}: {str(error)}"
        if context:
            error_msg += f" | 上下文: {context}"
            
        # 添加最近的函数调用信息
        recent_calls = self.debug_tracker.get_recent_calls(3)
        if recent_calls:
            call_info = " | 最近调用: " + " → ".join([f"{call['module']}.{call['function']}" if call['module'] else call['function'] for call in recent_calls[-3:]])
            error_msg += call_info
            
        self.log("ERROR", error_msg)
        
        # 如果需要，记录完整的堆栈追踪
        if include_traceback:
            traceback_msg = f"🔍 堆栈追踪:\n{traceback.format_exc()}"
            self.log("DEBUG", traceback_msg)
    
    def error_with_traceback(self, error: Exception, context: str = ""):
        """记录带有堆栈追踪的错误信息"""
        self.debug_error(error, context, include_traceback=True)
    
    def memory_snapshot(self, label: str = ""):
        """获取内存快照的简化方法"""
        return self.debug_memory_snapshot(label, log_details=True)
    
    def performance_monitor(self, operation_name: str):
        """性能监控上下文管理器"""
        import time
        import psutil
        
        class PerformanceMonitor:
            def __init__(self, logger, operation):
                self.logger = logger
                self.operation = operation
                self.start_time = None
                self.memory_before = None
            
            def __enter__(self):
                self.start_time = time.time()
                if self.logger.config['enable_memory_tracking']:
                    try:
                        process = psutil.Process()
                        self.memory_before = process.memory_info().rss / 1024 / 1024
                    except Exception:
                        pass
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                if self.start_time:
                    self.logger.debug_performance(self.operation, self.start_time, self.memory_before)
        
        return PerformanceMonitor(self, operation_name)
    
    def debug_info(self, message, category=None, **kwargs):
        """调试信息方法"""
        if category:
            full_message = f"[{category}] {message}"
        else:
            full_message = message
        # 过滤掉log方法不支持的参数
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in ['module', 'file_name']}
        self.log("INFO", full_message, **filtered_kwargs)
    
    def info(self, message, module="", **kwargs):
        """记录信息级别日志"""
        # 过滤掉log方法不支持的参数
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in ['file_name']}
        self.log("INFO", message, module=module, **filtered_kwargs)
    
    def error(self, message, module="", **kwargs):
        """记录错误信息"""
        # 过滤掉log方法不支持的参数
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in ['file_name']}
        self.log("ERROR", message, module=module, **filtered_kwargs)
    
    def critical(self, message, module="", **kwargs):
        """记录严重错误信息"""
        # 过滤掉log方法不支持的参数
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in ['file_name']}
        self.log("CRITICAL", message, module=module, **filtered_kwargs)
    
    def debug(self, message, module="", **kwargs):
        """记录调试级别日志"""
        # 过滤掉log方法不支持的参数
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in ['file_name']}
        self.log("DEBUG", message, module=module, **filtered_kwargs)
    
    def debug_system_info(self, message: str = "", extra_info: dict = None):
        """记录系统调试信息
        
        Args:
            message: 自定义消息
            extra_info: 额外信息字典
        """
        try:
            process = psutil.Process()
            
            if message:
                # 如果有自定义消息，记录它和额外信息
                log_msg = f"💻 {message}"
                if extra_info:
                    info_str = ", ".join([f"{k}: {v}" for k, v in extra_info.items()])
                    log_msg += f" | {info_str}"
                self.log("DEBUG", log_msg)
            else:
                # 默认系统信息
                system_msg = f"💻 系统信息: PID={process.pid} | 启动时间={datetime.fromtimestamp(process.create_time()).strftime('%H:%M:%S')} | 工作目录={process.cwd()}"
                self.log("DEBUG", system_msg)
                
                # CPU和内存信息
                cpu_percent = process.cpu_percent()
                memory_info = process.memory_info()
                resource_msg = f"📈 资源使用: CPU={cpu_percent:.1f}% | 内存={memory_info.rss/1024/1024:.1f}MB | 线程数={process.num_threads()}"
                self.log("DEBUG", resource_msg)
            
        except Exception as e:
            self.log("ERROR", f"💻 系统信息获取失败: {e}")
    
    def get_debug_summary(self) -> Dict[str, Any]:
        """获取调试摘要信息"""
        summary = {
            'debug_stats': {
                'total_debug_calls': self.stats['debug_calls'],
                'performance_records': self.stats['performance_records'],
                'memory_snapshots': self.stats['memory_snapshots'],
                'error_traces': len(self.debug_tracker.error_traces)
            },
            'performance_summary': self.debug_tracker.get_performance_summary(),
            'recent_calls': self.debug_tracker.get_recent_calls(5),
            'recent_errors': list(self.debug_tracker.error_traces)[-5:] if self.debug_tracker.error_traces else [],
            'latest_memory_snapshot': list(self.debug_tracker.memory_snapshots)[-1] if self.debug_tracker.memory_snapshots else None
        }
        return summary
    
    def shutdown(self):
        """关闭日志管理器"""
        # 记录关闭前的调试摘要
        if self.config['enable_debug_tracking']:
            summary = self.get_debug_summary()
            self.log("INFO", f"🔧 调试摘要: 函数调用={summary['debug_stats']['total_debug_calls']} | 性能记录={summary['debug_stats']['performance_records']} | 内存快照={summary['debug_stats']['memory_snapshots']} | 错误追踪={summary['debug_stats']['error_traces']}")
            
        self.async_writer.stop()
        
        # 关闭所有HTML处理器
        if hasattr(self, '_html_handlers'):
            for handler in self._html_handlers.values():
                try:
                    handler.close()
                except Exception as e:
                    print(f"关闭HTML处理器失败: {e}")
        
        self.save_config()

# 全局实例
_enhanced_logger = None

def get_enhanced_logger() -> EnhancedLogger:
    """获取全局增强日志管理器实例"""
    global _enhanced_logger
    if _enhanced_logger is None:
        _enhanced_logger = EnhancedLogger()
    return _enhanced_logger

def init_enhanced_logging(logs_dir: str = "logs") -> EnhancedLogger:
    """初始化增强日志系统"""
    global _enhanced_logger
    _enhanced_logger = EnhancedLogger(logs_dir)
    return _enhanced_logger

# 创建全局实例供导入使用
enhanced_logger = get_enhanced_logger()