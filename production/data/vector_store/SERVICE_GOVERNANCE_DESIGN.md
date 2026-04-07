# 服务治理跨平台重构设计文档

**版本**: 1.1  
**作者**: Architect  
**日期**: 2026-04-05  
**状态**: 草稿

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0 | 2026-04-05 | 初始版本 |
| 1.1 | 2026-04-05 | 修订：外部配置层、持久化机制、单实例锁、资源阈值、依赖管理、幂等性、Windows兼容性、实施路径（回滚+灰度+测试） |

---

## 1. 问题分析（根因）

### 1.1 当前架构

```
launch_services.py (Windows注册表触发)
    │
    ├─→ supervisor.py ──→ api_service (8011)
    │                   ├─→ vector_service (8007)
    │                   ├─→ frontend (8090)
    │                   ├─→ compaction_writer (8014)
    │                   └─→ dream_service (8001) [硬编码Windows路径]
    │
    └─→ watchdog.py ──→ supervisor.py (双重守护)
                          ↑
monitoring_service.py ────┘ (功能重叠，独立运行)
```

### 1.2 根因分析

| 问题 | 根因 | 影响 |
|------|------|------|
| `DETACHED_PROCESS` 不可跨平台 | Windows API 无 POSIX 等价物 | 无法在 Linux/macOS 运行 |
| `dream_service` 硬编码 `C:/Users/...` | 未使用相对路径或环境变量 | 路径永远指向 Windows |
| 开机自启依赖注册表 | `HKCU:\Software\Microsoft\Windows\CurrentVersion\Run` | Linux 用 systemd，macOS 用 launchd |
| watchdog/monitoring_service/supervisor 三层重叠 | 历史上逐步叠加，未统一设计 | 职责不清，冲突难排查 |
| watchdog 本身无守护 | watchdog.py 是叶子节点 | supervisor 挂了 watchdog 也挂 |

---

## 2. 目标架构

### 2.1 设计原则

1. **单层守护**：supervisor 唯一负责所有子服务监控，不再有 monitoring_service
2. **watchdog 独立守护 supervisor**：防止 supervisor 崩溃导致整体失效
3. **跨平台抽象层**：用 `multiprocessing` 或 `subprocess.DETACHED_PROCESS` 条件判断
4. **路径全部相对化**：通过 `PROJECT_DIR` 或环境变量计算，不硬编码
5. **配置外置**：服务列表在 YAML/JSON 中定义，支持热重载
6. **状态持久化**：SQLite 记录状态、事件、资源使用，支持审计回溯

### 2.2 目标架构图

```
┌─────────────────────────────────────────────────────────┐
│                    系统启动层 (跨平台)                    │
│  Windows: nssm.exe (服务)                               │
│  Linux:   systemd (service unit)                        │
│  macOS:   launchd (plist)                              │
└──────────────────────┬──────────────────────────────────┘
                       │ 触发
                       ▼
┌─────────────────────────────────────────────────────────┐
│              supervisor.py (统一守护进程)                 │
│  ├─ 读取 services.yaml 加载服务列表                       │
│  ├─ 启动所有子服务 (按 depends 顺序)                       │
│  ├─ 健康检查 (HTTP polling)                              │
│  ├─ 崩溃重启 (failcount >= threshold)                    │
│  ├─ 资源监控 (CPU/内存超限则重启/告警)                     │
│  ├─ 状态持久化 (SQLite)                                  │
│  └─ 单实例锁 (文件锁)                                    │
└──────────────────────┬──────────────────────────────────┘
                       │ 守护
                       ▼
┌─────────────────────────────────────────────────────────┐
│              watchdog.py (守护 supervisor)               │
│  ├─ 监控 supervisor 存活                                 │
│  └─ supervisor 挂了 → 重启 (带指数退避)                    │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 服务配置（外部化）

### 3.1 配置文件 `services.yaml`

所有服务定义在 `PROJECT_DIR/config/services.yaml`，supervisor.py 启动时读取，支持 SIGHUP 热重载。

```yaml
# services.yaml - 服务列表配置
version: "1.0"

