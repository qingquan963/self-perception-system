# 精简自我感知系统

## 🦞 系统简介

精简自我感知系统是一个轻量级的记忆管理和自我监控系统，专为AI助手设计。系统提供核心的记忆存储、检索、监控和预警功能，帮助AI助手更好地管理会话上下文和长期记忆。

### ✨ 核心特点

- **轻量级设计**：只包含核心功能，无冗余组件
- **实时监控**：Token使用率实时监控和预警
- **记忆管理**：向量化记忆存储和智能检索
- **模块化架构**：易于扩展和维护
- **RESTful API**：标准化的接口设计

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Windows/Linux/macOS
- 网络连接（用于API调用）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动系统

#### 方法一：一键启动（推荐）

```powershell
# Windows PowerShell
.\start_all_services.ps1

# 或使用Python
python start_all_services.py
```

#### 方法二：手动启动各服务

```bash
# 启动API服务（端口8001）
python start_api_service.py

# 启动向量服务（端口8007）
python vector_service.py

# 启动前端仪表板（端口8080）
python -m http.server 8080 -d frontend
```

### 验证安装

启动后，访问以下地址验证服务状态：

1. **API服务健康检查**：http://127.0.0.1:8001/health
2. **向量服务健康检查**：http://127.0.0.1:8007/health
3. **前端仪表板**：http://localhost:8080

## 📊 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    前端界面 (8080)                          │
│                    http://localhost:8080                    │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    API网关服务 (8001)                       │
│                    /health, /context/status                 │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    核心功能模块                             │
├─────────────────────────────────────────────────────────────┤
│  • 会话监控 (session_monitor.py)                           │
│  • 上下文预警 (context_alert.py)                           │
│  • 向量存储 (vector_service.py)                            │
│  • 记忆管理 (modules/conversation_memory.py)               │
│  • 任务跟踪 (modules/task_tracker.py)                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    数据存储层                               │
├─────────────────────────────────────────────────────────────┤
│  • SQLite数据库 (vectors.db)                               │
│  • JSON记忆文件 (vector_store/)                            │
│  • 配置文件 (config.json, .env)                            │
└─────────────────────────────────────────────────────────────┘
```

### 技术栈

- **后端框架**：FastAPI (Python)
- **数据库**：SQLite3
- **前端**：HTML5 + CSS3 + JavaScript
- **向量存储**：自定义向量化实现
- **监控**：自定义会话监控系统

## 🔧 配置说明

### 环境变量 (.env)

```env
# DeepSeek API配置
DEEPSEEK_API_KEY=sk-your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# Token监控配置
TOKEN_MONITOR_ENABLED=true
TOKEN_WARNING_THRESHOLD=80
TOKEN_CLEANUP_THRESHOLD=85
TOKEN_CRITICAL_THRESHOLD=90
MAX_CONTEXT_TOKENS=128000

# 系统配置
SELF_PERCEPTION_SYSTEM=true
VECTOR_SERVICE_PORT=8007
API_SERVICE_PORT=8001
```

### 系统配置 (config.json)

```json
{
    "system": {
        "name": "精简自我感知系统",
        "version": "1.0.0",
        "description": "精简的记忆和自我感知系统"
    },
    "services": {
        "api_port": 8001,
        "vector_port": 8007,
        "frontend_port": 8080
    },
    "memory": {
        "max_memories": 100,
        "auto_cleanup": true,
        "backup_enabled": true
    }
}
```

## 📖 用户手册

### API接口文档

系统提供完整的RESTful API接口，支持以下功能：

#### 1. 健康检查
```http
GET /health
```
**响应示例**：
```json
{
    "status": "healthy",
    "service": "Simple Self-Perception System",
    "version": "1.0.0",
    "timestamp": "2026-03-28T22:52:00.123456",
    "components": {
        "api": true,
        "context_alert": true
    }
}
```

#### 2. 上下文状态
```http
GET /context/status
```
**响应示例**：
```json
{
    "token_usage_percentage": 39.06,
    "total_tokens": 128000,
    "used_tokens": 50000,
    "warning_level": "NORMAL",
    "timestamp": "2026-03-28T22:52:00.123456"
}
```

#### 3. 向量服务API

**获取所有记忆**：
```http
GET /memories?limit=100
```

**搜索记忆**：
```http
GET /memories/search?query=关键词&limit=10
```

**添加记忆**：
```http
POST /memories/add
Content-Type: application/json

{
    "content": "记忆内容",
    "type": "conversation",
    "type_name": "对话记忆",
    "importance": 1,
    "metadata": {
        "source": "user_input",
        "category": "general"
    }
}
```

### 前端界面使用

前端界面提供系统状态监控和可视化展示：

1. **系统状态面板**：显示各服务运行状态
2. **Token使用监控**：实时显示Token使用率
3. **记忆统计**：显示记忆数量和类型分布
4. **时间显示**：当前系统时间

访问地址：http://localhost:8080

### 记忆管理操作

#### 添加记忆
```python
from vector_service import VectorStorage

