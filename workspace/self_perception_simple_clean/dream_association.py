"""
做梦模式 - 关联记忆写入脚本
使用 MiniMax 模型（DeepSeek 作为备用）
"""
import json
import urllib.request
import urllib.error
import sys
import os
import time

VECTOR_API = "http://127.0.0.1:8007"

# MiniMax API 配置 (Anthropic 格式)
MINIMAX_API = "https://api.minimaxi.com/anthropic/v1/messages"
import subprocess
MINIMAX_KEY = os.environ.get("MINIMAX_API_KEY", "your_minimax_key_here")

# DeepSeek 备用配置
DEEPSEEK_API = "https://api.deepseek.com/v1"
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "your_deepseek_key_here")

# MiniMax 限流器：每秒最多40次，留有余量
_MINIMAX_TOKENS = 40  # 每秒令牌数
_MINIMAX_BUCKET = []  # 时间戳队列


def _wait_for_token():
    """等待一个令牌（限流）"""
    now = time.time()
    # 清理超过1秒的旧时间戳
    while _MINIMAX_BUCKET and _MINIMAX_BUCKET[0] < now - 1:
        _MINIMAX_BUCKET.pop(0)
    # 桶满则等待
    if len(_MINIMAX_BUCKET) >= _MINIMAX_TOKENS:
        wait_time = 1 - (now - _MINIMAX_BUCKET[0])
        if wait_time > 0:
            time.sleep(wait_time)
            _wait_for_token()
            return
    _MINIMAX_BUCKET.append(now)


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