services:
  api_service:
    port: 8011
    cmd: ["python", "-m", "uvicorn", "api_service:app", "--host", "127.0.0.1", "--port", "8011"]
    cwd: "{{PROJECT_DIR}}"
    health_url: "http://127.0.0.1:8011/health"
    health_interval: 20
    restart_threshold: 2       # 连续失败次数阈值
    depends: []               # 依赖的服务名（必须先启动）
    resources:
      max_memory_mb: 512
      max_cpu_percent: 80
    start_timeout: 30

  vector_service:
    port: 8007
    cmd: ["python", "-m", "uvicorn", "vector_service:app", "--host", "127.0.0.1", "--port", "8007"]
    cwd: "{{PROJECT_DIR}}"
    health_url: "http://127.0.0.1:8007/health"
    depends: []
    resources:
      max_memory_mb: 1024
      max_cpu_percent: 90

  frontend:
    port: 8090
    cmd: ["python", "-m", "http.server", "8090", "--bind", "127.0.0.1"]
    cwd: "{{PROJECT_DIR}}"
    health_url: "http://127.0.0.1:8090/dashboard.html"
    depends: []
    resources:
      max_memory_mb: 256
      max_cpu_percent: 50

  compaction_writer:
    port: 8014
    cmd: ["python", "compaction_writer.py"]
    cwd: "{{PROJECT_DIR}}"
    health_url: "http://127.0.0.1:8014/health"
    depends: ["api_service", "vector_service"]
    resources:
      max_memory_mb: 384
      max_cpu_percent: 70

  dream_service:
    port: 8001
    cmd: ["python", "dream_service.py"]
    cwd: "{{DREAM_SERVICE_DIR}}"
    health_url: "http://127.0.0.1:8001/memories/dream/status"
    depends: []
    resources:
      max_memory_mb: 512
      max_cpu_percent: 80

# 全局配置
supervisor:
  health_check_interval: 20      # 秒
  restart_cooldown: 10            # 重启冷却时间（秒）
  max_restart_attempts: 5        # 单服务每小时最大重启次数（防无限循环）
  instance_lock_file: "{{PROJECT_DIR}}/data/supervisor.lock"
  state_db: "{{PROJECT_DIR}}/data/state.db"
```

### 3.2 热重载机制

- supervisor 启动时注册 SIGHUP 信号处理（Unix）/ `signal.SIGINT`（Windows）
- 收到信号后：重新读取 `services.yaml` → 对比服务列表差异 → 仅变更部分生效（新增/停止/配置变更）
- 不中断正在运行的服务（除非其配置项实际变更）

### 3.3 路径变量替换

配置文件中 `{{PROJECT_DIR}}` 和 `{{DREAM_SERVICE_DIR}}` 在加载时替换为实际绝对路径。

---

## 4. 状态持久化

### 4.1 SQLite 数据库

状态存储在 `PROJECT_DIR/data/state.db`（SQLite，无外部依赖），表结构如下：

```sql
-- 服务状态快照（每次健康检查后更新）
CREATE TABLE service_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL,
    status TEXT NOT NULL,          -- 'running'|'stopped'|'restarting'|'failed'
    port integer,
    pid integer,
    last_health_check_at TEXT,    -- ISO8601
    last_health_check_result TEXT, -- 'ok'|'failed'
    restart_count_hourly INTEGER DEFAULT 0,
    memory_mb REAL,
    cpu_percent REAL,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 崩溃/重启事件（append-only，用于审计）
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL,
    event_type TEXT NOT NULL,      -- 'started'|'stopped'|'crashed'|'restarted'|'threshold_exceeded'
    detail TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 资源超限事件
CREATE TABLE resource_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL,
    resource_type TEXT NOT NULL,   -- 'memory'|'cpu'
    value REAL,
    threshold REAL,
    created_at TEXT DEFAULT (datetime('now'))
);
```

### 4.2 写入时机

| 数据 | 写入时机 | 目的 |
|------|----------|------|
| `service_states` | 每次健康检查完成（成功或失败） | 状态快照 |
| `events` | 服务启动/停止/崩溃时 | 审计追踪 |
| `resource_alerts` | CPU 或内存超限时 | 告警记录 |

**性能注意**：状态更新使用 upsert（INSERT OR REPLACE），避免频繁写入时的锁竞争；事件表仅 append，不频繁更新。

---

## 5. 服务依赖管理与启动顺序

### 5.1 依赖拓扑排序

supervisor 加载服务配置后，按 `depends` 构建有向图，用 Kahn 算法做拓扑排序，确定启动顺序：

```python
def resolve_startup_order(services):
    """返回按依赖顺序排好的服务列表"""
    graph = {s["name"]: s.get("depends", []) for s in services}
    visited, order = set(), []
    def dfs(name, path):
        if name in path: raise ValueError(f"Circular dependency: {' -> '.join(path + [name])}")
        if name in visited: return
        visited.add(name)
        for dep in graph[name]:
            dfs(dep, path + [name])
        order.append(name)
    for name in graph: dfs(name, [])
    return order
