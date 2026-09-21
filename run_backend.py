#!/usr/bin/env python3
"""Start the airflow gRPC adapter and C++ calculation backend."""

from __future__ import annotations

import argparse
from pathlib import Path

from grpc_adapter.server import create_server


PROJECT_ROOT = Path(__file__).resolve().parent


def locate_executable(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend(
        [
            PROJECT_ROOT / "build-codex" / "airflow_cli.exe",
            PROJECT_ROOT / "build-release" / "airflow_cli.exe",
            PROJECT_ROOT / "build" / "Release" / "airflow_cli.exe",
            PROJECT_ROOT / "build" / "airflow_cli.exe",
            PROJECT_ROOT / "build" / "Debug" / "airflow_cli.exe",
            PROJECT_ROOT / "build-release" / "airflow_cli",
            PROJECT_ROOT / "build" / "airflow_cli",
        ]
    )
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved.is_file():
            return resolved
    searched = "\n".join(f"  - {item}" for item in candidates)
    raise FileNotFoundError(
        "airflow_cli executable was not found. Build the C++ project first.\n"
        f"Searched:\n{searched}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=51051)
    parser.add_argument("--exe", help="Path to airflow_cli executable")
    arguments = parser.parse_args()

    executable = locate_executable(arguments.exe)
    print(f"Starting backend on {arguments.host}:{arguments.port}")
    print(f"C++ executable: {executable}")
    server = create_server(executable)
    address = f"{arguments.host}:{arguments.port}"
    server.add_insecure_port(address)
    server.start()
    print(f"Backend is ready: {address}")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(grace=2).wait(timeout=3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
