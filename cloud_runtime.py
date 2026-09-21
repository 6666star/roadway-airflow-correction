"""Build the unchanged C++ core and share one loopback gRPC server per process."""
from __future__ import annotations
import atexit
import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
import grpc
import streamlit as st

ROOT = Path(__file__).resolve().parent

def source_revision() -> str:
    digest = hashlib.sha256()
    files = [ROOT / "CMakeLists.txt", *sorted((ROOT / "src").glob("*.cpp")),
             *sorted((ROOT / "include").rglob("*.hpp")), *sorted((ROOT / "include").rglob("*.h"))]
    for path in files:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]

def build_executable(revision: str) -> Path:
    build = ROOT / ".build-cloud" / revision
    suffix = ".exe" if os.name == "nt" else ""
    candidates = [build / ("airflow_cli" + suffix), build / "Release" / ("airflow_cli" + suffix)]
    existing = next((p for p in candidates if p.is_file()), None)
    if existing:
        return existing
    commands = [["cmake", "-S", str(ROOT), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"],
                ["cmake", "--build", str(build), "--config", "Release", "--target", "airflow_cli", "-j", "2"]]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=240)
        if result.returncode:
            raise RuntimeError(f"Build failed: {result.stdout}\n{result.stderr}")
    executable = next((p for p in candidates if p.is_file()), None)
    if executable is None:
        raise RuntimeError("CMake did not produce airflow_cli")
    return executable

@dataclass
class Backend:
    server: object
    address: str
    executable: Path

@st.cache_resource(show_spinner=False)
def _start_backend(revision: str) -> Backend:
    from grpc_adapter.server import create_server
    executable = build_executable(revision)
    server = create_server(executable, workers=4)
    port = server.add_insecure_port("127.0.0.1:0")
    if port == 0:
        raise RuntimeError("Cannot bind local computation service")
    address = f"127.0.0.1:{port}"
    server.start()
    try:
        with grpc.insecure_channel(address) as channel:
            grpc.channel_ready_future(channel).result(timeout=10)
    except Exception:
        server.stop(0).wait()
        raise
    atexit.register(lambda: server.stop(0).wait())
    return Backend(server, address, executable)

def start_backend() -> Backend:
    return _start_backend(source_revision())
