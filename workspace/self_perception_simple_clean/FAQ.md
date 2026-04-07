# 常见问题解答 (FAQ)

## 📋 目录

1. [安装问题](#安装问题)
2. [使用问题](#使用问题)
3. [故障问题](#故障问题)
4. [性能优化](#性能优化)
5. [配置问题](#配置问题)
6. [API问题](#api问题)
7. [数据库问题](#数据库问题)
8. [安全问题](#安全问题)

## 🛠️ 安装问题

### Q1: 系统启动时显示"端口被占用"错误怎么办？

**问题描述**：
```
Error: [Errno 10048] Only one usage of each socket address is permitted
```

**解决方案**：

#### 方法1：查找并终止占用进程
```powershell
# Windows
netstat -ano | findstr :8001
# 找到PID后
taskkill /PID <PID> /F

# Linux/macOS
lsof -i :8001
# 找到PID后
kill -9 <PID>
```

#### 方法2：修改端口配置
编辑 `.env` 文件，修改端口：
```env
API_SERVICE_PORT=8002
VECTOR_SERVICE_PORT=8008
FRONTEND_PORT=8081
```

#### 方法3：使用备用启动脚本
```bash
python start_api_service.py --port 8002
python vector_service.py --port 8008
```

### Q2: 安装依赖时出现"Could not find a version"错误怎么办？

**问题描述**：
```
ERROR: Could not find a version that satisfies the requirement package-name
```

**解决方案**：

#### 方法1：升级pip
```bash
python -m pip install --upgrade pip
```

#### 方法2：使用国内镜像源
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

#### 方法3：手动安装缺失包
```bash
# 查看具体缺失的包
pip install package-name==specific-version

# 或尝试安装最新版
pip install package-name --upgrade
```

### Q3: Windows系统下启动脚本无法执行怎么办？

**问题描述**：
```
.\start_all_services.ps1 : 无法加载文件...因为在此系统上禁止运行脚本
```

**解决方案**：

#### 方法1：修改执行策略（临时）
```powershell
# 以管理员身份运行PowerShell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

#### 方法2：修改执行策略（永久）
```powershell
# 以管理员身份运行
Set-ExecutionPolicy RemoteSigned
```

#### 方法3：使用替代方法启动
```powershell
# 手动启动各服务
python start_api_service.py
# 新开终端
python vector_service.py
# 新开终端
python -m http.server 8080 -d frontend
```

### Q4: 数据库初始化失败怎么办？

**问题描述**：
```
sqlite3.OperationalError: unable to open database file
```

**解决方案**：

#### 方法1：检查文件权限
```bash
# 检查文件权限
ls -la vectors.db

# 修改权限
chmod 644 vectors.db
```

#### 方法2：删除损坏的数据库文件
```bash
# 备份现有文件
cp vectors.db vectors.db.backup

# 删除文件
rm vectors.db

# 重新初始化
python create_clean_db.py
```

#### 方法3：检查磁盘空间
```bash
# 检查磁盘空间
df -h .

# 清理空间
rm -f *.log
rm -f __pycache__/*.pyc
```

## 🖥️ 使用问题

### Q5: 前端界面无法访问怎么办？

**问题描述**：
访问 http://localhost:8080 显示连接被拒绝或空白页面。

**解决方案**：

#### 方法1：检查前端服务是否运行
```bash
# 检查端口监听
netstat -ano | findstr :8080

# 如果没有监听，启动前端服务
python -m http.server 8080 -d frontend
```

#### 方法2：检查防火墙设置
```powershell
# Windows - 检查防火墙规则
netsh advfirewall firewall show rule name=all | findstr 8080

# 添加防火墙规则（如果需要）
netsh advfirewall firewall add rule name="Self Perception Frontend" dir=in action=allow protocol=TCP localport=8080
```

#### 方法3：使用不同的浏览器或清除缓存
- 尝试使用 Chrome、Firefox 或 Edge
- 按 Ctrl+Shift+R 强制刷新
- 清除浏览器缓存

### Q6: 如何查看系统日志？

**问题描述**：
需要查看系统运行日志进行调试。

**解决方案**：

#### 方法1：查看标准输出日志
```bash
# 如果服务在终端运行，直接查看输出
python start_api_service.py
```

#### 方法2：查看日志文件
```bash
# 检查日志文件
ls -la *.log

# 查看最新日志
tail -f api_service.log
tail -f vector_service.log
```

#### 方法3：启用详细日志
编辑 `.env` 文件：
```env
LOG_LEVEL=DEBUG
LOG_FILE=system_debug.log
```

然后重启服务。

### Q7: 如何添加自定义记忆类型？

**问题描述**：
需要添加系统不支持的记忆类型。

**解决方案**：

#### 方法1：通过API添加时指定类型
```python
import requests

memory_data = {
    "content": "自定义内容",
    "type": "custom_type",      # 自定义类型
    "type_name": "自定义类型名称",  # 显示名称
    "importance": 2,
    "metadata": {
        "category": "custom",
        "source": "manual"
    }
}

response = requests.post(
    "http://localhost:8007/memories/add",
    json=memory_data
)
```

#### 方法2：修改数据库支持新类型
```python
# 在 vector_service.py 中添加类型验证
VALID_TYPES = [
    'conversation', 'preference', 'task', 
    'learning', 'important', 'custom_type'  # 添加自定义类型
]

def validate_memory_type(memory_type):
    if memory_type not in VALID_TYPES:
        # 自动转换为默认类型或记录警告
        return 'conversation'
    return memory_type
```

#### 方法3：创建类型管理模块
创建 `modules/memory_types.py`：
```python
class MemoryTypeManager:
    TYPES = {
        'conversation': {'name': '对话记忆', 'priority': 1},
        'preference': {'name': '用户偏好', 'priority': 2},
        'custom_type': {'name': '自定义类型', 'priority': 1},
    }
    
    @classmethod
    def get_type_info(cls, type_key):
        return cls.TYPES.get(type_key, cls.TYPES['conversation'])
```

### Q8: 如何备份和恢复系统数据？

**问题描述**：
需要定期备份系统数据以防丢失。

**解决方案**：

#### 方法1：手动备份
```bash
# 创建备份目录
mkdir -p backups/$(date +%Y%m%d)

# 备份数据库
cp vectors.db backups/$(date +%Y%m%d)/vectors.db.backup

# 备份记忆文件
cp vector_store/*.json backups/$(date +%Y%m%d)/

# 备份配置文件
cp .env config.json backups/$(date +%Y%m%d)/
```

#### 方法2：使用备份脚本
创建 `scripts/backup.py`：
```python
#!/usr/bin/env python3
import shutil
import json
from datetime import datetime
import os

def backup_system():
    backup_dir = f"backups/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    # 备份文件列表
    files_to_backup = [
        'vectors.db',
        'vector_store/enhanced_memories_v1.json',
        '.env',
        'config.json'
    ]
    
    for file in files_to_backup:
        if os.path.exists(file):
            shutil.copy2(file, backup_dir)
            print(f"已备份: {file}")
    
    # 创建备份元数据
    metadata = {
        'backup_time': datetime.now().isoformat(),
        'files': files_to_backup,
        'system_version': '1.0.0'
    }
    
    with open(f'{backup_dir}/backup_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"备份完成: {backup_dir}")
    return backup_dir
```

#### 方法3：自动定时备份
使用cron（Linux）或任务计划程序（Windows）设置定时备份。

## 🔧 故障问题

### Q9: API服务返回500内部错误怎么办？

**问题描述**：
```
{
  "detail": "Internal Server Error"
}
```

**解决方案**：

#### 方法1：查看详细错误日志
```bash
# 查看API服务日志
tail -100 api_service.log

# 启用调试模式
python start_api_service.py --debug
```

#### 方法2：检查依赖包版本
```bash
# 检查关键依赖
pip show fastapi uvicorn

# 重新安装依赖
pip install --upgrade fastapi uvicorn
```

#### 方法3：简化测试
```bash
# 测试最简单的端点
curl http://127.0.0.1:8001/

# 测试健康检查
curl http://127.0.0.1:8001/health
```

### Q10: 向量服务搜索无结果怎么办？

**问题描述**：
搜索关键词返回空结果，但数据库中有相关记忆。

**解决方案**：

#### 方法1：检查数据库内容
```bash
# 使用SQLite命令行检查
sqlite3 vectors.db "SELECT content FROM vectors LIMIT 5;"
```

#### 方法2：重建搜索索引
```python
# 创建重建索引脚本 rebuild_index.py
import sqlite3

def rebuild_index():
    conn = sqlite3.connect('vectors.db')
    cursor = conn.cursor()
    
    # 删除旧索引
    cursor.execute('DROP INDEX IF EXISTS idx_search_content')
    
    # 创建新索引
    cursor.execute('''
        CREATE INDEX idx_search_content 
        ON vectors(content)
    ''')
    
    conn.commit()
    conn.close()
    print("搜索索引已重建")
```

#### 方法3：优化搜索查询
```python
# 修改搜索逻辑，支持模糊匹配
def enhanced_search(query, limit=10):
    conn = sqlite3.connect('vectors.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 使用多个搜索条件
    search_patterns = [
        f'%{query}%',           # 包含查询词
        f'{query}%',            # 以查询词开头
        f'%{query}',            # 以查询词结尾
    ]
    
    all_results = []
    for pattern in search_patterns:
        cursor.execute('''
            SELECT * FROM vectors 
            WHERE content LIKE ? 
            ORDER BY importance DESC, created_at DESC 
            LIMIT ?
        ''', (pattern, limit))
        
        all_results.extend(cursor.fetchall())
    
    # 去重并排序
    unique_results = []
    seen_ids = set()
    for row in all_results:
        if row['id'] not in seen_ids:
            seen_ids.add(row['id'])
            unique_results.append(dict(row))
    
    conn.close()
    return unique_results[:limit]
```

### Q11: Token监控显示异常值怎么办？

**问题描述**：
Token使用率显示为0%、100%或其他异常值。

**解决方案**：

#### 方法1：重置监控状态
```python
# 创建重置脚本 reset_monitor.py
from session_monitor import session_monitor

# 重置会话监控器
session_monitor.start_time = datetime.now()
print("会话监控器已重置")
```

#### 方法2：检查监控配置
```env
# 确保.env中配置正确
MAX_CONTEXT_TOKENS=128000
TOKEN_WARNING_THRESHOLD=80
TOKEN_CRITICAL_THRESHOLD=90
```

#### 方法3：手动计算Token使用
```python
import tiktoken

def calculate_tokens(text):
    """计算文本的Token数量"""
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

# 测试计算
text = "这是一个测试文本"
token_count = calculate_tokens(text)
print(f"文本Token数: {token_count}")
```

### Q12: 系统内存占用过高怎么办？

**问题描述**：
系统运行一段时间后内存占用持续增长。

**解决方案**：

#### 方法1：监控内存使用
```bash
# Linux/macOS
top -p $(pgrep -f "python.*self_perception")

# Windows
tasklist | findstr python
```

#### 方法2：添加内存清理机制
```python
# 在 vector_service.py 中添加定期清理
import gc
import threading
import time

def memory_cleanup_worker():
    """内存清理工作线程"""
    while True:
        time.sleep(300)  # 每5分钟清理一次
        gc.collect()     # 强制垃圾回收
        print("内存清理完成")

# 启动清理线程
cleanup_thread = threading.Thread(target=memory_cleanup_worker, daemon=True)
cleanup_thread.start()
```

#### 方法3：优化数据库连接
```python
# 使用连接池
import sqlite3
from contextlib import contextmanager

class ConnectionPool:
    def __init__(self, db_path, pool_size=5):
        self.db_path = db_path
        self.pool = []
        self.lock = threading.Lock()
        
    @contextmanager
    def get_connection(self):
        with self.lock:
            if self.pool:
                conn = self.pool.pop()
            else:
                conn = sqlite3.connect(self.db_path)
        
        try:
            yield conn
        finally:
            with self.lock:
                self.pool.append(conn)
```

## ⚡ 性能优化

### Q13: 如何提高系统响应速度？

**问题描述**：
API响应慢，搜索操作耗时过长。

**解决方案**：

#### 方法1：启用数据库索引
```sql
-- 确保以下索引存在
CREATE INDEX IF NOT EXISTS idx_content ON vectors(content);
CREATE INDEX IF NOT EXISTS idx_created_at ON vectors(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_importance ON vectors(importance DESC);
```

#### 方法2：优化查询语句
```python
# 使用更高效的查询
def optimized_search(query, limit=10):
    conn = sqlite3.connect('vectors.db')
    conn.row_factory = sqlite3.Row
    
    # 使用EXPLAIN QUERY PLAN分析查询
    cursor = conn.cursor()
    cursor.execute('EXPLAIN QUERY PLAN SELECT * FROM vectors WHERE content LIKE ?', (f'%{query}%',))
    print("查询计划:", cursor.fetchall())
    
    # 优化后的查询
    cursor.execute('''
        SELECT id, content, created_at 
        FROM vectors 
        WHERE content LIKE ? 
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (f'%{query}%', limit))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results
```

#### 方法3：添加缓存机制
```python
import functools
import time
from typing import Dict, Any

class MemoryCache:
    def __init__(self, ttl_seconds=300):
        self.cache: Dict[str, Any] = {}
        self.ttl = ttl_seconds
    
    def get(self, key):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None
    
    def set(self, key, value):
        self.cache[key] = (value, time.time())

# 使用缓存装饰器
cache = MemoryCache()

def cached_search(query, limit=10):
    cache_key = f"search:{query}:{limit}"
    cached_result = cache.get(cache_key)
    
    if cached_result is not None:
        print(f"缓存命中: {query}")
        return cached_result
    
    # 执行实际搜索
    result = perform_actual_search(query, limit)
    cache.set(cache_key, result)
    
    return result
```

### Q14: 如何减少数据库文件大小？

**问题描述**：
vectors.db 文件过大，影响性能。

**解决方案**：

#### 方法1：清理旧数据
```python
def cleanup_old_memories(days_old=30):
    """清理指定天数前的记忆"""
    conn = sqlite3.connect('vectors.db')
    cursor = conn.cursor()
    
    cutoff_date = datetime.now() - timedelta(days=days_old)
    
    cursor.execute('''
        DELETE FROM vectors 
        WHERE created_at < ? AND importance < 3
    ''', (cutoff_date.isoformat(),))
    
    deleted_count = cursor.rowcount
    conn.commit()
    
    # 执行VACUUM释放空间
    cursor.execute('VACUUM')
    
    conn.close()
    print(f"已清理 {deleted_count} 条旧记忆")
    return deleted_count
```

#### 方法2：压缩数据库
```bash
# 使用SQLite命令行压缩
sqlite3 vectors.db "VACUUM;"

# 或使用Python
import sqlite3
conn = sqlite3.connect('vectors.db')
conn.execute('VACUUM')
conn.close()
```

#### 方法3：归档历史数据
```python
def archive_old_memories(days_old=90, archive_file='memories_archive.json'):
    """归档旧记忆到JSON文件"""
    conn = sqlite3.connect('vectors.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cutoff_date = datetime.now() - timedelta(days=days_old