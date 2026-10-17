import ipaddress
import socket
from urllib.parse import urlsplit


def validate_url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('请填写公开网页的 HTTP 或 HTTPS 地址')
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme=='https' else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('网站获取入口只接收公开互联网地址')
    return value
