#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
做梦模式服务（Dream Maintenance）
快速版本 Phase 0-1-2-3

功能：
- POST /memories/dream/run      手动触发做梦
- GET  /memories/dream/status   查看运行状态
- POST /memories/dream/stop     暂停做梦任务
- GET  /memories/dream/report   查看上次运行报告
- GET  /memories/dream/config   获取/设置配置

作者：Architect Agent | 2026-04-04
版本：适配 Python 3.10 - 不依赖 retrieval_client，通过 HTTP API 调用向量库
"""

import os, sys, json, time, uuid, logging, threading, traceback, math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

# ── 基础路径配置 ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
VECTOR_STORE_PATH = BASE_DIR
STATE_FILE = BASE_DIR / "dream_state.json"
CONFIG_FILE = BASE_DIR / "dream_config.json"
LOG_DIR = BASE_DIR / "logs" / "dream"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── 日志配置 ──────────────────────────────────────────────────────────────────
def _setup_log(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(LOG_DIR / f"dream_{datetime.now().strftime('%Y%m%d')}.log", encoding="utf-8")
    fh.setLevel(logging.INFO)
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger

logger = _setup_log("dream_service")

# ── HTTP 向量库客户端（替代 retrieval_client）──────────────────────────────────
VectorStoreBaseUrl = "http://127.0.0.1:8007"

try:
    import httpx as _httpx
    _http_available = True
except ImportError:
    _httpx = None
    _http_available = False
    logger.warning("[Dream] httpx 未安装，将无法连接向量库")

try:
    import numpy as np
    _np_available = True
except ImportError:
    np = None
    _np_available = False
    logger.warning("[Dream] numpy 未安装")


class HttpVectorCollection:
    """
    模拟 ChromaDB collection 接口，通过 HTTP API 操作向量库。
    兼容原 RetrievalClient.collection 的用法：
      client.collection.get(include=["documents", "metadatas"])
      client.collection.delete(ids=["1"])
      client.collection.update(ids=["1"], metadatas=[{...}])
    """

    def __init__(self, base_url: str = VectorStoreBaseUrl, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = _httpx.Client(timeout=timeout) if _http_available else None

    def _get_all_memories_raw(self, limit: int = 10000) -> List[Dict]:
        if not _http_available or self._client is None:
            logger.error("[HttpVectorCollection] httpx 不可用")
            return []
        try:
            resp = self._client.get(f"{self.base_url}/memories", params={"limit": limit})
            resp.raise_for_status()
            return resp.json().get("memories", [])
        except Exception as e:
            logger.error(f"[HttpVectorCollection] 获取记忆失败: {e}")
            return []

    def get(self, include: List[str] = None) -> Dict[str, List]:
        include = include or []
        memories = self._get_all_memories_raw()
        ids, documents, metadatas = [], [], []
        for mem in memories:
            ids.append(str(mem.get("id", "")))
            documents.append(mem.get("content", ""))
            metadatas.append(mem.get("metadata", {}))
        return {"ids": ids, "documents": documents, "metadatas": metadatas}

    def delete(self, ids: List[str]) -> None:
        if not _http_available or self._client is None:
            return
        for id_str in ids:
            try:
                int_id = int(id_str)
                self._client.delete(f"{self.base_url}/memories/{int_id}")
            except Exception as e:
                logger.warning(f"[HttpVectorCollection] 删除记忆 {id_str} 失败: {e}")

    def update(self, ids: List[str], metadatas: List[Dict]) -> None:
        if not _http_available or self._client is None:
            return
        for id_str, meta in zip(ids, metadatas):
            try:
                int_id = int(id_str)
                self._client.put(f"{self.base_url}/memories/{int_id}", json=meta)
            except Exception as e:
                logger.warning(f"[HttpVectorCollection] 更新记忆 {id_str} 失败: {e}")

    def close(self):
        if self._client:
            self._client.close()


class RetrievalClientSimulator:
    """替代 retrieval_client.RetrievalClient，提供 .collection 属性"""
    def __init__(self, base_url: str = VectorStoreBaseUrl):
        if not _http_available:
            raise RuntimeError("httpx 未安装，无法使用向量库客户端")
        self.base_url = base_url
        self.collection = HttpVectorCollection(base_url)
        logger.info(f"[RetrievalClientSimulator] 初始化完成，连接到 {base_url}")


# ── SentenceTransformer（延迟导入）───────────────────────────────────────────
SentenceTransformer = None

def _lazy_imports():
    global SentenceTransformer
    if SentenceTransformer is None:
        try:
            from sentence_transformers import SentenceTransformer as _ST
            SentenceTransformer = _ST
            logger.info("[Dream] sentence_transformers 加载成功")
        except ImportError as e:
            logger.warning(f"[Dream] sentence_transformers 未找到: {e}")


# ── 默认配置 ───────────────────────────────────────────────────────────────────
DEFAULT_DREAM_CONFIG = {
    "enabled": True,
    "trigger": {"schedule": "0 3 * * *", "token_threshold": 0.90, "idle_trigger": True, "idle_minutes": 30, "manual": True},
    "execution": {"max_duration_minutes": 20, "batch_size": 30, "concurrency": 2, "dry_run": False, "cpu_threshold": 0.95, "memory_threshold_mb": 14000},
    "modules": {"deduplicator": True, "merger": True, "structurer": True, "denoiser": True},
    "thresholds": {
        "dedup_similarity": {"short": 0.95, "medium": 0.92, "long": 0.88},
        "merge_similarity": {"short": 0.85, "medium": 0.78, "long": 0.75},
        "min_importance": 3, "max_age_days": 90, "min_content_length": 10,
        "llm_merge_monthly_budget": 100, "llm_merge_priority_importance": 5,
    },
    "soft_delete_buffer_days": {"high": 14, "low": 7},
}


# ── 状态管理 ───────────────────────────────────────────────────────────────────
class DreamState:
    def __init__(self):
        self.state_file = STATE_FILE
        self._lock = threading.RLock()
        self._state = self._load()

    def _load(self) -> Dict:
        if os.path.exists(str(self.state_file)):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"[Dream] 状态文件加载失败: {e}")
        return self._default_state()

    def _default_state(self) -> Dict:
        return {"status": "idle", "run_id": None, "phase": None, "started_at": None,
                "completed_at": None, "progress": 0.0, "can_resume": False, "last_report": None, "last_error": None}

    def save(self):
        with self._lock:
            try:
                with open(self.state_file, "w", encoding="utf-8") as f:
                    json.dump(self._state, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"[Dream] 状态保存失败: {e}")

    def update(self, **kwargs):
        with self._lock:
            self._state.update(kwargs)
            self.save()

    def get(self, key: str, default=None):
        return self._state.get(key, default)

    @property
    def status(self) -> str:
        return self._state.get("status", "idle")

    @property
    def is_running(self) -> bool:
        return self._state.get("status") == "running"


# ── 工具函数 ───────────────────────────────────────────────────────────────────
def get_dedup_threshold(text_length: int, thresholds: Dict) -> float:
    if text_length < 50: return thresholds["short"]
    elif text_length <= 500: return thresholds["medium"]
    return thresholds["long"]

def soft_delete_buffer_days(importance: float, config: Dict) -> int:
    buf = config.get("soft_delete_buffer_days", {})
    return buf.get("high", 14) if importance >= 5 else buf.get("low", 7)

def parse_time(time_str: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    except Exception:
        return None

def check_resources(logger: logging.Logger) -> tuple:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        return True, float(cpu), float(mem.used / (1024 * 1024))
    except ImportError:
        return True, 0.0, 0.0
    except Exception:
        return True, 0.0, 0.0

def content_quality_score(content: str) -> float:
    if not content or len(content.strip()) < 5:
        return 0.0
    score = 0.5
    if len(content.split()) > 5:
        score += 0.2
    alpha_count = sum(1 for c in content if c.isalpha())
    if alpha_count / max(len(content), 1) > 0.3:
        score += 0.15
    if any(p in content for p in "，。！？；：、""''（）"):
        score += 0.15
    return min(score, 1.0)


# ── 查重去重器 ─────────────────────────────────────────────────────────────────
class Deduplicator:
    def __init__(self, client, embed_model, config: Dict, state: DreamState):
        self.client = client
        self.embed_model = embed_model
        self.config = config
        self.state = state
        self.thresholds = config["thresholds"]
        self.batch_size = config["execution"]["batch_size"]

    def run(self) -> Dict[str, Any]:
        dedup_cfg = self.thresholds["dedup_similarity"]
        result = {"candidates": 0, "duplicates_found": 0, "merged_candidates": 0,
                  "deleted_ids": [], "skipped": 0, "errors": []}
        try:
            all_memories = self._fetch_all_memories()
            result["candidates"] = len(all_memories)
            if not all_memories:
                logger.info("[Deduplicator] 没有记忆需要处理")
                return result
            memories = [m for m in all_memories if m.get("importance", 5) < 9]
            result["skipped"] = len(all_memories) - len(memories)
            logger.info(f"[Deduplicator] 候选 {len(memories)} 条，跳过 {result['skipped']} 条（importance≥9）")
            total_batches = (len(memories) + self.batch_size - 1) // self.batch_size
            for batch_idx in range(total_batches):
                batch = memories[batch_idx * self.batch_size:(batch_idx + 1) * self.batch_size]
                dr = self._process_batch(batch, dedup_cfg)
                result["deleted_ids"].extend(dr.get("deleted_ids", []))
                result["duplicates_found"] += dr.get("duplicates_found", 0)
                result["errors"].extend(dr.get("errors", []))
                self.state.update(progress=round((batch_idx + 1) / total_batches * 0.5, 4))
            logger.info(f"[Deduplicator] 完成：发现重复 {result['duplicates_found']} 组，删除 {len(result['deleted_ids'])} 条")
        except Exception as e:
            logger.warning(f"[Deduplicator] 执行出错: {e}\n{traceback.format_exc()}")
            result["errors"].append(str(e))
        return result

    def _fetch_all_memories(self) -> List[Dict]:
        try:
            res = self.client.collection.get(include=["documents", "metadatas"])
            if not res["ids"]:
                return []
            docs = res.get("documents") or []
            metas = res.get("metadatas") or []
            ids = res.get("ids") or []
            memories = []
            for i, doc_id in enumerate(ids):
                meta = metas[i] if i < len(metas) else {}
                importance = meta.get("importance") if isinstance(meta, dict) else None
                access_count = meta.get("access_count", 0) if isinstance(meta, dict) else 0
                memories.append({
                    "id": doc_id,
                    "content": docs[i] if i < len(docs) else "",
                    "metadata": meta,
                    "importance": float(importance) if importance is not None else 5.0,
                    "access_count": access_count or 0,
                })
            return memories
        except Exception as e:
            logger.warning(f"[Deduplicator] 获取记忆失败: {e}")
            return []

    def _process_batch(self, batch: List[Dict], dedup_cfg: Dict) -> Dict:
        result = {"duplicates_found": 0, "merged_candidates": 0, "deleted_ids": [], "errors": []}
        contents = [m.get("content", "") for m in batch]
        try:
            if self.embed_model is not None:
                vectors = self.embed_model.encode(contents).tolist()
            else:
                logger.warning("[Deduplicator] embed_model 不可用，跳过批处理")
                return result
        except Exception as e:
            logger.warning(f"[Deduplicator] 向量化失败: {e}")
            return result

        for i, mem_i in enumerate(batch):
            if mem_i["id"] in result["deleted_ids"]:
                continue
            importance_i = mem_i.get("importance", 5.0)
            len_i = len(mem_i.get("content", ""))
            vec_i = vectors[i]
            dedup_thresh = get_dedup_threshold(len_i, dedup_cfg)
            to_delete = []
            for j, mem_j in enumerate(batch):
                if i == j or mem_j["id"] in result["deleted_ids"]:
                    continue
                importance_j = mem_j.get("importance", 5.0)
                if importance_j >= 7 and importance_i < 7:
                    continue
                vec_j = vectors[j]
                try:
                    norm_i = np.linalg.norm(vec_i)
                    norm_j = np.linalg.norm(vec_j)
                    if norm_i > 0 and norm_j > 0:
                        sim = float(np.dot(vec_i, vec_j) / (norm_i * norm_j))
                    else:
                        continue
                except Exception:
                    continue
                if sim >= dedup_thresh:
                    result["duplicates_found"] += 1
                    keep = self._pick_best(mem_i, mem_j, importance_i, importance_j)
                    if keep == "i":
                        to_delete.append(mem_j["id"])
                    else:
                        to_delete.append(mem_i["id"])
                        break
            for del_id in to_delete:
                if del_id not in result["deleted_ids"]:
                    try:
                        self.client.collection.delete(ids=[del_id])
                        result["deleted_ids"].append(del_id)
                        logger.info(f"[Deduplicator] 删除重复记忆: {del_id}")
                    except Exception as e:
                        result["errors"].append(f"删除 {del_id} 失败: {e}")
        return result

    def _pick_best(self, mem_i: Dict, mem_j: Dict, imp_i: float, imp_j: float) -> str:
        if imp_i != imp_j:
            return "i" if imp_i > imp_j else "j"
        ac_i = mem_i.get("access_count", 0) or 0
        ac_j = mem_j.get("access_count", 0) or 0
        if ac_i != ac_j:
            return "i" if ac_i > ac_j else "j"
        ct_i = parse_time(mem_i.get("created_at", "")) or datetime.min
        ct_j = parse_time(mem_j.get("created_at", "")) or datetime.min
        return "i" if ct_i > ct_j else "j"


# ── 降噪优化器 ─────────────────────────────────────────────────────────────────
class Denoiser:
    def __init__(self, client, config: Dict, state: DreamState):
        self.client = client
        self.config = config
        self.state = state
        self.thresholds = config["thresholds"]
        self.batch_size = config["execution"]["batch_size"]
        self.now = datetime.now()

    def run(self) -> Dict[str, Any]:
        result = {"candidates": 0, "soft_deleted": [], "hard_deleted": [],
                  "restored": [], "skipped": 0, "errors": []}
        try:
            memories = self._fetch_all_memories()
            result["candidates"] = len(memories)
            for mem in memories:
                mem_id = mem["id"]
                importance = mem.get("importance", 5)
                content = mem.get("content", "")
                metadata = mem.get("metadata", {})
                expire_at_str = metadata.get("expire_at")
                access_count = mem.get("access_count", 0) or 0
                if importance >= 9:
                    result["skipped"] += 1
                    continue
                if expire_at_str:
                    expire_at = parse_time(expire_at_str)
                    if expire_at and self.now < expire_at and access_count > 0:
                        self._restore(mem_id, metadata)
                        result["restored"].append(mem_id)
                        continue
                    elif expire_at and self.now >= expire_at:
                        try:
                            self.client.collection.delete(ids=[mem_id])
                            result["hard_deleted"].append(mem_id)
                            logger.info(f"[Denoiser] 真删除过期软删除: {mem_id}")
                            continue
                        except Exception as e:
                            result["errors"].append(f"真删除 {mem_id} 失败: {e}")
                            continue
                action = self._should_delete(content, importance, metadata)
                if action == "hard":
                    try:
                        self.client.collection.delete(ids=[mem_id])
                        result["hard_deleted"].append(mem_id)
                        logger.info(f"[Denoiser] 硬删除: {mem_id}")
                    except Exception as e:
                        result["errors"].append(f"硬删除 {mem_id} 失败: {e}")
                elif action == "soft":
                    buf_days = soft_delete_buffer_days(importance, self.config)
                    expire_at_new = self.now + timedelta(days=buf_days)
                    try:
                        new_meta = dict(metadata)
                        new_meta["expire_at"] = expire_at_new.isoformat()
                        new_meta["soft_deleted"] = True
                        self.client.collection.update(ids=[mem_id], metadatas=[new_meta])
                        result["soft_deleted"].append(mem_id)
                        logger.info(f"[Denoiser] 软删除 {mem_id}（缓冲期{buf_days}天）")
                    except Exception as e:
                        result["errors"].append(f"软删除 {mem_id} 失败: {e}")
            logger.info(f"[Denoiser] 完成：硬删除 {len(result['hard_deleted'])} 条，软删除 {len(result['soft_deleted'])} 条，恢复 {len(result['restored'])} 条")
        except Exception as e:
            logger.warning(f"[Denoiser] 执行出错: {e}\n{traceback.format_exc()}")
            result["errors"].append(str(e))
        return result

    def _fetch_all_memories(self) -> List[Dict]:
        try:
            res = self.client.collection.get(include=["documents", "metadatas"])
            if not res.get("ids"):
                return []
            docs = res.get("documents") or []
            metas = res.get("metadatas") or []
            ids = res.get("ids") or []
            memories = []
            for i, doc_id in enumerate(ids):
                meta = metas[i] if i < len(metas) else {}
                importance = meta.get("importance") if isinstance(meta, dict) else None
                memories.append({
                    "id": doc_id, "content": docs[i] if i < len(docs) else "",
                    "metadata": meta, "importance": float(importance) if importance is not None else 5.0,
                })
            return memories
        except Exception as e:
            logger.warning(f"[Denoiser] 获取记忆失败: {e}")
            return []

    def _should_delete(self, content: str, importance: float, metadata: Dict) -> str:
        content_len = len(content.strip())
        if content_len < self.thresholds.get("min_content_length", 10):
            return "hard"
        if content_quality_score(content) < 0.2:
            return "soft" if importance >= 3 else "hard"
        if importance < 3:
            access_count = metadata.get("access_count", 0) or 0 if isinstance(metadata, dict) else 0
            if access_count == 0:
                return "soft"
        if content.strip().endswith("...") and content_len < 50:
            return "soft"
        mem_type = metadata.get("type", "") if isinstance(metadata, dict) else ""
        if mem_type == "knowledge":
            expiring_count = metadata.get("expiring_count", 0) or 0 if isinstance(metadata, dict) else 0
            access_count = metadata.get("access_count", 0) or 0 if isinstance(metadata, dict) else 0
            if expiring_count > 0 and access_count == 0 and importance < 5:
                return "soft"
        if importance >= 7:
            return "skip"
        created_str = metadata.get("created_at", "") if isinstance(metadata, dict) else ""
        if created_str:
            created_dt = parse_time(created_str)
            if created_dt:
                max_age = self.thresholds.get("max_age_days", 90)
                if (self.now - created_dt).days > max_age:
                    return "soft" if importance >= 5 else "hard"
        return "skip"

    def _restore(self, mem_id: str, metadata: Dict):
        try:
            new_meta = dict(metadata)
            new_meta.pop("expire_at", None)
            new_meta.pop("soft_deleted", None)
            self.client.collection.update(ids=[mem_id], metadatas=[new_meta])
            logger.info(f"[Denoiser] 恢复软删除: {mem_id}")
        except Exception as e:
            logger.warning(f"[Denoiser] 恢复失败 {mem_id}: {e}")


# ── 做梦引擎 ───────────────────────────────────────────────────────────────────
class DreamEngine:
    def __init__(self, config: Dict, state: DreamState):
        self.config = config
        self.state = state
        self.client = None
        self.embed_model = None
        self._stop_flag = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _init_clients(self):
        """
        核心改动：用 RetrievalClientSimulator（HTTP）替代 retrieval_client.RetrievalClient。
        不再依赖 retrieval_client 库，直接通过 HTTP API 操作向量库。
        """
        _lazy_imports()
        if not _http_available:
            raise RuntimeError("httpx 未安装，请先安装 httpx")
        try:
            self.client = RetrievalClientSimulator(VectorStoreBaseUrl)
            model_name = self.config.get("embedding_model", "sentence-transformers/all-MiniLM-L6-v2")
            if SentenceTransformer is not None:
                self.embed_model = SentenceTransformer(model_name)
                logger.info(f"[Dream] 嵌入模型加载成功: {model_name}")
            else:
                self.embed_model = None
                logger.warning("[Dream] sentence_transformers 未安装，向量计算不可用")
            logger.info("[Dream] 向量库客户端初始化成功（HTTP API 模式）")
        except Exception as e:
            logger.error(f"[Dream] 客户端初始化失败: {e}")
            raise

    def run(self, dry_run: bool = False, modules: List[str] = None) -> Dict[str, Any]:
        run_id = str(uuid.uuid4())
        started_at = datetime.now()
        self._stop_flag.clear()
        self.state.update(status="running", run_id=run_id, phase="initializing",
                           started_at=started_at.isoformat(), completed_at=None,
                           progress=0.0, can_resume=False, last_error=None)
        report = {"run_id": run_id, "started_at": started_at.isoformat(), "completed_at": None,
                  "duration_seconds": 0.0, "dry_run": dry_run, "phases": {}, "summary": {}, "issues": []}
        max_duration_sec = self.config["execution"]["max_duration_minutes"] * 60
        modules = modules or [k for k, v in self.config["modules"].items() if v]
        try:
            self._init_clients()
            for phase_name in ["deduplicator", "denoiser"]:
                if phase_name not in modules:
                    continue
                if self._stop_flag.is_set():
                    logger.info(f"[Dream] 收到停止信号，退出 Phase {phase_name}")
                    report["issues"].append(f"Phase {phase_name} 被停止信号中断")
                    break
                elapsed = (datetime.now() - started_at).total_seconds()
                if elapsed >= max_duration_sec:
                    logger.warning(f"[Dream] 达到最大时长 {max_duration_sec}s，停止")
                    report["issues"].append("达到最大执行时长，任务被截断")
                    break
                ok, cpu, mem_mb = check_resources(logger)
                cpu_limit = self.config["execution"]["cpu_threshold"]
                mem_limit = self.config["execution"]["memory_threshold_mb"]
                if not ok or cpu > cpu_limit or mem_mb > mem_limit:
                    logger.warning(f"[Dream] 资源不足 CPU={cpu:.1f}% MEM={mem_mb:.0f}MB，仍尝试执行，暂不跳过 {phase_name}")


                self.state.update(phase=phase_name)
                if phase_name == "deduplicator" and self.config["modules"].get("deduplicator"):
                    engine = Deduplicator(self.client, self.embed_model, self.config, self.state)
                    phase_report = engine.run()
                    report["phases"]["deduplicator"] = phase_report
                    self.state.update(progress=0.5)
                elif phase_name == "denoiser" and self.config["modules"].get("denoiser"):
                    engine = Denoiser(self.client, self.config, self.state)
                    phase_report = engine.run()
                    report["phases"]["denoiser"] = phase_report
                    self.state.update(progress=0.9)
            completed_at = datetime.now()
            duration = (completed_at - started_at).total_seconds()
            total_deleted = total_soft = total_hard = 0
            for phase_name, pr in report["phases"].items():
                if phase_name == "deduplicator":
                    total_deleted += len(pr.get("deleted_ids", []))
                elif phase_name == "denoiser":
                    total_hard += len(pr.get("hard_deleted", []))
                    total_soft += len(pr.get("soft_deleted", []))
            report["completed_at"] = completed_at.isoformat()
            report["duration_seconds"] = round(duration, 2)
            report["summary"] = {"total_deleted": total_deleted, "total_soft_deleted": total_soft,
                                  "total_hard_deleted": total_hard, "duration_seconds": round(duration, 2)}
            self.state.update(status="idle", phase=None, completed_at=completed_at.isoformat(),
                               progress=1.0, can_resume=False, last_report=report)
            self.state.save()
            logger.info(f"[Dream] 完成！运行 {duration:.1f}s，删除 {total_deleted} 条，硬删 {total_hard} 条，软删 {total_soft} 条")
        except Exception as e:
            logger.warning(f"[Dream] 执行出错: {e}\n{traceback.format_exc()}")
            report["issues"].append(str(e))
            report["completed_at"] = datetime.now().isoformat()
            self.state.update(status="error", phase=None, completed_at=datetime.now().isoformat(),
                               last_error=str(e), last_report=report)
            self.state.save()
        return report

    def stop(self):
        self._stop_flag.set()
        logger.info("[Dream] 停止信号已发送")

    def start_async(self, dry_run: bool = False, modules: List[str] = None):
        if self.state.is_running:
            logger.warning("[Dream] 已有任务在运行，忽略本次请求")
            return False
        self._thread = threading.Thread(target=self.run, args=(dry_run, modules),
                                          daemon=True, name="DreamEngine-thread")
        self._thread.start()
        return True


# ── 配置管理 ───────────────────────────────────────────────────────────────────
class DreamConfigManager:
    def __init__(self, config_file: Path = CONFIG_FILE):
        self.config_file = config_file
        self._config = self._load()

    def _load(self) -> Dict:
        if os.path.exists(str(self.config_file)):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"[Dream] 配置加载失败: {e}")
        return dict(DEFAULT_DREAM_CONFIG)

    def save(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[Dream] 配置保存失败: {e}")

    def get(self) -> Dict:
        return self._config

    def update(self, updates: Dict) -> Dict:
        self._config.update(updates)
        self.save()
        return self._config


# ── FastAPI 应用 ────────────────────────────────────────────────────────────────
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Dream Maintenance API", version="1.0.0")

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.dream_engine: Optional[DreamEngine] = None
app.state.dream_state = DreamState()
app.state.dream_config = DreamConfigManager()


class DreamRunRequest(BaseModel):
    dry_run: bool = Field(False)
    modules: Optional[List[str]] = Field(None)


class DreamConfigUpdateRequest(BaseModel):
    config: Dict[str, Any] = Field(...)


@app.on_event("startup")
async def startup():
    logger.info("[Dream API] 做梦模式服务启动（HTTP API 模式，不依赖 retrieval_client）")
    config = app.state.dream_config.get()
    config["embedding_model"] = "sentence-transformers/all-MiniLM-L6-v2"
    app.state.dream_engine = DreamEngine(config, app.state.dream_state)


@app.get("/memories/dream/status")
async def get_status():
    state = app.state.dream_state
    return {"status": state.status, "run_id": state.get("run_id"), "phase": state.get("phase"),
            "started_at": state.get("started_at"), "completed_at": state.get("completed_at"),
            "progress": state.get("progress", 0.0), "can_resume": state.get("can_resume", False),
            "last_error": state.get("last_error")}


@app.post("/memories/dream/run")
async def run_dream(req: DreamRunRequest = DreamRunRequest()):
    if app.state.dream_state.is_running:
        raise HTTPException(status_code=409, detail="已有任务在运行中，请稍后再试或先调用 /memories/dream/stop")
    config = app.state.dream_config.get()
    engine = DreamEngine(config, app.state.dream_state)
    app.state.dream_engine = engine
    ok = engine.start_async(dry_run=req.dry_run, modules=req.modules)
    if not ok:
        raise HTTPException(status_code=409, detail="启动失败，已有任务在运行")
    return {"message": "做梦任务已启动", "run_id": app.state.dream_state.get("run_id"),
            "dry_run": req.dry_run, "status_url": "/memories/dream/status"}


@app.post("/memories/dream/stop")
async def stop_dream():
    if not app.state.dream_state.is_running:
        raise HTTPException(status_code=400, detail="当前没有正在运行的任务")
    if app.state.dream_engine:
        app.state.dream_engine.stop()
    app.state.dream_state.update(status="stopping")
    return {"message": "停止信号已发送，请等待当前批次完成"}


@app.get("/memories/dream/report")
async def get_report():
    report = app.state.dream_state.get("last_report")
    if not report:
        raise HTTPException(status_code=404, detail="没有找到上次运行报告")
    return report


@app.get("/memories/dream/config")
async def get_config():
    return app.state.dream_config.get()


@app.put("/memories/dream/config")
async def update_config(req: DreamConfigUpdateRequest):
    new_config = app.state.dream_config.update(req.config)
    if app.state.dream_engine:
        app.state.dream_engine.config = new_config
    return {"message": "配置已更新", "config": new_config}


# ── 独立运行入口 ──────────────────────────────────────────────────────────────
def main():
    import argparse, uvicorn
    parser = argparse.ArgumentParser(description="Dream Maintenance Service")
    parser.add_argument("--port", type=int, default=8001, help="服务端口（默认8001）")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    args = parser.parse_args()
    print("=" * 60)
    print("做梦模式服务（Dream Maintenance）")
    print("=" * 60)
    print(f"API 文档: http://localhost:{args.port}/docs")
    print(f"端点:")
    print(f"  POST /memories/dream/run     触发做梦")
    print(f"  GET  /memories/dream/status  查看状态")
    print(f"  POST /memories/dream/stop    停止")
    print(f"  GET  /memories/dream/report  报告")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