# 初始化向量存储
storage = VectorStorage("vectors.db")

# 添加记忆
memory = {
    "content": "用户喜欢喝咖啡",
    "type": "preference",
    "type_name": "用户偏好",
    "importance": 2,
    "metadata": {
        "source": "conversation",
        "timestamp": "2026-03-28T22:52:00"
    }
}

success = storage.add_memory(memory)
```

#### 搜索记忆
```python
# 搜索相关记忆
results = storage.search_memories("咖啡", limit=5)
for memory in results:
    print(f"内容: {memory['content']}")
    print(f"类型: {memory['type']}")
    print(f"时间: {memory['created_at']}")
    print("---")
```

#### 获取记忆统计
```python
# 获取记忆数量
count = storage.get_memory_count()
print(f"总记忆数: {count}")

# 获取所有记忆
all_memories = storage.get_all_memories(limit=50)
```

### 任务跟踪

系统内置任务跟踪模块，帮助管理长期任务：

```python
from modules.task_tracker import TaskTracker

# 初始化任务跟踪器
tracker = TaskTracker()

# 创建新任务
task_id = tracker.create_task(
    title="文档编写",
    description="编写系统用户文档",
    priority="high",
    estimated_hours=4
)

# 更新任务状态
tracker.update_task_status(task_id, "in_progress", progress=25)

# 完成任务
tracker.complete_task(task_id, "文档编写完成")
```

## 👨‍💼 管理员手册

### 系统安装部署

#### 全新安装步骤

1. **环境准备**
   ```bash
   # 克隆或下载系统代码
   git clone <repository-url>
   cd self_perception_simple_clean
   
   # 创建虚拟环境
   python -m venv venv
   
   # 激活虚拟环境
   # Windows
   venv\Scripts\activate
   # Linux/macOS
   source venv/bin/activate
   
   # 安装依赖
   pip install -r requirements.txt
   ```

2. **配置设置**
   ```bash
   # 复制环境变量模板
   cp .env.example .env
   
   # 编辑.env文件，配置API密钥等
   # 使用文本编辑器编辑.env文件
   ```

3. **数据库初始化**
   ```bash
   # 运行数据库初始化脚本
   python create_clean_db.py
   
   # 或检查数据库状态
   python check_db.py
   ```

4. **启动服务**
   ```bash
   # 使用启动脚本
   .\start_all_services.ps1
   ```

#### Docker部署（可选）

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001 8007 8080

CMD ["python", "start_all_services.py"]
```

### 服务配置说明

#### 端口配置

系统使用以下默认端口：
- **API服务**：8001
- **向量服务**：8007
- **前端服务**：8080

如需修改端口，请更新以下文件：
1. `.env` 文件中的 `API_SERVICE_PORT` 和 `VECTOR_SERVICE_PORT`
2. `config.json` 文件中的 `services` 部分
3. 各服务的启动脚本

#### 监控配置

Token监控阈值配置：
- **警告阈值**：80%（达到此值系统发出警告）
- **清理阈值**：85%（触发自动清理机制）
- **严重阈值**：90%（需要立即处理）

修改 `.env` 文件中的相应配置项。

### 监控和维护指南

#### 日常监控

1. **服务状态监控**
   ```bash
   # 检查服务是否运行
   netstat -ano | findstr :8001
   netstat -ano | findstr :8007
   ```

2. **日志查看**
   ```bash
   # 查看API服务日志
   tail -f api_service.log
   
   # 查看向量服务日志
   tail -f vector_service.log
   ```

3. **性能监控**
   ```bash
   # 检查内存使用
   python check_performance.py
   
   # 检查数据库状态
   python check_db.py
   ```

#### 定期维护

1. **数据库备份**
   ```bash
   # 备份SQLite数据库
   cp vectors.db vectors.db.backup.$(date +%Y%m%d)
   
   # 备份记忆文件
   cp vector_store/enhanced_memories_v1.json vector_store/backup/
   ```

2. **日志清理**
   ```bash
   # 清理30天前的日志
   find . -name "*.log" -mtime +30 -delete
   ```

3. **记忆清理**
   ```bash
   # 运行记忆清理脚本
   python cleanup_memories.py --days 30
   ```

### 故障排查手册

#### 常见问题及解决方案

**问题1：服务启动失败**
```
症状：端口被占用或依赖缺失
解决方案：
1. 检查端口占用：netstat -ano | findstr :8001
2. 杀死占用进程：taskkill /PID <pid> /F
3. 重新安装依赖：pip install -r requirements.txt
```

**问题2：数据库连接错误**
```
症状：无法连接SQLite数据库
解决方案：
1. 检查数据库文件权限：确保有读写权限
2. 修复数据库：python check_db.py --repair
3. 重建数据库：python create_clean_db.py
```

