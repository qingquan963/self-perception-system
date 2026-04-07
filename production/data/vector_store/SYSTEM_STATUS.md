# 自我感知系统（OpenClaw 生态系统）现状报告

> 生成时间：2026-04-07 18:49 GMT+8  
> 架构师：Architect Agent  
> 数据来源：实际进程检查 + 服务健康检查 + jobs.json

---

## 一、服务端口映射（已验证）

| 端口 | 绑定地址 | PID | 进程 | 服务名称 | 健康状态 |
|------|----------|-----|------|----------|----------|
| **8001** | 0.0.0.0 | 4252 | `svchost.exe` | ❓ Windows系统服务（非Python，无法HTTP访问） | N/A（不可用） |
| **8002** | 0.0.0.0 | 12196 | `python.exe` | DreamMode 做梦服务（dream_service.py） | ✅ Idle |
| **8007** | 0.0.0.0 | 13624 | `python.exe` | 向量记忆服务（vector_service.py） | ✅ Healthy（v2.1.0，81条记忆） |
| **8007** | 127.0.0.1 | 10052 | `python.exe` | 向量记忆服务（副本/重定向） | ✅ 同上 |
| **8011** | 127.0.0.1 | 7300 | `python.exe` | **自我感知系统API**（api_service.py） | ✅ Healthy（v1.0.0） |
| **8014** | 127.0.0.1 | 2532 | `python.exe` | 向量压缩写入端（compaction_writer.py） | ✅ Healthy（启动略慢） |
| **8090** | 0.0.0.0 | 9972 | `python.exe` | Dashboard前端（frontend_server.py） | ✅ 200 OK（HTML页面） |
| **8090** | 127.0.0.1 | 15084 | `python.exe` | Dashboard（副本） | ✅ 同上 |

### ⚠️ 重要修正

**原文档错误**（DREAM_MODE_DESIGN.md 旧版）：
- ❌ 8001 = 自我感知API
- ❌ dream_service 端口 = 8001

**实际配置**：
- ✅ 8001 = Windows svchost（非服务组件，无需关注）
- ✅ **自我感知API = 8011**（api_service.py，FastAPI）
- ✅ **DreamMode = 8002**（dream_service.py，FastAPI）

---

## 二、服务功能说明

### 2.1 向量记忆服务（8007）
- **进程**：`vector_service.py`（Python + sentence-transformers）
- **版本**：v2.1.0
- **向量模型**：`paraphrase-multilingual-MiniLM-L12-v2`
- **向量库**：ChromaDB（SQLite 后端）
- **功能**：
  - 记忆存取（CRUD）
  - 向量化（embedding）
  - 相似度召回（recall）
  - 自动去重写入（写入时检测相似度）
  - 重要性自动评分（1-5分）
  - 过期机制（knowledge 类型支持 expire_at）
- **当前状态**：81条记忆，运行健康

### 2.2 自我感知系统 API（8011）
- **进程**：`api_service.py`（FastAPI + uvicorn）
- **版本**：1.0.0
- **功能**：
  - Session 上下文监控（token 阈值检测）
  - 自动保存触发（auto_save.py）
  - 上下文压缩（auto-cleanup）
  - `/health` 健康检查（返回 `components: {api: true, context_alert: true}`）
- **阈值配置**：`TOKEN_WARNING_THRESHOLD=80%`，`TOKEN_CRITICAL_THRESHOLD=90%`
- **与 8007 关系**：通过 HTTP API 操作向量库

### 2.3 向量压缩写入端（8014）
- **进程**：`compaction_writer.py`（Python 内置 HTTPServer）
- **功能**：
  - 监控 session compaction 摘要
  - 自动将摘要写入向量库（type=conversation）
  - 提供 `/health` 健康检查
- **当前状态**：`total_written: 0`（暂无写入）

### 2.4 DreamMode 做梦服务（8002）
- **进程**：`dream_service.py`（FastAPI）
- **版本**：通过 dream_state.json 管理
- **功能模块**：
  - **Deduplicator**：查重去重（动态阈值：短文本0.95，中等0.92，长0.88）
  - **Denoiser**：降噪优化（软删除/硬删除低重要性记忆）
  - **Merger**：同类记忆合并（需 LLM）
  - **Structurer**：结构化梳理（需 LLM）
- **当前状态**：Idle，上次运行 2026-04-07 17:52:56（24秒完成）
  - 最近一次运行：删除了 3 条重复记忆 + 4 条降噪记忆
- **触发方式**：每天 13:30（cron `30 13 * * *`，Asia/Shanghai）

### 2.5 Dashboard 前端（8090）
- **进程**：`frontend_server.py`（Python 内置 http.server）
- **功能**：提供 Web Dashboard UI
- **当前状态**：运行中，返回 HTML 页面

