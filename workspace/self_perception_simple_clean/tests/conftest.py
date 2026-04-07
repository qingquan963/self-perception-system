#!/usr/bin/env python3
"""
conftest.py - pytest 配置和共享 fixtures
"""
import pytest
import tempfile
import os
from pathlib import Path

# 添加项目路径到 sys.path
PROJECT_DIR = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(PROJECT_DIR))


@pytest.fixture(scope="session")
def project_dir():
    """项目目录"""
    return PROJECT_DIR


@pytest.fixture(scope="session")
def config_dir(project_dir):
    """配置目录"""
    return project_dir / "config"


@pytest.fixture
def temp_dir():
    """临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_services_yaml(temp_dir):
    """示例 services.yaml 内容"""
    yaml_content = """
version: "1.0"

services:
  api_service:
    name: "api_service"
    port: 8011
    cmd: ["python", "-m", "uvicorn", "api_service:app"]
    cwd: "{{PROJECT_DIR}}"
    health_url: "http://127.0.0.1:8011/health"
    depends: []
    resources:
      max_memory_mb: 512
      max_cpu_percent: 80

  vector_service:
    name: "vector_service"
    port: 8007
    cmd: ["python", "-m", "uvicorn", "vector_service:app"]
    cwd: "{{PROJECT_DIR}}"
    health_url: "http://127.0.0.1:8007/health"
    depends: []
    resources:
      max_memory_mb: 1024
      max_cpu_percent: 90

  compaction_writer:
    name: "compaction_writer"
    port: 8014
    cmd: ["python", "compaction_writer.py"]
    cwd: "{{PROJECT_DIR}}"
    health_url: "http://127.0.0.1:8014/health"
    depends: ["api_service", "vector_service"]
    resources:
      max_memory_mb: 384
      max_cpu_percent: 70
"""
    yaml_path = temp_dir / "services.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")
    return yaml_path
