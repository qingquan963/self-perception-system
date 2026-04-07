# 做梦模式（Dream Maintenance）完整设计方案

> 架构师: Architect Agent | 日期: 2026-04-04 | 状态: 设计完成 | **更新: 2026-04-07**（端口映射已纠正）

> ⚠️ **2026-04-07 重大修正**：
> - 原文档将 dream_service 误标为端口 8001，实际运行在 **8002**
> - 自我感知 API（api_service）运行在 **8011**，非 8001
> - 定时触发已更新为 cron `"30 13 * * *"`（每天 13:30，即下午1:30）
> - 下方 2.2 节 API 端点路径已更新为实际地址

---

## 一、现状调研

### 1.1 当前向量库基本情况

| 指标 | 数值 |
|------|------|
| 服务版本 | v2.1.0 |
| 总记忆数（清理前） | 102 |
| 总记忆数（清理后） | 73 |
| 清理删除数 | 29（均为过期/无效） |
| 向量化率 | 98.6%（72/73） |
| 平均访问次数 | 0.2次 |
| 最大访问次数 | 12次 |

### 1.2 记忆类型分布

| 类型 | 数量 | 占比 | 说明 |
|------|------|------|------|
| conversation | 42 | 41.2% | 会话记录 |
| knowledge | 27 | 26.5% | 知识（30天过期） |
| lesson | 23 | 22.5% | 教训（永久） |
| task | 8 | 7.8% | 任务（无过期） |
| user_preference | 2 | 2.0% | 用户偏好（永久） |

### 1.3 记忆来源分布

| 来源 | 数量 | 说明 |
|------|------|------|
| auto_important_keyword | 27 | 关键词触发重要信息 |
| auto_decision_keyword | 20 | 决策类关键词 |
| auto_topic_switch | 20 | 话题切换触发 |
| auto_timer | 16 | 30分钟定时保存 |
| ai_summary | 5 | AI摘要 |
| user_said | 5 | 用户直接说 |
| system | 4 | 系统生成 |
| user_command | 2 | 用户命令 |
| unknown | 1 | 来源不明 |
| auto_compaction | 2 | 自动压缩 |

### 1.4 明显问题识别

**问题1：高度碎片化**
- 同一话题被多次自动保存（如"文件列表"在10分钟内被保存了20次）
- auto_timer 触发的记忆大量是原始对话转储，内容冗长（单个记忆最高2444字符）
- auto_topic_switch 在2026-04-03一天内产生55条记录

**问题2：记忆利用率极低**
- 平均访问0.2次，83%的记忆从未被 recall 命中
- 大部分自动保存的内容没有被实际使用
- 访问次数最高的记忆也只有12次

**问题3：无去重合并机制**
- `/memories/cleanup` 仅做过期删除，不做相似度去重
- 无跨记忆的同类信息合并能力
- 高达20个 auto_decision_keyword 记忆可能包含大量重复决策

**问题4：知识类记忆过期无感知刷新**
- 27条 expiring count 但无刷新机制
- 过期的 knowledge 类记忆直接被删，不尝试更新

**问题5：1条记录未向量化**
- 数据质量问题

---

## 二、系统架构

### 2.1 整体架构

```
                    ┌─────────────────────────────────┐
                    │     Dream Maintenance Engine     │
                    │   (做梦模式 - 后台整理引擎)        │
                    └─────────────────────────────────┘
                                     │
          ┌──────────────────────────┼──────────────────────────┐
          ▼                          ▼                          ▼
   ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
   │ Deduplicator  │          │   Merger     │          │  Structurer  │
   │   查重去重     │          │  同类记忆合并  │          │  结构化梳理   │
   └──────────────┘          └──────────────┘          └──────────────┘
          │                          │                          │
          └──────────────────────────┼──────────────────────────┘
                                     ▼
                            ┌──────────────┐
                            │  Denoiser     │
                            │   降噪优化    │
                            └──────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
           ┌──────────────┐                    ┌──────────────┐
           │  ChromaDB    │                    │   8007 API   │
           │ memory_store │                    │  向量库服务   │
           └──────────────┘                    └──────────────┘
```

