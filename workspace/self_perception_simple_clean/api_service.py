#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
精简自我感知系统API服务
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime
import json
import os
import sqlite3
import httpx
import asyncio
import logging
from typing import Any, Dict, Optional
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 加载 .env 配置
_BASE_DIR = Path(__file__).parent
load_dotenv(_BASE_DIR / ".env")

# ─── 自动保存触发器 ─────────────────────────────────────────────────
from auto_save import check_and_save, get_tracker_status, set_context_state, get_tracker

app = FastAPI(title="Simple Self-Perception System", version="1.0.0")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ─── 上下文监控配置（从 .env 读取）────────────────────────────────────
_DB_PATH = _BASE_DIR / "vectors.db"
_WARN_THRESHOLD_PCT   = int(os.getenv("TOKEN_WARNING_THRESHOLD", 80))
_CRIT_THRESHOLD_PCT   = int(os.getenv("TOKEN_CRITICAL_THRESHOLD", 90))

# 进程内累计状态（重启清零，记录本次运行期间的操作次数）
_context_state = {
    "auto_cleanup_enabled": True,
    "auto_save_enabled": True,
    "cleanup_count": 0,
    "save_count": 0,
    "last_cleanup_at": None,
    "last_save_at": None,
}

# 注入到 auto_save 模块
set_context_state(_context_state)


def _estimate_tokens_from_text(text: str) -> int:
    """估算文本的 token 数（中英混合：约 0.75 字符/token）"""
    if not text:
        return 0
    return max(1, int(len(text) * 0.75))


# ─── OpenClaw 会话 sessions.json 路径（自动查找最新会话）──────────────────
_SESSIONS_JSON = Path(os.path.expanduser("~")) / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json"


