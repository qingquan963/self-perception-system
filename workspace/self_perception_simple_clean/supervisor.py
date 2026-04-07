#!/usr/bin/env python3
"""
supervisor.py - 统一守护进程（重构版）
支持外部配置、单实例锁、服务依赖管理、资源监控、状态持久化

架构：
  watchdog.py → supervisor.py → api_service / vector_service / frontend / ...
                      ↓
              SQLite state.db（状态持久化）

启动方式：
  python supervisor.py
  （由 watchdog.py 在开机时启动）
"""
import os
import sys
import time
import signal
import logging
import platform
from pathlib import Path
from typing import Optional, Dict, Any, List

# ─── 路径设置 ────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

# 导入内部模块
from process_utils import (
    FileLock, is_port_available, is_port_listening,
    is_pid_alive, find_process_by_cmdline, find_process_by_port,
    start_detached_process, stop_process_graceful,
    get_process_resources, wait_for_port,
    write_pid_file, clear_pid_file, get_pid_from_file,
    is_port_listening as check_port
)
from state_db import init_db, log_event, update_health_check, log_resource_alert, \
    get_restart_count, increment_restart_count, reset_restart_count, \
    get_service_state, upsert_service_state, get_all_service_states
from config_loader import init_config, get_config, resolve_startup_order, resolve_stop_order

# ─── 日志配置 ────────────────────────────────────────────────────
LOG_DIR = PROJECT_DIR / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "supervisor.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("supervisor")

# ─── 单实例锁 ────────────────────────────────────────────────────
LOCK_FILE = PROJECT_DIR / "data" / "supervisor.lock"


def acquire_instance_lock():
    """获取单实例锁，防止多实例运行"""
    lock = FileLock(LOCK_FILE)
    if not lock.acquire():
        logger.error("另一个 supervisor 实例正在运行，退出。")
        sys.exit(1)
    return lock


# ─── 主服务管理类 ────────────────────────────────────────────────

