# core/performance_monitor.py
"""
性能监控和内存管理优化系统

该模块提供全面的性能监控功能：
- CPU和内存使用监控
- 函数执行时间分析
- 内存泄漏检测
- 性能瓶颈识别
- 资源使用优化
- 性能报告生成
- 实时性能警报

作者：XuanWu OCR Team
版本：2.1.7
"""

import time
import threading
import psutil
import gc
import sys
import tracemalloc
import weakref
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from functools import wraps
import json
from pathlib import Path
import statistics

from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.enhanced_logger import get_enhanced_logger


@dataclass
class PerformanceMetrics:
    """性能指标"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used: int  # bytes
    memory_available: int  # bytes
    disk_io_read: int  # bytes
    disk_io_write: int  # bytes
    network_sent: int  # bytes
    network_recv: int  # bytes
    thread_count: int
    process_count: int
    gpu_usage: Optional[float] = None
    gpu_memory: Optional[int] = None


@dataclass
class FunctionMetrics:
    """函数性能指标"""
    name: str
    module: str
    call_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    last_call_time: float = 0.0
    memory_usage: List[int] = field(default_factory=list)
    error_count: int = 0


@dataclass
class MemorySnapshot:
    """内存快照"""
    timestamp: float
    total_memory: int
    available_memory: int
    used_memory: int
    memory_percent: float
    swap_total: int
    swap_used: int
    swap_percent: float
    gc_stats: Dict[str, Any]
    top_objects: List[Tuple[str, int]]  # (type_name, count)


class MemoryTracker:
    """内存跟踪器"""
    
    def __init__(self, max_snapshots: int = 100):
        self.max_snapshots = max_snapshots
        self.snapshots = deque(maxlen=max_snapshots)
        self.object_refs = weakref.WeakSet()
        self.logger = get_enhanced_logger()
        
        # 启用内存跟踪
        if not tracemalloc.is_tracing():
            tracemalloc.start()
    
    def take_snapshot(self) -> MemorySnapshot:
        """拍摄内存快照"""
        try:
            # 获取系统内存信息
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # 获取GC统计信息
            gc_stats = {
                'collections': gc.get_stats(),
                'count': gc.get_count(),
                'threshold': gc.get_threshold()
            }
            
            # 获取对象统计
            top_objects = self._get_top_objects()
            
            snapshot = MemorySnapshot(
                timestamp=time.time(),
                total_memory=memory.total,
                available_memory=memory.available,
                used_memory=memory.used,
                memory_percent=memory.percent,
                swap_total=swap.total,
                swap_used=swap.used,
                swap_percent=swap.percent,
                gc_stats=gc_stats,
                top_objects=top_objects
            )
            
            self.snapshots.append(snapshot)
            return snapshot
            
        except Exception as e:
            self.logger.error(f"拍摄内存快照失败：{e}")
            return None
    
    def _get_top_objects(self, limit: int = 10) -> List[Tuple[str, int]]:
        """获取占用内存最多的对象类型"""
        try:
            # 统计对象类型
            type_counts = defaultdict(int)
            for obj in gc.get_objects():
                type_name = type(obj).__name__
                type_counts[type_name] += 1
            
            # 排序并返回前N个
            sorted_types = sorted(type_counts.items(), 
                                key=lambda x: x[1], reverse=True)
            return sorted_types[:limit]
            
        except Exception as e:
            self.logger.error(f"获取对象统计失败：{e}")
            return []
    
    def detect_memory_leaks(self, threshold: float = 10.0) -> List[str]:
        """检测内存泄漏"""
        leaks = []
        
        try:
            if len(self.snapshots) < 2:
                return leaks
            
            # 比较最近的快照
            recent = list(self.snapshots)[-5:]  # 最近5个快照
            if len(recent) < 2:
                return leaks
            
            # 计算内存增长趋势
            memory_usage = [s.used_memory for s in recent]
            if len(memory_usage) >= 3:
                # 计算增长率
                growth_rates = []
                for i in range(1, len(memory_usage)):
                    if memory_usage[i-1] > 0:
                        growth_rate = ((memory_usage[i] - memory_usage[i-1]) / 
                                     memory_usage[i-1]) * 100
                        growth_rates.append(growth_rate)
                
                if growth_rates:
                    avg_growth = statistics.mean(growth_rates)
                    if avg_growth > threshold:
                        leaks.append(f"内存持续增长，平均增长率：{avg_growth:.2f}%")
            
            # 检查对象数量异常增长
            if len(recent) >= 2:
                old_objects = dict(recent[0].top_objects)
                new_objects = dict(recent[-1].top_objects)
                
                for obj_type, new_count in new_objects.items():
                    old_count = old_objects.get(obj_type, 0)
                    if old_count > 0:
                        growth = ((new_count - old_count) / old_count) * 100
                        if growth > threshold * 2:  # 对象增长阈值更高
                            leaks.append(f"对象类型 {obj_type} 数量异常增长：{growth:.2f}%")
            
        except Exception as e:
            self.logger.error(f"内存泄漏检测失败：{e}")
        
        return leaks
    
    def get_memory_trend(self, duration: int = 300) -> Dict[str, Any]:
        """获取内存使用趋势"""
        try:
            current_time = time.time()
            recent_snapshots = [
                s for s in self.snapshots 
                if current_time - s.timestamp <= duration
            ]
            
            if not recent_snapshots:
                return {}
            
            memory_usage = [s.used_memory for s in recent_snapshots]
            memory_percent = [s.memory_percent for s in recent_snapshots]
            
            return {
                'duration': duration,
                'snapshot_count': len(recent_snapshots),
                'memory_usage': {
                    'min': min(memory_usage),
                    'max': max(memory_usage),
                    'avg': statistics.mean(memory_usage),
                    'current': memory_usage[-1] if memory_usage else 0
                },
                'memory_percent': {
                    'min': min(memory_percent),
                    'max': max(memory_percent),
                    'avg': statistics.mean(memory_percent),
                    'current': memory_percent[-1] if memory_percent else 0
                },
                'trend': 'increasing' if len(memory_usage) >= 2 and memory_usage[-1] > memory_usage[0] else 'stable'
            }
            
        except Exception as e:
            self.logger.error(f"获取内存趋势失败：{e}")
            return {}


class FunctionProfiler:
    """函数性能分析器"""
    
    def __init__(self):
        self.metrics = {}
        self.lock = threading.Lock()
        self.logger = get_enhanced_logger()
    
    def profile_function(self, func_name: str, module: str, 
                        execution_time: float, memory_before: int, 
                        memory_after: int, error: bool = False):
        """记录函数性能数据"""
        with self.lock:
            key = f"{module}.{func_name}"
            
            if key not in self.metrics:
                self.metrics[key] = FunctionMetrics(
                    name=func_name,
                    module=module
                )
            
            metric = self.metrics[key]
            metric.call_count += 1
            metric.total_time += execution_time
            metric.min_time = min(metric.min_time, execution_time)
            metric.max_time = max(metric.max_time, execution_time)
            metric.avg_time = metric.total_time / metric.call_count
            metric.last_call_time = time.time()
            
            # 记录内存使用
            memory_diff = memory_after - memory_before
            metric.memory_usage.append(memory_diff)
            
            # 限制内存使用记录数量
            if len(metric.memory_usage) > 100:
                metric.memory_usage = metric.memory_usage[-100:]
            
            if error:
                metric.error_count += 1
    
    def get_function_stats(self, func_name: Optional[str] = None) -> Dict[str, Any]:
        """获取函数统计信息"""
        with self.lock:
            if func_name:
                return self.metrics.get(func_name, {})
            
            # 返回所有函数的统计信息
            stats = {}
            for key, metric in self.metrics.items():
                stats[key] = {
                    'call_count': metric.call_count,
                    'total_time': metric.total_time,
                    'avg_time': metric.avg_time,
                    'min_time': metric.min_time,
                    'max_time': metric.max_time,
                    'error_count': metric.error_count,
                    'avg_memory_usage': statistics.mean(metric.memory_usage) if metric.memory_usage else 0
                }
            
            return stats
    
    def get_slowest_functions(self, limit: int = 10) -> List[Tuple[str, float]]:
        """获取最慢的函数"""
        with self.lock:
            sorted_functions = sorted(
                self.metrics.items(),
                key=lambda x: x[1].avg_time,
                reverse=True
            )
            
            return [(name, metric.avg_time) for name, metric in sorted_functions[:limit]]
    
    def get_most_called_functions(self, limit: int = 10) -> List[Tuple[str, int]]:
        """获取调用次数最多的函数"""
        with self.lock:
            sorted_functions = sorted(
                self.metrics.items(),
                key=lambda x: x[1].call_count,
                reverse=True
            )
            
            return [(name, metric.call_count) for name, metric in sorted_functions[:limit]]


class PerformanceMonitor(QObject):
    """性能监控器"""
    
    # 信号
    performance_alert = pyqtSignal(str, dict)  # 性能警报
    memory_warning = pyqtSignal(float)  # 内存警告
    
    def __init__(self, 
                 monitor_interval: int = 5,  # 监控间隔（秒）
                 max_metrics: int = 1000,    # 最大指标数量
                 memory_threshold: float = 80.0,  # 内存警告阈值（%）
                 cpu_threshold: float = 90.0):    # CPU警告阈值（%）
        
        super().__init__()
        
        self.monitor_interval = monitor_interval
        self.max_metrics = max_metrics
        self.memory_threshold = memory_threshold
        self.cpu_threshold = cpu_threshold
        
        self.logger = get_enhanced_logger()
        self.is_monitoring = False
        
        # 性能指标存储
        self.metrics = deque(maxlen=max_metrics)
        self.metrics_lock = threading.Lock()
        
        # 组件初始化
        self.memory_tracker = MemoryTracker()
        self.function_profiler = FunctionProfiler()
        
        # 监控定时器
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._collect_metrics)
        
        # 进程信息
        self.process = psutil.Process()
        self.initial_memory = self.process.memory_info().rss
        
        self.logger.info("性能监控器初始化完成")
    
    def start_monitoring(self):
        """开始监控"""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.monitor_timer.start(self.monitor_interval * 1000)
            self.logger.info("性能监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        if self.is_monitoring:
            self.is_monitoring = False
            self.monitor_timer.stop()
            self.logger.info("性能监控已停止")
    
    def _collect_metrics(self):
        """收集性能指标"""
        try:
            # 获取系统指标
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk_io = psutil.disk_io_counters()
            network_io = psutil.net_io_counters()
            
            # 获取进程信息
            process_info = self.process.as_dict([
                'num_threads', 'memory_info'
            ])
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used=memory.used,
                memory_available=memory.available,
                disk_io_read=disk_io.read_bytes if disk_io else 0,
                disk_io_write=disk_io.write_bytes if disk_io else 0,
                network_sent=network_io.bytes_sent if network_io else 0,
                network_recv=network_io.bytes_recv if network_io else 0,
                thread_count=process_info.get('num_threads', 0),
                process_count=len(psutil.pids())
            )
            
            # 尝试获取GPU信息（如果可用）
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]  # 使用第一个GPU
                    metrics.gpu_usage = gpu.load * 100
                    metrics.gpu_memory = gpu.memoryUsed
            except ImportError:
                pass  # GPU监控不可用
            
            # 存储指标
            with self.metrics_lock:
                self.metrics.append(metrics)
            
            # 检查警告条件
            self._check_performance_alerts(metrics)
            
            # 拍摄内存快照
            self.memory_tracker.take_snapshot()
            
        except Exception as e:
            self.logger.error(f"收集性能指标失败：{e}")
    
    def _check_performance_alerts(self, metrics: PerformanceMetrics):
        """检查性能警报"""
        try:
            # 内存警告
            if metrics.memory_percent > self.memory_threshold:
                self.memory_warning.emit(metrics.memory_percent)
                self.performance_alert.emit(
                    "memory_high",
                    {
                        'memory_percent': metrics.memory_percent,
                        'threshold': self.memory_threshold,
                        'timestamp': metrics.timestamp
                    }
                )
            
            # CPU警告
            if metrics.cpu_percent > self.cpu_threshold:
                self.performance_alert.emit(
                    "cpu_high",
                    {
                        'cpu_percent': metrics.cpu_percent,
                        'threshold': self.cpu_threshold,
                        'timestamp': metrics.timestamp
                    }
                )
            
            # 检查内存泄漏
            leaks = self.memory_tracker.detect_memory_leaks()
            if leaks:
                self.performance_alert.emit(
                    "memory_leak",
                    {
                        'leaks': leaks,
                        'timestamp': metrics.timestamp
                    }
                )
            
        except Exception as e:
            self.logger.error(f"检查性能警报失败：{e}")
    
    def get_current_metrics(self) -> Optional[PerformanceMetrics]:
        """获取当前性能指标"""
        with self.metrics_lock:
            return self.metrics[-1] if self.metrics else None
    
    def get_metrics_history(self, duration: int = 300) -> List[PerformanceMetrics]:
        """获取指定时间段的性能历史"""
        current_time = time.time()
        with self.metrics_lock:
            return [
                m for m in self.metrics
                if current_time - m.timestamp <= duration
            ]
    
    def get_performance_summary(self, duration: int = 300) -> Dict[str, Any]:
        """获取性能摘要"""
        try:
            history = self.get_metrics_history(duration)
            if not history:
                return {}
            
            cpu_values = [m.cpu_percent for m in history]
            memory_values = [m.memory_percent for m in history]
            
            return {
                'duration': duration,
                'sample_count': len(history),
                'cpu': {
                    'min': min(cpu_values),
                    'max': max(cpu_values),
                    'avg': statistics.mean(cpu_values),
                    'current': cpu_values[-1]
                },
                'memory': {
                    'min': min(memory_values),
                    'max': max(memory_values),
                    'avg': statistics.mean(memory_values),
                    'current': memory_values[-1]
                },
                'memory_trend': self.memory_tracker.get_memory_trend(duration),
                'function_stats': self.function_profiler.get_function_stats(),
                'slowest_functions': self.function_profiler.get_slowest_functions(),
                'most_called_functions': self.function_profiler.get_most_called_functions()
            }
            
        except Exception as e:
            self.logger.error(f"获取性能摘要失败：{e}")
            return {}
    
    def optimize_memory(self):
        """内存优化"""
        try:
            self.logger.info("开始内存优化")
            
            # 强制垃圾回收
            collected = gc.collect()
            self.logger.info(f"垃圾回收释放了 {collected} 个对象")
            
            # 清理缓存（如果有缓存管理器）
            try:
                from core.cache_manager import get_cache_manager
                cache_manager = get_cache_manager()
                result = cache_manager.cleanup_expired()
                self.logger.info(f"已清理过期缓存: {result['total_cleaned']} 个项目")
            except ImportError:
                pass
            
            # 优化Qt应用
            app = QApplication.instance()
            if app:
                app.processEvents()
            
            self.logger.info("内存优化完成")
            
        except Exception as e:
            self.logger.error(f"内存优化失败：{e}")
    
    def export_performance_report(self, file_path: str, 
                                 duration: int = 3600) -> bool:
        """导出性能报告"""
        try:
            report_data = {
                'export_time': time.time(),
                'duration': duration,
                'summary': self.get_performance_summary(duration),
                'metrics_history': [
                    {
                        'timestamp': m.timestamp,
                        'cpu_percent': m.cpu_percent,
                        'memory_percent': m.memory_percent,
                        'memory_used': m.memory_used,
                        'thread_count': m.thread_count
                    }
                    for m in self.get_metrics_history(duration)
                ],
                'memory_snapshots': [
                    {
                        'timestamp': s.timestamp,
                        'memory_percent': s.memory_percent,
                        'used_memory': s.used_memory,
                        'top_objects': s.top_objects[:5]  # 只保存前5个
                    }
                    for s in list(self.memory_tracker.snapshots)[-50:]  # 最近50个快照
                ]
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"性能报告导出成功：{file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"导出性能报告失败：{e}")
            return False


# 全局性能监控器实例
_performance_monitor = None
_monitor_lock = threading.Lock()


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    global _performance_monitor
    
    if _performance_monitor is None:
        with _monitor_lock:
            if _performance_monitor is None:
                _performance_monitor = PerformanceMonitor()
    
    return _performance_monitor


# 性能分析装饰器
def profile_performance(category: str = "general"):
    """性能分析装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            
            # 记录开始时间和内存
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss
            
            error_occurred = False
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error_occurred = True
                raise
            finally:
                # 记录结束时间和内存
                end_time = time.time()
                end_memory = psutil.Process().memory_info().rss
                execution_time = end_time - start_time
                
                # 记录性能数据
                monitor.function_profiler.profile_function(
                    func_name=func.__name__,
                    module=func.__module__ or "unknown",
                    execution_time=execution_time,
                    memory_before=start_memory,
                    memory_after=end_memory,
                    error=error_occurred
                )
        
        return wrapper
    return decorator