```

### 5.2 停止顺序

停止时按启动顺序的**逆序**执行，确保依赖者先于被依赖者关闭（例如 compaction_writer 依赖 api_service，停止时先停 compaction_writer 再停 api_service）。

### 5.3 启动时的依赖检查

服务启动前，检查其依赖的服务是否处于 running 状态。若依赖未就绪，该服务延迟启动（最多等待 `start_timeout` 秒，超时则记录失败事件并跳过）。

---

## 6. 单实例锁（并发安全）

### 6.1 文件锁实现

supervisor 启动时尝试获取排他锁，防止多实例同时运行：

```python
import os
import sys
import tempfile

LOCK_FILE = Path(config.get("instance_lock_file", "data/supervisor.lock"))

def acquire_lock():
    """尝试获取排他锁，失败则退出"""
    lock_fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR)
    try:
        # Windows: _wsopen + LOCKFILE_EXCLUSIVE_LOCK
        # Unix: flock via fcntl
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # 写入当前 PID
        os.ftruncate(lock_fd, 0)
        os.write(lock_fd, str(os.getpid()).encode())
        os lseek(lock_fd, 0, os.SEEK_SET)
        return lock_fd
    except (OSError, IOError):
        os.close(lock_fd)
        print(f"Another supervisor instance is running. Exiting.", file=sys.stderr)
        sys.exit(1)
```

**跨平台兼容**：Windows 用 `msvcrt.locking()`（文件锁），Unix 用 `fcntl.flock()`。锁文件存于 `PROJECT_DIR/data/`，确保同一机器唯一。

### 6.2 僵尸进程防护（幂等性）

- **停止服务时**：先发送 SIGTERM（Unix）/ `CTRL_BREAK_EVENT`（Windows），等待最多 10 秒退出；若仍未退出，SIGKILL（Unix）/ `TerminateProcess`（Windows）强制终止
- **启动前**：检查目标端口是否已被占用；若被占用，记录事件并跳过该服务（不重复启动）

---

## 7. 崩溃恢复与最大重试限制

### 7.1 watchdog 双层守护

```
系统服务管理器 (systemd/launchd/nssm)
    │
    ├─ watchdog.py 进程  [Restart=always, RestartSec=5]
    │       │
    │       └─→ supervisor.py 进程  [单实例锁保护]
    │               │
    │               └─→ 5 个子服务进程 (按拓扑顺序启动)
    │
    └─ OpenClaw 主进程
```

**watchdog 配置要点**：
- `systemd`: `Restart=always`, `RestartSec=5`
- `nssm`: `nssm set <service> AppRestart 1`
- `launchd`: `KeepAlive` 设置

### 7.2 最大重试退避策略

```python
# supervisor.py - 单服务最大重试
MAX_RESTART_PER_HOUR = config.get("max_restart_attempts", 5)
RESTART_COOLDOWN = config.get("restart_cooldown", 10)

def should_restart(service_name):
    """检查该服务本小时内已重启次数"""
    count = get_restart_count_from_db(service_name, last_hour=True)
    if count >= MAX_RESTART_PER_HOUR:
        log_event(service_name, "threshold_exceeded", f"Restart count {count} >= {MAX_RESTART_PER_HOUR}")
        return False
    return True

def restart_service(service):
    if not should_restart(service["name"]):
        mark_failed(service["name"])  # 停止重试，标记 failed
        return
    stop_service(service)
    time.sleep(RESTART_COOLDOWN)
    start_service(service)
    increment_restart_count(service["name"])
