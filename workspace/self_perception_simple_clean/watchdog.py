#!/usr/bin/env python3
"""
watchdog.py - 看门狗守护进程（重构版）
守护 supervisor.py 本身，实现双重保障

架构：
  系统服务管理器 (systemd/nssm/launchd)
      │
      └─→ watchdog.py ──→ supervisor.py ──→ 子服务

watchdog 负责：
  1. 监控 supervisor 存活
  2. supervisor 崩溃后重启（带指数退避）
  3. 连续失败后的暂停机制（防忙轮询）

跨平台：Windows / Linux / macOS
"""
import os
import sys
import time
import signal
import logging
import platform
from pathlib import Path
from typing import Optional

# ─── 路径设置 ────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

from process_utils import (
    is_pid_alive, find_process_by_cmdline,
    start_detached_process, stop_process_graceful,
    FileLock, write_pid_file, clear_pid_file, get_pid_from_file
)

# ─── 配置 ────────────────────────────────────────────────────────
PYTHON = sys.executable
LOG_DIR = PROJECT_DIR / "data" / "logs"
LOG_FILE = LOG_DIR / "watchdog.log"
PID_FILE = LOG_DIR / "watchdog.pid"
SUPERVISOR_PID_FILE = LOG_DIR / "supervisor.pid"

# supervisor 启动命令
SUPERVISOR_CMD = [PYTHON, "supervisor.py"]

# 健康检查：api_service 在线 = supervisor 在正常工作
HEALTH_URL = "http://127.0.0.1:8011/health"
CHECK_INTERVAL = 10      # 每 10 秒检查一次
RESTART_DELAY = 5         # 重启后等待秒数
MAX_CONSECUTIVE_FAILURES = 3  # 连续失败次数阈值
PAUSE_AFTER_MAX_FAILURES = 300  # 达到最大失败后暂停 5 分钟

# 日志
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("watchdog")


# ─── 单实例锁 ────────────────────────────────────────────────────
LOCK_FILE = PROJECT_DIR / "data" / "watchdog.lock"


def acquire_instance_lock():
    """获取单实例锁"""
    lock = FileLock(LOCK_FILE)
    if not lock.acquire():
        logger.error("另一个 watchdog 实例正在运行，退出。")
        sys.exit(1)
    return lock


# ─── 辅助函数 ────────────────────────────────────────────────────

def write_own_pid():
    """写入自身 PID"""
    write_pid_file(PID_FILE, os.getpid())


def is_supervisor_alive() -> bool:
    """检查 supervisor 是否存活"""
    # 方法 1：检查 supervisor PID 文件
    pid = get_pid_from_file(SUPERVISOR_PID_FILE)
    if pid and is_pid_alive(pid):
        return True

    # 方法 2：通过 api_service 健康端点判断
    try:
        import urllib.request
        urllib.request.urlopen(HEALTH_URL, timeout=5)
        return True
    except Exception:
        pass

    # 方法 3：通过命令行查找
    pid = find_process_by_cmdline("supervisor.py")
    if pid and is_pid_alive(pid):
        return True

    return False


def stop_supervisor():
    """停止 supervisor 进程"""
    # 先尝试优雅停止
    pid = get_pid_from_file(SUPERVISOR_PID_FILE)
    if pid:
        logger.info(f"停止旧 supervisor (PID {pid})...")
        stop_process_graceful(pid, timeout=10)

    # 确保清理
    clear_pid_file(SUPERVISOR_PID_FILE)

    # 额外检查：通过命令行查找并停止
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                cmdline = " ".join(proc.info["cmdline"] or [])
                if "supervisor.py" in cmdline and "python" in cmdline.lower():
                    logger.info(f"停止残留 supervisor (PID {proc.pid})")
                    proc.terminate()
                    proc.wait(timeout=5)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except ImportError:
        pass


def start_supervisor():
    """启动 supervisor"""
    logger.info(f"启动 supervisor: {' '.join(SUPERVISOR_CMD)}")

    log_out = LOG_DIR / "supervisor_stdout.log"
    log_err = LOG_DIR / "supervisor_stderr.log"

    try:
        proc = start_detached_process(
            cmd=SUPERVISOR_CMD,
            cwd=PROJECT_DIR,
            stdout_path=log_out,
            stderr_path=log_err,
        )
        logger.info(f"supervisor 已启动 (PID {proc.pid})")
        return proc.pid
    except Exception as e:
        logger.error(f"启动 supervisor 失败: {e}")
        return None