### 2.2 API 端点设计

> **实际服务地址**：`http://127.0.0.1:8002`（dream_service.py，PID 12196）

```
POST http://127.0.0.1:8002/memories/dream/run          # 手动触发做梦
GET  http://127.0.0.1:8002/memories/dream/status       # 查看运行状态
GET  http://127.0.0.1:8002/memories/dream/report       # 查看上次运行报告
POST http://127.0.0.1:8002/memories/dream/stop         # 停止正在运行的做梦任务

配置端点（均支持 GET/PUT）:
GET/PUT http://127.0.0.1:8002/memories/dream/config    # 整体配置
```

### 2.3 做梦配置数据模型

```python
class DreamConfig(BaseModel):
    enabled: bool = True
    
    # 触发机制
    trigger: Dict[str, Any] = {
        "schedule": "0 3 * * *",      # 默认凌晨3点
        "token_threshold": 0.85,       # Token 85% 触发（与auto_cleanup协同）
        "idle_trigger": True,          # 设备空闲触发
        "idle_minutes": 30,           # 空闲30分钟视为空闲
        "manual": True,               # 允许手动触发
    }
    
    # 执行策略
    execution: Dict[str, Any] = {
        "max_duration_minutes": 20,   # 单次最长执行20分钟（缩短）
        "batch_size": 30,             # 每批处理30条记忆（减小）
        "concurrency": 2,              # 最大并发2
        "dry_run": False,              # 默认真实执行
        "cpu_threshold": 0.3,          # CPU占用上限30%
        "memory_threshold_mb": 500,    # 内存占用上限500MB
    }
    
    # 各模块开关
    modules: Dict[str, bool] = {
        "deduplicator": True,         # 查重去重
        "merger": True,               # 同类合并
        "structurer": True,           # 结构化梳理
        "denoiser": True,             # 降噪优化
    }
    
    # 各模块阈值（动态阈值，按文本长度自适应）
    thresholds: Dict[str, Any] = {
        # 动态去重相似度阈值
        "dedup_similarity": {
            "short": 0.95,      # 短文本(<50字)
            "medium": 0.92,     # 中等文本(50-500字)
            "long": 0.88,       # 长文本(>500字)
        },
        # 动态合并相似度阈值
        "merge_similarity": {
            "short": 0.85,      # 短文本(<50字)
            "medium": 0.78,     # 中等文本(50-500字)
            "long": 0.75,       # 长文本(>500字)
        },
        "min_importance": 3,          # 最低重要性（低于此软删除）
        "max_age_days": 90,           # 最大保留天数（可配置）
        "min_content_length": 10,     # 最小内容长度
        "llm_merge_monthly_budget": 100,  # LLM合并每月预算（次）
        "llm_merge_priority_importance": 5,  # LLM合并优先 importance≥5
    }
```

---

## 三、核心逻辑设计

### 3.1 查重去重（Deduplicator）

**目标**：发现并处理高相似度记忆，保留最优者

**算法**：
```
1. 获取所有记忆（分批，每批50条）
2. 对每条记忆计算向量
3. 两两比对（只比对同类型记忆）
   - 相似度 > 0.92 → 重复候选
   - 相似度 > 0.78 AND < 0.92 → 合并候选
4. 对重复候选：
   - 保留 importance 最高者
   - 保留 access_count 最高者
   - 保留 created_at 最新者
5. 删除被标记为"重复"的记忆
```

**分层保护策略**：
```
importance ≥ 9：完全保护，不参与任何自动操作（删除/合并）
importance ≥ 7：只参与去重，不参与删除（可被合并但不会被删除）
importance ≥ 5：参与所有操作，软删除缓冲期 14 天
importance < 5：参与所有操作，软删除缓冲期 7 天
```

