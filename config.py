"""
traficman configuration and endpoints.
Zero emojis - clean ASCII only.
"""

import subprocess

# Global fast CDN download mirrors
CDN_ENDPOINTS = {
    "google": {
        "name": "Google Edge CDN",
        "url": "https://dl.google.com/android/repository/platform-tools_r35.0.0-linux.zip",
        "host": "dl.google.com"
    },
    "cloudflare": {
        "name": "Cloudflare Speed CDN",
        "url": "https://speed.cloudflare.com/__down?bytes=50000000",
        "host": "speed.cloudflare.com"
    },
    "kernel": {
        "name": "Kernel Fastly CDN",
        "url": "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.1.tar.xz",
        "host": "cdn.kernel.org"
    },
    "alpine": {
        "name": "Alpine Fastly CDN",
        "url": "https://dl-cdn.alpinelinux.org/alpine/v3.20/main/x86_64/APKINDEX.tar.gz",
        "host": "dl-cdn.alpinelinux.org"
    },
    "ovh": {
        "name": "OVH Telecom CDN",
        "url": "https://proof.ovh.net/files/100Mb.dat",
        "host": "proof.ovh.net"
    }
}

DEFAULT_UPLOAD_URL = "https://speed.cloudflare.com/__up"
USER_AGENT = "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"

def get_network_info():
    """Detect mobile cellular network type using Android getprop."""
    try:
        res = subprocess.run(
            ["getprop", "gsm.network.type"],
            capture_output=True,
            text=True,
            timeout=1
        )
        if res.returncode == 0 and res.stdout.strip():
            raw = res.stdout.strip().split(",")[0].strip()
            if "NR" in raw:
                return f"5G ({raw})"
            elif "LTE" in raw:
                return f"4G/LTE ({raw})"
            elif "HSPA" in raw or "UMTS" in raw:
                return f"3G ({raw})"
            return raw
    except Exception:
        pass
    return "Cellular / Mobile Network"
