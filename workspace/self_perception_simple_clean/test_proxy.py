import sys
print("Python:", sys.version)
import os
print("HTTP_PROXY:", os.environ.get("HTTP_PROXY", "not set"))
print("HTTPS_PROXY:", os.environ.get("HTTPS_PROXY", "not set"))
print("ALL_PROXY:", os.environ.get("ALL_PROXY", "not set"))
print("all_proxy:", os.environ.get("all_proxy", "not set"))

import urllib.request
print("\nProxy handler:", urllib.request.getproxies())

# Try direct connection
import socket
try:
    s = socket.create_connection(("api.minimaxi.com", 443), timeout=5)
    s.close()
    print("\nDirect socket connection: SUCCESS")
except Exception as e:
    print(f"\nDirect socket connection: FAILED - {e}")
