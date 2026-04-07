# 模块集成指南

## 概述

本文档详细介绍了如何将5个核心模块集成到自我感知系统中，包括模块功能、API接口、数据存储和系统架构。

## 集成模块列表

1. **对话记忆模块** (`conversation_memory.py`) - 记录和管理对话历史
2. **任务跟踪模块** (`task_tracker.py`) - 创建、跟踪和管理任务
3. **决策记录模块** (`decision_recorder.py`) - 记录决策过程和结果
4. **学习反馈模块** (`learning_feedback.py`) - 记录学习经验和反馈
5. **能力评估模块** (`capability_assessment.py`) - 评估和跟踪能力发展

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                   前端界面 (端口: 8000)                      │
│  • 模块集成仪表板 (modules_dashboard.html)                  │
│  • 原始仪表板 (dashboard.html)                              │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                   API服务 (端口: 8001)                       │
│  • 统一API网关                                            │
│  • 代理到其他服务                                         │
│  • 系统状态聚合                                           │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│               集成服务 (端口: 8002)                          │
│  • 模块管理器 (module_manager.py)                          │
│  • 数据路由和缓冲                                         │
│  • 模块状态监控                                           │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│               向量服务 (端口: 8007)                          │
│  • 向量存储 (vector_service.py)                            │
│  • 支持6种数据类型                                        │
│  • 数据检索和统计                                         │
└─────────────────────────────────────────────────────────────┘
```

## 数据流

```
外部数据 → API服务 → 集成服务 → 模块管理器 → 各模块 → 向量存储
      │         │          │           │         │         │
      │         │          │           │         │         │
      ▼         ▼          ▼           ▼         ▼         ▼
   用户界面   健康检查   状态监控     数据缓存   本地存储   数据库
```

## API接口

### 1. API服务 (端口: 8001)

#### 健康检查
- `GET /health` - 服务健康状态
- `GET /system/status` - 完整系统状态

#### 模块相关
- `GET /modules/status` - 所有模块状态
- `GET /modules/summary` - 系统摘要
- `GET /modules/{module_name}/data` - 获取模块数据
- `GET /modules/search` - 搜索模块数据
- `POST /modules/test` - 测试模块集成
- `GET /modules/vector/stats` - 向量存储统计
- `GET /modules/vector/recent` - 最近向量数据

### 2. 集成服务 (端口: 8002)

#### 模块管理
- `GET /modules/status` - 模块状态详情
- `GET /modules/summary` - 系统摘要详情
- `POST /modules/data` - 添加数据到模块系统
- `GET /modules/{module_name}/data` - 获取模块原始数据
- `GET /modules/search` - 搜索模块原始数据

### 3. 向量服务 (端口: 8007)

#### 数据存储
- `POST /add` - 添加向量数据
- `GET /memories` - 获取所有记忆
- `GET /stats` - 统计信息
- `GET /recent` - 最近数据
- `GET /data/summary` - 数据摘要
- `GET /data/modules` - 模块数据统计

## 模块详细说明

### 1. 对话记忆模块

**功能**:
- 记录对话内容和上下文
- 提取关键词和摘要
- 管理对话历史
- 重要性评分

**数据结构**:
```json
{
  "type": "conversation",
  "content": "对话内容",
  "participants": ["用户", "系统"],
  "context": "对话上下文",
  "importance": 1,
  "metadata": {
    "source": "conversation_memory",
    "timestamp": "2024-01-01T12:00:00"
  }
}
```

### 2. 任务跟踪模块

**功能**:
- 任务创建、更新、完成
- 进度跟踪和提醒
- 优先级管理
- 任务分类和标签

**数据结构**:
```json
{
  "type": "task",
  "title": "任务标题",
  "description": "任务描述",
  "status": "todo",
  "priority": 2,
  "due_date": "2024-01-01T12:00:00",
  "progress": 0,
  "tags": ["开发", "重要"]
}
```

### 3. 决策记录模块

**功能**:
- 记录决策上下文
- 选项分析和评估
- 结果跟踪
- 教训总结

**数据结构**:
```json
{
  "type": "decision",
  "title": "决策标题",
  "context": "决策上下文",
  "options": [
    {"description": "选项A", "evaluation": "优点缺点"},
    {"description": "选项B", "evaluation": "优点缺点"}
  ],
  "chosen_option": {"description": "选项B"},
  "rationale": "选择理由",
  "importance": 2,
  "outcome": "success"
}
```

### 4. 学习反馈模块

**功能**:
- 记录错误和修复
- 成功经验总结
- 行为优化建议
- 反馈分类和标签

**数据结构**:
```json
{
  "type": "feedback",
  "content": "反馈内容",
  "feedback_type": "success",
  "impact": 2,
  "context": "反馈上下文",
  "source": "系统",
  "tags": ["优化", "经验"],
  "applied": false
}
```

### 5. 能力评估模块

**功能**:
- 当前能力评估
- 能力差距分析
- 能力提升规划
- 评估历史跟踪

**数据结构**:
```json
{
  "type": "capability",
  "category": "technical",
  "level": 2,
  "evidence": ["成功案例1", "成功案例2"],
  "assessment_date": "2024-01-01T12:00:00",
  "next_review_date": "2024-02-01T12:00:00",
  "improvement_plan": ["学习计划1", "实践计划2"]
}
```

## 数据存储

### 向量数据库表结构
```sql
CREATE TABLE vectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    vector BLOB,
    metadata TEXT,
    vector_type TEXT,      -- conversation, task, decision, learning, capability, test
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    type TEXT,             -- 同vector_type，保持兼容性
    type_name TEXT,        -- 类型显示名称
    importance INTEGER DEFAULT 1
);
```

### 支持的数据类型
1. `conversation` - 对话记忆
2. `task` - 任务跟踪
3. `decision` - 决策记录
4. `learning` - 学习反馈
5. `capability` - 能力评估
6. `test` - 测试数据

## 启动和部署

### 1. 快速启动
```powershell
# 使用集成启动脚本
.\start_all_services_integrated.ps1
```

### 2. 手动启动
```powershell
# 启动向量服务
python -m uvicorn vector_service:app --host 0.0.0.0 --port 8007 --reload

