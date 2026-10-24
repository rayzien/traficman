#!/data/data/com.termux/files/usr/bin/env python3
"""
traficman - High Traffic Generator for Mobile Data & Spike Testing.
Strictly zero emojis. Pure ASCII output, real-time logging, customizable endpoints.
"""

import sys
import os
import time
import socket
import threading
import argparse
import urllib.request
import urllib.error

# Ensure package root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from traficman.config import CDN_ENDPOINTS, DEFAULT_UPLOAD_URL, USER_AGENT, get_network_info
from traficman.logger import Logger, format_bytes, format_speed, format_time, Ansi
from traficman.interactive import run_interactive_wizard

class EngineState:
    def __init__(self, data_limit=0, duration=0, target_speed_bps=0):
        self.data_limit = data_limit
        self.duration = duration
        self.target_speed_bps = target_speed_bps
        
        self.rx_bytes = 0
        self.tx_bytes = 0
        self.start_time = time.time()
        self.stop_requested = threading.Event()
        self.lock = threading.Lock()
        
        # Burst control
        self.burst_active = threading.Event()
        self.burst_active.set()
        self.is_burst_mode = False
        
        # Telemetry
        self.peak_speed_bps = 0.0
        self.last_check_time = time.time()
        self.last_check_bytes = 0
        self.current_speed_bps = 0.0
        self.active_streams = 0

    @property
    def total_bytes(self):
        return self.rx_bytes + self.tx_bytes

    def add_rx(self, n):
        with self.lock:
            self.rx_bytes += n
            if self.data_limit > 0 and self.total_bytes >= self.data_limit:
                self.stop_requested.set()

    def add_tx(self, n):
        with self.lock:
            self.tx_bytes += n
            if self.data_limit > 0 and self.total_bytes >= self.data_limit:
                self.stop_requested.set()

    def update_speed(self):
        now = time.time()
        elapsed = now - self.last_check_time
        if elapsed >= 0.35:
            current_total = self.total_bytes
            delta = current_total - self.last_check_bytes
            speed = (delta * 8) / elapsed if elapsed > 0 else 0.0
            self.current_speed_bps = speed
            if speed > self.peak_speed_bps:
                self.peak_speed_bps = speed
            self.last_check_time = now
            self.last_check_bytes = current_total

    def is_running(self):
        if self.stop_requested.is_set():
            return False
        if self.duration > 0 and (time.time() - self.start_time) >= self.duration:
            self.stop_requested.set()
            return False
        if self.data_limit > 0 and self.total_bytes >= self.data_limit:
            self.stop_requested.set()
            return False
        return True


def parse_size(val_str):
    val_str = str(val_str).strip().upper()
    if not val_str or val_str == "0" or val_str in ("UNLIMITED", "NONE", "MAX"):
        return 0
    multiplier = 1
    if val_str.endswith("G") or val_str.endswith("GB"):
        multiplier = 1024 * 1024 * 1024
        val_str = val_str.rstrip("GB").rstrip("G")
    elif val_str.endswith("M") or val_str.endswith("MB"):
        multiplier = 1024 * 1024
        val_str = val_str.rstrip("MB").rstrip("M")
    elif val_str.endswith("K") or val_str.endswith("KB"):
        multiplier = 1024
        val_str = val_str.rstrip("KB").rstrip("K")
    elif val_str.endswith("B"):
        multiplier = 1
        val_str = val_str.rstrip("B")
    try:
        return int(float(val_str) * multiplier)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid size: '{val_str}'")


def parse_speed(val_str):
    val_str = str(val_str).strip().upper()
    if not val_str or val_str == "0" or val_str in ("MAX", "UNLIMITED", "NONE"):
        return 0
    multiplier = 1_000_000
    if val_str.endswith("G") or val_str.endswith("GBPS"):
        multiplier = 1_000_000_000
        val_str = val_str.rstrip("GBPS").rstrip("G")
    elif val_str.endswith("M") or val_str.endswith("MBPS"):
        multiplier = 1_000_000
        val_str = val_str.rstrip("MBPS").rstrip("M")
    elif val_str.endswith("K") or val_str.endswith("KBPS"):
        multiplier = 1_000
        val_str = val_str.rstrip("KBPS").rstrip("K")
    try:
        return float(val_str) * multiplier
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid speed: '{val_str}'")


