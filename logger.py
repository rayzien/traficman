"""
Real-time logging module for traficman.
Zero emojis - clean ASCII output with timestamps and status tags.
"""

import sys
import time

class Ansi:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    CLEAR_LINE = "\033[2K\r"

def get_timestamp():
    return time.strftime("%H:%M:%S")

def format_bytes(n):
    if n >= 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024 * 1024):.2f} GB"
    elif n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.2f} MB"
    elif n >= 1024:
        return f"{n / 1024:.2f} KB"
    return f"{n} B"

def format_speed(bps):
    mbps = bps / 1_000_000
    mbyte_s = (bps / 8) / (1024 * 1024)
    if mbps >= 1000:
        return f"{mbps / 1000:.2f} Gbps ({mbyte_s:.1f} MB/s)"
    elif mbps >= 1.0:
        return f"{mbps:.2f} Mbps ({mbyte_s:.2f} MB/s)"
    else:
        kbps = bps / 1000
        kbyte_s = (bps / 8) / 1024
        return f"{kbps:.1f} Kbps ({kbyte_s:.1f} KB/s)"

def format_time(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"

class Logger:
    def __init__(self, mode="hybrid"):
        # mode: 'verbose', 'dashboard', 'hybrid'
        self.mode = mode
        self.last_status_print = 0

    def log(self, level, message, highlight=False):
        ts = get_timestamp()
        color = Ansi.WHITE
        tag = f"[{level}]"

        if level == "INFO":
            color = Ansi.CYAN
        elif level == "FLOW":
            color = Ansi.GREEN
        elif level == "BURST":
            color = Ansi.MAGENTA
        elif level == "LIMIT":
            color = Ansi.YELLOW
        elif level == "WARN":
            color = Ansi.RED
        elif level == "NET":
            color = Ansi.BLUE
        elif level == "DONE":
            color = Ansi.GREEN

        tag_formatted = f"{color}{Ansi.BOLD}{tag:<7}{Ansi.RESET}"
        msg_formatted = f"{Ansi.BOLD}{message}{Ansi.RESET}" if highlight else message
        sys.stdout.write(f"\r{Ansi.CLEAR_LINE}[{ts}] {tag_formatted} {msg_formatted}\n")
        sys.stdout.flush()

    def info(self, msg, highlight=False):
        self.log("INFO", msg, highlight)

    def flow(self, msg, highlight=False):
        if self.mode in ("verbose", "hybrid"):
            self.log("FLOW", msg, highlight)

    def burst(self, msg, highlight=False):
        self.log("BURST", msg, highlight)

    def limit(self, msg, highlight=False):
        self.log("LIMIT", msg, highlight)

    def warn(self, msg, highlight=False):
        self.log("WARN", msg, highlight)

    def net(self, msg, highlight=False):
        self.log("NET", msg, highlight)

    def done(self, msg, highlight=False):
        self.log("DONE", msg, highlight)

    def render_dashboard(self, state, net_info):
        elapsed = max(0.001, time.time() - state.start_time)
        state.update_speed()

        if self.mode == "verbose":
            return

        # State Tag
        if state.is_burst_mode:
            if state.burst_active.is_set():
                state_str = f"{Ansi.RED}{Ansi.BOLD}[BURST: SPIKE HIGH]{Ansi.RESET}"
            else:
                state_str = f"{Ansi.YELLOW}[BURST: IDLE REST]{Ansi.RESET}"
        elif state.total_bytes == 0:
            state_str = f"{Ansi.YELLOW}[CONNECTING]{Ansi.RESET}"
        else:
            state_str = f"{Ansi.GREEN}{Ansi.BOLD}[ACTIVE FLOW]{Ansi.RESET}"

        # Progress calculation
        pct = 0.0
        if state.data_limit > 0 and state.duration > 0:
            pct = max(state.total_bytes / state.data_limit, elapsed / state.duration)
        elif state.data_limit > 0:
            pct = state.total_bytes / state.data_limit
        elif state.duration > 0:
            pct = elapsed / state.duration

        pct = min(1.0, max(0.0, pct))
        bar_len = 16
        filled = int(pct * bar_len)
        bar = f"[{'#' * filled}{'.' * (bar_len - filled)}]"

        speed_str = format_speed(state.current_speed_bps)
        bytes_str = format_bytes(state.total_bytes)
        limit_str = format_bytes(state.data_limit) if state.data_limit > 0 else "UNLIMITED"
        time_str = format_time(elapsed)
        dur_str = format_time(state.duration) if state.duration > 0 else "CONT"

        line = (
            f"{Ansi.CLEAR_LINE}{state_str} "
            f"Rate: {Ansi.BOLD}{Ansi.CYAN}{speed_str:<20}{Ansi.RESET} | "
            f"Data: {Ansi.BOLD}{bytes_str}{Ansi.RESET}/{limit_str} | "
            f"Time: {time_str}/{dur_str} {bar}"
        )
        sys.stdout.write(line)
        sys.stdout.flush()
