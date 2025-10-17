# core/thread_pool_manager.py
"""
线程池管理器

该模块提供统一的线程池管理功能，包括：
- 多种类型的线程池（IO密集型、CPU密集型、通用）
- 任务优先级管理
- 线程池监控和统计
- 资源自动清理
- 异常处理和重试机制

作者：XuanWu OCR Team
版本：2.1.7
"""

import threading
import time
import logging
import queue
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass
from enum import Enum
import weakref
from functools import wraps


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class PoolType(Enum):
    """线程池类型"""
    IO_BOUND = "io_bound"      # IO密集型任务
    CPU_BOUND = "cpu_bound"    # CPU密集型任务
    GENERAL = "general"        # 通用任务
    OCR = "ocr"               # OCR专用
    NETWORK = "network"        # 网络请求专用


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    func: Callable
    args: tuple
    kwargs: dict
    priority: TaskPriority
    pool_type: PoolType
    created_at: float
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 0


@dataclass
class PoolStats:
    """线程池统计信息"""
    pool_type: PoolType
    active_threads: int
    pending_tasks: int
    completed_tasks: int
    failed_tasks: int
    average_execution_time: float
    created_at: float


class TaskFuture:
    """任务Future包装器，提供类似concurrent.futures.Future的接口"""
    
    def __init__(self, task_id: str, pool: 'ManagedThreadPool'):
        self.task_id = task_id
        self.pool = pool
        self._result = None
        self._exception = None
        self._done = False
        
    def result(self, timeout: Optional[float] = None) -> Any:
        """获取任务结果"""
        if self._done:
            if self._exception:
                raise self._exception
            return self._result
        
        start_time = time.time()
        
        while not self._done:
            with self.pool._lock:
                # 首先检查任务是否已完成
                if hasattr(self.pool, 'completed_tasks') and self.task_id in self.pool.completed_tasks:
                    result_info = self.pool.completed_tasks[self.task_id]
                    if 'exception' in result_info:
                        self._exception = result_info['exception']
                        self._done = True
                        raise self._exception
                    else:
                        self._result = result_info['result']
                        self._done = True
                        return self._result
                
                # 检查任务是否在活跃任务中
                elif self.task_id in self.pool.active_tasks:
                    future = self.pool.active_tasks[self.task_id]
                    
                    # 检查Future是否已完成
                    if future.done():
                        try:
                            self._result = future.result()
                            self._done = True
                            return self._result
                        except Exception as e:
                            self._exception = e
                            self._done = True
                            raise
            
            # 检查超时
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    raise TimeoutError("任务执行超时")
            
            # 短暂等待后重试
            time.sleep(0.01)
        
        if self._exception:
            raise self._exception
        return self._result
    
    def done(self) -> bool:
        """检查任务是否完成"""
        if self._done:
            return True
            
        with self.pool._lock:
            if self.task_id not in self.pool.active_tasks:
                self._done = True
                return True
        return False
    
    def cancel(self) -> bool:
        """取消任务（如果可能）"""
        with self.pool._lock:
            if self.task_id in self.pool.active_tasks:
                future = self.pool.active_tasks[self.task_id]
                return future.cancel()
        return False


class PriorityQueue:
    """优先级队列"""
    
    def __init__(self):
        self._queues = {
            TaskPriority.URGENT: queue.Queue(),
            TaskPriority.HIGH: queue.Queue(),
            TaskPriority.NORMAL: queue.Queue(),
            TaskPriority.LOW: queue.Queue()
        }
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
    
    def put(self, item: TaskInfo):
        """添加任务"""
        with self._not_empty:
            self._queues[item.priority].put(item)
            self._not_empty.notify()
    
    def get(self, timeout: Optional[float] = None) -> Optional[TaskInfo]:
        """获取任务（按优先级）"""
        with self._not_empty:
            end_time = time.time() + timeout if timeout else None
            
            while True:
                # 按优先级顺序检查队列
                for priority in [TaskPriority.URGENT, TaskPriority.HIGH, 
                               TaskPriority.NORMAL, TaskPriority.LOW]:
                    try:
                        return self._queues[priority].get_nowait()
                    except queue.Empty:
                        continue
                
                # 所有队列都为空，等待
                if timeout is not None:
                    remaining = end_time - time.time()
                    if remaining <= 0:
                        return None
                    self._not_empty.wait(remaining)
                else:
                    self._not_empty.wait()
    
    def qsize(self) -> int:
        """获取队列大小"""
        return sum(q.qsize() for q in self._queues.values())
    
    def empty(self) -> bool:
        """检查队列是否为空"""
        return all(q.empty() for q in self._queues.values())


