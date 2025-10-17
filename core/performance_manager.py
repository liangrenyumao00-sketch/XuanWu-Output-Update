# performance_manager.py
# 性能数据管理器 - 负责性能数据的收集、存储和分析

"""
性能数据管理模块

该模块提供了完整的系统性能监控和基准测试功能，包括：
- 系统资源使用情况监控（CPU、内存、磁盘、网络）
- 性能数据的持久化存储
- 历史数据分析和趋势预测
- 基准测试套件
- 性能数据的可视化支持

主要类:
    PerformanceManager: 核心性能管理器，提供所有性能相关功能

依赖:
    - sqlite3: 数据持久化
    - psutil: 系统信息收集（可选）
    - threading: 线程安全
    
作者: XuanWu Team
版本: 2.1.7
"""

import json
import os
import time
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

# 使用专用logger，日志将记录到xuanwu_log.html
logger = logging.getLogger('performance_manager')

try:
    import psutil
except ImportError:
    psutil = None

class PerformanceManager:
    """
    性能数据管理器
    
    负责收集、存储和分析系统性能数据的核心类。提供实时性能监控、
    历史数据分析、基准测试等功能。
    
    该类采用SQLite数据库存储性能数据，支持多线程安全访问，
    可以长期运行并定期收集性能指标。
    
    Attributes:
        db_path (str): 数据库文件路径
        lock (threading.Lock): 线程锁，确保数据库操作的线程安全
        
    Example:
        >>> pm = PerformanceManager("performance.db")
        >>> data = pm.collect_current_performance()
        >>> pm.save_performance_data(data)
        >>> trends = pm.get_performance_trends("cpu_percent", hours=24)
    """
    
    def __init__(self, db_path: str = "performance_data.db"):
        """
        初始化性能管理器
        
        Args:
            db_path (str, optional): 数据库文件路径。默认为 "performance_data.db"
            
        Raises:
            Exception: 当数据库初始化失败时抛出异常
        """
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_database()
        
        # 监控相关属性
        self.is_monitoring = False
        self.monitor_thread = None
        self.monitor_interval = 5  # 默认5秒间隔
        
    def _init_database(self):
        """
        初始化SQLite数据库
        
        创建性能数据表和基准测试表，如果表已存在则跳过。
        数据库结构包括：
        - performance_data: 存储实时性能数据
        - benchmark_data: 存储基准测试结果
        
        Raises:
            Exception: 当数据库创建失败时记录错误日志
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建性能数据表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS performance_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        cpu_percent REAL,
                        cpu_user REAL,
                        cpu_system REAL,
                        cpu_idle REAL,
                        memory_percent REAL,
                        memory_used_gb REAL,
                        memory_total_gb REAL,
                        disk_percent REAL,
                        disk_used_gb REAL,
                        disk_total_gb REAL,
                        network_sent_mb REAL,
                        network_recv_mb REAL,
                        process_memory_mb REAL,
                        process_cpu_percent REAL,
                        thread_count INTEGER,
                        data_json TEXT
                    )
                """)
                
                # 创建基准测试表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS benchmark_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        test_name TEXT NOT NULL,
                        score REAL,
                        details_json TEXT
                    )
                """)
                
                conn.commit()
                
        except Exception as e:
            logging.error(f"初始化性能数据库失败: {e}")
    
    def collect_current_performance(self) -> Dict[str, Any]:
        """
        收集当前系统性能数据
        
        收集包括CPU、内存、磁盘、网络等系统资源的实时使用情况。
        如果psutil库不可用，将返回默认值（全部为0）。
        
        Returns:
            Dict[str, Any]: 包含以下键值的性能数据字典：
                - timestamp (str): ISO格式的时间戳
                - cpu_percent (float): CPU使用率百分比
                - cpu_user (float): 用户态CPU使用率
                - cpu_system (float): 系统态CPU使用率
                - cpu_idle (float): CPU空闲率
                - memory_percent (float): 内存使用率百分比
                - memory_used_gb (float): 已使用内存（GB）
                - memory_total_gb (float): 总内存（GB）
                - disk_percent (float): 磁盘使用率百分比
                - disk_used_gb (float): 已使用磁盘空间（GB）
                - disk_total_gb (float): 总磁盘空间（GB）
                - network_sent_mb (float): 网络发送数据（MB）
                - network_recv_mb (float): 网络接收数据（MB）
                - process_memory_mb (float): 当前进程内存使用（MB）
                - process_cpu_percent (float): 当前进程CPU使用率
                - thread_count (int): 当前进程线程数
                
        Example:
            >>> pm = PerformanceManager()
            >>> data = pm.collect_current_performance()
            >>> print(f"CPU使用率: {data['cpu_percent']}%")
        """
        data = {
            'timestamp': datetime.now().isoformat(),
            'cpu_percent': 0,
            'cpu_user': 0,
            'cpu_system': 0,
            'cpu_idle': 0,
            'memory_percent': 0,
            'memory_used_gb': 0,
            'memory_total_gb': 0,
            'disk_percent': 0,
            'disk_used_gb': 0,
            'disk_total_gb': 0,
            'network_sent_mb': 0,
            'network_recv_mb': 0,
            'process_memory_mb': 0,
            'process_cpu_percent': 0,
            'thread_count': 0
        }
        
        if psutil:
            try:
                # CPU信息
                cpu_times = psutil.cpu_times_percent(interval=0.1)
                data['cpu_percent'] = psutil.cpu_percent(interval=0.1)
                data['cpu_user'] = cpu_times.user
                data['cpu_system'] = cpu_times.system
                data['cpu_idle'] = cpu_times.idle
                
                # 内存信息
                vm = psutil.virtual_memory()
                data['memory_percent'] = vm.percent
                data['memory_used_gb'] = vm.used / (1024**3)
                data['memory_total_gb'] = vm.total / (1024**3)
                
                # 磁盘信息
                try:
                    disk = psutil.disk_usage('/')
                    data['disk_percent'] = (disk.used / disk.total) * 100
                    data['disk_used_gb'] = disk.used / (1024**3)
                    data['disk_total_gb'] = disk.total / (1024**3)
                except (AttributeError, OSError):
                    pass
                
                # 网络信息
                try:
                    net_io = psutil.net_io_counters()
                    data['network_sent_mb'] = net_io.bytes_sent / (1024**2)
                    data['network_recv_mb'] = net_io.bytes_recv / (1024**2)
                except (AttributeError, OSError):
                    pass
                
                # 进程信息
                try:
                    proc = psutil.Process()
                    mem_info = proc.memory_info()
                    data['process_memory_mb'] = mem_info.rss / (1024**2)
                    data['process_cpu_percent'] = proc.cpu_percent()
                    data['thread_count'] = proc.num_threads()
                except (AttributeError, OSError, psutil.NoSuchProcess):
                    pass
                    
            except Exception as e:
                logging.error(f"收集性能数据失败: {e}")
        
        return data
    
    def save_performance_data(self, data: Dict[str, Any]) -> bool:
        """
        保存性能数据到SQLite数据库
        
        将性能数据以线程安全的方式保存到数据库中。数据会同时以结构化字段
        和JSON格式存储，便于查询和分析。
        
        Args:
            data (Dict[str, Any]): 由collect_current_performance()返回的性能数据
            
        Returns:
            bool: 保存成功返回True，失败返回False
            
        Raises:
            Exception: 数据库操作失败时记录错误日志
            
        Example:
            >>> pm = PerformanceManager()
            >>> data = pm.collect_current_performance()
            >>> success = pm.save_performance_data(data)
            >>> if success:
            ...     print("性能数据保存成功")
        """
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO performance_data (
                            timestamp, cpu_percent, cpu_user, cpu_system, cpu_idle,
                            memory_percent, memory_used_gb, memory_total_gb,
                            disk_percent, disk_used_gb, disk_total_gb,
                            network_sent_mb, network_recv_mb,
                            process_memory_mb, process_cpu_percent, thread_count,
                            data_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        data['timestamp'],
                        data['cpu_percent'],
                        data['cpu_user'],
                        data['cpu_system'],
                        data['cpu_idle'],
                        data['memory_percent'],
                        data['memory_used_gb'],
                        data['memory_total_gb'],
                        data['disk_percent'],
                        data['disk_used_gb'],
                        data['disk_total_gb'],
                        data['network_sent_mb'],
                        data['network_recv_mb'],
                        data['process_memory_mb'],
                        data['process_cpu_percent'],
                        data['thread_count'],
                        json.dumps(data)
                    ))
                    
                    conn.commit()
                    return True
                    
        except Exception as e:
            logging.error(f"保存性能数据失败: {e}")
            return False
    
    def get_historical_data(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        获取指定时间范围内的历史性能数据
        
        从数据库中检索指定小时数内的所有性能记录，按时间升序排列。
        
        Args:
            hours (int, optional): 要检索的小时数，默认为24小时
            
        Returns:
            List[Dict[str, Any]]: 性能数据记录列表，每个记录包含所有性能指标
            
        Raises:
            Exception: 数据库查询失败时记录错误日志并返回空列表
            
        Example:
            >>> pm = PerformanceManager()
            >>> data = pm.get_historical_data(hours=12)
            >>> print(f"获取到 {len(data)} 条历史记录")
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 计算时间范围
                end_time = datetime.now()
                start_time = end_time - timedelta(hours=hours)
                
                cursor.execute("""
                    SELECT * FROM performance_data 
                    WHERE timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp ASC
                """, (start_time.isoformat(), end_time.isoformat()))
                
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logging.error(f"获取历史数据失败: {e}")
            return []
    
    def get_performance_trends(self, metric: str, hours: int = 24) -> Dict[str, Any]:
        """
        分析指定性能指标的趋势
        
        对指定的性能指标进行统计分析，包括平均值、最值、趋势方向等。
        
        Args:
            metric (str): 要分析的性能指标名称，如 'cpu_percent', 'memory_percent'
            hours (int, optional): 分析的时间范围（小时），默认为24小时
            
        Returns:
            Dict[str, Any]: 趋势分析结果，包含以下键值：
                - metric (str): 指标名称
                - count (int): 数据点数量
                - average (float): 平均值
                - min (float): 最小值
                - max (float): 最大值
                - current (float): 最新值
                - trend (str): 趋势方向 ('increasing', 'decreasing', 'stable')
                
        Returns:
            Dict: 如果数据不足或指标不存在，返回空字典
            
        Example:
            >>> pm = PerformanceManager()
            >>> trends = pm.get_performance_trends("cpu_percent", hours=6)
            >>> print(f"CPU趋势: {trends.get('trend', 'unknown')}")
        """
        data = self.get_historical_data(hours)
        
        if not data or metric not in data[0]:
            return {}
        
        values = [row[metric] for row in data if row[metric] is not None]
        
        if not values:
            return {}
        
        return {
            'metric': metric,
            'count': len(values),
            # 防止除零错误
            'average': sum(values) / len(values) if len(values) > 0 else 0.0,
            'min': min(values),
            'max': max(values),
            'current': values[-1] if values else 0,
            'trend': 'increasing' if len(values) > 1 and values[-1] > values[0] else 'decreasing' if len(values) > 1 and values[-1] < values[0] else 'stable'
        }
    
    def run_benchmark_test(self, test_name: str) -> Dict[str, Any]:
        """
        运行指定的基准测试
        
        执行系统性能基准测试并保存结果。支持CPU、内存、磁盘和综合测试。
        
        Args:
            test_name (str): 测试类型，支持以下值：
                - 'cpu_benchmark': CPU性能测试
                - 'memory_benchmark': 内存性能测试
                - 'disk_benchmark': 磁盘I/O性能测试
                - 'comprehensive': 综合性能测试
                
        Returns:
            Dict[str, Any]: 测试结果，包含以下键值：
                - test_name (str): 测试名称
                - timestamp (str): 测试时间戳
                - score (float): 性能分数（越高越好）
                - details (Dict): 详细测试数据
                - error (str, optional): 错误信息（如果测试失败）
                
        Example:
            >>> pm = PerformanceManager()
            >>> result = pm.run_benchmark_test("cpu_benchmark")
            >>> print(f"CPU性能分数: {result['score']:.2f}")
        """
        results = {
            'test_name': test_name,
            'timestamp': datetime.now().isoformat(),
            'score': 0,
            'details': {}
        }
        
        try:
            if test_name == 'cpu_benchmark':
                results.update(self._cpu_benchmark())
            elif test_name == 'memory_benchmark':
                results.update(self._memory_benchmark())
            elif test_name == 'disk_benchmark':
                results.update(self._disk_benchmark())
            elif test_name == 'comprehensive':
                results.update(self._comprehensive_benchmark())
                
        except Exception as e:
            logging.error(f"基准测试失败: {e}")
            results['error'] = str(e)
        
        # 保存基准测试结果
        self._save_benchmark_result(results)
        
        return results
    
    def _cpu_benchmark(self) -> Dict[str, Any]:
        """
        CPU基准测试
        
        执行CPU密集型计算任务来测试CPU性能。通过大量数学运算
        来评估CPU的计算能力。
        
        Returns:
            Dict[str, Any]: CPU测试结果，包含：
                - score (float): CPU性能分数（基于执行时间计算）
                - details (Dict): 详细信息
                    - duration_seconds (float): 测试耗时（秒）
                    - operations_per_second (float): 每秒操作数
                    
        Note:
            分数计算公式：1000 / 执行时间（秒）
            执行100万次平方运算作为基准负载
        """
        start_time = time.time()
        
        # 简单的CPU密集型计算
        result = 0
        for i in range(1000000):
            result += i * i
        
        duration = time.time() - start_time
        score = 1000 / duration  # 分数越高越好
        
        return {
            'score': score,
            'details': {
                'duration_seconds': duration,
                'operations_per_second': 1000000 / duration
            }
        }
    
    def _memory_benchmark(self) -> Dict[str, Any]:
        """
        内存基准测试
        
        测试内存分配和访问性能。创建大量数据结构并进行访问操作
        来评估内存子系统的性能。
        
        Returns:
            Dict[str, Any]: 内存测试结果，包含：
                - score (float): 内存性能分数
                - details (Dict): 详细信息
                    - duration_seconds (float): 测试耗时（秒）
                    - memory_operations_per_second (float): 每秒内存操作数
                    - total_sum (int): 计算结果总和（用于验证）
                    
        Note:
            测试包括分配10万个包含100个元素的列表，然后遍历求和
        """
        start_time = time.time()
        
        # 内存分配和访问测试
        data = []
        for i in range(100000):
            data.append([j for j in range(100)])
        
        # 访问测试
        total = 0
        for sublist in data:
            total += sum(sublist)
        
        duration = time.time() - start_time
        score = 1000 / duration
        
        return {
            'score': score,
            'details': {
                'duration_seconds': duration,
                'memory_operations_per_second': 100000 / duration,
                'total_sum': total
            }
        }
    
    def _disk_benchmark(self) -> Dict[str, Any]:
        """
        磁盘I/O基准测试
        
        测试磁盘读写性能。创建临时文件进行写入和读取操作
        来评估存储子系统的性能。
        
        Returns:
            Dict[str, Any]: 磁盘测试结果，包含：
                - score (float): 磁盘性能分数（MB/s）
                - details (Dict): 详细信息
                    - duration_seconds (float): 测试耗时（秒）
                    - throughput_mb_per_second (float): 吞吐量（MB/s）
                    - data_size_mb (int): 测试数据大小（MB）
                    
        Note:
            测试写入10MB数据（10个1MB块），然后读取全部数据
            测试完成后自动清理临时文件
        """
        import tempfile
        
        start_time = time.time()
        
        # 写入测试
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_data = b'0' * 1024 * 1024  # 1MB
            for _ in range(10):
                f.write(test_data)
            temp_file = f.name
        
        # 读取测试
        with open(temp_file, 'rb') as f:
            data = f.read()
        
        # 清理
        os.unlink(temp_file)
        
        duration = time.time() - start_time
        score = 100 / duration  # MB/s
        
        return {
            'score': score,
            'details': {
                'duration_seconds': duration,
                'throughput_mb_per_second': 10 / duration,
                'data_size_mb': 10
            }
        }
    
    def _comprehensive_benchmark(self) -> Dict[str, Any]:
        """
        综合基准测试
        
        依次执行CPU、内存和磁盘测试，计算综合性能分数。
        提供系统整体性能的评估。
        
        Returns:
            Dict[str, Any]: 综合测试结果，包含：
                - score (float): 综合性能分数（三项测试的平均值）
                - details (Dict): 详细信息
                    - cpu_score (float): CPU测试分数
                    - memory_score (float): 内存测试分数
                    - disk_score (float): 磁盘测试分数
                    - cpu_details (Dict): CPU测试详细信息
                    - memory_details (Dict): 内存测试详细信息
                    - disk_details (Dict): 磁盘测试详细信息
                    
        Note:
            综合分数 = (CPU分数 + 内存分数 + 磁盘分数) / 3
        """
        cpu_result = self._cpu_benchmark()
        memory_result = self._memory_benchmark()
        disk_result = self._disk_benchmark()
        
        # 计算综合分数
        total_score = (cpu_result['score'] + memory_result['score'] + disk_result['score']) / 3
        
        return {
            'score': total_score,
            'details': {
                'cpu_score': cpu_result['score'],
                'memory_score': memory_result['score'],
                'disk_score': disk_result['score'],
                'cpu_details': cpu_result['details'],
                'memory_details': memory_result['details'],
                'disk_details': disk_result['details']
            }
        }
    
    def _save_benchmark_result(self, result: Dict[str, Any]):
        """
        保存基准测试结果到数据库
        
        将基准测试结果以线程安全的方式保存到benchmark_data表中。
        
        Args:
            result (Dict[str, Any]): 基准测试结果数据
            
        Raises:
            Exception: 数据库操作失败时记录错误日志
            
        Note:
            这是一个私有方法，由run_benchmark_test()自动调用
        """
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO benchmark_data (timestamp, test_name, score, details_json)
                        VALUES (?, ?, ?, ?)
                    """, (
                        result['timestamp'],
                        result['test_name'],
                        result['score'],
                        json.dumps(result['details'])
                    ))
                    
                    conn.commit()
                    
        except Exception as e:
            logging.error(f"保存基准测试结果失败: {e}")
    
    def get_benchmark_history(self, test_name: Optional[str] = None, days: int = 30) -> List[Dict[str, Any]]:
        """
        获取基准测试历史记录
        
        从数据库中检索指定时间范围内的基准测试结果，支持按测试类型过滤。
        
        Args:
            test_name (Optional[str], optional): 测试类型过滤器，None表示获取所有类型
            days (int, optional): 要检索的天数，默认为30天
            
        Returns:
            List[Dict[str, Any]]: 基准测试记录列表，按时间降序排列
            
        Raises:
            Exception: 数据库查询失败时记录错误日志并返回空列表
            
        Example:
            >>> pm = PerformanceManager()
            >>> # 获取所有测试记录
            >>> all_tests = pm.get_benchmark_history()
            >>> # 获取CPU测试记录
            >>> cpu_tests = pm.get_benchmark_history("cpu_benchmark", days=7)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                end_time = datetime.now()
                start_time = end_time - timedelta(days=days)
                
                if test_name:
                    cursor.execute("""
                        SELECT * FROM benchmark_data 
                        WHERE test_name = ? AND timestamp >= ? AND timestamp <= ?
                        ORDER BY timestamp DESC
                    """, (test_name, start_time.isoformat(), end_time.isoformat()))
                else:
                    cursor.execute("""
                        SELECT * FROM benchmark_data 
                        WHERE timestamp >= ? AND timestamp <= ?
                        ORDER BY timestamp DESC
                    """, (start_time.isoformat(), end_time.isoformat()))
                
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logging.error(f"获取基准测试历史失败: {e}")
            return []
    
    def cleanup_old_data(self, days: int = 30):
        """
        清理过期的性能数据
        
        删除指定天数之前的性能数据和基准测试记录，以控制数据库大小。
        
        Args:
            days (int, optional): 保留数据的天数，默认为30天
            
        Raises:
            Exception: 数据库操作失败时记录错误日志
            
        Note:
            建议定期调用此方法以避免数据库文件过大
            
        Example:
            >>> pm = PerformanceManager()
            >>> pm.cleanup_old_data(days=7)  # 只保留最近7天的数据
        """
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cutoff_time = (datetime.now() - timedelta(days=days)).isoformat()
                    
                    cursor.execute("DELETE FROM performance_data WHERE timestamp < ?", (cutoff_time,))
                    cursor.execute("DELETE FROM benchmark_data WHERE timestamp < ?", (cutoff_time,))
                    
                    conn.commit()
                    
        except Exception as e:
            logging.error(f"清理旧数据失败: {e}")
    
    def start_monitoring(self, interval: int = 5):
        """
        开始性能监控
        
        启动后台线程定期收集和保存性能数据。
        
        Args:
            interval (int, optional): 监控间隔（秒），默认为5秒
            
        Note:
            如果监控已经在运行，此方法不会重复启动
        """
        if self.is_monitoring:
            logger.warning("性能监控已在运行中")
            return
            
        self.monitor_interval = interval
        self.is_monitoring = True
        
        def monitor_loop():
            """监控循环"""
            while self.is_monitoring:
                try:
                    # 收集性能数据
                    data = self.collect_current_performance()
                    # 保存到数据库
                    self.save_performance_data(data)
                    
                    # 等待指定间隔
                    time.sleep(self.monitor_interval)
                    
                except Exception as e:
                    logger.error(f"性能监控循环出错: {e}")
                    time.sleep(1)  # 出错时短暂等待
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"性能监控已启动，间隔: {interval}秒")
    
    def stop_monitoring(self):
        """
        停止性能监控
        
        停止后台监控线程并清理资源。
        """
        if not self.is_monitoring:
            logger.warning("性能监控未在运行")
            return
            
        self.is_monitoring = False
        
        # 等待监控线程结束
        if self.monitor_thread and self.monitor_thread.is_alive():
            try:
                # 尝试在短时间内等待线程结束，避免退出阶段被 Ctrl+C 打断
                self.monitor_thread.join(timeout=2)
            except KeyboardInterrupt:
                # 在退出清理阶段，如果用户触发了中断，直接跳过等待
                logger.warning("停止性能监控等待被中断，跳过等待直接退出")
            except Exception as e:
                # 不中断退出流程，记录调试信息
                logger.debug(f"停止性能监控join异常: {e}")
            finally:
                # 如果线程仍然存活（守护线程），让其随进程一同退出
                if self.monitor_thread.is_alive():
                    logger.debug("监控线程未在超时内结束，作为守护线程随进程退出")
        
        self.monitor_thread = None
        logger.info("性能监控已停止")