**问题3：Token监控异常**
```
症状：Token使用率显示异常
解决方案：
1. 检查环境变量：确保MAX_CONTEXT_TOKENS设置正确
2. 重启监控服务：重启session_monitor.py
3. 查看日志：检查context_alert.log
```

**问题4：记忆搜索无结果**
```
症状：搜索关键词无返回结果
解决方案：
1. 检查数据库：python check_db.py
2. 重建索引：python rebuild_index.py
3. 检查搜索逻辑：确保查询参数正确
```

#### 紧急恢复流程

1. **服务宕机恢复**
   ```bash
   # 停止所有服务
   pkill -f "python.*self_perception"
   
   # 备份当前状态
   cp vectors.db vectors.db.emergency.backup
   
   # 重新启动
   .\start_all_services.ps1
   ```

2. **数据损坏恢复**
   ```bash
   # 从备份恢复数据库
   cp vectors.db.backup vectors.db
   
   # 从备份恢复记忆文件
   cp vector_store/backup/enhanced_memories_v1.json vector_store/
   
   # 重启服务
   .\start_all_services.ps1
   ```

## 👨‍💻 开发文档

### 代码结构说明

```
self_perception_simple_clean/
├── frontend/                    # 前端文件
│   └── waiting.html            # 前端界面
├── modules/                     # 功能模块
│   ├── capability_assessment.py # 能力评估
│   ├── conversation_memory.py   # 对话记忆
│   ├── decision_recorder.py     # 决策记录
│   ├── learning_feedback.py     # 学习反馈
│   └── task_tracker.py          # 任务跟踪
├── utils/                       # 工具函数
├── vector_store/                # 向量存储
│   ├── enhanced_memories_v1.json      # 记忆数据
│   └── enhanced_memories_v1_clean.json # 清理后记忆
├── .env                         # 环境变量
├── api_service.py               # API服务
├── config.json                  # 配置文件
├── context_alert.py             # 上下文预警
├── create_clean_db.py           # 数据库创建
├── README.md                    # 原始README
├── requirements.txt             # 依赖列表
├── session_monitor.py           # 会话监控
├── start_all_services.ps1       # 启动脚本
├── start_api_service.py         # API启动脚本
├── vector_service.py            # 向量服务
└── vectors.db                   # SQLite数据库
```

### 模块开发指南

#### 添加新模块

1. **创建模块文件**
   ```python
   # modules/new_module.py
   class NewModule:
       def __init__(self):
           self.name = "新模块"
           
       def process(self, data):
           """处理数据"""
           # 实现功能逻辑
           return processed_data
   ```

2. **集成到系统**
   ```python
   # 在主服务中导入
   from modules.new_module import NewModule
   
   # 初始化模块
   new_module = NewModule()
   
   # 在API端点中使用
   @app.get("/new-endpoint")
   async def new_endpoint():
       result = new_module.process(request_data)
       return result
   ```

#### API扩展方法

1. **添加新API端点**
   ```python
   # 在api_service.py中添加
   @app.get("/new-feature")
   async def new_feature():
       """新功能端点"""
       return {
           "feature": "new",
           "status": "available",
           "timestamp": datetime.now().isoformat()
       }
   
   @app.post("/process-data")
   async def process_data(data: dict):
       """处理数据端点"""
       # 处理逻辑
       result = process_function(data)
       return {
           "status": "processed",
           "result": result,
           "timestamp": datetime.now().isoformat()
       }
   ```

2. **添加请求验证**
   ```python
   from pydantic import BaseModel
   
   class ProcessRequest(BaseModel):
       input_data: str
       options: dict = {}
   
   @app.post("/process")
   async def process(request: ProcessRequest):
       """带验证的处理端点"""
       result = process_function(request.input_data, request.options)
       return {
           "input": request.input_data,
           "result": result,
           "timestamp": datetime.now().isoformat()
       }
   ```

### 测试和部署流程

#### 单元测试

```python
# test_api_service.py
import pytest
from fastapi.testclient import TestClient
from api_service import app

client = TestClient(app)

def test_health_check():
    """测试健康检查端点"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_context_status():
    """测试上下文状态端点"""
    response = client.get("/context/status")
    assert response.status_code == 200
    assert "token_usage_percentage" in response.json()
```

#### 集成测试

```python
# test_integration.py
def test_full_workflow():
    """测试完整工作流程"""
    # 1. 启动服务
    # 2. 添加记忆
    # 3. 搜索记忆
    # 4. 检查状态
    # 5. 验证结果
    pass
```

#### 部署流程

1. **开发环境**
   ```bash
   # 本地开发
   python start_api_service.py --dev
   ```

2. **测试环境**
   ```bash
   # 运行测试
   pytest tests/
   
   #