def download_stream_worker(worker_id, state, target_meta, logger, thread_rate_bps=0):
    url = target_meta["url"]
    name = target_meta["name"]
    host = target_meta.get("host", name)
    chunk_size = 65536
    headers = {"User-Agent": USER_AGENT}

    with state.lock:
        state.active_streams += 1

    logger.info(f"Stream #{worker_id} initializing connection to [{name}] ({host})...")

    try:
        while state.is_running():
            if state.is_burst_mode and not state.burst_active.is_set():
                time.sleep(0.1)
                continue

            t_req_start = time.time()
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    t_connect = time.time() - t_req_start
                    logger.info(f"Stream #{worker_id} connected to [{name}] in {t_connect:.2f}s | HTTP {resp.status}")

                    t0 = time.time()
                    bytes_batch = 0
                    chunk_count = 0
                    while state.is_running():
                        if state.is_burst_mode and not state.burst_active.is_set():
                            break

                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break

                        c_len = len(chunk)
                        state.add_rx(c_len)
                        bytes_batch += c_len
                        chunk_count += 1

                        if chunk_count % 30 == 0:
                            logger.flow(f"Stream #{worker_id} active: {format_bytes(bytes_batch)} received from [{name}]")

                        if thread_rate_bps > 0:
                            elapsed = time.time() - t0
                            expected = (bytes_batch * 8) / thread_rate_bps
                            if expected > elapsed:
                                sleep_sec = expected - elapsed
                                if sleep_sec > 0:
                                    time.sleep(sleep_sec)
            except Exception as e:
                if not state.is_running():
                    break
                logger.warn(f"Stream #{worker_id} reconnecting to [{name}]: {str(e)[:45]}")
                time.sleep(0.4)
    finally:
        with state.lock:
            state.active_streams -= 1
        logger.info(f"Stream #{worker_id} closed.")


def upload_stream_worker(worker_id, state, url, logger, thread_rate_bps=0):
    chunk_size = 262144
    payload = b"TRAFICMAN_PAYLOAD_CHUNK_DATA_" * (chunk_size // 30)
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/octet-stream"
    }

    with state.lock:
        state.active_streams += 1

    logger.info(f"Upload Stream #{worker_id} connected to Cloudflare upload sink...")

    try:
        while state.is_running():
            if state.is_burst_mode and not state.burst_active.is_set():
                time.sleep(0.1)
                continue

            t0 = time.time()
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp.read(256)
                state.add_tx(len(payload))
                logger.flow(f"Upload #{worker_id} transmitted {format_bytes(len(payload))} payload")

                if thread_rate_bps > 0:
                    elapsed = time.time() - t0
                    expected = (len(payload) * 8) / thread_rate_bps
                    if expected > elapsed:
                        time.sleep(expected - elapsed)
            except Exception as e:
                if not state.is_running():
                    break
                time.sleep(0.4)
    finally:
        with state.lock:
            state.active_streams -= 1


def burst_controller(state, on_time, off_time, logger):
    while state.is_running():
        state.burst_active.set()
        logger.burst(f"BURST WAVE ACTIVATED: Heavy traffic spike for {on_time:.1f}s", highlight=True)
        end_on = time.time() + on_time
        while time.time() < end_on and state.is_running():
            time.sleep(0.1)

        if not state.is_running():
            break

        state.burst_active.clear()
        logger.burst(f"BURST WAVE RESTING: Idle pause for {off_time:.1f}s (Testing app alarm cooldown)", highlight=True)
        end_off = time.time() + off_time
        while time.time() < end_off and state.is_running():
            time.sleep(0.1)


def run_local_tcp_server(port, logger):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(10)
    logger.info(f"Local test server listening on port {port} (0 mobile data used)")
    logger.info(f"Run client with: traficman -m local-client --port {port}")

    def client_handler(conn):
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        buf = b"0" * 65536
        try:
            while True:
                conn.sendall(buf)
        except Exception:
            pass
        finally:
            conn.close()

    try:
        while True:
            conn, _ = s.accept()
            t = threading.Thread(target=client_handler, args=(conn,), daemon=True)
            t.start()
    except KeyboardInterrupt:
        logger.info("Local test server stopped.")
    finally:
        s.close()


def run_local_tcp_client(worker_id, state, host, port, logger, thread_rate_bps=0):
    with state.lock:
        state.active_streams += 1
    logger.info(f"Local client #{worker_id} connecting to {host}:{port}...")

    try:
        while state.is_running():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((host, port))
                t0 = time.time()
                bytes_batch = 0
                while state.is_running():
                    data = s.recv(65536)
                    if not data:
                        break
                    l = len(data)
                    state.add_rx(l)
                    bytes_batch += l
                    if thread_rate_bps > 0:
                        elapsed = time.time() - t0
                        expected = (bytes_batch * 8) / thread_rate_bps
                        if expected > elapsed:
                            time.sleep(expected - elapsed)
                s.close()
            except Exception:
                if not state.is_running():
                    break
                time.sleep(0.5)
    finally:
        with state.lock:
            state.active_streams -= 1


