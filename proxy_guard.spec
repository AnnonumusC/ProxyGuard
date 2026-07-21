# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for ProxyGuard Ultimate v3
# Build: pyinstaller proxy_guard.spec

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ["proxy_guard.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=[
        ("config.example.json", "."),
        ("config.example.yaml", "."),
        ("README.md", "."),
    ],
    hiddenimports=[
        # click internals
        "click",
        "click.core",
        "click.decorators",
        # httpx internals
        "httpx",
        "httpx._client",
        "httpx._transports",
        # python-socks
        "python_socks",
        "python_socks.async_",
        "python_socks.async_.asyncio",
        # Optional: textual TUI
        "textual",
        "textual.app",
        "textual.containers",
        "textual.widgets",
        "rich",
        "rich.text",
        "rich.panel",
        # Optional: cryptography
        "cryptography",
        "cryptography.hazmat",
        "cryptography.hazmat.primitives",
        "cryptography.hazmat.primitives.ciphers",
        "cryptography.hazmat.primitives.ciphers.aead",
        "cryptography.hazmat.primitives.asymmetric",
        "cryptography.hazmat.primitives.asymmetric.x25519",
        "cryptography.hazmat.primitives.serialization",
        # Optional: yaml
        "yaml",
        # stdlib async
        "asyncio",
        "asyncio.streams",
        "asyncio.tasks",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # keep bundle small — scapy pulls in everything
        "scapy",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "PIL",
        "tkinter",
        "unittest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ProxyGuard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # keep console visible — this is a CLI tool
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Icon: generated from attached GIF by the build workflow
    icon="icon.ico",
    version_info={
        "FileDescription": "ProxyGuard Ultimate — Anonymous Proxy Rotator",
        "ProductName": "ProxyGuard",
        "FileVersion": "3.0.0.0",
        "ProductVersion": "3.0.0.0",
        "LegalCopyright": "MIT License",
        "OriginalFilename": "ProxyGuard.exe",
    },
)
