# Dream Association 网络问题修复方案

> 架构师: Architect Agent | 日期: 2026-04-06 | 状态: 设计完成

---

## 一、问题分析

### 1.1 已确认的事实

| 项目 | 状态 |
|------|------|
| 向量服务端口 | 8007 (绑定 0.0.0.0) |
| 向量服务进程 | Python PID 10084 (C:\Python310) |
| 向量服务类型 | 原生 Windows 进程，非 Docker |
| Docker 状态 | **未运行** (Docker Desktop 未启动) |
| 端口可访问性 | `netstat` 显示 127.0.0.1:8007 LISTENING |
| 健康检查 (cron isolated) | ✅ 成功 (port 8007 正常) |
| HTTP_PROXY 环境变量 | `http://127.0.0.1:10808` (代理未运行) |
| NO_PROXY | `*.qq.com,*.minimaxi.com,localhost,127.0.0.1,...` |

### 1.2 问题现象回顾

**现象 1: 本地直接运行**
- `api_get("/memories")` → ✅ 成功
- `call_minimax()` → ❌ 连接被拒绝

**现象 2: Cron Isolated Session 运行**
- MiniMax API 调用 → ✅ 成功 (token 使用证明)
- localhost:8007 连接 → ❌ 失败

**现象 3: 子进程隔离方案**
- 在 isolated session 中也有问题

---

## 二、根本原因分析

### 2.1 问题 1: urllib 代理处理 Bug

**影响范围**: 本地直接运行 + 所有环境

Python `urllib` 的 `NO_PROXY` 处理存在已知问题：

1. **通配符域名匹配 bug**: `*.qq.com` 这样的模式可能导致后续精确匹配 `qq.com` 失效
2. **端口级匹配缺失**: `localhost` 不匹配 `localhost:8007`（标准库只检查 host，不检查 port）
3. **环境变量大小写**: Windows 上 `NO_PROXY` 和 `no_proxy` 可能被不同组件以不同方式解释

**代码证据** (`dream_association.py`):
```python
# api_get 使用自定义 opener，但仍然受系统代理影响
opener = urllib.request.build_opener()
opener.addheaders = [("Connection", "close")]

# call_minimax 的子进程隔离尝试清除 proxy env vars
env = os.environ.copy()
for k in list(env.keys()):
    if 'proxy' in k.lower():
        del env[k]
```

`api_get` 使用 urllib 直接连接，虽然 NO_PROXY 包含 `localhost`，但 urllib 可能仍尝试通过代理（特别是 Windows 的 WinHTTP/WinInet 级别代理设置）。

### 2.2 问题 2: Cron Isolated Session 网络隔离

**影响范围**: 仅 cron isolated session

根据 `openclaw.json` 配置:
```json
"agents": {
    "defaults": {
      "sandbox": {
        "mode": "non-main",
        "docker": {
          "image": "openclaw-sandbox-common:bookworm-slim",
          "network": "bridge"
        }
      }
    }
}
```

但 **Docker 未运行**，所以 isolated session 实际行为可能退化到某种 fallback 模式。

健康检查 cron job 成功连接 8007，但 dream_association.py 失败。差异在于:
- 健康检查使用 `netstat` 检查端口状态（不建立 HTTP 连接）
- dream_association.py 使用 urllib HTTP 请求

**可能的根因**: Isolated session 的 HTTP 请求走了不同的网络路径（如代理），而 `NO_PROXY` 设置在 isolated session 中可能未正确传递或解析。

### 2.3 问题 3: 子进程隔离的 proxy env var 清除不完整

**代码问题**:
```python
for k in list(env.keys()):
    if 'proxy' in k.lower():
        del env[k]
```

只删除 key 包含 "proxy" 的环境变量，但:
1. Windows 系统代理可能存储在注册表，不通过 env var 传递
2. `requests` 库会读取 `HTTP_PROXY` / `http_proxy`，但 urllib 也会检查 `HTTPS_PROXY` / `https_proxy`
3. 可能有 `ALL_PROXY` / `all_proxy` 未被清除

---

## 三、解决方案设计

### 3.1 核心原则

1. **显式覆盖代理设置** - 不依赖 NO_PROXY，在代码中显式禁用代理
2. **跨平台兼容** - 同时支持 Windows/Linux/macOS
3. **独立于环境** - 不依赖特定的 cron session 类型
4. **最小改动** - 保持现有架构不变

