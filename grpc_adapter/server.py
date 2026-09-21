#!/usr/bin/env python3
"""gRPC service adapter that delegates calculations to airflow_cli."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from concurrent import futures
from pathlib import Path

import grpc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = PROJECT_ROOT / "generated"
sys.path.insert(0, str(GENERATED_DIR))

import airflow_correction_pb2 as pb2  # noqa: E402
import airflow_correction_pb2_grpc as pb2_grpc  # noqa: E402


DEFAULT_MODEL_METADATA = {
    pb2.GEOMETRY_TYPE_CIRCLE: pb2.ModelMetadata(
        model_id="CIRCLE_POWER_1_7",
        name="圆形 1/7 次幂律完整风场",
        version="1.0.0",
        capability="FULL_FIELD",
        source="Classical fully-developed turbulent pipe engineering model",
    ),
    pb2.GEOMETRY_TYPE_RECTANGLE: pb2.ModelMetadata(
        model_id="RECT_ZHANG2022_CENTERLINE",
        name="Zhang 2022 矩形中央竖线校正",
        version="1.0.0",
        capability="DIRECT_CORRECTION",
        source="Zhang, Luo & Zou, Energy Science & Engineering 10 (2022)",
    ),
    pb2.GEOMETRY_TYPE_SEMICIRCLE_ARCH: pb2.ModelMetadata(
        model_id="SEMICIRCLE_ZHANG2022_CENTERLINE",
        name="Zhang 2022 半圆拱中央竖线校正",
        version="1.0.0",
        capability="DIRECT_CORRECTION",
        source="Zhang, Luo & Zou, Energy Science & Engineering 10 (2022)",
    ),
}

WEI2019_RECTANGLE_METADATA = pb2.ModelMetadata(
    model_id="RECT_WEI2019_POINT",
    name="Wei 2019 矩形任意点等效距离模型",
    version="1.0.0",
    capability="FULL_FIELD",
    source="Wei et al., Thermal Science 23(3A) (2019), 1513-1519",
)

MODEL_METADATA_BY_ID = {
    metadata.model_id: metadata
    for metadata in DEFAULT_MODEL_METADATA.values()
}
MODEL_METADATA_BY_ID[WEI2019_RECTANGLE_METADATA.model_id] = WEI2019_RECTANGLE_METADATA
RADIAL_SHAPES = {
    pb2.GEOMETRY_TYPE_RECTANGLE: ("rectangle", "RECTANGLE", ("width", "height")),
    pb2.GEOMETRY_TYPE_SEMICIRCLE_ARCH: ("semicircle", "SEMICIRCLE_ARCH", ("width", "height")),
    pb2.GEOMETRY_TYPE_TRAPEZOID: ("trapezoid", "TRAPEZOID", ("bottom_width", "top_width", "height")),
    pb2.GEOMETRY_TYPE_THREE_CENTER_ARCH: ("three-center", "THREE_CENTER_ARCH", ("width", "wall_height", "arch_rise", "crown_radius", "side_radius")),
}
for _type, (_, _prefix, _) in RADIAL_SHAPES.items():
    _metadata = pb2.ModelMetadata(
        model_id=_prefix + "_WEI_RADIAL", name="Wei radial equivalent-circle correction",
        version="2.0.0", capability="DIRECT_CORRECTION",
        source="Wei 2019 Eq.(5); radial geometry extension (accuracy pending validation)")
    MODEL_METADATA_BY_ID[_metadata.model_id] = _metadata
    if _type not in DEFAULT_MODEL_METADATA:
        DEFAULT_MODEL_METADATA[_type] = _metadata


def locate_executable(explicit: str | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("AIRFLOW_CLI"):
        candidates.append(Path(os.environ["AIRFLOW_CLI"]))
    candidates.extend(
        [
            # This local machine's application-control policy permits the
            # non-LTO debug build while it may block a newly linked release EXE.
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
    raise FileNotFoundError(f"airflow_cli executable was not found. Searched:\n{searched}")


def dimension(request: pb2.GeometryRequest, name: str) -> float:
    if name not in request.dimensions_m:
        raise ValueError(f"Missing geometry dimension: {name}")
    value = request.dimensions_m[name]
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"Geometry dimension {name} must be positive")
    return value


def geometry_area(geometry: pb2.GeometryRequest) -> float:
    if geometry.type == pb2.GEOMETRY_TYPE_TRAPEZOID:
        return (dimension(geometry, "bottom_width") + dimension(geometry, "top_width")) * dimension(geometry, "height") / 2
    if geometry.type == pb2.GEOMETRY_TYPE_THREE_CENTER_ARCH:
        w = dimension(geometry, "width")
        f = dimension(geometry, "arch_rise")
        R = dimension(geometry, "crown_radius")
        r = dimension(geometry, "side_radius")
        if "wall_height" not in geometry.dimensions_m:
            raise ValueError("Missing wall_height")
        h = geometry.dimensions_m["wall_height"]
        if not math.isfinite(h) or h < 0:
            raise ValueError("wall_height must be finite and nonnegative")
        dx, dy = w / 2 - r, R - f
        if not (R > r and r < w / 2 and R > f) or abs(math.hypot(dx, dy) - (R-r)) > 1e-8 * max(w, R, r):
            raise ValueError("Invalid three-center arc tangency")
        a = math.atan2(dy, dx)
        def arc_area(cx, cy, radius, start, end):
            return (radius*cx*(math.sin(end)-math.sin(start)) +
                    radius*cy*(math.cos(start)-math.cos(end)) +
                    radius*radius*(end-start))/2
        return (w*h/2 + arc_area(w-r,h,r,0,a) +
                arc_area(w/2,h+f-R,R,a,math.pi-a) +
                arc_area(r,h,r,math.pi-a,math.pi))
    if geometry.type == pb2.GEOMETRY_TYPE_CIRCLE:
        radius = dimension(geometry, "radius")
        return math.pi * radius * radius
    if geometry.type == pb2.GEOMETRY_TYPE_RECTANGLE:
        return dimension(geometry, "width") * dimension(geometry, "height")
    if geometry.type == pb2.GEOMETRY_TYPE_SEMICIRCLE_ARCH:
        width = dimension(geometry, "width")
        height = dimension(geometry, "height")
        radius = width / 2.0
        if height < radius:
            raise ValueError("Semicircle-arch height must be at least width/2")
        return width * (height - radius) + 0.5 * math.pi * radius * radius
    if geometry.type in (
        pb2.GEOMETRY_TYPE_TRAPEZOID,
        pb2.GEOMETRY_TYPE_THREE_CENTER_ARCH,
    ):
        raise NotImplementedError("This geometry is reserved but has no verified model")
    raise ValueError("Unknown geometry type")


class AirflowCorrectionAdapter(pb2_grpc.AirflowCorrectionServiceServicer):
    def __init__(self, executable: Path):
        self._executable = executable

    def ValidateGeometry(self, request, context):  # noqa: N802
        try:
            area = geometry_area(request)
            return pb2.GeometryValidationResponse(valid=True, area_m2=area)
        except (ValueError, NotImplementedError) as error:
            return pb2.GeometryValidationResponse(valid=False, errors=[str(error)])

    def ListApplicableModels(self, request, context):  # noqa: N802
        try:
            geometry_area(request.geometry)
        except (ValueError, NotImplementedError):
            return pb2.ModelListResponse()
        metadata = DEFAULT_MODEL_METADATA.get(request.geometry.type)
        models = [metadata] if metadata else []
        if request.geometry.type == pb2.GEOMETRY_TYPE_RECTANGLE:
            models.append(WEI2019_RECTANGLE_METADATA)
        if request.geometry.type in RADIAL_SHAPES:
            radial = MODEL_METADATA_BY_ID[RADIAL_SHAPES[request.geometry.type][1] + "_WEI_RADIAL"]
            if not any(m.model_id == radial.model_id for m in models):
                models.append(radial)
        return pb2.ModelListResponse(models=models)

    def CalculateCorrection(self, request, context):  # noqa: N802
        try:
            command = self._build_command(request)
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
            payload = json.loads(completed.stdout)
            if completed.returncode != 0 or not payload.get("success"):
                return pb2.CorrectionResponse(
                    success=False,
                    error_code=payload.get("error_code", "CPP_BACKEND_ERROR"),
                    message=payload.get("message", completed.stderr or "C++ backend failed"),
                )

            warnings = []
            if payload.get("warning"):
                warnings.append(payload["warning"])
            metadata = MODEL_METADATA_BY_ID.get(
                payload.get("model_id", ""),
                DEFAULT_MODEL_METADATA.get(request.geometry.type, pb2.ModelMetadata()),
            )
            return pb2.CorrectionResponse(
                success=True,
                section_area_m2=payload["section_area_m2"],
                correction_factor=payload["correction_factor"],
                mean_velocity_mps=payload["mean_velocity_mps"],
                air_volume_m3ps=payload["air_volume_m3ps"],
                confidence_level=payload["confidence_level"],
                model=metadata,
                warnings=warnings,
                parameter_set_id=payload.get("parameter_set_id", ""),
                integration_relative_error=payload.get("integration_relative_error", 0.0),
                integration_converged=payload.get("integration_converged", True),
                radial_eta=payload.get("radial_eta", 0),
                equivalent_radius_m=payload.get("equivalent_radius_m", 0),
                equivalent_wall_distance_m=payload.get("equivalent_wall_distance_m", 0),
                true_wall_distance_m=payload.get("true_wall_distance_m", 0),
            )
        except subprocess.TimeoutExpired:
            return pb2.CorrectionResponse(
                success=False,
                error_code="CPP_BACKEND_TIMEOUT",
                message="C++ calculation exceeded 30 seconds",
            )
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            return pb2.CorrectionResponse(
                success=False,
                error_code="INVALID_ARGUMENT",
                message=str(error),
            )
        except Exception as error:  # defensive RPC boundary
            return pb2.CorrectionResponse(
                success=False,
                error_code="INTERNAL_ERROR",
                message=str(error),
            )

    def CalculateField(self, request, context):  # noqa: N802
        context.abort(
            grpc.StatusCode.UNIMPLEMENTED,
            "Field grid transport is reserved for the next version",
        )

    def _build_command(self, request: pb2.CorrectionRequest) -> list[str]:
        geometry_area(request.geometry)
        sensor = request.sensor
        if not math.isfinite(sensor.measured_velocity_mps) or sensor.measured_velocity_mps <= 0:
            raise ValueError("Measured velocity must be positive")

        base = [str(self._executable)]
        requested = request.model_id or "AUTO"
        radial = RADIAL_SHAPES.get(request.geometry.type)
        if radial and (requested == radial[1] + "_WEI_RADIAL" or
                       (requested == "AUTO" and request.geometry.type in (
                           pb2.GEOMETRY_TYPE_TRAPEZOID, pb2.GEOMETRY_TYPE_THREE_CENTER_ARCH))):
            values = [request.geometry.dimensions_m[name] for name in radial[2]]
            roughness = request.absolute_roughness_m if request.HasField("absolute_roughness_m") else 0.0055
            if not math.isfinite(roughness) or roughness <= 0:
                raise ValueError("absolute_roughness_m must be positive and finite")
            command = base + [radial[0] + "-wei-radial"] + list(map(str, values))
            command += list(map(str, [sensor.x_m, sensor.y_m, sensor.measured_velocity_mps, roughness]))
            has_x, has_y = request.HasField("mapping_center_x_m"), request.HasField("mapping_center_y_m")
            if has_x != has_y:
                raise ValueError("Both mapping center coordinates are required")
            if has_x:
                command += [str(request.mapping_center_x_m), str(request.mapping_center_y_m)]
            return command
        if request.geometry.type == pb2.GEOMETRY_TYPE_CIRCLE:
            radius = dimension(request.geometry, "radius")
            resolution = request.mesh_resolution or 300
            return base + [
                "circle",
                str(radius),
                str(sensor.x_m),
                str(sensor.y_m),
                str(sensor.measured_velocity_mps),
                str(resolution),
            ]
        if request.geometry.type == pb2.GEOMETRY_TYPE_RECTANGLE:
            requested_model = request.model_id or "AUTO"
            if requested_model == "RECT_WEI2019_POINT":
                shape = "rectangle-wei2019"
            elif requested_model in ("AUTO", "RECT_ZHANG2022_CENTERLINE"):
                shape = "rectangle"
            else:
                raise ValueError(f"Unsupported rectangle model_id: {requested_model}")
        elif request.geometry.type == pb2.GEOMETRY_TYPE_SEMICIRCLE_ARCH:
            shape = "semicircle"
        else:
            raise ValueError("No implemented model for this geometry")

        width = dimension(request.geometry, "width")
        height = dimension(request.geometry, "height")
        command = base + [
            shape,
            str(width),
            str(height),
            str(sensor.x_m),
            str(sensor.y_m),
            str(sensor.measured_velocity_mps),
        ]
        if shape == "rectangle-wei2019":
            return command
        return command + [str(request.inlet_velocity_mps)]


def create_server(executable: Path, workers: int = 8) -> grpc.Server:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=workers))
    pb2_grpc.add_AirflowCorrectionServiceServicer_to_server(
        AirflowCorrectionAdapter(executable), server
    )
    return server


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=51051, type=int)
    parser.add_argument("--exe", help="Path to airflow_cli executable")
    arguments = parser.parse_args()

    executable = locate_executable(arguments.exe)
    server = create_server(executable)
    address = f"{arguments.host}:{arguments.port}"
    server.add_insecure_port(address)
    server.start()
    print(f"Airflow gRPC adapter listening on {address}")
    print(f"C++ backend: {executable}")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(grace=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
