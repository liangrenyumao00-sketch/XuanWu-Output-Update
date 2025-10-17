# 故障排除指南

本指南将帮助您诊断和解决 XuanWu OCR 使用过程中遇到的各种问题。

## 🔍 诊断流程

### 基础诊断步骤
1. **确认问题现象**: 详细描述遇到的问题
2. **检查系统环境**: 确认系统版本和硬件配置
3. **查看错误日志**: 检查程序日志文件
4. **尝试重现问题**: 确认问题的可重现性
5. **逐步排查**: 按照本指南逐步排查问题

### 日志文件位置
```
日志文件路径：
- 主日志: logs/xuanwu_log.html
- 错误日志: logs/debug.html
- 安全日志: logs/security/security_YYYY-MM-DD.log
- 控制面板日志: logs/control_panel/control_panel_YYYY-MM-DD.log
```

## 🚨 常见问题分类

### 启动问题

#### 程序无法启动
**症状**: 双击程序文件无反应或启动失败

**可能原因**:
- Python环境问题
- 依赖包缺失
- 权限不足
- 系统兼容性问题

**解决步骤**:
1. **检查Python环境**
   ```bash
   python --version
   pip --version
   ```

2. **重新安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **以管理员权限运行**
   - 右键点击程序文件
   - 选择"以管理员身份运行"

4. **检查系统要求**
   - Windows 10 1903 或更高版本
   - 4GB RAM 或更多
   - 500MB 可用磁盘空间

**日志检查**:
```
查看错误信息：
- 检查控制台输出
- 查看 logs/debug.html
- 检查系统事件日志
```

#### 启动缓慢
**症状**: 程序启动时间超过30秒

**解决步骤**:
1. **检查系统资源**
   - 确保有足够的CPU和内存
   - 关闭不必要的程序

2. **网络检查**
   - 确保网络连接正常
   - 检查防火墙设置

3. **清理缓存**
   - 删除 cache/ 目录下的文件
   - 重启程序

### OCR识别问题

#### 识别失败
**症状**: OCR识别返回空结果或错误

**诊断步骤**:
1. **检查API配置**
   ```json
   {
     "API Key": "检查是否正确",
     "Secret Key": "检查是否正确",
     "识别版本": "检查是否支持"
   }
   ```

2. **网络连接测试**
   ```bash
   ping baidu.com
   telnet aip.baidubce.com 443
   ```

3. **API配额检查**
   - 登录百度智能云控制台
   - 检查API调用配额
   - 确认账户余额

**解决方案**:
- 验证API密钥有效性
- 检查网络连接
- 更新API密钥
- 联系API服务商

#### 识别不准确
**症状**: OCR识别结果包含错误字符

**优化建议**:
1. **图像质量优化**
   - 选择文字清晰的区域
   - 提高屏幕分辨率
   - 调整对比度和亮度

2. **识别参数调整**
   - 使用高精度识别版本
   - 调整图像预处理参数
   - 启用图像增强功能

3. **匹配模式选择**
   - 使用模糊匹配模式
   - 调整相似度阈值
   - 设置容错参数

### 性能问题

#### 程序卡顿
**症状**: 界面响应缓慢，操作延迟

**诊断工具**:
```python
import psutil
import time

def check_performance():
    # CPU使用率
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # 内存使用率
    memory = psutil.virtual_memory()
    
    # 磁盘IO
    disk_io = psutil.disk_io_counters()
    
    print(f"CPU: {cpu_percent}%")
    print(f"Memory: {memory.percent}%")
    print(f"Disk IO: {disk_io}")
```

**优化建议**:
1. **调整识别参数**
   - 增加识别间隔到3-5秒
   - 减小监控区域大小
   - 减少关键词数量

2. **系统优化**
   - 关闭不必要的程序
   - 清理系统垃圾文件
   - 更新显卡驱动

3. **程序配置**
   - 启用智能缓存
   - 调整线程池大小
   - 优化内存使用

#### 内存占用过高
**症状**: 程序内存使用超过500MB

**解决方案**:
1. **内存管理**
   ```json
   {
     "缓存大小": "100MB",
     "历史保留": "7天",
     "自动清理": true,
     "垃圾回收": "自动"
   }
   ```

2. **数据清理**
   - 清理历史记录
   - 删除临时文件
   - 压缩日志文件

3. **配置优化**
   - 减少并发线程数
   - 降低缓存大小
   - 启用内存监控

### 网络连接问题

#### API连接失败
**症状**: 无法连接到OCR服务

**诊断命令**:
```bash
# 测试网络连接
ping aip.baidubce.com
nslookup aip.baidubce.com

# 测试HTTPS连接
curl -I https://aip.baidubce.com

# 检查代理设置
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

**解决方案**:
1. **网络配置**
   - 检查网络连接
   - 配置代理设置
   - 检查防火墙规则

2. **DNS设置**
   - 更换DNS服务器
   - 清除DNS缓存
   - 检查hosts文件

3. **SSL证书**
   - 更新SSL证书
   - 检查证书有效性
   - 配置证书路径

#### 连接超时
**症状**: API调用超时或响应缓慢

**配置优化**:
```json
{
  "超时设置": {
    "连接超时": 10,
    "读取超时": 30,
    "重试次数": 3,
    "重试间隔": 1
  }
}
```

### 界面问题

#### 界面显示异常
**症状**: 界面元素显示不正确或布局混乱

**解决方案**:
1. **主题重置**
   - 重置为默认主题
   - 检查主题文件完整性
   - 重新加载界面

2. **分辨率适配**
   - 调整显示缩放
   - 检查DPI设置
   - 更新显卡驱动

3. **字体问题**
   - 重置字体设置
   - 检查字体文件
   - 使用系统默认字体

#### 快捷键不生效
**症状**: 全局快捷键无法使用

**诊断步骤**:
1. **权限检查**
   - 确认以管理员权限运行
   - 检查用户账户控制设置

2. **冲突检查**
   - 检查其他程序快捷键冲突
   - 查看系统快捷键设置

3. **重新注册**
   - 注销现有快捷键
   - 重新注册快捷键
   - 重启程序

## 🛠️ 高级故障排除

### 调试模式

#### 启用调试模式
```python
# 在配置文件中启用调试模式
{
  "debug": {
    "enabled": true,
    "log_level": "DEBUG",
    "console_output": true,
    "file_output": true
  }
}
```

#### 调试信息收集
```python
import logging
import traceback

