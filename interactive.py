"""
Interactive CLI Wizard for traficman.
Asks step-by-step setup questions with clean ASCII menus and zero emojis.
"""

import sys
from .config import CDN_ENDPOINTS

def prompt_choice(prompt_text, options, default_idx=1):
    print(f"\n{prompt_text}")
    for idx, opt in enumerate(options, 1):
        marker = "[*]" if idx == default_idx else "   "
        print(f" {marker} [{idx}] {opt}")
    
    while True:
        try:
            val = input(f"Select option (1-{len(options)}) [default: {default_idx}]: ").strip()
            if not val:
                return default_idx
            idx = int(val)
            if 1 <= idx <= len(options):
                return idx
            print(f"[-] Invalid selection. Enter a number between 1 and {len(options)}.")
        except (ValueError, EOFError):
            return default_idx

def prompt_number(prompt_text, default_val, unit=""):
    unit_str = f" ({unit})" if unit else ""
    while True:
        try:
            val = input(f"{prompt_text}{unit_str} [default: {default_val}]: ").strip()
            if not val:
                return default_val
            return float(val)
        except (ValueError, EOFError):
            print("[-] Please enter a valid numerical value.")

def run_interactive_wizard():
    print("\n" + "=" * 62)
    print(" TRAFICMAN - INTERACTIVE CONFIGURATION WIZARD")
    print(" Configure traffic generation parameters step-by-step.")
    print(" Press Enter on any prompt to accept default recommendation.")
    print("=" * 62)

    # 1. Traffic Mode
    mode_options = [
        "Download - High Throughput In-Memory Stream",
        "Upload   - High Throughput POST Stream",
        "Duplex   - Simultaneous Download and Upload",
        "Burst    - High Traffic Waves (Spikes & Pauses for Alarm Testing)",
        "Multi    - Multi-Website Round-Robin Rotation",
        "Local    - Zero Mobile Data (LAN / Wi-Fi Test Server)"
    ]
    mode_idx = prompt_choice("Step 1: Select Traffic Mode", mode_options, default_idx=1)
    mode_map = {1: "download", 2: "upload", 3: "duplex", 4: "burst", 5: "multi", 6: "local-server"}
    selected_mode = mode_map[mode_idx]

    if selected_mode == "local-server":
        port = int(prompt_number("Enter local server port", 9999))
        return {
            "mode": "local-server",
            "port": port,
            "threads": 4,
            "limit": 0,
            "duration": 0,
            "speed": 0,
            "cdn_target": "local",
            "log_mode": "verbose"
        }

    # 2. Target Speed / Intensity
    speed_options = [
        "Maximum Unthrottled (Line-Rate Saturation)",
        "Ultra High (100 Mbps)",
        "High (50 Mbps)",
        "Medium (20 Mbps)",
        "Low (5 Mbps)",
        "Custom Speed (Specify exact target Mbps)"
    ]
    speed_idx = prompt_choice("Step 2: Select Traffic Speed / Intensity", speed_options, default_idx=1)
    if speed_idx == 1:
        speed_bps = 0
    elif speed_idx == 2:
        speed_bps = 100_000_000
    elif speed_idx == 3:
        speed_bps = 50_000_000
    elif speed_idx == 4:
        speed_bps = 20_000_000
    elif speed_idx == 5:
        speed_bps = 5_000_000
    else:
        custom_mbps = prompt_number("Enter target speed in Mbps", 25.0, "Mbps")
        speed_bps = custom_mbps * 1_000_000

    # 3. Data Safety Limit
    limit_options = [
        "50 MB   (Quick check)",
        "100 MB  (Recommended safe test)",
        "250 MB  (Standard test)",
        "500 MB  (Heavy test)",
        "1 GB    (Extended test)",
        "Unlimited (No quota cap - Caution on mobile data)"
    ]
    limit_idx = prompt_choice("Step 3: Select Mobile Data Safety Limit", limit_options, default_idx=2)
    limit_map = {
        1: 50 * 1024 * 1024,
        2: 100 * 1024 * 1024,
        3: 250 * 1024 * 1024,
        4: 500 * 1024 * 1024,
        5: 1024 * 1024 * 1024,
        6: 0
    }
    data_limit = limit_map[limit_idx]

    # 4. Duration
    dur_options = [
        "15 seconds (Quick verification)",
        "30 seconds (Recommended standard)",
        "60 seconds (Full 1-minute benchmark)",
        "Continuous (Runs until limit reached or Ctrl+C)"
    ]
    dur_idx = prompt_choice("Step 4: Select Test Duration", dur_options, default_idx=2)
    dur_map = {1: 15, 2: 30, 3: 60, 4: 0}
    duration = dur_map[dur_idx]

    # 5. Target Website / CDN
    cdn_options = [
        "Multi-CDN Round-Robin (Google + Cloudflare + Kernel + Alpine + OVH)",
        "Google Edge CDN (dl.google.com)",
        "Cloudflare Speed CDN (speed.cloudflare.com)",
        "Kernel Fastly CDN (cdn.kernel.org)",
        "Alpine Linux CDN (dl-cdn.alpinelinux.org)",
        "OVH Telecom CDN (proof.ovh.net)",
        "Custom URL Endpoint"
    ]
    cdn_idx = prompt_choice("Step 5: Select Target Website / CDN", cdn_options, default_idx=1)
    custom_url = None
    if cdn_idx == 1:
        cdn_target = "all"
    elif cdn_idx == 2:
        cdn_target = "google"
    elif cdn_idx == 3:
        cdn_target = "cloudflare"
    elif cdn_idx == 4:
        cdn_target = "kernel"
    elif cdn_idx == 5:
        cdn_target = "alpine"
    elif cdn_idx == 6:
        cdn_target = "ovh"
    else:
        cdn_target = "custom"
        custom_url = input("Enter custom download URL: ").strip()

    # 6. Logging Mode
    log_options = [
        "Detailed Event Logs (Shows real-time connections, chunks, and latency)",
        "Compact Dashboard (Live progress bar and rate meter)",
        "Hybrid (Dashboard with periodic status logs)"
    ]
    log_idx = prompt_choice("Step 6: Select Real-Time Log Mode", log_options, default_idx=1)
    log_map = {1: "verbose", 2: "dashboard", 3: "hybrid"}
    log_mode = log_map[log_idx]

    # Burst timings if burst mode selected
    burst_on = 8.0
    burst_off = 4.0
    if selected_mode == "burst":
        burst_on = prompt_number("Seconds of heavy traffic per burst cycle", 6.0, "s")
        burst_off = prompt_number("Seconds of idle pause between bursts", 3.0, "s")

    # Thread concurrency
    threads = int(prompt_number("Number of concurrent parallel streams (1-16)", 4))
    threads = max(1, min(16, threads))

    return {
        "mode": selected_mode,
        "speed": speed_bps,
        "limit": data_limit,
        "duration": duration,
        "cdn_target": cdn_target,
        "custom_url": custom_url,
        "log_mode": log_mode,
        "burst_on": burst_on,
        "burst_off": burst_off,
        "threads": threads,
        "port": 9999,
        "host": "127.0.0.1"
    }
