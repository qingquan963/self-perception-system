#!/usr/bin/env python3
"""
process_utils.py - 跨平台进程管理工具
消除 Windows API 依赖，实现进程启动、端口检测、文件锁等功能。
"""
import os
import sys
import time
import signal
import socket
import subprocess
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger("process_utils")

# ─── 平台检测 ──────────────────────────────────────────────────────
IS_WINDOWS = sys.platform == "win32"
IS_UNIX = sys.platform in ("linux", "darwin")

# ─── 进程创建标志 ──────────────────────────────────────────────────
if IS_WINDOWS:
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_NO_WINDOW = 0x08000000
    PROCESS_QUERY_INFORMATION = 0x0400
    STILL_ACTIVE = 0x00000103

# ─── 端口检测 ──────────────────────────────────────────────────────

def is_port_available(port: int) -> bool:
    """检查端口是否可用（未被占用）"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
        sock.close()
        return True
    except OSError:
        return False


def is_port_listening(port: int) -> bool:
    """检查端口是否正在监听（服务已启动）"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(("127.0.0.1", port))
        sock.close()
        return True
    except (OSError, socket.timeout):
        return False


def find_process_by_port(port: int) -> Optional[int]:
    """查找占用指定端口的进程 PID"""
    try:
        import psutil
        for proc in psutil.process_iter(["pid"]):
            try:
                for conn in proc.net_connections():
                    if conn.laddr.port == port and conn.status == "LISTEN":
                        return proc.pid
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.NoSuchProperty):
                pass
    except ImportError:
        pass
    return None


# ─── PID 存活检测 ─────────────────────────────────────────────────

def is_pid_alive(pid: int) -> bool:
    """检查给定 PID 是否存活"""
    try:
        if IS_WINDOWS:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_INFORMATION = 0x0400
            handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
            if handle == 0:
                return False
            try:
                exit_code = ctypes.c_ulong()
                kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                return exit_code.value == STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        else:
            os.kill(pid, 0)
            return True
    except (OSError, AttributeError):
        return False


def kill_pid(pid: int, force: bool = False) -> bool:
    """终止进程"""
    try:
        if IS_WINDOWS:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_TERMINATE = 0x0001
            handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if handle == 0:
                return True  # 进程已不存在
            try:
                if force:
                    kernel32.TerminateProcess(handle, 1)
                else:
                    # 尝试优雅终止
                    kernel32.GenerateConsoleCtrlEvent(0, pid)
                    time.sleep(1)
                    # 检查是否已退出
                    exit_code = ctypes.c_ulong()
                    kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                    if exit_code.value != STILL_ACTIVE:
                        return True
                    # 强制终止
                    kernel32.TerminateProcess(handle, 1)
                return True
            finally:
                kernel32.CloseHandle(handle)
        else:
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
            return True
    except (OSError, AttributeError):
        return True  # 进程已不存在


# ─── 进程查找 ──────────────────────────────────────────────────────

