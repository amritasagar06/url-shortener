import socket
from urllib.parse import urlparse
import ipaddress
from fastapi import HTTPException, status
from app.config import settings

def is_safe_url(url: str) -> bool:
    """
    Task T5-5: Security URL safety check validator preventing SSRF vulnerabilities.
    Blocks non-web schemes, loopback networks, private IP space ranges, 
    and explicit domain blocklists.
    """
    try:
        parsed_url = urlparse(url)
        
        # 1. Enforce Web Schema Protocols
        if parsed_url.scheme not in ("http", "https"):
            return False
            
        # 2. Extract Hostname details
        hostname = parsed_url.hostname
        if not hostname:
            return False
            
        # 3. Check Domain Blocklist
        if hostname.lower() in settings.BLOCKED_DOMAINS:
            return False

        # 4. Prevent SSRF by checking IP addresses
        try:
            # Resolve Hostname to live IP addresses
            ip_addresses = socket.getaddrinfo(hostname, None)
            for addr in ip_addresses:
                ip_str = addr[4][0]
                ip_obj = ipaddress.ip_address(ip_str)
                
                # Block Private ranges, local loopbacks, linkage-local, and multicast
                if (
                    ip_obj.is_private or 
                    ip_obj.is_loopback or 
                    ip_obj.is_link_local or 
                    ip_obj.is_multicast or
                    ip_str.startswith("0.")
                ):
                    return False
        except socket.gaierror:
            # If DNS resolution fails, reject to be safe
            return False
            
        return True
        
    except Exception:
        return False

def validate_custom_code(code: str) -> str:
    """Ensure custom codes do not contain script elements or invalid characters."""
    cleaned = code.strip()
    if not cleaned.isalnum():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Custom short-code alias must contain only letters and numbers."
        )
    if len(cleaned) > 12:
         raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Custom short-code alias cannot exceed 12 characters."
        )
    return cleaned