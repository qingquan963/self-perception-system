# API 文档

## 📋 概述

精简自我感知系统提供完整的RESTful API接口，支持记忆管理、系统监控、状态查询等功能。所有API均返回JSON格式数据。

## 🔗 基础信息

- **基础URL**: `http://localhost:8001` (API服务)
- **向量服务URL**: `http://localhost:8007` (向量服务)
- **API版本**: v1.0.0
- **响应格式**: JSON
- **认证**: 当前版本无需认证（开发环境）

## 📊 API端点索引

### 系统状态端点
| 端点 | 方法 | 描述 | 服务 |
|------|------|------|------|
| `/` | GET | 根端点，系统基本信息 | API |
| `/health` | GET | 健康检查 | API |
| `/context/status` | GET | 上下文状态 | API |

### 向量服务端点
| 端点 | 方法 | 描述 | 服务 |
|------|------|------|------|
| `/` | GET | 向量服务根端点 | 向量 |
| `/health` | GET | 向量服务健康检查 | 向量 |
| `/memories` | GET | 获取所有记忆 | 向量 |
| `/memories/search` | GET | 搜索记忆 | 向量 |
| `/memories/add` | POST | 添加记忆 | 向量 |
| `/stats` | GET | 获取统计信息 | 向量 |

## 🔍 详细端点说明

### 1. 系统状态端点

#### 1.1 根端点
```http
GET /
```

**描述**: 返回系统基本信息

**响应示例**:
```json
{
    "service": "Simple Self-Perception System API",
    "version": "1.0.0",
    "status": "running",
    "timestamp": "2026-03-28T22:52:00.123456"
}
```

#### 1.2 健康检查
```http
GET /health
```

**描述**: 检查系统健康状况

**响应示例**:
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

**状态码**:
- `200 OK`: 系统健康
- `503 Service Unavailable`: 系统异常

#### 1.3 上下文状态
```http
GET /context/status
```

**描述**: 获取当前会话上下文状态，包括Token使用情况

**响应示例**:
```json
{
    "token_usage_percentage": 39.06,
    "total_tokens": 128000,
    "used_tokens": 50000,
    "warning_level": "NORMAL",
    "timestamp": "2026-03-28T22:52:00.123456"
}
```

**字段说明**:
- `token_usage_percentage`: Token使用百分比
- `total_tokens`: 总Token数（默认128000）
- `used_tokens`: 已使用Token数
- `warning_level`: 警告级别（NORMAL/WARNING/CRITICAL）
- `timestamp`: 时间戳

### 2. 向量服务端点

#### 2.1 向量服务根端点
```http
GET http://localhost:8007/
```

**描述**: 向量服务基本信息

**响应示例**:
```json
{
    "service": "向量存储服务",
    "version": "1.0.0",
    "status": "running",
    "timestamp": "2026-03-28T22:52:00.123456"
}
```

#### 2.2 向量服务健康检查
```http
GET http://localhost:8007/health
```

**描述**: 检查向量服务健康状况

**响应示例**:
```json
{
    "status": "healthy",
    "service": "向量存储服务",
    "version": "1.0.0",
    "timestamp": "2026-03-28T22:52:00.123456",
    "memory_count": 9,
    "components": {
        "database": true,
        "storage": true
    }
}
```

**字段说明**:
- `memory_count`: 当前记忆数量
- `components.database`: 数据库状态
- `components.storage`: 存储状态

#### 2.3 获取所有记忆
```http
GET http://localhost:8007/memories
```

**查询参数**:
- `limit` (可选): 返回记录数，默认100，最大1000

**响应示例**:
```json
{
    "count": 9,
    "memories": [
        {
            "id": 1,
            "content": "用户喜欢喝咖啡",
            "vector": null,
            "metadata": {
                "source": "conversation",
                "category": "preference"
            },
            "vector_type": "conversation",
            "type": "preference",
            "type_name": "用户偏好",
            "importance": 2,
            "created_at": "2026-03-28T20:15:30",
            "updated_at": "2026-03-28T20:15:30"
        }
    ],
    "timestamp": "2026-03-28T22:52:00.123456"
}
```

#### 2.4 搜索记忆
```http
GET http://localhost:8007/memories/search
```

**查询参数**:
- `query` (必需): 搜索关键词
- `limit` (可选): 返回记录数，默认10，最大100

**响应示例**:
```json
{
    "query": "咖啡",
    "count": 1,
    "memories": [
        {
            "id": 1,
            "content": "用户喜欢喝咖啡",
            "metadata": {
                "source": "conversation",
                "category": "preference"
            },
            "type": "preference",
            "type_name": "用户偏好",
            "created_at": "2026-03-28T20:15:30"
        }
    ],
    "timestamp": "2026-03-28T22:52:00.123456"
}
```

