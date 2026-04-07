#!/usr/bin/env python3
"""
test_state_db.py - 状态数据库测试
"""
import pytest
import tempfile
import time
import os
import sys
from pathlib import Path

# 添加项目路径
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from state_db import (
    init_db, get_db_path,
    upsert_service_state, get_service_state, get_all_service_states,
    log_event, get_events,
    log_resource_alert, get_resource_alerts,
    get_restart_count, increment_restart_count, reset_restart_count,
    update_health_check, cleanup_old_events, get_db_stats
)


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_db(db_path)
        yield db_path


class TestServiceState:
    """测试服务状态操作"""

    def test_upsert_and_get_service_state(self, temp_db):
        upsert_service_state(
            service_name="test_service",
            status="running",
            port=8001,
            pid=12345
        )

        state = get_service_state("test_service")
        assert state is not None
        assert state["service_name"] == "test_service"
        assert state["status"] == "running"
        assert state["port"] == 8001
        assert state["pid"] == 12345

    def test_upsert_updates_existing(self, temp_db):
        upsert_service_state(
            service_name="test_service",
            status="running",
            port=8001
        )
        upsert_service_state(
            service_name="test_service",
            status="stopped",
            port=8002
        )

        state = get_service_state("test_service")
        assert state["status"] == "stopped"
        assert state["port"] == 8002

    def test_get_nonexistent_service(self, temp_db):
        state = get_service_state("nonexistent")
        assert state is None

    def test_get_all_service_states(self, temp_db):
        upsert_service_state("service1", "running")
        upsert_service_state("service2", "stopped")

        states = get_all_service_states()
        assert len(states) >= 2
        names = {s["service_name"] for s in states}
        assert "service1" in names
        assert "service2" in names


class TestEvents:
    """测试事件日志"""

    def test_log_and_get_events(self, temp_db):
        log_event("test_service", "started", "测试启动")
        log_event("test_service", "stopped", "测试停止")

        events = get_events(service_name="test_service")
        assert len(events) >= 2

    def test_get_events_with_type_filter(self, temp_db):
        log_event("test_service", "started", "1")
        log_event("test_service", "crashed", "2")
        log_event("test_service", "started", "3")

        events = get_events(service_name="test_service", event_type="started")
        assert all(e["event_type"] == "started" for e in events)

    def test_events_append_only(self, temp_db):
        # 事件应该是追加的
        log_event("test_service", "started", "1")
        log_event("test_service", "started", "2")

        events = get_events(service_name="test_service", limit=10)
        assert len(events) >= 2


class TestResourceAlerts:
    """测试资源告警"""

    def test_log_and_get_resource_alert(self, temp_db):
        log_resource_alert("test_service", "memory", 600.0, 512.0)

        alerts = get_resource_alerts(service_name="test_service")
        assert len(alerts) >= 1
        assert alerts[0]["resource_type"] == "memory"
        assert alerts[0]["value"] == 600.0
        assert alerts[0]["threshold"] == 512.0


class TestRestartCount:
    """测试重启计数"""

    def test_increment_and_get_restart_count(self, temp_db):
        reset_restart_count("test_service")

        count1 = get_restart_count("test_service")
        increment_restart_count("test_service")
        count2 = get_restart_count("test_service")

        assert count2 == count1 + 1

    def test_reset_restart_count(self, temp_db):
        increment_restart_count("test_service")
        increment_restart_count("test_service")

        reset_restart_count("test_service")
        count = get_restart_count("test_service")

        assert count == 0


class TestHealthCheck:
    """测试健康检查更新"""

    def test_update_health_check(self, temp_db):
        update_health_check(
            "test_service",
            result="ok",
            memory_mb=100.5,
            cpu_percent=25.0
        )

        state = get_service_state("test_service")
        assert state["last_health_check_result"] == "ok"
        assert state["memory_mb"] == 100.5
        assert state["cpu_percent"] == 25.0
        assert state["status"] == "running"

    def test_update_health_check_failed(self, temp_db):
        update_health_check("test_service", result="failed")

        state = get_service_state("test_service")
        assert state["last_health_check_result"] == "failed"
        assert state["status"] == "stopped"


class TestDbStats:
    """测试数据库统计"""

    def test_get_db_stats(self, temp_db):
        upsert_service_state("test_service", "running")
        log_event("test_service", "started")

        stats = get_db_stats()
        assert "service_states" in stats
        assert "events" in stats
        assert "resource_alerts" in stats
        assert stats["service_states"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