def find_process_by_cmdline(keyword: str) -> Optional[int]:
    """通过 cmdline 查找目标进程 PID"""
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                cmdline = " ".join(proc.info["cmdline"] or [])
                if keyword in cmdline:
                    return proc.info["pid"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except ImportError:
        pass
    return None


def find_processes_by_name(name: str) -> List[int]:
    """查找所有匹配进程名的 PID 列表"""
    pids = []
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                proc_name = proc.info.get("name", "")
                cmdline = " ".join(proc.info.get("cmdline") or [])
                if name.lower() in proc_name.lower() or name in cmdline:
                    pids.append(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except ImportError:
        pass
    return pids


# ─── 进程启动（跨平台）────────────────────────────────────────────

def start_detached_process(
    cmd: List[str],
    cwd: Path,
    stdout_path: Optional[Path] = None,
    stderr_path: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    creationflags: int = 0
) -> subprocess.Popen:
    """
    跨平台启动分离子进程

    Args:
        cmd: 启动命令列表
        cwd: 工作目录
        stdout_path: stdout 日志文件路径
        stderr_path: stderr 日志文件路径
        env: 环境变量字典
        creationflags: Windows 进程创建标志

    Returns:
        subprocess.Popen 对象
    """
    # 准备文件句柄
    stdout_file = None
    stderr_file = None

    try:
        if stdout_path:
            stdout_file = open(stdout_path, "a", encoding="utf-8")
        else:
            stdout_file = subprocess.DEVNULL

        if stderr_path:
            stderr_file = open(stderr_path, "a", encoding="utf-8")
        else:
            stderr_file = subprocess.DEVNULL

        # 合并环境变量
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        # 构建进程启动参数
        start_kwargs = {
            "args": cmd,
            "cwd": str(cwd),
            "stdout": stdout_file,
            "stderr": stderr_file,
            "close_fds": True,
            "env": full_env,
        }

        if IS_WINDOWS:
            # Windows: 使用 CREATE_NO_WINDOW 隐藏控制台窗口
            flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
            if creationflags:
                flags |= creationflags
            start_kwargs["creationflags"] = flags
            # startupinfo 隐藏窗口
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            start_kwargs["startupinfo"] = startupinfo
        else:
            # Unix: 使用 double fork 守护进程化
            if os.fork() == 0:
                # 第一次 fork 后，子进程继续
                os.setsid()  # 创建新会话
                if os.fork() == 0:
                    # 第二次 fork 后，孙进程继续
                    pass
                else:
                    os._exit(0)
            else:
                # 父进程退出
                os._exit(0)

        proc = subprocess.Popen(**start_kwargs)
        logger.info(f"启动进程: {' '.join(cmd)} (PID {proc.pid})")
        return proc

    finally:
        # 不要在这里关闭文件句柄，让子进程继承
        pass


def start_process_simple(
    cmd: List[str],
    cwd: Path,
    log_file: Optional[Path] = None,
    err_file: Optional[Path] = None
) -> subprocess.Popen:
    """
    简化版进程启动（不分离进程，父进程等待）
    用于需要等待启动结果的场景
    """
    kwargs = {
        "args": cmd,
        "cwd": str(cwd),
        "close_fds": True,
    }

    if log_file:
        kwargs["stdout"] = open(log_file, "a", encoding="utf-8")
    else:
        kwargs["stdout"] = subprocess.PIPE

    if err_file:
        kwargs["stderr"] = open(err_file, "a", encoding="utf-8")
    else:
        kwargs["stderr"] = subprocess.PIPE

    if IS_WINDOWS:
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo

    return subprocess.Popen(**kwargs)


# ─── 文件锁（单实例）───────────────────────────────────────────────

class FileLock:
    """
    跨平台文件锁实现
    Windows: 使用 msvcrt.locking()
    Unix: 使用 fcntl.flock()
    """

    def __init__(self, lock_file: Path):
        self.lock_file = lock_file
        self.lock_fd = None

    def acquire(self) -> bool:
        """尝试获取排他锁，失败返回 False"""
        try:
            # 确保目录存在
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)

            # 打开或创建锁文件
            self.lock_fd = os.open(
                str(self.lock_file),
                os.O_CREAT | os.O_RDWR
            )

            if IS_WINDOWS:
                import msvcrt
                # Windows 文件锁（非阻塞）
                try:
                    msvcrt.locking(self.lock_fd, msvcrt.LK_NBLCK, 1)
                except IOError:
                    # 锁已被占用
                    os.close(self.lock_fd)
                    self.lock_fd = None
                    return False
            else:
                import fcntl
                # Unix 文件锁（非阻塞）
                try:
                    fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    os.close(self.lock_fd)
                    self.lock_fd = None
                    return False

            # 写入当前 PID
            os.ftruncate(self.lock_fd, 0)
            os.write(self.lock_fd, str(os.getpid()).encode())
            os.lseek(self.lock_fd, 0, os.SEEK_SET)

            logger.info(f"获取文件锁: {self.lock_file}")
            return True

        except Exception as e:
            logger.error(f"获取文件锁失败: {e}")
            if self.lock_fd is not None:
                try:
                    os.close(self.lock_fd)
                except:
                    pass
            self.lock_fd = None
            return False

    def release(self):
        """释放锁"""
        try:
            if self.lock_fd is not None:
                if IS_WINDOWS:
                    import msvcrt
                    try:
                        msvcrt.locking(self.lock_fd, msvcrt.LK_UNLCK, 1)
                    except:
                        pass
                os.close(self.lock_fd)
                self.lock_fd = None

            if self.lock_file.exists():
                self.lock_file.unlink()

            logger.info(f"释放文件锁: {self.lock_file}")
        except Exception as e:
            logger.error(f"释放文件锁失败: {e}")

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(f"无法获取文件锁: {self.lock_file}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


# ─── 资源监控 ──────────────────────────────────────────────────────

def get_process_resources(pid: int) -> Dict[str, float]:
    """
    获取进程资源使用情况
    Returns: {"memory_mb": float, "cpu_percent": float}
    """
    try:
        import psutil
        proc = psutil.Process(pid)
        mem_mb = proc.memory_info().rss / 1024 / 1024
        cpu = proc.cpu_percent(interval=0.5)
        return {"memory_mb": mem_mb, "cpu_percent": cpu}
    except (psutil.NoSuchProcess, psutil.AccessDenied, ImportError):
        return {"memory_mb": 0, "cpu_percent": 0}


# ─── 优雅停止进程 ─────────────────────────────────────────────────

def stop_process_graceful(pid: int, timeout: int = 10) -> bool:
    """
    优雅停止进程（先 SIGTERM/SIGINT，等待超时后 SIGKILL）
    """
    if not is_pid_alive(pid):
        return True

    try:
        if IS_WINDOWS:
            # Windows: 发送 CTRL_BREAK_EVENT 或 TerminateProcess
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_TERMINATE = 0x0001
            handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if handle == 0:
                return True

            try:
                # 尝试发送 Ctrl+Break (CTRL_BREAK_EVENT)
                kernel32.GenerateConsoleCtrlEvent(0, pid)
                time.sleep(1)

                # 检查是否已退出
                if not is_pid_alive(pid):
                    return True

                # 优雅终止失败，强制终止
                kernel32.TerminateProcess(handle, 1)
                return True
            finally:
                kernel32.CloseHandle(handle)
        else:
            # Unix: SIGTERM -> 等待 -> SIGKILL
            os.kill(pid, signal.SIGTERM)
            start_time = time.time()
            while time.time() - start_time < timeout:
                if not is_pid_alive(pid):
                    return True
                time.sleep(0.5)
            os.kill(pid, signal.SIGKILL)
            return True

    except (OSError, AttributeError):
        return True  # 进程已不存在


# ─── 进程终止（批量）──────────────────────────────────────────────

def kill_processes_by_name(name: str, force: bool = False) -> int:
    """停止所有匹配进程名的进程，返回停止的数量"""
    pids = find_processes_by_name(name)
    count = 0
    for pid in pids:
        if kill_pid(pid, force=force):
            count += 1
    return count


# ─── 工具函数 ──────────────────────────────────────────────────────

def wait_for_port(port: int, timeout: int = 30) -> bool:
    """等待端口开始监听（服务启动完成）"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_port_listening(port):
            return True
        time.sleep(0.5)
    return False


def get_pid_from_file(pid_file: Path) -> Optional[int]:
    """从 PID 文件读取 PID"""
    try:
        if pid_file.exists():
            return int(pid_file.read_text(encoding="utf-8").strip())
    except (ValueError, FileNotFoundError):
        pass
    return None


def write_pid_file(pid_file: Path, pid: int):
    """写入 PID 文件"""
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(pid), encoding="utf-8")


def clear_pid_file(pid_file: Path):
    """删除 PID 文件"""
    if pid_file.exists():
        pid_file.unlink()
