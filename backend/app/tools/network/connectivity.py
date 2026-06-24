import socket
import time
from typing import Any, Dict


def check_network() -> Dict[str, Any]:
    """检查网络连通性 — 小欧 2026-06-24 从3个文件中提取公共函数"""
    test_hosts = [("dns.google", 53), ("8.8.8.8", 53), ("1.1.1.1", 53)]
    for host, port in test_hosts:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            t1 = time.time()
            sock.connect((host, port))
            latency = (time.time() - t1) * 1000
            return {"connected": True, "host": host, "latency_ms": round(latency, 2)}
        except (socket.timeout, socket.error, OSError):
            pass
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
    return {"connected": False}
