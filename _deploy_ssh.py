#!/usr/bin/env python3
"""Deploy tbankmitm to VPS via SCP + restart (paramiko)."""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
HOST = "188.127.237.61"
USER = "root"
PASSWORD = os.environ.get("TBANKMITM_SSH_PASSWORD", "")
REMOTE = "/root/tbankmitm/tbankmitm"

FILES = [
    "history.py",
    "bank_filter.py",
    "browser_ops_injector.py",
    "operation_detail.py",
    "panel_bridge.py",
    "transfer.py",
    "nonbank_connect_block.py",
    "bank_merchants_presets.json",
    "config.json",
    "mitm_addon_chain.py",
    "bank_tls_upstream.py",
    "start_vps.sh",
    "deploy_to_vps.sh",
]


def main() -> int:
    if not PASSWORD:
        print("Set TBANKMITM_SSH_PASSWORD", file=sys.stderr)
        return 1
    try:
        import paramiko
    except ImportError:
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
        import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=60)
    sftp = client.open_sftp()
    try:
        sftp.stat(REMOTE)
    except OSError:
        stdin, stdout, stderr = client.exec_command(f"mkdir -p {REMOTE}/panel_static")
        stdout.channel.recv_exit_status()

    for name in FILES:
        local = os.path.join(ROOT, name)
        if not os.path.isfile(local):
            print(f"skip missing {name}")
            continue
        remote = f"{REMOTE}/{name}"
        print(f"upload {name}")
        sftp.put(local, remote)

    ps = os.path.join(ROOT, "panel_static")
    if os.path.isdir(ps):
        for entry in os.listdir(ps):
            lp = os.path.join(ps, entry)
            if os.path.isfile(lp):
                sftp.put(lp, f"{REMOTE}/panel_static/{entry}")

    cmd = (
        f"cd {REMOTE} && sed -i 's/\\r$//' start_vps.sh deploy_to_vps.sh 2>/dev/null; "
        "pkill -f mitm_run_dump || true; sleep 2; "
        "export TBANKMITM_PUBLIC_IP=188.127.237.61 TBANKMITM_PANEL_ALLOW_ANY=1; "
        "nohup bash start_vps.sh >/tmp/tbankmitm.log 2>&1 & sleep 5; "
        "curl -s -o /dev/null -w 'api %{http_code}\\n' http://127.0.0.1:8082/api/operations; "
        "curl -s -o /dev/null -w 'logo %{http_code}\\n' "
        "'http://127.0.0.1:8082/panel-bank-logo?u=https%3A%2F%2Fimgproxy.cdn-tinkoff.ru%2Fcompressed95%2FaHR0cHM6Ly9icmFuZHMtcHJvZC5jZG4tdGlua29mZi5ydS9nZW5lcmFsX2xvZ28vd2lsZGJlcnJpZXMtYmFuay5wbmc%3D'; "
        "tail -15 /tmp/tbankmitm.log"
    )
    print("restart mitm...")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    sftp.close()
    client.close()
    return 0 if code == 0 else code


if __name__ == "__main__":
    raise SystemExit(main())