class ManagedThreadPool:
    """托管线程池"""
    
    def __init__(self, pool_type: PoolType, max_workers: int):
        self.pool_type = pool_type
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers, 
                                         thread_name_prefix=f"{pool_type.value}_pool")
        self.task_queue = PriorityQueue()
        self.active_tasks: Dict[str, Future] = {}
        self.completed_tasks: Dict[str, Dict[str, Any]] = {}  # 存储已完成任务的结果
        self.stats = PoolStats(
            pool_type=pool_type,
            active_threads=0,
            pending_tasks=0,
            completed_tasks=0,
            failed_tasks=0,
            average_execution_time=0.0,
            created_at=time.time()
        )
        self.execution_times: List[float] = []
        self._lock = threading.Lock()
        self._shutdown = False
        
        # 启动任务处理线程
        self._worker_thread = threading.Thread(
            target=self._process_tasks,
            daemon=True,
            name=f"{pool_type.value}_worker"
        )
        self._worker_thread.start()
    
    def submit_task(self, task: TaskInfo) -> str:
        """提交任务"""
        if self._shutdown:
            raise RuntimeError("线程池已关闭")
        
        self.task_queue.put(task)
        with self._lock:
            self.stats.pending_tasks += 1
        
        return task.task_id
    
    def _process_tasks(self):
        """处理任务的工作线程"""
        while not self._shutdown:
            try:
                task = self.task_queue.get(timeout=1.0)
                if task is None:
                    continue
                
                # 检查任务是否超时
                if task.timeout and (time.time() - task.created_at) > task.timeout:
                    with self._lock:
                        self.stats.pending_tasks -= 1
                        self.stats.failed_tasks += 1
                    continue
                
                # 提交任务到线程池
                future = self.executor.submit(self._execute_task, task)
                
                with self._lock:
                    self.active_tasks[task.task_id] = future
                    self.stats.pending_tasks -= 1
                    self.stats.active_threads = len(self.active_tasks)
                
            except Exception as e:
                logging.error(f"任务处理出错: {e}")
    
    def _execute_task(self, task: TaskInfo) -> Any:
        """执行任务"""
        start_time = time.time()
        try:
            result = task.func(*task.args, **task.kwargs)
            
            # 记录执行时间
            execution_time = time.time() - start_time
            with self._lock:
                self.execution_times.append(execution_time)
                if len(self.execution_times) > 100:  # 只保留最近100次
                    self.execution_times.pop(0)
                
                self.stats.completed_tasks += 1
                self.stats.average_execution_time = sum(self.execution_times) / len(self.execution_times)
                
                # 存储完成的任务结果
                self.completed_tasks[task.task_id] = {'result': result}
                
                # 清理完成的任务
                if task.task_id in self.active_tasks:
                    del self.active_tasks[task.task_id]
                self.stats.active_threads = len(self.active_tasks)
                
                # 限制completed_tasks的大小，避免内存泄漏
                if len(self.completed_tasks) > 1000:
                    # 删除最旧的100个任务结果
                    oldest_keys = list(self.completed_tasks.keys())[:100]
                    for key in oldest_keys:
                        del self.completed_tasks[key]
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            with self._lock:
                self.stats.failed_tasks += 1
                
                # 存储异常信息
                if task.retry_count >= task.max_retries:
                    self.completed_tasks[task.task_id] = {'exception': e}
                
                if task.task_id in self.active_tasks:
                    del self.active_tasks[task.task_id]
                self.stats.active_threads = len(self.active_tasks)
            
            # 重试逻辑
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.created_at = time.time()  # 重置创建时间
                self.task_queue.put(task)
                logging.warning(f"任务 {task.task_id} 执行失败，正在重试 ({task.retry_count}/{task.max_retries}): {e}")
            else:
                logging.error(f"任务 {task.task_id} 执行失败: {e}")
                raise
    
    def get_stats(self) -> PoolStats:
        """获取统计信息"""
        with self._lock:
            return PoolStats(
                pool_type=self.stats.pool_type,
                active_threads=self.stats.active_threads,
                pending_tasks=self.stats.pending_tasks,
                completed_tasks=self.stats.completed_tasks,
                failed_tasks=self.stats.failed_tasks,
                average_execution_time=self.stats.average_execution_time,
                created_at=self.stats.created_at
            )
    
    def shutdown(self, wait: bool = True):
        """关闭线程池"""
        self._shutdown = True
        self.executor.shutdown(wait=wait)


