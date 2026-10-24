# traficman

High-speed traffic generator engineered for Android (Termux) and Linux to test network monitoring services, cellular data counters, and high-traffic / spike detection applications.

Strictly zero emojis. Pure ASCII terminal design, high concurrency, and granular rate control.

---

## Features

- **Zero Flash Storage Wear**: All streams buffer directly into memory and discard immediately. Never fills phone storage.
- **Strict Data Caps**: Built-in quota limit (`--limit 100M`) to prevent cellular carrier overages.
- **Interactive Question Wizard**: Launching with no arguments automatically asks step-by-step questions to configure the run.
- **Burst Wave Mode**: Periodically switches between heavy spikes and idle pauses to test app alarm triggers and cooldown timers.
- **Multi-Website Rotation**: Distributes parallel streams across Google Edge, Cloudflare, Linux Kernel, Alpine, and OVH CDN endpoints.
- **Rate Limiting**: Accurately throttles speed to test specific detection thresholds (e.g. 5 Mbps, 20 Mbps, 50 Mbps).
- **Real-Time Event Logs**: Displays connection times, chunk receipts, socket status, and throughput telemetry in real time.
- **Local LAN Zero-Data Mode**: Includes a built-in TCP test server and client to test traffic over Wi-Fi without consuming cellular data.

---

## Installation & Setup

Add executable symlinks so you can launch it using either `traficman` or `tm`:

```bash
chmod +x /data/data/com.termux/files/home/traficman/traficman.py
ln -sf /data/data/com.termux/files/home/traficman/traficman.py /data/data/com.termux/files/home/bin/traficman
ln -sf /data/data/com.termux/files/home/traficman/traficman.py /data/data/com.termux/files/home/bin/tm
```

---

## Usage

### 1. Interactive Mode (Asks Questions)
Simply run either command with no parameters:
```bash
traficman
```
or
```bash
tm
```

The wizard will ask you:
1. Traffic Mode (Download, Upload, Duplex, Burst, Multi-Website, Local LAN)
2. Target Speed / Intensity (Unthrottled, 100M, 50M, 20M, 5M, or Custom)
3. Data Safety Limit (50M, 100M, 250M, 500M, 1G, Unlimited)
4. Test Duration (15s, 30s, 60s, Continuous)
5. Target Website / CDN (Multi-CDN Round-Robin, Google, Cloudflare, Kernel, Alpine, OVH)
6. Real-Time Log Mode (Detailed Event Logs, Compact Dashboard, or Hybrid)

### 2. Command-Line Direct Runs

**Burst Spikes (Test App Alarms):**
```bash
tm -m burst --burst-on 6 --burst-off 3 --limit 150M --duration 30
```

**Multi-Website CDN Rotation:**
```bash
tm -m multi --threads 6 --limit 100M
```

**Test Specific Threshold (e.g., 20 Mbps):**
```bash
tm -s 20M --limit 100M --duration 30
```

**High Throughput Duplex (Download + Upload):**
```bash
tm -m duplex --threads 8 --limit 200M
```

**Detailed Event Logging:**
```bash
tm --log-mode verbose -l 20M -d 10
```

**Zero Mobile Data Local Test (Over Wi-Fi / Localhost):**
```bash
# Terminal 1 (Server):
tm -m local-server --port 9999

# Terminal 2 (Client):
tm -m local-client --port 9999 --limit 200M
```

---

## Command Reference

| Flag | Long Option | Description | Default |
|------|-------------|-------------|---------|
| `-m` | `--mode` | Traffic mode (`download`, `upload`, `duplex`, `burst`, `multi`, `local-server`, `local-client`) | `download` |
| `-t` | `--threads` | Number of concurrent parallel streams (1-16) | `4` |
| `-l` | `--limit` | Maximum data allowance before automatic halt (e.g. `50M`, `100M`, `1G`) | `100M` |
| `-d` | `--duration` | Time duration in seconds (`0` for continuous) | `30` |
| `-s` | `--speed` | Target speed throttle in Mbps (`0` for maximum line rate) | `0` (Max) |
| `--burst-on` | | Active high-traffic seconds during burst mode | `8.0` |
| `--burst-off` | | Idle rest seconds during burst mode | `4.0` |
| `--cdn` | | Target CDN (`all`, `google`, `cloudflare`, `kernel`, `alpine`, `ovh`) | `all` |
| `--log-mode` | | Logging output style (`verbose`, `dashboard`, `hybrid`) | `hybrid` |
| `-i` | `--interactive`| Launch interactive configuration questionnaire | False |
