import ipaddress
import re
import socket
import struct
from typing import Any, Dict
from urllib.parse import urlparse


def _is_private_or_loopback_ip(hostname: str) -> bool:
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        pass

    if re.match(r'^0x[0-9a-f]+$', hostname, re.IGNORECASE):
        try:
            ip_str = socket.inet_ntoa(struct.pack('!I', int(hostname, 16)))
            ip = ipaddress.ip_address(ip_str)
            return ip.is_private or ip.is_loopback or ip.is_reserved
        except (ValueError, OSError, struct.error):
            return False

    if re.match(r'^\d{7,10}$', hostname):
        try:
            ip_str = socket.inet_ntoa(struct.pack('!I', int(hostname)))
            ip = ipaddress.ip_address(ip_str)
            return ip.is_private or ip.is_loopback or ip.is_reserved
        except (ValueError, OSError, struct.error):
            return False

    octal_pattern = re.match(r'^(\d{1,4})\.(\d{1,4})\.(\d{1,4})\.(\d{1,4})$', hostname)
    if octal_pattern:
        try:
            raw_parts = octal_pattern.groups()
            has_octal = any(len(p) > 1 and p.startswith("0") for p in raw_parts)
            if has_octal:
                parts = [int(p, 8) if len(p) > 1 and p.startswith("0") else int(p) for p in raw_parts]
            else:
                parts = [int(p) for p in raw_parts]
            if all(0 <= p <= 255 for p in parts):
                ip_str = f"{parts[0]}.{parts[1]}.{parts[2]}.{parts[3]}"
                ip = ipaddress.ip_address(ip_str)
                return ip.is_private or ip.is_loopback or ip.is_reserved
        except (ValueError, OverflowError):
            return False

    if re.match(r'^\d+\.\d+$', hostname):
        try:
            parts = hostname.split('.')
            ip = ipaddress.ip_address(f"{parts[0]}.0.0.{parts[1]}")
            return ip.is_private or ip.is_loopback
        except ValueError:
            return False

    if hostname == "0":
        return True

    return False


def validate_url(url: str) -> Dict[str, Any]:
    """统一URL验证和SSRF检查 — 小欧 2026-06-24 从3个文件中提取+增强"""
    try:
        parsed = urlparse(url)
        is_valid = bool(parsed.scheme) and bool(parsed.netloc)
        valid_schemes = {"http", "https"}
        scheme_ok = parsed.scheme.lower() in valid_schemes
        if not (is_valid and scheme_ok):
            return {"valid": False, "scheme": parsed.scheme, "netloc": parsed.netloc, "path": parsed.path}

        hostname = parsed.hostname or ""

        if _is_private_or_loopback_ip(hostname):
            return {"valid": False, "error": f"SSRF拦截: 禁止访问内网地址 {hostname}"}

        blocked_domains = {"localhost", "metadata.google.internal", "metadata.internal",
                           "169.254.169.254", "0.0.0.0", "0", "::1", "[::1]"}
        if hostname.lower() in blocked_domains:
            return {"valid": False, "error": f"SSRF拦截: 禁止访问内网地址 {hostname}"}

        return {"valid": True, "scheme": parsed.scheme, "netloc": parsed.netloc, "path": parsed.path}
    except Exception as e:
        return {"valid": False, "error": str(e)}
