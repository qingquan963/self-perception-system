#!/usr/bin/env python3
"""
state_db.py - SQLite 状态持久化模块
管理服务状态快照、事件日志、资源告警
"""
import sqlite3
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

logger = logging.getLogger("state_db")

# ─── 数据库路径 ────────────────────────────────────────────────────
_db_path: Optional[Path] = None
_local = threading.local()


def init_db(db_path: Path):
    """初始化数据库路径"""
    global _db_path
    _db_path = db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _create_tables()


def get_db_path() -> Path:
    """获取数据库路径"""
    if _db_path is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")
    return _db_path


@contextmanager
def get_connection():
    """获取数据库连接的上下文管理器"""
    conn = getattr(_local, "conn", None)
    should_close = False

    if conn is None:
        conn = sqlite3.connect(str(get_db_path()), timeout=10)
        conn.row_factory = sqlite3.Row
        _local.conn = conn
        should_close = True

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()
            _local.conn = None


def _create_tables():
    """创建数据库表"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 服务状态快照表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                port INTEGER,
                pid INTEGER,
                last_health_check_at TEXT,
                last_health_check_result TEXT,
                restart_count_hourly INTEGER DEFAULT 0,
                memory_mb REAL,
                cpu_percent REAL,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # 事件日志表（append-only）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                detail TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # 资源告警表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resource_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                value REAL,
                threshold REAL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # 重启计数表（用于每小时限制）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS restart_counts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT NOT NULL UNIQUE,
                count INTEGER DEFAULT 0,
                window_start TEXT DEFAULT (strftime('%Y-%m-%d %H:00:00', 'now'))
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_service
            ON events(service_name, created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_resource_alerts_service
            ON resource_alerts(service_name, created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_service_states_name
            ON service_states(service_name)
        """)

        conn.commit()
        logger.info(f"数据库表初始化完成: {get_db_path()}")


# ─── 服务状态操作 ─────────────────────────────────────────────────

