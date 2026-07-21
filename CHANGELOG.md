# Changelog

All notable changes to ProxyGuard are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [3.0.0] — 2024

### Added
- **Tor-grade mesh circuits** — multi-hop onion-style routing with guard-node selection and stream isolation (`--mesh-hops N`)
- **Random OS/browser fingerprinting** — JA3 / JA4 / TLS fingerprint spoofing across 10 OS types and 7 browser families
- **Cloudflare Turnstile + IUAM + WAF bypass engine** — challenge detection, solving stubs, and cookie-jar rotation
- **Traffic obfuscation** — random byte padding, jitter injection, and HTTP protocol mimicry
- **Domain fronting** — CDN-backed domain fronting (CloudFront, Cloudflare, Fastly, Google)
- **DNS-over-HTTPS (DoH)** stealth resolver with multi-provider rotation and TTL cache
- **X25519 / ChaCha20-Poly1305** end-to-end encryption with ephemeral key rotation (requires `cryptography` extra)
- **Anti-bot behavior simulation** — randomised click delays, scroll events, and mouse movements
- **Live TUI dashboard** — 3D ASCII globe, neon proxy table, live request log, keyboard controls (requires `textual` extra)
- **System-wide TUN VPN mode** — captures all OS traffic through the proxy mesh (Linux/macOS root; requires `scapy` extra)
- **REST Control API** — `GET /proxies`, `GET /stats`, `POST /rotate`, `POST /check` (enable with `--api-port`)
- **YAML / JSON config file** support (`--config config.yaml`)
- **Scheduled URL refresh** — automatically re-fetch remote proxy lists on a configurable interval
- **Rate limiting** per client IP (`--rate-limit MAX:WINDOW`)
- **Local proxy authentication** (`--local-auth user:pass`)
- **Geo filtering** — keep only proxies in allowed country codes (`--geo-filter US DE NL`)
- **State persistence** — save / resume proxy health stats between runs
- **Public proxy auto-discovery** from 5 curated open-source lists (`--discover`)
- **Circuit breaker** per proxy — auto-quarantine on repeated failures with exponential back-off
- **Anti-replay protection** — nonce-based replay detection for secure channels
- **`sysproxy` CLI commands** — one-command system-wide proxy on/off (macOS, Linux, Windows)

### Changed
- Single-file architecture for zero-dependency install of the core feature set
- `--min-anonymity` now defaults to `anonymous` (was `transparent`)
- SOCKS4/5 proxies skip HTTP pre-hop chain (unsupported at protocol level) with a one-time warning

### Fixed
- Chunked transfer-encoding now passes through intact without pre-buffering
- Hop-by-hop headers (`Connection`, `Proxy-Authorization`) correctly stripped; `Transfer-Encoding` preserved
- IP-leaking headers (`X-Forwarded-For`, `Via`, `X-Real-IP`, etc.) fully sanitized on every request

---

## [2.x] — Legacy

Earlier versions provided basic round-robin HTTP/SOCKS proxy rotation with a simple CLI.  
No formal changelog was maintained.