def _get_real_session_tokens() -> dict:
    """
    从 OpenClaw sessions.json 读取当前会话的真实 Token 用量。
    返回字段：
      ok              bool   — 是否成功读取
      context_window  int    — 模型上下文窗口上限（contextTokens）
      total_tokens    int    — 本会话累计消耗 Token（input+output 历史合计）
      input_tokens    int    — 最近一次 API 调用的输入 token
      output_tokens   int    — 最近一次 API 调用的输出 token
      cache_read      int    — 缓存命中读取量
      compaction_count int   — OpenClaw 已自动压缩次数
      model           str    — 当前使用的模型名称
      percentage      float  — total_tokens / context_window * 100
    """
    try:
        if not _SESSIONS_JSON.exists():
            return {"ok": False, "error": "sessions.json 不存在", "percentage": 0.0}

        with open(_SESSIONS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not data:
            return {"ok": False, "error": "sessions.json 为空", "percentage": 0.0}

        # 取最近更新的会话
        sessions = list(data.values())
        sessions.sort(key=lambda s: s.get("updatedAt", 0), reverse=True)
        s = sessions[0]

        context_window   = s.get("contextTokens", 128000) or 128000
        total_tokens     = s.get("totalTokens", 0) or 0
        input_tokens     = s.get("inputTokens", 0) or 0
        output_tokens    = s.get("outputTokens", 0) or 0
        cache_read       = s.get("cacheRead", 0) or 0
        cache_write      = s.get("cacheWrite", 0) or 0
        compaction_count = s.get("compactionCount", 0) or 0
        model            = s.get("model", "unknown")
        model_provider   = s.get("modelProvider", "unknown")

        percentage = round(total_tokens / context_window * 100, 2) if context_window > 0 else 0.0

        return {
            "ok":               True,
            "context_window":   context_window,
            "total_tokens":     total_tokens,
            "input_tokens":     input_tokens,
            "output_tokens":    output_tokens,
            "cache_read":       cache_read,
            "cache_write":      cache_write,
            "compaction_count": compaction_count,
            "model":            model,
            "model_provider":   model_provider,
            "percentage":       percentage,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "percentage": 0.0}


def _get_real_context_usage() -> dict:
    """
    从 vectors.db 查询记忆库概况（统计信息，非容量百分比）。
    记忆库没有固定容量上限，像人的记忆一样越积越多。
    返回：记录总数、总字符数、估算 Token 数、按类型分布、最近活动时间。
    """
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        cur = conn.cursor()

        # 汇总所有记录
        cur.execute("""
            SELECT
                COUNT(id)                          AS total_records,
                COALESCE(SUM(LENGTH(content)), 0)  AS total_content_len,
                COALESCE(SUM(LENGTH(COALESCE(metadata,''))), 0) AS total_meta_len,
                MAX(created_at)                    AS last_activity
            FROM vectors
        """)
        row = cur.fetchone()

        total_records     = row[0] or 0
        total_content_len = row[1] or 0
        total_meta_len    = row[2] or 0
        last_activity     = row[3]

        # 按类型分布
        cur.execute("""
            SELECT COALESCE(type, 'unknown') as t, COUNT(*) as cnt, 
                   COALESCE(SUM(LENGTH(content)), 0) as chars
            FROM vectors GROUP BY t ORDER BY cnt DESC
        """)
        type_dist = {r[0]: {"count": r[1], "chars": r[2]} for r in cur.fetchall()}

        conn.close()

        # 估算 token（仅用于展示参考，不作为"容量百分比"的分母）
        estimated_tokens = int(total_content_len * 0.75) + int(total_meta_len * 0.5)

        return {
            "ok": True,
            "total_records": total_records,
            "total_chars": total_content_len,
            "estimated_tokens": estimated_tokens,
            "type_distribution": type_dist,
            "last_activity": last_activity,
        }
    except Exception as e:
        return {
            "ok": False,
            "total_records": 0,
            "total_chars": 0,
            "estimated_tokens": 0,
            "type_distribution": {},
            "last_activity": None,
            "error": str(e),
        }

# ─── 模块元数据定义 ──────────────────────────────────────────────────────
_MODULE_META = {
    "conversation_memory": {
        "display_name": "对话记忆",
        "icon": "fas fa-comments",
        "color": "#3498db",
        "storage_path": "向量数据库 vectors.db / 类型: conversation",
        "features": [
            "记录每轮对话内容与参与者",
            "自动提取关键词（最多5个）",
            "自动分类（7大类别）",
            "生成对话摘要",
            "本地缓存 + 向量服务双写",
            "重要性评分（1-5级）",
            "全文搜索 & 向量服务搜索",
        ],
    },
    "task_tracking": {
        "display_name": "任务跟踪",
        "icon": "fas fa-tasks",
        "color": "#2ecc71",
        "storage_path": "向量数据库 vectors.db / 类型: task",
        "features": [
            "任务全生命周期管理（TODO → 进行中 → 完成）",
            "四级优先级（LOW / MEDIUM / HIGH / CRITICAL）",
            "截止日期提醒（提前24小时）",
            "任务进度追踪（0-100%）",
            "支持负责人、标签、依赖关系",
            "任务笔记与注释",
            "超期任务自动识别",
            "已完成任务自动清理（7天后）",
        ],
    },
    "decision_recording": {
        "display_name": "决策记录",
        "icon": "fas fa-clipboard-check",
        "color": "#f39c12",
        "storage_path": "向量数据库 vectors.db / 类型: decision",
        "features": [
            "记录决策标题、上下文、选项列表",
            "四级重要性（LOW / MEDIUM / HIGH / CRITICAL）",
            "选择理由与利益相关者归档",
            "决策结果评估（成功/部分成功/失败）",
            "经验教训积累",
            "决策前后指标对比",
            "成功率统计与模式分析",
            "高风险决策模式识别",
        ],
    },
    "learning_feedback": {
        "display_name": "学习反馈",
        "icon": "fas fa-graduation-cap",
        "color": "#9b59b6",
        "storage_path": "向量数据库 vectors.db / 类型: learning",
        "features": [
            "五类反馈（错误/成功/改进/问题/洞察）",
            "四级影响程度评估",
            "错误根本原因与预防建议",
            "成功经验与可复制模式",
            "行动项管理（含优先级和截止日期）",
            "应用效果跟踪（1-5分）",
            "高频关键词与主题统计",
            "改进建议自动生成",
        ],
    },
    "capability_assessment": {
        "display_name": "能力评估",
        "icon": "fas fa-chart-bar",
        "color": "#1abc9c",
        "storage_path": "向量数据库 vectors.db / 类型: capability",
        "features": [
            "7大能力维度（技术/问题解决/沟通/学习/决策/领导/创新）",
            "每维度4项子能力精细评估",
            "四级成熟度（初级/中级/高级/专家）",
            "加权综合得分计算",
            "能力差距识别与优先级排序",
            "多次评估历史对比",
            "能力提升建议自动生成",
            "6个月发展计划制定",
        ],
    },
    # ── 扩展 3 类型（可用于新增记忆）───────────────────────────────────────────
    "user_preference": {
        "display_name": "用户偏好",
        "icon": "fas fa-sliders-h",
        "color": "#e91e63",
        "storage_path": "向量数据库 vectors.db / 类型: user_preference",
        "features": ["记录用户偏好、习惯、行为规律", "跨会话持久化", "语义搜索"],
    },
    "project_status": {
        "display_name": "项目状态",
        "icon": "fas fa-project-diagram",
        "color": "#00bcd4",
        "storage_path": "向量数据库 vectors.db / 类型: project_status",
        "features": ["项目里程碑、进度快照、阶段总结", "时序状态对比"],
    },
    "lesson_learned": {
        "display_name": "经验教训",
        "icon": "fas fa-lightbulb",
        "color": "#ff9800",
        "storage_path": "向量数据库 vectors.db / 类型: lesson_learned",
        "features": ["复盘总结、踩坑记录、最佳实践沉淀", "关键词聚类检索"],
    },
}


@app.get("/")
async def root():
    """根端点"""
    return {
        "service": "Simple Self-Perception System API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "Simple Self-Perception System",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "api": True,
            "context_alert": True
        }
    }

