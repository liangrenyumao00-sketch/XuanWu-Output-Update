# 性能调优指南

本指南将帮助您优化 XuanWu OCR 的性能，提升识别效率和系统响应速度。

## 🎯 性能优化概览

### 优化目标
- **提升识别速度**: 减少OCR识别延迟
- **降低资源消耗**: 减少CPU、内存使用
- **提高稳定性**: 避免程序卡顿和崩溃
- **优化用户体验**: 提升界面响应速度

### 性能指标
- **识别延迟**: < 2秒（从截图到识别完成）
- **CPU使用率**: < 30%（正常监控状态）
- **内存使用**: < 200MB（基础运行）
- **成功率**: > 95%（正常网络环境）

## ⚙️ 系统级优化

### 识别参数优化

#### 识别间隔设置
```
推荐设置：
- 实时监控: 1-2秒
- 普通监控: 3-5秒  
- 低频监控: 10-30秒
- 避免设置: < 0.5秒（资源消耗过大）
```

#### 区域大小优化
```
性能建议：
- 最佳区域: 200x100 到 800x400 像素
- 避免过大: > 1920x1080 像素
- 避免过小: < 100x50 像素
- 长宽比: 建议 2:1 到 4:1
```

#### 图像预处理优化
```json
{
  "图像缩放": {
    "最大宽度": 2048,
    "最大高度": 2048,
    "保持比例": true,
    "缩放算法": "高质量"
  },
  "图像增强": {
    "对比度增强": true,
    "亮度调整": "自动",
    "噪声去除": true,
    "边缘锐化": false
  }
}
```

### 缓存策略优化

#### 智能缓存配置
```json
{
  "缓存策略": {
    "启用缓存": true,
    "缓存大小": "100MB",
    "缓存算法": "LRU",
    "相似度阈值": 0.95,
    "清理策略": "自动清理"
  }
}
```

#### 缓存优化建议
1. **合理设置缓存大小**: 根据可用内存设置
2. **启用相似度检测**: 避免重复识别相似图像
3. **定期清理**: 设置自动清理过期缓存
4. **压缩存储**: 使用图像压缩减少存储空间

### 多线程优化

#### 线程池配置
```json
{
  "线程池设置": {
    "核心线程数": 2,
    "最大线程数": 4,
    "队列大小": 100,
    "线程空闲时间": 60,
    "任务超时": 30
  }
}
```

#### 并发控制
- **API并发**: 限制同时进行的API调用数
- **图像处理**: 并行处理多个图像
- **数据库操作**: 异步数据库读写
- **网络请求**: 使用连接池管理网络连接

## 🔧 网络优化

### API调用优化

#### 请求优化
```json
{
  "API优化": {
    "连接超时": 10,
    "读取超时": 30,
    "重试次数": 3,
    "重试间隔": 1,
    "并发限制": 5
  }
}
```

#### 多引擎负载均衡
```json
{
  "负载均衡": {
    "轮询算法": "加权轮询",
    "健康检查": true,
    "故障转移": true,
    "权重配置": {
      "百度OCR": 0.6,
      "腾讯OCR": 0.3,
      "阿里OCR": 0.1
    }
  }
}
```

### 网络连接优化

#### 连接池配置
```json
{
  "连接池": {
    "最大连接数": 10,
    "连接超时": 5,
    "保持连接": true,
    "复用连接": true
  }
}
```

#### 代理优化
- **使用代理**: 在企业网络环境中配置代理
- **连接复用**: 启用HTTP连接复用
- **压缩传输**: 启用gzip压缩减少传输量
- **DNS缓存**: 启用DNS缓存减少解析时间

## 💾 内存优化

### 内存管理策略

#### 内存使用监控
```json
{
  "内存管理": {
    "最大内存": "512MB",
    "垃圾回收": "自动",
    "内存监控": true,
    "内存告警": "400MB"
  }
}
```

#### 内存优化技巧
1. **及时释放**: 及时释放不再使用的对象
2. **对象复用**: 复用对象减少创建开销
3. **延迟加载**: 按需加载数据和资源
4. **内存映射**: 对大文件使用内存映射

### 数据结构优化

#### 高效数据结构
```python
# 使用高效的数据结构
from collections import deque
from typing import Dict, Set

# 关键词匹配使用集合
keywords: Set[str] = set()

# 历史记录使用双端队列
history: deque = deque(maxlen=1000)

# 缓存使用LRU字典
from functools import lru_cache

@lru_cache(maxsize=128)
def process_image(image_hash: str):
    pass
```

## 🗄️ 数据库优化

### SQLite优化配置

#### 数据库参数
```sql
-- 启用WAL模式提升并发性能
PRAGMA journal_mode=WAL;

-- 设置缓存大小
PRAGMA cache_size=10000;

-- 启用内存映射
PRAGMA mmap_size=268435456;

-- 设置同步模式
PRAGMA synchronous=NORMAL;

-- 启用外键约束
PRAGMA foreign_keys=ON;
```

#### 索引优化
```sql
-- 为常用查询创建索引
CREATE INDEX idx_timestamp ON history(created_at);
CREATE INDEX idx_keyword ON history(keyword);
CREATE INDEX idx_status ON history(status);

-- 复合索引
CREATE INDEX idx_timestamp_keyword ON history(created_at, keyword);
```

### 查询优化