#### 2.5 添加记忆
```http
POST http://localhost:8007/memories/add
Content-Type: application/json
```

**请求体**:
```json
{
    "id": "memory_123456789",  // 可选，不提供则自动生成
    "content": "用户喜欢喝茶",
    "type": "preference",
    "type_name": "用户偏好",
    "importance": 1,
    "metadata": {
        "source": "conversation",
        "category": "preference",
        "confidence": 0.8
    },
    "created_at": "2026-03-28T22:52:00",  // 可选
    "updated_at": "2026-03-28T22:52:00"   // 可选
}
```

**响应示例** (成功):
```json
{
    "status": "success",
    "message": "记忆添加成功",
    "memory_id": "memory_123456789",
    "timestamp": "2026-03-28T22:52:00.123456"
}
```

**响应示例** (失败):
```json
{
    "detail": "记忆添加失败"
}
```

**状态码**:
- `200 OK`: 添加成功
- `500 Internal Server Error`: 添加失败

#### 2.6 获取统计信息
```http
GET http://localhost:8007/stats
```

**描述**: 获取向量存储统计信息

**响应示例**:
```json
{
    "total_memories": 9,
    "timestamp": "2026-03-28T22:52:00.123456"
}
```

## 🛠️ 使用示例

### Python客户端示例

```python
import requests
import json

class SelfPerceptionClient:
    def __init__(self, base_url="http://localhost:8001", vector_url="http://localhost:8007"):
        self.base_url = base_url
        self.vector_url = vector_url
    
    def check_health(self):
        """检查系统健康状态"""
        response = requests.get(f"{self.base_url}/health")
        return response.json()
    
    def get_context_status(self):
        """获取上下文状态"""
        response = requests.get(f"{self.base_url}/context/status")
        return response.json()
    
    def add_memory(self, content, memory_type="conversation", importance=1, metadata=None):
        """添加记忆"""
        if metadata is None:
            metadata = {}
        
        memory_data = {
            "content": content,
            "type": memory_type,
            "type_name": "对话记忆",
            "importance": importance,
            "metadata": metadata
        }
        
        response = requests.post(
            f"{self.vector_url}/memories/add",
            json=memory_data,
            headers={"Content-Type": "application/json"}
        )
        
        return response.json()
    
    def search_memories(self, query, limit=10):
        """搜索记忆"""
        params = {
            "query": query,
            "limit": limit
        }
        
        response = requests.get(
            f"{self.vector_url}/memories/search",
            params=params
        )
        
        return response.json()
    
    def get_all_memories(self, limit=100):
        """获取所有记忆"""
        params = {"limit": limit}
        response = requests.get(f"{self.vector_url}/memories", params=params)
        return response.json()

# 使用示例
if __name__ == "__main__":
    client = SelfPerceptionClient()
    
    # 检查系统状态
    health = client.check_health()
    print(f"系统状态: {health['status']}")
    
    # 添加记忆
    result = client.add_memory(
        content="用户偏好使用Markdown格式",
        memory_type="preference",
        importance=2,
        metadata={"source": "observation", "confidence": 0.9}
    )
    print(f"添加记忆结果: {result}")
    
    # 搜索记忆
    search_results = client.search_memories("Markdown", limit=5)
    print(f"找到 {search_results['count']} 条相关记忆")
```

### cURL示例

```bash
# 检查系统健康
curl -X GET "http://localhost:8001/health"

# 获取上下文状态
curl -X GET "http://localhost:8001/context/status"

# 添加记忆
curl -X POST "http://localhost:8007/memories/add" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "用户经常在晚上工作",
    "type": "habit",
    "type_name": "用户习惯",
    "importance": 1,
    "metadata": {
      "source": "observation",
      "time_pattern": "night"
    }
  }'

# 搜索记忆
curl -X GET "http://localhost:8007/memories/search?query=晚上&limit=5"

# 获取所有记忆
curl -X GET "http://localhost:8007/memories?limit=50"
```

### JavaScript/Node.js示例

