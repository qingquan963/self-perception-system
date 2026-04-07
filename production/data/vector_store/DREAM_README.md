# 做梦模式服务（Dream Maintenance）

> Phase 0-1-2-3 快速版本 | 2026-04-04

## 文件列表

```
vector_store/
├── dream_service.py          # 核心服务（FastAPI + 做梦引擎）
├── start_dream_service.bat    # Windows 启动脚本
└── DREAM_README.md            # 本文件
```

状态文件: `dream_state.json`（自动创建）
配置文件: `dream_config.json`（自动创建，首次运行生成）

---

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/memories/dream/run` | 手动触发做梦 |
| GET  | `/memories/dream/status` | 查看运行状态 |
| POST | `/memories/dream/stop` | 停止正在运行的任务 |
| GET  | `/memories/dream/report` | 查看上次运行报告 |
| GET  | `/memories/dream/config` | 获取当前配置 |
| PUT  | `/memories/dream/config` | 更新配置 |

---

## 快速启动

### 方式1：启动脚本（推荐）

```cmd
cd C:\Users\Administrator\.openclaw\production\data\vector_store
start_dream_service.bat
```

服务将在 `http://localhost:8001` 启动，API 文档在 `http://localhost:8001/docs`

### 方式2：直接运行

```cmd
python dream_service.py --port 8001 --host 0.0.0.0
```

### 方式3：Python 代码调用

```python
import sys
sys.path.insert(0, r'C:\Users\Administrator\.openclaw\production\data\vector_store')
from dream_service import DreamEngine, DreamState, DEFAULT_DREAM_CONFIG

state = DreamState()
engine = DreamEngine(DEFAULT_DREAM_CONFIG, state)
report = engine.run(dry_run=False)  # dry_run=True 只生成报告
print(report)
```

---

## 配置说明

```json
{
  "enabled": true,
  "execution": {
    "max_duration_minutes": 20,    // 单次最长20分钟
    "batch_size": 30,              // 每批处理30条
    "cpu_threshold": 0.3,          // CPU上限30%
    "memory_threshold_mb": 500     // 内存上限500MB
  },
  "modules": {
    "deduplicator": true,   // 查重去重
    "denoiser": true       // 降噪优化
  },
  "thresholds": {
    "dedup_similarity": {
      "short": 0.95,   // <50字
      "medium": 0.92,  // 50-500字
      "long": 0.88     // >500字
    }
  }
}
```

---

## 分层保护策略

| importance 范围 | 行为 |
|-----------------|------|
| ≥ 9 | 完全保护，不参与任何自动操作 |
| ≥ 7 | 只去重，不删除 |
| ≥ 5 | 参与所有操作，软删除缓冲期 14 天 |
| < 5 | 参与所有操作，软删除缓冲期 7 天 |

---

## 验证结果（2026-04-04）

- ✅ 语法检查通过
- ✅ 所有单元测试通过（10/10）
- ✅ ChromaDB 连接正常（66 条记忆）
- ✅ Deduplicator 获取记忆正确
- ✅ Denoiser 获取记忆正确
- ✅ 配置默认值正确

---

## 日志

日志文件位于: `logs/dream/dream_YYYYMMDD.log`

---

## 注意事项

1. **端口**：默认 8001（与主 API 8000 错开）
2. **不修改会话上下文**：只处理向量库中的记忆
3. **不修改文件记忆**：只操作 ChromaDB
4. **幂等性**：重复执行是安全的，状态文件记录进度
5. **静默降级**：所有错误记录 warn 日志，不影响服务
