#!/usr/bin/env python3
"""End-to-end checks: Python gRPC client -> adapter -> C++ CLI."""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
import time
from pathlib import Path

import grpc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = PROJECT_ROOT / "generated"
sys.path.insert(0, str(GENERATED_DIR))

import airflow_correction_pb2 as pb2  # noqa: E402
import airflow_correction_pb2_grpc as pb2_grpc  # noqa: E402


def request(
    geometry_type: int,
    dimensions: dict[str, float],
    x: float,
    y: float,
    measured: float,
    inlet: float = 0.0,
    model_id: str = "AUTO",
) -> pb2.CorrectionRequest:
    return pb2.CorrectionRequest(
        geometry=pb2.GeometryRequest(type=geometry_type, dimensions_m=dimensions),
        sensor=pb2.SensorMeasurement(x_m=x, y_m=y, measured_velocity_mps=measured),
        inlet_velocity_mps=inlet,
        model_id=model_id,
        mesh_resolution=300,
        centerline_tolerance_m=0.02,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--port", default=51052, type=int)
    arguments = parser.parse_args()

    address = f"127.0.0.1:{arguments.port}"
    server = subprocess.Popen(
        [
            sys.executable,
            str(PROJECT_ROOT / "grpc_adapter" / "server.py"),
            "--port",
            str(arguments.port),
            "--exe",
            str(arguments.exe.resolve()),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        with grpc.insecure_channel(address) as channel:
            grpc.channel_ready_future(channel).result(timeout=10)
            stub = pb2_grpc.AirflowCorrectionServiceStub(channel)

            circle = stub.CalculateCorrection(
                request(pb2.GEOMETRY_TYPE_CIRCLE, {"radius": 2.0}, 0.0, 0.0, 3.0),
                timeout=10,
            )
            assert circle.success, circle
            assert abs(circle.correction_factor - 49.0 / 60.0) < 2e-3
            assert circle.model.capability == "FULL_FIELD"

            rectangle = stub.CalculateCorrection(
                request(
                    pb2.GEOMETRY_TYPE_RECTANGLE,
                    {"width": 4.0, "height": 3.0},
                    2.0,
                    2.0,
                    3.0,
                    4.0,
                ),
                timeout=10,
            )
            assert rectangle.success, rectangle
            assert abs(rectangle.correction_factor - 1.0 / 1.1406) < 1e-12
            assert rectangle.parameter_set_id == "RECT_4x3_V4"

            wei_rectangle = stub.CalculateCorrection(
                request(
                    pb2.GEOMETRY_TYPE_RECTANGLE,
                    {"width": 4.94, "height": 3.43},
                    0.4,
                    3.03,
                    1.8,
                    model_id="RECT_WEI2019_POINT",
                ),
                timeout=10,
            )
            assert wei_rectangle.success, wei_rectangle
            assert wei_rectangle.model.model_id == "RECT_WEI2019_POINT"
            assert wei_rectangle.model.capability == "FULL_FIELD"
            assert abs(wei_rectangle.mean_velocity_mps - 1.81913) < 0.002

            semicircle = stub.CalculateCorrection(
                request(
                    pb2.GEOMETRY_TYPE_SEMICIRCLE_ARCH,
                    {"width": 4.0, "height": 3.0},
                    2.0,
                    2.0,
                    3.0,
                    4.0,
                ),
                timeout=10,
            )
            assert semicircle.success, semicircle
            assert abs(semicircle.section_area_m2 - (4 + 2 * math.pi)) < 1e-12

            rejected = stub.CalculateCorrection(
                request(
                    pb2.GEOMETRY_TYPE_RECTANGLE,
                    {"width": 4.0, "height": 3.0},
                    2.2,
                    2.0,
                    3.0,
                    4.0,
                ),
                timeout=10,
            )
            assert not rejected.success
            assert rejected.error_code == "SENSOR_NOT_ON_REQUIRED_LINE"

        print("PASS gRPC circle -> C++")
        print("PASS gRPC rectangle -> C++")
        print("PASS gRPC Wei 2019 rectangle -> C++")
        print("PASS gRPC semicircle -> C++")
        print("PASS gRPC validation error propagation")
        print("All gRPC end-to-end checks passed.")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
