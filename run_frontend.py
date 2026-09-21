#!/usr/bin/env python3
"""Start Streamlit on port 8051 and open it in the default browser."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from streamlit.web import cli as streamlit_cli


PROJECT_ROOT = Path(__file__).resolve().parent


def wait_until_ready(url: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.25)
    return False


def open_browser_when_ready(url: str, no_browser: bool) -> None:
    if not wait_until_ready(url, timeout=60.0):
        print("Frontend did not become ready within 60 seconds.", file=sys.stderr)
        return
    print(f"Frontend is ready: {url}")
    if not no_browser and not webbrowser.open(url, new=2):
        print(f"Browser could not be opened automatically. Open {url} manually.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8051)
    parser.add_argument("--grpc-address", default="127.0.0.1:51051")
    parser.add_argument("--no-browser", action="store_true")
    arguments = parser.parse_args()

    url = f"http://{arguments.host}:{arguments.port}"
    os.environ["AIRFLOW_GRPC_ADDRESS"] = arguments.grpc_address
    threading.Thread(
        target=open_browser_when_ready,
        args=(url, arguments.no_browser),
        daemon=True,
    ).start()

    sys.argv = [
        "streamlit",
        "run",
        str(PROJECT_ROOT / "frontend" / "app.py"),
        "--server.address",
        arguments.host,
        "--server.port",
        str(arguments.port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]

    print(f"Starting Streamlit frontend: {url}")
    return streamlit_cli.main()


if __name__ == "__main__":
    raise SystemExit(main())
