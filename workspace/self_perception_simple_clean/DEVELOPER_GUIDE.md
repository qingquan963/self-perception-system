# 开发指南

## 📋 目录

1. [代码结构详解](#代码结构详解)
2. [开发环境搭建](#开发环境搭建)
3. [模块开发指南](#模块开发指南)
4. [API扩展方法](#api扩展方法)
5. [数据库设计](#数据库设计)
6. [测试框架](#测试框架)
7. [部署流程](#部署流程)
8. [贡献指南](#贡献指南)

## 🏗️ 代码结构详解

### 项目目录结构

```
self_perception_simple_clean/
├── frontend/                    # 前端文件
│   └── waiting.html            # 前端界面
├── modules/                     # 功能模块
│   ├── __init__.py             # 模块初始化
│   ├── capability_assessment.py # 能力评估模块
│   ├── conversation_memory.py   # 对话记忆模块
│   ├── decision_recorder.py     # 决策记录模块
│   ├── learning_feedback.py     # 学习反馈模块
│   └── task_tracker.py          # 任务跟踪模块
├── utils/                       # 工具函数
│   └── __init__.py             # 工具模块初始化
├── vector_store/                # 向量存储数据
│   ├── enhanced_memories_v1.json      # 记忆数据
│   └── enhanced_memories_v1_clean.json # 清理后记忆
├── .env                         # 环境变量
├── .env.example                 # 环境变量示例
├── .gitignore                   # Git忽略文件
├── api_service.py               # API服务主文件
├── API_DOCUMENTATION.md         # API文档
├── config.json                  # 系统配置文件
├── context_alert.py             # 上下文预警系统
├── create_clean_db.py           # 数据库创建脚本
├── check_db.py                  # 数据库检查脚本
├── README.md                    # 原始README
├── README_CN.md                 # 中文README（主文档）
├── USER_MANUAL.md               # 用户手册
├── ADMIN_GUIDE.md               # 管理员指南
├── DEVELOPER_GUIDE.md           # 开发指南（本文档）
├── FAQ.md                       # 常见问题解答
├── requirements.txt             # Python依赖
├── session_monitor.py           # 会话监控
├── start_all_services.ps1       # Windows启动脚本
├── start_all_services.sh        # Linux/macOS启动脚本
├── start_api_service.py         # API服务启动脚本
├── vector_service.py            # 向量存储服务
└── vectors.db                   # SQLite数据库文件
```

### 核心文件说明

#### 1. `api_service.py` - API服务主文件
```python
# 架构：FastAPI应用
# 功能：提供系统状态查询接口
# 端口：8001
# 主要端点：/, /health, /context/status
```

#### 2. `vector_service.py` - 向量存储服务
```python
# 架构：FastAPI + SQLite
# 功能：记忆存储和检索
# 端口：8007
# 主要端点：/, /health, /memories, /memories/search, /memories/add
```

#### 3. `session_monitor.py` - 会话监控
```python
# 架构：单例模式
# 功能：监控Token使用情况
# 集成：被API服务调用
```

#### 4. `context_alert.py` - 上下文预警
```python
# 架构：预警系统
# 功能：检查Token阈值并生成预警
# 配置：通过.env文件配置阈值
```

### 模块化设计

系统采用模块化设计，每个模块都有明确的职责：

1. **核心服务模块** (`api_service.py`, `vector_service.py`)
   - 提供基础服务功能
   - 处理HTTP请求和响应
   - 管理服务生命周期

2. **监控模块** (`session_monitor.py`, `context_alert.py`)
   - 监控系统状态
   - 生成预警和通知
   - 提供健康检查

3. **功能模块** (`modules/` 目录)
   - 可插拔的功能组件
   - 独立的功能实现
   - 标准化的接口设计

4. **工具模块** (`utils/` 目录)
   - 共享的工具函数
   - 辅助类和函数
   - 通用功能实现

## 🛠️ 开发环境搭建

### 环境要求

#### 基础环境
```bash
# 检查Python版本
python --version  # 需要3.8+

# 检查pip版本
pip --version     # 需要20.0+

# 检查Git版本
git --version     # 需要2.20+
```

#### 推荐开发工具
- **代码编辑器**: VS Code, PyCharm, Sublime Text
- **终端**: Windows Terminal, iTerm2, GNOME Terminal
- **数据库工具**: DB Browser for SQLite, DBeaver
- **API测试**: Postman, Insomnia, curl

### 开发环境配置步骤

#### 步骤1：克隆代码库

```bash
# 克隆项目
git clone https://github.com/your-username/self_perception_simple_clean.git
cd self_perception_simple_clean

# 创建开发分支
git checkout -b feature/your-feature-name
```

#### 步骤2：设置Python虚拟环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# 验证激活
which python  # 应该显示venv目录下的python
```

#### 步骤3：安装开发依赖

```bash
# 安装基础依赖
pip install -r requirements.txt

# 安装开发工具
pip install black flake8 mypy pytest pytest-cov pre-commit

# 安装开发环境额外工具
pip install ipython ipdb  # 交互式调试工具
```

#### 步骤4：配置开发环境变量

```bash
# 复制开发环境配置
cp .env.example .env.development

# 编辑开发配置
# Windows
notepad .env.development
# Linux/macOS
nano .env.development
```

开发环境配置示例：

```env
# 开发环境配置
DEEPSEEK_API_KEY=sk-dev-test-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# 开发模式设置
DEBUG=true
RELOAD=true
LOG_LEVEL=DEBUG

# 开发端口
API_SERVICE_PORT=8001
VECTOR_SERVICE_PORT=8007
FRONTEND_PORT=8080

# 开发数据库
DATABASE_PATH=vectors_dev.db
```

#### 步骤5：设置Git钩子

```bash
# 安装pre-commit钩子
pre-commit install

# 查看钩子配置
cat .pre-commit-config.yaml
```

示例 `.pre-commit-config.yaml`：

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3
        
  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=88', '--extend-ignore=E203,W503']
```

#### 步骤6：初始化开发数据库

```bash
# 创建开发数据库
python create_clean_db.py --env development

# 导入测试数据
python scripts/import_test_data.py
```

### 开发工作流

#### 日常开发流程

```bash
# 1. 更新代码
git pull origin main

# 2. 启动开发服务
python start_api_service.py --dev

# 3. 在另一个终端启动向量服务
python vector_service.py --dev

# 4. 运行测试
pytest tests/ -v

# 5. 代码格式化
black .
flake8 .

# 6. 提交代码
git add .
git commit -m "feat: 添加新功能"
git push origin feature/your-feature-name
```

#### 调试技巧

1. **使用调试器**：
```python
import ipdb

def some_function():
    # 设置断点
    ipdb.set_trace()
    # 代码执行会在这里暂停
    result = process_data()
    return result
```

2. **日志调试**：
```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_function():
    logger.debug("进入函数")
    try:
        result = risky_operation()
        logger.debug(f"操作结果: {result}")
    except Exception as e:
        logger.error(f"操作失败: {e}", exc_info=True)
```

3. **API测试**：
```bash
# 使用curl测试API
curl -X GET "http://localhost:8001/health"
curl -X POST "http://localhost:8007/memories/add" \
  -H "Content-Type: application/json" \
  -d '{"content": "测试记忆", "type": "test"}'
```

## 🧩 模块开发指南

### 模块设计原则

#### 1. 单一职责原则
每个模块只负责一个明确的功能领域。

#### 2. 接口标准化
模块提供统一的接口规范。

#### 3. 依赖注入
模块之间通过依赖注入减少耦合。

#### 4. 配置驱动
模块行为通过配置文件控制。

### 创建新模块

#### 步骤1：创建模块文件

在 `modules/` 目录下创建新模块文件，例如 `new_module.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新功能模块
功能描述：实现XXX功能
作者：你的名字
日期：2026-03-28
版本：1.0.0
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)

class NewModule:
    """新功能模块类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化模块
        
        Args:
            config: 模块配置字典
        """
        self.config = config or {}
        self.name = self.config.get('name', 'NewModule')
        self.version = '1.0.0'
        
        # 初始化模块状态
        self.initialized = False
        self.last_activity = None
        
        logger.info(f"模块初始化: {self.name} v{self.version}")
    
    def initialize(self) -> bool:
        """初始化模块"""
        try:
            # 执行初始化逻辑
            self.initialized = True
            self.last_activity = datetime.now()
            
            logger.info(f"模块 {self.name} 初始化成功")
            return True
        except Exception as e:
            logger.error(f"模块初始化失败: {e}")
            return False
    
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理数据
        
        Args:
            data: 输入数据
            
        Returns:
            处理结果
        """
        if not self.initialized:
            raise RuntimeError("模块未初始化")
        
        try:
            logger.debug(f"开始处理数据: {data}")
            
            # 处理逻辑
            result = {
                'processed': True,
                'input': data,
                'output': self._process_logic(data),
                'timestamp': datetime.now().isoformat(),
                'module': self.name
            }
            
            self.last_activity = datetime.now()
            logger.info(f"数据处理完成: {result}")
            
            return result
        except Exception as e:
            logger.error(f"数据处理失败: {e}", exc_info=True)
            raise
    
    def _process_logic(self, data: Dict[str, Any]) -> Any:
        """内部处理逻辑"""
        # 实现具体的处理逻辑
        return {"status": "processed", "data": data}
    
    def get_status(self) -> Dict[str, Any]:
        """获取模块状态"""
        return {
            'name': self.name,
            'version': self.version,
            'initialized': self.initialized,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'config': self.config
        }
    
    def cleanup(self):
        """清理资源"""
        logger.info(f"清理模块资源: {self.name}")
        self.initialized = False
```

#### 步骤2：创建模块测试

在 `tests/` 目录下创建测试文件 `test_new_module.py`：

```python
#!/usr/bin/env python3
"""
新模块测试
"""

import pytest
from modules.new_module import NewModule

class TestNewModule:
    """新模块测试类"""
    
    def setup_method(self):
        """测试设置"""
        self.module = NewModule({'name': 'TestModule'})
    
    def teardown_method(self):
        """测试清理"""
        self.module.cleanup()
    
    def test_initialization(self):
        """测试初始化"""
        assert self.module.name == 'TestModule'
        assert self.module.version == '1.0.0'
        assert not self.module.initialized
    
    def test_initialize(self):
        """测试初始化方法"""
        result = self.module.initialize()
        assert result is True
        assert self.module.initialized is True
    
    def test_process(self):
        """测试数据处理"""
        self.module.initialize()
        
        test_data = {'key': 'value'}
        result = self.module.process(test_data)
        
        assert result['processed'] is True
        assert result['input'] == test_data
        assert 'output' in result
        assert 'timestamp' in result
    
    def test_get_status(self):
        """测试状态获取"""
        status = self.module.get_status()
        
        assert status['name'] == 'TestModule'
        assert status['version'] == '1.0.0'
        assert status['initialized'] is False
```

#### 步骤3：集成到主系统

在 `api_service.py` 中集成新模块：

```python
# 导入新模块
from modules.new_module import NewModule

# 初始化模块
new_module = NewModule(config={'name': 'ProductionModule'})
new_module.initialize()

# 添加API端点
@app.get("/new-module/status")
async def get_new_module_status():
    """获取新模块状态"""
    return new_module.get_status()

@app.post("/new-module/process")
async def process_with_new_module(data: dict):
    """使用新模块处理数据"""
    try:
        result = new_module.process(data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 步骤4：更新配置文件

在 `config.json` 中添加模块配置：

```json
{
    "modules": {
        "new_module": {
            "enabled": true,
            "name": "NewModule",
            "config": {
                "param1": "value1",
                "param2": 100
            }
        }
    }
}
```

### 模块接口规范

#### 1. 基础接口

所有模块应该实现以下基础接口：

```python
class BaseModule:
    """模块基类"""
    
    def __init__(self, config: dict):
        self.config = config
    
    def initialize(self) -> bool:
        """初始化模块"""
        pass
    
    def process(self, data: dict) -> dict:
        """处理数据"""
        pass
    
    def get_status(self) -> dict:
        """获取模块状态"""
        pass
    
    def cleanup(self):
        """清理资源"""
        pass
```

#### 2. 配置规范

模块配置应该遵循以下规范：

```python
DEFAULT_CONFIG = {
    'enabled': True,           # 是否启用
    'name': 'ModuleName',      # 模块名称
    'version': '1.0.0',        # 模块版本
    'timeout': 30,             # 超时时间（秒）
    'retry_count': 3,          # 重试次数
    'log_level': 'INFO'        # 日志级别
}
```

#### 3. 响应格式规范

模块处理结果应该遵循以下格式：

```python
STANDARD_RESPONSE = {
    'success': True,           # 是否成功
    'data': {},                # 处理结果数据
    'error': None,             # 错误信息（成功时为None）
    'timestamp': 'ISO时间戳',   # 时间戳
    'module': '模块名称',       # 模块标识
    'processing_time': 0.123   # 处理时间（秒）
}
```

### 模块依赖管理

#### 1. 依赖声明

在模块文件顶部声明依赖：

```python
"""
模块依赖：
- fastapi: Web框架
- sqlalchemy: ORM框架
- pydantic: 数据验证
"""

REQUIREMENTS = [
    'fastapi>=0.100.0',
    'sqlalchemy>=2.0.0',
    'pydantic>=2.0.0'
]
```

#### 2. 可选依赖处理

```python
try:
    import optional_dependency
    HAS_OPTIONAL_DEP = True
except ImportError:
    HAS_OPTIONAL_DEP = False
    import warnings
    warnings.warn("可选依赖 optional_dependency 未安装，某些功能不可用")

class ModuleWithOptional:
    def __init__(self):
        if not HAS_OPTIONAL_DEP:
            raise ImportError("需要安装 optional_dependency")
```

#### 3. 延迟导入

```python
class LazyModule:
    def __init__(self):
        self._heavy_dependency = None
    
    @property
    def heavy_d