def api_put_memory(mem_id, metadata):
    """使用禁用代理的 opener 访问向量服务"""
    url = f"{VECTOR_API}/memories/{mem_id}"
    data = json.dumps({"metadata": metadata}).encode()
    opener = _get_no_proxy_opener()
    opener.addheaders = [("Content-Type", "application/json"), ("Connection", "close")]
    try:
        resp = opener.open(url, data=data, timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def call_minimax(prompt):
    """调用 MiniMax 模型 (Anthropic 格式) - 子进程隔离版本"""
    _wait_for_token()  # 限流
    
    # 在子进程中执行 HTTPS 请求，避免 urllib 连接池污染
    script = f'''
import json, urllib.request, urllib.error, sys

MINIMAX_API = "https://api.minimaxi.com/anthropic/v1/messages"
MINIMAX_KEY = "sk-cp-X-Fa2n3FlZdich53szybFBilDJrP2iZcItZMFWpqMOpZJ66nW4oI26zg5wH-K4kDX-eXvI8cfVSKf7Qd3KIm4z6rgX417cGd2oo3nNof0Wx4lmS6i100eC0"

system_msg = "你是一个记忆关联分析器。只输出JSON数组，不要任何思考过程、解释或额外文字。格式：[{{\\"id1\\":\\"xxx\\",\\"id2\\":\\"yyy\\",\\"relation\\":\\"类型\\",\\"reason\\":\\"原因\\"}}]"
payload = {{
    "model": "MiniMax-M2.7",
    "messages": [
        {{"role": "system", "content": system_msg}},
        {{"role": "user", "content": {json.dumps(prompt)}}}
    ],
    "max_tokens": 4000
}}
data = json.dumps(payload).encode()
req = urllib.request.Request(
    MINIMAX_API,
    data=data,
    method="POST"
)
req.add_header("Content-Type", "application/json")
req.add_header("Authorization", f"Bearer {{MINIMAX_KEY}}")
req.add_header("anthropic-version", "2023-06-01")
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
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
        # 清除代理设置，避免连接127.0.0.1:10808(代理未运行)
        for k in list(env.keys()):
            if 'proxy' in k.lower():
                del env[k]
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


def normalize_metadata(metadata):
    """兼容旧数据：relation_types 可能是 list 或 dict"""
    if not isinstance(metadata, dict):
        return {}
    
    result = dict(metadata)
    
    # 确保 related_ids 是 list
    if "related_ids" not in result:
        result["related_ids"] = []
    elif not isinstance(result["related_ids"], list):
        # 如果是单个值，转成列表
        result["related_ids"] = [result["related_ids"]]
    
    # 确保 relation_types 是 dict（兼容旧的 list 格式）
    if "relation_types" not in result:
        result["relation_types"] = {}
    elif isinstance(result["relation_types"], list):
        # 旧的 list 格式：无法完美转换，只能清空重写
        # 保留 list 格式的原有信息，不覆盖
        result["relation_types"] = {}
    
    return result




def _get_no_proxy_opener():
    """创建显式禁用代理的 opener，解决代理未运行问题"""
    # 空 ProxyHandler = 不使用任何代理
    proxy_handler = urllib.request.ProxyHandler()
    return urllib.request.build_opener(proxy_handler)

def call_deepseek(prompt):
    """调用 DeepSeek 模型（备用）- 显式禁用代理"""
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
    opener = _get_no_proxy_opener()
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


def extract_json(text):
    """从文本中提取 JSON 数组，处理 thinking 干扰"""
    if not text:
        return None
    
    text = text.strip()
    
    # 方法1: 直接尝试解析整个文本（如果本身就是干净 JSON）
    if text.startswith("["):
        try:
            return json.loads(text)
        except:
            pass
    
    # 方法2: 查找 JSON 数组模式
    # 移除可能的 thinking 标记内容
    lines = text.split("\n")
    clean_lines = []
    skip_mode = False
    
    for line in lines:
        # 跳过 thinking 相关行
        if any(marker in line.lower() for marker in ["thinking", "thought", "分析中", "让我", "首先", "然后"]):
            # 检查是否是 JSON 内容行
            if not line.strip().startswith("{"):
                skip_mode = True
                continue
        if skip_mode and line.strip().startswith("}"):
            skip_mode = False
            continue
        if not skip_mode:
            clean_lines.append(line)
    
    clean_text = "\n".join(clean_lines)
    
    # 查找 [{...}] 或 [...]
    for start_marker in ["[{", "["]:
        start = clean_text.find(start_marker)
        if start >= 0:
            depth = 0
            end = 0
            for i, c in enumerate(clean_text[start:], start):
                if c in "{[":
                    depth += 1
                elif c in "}]":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end > start:
                try:
                    parsed = json.loads(clean_text[start:end])
                    if isinstance(parsed, list):
                        return parsed
                except:
                    pass
    
    return None


def main():
    print("=" * 50)
    print("做梦模式 - 关联记忆开始")
    
    # Step 1: 获取所有记忆
    print("获取记忆列表...")
    result = api_get("/memories")
    memories = result.get("memories", [])
    total = len(memories)
    print(f"共 {total} 条记忆")
    
    if total == 0:
        print("无记忆，退出")
        return
    
    # 构建有效 ID 集合（用于过滤 LLM 幻觉 ID）
    all_valid_ids = {str(m["id"]) for m in memories}
    
    # Step 2: 分批分析
    batch_size = 10
    all_pairs = []
    
    for i in range(0, total, batch_size):
        batch = memories[i:i+batch_size]
        batch_num = i // batch_size + 1
        print(f"分析批次 {batch_num}，记忆 {i+1}-{min(i+batch_size, total)}...")
        
        # 构造 prompt
        available_ids = ", ".join(str(m['id']) for m in batch)
        mem_list = "\n".join([
            f"[{m['id']}] {str(m.get('content', ''))[:200]}"
            for m in batch
        ])
        
        prompt = f"""分析以下记忆，找出语义相关的内容对。关联类型：
- same_project：同一个项目
- same_topic：同一主题
- follow_up：后续讨论/延续
- related：广义相关

【重要约束】本批次可用 ID（必须从下列 ID 中选择，不得发明新 ID）：{available_ids}
如果某对记忆没有合适的关联，直接跳过，不要编造 ID。

记忆列表：
{mem_list}

直接输出JSON数组，每项包含id1, id2, relation, reason，不要其他文字：
[{{"id1": "123", "id2": "456", "relation": "same_project", "reason": "简要原因"}}]"""

        # 先用 MiniMax
        use_deepseek = "--deepseek" in sys.argv
        if use_deepseek:
            print(f"  [DeepSeek 模式]")
            response = call_deepseek(prompt)
        else:
            response = call_minimax(prompt)
        
        if response.startswith("ERROR") or response.startswith("HTTP"):
            print(f"  批次 {batch_num} API错误: {response[:100]}")
            if "401" in response or "403" in response:
                print("  尝试切换到 DeepSeek...")
                response = call_deepseek(prompt)
                if response.startswith("ERROR") or response.startswith("HTTP"):
                    print(f"  DeepSeek 也失败: {response[:100]}")
                    continue
            else:
                continue
        
        pairs = extract_json(response)
        if pairs:
            # ---- A方案：过滤掉幻觉 ID ----
            valid_pairs = [
                p for p in pairs
                if str(p.get("id1", "")) in all_valid_ids
                and str(p.get("id2", "")) in all_valid_ids
            ]
            invalid_count = len(pairs) - len(valid_pairs)
            if invalid_count > 0:
                print(f"  批次 {batch_num} 过滤掉 {invalid_count} 个幻觉 ID 配对")
            pairs = valid_pairs
            # ---- 过滤结束 ----
            if pairs:
                all_pairs.extend(pairs)
                print(f"  批次 {batch_num} 发现 {len(pairs)} 对有效关联")
        else:
            print(f"  批次 {batch_num} 无法解析JSON，跳过")
    
    print(f"\n共发现 {len(all_pairs)} 对关联")
    
    if not all_pairs:
        print("无关联可写入，退出")
        return
    
    # Step 3: 双向写入关联
    print("写入关联到 metadata...")
    
    relations = {}
    for pair in all_pairs:
        id1 = str(pair["id1"])
        id2 = str(pair["id2"])
        rel = pair.get("relation", "related")
        
        if id1 not in relations:
            relations[id1] = {}
        if id2 not in relations:
            relations[id2] = {}
        
        relations[id1][id2] = rel
        relations[id2][id1] = rel
    
    updated = 0
    for mem_id, related in relations.items():
        try:
            mem_data = api_get(f"/memories/{mem_id}")
            existing = normalize_metadata(mem_data.get("memory", {}).get("metadata", {}))
            
            for rid in related:
                if rid not in existing.get("related_ids", []):
                    existing.setdefault("related_ids", []).append(rid)
                if rid not in existing.get("relation_types", {}):
                    existing.setdefault("relation_types", {})[rid] = related[rid]
            
            result = api_put_memory(mem_id, existing)
            if result.get("status") == "success":
                updated += 1
        except Exception as e:
            print(f"  更新 {mem_id} 失败: {e}")
    
    print(f"\n完成！更新了 {updated} 条记忆的关联")
    print("=" * 50)


if __name__ == "__main__":
    main()
