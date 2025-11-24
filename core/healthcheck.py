"""Healthcheck implementations for deployment targets."""

from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
from pathlib import Path
from typing import Iterable, Optional


def check_port(host: str, port: int, timeout: float = 3.0) -> bool:
    """Return True if a TCP connection to the host/port succeeds."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False


def check_http(host: str, port: int = 80, path: str = "/", timeout: float = 3.0, expected_status: int = 200) -> bool:
    """Return True if an HTTP request returns the expected status code."""

    connection = http.client.HTTPConnection(host, port=port, timeout=timeout)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status == expected_status
    except OSError:
        return False
    finally:
        connection.close()


def check_gpu(command: str = "nvidia-smi", timeout: float = 3.0) -> bool:
    """Return True if a GPU command can be executed successfully."""

    try:
        process = subprocess.run(
            [command, "-L"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False

    return process.returncode == 0 and bool(process.stdout.strip())


def check_disk(path: Path, minimum_free_gb: float) -> bool:
    """Return True if the path has at least the requested free disk space."""

    if not path.exists():
        return False

    stats = os.statvfs(path)
    free_bytes = stats.f_bavail * stats.f_frsize
    return free_bytes >= minimum_free_gb * 1024 * 1024 * 1024


def check_logs(log_path: Path, required_keywords: Optional[Iterable[str]] = None) -> bool:
    """Return True if the log file exists and contains all required keywords."""

    if not log_path.exists():
        return False

    content = log_path.read_text(errors="ignore")
    if required_keywords:
        return all(keyword in content for keyword in required_keywords)
    return bool(content.strip())


def serialize_health_summary(status: bool, metadata: Optional[dict] = None) -> str:
    """Serialize a healthcheck result into a JSON string."""

    payload = {"healthy": status, "metadata": metadata or {}}
    return json.dumps(payload)

