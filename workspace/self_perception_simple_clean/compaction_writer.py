#!/usr/bin/env python3
"""
Compaction Writer Service
监控 session compaction 摘要，自动写入向量库（type=conversation）
同时提供 /health HTTP 端点供 supervisor 监控
"""
import subprocess
import threading
import time
import sys
import logging
import json
import os
import traceback
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib import request as urllib2
from urllib.error import URLError

# ─── 配置 ────────────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).parent.resolve()
LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

VECTOR_API = os.getenv("VECTOR_API_URL", "http://127.0.0.1:8007/memories/add")
# 跨平台 session 目录：支持 Linux/Mac/Windows
_default_sessions = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
SESSION_JSONL_DIR = Path(os.getenv("SESSION_JSONL_DIR", str(_default_sessions)))
STATE_FILE = LOG_DIR / "processed_compaction_ids.json"
LOG_FILE = LOG_DIR / "compaction_writer.log"
HEALTH_FILE = LOG_DIR / "compaction_writer_heartbeat.txt"

HEALTH_PORT = 8014
POLL_INTERVAL_SEC = 3
MAX_RETRIES = 3
RETRY_DELAY_MS = 1000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("compaction_writer")

# ─── 状态 ────────────────────────────────────────────────────────────
class WriterState:
    def __init__(self):
        self.processed_ids: set = set()
        self.last_write_time = None
        self.total_written = 0
        self.running = True
        self._load()

    def _load(self):
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    self.processed_ids = set(json.load(f))
                logger.info(f"Loaded {len(self.processed_ids)} processed IDs")
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")

    def save(self):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(list(self.processed_ids), f)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def mark_written(self, comp_id: str):
        self.processed_ids.add(comp_id)
        self.total_written += 1
        self.last_write_time = time.time()


state = WriterState()

# ─── 核心写入逻辑 ────────────────────────────────────────────────────
def write_to_vector(comp_data: dict) -> bool:
    payload = {
        "content": comp_data.get("summary", ""),
        "type": "conversation",
        "source": "compaction",
        "metadata": {
            "session_id": comp_data.get("session_id", ""),
            "compaction_id": comp_data.get("id", ""),
            "timestamp": comp_data.get("timestamp", ""),
            "model": comp_data.get("model", ""),
        }
    }
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib2.Request(
                VECTOR_API,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib2.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    logger.info(f"Wrote compaction {payload['metadata']['compaction_id']} to vector DB")
                    return True
        except URLError as e:
            logger.warning(f"Attempt {attempt+1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_MS / 1000)
    return False


def scan_and_write():
    """扫描所有 session jsonl 文件，检测新的 compaction 条目"""
    try:
        jsonl_files = list(SESSION_JSONL_DIR.glob("*.jsonl"))
    except Exception as e:
        logger.warning(f"Failed to scan sessions dir: {e}")
        return

    for jsonl_file in jsonl_files:
        try:
            with open(jsonl_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # 检测 compaction 行
                    if entry.get("role") == "system" and "compaction" in entry.get("content", "").lower():
                        comp_id = entry.get("id") or entry.get("session_id", "")
                        if comp_id and comp_id not in state.processed_ids:
                            summary = entry.get("content", "")
                            comp_data = {
                                "id": comp_id,
                                "session_id": entry.get("session_id", jsonl_file.stem),
                                "summary": summary,
                                "timestamp": entry.get("timestamp", ""),
                                "model": entry.get("model", ""),
                            }
                            if write_to_vector(comp_data):
                                state.mark_written(comp_id)
                                state.save()
        except Exception as e:
            logger.error(f"Error scanning {jsonl_file.name}: {e}")
            traceback.print_exc()


def heartbeat():
    """写心跳文件供外部监控"""
    HEALTH_FILE.write_text(str(int(state.last_write_time or 0)), encoding="utf-8")


def background_loop():
    """后台轮询线程"""
    logger.info(f"Compaction writer started, polling every {POLL_INTERVAL_SEC}s")
    while state.running:
        try:
            scan_and_write()
            heartbeat()
        except Exception as e:
            logger.error(f"Background loop error: {e}")
        time.sleep(POLL_INTERVAL_SEC)


# ─── 健康检查 HTTP 服务 ──────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    
    def do_GET(self):
        if self.path in ("/health", "/"):
            # 检查进程是否在跑（通过心跳文件）
            last_write = 0
            if HEALTH_FILE.exists():
                try:
                    last_write = int(HEALTH_FILE.read_text(encoding="utf-8").strip())
                except:
                    pass
            
            alive = state.running and (time.time() - last_write < 300) if last_write else state.running
            
            self.send_response(200 if alive else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            response = {
                "status": "healthy" if alive else "stopped",
                "total_written": state.total_written,
                "last_write": state.last_write_time,
            }
            self.wfile.write(json.dumps(response).encode("utf-8"))
        else:
            self.send_response(404)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # 安静日志


def run_health_server():
    server = HTTPServer(("127.0.0.1", HEALTH_PORT), HealthHandler)
    logger.info(f"Health server listening on port {HEALTH_PORT}")
    server.serve_forever()


def main():
    logger.info("=" * 40)
    logger.info("Compaction Writer Service starting...")
    logger.info(f"Vector API: {VECTOR_API}")
    logger.info(f"Sessions dir: {SESSION_JSONL_DIR}")
    logger.info("=" * 40)

    # 启动后台轮询线程
    poll_thread = threading.Thread(target=background_loop, daemon=True)
    poll_thread.start()

    # 启动健康检查 HTTP 服务（独立线程，避免主线程阻塞导致进程退出）
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    health_thread.join()  # 主线程在这里等待


if __name__ == "__main__":
    main()