class ThreadPoolManager:
    """线程池管理器"""
    
    def __init__(self):
        self.pools: Dict[PoolType, ManagedThreadPool] = {}
        self.logger = logging.getLogger(__name__)
        self._task_counter = 0
        self._lock = threading.Lock()
        
        # 默认线程池配置
        self.default_configs = {
            PoolType.IO_BOUND: 20,      # IO密集型任务可以有更多线程
            PoolType.CPU_BOUND: 4,      # CPU密集型任务线程数接近CPU核心数
            PoolType.GENERAL: 10,       # 通用任务池
            PoolType.OCR: 3,           # OCR任务池（限制并发）
            PoolType.NETWORK: 15       # 网络请求池
        }
        
        self._initialize_pools()
    
    def _initialize_pools(self):
        """初始化线程池"""
        for pool_type, max_workers in self.default_configs.items():
            self.pools[pool_type] = ManagedThreadPool(pool_type, max_workers)
            self.logger.info(f"初始化线程池: {pool_type.value} (最大线程数: {max_workers})")
    
    def submit(self, 
               func: Callable,
               *args,
               pool_type: PoolType = PoolType.GENERAL,
               priority: TaskPriority = TaskPriority.NORMAL,
               timeout: Optional[float] = None,
               max_retries: int = 0,
               **kwargs) -> 'TaskFuture':
        """
        提交任务到线程池
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            pool_type: 线程池类型
            priority: 任务优先级
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
            **kwargs: 函数关键字参数
            
        Returns:
            TaskFuture对象
        """
        with self._lock:
            self._task_counter += 1
            task_id = f"{pool_type.value}_{self._task_counter}_{int(time.time())}"
        
        task = TaskInfo(
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            pool_type=pool_type,
            created_at=time.time(),
            timeout=timeout,
            max_retries=max_retries
        )
        
        if pool_type not in self.pools:
            raise ValueError(f"未知的线程池类型: {pool_type}")
        
        self.pools[pool_type].submit_task(task)
        self.logger.debug(f"任务已提交: {task_id} ({pool_type.value}, {priority.name})")
        
        return TaskFuture(task_id, self.pools[pool_type])
    
    def submit_io_task(self, func: Callable, *args, **kwargs) -> 'TaskFuture':
        """提交IO密集型任务"""
        return self.submit(func, *args, pool_type=PoolType.IO_BOUND, **kwargs)
    
    def submit_cpu_task(self, func: Callable, *args, **kwargs) -> 'TaskFuture':
        """提交CPU密集型任务"""
        return self.submit(func, *args, pool_type=PoolType.CPU_BOUND, **kwargs)
    
    def submit_ocr_task(self, func: Callable, *args, **kwargs) -> 'TaskFuture':
        """提交OCR任务"""
        return self.submit(func, *args, pool_type=PoolType.OCR, **kwargs)
    
    def submit_network_task(self, func: Callable, *args, **kwargs) -> 'TaskFuture':
        """提交网络任务"""
        return self.submit(func, *args, pool_type=PoolType.NETWORK, **kwargs)
    
    def get_pool_stats(self, pool_type: Optional[PoolType] = None) -> Union[PoolStats, Dict[PoolType, PoolStats]]:
        """获取线程池统计信息"""
        if pool_type:
            if pool_type in self.pools:
                return self.pools[pool_type].get_stats()
            else:
                raise ValueError(f"未知的线程池类型: {pool_type}")
        else:
            return {pt: pool.get_stats() for pt, pool in self.pools.items()}
    
    def get_overall_stats(self) -> Dict[str, Any]:
        """获取总体统计信息"""
        all_stats = self.get_pool_stats()
        
        total_active = sum(stats.active_threads for stats in all_stats.values())
        total_pending = sum(stats.pending_tasks for stats in all_stats.values())
        total_completed = sum(stats.completed_tasks for stats in all_stats.values())
        total_failed = sum(stats.failed_tasks for stats in all_stats.values())
        
        avg_execution_times = [stats.average_execution_time for stats in all_stats.values() 
                              if stats.average_execution_time > 0]
        overall_avg_time = sum(avg_execution_times) / len(avg_execution_times) if avg_execution_times else 0
        
        return {
            'total_active_threads': total_active,
            'total_pending_tasks': total_pending,
            'total_completed_tasks': total_completed,
            'total_failed_tasks': total_failed,
            'overall_average_execution_time': overall_avg_time,
            'pool_count': len(self.pools),
            'success_rate': total_completed / (total_completed + total_failed) if (total_completed + total_failed) > 0 else 0
        }
    
    def resize_pool(self, pool_type: PoolType, new_size: int):
        """调整线程池大小"""
        if pool_type in self.pools:
            # 关闭旧的线程池
            old_pool = self.pools[pool_type]
            old_pool.shutdown(wait=False)
            
            # 创建新的线程池
            self.pools[pool_type] = ManagedThreadPool(pool_type, new_size)
            self.logger.info(f"线程池 {pool_type.value} 大小已调整为: {new_size}")
        else:
            raise ValueError(f"未知的线程池类型: {pool_type}")
    
    def shutdown_all(self, wait: bool = True):
        """关闭所有线程池"""
        self.logger.info("正在关闭所有线程池...")
        
        for pool_type, pool in self.pools.items():
            try:
                pool.shutdown(wait=wait)
                self.logger.info(f"线程池 {pool_type.value} 已关闭")
            except Exception as e:
                self.logger.error(f"关闭线程池 {pool_type.value} 时出错: {e}")
        
        self.pools.clear()
        self.logger.info("所有线程池已关闭")