```

### 7.3 watchdog 对 supervisor 的守护

watchdog 每 10 秒检查 supervisor 存活（通过 PID 文件或进程存在检测），supervisor 退出码非 0 时重启，并记录事件。连续 3 次 supervisor 启动失败后，watchdog 暂停重启 5 分钟（防止忙轮询），避免系统资源耗尽。

---

## 8. 资源阈值与监控

### 8.1 阈值定义

每个服务在 `services.yaml` 中声明 `resources.max_memory_mb` 和 `max_cpu_percent`。

### 8.2 超限处理策略

```python
# supervisor.py - 资源监控循环（每次健康检查时执行）
import psutil

def check_resources(service, pid):
    try:
        proc = psutil.Process(pid)
        mem_mb = proc.memory_info().rss / 1024 / 1024
        cpu = proc.cpu_percent(interval=0.5)

        # 记录到状态表
        update_service_state(service["name"], memory_mb=mem_mb, cpu_percent=cpu)

        if mem_mb > service["resources"]["max_memory_mb"]:
            insert_resource_alert(service["name"], "memory", mem_mb, service["resources"]["max_memory_mb"])
            log_event(service["name"], "crashed", f"Memory {mem_mb:.1f}MB > limit {service['resources']['max_memory_mb']}MB, restarting")
            restart_service(service)

        if cpu > service["resources"]["max_cpu_percent"]:
            insert_resource_alert(service["name"], "cpu", cpu, service["resources"]["max_cpu_percent"])
            log_event(service["name"], "crashed", f"CPU {cpu:.1f}% > limit {service['resources']['max_cpu_percent']}%, restarting")
            # CPU 超限优先降级：降低优先级后继续运行，若持续超限才重启
            try:
                proc.nice(psutil.HIGH_PRIORITY_CLASS if sys.platform == "win32" else 10)
            except: pass
    except psutil.NoSuchProcess:
        # 进程已消失，按崩溃流程处理
        handle_unexpected_exit(service)
```

### 8.3 降级策略

| 触发条件 | 处理策略 |
|----------|----------|
| 内存超限 | 重启服务 |
| CPU 持续超限 3 次检查周期 | 重启服务 |
| 某服务连续崩溃超过阈值 | 标记 failed，停止重启，触发告警 |

---

## 9. 幂等性保障

### 9.1 端口占用检测

```python
def is_port_available(port):
    """检查端口是否已被占用"""
    import socket
    try:
        with socket.create_server(("127.0.0.1", port), reuse_addr=True):
            return True
    except OSError:
        return False

def start_service(service):
    if not is_port_available(service["port"]):
        log_event(service["name"], "crashed", f"Port {service['port']} already in use, skipping start")
        return
    # ... 正常启动
```

### 9.2 重复启动检测

每次 `start_service()` 前，先检查该服务是否已在运行（通过 PID 文件或进程查找），若 PID 有效且进程存活则跳过。

### 9.3 僵尸进程清理

watchdog 每次检查时，验证 supervisor PID 是否为有效进程（Unix: `kill -0 pid`，Windows: `OpenProcess(PROCESS_QUERY_INFORMATION)`）。无效则判定 supervisor 已崩溃，执行重启。

---

## 10. Windows 兼容性专项

### 10.1 服务账户

| 场景 | 推荐账户 | 说明 |
|------|----------|------|
| 开发/桌面环境 | 当前用户 (不受限) | 方便调试 |
| 生产环境 | `NT AUTHORITY\LocalService` | 最小权限原则 |
| 需要网络访问 | `NT AUTHORITY\NetworkService` | 网络服务账号 |

nssm 注册时通过 `nssm set <service> ObjectName <user> <password>` 指定账户。

### 10.2 路径长度限制

- Windows MAX_PATH = 260 字符限制通过以下方式规避：
  - 使用 `\\?\` 前缀启用长路径（Python 3.6+ `os.path.abspath()` 自动支持）
  - 配置路径控制在 200 字符以内
  - 日志路径使用短别名（如 `data/logs` 相对于 `PROJECT_DIR`）

### 10.3 环境变量大小写

- Windows 系统环境变量**不区分大小写**（`%PATH%` == `%path%`）
- 配置中统一使用**大写**命名环境变量（如 `DREAM_SERVICE_DIR`），与 Unix 风格对齐
- 代码读取时使用 `os.environ.get("DREAM_SERVICE_DIR")` 或 `os.environ.get("dream_service_dir")` 做兼容性兜底

---

## 11. 跨平台实现方案

### 11.1 消除 Windows API 依赖

```python
import sys, subprocess, shutil

