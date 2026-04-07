# 🧠 自我感知 + 做梦模式 整合系统

跨平台一键部署，集成了记忆系统所有核心模块。

---

## 📦 包含模块

| 模块 | 端口 | 说明 |
|------|------|------|
| 向量记忆服务 | 8007 | Chroma 向量数据库 API |
| 自我感知 API | 8011 | Token 监控、自动保存、上下文管理 |
| Compaction Writer | 8014 | 监听 session 摘要，自动写入向量库 |
| Dream Mode | 8001 | 做梦模式，记忆关联与整合 |
| 前端仪表板 | 8090 | Web 可视化监控面板 |

---

## 🚀 快速开始

### 方式一：Docker（推荐）

```bash
# 克隆项目后
docker compose up
```

服务就绪后访问：
- 仪表板：http://localhost:8090
- API 文档：http://localhost:8011/docs
- 向量服务：http://localhost:8007

### 方式二：直接运行（Linux / Mac）

```bash
chmod +x start.sh
./start.sh
```

### 方式三：Windows

```bat
start.bat
```

---

## ⚙️ 首次配置

1. 复制环境变量模板：
   ```bash
   cp .env.example .env
   ```

2. 编辑 `.env`，填入真实 API Key：
   ```env
   MINIMAX_API_KEY=your_real_key
   DEEPSEEK_API_KEY=your_real_key
   ```

3. 如果使用 Docker，将宿主机 OpenClaw 的 sessions 目录映射进去（docker-compose.yml 已配置）：
   ```yaml
   volumes:
     - ~/.openclaw/agents/main/sessions:/sessions:ro
   ```

---

## 🏗️ 架构

```
┌─────────────────────────────────────────────────┐
│  supervisor.py（进程管理器）                    │
│                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │api_service│ │vector_sv │ │compaction_wrt│   │
│  │  8011    │ │  8007    │ │    8014      │   │
│  └──────────┘ └──────────┘ └──────────────┘   │
│  ┌──────────┐ ┌──────────┐                    │
│  │dream_sv  │ │ frontend │                    │
│  │  8001    │ │  8090    │                    │
│  └──────────┘ └──────────┘                    │
└─────────────────────────────────────────────────┘
         ↕ 共享向量库 8007
┌──────────────────┐
│  Chroma SQLite    │
│  (向量数据库)     │
└──────────────────┘
```

---

## 🔧 目录结构

```
.
├── api_service.py          # 自我感知 API
├── vector_service.py        # 向量记忆服务
├── compaction_writer.py     # 摘要压缩写入
├── dream_service.py        # 做梦模式服务
├── dream_association.py    # 记忆关联脚本
├── frontend_server.py      # 仪表板前端
├── supervisor.py           # 进程管理器
├── watchdog.py             # 看门狗（双重守护）
├── config_loader.py         # 配置加载器
├── process_utils.py        # 跨平台进程工具
├── state_db.py             # 状态持久化
├── auto_save.py            # 自动保存模块
├── config/
│   └── services.yaml       # 服务列表配置
├── frontend/
│   └── (Web UI 文件)
├── data/
│   ├── logs/               # 日志目录
│   └── vector_store/        # 向量数据库文件
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🔄 启动流程

```
宿主机系统服务
    ↓
watchdog.py（看门狗，监控 supervisor 存活）
    ↓
supervisor.py（统一管理 5 个子服务）
    ↓
┌───────────────────────────────────────┐
│  api_service    ← Self-Perception API │
│  vector_service ← 向量记忆服务        │
│  compaction_wr  ← 摘要写入            │
│  dream_service  ← 做梦模式           │
│  frontend       ← Web 仪表板         │
└───────────────────────────────────────┘
```

---

## 🔒 安全说明

- `.env` 文件**不包含真实 Key**（已在 .gitignore 中排除）
- API Key 通过环境变量注入，不要硬编码
- 生产部署请务必修改所有默认端口和 Key

---

## 📋 配合 OpenClaw 使用

系统为 OpenClaw 提供记忆增强能力：

1. 向量记忆查询 → `POST http://localhost:8007/memories/search`
2. 自我感知状态 → `GET http://localhost:8011/context/status`
3. 做梦任务触发 → `POST http://localhost:8001/memories/dream/run`
4. Compaction 状态 → `GET http://localhost:8014/health`