**动态阈值决策树**（根据文本长度自适应）：
```
文本长度 < 50字
    ├── 相似度 ≥ 0.95 → 重复候选，保留最优1条
    └── 0.85 ≤ 相似度 < 0.95 → 合并候选
    
50字 ≤ 文本长度 ≤ 500字
    ├── 相似度 ≥ 0.92 → 重复候选，保留最优1条
    └── 0.78 ≤ 相似度 < 0.92 → 合并候选
    
文本长度 > 500字
    ├── 相似度 ≥ 0.88 → 重复候选，保留最优1条
    └── 0.75 ≤ 相似度 < 0.88 → 合并候选

重复保留策略（优先级从高到低）：
1. importance 最高
2. access_count 最高
3. created_at 最新
```

### 3.2 同类记忆合并（Merger）

**目标**：将同一话题的多个片段整合为一个完整记忆

**触发条件**：
- 同一类型（type）
- 相似度在动态阈值范围内（见 Deduplicator）
- 时间跨度 < 14天（扩大窗口）
- 至少有2条候选（原3条，降低门槛）
- 优先处理 importance ≥ 5 的记忆

**合并策略**：
```
输入：[记忆A, 记忆B, 记忆C]（同一话题）

1. 按 created_at 排序
2. 提取各记忆的核心信息（去重填充）
3. 用 LLM 生成合并摘要：
   Prompt: "将以下关于同一话题的记忆片段合并为一个连贯的总结：
   [片段1]...
   [片段2]...
   [片段3]..."
4. 生成新的合并记忆：
   - content: 合并摘要
   - type: 保持原类型
   - importance: max(各片段)
   - metadata.source: "dream_merged"
   - metadata.merged_from: [A.id, B.id, C.id]
5. 删除原始片段
6. 添加新记忆
```

### 3.3 结构化梳理（Structurer）

**目标**：从非结构化内容中提取实体和关系，建立结构化记忆

**实体类型**：
```python
entities = {
    "person": ["人名", "角色"],
    "project": ["项目名", "代码仓库"],
    "file": ["文件路径", "配置项"],
    "preference": ["偏好设置"],
    "decision": ["已做决定"],
    "task": ["待办任务"],
    "tool": ["工具名称"],
}
```

**处理流程**：
```
1. 获取所有 knowledge 类型且 importance < 5 的记忆
2. 对每条记忆：
   a. 提取实体（正则 + 关键词）
   b. 判断类型
   c. 检查是否可归类到已有结构
3. 如果发现重复结构化信息：
   - 合并到已有结构化记忆
   - 标记来源记忆为 "absorbed"
4. 生成结构化摘要记忆：
   - type: 保持原 type
   - content: "## [主题]\n- 实体1\n- 实体2\n- 关系"
   - importance: +2（结构化后提升重要性）
```

**示例**：
```
输入：["用户偏好Chrome浏览器", "用户使用Chrome开发"]
处理后：["用户浏览器偏好：Chrome（高优先级）"]
```

### 3.4 降噪优化（Denoiser）

**目标**：移除低质量、过期、无意义的记忆

**过滤规则**（按优先级）：

| 规则 | 条件 | 动作 |
|------|------|------|
| 完全保护 | importance ≥ 9 | 不做任何操作 |
| 删除保护 | importance ≥ 7 | 不删除，可合并 |
| 空内容 | content.length < 10 | 删除 |
| 系统噪声 | source=system 且无实际内容 | 删除 |
| 过度重复 | 同一内容出现5次以上 | 合并为1条 |
| 过期知识 | knowledge过期且无访问 | **先尝试LLM刷新，失败才删除** |
| 低重要性 | importance < 3 且 access_count=0 | 软删除（**7天**后真删） |
| importance≥5 | importance ≥ 5 且 access_count=0 | 软删除（**14天**缓冲期） |
| 超短内容 | 内容<20字且非preference/task | 删除 |
| 截断内容 | 内容以"..."结尾 | 检查完整性 |
| 超长内容 | 内容>5000字 | 拆分或截断 |

