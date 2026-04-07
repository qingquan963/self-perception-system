# 管理员指南

## 📋 目录

1. [系统架构详解](#系统架构详解)
2. [安装部署指南](#安装部署指南)
3. [服务配置管理](#服务配置管理)
4. [监控和维护](#监控和维护)
5. [备份和恢复](#备份和恢复)
6. [性能优化](#性能优化)
7. [安全加固](#安全加固)
8. [故障排查](#故障排查)
9. [升级和迁移](#升级和迁移)

## 🏗️ 系统架构详解

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                   用户界面层                                │
│                   • 前端仪表板 (8080)                       │
│                   • API客户端                               │
│                   • 命令行工具                              │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                   API网关层                                 │
│                   • FastAPI应用 (8001)                      │
│                   • 请求路由和验证                          │
│                   • 响应格式化                              │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                   业务逻辑层                                │
│                   • 会话监控 (session_monitor.py)           │
│                   • 上下文预警 (context_alert.py)           │
│                   • 向量服务 (vector_service.py)            │
│                   • 功能模块 (modules/)                     │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                   数据访问层                                │
│                   • SQLite数据库连接                        │
│                   • JSON文件操作                            │
│                   • 向量存储管理                            │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                   数据存储层                                │
│                   • SQLite数据库 (vectors.db)               │
│                   • JSON记忆文件 (vector_store/)            │
│                   • 配置文件 (.env, config.json)            │
│                   • 日志文件                                │
└─────────────────────────────────────────────────────────────┘
```

### 组件详细说明

#### 1. API服务 (api_service.py)
- **端口**: 8001
- **框架**: FastAPI
- **功能**: 
  - 提供系统状态查询接口
  - 处理健康检查请求
  - 返回上下文状态信息
  - 作为系统入口点

#### 2. 向量服务 (vector_service.py)
- **端口**: 8007
- **框架**: FastAPI + SQLite
- **功能**:
  - 记忆的存储和检索
  - 向量化搜索（简化版）
  - 记忆统计和管理
  - 数据库操作封装

#### 3. 会话监控 (session_monitor.py)
- **类型**: 后台服务
- **功能**:
  - 监控Token使用情况
  - 计算会话持续时间
  - 提供Token使用统计

#### 4. 上下文预警 (context_alert.py)
- **类型**: 预警系统
- **功能**:
  - 检查Token使用率阈值
  - 生成预警消息
  - 提供预警级别判断

#### 5. 功能模块 (modules/)
- **conversation_memory.py**: 对话记忆管理
- **task_tracker.py**: 任务跟踪和管理
- **decision_recorder.py**: 决策记录
- **learning_feedback.py**: 学习反馈
- **capability_assessment.py**: 能力评估

### 数据流说明

```
用户请求 → API网关 → 业务逻辑处理 → 数据访问 → 数据存储
    ↑           ↓           ↓           ↓           ↓
用户响应 ← 响应格式化 ← 结果处理 ← 数据查询 ← 数据读取
```

## 🚀 安装部署指南

### 环境要求

#### 硬件要求
- **CPU**: 1核心以上
- **内存**: 512MB以上
- **存储**: 100MB可用空间
- **网络**: 本地网络访问

#### 软件要求
- **操作系统**: Windows 10+, Linux, macOS
- **Python**: 3.8或更高版本
- **包管理器**: pip 20.0+
- **数据库**: SQLite3 (Python内置)

#### 网络要求
- **端口**: 8001, 8007, 8080 需要开放
- **防火墙**: 允许本地回环访问
- **代理**: 如需访问外部API，需要配置代理

### 全新安装步骤

#### 步骤1：环境准备

```bash
# 1. 创建项目目录
mkdir -p /opt/self_perception
cd /opt/self_perception

# 2. 克隆或下载代码
git clone <repository-url> self_perception_simple_clean
# 或解压下载的代码包
# tar -xzf self_perception_simple_clean.tar.gz

# 3. 进入项目目录
cd self_perception_simple_clean
```

#### 步骤2：Python环境设置

```bash
# 1. 创建虚拟环境（推荐）
python -m venv venv

# 2. 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# 3. 升级pip
python -m pip install --upgrade pip
```

#### 步骤3：安装依赖

```bash
# 1. 安装基础依赖
pip install -r requirements.txt

# 2. 验证安装
python -c "import fastapi; print(f'FastAPI版本: {fastapi.__version__}')"
python -c "import uvicorn; print(f'Uvicorn版本: {uvicorn.__version__}')"
```

#### 步骤4：配置文件设置

```bash
# 1. 复制环境变量模板
cp .env.example .env

# 2. 编辑配置文件
# Windows
notepad .env
# Linux/macOS
nano .env
```

编辑`.env`文件，至少设置以下内容：

```env
# 必须配置
DEEPSEEK_API_KEY=sk-your-actual-api-key-here

# 可选配置（根据需求调整）
TOKEN_WARNING_THRESHOLD=80
TOKEN_CRITICAL_THRESHOLD=90
MAX_CONTEXT_TOKENS=128000
```

#### 步骤5：数据库初始化

```bash
# 1. 运行数据库初始化脚本
python create_clean_db.py

# 2. 验证数据库
python check_db.py

# 3. 导入初始记忆数据（可选）
python import_initial_memories.py
```

#### 步骤6：启动服务

```bash
# 方法1：使用启动脚本（推荐）
.\start_all_services.ps1  # Windows
./start_all_services.sh   # Linux/macOS

# 方法2：手动启动
# 终端1：启动API服务
python start_api_service.py

# 终端2：启动向量服务  
python vector_service.py

# 终端3：启动前端服务
python -m http.server 8080 -d frontend
```

#### 步骤7：验证安装

```bash
# 检查服务状态
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8007/health

# 检查前端
curl -I http://localhost:8080
```

### Docker部署

#### Dockerfile

创建 `Dockerfile`：

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p /data && chmod 777 /data

# 环境变量
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/data

# 暴露端口
EXPOSE 8001 8007 8080

# 启动命令
CMD ["python", "start_all_services.py"]
```

#### Docker Compose配置

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  self-perception:
    build: .
    container_name: self-perception-system
    ports:
      - "8001:8001"  # API服务
      - "8007:8007"  # 向量服务
      - "8080:8080"  # 前端服务
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - DATA_DIR=/data
    volumes:
      - ./data:/data  # 数据持久化
      - ./logs:/app/logs  # 日志持久化
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### 构建和运行

```bash
# 1. 构建镜像
docker-compose build

# 2. 设置环境变量
export DEEPSEEK_API_KEY=your-api-key

# 3. 启动服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f

# 5. 停止服务
docker-compose down
```

### 生产环境部署

#### 使用Systemd（Linux）

创建服务文件 `/etc/systemd/system/self-perception.service`：

```ini
[Unit]
Description=Self Perception System
After=network.target

[Service]
Type=simple
User=selfperception
Group=selfperception
WorkingDirectory=/opt/self_perception/self_perception_simple_clean
Environment="PATH=/opt/self_perception/venv/bin"
Environment="DEEPSEEK_API_KEY=your-api-key"
ExecStart=/opt/self_perception/venv/bin/python start_all_services.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

启用和启动服务：

```bash
# 创建系统用户
sudo useradd -r -s /bin/false selfperception

# 设置目录权限
sudo chown -R selfperception:selfperception /opt/self_perception

# 重新加载systemd
sudo systemctl daemon-reload

# 启用服务
sudo systemctl enable self-perception

# 启动服务
sudo systemctl start self-perception

# 查看状态
sudo systemctl status self-perception

# 查看日志
sudo journalctl -u self-perception -f
```

#### 使用Nginx反向代理

创建Nginx配置 `/etc/nginx/sites-available/self-perception`：

```nginx
upstream api_backend {
    server 127.0.0.1:8001;
}

upstream vector_backend {
    server 127.0.0.1:8007;
}

upstream frontend_backend {
    server 127.0.0.1:8080;
}

server {
    listen 80;
    server_name self-perception.your-domain.com;
    
    # API服务
    location /api/ {
        proxy_pass http://api_backend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # 向量服务
    location /vector/ {
        proxy_pass http://vector_backend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # 前端服务
    location / {
        proxy_pass http://frontend_backend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # 静态文件缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

启用配置：

```bash
# 创建符号链接
sudo ln -s /etc/nginx/sites-available/self-perception /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重新加载Nginx
sudo systemctl reload nginx
```

## ⚙️ 服务配置管理

### 配置文件详解

#### 1. 环境变量文件 (.env)

```env
# ====================
# API配置
# ====================
DEEPSEEK_API_KEY=sk-your-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# ====================
# Token监控配置
# ====================
TOKEN_MONITOR_ENABLED=true
TOKEN_WARNING_THRESHOLD=80      # 警告阈值百分比
TOKEN_CLEANUP_THRESHOLD=85      # 清理触发阈值
TOKEN_CRITICAL_THRESHOLD=90     # 严重警告阈值
MAX_CONTEXT_TOKENS=128000       # 最大上下文Token数

# ====================
# 系统配置
# ====================
SELF_PERCEPTION_SYSTEM=true
VECTOR_SERVICE_PORT=8007
API_SERVICE_PORT=8001
FRONTEND_PORT=8080

# ====================
# 数据库配置
# ====================
DATABASE_PATH=vectors.db
BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=24

# ====================
# 日志配置
# ====================
LOG_LEVEL=INFO
LOG_FILE=system.log
LOG_MAX_SIZE_MB=10
LOG_BACKUP_COUNT=5

# ====================
# 性能配置
# ====================
WORKER_COUNT=1
MAX_CONNECTIONS=100
REQUEST_TIMEOUT=30
```

#### 2. 系统配置文件 (config.json)

```json
{
    "system": {
        "name": "精简自我感知系统",
        "version": "1.0.0",
        "description": "精简的记忆和自我感知系统",
        "environment": "production",
        "debug": false
    },
    "services": {
        "api": {
            "port": 8001,
            "host": "0.0.0.0",
            "workers": 1,
            "reload": false
        },
        "vector": {
            "port": 8007,
            "host": "0.0.0.0",
            "database": "vectors.db",
            "max_connections": 10
        },
        "frontend": {
            "port": 8080,
            "host": "0.0.0.0",
            "directory": "frontend"
        }
    },
    "memory": {
        "max_memories": 1000,
        "auto_cleanup": true,
        "cleanup_threshold": 800,
        "backup_enabled": true,
        "backup_directory": "backups",
        "retention_days": 30
    },
    "monitoring": {
        "enabled": true,
        "interval_seconds": 60,
        "alert_channels": ["log", "email"],
        "email_notifications": {
            "enabled": false,
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "sender_email": "alerts@example.com",
            "recipient_emails": ["admin@example.com"]
        }
    },
    "security": {
        "cors_origins": ["http://localhost:8080"],
        "rate_limiting": {
            "enabled": true,
            "requests_per_minute": 60
        },
        "authentication": {
            "enabled": false,
            "api_keys": ["default-key"]
        }
    }
}
```

### 配置管理最佳实践

#### 1. 环境特定的配置

创建不同环境的配置文件：

```bash
# 开发环境
cp .env.example .env.development

# 测试环境  
cp .env.example .env.test

# 生产环境
cp .env.example .env.production
```

使用环境变量指定配置：

```bash
# 启动时指定环境
ENV=production python start_all_services.py
```

#### 2. 配置验证脚本

创建 `validate_config.py`：

```python
#!/usr/bin/env python3
"""
配置验证脚本
"""

import os
import json
from dotenv import load_dotenv

def validate_env_config():
    """验证环境变量配置"""
    required_vars = [
        'DEEPSEEK_API_KEY',
        'API_SERVICE_PORT',
        'VECTOR_SERVICE_PORT'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ 缺少必需的环境变量: {', '.join(missing_vars)}")
        return False
    
    # 验证端口范围
    try:
        api_port = int(os.getenv('API_SERVICE_PORT', '8001'))
        vector_port = int(os.getenv('VECTOR_SERVICE_PORT', '8007'))
        
        if not (1024 <= api_port <= 65535):
            print(f"❌ API端口超出范围: {api_port}")
            return False
            
        if api_port == vector_port:
            print("❌ API端口和向量服务端口不能相同")
