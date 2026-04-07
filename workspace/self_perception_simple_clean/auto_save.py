#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动保存触发器（auto_save.py）
监控 OpenClaw 小龙虾的会话变化，根据触发规则自动将重要内容写入向量记忆库。

触发规则（按优先级）：
  1. compaction 检测 — 会话压缩时保存当前对话摘要（最重要，压缩会丢细节）
  2. 关键词检测 — 用户说出决策性/重要性用语时保存
  3. 定时保存 — 每隔 N 分钟保存一次对话摘要（兜底）
  4. 用户显式指令 — 用户说"记住这个""记下来"时保存

调用方式：
  - 由 api_service.py 的定时轮询调用 check_and_save()
  - 也可独立运行 python auto_save.py --daemon

改动说明（Phase 1 — 方案 B）：
  - 新增 wait_for_md_file_ready() — 等待 .md 文件就绪（≥3秒 + 行数稳定，最长10秒）
  - 新增 read_md_file_safely() — 安全读取 .md 文件（时间检查 + 最多3次重试）
  - 新增 CompactionIdempotencyTracker — 持久化已处理计数，防重复
  - 新增 fallback_to_jsonl() — 容错回退到 jsonl 总结
  - compaction 检测时优先读取 memory-flush 生成的 .md 文件
  - 保持原有 jsonl 回退逻辑，任何问题可回滚
