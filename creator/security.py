import ipaddress


def get_client_ip(request):
    """Use forwarded IP only when the TCP peer is the loopback reverse proxy."""
    remote_addr = request.META.get("REMOTE_ADDR", "")
    try:
        remote_ip = ipaddress.ip_address(remote_addr)
    except ValueError:
        return remote_addr or None

    if not remote_ip.is_loopback:
        return str(remote_ip)

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "").strip()
    if forwarded_for:
        try:
            # Caddy's default reverse_proxy emits one sanitized client address.
            if "," not in forwarded_for:
                return str(ipaddress.ip_address(forwarded_for))
        except ValueError:
            pass

    return str(remote_ip)