class ServiceManager:
    """统一服务管理器"""

    def __init__(self, config_path: Optional[Path] = None):
        # 初始化配置
        self.config_loader = init_config(config_path)

        # 初始化数据库
        db_path = PROJECT_DIR / "data" / "state.db"
        init_db(db_path)

        # 服务状态
        self.running = True
        self.failures: Dict[str, int] = {}
        self.service_pids: Dict[str, int] = {}

        # 配置热重载回调
        self.config_loader.on_reload(self._on_config_reload)

        # 注册信号处理
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, self._on_hup_signal)

        logger.info("=" * 60)
        logger.info("ServiceManager 初始化完成")
        logger.info(f"平台: {platform.system()} {platform.release()}")
        logger.info(f"Python: {platform.python_version()}")
        logger.info(f"项目目录: {PROJECT_DIR}")
        logger.info("=" * 60)

    def _on_signal(self, signum, frame):
        logger.info(f"收到信号 {signum}，准备优雅退出")
        self.running = False

    def _on_hup_signal(self, signum, frame):
        """SIGHUP 信号触发热重载"""
        logger.info("收到 SIGHUP，触发配置热重载")
        self.config_loader.reload()

    def _on_config_reload(self, new_config: Dict[str, Any]):
        """配置热重载回调"""
        logger.info("配置已热重载，新的服务列表:")
        for name in new_config.get("services", {}):
            logger.info(f"  - {name}")

    def _get_supervisor_config(self) -> Dict[str, Any]:
        """获取 supervisor 全局配置"""
        return self.config_loader.supervisor_config

    def _get_health_check_interval(self) -> int:
        """获取健康检查间隔"""
        return self._get_supervisor_config().get("health_check_interval", 20)

    def _get_restart_cooldown(self) -> int:
        """获取重启冷却时间"""
        return self._get_supervisor_config().get("restart_cooldown", 10)

    def _get_max_restart_attempts(self) -> int:
        """获取最大重启尝试次数"""
        return self._get_supervisor_config().get("max_restart_attempts", 5)

    def _get_restart_threshold(self, service: Dict[str, Any]) -> int:
        """获取服务连续失败阈值"""
        return service.get("restart_threshold", 2)

    # ─── 服务生命周期管理 ───────────────────────────────────────

    def start_service(self, service: Dict[str, Any]) -> bool:
        """启动单个服务"""
        name = service["name"]
        port = service.get("port")

        logger.info(f"[{name}] 启动中...")

        # 端口占用检测
        if port and not is_port_available(port):
            # 端口被占用，检查是否是该服务
            existing_pid = find_process_by_port(port)
            if existing_pid and is_pid_alive(existing_pid):
                logger.warning(f"[{name}] 端口 {port} 已被占用 (PID {existing_pid})，跳过启动")
                log_event(name, "started", f"端口被占用，跳过启动")
                self.service_pids[name] = existing_pid
                return True
            else:
                logger.warning(f"[{name}] 端口 {port} 异常，复用该端口")

        # 检查是否已在运行
        existing_pid = self._find_service_pid(service)
        if existing_pid and is_pid_alive(existing_pid):
            logger.info(f"[{name}] 已在运行 (PID {existing_pid})，跳过启动")
            self.service_pids[name] = existing_pid
            return True

        # 准备日志文件
        log_file_path = Path(service.get("log_file", str(LOG_DIR / f"{name}.log")))
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # 构建命令
            cwd = Path(service["cwd"])
            cmd = service["cmd"]

            # 启动进程
            proc = start_detached_process(
                cmd=cmd,
                cwd=cwd,
                stdout_path=log_file_path,
                stderr_path=log_file_path.with_suffix(".err.log"),
            )

            self.service_pids[name] = proc.pid

            # 写入 PID 文件
            pid_file = LOG_DIR / f"{name}.pid"
            write_pid_file(pid_file, proc.pid)

            # 等待服务启动
            if port:
                if wait_for_port(port, timeout=service.get("start_timeout", 30)):
                    logger.info(f"[{name}] 启动成功 (PID {proc.pid}, 端口 {port})")
                    log_event(name, "started", f"PID {proc.pid}")
                else:
                    logger.warning(f"[{name}] 启动后端口未就绪，将在后继健康检查中确认")

            # 更新数据库
            upsert_service_state(
                service_name=name,
                status="running",
                port=port,
                pid=proc.pid,
            )

            return True

        except Exception as e:
            logger.error(f"[{name}] 启动失败: {e}")
            log_event(name, "crashed", f"启动失败: {e}")
            return False

    def stop_service(self, service: Dict[str, Any]) -> bool:
        """停止单个服务"""
        name = service["name"]
        pid = self._find_service_pid(service)

        if pid is None or not is_pid_alive(pid):
            logger.info(f"[{name}] 未运行，无需停止")
            return True

        logger.info(f"[{name}] 停止中 (PID {pid})...")
        try:
            if stop_process_graceful(pid, timeout=10):
                logger.info(f"[{name}] 已停止")
                log_event(name, "stopped", f"PID {pid}")
            else:
                logger.warning(f"[{name}] 停止超时，强制终止")
                log_event(name, "stopped", f"强制终止 PID {pid}")
        except Exception as e:
            logger.error(f"[{name}] 停止失败: {e}")

        # 清理
        if name in self.service_pids:
            del self.service_pids[name]
        clear_pid_file(LOG_DIR / f"{name}.pid")

        upsert_service_state(
            service_name=name,
            status="stopped",
            pid=None,
        )

        return True

    def _find_service_pid(self, service: Dict[str, Any]) -> Optional[int]:
        """查找服务进程 PID"""
        name = service["name"]

        # 先尝试从 PID 文件读取
        pid_file = LOG_DIR / f"{name}.pid"
        pid = get_pid_from_file(pid_file)
        if pid and is_pid_alive(pid):
            return pid

        # 尝试从命令行查找
        cmd_keywords = {
            "api_service": "api_service:app",
            "vector_service": "vector_service:app",
            "frontend": "frontend_server.py",
            "compaction_writer": "compaction_writer.py",
            "dream_service": "dream_service.py",
        }

        keyword = cmd_keywords.get(name)
        if keyword:
            pid = find_process_by_cmdline(keyword)
            if pid:
                return pid

        return None

    # ─── 健康检查 ──────────────────────────────────────────────

    def _check_service_health(self, service: Dict[str, Any]) -> bool:
        """检查服务健康状态"""
        name = service["name"]
        health_url = service.get("health_url")

        if not health_url:
            # 无健康检查 URL，通过 PID 判断
            pid = self._find_service_pid(service)
            return pid is not None and is_pid_alive(pid)

        try:
            import urllib.request
            urllib.request.urlopen(health_url, timeout=5)
            return True
        except Exception:
            return False

    def _check_resources(self, service: Dict[str, Any]) -> bool:
        """
        检查服务资源使用，返回 True 表示超限需要重启
        """
        name = service["name"]
        pid = self._find_service_pid(service)

        if not pid:
            return False

        resources = get_process_resources(pid)
        mem_mb = resources["memory_mb"]
        cpu = resources["cpu_percent"]

        # 更新数据库
        update_health_check(name, "ok", mem_mb, cpu)

        # 检查内存限制
        max_mem = service.get("resources", {}).get("max_memory_mb")
        if max_mem and mem_mb > max_mem:
            logger.warning(f"[{name}] 内存超限: {mem_mb:.1f}MB > {max_mem}MB")
            log_resource_alert(name, "memory", mem_mb, max_mem)
            log_event(name, "crashed", f"内存超限 {mem_mb:.1f}MB > {max_mem}MB")
            return True

        # 检查 CPU 限制
        max_cpu = service.get("resources", {}).get("max_cpu_percent")
        if max_cpu and cpu > max_cpu:
            logger.warning(f"[{name}] CPU 超限: {cpu:.1f}% > {max_cpu}%")
            log_resource_alert(name, "cpu", cpu, max_cpu)
            # CPU 超限暂不自动重启，只记录告警

        return False

    def _should_restart(self, name: str) -> bool:
        """检查服务是否应该重启（防无限循环）"""
        max_attempts = self._get_max_restart_attempts()
        count = get_restart_count(name)
        if count >= max_attempts:
            logger.error(f"[{name}] 重启次数已达上限 ({count}/{max_attempts})，停止重启")
            log_event(name, "threshold_exceeded", f"重启次数 {count} >= {max_attempts}")
            return False
        return True

    def restart_service(self, service: Dict[str, Any]) -> bool:
        """重启服务"""
        name = service["name"]

        if not self._should_restart(name):
            upsert_service_state(name, status="failed")
            return False

        logger.info(f"[{name}] 执行重启...")
        log_event(name, "restarted", "开始重启")

        # 停止
        self.stop_service(service)
        time.sleep(self._get_restart_cooldown())

        # 启动
        success = self.start_service(service)
        if success:
            increment_restart_count(name)
        else:
            logger.error(f"[{name}] 重启失败")

        return success

    def check_and_restart(self, service: Dict[str, Any]) -> bool:
        """检查服务状态，必要时重启"""
        name = service["name"]
        threshold = self._get_restart_threshold(service)

        # 健康检查
        is_healthy = self._check_service_health(service)

        # 资源检查（如果健康）
        if is_healthy:
            self._check_resources(service)

        if is_healthy:
            if self.failures.get(name, 0) > 0:
                logger.info(f"[{name}] 已恢复正常")
                self.failures[name] = 0
            # 更新数据库状态
            upsert_service_state(name, status="running")
            return True

        # 服务不健康
        self.failures[name] = self.failures.get(name, 0) + 1
        logger.warning(f"[{name}] 不健康 (第 {self.failures[name]}/{threshold} 次)")

        if self.failures[name] >= threshold:
            logger.info(f"[{name}] 连续失败 {threshold} 次，执行重启...")
            self.failures[name] = 0
            return self.restart_service(service)

        return False

    # ─── 批量操作 ──────────────────────────────────────────────

    def start_all_services(self):
        """按依赖顺序启动所有服务"""
        config = self.config_loader.load()
        services = list(config.get("services", {}).values())

        # 拓扑排序
        sorted_services = resolve_startup_order(services)
        logger.info(f"服务启动顺序: {[s['name'] for s in sorted_services]}")

        for svc in sorted_services:
            self.start_service(svc)
            time.sleep(2)  # 等待服务启动

        # 记录启动事件
        for svc in sorted_services:
            log_event(svc["name"], "started", "Supervisor 启动")

    def stop_all_services(self):
        """按逆序停止所有服务"""
        config = self.config_loader.load()
        services = list(config.get("services", {}).values())

        # 逆序停止
        sorted_services = resolve_stop_order(services)
        logger.info(f"服务停止顺序: {[s['name'] for s in sorted_services]}")

        for svc in sorted_services:
            self.stop_service(svc)
            time.sleep(1)

    # ─── 状态显示 ──────────────────────────────────────────────

    def print_status(self):
        """打印所有服务状态"""
        try:
            os.system("cls" if os.name == "nt" else "clear")
        except:
            pass

        print("=" * 70)
        print(f"  自我感知系统 Supervisor  -  {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        config = self.config_loader.config
        services = config.get("services", {})

        all_states = get_all_service_states()
        state_map = {s["service_name"]: s for s in all_states}

        for name, svc in services.items():
            state = state_map.get(name, {})
            status = state.get("status", "unknown")
            pid = state.get("pid") or self._find_service_pid(svc)
            failures = self.failures.get(name, 0)
            mem = state.get("memory_mb", 0)
            cpu = state.get("cpu_percent", 0)

            if status == "running":
                mark = "[OK] "
            elif status == "failed":
                mark = "[FAIL]"
            else:
                mark = "[ERR] "

            pid_str = str(pid) if pid else "-"
            mem_str = f"{mem:.0f}MB" if mem else "-"
            cpu_str = f"{cpu:.0f}%" if cpu else "-"

            print(f"  {svc['name']:<22} {mark}  PID: {pid_str:<6}  "
                  f"Mem: {mem_str:<8} CPU: {cpu_str:<6}  失败: {failures}")

        print("-" * 70)

        # 显示数据库统计
        from state_db import get_db_stats
        stats = get_db_stats()
        print(f"  DB 记录: 服务状态 {stats.get('service_states', 0)} | "
              f"事件 {stats.get('events', 0)} | "
              f"告警 {stats.get('resource_alerts', 0)}")

        print("=" * 70)
        print("  按 Ctrl+C 优雅退出 | 发送 SIGHUP 热重载配置")
        print("=" * 70)

    # ─── 主循环 ────────────────────────────────────────────────

    def run(self):
        """主循环"""
        logger.info("=" * 60)
        logger.info("Supervisor 启动，开始守护所有子服务")
        logger.info("=" * 60)

        # 获取锁
        lock = acquire_instance_lock()

        try:
            # 启动所有服务
            self.start_all_services()

            # 主循环
            while self.running:
                config = self.config_loader.config
                services = list(config.get("services", {}).values())

                # 检查所有服务
                for svc in services:
                    if not self.running:
                        break
                    self.check_and_restart(svc)

                # 打印状态
                self.print_status()

                # 等待下一个周期
                interval = self._get_health_check_interval()
                for _ in range(interval):
                    if not self.running:
                        break
                    time.sleep(1)

        except KeyboardInterrupt:
            logger.info("用户中断")
        except Exception as e:
            logger.exception(f"Supervisor 异常: {e}")
        finally:
            logger.info("停止所有服务...")
            self.stop_all_services()
            lock.release()
            logger.info("Supervisor 已停止")


# ─── 入口 ────────────────────────────────────────────────────────
if __name__ == "__main__":
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 可选：指定配置文件路径
    config_path = None
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])
        if not config_path.exists():
            print(f"配置文件不存在: {config_path}")
            sys.exit(1)

    manager = ServiceManager(config_path)
    manager.run()
