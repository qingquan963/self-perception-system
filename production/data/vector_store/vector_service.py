#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
向量存储服务 v2.1
- 5种类型体系：conversation / knowledge / task / lesson / user_preference
- knowledge 子类型：price / market / reference / api_result / doc
- 过期机制：knowledge 类型支持 expire_at 自动清理
- 来源标记：source 字段标注数据来源
- 自动去重：写入时检测相似度，分三层处理（0.95+合并/0.85-0.95保留历史/0.70-0.85标记相关）
- 重要度自动评分：1-5分（访问热度+时间衰减+信号词+显式标记）
- 主动召回：POST /memories/recall 综合排序 + 自动更新访问统计
"""

import json
import logging
import sqlite3
import os
import sys
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import numpy as np

# 确保 stdout 使用 UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ── 嵌入模型（懒加载）────────────────────────────────────────
_embed_model = None
_embed_lock = threading.Lock()
EMBED_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# ── 召回统计（模块级别）────────────────────────────────────────
_recall_stats = {"count": 0, "total_results": 0, "last_time": None, "last_context_preview": ""}
_recall_lock = threading.Lock()

def get_embed_model():
    global _embed_model
    if _embed_model is None:
        with _embed_lock:
            if _embed_model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    import sentence_transformers as st_pkg
                    st_ver = getattr(st_pkg, '__version__', '0')
                    logger.info(f"加载嵌入模型: {EMBED_MODEL_NAME}  (sentence-transformers {st_ver})")
                    # sentence-transformers 3.x+ 不再需要 trust_remote_code，但 device 明确指定更稳
                    _embed_model = SentenceTransformer(EMBED_MODEL_NAME, device="cpu")
                    logger.info("嵌入模型加载完成")
                except Exception as e:
                    logger.error(f"嵌入模型加载失败: {e}")
    return _embed_model

def encode_vector(text: str) -> Optional[bytes]:
    """
    生成向量。
    兼容 sentence-transformers 2.x / 3.x / 5.x：
    - 使用 convert_to_numpy=True 强制返回 ndarray（5.x 默认返回 Tensor）
    - batch_size=1 + show_progress_bar=False 避免内部 tqdm/tokenizer 访问旧 key
    """
    model = get_embed_model()
    if model is None:
        logger.warning("Model not loaded, skipping vectorization")
        return None
    try:
        vec = model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=False,
            batch_size=1,
            show_progress_bar=False,
        )
        # 保险：如果还是 Tensor，手动转
        if not isinstance(vec, np.ndarray):
            if hasattr(vec, 'cpu'):
                vec = vec.cpu().numpy()
            else:
                vec = np.array(vec)
        return vec.astype(np.float32).tobytes()
    except Exception as e:
        logger.warning(f"Vector encode failed: {e}")
        return None

def decode_vector(blob) -> Optional[np.ndarray]:
    if blob is None:
        return None
    try:
        return np.frombuffer(bytes(blob), dtype=np.float32)
    except Exception:
        return None

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a is None or b is None:
        return 0.0
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))

def strip_vector(mem: dict) -> dict:
    if isinstance(mem, dict):
        mem.pop('vector', None)
    return mem

# ── 类型体系定义 ─────────────────────────────────────────────
TYPE_CONFIG = {
    # 核心5种类型
    "conversation":    {"name": "对话记忆",   "permanent": False, "default_expire_days": None},
    "knowledge":       {"name": "知识数据",   "permanent": False, "default_expire_days": 30},
    "task":            {"name": "任务与决策", "permanent": False, "default_expire_days": None},
    "lesson":          {"name": "经验教训",   "permanent": True,  "default_expire_days": None},
    "user_preference": {"name": "用户偏好",   "permanent": True,  "default_expire_days": None},
}

# knowledge 子类型及默认过期天数
KNOWLEDGE_TYPE_CONFIG = {
    "price":      {"name": "价格数据",   "expire_days": 7},
    "market":     {"name": "市场调研",   "expire_days": 14},
    "reference":  {"name": "参考资料",   "expire_days": None},   # 永久
    "api_result": {"name": "API结果",    "expire_days": 3},
    "doc":        {"name": "技术文档",   "expire_days": None},   # 永久
}

# 来源类型
SOURCE_TYPES = {
    "user_said":   "猫爸说的",
    "ai_summary":  "AI总结",
    "web_crawl":   "网页抓取",
    "api_result":  "API返回",
    "system":      "系统生成",
}

# 信号词：出现这些词的内容被认为更重要
IMPORTANCE_SIGNAL_WORDS = [
    "重要", "必须", "关键", "核心", "优先", "务必", "切记",
    "never", "always", "critical", "important", "must", "key", "essential",
]

def calc_importance(content: str, mem_type: str, metadata: dict,
                    access_count: int = 0, last_accessed_at: str = None) -> int:
    """
    自动计算重要度 1-5
    维度：类型权重 + 内容长度 + 信号词 + 访问热度 + 时间衰减 + 显式标记
    """
    score = 1

    # 维度1：内容长度
    if len(content) > 50:
        score += 1
    if len(content) > 200:
        score += 1

    # 维度2：类型权重
    if mem_type in ("lesson", "user_preference"):
        score += 2
    elif mem_type in ("task", "knowledge"):
        score += 1

    # 维度3：信号词
    content_lower = content.lower()
    signal_hits = sum(1 for w in IMPORTANCE_SIGNAL_WORDS if w in content_lower)
    if signal_hits >= 1:
        score += 1
    if signal_hits >= 3:
        score += 1

    # 维度4：访问热度（access_count）
    if access_count >= 5:
        score += 1
    if access_count >= 15:
        score += 1

    # 维度5：时间衰减（最近7天被访问过 → +1）
    if last_accessed_at and access_count > 0:
        try:
            last_dt = datetime.fromisoformat(last_accessed_at.replace("Z", "+00:00").replace("+00:00", ""))
            days_since = (datetime.now() - last_dt).days
            if days_since <= 7:
                score += 1
        except Exception:
            pass

    # 维度6：显式标记（最高优先级，直接覆盖计算值）
    meta_imp = metadata.get("importance", "")
    if isinstance(meta_imp, int):
        score = meta_imp
    elif meta_imp in ("high", "critical", "3"):
        score = 4
    elif meta_imp == "5":
        score = 5
    elif meta_imp == "4":
        score = 4
    elif meta_imp in ("low", "1"):
        score = 1

    return max(1, min(score, 5))

def calc_expire_at(mem_type: str, knowledge_type: str, expire_days_override=None) -> Optional[str]:
    """计算过期时间"""
    if expire_days_override is not None:
        return (datetime.now() + timedelta(days=int(expire_days_override))).isoformat()
    if mem_type == "knowledge":
        kt_cfg = KNOWLEDGE_TYPE_CONFIG.get(knowledge_type or "market", {})
        days = kt_cfg.get("expire_days")
        if days:
            return (datetime.now() + timedelta(days=days)).isoformat()
    return None


class VectorStorage:
    def __init__(self, db_path: str = "vectors.db"):
        self.db_path = db_path
        self._init_database()
        logger.info(f"向量存储初始化完成: {db_path}")

    def _init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vectors (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                content           TEXT NOT NULL,
                vector            BLOB,
                metadata          TEXT,
                vector_type       TEXT,
                type              TEXT,
                type_name         TEXT,
                importance        INTEGER DEFAULT 1,
                source            TEXT DEFAULT NULL,
                knowledge_type    TEXT DEFAULT NULL,
                expire_at         TIMESTAMP DEFAULT NULL,
                access_count      INTEGER DEFAULT 0,
                last_accessed_at  TIMESTAMP DEFAULT NULL,
                created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # 兼容旧库：补充缺失字段
        for col, defn in [
            ("source", "TEXT DEFAULT NULL"),
            ("knowledge_type", "TEXT DEFAULT NULL"),
            ("expire_at", "TIMESTAMP DEFAULT NULL"),
            ("access_count", "INTEGER DEFAULT 0"),
            ("last_accessed_at", "TIMESTAMP DEFAULT NULL"),
        ]:
            try:
                cursor.execute(f"ALTER TABLE vectors ADD COLUMN {col} {defn}")
            except Exception:
                pass
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_type ON vectors(type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_expire_at ON vectors(expire_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON vectors(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_importance ON vectors(importance)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_count ON vectors(access_count)')
        conn.commit()
        conn.close()

    def _purge_expired(self):
        """清理已过期的 knowledge 记录"""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            now = datetime.now().isoformat()
            cur.execute("DELETE FROM vectors WHERE expire_at IS NOT NULL AND expire_at < ?", (now,))
            deleted = cur.rowcount
            conn.commit()
            conn.close()
            if deleted:
                logger.info(f"清理过期记录: {deleted} 条")
            return deleted
        except Exception as e:
            logger.error(f"清理过期记录失败: {e}")
            return 0

    def add_memory(self, memory: Dict[str, Any]) -> dict:
        """
        写入记忆。
        返回: {"status": "added"|"updated"|"skipped", "id": int, "similarity": float}
        """
        try:
            content = memory.get("content", "").strip()
            if not content:
                return {"status": "skipped", "reason": "内容为空"}

            mem_type = memory.get("type", "conversation")
            if mem_type not in TYPE_CONFIG:
                logger.warning(f"未知类型 {mem_type}，回退到 conversation")
                mem_type = "conversation"

            type_name = TYPE_CONFIG[mem_type]["name"]
            knowledge_type = memory.get("knowledge_type") if mem_type == "knowledge" else None
            source = memory.get("source", "ai_summary")

            # metadata 处理
            extra_meta = memory.get("metadata", {})
            if isinstance(extra_meta, str):
                try:
                    extra_meta = json.loads(extra_meta)
                except Exception:
                    extra_meta = {}

            # 重要度
            importance = memory.get("importance") or calc_importance(content, mem_type, extra_meta)

            # 过期时间
            expire_at = calc_expire_at(
                mem_type, knowledge_type,
                memory.get("expire_days") or extra_meta.get("expire_days")
            )

            # 生成向量
            vector_blob = encode_vector(content)

            # ── 自动去重：分层阈值处理 ──────────────────────────────
            # 0.95+ 直接合并（内容几乎相同）
            # 0.85-0.95 合并但保留 merge_history
            # 0.70-0.85 标记为 related 记录但不合并
            MERGE_THRESHOLD = 0.95
            DEDUP_THRESHOLD = 0.85
            RELATED_THRESHOLD = 0.70
            if vector_blob is not None:
                new_np = decode_vector(vector_blob)
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                ccur = conn.cursor()
                ccur.execute(
                    "SELECT rowid, content, vector, metadata FROM vectors WHERE vector IS NOT NULL AND type = ?",
                    (mem_type,)
                )
                candidates = []  # (similarity, rowid, content, metadata)
                for row in ccur.fetchall():
                    try:
                        vec_blob = row["vector"]
                    except Exception as row_err:
                        logger.warning(f"Row access error: {row_err}, row keys: {row.keys()}")
                        continue
                    if vec_blob is None:
                        continue
                    try:
                        if not isinstance(vec_blob, bytes):
                            vec_blob = bytes(vec_blob)
                        old_vec = decode_vector(vec_blob)
                    except Exception:
                        old_vec = None
                    if old_vec is not None and len(old_vec) == len(new_np):
                        sim = cosine_similarity(new_np, old_vec)
                        if sim >= RELATED_THRESHOLD:
                            old_meta = {}
                            try:
                                old_meta = json.loads(row["metadata"]) if row["metadata"] else {}
                            except Exception:
                                pass
                            candidates.append((sim, row["rowid"], row["content"], old_meta))
                conn.close()

                # 按相似度降序
                candidates.sort(key=lambda x: x[0], reverse=True)

                if candidates:
                    best_sim, best_id, best_content, best_meta = candidates[0]

                    if best_sim >= MERGE_THRESHOLD:
                        # ── 0.95+：直接合并，无痕覆盖 ─────────
                        conn = sqlite3.connect(self.db_path)
                        cur = conn.cursor()
                        # 累加访问计数
                        cur.execute("SELECT access_count, last_accessed_at FROM vectors WHERE rowid=?", (best_id,))
                        old_row = cur.fetchone()
                        old_access = (old_row[0] or 0) if old_row else 0
                        cur.execute("""
                            UPDATE vectors SET content=?, vector=?, metadata=?, importance=?,
                                source=?, knowledge_type=?, expire_at=?, updated_at=?,
                                access_count=?
                            WHERE rowid=?
                        """, (
                            content, vector_blob,
                            json.dumps(extra_meta, ensure_ascii=False),
                            importance, source, knowledge_type, expire_at,
                            datetime.now().isoformat(),
                            old_access,  # 保留原访问计数
                            best_id
                        ))
                        conn.commit()
                        conn.close()
                        logger.info(f"完全合并: id={best_id}, sim={best_sim:.4f}, type={mem_type}")
                        return {"status": "merged", "id": best_id, "similarity": round(best_sim, 4), "dedup_level": "full_merge"}

                    elif best_sim >= DEDUP_THRESHOLD:
                        # ── 0.85-0.95：合并但保留 merge_history ────
                        merge_entry = {
                            "merged_at": datetime.now().isoformat(),
                            "similarity": round(best_sim, 4),
                            "old_content_preview": best_content[:100] + ("..." if len(best_content) > 100 else ""),
                            "new_content_preview": content[:100] + ("..." if len(content) > 100 else ""),
                        }
                        merge_history = best_meta.get("merge_history", [])
                        if isinstance(merge_history, str):
                            try:
                                merge_history = json.loads(merge_history)
                            except Exception:
                                merge_history = []
                        merge_history.append(merge_entry)
                        extra_meta["merge_history"] = merge_history[-10:]  # 最多保留10条历史

                        conn = sqlite3.connect(self.db_path)
                        cur = conn.cursor()
                        cur.execute("SELECT access_count FROM vectors WHERE rowid=?", (best_id,))
                        old_row = cur.fetchone()
                        old_access = (old_row[0] or 0) if old_row else 0
                        cur.execute("""
                            UPDATE vectors SET content=?, vector=?, metadata=?, importance=?,
                                source=?, knowledge_type=?, expire_at=?, updated_at=?,
                                access_count=?
                            WHERE rowid=?
                        """, (
                            content, vector_blob,
                            json.dumps(extra_meta, ensure_ascii=False),
                            importance, source, knowledge_type, expire_at,
                            datetime.now().isoformat(),
                            old_access,
                            best_id
                        ))
                        conn.commit()
                        conn.close()
                        logger.info(f"去重更新(含历史): id={best_id}, sim={best_sim:.4f}, type={mem_type}")
                        return {"status": "updated", "id": best_id, "similarity": round(best_sim, 4), "dedup_level": "soft_merge"}

                    elif best_sim >= RELATED_THRESHOLD:
                        # ── 0.70-0.85：标记为相关但不合并，继续新增 ──
                        extra_meta["related_to"] = {
                            "id": best_id,
                            "similarity": round(best_sim, 4),
                            "detected_at": datetime.now().isoformat(),
                        }
                        # 不 return，继续走新增流程
                        logger.info(f"相关记录: id={best_id}, sim={best_sim:.4f}, 标记related但不合并")

            # ── 新增记录 ─────────────────────────────────────────
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            now = datetime.now().isoformat()
            cur.execute("""
                INSERT INTO vectors
                    (content, vector, metadata, vector_type, type, type_name,
                     importance, source, knowledge_type, expire_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                content, vector_blob,
                json.dumps(extra_meta, ensure_ascii=False),
                mem_type, mem_type, type_name,
                importance, source, knowledge_type, expire_at, now, now
            ))
            new_id = cur.lastrowid
            conn.commit()
            conn.close()
            logger.info(f"新增记忆: id={new_id}, type={mem_type}, source={source}, expire_at={expire_at}")
            return {"status": "added", "id": new_id, "similarity": 0.0}

        except Exception as e:
            logger.error(f"写入记忆失败: {e}")
            return {"status": "error", "reason": str(e)}

    def search_memories(self, query: str, limit: int = 10, mem_type: str = None) -> List[Dict[str, Any]]:
        """语义搜索，自动过滤已过期记录，支持按 type 筛选"""
        self._purge_expired()
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            query_vec = encode_vector(query) if query else None
            if query_vec is not None:
                query_np = decode_vector(query_vec)
                sql = "SELECT * FROM vectors WHERE vector IS NOT NULL"
                params = []
                if mem_type:
                    sql += " AND type = ?"
                    params.append(mem_type)
                cur.execute(sql, params)
                rows = cur.fetchall()
                scored = []
                for row in rows:
                    mem = dict(row)
                    vec = decode_vector(mem["vector"])
                    if vec is not None and len(vec) == len(query_np):
                        score = cosine_similarity(query_np, vec)
                        scored.append((score, mem))
                scored.sort(key=lambda x: x[0], reverse=True)
                results = []
                for score, mem in scored[:limit]:
                    mem["metadata"] = json.loads(mem["metadata"]) if mem["metadata"] else {}
                    mem["similarity_score"] = round(score, 4)
                    strip_vector(mem)
                    results.append(mem)
                conn.close()
                return results

            # 回退关键词搜索
            sql = "SELECT * FROM vectors WHERE content LIKE ?"
            params = [f"%{query}%"]
            if mem_type:
                sql += " AND type = ?"
                params.append(mem_type)
            sql += " ORDER BY importance DESC, created_at DESC LIMIT ?"
            params.append(limit)
            cur.execute(sql, params)
            results = []
            for row in cur.fetchall():
                mem = dict(row)
                mem["metadata"] = json.loads(mem["metadata"]) if mem["metadata"] else {}
                strip_vector(mem)
                results.append(mem)
            conn.close()
            return results
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    def delete_memory(self, memory_id: int) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("DELETE FROM vectors WHERE rowid = ?", (memory_id,))
            ok = cur.rowcount > 0
            conn.commit()
            conn.close()
            return ok
        except Exception as e:
            logger.error(f"删除失败: {e}")
            return False

    def update_memory(self, memory_id: int, updates: Dict[str, Any]) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT rowid FROM vectors WHERE rowid = ?", (memory_id,))
            if not cur.fetchone():
                conn.close()
                return False
            set_parts, values = [], []
            if "content" in updates:
                set_parts.append("content = ?")
                values.append(updates["content"])
                new_vec = encode_vector(updates["content"])
                if new_vec:
                    set_parts.append("vector = ?")
                    values.append(new_vec)
            if "type" in updates:
                new_type = updates["type"]
                if new_type in TYPE_CONFIG:
                    set_parts += ["type = ?", "type_name = ?", "vector_type = ?"]
                    values += [new_type, TYPE_CONFIG[new_type]["name"], new_type]
            if "knowledge_type" in updates:
                set_parts.append("knowledge_type = ?")
                values.append(updates["knowledge_type"])
            if "source" in updates:
                set_parts.append("source = ?")
                values.append(updates["source"])
            if "importance" in updates:
                set_parts.append("importance = ?")
                values.append(updates["importance"])
            if "metadata" in updates:
                set_parts.append("metadata = ?")
                values.append(json.dumps(updates["metadata"], ensure_ascii=False))
            if "expire_days" in updates:
                expire_at = (datetime.now() + timedelta(days=int(updates["expire_days"]))).isoformat()
                set_parts.append("expire_at = ?")
                values.append(expire_at)
            if not set_parts:
                conn.close()
                return True
            set_parts.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(memory_id)
            cur.execute(f"UPDATE vectors SET {', '.join(set_parts)} WHERE rowid = ?", values)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"更新失败: {e}")
            return False

    def get_memory_by_id(self, memory_id: int) -> Optional[Dict[str, Any]]:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT rowid AS id, * FROM vectors WHERE rowid = ?", (memory_id,))
            row = cur.fetchone()
            conn.close()
            if not row:
                return None
            d = dict(row)
            d["metadata"] = json.loads(d.get("metadata") or "{}")
            strip_vector(d)
            return d
        except Exception as e:
            logger.error(f"获取记忆失败: {e}")
            return None

    def get_all_memories(self, limit: int = 100, mem_type: str = None) -> List[Dict[str, Any]]:
        self._purge_expired()
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if mem_type:
                cur.execute("SELECT * FROM vectors WHERE type = ? ORDER BY importance DESC, created_at DESC LIMIT ?", (mem_type, limit))
            else:
                cur.execute("SELECT * FROM vectors ORDER BY importance DESC, created_at DESC LIMIT ?", (limit,))
            results = []
            for row in cur.fetchall():
                mem = dict(row)
                mem["metadata"] = json.loads(mem["metadata"]) if mem["metadata"] else {}
                strip_vector(mem)
                results.append(mem)
            conn.close()
            return results
        except Exception as e:
            logger.error(f"获取记忆失败: {e}")
            return []

    def get_memory_count(self) -> int:
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM vectors")
            count = cur.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    def get_detailed_stats(self) -> Dict[str, Any]:
        self._purge_expired()
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM vectors")
            total = cur.fetchone()[0]
            cur.execute("SELECT type, COUNT(*) FROM vectors GROUP BY type")
            type_dist = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute("SELECT COUNT(*) FROM vectors WHERE DATE(created_at) = DATE('now')")
            today_new = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM vectors WHERE vector IS NOT NULL AND length(vector) > 4")
            vectorized = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM vectors WHERE expire_at IS NOT NULL AND expire_at > datetime('now')")
            expiring = cur.fetchone()[0]
            cur.execute("SELECT source, COUNT(*) FROM vectors GROUP BY source")
            source_dist = {r[0] or "unknown": r[1] for r in cur.fetchall()}
            cur.execute("SELECT SUM(COALESCE(access_count, 0)), AVG(COALESCE(access_count, 0)), MAX(COALESCE(access_count, 0)) FROM vectors")
            access_row = cur.fetchone()
            # 最近7天每日新增
            cur.execute("""
                SELECT DATE(created_at) as day, COUNT(*) as cnt
                FROM vectors
                WHERE created_at >= datetime('now', '-7 days')
                GROUP BY DATE(created_at)
                ORDER BY day
            """)
            weekly_trend = [{"date": r[0], "count": r[1]} for r in cur.fetchall()]
            conn.close()
            return {
                "total": total,
                "today_new": today_new,
                "type_distribution": type_dist,
                "source_distribution": source_dist,
                "access_stats": {
                    "total_accesses": access_row[0] or 0,
                    "avg_accesses": round(access_row[1] or 0, 1),
                    "max_accesses": access_row[2] or 0,
                },
                "vectorization": {
                    "vectorized": vectorized,
                    "not_vectorized": total - vectorized,
                    "ratio": round(vectorized / total * 100, 1) if total > 0 else 0,
                    "model": EMBED_MODEL_NAME,
                    "model_loaded": _embed_model is not None,
                },
                "expiring_count": expiring,
                "weekly_trend": weekly_trend,
            }
        except Exception as e:
            logger.error(f"统计失败: {e}")
            return {}

    def get_modules_status(self) -> Dict[str, Any]:
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            result = {}
            for t in TYPE_CONFIG:
                cur.execute("SELECT COUNT(*), MAX(created_at) FROM vectors WHERE type = ?", (t,))
                row = cur.fetchone()
                result[t] = {
                    "count": row[0],
                    "latest_activity": row[1],
                    "status": "active" if row[0] > 0 else "inactive",
                    "permanent": TYPE_CONFIG[t]["permanent"],
                }
            conn.close()
            return result
        except Exception as e:
            logger.error(f"模块状态失败: {e}")
            return {}

    def cleanup_memories(self, keep_recent_days: int = 30, keep_per_type: int = 20,
                         dry_run: bool = False, max_content_length: int = 0) -> dict:
        """清理旧记忆（永久类型不清理）。max_content_length > 0 时，同时清理超长内容记录。"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        deleted_ids = []
        
        # 新增：清理超长内容记录（非 knowledge 类型，避免误删有价值的知识）
        if max_content_length > 0:
            cur.execute("""
                SELECT id FROM vectors 
                WHERE LENGTH(content) > ? 
                AND COALESCE(type, 'conversation') NOT IN ('knowledge', 'user_preference')
            """, (max_content_length,))
            long_ids = [r[0] for r in cur.fetchall()]
            deleted_ids.extend(long_ids)
        
        permanent_types = [t for t, cfg in TYPE_CONFIG.items() if cfg["permanent"]]
        placeholders = ",".join("?" * len(permanent_types))
        cutoff = (datetime.now() - timedelta(days=keep_recent_days)).isoformat()
        cur.execute(
            f"SELECT id FROM vectors WHERE created_at < ? AND type NOT IN ({placeholders})",
            (cutoff, *permanent_types)
        )
        deleted_ids.extend([r[0] for r in cur.fetchall()])
        for t in TYPE_CONFIG:
            if TYPE_CONFIG[t]["permanent"]:
                continue
            cur.execute("SELECT id FROM vectors WHERE type = ? ORDER BY created_at DESC", (t,))
            all_ids = [r[0] for r in cur.fetchall()]
            for oid in all_ids[keep_per_type:]:
                if oid not in deleted_ids:
                    deleted_ids.append(oid)
        total_candidates = len(deleted_ids)
        actual_deleted = 0
        if not dry_run and deleted_ids:
            ph = ",".join("?" * len(deleted_ids))
            cur.execute(f"DELETE FROM vectors WHERE id IN ({ph})", deleted_ids)
            actual_deleted = cur.rowcount
            conn.commit()
        conn.close()
        return {
            "dry_run": dry_run,
            "candidates": total_candidates,
            "deleted": actual_deleted,
            "remaining": self.get_memory_count(),
        }

    def _bump_access(self, memory_ids: List[int]):
        """批量更新访问计数和最后访问时间"""
        if not memory_ids:
            return
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            now = datetime.now().isoformat()
            for mid in memory_ids:
                cur.execute(
                    "UPDATE vectors SET access_count = COALESCE(access_count, 0) + 1, last_accessed_at = ? WHERE rowid = ?",
                    (now, mid)
                )
            conn.commit()
            conn.close()
            logger.info(f"更新访问统计: {len(memory_ids)} 条记录")
        except Exception as e:
            logger.error(f"更新访问统计失败: {e}")

    def recall_memories(self, context: str, limit: int = 10,
                        mem_types: List[str] = None,
                        similarity_weight: float = 0.6,
                        importance_weight: float = 0.4) -> List[Dict[str, Any]]:
        """
        主动召回：综合相似度+重要度排序，自动更新访问统计。
        返回每条结果附带 recall_reason 说明召回原因。
        """
        self._purge_expired()
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            query_vec = encode_vector(context) if context else None
            recalled_ids = []

            if query_vec is not None:
                query_np = decode_vector(query_vec)
                sql = "SELECT * FROM vectors WHERE vector IS NOT NULL"
                params = []
                if mem_types:
                    placeholders = ",".join("?" * len(mem_types))
                    sql += f" AND type IN ({placeholders})"
                    params.extend(mem_types)
                cur.execute(sql, params)
                rows = cur.fetchall()

                scored = []
                for row in rows:
                    mem = dict(row)
                    vec = decode_vector(mem["vector"])
                    if vec is not None and len(vec) == len(query_np):
                        sim = cosine_similarity(query_np, vec)

                        # 重要度归一化到 0-1
                        raw_importance = mem.get("importance", 1) or 1
                        norm_importance = raw_importance / 5.0

                        # 综合评分
                        composite = sim * similarity_weight + norm_importance * importance_weight

                        # 召回原因
                        reasons = []
                        if sim >= 0.8:
                            reasons.append(f"高度相关(相似度{sim:.2f})")
                        elif sim >= 0.5:
                            reasons.append(f"语义相关(相似度{sim:.2f})")
                        if raw_importance >= 4:
                            reasons.append(f"重要度高({raw_importance}/5)")
                        mem_access = mem.get("access_count", 0) or 0
                        if mem_access >= 10:
                            reasons.append(f"高频访问({mem_access}次)")
                        if not reasons:
                            reasons.append(f"综合评分{composite:.2f}")

                        scored.append((composite, sim, mem))

                scored.sort(key=lambda x: x[0], reverse=True)
                results = []
                for composite, sim, mem in scored[:limit]:
                    mem["metadata"] = json.loads(mem["metadata"]) if mem["metadata"] else {}
                    mem["similarity_score"] = round(sim, 4)
                    mem["composite_score"] = round(composite, 4)
                    reasons = []
                    if sim >= 0.8:
                        reasons.append(f"高度相关(相似度{sim:.2f})")
                    elif sim >= 0.5:
                        reasons.append(f"语义相关(相似度{sim:.2f})")
                    if (mem.get("importance") or 1) >= 4:
                        reasons.append(f"重要度高({mem.get('importance')}/5)")
                    if (mem.get("access_count") or 0) >= 10:
                        reasons.append(f"高频访问({mem.get('access_count')}次)")
                    if not reasons:
                        reasons.append(f"综合评分{composite:.2f}")
                    mem["recall_reason"] = " | ".join(reasons)
                    strip_vector(mem)
                    results.append(mem)
                    recalled_ids.append(mem["id"])
                conn.close()
            else:
                # 回退：按重要度+访问数排序
                sql = "SELECT * FROM vectors"
                params = []
                if mem_types:
                    placeholders = ",".join("?" * len(mem_types))
                    sql += f" AND type IN ({placeholders})"
                    params.extend(mem_types)
                sql += " ORDER BY importance DESC, COALESCE(access_count, 0) DESC, created_at DESC LIMIT ?"
                params.append(limit)
                cur.execute(sql, params)
                results = []
                for row in cur.fetchall():
                    mem = dict(row)
                    mem["metadata"] = json.loads(mem["metadata"]) if mem["metadata"] else {}
                    mem["similarity_score"] = 0.0
                    mem["composite_score"] = round((mem.get("importance") or 1) / 5.0 * importance_weight, 4)
                    mem["recall_reason"] = f"重要度排序({mem.get('importance')}/5)"
                    strip_vector(mem)
                    results.append(mem)
                    recalled_ids.append(mem["id"])
                conn.close()

            # 异步更新访问统计
            self._bump_access(recalled_ids)
            return results

        except Exception as e:
            logger.error(f"召回失败: {e}")
            return []


# ── FastAPI 应用 ─────────────────────────────────────────────
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
import uvicorn

app = FastAPI(title="向量存储服务 v2.1", version="2.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

vector_storage = VectorStorage()

# 强制 UTF-8 响应
@app.middleware("http")
async def add_utf8_header(request, call_next):
    response = await call_next(request)
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response


@app.get("/")
async def root():
    return {"service": "向量存储服务", "version": "2.1.0", "status": "running",
            "types": list(TYPE_CONFIG.keys()), "timestamp": datetime.now().isoformat()}

@app.get("/health")
async def health():
    count = vector_storage.get_memory_count()
    return {"status": "healthy", "version": "2.1.0", "memory_count": count,
            "timestamp": datetime.now().isoformat()}

@app.get("/memories")
async def get_memories(limit: int = 100, type: str = None):
    memories = vector_storage.get_all_memories(limit, mem_type=type)
    return {"count": len(memories), "memories": memories, "timestamp": datetime.now().isoformat()}

@app.get("/memories/search")
async def search_memories(query: str, limit: int = 10, type: str = None):
    memories = await run_in_threadpool(vector_storage.search_memories, query, limit, type)
    return {"query": query, "count": len(memories), "memories": memories,
            "timestamp": datetime.now().isoformat()}

# ── 3-Layer Memory Retrieval (借鉴 claude-mem 的渐进式披露) ──────────────────

def _compact_memory(mem: dict, similarity_score: float = None) -> dict:
    """
    将完整记忆压缩为 Layer 1 紧凑索引。
    只保留：id, type, content_preview, importance, source, created_at, similarity_score, metadata(keys only)
    """
    content = mem.get("content", "")
    preview = content[:100] + "..." if len(content) > 100 else content
    compact = {
        "id": mem.get("id"),
        "type": mem.get("type"),
        "type_name": mem.get("type_name"),
        "source": mem.get("source"),
        "importance": mem.get("importance", 1),
        "created_at": mem.get("created_at"),
        "content_preview": preview,
        "metadata_keys": list(mem.get("metadata", {}).keys()) if mem.get("metadata") else [],
        "knowledge_type": mem.get("knowledge_type"),
        "expire_at": mem.get("expire_at"),
    }
    if similarity_score is not None:
        compact["similarity_score"] = round(similarity_score, 4)
    return compact


@app.get("/memories/index")
async def memories_index(query: str, limit: int = 10, type: str = None):
    """
    Layer 1 - 紧凑索引：快速返回搜索结果概览，不含完整内容。
    每次工具调用先用这个，再用 timeline/get_observations 取详情。
    """
    memories = await run_in_threadpool(vector_storage.search_memories, query, limit, type)
    compact_results = []
    for mem in memories:
        score = mem.pop("similarity_score", None) if isinstance(mem, dict) else None
        compact_results.append(_compact_memory(mem, score))
    return {
        "query": query,
        "count": len(compact_results),
        "memories": compact_results,
        "note": "Layer 1: 完整详情请用 POST /memories/batch 或 GET /memories/{id}/timeline",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/memories/{memory_id}/timeline")
async def memories_timeline(memory_id: int, radius: int = 3):
    """
    Layer 2 - 时间线上下文：获取指定记忆及其前后各 radius 条记忆。
    用于理解某个事件发生时的上下文。
    """
    mem = vector_storage.get_memory_by_id(memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail=f"记忆 id={memory_id} 不存在")
    # get_memory_by_id 已解析 metadata 和 strip_vector，这里不需要重复处理

    # 获取同一时间窗口的所有记忆，按 created_at 排序，找当前位置
    conn = sqlite3.connect(vector_storage.db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM vectors ORDER BY created_at ASC"
    )
    all_rows = cur.fetchall()
    conn.close()

    # 找到当前记忆的位置
    all_ids = [dict(r)["id"] for r in all_rows]
    try:
        idx = all_ids.index(memory_id)
    except ValueError:
        idx = -1

    # 取出前后 radius 条
    start = max(0, idx - radius)
    end = min(len(all_rows), idx + radius + 1)
    surrounding = [dict(r) for r in all_rows[start:end]]

    timeline = []
    for m in surrounding:
        strip_vector(m)
        m["metadata"] = json.loads(m["metadata"]) if m.get("metadata") else {}
        m["_is_target"] = (m["id"] == memory_id)
        timeline.append(m)

    return {
        "target_id": memory_id,
        "target": mem,
        "surrounding_count": len(surrounding),
        "timeline": timeline,
        "note": "Layer 2: _is_target=true 标记目标记忆；完整详情用 POST /memories/batch",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/memories/batch")
async def memories_batch(req: Request):
    """
    Layer 3 - 批量完整详情：只对已知 ID 取完整记忆内容。
    前两步用 /memories/index 和 /memories/{id}/timeline 筛选后，再取完整内容。
    """
    body = await req.body()
    try:
        params = json.loads(body) if body else {}
    except Exception:
        params = {}
    ids = params.get("ids", [])
    if not ids or not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="ids 必须是非空列表")

    results = []
    for mid in ids:
        mem = vector_storage.get_memory_by_id(int(mid))
        if mem:
            # get_memory_by_id 已经处理过 strip_vector 和 metadata 解析
            results.append(mem)

    return {
        "count": len(results),
        "memories": results,
        "note": f"Layer 3: 共 {len(ids)} 条请求，返回 {len(results)} 条",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/memories/recall")
async def recall_memories(req: Request):
    """
    主动召回：根据上下文综合排序，返回最相关的记忆。
    Body: {
        "context": "当前上下文文本",
        "limit": 10,
        "types": ["lesson", "task"],       // 可选，限定类型
        "similarity_weight": 0.6,          // 可选，默认0.6
        "importance_weight": 0.4           // 可选，默认0.4
    }
    """
    try:
        body = await req.body()
        params = json.loads(body) if body else {}
    except Exception:
        params = {}
    context = params.get("context", "")
    if not context:
        raise HTTPException(status_code=400, detail="context 参数不能为空")
    limit = int(params.get("limit", 10))
    mem_types = params.get("types")
    if isinstance(mem_types, str):
        mem_types = [mem_types]
    sim_w = float(params.get("similarity_weight", 0.6))
    imp_w = float(params.get("importance_weight", 0.4))
    memories = await run_in_threadpool(
        vector_storage.recall_memories, context, limit, mem_types, sim_w, imp_w
    )
    # 统计
    with _recall_lock:
        _recall_stats["count"] += 1
        _recall_stats["total_results"] += len(memories)
        _recall_stats["last_time"] = datetime.now().isoformat()
        _recall_stats["last_context_preview"] = context[:80]
    return {
        "context": context,
        "count": len(memories),
        "memories": memories,
        "weights": {"similarity": sim_w, "importance": imp_w},
        "timestamp": datetime.now().isoformat()
    }

@app.post("/memories/add")
async def add_memory(memory: Dict[str, Any]):
    logger.info(f"API add_memory called: {memory}")
    try:
        result = await run_in_threadpool(vector_storage.add_memory, memory)
    except Exception as thread_err:
        logger.error(f"Thread error: {thread_err}")
        raise HTTPException(status_code=500, detail=str(thread_err))
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("reason"))
    return {**result, "timestamp": datetime.now().isoformat()}

@app.get("/memories/{memory_id}")
async def get_memory(memory_id: int):
    mem = vector_storage.get_memory_by_id(memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail=f"记忆 id={memory_id} 不存在")
    return {"memory": mem, "timestamp": datetime.now().isoformat()}

@app.delete("/memories/{memory_id}")
async def delete_memory(memory_id: int):
    ok = vector_storage.delete_memory(memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"记忆 id={memory_id} 不存在")
    return {"status": "success", "message": f"id={memory_id} 已删除", "timestamp": datetime.now().isoformat()}

@app.put("/memories/{memory_id}")
async def update_memory(memory_id: int, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    ok = await run_in_threadpool(vector_storage.update_memory, memory_id, body)
    if not ok:
        raise HTTPException(status_code=404, detail=f"记忆 id={memory_id} 不存在")
    return {"status": "success", "timestamp": datetime.now().isoformat()}

@app.get("/stats")
async def get_stats():
    return {"total_memories": vector_storage.get_memory_count(), "timestamp": datetime.now().isoformat()}

@app.get("/stats/detailed")
async def get_detailed_stats():
    return {"stats": vector_storage.get_detailed_stats(), "timestamp": datetime.now().isoformat()}

@app.get("/data/modules")
async def get_modules_status():
    return vector_storage.get_modules_status()

@app.post("/memories/cleanup")
async def cleanup_memories(req: Request):
    try:
        body = await req.body()
        params = json.loads(body) if body else {}
    except Exception:
        params = {}
    result = await run_in_threadpool(
        vector_storage.cleanup_memories,
        int(params.get("keep_recent_days", 30)),
        int(params.get("keep_per_type", 20)),
        bool(params.get("dry_run", False)),
        int(params.get("max_content_length", 0)),
    )
    return {**result, "timestamp": datetime.now().isoformat()}

@app.get("/types")
async def get_types():
    """返回类型体系定义，供龙虾参考"""
    return {
        "types": TYPE_CONFIG,
        "knowledge_subtypes": KNOWLEDGE_TYPE_CONFIG,
        "source_types": SOURCE_TYPES,
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/vectors/status")
async def vector_status():
    conn = sqlite3.connect(vector_storage.db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM vectors")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM vectors WHERE vector IS NOT NULL AND length(vector) > 4")
    vectorized = cur.fetchone()[0]
    conn.close()
    return {
        "model": EMBED_MODEL_NAME, "model_loaded": _embed_model is not None,
        "total": total, "vectorized": vectorized,
        "ratio_pct": round(vectorized / total * 100, 1) if total > 0 else 0,
        "timestamp": datetime.now().isoformat(),
    }

@app.post("/vectors/backfill")
async def backfill_vectors():
    model = get_embed_model()
    if model is None:
        return {"status": "error", "message": "嵌入模型未加载"}
    conn = sqlite3.connect(vector_storage.db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, content FROM vectors WHERE vector IS NULL OR length(vector) <= 4")
    rows = cur.fetchall()
    updated, failed = 0, 0
    for (row_id, content) in rows:
        if not content:
            continue
        blob = encode_vector(content)
        if blob:
            cur.execute("UPDATE vectors SET vector = ?, updated_at = ? WHERE id = ?",
                        (blob, datetime.now().isoformat(), row_id))
            updated += 1
        else:
            failed += 1
    conn.commit()
    conn.close()
    return {"status": "success", "updated": updated, "failed": failed,
            "timestamp": datetime.now().isoformat()}

@app.get("/data/summary")
async def get_data_summary():
    """数据摘要（前端仪表板用）"""
    stats = vector_storage.get_detailed_stats()
    count = vector_storage.get_memory_count()
    conn = sqlite3.connect(vector_storage.db_path)
    cur = conn.cursor()
    cur.execute("SELECT MIN(created_at), MAX(created_at) FROM vectors")
    row = cur.fetchone()
    conn.close()
    return {
        "total_records": count,
        "today_new": stats.get("today_new", 0),
        "earliest": row[0],
        "latest": row[1],
        "type_distribution": stats.get("type_distribution", {}),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/stats/recent")
async def get_recent_memories(limit: int = 20):
    """最近记忆（前端仪表板用）"""
    memories = vector_storage.get_all_memories(limit)
    return {
        "count": len(memories),
        "recent_memories": memories,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/stats/recall")
async def get_recall_stats():
    """召回统计（被 api_service 的 /services/monitor 聚合调用）"""
    with _recall_lock:
        stats = dict(_recall_stats)
    avg_results = round(stats["total_results"] / stats["count"], 1) if stats["count"] > 0 else 0
    return {
        **stats,
        "avg_results_per_call": avg_results,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8007)