"""

import json
import os
import re
import time
import logging
import threading
import httpx
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ─── 配置 ──────────────────────────────────────────────────────────
_VECTOR_API = "http://127.0.0.1:8007"
_SESSIONS_JSON = Path(os.path.expanduser("~")) / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json"
_OPENCLAW_DIR = Path(os.path.expanduser("~")) / ".openclaw"
_WORKSPACE_DIR = _OPENCLAW_DIR / "workspace"  # 新增

# memory-flush .md 文件目录（方案 B：复用 memory-flush 输出的 .md 总结文件）
_MEMORY_FLUSH_DIR = _WORKSPACE_DIR / "memory"  # 修正

# compaction 检测
_last_compaction_count: int = -1  # 初始化为 -1，第一次读取后才有基准

# 关键词触发规则
DECISION_KEYWORDS = [
    "就用这个方案", "确认用", "就这么定了", "决定用", "选这个",
    "不改了", "最终决定", "敲定", "定了", "go with",
    "就用这个", "按这个来", "按这个方案", "用这个方法",
    "start with this", "let's go with", "we'll use", "confirmed",
    "不改了", "不改", "不改了", "保持", "维持现状",
]

IMPORTANT_KEYWORDS = [
    "重要", "必须", "关键", "核心", "优先", "务必", "切记",
    "千万不要", "绝对不能", "一定注意", "特别说明",
    "important", "critical", "must", "essential", "never", "always",
]

MEMORIZE_KEYWORDS = [
    "记住这个", "记下来", "记住", "帮我记", "备忘", "记一下",
    "别忘了", "提醒我", "mark this", "remember this", "note this",
    "write this down", "don't forget",
]

# 定时保存间隔（秒），默认 30 分钟
TIMER_SAVE_INTERVAL = int(os.getenv("AUTO_SAVE_INTERVAL", 1800))

# 最小内容长度（字符），太短的对话不值得保存
MIN_CONTENT_LENGTH = 20

# 最大内容长度（字符），超过此长度的内容会被截断并提取摘要
# 防止自动保存把整段对话原文（可能上万字符）塞进向量库
MAX_CONTENT_LENGTH = 800

# 防抖：同一条消息不重复保存（按 message id 去重）
_processed_message_ids: set = set()
_max_processed_ids = 5000  # 防止内存无限增长


# ─── 新增功能（方案 B）──────────────────────────────────────────────

def is_file_stable(file_path: Path, min_age_seconds: float = 5.0) -> bool:
    """
    检查文件是否已稳定写入（最后修改时间距今超过指定秒数）
    用于避免读到写入中的文件。
    """
    if not file_path.exists():
        return False
    mtime = os.path.getmtime(file_path)
    age = time.time() - mtime
    return age >= min_age_seconds


def count_lines(file_path: Path) -> int:
    """快速统计文件行数"""
    try:
        with open(file_path, "rb") as f:
            return sum(1 for _ in f)
    except IOError:
        return -1


def wait_for_md_file_ready(
    md_path: Path,
    max_wait: float = 10.0,
    check_interval: float = 0.5
) -> bool:
    """
    等待 .md 文件写入完成。

    策略：
    1. 文件存在
    2. 文件最后修改时间 > 3 秒前（确保写入基本完成）
    3. 连续两次检查行数不变（文件已稳定）

    返回：True 表示文件已就绪，False 表示超时
    """
    start_time = time.time()
    last_line_count = -1
    stable_count = 0

    while time.time() - start_time < max_wait:
        if not md_path.exists():
            time.sleep(check_interval)
            continue

        # 方案 A：时间检查
        if not is_file_stable(md_path, min_age_seconds=3):
            time.sleep(check_interval)
            continue

        # 方案 B：行数稳定性检查
        try:
            current_line_count = count_lines(md_path)
            if current_line_count == last_line_count and current_line_count > 0:
                stable_count += 1
                if stable_count >= 2:  # 连续两次行数不变，认为已稳定
                    logger.info(f"[AutoSave] .md 文件已稳定，行数={current_line_count}")
                    return True
            else:
                stable_count = 0
            last_line_count = current_line_count
        except IOError:
            pass

        time.sleep(check_interval)

    logger.warning(f"[AutoSave] 等待 .md 文件就绪超时 ({max_wait}s)，继续尝试读取")
    return md_path.exists()


def read_md_file_safely(
    md_path: Path,
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> str:
    """
    安全读取 .md 文件：时间检查 + 重试机制。

    策略：
    1. 文件最后修改时间 > 5 秒前才读取（避免读到写入中的文件）
    2. 读取失败则等待重试，最多重试 max_retries 次
    """
    for attempt in range(max_retries):
        # 方案 A：时间检查 - 确保文件已稳定写入
        if not is_file_stable(md_path, min_age_seconds=5):
            wait_time = retry_delay * (attempt + 1)
            logger.info(f"[AutoSave] 文件尚未稳定写入，等待 {wait_time}s (尝试 {attempt + 1}/{max_retries})")
            time.sleep(wait_time)
            continue

        # 方案 C：重试读取
        try:
            content = md_path.read_text(encoding="utf-8")
            # 额外验证：文件不为空，内容长度合理
            if len(content.strip()) > 0:
                return content
            else:
                logger.warning(f"[AutoSave] 文件内容为空 (尝试 {attempt + 1}/{max_retries})")
        except (IOError, OSError) as e:
            logger.warning(f"[AutoSave] 读取失败: {e} (尝试 {attempt + 1}/{max_retries})")

        if attempt < max_retries - 1:
            time.sleep(retry_delay)

    # 所有重试均失败
    raise IOError(f"读取 .md 文件失败，已重试 {max_retries} 次: {md_path}")


def parse_md_summary(content: str) -> dict:
    """
    解析 memory-flush 生成的 .md 文件，提取摘要内容。
    预期格式（简单版）：

    # 压缩总结 [2026-04-03 20:15]

    ## 上下文概要
    - 主题：xxx
    - 关键决策：xxx
    - 待办事项：xxx

    ## 重要信息
    xxx
    """
    lines = content.split("\n")

    # 简单解析：提取关键章节的内容
    summary = {"raw": content}

    # 更健壮的解析应该使用正则或 AST，但这里保持简单
    # 如果格式变化，fallback_to_jsonl 会作为兜底
    if "## 上下文概要" not in content and "# 压缩总结" not in content:
        raise ValueError(f"未知的 .md 格式")

    # 提取上下文概要下的内容
    in_summary_section = False
    summary_parts = []
    for line in lines:
        if "## 上下文概要" in line or "## 重要信息" in line:
            in_summary_section = True
            continue
        if line.startswith("## ") and in_summary_section:
            in_summary_section = False
        if in_summary_section and line.strip():
            summary_parts.append(line.strip())

    if summary_parts:
        summary["text"] = "\n".join(summary_parts)

    return summary


class CompactionIdempotencyTracker:
    """
    记录已处理的 compactionCount，防止服务重启后重复处理。
    持久化到本地文件，重启后可恢复。
    """

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.processed_counts: Set[int] = self._load()

    def _load(self) -> Set[int]:
        """从本地文件加载已处理的 compactionCount"""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                return set(data.get("processed_compaction_counts", []))
            except (json.JSONDecodeError, IOError):
                return set()
        return set()

    def _save(self):
        """持久化到本地文件"""
        data = {"processed_compaction_counts": list(self.processed_counts)}
        self.state_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def is_already_processed(self, compaction_count: int) -> bool:
        """检查是否已处理过此 compaction 事件"""
        return compaction_count in self.processed_counts

    def mark_processed(self, compaction_count: int):
        """标记为已处理"""
        self.processed_counts.add(compaction_count)
        # 保留最近 1000 条，防止文件无限增长
        if len(self.processed_counts) > 1000:
            self.processed_counts = set(sorted(self.processed_counts)[-1000:])
        self._save()


class MDStateManager:
    """
    管理 memory-flush .md 文件相关的状态。
    方案 B：检测 .md 文件就绪情况，读取内容用于向量库写入。
    """

    def __init__(self):
        # 确保 memory-flush 目录存在
        _MEMORY_FLUSH_DIR.mkdir(parents=True, exist_ok=True)

    def get_md_path(self, compaction_count: int) -> Path:
        """获取指定 compaction 的 .md 文件路径"""
        today = datetime.now().strftime("%Y-%m-%d")  # 用日期
        return _MEMORY_FLUSH_DIR / f"{today}.md"

    def md_file_exists(self, compaction_count: int) -> bool:
        """检查 .md 文件是否存在"""
        return self.get_md_path(compaction_count).exists()

    def read_md_content(self, compaction_count: int) -> Optional[str]:
        """
        尝试读取 .md 文件内容。
        返回 None 如果文件不存在或读取失败。
        """
        md_path = self.get_md_path(compaction_count)

        # 等待文件就绪
        if not wait_for_md_file_ready(md_path, max_wait=10.0):
            logger.warning(f"[AutoSave] .md 文件未就绪: {md_path}")
            return None

        # 安全读取
        try:
            content = read_md_file_safely(md_path, max_retries=3, retry_delay=1.0)
            return content
        except IOError as e:
            logger.warning(f"[AutoSave] 读取 .md 文件失败: {e}")
            return None


# ─── 数据结构 ──────────────────────────────────────────────────────
class SaveTrigger:
    """一次保存触发的上下文信息"""
    def __init__(self, trigger_type: str, reason: str, content: str,
                 mem_type: str = "conversation", metadata: dict = None):
        self.trigger_type = trigger_type   # compaction / keyword / timer / memorize
        self.reason = reason               # 人类可读的触发原因
        self.content = content             # 要保存的内容
        self.mem_type = mem_type            # 记忆类型
        self.metadata = metadata or {}

    def __repr__(self):
        return f"<SaveTrigger {self.trigger_type}: {self.reason[:50]}>"


class SessionTracker:
    """
    跟踪单个 OpenClaw 会话的状态，用于检测变化。
    每次调用 check() 时对比上次状态，产生保存触发事件。
    """
    def __init__(self):
        # 会话级状态
        self.session_id: str = ""
        self.jsonl_path: str = ""
        self.last_file_pos: int = 0         # jsonl 文件已读取到的字节位置
        self.last_compaction_count: int = -1
        self.last_save_time: float = 0.0
        self.message_buffer: List[dict] = []  # 最近 N 条消息的缓冲
        self.max_buffer_size = 50           # 最多缓冲 50 条消息
        self._cold_start: bool = True      # 冷启动标记：首次运行只建立基准，不触发保存

        # 统计
        self.total_saves = 0
        self.last_trigger: Optional[SaveTrigger] = None
        self.trigger_history: List[dict] = []  # 最近 20 条触发记录

        # 方案 B：幂等性追踪器和 .md 文件状态管理器
        self.idempotency_tracker = CompactionIdempotencyTracker(
            _OPENCLAW_DIR / "auto_save_compaction_state.json"
        )
        self.md_state_manager = MDStateManager()

    def _get_latest_session(self) -> dict:
        """读取 sessions.json，找到最新活跃会话"""
        if not _SESSIONS_JSON.exists():
            return {}
        try:
            with open(_SESSIONS_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not data:
                return {}
            sessions = list(data.values())
            sessions.sort(key=lambda s: s.get("updatedAt", 0), reverse=True)
            return sessions[0]
        except Exception as e:
            logger.error(f"读取 sessions.json 失败: {e}")
            return {}

    def _parse_jsonl_new_messages(self) -> List[dict]:
        """增量读取 jsonl 文件中新增的消息行"""
        if not self.jsonl_path or not os.path.exists(self.jsonl_path):
            return []

        new_messages = []
        try:
            with open(self.jsonl_path, "r", encoding="utf-8") as f:
                # 定位到上次读取的位置
                f.seek(self.last_file_pos)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("type") == "message":
                            new_messages.append(entry)
                    except json.JSONDecodeError:
                        continue
                # 更新位置
                self.last_file_pos = f.tell()
        except Exception as e:
            logger.error(f"读取 jsonl 失败: {e}")

        return new_messages

    def _extract_text_from_message(self, msg: dict) -> Tuple[str, str]:
        """
        从消息中提取纯文本内容。
        返回 (text, role)
        """
        role = msg.get("message", {}).get("role", "unknown")
        content_list = msg.get("message", {}).get("content", [])
        text_parts = []
        for block in content_list:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        full_text = "\n".join(text_parts).strip()
        return full_text, role

    def _clean_text(self, text: str) -> str:
        """清理文本，移除 QQ 元数据和 system prompt 包裹"""
        # 移除 QQ 元数据块（跨多行）
        text = re.sub(r'Conversation info \(untrusted metadata\):.*?(?=\n\n|\n\S)', '', text, flags=re.DOTALL)
        text = re.sub(r'Sender \(untrusted metadata\):.*?(?=\n\n|\n\S)', '', text, flags=re.DOTALL)
        # 移除 JSON 代码块（```json ... ```）
        text = re.sub(r'```json\s*\{.*?```', '', text, flags=re.DOTALL)
        text = re.sub(r'```\s*\{.*?```', '', text, flags=re.DOTALL)
        # 移除其他代码块
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        # 移除独立的 JSON 行（以 { 开头且包含 message_id）
        text = re.sub(r'^\s*\{[^"]*"message_id".*?\}\s*$', '', text, flags=re.MULTILINE | re.DOTALL)
        # 移除 <final> 标签
        text = re.sub(r'</?final>', '', text)
        # 移除纯 JSON 元数据残留行
        text = re.sub(r'^\s*"[^"]*":\s*"[^"]*"\s*$\n?', '', text, flags=re.MULTILINE)
        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _build_conversation_summary(self, messages: List[dict]) -> str:
        """
        从消息列表构建对话摘要文本。
        格式: 用户: xxx\n助手: xxx
        """
        if not messages:
            return ""
        parts = []
        for msg in messages:
            text, role = self._extract_text_from_message(msg)
            if not text or len(text) < 5:
                continue
            text = self._clean_text(text)
            if len(text) < 3 or self._is_metadata_only(text):
                continue
            label = "用户" if role == "user" else "助手"
            parts.append(f"{label}: {text}")
        return "\n".join(parts)

    def _check_memorize_command(self, text: str) -> bool:
        """检查用户是否显式要求保存"""
        return any(kw in text for kw in MEMORIZE_KEYWORDS)

    def _check_decision_keyword(self, text: str) -> bool:
        """检查是否包含决策关键词"""
        return any(kw in text for kw in DECISION_KEYWORDS)

    def _check_important_keyword(self, text: str) -> bool:
        """检查是否包含重要信息关键词"""
        return any(kw in text.lower() for kw in IMPORTANT_KEYWORDS)

    def _is_metadata_only(self, text: str) -> bool:
        """检查是否是纯元数据/JSON内容，不应该保存"""
        # 纯 JSON 内容
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return True
        if stripped.startswith("[") and stripped.endswith("]"):
            return True
        # Conversation info / Sender info 等 QQ 元数据
        if "Conversation info" in text and "message_id" in text:
            return True
        if "Sender (untrusted metadata)" in text:
            return True
        # 纯链接/URL
        if re.match(r'^https?://\S+$', stripped):
            return True
        # 太短的内容
        if len(stripped) < MIN_CONTENT_LENGTH:
            return True
        return False

    def _process_compaction_md(self, compaction_count: int) -> Optional[str]:
        """
        方案 B：处理 compaction 事件，优先读取 .md 文件。
        返回摘要内容，或 None（需要 fallback）。
        """
        md_content = self.md_state_manager.read_md_content(compaction_count)
        if md_content is None:
            return None

        try:
            parsed = parse_md_summary(md_content)
            if "text" in parsed:
                return parsed["text"]
            return parsed.get("raw", "")
        except Exception as e:
            logger.warning(f"[AutoSave] 解析 .md 内容失败: {e}，尝试 jsonl 回退")
            return None

    def _fallback_to_jsonl(self) -> str:
        """
        回退到原有 jsonl 总结流程。
        保持向后兼容，不丢失数据。
        """
        if not self.message_buffer:
            logger.info("[AutoSave] 缓冲消息为空，无法回退")
            return ""

        jsonl_content = ""
        if self.jsonl_path and os.path.exists(self.jsonl_path):
            try:
                with open(self.jsonl_path, "r", encoding="utf-8") as f:
                    jsonl_content = f.read()
            except Exception as e:
                logger.warning(f"[AutoSave] 读取 jsonl 失败: {e}")

        # 使用缓冲消息生成摘要
        summary = self._build_conversation_summary(self.message_buffer)
        if summary:
            logger.info(f"[AutoSave] 使用 jsonl 回退流程生成摘要，长度={len(summary)}")
        return summary

    def check(self) -> List[SaveTrigger]:
        """
        主检测入口。每次调用时：
        1. 获取最新会话信息
        2. 读取新增消息
        3. 检查各种触发条件
        4. 返回触发的保存事件列表
        """
        triggers = []

        # 1. 获取最新会话
        session = self._get_latest_session()
        if not session:
            return triggers

        session_id = session.get("sessionId", "")
        compaction_count = session.get("compactionCount", 0) or 0
        jsonl_path = session.get("sessionFile", "")

        # 会话切换时重置
        if session_id != self.session_id:
            if self.session_id:
                logger.info(f"会话切换: {self.session_id[:8]}... -> {session_id[:8]}...")
                # 如果有缓冲消息，保存旧会话摘要
                if len(self.message_buffer) >= 2:
                    summary = self._build_conversation_summary(self.message_buffer[-20:])
                    if len(summary) >= MIN_CONTENT_LENGTH:
                        triggers.append(SaveTrigger(
                            trigger_type="topic_switch",
                            reason=f"会话切换，保存旧会话对话摘要",
                            content=summary,
                            mem_type="conversation",
                            metadata={"source": "auto_topic_switch", "session_id": self.session_id[:8]}
                        ))
            self.session_id = session_id
            self.jsonl_path = jsonl_path
            self.last_file_pos = 0
            self.message_buffer = []

        # 2. compaction 检测（方案 B：优先读取 .md 文件）
        if self.last_compaction_count >= 0 and compaction_count > self.last_compaction_count:
            diff = compaction_count - self.last_compaction_count
            logger.warning(f"[AutoSave] 检测到 compaction: {self.last_compaction_count} -> {compaction_count} (+{diff})")

            # 遍历处理每个新 compaction 事件（防止跳变）
            for comp_cnt in range(self.last_compaction_count + 1, compaction_count + 1):
                # 幂等性检查
                if self.idempotency_tracker.is_already_processed(comp_cnt):
                    logger.info(f"[AutoSave] compactionCount={comp_cnt} 已处理，跳过")
                    continue

                # 方案 B：优先读取 .md 文件
                summary = self._process_compaction_md(comp_cnt)

                # 如果 .md 文件不存在或读取失败，回退到 jsonl
                if summary is None or len(summary) < MIN_CONTENT_LENGTH:
                    logger.info(f"[AutoSave] .md 文件不可用或内容不足，尝试 jsonl 回退")
                    summary = self._fallback_to_jsonl()

                if len(summary) >= MIN_CONTENT_LENGTH:
                    triggers.append(SaveTrigger(
                        trigger_type="compaction",
                        reason=f"会话压缩前自动保存（第 {comp_cnt} 次压缩）",
                        content=summary,
                        mem_type="conversation",
                        metadata={"source": "auto_compaction", "compaction_count": comp_cnt}
                    ))
                    # 标记为已处理
                    self.idempotency_tracker.mark_processed(comp_cnt)
                    logger.info(f"[AutoSave] compactionCount={comp_cnt} 处理完成")
                else:
                    logger.warning(f"[AutoSave] compactionCount={comp_cnt} 摘要内容不足，跳过")

            # 压缩后清空缓冲，避免重复保存
            self.message_buffer = self.message_buffer[-5:]

        self.last_compaction_count = compaction_count

        # 3. 读取新增消息
        new_msgs = []
        if jsonl_path and os.path.exists(jsonl_path):
            new_msgs = self._parse_jsonl_new_messages()
            for msg in new_msgs:
                msg_id = msg.get("id", "")
                # 去重
                if msg_id in _processed_message_ids:
                    continue
                _processed_message_ids.add(msg_id)
                # 防止内存膨胀
                if len(_processed_message_ids) > _max_processed_ids:
                    # 移除最早的一半
                    to_remove = list(_processed_message_ids)[:_max_processed_ids // 2]
                    for mid in to_remove:
                        _processed_message_ids.discard(mid)

                text, role = self._extract_text_from_message(msg)
                text = self._clean_text(text)
                if not text or len(text) < 5:
                    self.message_buffer.append(msg)
                    continue

                # 过滤纯 JSON/元数据内容（不应该保存的垃圾数据）
                if self._is_metadata_only(text):
                    self.message_buffer.append(msg)
                    continue

                # 加入缓冲
                self.message_buffer.append(msg)
                if len(self.message_buffer) > self.max_buffer_size:
                    self.message_buffer = self.message_buffer[-self.max_buffer_size:]

                # 冷启动期间：只缓冲不触发
                if self._cold_start:
                    continue

                # 只检查用户消息
                if role != "user":
                    continue

                # 3a. 用户显式指令（最高优先级关键词触发）
                if self._check_memorize_command(text):
                    triggers.append(SaveTrigger(
                        trigger_type="memorize",
                        reason="用户显式要求保存",
                        content=text,
                        mem_type="conversation",
                        metadata={"source": "user_command", "keyword_matched": "memorize"}
                    ))

                # 3b. 决策关键词
                elif self._check_decision_keyword(text):
                    # 附带上文（最近的助手回复）
                    context_parts = []
                    for prev_msg in reversed(self.message_buffer[:-1]):
                        if len(context_parts) >= 2:
                            break
                        prev_text, prev_role = self._extract_text_from_message(prev_msg)
                        prev_text = self._clean_text(prev_text)
                        if prev_text:
                            label = "用户" if prev_role == "user" else "助手"
                            context_parts.insert(0, f"{label}: {prev_text[:300]}")
                    context_text = "\n".join(context_parts) if context_parts else ""
                    full_content = f"[决策记录]\n{context_text}\n---\n用户决策: {text}" if context_text else f"[决策记录] {text}"
                    triggers.append(SaveTrigger(
                        trigger_type="keyword_decision",
                        reason=f"检测到决策关键词: {[kw for kw in DECISION_KEYWORDS if kw in text][:2]}",
                        content=full_content,
                        mem_type="lesson",  # 决策归为经验教训类
                        metadata={"source": "auto_decision_keyword", "keyword_matched": "decision"}
                    ))

                # 3c. 重要信息关键词
                elif self._check_important_keyword(text):
                    triggers.append(SaveTrigger(
                        trigger_type="keyword_important",
                        reason=f"检测到重要信息关键词: {[kw for kw in IMPORTANT_KEYWORDS if kw in text.lower()][:2]}",
                        content=text,
                        mem_type="knowledge",
                        metadata={"source": "auto_important_keyword", "keyword_matched": "important"}
                    ))

        # 冷启动完成标记（第一次扫描完所有历史消息后）
        if self._cold_start and not new_msgs:
            self._cold_start = False
            logger.info("[AutoSave] 冷启动完成，开始正常监控")

        # 4. 定时保存检查
        now = time.time()
        if (now - self.last_save_time >= TIMER_SAVE_INTERVAL
                and len(self.message_buffer) >= 2
                and not self._cold_start):
            summary = self._build_conversation_summary(self.message_buffer[-20:])
            if len(summary) >= MIN_CONTENT_LENGTH:
                triggers.append(SaveTrigger(
                    trigger_type="timer",
                    reason=f"定时保存（间隔 {TIMER_SAVE_INTERVAL // 60} 分钟）",
                    content=summary,
                    mem_type="conversation",
                    metadata={"source": "auto_timer", "interval_min": TIMER_SAVE_INTERVAL // 60}
                ))
                self.last_save_time = now
                # 保存后缩短缓冲
                self.message_buffer = self.message_buffer[-5:]

        # 记录最后触发
        for t in triggers:
            self.total_saves += 1
            self.last_trigger = t
            self.trigger_history.append({
                "type": t.trigger_type,
                "reason": t.reason,
                "time": datetime.now().isoformat(),
                "content_preview": t.content[:100],
            })
            if len(self.trigger_history) > 20:
                self.trigger_history = self.trigger_history[-20:]

        return triggers


async def save_trigger(trigger: SaveTrigger) -> dict:
    """
    将一个 SaveTrigger 写入向量记忆库。
    返回 API 响应。
    """
    # 内容长度限制：超过 MAX_CONTENT_LENGTH 的截断，保留首尾
    content = trigger.content
    if len(content) > MAX_CONTENT_LENGTH:
        # 保留开头和结尾，中间用省略号，优先保留关键信息
        head = content[:MAX_CONTENT_LENGTH // 2]
        tail = content[-MAX_CONTENT_LENGTH // 4:]
        content = f"{head}\n...[已截断，原文 {len(trigger.content)} 字符]...\n{tail}"
        logger.info(f"[AutoSave] 内容过长 ({len(trigger.content)} 字符)，已截断至 {len(content)} 字符")

    payload = {
        "content": content,
        "type": trigger.mem_type,
        "source": trigger.metadata.get("source", "auto_save"),
        "metadata": {
            **trigger.metadata,
            "auto_save": True,
            "trigger_type": trigger.trigger_type,
            "trigger_reason": trigger.reason,
            "saved_at": datetime.now().isoformat(),
        },
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{_VECTOR_API}/memories/add",
                json=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            if resp.status_code == 200:
                result = resp.json()
                logger.info(
                    f"[AutoSave] 保存成功: type={trigger.trigger_type}, "
                    f"status={result.get('status')}, id={result.get('id')}"
                )
                return result
            else:
                logger.error(f"[AutoSave] 保存失败: {resp.status_code} {resp.text[:200]}")
                return {"status": "error", "error": resp.text[:200]}
    except Exception as e:
        logger.error(f"[AutoSave] 保存请求异常: {e}")
        return {"status": "error", "error": str(e)}


# ─── 全局单例 ──────────────────────────────────────────────────────
_tracker: Optional[SessionTracker] = None


def get_tracker() -> SessionTracker:
    global _tracker
    if _tracker is None:
        _tracker = SessionTracker()
    return _tracker


async def check_and_save() -> List[dict]:
    """
    对外接口：检查触发条件，执行保存，返回保存结果列表。
    由 api_service.py 的定时轮询调用。
    """
    tracker = get_tracker()
    triggers = tracker.check()

    results = []
    for trigger in triggers:
        result = await save_trigger(trigger)
        results.append({
            "trigger_type": trigger.trigger_type,
            "reason": trigger.reason,
            "content_preview": trigger.content[:100],
            "mem_type": trigger.mem_type,
            "save_result": result,
        })

    return results


def get_tracker_status() -> dict:
    """获取当前 tracker 状态（供 API 端点查询）"""
    tracker = get_tracker()
    return {
        "enabled": _context_state.get("auto_save_enabled", True),
        "session_id": tracker.session_id[:16] if tracker.session_id else "none",
        "last_compaction_count": tracker.last_compaction_count,
        "message_buffer_size": len(tracker.message_buffer),
        "total_saves": tracker.total_saves,
        "last_save_time": tracker.last_save_time,
        "timer_interval_min": TIMER_SAVE_INTERVAL // 60,
        "last_trigger": {
            "type": tracker.last_trigger.trigger_type,
            "reason": tracker.last_trigger.reason,
            "time": datetime.now().isoformat(),
        } if tracker.last_trigger else None,
        "recent_triggers": tracker.trigger_history[-5:],
        "idempotency_processed_counts": list(tracker.idempotency_tracker.processed_counts)[-10:],
        "timestamp": datetime.now().isoformat(),
    }


# 复用 api_service 的状态字典（初始化时由 api_service 注入）
_context_state: dict = {}


def set_context_state(state: dict):
    """由 api_service 在启动时注入状态字典"""
    global _context_state
    _context_state = state


# ─── 独立运行模式 ──────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    )

    async def daemon_loop():
        logger.info(f"自动保存守护进程启动，检查间隔 60 秒")
        while True:
            try:
                results = await check_and_save()
                if results:
                    for r in results:
                        logger.info(f"触发保存: {r['trigger_type']} - {r['reason']}")
            except Exception as e:
                logger.error(f"检查循环异常: {e}")
            await asyncio.sleep(60)  # 每 60 秒检查一次

    print("=== 自动保存触发器（独立模式）===")
    print(f"检查间隔: 60 秒")
    print(f"定时保存: 每 {TIMER_SAVE_INTERVAL // 60} 分钟")
    print(f"向量服务: {_VECTOR_API}")
    print(f"memory-flush 目录: {_MEMORY_FLUSH_DIR}")
