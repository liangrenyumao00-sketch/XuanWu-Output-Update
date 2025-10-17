# core/cache_manager.py
"""
统一缓存管理器

该模块提供统一的缓存管理功能：
- 内存缓存（LRU策略）
- 磁盘缓存（持久化）
- 缓存过期管理
- 缓存统计和监控
- 多级缓存支持
- 缓存预热和清理

作者：XuanWu OCR Team
版本：2.1.7
"""

import os
import json
import pickle
import time
import threading
import hashlib
from typing import Any, Dict, Optional, Union, List, Callable
from collections import OrderedDict
from dataclasses import dataclass, asdict
from pathlib import Path

from core.enhanced_logger import get_enhanced_logger


@dataclass
class CacheItem:
    """缓存项"""
    key: str
    value: Any
    created_at: float
    accessed_at: float
    expires_at: Optional[float] = None
    access_count: int = 0
    size: int = 0
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def update_access(self):
        """更新访问信息"""
        self.accessed_at = time.time()
        self.access_count += 1


class LRUCache:
    """LRU内存缓存"""
    
    def __init__(self, max_size: int = 1000, max_memory: int = 100 * 1024 * 1024):  # 100MB
        self.max_size = max_size
        self.max_memory = max_memory
        self.cache = OrderedDict()
        self.current_memory = 0
        self.lock = threading.RLock()
        self.logger = get_enhanced_logger()
    
    def get(self, key: str) -> Optional[CacheItem]:
        """获取缓存项"""
        with self.lock:
            if key not in self.cache:
                return None
            
            item = self.cache[key]
            
            # 检查过期
            if item.is_expired():
                self._remove_item(key)
                return None
            
            # 更新访问信息并移到末尾（最近使用）
            item.update_access()
            self.cache.move_to_end(key)
            
            return item
    
    def put(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """添加缓存项"""
        with self.lock:
            try:
                # 计算大小
                size = self._calculate_size(value)
                
                # 检查是否超过单个项目大小限制
                if size > self.max_memory:
                    self.logger.warning(f"缓存项过大，无法存储: {key}, 大小: {size}")
                    return False
                
                # 如果已存在，先删除
                if key in self.cache:
                    self._remove_item(key)
                
                # 确保有足够空间
                while (len(self.cache) >= self.max_size or 
                       self.current_memory + size > self.max_memory):
                    if not self.cache:
                        break
                    self._remove_oldest()
                
                # 创建缓存项
                expires_at = time.time() + ttl if ttl else None
                item = CacheItem(
                    key=key,
                    value=value,
                    created_at=time.time(),
                    accessed_at=time.time(),
                    expires_at=expires_at,
                    size=size
                )
                
                # 添加到缓存
                self.cache[key] = item
                self.current_memory += size
                
                return True
                
            except Exception as e:
                self.logger.error(f"添加缓存项失败: {key}, 错误: {e}")
                return False
    
    def remove(self, key: str) -> bool:
        """删除缓存项"""
        with self.lock:
            if key in self.cache:
                self._remove_item(key)
                return True
            return False
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.current_memory = 0
    
    def cleanup_expired(self) -> int:
        """清理过期项"""
        with self.lock:
            expired_keys = []
            for key, item in self.cache.items():
                if item.is_expired():
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._remove_item(key)
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self.lock:
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'memory_usage': self.current_memory,
                'max_memory': self.max_memory,
                'memory_usage_percent': (self.current_memory / self.max_memory) * 100,
                'items': [
                    {
                        'key': item.key,
                        'size': item.size,
                        'created_at': item.created_at,
                        'accessed_at': item.accessed_at,
                        'access_count': item.access_count,
                        'expires_at': item.expires_at
                    }
                    for item in self.cache.values()
                ]
            }
    
    def _remove_item(self, key: str):
        """删除缓存项"""
        if key in self.cache:
            item = self.cache.pop(key)
            self.current_memory -= item.size
    
    def _remove_oldest(self):
        """删除最旧的项"""
        if self.cache:
            key = next(iter(self.cache))
            self._remove_item(key)
    
    def _calculate_size(self, value: Any) -> int:
        """计算对象大小"""
        try:
            if isinstance(value, (str, bytes)):
                return len(value)
            elif isinstance(value, (int, float, bool)):
                return 8
            elif isinstance(value, (list, tuple)):
                return sum(self._calculate_size(item) for item in value)
            elif isinstance(value, dict):
                return sum(self._calculate_size(k) + self._calculate_size(v) 
                          for k, v in value.items())
            else:
                # 使用pickle估算大小
                return len(pickle.dumps(value))
        except Exception:
            return 1024  # 默认1KB


