# 用户手册

## 📖 目录

1. [系统概述](#系统概述)
2. [快速入门](#快速入门)
3. [前端界面使用](#前端界面使用)
4. [记忆管理操作](#记忆管理操作)
5. [任务跟踪使用](#任务跟踪使用)
6. [系统监控](#系统监控)
7. [高级功能](#高级功能)
8. [故障排除](#故障排除)

## 🦞 系统概述

### 什么是精简自我感知系统？

精简自我感知系统是一个专为AI助手设计的轻量级记忆管理和自我监控平台。系统帮助AI助手：

- **管理长期记忆**：存储和检索重要信息
- **监控会话状态**：实时跟踪Token使用情况
- **预警和提醒**：在资源紧张时发出警告
- **任务跟踪**：管理长期任务和进度

### 目标用户

- **AI助手开发者**：需要为AI助手添加记忆功能
- **系统管理员**：需要监控AI助手运行状态
- **终端用户**：通过前端界面查看系统状态

### 系统特点

- **轻量高效**：核心功能精简，资源占用少
- **实时监控**：Token使用率实时更新
- **易于集成**：提供标准RESTful API
- **可视化界面**：直观的前端仪表板
- **模块化设计**：易于扩展和维护

## 🚀 快速入门

### 第一步：启动系统

#### Windows用户
```powershell
# 进入系统目录
cd C:\Users\Administrator\.openclaw\workspace\self_perception_simple_clean

# 启动所有服务
.\start_all_services.ps1
```

#### Linux/macOS用户
```bash
# 进入系统目录
cd ~/.openclaw/workspace/self_perception_simple_clean

# 启动服务
python start_api_service.py &
python vector_service.py &
python -m http.server 8080 -d frontend &
```

### 第二步：验证服务

打开浏览器，访问以下地址：

1. **前端仪表板**: http://localhost:8080
2. **API健康检查**: http://127.0.0.1:8001/health
3. **向量服务健康检查**: http://127.0.0.1:8007/health

如果看到以下内容，说明系统启动成功：

- ✅ 前端界面显示系统状态
- ✅ API服务返回`{"status": "healthy"}`
- ✅ 向量服务返回`{"status": "healthy"}`

### 第三步：首次配置

1. **配置API密钥**（如果需要）：
   - 编辑`.env`文件
   - 设置`DEEPSEEK_API_KEY`为你的API密钥

2. **调整监控阈值**（可选）：
   ```env
   # 在.env文件中调整
   TOKEN_WARNING_THRESHOLD=75      # 警告阈值调整为75%
   TOKEN_CRITICAL_THRESHOLD=85     # 严重阈值调整为85%
   ```

3. **初始化记忆库**：
   ```bash
   python create_clean_db.py
   ```

## 🖥️ 前端界面使用

### 界面布局

前端界面采用现代化设计，包含以下区域：

```
┌─────────────────────────────────────────────────────┐
│                    🦞 系统标题                      │
├─────────────────────────────────────────────────────┤
│              📊 状态卡片（5个状态项）               │
│  • 系统状态    ✅ 运行中                            │
│  • API服务    ✅ 端口8001监听中                    │
│  • 向量服务    ✅ 端口8007监听中                    │
│  • 前端服务    ✅ 端口8080监听中                    │
│  • 记忆数量    ⚠️  9条                             │
├─────────────────────────────────────────────────────┤
│              🕐 时间显示区域                        │
│              2026年3月28日 22:52:00                │
├─────────────────────────────────────────────────────┤
│              📝 页脚信息                            │
│              🦞 为猫爸服务 | 系统版本: v1.0        │
└─────────────────────────────────────────────────────┘
```

### 状态指示器

| 状态 | 图标 | 颜色 | 含义 |
|------|------|------|------|
| 正常 | ✅ | 绿色 | 服务运行正常 |
| 警告 | ⚠️ | 黄色 | 需要注意，但可继续运行 |
| 错误 | ❌ | 红色 | 服务异常，需要处理 |
| 运行中 | 🔄 | 蓝色 | 服务正在启动或处理中 |

### 实时功能

1. **自动时间更新**：界面时间每秒自动更新
2. **状态动画**：状态项有淡入动画效果
3. **响应式设计**：适配不同屏幕尺寸

### 快捷键

- **F5** 或 **Ctrl+R**: 刷新页面
- **Ctrl+Shift+R**: 强制刷新（清除缓存）
- **F12**: 打开开发者工具

## 🧠 记忆管理操作

### 什么是记忆？

在自我感知系统中，"记忆"是指AI助手需要长期保存的信息，例如：

- **用户偏好**：用户喜欢什么，不喜欢什么
- **重要对话**：关键的历史对话内容
- **任务记录**：已完成或进行中的任务
- **学习经验**：从错误中学习的经验教训

### 记忆类型

系统支持多种记忆类型：

| 类型 | 类型名称 | 用途 | 重要性范围 |
|------|----------|------|------------|
| `conversation` | 对话记忆 | 普通对话内容 | 1-3 |
| `preference` | 用户偏好 | 用户喜好和习惯 | 2-4 |
| `task` | 任务记录 | 任务相关信息 | 2-5 |
| `learning` | 学习经验 | 从经验中学到的知识 | 3-5 |
| `important` | 重要信息 | 关键信息，需要长期保存 | 4-5 |

### 添加记忆

#### 通过API添加

```python
import requests

# 添加用户偏好记忆
memory_data = {
    "content": "用户喜欢在早上喝咖啡，不喜欢加糖",
    "type": "preference",
    "type_name": "用户偏好",
    "importance": 3,  # 中等重要性
    "metadata": {
        "source": "conversation_20260328",
        "category": "beverage",
        "confidence": 0.9
    }
}

response = requests.post(
    "http://localhost:8007/memories/add",
    json=memory_data
)

if response.status_code == 200:
    print("记忆添加成功！")
    print(f"记忆ID: {response.json()['memory_id']}")
else:
    print("记忆添加失败")
```

#### 通过Python代码添加

```python
from vector_service import VectorStorage

# 初始化存储
storage = VectorStorage("vectors.db")

# 添加多个记忆
memories_to_add = [
    {
        "content": "用户的工作时间是9:00-18:00",
        "type": "preference",
        "type_name": "工作时间",
        "importance": 2
    },
    {
        "content": "用户经常使用Markdown格式",
        "type": "preference", 
        "type_name": "文档偏好",
        "importance": 3
    },
    {
        "content": "上次系统更新在2026年3月28日",
        "type": "important",
        "type_name": "系统记录",
        "importance": 4
    }
]

for memory in memories_to_add:
    success = storage.add_memory(memory)
    if success:
        print(f"添加成功: {memory['content'][:30]}...")
    else:
        print(f"添加失败: {memory['content'][:30]}...")
```

### 搜索记忆

#### 简单关键词搜索

```python
from vector_service import VectorStorage

storage = VectorStorage("vectors.db")

# 搜索包含"咖啡"的记忆
results = storage.search_memories("咖啡", limit=5)

print(f"找到 {len(results)} 条相关记忆:")
for i, memory in enumerate(results, 1):
    print(f"{i}. {memory['content'][:50]}...")
    print(f"   类型: {memory['type_name']}")
    print(f"   时间: {memory['created_at']}")
    print()
```

#### 高级搜索示例

```python
def search_important_memories(keyword, min_importance=3):
    """搜索重要记忆"""
    storage = VectorStorage("vectors.db")
    all_memories = storage.get_all_memories(limit=100)
    
    # 过滤重要记忆
    important_memories = [
        m for m in all_memories 
        if m['importance'] >= min_importance 
        and keyword.lower() in m['content'].lower()
    ]
    
    return important_memories

# 搜索重要性3以上的"工作"相关记忆
work_memories = search_important_memories("工作", min_importance=3)
print(f"找到 {len(work_memories)} 条重要工作记忆")
```

### 记忆管理最佳实践

1. **分类明确**：为记忆设置合适的类型
2. **重要性分级**：根据重要性设置1-5级
3. **元数据丰富**：添加详细的metadata信息
4. **定期清理**：删除过时或不重要的记忆
5. **备份重要记忆**：定期导出重要记忆

### 记忆导出和导入

#### 导出记忆到JSON

```python
import json
from vector_service import VectorStorage
from datetime import datetime

def export_memories_to_json(filename):
    """导出所有记忆到JSON文件"""
    storage = VectorStorage("vectors.db")
    memories = storage.get_all_memories(limit=1000)
    
    export_data = {
        "export_time": datetime.now().isoformat(),
        "total_memories": len(memories),
        "memories": memories
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    print(f"已导出 {len(memories)} 条记忆到 {filename}")
    return filename

# 导出记忆
export_memories_to_json("memories_export_20260328.json")
```

#### 从JSON导入记忆

```python
import json
from vector_service import VectorStorage

def import_memories_from_json(filename):
    """从JSON文件导入记忆"""
    storage = VectorStorage("vectors.db")
    
    with open(filename, 'r', encoding='utf-8') as f:
        import_data = json.load(f)
    
    imported_count = 0
    for memory in import_data.get('memories', []):
        # 移除数据库ID，让系统重新生成
        if 'id' in memory and isinstance(memory['id'], int):
            del memory['id']
        
        success = storage.add_memory(memory)
        if success:
            imported_count += 1
    
    print(f"已导入 {imported_count} 条记忆")
    return imported_count

# 导入记忆
import_memories_from_json("memories_backup.json")
```

## 📋 任务跟踪使用

### 任务跟踪模块概述

任务跟踪模块帮助AI助手管理长期任务，包括：

- **任务创建**：定义新任务和子任务
- **进度跟踪**：实时更新任务进度
- **状态管理**：任务状态转换（待处理、进行中、完成等）
- **优先级管理**：根据重要性设置任务优先级

### 创建和管理任务

#### 基本任务创建

```python
from modules.task_tracker import TaskTracker

# 初始化任务跟踪器
tracker = TaskTracker()

# 创建新任务
task_id = tracker.create_task(
    title="编写用户文档",
    description="为自我感知系统编写完整的用户文档",
    priority="high",  # low, medium, high, critical
    estimated_hours=4,
    category="documentation",
    assignee="龙虾小兵"
)

print(f"创建任务成功，任务ID: {task_id}")
```

#### 更新任务状态

```python
# 更新任务进度
tracker.update_task_status(
    task_id=task_id,
    status="in_progress",  # pending, in_progress, blocked, completed, cancelled
    progress=25,  # 进度百分比
    notes="已完成文档结构规划"
)

# 添加任务评论
tracker.add_task_comment(
    task_id=task_id,
    comment="需要添加API文档示例",
    author="猫爸"
)
```

#### 查询任务

```python
# 获取任务详情
task_details = tracker.get_task(task_id)
print(f"任务标题: {task_details['title']}")
print(f"当前状态: {task_details['status']}")
print(f"进度: {task_details['progress']}%")

# 搜索任务
search_results = tracker.search_tasks(
    query="文档",
    status="in_progress",
    priority="high"
)

print(f"找到 {len(search_results)} 个相关任务")
```

### 任务状态工作流

```
待处理 (pending)
    ↓
进行中 (in_progress)
    ├── 完成 (completed)
    ├── 阻塞 (blocked) → 解决后 → 进行中
    └── 取消 (cancelled)
```

### 任务提醒和通知

```python
# 设置任务提醒
tracker.set_task_reminder(
    task_id=task_id,
    reminder_time="2026-03-29T10:00:00",  # ISO格式时间
    message="检查文档编写进度"
)

# 获取即将到期的任务
upcoming_tasks = tracker.get_upcoming_tasks(hours_ahead=24)
for task in upcoming_tasks:
    print(f"即将到期: {task['title']} (截止时间: {task['deadline']})")
```

### 任务统计和报告

```python
# 生成任务统计报告
report = tracker.generate_task_report(
    start_date="2026-03-01",
    end_date="2026-03-28"
)

print("=== 任务统计报告 ===")
print(f"总任务数: {report['total_tasks']}")
print(f"已完成: {report['completed_tasks']}")
print(f"进行中: {report['in_progress_tasks']}")
print(f"完成率: {report['completion_rate']:.1f}%")
print(f"平均完成时间: {report['avg_completion_hours']:.1f}小时")
```

## 📊 系统监控

### Token使用监控

#### 实时监控Token使用率

```python
from session_monitor import session_monitor
from context_alert import context_alert

# 获取当前Token使用情况
tokens = session_monitor.get_current_session_tokens()
print(f"Token使用情况:")
print(f"  已使用: {tokens['used']:,} tokens")
print(f"  总量: {tokens['max']:,} tokens")
print(f"  使用率: {tokens['percentage']:.1f}%")

# 检查预警状态
alert_status = context_alert.check_status(tokens['used'], tokens['max'])
print(f"预警级别: {alert_status['level']}")
print(f"预警信息: {alert_status['message']}")
```

#### 监控配置

在`.env`文件中配置监控参数：

```env
# Token监控配置
TOKEN_MONITOR_ENABLED=true
TOKEN_WARNING_THRESHOLD=80      # 达到80%发出警告
TOKEN_CLEANUP_THRESHOLD=85      # 达到85%触发清理
TOKEN_CRITICAL_THRESHOLD=90     # 达到90%严重警告
MAX_CONTEXT_TOKENS=128000       # 最大Token数
```

### 服务健康监控

#### 检查所有服务状态

```python
import requests
import time

def check_all_services():
    """检查所有服务状态"""
    services = [
        {"name": "API服务", "url": "http://127.0.0.1:8001/health"},
        {"name": "向量服务", "url": "http://127.0.0.1:8007/health"},
    ]
    
    results = []
    for service in services:
        try:
            start_time = time.time()
            response = requests.get(service["url"], timeout=5)
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                status = "✅ 健康"
            else:
                status = "❌ 异常"
                
            results.append({
                "service": service["name"],
                "status": status,
                "response_time": f"{response_time:.0f}ms",
                "details": response.json() if response.status_code == 200 else None
            })
        except Exception as e:
            results.append({
                "service": service["name"],
                "status": "❌ 无法连接",
                "response_time": "超时",
                "details": str(e)
            })
    
    return results

# 执行监控检查
monitor_results = check_all_services()
for result in monitor_results:
    print(f"{result['service']}: {result['status']} ({result['response_time']})")
```

#### 自动化监控脚本

创建监控脚本 `monitor_services.py`：

```python
#!/usr/bin/env python3
"""
服务监控脚本 - 定期检查系统服务状态
"""

import requests
import time
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('service_monitor.log'),
        logging.StreamHandler()
    ]
)

def monitor_services():
    """监控所有服务"""
    services = [
        {"name": "API服务", "url": "http://127.0.0.1:8001/health"},
        {"name": "向量服务", "url": "http://127.0.0.1:8007/health"},
    ]
    
    all