**分层保护说明**：
- importance ≥ 9：完全保护，不参与任何自动操作
- importance ≥ 7：只参与去重，不参与删除
- importance ≥ 5：参与所有操作，软删除缓冲期 14 天
- importance < 5：参与所有操作，软删除缓冲期 7 天

**软删除机制**：
- 不直接删除，而是设置 `expire_at = now + 缓冲期`
- importance ≥ 5：缓冲期 **14 天**
- importance < 5：缓冲期 **7 天**
- 缓冲期内被访问则恢复 `expire_at = null`
- 缓冲期无访问则在下一次做梦时真删除

---

## 四、触发与执行策略

### 4.1 触发机制

**1. 定时触发（Schedule）**
```python
# ⚠️ 实际运行 cron（来自 jobs.json）：每天 13:30（下午1:30）Asia/Shanghai
cron: "30 13 * * *"
# 旧设计默认值：每天凌晨3点（已被实际配置覆盖）
cron: "0 3 * * *"
```

**2. Token 阈值触发**
```python
# 与 auto_cleanup 协同
# 当 Token 使用达到 85% 时：
# 1. 先运行 auto_cleanup（清理过期）
# 2. 如果 Token 仍高，运行 Dream Maintenance
token_threshold: 0.85
```

**3. 设备空闲触发**
```python
idle_trigger: True
idle_minutes: 30  # 30分钟无操作视为空闲

# 检测方式：
# - 无键盘/鼠标输入
# - 无活跃进程（排除系统进程）
# - CPU 使用率 < 10%
```

**4. 手动触发**
```bash
POST /memories/dream/run
{
    "modules": ["deduplicator", "merger", "denoiser"],  # 可选模块
    "dry_run": false  # dry_run=true 时只生成报告不执行
}
```

### 4.2 执行策略

**时长限制**：
```python
max_duration_minutes: 30  # 单次最长30分钟

# 渐进式检查点：
# - 每处理10条记忆检查一次时间
# - 剩余时间 < 5分钟时停止新批次
# - 当前批次完成后停止
```

**并发控制**：
```python
concurrency: 2  # 最大并发数

# 分阶段串行：
# Phase 1: Deduplicator（需全量扫描）
# Phase 2: Merger（依赖 Phase 1 结果）
# Phase 3: Structurer（可部分并行）
# Phase 4: Denoiser（可部分并行）
```

**幂等性保证**：
```python
# 每个操作前检查状态
dream_state = {
    "run_id": "uuid",
    "phase": "deduplicator",
    "started_at": "ISO timestamp",
    "processed": 0,
    "deleted": [],
    "merged": [],
    "updated": [],
}

# 每次写操作前保存状态快照
# 如果服务崩溃，重启后检查状态
# - 已删除的记忆不做二次删除
# - 已合并的记忆不做二次合并
# - 未完成的操作可选择继续或回滚
```

**断点续传**：
```python
# 状态文件位置：
# C:\Users\Administrator\.openclaw\production\data\vector_store\dream_state.json

{
    "run_id": "550e8400-e29b-41d4-a716-446655440000",
    "phase": "merger",
    "started_at": "2026-04-04T03:00:00.000Z",
    "checkpoint_at": "2026-04-04T03:15:00.000Z",
    "memory_snapshot": {
        "phase1_deleted": [id1, id2, ...],
        "phase1_merged": [id3, id4, ...]
    },
    "can_resume": true
}
```

---

## 五、实施路径

### 5.1 依赖分析

```
                    ┌─────────────────────┐
                    │   无依赖，可直接实施   │
                    │  Phase 0: 基础框架    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Phase 1: API端点    │
                    │  /dream/run 等      │
                    │  依赖: 8007服务运行中│
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Phase 2: Deduplicator│  │ Phase 3: Denoiser │  │ Phase 4: Merger  │
│ 直接可做          │  │ 直接可做         │  │ 需 LLM 调用     │
│ 依赖 Phase 1     │  │ 依赖 Phase 1     │  │ 依赖 Phase 1    │
└─────────────────┘  └─────────────────┘  └────────┬────────┘
                                                     │
                                          ┌──────────▼──────────┐
                                          │ Phase 5: Structurer │
                                          │ 需 LLM 调用 + 实体库 │
                                          │ 依赖 Phase 1        │
                                          └─────────────────────┘
```