# 启动集成服务
python integration_service.py

# 启动API服务
python api_service.py

# 启动前端服务
cd frontend
python -m http.server 8000
```

### 3. 测试集成
```powershell
# 运行集成测试
python test_module_integration.py

# 查看测试报告
cat module_integration_test_report.json
```

## 监控和维护

### 健康检查
```bash
# 检查所有服务
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8007/health

# 检查系统状态
curl http://localhost:8001/system/status

# 检查模块状态
curl http://localhost:8001/modules/status
```

### 数据统计
```bash
# 查看向量存储统计
curl http://localhost:8001/modules/vector/stats

# 查看系统摘要
curl http://localhost:8001/modules/summary

# 查看最近数据
curl http://localhost:8001/modules/vector/recent?limit=10
```

## 故障排除

### 常见问题

1. **服务启动失败**
   - 检查端口是否被占用
   - 检查Python依赖是否安装
   - 查看日志文件

2. **模块数据不显示**
   - 检查集成服务是否运行
   - 检查向量服务连接
   - 查看模块状态

3. **API调用失败**
   - 检查服务地址和端口
   - 检查网络连接
   - 查看API响应状态码

### 日志文件
- `logs/api_service.log` - API服务日志
- `logs/integration_service.log` - 集成服务日志
- `logs/vector_service.log` - 向量服务日志

## 性能指标

### 响应时间要求
- 模块调用响应时间 < 100ms
- 数据存储延迟 < 50ms
- API响应时间 < 200ms

### 资源使用
- 内存使用: < 500MB
- CPU使用: < 30%
- 数据库大小: 自动清理旧数据

## 扩展和定制

### 添加新模块
1. 创建模块类，实现标准接口
2. 在模块管理器中注册
3. 更新向量服务支持新类型
4. 更新API端点
5. 更新前端界面

### 修改数据格式
1. 更新模块数据结构
2. 更新向量存储格式
3. 更新API序列化
4. 保持向后兼容性

### 集成外部系统
1. 通过API服务添加数据端点
2. 使用模块管理器处理数据
3. 存储到向量数据库
4. 提供查询接口

## 安全考虑

### 访问控制
- API服务提供统一入口
- 前端服务静态文件
- 内部服务间通信

### 数据安全
- 敏感数据加密存储
- 访问日志记录
- 定期数据备份

### 系统安全
- 服务隔离运行
- 错误处理和恢复
- 监控和告警

## 版本历史

### v1.0.0 (当前版本)
- 5个核心模块集成
- 统一API接口
- 模块集成仪表板
- 完整测试套件

### 未来计划
- 实时数据同步
- 高级搜索功能
- 机器学习集成
- 移动端支持

## 支持与联系

如有问题或建议，请参考：
- `ADMIN_GUIDE.md` - 管理员指南
- `DEVELOPER_GUIDE.md` - 开发者指南
- `FAQ.md` - 常见问题
- `TEST_REPORT.md` - 测试报告

---

**集成状态**: ✅ 完成  
**测试状态**: ✅ 通过  
**部署状态**: ✅ 就绪  
**文档状态**: ✅ 完整