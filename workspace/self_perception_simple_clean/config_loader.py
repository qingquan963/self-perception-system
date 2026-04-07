#!/usr/bin/env python3
"""
config_loader.py - 服务配置加载器
支持 YAML 配置解析、变量替换、热重载
"""
import os
import re
import yaml
import logging
import signal
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

logger = logging.getLogger("config_loader")

# ─── 路径变量 ────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).parent
DREAM_SERVICE_DIR = Path(os.environ.get(
    "DREAM_SERVICE_DIR",
    Path(__file__).parent  # 默认：在项目根目录（整合版）
))

# ─── 变量替换 ────────────────────────────────────────────────────

def substitute_vars(text: str, vars_dict: Optional[Dict[str, Path]] = None) -> str:
    """替换配置中的 {{VAR}} 变量"""
    if vars_dict is None:
        vars_dict = {
            "PROJECT_DIR": PROJECT_DIR,
            "DREAM_SERVICE_DIR": DREAM_SERVICE_DIR,
        }

    def replace_var(match):
        var_name = match.group(1)
        if var_name in vars_dict:
            return str(vars_dict[var_name])
        logger.warning(f"配置变量未定义: {{{var_name}}}")
        return match.group(0)

    return re.sub(r'\{\{(\w+)\}\}', replace_var, text)


def substitute_dict(obj: Any, vars_dict: Optional[Dict[str, Path]] = None) -> Any:
    """递归替换字典中的所有字符串变量"""
    if vars_dict is None:
        vars_dict = {
            "PROJECT_DIR": PROJECT_DIR,
            "DREAM_SERVICE_DIR": DREAM_SERVICE_DIR,
        }

    if isinstance(obj, str):
        return substitute_vars(obj, vars_dict)
    elif isinstance(obj, dict):
        return {k: substitute_dict(v, vars_dict) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [substitute_dict(item, vars_dict) for item in obj]
    else:
        return obj


# ─── 配置加载器 ──────────────────────────────────────────────────

class ConfigLoader:
    """
    服务配置加载器，支持：
    1. YAML 文件解析
    2. {{PROJECT_DIR}} / {{DREAM_SERVICE_DIR}} 变量替换
    3. SIGHUP 热重载（Unix）/ 信号热重载（Windows）
    """

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._config: Optional[Dict[str, Any]] = None
        self._last_mtime: Optional[float] = None
        self._reload_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._loaded_at: Optional[datetime] = None

        # 注册信号处理器（热重载）
        self._register_signal_handler()

    def _register_signal_handler(self):
        """注册热重载信号处理器"""
        def on_reload(signum, frame):
            logger.info(f"收到热重载信号 {signum}")
            self.reload()

        try:
            signal.signal(signal.SIGINT, on_reload)
            signal.signal(signal.SIGTERM, on_reload)
            # Unix 专用信号
            if hasattr(signal, 'SIGHUP'):
                signal.signal(signal.SIGHUP, on_reload)
        except (AttributeError, OSError):
            pass  # Windows 不支持 SIGHUP

    def load(self, force: bool = False) -> Dict[str, Any]:
        """加载配置（带缓存）"""
        if self._config is not None and not force:
            return self._config

        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        # 检查文件是否变更
        mtime = self.config_path.stat().st_mtime
        if not force and self._last_mtime == mtime:
            return self._config

        logger.info(f"加载配置文件: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)

        # 变量替换
        self._config = substitute_dict(raw_config)
        self._last_mtime = mtime
        self._loaded_at = datetime.now()

        logger.info(f"配置加载完成，共 {len(self._config.get('services', {}))} 个服务")
        return self._config

    def reload(self):
        """重新加载配置并触发回调"""
        logger.info("热重载配置...")
        old_config = self._config
        try:
            self.load(force=True)
            for callback in self._reload_callbacks:
                callback(self._config)
            logger.info("热重载完成")
        except Exception as e:
            logger.error(f"热重载失败: {e}，使用旧配置")
            self._config = old_config

    def on_reload(self, callback: Callable[[Dict[str, Any]], None]):
        """注册配置变更回调"""
        self._reload_callbacks.append(callback)

    @property
    def config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self.load()

    @property
    def services(self) -> Dict[str, Dict[str, Any]]:
        """获取服务配置字典"""
        return self.config.get("services", {})

    @property
    def supervisor_config(self) -> Dict[str, Any]:
        """获取 supervisor 全局配置"""
        return self.config.get("supervisor", {})

    def get_service(self, name: str) -> Optional[Dict[str, Any]]:
        """获取单个服务配置"""
        return self.services.get(name)

    def get_all_services(self) -> List[Dict[str, Any]]:
        """获取所有服务配置列表"""
        return list(self.services.values())


# ─── 拓扑排序 ────────────────────────────────────────────────────

def resolve_startup_order(services: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    根据依赖关系进行拓扑排序，确定服务启动顺序

    使用 Kahn 算法实现
    """
    # 构建依赖图
    graph: Dict[str, List[str]] = {}
    service_map: Dict[str, Dict[str, Any]] = {}

    for svc in services:
        name = svc["name"]
        service_map[name] = svc
        graph[name] = svc.get("depends", [])

    # 检查循环依赖
    visited: set = set()
    path: list = []

    def dfs(name: str):
        if name in path:
            cycle = " -> ".join(path + [name])
            raise ValueError(f"循环依赖检测到: {cycle}")
        if name in visited:
            return
        visited.add(name)
        path.append(name)
        for dep in graph.get(name, []):
            dfs(dep)
        path.pop()

    for name in graph:
        dfs(name)

    # Kahn 算法拓扑排序
    in_degree = {name: 0 for name in graph}
    for name, deps in graph.items():
        for dep in deps:
            if dep in in_degree:
                in_degree[name] += 1

    queue = [name for name, degree in in_degree.items() if degree == 0]
    result = []

    while queue:
        # 按字母顺序保证确定性
        queue.sort()
        name = queue.pop(0)
        result.append(service_map[name])

        for other_name, deps in graph.items():
            if name in deps:
                in_degree[other_name] -= 1
                if in_degree[other_name] == 0:
                    queue.append(other_name)

    if len(result) != len(services):
        missing = set(services) - set(result)
        raise ValueError(f"拓扑排序不完整，缺失服务: {missing}")

    return result


def resolve_stop_order(services: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    确定服务停止顺序（启动顺序的逆序，依赖者先停）
    """
    startup_order = resolve_startup_order(services)
    return list(reversed(startup_order))


# ─── 便捷函数 ────────────────────────────────────────────────────

_config_loader: Optional[ConfigLoader] = None


def init_config(config_path: Optional[Path] = None) -> ConfigLoader:
    """初始化配置加载器（单例模式）"""
    global _config_loader
    if config_path is None:
        config_path = PROJECT_DIR / "config" / "services.yaml"
    _config_loader = ConfigLoader(config_path)
    return _config_loader


def get_config() -> ConfigLoader:
    """获取配置加载器"""
    if _config_loader is None:
        return init_config()
    return _config_loader