```javascript
const axios = require('axios');

class SelfPerceptionClient {
    constructor(baseUrl = 'http://localhost:8001', vectorUrl = 'http://localhost:8007') {
        this.baseUrl = baseUrl;
        this.vectorUrl = vectorUrl;
        this.axios = axios.create({
            timeout: 10000,
            headers: {
                'Content-Type': 'application/json'
            }
        });
    }

    async checkHealth() {
        const response = await this.axios.get(`${this.baseUrl}/health`);
        return response.data;
    }

    async getContextStatus() {
        const response = await this.axios.get(`${this.baseUrl}/context/status`);
        return response.data;
    }

    async addMemory(content, options = {}) {
        const {
            type = 'conversation',
            typeName = '对话记忆',
            importance = 1,
            metadata = {}
        } = options;

        const memoryData = {
            content,
            type,
            type_name: typeName,
            importance,
            metadata
        };

        const response = await this.axios.post(
            `${this.vectorUrl}/memories/add`,
            memoryData
        );

        return response.data;
    }

    async searchMemories(query, limit = 10) {
        const response = await this.axios.get(`${this.vectorUrl}/memories/search`, {
            params: { query, limit }
        });
        return response.data;
    }

    async getAllMemories(limit = 100) {
        const response = await this.axios.get(`${this.vectorUrl}/memories`, {
            params: { limit }
        });
        return response.data;
    }
}

// 使用示例
async function main() {
    const client = new SelfPerceptionClient();
    
    try {
        // 检查系统状态
        const health = await client.checkHealth();
        console.log('系统状态:', health.status);
        
        // 添加记忆
        const addResult = await client.addMemory('用户喜欢自动化工具', {
            type: 'preference',
            typeName: '用户偏好',
            importance: 2,
            metadata: { source: 'conversation', category: 'tools' }
        });
        console.log('添加记忆结果:', addResult);
        
        // 搜索记忆
        const searchResults = await client.searchMemories('自动化', 5);
        console.log(`找到 ${searchResults.count} 条相关记忆`);
        
    } catch (error) {
        console.error('API调用错误:', error.message);
    }
}

main();
```

## ⚠️ 错误处理

### 错误响应格式

所有错误都返回标准化的错误响应：

```json
{
    "detail": "错误描述信息",
    "error_code": "ERROR_CODE",  // 可选
    "timestamp": "2026-03-28T22:52:00.123456"
}
```

### 常见错误码

| 状态码 | 错误码 | 描述 | 解决方案 |
|--------|--------|------|----------|
| 400 | `INVALID_REQUEST` | 请求参数无效 | 检查请求参数格式 |
| 404 | `ENDPOINT_NOT_FOUND` | 端点不存在 | 检查URL路径 |
| 500 | `INTERNAL_ERROR` | 服务器内部错误 | 查看服务器日志 |
| 503 | `SERVICE_UNAVAILABLE` | 服务不可用 | 检查服务是否启动 |

### 重试策略

建议在遇到以下错误时实施重试策略：

1. **网络错误** (5xx状态码): 等待1秒后重试，最多3次
2. **速率限制** (429状态码): 等待指定时间后重试
3. **服务不可用** (503状态码): 等待5秒后重试，最多2次

## 📈 性能指标

### 响应时间

| 端点 | 平均响应时间 | 95%响应时间 |
|------|--------------|-------------|
| `/health` | < 50ms | < 100ms |
| `/context/status` | < 100ms | < 200ms |
| `/memories/search` | < 200ms | < 500ms |
| `/memories/add` | < 300ms | < 800ms |

### 吞吐量

- **最大并发连接数**: 100
- **QPS (查询每秒)**: 支持50-100 QPS
- **数据大小限制**: 请求体最大1MB，响应体最大10MB

## 🔐 安全建议

### 生产环境部署

1. **启用认证**:
   ```python
   # 在api_service.py中添加认证中间件
   from fastapi.security import HTTPBearer
   
   security = HTTPBearer()
   
   @app.get("/protected")
   async def protected_endpoint(token: str = Depends(security)):
       # 验证token
       pass
   ```

2. **限制访问**:
   ```python
   # 配置CORS白名单
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://your-domain.com"],  # 只允许特定域名
       allow_credentials=True,
       allow_methods=["GET", "POST"],
       allow_headers=["*"],
   )
   ```

3. **启用HTTPS**:
   ```python
   # 使用SSL证书
   uvicorn.run(
       app,
       host="0.0.0.0",
       port=8001,
       ssl_keyfile="key.pem",
       ssl_certfile="cert.pem"
   )
   ```

### 监控和日志

1. **启用访问日志**:
   ```python
   import logging
   
   logging.basicConfig(
       level=logging.INFO,
       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
       handlers=[
           logging.FileHandler('api_access.log'),
           logging.StreamHandler()
       ]
   )
   ```

2. **监控API使用**:
   - 记录每个端点的调用次数
   - 监控响应时间
   - 跟踪错误率

## 🔄 版本管理

### API版本控制

系统使用URL路径版本控制：

```
http://localhost:8001/v1/health
http://localhost:8007/v1/memories
```

### 向后兼容性

- 新版本API保持向后兼容
- 废弃的端点标记为`deprecated`
- 提供迁移指南

### 版本发布说明

**v1.0.0** (当前版本)
- 初始版本发布
- 基础记忆管理功能
- 系统监控API
- 向量存储服务

## 📞 支持与反馈

如有问题或建议，请：

1. **查看日志文件**: `api_service.log`, `vector_service.log`
2. **检查系统状态**: 访问 `/health` 端点
3. **提交问题**: 通过GitHub Issues或联系系统管理员

---

*最后更新: 202