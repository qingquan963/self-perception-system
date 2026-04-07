# OpenClaw 自我感知系统备份

OpenClaw 的自我感知系统——向量记忆、DreamMode 做梦模式、上下文压缩、前置召回的完整备份。**已剥离所有敏感信息（API keys、tokens、personal paths）。**

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                     OpenClaw Gateway                     │
│                   (WebSocket Port 18789)                 │
└─────────────────────────────────────────────────────────┘
                            │
    ┌───────────┬───────────┬───────────┬──────────┐
    ▼           ▼           ▼           ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│  Agent │ │向量记忆│ │自我感知│ │做梦模式│ │压缩写入│
│  Team  │ │API Svc │ │ API    │ │DreamSvc│ │Compac- │
│        │ │8007    │ │ 8011   │ │ 8002   │ │tionWrtr│
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

## 核心服务端口映射

| 服务 | 端口 | 说明 |
|------|------|------|
| 向量记忆服务 | 8007 | 底层向量存储，ChromaDB |
| 自我感知 API | 8011 | 上层 API 网关 |
| 监控仪表盘 | 8090 | 可视化界面 |
| 做梦服务 | 8002 | DreamMode 关联分析 |
| 压缩写入服务 | 8014 | Compaction watcher |

## 记忆类型系统

| 类型 | 说明 | 默认过期 |
|------|------|---------|
| conversation | 会话记录 | 无 |
| knowledge | 知识 | 30天 |
| lesson | 深刻教训 | 永久 |
| task | 任务 | 无 |
| user_preference | 用户偏好 | 永久 |

## 目录结构

```
openclaw-self-perception/
├── openclaw-config/       # OpenClaw 核心配置（已脱敏）
│   ├── openclaw.json      # 主配置
│   └── cron_jobs.json     # 定时任务配置
├── agents/                 # Agent 角色定义
│   ├── architect/         # 架构师（只读不写）
│   ├── executor/          # 执行者（TDD）
│   ├── planner/           # 任务规划
│   ├── reviewer/          # 代码审查
│   ├── verifier/          # 验收测试
│   ├── debugger/          # 调试（DeepSeek）
│   ├── security-reviewer/ # 安全审查
│   ├── deployer/          # 部署
│   └── doc-writer/        # 文档
├── production/             # 自我感知系统 Python 代码
│   ├── data/vector_store/ # 向量存储核心代码
│   │   ├── vector_service.py
│   │   ├── dream_service.py
│   │   ├── DREAM_MODE_DESIGN.md
│   │   └── SERVICE_GOVERNANCE_DESIGN.md
│   └── config/            # 配置
└── workspace/
    └── self_perception_simple_clean/  # 完整自我感知系统
        ├── vector_service.py         # 向量服务
        ├── api_service.py            # API 网关
        ├── state_db.py               # 状态数据库
        ├── supervisor.py             # 进程监管
        ├── compaction_writer.py       # 压缩写入
        ├── watchdog.py                # 看门狗
        ├── auto_save.py              # 自动保存
        ├── dream_service.py           # 做梦服务
        ├── dream_association.py       # 关联分析
        ├── config_loader.py           # 配置加载
        ├── process_utils.py           # 进程工具
        ├── frontend_server.py         # 前端服务
        ├── requirements.txt
        ├── Dockerfile
        ├── docker-compose.yml
        └── README.md
```

## DreamMode 做梦模式

每天 13:30 自动触发，执行记忆关联分析：
- 扫描所有记忆类型（conversation/knowledge/lesson/task）
- 发现跨类型关联对
- 更新记忆关系网络
- 用 DeepSeek 生成关联摘要

## 向量记忆 API

```bash
# 写入记忆
curl -X POST http://127.0.0.1:8007/memories/add \
  -H "Content-Type: application/json" \
  -d '{"content": "...", "type": "conversation", "source": "user_said"}'

# 搜索记忆
curl "http://127.0.0.1:8007/memories/search?query=关键词&limit=5"

# 删除记忆
curl -X DELETE http://127.0.0.1:8007/memories/{id}

# 查看统计
curl http://127.0.0.1:8007/context/monitor
```

## 定时任务

| 任务 | 周期 | 说明 |
|------|------|------|
| 服务健康检查 | 30分钟 | 5大端口存活检查 |
| 做梦模式 | 每天13:30 | 关联记忆分析 |
| 运维早间巡检 | 每天8:00 | 端口+向量库+cron |
| 运维晚间巡检 | 每天21:00 | 全面健康检查 |

## 安全说明

- ✅ 所有 API keys 已替换为 `[REDACTED]`
- ✅ 所有 tokens 已替换为 `[REDACTED]`
- ✅ 所有 clientSecret 已替换为 `[REDACTED]`
- ✅ 所有 local paths 已替换为 `[REDACTED]`
- ✅ 向量数据库文件未包含（运行时数据）
- ✅ 日志文件未包含
- ✅ sessions 文件未包含
- ⚠️ cron jobs 中的任务消息内容已简化（不包含具体 token/paths）