### 3.2 方案: 显式 Proxy Override

为所有 HTTP 请求显式设置 `proxy = None`，绕过系统代理配置。

#### 3.2.1 修改 api_get / api_put_memory

```python
import os
from urllib.parse import urlparse

def _get_no_proxy_opener():
    """创建显式禁用代理的 opener"""
    proxy_handler = urllib.request.ProxyHandler({
        'http': None,
        'https': None,
        'ftp': None,
    })
    return urllib.request.build_opener(proxy_handler)

def api_get(path):
    """使用禁用代理的 opener 访问向量服务"""
    url = f"{VECTOR_API}{path}"
    opener = _get_no_proxy_opener()
    opener.addheaders = [("Connection", "close")]
    try:
        resp = opener.open(url, timeout=30)
        return json.loads(resp.read())
    except Exception as e:
        print(f"    [api_get ERROR] {path}: {e}", flush=True)
        raise
```

**原理**: `ProxyHandler({'http': None})` 强制 urllib 不使用任何代理，直接连接。

#### 3.2.2 修改 call_minimax 子进程

在子进程中同样使用 `ProxyHandler` 强制禁用代理:

```python
script = f'''
import json, urllib.request, urllib.error, sys
from urllib.request import ProxyHandler, build_opener

# 强制禁用代理
proxy_handler = ProxyHandler({{'http': None, 'https': None}})
opener = build_opener(proxy_handler)
opener.addheaders = []

# ... 后续使用 opener 而不是 urllib.urlopen
'''
```

同时保留现有的 env var 清除逻辑，作为纵深防御。

#### 3.2.3 修复后的 call_minimax 完整代码

```python
def call_minimax(prompt):
    """调用 MiniMax 模型 (Anthropic 格式) - 子进程隔离版本"""
    _wait_for_token()  # 限流
    
    script = f'''
import json, urllib.request, urllib.error, sys
from urllib.request import ProxyHandler, build_opener

# 强制禁用代理 - 解决 127.0.0.1:10808 代理未运行问题
proxy_handler = ProxyHandler({{'http': None, 'https': None}})
opener = build_opener(proxy_handler)
opener.addheaders = [
    ("Content-Type", "application/json"),
    ("Authorization", "Bearer MINIMAX_KEY_PLACEHOLDER"),
    ("anthropic-version", "2023-06-01"),
]

MINIMAX_API = "https://api.minimaxi.com/anthropic/v1/messages"
MINIMAX_KEY = "sk-cp-X-Fa2n3FlZdich53szybFBilDJrP2iZcItZMFWpqMOpZJ66nW4oI26zg5wH-K4kDX-eXvI8cfVSKf7Qd3KIm4z6rgX417cGd2oo3nNof0Wx4lmS6i100eC0"

system_msg = "你是一个记忆关联分析器。只输出JSON数组，不要任何思考过程、解释或额外文字。"
payload = {{
    "model": "MiniMax-M2.7",
    "messages": [
        {{"role": "system", "content": system_msg}},
        {{"role": "user", "content": {json.dumps(prompt)}}}
    ],
    "max_tokens": 4000
}}
data = json.dumps(payload).encode()

try:
    req = urllib.request.Request(MINIMAX_API, data=data, method="POST")
    resp = opener.open(req, timeout=120)
    result = json.loads(resp.read().decode())
    content = result.get("content", [])
    if content and isinstance(content, list):
        for item in content:
            if item.get("type") == "text":
                print(item.get("text", ""), end="", flush=True)
                sys.exit(0)
    print("", end="", flush=True)
    sys.exit(0)
except urllib.error.HTTPError as e:
    print(f"HTTP {{e.code}}", end="", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {{e}}", end="", flush=True)
    sys.exit(1)
'''
    
    try:
        env = os.environ.copy()
        # 清除所有可能的代理环境变量
        for k in list(env.keys()):
            if 'proxy' in k.lower():
                del env[k]
        # 额外清除（确保全面）
        for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'FTP_PROXY', 'ALL_PROXY',
                  'http_proxy', 'https_proxy', 'ftp_proxy', 'all_proxy',
                  'NO_PROXY', 'no_proxy']:
            env.pop(k, None)
        
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=130,
            env=env
        )
        if result.returncode == 0:
            return result.stdout
        else:
            return f"ERROR: {result.stdout}"
    except subprocess.TimeoutExpired:
        return "ERROR: Timeout"
    except Exception as e:
        return f"ERROR: {e}"
```

