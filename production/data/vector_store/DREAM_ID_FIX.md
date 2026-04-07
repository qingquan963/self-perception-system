# DREAM_ID_FIX.md - 做梦脚本 LLM 幻觉 ID 问题修复方案

## 问题根因

`dream_association.py` 在 `main()` 函数中：

1. **Prompt 给出的是 `[id] content` 格式**，LLM 确实看到了这些 ID（如 `1`, `2`, `3`）
2. **但 LLM 生成输出时**，可能"创造"出不在输入中的 ID（如 `369`, `432`）
3. **`extract_json()` 只负责解析 JSON**，不做 ID 有效性验证
4. **`api_put_memory()` 直接写入**，没有检查 ID 是否真实存在
5. **结果**：向量库中出现指向不存在记忆的关联

**核心问题**：LLM 被要求从"一批记忆"中分析关联，但这批记忆的 ID 并未被明确告知为"唯一种子"——LLM 可能会超出这个范围进行"推理扩展"，生成幻觉 ID。

---

## 解决方案

### 方案 A（推荐）：解析后验证 + 有效 ID 集合过滤

**原理**：在 `extract_json()` 返回结果后，用从 `/memories` API 获取的真实 ID 集合做过滤，只保留 ID 真实存在的配对。

**优点**：改动最小，对 prompt 无需大幅修改
**缺点**：过滤掉 LLM 的幻觉输出，浪费一次 API 调用

**代码改动**：

```python
# Step 2 之前，先获取所有有效 ID 集合
all_valid_ids = {str(m["id"]) for m in memories}  # {"1","2","3"...}

# 在 extract_json 之后，加一行过滤：
if pairs:
    valid_pairs = [p for p in pairs if str(p["id1"]) in all_valid_ids and str(p["id2"]) in all_valid_ids]
    invalid_count = len(pairs) - len(valid_pairs)
    if invalid_count > 0:
        print(f"  过滤掉 {invalid_count} 个无效 ID 配对")
    pairs = valid_pairs
    if pairs:
        all_pairs.extend(pairs)
```

---

### 方案 B（核心修复）：Prompt 强化约束

**原理**：在 prompt 中明确声明：
1. 有效 ID 范围（即本次批次内的 ID 列表）
2. **只允许使用本批次内出现的 ID**
3. **禁止发明或推断本批次以外的 ID**

**改动的 prompt**：

```python
prompt = f"""分析以下记忆，找出语义相关的内容对。关联类型：
- same_project：同一个项目
- same_topic：同一主题
- follow_up：后续讨论/延续
- related：广义相关

【重要】本批次可用 ID 列表：{可用ID列表}
你只能使用上述列表中的 ID，不得使用任何其他 ID（包括不存在的数字）。
如果某对记忆没有合适的关联，不要编造，直接跳过。

记忆列表：
{mem_list}

直接输出JSON数组，每项包含id1, id2, relation, reason，不要其他文字：
[{{"id1": "123", "id2": "456", "relation": "same_project", "reason": "简要原因"}}]"""
```

其中 `可用ID列表` 由代码生成：

```python
available_ids = ", ".join(str(m["id"]) for m in batch)
```

---

### 方案 C（最彻底）：两阶段 ID 引用

**原理**：让 LLM 不输出原始数字 ID，而是输出"在本批次列表中的行号"（1-based），然后在 Python 代码中映射回真实 ID。

**优点**：彻底避免 LLM 生成任意数字
**缺点**：需要改代码解析逻辑，prompt 和后处理都需改动

**不推荐在此场景使用**——批次数最多 58 条，直接传真实 ID 即可。

---

## 最终推荐方案：A + B 组合

### 改动 1：`main()` 函数中添加有效 ID 集合

```python
# Step 1: 获取所有记忆
result = api_get("/memories")
memories = result.get("memories", [])
total = len(memories)
print(f"共 {total} 条记忆")

if total == 0:
    print("无记忆，退出")
    return

# 构建有效 ID 集合（用于后续过滤 LLM 幻觉输出）
all_valid_ids = {str(m["id"]) for m in memories}
```

### 改动 2：批次处理后加过滤逻辑（在 `all_pairs.extend(pairs)` 之前）

```python
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
```

### 改动 3：Prompt 强化（B 方案）

在 `prompt = f"""...` 的内容中，找到这行：
```
记忆列表：
```

在它之前插入：

```
【重要约束】本批次可用 ID（必须从下列 ID 中选择，不得发明新 ID）：{available_ids}
如果某对记忆没有合适的关联，直接跳过，不要编造 ID。

```

生成 `available_ids` 的代码在构造 prompt 的函数内：

```python
available_ids = ", ".join(str(m['id']) for m in batch)
```

---

## 完整改动点定位

文件：`dream_association.py`

| 位置 | 改动类型 | 描述 |
|------|---------|------|
| `main()` 内，API 调用后 | 新增 | `all_valid_ids = {str(m["id"]) for m in memories}` |
| `for m in batch` 循环内，prompt 构造处 | 修改 | 插入 `[【重要约束】本批次可用 ID...]` |
| `pairs = extract_json(response)` 后 | 新增 | 过滤逻辑（valid_pairs 检查） |

---

## 验证方法

修改后运行：
```bash
python dream_association.py
```

观察输出：
- `过滤掉 X 个幻觉 ID 配对` — 说明过滤生效
- 如果批次 1-6 共 58 条记忆，理论上所有有效 ID 都在 `{1..58}` 范围内（假设自增），超出范围的会被过滤

**额外验证**：在写入后查 `/memories` API，确认所有 `related_ids` 中的 ID 都在有效范围内。

---

## 总结

| 方案 | 改动量 | 效果 | 推荐度 |
|------|--------|------|--------|
| A: 解析后过滤 | ~5 行 | 堵住幻觉写入 | ⭐⭐⭐⭐⭐ |
| B: Prompt 约束 | ~3 行 | 减少幻觉生成 | ⭐⭐⭐⭐ |
| C: 两阶段 ID | 大改 | 彻底解决但复杂 | ⭐⭐ |

**实际采用 A+B**，5-8 行代码改动即可解决问题，且不依赖 prompt 工程的不确定性。
