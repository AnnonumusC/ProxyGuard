# 🛡️ ProxyGuard Ultimate v3

> **Anonymous proxy rotator with mesh circuits, fingerprint spoofing, Cloudflare bypass, and a live neon TUI — all in one Python file.**

<!-- ── Live badges ─────────────────────────────────────────────────────────── -->
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/AnnonumusC/ProxyGuard?include_prereleases&logo=github&color=blue)](https://github.com/AnnonumusC/ProxyGuard/releases)
[![GitHub stars](https://img.shields.io/github/stars/AnnonumusC/ProxyGuard?style=flat&logo=github&color=yellow)](https://github.com/AnnonumusC/ProxyGuard/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/AnnonumusC/ProxyGuard?style=flat&logo=github&color=orange)](https://github.com/AnnonumusC/ProxyGuard/network/members)
[![GitHub issues](https://img.shields.io/github/issues/AnnonumusC/ProxyGuard?logo=github&color=red)](https://github.com/AnnonumusC/ProxyGuard/issues)
[![Last commit](https://img.shields.io/github/last-commit/AnnonumusC/ProxyGuard?logo=git&logoColor=white)](https://github.com/AnnonumusC/ProxyGuard/commits/main)
[![CI](https://img.shields.io/github/actions/workflow/status/AnnonumusC/ProxyGuard/ci.yml?label=CI&logo=github-actions&logoColor=white)](https://github.com/AnnonumusC/ProxyGuard/actions/workflows/ci.yml)
[![Build EXE](https://img.shields.io/github/actions/workflow/status/AnnonumusC/ProxyGuard/build-exe.yml?label=EXE%20build&logo=windows&logoColor=white)](https://github.com/AnnonumusC/ProxyGuard/actions/workflows/build-exe.yml)
[![Telegram](https://img.shields.io/badge/Telegram-%40AnnonumuscDev-2CA5E0?logo=telegram&logoColor=white)](https://t.me/AnnonumuscDev)
[![Discord](https://img.shields.io/badge/Discord-%40annonumusc-5865F2?logo=discord&logoColor=white)](https://discord.com/users/annonumusc)

---

## ✨ Features

| Category | Capability |
|---|---|
| **Routing** | HTTP, HTTPS, SOCKS4, SOCKS5 proxy rotation |
| **Strategies** | Round-robin, random, least-used, best-score, sticky |
| **Mesh / Onion** | Multi-hop onion circuits with guard-node selection (`--mesh-hops N`) |
| **Fingerprinting** | JA3 / JA4 / TLS spoofing across 10 OS types & 7 browser families |
| **Cloudflare** | Turnstile + IUAM + WAF bypass engine, rotating cookie jars |
| **Obfuscation** | Random padding, jitter, HTTP protocol mimicry |
| **Domain Fronting** | CDN-backed fronting via CloudFront, Cloudflare, Fastly, Google |
| **DNS** | DNS-over-HTTPS stealth resolver with multi-provider rotation |
| **Encryption** | X25519 + ChaCha20-Poly1305 ephemeral sessions (optional) |
| **Anti-bot** | Randomised mouse/scroll/click simulation |
| **TUI** | Live 3D ASCII globe, neon proxy table, real-time request log |
| **TUN / VPN** | System-wide TUN interface — captures all OS traffic |
| **Control API** | REST API for remote management |
| **Geo** | Country-code filtering, exit-IP detection |
| **Rate Limiting** | Per-client IP rate limiting |
| **Persistence** | Save & resume proxy health stats across restarts |
| **Discovery** | Auto-fetch from 5 curated public proxy lists |

---

## 📦 Installation

### 1. Clone

```bash
git clone https://github.com/yourusername/proxyguard.git
cd proxyguard
```

### 2. Install core dependencies

```bash
pip install -r requirements.txt
```

### 3. Install optional extras (recommended)

```bash
pip install -r requirements-optional.txt
```

Or install only the extras you need via pip:

```bash
pip install "proxyguard[tui]"       # Neon TUI dashboard
pip install "proxyguard[crypto]"    # X25519 + ChaCha20-Poly1305 encryption
pip install "proxyguard[yaml]"      # YAML config-file support
pip install "proxyguard[tun]"       # System-wide TUN VPN (Linux/macOS root)
pip install "proxyguard[all]"       # Everything
```

### Dependency overview

| Package | Role | Required? |
|---|---|---|
| `click` | CLI framework | ✅ Core |
| `httpx` | Async HTTP client | ✅ Core |
| `python-socks` | SOCKS4/5 support | ✅ Core |
| `textual` + `rich` | TUI dashboard | Optional |
| `cryptography` | X25519 / ChaCha20 encryption | Optional |
| `pyyaml` | YAML config files | Optional |
| `scapy` | TUN/VPN packet handling | Optional (root only) |

---

## 🚀 Quick Start

```bash
# Auto-discover public proxies and run with live TUI
python proxy_guard.py --discover

# Load your own proxy list
python proxy_guard.py proxies.txt

# 3-hop onion routing
python proxy_guard.py proxies.txt --mesh-hops 3

# Elite-only proxies, random rotation
python proxy_guard.py proxies.txt --min-anonymity elite --strategy random

# System-wide VPN mode (requires root + scapy)
sudo python proxy_guard.py proxies.txt --tun-mode

# Headless server (no TUI), with REST control API on port 9090
python proxy_guard.py proxies.txt --headless --api-port 9090

# Load from URL
python proxy_guard.py --source-url https://example.com/proxies.txt
```

After launch, configure your browser or system proxy to:
```
127.0.0.1:8080
```

---

## 🖥️ TUI Dashboard

The live dashboard (requires `textual` + `rich`) shows:

- **Header** — bound host:port, alive/dead/total proxy counts, bytes relayed
- **3D ASCII globe** — real-time exit-node location visualisation
- **Proxy table** — score, latency, success rate, exit IP, country, anonymity level
- **Request log** — last 150 requests with status, method, host, latency, proxy used
- **Mini stats** — forwarded / failed / bytes / current proxy

### Keyboard shortcuts

| Key | Action |
|---|---|
| `q` | Quit |
| `r` | Rotate to next proxy immediately |
| `c` | Re-check all proxies now |
| `d` | Purge dead proxies |
| `s` | Sort table by score |
| `f` | Sort table by fastest latency |

---

## ⚙️ All CLI Options

```
Usage: proxy_guard.py [OPTIONS] [FILE] COMMAND [ARGS]...

Arguments:
  FILE                    Proxy list file (txt / csv / json). Optional if --discover or --source-url is used.

Options:
  --source-url URL        Fetch proxies from this URL (repeatable)
  --host TEXT             Bind address            [default: 127.0.0.1]
  --port INTEGER          Listen port             [default: 8080]
  --threads INTEGER       Health-check workers    [default: 20]
  --strategy CHOICE       round_robin | random | least_used | best_score | sticky
  --rotate-every N        Rotate after N requests [default: 1]
  --rotate-seconds FLOAT  Force rotation every N seconds
  --max-failures INT      Drop proxy after N failures [default: 3]
  --auto-clean-interval S Background re-check interval [default: 120]
  --check-timeout FLOAT   Per-proxy check timeout [default: 10.0]
  --max-retries INT       Attempts per request    [default: 3]
  --min-anonymity CHOICE  transparent | anonymous | elite [default: anonymous]
  --skip-initial-check    Skip startup health check
  --headless              Run without TUI
  --allow-direct-fallback DANGER: fall back to direct if pool is empty
  --chain-file PATH       HTTP pre-hop chain file
  --direct-domain DOMAIN  Bypass proxy for this domain (repeatable)
  --state-file PATH       Persist stats to this file
  --resume / --no-resume  Resume from prior state  [default: no-resume]
  --export-stats PATH     Write final stats JSON here
  --api-port INT          Control API port (0 = disabled) [default: 0]
  --api-host TEXT         Control API bind address [default: 127.0.0.1]
  --geo / --no-geo        Fetch exit country during check
  --geo-filter CODE       Allow only proxies in this country (repeatable)
  --local-auth USER:PASS  Require auth to use the local proxy
  --log-file PATH         Write request log as JSON
  --discover              Auto-discover from public proxy lists
  --refresh-url URL       Re-fetch this URL on interval (repeatable)
  --refresh-interval S    Seconds between URL refreshes [default: 600]
  --rate-limit MAX:WIN    e.g. 100:60 = 100 req per 60 s per client
  --mesh-hops INT         Onion pre-hop count (0 = disabled) [default: 0]
  --mesh-rotate-seconds S Rebuild mesh circuit every N seconds [default: 300]
  --tun-mode              Enable system-wide TUN VPN
  --tun-name TEXT         TUN interface name
  --tun-network CIDR      Virtual network CIDR    [default: 10.10.0.0/24]
  --tun-dns-doh           Use DoH for DNS interception [default: true]
  --config PATH           JSON or YAML config file
  --help                  Show this message and exit
```

---

## 📡 REST Control API

Enable with `--api-port 9090`:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/proxies` | List all proxies with stats |
| `GET` | `/stats` | Pool summary |
| `POST` | `/rotate` | Force immediate rotation |
| `POST` | `/check` | Trigger health re-check |

```bash
curl http://127.0.0.1:9090/stats | python -m json.tool
```

---

## 🌍 System Proxy Integration

ProxyGuard includes `sysproxy` sub-commands to set/clear your OS proxy in one step:

```bash
# Set system proxy to the running rotator
python proxy_guard.py sysproxy on

# Clear system proxy
python proxy_guard.py sysproxy off

# Check status
python proxy_guard.py sysproxy status
```

Works on **macOS** (`networksetup`), **Linux** (GNOME/KDE gsettings), and **Windows** (registry).

---

## 🔒 System-wide TUN VPN Mode

> ⚠️ Requires **root / Administrator** and the `scapy` package.

```bash
sudo pip install scapy
sudo python proxy_guard.py proxies.txt --tun-mode --tun-network 10.10.0.0/24
```

This creates a virtual TUN interface that captures **all** outgoing OS traffic and routes it through the proxy mesh — no per-application proxy settings needed.

Manual route setup (if not automatic):

```bash
python proxy_guard.py tun routes --network 10.10.0.0/24 --interface tun0
```

---

## 📂 Proxy File Formats

ProxyGuard accepts any of the following:

**Plain text** (one proxy per line):
```
1.2.3.4:8080
socks5://user:pass@5.6.7.8:1080
https://9.10.11.12:443
```

**CSV** (with header row):
```csv
host,port,protocol,username,password
1.2.3.4,8080,http,,
5.6.7.8,1080,socks5,user,pass
```

**JSON**:
```json
[
  {"host": "1.2.3.4", "port": 8080, "protocol": "http"},
  {"host": "5.6.7.8", "port": 1080, "protocol": "socks5", "username": "user", "password": "pass"}
]
```

---

## ⚙️ Config File

Copy `config.example.yaml` (or `config.example.json`) and pass it with `--config`:

```bash
cp config.example.yaml config.yaml
# Edit config.yaml ...
python proxy_guard.py proxies.txt --config config.yaml
```

All CLI flags can be set in the config file. CLI flags take precedence over the config file.

---

## 🔄 Rotation Strategies

| Strategy | Description |
|---|---|
| `round_robin` | Cycle through proxies in order |
| `random` | Pick a random alive proxy each time |
| `least_used` | Prefer the proxy with fewest requests |
| `best_score` | Prefer the highest-scoring (latency + success rate) proxy |
| `sticky` | Pin each client IP to a proxy for the session |

---

## 📊 Proxy Scoring

Each proxy accumulates a **score** (0–100) based on:
- **Success rate** — percentage of successful requests
- **Average latency** — lower is better
- **Consecutive failures** — rapidly penalises unreliable proxies
- **Anonymity level** — elite proxies receive a small bonus

Proxies below the score threshold are quarantined; dead proxies are removed automatically.

---

## 🤝 Contact & Support

Have a question, found a bug, or want to collaborate?

- **Telegram:** [@AnnonumuscDev](https://t.me/AnnonumuscDev)
- **Discord:** [@annonumusc](https://discord.com/users/annonumusc)
- **Issues:** [GitHub Issues](https://github.com/yourusername/proxyguard/issues)

Feel free to reach out on either platform — I'm happy to help with setup, feature requests, or anything else.

---

## 📄 License

[MIT](LICENSE) © ProxyGuard Contributors

---

## ⚠️ Legal Notice

This tool is provided for **educational and legitimate privacy/research purposes only**.  
You are solely responsible for how you use it. Do not use this software to violate the terms of service of any website or platform, conduct illegal activities, or circumvent legal access controls. The authors accept no liability for misuse.
