# validate/url_validator.py — URL业务级安全检查（集中管理）
# 小沈 2026-06-27 — 从 tools/network/url_validator.py 迁移+重构

import ipaddress
import re
import socket
import struct
from typing import Optional, Tuple
from urllib.parse import urlparse

# 协议白名单：仅允许安全的协议
ALLOWED_PROTOCOLS = {"https"}

# 内网IP段（用于DNS解析后检查）
# 注意：仅覆盖IPv4内网段。IPv6内网（fd00::/8）暂未覆盖
PRIVATE_IP_PREFIXES = (
    "10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
    "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
    "172.30.", "172.31.", "192.168.",
)

LOOPBACK = ("127.", "0.", "::1", "localhost")


def _is_private_or_loopback_ip(hostname: str) -> bool:
    """全面IP地址检测（含hex/octal/小数等SSRF绕过手法）— 小欧 2026-06-24"""
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


def validate_url(url: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    URL业务级安全检查（适用于httpget、download、fetchpage）
    
    检查内容：
    1. URL格式是否合法
    2. 协议是否在白名单内（仅允许https）
    3. 主机名是否为内网/回环地址（SSRF防护，含hex/octal绕过检测）
    4. 是否为裸IP+端口（SSRF绕过常见手法）
    
    Returns: (is_valid, error_msg, warning_msg)
    """
    if not url or not isinstance(url, str):
        return False, "URL不能为空", None
    
    try:
        parsed = urlparse(url)
    except Exception:
        return False, f"URL格式解析失败: {url}", None
    
    if parsed.scheme not in ALLOWED_PROTOCOLS:
        return False, f"不允许的协议: {parsed.scheme}（仅允许https）", None
    
    hostname = parsed.hostname
    if not hostname:
        return False, f"URL缺少主机名: {url}", None
    
    host_lower = hostname.lower()
    if host_lower in LOOPBACK or host_lower.startswith(LOOPBACK):
        return False, f"不允许访问回环地址: {hostname}", None
    
    if _is_private_or_loopback_ip(hostname):
        return False, f"不允许访问内网地址: {hostname}", None
    
    # DNS二次校验（防DNS rebinding）
    try:
        addrs = socket.getaddrinfo(hostname, None)
        for addr in addrs:
            ip = addr[4][0]
            if _is_private_or_loopback_ip(ip):
                return False, f"DNS解析到内网地址: {ip}", None
    except OSError:
        return False, f"DNS解析失败: {hostname}", None

    # 裸IP检查（SSRF绕过常见手法）
    if _is_literal_ip(host_lower):
        return True, None, f"目标为IP地址而非域名，请确认"
    
    return True, None, None


def validate_proxy(proxy: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    proxy地址安全检查（适用于所有HTTP类工具）
    
    Returns: (is_valid, error_msg, warning_msg)
    """
    if not proxy:
        return True, None, None
    
    try:
        parsed = urlparse(proxy)
    except Exception:
        return False, f"proxy地址格式解析失败: {proxy}", None
    
    hostname = parsed.hostname
    if not hostname:
        return False, f"proxy地址缺少主机名: {proxy}", None
    
    host_lower = hostname.lower()
    if host_lower in LOOPBACK or host_lower.startswith(LOOPBACK):
        return False, f"不允许使用localhost作为proxy", None
    
    if _is_private_or_loopback_ip(hostname):
        return False, f"不允许使用内网地址作为proxy", None
    
    return True, None, None



def _is_literal_ip(hostname: str) -> bool:
    """检查主机名是否为IP地址（而非域名）"""
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', hostname):
        return True
    if ':' in hostname:
        return True
    return False