#### 3.2.4 修复 call_deepseek

同样修复 `call_deepseek`，使用 `ProxyHandler`:

```python
def call_deepseek(prompt):
    """调用 DeepSeek 模型（备用）- 显式禁用代理"""
    from urllib.request import ProxyHandler, build_opener
    
    proxy_handler = ProxyHandler({'http': None, 'https': None})
    opener = build_opener(proxy_handler)
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4000
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{DEEPSEEK_API}/chat/completions",
        data=data,
        method="POST"
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {DEEPSEEK_KEY}")
    try:
        resp = opener.open(req, timeout=120)
        result = json.loads(resp.read().decode())
        choices = result.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return f"HTTP {e.code}: {body}"
    except Exception as e:
        return f"ERROR: {e}"
```

---

## 四、替代方案（备选）

### 4.1 方案 B: 使用 requests 库替代 urllib

`requests` 库的代理处理更可靠:

```python
import requests

def api_get(path):
    url = f"{VECTOR_API}{path}"
    try:
        resp = requests.get(url, timeout=30, proxies={'http': None, 'https': None})
        return resp.json()
    except Exception as e:
        print(f"    [api_get ERROR] {path}: {e}", flush=True)
        raise
```

**缺点**: 需要安装 requests 库，当前环境可能未安装

### 4.2 方案 C: 使用 httpx（与 dream_service.py 保持一致）

`dream_service.py` 已使用 `httpx`，可保持一致性:

```python
import httpx

def api_get(path):
    url = f"{VECTOR_API}{path}"
    try:
        resp = httpx.get(url, timeout=30, proxy=False)
        return resp.json()
    except Exception as e:
        print(f"    [api_get ERROR] {path}: {e}", flush=True)
        raise
```

---

## 五、验证计划

### 5.1 单元测试

1. **代理覆盖测试**: 验证 `ProxyHandler({...})` 确实禁用代理
2. **子进程环境测试**: 验证子进程不继承任何 proxy env vars
3. **直接运行测试**: 手动运行脚本，验证:
   - `api_get("/memories")` 返回正确数据
   - `call_minimax()` 返回有效响应

### 5.2 Cron Isolated Session 测试

1. 创建测试 cron job，运行简化版脚本
2. 验证 localhost:8007 连接成功
3. 验证 MiniMax API 调用成功

### 5.3 回归测试

1. 确认原有功能（向量写入、关联更新）不受影响
2. 确认限流逻辑仍然有效
3. 确认错误处理逻辑不变

---

## 六、修改清单

| 文件 | 修改内容 |
|------|---------|
| `dream_association.py` | 1. 添加 `_get_no_proxy_opener()` 函数<br>2. 修改 `api_get()` 使用 `ProxyHandler`<br>3. 修改 `api_put_memory()` 使用 `ProxyHandler`<br>4. 修改 `call_minimax()` 子进程脚本添加 `ProxyHandler`<br>5. 修改 `call_deepseek()` 使用 `ProxyHandler`<br>6. 增强 env var 清除逻辑 |

---

## 七、风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| ProxyHandler 仍受系统代理影响 | 低 | 中 | requests/httpx 备选方案 |
| 子进程脚本注入引号转义问题 | 中 | 中 | 使用模板字符串正确转义 |
| 修改破坏现有功能 | 低 | 高 | 保留原逻辑作为 fallback |
| 跨平台兼容性 | 低 | 中 | Windows/Linux/macOS 均支持 ProxyHandler |

---

## 八、结论

**推荐采用方案 3.2（显式 ProxyHandler Override）**，理由:
1. **最小改动**: 只需修改 `dream_association.py`
2. **无需依赖**: 不需要安装额外库
3. **跨平台**: Python 标准库，`ProxyHandler` 在所有平台行为一致
4. **可验证**: 容易编写测试验证
5. **彻底**: 直接在 urllib 层面禁用代理，不依赖环境变量

**预计工作量**: 1-2 小时（包括测试）
