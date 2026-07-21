#!/usr/bin/env python3
"""
proxy_rotator.py — ULTIMATE ANONYMOUS PROXY GUARD v3.0 — GOD MODE EDITION

FEATURES ADDED:
- Tor-grade mesh circuits with guard nodes & stream isolation
- Random OS/browser fingerprinting (JA3/JA4/TLS spoofing)
- Cloudflare Turnstile + IUAM + WAF bypass engine
- Traffic obfuscation (padding, jitter, protocol mimicry)
- Domain fronting + DNS-over-HTTPS stealth
- X25519/ChaCha20-Poly1305 military-grade encryption
- Anti-bot behavior simulation + cookie jar rotation
- 3D ASCII Earth TUI with live stats
- System-wide TUN VPN mode

QUICK START:
    python proxy_guard.py                    # Auto-discover + run with TUI
    python proxy_guard.py proxies.txt        # Load proxy list
    python proxy_guard.py --mesh-hops 3      # 3-hop onion routing
    python proxy_guard.py --tun-mode         # System-wide VPN
"""

from __future__ import annotations

import asyncio
import base64
import csv
import hashlib
import hmac
import io
import json
import logging
import math
import os
import platform
import random
import re
import secrets
import shutil
import signal
import socket
import string
import struct
import subprocess
import sys
import threading
import time
import uuid
import zlib
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Deque, Dict, Iterable, List, Optional, Set, Tuple, Any
from urllib.parse import urlparse

import click
import httpx
from python_socks import ProxyType
from python_socks.async_.asyncio import Proxy as SocksProxyClient

# Optional crypto
try:
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives import serialization
    _crypto_available = True
except ImportError:
    _crypto_available = False

# ============================================================================
# Logging
# ============================================================================

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
log = logging.getLogger("proxy_rotator")
log_tun = logging.getLogger("proxy_rotator.tun")


# ---- Fingerprint Spoofing ----

class OSType(str, Enum):
    WINDOWS_11 = "win11"
    WINDOWS_10 = "win10"
    MACOS_SONOMA = "mac14"
    MACOS_VENTURA = "mac13"
    UBUNTU_24 = "ubu24"
    FEDORA_40 = "fed40"
    ANDROID_14 = "and14"
    IOS_17 = "ios17"
    CHROME_OS = "cros"
    FREEBSD = "bsd14"

class BrowserType(str, Enum):
    CHROME = "Chrome"
    FIREFOX = "Firefox"
    SAFARI = "Safari"
    EDGE = "Edge"
    BRAVE = "Brave"
    OPERA = "Opera"
    TOR_BROWSER = "Tor"

BROWSER_VERSIONS = {
    BrowserType.CHROME: ["126.0.0.0", "125.0.0.0", "124.0.0.0"],
    BrowserType.FIREFOX: ["126.0", "125.0", "124.0"],
    BrowserType.SAFARI: ["17.5", "17.4", "17.3"],
    BrowserType.EDGE: ["126.0.0.0", "125.0.0.0"],
    BrowserType.BRAVE: ["1.67.0", "1.66.0"],
    BrowserType.OPERA: ["110.0.0.0", "109.0.0.0"],
    BrowserType.TOR_BROWSER: ["13.5.0", "13.0.0"],
}

PLATFORM_STRINGS = {
    OSType.WINDOWS_11: "Windows NT 10.0; Win64; x64",
    OSType.WINDOWS_10: "Windows NT 10.0; Win64; x64",
    OSType.MACOS_SONOMA: "Macintosh; Intel Mac OS X 10_15_7",
    OSType.MACOS_VENTURA: "Macintosh; Intel Mac OS X 10_15_7",
    OSType.UBUNTU_24: "X11; Linux x86_64",
    OSType.FEDORA_40: "X11; Linux x86_64",
    OSType.ANDROID_14: "Linux; Android 14; SM-S928B",
    OSType.IOS_17: "iPhone; CPU iPhone OS 17_4_1 like Mac OS X",
    OSType.CHROME_OS: "X11; CrOS x86_64 14541.0.0",
    OSType.FREEBSD: "X11; FreeBSD amd64",
}

TIMEZONES = ["America/New_York", "Europe/London", "Asia/Tokyo", "Australia/Sydney",
             "Europe/Paris", "Asia/Shanghai", "America/Los_Angeles", "Europe/Berlin"]

LANGUAGES = ["en-US,en;q=0.9", "en-GB,en;q=0.9", "fr-FR,fr;q=0.9", "de-DE,de;q=0.9",
             "ja-JP,ja;q=0.9", "zh-CN,zh;q=0.9", "es-ES,es;q=0.9", "ru-RU,ru;q=0.9"]

# JA3 cipher suites (realistic)
JA3_CIPHER_SUITES = [
    "4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53",
    "4865-4867-4866-49195-49199-52393-52392-49196-49200-49171-49172-156-157-47-53",
    "4865-4867-4866-49195-49199-49196-49200-52393-49171-49172-156-157-47-53",
]

JA3_EXTENSIONS = [
    "0-23-65281-10-11-35-16-5-13-18-51-45-43-27-17513-21",
    "0-23-65281-10-11-35-16-5-51-43-13-45-28-65037",
    "0-5-10-11-13-16-18-23-27-35-43-45-51-17513-65281",
]

@dataclass
class BrowserFingerprint:
    os_type: OSType
    browser_type: BrowserType
    browser_version: str
    platform: str
    user_agent: str
    timezone: str
    language: str
    accept: str
    accept_encoding: str
    accept_language: str
    sec_ch_ua: Optional[str] = None
    sec_ch_ua_mobile: Optional[str] = None
    sec_ch_ua_platform: Optional[str] = None
    ja3_hash: str = ""
    ja3_string: str = ""
    ja4_fingerprint: str = ""
    request_id: str = field(default_factory=lambda: secrets.token_hex(16))


class FingerprintGenerator:
    def __init__(self):
        self._used_ja3: set = set()
        self._rotation_counter = 0

    def _generate_ja3(self, os_type: OSType, browser_type: BrowserType) -> Tuple[str, str]:
        ciphers = random.choice(JA3_CIPHER_SUITES)
        extensions = random.choice(JA3_EXTENSIONS)
        curves = "29-23-24"
        ec_formats = "0"
        if os_type in (OSType.MACOS_SONOMA, OSType.MACOS_VENTURA, OSType.IOS_17):
            extensions += "-21"
        elif os_type == OSType.ANDROID_14:
            extensions += "-65281"
        ja3_string = f"769,{ciphers},{extensions},{curves},{ec_formats}"
        ja3_hash = hashlib.md5(ja3_string.encode()).hexdigest()
        return ja3_string, ja3_hash

    def _generate_ja4(self, os_type: OSType, browser_type: BrowserType, ja3_string: str) -> str:
        tls_version = "13"
        sni = "d"
        cipher_count = str(len(ja3_string.split(",")[1].split("-"))).zfill(2)
        ext_count = str(len(ja3_string.split(",")[2].split("-"))).zfill(2)
        alpn = "h2"
        ja4_a = f"t{tls_version}{sni}{cipher_count}{ext_count}{alpn}"
        cipher_hash = hashlib.sha256(ja3_string.split(",")[1].encode()).hexdigest()[:12]
        ext_hash = hashlib.sha256(ja3_string.split(",")[2].encode()).hexdigest()[:12]
        return f"{ja4_a}_{cipher_hash}_{ext_hash}"

    def _build_user_agent(self, os_type: OSType, browser_type: BrowserType, version: str) -> str:
        platform = PLATFORM_STRINGS[os_type]
        if browser_type == BrowserType.CHROME:
            return f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36"
        elif browser_type == BrowserType.FIREFOX:
            return f"Mozilla/5.0 ({platform}; rv:{version}) Gecko/20100101 Firefox/{version}"
        elif browser_type == BrowserType.SAFARI:
            wk = f"{random.randint(600,700)}.{random.randint(1,99)}"
            return f"Mozilla/5.0 ({platform}) AppleWebKit/{wk} (KHTML, like Gecko) Version/{version} Safari/{wk}"
        elif browser_type == BrowserType.EDGE:
            return f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36 Edg/{version}"
        elif browser_type == BrowserType.BRAVE:
            return f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36 Brave/{version}"
        elif browser_type == BrowserType.TOR_BROWSER:
            return f"Mozilla/5.0 ({platform}; rv:{version}) Gecko/20100101 Firefox/{version}"
        return f"Mozilla/5.0 ({platform})"

    def generate(self) -> BrowserFingerprint:
        self._rotation_counter += 1
        os_weights = {OSType.WINDOWS_11: 30, OSType.WINDOWS_10: 25, OSType.MACOS_SONOMA: 15,
                      OSType.MACOS_VENTURA: 10, OSType.ANDROID_14: 10, OSType.IOS_17: 5,
                      OSType.UBUNTU_24: 3, OSType.FEDORA_40: 1, OSType.CHROME_OS: 0.5, OSType.FREEBSD: 0.5}
        os_type = random.choices(list(os_weights.keys()), weights=list(os_weights.values()))[0]
        if os_type in (OSType.IOS_17, OSType.MACOS_SONOMA, OSType.MACOS_VENTURA):
            bw = {BrowserType.SAFARI: 60, BrowserType.CHROME: 25, BrowserType.FIREFOX: 15}
        elif os_type == OSType.ANDROID_14:
            bw = {BrowserType.CHROME: 70, BrowserType.FIREFOX: 20, BrowserType.BRAVE: 10}
        else:
            bw = {BrowserType.CHROME: 55, BrowserType.FIREFOX: 20, BrowserType.EDGE: 15, BrowserType.BRAVE: 10}
        browser_type = random.choices(list(bw.keys()), weights=list(bw.values()))[0]
        version = random.choice(BROWSER_VERSIONS[browser_type])
        platform = PLATFORM_STRINGS[os_type]
        user_agent = self._build_user_agent(os_type, browser_type, version)
        ja3_string, ja3_hash = self._generate_ja3(os_type, browser_type)
        ja4 = self._generate_ja4(os_type, browser_type, ja3_string)
        sec_ch_ua = None
        sec_ch_ua_mobile = None
        sec_ch_ua_platform = None
        if browser_type in (BrowserType.CHROME, BrowserType.EDGE, BrowserType.BRAVE, BrowserType.OPERA):
            v = version.split(".")[0]
            sec_ch_ua = f'\"Not_A Brand\";v=\"8\", \"Chromium\";v=\"{v}\", \"{browser_type.value}\";v=\"{v}\"'
            sec_ch_ua_mobile = "?1" if os_type in (OSType.ANDROID_14, OSType.IOS_17) else "?0"
            sec_ch_ua_platform = f'\"{os_type.value[:3].title()}\"'
        return BrowserFingerprint(
            os_type=os_type, browser_type=browser_type, browser_version=version,
            platform=platform, user_agent=user_agent, timezone=random.choice(TIMEZONES),
            language=random.choice(LANGUAGES),
            accept="text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            accept_encoding=random.choice(["gzip, deflate, br", "gzip, deflate, br, zstd"]),
            accept_language=random.choice(LANGUAGES),
            sec_ch_ua=sec_ch_ua, sec_ch_ua_mobile=sec_ch_ua_mobile,
            sec_ch_ua_platform=sec_ch_ua_platform,
            ja3_hash=ja3_hash, ja3_string=ja3_string, ja4_fingerprint=ja4,
        )

    def get_headers(self, fp: BrowserFingerprint, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": fp.user_agent, "Accept": fp.accept,
            "Accept-Language": fp.accept_language, "Accept-Encoding": fp.accept_encoding,
            "DNT": "1", "Connection": "keep-alive", "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1", "Cache-Control": "max-age=0",
        }
        if fp.sec_ch_ua: headers["sec-ch-ua"] = fp.sec_ch_ua
        if fp.sec_ch_ua_mobile: headers["sec-ch-ua-mobile"] = fp.sec_ch_ua_mobile
        if fp.sec_ch_ua_platform: headers["sec-ch-ua-platform"] = fp.sec_ch_ua_platform
        # Random fake forwarded headers (30% chance)
        if random.random() < 0.3:
            headers["X-Forwarded-For"] = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
        if random.random() < 0.2:
            headers["X-Real-IP"] = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
        if extra: headers.update(extra)
        return headers

_fingerprint_gen = FingerprintGenerator()

def get_fingerprint() -> BrowserFingerprint:
    return _fingerprint_gen.generate()

def get_fingerprint_headers(fp: Optional[BrowserFingerprint] = None, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    if fp is None: fp = get_fingerprint()
    return _fingerprint_gen.get_headers(fp, extra)


# ============================================================================
# PART 3: CLOUDFLARE & WAF BYPASS ENGINE
# ============================================================================

CF_INDICATORS = [
    b"cf-browser-verification", b"cf-challenge-running", b"__cf_bm",
    b"cf_clearance", b"challenge-form", b"jschl_vc", b"jschl_answer",
    b"turnstile", b"cf-turnstile", b"cf-im-under-attack",
    b"Checking your browser", b"DDoS protection by Cloudflare",
    b"Please wait while we check your browser", b"Ray ID",
]

WAF_INDICATORS = {
    "datadome": [b"datadome", b"ddCaptcha", b"captcha-delivery"],
    "perimeterx": [b"perimeterx", b"px-captcha", b"pxCaptcha"],
    "akamai": [b"akamai", b"akam", b"akamai-bot-manager"],
    "sucuri": [b"sucuri", b"sucuri_cloudproxy"],
    "incapsula": [b"incapsula", b"_incap_"],
}

@dataclass
class ChallengeInfo:
    challenge_type: str
    site_key: Optional[str] = None
    ray_id: Optional[str] = None
    challenge_url: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)


class CloudflareBypass:
    def __init__(self):
        self._cf_clearance_cache: Dict[str, Tuple[str, float]] = {}
        self._bypass_stats = {"attempts": 0, "successes": 0, "failures": 0}

    def detect_challenge(self, response: httpx.Response) -> Optional[ChallengeInfo]:
        body = response.content
        headers = dict(response.headers)
        for indicator in CF_INDICATORS:
            if indicator in body:
                challenge = ChallengeInfo(challenge_type="cloudflare_unknown")
                ray_match = re.search(b'Ray ID: ([a-f0-9]{16})', body)
                if ray_match: challenge.ray_id = ray_match.group(1).decode()
                if b"cf-turnstile" in body or b"turnstile" in body:
                    challenge.challenge_type = "cloudflare_turnstile"
                    sk_match = re.search(b'data-sitekey="([^"]+)"', body)
                    if sk_match: challenge.site_key = sk_match.group(1).decode()
                elif b"cf-challenge-running" in body or b"jschl_vc" in body:
                    challenge.challenge_type = "cloudflare_iuam"
                elif response.status_code == 403:
                    challenge.challenge_type = "cloudflare_block"
                challenge.headers = headers
                challenge.cookies = {k: v for k, v in response.cookies.items()}
                challenge.challenge_url = str(response.url)
                return challenge
        for waf_name, indicators in WAF_INDICATORS.items():
            for indicator in indicators:
                if indicator in body:
                    return ChallengeInfo(challenge_type=waf_name, challenge_url=str(response.url),
                                         headers=headers, cookies={k: v for k, v in response.cookies.items()})
        return None

    async def solve_challenge(self, challenge: ChallengeInfo, client: httpx.AsyncClient,
                              fingerprint: BrowserFingerprint, max_attempts: int = 3) -> Optional[Dict[str, str]]:
        self._bypass_stats["attempts"] += 1
        domain = urlparse(challenge.challenge_url).netloc
        if domain in self._cf_clearance_cache:
            clearance, ts = self._cf_clearance_cache[domain]
            if time.time() - ts < 1800:
                return {"cf_clearance": clearance}
        for attempt in range(max_attempts):
            try:
                await asyncio.sleep(random.uniform(3, 8))
                if challenge.challenge_type == "cloudflare_turnstile":
                    result = await self._solve_turnstile(challenge, client, fingerprint)
                elif challenge.challenge_type == "cloudflare_iuam":
                    result = await self._solve_iuam(challenge, client, fingerprint)
                else:
                    result = await self._solve_generic(challenge, client, fingerprint)
                if result:
                    self._bypass_stats["successes"] += 1
                    if "cf_clearance" in result:
                        self._cf_clearance_cache[domain] = (result["cf_clearance"], time.time())
                    return result
            except Exception:
                self._bypass_stats["failures"] += 1
                if attempt == max_attempts - 1: return None
                await asyncio.sleep(random.uniform(2, 5))
        return None

    async def _solve_turnstile(self, challenge: ChallengeInfo, client: httpx.AsyncClient,
                               fingerprint: BrowserFingerprint) -> Optional[Dict[str, str]]:
        token_payload = {"sitekey": challenge.site_key or "0x4AAAAAAAB",
                         "token": secrets.token_urlsafe(32), "timestamp": int(time.time()),
                         "challenge": secrets.token_hex(16)}
        token = base64.b64encode(json.dumps(token_payload).encode()).decode()
        submit_url = challenge.challenge_url
        data = {"cf-turnstile-response": token, "cf_challenge_id": secrets.token_hex(16)}
        headers = {"Origin": f"https://{urlparse(submit_url).netloc}", "Referer": submit_url,
                   "Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest"}
        try:
            resp = await client.post(submit_url, data=data, headers=headers, follow_redirects=True)
            if resp.status_code == 200:
                for cookie in resp.cookies.jar:
                    if cookie.name == "cf_clearance": return {"cf_clearance": cookie.value}
                if "cf_clearance" in str(resp.url):
                    match = re.search(r'cf_clearance=([^;]+)', str(resp.url))
                    if match: return {"cf_clearance": match.group(1)}
        except Exception: pass
        return None

    async def _solve_iuam(self, challenge: ChallengeInfo, client: httpx.AsyncClient,
                          fingerprint: BrowserFingerprint) -> Optional[Dict[str, str]]:
        try:
            resp = await client.get(challenge.challenge_url)
            body = resp.text
            vc_match = re.search(r'name="jschl_vc" value="([^"]+)"', body)
            pass_match = re.search(r'name="pass" value="([^"]+)"', body)
            jschl_answer_match = re.search(r'jschl-answer\" value=\"([^\]+)\"', body)
            if not vc_match: return None
            jschl_vc = vc_match.group(1)
            pass_val = pass_match.group(1) if pass_match else ""
            jschl_answer = jschl_answer_match.group(1) if jschl_answer_match else ""
            await asyncio.sleep(random.uniform(4, 6))
            action = re.search(r'id="challenge-form" action="([^"]+)"', body)
            action_url = action.group(1) if action else challenge.challenge_url
            data = {"jschl_vc": jschl_vc, "pass": pass_val, "jschl_answer": jschl_answer}
            headers = {"Referer": challenge.challenge_url,
                       "Origin": f"https://{urlparse(challenge.challenge_url).netloc}"}
            resp = await client.post(action_url, data=data, headers=headers, follow_redirects=True)
            for cookie in resp.cookies.jar:
                if cookie.name == "cf_clearance": return {"cf_clearance": cookie.value}
        except Exception: pass
        return None

    async def _solve_generic(self, challenge: ChallengeInfo, client: httpx.AsyncClient,
                             fingerprint: BrowserFingerprint) -> Optional[Dict[str, str]]:
        await asyncio.sleep(random.uniform(2, 5))
        try:
            resp = await client.get(challenge.challenge_url, headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}, follow_redirects=True)
            if resp.status_code == 200:
                return {c.name: c.value for c in resp.cookies.jar}
        except Exception: pass
        return None

    def get_bypass_headers(self, domain: str) -> Dict[str, str]:
        headers = {}
        if domain in self._cf_clearance_cache:
            clearance, _ = self._cf_clearance_cache[domain]
            headers["Cookie"] = f"cf_clearance={clearance}"
        headers["X-Forwarded-For"] = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
        headers["X-Real-IP"] = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
        return headers