def collect_debug_info():
    debug_info = {
        "系统信息": {
            "操作系统": platform.system(),
            "版本": platform.version(),
            "架构": platform.architecture()
        },
        "Python环境": {
            "版本": sys.version,
            "路径": sys.executable
        },
        "依赖包": {
            "PyQt6": get_pyqt_version(),
            "requests": get_requests_version()
        },
        "程序配置": load_config(),
        "错误日志": get_recent_errors()
    }
    return debug_info
```

### 性能分析

#### 性能监控
```python
import cProfile
import pstats

def profile_performance():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # 运行需要分析的代码
    your_function()
    
    profiler.disable()
    
    # 保存性能数据
    profiler.dump_stats('performance.prof')
    
    # 分析结果
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)
```

#### 内存分析
```python
import tracemalloc

def analyze_memory():
    tracemalloc.start()
    
    # 运行代码
    your_function()
    
    # 获取内存快照
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')
    
    # 显示内存使用情况
    for stat in top_stats[:10]:
        print(stat)
```

### 数据恢复

#### 配置恢复
```python
def restore_config():
    """恢复配置文件"""
    backup_files = [
        "settings.json.backup",
        "config/backup_*.json"
    ]
    
    for backup_file in backup_files:
        if os.path.exists(backup_file):
            shutil.copy2(backup_file, "settings.json")
            print(f"已恢复配置: {backup_file}")
            break
```

#### 数据修复
```python
def repair_database():
    """修复数据库"""
    import sqlite3
    
    # 连接到数据库
    conn = sqlite3.connect('performance_data.db')
    
    # 执行修复
    conn.execute("VACUUM")
    conn.execute("REINDEX")
    
    # 检查完整性
    integrity_check = conn.execute("PRAGMA integrity_check").fetchone()
    print(f"数据库完整性: {integrity_check}")
    
    conn.close()
```

## 📞 获取帮助

### 自助诊断工具

#### 系统诊断脚本
```python
def system_diagnosis():
    """系统诊断工具"""
    print("=== 系统诊断报告 ===")
    
    # 系统信息
    print(f"操作系统: {platform.system()} {platform.version()}")
    print(f"Python版本: {sys.version}")
    print(f"程序版本: {get_version()}")
    
    # 硬件信息
    print(f"CPU核心数: {psutil.cpu_count()}")
    print(f"内存总量: {psutil.virtual_memory().total / (1024**3):.1f}GB")
    
    # 程序状态
    print(f"进程状态: {'运行中' if is_running() else '未运行'}")
    print(f"配置状态: {'正常' if check_config() else '异常'}")
    
    # 网络状态
    print(f"网络连接: {'正常' if test_network() else '异常'}")
    
    # 权限状态
    print(f"管理员权限: {'是' if is_admin() else '否'}")
```

#### 配置验证工具
```python
def validate_config():
    """配置验证工具"""
    issues = []
    
    # 检查API配置
    if not validate_api_config():
        issues.append("API配置无效")
    
    # 检查文件权限
    if not check_file_permissions():
        issues.append("文件权限不足")
    
    # 检查网络连接
    if not test_api_connection():
        issues.append("API连接失败")
    
    return issues
```

### 技术支持

#### 问题报告模板
```
问题报告模板：

1. 问题描述：
   - 详细描述遇到的问题
   - 问题发生的时间和环境

2. 系统环境：
   - 操作系统版本
   - Python版本
   - 程序版本

3. 重现步骤：
   - 详细的重现步骤
   - 预期结果和实际结果

4. 错误信息：
   - 完整的错误信息
   - 相关的日志文件

5. 已尝试的解决方案：
   - 列出已经尝试的解决方法
   - 结果如何
```

#### 联系信息
- **GitHub Issues**: [提交问题](https://github.com/liangrenyumao00-sketch/XuanWu-Output-Update/issues)
- **邮箱支持**: 发送邮件到技术支持邮箱
- **在线文档**: 查看完整的在线文档
- **社区论坛**: 参与社区讨论

### 预防措施

#### 定期维护
1. **定期更新**: 保持程序和依赖包最新
2. **定期备份**: 定期备份配置和数据
3. **定期清理**: 清理临时文件和日志
4. **定期检查**: 检查系统健康状态

#### 监控告警
```python
def setup_monitoring():
    """设置监控告警"""
    monitors = {
        "CPU使用率": {"阈值": 80, "告警": "CPU使用率过高"},
        "内存使用率": {"阈值": 90, "告警": "内存使用率过高"},
        "识别失败率": {"阈值": 10, "告警": "识别失败率过高"},
        "网络延迟": {"阈值": 5000, "告警": "网络延迟过高"}
    }
    
    return monitors
```

---

*如果问题仍然无法解决，请提供详细的诊断信息联系技术支持。*
