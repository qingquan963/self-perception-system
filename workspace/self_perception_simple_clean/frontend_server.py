#!/usr/bin/env python3
"""前端静态文件服务器 - 修复 Windows 下的 UTF-8 编码"""
import http.server
import socketserver
import sys

PORT = 8090
DIRECTORY = "C:\\Users\\Administrator\\.openclaw\\workspace\\self_perception_simple_clean\\frontend"

# Windows 上强制 UTF-8
if sys.platform == "win32":
    import codecs
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

class UTF8Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # 强制 HTML 输出 UTF-8
        self.send_header("Content-Type", "text/html; charset=utf-8")
        super().end_headers()

    def log_message(self, format, *args):
        pass  # 静默日志

with socketserver.TCPServer(("", PORT), UTF8Handler) as httpd:
    print(f"Frontend serving at http://127.0.0.1:{PORT}")
    httpd.serve_forever()