def run_generator(params):
    mode = params["mode"]
    port = params.get("port", 9999)
    log_mode = params.get("log_mode", "hybrid")
    logger = Logger(mode=log_mode)

    if mode == "local-server":
        run_local_tcp_server(port, logger)
        return

    data_limit = params.get("limit", 100 * 1024 * 1024)
    duration = params.get("duration", 30)
    target_speed = params.get("speed", 0)
    threads_count = max(1, min(16, params.get("threads", 4)))
    burst_on = params.get("burst_on", 8.0)
    burst_off = params.get("burst_off", 4.0)
    cdn_choice = params.get("cdn_target", "all")
    custom_url = params.get("custom_url")

    state = EngineState(
        data_limit=data_limit,
        duration=duration,
        target_speed_bps=target_speed
    )

    if mode == "burst":
        state.is_burst_mode = True

    thread_rate = (target_speed / threads_count) if target_speed > 0 else 0
    net_info = get_network_info()

    # Determine endpoint list
    if custom_url:
        targets_pool = [{"name": "Custom Endpoint", "url": custom_url, "host": "custom"}]
    elif cdn_choice in CDN_ENDPOINTS:
        targets_pool = [CDN_ENDPOINTS[cdn_choice]]
    else:
        # Round-robin all CDNs
        targets_pool = list(CDN_ENDPOINTS.values())

    print("\n" + "=" * 62)
    print(" TRAFICMAN - HIGH TRAFFIC GENERATOR")
    print("=" * 62)
    print(f" Mode            : {mode.upper()}")
    print(f" Network Status  : {net_info}")
    print(f" Parallel Streams: {threads_count} concurrent workers")
    print(f" Data Safety Cap : {format_bytes(data_limit) if data_limit > 0 else 'UNLIMITED (CAUTION)'}")
    print(f" Duration Cap    : {f'{duration}s' if duration > 0 else 'Continuous until stopped'}")
    if target_speed > 0:
        print(f" Target Speed    : {format_speed(target_speed)}")
    else:
        print(f" Target Speed    : MAXIMUM (Unthrottled Line Rate)")
    print(f" CDN Endpoints   : {', '.join(t['name'] for t in targets_pool)}")
    if mode == "burst":
        print(f" Burst Pattern   : {burst_on}s SPIKE HIGH / {burst_off}s IDLE REST")
    print(f" Zero-Disk Wear  : 100% In-Memory Buffers (Preserves phone flash storage)")
    print("-" * 62)
    print(" Press Ctrl+C at any time to halt safely.")
    print("-" * 62 + "\n")

    # Start workers
    worker_threads = []

    if mode == "local-client":
        host = params.get("host", "127.0.0.1")
        for i in range(threads_count):
            t = threading.Thread(
                target=run_local_tcp_client,
                args=(i + 1, state, host, port, logger, thread_rate),
                daemon=True
            )
            worker_threads.append(t)
    elif mode in ("download", "burst", "multi"):
        for i in range(threads_count):
            target_meta = targets_pool[i % len(targets_pool)]
            t = threading.Thread(
                target=download_stream_worker,
                args=(i + 1, state, target_meta, logger, thread_rate),
                daemon=True
            )
            worker_threads.append(t)
    elif mode == "upload":
        ul_url = custom_url or DEFAULT_UPLOAD_URL
        for i in range(threads_count):
            t = threading.Thread(
                target=upload_stream_worker,
                args=(i + 1, state, ul_url, logger, thread_rate),
                daemon=True
            )
            worker_threads.append(t)
    elif mode == "duplex":
        ul_url = custom_url or DEFAULT_UPLOAD_URL
        half = max(1, threads_count // 2)
        for i in range(half):
            target_meta = targets_pool[i % len(targets_pool)]
            t = threading.Thread(
                target=download_stream_worker,
                args=(i + 1, state, target_meta, logger, thread_rate),
                daemon=True
            )
            worker_threads.append(t)
        for i in range(threads_count - half):
            t = threading.Thread(
                target=upload_stream_worker,
                args=(half + i + 1, state, ul_url, logger, thread_rate),
                daemon=True
            )
            worker_threads.append(t)

    if mode == "burst":
        bc = threading.Thread(
            target=burst_controller,
            args=(state, burst_on, burst_off, logger),
            daemon=True
        )
        bc.start()

    state.start_time = time.time()
    state.last_check_time = state.start_time
    state.last_check_bytes = 0

    for t in worker_threads:
        t.start()

    try:
        while state.is_running():
            logger.render_dashboard(state, net_info)
            time.sleep(0.3)
    except KeyboardInterrupt:
        state.stop_requested.set()
        logger.warn("\nInterrupted by user (Ctrl+C). Halting all streams...")

    elapsed_total = max(0.001, time.time() - state.start_time)
    avg_speed_bps = (state.total_bytes * 8) / elapsed_total

    print("\n\n" + "=" * 62)
    print(" TRAFICMAN - SESSION SUMMARY REPORT")
    print("=" * 62)
    print(f" Total Transferred : {format_bytes(state.total_bytes)} ({state.total_bytes:,} bytes)")
    if state.rx_bytes > 0:
        print(f"  - Download (Rx)  : {format_bytes(state.rx_bytes)}")
    if state.tx_bytes > 0:
        print(f"  - Upload (Tx)    : {format_bytes(state.tx_bytes)}")
    print(f" Active Duration   : {elapsed_total:.2f}s ({format_time(elapsed_total)})")
    print(f" Average Speed     : {format_speed(avg_speed_bps)}")
    print(f" Peak Speed        : {format_speed(state.peak_speed_bps)}")
    print(f" Network Used      : {net_info}")
    print(f" Exit Reason       : {'Data Limit Reached' if state.data_limit > 0 and state.total_bytes >= state.data_limit else ('Duration Expired' if state.duration > 0 and elapsed_total >= state.duration else 'User Stopped')}")
    print("=" * 62 + "\n")


def main():
    # If no arguments provided, enter interactive wizard automatically
    if len(sys.argv) == 1:
        params = run_interactive_wizard()
        run_generator(params)
        return

    parser = argparse.ArgumentParser(
        description="traficman - High Traffic Generator (Zero Emojis)",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Examples:
  traficman                              # Run interactive setup wizard
  tm                                     # Short alias for traficman
  traficman -m burst                     # Test spike detection alarms
  traficman -m multi                     # Multi-website round-robin rotation
  traficman -s 25M                       # Target 25 Mbps threshold
  traficman -l 250M -d 60                # 250MB limit or 60s
  traficman -m local-server --port 9999  # Zero-mobile-data local test server
"""
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["download", "upload", "duplex", "burst", "multi", "local-server", "local-client"],
        default="download",
        help="Traffic mode (default: download)"
    )
    parser.add_argument(
        "-t", "--threads",
        type=int,
        default=4,
        help="Number of concurrent worker streams (default: 4, 1-16)"
    )
    parser.add_argument(
        "-l", "--limit",
        type=parse_size,
        default=parse_size("100M"),
        help="Data limit cap (e.g. 50M, 100M, 500M, 1G; default: 100M)"
    )
    parser.add_argument(
        "-d", "--duration",
        type=int,
        default=30,
        help="Duration in seconds (0 for continuous; default: 30s)"
    )
    parser.add_argument(
        "-s", "--speed",
        type=parse_speed,
        default=0,
        help="Target speed limit in Mbps (e.g. 10M, 25M, 50M; default: 0 for max)"
    )
    parser.add_argument(
        "--burst-on",
        type=float,
        default=8.0,
        help="Seconds of heavy traffic in burst mode (default: 8.0s)"
    )
    parser.add_argument(
        "--burst-off",
        type=float,
        default=4.0,
        help="Seconds of idle rest in burst mode (default: 4.0s)"
    )
    parser.add_argument(
        "--cdn",
        choices=["all", "google", "cloudflare", "kernel", "alpine", "ovh"],
        default="all",
        help="Target CDN mirror (default: all)"
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Custom URL endpoint"
    )
    parser.add_argument(
        "--log-mode",
        choices=["verbose", "dashboard", "hybrid"],
        default="hybrid",
        help="Logging mode: verbose (all events), dashboard (speedometer), hybrid (both; default: hybrid)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9999,
        help="Port for local-server/client (default: 9999)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host for local-client (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--no-limit",
        action="store_true",
        help="Disable data limit"
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Launch interactive setup wizard"
    )

    args = parser.parse_args()

    if args.interactive:
        params = run_interactive_wizard()
        run_generator(params)
        return

    data_limit = 0 if args.no_limit else args.limit
    params = {
        "mode": args.mode,
        "threads": args.threads,
        "limit": data_limit,
        "duration": args.duration,
        "speed": args.speed,
        "burst_on": args.burst_on,
        "burst_off": args.burst_off,
        "cdn_target": args.cdn,
        "custom_url": args.url,
        "log_mode": args.log_mode,
        "port": args.port,
        "host": args.host
    }
    run_generator(params)

if __name__ == "__main__":
    main()
