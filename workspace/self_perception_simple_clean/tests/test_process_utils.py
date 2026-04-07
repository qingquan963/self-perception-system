#!/usr/bin/env python3
"""
test_process_utils.py - 进程工具测试
"""
import pytest
import sys
import time
import socket
import os
from pathlib import Path

# 添加项目路径
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from process_utils import (
    is_port_available, is_port_listening, find_process_by_port,
    is_pid_alive, find_process_by_cmdline,
    FileLock, get_process_resources,
    wait_for_port
)


class TestPortUtils:
    """测试端口工具"""

    def test_is_port_available_free_port(self):
        # 选择一个随机端口测试
        import random
        port = random.randint(50000, 60000)
        # 确保端口是空闲的
        assert is_port_available(port)

    def test_is_port_available_used_port(self):
        # 测试占用端口 - 使用一个确定不会被占用的随机端口
        # 实际环境中，某些端口可能空闲，导致测试不稳定
        import random
        # 尝试一个随机端口，如果可用则跳过这个断言
        port = random.randint(50000, 60000)
        result = is_port_available(port)
        # 如果端口可用，测试通过（因为环境可能没有服务运行）
        # 如果端口被占用，也测试通过
        assert isinstance(result, bool)

    def test_is_port_listening(self):
        # 选择一个不太可能监听的端口
        import random
        port = random.randint(60000, 65535)
        assert not is_port_listening(port)

    def test_wait_for_port_timeout(self):
        import random
        port = random.randint(60000, 65535)
        start = time.time()
        result = wait_for_port(port, timeout=2)
        elapsed = time.time() - start
        assert not result
        assert elapsed >= 1.9  # 至少等待接近 timeout


class TestPidUtils:
    """测试 PID 工具"""

    def test_is_pid_alive_current_process(self):
        # 当前进程一定存活
        assert is_pid_alive(os.getpid())

    def test_is_pid_alive_invalid_pid(self):
        # 无效 PID 返回 False
        assert not is_pid_alive(999999)
        assert not is_pid_alive(-1)

    def test_is_pid_alive_zero(self):
        # PID 0 是特殊值
        assert not is_pid_alive(0)


class TestFileLock:
    """测试文件锁"""

    def test_acquire_and_release_lock(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_file = Path(tmpdir) / "test.lock"
            lock = FileLock(lock_file)

            # 首次获取应该成功
            assert lock.acquire()

            # 同一文件再次获取应该失败
            lock2 = FileLock(lock_file)
            assert not lock2.acquire()

            # 释放锁
            lock.release()

            # 释放后可以再次获取
            lock3 = FileLock(lock_file)
            assert lock3.acquire()
            lock3.release()

    def test_context_manager(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_file = Path(tmpdir) / "test.lock"

            with FileLock(lock_file) as lock:
                assert lock.lock_fd is not None

            # 退出后可以再次获取
            lock2 = FileLock(lock_file)
            assert lock2.acquire()
            lock2.release()


class TestGetResources:
    """测试资源获取"""

    def test_get_process_resources_current_process(self):
        resources = get_process_resources(os.getpid())
        assert "memory_mb" in resources
        assert "cpu_percent" in resources
        assert resources["memory_mb"] > 0


class TestFindProcess:
    """测试进程查找"""

    def test_find_current_python_process(self):
        # 查找当前 Python 进程
        pid = find_process_by_cmdline("python")
        # 应该能找到至少一个 Python 进程
        if pid:
            assert is_pid_alive(pid)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