def start_detached(cmd, cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
    """跨平台分离子进程"""
    if sys.platform == "win32":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
    else:
        creationflags = 0
        # Unix: 守护进程化 (double fork)
        if shutil.which("start-stop-daemon"):
            # Debian/Ubuntu: 使用 start-stop-daemon
            subprocess.run(["start-stop-daemon", "--start", "--background",
                           "--chdir", str(cwd), "--startas", "--"] + cmd)
            return
    subprocess.Popen(cmd, cwd=str(cwd), stdout=stdout, stderr=stderr,
                     close_fds=True, creationflags=creationflags)
```

### 11.2 消除硬编码路径

```python
from pathlib import Path
import os

PROJECT_DIR = Path(__file__).parent
DREAM_SERVICE_DIR = Path(os.environ.get(
    "DREAM_SERVICE_DIR",
    Path.home() / ".openclaw" / "production" / "data" / "vector_store"
))
```

### 11.3 开机自启跨平台

| 平台 | 方案 | 配置方式 |
|------|------|----------|
| Windows | **nssm.exe** | 注册系统服务，脱离用户登录依赖 |
| Linux | **systemd user** | `~/.config/systemd/user/supervisor.service` |
| macOS | **launchd** | `~/Library/LaunchAgents/com.self-perception.supervisor.plist` |

---

## 12. 迁移步骤

### 阶段 1：重构代码（不改行为）

1. 创建 `config/services.yaml`，将 supervisor.py 中的服务列表迁出
2. 创建 `process_utils.py` - 跨平台进程启动封装 + 端口检测
3. 修改 `supervisor.py`：
   - 引入 `services.yaml` 配置读取
   - 实现 SQLite 持久化
   - 实现单实例锁
   - 实现资源监控
   - 实现依赖拓扑排序
   - 实现最大重试退避
4. 修改 `watchdog.py`：引入 `process_utils.py`
5. 修改 `launch_services.py`：引入 `process_utils.py`
6. 删除 `monitoring_service.py`

### 阶段 2：跨平台自启

1. **Windows**: nssm 注册 supervisor 服务，watchdog 注册为二级服务
2. **Linux**: systemd unit（`Restart=always`）
3. **macOS**: launchd plist（`KeepAlive`）

### 阶段 3：验证与灰度

---

## 13. 灰度发布与回滚方案

### 13.1 灰度策略

| 阶段 | 范围 | 验证内容 | 通过标准 |
|------|------|----------|----------|
| **Canary 1** | 本机开发环境 | 启动 5 个子服务 | 所有服务 health check 通过 |
| **Canary 2** | 内网测试机（手动触发） | 正常启停、崩溃重启、资源超限 | supervisor 重启 <60s，watchdog 重启 <30s |
| **Canary 3** | 生产机器（保留旧版备份） | 开机自启、运行 24h | 无崩溃、无僵尸进程 |
| **Full** | 全部机器 | 切到新架构 | 监控指标正常 |

### 13.2 回滚计划

每个阶段失败时，回滚到上一阶段：

- **备份内容**：
  - 旧版 `supervisor.py`、`watchdog.py`、`launch_services.py` 打包为 `supervisor_backup_v1.0.zip`
  - 旧版 `services.yaml`（如存在）
  - 旧版 `state.db`（最后一次正常状态的快照）
- **回滚操作**：
  1. 停止 supervisor/watchdog
  2. 解压恢复备份文件
  3. 重启服务
- **回滚触发条件**：Canary 阶段连续 3 次崩溃，或出现数据丢失

### 13.3 数据库迁移

state.db 首次创建（如从零开始）。如需从旧架构迁移，另建 `state_migration.py` 脚本，一次性导入历史日志文件到 SQLite。

---

## 14. 测试方案

### 14.1 单元测试

| 测试项 | 工具 | 通过标准 |
|--------|------|----------|
| 拓扑排序（依赖图） | pytest | 线性依赖、并行依赖、循环依赖检测 |
| 端口可用性检测 | pytest + unittest.mock | 端口占用/空闲返回正确 |
| 单实例锁（获取/释放） | pytest（跨进程） | 同文件二次获取失败 |
| 资源阈值判断 | pytest | 超限/未超限正确触发 |
| 状态持久化（upsert/query） | pytest + tempfile | 数据一致 |

### 14.2 集成测试

| 测试项 | 操作 | 预期结果 |
|--------|------|----------|
| 正常启动 | 启动 supervisor | 5 个子服务全部 running |
| 单服务崩溃 | kill 某子服务 | supervisor ≤60s 重启该服务 |
| supervisor 崩溃 | kill supervisor | watchdog ≤30s 重启 supervisor |
| watchdog 崩溃 | kill watchdog | 系统服务管理器 ≤60s 重启 watchdog |
| 端口冲突启动 | 占用某服务端口后启动 | 服务跳过，事件写入 DB |
| 资源超限 | mock 超限进程 | 服务重启，alert 写入 DB |
| 循环依赖检测 | 配置 circular depends | 启动失败，报错明确 |

### 14.3 跨平台测试矩阵

| 平台 | Python 版本 | 测试内容 |
|------|-------------|----------|
| Windows 10/11 | 3.10+ | 完整集成测试（nssm 注册/卸载） |
| Linux (Ubuntu 22.04) | 3.10+ | systemd install/uninstall, service 状态 |
| macOS 13+ | 3.10+ | launchd load/unload, plist 验证 |

### 14.4 混沌测试

- 随机 kill 进程（子服务/supervisor/watchdog）
- 模拟端口被占用
- 模拟资源超限
- 验证自动恢复和事件记录完整性

---

## 15. 验收标准

### 15.1 功能验收

- [ ] 5 个子服务开机自启（按依赖顺序）
- [ ] `services.yaml` 修改后 SIGHUP 热重载生效
- [ ] 任意子服务崩溃后，supervisor 在 ≤60s 内重启
- [ ] supervisor 崩溃后，watchdog 在 ≤30s 内重启
- [ ] watchdog 崩溃后，系统服务管理器在 ≤60s 内重启
- [ ] 单机多实例启动被阻止
- [ ] `state.db` 中 `events` 表记录完整（启动/崩溃/重启/阈值）
- [ ] 资源超限触发重启并写入 `resource_alerts` 表

### 15.2 跨平台验收

- [ ] Linux: `systemctl --user enable supervisor` 生效
- [ ] macOS: `launchctl load` plist 生效
- [ ] Windows: nssm 服务可在"服务"管理器中看到
- [ ] 代码无 `0x00000008`、`DETACHED_PROCESS`、`C:/Users/Administrator` 字符串
- [ ] `services.yaml` 支持 `{{PROJECT_DIR}}` 变量替换

### 15.3 代码质量验收

- [ ] 删除 `monitoring_service.py`
- [ ] 所有路径使用 `Path()` 或环境变量
- [ ] watchdog 只守护 supervisor，不直接管理子服务
- [ ] 单元测试覆盖率 ≥80%（核心逻辑）

---

## 16. 附录

### 16.1 服务健康检查端点

| 服务 | URL | 预期响应 |
|------|-----|---------|
| api_service | `GET /health` | `200 OK` |
| vector_service | `GET /health` | `200 OK` |
| frontend | `GET /dashboard.html` | `200 OK` |
| compaction_writer | `GET /health` | `200 OK` |
| dream_service | `GET /memories/dream/status` | `200 OK` |

### 16.2 日志文件位置

```
PROJECT_DIR/
├── config/
│   └── services.yaml       # 服务配置（可热重载）
└── data/
    ├── state.db            # SQLite 状态数据库
    ├── supervisor.lock     # 单实例锁文件
    └── logs/
        ├── supervisor.log
        ├── watchdog.log
        ├── api_service.log
        ├── vector_service.log
        ├── frontend.log
        ├── compaction_writer.log
        └── dream_service.log
```

### 16.3 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `DREAM_SERVICE_DIR` | `~/.openclaw/production/data/vector_store` | dream_service 工作目录 |
| `PROJECT_DIR` | `supervisor.py 所在目录` | 项目根目录 |
| `SUPERVISOR_LOG_DIR` | `PROJECT_DIR/data/logs` | 日志目录 |
| `HEALTH_CHECK_INTERVAL` | `20`（秒） | 健康检查间隔 |
| `FAILURES_BEFORE_RESTART` | `2` | 连续失败次数阈值 |
| `MAX_RESTART_PER_HOUR` | `5` | 单服务每小时最大重启次数 |