class DiskCache:
    """磁盘缓存"""
    
    def __init__(self, cache_dir: str, max_size: int = 1000):
        self.cache_dir = Path(cache_dir)
        self.max_size = max_size
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.cache_dir / "cache_index.json"
        self.lock = threading.RLock()
        self.logger = get_enhanced_logger()
        
        # 加载索引
        self.index = self._load_index()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存项"""
        with self.lock:
            if key not in self.index:
                return None
            
            item_info = self.index[key]
            
            # 检查过期
            if item_info.get('expires_at') and time.time() > item_info['expires_at']:
                self._remove_item(key)
                return None
            
            # 读取文件
            file_path = self.cache_dir / item_info['filename']
            if not file_path.exists():
                self._remove_item(key)
                return None
            
            try:
                with open(file_path, 'rb') as f:
                    value = pickle.load(f)
                
                # 更新访问信息
                item_info['accessed_at'] = time.time()
                item_info['access_count'] = item_info.get('access_count', 0) + 1
                self._save_index()
                
                return value
                
            except Exception as e:
                self.logger.error(f"读取缓存文件失败: {key}, 错误: {e}")
                self._remove_item(key)
                return None
    
    def put(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """添加缓存项"""
        with self.lock:
            try:
                # 生成文件名
                filename = self._generate_filename(key)
                file_path = self.cache_dir / filename
                
                # 如果已存在，先删除
                if key in self.index:
                    self._remove_item(key)
                
                # 确保有足够空间
                while len(self.index) >= self.max_size:
                    if not self.index:
                        break
                    self._remove_oldest()
                
                # 写入文件
                with open(file_path, 'wb') as f:
                    pickle.dump(value, f)
                
                # 更新索引
                expires_at = time.time() + ttl if ttl else None
                self.index[key] = {
                    'filename': filename,
                    'created_at': time.time(),
                    'accessed_at': time.time(),
                    'expires_at': expires_at,
                    'access_count': 0,
                    'size': file_path.stat().st_size
                }
                
                self._save_index()
                return True
                
            except Exception as e:
                self.logger.error(f"写入缓存文件失败: {key}, 错误: {e}")
                return False
    
    def remove(self, key: str) -> bool:
        """删除缓存项"""
        with self.lock:
            if key in self.index:
                self._remove_item(key)
                return True
            return False
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            for key in list(self.index.keys()):
                self._remove_item(key)
    
    def cleanup_expired(self) -> int:
        """清理过期项"""
        with self.lock:
            expired_keys = []
            current_time = time.time()
            
            for key, item_info in self.index.items():
                if (item_info.get('expires_at') and 
                    current_time > item_info['expires_at']):
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._remove_item(key)
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self.lock:
            total_size = sum(item.get('size', 0) for item in self.index.values())
            return {
                'size': len(self.index),
                'max_size': self.max_size,
                'total_disk_size': total_size,
                'cache_dir': str(self.cache_dir),
                'items': list(self.index.values())
            }
    
    def _load_index(self) -> Dict[str, Any]:
        """加载索引"""
        try:
            if self.index_file.exists():
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"加载缓存索引失败: {e}")
        
        return {}
    
    def _save_index(self):
        """保存索引"""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存缓存索引失败: {e}")
    
    def _remove_item(self, key: str):
        """删除缓存项"""
        if key in self.index:
            item_info = self.index.pop(key)
            file_path = self.cache_dir / item_info['filename']
            
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                self.logger.error(f"删除缓存文件失败: {file_path}, 错误: {e}")
            
            self._save_index()
    
    def _remove_oldest(self):
        """删除最旧的项"""
        if self.index:
            # 按访问时间排序，删除最旧的
            oldest_key = min(self.index.keys(), 
                           key=lambda k: self.index[k].get('accessed_at', 0))
            self._remove_item(oldest_key)
    
    def _generate_filename(self, key: str) -> str:
        """生成文件名"""
        hash_obj = hashlib.md5(key.encode('utf-8'))
        return f"cache_{hash_obj.hexdigest()}.pkl"


class CacheManager:
    """统一缓存管理器"""
    
    def __init__(self, 
                 memory_cache_size: int = 1000,
                 memory_cache_memory: int = 100 * 1024 * 1024,  # 100MB
                 disk_cache_size: int = 10000,
                 cache_dir: str = "cache"):
        
        self.logger = get_enhanced_logger()
        
        # 初始化缓存
        self.memory_cache = LRUCache(memory_cache_size, memory_cache_memory)
        self.disk_cache = DiskCache(cache_dir, disk_cache_size)
        
        # 统计信息
        self.stats = {
            'memory_hits': 0,
            'disk_hits': 0,
            'misses': 0,
            'puts': 0,
            'removes': 0
        }
        
        # 清理定时器
        self.cleanup_timer = None
        self._start_cleanup_timer()
        
        self.logger.info("缓存管理器初始化完成")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值"""
        try:
            # 先查内存缓存
            item = self.memory_cache.get(key)
            if item is not None:
                self.stats['memory_hits'] += 1
                return item.value
            
            # 再查磁盘缓存
            value = self.disk_cache.get(key)
            if value is not None:
                self.stats['disk_hits'] += 1
                # 将热点数据提升到内存缓存
                self.memory_cache.put(key, value)
                return value
            
            # 缓存未命中
            self.stats['misses'] += 1
            return default
            
        except Exception as e:
            self.logger.error(f"获取缓存失败: {key}, 错误: {e}")
            return default
    
    def put(self, key: str, value: Any, ttl: Optional[int] = None, 
            memory_only: bool = False, disk_only: bool = False) -> bool:
        """设置缓存值"""
        try:
            success = True
            
            if not disk_only:
                # 存储到内存缓存
                if not self.memory_cache.put(key, value, ttl):
                    success = False
            
            if not memory_only:
                # 存储到磁盘缓存
                if not self.disk_cache.put(key, value, ttl):
                    success = False
            
            if success:
                self.stats['puts'] += 1
            
            return success
            
        except Exception as e:
            self.logger.error(f"设置缓存失败: {key}, 错误: {e}")
            return False
    
    def remove(self, key: str) -> bool:
        """删除缓存"""
        try:
            memory_removed = self.memory_cache.remove(key)
            disk_removed = self.disk_cache.remove(key)
            
            if memory_removed or disk_removed:
                self.stats['removes'] += 1
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"删除缓存失败: {key}, 错误: {e}")
            return False
    
    def clear(self, memory_only: bool = False, disk_only: bool = False):
        """清空缓存"""
        try:
            if not disk_only:
                self.memory_cache.clear()
            
            if not memory_only:
                self.disk_cache.clear()
            
            self.logger.info("缓存已清空")
            
        except Exception as e:
            self.logger.error(f"清空缓存失败: {e}")
    
    def cleanup_expired(self) -> Dict[str, int]:
        """清理过期缓存"""
        try:
            memory_cleaned = self.memory_cache.cleanup_expired()
            disk_cleaned = self.disk_cache.cleanup_expired()
            
            result = {
                'memory_cleaned': memory_cleaned,
                'disk_cleaned': disk_cleaned,
                'total_cleaned': memory_cleaned + disk_cleaned
            }
            
            if result['total_cleaned'] > 0:
                self.logger.info(f"清理过期缓存: {result}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"清理过期缓存失败: {e}")
            return {'memory_cleaned': 0, 'disk_cleaned': 0, 'total_cleaned': 0}
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        try:
            memory_stats = self.memory_cache.get_stats()
            disk_stats = self.disk_cache.get_stats()
            
            total_hits = self.stats['memory_hits'] + self.stats['disk_hits']
            total_requests = total_hits + self.stats['misses']
            hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'hit_rate': hit_rate,
                'memory_hit_rate': (self.stats['memory_hits'] / total_requests * 100) if total_requests > 0 else 0,
                'disk_hit_rate': (self.stats['disk_hits'] / total_requests * 100) if total_requests > 0 else 0,
                'total_requests': total_requests,
                'memory_hits': self.stats['memory_hits'],
                'disk_hits': self.stats['disk_hits'],
                'misses': self.stats['misses'],
                'puts': self.stats['puts'],
                'removes': self.stats['removes'],
                'memory_cache': memory_stats,
                'disk_cache': disk_stats
            }
            
        except Exception as e:
            self.logger.error(f"获取缓存统计失败: {e}")
            return {}
    
    def cache_decorator(self, key_func: Optional[Callable] = None, 
                       ttl: Optional[int] = None,
                       memory_only: bool = False,
                       disk_only: bool = False):
        """缓存装饰器"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                # 生成缓存键
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
                
                # 尝试从缓存获取
                result = self.get(cache_key)
                if result is not None:
                    return result
                
                # 执行函数并缓存结果
                result = func(*args, **kwargs)
                self.put(cache_key, result, ttl, memory_only, disk_only)
                
                return result
            
            return wrapper
        return decorator
    
    def _start_cleanup_timer(self):
        """启动清理定时器"""
        def cleanup_task():
            self.cleanup_expired()
            # 重新设置定时器
            self.cleanup_timer = threading.Timer(300, cleanup_task)  # 5分钟
            self.cleanup_timer.daemon = True
            self.cleanup_timer.start()
        
        self.cleanup_timer = threading.Timer(300, cleanup_task)
        self.cleanup_timer.daemon = True
        self.cleanup_timer.start()
    
    def shutdown(self):
        """关闭缓存管理器"""
        try:
            if self.cleanup_timer:
                self.cleanup_timer.cancel()
            
            # 最后一次清理
            self.cleanup_expired()
            
            self.logger.info("缓存管理器已关闭")
            
        except Exception as e:
            self.logger.error(f"关闭缓存管理器失败: {e}")


# 全局缓存管理器实例
_cache_manager = None
_cache_manager_lock = threading.Lock()


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例"""
    global _cache_manager
    
    if _cache_manager is None:
        with _cache_manager_lock:
            if _cache_manager is None:
                _cache_manager = CacheManager()
    
    return _cache_manager


def cache(key_func: Optional[Callable] = None, 
          ttl: Optional[int] = None,
          memory_only: bool = False,
          disk_only: bool = False):
    """缓存装饰器"""
    return get_cache_manager().cache_decorator(key_func, ttl, memory_only, disk_only)


# 便捷函数
def get_cache(key: str, default: Any = None) -> Any:
    """获取缓存"""
    return get_cache_manager().get(key, default)


def set_cache(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """设置缓存"""
    return get_cache_manager().put(key, value, ttl)


def remove_cache(key: str) -> bool:
    """删除缓存"""
    return get_cache_manager().remove(key)


def clear_cache():
    """清空缓存"""
    get_cache_manager().clear()


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计"""
    return get_cache_manager().get_stats()