def wait_and_check(sec: int) -> bool:
    """等待 N 秒后检查 supervisor 是否活过来了"""
    logger.info(f"等待 {sec} 秒后检查...")
    for _ in range(sec):
        if is_supervisor_alive():
            return True
        time.sleep(1)
    return False


# ─── 主循环 ──────────────────────────────────────────────────────

class Watchdog:
    """看门狗主类"""

    def __init__(self):
        self.running = True
        self.consecutive_failures = 0
        self.pause_until = 0  # 暂停截止时间戳
        self.restart_count = 0  # 本次运行重启次数

        # 信号处理
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)

        logger.info("=" * 60)
        logger.info("Watchdog 初始化")
        logger.info(f"平台: {platform.system()} {platform.release()}")
        logger.info(f"Python: {platform.python_version()}")
        logger.info(f"项目目录: {PROJECT_DIR}")
        logger.info(f"检查间隔: {CHECK_INTERVAL} 秒")
        logger.info(f"最大连续失败: {MAX_CONSECUTIVE_FAILURES}")
        logger.info(f"暂停时长: {PAUSE_AFTER_MAX_FAILURES} 秒")
        logger.info("=" * 60)

    def _on_signal(self, signum, frame):
        logger.info(f"收到信号 {signum}，退出")
        self.running = False

    def check_and_restart_supervisor(self) -> bool:
        """检查并必要时重启 supervisor"""
        current_time = time.time()

        # 检查是否处于暂停期
        if current_time < self.pause_until:
            remaining = int(self.pause_until - current_time)
            if self.restart_count > 0:
                logger.info(f"暂停中，剩余 {remaining} 秒 ({self.restart_count} 次重启后触发)")
            time.sleep(min(CHECK_INTERVAL, remaining))
            return False

        # 检查 supervisor 状态
        if is_supervisor_alive():
            if self.consecutive_failures > 0:
                logger.info("supervisor 已恢复正常")
                self.consecutive_failures = 0
            return True

        # supervisor 不健康
        self.consecutive_failures += 1
        logger.warning(f"supervisor 不健康 (连续第 {self.consecutive_failures} 次)")

        # 连续失败达到阈值，执行重启
        if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.warning("连续失败达到阈值，执行重启...")
            self._restart_supervisor()
            self.consecutive_failures = 0

        return False

    def _restart_supervisor(self):
        """重启 supervisor"""
        self.restart_count += 1
        logger.info(f"第 {self.restart_count} 次重启 supervisor")

        # 停止旧 supervisor
        stop_supervisor()
        time.sleep(2)

        # 启动新 supervisor
        pid = start_supervisor()
        if pid is None:
            logger.error("supervisor 启动失败")
            self.pause_until = time.time() + PAUSE_AFTER_MAX_FAILURES
            logger.info(f"暂停 {PAUSE_AFTER_MAX_FAILURES} 秒后重试")
            return

        # 等待 supervisor 就绪
        if wait_and_check(RESTART_DELAY):
            logger.info("supervisor 重启成功")
            self.restart_count = 0
        else:
            logger.error("supervisor 重启后未响应")
            # 指数退避
            pause_time = min(PAUSE_AFTER_MAX_FAILURES * (2 ** (self.restart_count - 1)), 3600)
            self.pause_until = time.time() + pause_time
            logger.info(f"指数退避，暂停 {pause_time} 秒")

    def run(self):
        """主循环"""
        logger.info("=" * 60)
        logger.info("Watchdog 启动，开始守护 supervisor")
        logger.info("=" * 60)

        # 获取锁
        lock = acquire_instance_lock()

        try:
            # 写入自身 PID
            write_own_pid()

            # 启动 supervisor（如未运行）
            if not is_supervisor_alive():
                logger.info("supervisor 未运行，先启动...")
                self._restart_supervisor()

            # 主循环
            while self.running:
                self.check_and_restart_supervisor()

                # 每轮检查后等待
                for _ in range(CHECK_INTERVAL):
                    if not self.running:
                        break
                    time.sleep(1)

        except KeyboardInterrupt:
            logger.info("用户中断")
        except Exception as e:
            logger.exception(f"Watchdog 异常: {e}")
        finally:
            logger.info("Watchdog 停止")
            lock.release()


# ─── 入口 ────────────────────────────────────────────────────────

if __name__ == "__main__":
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    watchdog = Watchdog()
    watchdog.run()