### 5.2 实施顺序

**Phase 0: 基础设施（1天）**
- [ ] 定义 DreamConfig 数据模型
- [ ] 创建状态管理模块（dream_state.json）
- [ ] 定义日志格式

**Phase 1: API 端点（1天）**
- [ ] 添加 `/memories/dream/run` POST 端点
- [ ] 添加 `/memories/dream/status` GET 端点
- [ ] 添加 `/memories/dream/report` GET 端点
- [ ] 添加 `/memories/dream/config` GET/PUT 端点
- [ ] 添加 `/memories/dream/stop` POST 端点

**Phase 2: Deduplicator（2天）**
- [ ] 实现批量相似度比对逻辑
- [ ] 实现"最优记忆"选择策略
- [ ] 实现删除和状态更新
- [ ] 单元测试

**Phase 3: Denoiser（1天）**
- [ ] 实现各过滤规则
- [ ] 实现软删除机制
- [ ] 实现过期知识刷新逻辑
- [ ] 单元测试

**Phase 4: Merger（2天）**
- [ ] 实现候选分组逻辑
- [ ] 集成 LLM 合并摘要生成
- [ ] 实现合并后记忆创建
- [ ] 单元测试

**Phase 5: Structurer（3天）**
- [ ] 实体提取规则库（正则+关键词）
- [ ] 结构化摘要生成
- [ ] 与现有结构化记忆合并
- [ ] 单元测试

**Phase 6: 触发器集成（1天）**
- [ ] 定时触发（cron）
- [ ] Token 阈值触发（与 auto_cleanup 协同）
- [ ] 空闲检测触发

**Phase 7: 监控与报告（1天）**
- [ ] 运行报告生成
- [ ] 日志完善
- [ ] 健康检查端点

**总计：约12个工作日**

### 5.3 快速收益方案（2天可上线）

先实施 **Phase 0 + 1 + 2 + 3**（查重去重 + 降噪优化）：

```
实施内容：
1. API 端点（/dream/run, /dream/status）
2. Deduplicator（查重，动态阈值删除）
3. Denoiser（空内容删除 + 低重要性删除 + 过期删除）
4. 简单基于关键词的合并（非LLM）

收益量化：
- 快速版本：预计删除 **15-25 条**低质量记忆（20-30%）
- 完整版本：预计减少记忆总量 **40-50%**
```

---

## 六、做梦报告数据模型

```python
class DreamReport(BaseModel):
    run_id: str
    started_at: str
    completed_at: Optional[str]
    duration_seconds: float
    
    phases: Dict[str, PhaseReport] = {
        "deduplicator": PhaseReport(...),
        "merger": PhaseReport(...),
        "structurer": PhaseReport(...),
        "denoiser": PhaseReport(...),
    }
    
    summary: Dict[str, Any] = {
        "total_processed": 73,
        "total_deleted": 15,
        "total_merged": 5,
        "total_updated": 3,
        "remaining": 56,
        "duration_minutes": 12.5,
    }
    
    issues: List[str] = []  # 执行中的问题

class PhaseReport(BaseModel):
    enabled: bool
    candidates: int
    processed: int
    deleted: List[int]
    merged: List[int]
    updated: List[int]
    skipped: int
    errors: List[str]
```

---

## 七、潜在风险与缓解