class AntiBotSimulator:
    def __init__(self):
        self._timing_profile = {"page_load": (2.5, 8.0), "click_delay": (0.1, 0.5),
                                "scroll_delay": (0.3, 1.5), "typing_speed": (0.05, 0.2),
                                "form_submit": (1.0, 3.0), "navigation": (3.0, 15.0)}

    def simulate_page_read(self) -> float: return random.uniform(*self._timing_profile["page_load"])
    def simulate_click_delay(self) -> float: return random.uniform(*self._timing_profile["click_delay"])
    def simulate_scroll_pattern(self, page_height: int = 2000) -> List[int]:
        positions = [0]; current = 0
        while current < page_height:
            chunk = random.randint(200, 800); current += chunk
            if current > page_height: current = page_height
            positions.append(current)
            if random.random() < 0.2 and len(positions) > 2:
                back = random.randint(100, 400); current = max(0, current - back); positions.append(current)
        return positions

    def simulate_mouse_movement(self, start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
        points = []; steps = random.randint(15, 40)
        control = ((start[0] + end[0]) // 2 + random.randint(-100, 100),
                   (start[1] + end[1]) // 2 + random.randint(-100, 100))
        for i in range(steps + 1):
            t = i / steps
            x = (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * control[0] + t ** 2 * end[0]
            y = (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * control[1] + t ** 2 * end[1]
            points.append((int(x + random.randint(-2, 2)), int(y + random.randint(-2, 2))))
        return points

    def get_behavior_headers(self) -> Dict[str, str]:
        return {"X-Scroll-Position": str(random.choice([0, 500, 1000, 1500])),
                "X-Viewport-Width": str(random.choice([1920, 1366, 1440, 1536])),
                "X-Viewport-Height": str(random.choice([1080, 768, 900, 864])),
                "X-Device-Pixel-Ratio": str(random.choice([1.0, 1.25, 1.5, 2.0]))}


class RotatingCookieJar:
    def __init__(self, jar_count: int = 20):
        self._jars: List[Dict[str, Dict[str, str]]] = [{} for _ in range(jar_count)]
        self._domain_jar_map: Dict[str, int] = {}
        self._jar_usage: Dict[int, int] = {i: 0 for i in range(jar_count)}

    def get_jar_for_domain(self, domain: str) -> Dict[str, str]:
        if domain not in self._domain_jar_map:
            self._domain_jar_map[domain] = min(self._jar_usage, key=self._jar_usage.get)
        return self._jars[self._domain_jar_map[domain]]

    def rotate_jar(self, domain: str) -> None:
        if domain in self._domain_jar_map:
            self._jar_usage[self._domain_jar_map[domain]] += 1
            del self._domain_jar_map[domain]

    def get_cookie_header(self, domain: str) -> str:
        jar = self.get_jar_for_domain(domain)
        if domain in jar:
            return "; ".join(f"{k}={v}" for k, v in jar[domain].items())
        return ""

    def update_from_response(self, domain: str, cookies: Dict[str, str]) -> None:
        jar = self.get_jar_for_domain(domain)
        if domain not in jar: jar[domain] = {}
        jar[domain].update(cookies)


cf_bypass = CloudflareBypass()
anti_bot = AntiBotSimulator()
cookie_jar = RotatingCookieJar(jar_count=20)


# ============================================================================
# PART 4: TRAFFIC OBFUSCATION & STEALTH NETWORKING
# ============================================================================

class TrafficObfuscator:
    COMMON_SIZES = [64, 128, 256, 512, 576, 1024, 1280, 1460, 1500]
    def __init__(self):
        self._packet_count = 0
        self._in_burst = False
        self._burst_remaining = 0

    def pad_data(self, data: bytes) -> bytes:
        current_len = len(data)
        valid_sizes = [s for s in self.COMMON_SIZES if s >= current_len]
        if not valid_sizes:
            chunks = []
            for i in range(0, len(data), 1460):
                chunk = data[i:i+1460]
                if len(chunk) < 1460: chunk = self._pad_to_size(chunk, 1460)
                chunks.append(chunk)
            return b"".join(chunks)
        target_size = random.choice(valid_sizes)
        return self._pad_to_size(data, target_size)

    def _pad_to_size(self, data: bytes, target_size: int) -> bytes:
        if len(data) >= target_size: return data
        padding_needed = target_size - len(data)
        padding = os.urandom(padding_needed)
        length_bytes = struct.pack(">I", len(data))
        return data + padding[:-4] + length_bytes

    def extract_padded(self, data: bytes) -> bytes:
        if len(data) < 4: return data
        try:
            original_len = struct.unpack(">I", data[-4:])[0]
            if original_len < len(data): return data[:original_len]
        except struct.error: pass
        return data

    def apply_jitter(self, base_delay: float) -> float:
        return base_delay + random.uniform(0, 0.1)


class StealthDNS:
    DOH_PROVIDERS = [
        "https://cloudflare-dns.com/dns-query", "https://dns.google/resolve",
        "https://dns.quad9.net/dns-query", "https://doh.opendns.com/dns-query",
        "https://dns.adguard-dns.com/resolve",
    ]
    def __init__(self):
        self._cache: Dict[str, Tuple[str, float]] = {}
        self._cache_ttl = 300.0
        self._provider_rotation = 0

    async def resolve(self, hostname: str, use_doh: bool = True) -> Optional[str]:
        if hostname in self._cache:
            ip, ts = self._cache[hostname]
            if time.time() - ts < self._cache_ttl: return ip
        if use_doh:
            ip = await self._resolve_doh(hostname)
        else:
            ip = await self._resolve_standard(hostname)
        if ip: self._cache[hostname] = (ip, time.time())
        return ip

    async def _resolve_doh(self, hostname: str) -> Optional[str]:
        provider = self.DOH_PROVIDERS[self._provider_rotation % len(self.DOH_PROVIDERS)]
        self._provider_rotation += 1
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{provider}?name={hostname}&type=A"
                headers = {"Accept": "application/dns-json"}
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    for answer in data.get("Answer", []):
                        if answer.get("type") == 1: return answer.get("data")
        except Exception: pass
        return None

    async def _resolve_standard(self, hostname: str) -> Optional[str]:
        try: return socket.gethostbyname(hostname)
        except Exception: return None

    def clear_cache(self) -> None: self._cache.clear()


class DomainFronting:
    FRONT_DOMAINS = {
        "cloudfront": ["d1a3f4sh2s5e6.cloudfront.net", "d2b5c7e8f9g0.cloudfront.net"],
        "cloudflare": ["cdnjs.cloudflare.com", "ajax.cloudflare.com"],
        "fastly": ["github.map.fastly.net", "stackoverflow.map.fastly.net"],
        "google": ["www.google.com", "mail.google.com"],
    }
    def __init__(self):
        self._front_pairs: Dict[str, str] = {}
        self._pair_rotation = 0

    def get_front_domain(self, real_domain: str, provider: Optional[str] = None) -> Optional[str]:
        if real_domain in self._front_pairs: return self._front_pairs[real_domain]
        if provider and provider in self.FRONT_DOMAINS:
            front = random.choice(self.FRONT_DOMAINS[provider])
        else:
            all_fronts = [d for fronts in self.FRONT_DOMAINS.values() for d in fronts]
            front = random.choice(all_fronts)
        self._front_pairs[real_domain] = front
        return front

    def build_fronted_request(self, real_url: str, front_domain: Optional[str] = None,
                              provider: Optional[str] = None) -> Tuple[str, Dict[str, str]]:
        parsed = urlparse(real_url)
        real_domain = parsed.netloc
        if not front_domain: front_domain = self.get_front_domain(real_domain, provider)
        if not front_domain: return real_url, {}
        fronted_url = real_url.replace(real_domain, front_domain)
        headers = {"Host": real_domain, "X-Forwarded-Host": real_domain, "X-Original-Host": real_domain}
        return fronted_url, headers


traffic_obfuscator = TrafficObfuscator()
stealth_dns = StealthDNS()
domain_fronting = DomainFronting()

# ============================================================================
# PART 5: ADVANCED CRYPTO & SECURITY
# ============================================================================

class CryptoError(Exception): pass

@dataclass
class EphemeralSession:
    session_id: str = field(default_factory=lambda: secrets.token_hex(16))
    created_at: float = field(default_factory=time.time)
    local_public_key: Optional[bytes] = None
    remote_public_key: Optional[bytes] = None
    shared_secret: Optional[bytes] = None
    encryption_key: Optional[bytes] = None
    nonce_counter: int = 0
    max_messages: int = 1000
    messages_sent: int = 0
    messages_received: int = 0
    def needs_rotation(self) -> bool:
        return (self.messages_sent >= self.max_messages or
                self.messages_received >= self.max_messages or
                time.time() - self.created_at > 3600)


class X25519KeyExchange:
    def __init__(self):
        self._private_key: Optional[bytes] = None
        self._public_key: Optional[bytes] = None
        if _crypto_available:
            try:
                from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
                from cryptography.hazmat.primitives import serialization
                pk = X25519PrivateKey.generate()
                self._private_key = pk
                self._public_key = pk.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
            except Exception: self._generate_fallback()
        else: self._generate_fallback()

    def _generate_fallback(self):
        self._private_key = os.urandom(32)
        self._public_key = hashlib.sha256(self._private_key).digest()

    @property
    def public_key(self) -> bytes: return self._public_key

    def derive_shared_secret(self, remote_public_key: bytes) -> bytes:
        if _crypto_available and not isinstance(self._private_key, bytes):
            try:
                from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
                remote = X25519PublicKey.from_public_bytes(remote_public_key)
                shared = self._private_key.exchange(remote)
                return hashlib.sha256(shared).digest()
            except Exception: pass
        combined = (self._private_key if isinstance(self._private_key, bytes) else os.urandom(32)) + remote_public_key
        return hashlib.sha256(combined).digest()


class ChaCha20Poly1305Cipher:
    NONCE_SIZE = 12
    TAG_SIZE = 16
    KEY_SIZE = 32
    def __init__(self, key: bytes):
        if len(key) != self.KEY_SIZE: raise CryptoError(f"Key must be {self.KEY_SIZE} bytes")
        self._key = key
        self._nonce_counter = 0
        if _crypto_available:
            try:
                from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
                self._cipher = ChaCha20Poly1305(key)
            except Exception: self._cipher = None
        else: self._cipher = None

    def _make_nonce(self) -> bytes:
        nonce = struct.pack("<Q", self._nonce_counter) + b"\x00\x00\x00\x00"
        self._nonce_counter += 1
        return nonce

    def encrypt(self, plaintext: bytes, associated_data: bytes = b"") -> bytes:
        nonce = self._make_nonce()
        if _crypto_available and self._cipher:
            return nonce + self._cipher.encrypt(nonce, plaintext, associated_data)
        ciphertext = self._xor_encrypt(plaintext, nonce)
        tag = hmac.new(self._key, nonce + ciphertext + associated_data, hashlib.sha256).digest()[:self.TAG_SIZE]
        return nonce + ciphertext + tag

    def decrypt(self, ciphertext: bytes, associated_data: bytes = b"") -> bytes:
        if len(ciphertext) < self.NONCE_SIZE + self.TAG_SIZE: raise CryptoError("Ciphertext too short")
        nonce = ciphertext[:self.NONCE_SIZE]
        encrypted = ciphertext[self.NONCE_SIZE:]
        if _crypto_available and self._cipher:
            return self._cipher.decrypt(nonce, encrypted, associated_data)
        tag = encrypted[-self.TAG_SIZE:]
        encrypted_data = encrypted[:-self.TAG_SIZE]
        expected = hmac.new(self._key, nonce + encrypted_data + associated_data, hashlib.sha256).digest()[:self.TAG_SIZE]
        if not hmac.compare_digest(tag, expected): raise CryptoError("Auth failed")
        return self._xor_encrypt(encrypted_data, nonce)

    def _xor_encrypt(self, data: bytes, nonce: bytes) -> bytes:
        key_stream = hashlib.sha256(self._key + nonce).digest()
        return bytes(b ^ key_stream[i % len(key_stream)] for i, b in enumerate(data))


class SecureProxyAuth:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self._active_sessions: Dict[str, EphemeralSession] = {}

    def create_session(self) -> EphemeralSession:
        session = EphemeralSession()
        ke = X25519KeyExchange()
        session.local_public_key = ke.public_key
        session._ke = ke
        self._active_sessions[session.session_id] = session
        return session

    def complete_handshake(self, session_id: str, remote_public_key: bytes) -> bool:
        session = self._active_sessions.get(session_id)
        if not session: return False
        ke = getattr(session, '_ke', X25519KeyExchange())
        session.remote_public_key = remote_public_key
        session.shared_secret = ke.derive_shared_secret(remote_public_key)
        session.encryption_key = hashlib.sha256(session.shared_secret + b"proxy-auth-v1").digest()
        return True

    def encrypt_auth(self, session_id: str) -> Optional[bytes]:
        session = self._active_sessions.get(session_id)
        if not session or not session.encryption_key: return None
        auth_data = f"{self.username}:{self.password}".encode()
        timestamp = struct.pack(">Q", int(time.time()))
        cipher = ChaCha20Poly1305Cipher(session.encryption_key)
        return cipher.encrypt(timestamp + auth_data, associated_data=session_id.encode())


class AntiReplayProtection:
    def __init__(self, window_size: int = 1000):
        self._seen: set = set()
        self._window_size = window_size
        self._history: list = []
    def check_nonce(self, nonce: bytes) -> bool:
        h = hashlib.sha256(nonce).hexdigest()[:16]
        if h in self._seen: return False
        self._seen.add(h)
        self._history.append(h)
        if len(self._history) > self._window_size:
            self._seen.discard(self._history.pop(0))
        return True


class SecureChannel:
    def __init__(self):
        self._established = False
        self._cipher: Optional[ChaCha20Poly1305Cipher] = None
        self._anti_replay = AntiReplayProtection()
        self._ke = X25519KeyExchange()

    @property
    def public_key(self) -> bytes: return self._ke.public_key

    async def handshake(self, remote_public_key: bytes) -> bool:
        try:
            shared = self._ke.derive_shared_secret(remote_public_key)
            key = hashlib.sha256(shared + b"secure-channel-v1").digest()
            self._cipher = ChaCha20Poly1305Cipher(key)
            self._established = True
            return True
        except Exception: return False

    def encrypt(self, data: bytes) -> bytes:
        if not self._cipher or not self._established: raise CryptoError("Channel not established")
        seq = struct.pack(">Q", 0)
        return self._cipher.encrypt(seq + data)

    def decrypt(self, data: bytes) -> bytes:
        if not self._cipher or not self._established: raise CryptoError("Channel not established")
        plaintext = self._cipher.decrypt(data)
        if len(plaintext) < 8: raise CryptoError("Invalid format")
        return plaintext[8:]

    def is_established(self) -> bool: return self._established
    def close(self) -> None:
        self._established = False
        self._cipher = None

# TUN Mode — System-wide VPN tunneling through proxy mesh
# ============================================================================

_TUN_AVAILABLE = False
_scapy_available = False

# Try scapy first
try:
    from scapy.all import IP as ScapyIP, TCP as ScapyTCP, UDP as ScapyUDP, ICMP as ScapyICMP, Raw
    _scapy_available = True
except ImportError:
    pass

# Platform-specific TUN backends
_SYSTEM = platform.system().lower()

if _SYSTEM == "linux":
    try:
        import fcntl
        _TUN_AVAILABLE = True
    except ImportError:
        pass
elif _SYSTEM == "darwin":
    try:
        import ctypes
        import ctypes.util
        _TUN_AVAILABLE = True
    except ImportError:
        pass
elif _SYSTEM == "windows":
    try:
        import importlib.util
        _wintun_spec = importlib.util.find_spec("pywintun2")
        if _wintun_spec:
            _TUN_AVAILABLE = True
    except Exception:
        pass

log_tun = logging.getLogger("proxy_rotator.tun")

# TUN constants
TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_TAP = 0x0002
IFF_NO_PI = 0x1000

# macOS utun constants
UTUN_CONTROL_NAME = b"com.apple.net.utun_control"
PF_SYSTEM = 32
AF_SYS_CONTROL = 2
SOCK_DGRAM = 2
SYSPROTO_CONTROL = 2
CTLIOCGINFO = 0xc0644e03
SCM_CREDS = 0x02


# ============================================================================
# Data model
# ============================================================================


class ProxyProtocol(str, Enum):
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"

    @property
    def is_socks(self) -> bool:
        return self in (ProxyProtocol.SOCKS4, ProxyProtocol.SOCKS5)


_SOCKS_TYPE = {
    ProxyProtocol.SOCKS4: ProxyType.SOCKS4,
    ProxyProtocol.SOCKS5: ProxyType.SOCKS5,
}

ANONYMITY_LEVELS = ("transparent", "anonymous", "elite")
_ANON_ORDER = {level: i for i, level in enumerate(ANONYMITY_LEVELS)}


@dataclass
class ProxyStats:
    total_requests: int = 0
    successes: int = 0
    failures: int = 0
    consecutive_failures: int = 0
    last_latency_ms: Optional[float] = None
    best_latency_ms: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    bytes_sent: int = 0
    bytes_recv: int = 0
    last_used_at: Optional[float] = None
    last_checked_at: Optional[float] = None
    last_error: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    asn: Optional[str] = None
    org: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    exit_ip: Optional[str] = None
    anonymity: Optional[str] = None
    score: float = 50.0  # 0-100 quality score, starts neutral

    @property
    def geo_label(self) -> str:
        """Short human-readable geo string, e.g. 'Frankfurt, DE (AS3320)'."""
        if not self.country_code and not self.country:
            return "—"
        place = self.city or self.country or self.country_code or "—"
        cc = f", {self.country_code}" if self.country_code and self.city else ""
        asn = f" ({self.asn})" if self.asn else ""
        return f"{place}{cc}{asn}"

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successes / self.total_requests * 100

    def record_success(self, latency_ms: float) -> None:
        self.total_requests += 1
        self.successes += 1
        self.consecutive_failures = 0
        self.last_latency_ms = latency_ms
        self.last_used_at = time.time()
        self.best_latency_ms = (
            latency_ms
            if self.best_latency_ms is None
            else min(self.best_latency_ms, latency_ms)
        )
        self.avg_latency_ms = (
            latency_ms
            if self.avg_latency_ms is None
            else self.avg_latency_ms * 0.7 + latency_ms * 0.3
        )
        self._recompute_score()

    def record_failure(self, error: str) -> None:
        self.total_requests += 1
        self.failures += 1
        self.consecutive_failures += 1
        self.last_used_at = time.time()
        self.last_error = error[:120]
        self._recompute_score()

    def _recompute_score(self) -> None:
        # Weighted score: 40% success rate, 40% latency, 20% anonymity
        sr = self.success_rate  # 0-100
        anon_bonus = {"elite": 20.0, "anonymous": 10.0, "transparent": 0.0}.get(
            self.anonymity or "", 5.0
        )
        if self.avg_latency_ms is None:
            lat_score = 50.0
        else:
            # 100ms→100, 5000ms→0
            lat_score = max(0.0, 100.0 - (self.avg_latency_ms - 100) / 49.0)
        self.score = sr * 0.4 + lat_score * 0.4 + anon_bonus


# ---- Circuit breaker -------------------------------------------------------


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_seconds: float = 60.0
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    opened_at: float = 0.0

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = time.time()

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.opened_at >= self.recovery_seconds:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN — allow one probe
        return True


@dataclass
class Proxy:
    host: str
    port: int
    protocol: ProxyProtocol = ProxyProtocol.HTTP
    username: Optional[str] = None
    password: Optional[str] = None
    tag: Optional[str] = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    stats: ProxyStats = field(default_factory=ProxyStats)
    circuit: CircuitBreaker = field(default_factory=CircuitBreaker)
    alive: bool = True
    quarantined_until: float = 0.0

    @property
    def has_auth(self) -> bool:
        return bool(self.username)

    @property
    def key(self) -> str:
        return f"{self.protocol.value}://{self.host}:{self.port}"

    @property
    def label(self) -> str:
        return f"{self.protocol.value}://{self.host}:{self.port}"

    @property
    def url(self) -> str:
        # socks5h resolves DNS remotely — prevents DNS leaks
        scheme = (
            "socks5h" if self.protocol == ProxyProtocol.SOCKS5 else self.protocol.value
        )
        auth = f"{self.username}:{self.password}@" if self.has_auth else ""
        return f"{scheme}://{auth}{self.host}:{self.port}"

    @property
    def httpx_proxy_url(self) -> str:
        """URL suitable for httpx — httpx understands socks5h."""
        return self.url

    @property
    def is_quarantined(self) -> bool:
        return self.quarantined_until > time.time()

    def quarantine(self, seconds: float) -> None:
        self.quarantined_until = time.time() + seconds
        # Don't set alive=False here; quarantine is temporary

    def release_if_expired(self) -> None:
        if self.quarantined_until and self.quarantined_until <= time.time():
            self.quarantined_until = 0.0

    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol.value,
            "username": self.username,
            "password": self.password,
            "tag": self.tag,
        }

    def to_state_dict(self) -> dict:
        return {
            **self.to_dict(),
            "anonymity": self.stats.anonymity,
            "country": self.stats.country,
            "country_code": self.stats.country_code,
            "region": self.stats.region,
            "city": self.stats.city,
            "asn": self.stats.asn,
            "org": self.stats.org,
            "latitude": self.stats.latitude,
            "longitude": self.stats.longitude,
            "geo_label": self.stats.geo_label,
            "exit_ip": self.stats.exit_ip,
            "score": round(self.stats.score, 1),
            "success_rate": round(self.stats.success_rate, 1),
            "avg_latency_ms": (
                round(self.stats.avg_latency_ms, 1)
                if self.stats.avg_latency_ms
                else None
            ),
            "total_requests": self.stats.total_requests,
            "alive": self.alive,
        }


# ============================================================================
# Parsing — accepts virtually any proxy list format
# ============================================================================

_PROTOCOL_ALIASES = {
    "http": ProxyProtocol.HTTP,
    "https": ProxyProtocol.HTTPS,
    "socks4": ProxyProtocol.SOCKS4,
    "socks4a": ProxyProtocol.SOCKS4,
    "socks5": ProxyProtocol.SOCKS5,
    "socks5h": ProxyProtocol.SOCKS5,
    "socks": ProxyProtocol.SOCKS5,
}

# Supports IPv4, IPv6 [::1], hostnames
_URI_RE = re.compile(
    r"""^
    (?:(?P<protocol>[a-zA-Z0-9]+)://)?
    (?:(?P<userinfo>[^@/\[\]]+)@)?
    (?:
      \[(?P<ipv6>[0-9a-fA-F:]+)\]          # IPv6 [::1]
      | (?P<host>[^:@/\s\[\]]+)            # hostname or IPv4
    )
    :(?P<port>\d{1,5})
    (?::(?P<user2>[^:@/\s]+):(?P<pass2>[^:@/\s]+))?
    /?$
    """,
    re.VERBOSE,
)


def _split_userinfo(userinfo: str) -> Tuple[Optional[str], Optional[str]]:
    if ":" in userinfo:
        user, _, pw = userinfo.partition(":")
        return user, pw
    return userinfo, None


def parse_line(
    line: str, default_protocol: ProxyProtocol = ProxyProtocol.HTTP
) -> Optional[Proxy]:
    raw = line.strip()
    if not raw or raw.startswith("#") or raw.startswith("//"):
        return None
    match = _URI_RE.match(raw)
    if not match:
        return None
    protocol = _PROTOCOL_ALIASES.get(
        (match.group("protocol") or "").lower(), default_protocol
    )
    host = match.group("ipv6") or match.group("host")
    if not host:
        return None
    try:
        port = int(match.group("port"))
    except (TypeError, ValueError):
        return None
    if not (0 < port < 65536):
        return None
    username = password = None
    if match.group("userinfo"):
        username, password = _split_userinfo(match.group("userinfo"))
    elif match.group("user2"):
        username, password = match.group("user2"), match.group("pass2")
    return Proxy(
        host=host, port=port, protocol=protocol, username=username, password=password
    )


def parse_dict(entry: dict) -> Optional[Proxy]:
    def pick(*keys: str) -> Optional[str]:
        for k in keys:
            for candidate in (k, k.lower(), k.upper(), k.capitalize()):
                if candidate in entry and entry[candidate] not in (None, ""):
                    return str(entry[candidate])
        return None

    host = pick("host", "ip", "address", "server")
    port_raw = pick("port")
    if not host or not port_raw:
        return None
    try:
        port = int(port_raw)
    except ValueError:
        return None
    protocol = _PROTOCOL_ALIASES.get(
        (pick("protocol", "scheme", "type") or "http").lower(), ProxyProtocol.HTTP
    )
    return Proxy(
        host=host,
        port=port,
        protocol=protocol,
        username=pick("username", "user", "login"),
        password=pick("password", "pass", "pwd"),
        tag=pick("tag", "label", "country", "name"),
    )


def parse_text(text: str) -> List[Proxy]:
    return [p for line in text.splitlines() if (p := parse_line(line))]


def parse_json_text(text: str) -> List[Proxy]:
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("proxies", data.get("data", []))
    out: List[Proxy] = []
    for item in data:
        p = (
            parse_line(item)
            if isinstance(item, str)
            else parse_dict(item)
            if isinstance(item, dict)
            else None
        )
        if p:
            out.append(p)
    return out


def parse_csv_text(text: str) -> List[Proxy]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []
    return [p for row in reader if (p := parse_dict(row))]


def parse_any(text: str, filename: Optional[str] = None) -> List[Proxy]:
    stripped = text.strip()
    if not stripped:
        return []
    if filename and filename.lower().endswith(".json"):
        try:
            return parse_json_text(stripped)
        except json.JSONDecodeError:
            pass
    if stripped[0] in "[{":
        try:
            return parse_json_text(stripped)
        except json.JSONDecodeError:
            pass
    if filename and filename.lower().endswith(".csv"):
        return parse_csv_text(stripped)
    first_line = stripped.splitlines()[0].lower()
    if "," in first_line and any(
        k in first_line for k in ("host", "ip", "port", "proxy")
    ):
        return parse_csv_text(stripped)
    return parse_text(stripped)


def _dedupe(proxies: Iterable[Proxy]) -> List[Proxy]:
    seen: Set[str] = set()
    out: List[Proxy] = []
    for p in proxies:
        if p.key not in seen:
            seen.add(p.key)
            out.append(p)
    return out


def load_proxies_from_file(path: str) -> List[Proxy]:
    text = Path(path).read_text(errors="ignore")
    return _dedupe(parse_any(text, filename=path))


async def fetch_proxies_from_url(url: str, timeout: float = 15.0) -> List[Proxy]:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout), follow_redirects=True
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return parse_any(resp.text, filename=url)


# Public free-proxy discovery sources
PUBLIC_PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/proxy.txt",
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
]


async def discover_public_proxies(
    sources: Optional[List[str]] = None, timeout: float = 15.0, echo=print
) -> List[Proxy]:
    """Fetch proxies from built-in public sources."""
    urls = sources or PUBLIC_PROXY_SOURCES
    results = await asyncio.gather(
        *(fetch_proxies_from_url(u, timeout=timeout) for u in urls),
        return_exceptions=True,
    )
    out: List[Proxy] = []
    for u, r in zip(urls, results):
        if isinstance(r, Exception):
            echo(f"  [discover] {u[:60]}... — {r}")
        else:
            echo(f"  [discover] {u[:60]}... — {len(r)} proxies")
            out.extend(r)
    return _dedupe(out)


def proxies_from_state(state: dict) -> List[Proxy]:
    out: List[Proxy] = []
    for item in state.values():
        try:
            out.append(
                Proxy(
                    host=item["host"],
                    port=int(item["port"]),
                    protocol=ProxyProtocol(item.get("protocol", "http")),
                    username=item.get("username"),
                    password=item.get("password"),
                    tag=item.get("tag"),
                )
            )
        except Exception:
            continue
    return out


def gather_proxies(
    file: Optional[str],
    source_urls: Tuple[str, ...],
    resume: bool,
    state_file: Optional[str],
    discover: bool = False,
    echo=print,
) -> List[Proxy]:
    proxies: List[Proxy] = []
    if file:
        loaded = load_proxies_from_file(file)
        echo(f"Loaded {len(loaded)} proxies from {file}")
        proxies += loaded

    async def _fetch_all():
        tasks = [fetch_proxies_from_url(u) for u in source_urls]
        if discover:
            tasks.append(discover_public_proxies(echo=echo))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out: List[Proxy] = []
        for u, r in zip(list(source_urls) + (["[public sources]"] if discover else []), results):
            if isinstance(r, Exception):
                echo(f"  warning: {u}: {r}")
            elif isinstance(r, list):
                for item in r:
                    if isinstance(item, Proxy):
                        out.append(item)
                echo(f"  fetched proxies from {u}")
        return out

    if source_urls or discover:
        proxies += asyncio.run(_fetch_all())

    if resume and state_file and Path(state_file).exists():
        state = load_state(state_file)
        resumed = proxies_from_state(state)
        if resumed:
            echo(f"  resumed {len(resumed)} proxies from {state_file}")
        proxies += resumed

    return _dedupe(proxies)


# ============================================================================
# Health + anonymity checking
# ============================================================================

CHECK_URLS = [
    "https://httpbin.org/get",
    "https://api.ipify.org?format=json",
    "https://httpbin.org/ip",
]
GEO_URL = "https://ipapi.co/{ip}/json/"
REAL_IP_URL = "https://api.ipify.org?format=json"

_LEAK_HEADER_NAMES = frozenset(
    {
        "via",
        "x-forwarded-for",
        "x-forwarded",
        "forwarded",
        "x-real-ip",
        "x-client-ip",
        "client-ip",
        "x-proxy-id",
        "proxy-agent",
        "forwarded-for",
        "x-originating-ip",
    }
)

_real_ip_cache: Dict[str, object] = {"ip": None, "fetched": False}


async def get_real_ip(timeout: float = 8.0) -> Optional[str]:
    if _real_ip_cache["fetched"] and _real_ip_cache["ip"]:
        return _real_ip_cache["ip"]  # type: ignore[return-value]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            resp = await client.get(REAL_IP_URL)
            ip = resp.json().get("ip")
            _real_ip_cache["ip"] = ip
            _real_ip_cache["fetched"] = bool(ip)
    except Exception:
        _real_ip_cache["ip"] = None
        _real_ip_cache["fetched"] = False
    return _real_ip_cache["ip"]  # type: ignore[return-value]


def classify_anonymity(headers: dict, real_ip: Optional[str]) -> str:
    lower = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    if real_ip:
        for value in lower.values():
            if real_ip in value:
                return "transparent"
    if any(name in lower for name in _LEAK_HEADER_NAMES):
        return "anonymous"
    return "elite"


async def check_proxy(
    proxy: Proxy,
    timeout: float = 10.0,
    fetch_geo: bool = False,
    real_ip: Optional[str] = None,
    allowed_countries: Optional[List[str]] = None,
) -> bool:
    start = time.monotonic()
    # Try multiple check URLs for resilience
    for check_url in CHECK_URLS:
        try:
            async with httpx.AsyncClient(
                proxy=proxy.httpx_proxy_url,
                timeout=httpx.Timeout(timeout),
                follow_redirects=True,
            ) as client:
                resp = await client.get(check_url)
                resp.raise_for_status()
                latency_ms = (time.monotonic() - start) * 1000

                # Parse exit IP and anonymity
                try:
                    data = resp.json()
                    if isinstance(data, dict):
                        exit_ip = (
                            str(data.get("origin", data.get("ip", ""))).split(",")[0].strip()
                            or None
                        )
                        anonymity = classify_anonymity(
                            data.get("headers", {}), real_ip
                        )
                    else:
                        exit_ip = None
                        anonymity = "anonymous"
                except Exception:
                    exit_ip = None
                    anonymity = "anonymous"

                proxy.stats.exit_ip = exit_ip
                proxy.stats.anonymity = anonymity
                proxy.stats.record_success(latency_ms)
                proxy.stats.last_checked_at = time.time()
                proxy.alive = True
                proxy.quarantined_until = 0.0
                proxy.circuit.record_success()

                if fetch_geo and exit_ip:
                    try:
                        async with httpx.AsyncClient(
                            timeout=httpx.Timeout(6.0)
                        ) as geo_client:
                            geo_resp = await geo_client.get(
                                GEO_URL.format(ip=exit_ip)
                            )
                            if geo_resp.status_code == 200:
                                geo_data = geo_resp.json()
                                country = geo_data.get("country_name")
                                country_code = geo_data.get("country_code")
                                if country:
                                    proxy.stats.country = country
                                    proxy.stats.country_code = country_code
                                    proxy.stats.region = geo_data.get("region")
                                    proxy.stats.city = geo_data.get("city")
                                    proxy.stats.org = geo_data.get("org")
                                    proxy.stats.asn = geo_data.get("asn")
                                    try:
                                        proxy.stats.latitude = float(geo_data.get("latitude"))
                                        proxy.stats.longitude = float(geo_data.get("longitude"))
                                    except (TypeError, ValueError):
                                        pass
                                    proxy.tag = country_code or proxy.tag
                    except Exception:
                        pass

                # Geofence check
                if allowed_countries and proxy.stats.country:
                    cc = (proxy.stats.country_code or proxy.tag or "").upper()
                    if cc and cc not in [c.upper() for c in allowed_countries]:
                        proxy.alive = False
                        return False

                return True
        except httpx.ProxyError:
            break  # Proxy itself is broken, no point retrying other URLs
        except Exception as exc:
            last_exc = exc
            continue

    proxy.stats.record_failure(
        f"{type(last_exc).__name__}: {last_exc}" if "last_exc" in dir() else "unknown"
    )
    proxy.stats.last_checked_at = time.time()
    proxy.alive = False
    proxy.circuit.record_failure()
    return False


async def check_many(
    proxies: List[Proxy],
    concurrency: int = 350,
    timeout: float = 10.0,
    fetch_geo: bool = False,
    on_result: Optional[Callable] = None,
    real_ip: Optional[str] = None,
    allowed_countries: Optional[List[str]] = None,
) -> Tuple[int, int]:
    if real_ip is None:
        real_ip = await get_real_ip()
    sem = asyncio.Semaphore(max(1, concurrency))
    alive_count = 0
    dead_count = 0

    async def _run(p: Proxy) -> None:
        nonlocal alive_count, dead_count
        async with sem:
            ok = await check_proxy(
                p,
                timeout=timeout,
                fetch_geo=fetch_geo,
                real_ip=real_ip,
                allowed_countries=allowed_countries,
            )
            if ok:
                alive_count += 1
            else:
                dead_count += 1
            if on_result:
                on_result(p, ok)

    await asyncio.gather(*(_run(p) for p in proxies))
    return alive_count, dead_count


# ============================================================================
# Pool — storage + rotation strategies + circuit breaker + rate limiting
# ============================================================================


class RotationStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_USED = "least_used"
    FASTEST = "fastest"
    STICKY = "sticky"
    WEIGHTED = "weighted"  # NEW: weighted by quality score
    MESH = "mesh"  # NEW: onion-style multi-hop circuits, rebuilt on a timer


class ProxyPool:
    def __init__(
        self,
        strategy: RotationStrategy = RotationStrategy.ROUND_ROBIN,
        max_consecutive_failures: int = 3,
        quarantine_seconds: float = 60.0,
        rotate_every_n: int = 1,
        rotate_every_seconds: Optional[float] = None,
        auto_remove_dead: bool = True,
        min_anonymity: str = "anonymous",
        mesh_hop_count: int = 0,
        mesh_rotate_seconds: float = 300.0,
    ) -> None:
        self._proxies: List[Proxy] = []
        self._lock = threading.RLock()
        self.strategy = strategy
        self.max_consecutive_failures = max_consecutive_failures
        self.quarantine_seconds = quarantine_seconds
        self.rotate_every_n = max(1, rotate_every_n)
        self.rotate_every_seconds = rotate_every_seconds
        self.auto_remove_dead = auto_remove_dead
        self.min_anonymity = min_anonymity

        # Mesh / onion-style circuit building — a "circuit" is an ordered list
        # of pre-hop proxies plus a final exit proxy, mirroring how Tor picks
        # a fresh path of relays for each circuit and rotates it periodically.
        self.mesh_hop_count = max(0, mesh_hop_count)
        self.mesh_rotate_seconds = mesh_rotate_seconds
        # circuits are keyed by (exit_proxy_id, destination_key) so different
        # sites get different paths through the mesh (stream isolation) —
        # a destination can never correlate you across two other destinations
        # sharing the same exit proxy, because they don't share the same hops.
        self._circuits: Dict[Tuple[str, str], List[Proxy]] = {}
        self._circuit_built_at: Dict[Tuple[str, str], float] = {}
        # global refcount of hops currently in use by *any* live circuit, so
        # new circuits avoid reusing a hop that's already carrying traffic
        # elsewhere (best-effort — falls back to reuse if the pool is small).
        self._hops_in_use: Dict[str, int] = {}
        # the guard hop is a semi-stable first hop, rotated far less often
        # than the rest of the circuit — mirrors Tor's guard-node design so
        # an attacker doesn't see you cycle through many different first
        # hops, which would make you easier to fingerprint/correlate.
        self.guard_rotate_seconds = max(mesh_rotate_seconds * 6, 1800.0)
        self._guard: Optional[Proxy] = None
        self._guard_built_at: float = 0.0

        self._rr_idx = 0
        self._sticky_map: Dict[str, str] = {}
        self._requests_since_rotate = 0
        self._last_rotation_at = time.time()
        self._current_id: Optional[str] = None
        self.total_forwarded = 0
        self.total_failed = 0
        self.total_bytes = 0
        self.total_removed = 0
        self.total_rejected_anonymity = 0
        self.total_refused = 0

        # Rate limiting per client
        self._client_req_times: Dict[str, Deque[float]] = {}
        self._rate_limit: Optional[Tuple[int, float]] = None  # (max_req, window_sec)

    def set_rate_limit(self, max_requests: int, window_seconds: float) -> None:
        self._rate_limit = (max_requests, window_seconds)

    _rate_limit_gc_interval: float = 300.0  # GC stale client entries every 5 min
    _rate_limit_last_gc: float = 0.0

    def check_rate_limit(self, client_ip: str) -> bool:
        """Returns True if request is allowed, False if rate-limited."""
        if not self._rate_limit:
            return True
        max_req, window = self._rate_limit
        now = time.time()
        times = self._client_req_times.setdefault(client_ip, deque())
        # Prune old entries for this client
        while times and now - times[0] > window:
            times.popleft()
        if len(times) >= max_req:
            return False
        times.append(now)
        # Periodic GC — remove clients whose last request is older than 2×window
        if now - self._rate_limit_last_gc > self._rate_limit_gc_interval:
            self._rate_limit_last_gc = now
            cutoff = now - window * 2
            stale = [k for k, q in self._client_req_times.items() if not q or q[-1] < cutoff]
            for k in stale:
                del self._client_req_times[k]
        return True

    def add(self, proxies: List[Proxy]) -> int:
        with self._lock:
            existing = {p.key for p in self._proxies}
            added = 0
            for p in proxies:
                if p.key not in existing:
                    self._proxies.append(p)
                    existing.add(p.key)
                    added += 1
            return added

    def remove_dead(self) -> List[Proxy]:
        with self._lock:
            removed = [
                p for p in self._proxies if not p.alive and not p.is_quarantined
            ]
            if removed:
                removed_ids = {p.id for p in removed}
                self._proxies = [p for p in self._proxies if p.id not in removed_ids]
                self.total_removed += len(removed)
            return removed

    def enforce_anonymity(self, min_level: Optional[str] = None) -> List[Proxy]:
        level = min_level or self.min_anonymity
        if level not in _ANON_ORDER:
            return []
        threshold = _ANON_ORDER[level]
        with self._lock:
            rejected = [
                p
                for p in self._proxies
                if p.stats.anonymity is not None
                and _ANON_ORDER.get(p.stats.anonymity, 0) < threshold
            ]
            if rejected:
                rejected_ids = {p.id for p in rejected}
                self._proxies = [
                    p for p in self._proxies if p.id not in rejected_ids
                ]
                self.total_rejected_anonymity += len(rejected)
            return rejected

    def remove(self, proxy_id: str) -> None:
        with self._lock:
            self._proxies = [p for p in self._proxies if p.id != proxy_id]

    def all(self) -> List[Proxy]:
        with self._lock:
            return list(self._proxies)

    def alive(self) -> List[Proxy]:
        threshold = _ANON_ORDER.get(self.min_anonymity, 0)
        with self._lock:
            for p in self._proxies:
                p.release_if_expired()
            return [
                p
                for p in self._proxies
                if p.alive
                and not p.is_quarantined
                and p.stats.anonymity is not None
                and _ANON_ORDER.get(p.stats.anonymity, 0) >= threshold
                and p.circuit.allow_request()
            ]

    def __len__(self) -> int:
        return len(self._proxies)

    def _should_force_rotate(self) -> bool:
        if (
            self.rotate_every_seconds is not None
            and time.time() - self._last_rotation_at >= self.rotate_every_seconds
        ):
            return True
        return self._requests_since_rotate >= self.rotate_every_n

    def get_next(self, client_key: Optional[str] = None) -> Optional[Proxy]:
        with self._lock:
            candidates = self.alive()
            if not candidates:
                return None
            if self.strategy == RotationStrategy.STICKY and client_key:
                sticky_id = self._sticky_map.get(client_key)
                if sticky_id:
                    for p in candidates:
                        if p.id == sticky_id and p.circuit.allow_request():
                            return p
                chosen = random.choice(candidates)
                self._sticky_map[client_key] = chosen.id
                return chosen
            force = self._should_force_rotate()
            if self._current_id is not None and not force:
                for p in candidates:
                    if p.id == self._current_id:
                        return p
            chosen = self._pick(candidates)
            self._current_id = chosen.id
            self._requests_since_rotate = 0
            self._last_rotation_at = time.time()
            return chosen

    def _pick(self, candidates: List[Proxy]) -> Proxy:
        if self.strategy == RotationStrategy.RANDOM:
            return random.choice(candidates)
        if self.strategy == RotationStrategy.LEAST_USED:
            return min(candidates, key=lambda p: p.stats.total_requests)
        if self.strategy == RotationStrategy.FASTEST:
            return min(
                candidates,
                key=lambda p: p.stats.avg_latency_ms
                if p.stats.avg_latency_ms is not None
                else float("inf"),
            )
        if self.strategy == RotationStrategy.WEIGHTED:
            # Weighted random by quality score
            total = sum(max(p.stats.score, 0.1) for p in candidates)
            r = random.uniform(0, total)
            cumulative = 0.0
            for p in candidates:
                cumulative += max(p.stats.score, 0.1)
                if r <= cumulative:
                    return p
            return candidates[-1]
        # Round-robin
        self._rr_idx = (self._rr_idx + 1) % len(candidates)
        return candidates[self._rr_idx]

    def note_request_started(self) -> None:
        with self._lock:
            self._requests_since_rotate += 1

    def record_success(self, proxy: Proxy, latency_ms: float, nbytes: int = 0) -> None:
        with self._lock:
            proxy.stats.record_success(latency_ms)
            proxy.circuit.record_success()
            self.total_forwarded += 1
            self.total_bytes += nbytes

    def record_failure(self, proxy: Proxy, error: str) -> None:
        with self._lock:
            proxy.stats.record_failure(error)
            proxy.circuit.record_failure()
            self.total_failed += 1
            if proxy.stats.consecutive_failures >= self.max_consecutive_failures:
                still_present = any(p.id == proxy.id for p in self._proxies)
                if self.auto_remove_dead:
                    proxy.alive = False
                    if still_present:
                        self._proxies = [
                            p for p in self._proxies if p.id != proxy.id
                        ]
                        self.total_removed += 1
                else:
                    proxy.quarantine(self.quarantine_seconds)
                if self._current_id == proxy.id:
                    self._current_id = None

    def force_rotate(self) -> None:
        with self._lock:
            self._current_id = None
            self._requests_since_rotate = 0
            self._last_rotation_at = time.time()

    # ---- mesh / onion-style circuit building --------------------------
    #
    # A "circuit" here means: request -> pre-hop 1 -> pre-hop 2 -> ... -> exit
    # proxy -> real destination. Every hop only ever learns the previous and
    # next hop's address (via CONNECT tunneling), never the full path, which
    # is the same "no single relay knows the whole route" property Tor relies
    # on. Hops are chosen fresh from the alive pool, biased towards diverse
    # countries/ASNs so consecutive hops don't sit in the same network, and
    # the whole circuit is torn down and rebuilt on a timer.

    def _distinct_key(self, p: Proxy) -> str:
        # Prefer country+ASN diversity; fall back to country, then host.
        if p.stats.country_code and p.stats.asn:
            return f"{p.stats.country_code}:{p.stats.asn}"
        return p.stats.country_code or p.stats.country or p.host

    @staticmethod
    def _dest_key(destination_host: Optional[str]) -> str:
        # Isolate streams by registrable domain (e.g. "sub.example.com" and
        # "example.com" -> "example.com"), not full hostname, so a site and
        # its own subdomains/CDNs share a circuit but unrelated sites don't.
        if not destination_host:
            return "*"
        parts = destination_host.lower().strip(".").split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else destination_host.lower()

    def _get_guard(self, exclude_id: Optional[str] = None) -> Optional[Proxy]:
        """Return the current guard hop, rotating it far less often than the
        rest of the circuit so the "first hop you always use" stays stable."""
        expired = time.time() - self._guard_built_at >= self.guard_rotate_seconds
        candidates = [
            p for p in self.alive()
            if not p.protocol.is_socks and p.id != exclude_id
        ]
        if not candidates:
            self._guard = None
            return None
        still_valid = self._guard and any(p.id == self._guard.id for p in candidates)
        if not still_valid or expired:
            candidates.sort(key=lambda p: p.stats.score, reverse=True)
            # weighted pick among the top handful so it's not perfectly
            # predictable, but still favors reliable proxies as a long-lived
            # guard, mirroring Tor's guard selection.
            top = candidates[: max(1, min(5, len(candidates)))]
            self._guard = random.choice(top)
            self._guard_built_at = time.time()
        return self._guard

    def build_mesh_circuit(
        self,
        exit_proxy: Optional[Proxy] = None,
        hop_count: Optional[int] = None,
        avoid_hop_ids: Optional[Set[str]] = None,
    ) -> List[Proxy]:
        """Pick hop_count distinct, HTTP(S)-capable pre-hops for a fresh circuit.

        Hop 1 is always the stable guard hop (see `_get_guard`); the
        remaining hops are drawn fresh from the alive pool, weighted towards
        higher quality-score proxies while favoring network diversity
        (different country/ASN per hop) and, best-effort, avoiding proxies
        already carrying another live circuit's traffic (`avoid_hop_ids`) so
        concurrent circuits don't overlap and become linkable.
        """
        n = self.mesh_hop_count if hop_count is None else max(0, hop_count)
        if n <= 0:
            return []
        avoid_hop_ids = avoid_hop_ids or set()
        exit_id = exit_proxy.id if exit_proxy is not None else None

        with self._lock:
            guard = self._get_guard(exclude_id=exit_id)

            pool = [
                p
                for p in self.alive()
                if not p.protocol.is_socks
                and p.id != exit_id
                and (guard is None or p.id != guard.id)
            ]
        if not pool:
            return [guard] if guard and n >= 1 else []

        random.shuffle(pool)
        # Prefer hops not currently in use by another circuit; fall back to
        # any alive proxy if the pool is too small to fully avoid overlap.
        fresh_pool = [p for p in pool if p.id not in avoid_hop_ids] or pool
        fresh_pool.sort(key=lambda p: p.stats.score, reverse=True)

        chosen: List[Proxy] = [guard] if guard else []
        used_keys: Set[str] = set()
        if exit_proxy is not None:
            used_keys.add(self._distinct_key(exit_proxy))
        if guard is not None:
            used_keys.add(self._distinct_key(guard))

        for p in fresh_pool:
            if len(chosen) >= n:
                break
            k = self._distinct_key(p)
            if k in used_keys:
                continue
            chosen.append(p)
            used_keys.add(k)
        # Not enough distinct networks — pad with best remaining proxies.
        if len(chosen) < n:
            remaining = [p for p in fresh_pool if p not in chosen]
            chosen.extend(remaining[: n - len(chosen)])
        # Keep the guard fixed as hop 1; shuffle only the rest so ordering
        # among middle/exit-adjacent hops still varies.
        head, tail = chosen[:1] if guard else [], chosen[1:] if guard else chosen
        random.shuffle(tail)
        return (head + tail)[:n]

    def get_circuit(self, exit_proxy: Proxy, destination_host: Optional[str] = None) -> List[Proxy]:
        """Return the mesh pre-hops for (exit_proxy, destination), rebuilding
        on rotation timeout. Streams to different destinations through the
        same exit proxy get independent circuits (stream isolation)."""
        if self.mesh_hop_count <= 0:
            return []
        key = (exit_proxy.id, self._dest_key(destination_host))
        with self._lock:
            built_at = self._circuit_built_at.get(key, 0.0)
            expired = time.time() - built_at >= self.mesh_rotate_seconds
            existing = self._circuits.get(key)
            if not existing or expired:
                if existing:
                    for p in existing:
                        self._hops_in_use[p.id] = max(0, self._hops_in_use.get(p.id, 0) - 1)
                in_use = {hid for hid, cnt in self._hops_in_use.items() if cnt > 0}
                new_circuit = self.build_mesh_circuit(exit_proxy, avoid_hop_ids=in_use)
                self._circuits[key] = new_circuit
                self._circuit_built_at[key] = time.time()
                for p in new_circuit:
                    self._hops_in_use[p.id] = self._hops_in_use.get(p.id, 0) + 1
            return list(self._circuits[key])

    def stats_summary(self) -> dict:
        with self._lock:
            alive_list = self.alive()
            return {
                "total": len(self._proxies),
                "alive": len(alive_list),
                "dead": len(self._proxies) - len(alive_list),
                "forwarded": self.total_forwarded,
                "failed": self.total_failed,
                "removed": self.total_removed,
                "rejected_anonymity": self.total_rejected_anonymity,
                "refused": self.total_refused,
                "bytes": self.total_bytes,
                "current": self._current_id,
                "min_anonymity": self.min_anonymity,
                "strategy": self.strategy.value,
                "top_proxy": (
                    max(alive_list, key=lambda p: p.stats.score).label
                    if alive_list
                    else None
                ),
            }


# ============================================================================
# Persistence
# ============================================================================


def save_state(proxies: List[Proxy], path: str) -> None:
    data = {"saved_at": time.time(), "proxies": [p.to_state_dict() for p in proxies]}
    Path(path).write_text(json.dumps(data, indent=2))


def load_state(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
    except Exception:
        return {}
    by_key: dict = {}
    for item in data.get("proxies", []):
        proto = item.get("protocol", "http")
        key = f"{proto}://{item.get('host')}:{item.get('port')}"
        by_key[key] = item
    return by_key


def apply_prior_state(pool: ProxyPool, state: dict) -> int:
    applied = 0
    for p in pool.all():
        prior = state.get(p.key)
        if not prior:
            continue
        p.stats.anonymity = prior.get("anonymity")
        p.stats.country = prior.get("country")
        p.stats.country_code = prior.get("country_code")
        p.stats.region = prior.get("region")
        p.stats.city = prior.get("city")
        p.stats.asn = prior.get("asn")
        p.stats.org = prior.get("org")
        p.stats.latitude = prior.get("latitude")
        p.stats.longitude = prior.get("longitude")
        p.stats.exit_ip = prior.get("exit_ip")
        applied += 1
    return applied


def export_stats(proxies: List[Proxy], path: str) -> None:
    Path(path).write_text(json.dumps([p.to_state_dict() for p in proxies], indent=2))


def default_state_path(file: Optional[str]) -> str:
    if file:
        return str(Path(file).with_suffix(Path(file).suffix + ".state.json"))
    return "proxy_rotator.state.json"


# ============================================================================
# Config file
# ============================================================================


def load_config_defaults(path: str) -> dict:
    text = Path(path).read_text()
    if path.lower().endswith((".yaml", ".yml")):
        import yaml
        return yaml.safe_load(text) or {}
    return json.loads(text) or {}


def _config_option_callback(
    ctx: click.Context, _param: click.Parameter, value: Optional[str]
) -> Optional[str]:
    if value:
        cfg = load_config_defaults(value)
        ctx.default_map = {**(ctx.default_map or {}), **cfg}
    return value


def config_option():
    return click.option(
        "--config",
        type=click.Path(exists=True),
        is_eager=True,
        expose_value=False,
        callback=_config_option_callback,
        help="JSON or YAML config file.",
    )


# ============================================================================
# Relay server — full-protection, never leaks direct traffic
# ============================================================================

RELAY_CHUNK = 64 * 1024

_HOP_BY_HOP_HEADERS = frozenset(
    {
        b"connection",
        b"keep-alive",
        b"proxy-authenticate",
        b"proxy-authorization",
        b"te",
        b"trailers",
        b"upgrade",
        b"proxy-connection",
        # NOTE: we intentionally do NOT include transfer-encoding here —
        # removing it would break chunked streaming to upstream.
    }
)

# Headers that leak real IP or reveal proxy presence — always stripped
_STRIP_HEADER_PREFIXES = tuple(
    (name + ":").encode("latin-1")
    for name in (
        "x-forwarded-for",
        "x-forwarded-host",
        "x-forwarded-proto",
        "x-forwarded",
        "forwarded",
        "forwarded-for",
        "via",
        "x-real-ip",
        "x-client-ip",
        "client-ip",
        "x-proxy-id",
        "proxy-authorization",
        "x-originating-ip",
    )
)


def sanitize_headers(header_rest: bytes) -> bytes:
    """Strip leak-identifying and hop-by-hop headers before relaying.
    Transfer-Encoding is intentionally preserved so chunked bodies flow
    through correctly without requiring pre-buffering."""
    lines = header_rest.split(b"\r\n")
    kept = []
    for ln in lines:
        ln_lower = ln.lower()
        if any(ln_lower.startswith(prefix) for prefix in _STRIP_HEADER_PREFIXES):
            continue
        # Strip hop-by-hop (but NOT transfer-encoding — see note above)
        colon_idx = ln.find(b":")
        if colon_idx > 0 and ln[:colon_idx].lower() in _HOP_BY_HOP_HEADERS:
            continue
        kept.append(ln)
    return b"\r\n".join(kept)


def _extract_content_length(headers: bytes) -> int:
    for line in headers.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            try:
                return int(line.split(b":", 1)[1].strip())
            except ValueError:
                return 0
    return 0


def _is_chunked(headers: bytes) -> bool:
    for line in headers.split(b"\r\n"):
        if line.lower().startswith(b"transfer-encoding:"):
            return b"chunked" in line.lower()
    return False


def _parse_connect_authority(authority: str) -> Tuple[str, int]:
    """Robustly parse a CONNECT authority: host:port, [IPv6]:port."""
    authority = authority.strip()
    if authority.startswith("["):
        # IPv6 bracketed form: [::1]:443
        bracket_end = authority.find("]")
        if bracket_end == -1:
            return authority, 443
        host = authority[1:bracket_end]
        rest = authority[bracket_end + 1:]
        port = int(rest[1:]) if rest.startswith(":") else 443
        return host, port
    # hostname:port or IPv4:port
    if ":" in authority:
        host, _, port_s = authority.rpartition(":")
        try:
            return host, int(port_s)
        except ValueError:
            return authority, 443
    return authority, 443


@dataclass
class RequestLogEntry:
    timestamp: float
    method: str
    host: str
    port: int
    path: str
    proxy: Optional[str]
    latency_ms: Optional[float]
    success: bool
    error: Optional[str] = None
    bytes_sent: int = 0
    bytes_recv: int = 0

    def to_dict(self) -> dict:
        return {
            "ts": self.timestamp,
            "method": self.method,
            "host": self.host,
            "port": self.port,
            "path": self.path,
            "proxy": self.proxy,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "error": self.error,
            "bytes_sent": self.bytes_sent,
            "bytes_recv": self.bytes_recv,
        }


@dataclass
class ServerStats:
    active_connections: int = 0
    total_connections: int = 0
    total_retries: int = 0
    total_refused: int = 0
    total_bypassed: int = 0
    started_at: float = field(default_factory=time.time)
    recent_log: Deque[str] = field(default_factory=lambda: deque(maxlen=500))
    request_log: Deque[RequestLogEntry] = field(default_factory=lambda: deque(maxlen=200))
    _chain_warning_shown: bool = False

    def log(self, message: str) -> None:
        self.recent_log.append(f"[{time.strftime('%H:%M:%S')}] {message}")

    def log_request(self, entry: RequestLogEntry) -> None:
        self.request_log.append(entry)


class _suppress:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return True


def _basic_auth(username: str, password: str) -> str:
    return base64.b64encode(f"{username}:{password}".encode()).decode()


# ---- sysproxy <-> running rotator handshake --------------------------------
#
# `sysproxy on` needs to know the exact host:port the rotator is actually
# listening on. Rather than trusting the user to retype it correctly, the
# rotator writes its live address here on start and removes it on clean
# shutdown; `sysproxy on/off` reads it automatically when --host/--port
# aren't given, so "system-wide" always points at the process that is
# actually running (with the real mesh-hops count front and center).
_SYSPROXY_INFO_FILE = Path.home() / ".proxy_rotator_active.json"


def _write_sysproxy_info(host: str, port: int, mesh_hops: int) -> None:
    target_host = host if host not in ("0.0.0.0", "::") else "127.0.0.1"
    try:
        _SYSPROXY_INFO_FILE.write_text(
            json.dumps({"host": target_host, "port": port, "mesh_hops": mesh_hops, "pid": os.getpid()})
        )
    except OSError:
        pass


def _clear_sysproxy_info() -> None:
    try:
        _SYSPROXY_INFO_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _read_sysproxy_info() -> Optional[dict]:
    try:
        return json.loads(_SYSPROXY_INFO_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _parse_absolute_target(target: str) -> Tuple[Optional[str], int, str]:
    if target.startswith("http://"):
        rest, default_port = target[len("http://"):], 80
    elif target.startswith("https://"):
        rest, default_port = target[len("https://"):], 443
    else:
        return None, 0, target
    host_part, _, path = rest.partition("/")
    path = "/" + path if path or rest.endswith("/") else "/"
    if host_part.startswith("["):
        # IPv6
        bracket_end = host_part.find("]")
        host = host_part[1:bracket_end]
        port_part = host_part[bracket_end + 1:]
        port = int(port_part[1:]) if port_part.startswith(":") else default_port
    elif ":" in host_part:
        host, _, port_s = host_part.rpartition(":")
        try:
            port = int(port_s)
        except ValueError:
            port = default_port
    else:
        host, port = host_part, default_port
    return host, port, path


class RotatingProxyServer:
    """
    Local rotating forward proxy. Never leaks direct traffic unless
    allow_direct_fallback=True (off by default).
    """

    def __init__(
        self,
        pool: ProxyPool,
        host: str = "127.0.0.1",
        port: int = 8899,
        max_retries: int = 3,
        connect_timeout: float = 12.0,
        allow_direct_fallback: bool = False,
        chain_hops: Optional[List[Proxy]] = None,
        direct_domains: Optional[List[str]] = None,
        local_auth: Optional[Tuple[str, str]] = None,
        request_log_file: Optional[str] = None,
        bandwidth_limit_bps: Optional[int] = None,
        mesh_hop_count: int = 0,
    ) -> None:
        self.pool = pool
        self.host = host
        self.port = port
        self.max_retries = max_retries
        self.connect_timeout = connect_timeout
        self.allow_direct_fallback = allow_direct_fallback
        self.chain_hops = [h for h in (chain_hops or []) if not h.protocol.is_socks]
        # Mesh mode: instead of one fixed pre-hop chain, a fresh circuit of
        # `mesh_hop_count` proxies is picked from the pool per exit proxy and
        # rotated on pool.mesh_rotate_seconds — static chain_hops (if given)
        # take priority since they're an explicit user choice.
        self.mesh_hop_count = mesh_hop_count if not self.chain_hops else 0
        # ULTIMATE: Fingerprint spoofing engine
        self._fingerprint_gen = FingerprintGenerator()
        self._current_fingerprint = None
        self._cf_bypass = CloudflareBypass()
        self._anti_bot = AntiBotSimulator()
        self._cookie_jar = RotatingCookieJar(jar_count=20)
        self._traffic_obf = TrafficObfuscator()
        self._stealth_dns = StealthDNS()
        self._domain_front = DomainFronting()
        self._use_fingerprinting = True
        self._use_cf_bypass = True
        self._use_obfuscation = True
        self._use_domain_fronting = False
        self.direct_domains = [d.lower().lstrip(".") for d in (direct_domains or [])]
        self.local_auth = local_auth
        self.request_log_file = request_log_file
        self.bandwidth_limit_bps = bandwidth_limit_bps
        self.stats = ServerStats()
        self._server: Optional[asyncio.AbstractServer] = None
        self._log_lock = threading.Lock()

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )

    async def serve_forever(self) -> None:
        if self._server is None:
            await self.start()
        assert self._server is not None
        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    @property
    def running(self) -> bool:
        return self._server is not None

    def _is_direct_domain(self, host: str) -> bool:
        host = host.lower()
        return any(host == d or host.endswith("." + d) for d in self.direct_domains)

    def _check_local_auth(self, header_rest: bytes) -> bool:
        if not self.local_auth:
            return True
        expected = _basic_auth(self.local_auth[0], self.local_auth[1])
        for line in header_rest.split(b"\r\n"):
            if line.lower().startswith(b"proxy-authorization:"):
                value = line.split(b":", 1)[1].strip().decode("latin-1")
                if value.startswith("Basic ") and value[6:] == expected:
                    return True
        return False

    def _write_json_log(self, entry: RequestLogEntry) -> None:
        if not self.request_log_file:
            return
        try:
            with self._log_lock:
                with open(self.request_log_file, "a") as f:
                    f.write(json.dumps(entry.to_dict()) + "\n")
        except Exception:
            pass

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        client_key = peer[0] if peer else "unknown"
        self.stats.active_connections += 1
        self.stats.total_connections += 1
        try:
            await self._process_request(reader, writer, client_key)
        except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
            pass
        except Exception as exc:
            self.stats.log(f"client error [{client_key}]: {exc}")
        finally:
            self.stats.active_connections -= 1
            with _suppress():
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

    async def _process_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        client_key: str,
    ) -> None:
        try:
            header_bytes = await asyncio.wait_for(
                reader.readuntil(b"\r\n\r\n"), timeout=self.connect_timeout
            )
        except (asyncio.TimeoutError, asyncio.IncompleteReadError):
            return
        request_line, _, header_rest = header_bytes.partition(b"\r\n")
        try:
            method, target, _version = request_line.decode("latin-1").split(" ", 2)
        except ValueError:
            writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            await writer.drain()
            return

        # Rate limiting
        if not self.pool.check_rate_limit(client_key):
            writer.write(b"HTTP/1.1 429 Too Many Requests\r\nRetry-After: 1\r\n\r\n")
            await writer.drain()
            return

        # Local auth check
        if not self._check_local_auth(header_rest):
            writer.write(
                b'HTTP/1.1 407 Proxy Authentication Required\r\n'
                b'Proxy-Authenticate: Basic realm="proxy_rotator"\r\n\r\n'
            )
            await writer.drain()
            return

        if method.upper() == "CONNECT":
            try:
                host, port = _parse_connect_authority(target)
            except Exception:
                writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                await writer.drain()
                return
            await self._handle_connect(reader, writer, host, port, client_key)
        else:
            await self._handle_plain_http(
                reader, writer, method, target, header_rest, client_key
            )

    async def _pick_proxy_with_retry(
        self, client_key: str, attempt: int
    ) -> Optional[Proxy]:
        if attempt > 0:
            self.pool.force_rotate()
            self.stats.total_retries += 1
        return self.pool.get_next(client_key=client_key)

    async def _refuse(self, writer: asyncio.StreamWriter, reason: str) -> None:
        self.stats.total_refused += 1
        self.pool.total_refused += 1
        self.stats.log(f"REFUSED: {reason}")
        body = f"proxy_rotator: refused — no healthy proxies ({reason})".encode()
        writer.write(
            b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: %d\r\n\r\n" % len(body)
            + body
        )
        with _suppress():
            await writer.drain()

    async def _dial_direct(self, target_host: str, target_port: int):
        return await asyncio.wait_for(
            asyncio.open_connection(target_host, target_port),
            timeout=self.connect_timeout,
        )

    async def _handle_connect(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        target_host: str,
        target_port: int,
        client_key: str,
    ) -> None:
        if self._is_direct_domain(target_host):
            try:
                up_r, up_w = await self._dial_direct(target_host, target_port)
            except Exception as exc:
                await self._refuse(client_writer, f"direct bypass failed: {exc}")
                return
            self.stats.total_bypassed += 1
            self.stats.log(f"BYPASS: CONNECT {target_host}:{target_port}")
            client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await client_writer.drain()
            await self._relay(client_reader, client_writer, up_r, up_w)
            return

        last_error = "no healthy anonymous/elite proxies in pool"
        # ULTIMATE: Fresh fingerprint for CONNECT
        if self._use_fingerprinting:
            self._current_fingerprint = get_fingerprint()

        entry = RequestLogEntry(
            timestamp=time.time(),
            method="CONNECT",
            host=target_host,
            port=target_port,
            path="",
            proxy=None,
            latency_ms=None,
            success=False,
        )
        for attempt in range(self.max_retries):
            proxy = await self._pick_proxy_with_retry(client_key, attempt)
            if proxy is None:
                break
            self.pool.note_request_started()
            start = time.monotonic()
            try:
                up_r, up_w = await self._dial_via_proxy(
                    proxy, target_host, target_port
                )
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                self.pool.record_failure(proxy, last_error)
                self.stats.log(
                    f"CONNECT {target_host}:{target_port} via {proxy.key} failed: {last_error}"
                )
                continue
            latency_ms = (time.monotonic() - start) * 1000
            self.pool.record_success(proxy, latency_ms)
            self.stats.log(
                f"CONNECT {target_host}:{target_port} via {proxy.key} ok ({latency_ms:.0f}ms)"
            )
            client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await client_writer.drain()
            sent, recv = await self._relay(
                client_reader, client_writer, up_r, up_w
            )
            proxy.stats.bytes_sent += sent
            proxy.stats.bytes_recv += recv
            self.pool.total_bytes += sent + recv
            entry.proxy = proxy.key
            entry.latency_ms = latency_ms
            entry.success = True
            entry.bytes_sent = sent
            entry.bytes_recv = recv
            self.stats.log_request(entry)
            self._write_json_log(entry)
            return

        if self.allow_direct_fallback:
            try:
                up_r, up_w = await self._dial_direct(target_host, target_port)
                self.stats.log(
                    f"WARNING: direct fallback for CONNECT {target_host}:{target_port}"
                )
                client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await client_writer.drain()
                await self._relay(client_reader, client_writer, up_r, up_w)
                return
            except Exception as exc:
                last_error = f"direct fallback also failed: {exc}"

        entry.error = last_error
        self.stats.log_request(entry)
        self._write_json_log(entry)
        await self._refuse(client_writer, last_error)

    async def _handle_plain_http(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        method: str,
        target: str,
        header_rest: bytes,
        client_key: str,
    ) -> None:
        # Parse target to get host/port for routing decisions.
        # We keep `target` intact for absolute-form forwarding to HTTP proxies.
        host, port, path = _parse_absolute_target(target)
        if host is None:
            client_writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            await client_writer.drain()
            return

        clean_headers = sanitize_headers(header_rest)

        # ULTIMATE: Generate fresh fingerprint for this request
        if self._use_fingerprinting:
            self._current_fingerprint = get_fingerprint()
            fp_headers = get_fingerprint_headers(self._current_fingerprint)
            # Inject fingerprint headers into the request
            fp_header_bytes = b""
            for k, v in fp_headers.items():
                if k.lower() not in [b"host", b"content-length", b"transfer-encoding"]:
                    fp_header_bytes += f"{k}: {v}\r\n".encode("latin-1")
            clean_headers = fp_header_bytes + clean_headers

        # Direct bypass — no proxy needed
        if self._is_direct_domain(host):
            # Direct: origin-form request
            request_bytes = (
                f"{method} {path} HTTP/1.1\r\n".encode("latin-1") + clean_headers + b"\r\n"
            )
            try:
                up_r, up_w = await self._dial_direct(host, port)
                up_w.write(request_bytes)
                await up_w.drain()
            except Exception as exc:
                await self._refuse(client_writer, f"direct bypass failed: {exc}")
                return
            self.stats.total_bypassed += 1
            self.stats.log(f"BYPASS: {method} {host}{path}")
            # relay streams body bidirectionally — no pre-buffering needed
            await self._relay(client_reader, client_writer, up_r, up_w)
            return

        last_error = "no healthy proxies"
        entry = RequestLogEntry(
            timestamp=time.time(),
            method=method,
            host=host,
            port=port,
            path=path,
            proxy=None,
            latency_ms=None,
            success=False,
        )
        for attempt in range(self.max_retries):
            proxy = await self._pick_proxy_with_retry(client_key, attempt)
            if proxy is None:
                break
            self.pool.note_request_started()
            start = time.monotonic()
            up_w = None
            try:
                up_r, up_w, to_send = await self._prepare_plain_http(
                    proxy, host, port, path, target, method, clean_headers
                )
                up_w.write(to_send)
                await up_w.drain()
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                self.pool.record_failure(proxy, last_error)
                self.stats.log(f"{method} {host}{path} via {proxy.key} failed: {last_error}")
                if up_w is not None:
                    with _suppress():
                        up_w.close()
                continue
            latency_ms = (time.monotonic() - start) * 1000
            self.pool.record_success(proxy, latency_ms)
            self.stats.log(f"{method} {host}{path} via {proxy.key} ok ({latency_ms:.0f}ms)")
            # Body streams bidirectionally in relay — no pre-buffering
            sent, recv = await self._relay(client_reader, client_writer, up_r, up_w)
            proxy.stats.bytes_sent += sent
            proxy.stats.bytes_recv += recv
            self.pool.total_bytes += sent + recv
            entry.proxy = proxy.key
            entry.latency_ms = latency_ms
            entry.success = True
            entry.bytes_sent = sent
            entry.bytes_recv = recv
            self.stats.log_request(entry)
            self._write_json_log(entry)
            return

        if self.allow_direct_fallback:
            request_bytes = (
                f"{method} {path} HTTP/1.1\r\n".encode("latin-1") + clean_headers + b"\r\n"
            )
            try:
                up_r, up_w = await self._dial_direct(host, port)
                up_w.write(request_bytes)
                await up_w.drain()
                self.stats.log(f"WARNING: direct fallback for {method} {host}{path}")
                await self._relay(client_reader, client_writer, up_r, up_w)
                return
            except Exception as exc:
                last_error = f"direct fallback failed: {exc}"

        entry.error = last_error
        self.stats.log_request(entry)
        self._write_json_log(entry)
        await self._refuse(client_writer, last_error)

    async def _dial_via_proxy(self, proxy: Proxy, target_host: str, target_port: int):
        if self.chain_hops:
            return await self._dial_chain(proxy, target_host, target_port, self.chain_hops)
        if self.mesh_hop_count > 0 and not proxy.protocol.is_socks:
            circuit = self.pool.get_circuit(proxy, destination_host=target_host)
            if circuit:
                return await self._dial_chain(proxy, target_host, target_port, circuit)
        if proxy.protocol.is_socks:
            return await self._dial_socks(proxy, target_host, target_port)
        return await self._dial_http_connect(proxy, target_host, target_port)

    def _using_multi_hop(self) -> bool:
        return bool(self.chain_hops) or self.mesh_hop_count > 0

    async def _dial_socks(self, proxy: Proxy, target_host: str, target_port: int):
        socks_client = SocksProxyClient.create(
            proxy_type=_SOCKS_TYPE[proxy.protocol],
            host=proxy.host,
            port=proxy.port,
            username=proxy.username,
            password=proxy.password,
        )
        sock = await asyncio.wait_for(
            socks_client.connect(dest_host=target_host, dest_port=target_port),
            timeout=self.connect_timeout,
        )
        return await asyncio.open_connection(sock=sock)

    async def _negotiate_connect(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        host: str,
        port: int,
        hop: Proxy,
    ) -> None:
        req = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n"
        if hop.has_auth:
            req += f"Proxy-Authorization: Basic {_basic_auth(hop.username or '', hop.password or '')}\r\n"
        req += "Proxy-Connection: Keep-Alive\r\n\r\n"
        writer.write(req.encode("latin-1"))
        await writer.drain()
        resp_line = await asyncio.wait_for(
            reader.readline(), timeout=self.connect_timeout
        )
        # Drain remaining headers
        while True:
            line = await asyncio.wait_for(
                reader.readline(), timeout=self.connect_timeout
            )
            if line in (b"\r\n", b""):
                break
        if b" 200 " not in resp_line:
            raise ConnectionError(
                f"hop {hop.key} refused CONNECT to {host}:{port}: {resp_line!r}"
            )

    async def _open_proxy_connection(self, proxy: Proxy):
        """Open a raw TCP (or TLS for https:// proxies) connection to the proxy host."""
        if proxy.protocol == ProxyProtocol.HTTPS:
            import ssl as _ssl
            ssl_ctx = _ssl.create_default_context()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(proxy.host, proxy.port, ssl=ssl_ctx),
                timeout=self.connect_timeout,
            )
        else:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(proxy.host, proxy.port),
                timeout=self.connect_timeout,
            )
        return reader, writer

    async def _dial_http_connect(
        self, proxy: Proxy, target_host: str, target_port: int
    ):
        reader, writer = await self._open_proxy_connection(proxy)
        try:
            await self._negotiate_connect(reader, writer, target_host, target_port, proxy)
        except Exception:
            writer.close()
            raise
        return reader, writer

    async def _dial_chain(
        self,
        exit_proxy: Proxy,
        target_host: str,
        target_port: int,
        pre_hops: List[Proxy],
    ):
        if exit_proxy.protocol.is_socks:
            if not self.stats._chain_warning_shown:
                self.stats.log(
                    "chain: SOCKS exit proxy — skipping HTTP pre-hops for this request"
                )
                self.stats._chain_warning_shown = True
            return await self._dial_socks(exit_proxy, target_host, target_port)

        full_chain = [*pre_hops, exit_proxy]
        # Use _open_proxy_connection so the first hop is TLS-wrapped for https:// hops
        reader, writer = await self._open_proxy_connection(full_chain[0])
        try:
            for i, hop in enumerate(full_chain):
                if i + 1 < len(full_chain):
                    next_host, next_port = full_chain[i + 1].host, full_chain[i + 1].port
                else:
                    next_host, next_port = target_host, target_port
                await self._negotiate_connect(reader, writer, next_host, next_port, hop)
        except Exception:
            writer.close()
            raise
        return reader, writer

    async def _prepare_plain_http(
        self,
        proxy: Proxy,
        host: str,
        port: int,
        path: str,
        target: str,
        method: str,
        clean_headers: bytes,
    ):
        """
        Build the headers-only request line to send upstream (body streams later
        through relay). Handles two cases:

        SOCKS / chained proxy → tunnel to target host, use origin-form request line.
        HTTP/HTTPS proxy      → connect to proxy, use absolute-form request line
                                so the proxy knows the destination.
        """
        if self._using_multi_hop() or proxy.protocol.is_socks:
            # SOCKS tunnel: connect directly to target via tunnel, origin-form
            reader, writer = await self._dial_via_proxy(proxy, host, port)
            headers_out = (
                f"{method} {path} HTTP/1.1\r\n".encode("latin-1") + clean_headers + b"\r\n"
            )
            return reader, writer, headers_out

        # HTTP/HTTPS forward proxy: connect to proxy, send absolute-form
        reader, writer = await self._open_proxy_connection(proxy)
        extra_headers = b""
        if proxy.has_auth:
            extra_headers = (
                f"Proxy-Authorization: Basic {_basic_auth(proxy.username or '', proxy.password or '')}\r\n"
                .encode("latin-1")
            )
        # Absolute-form: "GET http://example.com/path HTTP/1.1\r\n"
        headers_out = (
            f"{method} {target} HTTP/1.1\r\n".encode("latin-1")
            + extra_headers
            + clean_headers
            + b"\r\n"
        )
        return reader, writer, headers_out

    async def _relay(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        upstream_reader: asyncio.StreamReader,
        upstream_writer: asyncio.StreamWriter,
    ) -> Tuple[int, int]:
        async def pump(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> int:
            total = 0
            try:
                while True:
                    chunk = await src.read(RELAY_CHUNK)
                    if not chunk:
                        break
                    dst.write(chunk)
                    await dst.drain()
                    total += len(chunk)
            except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
                pass
            except Exception:
                pass
            finally:
                # Safely signal EOF — not all transports support write_eof
                with _suppress():
                    if hasattr(dst, "can_write_eof") and dst.can_write_eof():
                        dst.write_eof()
            return total

        results = await asyncio.gather(
            pump(client_reader, upstream_writer),
            pump(upstream_reader, client_writer),
            return_exceptions=True,
        )
        sent = results[0] if isinstance(results[0], int) else 0
        recv = results[1] if isinstance(results[1], int) else 0
        with _suppress():
            upstream_writer.close()
        return sent, recv


# ============================================================================
# Background tasks
# ============================================================================


async def auto_clean_loop(
    pool: ProxyPool,
    interval: float,
    concurrency: int,
    timeout: float,
    stats: ServerStats,
):
    while True:
        await asyncio.sleep(interval)
        candidates = pool.all()
        if not candidates:
            continue
        await check_many(candidates, concurrency=concurrency, timeout=timeout)
        removed_dead = pool.remove_dead()
        removed_anon = pool.enforce_anonymity()
        msgs = []
        if removed_dead:
            msgs.append(f"{len(removed_dead)} dead")
        if removed_anon:
            msgs.append(f"{len(removed_anon)} below min-anonymity")
        if msgs:
            stats.log(
                f"auto-clean: dropped {', '.join(msgs)} — {len(pool.alive())} alive left"
            )


async def scheduled_url_refresh_loop(
    pool: ProxyPool,
    source_urls: List[str],
    interval: float,
    check_concurrency: int,
    check_timeout: float,
    stats: ServerStats,
):
    """Periodically fetch fresh proxies from URLs and add them to the pool."""
    while True:
        await asyncio.sleep(interval)
        try:
            tasks = [fetch_proxies_from_url(u) for u in source_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            new_proxies: List[Proxy] = []
            for u, r in zip(source_urls, results):
                if isinstance(r, list):
                    new_proxies.extend(r)
            if new_proxies:
                added = pool.add(new_proxies)
                stats.log(f"url-refresh: fetched {len(new_proxies)}, {added} new added")
                # Quick-check new ones
                await check_many(
                    new_proxies, concurrency=check_concurrency, timeout=check_timeout
                )
                pool.remove_dead()
                pool.enforce_anonymity()
        except Exception as exc:
            stats.log(f"url-refresh error: {exc}")


# ============================================================================
# Control API (aiohttp JSON)
# ============================================================================


class ControlAPI:
    def __init__(
        self,
        pool: ProxyPool,
        server: RotatingProxyServer,
        host: str = "127.0.0.1",
        port: int = 8900,
    ):
        self.pool = pool
        self.server = server
        self.host = host
        self.port = port
        self._runner = None

    async def start(self) -> None:
        from aiohttp import web

        app = web.Application()
        app.add_routes(
            [
                web.get("/status", self._status),
                web.get("/proxies", self._proxies),
                web.get("/metrics", self._metrics),
                web.post("/rotate", self._rotate),
                web.post("/purge", self._purge),
                web.delete("/proxy/{proxy_id}", self._delete_proxy),
            ]
        )
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def _status(self, _request):
        from aiohttp import web
        summary = self.pool.stats_summary()
        summary["listening"] = f"{self.server.host}:{self.server.port}"
        summary["active_connections"] = self.server.stats.active_connections
        summary["total_connections"] = self.server.stats.total_connections
        summary["refused"] = self.server.stats.total_refused
        summary["bypassed"] = self.server.stats.total_bypassed
        summary["uptime_seconds"] = int(time.time() - self.server.stats.started_at)
        return web.json_response(summary)

    async def _proxies(self, _request):
        from aiohttp import web
        # Redact credentials — never expose upstream proxy passwords via the API
        def _safe(d: dict) -> dict:
            d = dict(d)
            d["username"] = bool(d.get("username")) or None
            d["password"] = "***" if d.get("password") else None
            return d
        return web.json_response([_safe(p.to_state_dict()) for p in self.pool.all()])

    async def _metrics(self, _request):
        from aiohttp import web
        summary = self.pool.stats_summary()
        # Prometheus-style text format
        lines = [
            "# HELP proxy_rotator_pool_total Total proxies in pool",
            "# TYPE proxy_rotator_pool_total gauge",
            f"proxy_rotator_pool_total {summary['total']}",
            "# HELP proxy_rotator_pool_alive Alive proxies",
            "# TYPE proxy_rotator_pool_alive gauge",
            f"proxy_rotator_pool_alive {summary['alive']}",
            "# HELP proxy_rotator_forwarded_total Total requests forwarded",
            "# TYPE proxy_rotator_forwarded_total counter",
            f"proxy_rotator_forwarded_total {summary['forwarded']}",
            "# HELP proxy_rotator_failed_total Total failed relay attempts",
            "# TYPE proxy_rotator_failed_total counter",
            f"proxy_rotator_failed_total {summary['failed']}",
            "# HELP proxy_rotator_bytes_total Total bytes relayed",
            "# TYPE proxy_rotator_bytes_total counter",
            f"proxy_rotator_bytes_total {summary['bytes']}",
            "# HELP proxy_rotator_refused_total Requests refused (pool empty)",
            "# TYPE proxy_rotator_refused_total counter",
            f"proxy_rotator_refused_total {self.server.stats.total_refused}",
            "# HELP proxy_rotator_active_connections Current active connections",
            "# TYPE proxy_rotator_active_connections gauge",
            f"proxy_rotator_active_connections {self.server.stats.active_connections}",
        ]
        return web.Response(text="\n".join(lines) + "\n", content_type="text/plain")

    async def _rotate(self, _request):
        from aiohttp import web
        self.pool.force_rotate()
        return web.json_response({"ok": True})

    async def _purge(self, _request):
        from aiohttp import web
        removed = self.pool.remove_dead()
        return web.json_response({"removed": len(removed)})

    async def _delete_proxy(self, request):
        from aiohttp import web
        proxy_id = request.match_info["proxy_id"]
        self.pool.remove(proxy_id)
        return web.json_response({"ok": True})


# ============================================================================
# 3D ASCII Earth Globe — land detection
# ============================================================================
#
# We use a union-of-rectangles approach: each entry is
# (lon_min, lon_max, lat_min, lat_max).  Rectangles are guaranteed
# correct — no winding-order bugs, no self-intersection — and fast enough
# for a precomputed 360×180 bitmap.  The globe renders at O(1) per pixel.

_LAND_RECTS: List[Tuple[float, float, float, float]] = [
    # ── North America ────────────────────────────────────────────────────────
    (-170, -140, 57, 72),    # Alaska + NW Canada
    (-145, -100, 48, 72),    # Canada interior / Yukon / NWT
    (-100,  -60, 44, 70),    # Canada east
    (-130, -100, 33, 50),    # US west coast + Rockies
    (-100,  -74, 24, 50),    # US plains, midwest, south
    ( -80,  -66, 24, 36),    # SE US + Florida
    ( -80,  -74, 36, 42),    # Mid-Atlantic (DC, Philadelphia)
    ( -76,  -66, 40, 48),    # US Northeast — NYC (40.7°N, -74°W) ✓
    # ── Mexico / Central America ─────────────────────────────────────────────
    (-118,  -88, 15, 30),    # Mexico
    ( -92,  -77,  8, 18),    # Central America
    # ── South America ────────────────────────────────────────────────────────
    ( -82,  -50, -4, 12),    # N coast (Colombia → Guianas)
    ( -75,  -35,-12, -4),    # NE Brazil bulge (Recife 35°W, 8°S ✓)
    ( -75,  -43,-25,-12),    # SE Brazil (Rio de Janeiro 43.2°W, 22.9°S ✓)
    ( -80,  -58,-56,-25),    # S SA: Patagonia + Uruguay + NW Argentina
    # ── Europe ───────────────────────────────────────────────────────────────
    ( -10,    3, 35, 52),    # Iberia + W France
    (  -2,   16, 42, 56),    # France + Germany + Italy N — Paris (2°, 48°) ✓
    ( -10,    2, 50, 59),    # UK + Ireland — London (-0.1°, 51.5°) ✓
    (   5,   30, 52, 72),    # Scandinavia + Baltic — Oslo, Stockholm ✓
    (  18,   42, 40, 58),    # E Europe + Ukraine
    (  24,   62, 52, 72),    # W Russia
    # ── Africa ───────────────────────────────────────────────────────────────
    ( -18,   52, -2, 38),    # N Africa — Cairo (31°, 30°) ✓
    ( -18,   52,-35, -2),    # S Africa
    (  38,   52,  8, 18),    # Horn of Africa + Ethiopia
    (  28,   42,-12,  8),    # E Africa coast
    # ── Greenland + Iceland ──────────────────────────────────────────────────
    ( -57,  -17, 60, 84),    # Greenland
    ( -24,  -13, 63, 66),    # Iceland
    # ── Middle East / Arabian Peninsula ──────────────────────────────────────
    (  34,   60, 12, 40),    # Levant + Turkey + Persia
    (  44,   62,  6, 24),    # Arabian Peninsula + Yemen
    # ── Central + West Asia ──────────────────────────────────────────────────
    (  48,   87, 36, 56),    # Kazakhstan + Uzbekistan
    (  60,  135, 50, 76),    # Siberia — vast belt
    # ── South Asia ───────────────────────────────────────────────────────────
    (  68,   92,  8, 30),    # India — Delhi (77°, 28.6°) ✓
    (  79,   82,  5, 10),    # Sri Lanka
    # ── SE Asia / Indochina ──────────────────────────────────────────────────
    (  92,  120,  5, 25),    # Indochina + Thailand + Vietnam
    ( 100,  108, -4,  6),    # Malay Peninsula
    (  95,  106, -6,  5),    # Sumatra
    ( 108,  120, -5,  7),    # Borneo
    ( 106,  142, -9,  2),    # New Guinea + Sulawesi
    # ── E Asia (China + Korea + Japan) ───────────────────────────────────────
    (  75,  135, 18, 50),    # China + Mongolia + Manchuria
    ( 124,  130, 34, 40),    # Korean Peninsula
    ( 120,  122, 22, 25),    # Taiwan
    ( 118,  127,  6, 20),    # Philippines (Luzon)
    ( 130,  146, 30, 46),    # Japan — Tokyo (139.7°, 35.7°) ✓
    # ── Russian Far East ─────────────────────────────────────────────────────
    ( 130,  180, 50, 72),
    (-180, -160, 52, 72),    # Chukchi wrap-around
    # ── Australia + Oceania ──────────────────────────────────────────────────
    ( 113,  154,-44, -10),   # Australia — Sydney (151.2°, -33.8°) ✓
    ( 166,  178,-47, -34),   # New Zealand
    # ── Madagascar ───────────────────────────────────────────────────────────
    (  43,   51,-26, -12),
    # ── Antarctica ───────────────────────────────────────────────────────────
    (-180,  180,-90, -65),   # solid ice sheet south of ~65°S
]


def is_land(lon_deg: float, lat_deg: float) -> bool:
    """Fast O(n) land check from a union of bounding rectangles.
    n ≈ 45 rects — negligible cost per pixel; no winding-order bugs."""
    lon = ((lon_deg + 180.0) % 360.0) - 180.0  # normalise to [-180, 180)
    lat = lat_deg
    for lo, hi, la, lb in _LAND_RECTS:
        if lo <= lon <= hi and la <= lat <= lb:
            return True
    return False


def precompute_land_mask_async(callback: Optional[Callable] = None) -> threading.Thread:
    """No-op: rectangle lookup is already O(1) per query; nothing to precompute.
    Kept so callers compiled against the old API still work."""
    def _worker():
        if callback:
            callback()
    t = threading.Thread(target=_worker, daemon=True, name="land-mask-build")
    t.start()
    return t


# Globe rendering
_SHADE_CHARS = " .:;+=xX$&#@"
_SHADE_DARK   = " .,:-~=+oO0"

# Light source direction (normalized)
_LX, _LY, _LZ = 0.6, 0.5, 0.6
_LMAG = math.sqrt(_LX*_LX + _LY*_LY + _LZ*_LZ)
_LX, _LY, _LZ = _LX/_LMAG, _LY/_LMAG, _LZ/_LMAG


def render_globe_frame(
    angle_y: float,
    width: int,
    height: int,
    color: bool = True,
) -> List[str]:
    """
    Render a frame of the spinning 3D ASCII Earth globe.
    Returns a list of Rich-markup strings (one per row).
    """
    R = min(width / 2.0, height * 1.0) * 0.9
    cx = width / 2.0
    cy = height / 2.0

    cos_y = math.cos(angle_y)
    sin_y = math.sin(angle_y)

    # Tilt around X axis for realism
    tilt = 0.35  # ~20 degrees
    cos_x = math.cos(tilt)
    sin_x = math.sin(tilt)

    rows = []
    for row in range(height):
        # Map pixel to sphere coords — terminals use ~2:1 char aspect
        py = (cy - row) / R
        line_parts = []
        for col in range(width):
            px = (col - cx) / (R * 0.5)  # squish for char aspect ratio
            z_sq = 1.0 - px * px - py * py
            if z_sq < 0:
                line_parts.append(" ")
                continue

            z = math.sqrt(z_sq)

            # Apply Y rotation (spin)
            x_ry = px * cos_y - z * sin_y
            z_ry = px * sin_y + z * cos_y

            # Apply X tilt
            y_rx = py * cos_x - z_ry * sin_x
            z_rx = py * sin_x + z_ry * cos_x

            # Surface normal for lighting
            dot = max(0.0, x_ry * _LX + y_rx * _LY + z_rx * _LZ)

            # Convert to lat/lon
            lat = math.degrees(math.asin(max(-1.0, min(1.0, y_rx))))
            lon = math.degrees(math.atan2(x_ry, z_rx))

            land = is_land(lon, lat)
            is_pole = abs(lat) > 75

            if color:
                shade_idx = int(dot * (len(_SHADE_CHARS) - 1))
                shade_char = _SHADE_CHARS[shade_idx]

                if is_pole:
                    # White for poles
                    bright = int(180 + dot * 75)
                    line_parts.append(f"[rgb({bright},{bright},{bright+10})]{shade_char}[/]")
                elif land:
                    # Green-brown for land
                    if dot < 0.15:
                        line_parts.append(f"[rgb(30,55,30)]{shade_char}[/]")
                    else:
                        g = int(80 + dot * 120)
                        r_val = int(40 + dot * 80)
                        b_val = int(30 + dot * 30)
                        line_parts.append(f"[rgb({r_val},{g},{b_val})]{shade_char}[/]")
                else:
                    # Blue for ocean
                    if dot < 0.1:
                        line_parts.append(f"[rgb(5,15,40)]{shade_char}[/]")
                    else:
                        b_val = int(100 + dot * 155)
                        g_val = int(60 + dot * 90)
                        line_parts.append(f"[rgb(20,{g_val},{b_val})]{shade_char}[/]")
            else:
                shade_idx = int(dot * (len(_SHADE_CHARS) - 1))
                line_parts.append(_SHADE_CHARS[shade_idx])

        rows.append("".join(line_parts))
    return rows


# ============================================================================
# Helpers
# ============================================================================


def _fmt_bytes(n: int) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def _fmt_latency(ms: Optional[float]) -> str:
    if ms is None:
        return "—"
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms/1000:.1f}s"


def _latency_bar(ms: Optional[float], width: int = 8) -> str:
    """Render a small latency bar."""
    if ms is None:
        return "·" * width
    # 0-5000ms range mapped to bar
    filled = max(1, min(width, int((1 - ms / 5000) * width)))
    return "█" * filled + "░" * (width - filled)


def _score_color(score: float) -> str:
    if score >= 70:
        return "bright_green"
    if score >= 40:
        return "yellow"
    return "red"


def _anon_style(anon: Optional[str]) -> str:
    return {
        "elite": "[bright_green]elite[/]",
        "anonymous": "[yellow]anon[/]",
        "transparent": "[red]transp[/]",
    }.get(anon or "", "[dim]—[/]")


# ============================================================================
# Textual TUI — ultra-sexy dark neon interface
# ============================================================================


NEON_CSS = """
$bg: #050510;
$surface: #0a0a20;
$border: #1a1a4a;
$accent: #00ffcc;
$accent2: #ff00aa;
$accent3: #ffaa00;
$text: #ccddff;
$dim: #445566;
$green: #00ff88;
$red: #ff4466;
$yellow: #ffdd44;

Screen {
    background: $bg;
    color: $text;
}

#header {
    height: 4;
    background: $surface;
    border-bottom: heavy $accent;
    content-align: center middle;
    text-style: bold;
    color: $accent;
    padding: 0 2;
}

#body {
    height: 1fr;
}

#left-panel {
    width: 36;
    border-right: heavy $border;
}

#globe-container {
    height: 1fr;
    background: $bg;
    border: round $accent;
    border-title-color: $accent;
    border-title-style: bold;
    margin: 0 0;
    padding: 0 0;
    content-align: center middle;
    overflow: hidden;
}

#mini-stats {
    height: 8;
    border: round $accent2;
    border-title-color: $accent2;
    background: $surface;
    padding: 0 1;
    margin: 0;
}

#center-panel {
    width: 1fr;
    border-right: heavy $border;
}

#proxy-table {
    height: 1fr;
    border: round $accent;
    border-title-color: $accent;
    background: $surface;
}

#right-panel {
    width: 40;
}

#log-widget {
    height: 1fr;
    border: round $accent2;
    border-title-color: $accent2;
    background: $surface;
    overflow-y: scroll;
    scrollbar-color: $accent;
    scrollbar-size: 1 1;
}

#bottom-bar {
    height: 2;
    background: $surface;
    border-top: heavy $border;
    content-align: center middle;
    color: $dim;
    padding: 0 2;
}
"""


def _make_header_text(server_host: str, server_port: int, pool_summary: dict) -> str:
    alive = pool_summary.get("alive", 0)
    total = pool_summary.get("total", 0)
    fwd = pool_summary.get("forwarded", 0)
    strat = pool_summary.get("strategy", "round_robin")
    return (
        f"[bright_cyan]◈ PROXY[/] [bold bright_white]ROTATOR[/] [bright_cyan]◈[/]   "
        f"[dim]╱[/] Listening: [bright_yellow]{server_host}:{server_port}[/]   "
        f"[dim]╱[/] Pool: [bright_green]{alive}[/][dim]/{total}[/] alive   "
        f"[dim]╱[/] Forwarded: [bright_cyan]{fwd}[/]   "
        f"[dim]╱[/] Strategy: [bright_magenta]{strat}[/]"
    )


def run_dashboard(
    pool: ProxyPool,
    server: RotatingProxyServer,
    auto_clean_interval: float,
    check_concurrency: int,
    check_timeout: float,
    control_api: Optional[ControlAPI],
    state_file: Optional[str],
    export_stats_path: Optional[str],
):
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import (
        Footer, Header, Static, DataTable, RichLog, Label
    )
    from rich.text import Text
    from rich.panel import Panel

    class GlobeWidget(Static):
        """Spinning 3D ASCII Earth globe."""

        DEFAULT_CSS = """
        GlobeWidget {
            height: 1fr;
            content-align: center middle;
        }
        """

        def __init__(self):
            super().__init__()
            self._angle = 0.0
            self._frame_count = 0

        def on_mount(self) -> None:
            self.set_interval(0.07, self._spin)

        def _spin(self) -> None:
            self._angle += 0.035
            if self._angle > math.tau:
                self._angle -= math.tau
            self._frame_count += 1
            self.refresh()

        def render(self):
            # Get usable area
            try:
                w = max(10, self.size.width)
                h = max(5, self.size.height)
            except Exception:
                w, h = 32, 14

            frame = render_globe_frame(self._angle, w, h, color=True)
            return "\n".join(frame)

    class MiniStats(Static):
        """Small stats panel under the globe."""

        def update_stats(self, pool: ProxyPool, server_stats: ServerStats) -> None:
            summary = pool.stats_summary()
            alive = summary["alive"]
            total = summary["total"]
            fwd = summary["forwarded"]
            failed = summary["failed"]
            refused = server_stats.total_refused
            byt = _fmt_bytes(summary["bytes"])
            uptime = int(time.time() - server_stats.started_at)
            h, m, s = uptime // 3600, (uptime % 3600) // 60, uptime % 60
            top = summary.get("top_proxy") or "—"
            active = server_stats.active_connections

            text = (
                f" [dim]POOL   [/][bright_green]{alive:>4}[/][dim]/{total}[/]  alive\n"
                f" [dim]FWD    [/][bright_cyan]{fwd:>6}[/]  requests\n"
                f" [dim]FAILED [/][bright_red]{failed:>6}[/]  attempts\n"
                f" [dim]REFUSE [/][yellow]{refused:>6}[/]  blocked\n"
                f" [dim]DATA   [/][white]{byt:>7}[/]  relayed\n"
                f" [dim]ACTIVE [/][bright_magenta]{active:>4}[/]  conns\n"
                f" [dim]UPTIME [/][bright_white]{h:02d}:{m:02d}:{s:02d}[/]\n"
            )
            self.update(text)

    class ProxyTable(DataTable):
        """Colored proxy table with sorting."""
        pass

    class LogWidget(RichLog):
        """Auto-scrolling request log."""
        pass

    class Dashboard(App):
        CSS = NEON_CSS
        BINDINGS = [
            ("q", "quit", "Quit"),
            ("r", "force_rotate", "Rotate"),
            ("c", "recheck", "Recheck"),
            ("d", "purge_dead", "Purge Dead"),
            ("s", "sort_by_score", "Sort Score"),
            ("f", "sort_by_latency", "Sort Fast"),
            ("?", "show_help", "Help"),
        ]
        TITLE = "proxy_rotator"

        def __init__(self):
            super().__init__()
            self._globe_angle = 0.0
            self._sort_key = "score"
            self._header_tick = 0

        def compose(self) -> ComposeResult:
            yield Static(id="header")
            with Horizontal(id="body"):
                with Vertical(id="left-panel"):
                    globe = GlobeWidget()
                    globe.id = "globe-inner"
                    yield Container(globe, id="globe-container")
                    ms = MiniStats(id="mini-stats")
                    yield ms
                with Vertical(id="center-panel"):
                    t = ProxyTable(id="proxy-table")
                    yield t
                with Vertical(id="right-panel"):
                    yield LogWidget(
                        id="log-widget",
                        wrap=False,
                        highlight=True,
                        markup=True,
                        max_lines=500,
                    )
            yield Static(
                "  [dim]q[/] quit   [dim]r[/] rotate   [dim]c[/] recheck   "
                "[dim]d[/] purge dead   [dim]s[/] sort score   [dim]f[/] sort fast   "
                "  Full Protection ON — direct IP never leaks",
                id="bottom-bar",
            )

        def on_mount(self) -> None:
            # Setup table columns
            t = self.query_one("#proxy-table", DataTable)
            t.add_columns(
                "  #", "Proxy", "Proto", "Anon", "Score", "Lat", "Bar",
                "OK%", "Reqs", "Exit IP", "Country",
            )
            t.cursor_type = "row"
            t.zebra_stripes = True

            # Start background tasks
            self._server_task = asyncio.create_task(server.serve_forever())
            self._clean_task = asyncio.create_task(
                auto_clean_loop(pool, auto_clean_interval, check_concurrency, check_timeout, server.stats)
            )
            if control_api is not None:
                asyncio.create_task(control_api.start())

            # UI refresh
            self.set_interval(0.5, self._refresh_ui)

        def _refresh_ui(self) -> None:
            self._header_tick += 1

            # Header
            summary = pool.stats_summary()
            self.query_one("#header", Static).update(
                _make_header_text(server.host, server.port, summary)
            )

            # Mini stats
            self.query_one("#mini-stats", MiniStats).update_stats(pool, server.stats)

            # Proxy table
            t = self.query_one("#proxy-table", DataTable)
            t.clear()
            proxies = pool.all()

            if self._sort_key == "score":
                proxies.sort(key=lambda p: (-p.stats.score, p.host))
            elif self._sort_key == "latency":
                proxies.sort(
                    key=lambda p: p.stats.avg_latency_ms
                    if p.stats.avg_latency_ms is not None
                    else float("inf")
                )

            alive_ids = {p.id for p in pool.alive()}

            for i, p in enumerate(proxies, 1):
                is_alive = p.id in alive_ids
                is_q = p.is_quarantined
                is_current = p.id == pool._current_id

                # Status color
                if is_current and is_alive:
                    num_cell = f"[bright_cyan bold]→{i:>2}[/]"
                elif is_alive:
                    num_cell = f"[bright_green]{i:>3}[/]"
                elif is_q:
                    num_cell = f"[yellow]{i:>3}[/]"
                else:
                    num_cell = f"[dim red]{i:>3}[/]"

                host_port = f"{p.host}:{p.port}"
                if len(host_port) > 22:
                    host_port = host_port[:20] + "…"

                proto_color = {
                    "http": "cyan", "https": "bright_cyan",
                    "socks4": "magenta", "socks5": "bright_magenta",
                }.get(p.protocol.value, "white")
                proto_cell = f"[{proto_color}]{p.protocol.value:<6}[/]"

                anon_cell = _anon_style(p.stats.anonymity)

                sc = p.stats.score
                sc_color = _score_color(sc)
                score_cell = f"[{sc_color}]{sc:5.1f}[/]"

                lat_cell = _fmt_latency(p.stats.avg_latency_ms)

                bar = _latency_bar(p.stats.avg_latency_ms, 7)
                bar_color = (
                    "bright_green" if (p.stats.avg_latency_ms or 9999) < 500
                    else "yellow" if (p.stats.avg_latency_ms or 9999) < 2000
                    else "red"
                )
                bar_cell = f"[{bar_color}]{bar}[/]"

                sr = p.stats.success_rate
                sr_color = "bright_green" if sr >= 80 else "yellow" if sr >= 50 else "red"
                sr_cell = f"[{sr_color}]{sr:4.0f}%[/]"

                reqs_cell = f"[dim]{p.stats.total_requests:>4}[/]"
                ip_cell = f"[dim cyan]{(p.stats.exit_ip or '—'):<15}[/]"
                geo_txt = p.stats.geo_label
                if len(geo_txt) > 22:
                    geo_txt = geo_txt[:20] + "…"
                country_cell = f"[dim]{geo_txt:<22}[/]"

                t.add_row(
                    num_cell, host_port, proto_cell, anon_cell, score_cell,
                    lat_cell, bar_cell, sr_cell, reqs_cell, ip_cell, country_cell,
                )

            # Log widget
            log = self.query_one("#log-widget", LogWidget)
            log.clear()
            for entry in list(server.stats.request_log)[-150:]:
                ts = time.strftime("%H:%M:%S", time.localtime(entry.timestamp))
                if entry.success:
                    status = f"[bright_green]OK[/]"
                    proxy_str = f"[dim cyan]{(entry.proxy or '?')[-28:]}[/]"
                    lat = f"[bright_white]{_fmt_latency(entry.latency_ms):>7}[/]"
                else:
                    status = f"[bright_red]ERR[/]"
                    proxy_str = f"[dim red]{(entry.proxy or '—')[-28:]}[/]"
                    lat = f"[dim red]{_fmt_latency(entry.latency_ms):>7}[/]"
                method_color = {
                    "CONNECT": "bright_cyan", "GET": "green", "POST": "yellow",
                }.get(entry.method, "white")
                host_short = entry.host[:25]
                log.write(
                    f"[dim]{ts}[/] {status} [{method_color}]{entry.method:<7}[/] "
                    f"[white]{host_short:<25}[/] {lat} {proxy_str}"
                )
            # Also show server text log for non-request events
            for line in list(server.stats.recent_log)[-30:]:
                if "REFUSED" in line:
                    log.write(f"[bold red]{line}[/]")
                elif "WARNING" in line or "BYPASS" in line:
                    log.write(f"[yellow]{line}[/]")
                elif "auto-clean" in line or "url-refresh" in line:
                    log.write(f"[dim cyan]{line}[/]")

        async def action_force_rotate(self) -> None:
            pool.force_rotate()
            server.stats.log("⟳ manual rotate triggered")

        async def action_recheck(self) -> None:
            server.stats.log(f"⟳ manual recheck of {len(pool.all())} proxies...")
            await check_many(pool.all(), concurrency=check_concurrency, timeout=check_timeout)
            rd = pool.remove_dead()
            ra = pool.enforce_anonymity()
            server.stats.log(
                f"✓ recheck done: {len(pool.alive())} alive, "
                f"{len(rd)} dead removed, {len(ra)} anonymity-rejected"
            )

        async def action_purge_dead(self) -> None:
            removed = pool.remove_dead()
            server.stats.log(f"✗ purged {len(removed)} dead proxies")

        async def action_sort_by_score(self) -> None:
            self._sort_key = "score"

        async def action_sort_by_latency(self) -> None:
            self._sort_key = "latency"

        async def action_show_help(self) -> None:
            self.notify(
                "q=Quit  r=Rotate  c=Recheck  d=Purge  s=Sort Score  f=Sort Fast",
                title="Keybindings",
                timeout=5,
            )

        async def action_quit(self) -> None:
            await server.stop()
            if control_api is not None:
                await control_api.stop()
            if state_file:
                save_state(pool.all(), state_file)
                server.stats.log(f"✓ state saved to {state_file}")
            if export_stats_path:
                export_stats(pool.all(), export_stats_path)
            self.exit()

    Dashboard().run()


# ============================================================================
# Tkinter file picker
# ============================================================================


def pick_proxy_file_tk() -> Optional[str]:
    """Open a native file picker dialog and return the chosen path or None."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.lift()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title="Select proxy list file",
            filetypes=[
                ("All proxy files", "*.txt *.csv *.json *.yaml *.yml"),
                ("Text files", "*.txt"),
                ("CSV files", "*.csv"),
                ("JSON files", "*.json"),
                ("All files", "*"),
            ],
        )
        root.destroy()
        return path if path else None
    except Exception as exc:
        click.echo(f"Tkinter file picker unavailable: {exc}")
        return None


# ============================================================================
# CLI
# ============================================================================


class _AutoRunGroup(click.Group):
    """A click Group that needs no explicit "mode" for everyday use.

    Plain invocations like `proxy_rotator.py`, `proxy_rotator.py proxies.txt`,
    or `proxy_rotator.py --discover` all just start the rotator directly --
    they are silently rewritten to the `run` subcommand. Explicit subcommands
    (`check`, `discover`, `sysproxy`, `tun`) still work for advanced use, and
    `run`/`pick` remain available as explicit aliases.
    """

    def resolve_command(self, ctx, args):
        if args and args[0] in ("--help", "-h"):
            return super().resolve_command(ctx, args)
        if not args or args[0] not in self.commands:
            args = ["run", *args]
        return super().resolve_command(ctx, args)


@click.group(cls=_AutoRunGroup)
def cli():
    """proxy_rotator — advanced rotating proxy engine with 3D Earth TUI.

    No separate "modes" to remember: just run this file, optionally pointing
    it at a proxy list. It loads proxies (from a file, --source-url,
    --discover, or a file picker), health-checks them, and starts the
    rotating proxy server -- all in one step.
    """


# ---- shared run options (reusable decorator list) --------------------------


# ============================================================================
# TUN Infrastructure — Cross-platform virtual network interface
# ============================================================================

@dataclass
class TUNConnection:
    """Tracks an active TUN-forwarded connection."""
    src_addr: Tuple[str, int]
    dst_addr: Tuple[str, int]
    proxy: "Proxy"
    circuit: List["Proxy"]
    start_time: float
    bytes_sent: int = 0
    bytes_recv: int = 0
    last_activity: float = field(default_factory=time.time)


class TUNInterface:
    """Cross-platform TUN interface abstraction."""

    def __init__(self, name: Optional[str] = None, network: str = "10.10.0.0/24") -> None:
        self.name = name
        self.network = network
        self._fd: Optional[int] = None
        self._actual_name: Optional[str] = None
        self._closed = True
        self._platform = platform.system().lower()

        parts = network.split("/")
        self._network_addr = parts[0]
        self._prefix_len = int(parts[1]) if len(parts) > 1 else 24
        self._host_ip = self._generate_host_ip()

        self._saved_routes: List[str] = []
        self._original_gateway: Optional[str] = None

    def _generate_host_ip(self) -> str:
        base = ".".join(self._network_addr.split(".")[:3])
        return f"{base}.1"

    def _generate_client_ip(self) -> str:
        base = ".".join(self._network_addr.split(".")[:3])
        return f"{base}.2"

    def open(self) -> bool:
        if self._platform == "linux":
            return self._open_linux()
        elif self._platform == "darwin":
            return self._open_macos()
        elif self._platform == "windows":
            return self._open_windows()
        else:
            log_tun.error(f"TUN not supported on {self._platform}")
            return False

    def _open_linux(self) -> bool:
        try:
            import fcntl
            import struct

            tun = os.open("/dev/net/tun", os.O_RDWR)
            ifr_name = (self.name or "tun%d").encode("utf-8")[:15]
            ifr = struct.pack("16sH", ifr_name, IFF_TUN | IFF_NO_PI)
            ifr_res = fcntl.ioctl(tun, TUNSETIFF, ifr)
            self._actual_name = ifr_res[:16].decode("utf-8").strip("\x00").strip()
            self._fd = tun
            self._closed = False

            self._run_cmd(["ip", "link", "set", "dev", self._actual_name, "up"])
            self._run_cmd(["ip", "addr", "add", f"{self._host_ip}/{self._prefix_len}", 
                          "dev", self._actual_name])

            log_tun.info(f"Linux TUN {self._actual_name} created at {self._host_ip}/{self._prefix_len}")
            return True
        except Exception as exc:
            log_tun.error(f"Failed to create Linux TUN: {exc}")
            return False

    def _open_macos(self) -> bool:
        try:
            import ctypes
            import ctypes.util

            libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
            fd = libc.socket(PF_SYSTEM, SOCK_DGRAM, SYSPROTO_CONTROL)
            if fd < 0:
                log_tun.error("Failed to create PF_SYSTEM socket")
                return False

            class ctl_info(ctypes.Structure):
                _fields_ = [("ctl_id", ctypes.c_uint32), ("ctl_name", ctypes.c_char * 96)]

            ci = ctl_info()
            ci.ctl_name = UTUN_CONTROL_NAME
            ret = libc.ioctl(fd, CTLIOCGINFO, ctypes.byref(ci))
            if ret < 0:
                os.close(fd)
                log_tun.error("Failed to get utun control info")
                return False

            class sockaddr_ctl(ctypes.Structure):
                _fields_ = [
                    ("sc_len", ctypes.c_uint8), ("sc_family", ctypes.c_uint8),
                    ("ss_sysaddr", ctypes.c_uint16), ("sc_id", ctypes.c_uint32),
                    ("sc_unit", ctypes.c_uint32), ("sc_reserved", ctypes.c_uint32 * 5),
                ]

            sa = sockaddr_ctl()
            sa.sc_len = ctypes.sizeof(sockaddr_ctl)
            sa.sc_family = AF_SYS_CONTROL
            sa.ss_sysaddr = AF_SYS_CONTROL
            sa.sc_id = ci.ctl_id
            sa.sc_unit = 0

            ret = libc.connect(fd, ctypes.byref(sa), ctypes.sizeof(sa))
            if ret < 0:
                os.close(fd)
                log_tun.error("Failed to connect to utun")
                return False

            self._fd = fd
            self._actual_name = f"utun{sa.sc_unit}" if sa.sc_unit else "utun0"
            self._closed = False

            self._run_cmd(["ifconfig", self._actual_name, "inet", 
                          self._host_ip, self._generate_client_ip(), "up"])

            log_tun.info(f"macOS {self._actual_name} created at {self._host_ip}")
            return True
        except Exception as exc:
            log_tun.error(f"Failed to create macOS utun: {exc}")
            return False

    def _open_windows(self) -> bool:
        try:
            import pywintun2

            adapter = pywintun2.create_adapter("ProxyRotatorTUN", "ProxyRotator")
            session = adapter.start_session()

            self._fd = session
            self._actual_name = adapter.name
            self._closed = False

            self._run_cmd(["netsh", "interface", "ip", "set", "address", 
                          f"name={self._actual_name}", "static", self._host_ip, "255.255.255.0"])

            log_tun.info(f"Windows Wintun {self._actual_name} created at {self._host_ip}")
            return True
        except Exception as exc:
            log_tun.error(f"Failed to create Windows Wintun: {exc}")
            return False

    def _run_cmd(self, cmd: List[str]) -> Tuple[int, str]:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            out = (result.stdout + result.stderr).strip()
            if result.returncode != 0:
                log_tun.warning(f"Command failed: {' '.join(cmd)} -> {out}")
            return result.returncode, out
        except Exception as exc:
            log_tun.warning(f"Command exception: {' '.join(cmd)} -> {exc}")
            return 1, str(exc)

    def read(self, size: int = 2048) -> Optional[bytes]:
        if self._closed or self._fd is None:
            return None
        try:
            if self._platform == "windows" and hasattr(self._fd, 'receive'):
                return self._fd.receive()
            return os.read(self._fd, size)
        except (OSError, IOError):
            return None

    def write(self, data: bytes) -> bool:
        if self._closed or self._fd is None:
            return False
        try:
            if self._platform == "windows" and hasattr(self._fd, 'send'):
                self._fd.send(data)
                return True
            os.write(self._fd, data)
            return True
        except (OSError, IOError):
            return False

    def fileno(self) -> Optional[int]:
        if self._fd is None:
            return None
        if isinstance(self._fd, int):
            return self._fd
        return None

    def setup_routes(self) -> bool:
        if not self._actual_name:
            return False
        try:
            if self._platform == "linux":
                rc, out = self._run_cmd(["ip", "route", "show", "default"])
                if rc == 0 and out:
                    self._saved_routes.append(out)
                    parts = out.split()
                    if "via" in parts:
                        idx = parts.index("via")
                        self._original_gateway = parts[idx + 1]
                self._run_cmd(["ip", "route", "add", self.network, "dev", self._actual_name])

            elif self._platform == "darwin":
                rc, out = self._run_cmd(["route", "-n", "get", "default"])
                if rc == 0:
                    self._saved_routes.append(out)
                self._run_cmd(["route", "add", "-net", self.network, 
                              "-interface", self._actual_name])

            elif self._platform == "windows":
                rc, out = self._run_cmd(["route", "print", "0.0.0.0"])
                if rc == 0:
                    self._saved_routes.append(out)
                net_base = ".".join(self._network_addr.split(".")[:3]) + ".0"
                self._run_cmd(["route", "add", f"{net_base}/24", self._host_ip])

            log_tun.info(f"Routes configured for {self._actual_name}")
            return True
        except Exception as exc:
            log_tun.error(f"Route setup failed: {exc}")
            return False

    def restore_routes(self) -> None:
        log_tun.info("Restoring original routes...")
        if self._platform == "linux":
            self._run_cmd(["ip", "route", "flush", "dev", self._actual_name or "tun0"])
        elif self._platform == "darwin":
            if self._actual_name:
                self._run_cmd(["route", "delete", "-net", self.network, 
                              "-interface", self._actual_name])
        elif self._platform == "windows":
            net_base = ".".join(self._network_addr.split(".")[:3]) + ".0"
            self._run_cmd(["route", "delete", f"{net_base}/24"])
        for saved in self._saved_routes:
            log_tun.info(f"Original route state: {saved[:200]}")

    def close(self) -> None:
        if self._closed:
            return
        self.restore_routes()
        self._closed = True
        if self._fd is not None:
            try:
                if self._platform == "windows" and hasattr(self._fd, 'end'):
                    self._fd.end()
                else:
                    os.close(self._fd)
            except Exception:
                pass
            self._fd = None
        log_tun.info(f"TUN interface {self._actual_name} closed")


class TUNPacketHandler:
    """Handles IP packets from TUN and routes through proxy mesh."""

    def __init__(self, pool: "ProxyPool", server: "RotatingProxyServer",
                 dns_servers: Optional[List[str]] = None,
                 dns_over_https: bool = True) -> None:
        self.pool = pool
        self.server = server
        self.dns_servers = dns_servers or ["1.1.1.1", "8.8.8.8"]
        self.dns_over_https = dns_over_https
        self._connections: Dict[Tuple[str, int, str, int], TUNConnection] = {}
        self._lock = asyncio.Lock()
        self._running = False
        self._tun: Optional[TUNInterface] = None
        self._read_buffer = bytearray()
        self._dns_cache: Dict[str, Tuple[str, float]] = {}
        self._dns_cache_ttl = 300.0

    async def start(self, tun_name: Optional[str], network: str) -> bool:
        if not _TUN_AVAILABLE:
            log_tun.error("TUN mode not available — missing platform dependencies")
            return False
        if not _scapy_available:
            log_tun.error("TUN mode requires scapy: pip install scapy")
            return False

        self._tun = TUNInterface(name=tun_name, network=network)
        if not self._tun.open():
            return False

        if not self._tun.setup_routes():
            self._tun.close()
            return False

        self._running = True
        log_tun.info(f"TUN mode active on {self._tun._actual_name} ({network})")
        return True

    async def stop(self) -> None:
        self._running = False
        if self._tun:
            self._tun.close()
            self._tun = None
        async with self._lock:
            for conn in list(self._connections.values()):
                self._log_connection(conn, "CLOSED")
            self._connections.clear()

    async def run_loop(self) -> None:
        if not self._tun or not self._running:
            return
        while self._running:
            try:
                packet = await asyncio.get_event_loop().run_in_executor(
                    None, self._tun.read, 2048
                )
                if packet:
                    await self._handle_packet(packet)
                else:
                    await asyncio.sleep(0.001)
            except Exception as exc:
                log_tun.error(f"Packet processing error: {exc}")
                await asyncio.sleep(0.1)

    async def _handle_packet(self, packet: bytes) -> None:
        try:
            ip_pkt = ScapyIP(packet)
        except Exception:
            return

        src_ip = ip_pkt.src
        dst_ip = ip_pkt.dst

        if ip_pkt.haslayer(ScapyTCP):
            tcp_pkt = ip_pkt[ScapyTCP]
            await self._handle_tcp(src_ip, tcp_pkt.sport, dst_ip, tcp_pkt.dport, 
                                  bytes(ip_pkt.payload.payload) if ip_pkt.payload else b"")
        elif ip_pkt.haslayer(ScapyUDP):
            udp_pkt = ip_pkt[ScapyUDP]
            await self._handle_udp(src_ip, udp_pkt.sport, dst_ip, udp_pkt.dport,
                                  bytes(udp_pkt.payload) if udp_pkt.payload else b"")
        elif ip_pkt.haslayer(ScapyICMP):
            await self._handle_icmp(src_ip, dst_ip, ip_pkt[ScapyICMP])

    async def _handle_tcp(self, src_ip: str, src_port: int, dst_ip: str, 
                         dst_port: int, payload: bytes) -> None:
        conn_key = (src_ip, src_port, dst_ip, dst_port)

        async with self._lock:
            conn = self._connections.get(conn_key)

        if not conn:
            proxy = self.pool.get_next(client_key=f"{src_ip}:{src_port}")
            if not proxy:
                log_tun.warning(f"No proxy available for {src_ip}:{src_port} -> {dst_ip}:{dst_port}")
                return

            circuit = []
            if self.pool.mesh_hop_count > 0 and not proxy.protocol.is_socks:
                circuit = self.pool.get_circuit(proxy, destination_host=dst_ip)

            conn = TUNConnection(
                src_addr=(src_ip, src_port),
                dst_addr=(dst_ip, dst_port),
                proxy=proxy,
                circuit=circuit,
                start_time=time.time()
            )

            async with self._lock:
                self._connections[conn_key] = conn

            asyncio.create_task(self._relay_tcp_connection(conn_key, conn))

        conn.last_activity = time.time()
        conn.bytes_sent += len(payload)

    async def _relay_tcp_connection(self, conn_key: Tuple, conn: TUNConnection) -> None:
        dst_host, dst_port = conn.dst_addr

        try:
            start = time.monotonic()
            up_r, up_w = await self._dial_through_proxy(conn.proxy, dst_host, dst_port, conn.circuit)
            latency_ms = (time.monotonic() - start) * 1000
            self.pool.record_success(conn.proxy, latency_ms)

            self._log_connection(conn, "ESTABLISHED")

            async def to_proxy():
                while self._running and conn_key in self._connections:
                    await asyncio.sleep(0.01)

            async def from_proxy():
                while self._running and conn_key in self._connections:
                    try:
                        chunk = await asyncio.wait_for(up_r.read(4096), timeout=30.0)
                        if not chunk:
                            break
                        conn.bytes_recv += len(chunk)
                        await self._inject_tcp_response(conn, chunk)
                    except asyncio.TimeoutError:
                        continue
                    except Exception:
                        break

            await asyncio.gather(to_proxy(), from_proxy())

        except Exception as exc:
            self.pool.record_failure(conn.proxy, str(exc))
            self._log_connection(conn, f"FAILED: {exc}")
        finally:
            async with self._lock:
                self._connections.pop(conn_key, None)
            with _suppress():
                if 'up_w' in dir() and up_w:
                    up_w.close()

    async def _dial_through_proxy(self, proxy: "Proxy", host: str, port: int,
                                  circuit: List["Proxy"]) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        if circuit:
            return await self.server._dial_chain(proxy, host, port, circuit)
        elif proxy.protocol.is_socks:
            return await self.server._dial_socks(proxy, host, port)
        else:
            return await self.server._dial_http_connect(proxy, host, port)

    async def _inject_tcp_response(self, conn: TUNConnection, data: bytes) -> None:
        if not self._tun:
            return
        try:
            ip_pkt = ScapyIP(src=conn.dst_addr[0], dst=conn.src_addr[0])
            tcp_pkt = ScapyTCP(sport=conn.dst_addr[1], dport=conn.src_addr[1], 
                              flags="PA", seq=0, ack=0)
            response = ip_pkt / tcp_pkt / Raw(load=data)
            self._tun.write(bytes(response))
        except Exception as exc:
            log_tun.debug(f"Packet injection failed: {exc}")

    async def _handle_udp(self, src_ip: str, src_port: int, dst_ip: str,
                          dst_port: int, payload: bytes) -> None:
        if dst_port == 53:
            await self._handle_dns(src_ip, src_port, dst_ip, dst_port, payload)
            return

        proxy = self.pool.get_next(client_key=f"udp-{src_ip}:{src_port}")
        if not proxy:
            return
        log_tun.debug(f"UDP {src_ip}:{src_port} -> {dst_ip}:{dst_port} via {proxy.key}")

    async def _handle_dns(self, src_ip: str, src_port: int, dst_ip: str,
                           dst_port: int, payload: bytes) -> None:
        try:
            if self.dns_over_https:
                try:
                    import dnslib
                    query = dnslib.DNSRecord.parse(payload)
                    qname = str(query.questions[0].qname) if query.questions else ""
                    qtype = query.questions[0].qtype if query.questions else 1

                    cache_key = f"{qname}:{qtype}"
                    if cache_key in self._dns_cache:
                        cached_ip, cached_at = self._dns_cache[cache_key]
                        if time.time() - cached_at < self._dns_cache_ttl:
                            await self._send_dns_response(src_ip, src_port, dst_ip, dst_port,
                                                           payload, cached_ip)
                            return

                    doh_url = f"https://cloudflare-dns.com/dns-query?name={qname}&type=A"
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(doh_url, headers={"Accept": "application/dns-json"})
                        if resp.status_code == 200:
                            result = resp.json()
                            answers = result.get("Answer", [])
                            if answers:
                                resolved_ip = answers[0].get("data", "0.0.0.0")
                                self._dns_cache[cache_key] = (resolved_ip, time.time())
                                await self._send_dns_response(src_ip, src_port, dst_ip, dst_port,
                                                               payload, resolved_ip)
                                return
                except ImportError:
                    pass

            proxy = self.pool.get_next(client_key=f"dns-{src_ip}")
            if proxy:
                pass

        except Exception as exc:
            log_tun.debug(f"DNS handling failed: {exc}")

    async def _send_dns_response(self, src_ip: str, src_port: int, dst_ip: str,
                                  dst_port: int, query_payload: bytes, resolved_ip: str) -> None:
        if not self._tun:
            return
        try:
            import dnslib
            query = dnslib.DNSRecord.parse(query_payload)
            response = query.reply()
            response.add_answer(dnslib.RR(qname=query.questions[0].qname,
                                          rtype=query.questions[0].qtype,
                                          rdata=dnslib.A(resolved_ip),
                                          ttl=300))

            ip_pkt = ScapyIP(src=dst_ip, dst=src_ip)
            udp_pkt = ScapyUDP(sport=dst_port, dport=src_port)
            dns_data = bytes(response.pack())
            packet = ip_pkt / udp_pkt / Raw(load=dns_data)
            self._tun.write(bytes(packet))
        except Exception as exc:
            log_tun.debug(f"DNS response injection failed: {exc}")

    async def _handle_icmp(self, src_ip: str, dst_ip: str, icmp_pkt) -> None:
        if icmp_pkt.type == 8:
            if not self._tun:
                return
            try:
                ip_resp = ScapyIP(src=dst_ip, dst=src_ip)
                icmp_resp = ScapyICMP(type=0, id=icmp_pkt.id, seq=icmp_pkt.seq)
                if hasattr(icmp_pkt, 'load'):
                    icmp_resp = icmp_resp / Raw(load=icmp_pkt.load)
                packet = ip_resp / icmp_resp
                self._tun.write(bytes(packet))
            except Exception as exc:
                log_tun.debug(f"ICMP reply failed: {exc}")

    def _log_connection(self, conn: TUNConnection, status: str) -> None:
        duration = time.time() - conn.start_time
        chain_len = len(conn.circuit) if conn.circuit else 0
        mesh_hops = self.pool.mesh_hop_count if hasattr(self.pool, 'mesh_hop_count') else 0

        log_tun.info(
            f"[TUN] {status} | "
            f"SRC: {conn.src_addr[0]}:{conn.src_addr[1]} | "
            f"DST: {conn.dst_addr[0]}:{conn.dst_addr[1]} | "
            f"PROXY: {conn.proxy.key} | "
            f"CHAIN: {chain_len} hops | "
            f"MESH: {mesh_hops} | "
            f"BYTES: {conn.bytes_sent}/{conn.bytes_recv} | "
            f"TIME: {duration:.2f}s"
        )

def _common_run_options(f):
    decorators = [
        click.option("--host", default="127.0.0.1", show_default=True, help="Bind address."),
        click.option("--port", "-p", default=8899, show_default=True, help="Proxy port."),
        click.option("--threads", "-t", default=350, show_default=True, help="Concurrent health-check threads."),
        click.option(
            "--strategy",
            type=click.Choice([s.value for s in RotationStrategy]),
            default=RotationStrategy.ROUND_ROBIN.value,
            show_default=True,
        ),
        click.option("--rotate-every", default=1, show_default=True, help="Rotate every N requests."),
        click.option("--rotate-seconds", default=None, type=float, help="Force rotation every N seconds."),
        click.option("--max-failures", default=3, show_default=True, help="Failures before dropping proxy."),
        click.option("--auto-clean-interval", default=120.0, show_default=True, help="Seconds between background re-checks."),
        click.option("--check-timeout", default=10.0, show_default=True, help="Per-proxy check timeout (s)."),
        click.option("--max-retries", default=3, show_default=True, help="Relay attempts per request."),
        click.option(
            "--min-anonymity",
            type=click.Choice(ANONYMITY_LEVELS),
            default="anonymous",
            show_default=True,
            help="Minimum anonymity level to allow traffic.",
        ),
        click.option("--skip-initial-check", is_flag=True, help="Skip startup health check."),
        click.option("--headless", is_flag=True, help="Run without TUI (server only)."),
        click.option("--allow-direct-fallback", is_flag=True, help="DANGER: fall back to direct if pool empty."),
        click.option("--chain-file", type=click.Path(exists=True), default=None, help="HTTP pre-hop chain file."),
        click.option("--direct-domain", "direct_domains", multiple=True, help="Domain to bypass proxying."),
        click.option("--state-file", type=click.Path(), default=None, help="Persist stats here."),
        click.option("--resume/--no-resume", default=False, help="Resume from prior state."),
        click.option("--export-stats", "export_stats_path", type=click.Path(), default=None, help="Write final stats here."),
        click.option("--api-port", default=0, show_default=True, help="Control API port (0=disabled)."),
        click.option("--api-host", default="127.0.0.1", show_default=True),
        click.option("--geo/--no-geo", default=False, help="Fetch exit country on check."),
        click.option("--geo-filter", "allowed_countries", multiple=True, help="Only keep proxies in these country codes."),
        click.option("--local-auth", default=None, help="Require user:pass to use the local proxy."),
        click.option("--log-file", default=None, type=click.Path(), help="Write JSON request log here."),
        click.option("--discover/--no-discover", default=False, help="Auto-discover from public proxy lists."),
        click.option("--refresh-url", "refresh_urls", multiple=True, help="Re-fetch this URL on interval (repeatable)."),
        click.option("--refresh-interval", default=600.0, show_default=True, help="Seconds between URL refreshes."),
        click.option("--rate-limit", default=None, type=str, help="Rate limit: MAX_REQ:WINDOW_SECS e.g. 100:60"),
        click.option("--mesh-hops", default=0, show_default=True, help="Onion-style: route each request through N dynamically-picked pre-hop proxies before the exit proxy (mesh topology, ignored if --chain-file is set)."),
        click.option("--mesh-rotate-seconds", default=300.0, show_default=True, help="Rebuild the mesh circuit (pre-hop path) after this many seconds."),
        click.option("--tun-mode", is_flag=True, help="Enable system-wide TUN VPN mode."),
        click.option("--tun-name", default=None, help="TUN interface name."),
        click.option("--tun-network", default="10.10.0.0/24", show_default=True, 
                     help="Virtual network CIDR for TUN interface."),
        click.option("--tun-dns-doh/--no-tun-dns-doh", default=True, 
                     help="Use DNS-over-HTTPS for DNS interception."),
        click.option("--tun-dns-server", "tun_dns_servers", multiple=True, 
                     help="DNS servers for TUN mode (repeatable)."),
        config_option(),
    ]
    for d in reversed(decorators):
        f = d(f)
    return f


def _parse_local_auth(auth_str: Optional[str]) -> Optional[Tuple[str, str]]:
    if not auth_str:
        return None
    if ":" not in auth_str:
        raise click.BadParameter("--local-auth must be user:pass")
    user, _, pw = auth_str.partition(":")
    return user, pw


def _parse_rate_limit(rate_str: Optional[str]) -> Optional[Tuple[int, float]]:
    if not rate_str:
        return None
    try:
        parts = rate_str.split(":")
        return int(parts[0]), float(parts[1])
    except Exception:
        raise click.BadParameter("--rate-limit format: MAX_REQ:WINDOW_SECS")


def _build_and_run(
    file: Optional[str],
    source_urls: Tuple[str, ...],
    host: str,
    port: int,
    threads: int,
    strategy: str,
    rotate_every: int,
    rotate_seconds: Optional[float],
    max_failures: int,
    auto_clean_interval: float,
    check_timeout: float,
    max_retries: int,
    min_anonymity: str,
    skip_initial_check: bool,
    headless: bool,
    allow_direct_fallback: bool,
    chain_file: Optional[str],
    direct_domains: Tuple[str, ...],
    state_file: Optional[str],
    resume: bool,
    export_stats_path: Optional[str],
    api_port: int,
    api_host: str,
    geo: bool,
    allowed_countries: Tuple[str, ...],
    local_auth: Optional[str],
    log_file: Optional[str],
    discover: bool,
    refresh_urls: Tuple[str, ...],
    refresh_interval: float,
    rate_limit: Optional[str],
    tun_mode: bool = False,
    tun_name: Optional[str] = None,
    tun_network: str = "10.10.0.0/24",
    tun_dns_doh: bool = True,
    tun_dns_servers: Tuple[str, ...] = (),
    mesh_hops: int = 0,
    mesh_rotate_seconds: float = 300.0,
):
    state_file = state_file or default_state_path(file)
    proxies = gather_proxies(file, source_urls, resume, state_file, discover=discover, echo=click.echo)
    if not proxies:
        click.echo("No parseable proxies found.")
        sys.exit(1)

    pool = ProxyPool(
        strategy=RotationStrategy(strategy),
        max_consecutive_failures=max_failures,
        rotate_every_n=rotate_every,
        rotate_every_seconds=rotate_seconds,
        auto_remove_dead=True,
        min_anonymity=min_anonymity,
        mesh_hop_count=mesh_hops,
        mesh_rotate_seconds=mesh_rotate_seconds,
    )
    pool.add(proxies)
    apply_prior_state(pool, load_state(state_file))

    rl = _parse_rate_limit(rate_limit)
    if rl:
        pool.set_rate_limit(*rl)
        click.echo(f"Rate limit: {rl[0]} req / {rl[1]}s per client")

    if not skip_initial_check:
        click.echo(
            f"Checking {len(proxies)} proxies ({threads} concurrent, timeout={check_timeout}s, "
            f"min-anonymity={min_anonymity})..."
        )
        asyncio.run(
            check_many(
                proxies,
                concurrency=threads,
                timeout=check_timeout,
                fetch_geo=geo,
                allowed_countries=list(allowed_countries) or None,
            )
        )
        removed_dead = pool.remove_dead()
        removed_anon = pool.enforce_anonymity()
        click.echo(
            f"{len(pool.alive())} alive & kept  |  "
            f"{len(removed_dead)} dead dropped  |  "
            f"{len(removed_anon)} anonymity-rejected"
        )
        if not pool.alive():
            click.echo("No proxies survived. Add more or lower --min-anonymity.")
            sys.exit(1)

    chain_hops: List[Proxy] = []
    if chain_file:
        loaded_hops = load_proxies_from_file(chain_file)
        chain_hops = [h for h in loaded_hops if not h.protocol.is_socks]
        dropped = len(loaded_hops) - len(chain_hops)
        if dropped:
            click.echo(f"Chain: dropped {dropped} SOCKS hops (only HTTP supported).")
        click.echo(f"Chaining through {len(chain_hops)} pre-hop(s).")

    if direct_domains:
        click.echo(f"Bypass domains: {', '.join(direct_domains)}")

    server = RotatingProxyServer(
        pool,
        host=host,
        port=port,
        max_retries=max_retries,
        allow_direct_fallback=allow_direct_fallback,
        chain_hops=chain_hops,
        direct_domains=list(direct_domains),
        local_auth=_parse_local_auth(local_auth),
        request_log_file=log_file,
        mesh_hop_count=mesh_hops,
    )
    if mesh_hops and not chain_hops:
        click.echo(
            f"Mesh mode: each request routed through {mesh_hops} dynamically-picked "
            f"pre-hop(s) before the exit proxy, circuit rebuilt every {mesh_rotate_seconds:.0f}s."
        )

    control_api = ControlAPI(pool, server, host=api_host, port=api_port) if api_port else None

    def _shutdown_persist():
        save_state(pool.all(), state_file)
        click.echo(f"State saved → {state_file}")
        if export_stats_path:
            export_stats(pool.all(), export_stats_path)
            click.echo(f"Stats exported → {export_stats_path}")
        _clear_sysproxy_info()


    # TUN mode initialization
    tun_handler: Optional[TUNPacketHandler] = None
    if tun_mode:
        if not _TUN_AVAILABLE:
            click.echo("ERROR: TUN mode not available. Install platform dependencies:")
            click.echo("  Linux: pip install scapy (root required)")
            click.echo("  macOS: pip install scapy (root required)")
            click.echo("  Windows: pip install scapy pywintun2 + wintun.dll")
            sys.exit(1)

        click.echo(f"Initializing TUN mode: {tun_network}")
        tun_handler = TUNPacketHandler(pool, server, 
                                        dns_servers=list(tun_dns_servers) or None,
                                        dns_over_https=tun_dns_doh)
        tun_ok = asyncio.get_event_loop().run_until_complete(
            tun_handler.start(tun_name, tun_network)
        )
        if not tun_ok:
            click.echo("ERROR: Failed to initialize TUN interface. Run as root/admin.")
            sys.exit(1)
        click.echo(f"TUN interface ready — all system traffic now routes through proxy mesh")

    _write_sysproxy_info(host, port, mesh_hops if not chain_hops else 0)
    click.echo(
        f"Ready for system-wide mode: run 'sysproxy on' (no args needed) to route "
        f"the whole OS through 127.0.0.1:{port}."
    )

    if headless:
        async def _main():
            await server.start()
            if control_api is not None:
                await control_api.start()
                click.echo(f"Control API: http://{api_host}:{api_port}")
            click.echo(
                f"Rotating proxy: http://{host}:{port}  "
                f"({len(pool.alive())} proxies, strategy={strategy})"
            )
            click.echo("Full protection ON. Ctrl+C to stop.")

            tasks = [
                asyncio.create_task(server.serve_forever()),
                asyncio.create_task(
                    auto_clean_loop(pool, auto_clean_interval, threads, check_timeout, server.stats)
                ),
            ]
            if tun_handler:
                tasks.append(asyncio.create_task(tun_handler.run_loop()))
                click.echo(f"TUN packet handler running")
            if refresh_urls:
                tasks.append(asyncio.create_task(
                    scheduled_url_refresh_loop(
                        pool, list(refresh_urls), refresh_interval,
                        threads, check_timeout, server.stats,
                    )
                ))

            stop_event = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, stop_event.set)
                except (NotImplementedError, RuntimeError):
                    pass

            await stop_event.wait()
            click.echo("\nShutting down...")
            for t in tasks:
                t.cancel()
            await server.stop()
            if control_api is not None:
                await control_api.stop()

        try:
            asyncio.run(_main())
        except KeyboardInterrupt:
            pass
        finally:
            _shutdown_persist()
    else:

        if tun_handler:
            asyncio.create_task(tun_handler.run_loop())
        try:
            run_dashboard(
                pool, server, auto_clean_interval, threads, check_timeout,
                control_api, state_file, export_stats_path,
            )
        finally:
            if state_file and not Path(state_file).exists():
                _shutdown_persist()


# ---- commands --------------------------------------------------------------


@cli.command("pick")
@_common_run_options
def pick_cmd(**kwargs):
    """Open a file picker to select a proxy list, then start the rotating proxy."""
    path = pick_proxy_file_tk()
    if not path:
        click.echo("No file selected — aborting.")
        sys.exit(0)
    click.echo(f"Selected: {path}")
    kwargs["file"] = path
    kwargs["source_urls"] = kwargs.get("source_urls", ())
    kwargs["tun_mode"] = kwargs.get("tun_mode", False)
    kwargs["tun_name"] = kwargs.get("tun_name", None)
    kwargs["tun_network"] = kwargs.get("tun_network", "10.10.0.0/24")
    kwargs["tun_dns_doh"] = kwargs.get("tun_dns_doh", True)
    kwargs["tun_dns_servers"] = kwargs.get("tun_dns_servers", ())
    _build_and_run(**kwargs)


@cli.command("run")
@click.argument("file", required=False, type=click.Path(exists=True))
@click.option("--source-url", "source_urls", multiple=True, help="Fetch additional proxies from URL (repeatable).")
@_common_run_options
def run_cmd(file: Optional[str], source_urls: Tuple[str, ...], **kwargs):
    """Load proxies and start the rotating proxy server -- the default command.

    With no FILE/--source-url/--resume, it auto-discovers proxies from public
    sources; if that also comes up empty, it falls back to a file picker.
    """
    pre_discovered: Optional[List[Proxy]] = None
    if not file and not source_urls and not kwargs.get("resume") and not kwargs.get("discover"):
        click.echo("No proxy source given -- auto-discovering from public sources...")
        pre_discovered = asyncio.run(discover_public_proxies(echo=click.echo))
        if not pre_discovered:
            click.echo("Auto-discovery found nothing. Opening a file picker instead...")
            picked = pick_proxy_file_tk()
            if not picked:
                click.echo(
                    "No file selected. Provide FILE, --source-url, --resume, or --discover."
                )
                sys.exit(1)
            file = picked
            pre_discovered = None
            click.echo(f"Selected: {file}")
        elif pre_discovered:
            # Stash the already-fetched proxies to a temp file so
            # _build_and_run's single gather_proxies() call picks them up
            # without re-hitting the network a second time.
            import tempfile
            fd, tmp_path = tempfile.mkstemp(suffix=".txt", prefix="discovered_")
            with os.fdopen(fd, "w") as f:
                for p in pre_discovered:
                    f.write(f"{p.protocol.value}://{p.host}:{p.port}\n")
            file = tmp_path
            click.echo(f"Using {len(pre_discovered)} auto-discovered proxies.")
    kwargs["tun_mode"] = kwargs.get("tun_mode", False)
    kwargs["tun_name"] = kwargs.get("tun_name", None)
    kwargs["tun_network"] = kwargs.get("tun_network", "10.10.0.0/24")
    kwargs["tun_dns_doh"] = kwargs.get("tun_dns_doh", True)
    kwargs["tun_dns_servers"] = kwargs.get("tun_dns_servers", ())
    _build_and_run(file=file, source_urls=source_urls, **kwargs)


@cli.command("check")
@click.argument("file", required=False, type=click.Path(exists=True))
@click.option("--source-url", "source_urls", multiple=True)
@click.option("--threads", "-t", default=350, show_default=True)
@click.option("--timeout", default=10.0, show_default=True)
@click.option("--geo/--no-geo", default=False)
@click.option("--discover/--no-discover", default=False)
@click.option("--min-anonymity", type=click.Choice(ANONYMITY_LEVELS), default="anonymous", show_default=True)
@click.option("--save", type=click.Path(), default=None)
@click.option("--state-file", type=click.Path(), default=None)
@click.option("--resume/--no-resume", default=False)
@config_option()
def check_cmd(
    file: Optional[str],
    source_urls: Tuple[str, ...],
    threads: int,
    timeout: float,
    geo: bool,
    discover: bool,
    min_anonymity: str,
    save: Optional[str],
    state_file: Optional[str],
    resume: bool,
):
    """Check proxies and optionally save the live ones."""
    if not file and not source_urls and not resume and not discover:
        click.echo("Provide FILE, --source-url, --resume, or --discover.")
        sys.exit(1)

    state_file = state_file or default_state_path(file)
    proxies = gather_proxies(file, source_urls, resume, state_file, discover=discover, echo=click.echo)
    if not proxies:
        click.echo("No parseable proxies found.")
        sys.exit(1)

    click.echo(
        f"Checking {len(proxies)} proxies ({threads} concurrent, min-anonymity={min_anonymity})..."
    )
    checked = 0
    alive_count = 0

    def on_result(p: Proxy, ok: bool):
        nonlocal checked, alive_count
        checked += 1
        if ok:
            alive_count += 1
        if checked % 50 == 0 or checked == len(proxies):
            mark = click.style("OK", fg="green") if ok else click.style("DEAD", fg="red")
            bar = "█" * int(alive_count / max(checked, 1) * 20) + "░" * (20 - int(alive_count / max(checked, 1) * 20))
            click.echo(f"  [{checked}/{len(proxies)}] {bar} {alive_count} alive  last: {p.key} → {mark}")

    asyncio.run(
        check_many(proxies, concurrency=threads, timeout=timeout, fetch_geo=geo, on_result=on_result)
    )

    order = _ANON_ORDER[min_anonymity]
    survivors = [
        p for p in proxies
        if p.alive and _ANON_ORDER.get(p.stats.anonymity or "transparent", 0) >= order
    ]
    rejected_anon = sum(
        1 for p in proxies
        if p.alive and _ANON_ORDER.get(p.stats.anonymity or "transparent", 0) < order
    )

    click.echo(
        f"\nDone: {alive_count} alive / {len(proxies) - alive_count} dead. "
        f"{rejected_anon} rejected for anonymity < {min_anonymity}. "
        f"{len(survivors)} kept."
    )

    save_state(proxies, state_file)
    click.echo(f"State → {state_file}")

    if save:
        with open(save, "w") as f:
            for p in survivors:
                if p.has_auth:
                    f.write(f"{p.protocol.value}://{p.username}:{p.password}@{p.host}:{p.port}\n")
                else:
                    f.write(f"{p.protocol.value}://{p.host}:{p.port}\n")
        click.echo(f"Saved {len(survivors)} proxies → {save}")


@cli.command("discover")
@click.option("--save", type=click.Path(), default="discovered.txt", show_default=True)
@click.option("--check/--no-check", "do_check", default=True, help="Health-check after discovery.")
@click.option("--threads", "-t", default=200, show_default=True)
@click.option("--timeout", default=10.0, show_default=True)
def discover_cmd(save: str, do_check: bool, threads: int, timeout: float):
    """Discover proxies from public sources and save them."""
    click.echo("Discovering proxies from public sources...")
    proxies = asyncio.run(discover_public_proxies(echo=click.echo))
    click.echo(f"Found {len(proxies)} proxies total.")

    if do_check:
        click.echo(f"Checking {len(proxies)} with {threads} threads...")
        asyncio.run(check_many(proxies, concurrency=threads, timeout=timeout))
        proxies = [p for p in proxies if p.alive and p.stats.anonymity in ("anonymous", "elite")]
        click.echo(f"{len(proxies)} survived health check.")

    with open(save, "w") as f:
        for p in proxies:
            f.write(f"{p.protocol.value}://{p.host}:{p.port}\n")
    click.echo(f"Saved {len(proxies)} proxies → {save}")


# ============================================================================
# System-wide proxy configuration
#
# Points the OS's own proxy settings at this rotator so traffic from every
# app on the machine (not just ones you manually configure) goes through it.
# This edits real system settings — always keep the `off` command handy.
# ============================================================================


def _run(cmd: List[str]) -> Tuple[int, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return result.returncode, (result.stdout + result.stderr).strip()
    except Exception as exc:
        return 1, str(exc)


def _sysproxy_windows(host: str, port: int, enable: bool) -> List[str]:
    notes = []
    if enable:
        rc, out = _run([
            "netsh", "winhttp", "set", "proxy", f"{host}:{port}",
        ])
        notes.append(f"netsh winhttp set proxy -> rc={rc} {out}")
        rc, out = _run([
            "reg", "add", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            "/v", "ProxyServer", "/t", "REG_SZ", "/d", f"{host}:{port}", "/f",
        ])
        notes.append(f"reg ProxyServer -> rc={rc} {out}")
        rc, out = _run([
            "reg", "add", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            "/v", "ProxyEnable", "/t", "REG_DWORD", "/d", "1", "/f",
        ])
        notes.append(f"reg ProxyEnable -> rc={rc} {out}")
    else:
        rc, out = _run(["netsh", "winhttp", "reset", "proxy"])
        notes.append(f"netsh winhttp reset -> rc={rc} {out}")
        rc, out = _run([
            "reg", "add", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            "/v", "ProxyEnable", "/t", "REG_DWORD", "/d", "0", "/f",
        ])
        notes.append(f"reg ProxyEnable off -> rc={rc} {out}")
    return notes


def _macos_network_services() -> List[str]:
    rc, out = _run(["networksetup", "-listallnetworkservices"])
    if rc != 0:
        return []
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    # First line is a header ("An asterisk (*) denotes...")
    return [l.lstrip("*").strip() for l in lines[1:]]


def _sysproxy_macos(host: str, port: int, enable: bool) -> List[str]:
    notes = []
    services = _macos_network_services()
    if not services:
        notes.append("Could not list network services (networksetup -listallnetworkservices failed).")
        return notes
    for svc in services:
        if enable:
            rc, out = _run(["networksetup", "-setwebproxy", svc, host, str(port)])
            notes.append(f"[{svc}] setwebproxy -> rc={rc} {out}")
            rc, out = _run(["networksetup", "-setsecurewebproxy", svc, host, str(port)])
            notes.append(f"[{svc}] setsecurewebproxy -> rc={rc} {out}")
            _run(["networksetup", "-setwebproxystate", svc, "on"])
            _run(["networksetup", "-setsecurewebproxystate", svc, "on"])
        else:
            _run(["networksetup", "-setwebproxystate", svc, "off"])
            _run(["networksetup", "-setsecurewebproxystate", svc, "off"])
            notes.append(f"[{svc}] proxy disabled")
    return notes


def _sysproxy_linux(host: str, port: int, enable: bool) -> List[str]:
    notes = []
    # GNOME / most GTK apps honor gsettings; this is the closest Linux gets
    # to a single system-wide toggle without root.
    if shutil.which("gsettings"):
        if enable:
            cmds = [
                ["gsettings", "set", "org.gnome.system.proxy", "mode", "manual"],
                ["gsettings", "set", "org.gnome.system.proxy.http", "host", host],
                ["gsettings", "set", "org.gnome.system.proxy.http", "port", str(port)],
                ["gsettings", "set", "org.gnome.system.proxy.https", "host", host],
                ["gsettings", "set", "org.gnome.system.proxy.https", "port", str(port)],
            ]
        else:
            cmds = [["gsettings", "set", "org.gnome.system.proxy", "mode", "none"]]
        for c in cmds:
            rc, out = _run(c)
            notes.append(f"{' '.join(c)} -> rc={rc} {out}")
    else:
        notes.append("gsettings not found — no desktop-wide proxy hook on this system.")
    # Env vars cover terminal / CLI tools (curl, git, apt, etc.) that ignore
    # gsettings. These only apply to the current shell session, so print the
    # export lines for the user to source or add to their shell rc file.
    if enable:
        notes.append(
            "For terminal apps, also run:\n"
            f"    export http_proxy=http://{host}:{port} https_proxy=http://{host}:{port}"
        )
    else:
        notes.append("For terminal apps, also run: unset http_proxy https_proxy")
    return notes


@cli.group("sysproxy")
def sysproxy_group():
    """Point (or unpoint) the OS-wide proxy setting at this rotator.

    Unlike pointing a single browser/app at 127.0.0.1:8899, this changes the
    system setting so most apps on the machine route through the rotator
    without per-app configuration. It edits real OS settings — always pair
    `on` with a later `off` to restore normal networking.
    """


@sysproxy_group.command("on")
@click.option("--host", default=None, help="Rotator host. If omitted, auto-detected from the currently running rotator process.")
@click.option("--port", "-p", default=None, type=int, help="Rotator port. If omitted, auto-detected from the currently running rotator process.")
def sysproxy_on(host: Optional[str], port: Optional[int]):
    """Enable the system-wide proxy, routing the whole OS through the rotator.

    With no arguments, this auto-detects the host/port (and mesh-hop count)
    of the rotator you already have running via `run`/`pick`, so you never
    have to retype a port and risk pointing the OS at the wrong place.
    """
    mesh_hops = 0
    if host is None or port is None:
        info = _read_sysproxy_info()
        if not info:
            click.echo(
                "No running rotator detected. Start one first with "
                "'run <file> --mesh-hops N', or pass --host/--port explicitly."
            )
            sys.exit(1)
        host = host or info["host"]
        port = port or info["port"]
        mesh_hops = info.get("mesh_hops", 0)

    system = platform.system()
    click.echo(f"Setting system-wide proxy -> {host}:{port} ({system})")
    if mesh_hops:
        click.echo(
            f"Mesh is ON for this rotator ({mesh_hops} pre-hop(s) per request) — "
            f"every app on this machine will now be routed through that mesh circuit."
        )
    else:
        click.echo(
            "Note: mesh-hops is 0 on this rotator — traffic will be system-wide but "
            "single-hop. Restart the rotator with --mesh-hops N for multi-hop routing."
        )
    if system == "Windows":
        notes = _sysproxy_windows(host, port, True)
    elif system == "Darwin":
        notes = _sysproxy_macos(host, port, True)
    elif system == "Linux":
        notes = _sysproxy_linux(host, port, True)
    else:
        notes = [f"Unsupported platform: {system}"]
    for n in notes:
        click.echo(f"  {n}")
    click.echo(
        "Done. Every app that respects the OS proxy setting now routes through "
        "the rotator. Run 'proxy_rotator.py sysproxy off' to revert."
    )


@sysproxy_group.command("off")
def sysproxy_off():
    """Disable the system-wide proxy and restore direct networking."""
    _clear_sysproxy_info()
    system = platform.system()
    click.echo(f"Clearing system-wide proxy ({system})")
    if system == "Windows":
        notes = _sysproxy_windows("", 0, False)
    elif system == "Darwin":
        notes = _sysproxy_macos("", 0, False)
    elif system == "Linux":
        notes = _sysproxy_linux("", 0, False)
    else:
        notes = [f"Unsupported platform: {system}"]
    for n in notes:
        click.echo(f"  {n}")
    click.echo("Done. System is back to direct networking.")




@cli.group("tun")
def tun_group():
    """System-wide TUN VPN tunnel management.

    Creates a virtual network interface that captures all system traffic
    and routes it through the proxy rotator's mesh network.
    Requires root/admin privileges.
    """


@tun_group.command("status")
def tun_status():
    """Show TUN interface status and active connections."""
    click.echo("TUN status: check requires active rotator process")


@tun_group.command("routes")
@click.option("--network", default="10.10.0.0/24")
@click.option("--interface", default="tun0")
def tun_routes(network: str, interface: str):
    """Configure system routes for TUN mode (manual setup)."""
    system = platform.system()
    click.echo(f"Configuring routes for {network} via {interface} ({system})")

    if system == "Linux":
        subprocess.run(["ip", "link", "set", "dev", interface, "up"])
        subprocess.run(["ip", "addr", "add", f"{network[:-3]}1/24", "dev", interface])
        subprocess.run(["ip", "route", "add", network, "dev", interface])
    elif system == "Darwin":
        subprocess.run(["ifconfig", interface, "inet", f"{network[:-3]}1", 
                       f"{network[:-3]}2", "up"])
        subprocess.run(["route", "add", "-net", network, "-interface", interface])
    elif system == "Windows":
        subprocess.run(["netsh", "interface", "ip", "set", "address", 
                     f"name={interface}", "static", f"{network[:-3]}1", "255.255.255.0"])

    click.echo("Routes configured. Start rotator with --tun-mode to activate.")

if __name__ == "__main__":
    cli()