# 全局线程池管理器实例
_thread_pool_manager = None
_manager_lock = threading.Lock()


def get_thread_pool_manager() -> ThreadPoolManager:
    """获取线程池管理器实例（单例模式）"""
    global _thread_pool_manager
    if _thread_pool_manager is None:
        with _manager_lock:
            if _thread_pool_manager is None:
                _thread_pool_manager = ThreadPoolManager()
    return _thread_pool_manager


def async_task(pool_type: PoolType = PoolType.GENERAL, 
               priority: TaskPriority = TaskPriority.NORMAL,
               timeout: Optional[float] = None,
               max_retries: int = 0):
    """
    异步任务装饰器
    
    Args:
        pool_type: 线程池类型
        priority: 任务优先级
        timeout: 超时时间
        max_retries: 最大重试次数
    
    Returns:
        TaskFuture对象
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs) -> TaskFuture:
            manager = get_thread_pool_manager()
            return manager.submit(
                func, *args,
                pool_type=pool_type,
                priority=priority,
                timeout=timeout,
                max_retries=max_retries,
                **kwargs
            )
        return wrapper
    return decorator


# 便捷装饰器
def io_task(priority: TaskPriority = TaskPriority.NORMAL, **kwargs):
    """IO密集型任务装饰器"""
    return async_task(PoolType.IO_BOUND, priority, **kwargs)


def cpu_task(priority: TaskPriority = TaskPriority.NORMAL, **kwargs):
    """CPU密集型任务装饰器"""
    return async_task(PoolType.CPU_BOUND, priority, **kwargs)


def ocr_task(priority: TaskPriority = TaskPriority.NORMAL, **kwargs):
    """OCR任务装饰器"""
    return async_task(PoolType.OCR, priority, **kwargs)


def network_task(priority: TaskPriority = TaskPriority.NORMAL, **kwargs):
    """网络任务装饰器"""
    return async_task(PoolType.NETWORK, priority, **kwargs)