---

## 三、OpenClaw cron 定时任务

> 数据来源：`C:\Users\Administrator\.openclaw\cron\jobs.json`

| 任务名称 | ID | 触发规则 | 状态 | 最后运行 | 功能 |
|----------|----|----------|------|----------|------|
| 贴吧心跳-龙虾小兵 | 7345c700 | 每2小时 | ✅ 运行中 | 刚执行 | 贴吧消息回复+互动 |
| 服务健康检查 | f8a8a39f | 每30分钟 | ✅ 正常 | 刚执行 | 检查5大服务端口 |
| **做梦模式-空闲触发** | fabe6ef2 | **每天13:30** | ✅ 正常 | 今天13:30 | 运行 dream_association.py |
| 运维巡逻-早间检查 | b5e98edb | 每天08:00 | ✅ 正常 | 今天08:00 | 端口+向量库+做梦任务检查 |
| 运维巡逻-晚间检查 | 9df0f03b | 每天21:00 | ✅ 正常 | — | 同早间检查 |
| 币安数据采集 | b550c32b | 每5分钟 | ❌ **已禁用** | — | 币安K线数据采集 |

---

## 四、做梦模式最近运行报告

> 数据来源：`dream_state.json`（2026-04-07 17:52:56 执行）

```json
{
  "run_id": "c6b2cb0e-0b37-4de0-b808-bbba1f6e82c9",
  "duration_seconds": 24.16,
  "phases": {
    "deduplicator": {
      "candidates": 95,
      "duplicates_found": 3,
      "deleted_ids": ["234", "221", "194"]
    },
    "denoiser": {
      "candidates": 92,
      "hard_deleted": ["185", "181", "179", "175"]
    }
  },
  "summary": {
    "total_deleted": 7,
    "total_soft_deleted": 0,
    "total_hard_deleted": 4
  }
}
```

---

## 五、端口 8001 问题说明

**8001 端口由 `svchost.exe`（PID 4252）监听**，这是 Windows 系统服务，不是 Python 应用。

- **无法通过 HTTP 访问**（超时）
- **不是自我感知 API**（自我感知 API 实际在 8011）
- **DreamMode 不在 8001**（实际在 8002）
- 原文档 DREAM_MODE_DESIGN.md 中服务治理设计将 dream_service 标为 8001 是错误的

**可能原因**：8001 曾被用作 dream_service 端口，后迁移到 8002，但文档未同步更新。

---

## 六、与 OpenClaw 的集成方式

```
OpenClaw Gateway（WebSocket）
    │
    ├── 主会话（agent:main:main）
    │       └── auto_save.py → 上下文监控 → 8011 API
    │                              └── 阈值触发 → 自动保存到 8007
    │
    ├── cron 触发器（jobs.json）
    │       ├── 服务健康检查（每30分钟）
    │       ├── 做梦模式（每天13:30）→ 8002 /memories/dream/run
    │       ├── 运维巡逻（早08:00 / 晚21:00）
    │       └── 贴吧心跳（每2小时）
    │
    └── 向量召回
            └── 8007 /memories/recall → 供给主会话上下文
```

---

## 七、遗留问题

| # | 问题 | 严重程度 | 建议处理 |
|---|------|----------|----------|
| 1 | 8001 端口用途不明（svchost 占用） | 低 | 确认是否为旧服务遗留，如无需保留可忽略 |
| 2 | 8014 compaction_writer total_written=0 | 低 | 可能是 session compaction 尚未产生数据，持续观察 |
| 3 | DREAM_MODE_DESIGN.md 中 cpu_threshold 旧值（0.3）vs 实际值（0.95） | 低 | 文档已更正 |
| 4 | 向量库当前 81 条记忆，较之前 102/73 条有所减少 | 信息 | 正常，dream 去重已生效 |

---

## 八、相关文件路径

```
C:\Users\Administrator\.openclaw\
├── production\data\vector_store\
│   ├── DREAM_MODE_DESIGN.md          # 做梦模式设计文档
│   ├── SYSTEM_STATUS.md              # 本文件
│   ├── dream_service.py              # 做梦服务（端口8002）
│   ├── vector_service.py             # 向量库服务（端口8007）
│   ├── dream_state.json              # 做梦状态
│   └── logs\dream\                  # 做梦日志
├── workspace\self_perception_simple_clean\
│   ├── api_service.py               # 自我感知API（端口8011）
│   ├── compaction_writer.py         # 压缩写入（端口8014）
│   ├── frontend_server.py            # Dashboard（端口8090）
│   ├── auto_save.py                  # 自动保存
│   └── dream_association.py          # 关联分析脚本
├── cron\jobs.json                    # OpenClaw cron任务配置
└── openclaw.json                    # OpenClaw 主配置
```