#### 高效查询
```python
# 使用LIMIT限制结果集
def get_recent_history(limit=100):
    return db.execute(
        "SELECT * FROM history ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()

# 使用预编译语句
def get_keyword_stats():
    stmt = db.prepare("SELECT keyword, COUNT(*) FROM history GROUP BY keyword")
    return stmt.fetchall()
```

## 🎨 界面性能优化

### UI渲染优化

#### 控件优化
```python
# 使用虚拟列表减少内存使用
from PyQt6.QtWidgets import QListView

class VirtualListWidget(QListView):
    def __init__(self):
        super().__init__()
        self.setUniformItemSizes(True)  # 统一项目大小
        self.setViewMode(QListView.ViewMode.ListMode)
```

#### 布局优化
- **延迟布局**: 使用延迟布局减少计算开销
- **缓存渲染**: 缓存复杂控件的渲染结果
- **减少重绘**: 避免不必要的界面重绘
- **异步更新**: 使用异步方式更新界面

### 数据处理优化

#### 大数据处理
```python
# 分页加载大数据集
def load_history_page(page=0, page_size=100):
    offset = page * page_size
    return db.execute(
        "SELECT * FROM history ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (page_size, offset)
    ).fetchall()

# 流式处理大文件
def process_large_file(filename):
    with open(filename, 'r') as f:
        for line in f:
            yield process_line(line)
```

## 📊 性能监控

### 监控指标

#### 系统指标
```python
import psutil

def get_system_metrics():
    return {
        "CPU使用率": psutil.cpu_percent(),
        "内存使用率": psutil.virtual_memory().percent,
        "磁盘使用率": psutil.disk_usage('/').percent,
        "网络IO": psutil.net_io_counters()
    }
```

#### 应用指标
```python
def get_app_metrics():
    return {
        "识别次数": get_recognition_count(),
        "平均延迟": get_average_latency(),
        "成功率": get_success_rate(),
        "缓存命中率": get_cache_hit_rate()
    }
```

### 性能分析工具

#### 内存分析
```python
import tracemalloc

# 启用内存跟踪
tracemalloc.start()

# 获取内存快照
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

# 显示内存使用情况
for stat in top_stats[:10]:
    print(stat)
```

#### 性能分析
```python
import cProfile
import pstats

# 性能分析
profiler = cProfile.Profile()
profiler.enable()

# 运行代码
your_function()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats()
```

## 🔍 性能测试

### 基准测试

#### 识别性能测试
```python
import time

def benchmark_recognition():
    start_time = time.time()
    
    # 执行识别任务
    result = perform_recognition()
    
    end_time = time.time()
    latency = end_time - start_time
    
    return {
        "延迟": latency,
        "结果": result,
        "时间戳": start_time
    }
```

#### 压力测试
```python
import threading
import concurrent.futures

def stress_test(num_threads=10, duration=60):
    def worker():
        start_time = time.time()
        while time.time() - start_time < duration:
            benchmark_recognition()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker) for _ in range(num_threads)]
        concurrent.futures.wait(futures)
```

### 性能基准

#### 目标性能指标
```
识别性能：
- 单次识别延迟: < 2秒
- 批量识别延迟: < 5秒/100张
- 并发识别能力: 10个/秒

资源使用：
- CPU使用率: < 30%
- 内存使用: < 200MB
- 磁盘IO: < 10MB/s

稳定性：
- 连续运行时间: > 24小时
- 错误率: < 1%
- 内存泄漏: 无
```

## 🛠️ 优化工具

### 配置工具

#### 性能配置向导
```python
def performance_wizard():
    """性能配置向导"""
    print("=== 性能优化向导 ===")
    
    # 检测系统配置
    cpu_count = psutil.cpu_count()
    memory_gb = psutil.virtual_memory().total / (1024**3)
    
    # 推荐配置
    if memory_gb >= 8:
        cache_size = 200
        thread_count = min(cpu_count, 4)
    else:
        cache_size = 100
        thread_count = min(cpu_count, 2)
    
    return {
        "缓存大小": f"{cache_size}MB",
        "线程数": thread_count,
        "识别间隔": "1-2秒",
        "区域大小": "适中"
    }
```

#### 自动优化
```python
def auto_optimize():
    """自动性能优化"""
    # 清理缓存
    clear_cache()
    
    # 优化数据库
    optimize_database()
    
    # 调整线程池
    adjust_thread_pool()
    
    # 更新配置
    update_config()
```

## 📈 性能调优检查清单

### 基础优化
- [ ] 设置合适的识别间隔（1-2秒）
- [ ] 选择适中的监控区域大小
- [ ] 启用智能缓存功能
- [ ] 配置合理的线程池大小

### 高级优化
- [ ] 启用多引擎负载均衡
- [ ] 配置连接池和超时参数
- [ ] 优化数据库查询和索引
- [ ] 启用内存管理和垃圾回收

### 监控优化
- [ ] 配置性能监控指标
- [ ] 设置告警阈值
- [ ] 定期进行性能测试
- [ ] 分析性能瓶颈

### 持续优化
- [ ] 定期清理缓存和历史数据
- [ ] 监控系统资源使用情况
- [ ] 根据使用情况调整配置
- [ ] 关注程序更新和优化建议

---

*性能优化是一个持续的过程，建议定期检查和调整配置以获得最佳性能。*