# 内存使用上下文管理器
class memory_monitor:
    """内存监控上下文管理器"""
    
    def __init__(self, name: str = "operation"):
        self.name = name
        self.start_memory = 0
        self.logger = get_enhanced_logger()
    
    def __enter__(self):
        self.start_memory = psutil.Process().memory_info().rss
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_memory = psutil.Process().memory_info().rss
        memory_diff = end_memory - self.start_memory
        
        if memory_diff > 0:
            self.logger.info(f"{self.name} 内存使用增加：{memory_diff / 1024 / 1024:.2f} MB")
        else:
            self.logger.info(f"{self.name} 内存使用减少：{abs(memory_diff) / 1024 / 1024:.2f} MB")


# 便捷函数
def start_performance_monitoring():
    """启动性能监控"""
    get_performance_monitor().start_monitoring()


def stop_performance_monitoring():
    """停止性能监控"""
    get_performance_monitor().stop_monitoring()


def get_current_performance() -> Optional[PerformanceMetrics]:
    """获取当前性能指标"""
    return get_performance_monitor().get_current_metrics()


def optimize_memory():
    """优化内存使用"""
    get_performance_monitor().optimize_memory()


def export_performance_report(file_path: str) -> bool:
    """导出性能报告"""
    return get_performance_monitor().export_performance_report(file_path)