### 7.1 风险清单

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| LLM 调用超时导致任务失败 | 中 | 中 | 设置超时重试（3次），失败后跳过该条 |
| 误删重要记忆 | 低 | 高 | **分层保护**：importance≥9完全保护，≥7不删除；提供回滚接口 |
| 合并产生信息丢失 | 中 | 中 | 保留原始记忆 **7-14 天**后才真删除；合并前做 dry_run；每月LLM合并预算控制 |
| 服务资源占用过高 | 低 | 中 | 设置 max_duration + batch_size 限制；监控 CPU |
| 与 auto_cleanup 冲突 | 低 | 低 | 两者使用不同触发条件；状态文件隔离 |
| 向量相似度计算不准确 | 中 | 低 | 使用 paraphrase-multilingual-MiniLM-L12-v2（已有），定期验证 |
| 多进程并发执行 | 低 | 中 | 使用分布式锁；单实例运行时通过状态文件协调 |

### 7.2 回滚机制

```python
# 每次删除/合并前保存逆向操作
rollback_log = [
    {"action": "delete", "memory_id": 123, "backup": {...}},
    {"action": "merge", "original_ids": [456, 457], "new_id": 458},
]

# 回滚接口
POST /memories/dream/rollback
{
    "run_id": "550e8400-...",
    "to_phase": "deduplicator"  # 回滚到此阶段之前
}
```

---

## 八、与现有系统协同

### 8.1 与 auto_cleanup 协同

```
auto_cleanup (Token 85% 触发):
  └→ 清理过期/无效记忆（被动维护）
  
dream_maintenance (定时/空闲触发):
  └→ 主动优化记忆质量（主动维护）

触发优先级：
  1. auto_cleanup 先跑（轻量，快速）
  2. dream_maintenance 后跑（重量，需空闲）
```

### 8.2 与记忆来源协同

| 来源 | 做梦模式处理 |
|------|------------|
| user_said | 高优先级保留 |
| ai_summary | 检查内容质量，合并重复摘要 |
| auto_timer | 大量降噪目标，可能删除60%+ |
| auto_topic_switch | 合并同话题 |
| auto_decision_keyword | 保留决策结论，删除重复 |
| auto_important_keyword | 重要性评估，合并同话题 |
| auto_compaction | 保留（来源可靠） |

---

## 九、配置默认值建议

```python
DREAM_DEFAULT_CONFIG = {
    "enabled": True,
    "trigger": {
        "schedule": "30 13 * * *",     # ⚠️ 实际运行值：每天 13:30（每天下午1:30）
        "token_threshold": 0.90,         # Token 90%（高于cleanup的85%）
        "idle_trigger": True,
        "idle_minutes": 30,
        "manual": True,
    },
    "execution": {
        "max_duration_minutes": 20,      # 单次最长20分钟
        "batch_size": 30,                # 每批处理30条
        "concurrency": 2,
        "dry_run": False,
        "cpu_threshold": 0.95,           # ⚠️ 实际值：95%（旧设计 0.3 已修正）
        "memory_threshold_mb": 14000,    # ⚠️ 实际值：14000MB（旧设计 500 已修正）
    },
    "modules": {
        "deduplicator": True,
        "merger": True,
        "structurer": True,
        "denoiser": True,
    },
    "thresholds": {
        # 动态去重相似度阈值
        "dedup_similarity": {
            "short": 0.95,    # <50字
            "medium": 0.92,   # 50-500字
            "long": 0.88,     # >500字
        },
        # 动态合并相似度阈值
        "merge_similarity": {
            "short": 0.85,    # <50字
            "medium": 0.78,   # 50-500字
            "long": 0.75,     # >500字
        },
        "min_importance": 3,
        "max_age_days": 90,
        "min_content_length": 10,
        "llm_merge_monthly_budget": 100,           # LLM合并每月预算
        "llm_merge_priority_importance": 5,        # 优先合并 importance≥5
    }
}
```

---

## 十、后续扩展方向

1. **知识图谱化**：将 lesson/task/knowledge 的实体关系构建为图谱
2. **主动学习**：根据 recall 命中率反向优化 importance
3. **跨模态去重**：支持记忆片段与文件/代码的交叉去重
4. **分布式做梦**：多台设备协作，共享高质量记忆
5. **记忆标签系统**：用户可给记忆打标签，做标签维度的聚合