def upsert_service_state(
    service_name: str,
    status: str,
    port: Optional[int] = None,
    pid: Optional[int] = None,
    last_health_check_at: Optional[str] = None,
    last_health_check_result: Optional[str] = None,
    memory_mb: Optional[float] = None,
    cpu_percent: Optional[float] = None
):
    """更新或插入服务状态（upsert）"""
    now = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO service_states (
                service_name, status, port, pid,
                last_health_check_at, last_health_check_result,
                memory_mb, cpu_percent, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(service_name) DO UPDATE SET
                status = excluded.status,
                port = excluded.port,
                pid = excluded.pid,
                last_health_check_at = excluded.last_health_check_at,
                last_health_check_result = excluded.last_health_check_result,
                memory_mb = excluded.memory_mb,
                cpu_percent = excluded.cpu_percent,
                updated_at = excluded.updated_at
        """, (
            service_name, status, port, pid,
            last_health_check_at, last_health_check_result,
            memory_mb, cpu_percent, now
        ))


def get_service_state(service_name: str) -> Optional[Dict[str, Any]]:
    """获取服务状态"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM service_states WHERE service_name = ?",
            (service_name,)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def get_all_service_states() -> List[Dict[str, Any]]:
    """获取所有服务状态"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM service_states ORDER BY service_name")
        return [dict(row) for row in cursor.fetchall()]


def update_service_state_field(service_name: str, **kwargs):
    """更新服务状态单个字段"""
    if not kwargs:
        return
    set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [service_name]
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE service_states SET {set_clause}, updated_at = datetime('now') WHERE service_name = ?",
            values
        )


# ─── 事件日志操作 ─────────────────────────────────────────────────

def log_event(service_name: str, event_type: str, detail: Optional[str] = None):
    """
    记录事件（append-only）

    event_type: 'started' | 'stopped' | 'crashed' | 'restarted' | 'threshold_exceeded' | 'resource_alert'
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO events (service_name, event_type, detail)
            VALUES (?, ?, ?)
        """, (service_name, event_type, detail))
        logger.info(f"[{service_name}] 事件: {event_type} - {detail}")


def get_events(
    service_name: Optional[str] = None,
    event_type: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """查询事件日志"""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM events WHERE 1=1"
        params = []

        if service_name:
            query += " AND service_name = ?"
            params.append(service_name)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if since:
            query += " AND created_at >= ?"
            params.append(since.isoformat())

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


# ─── 资源告警操作 ─────────────────────────────────────────────────

def log_resource_alert(
    service_name: str,
    resource_type: str,
    value: float,
    threshold: float
):
    """记录资源超限告警"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO resource_alerts (service_name, resource_type, value, threshold)
            VALUES (?, ?, ?, ?)
        """, (service_name, resource_type, value, threshold))
        log_event(service_name, "resource_alert",
                  f"{resource_type.upper()} {value:.1f} > 阈值 {threshold:.1f}")


def get_resource_alerts(
    service_name: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """查询资源告警"""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM resource_alerts WHERE 1=1"
        params = []

        if service_name:
            query += " AND service_name = ?"
            params.append(service_name)
        if since:
            query += " AND created_at >= ?"
            params.append(since.isoformat())

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


# ─── 重启计数操作 ─────────────────────────────────────────────────

def get_restart_count(service_name: str, last_hour: bool = True) -> int:
    """获取服务重启次数"""
    with get_connection() as conn:
        cursor = conn.cursor()

        if last_hour:
            # 检查是否在当前小时窗口
            cursor.execute("""
                SELECT count, window_start FROM restart_counts
                WHERE service_name = ?
            """, (service_name,))
            row = cursor.fetchone()
            if row:
                window_start_str = row["window_start"]
                if window_start_str is None:
                    return 0
                window_start = datetime.fromisoformat(str(window_start_str))
                # 使用 UTC 时间比较（SQLite strftime('now') 返回 UTC）
                from datetime import timezone
                now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                if now_utc - window_start > timedelta(hours=1):
                    # 窗口过期，重置计数
                    cursor.execute("""
                        UPDATE restart_counts
                        SET count = 0, window_start = strftime('%Y-%m-%d %H:00:00', 'now')
                        WHERE service_name = ?
                    """, (service_name,))
                    return 0
                return row["count"]
            return 0
        else:
            cursor.execute(
                "SELECT count FROM restart_counts WHERE service_name = ?",
                (service_name,)
            )
            row = cursor.fetchone()
            return row["count"] if row else 0


def increment_restart_count(service_name: str):
    """增加重启计数"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO restart_counts (service_name, count, window_start)
            VALUES (?, 1, strftime('%Y-%m-%d %H:00:00', 'now'))
            ON CONFLICT(service_name) DO UPDATE SET
                count = count + 1
        """, (service_name,))


def reset_restart_count(service_name: str):
    """重置重启计数"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE restart_counts
            SET count = 0, window_start = strftime('%Y-%m-%d %H:00:00', 'now')
            WHERE service_name = ?
        """, (service_name,))


# ─── 健康检查状态更新 ─────────────────────────────────────────────

def update_health_check(
    service_name: str,
    result: str,  # 'ok' | 'failed'
    memory_mb: Optional[float] = None,
    cpu_percent: Optional[float] = None
):
    """更新健康检查结果"""
    now = datetime.now().isoformat()
    status = "running" if result == "ok" else "stopped"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO service_states (
                service_name, status, last_health_check_at,
                last_health_check_result, memory_mb, cpu_percent, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(service_name) DO UPDATE SET
                status = excluded.status,
                last_health_check_at = excluded.last_health_check_at,
                last_health_check_result = excluded.last_health_check_result,
                memory_mb = excluded.memory_mb,
                cpu_percent = excluded.cpu_percent,
                updated_at = excluded.updated_at
        """, (
            service_name, status, now, result,
            memory_mb, cpu_percent, now
        ))


# ─── 数据库维护 ──────────────────────────────────────────────────

def cleanup_old_events(hours: int = 24):
    """清理超过指定时间的旧事件"""
    cutoff = datetime.now() - timedelta(hours=hours)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM events WHERE created_at < ?",
            (cutoff.isoformat(),)
        )
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"清理了 {deleted} 条旧事件记录")


def get_db_stats() -> Dict[str, int]:
    """获取数据库统计信息"""
    with get_connection() as conn:
        cursor = conn.cursor()
        stats = {}
        for table in ["service_states", "events", "resource_alerts", "restart_counts"]:
            cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
            stats[table] = cursor.fetchone()["cnt"]
        return stats
