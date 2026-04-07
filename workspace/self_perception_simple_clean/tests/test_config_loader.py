#!/usr/bin/env python3
"""
test_config_loader.py - 配置加载器测试
"""
import pytest
import tempfile
import os
from pathlib import Path

# 添加项目路径
import sys
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from config_loader import (
    substitute_vars, substitute_dict,
    resolve_startup_order, resolve_stop_order,
    ConfigLoader
)


class TestSubstituteVars:
    """测试变量替换"""

    def test_substitute_project_dir(self):
        result = substitute_vars("{{PROJECT_DIR}}")
        assert str(PROJECT_DIR) in result

    def test_substitute_dream_service_dir(self):
        result = substitute_vars("{{DREAM_SERVICE_DIR}}")
        assert ".openclaw" in result

    def test_substitute_multiple(self):
        result = substitute_vars("{{PROJECT_DIR}}/data/{{PROJECT_DIR}}")
        # 两次替换应该得到相同路径拼接
        assert "data" in result

    def test_substitute_unknown_var(self):
        # 未知变量应保持原样
        result = substitute_vars("{{UNKNOWN_VAR}}")
        assert result == "{{UNKNOWN_VAR}}"


class TestSubstituteDict:
    """测试字典递归替换"""

    def test_substitute_simple_dict(self):
        input_dict = {
            "cwd": "{{PROJECT_DIR}}",
            "cmd": ["python", "test.py"]
        }
        result = substitute_dict(input_dict)
        assert "{{PROJECT_DIR}}" not in result["cwd"]
        assert "{{PROJECT_DIR}}" not in str(result)

    def test_substitute_nested_dict(self):
        input_dict = {
            "outer": {
                "inner": "{{PROJECT_DIR}}/test"
            }
        }
        result = substitute_dict(input_dict)
        assert "{{PROJECT_DIR}}" not in str(result)

    def test_substitute_list(self):
        input_dict = {
            "cmd": ["{{PROJECT_DIR}}/python", "test.py"]
        }
        result = substitute_dict(input_dict)
        assert "{{PROJECT_DIR}}" not in str(result)


class TestTopologicalSort:
    """测试拓扑排序"""

    def test_no_dependencies(self):
        services = [
            {"name": "a", "depends": []},
            {"name": "b", "depends": []},
            {"name": "c", "depends": []},
        ]
        order = resolve_startup_order(services)
        names = [s["name"] for s in order]
        assert set(names) == {"a", "b", "c"}

    def test_linear_dependency(self):
        # a -> b -> c
        services = [
            {"name": "c", "depends": ["b"]},
            {"name": "b", "depends": ["a"]},
            {"name": "a", "depends": []},
        ]
        order = resolve_startup_order(services)
        names = [s["name"] for s in order]
        # a 必须在 b 前面，b 必须在 c 前面
        assert names.index("a") < names.index("b") < names.index("c")

    def test_parallel_dependency(self):
        # a -> b, a -> c
        services = [
            {"name": "a", "depends": []},
            {"name": "b", "depends": ["a"]},
            {"name": "c", "depends": ["a"]},
        ]
        order = resolve_startup_order(services)
        names = [s["name"] for s in order]
        # a 必须在最前面
        assert names.index("a") == 0
        # b 和 c 都在 a 后面
        assert names.index("b") > 0
        assert names.index("c") > 0

    def test_complex_dependency(self):
        #    a
        #   / \
        #  b   c
        #   \ /
        #    d
        services = [
            {"name": "a", "depends": []},
            {"name": "b", "depends": ["a"]},
            {"name": "c", "depends": ["a"]},
            {"name": "d", "depends": ["b", "c"]},
        ]
        order = resolve_startup_order(services)
        names = [s["name"] for s in order]
        # a 最前，d 最后
        assert names.index("a") < names.index("d")
        # b 和 c 都在 d 前面
        assert names.index("b") < names.index("d")
        assert names.index("c") < names.index("d")

    def test_circular_dependency(self):
        # a -> b -> c -> a (循环)
        services = [
            {"name": "a", "depends": ["c"]},
            {"name": "b", "depends": ["a"]},
            {"name": "c", "depends": ["b"]},
        ]
        with pytest.raises(ValueError, match="循环依赖"):
            resolve_startup_order(services)

    def test_self_dependency(self):
        services = [
            {"name": "a", "depends": ["a"]},
        ]
        with pytest.raises(ValueError, match="循环依赖"):
            resolve_startup_order(services)


class TestStopOrder:
    """测试停止顺序（启动顺序的逆序）"""

    def test_stop_order_reversed(self):
        services = [
            {"name": "a", "depends": []},
            {"name": "b", "depends": ["a"]},
            {"name": "c", "depends": ["b"]},
        ]
        start_order = resolve_startup_order(services)
        stop_order = resolve_stop_order(services)
        # 停止顺序应该是启动顺序的逆序
        start_names = [s["name"] for s in start_order]
        stop_names = [s["name"] for s in stop_order]
        assert stop_names == list(reversed(start_names))


class TestConfigLoader:
    """测试配置加载器"""

    def test_load_services_yaml(self):
        config_path = PROJECT_DIR / "config" / "services.yaml"
        if not config_path.exists():
            pytest.skip("services.yaml not found")

        loader = ConfigLoader(config_path)
        config = loader.load()

        assert "services" in config
        assert len(config["services"]) > 0

        # 检查所有服务都有必要字段
        for name, svc in config["services"].items():
            assert "name" in svc
            assert "port" in svc
            assert "cmd" in svc
            assert "cwd" in svc

    def test_service_has_dependencies_field(self):
        config_path = PROJECT_DIR / "config" / "services.yaml"
        if not config_path.exists():
            pytest.skip("services.yaml not found")

        loader = ConfigLoader(config_path)
        config = loader.load()

        for name, svc in config["services"].items():
            assert "depends" in svc


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