@app.get("/context/status")
async def context_status():
    """上下文状态（简化版，兼容旧调用）——返回记忆库统计 + 大模型会话状态"""
    usage = _get_real_context_usage()
    st = _get_real_session_tokens()

    return {
        "token_usage_percentage": st["percentage"] if st["ok"] else 0,
        "total_tokens": st.get("context_window", 0) if st["ok"] else 0,
        "used_tokens": st.get("total_tokens", 0) if st["ok"] else 0,
        "warning_level": "NORMAL",
        "data_source": "vectors.db" if usage["ok"] else "unavailable",
        "total_records": usage["total_records"],
        "timestamp": datetime.now().isoformat()
    }


@app.get("/context/monitor")
async def context_monitor():
    """
    上下文监控（供仪表板使用）。
    大模型会话窗口：有固定容量，监控百分比，超阈值自动清理。
    记忆库：无固定容量上限，像人的记忆一样越积越多，只展示统计信息。
    """
    usage = _get_real_context_usage()
    st = _get_real_session_tokens()

    # ── 记忆库统计（无容量上限概念）──
    memory_info = {
        "ok": usage["ok"],
        "total_records": usage["total_records"],
        "total_chars": usage["total_chars"],
        "estimated_tokens": usage["estimated_tokens"],
        "type_distribution": usage["type_distribution"],
        "last_activity": usage.get("last_activity"),
    }

    # ── 大模型会话窗口（有容量上限，需要监控百分比）──
    import asyncio as _asyncio
    real_pct = st["percentage"] if st["ok"] else 0
    # 只根据大模型 Token 池触发自动清理（记忆库无容量上限，不触发清理）
    _asyncio.ensure_future(_maybe_auto_cleanup(real_pct))

    auto_cleanup_triggered = (
        real_pct >= _AUTO_CLEANUP_THRESHOLD_PCT
        and _context_state["auto_cleanup_enabled"]
    )

    return {
        "memory": memory_info,
        "session": {
            "ok":             st.get("ok", False),
            "context_window": st.get("context_window", 128000),
            "total_tokens":   st.get("total_tokens", 0),
            "percentage":     st.get("percentage", 0.0),
            "compaction_count": st.get("compaction_count", 0),
            "model":          st.get("model", "unknown"),
            "color":          ("#e74c3c" if st.get("percentage", 0) >= _CRIT_THRESHOLD_PCT
                               else "#f39c12" if st.get("percentage", 0) >= _WARN_THRESHOLD_PCT
                               else "#2ecc71"),
        },
        "thresholds": {
            "warning":      _WARN_THRESHOLD_PCT,
            "critical":     _CRIT_THRESHOLD_PCT,
            "auto_cleanup": _AUTO_CLEANUP_THRESHOLD_PCT,
        },
        "auto_mechanisms": {
            "auto_cleanup_enabled":   _context_state["auto_cleanup_enabled"],
            "auto_save_enabled":      _context_state["auto_save_enabled"],
            "cleanup_count":          _context_state["cleanup_count"],
            "save_count":             _context_state["save_count"],
            "last_cleanup_at":        _context_state["last_cleanup_at"],
            "last_save_at":           _context_state["last_save_at"],
            "auto_cleanup_triggered": auto_cleanup_triggered,
            "auto_cleanup_threshold": _AUTO_CLEANUP_THRESHOLD_PCT,
            "auto_save_status":       None,  # 由前端按需加载 /auto-save/status
        },
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/context/session-tokens")
async def context_session_tokens():
    """
    获取当前 OpenClaw 会话的真实 Token 用量。
    数据来源：~/.openclaw/agents/main/sessions/sessions.json
    """
    st = _get_real_session_tokens()
    if not st["ok"]:
        return {
            "ok": False,
            "error": st.get("error", "未知错误"),
            "percentage": 0.0,
            "timestamp": datetime.now().isoformat(),
        }

    pct = st["percentage"]
    if pct >= _CRIT_THRESHOLD_PCT:
        level, label, color = "CRITICAL", "严重", "#e74c3c"
    elif pct >= _WARN_THRESHOLD_PCT:
        level, label, color = "WARNING",  "警告", "#f39c12"
    elif pct >= 60:
        level, label, color = "ELEVATED", "偏高", "#f39c12"
    else:
        level, label, color = "NORMAL",   "正常", "#2ecc71"

    return {
        "ok":               True,
        "context_window":   st["context_window"],
        "total_tokens":     st["total_tokens"],
        "input_tokens":     st["input_tokens"],
        "output_tokens":    st["output_tokens"],
        "cache_read":       st["cache_read"],
        "cache_write":      st["cache_write"],
        "compaction_count": st["compaction_count"],
        "model":            st["model"],
        "model_provider":   st["model_provider"],
        "percentage":       pct,
        "status": {
            "level": level,
            "label": label,
            "color": color,
        },
        "thresholds": {
            "warning":      _WARN_THRESHOLD_PCT,
            "critical":     _CRIT_THRESHOLD_PCT,
            "auto_cleanup": _AUTO_CLEANUP_THRESHOLD_PCT,
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/modules/detail/{module_name}")
async def get_module_detail(module_name: str):
    """获取单个模块的详细信息（含功能列表、存储路径）"""
    meta = _MODULE_META.get(module_name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"模块不存在: {module_name}")

    # 尝试从向量服务获取实际记录数
    count = 0
    latest_activity = None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://127.0.0.1:8007/data/modules")
            if resp.status_code == 200:
                modules_data = resp.json()
                module_info = modules_data.get(module_name, {})
                count = module_info.get("count", 0)
                latest_activity = module_info.get("latest_activity")
    except Exception:
        pass

    return {
        "module_name": module_name,
        "display_name": meta["display_name"],
        "icon": meta["icon"],
        "color": meta["color"],
        "storage_path": meta["storage_path"],
        "features": meta["features"],
        "stats": {
            "count": count,
            "latest_activity": latest_activity,
            "status": "active" if count > 0 else "inactive",
        },
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/modules/details/all")
async def get_all_modules_detail():
    """获取所有模块的详细信息"""
    # 先拿一次模块汇总（含记录数）
    modules_counts = {}
    modules_activity = {}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://127.0.0.1:8007/data/modules")
            if resp.status_code == 200:
                data = resp.json()
                for k, v in data.items():
                    if isinstance(v, dict):
                        modules_counts[k] = v.get("count", 0)
                        modules_activity[k] = v.get("latest_activity")
    except Exception:
        pass

    result = {}
    for module_name, meta in _MODULE_META.items():
        count = modules_counts.get(module_name, 0)
        result[module_name] = {
            "display_name": meta["display_name"],
            "icon": meta["icon"],
            "color": meta["color"],
            "storage_path": meta["storage_path"],
            "features": meta["features"],
            "stats": {
                "count": count,
                "latest_activity": modules_activity.get(module_name),
                "status": "active" if count > 0 else "inactive",
            },
        }
    return {"modules": result, "timestamp": datetime.now().isoformat()}

@app.get("/memories/count")
async def get_memory_count():
    """获取记忆数量（代理到向量服务）"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://127.0.0.1:8007/stats")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取记忆数量失败: {str(e)}")

@app.get("/memories")
async def get_memories(limit: int = 100):
    """获取记忆列表（代理到向量服务）"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"http://127.0.0.1:8007/memories?limit={limit}")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取记忆列表失败: {str(e)}")

@app.get("/memories/{memory_id}")
async def get_memory(memory_id: int):
    """获取单条记忆详情（代理到向量服务）"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"http://127.0.0.1:8007/memories/{memory_id}")
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"记忆 id={memory_id} 不存在")
            response.raise_for_status()
            return response.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取记忆失败: {str(e)}")

@app.delete("/memories/{memory_id}")
async def delete_memory(memory_id: int):
    """删除单条记忆（代理到向量服务）"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(f"http://127.0.0.1:8007/memories/{memory_id}")
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"记忆 id={memory_id} 不存在")
            response.raise_for_status()
            return response.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除记忆失败: {str(e)}")

@app.put("/memories/{memory_id}")
async def update_memory(memory_id: int, request: Request):
    """更新单条记忆内容/类型/元数据（代理到向量服务）"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.put(
                f"http://127.0.0.1:8007/memories/{memory_id}",
                json=body
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"记忆 id={memory_id} 不存在")
            response.raise_for_status()
            return response.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新记忆失败: {str(e)}")

# 模块集成相关端点
@app.get("/modules/status")
async def get_modules_status():
    """获取模块状态（代理到集成服务）"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://127.0.0.1:8002/modules/status")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模块状态失败: {str(e)}")

@app.get("/modules/summary")
async def get_system_summary():
    """获取系统摘要（代理到集成服务）"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://127.0.0.1:8002/modules/summary")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统摘要失败: {str(e)}")

@app.get("/modules/{module_name}/data")
async def get_module_data(module_name: str, limit: int = 100):
    """获取模块数据（代理到集成服务）"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"http://127.0.0.1:8002/modules/{module_name}/data?limit={limit}")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模块数据失败: {str(e)}")

@app.get("/modules/search")
async def search_modules_data(query: str, module_name: str = None, limit: int = 10):
    """搜索模块数据（代理到集成服务）"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            params = {"query": query, "limit": limit}
            if module_name:
                params["module_name"] = module_name
            
            response = await client.get("http://127.0.0.1:8002/modules/search", params=params)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索模块数据失败: {str(e)}")

@app.post("/modules/test")
async def test_module_integration():
    """测试模块集成（代理到集成服务）"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post("http://127.0.0.1:8002/modules/test")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模块集成测试失败: {str(e)}")

@app.get("/system/status")
async def get_system_status():
    """获取完整的系统状态"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 并行获取所有服务状态
            tasks = [
                client.get("http://127.0.0.1:8001/health"),
                client.get("http://127.0.0.1:8002/health"),
                client.get("http://127.0.0.1:8007/health"),
                client.get("http://127.0.0.1:8002/modules/summary")
            ]
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 解析响应
            api_status = responses[0] if not isinstance(responses[0], Exception) else {"status": "error", "error": str(responses[0])}
            integration_status = responses[1] if not isinstance(responses[1], Exception) else {"status": "error", "error": str(responses[1])}
            vector_status = responses[2] if not isinstance(responses[2], Exception) else {"status": "error", "error": str(responses[2])}
            module_summary = responses[3] if not isinstance(responses[3], Exception) else {"status": "error", "error": str(responses[3])}
            
            return {
                "timestamp": datetime.now().isoformat(),
                "services": {
                    "api_service": api_status,
                    "integration_service": integration_status,
                    "vector_service": vector_status
                },
                "modules": module_summary,
                "overall_status": "healthy" if all(
                    r.get("status") == "healthy" if isinstance(r, dict) else False 
                    for r in [api_status, integration_status, vector_status]
                ) else "degraded"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统状态失败: {str(e)}")

@app.post("/memories/recall")
async def recall_memories_proxy(req: Request):
    """
    主动召回（代理到 vector_service POST /memories/recall）
    """
    try:
        body = await req.body()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "http://127.0.0.1:8007/memories/recall",
                content=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"召回失败: {str(e)}")

@app.post("/context/cleanup")
async def trigger_cleanup(req: Request):
    """
    手动触发记忆清理（代理到 vector_service POST /memories/cleanup）

    可选请求体参数（默认值见 vector_service）：
      keep_recent_days: int  (默认 30)
      keep_per_type:    int  (默认 20)
      dry_run:          bool (默认 False)
    """
    try:
        body = await req.body()
        request = json.loads(body) if body else {}
    except Exception:
        request = {}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "http://127.0.0.1:8007/memories/cleanup",
                json=request,
            )
            resp.raise_for_status()
            result = resp.json()

        # 更新本地状态
        _context_state["cleanup_count"] += 1
        _context_state["last_cleanup_at"] = datetime.now().isoformat()

        return {
            "triggered_by": "manual",
            "result": result,
            "cleanup_count": _context_state["cleanup_count"],
            "last_cleanup_at": _context_state["last_cleanup_at"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


# ─── 自动触发阈值（85%）────────────────────────────────────────
_AUTO_CLEANUP_THRESHOLD_PCT = 85
# 防止短时间内重复触发（距上次自动清理至少 300 秒）
_last_auto_cleanup_ts: float = 0.0


async def _maybe_auto_cleanup(session_pct: float):
    """当大模型会话 Token 池使用率 ≥ 85% 时自动触发清理（非阻塞）。
    注意：记忆库没有固定容量上限，不需要基于记忆库大小触发清理。
    """
    global _last_auto_cleanup_ts
    if not _context_state["auto_cleanup_enabled"]:
        return
    if session_pct < _AUTO_CLEANUP_THRESHOLD_PCT:
        return
    import time
    now = time.time()
    if now - _last_auto_cleanup_ts < 300:
        return  # 5 分钟内已触发过，跳过
    _last_auto_cleanup_ts = now

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "http://127.0.0.1:8007/memories/cleanup",
                json={"keep_recent_days": 30, "keep_per_type": 20, "dry_run": False},
            )
            if resp.status_code == 200:
                _context_state["cleanup_count"] += 1
                _context_state["last_cleanup_at"] = datetime.now().isoformat()
                logger.warning(
                    f"[AutoCleanup] 会话Token池={session_pct:.1f}% ≥ {_AUTO_CLEANUP_THRESHOLD_PCT}%，"
                    f"自动清理已触发，本次删除={resp.json().get('deleted', 0)} 条"
                )
    except Exception as e:
        logger.error(f"[AutoCleanup] 自动清理失败: {e}")


# ─── 自动保存：后台轮询（每 60 秒检查一次触发条件）──────────────────
_auto_save_interval = 60  # 检查间隔（秒）
_auto_save_running = False


async def _auto_save_loop():
    """后台循环：定期检查是否需要自动保存"""
    global _auto_save_running
    _auto_save_running = True
    logger.info("[AutoSave] 后台轮询已启动，检查间隔 60 秒")
    while _auto_save_running:
        try:
            if not _context_state.get("auto_save_enabled", True):
                await asyncio.sleep(_auto_save_interval)
                continue
            results = await check_and_save()
            if results:
                _context_state["save_count"] += len(results)
                _context_state["last_save_at"] = datetime.now().isoformat()
                for r in results:
                    logger.info(
                        f"[AutoSave] 触发保存: type={r['trigger_type']}, "
                        f"reason={r['reason']}, status={r['save_result'].get('status')}"
                    )
        except Exception as e:
            logger.error(f"[AutoSave] 轮询异常: {e}")
        await asyncio.sleep(_auto_save_interval)


@app.on_event("startup")
async def startup_event():
    """服务启动时，在后台启动自动保存轮询"""
    asyncio.ensure_future(_auto_save_loop())


@app.on_event("shutdown")
async def shutdown_event():
    """服务关闭时，停止自动保存轮询"""
    global _auto_save_running
    _auto_save_running = False
    logger.info("[AutoSave] 后台轮询已停止")


# ─── 自动保存状态 API ──────────────────────────────────────────────
@app.get("/auto-save/status")
async def auto_save_status():
    """获取自动保存触发器的当前状态"""
    try:
        status = get_tracker_status()
        status["config"] = {
            "enabled": _context_state.get("auto_save_enabled", True),
            "check_interval_sec": _auto_save_interval,
            "timer_save_interval_min": 30,
            "trigger_rules": ["compaction", "keyword_decision", "keyword_important", "memorize", "timer"],
        }
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取自动保存状态失败: {str(e)}")


@app.post("/auto-save/toggle")
async def auto_save_toggle(req: Request):
    """开关自动保存功能"""
    try:
        body = await req.json()
    except Exception:
        body = {}
    enabled = body.get("enabled")
    if enabled is not None:
        _context_state["auto_save_enabled"] = bool(enabled)
        get_tracker()  # 确保 tracker 已初始化
    return {
        "auto_save_enabled": _context_state.get("auto_save_enabled", True),
        "save_count": _context_state["save_count"],
        "last_save_at": _context_state["last_save_at"],
    }


@app.post("/auto-save/force-check")
async def auto_save_force_check():
    """手动触发一次检查（不等定时器）"""
    try:
        results = await check_and_save()
        if results:
            _context_state["save_count"] += len(results)
            _context_state["last_save_at"] = datetime.now().isoformat()
        return {
            "triggered": len(results),
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"强制检查失败: {str(e)}")

@app.get("/services/monitor")
async def services_monitor():
    """
    三层记忆体系三大核心服务的实时运行状况监控。
    聚合：auto_save / recall / Memory Compression
    """
    import psutil
    now = datetime.now().isoformat()

    # 1. auto_save 统计
    save_status = await auto_save_status()

    # 2. recall 统计（从 vector_service 获取）
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            vr = await client.get("http://127.0.0.1:8007/stats/recall")
            vr.raise_for_status()
            recall_data = vr.json()
    except Exception:
        recall_data = {"error": "vector_service 不可达"}

    # 3. Memory Compression 进程状态（进程名 MemCompression）
    mc_status = {"running": False, "pid": None, "memory_mb": None, "cpu_sec": None, "name": None}
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = proc.info["name"] or ""
            # Windows/MemCompression = Memory Compression（OpenClaw 压缩模块）
            if name in ("Memory Compression", "MemCompression"):
                p = psutil.Process(proc.info["pid"])
                mc_status = {
                    "running": True,
                    "pid": proc.info["pid"],
                    "name": name,
                    "memory_mb": round(p.memory_info().rss / 1024 / 1024, 1),
                    "cpu_sec": round(p.cpu_times().user, 1),
                    "create_time": datetime.fromtimestamp(p.create_time()).isoformat(),
                }
                break
        except Exception:
            pass

    return {
        "generated_at": now,
        "auto_save": {
            "save_count": save_status.get("total_saves", 0),
            "last_save_time": save_status.get("last_save_time"),
            "recent_triggers": save_status.get("recent_triggers", [])[:5],
            "enabled": save_status.get("enabled", True),
        },
        "recall": {
            "total_calls": recall_data.get("count", 0),
            "avg_results": recall_data.get("avg_results_per_call", 0),
            "total_results": recall_data.get("total_results", 0),
            "last_time": recall_data.get("last_time"),
            "last_context_preview": recall_data.get("last_context_preview", ""),
        },
        "memory_compression": {
            "running": mc_status["running"],
            "pid": mc_status["pid"],
            "memory_mb": mc_status["memory_mb"],
            "cpu_sec": mc_status["cpu_sec"],
            "create_time": mc_status.get("create_time"),
        },
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8011)