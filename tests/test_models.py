#!/usr/bin/env python3
"""Cross-check the C++ models against analytical and published examples."""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(executable: Path, *arguments: object, expect_success: bool = True) -> dict:
    completed = subprocess.run(
        [str(executable), *(str(value) for value in arguments)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(
            f"CLI did not return JSON. exit={completed.returncode}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        ) from error

    if expect_success:
        assert completed.returncode == 0, payload
        assert payload["success"] is True, payload
    else:
        assert completed.returncode != 0, payload
        assert payload["success"] is False, payload
    return payload


def assert_close(actual: float, expected: float, tolerance: float, label: str) -> None:
    difference = abs(actual - expected)
    if difference > tolerance:
        raise AssertionError(
            f"{label}: actual={actual:.12g}, expected={expected:.12g}, "
            f"difference={difference:.3g}, tolerance={tolerance:.3g}"
        )


def test_circle_center(executable: Path) -> None:
    measured = 3.0
    radius = 2.0
    payload = run(executable, "circle", radius, 0.0, 0.0, measured, 500)

    expected_factor = 49.0 / 60.0
    expected_mean = measured * expected_factor
    expected_flow = math.pi * radius**2 * expected_mean

    # Midpoint integration is checked against the analytical 1/7-power result.
    assert_close(payload["correction_factor"], expected_factor, 1.5e-3, "circle Ku")
    assert_close(payload["mean_velocity_mps"], expected_mean, 5e-3, "circle mean")
    assert_close(payload["air_volume_m3ps"], expected_flow, 7e-2, "circle flow")
    assert payload["integration_converged"] is True
    assert payload["model_capability"] == "FULL_FIELD"


def test_circle_off_center(executable: Path) -> None:
    radius = 2.0
    measured = 2.4
    sensor_radius = 1.0
    payload = run(executable, "circle", radius, sensor_radius, 0.0, measured, 500)

    phi_sensor = (1.0 - sensor_radius / radius) ** (1.0 / 7.0)
    expected_factor = (49.0 / 60.0) / phi_sensor
    assert_close(payload["correction_factor"], expected_factor, 1.5e-3, "off-center Ku")


def test_rectangle_log_zone(executable: Path) -> None:
    # Zhang 2022, rectangle 4 m x 3 m, inlet velocity 4 m/s.
    # d=1 m makes ln(d)=0, so u/mean=1.1406.
    measured = 3.0
    payload = run(executable, "rectangle", 4.0, 3.0, 2.0, 2.0, measured, 4.0)
    expected_factor = 1.0 / 1.1406
    assert_close(payload["correction_factor"], expected_factor, 1e-12, "rectangle log Ku")
    assert_close(payload["mean_velocity_mps"], measured * expected_factor, 1e-12, "rectangle mean")
    assert payload["parameter_set_id"] == "RECT_4x3_V4"
    assert payload["model_capability"] == "DIRECT_CORRECTION"


def test_rectangle_core_zone(executable: Path) -> None:
    # d=1.4 m lies in the published [1.25, 1.50] core interval.
    measured = 3.0
    payload = run(executable, "rectangle", 4.0, 3.0, 2.0, 1.6, measured, 4.0)
    expected_factor = 1.0 / 1.1850
    assert_close(payload["correction_factor"], expected_factor, 1e-12, "rectangle core Ku")


def test_wei2019_rectangle_equation(executable: Path) -> None:
    width = 4.94
    height = 3.43
    roughness = 0.0055
    x_from_left = 0.40
    y_from_top = 0.40
    sensor_y = height - y_from_top
    measured = 1.80

    payload = run(
        executable,
        "rectangle-wei2019",
        width,
        height,
        x_from_left,
        sensor_y,
        measured,
        roughness,
    )

    r0 = width * height / (width + height)
    a = abs(x_from_left - width / 2.0)
    b = abs(sensor_y - height / 2.0)
    delta = r0 - 2.0 * a * b / (a + b)
    phi = (
        math.log(delta) - math.log(roughness) + 3.4
    ) / (
        math.log(r0) - math.log(roughness) + 1.9
    )

    assert_close(payload["correction_factor"], 1.0 / phi, 1e-12, "Wei 2019 Ku")
    assert_close(payload["mean_velocity_mps"], measured / phi, 1e-12, "Wei 2019 mean")
    assert payload["model_id"] == "RECT_WEI2019_POINT"
    assert payload["model_capability"] == "FULL_FIELD"


def test_wei2019_all_24_published_points(executable: Path) -> None:
    width = 4.94
    height = 3.43
    published_mean = 1.94
    roughness = 0.0055
    data_path = PROJECT_ROOT / "data" / "wei2019_rectangle_points.csv"

    point_errors = []
    inverse_errors = []
    calculated_differences = []
    with data_path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))

    assert len(rows) == 24
    for row in rows:
        measured = float(row["measured_velocity_mps"])
        payload = run(
            executable,
            "rectangle-wei2019",
            width,
            height,
            float(row["x_from_left_m"]),
            height - float(row["y_from_top_m"]),
            measured,
            roughness,
        )
        phi = 1.0 / payload["correction_factor"]
        predicted_point = published_mean * phi
        point_errors.append(abs(predicted_point - measured) / measured * 100.0)
        inverse_errors.append(
            abs(payload["mean_velocity_mps"] - published_mean) / published_mean * 100.0
        )
        calculated_differences.append(
            abs(predicted_point - float(row["paper_calculated_velocity_mps"]))
        )

    # Equation (5) with epsilon=0.0055 reproduces rounded Table 2 values.
    assert max(calculated_differences) < 0.006
    assert_close(sum(point_errors) / len(point_errors), 3.11, 0.03, "Wei 2019 mean point error")
    assert_close(max(point_errors), 8.36, 0.05, "Wei 2019 maximum point error")
    assert sum(error > 5.0 for error in point_errors) == 5
    assert_close(sum(inverse_errors) / len(inverse_errors), 3.103, 0.01, "Wei 2019 mean inverse error")
    assert_close(max(inverse_errors), 7.715, 0.01, "Wei 2019 maximum inverse error")


def test_wei2019_reject_wall_sensor(executable: Path) -> None:
    payload = run(
        executable,
        "rectangle-wei2019",
        4.94,
        3.43,
        0.0,
        0.0,
        1.8,
        0.0055,
        expect_success=False,
    )
    assert payload["error_code"] == "SENSOR_TOO_CLOSE_TO_WALL"


def test_semicircle_log_zone(executable: Path) -> None:
    # Zhang 2022, semicircle arch 4 m x 3 m, inlet velocity 4 m/s.
    # d=1 m gives u/mean=1.1055.
    measured = 3.0
    payload = run(executable, "semicircle", 4.0, 3.0, 2.0, 2.0, measured, 4.0)
    expected_factor = 1.0 / 1.1055
    expected_area = 4.0 * 1.0 + 0.5 * math.pi * 2.0**2
    assert_close(payload["correction_factor"], expected_factor, 1e-12, "semicircle Ku")
    assert_close(payload["section_area_m2"], expected_area, 1e-12, "semicircle area")
    assert payload["parameter_set_id"] == "SEMI_4x3_V4"


def test_all_published_parameter_rows(executable: Path) -> None:
    """Check A, B and core ratio for every Zhang 2022 row stored by C++."""
    rows = [
        # command, W, H, inlet velocity, log end, core end, A, B, C
        ("rectangle", 4.0, 3.0, 0.8, 1.25, 1.50, 1.1839, 0.1633, 1.2250),
        ("rectangle", 4.0, 3.0, 2.0, 1.25, 1.50, 1.1573, 0.1391, 1.2100),
        ("rectangle", 4.0, 3.0, 4.0, 1.25, 1.50, 1.1406, 0.1267, 1.1850),
        ("rectangle", 4.0, 3.0, 6.0, 1.25, 1.50, 1.1332, 0.1189, 1.1750),
        ("rectangle", 4.0, 3.0, 8.0, 1.25, 1.50, 1.1273, 0.1146, 1.1663),
        ("rectangle", 5.0, 3.5, 0.8, 1.50, 1.75, 1.1605, 0.1686, 1.2250),
        ("rectangle", 5.0, 3.5, 2.0, 1.50, 1.75, 1.1179, 0.1221, 1.1750),
        ("rectangle", 5.0, 3.5, 4.0, 1.50, 1.75, 1.1065, 0.1113, 1.1575),
        ("rectangle", 5.0, 3.5, 6.0, 1.50, 1.75, 1.0999, 0.1050, 1.1470),
        ("rectangle", 5.0, 3.5, 8.0, 1.50, 1.75, 1.0924, 0.0968, 1.1338),
        ("rectangle", 6.0, 4.0, 0.8, 1.70, 2.00, 1.1171, 0.1430, 1.1875),
        ("rectangle", 6.0, 4.0, 2.0, 1.70, 2.00, 1.0899, 0.1084, 1.1550),
        ("rectangle", 6.0, 4.0, 4.0, 1.70, 2.00, 1.0796, 0.0964, 1.1350),
        ("rectangle", 6.0, 4.0, 6.0, 1.70, 2.00, 1.0596, 0.0723, 1.0970),
        ("rectangle", 6.0, 4.0, 8.0, 1.70, 2.00, 1.0718, 0.0866, 1.1200),
        ("semicircle", 4.0, 3.0, 0.8, 1.25, 1.50, 1.1730, 0.1530, 1.2125),
        ("semicircle", 4.0, 3.0, 2.0, 1.25, 1.50, 1.1157, 0.1075, 1.1450),
        ("semicircle", 4.0, 3.0, 4.0, 1.25, 1.50, 1.1055, 0.0975, 1.1275),
        ("semicircle", 4.0, 3.0, 6.0, 1.25, 1.50, 1.0985, 0.0920, 1.1180),
        ("semicircle", 4.0, 3.0, 8.0, 1.25, 1.50, 1.0941, 0.0881, 1.1113),
        ("semicircle", 4.5, 3.3, 0.8, 1.60, 1.65, 1.1476, 0.1473, 1.2000),
        ("semicircle", 4.5, 3.3, 2.0, 1.60, 1.65, 1.1020, 0.1038, 1.1350),
        ("semicircle", 4.5, 3.3, 4.0, 1.60, 1.65, 1.0894, 0.0908, 1.1175),
        ("semicircle", 4.5, 3.3, 6.0, 1.60, 1.65, 1.0827, 0.0840, 1.1070),
        ("semicircle", 4.5, 3.3, 8.0, 1.60, 1.65, 1.0793, 0.0806, 1.1012),
    ]

    measured = 2.75
    log_distance = 0.8
    for command, width, height, inlet, log_end, core_end, a, b, core in rows:
        assert log_distance <= log_end
        log_y = height - log_distance
        log_payload = run(
            executable,
            command,
            width,
            height,
            width / 2.0,
            log_y,
            measured,
            inlet,
        )
        expected_log_ratio = a + b * math.log(log_distance)
        assert_close(
            log_payload["correction_factor"],
            1.0 / expected_log_ratio,
            1e-12,
            f"{command} {width}x{height} V={inlet} log coefficient",
        )

        core_distance = (log_end + core_end) / 2.0
        core_y = height - core_distance
        core_payload = run(
            executable,
            command,
            width,
            height,
            width / 2.0,
            core_y,
            measured,
            inlet,
        )
        assert_close(
            core_payload["correction_factor"],
            1.0 / core,
            1e-12,
            f"{command} {width}x{height} V={inlet} core ratio",
        )


def test_reject_off_centerline(executable: Path) -> None:
    payload = run(
        executable,
        "rectangle",
        4.0,
        3.0,
        2.2,
        2.0,
        3.0,
        4.0,
        expect_success=False,
    )
    assert payload["error_code"] == "SENSOR_NOT_ON_REQUIRED_LINE"


def test_reject_unknown_parameter_set(executable: Path) -> None:
    payload = run(
        executable,
        "rectangle",
        4.2,
        3.0,
        2.1,
        2.0,
        3.0,
        4.0,
        expect_success=False,
    )
    assert payload["error_code"] == "MODEL_NOT_APPLICABLE"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    arguments = parser.parse_args()
    executable = arguments.exe.resolve()
    if not executable.exists():
        parser.error(f"Executable does not exist: {executable}")

    tests = [
        test_circle_center,
        test_circle_off_center,
        test_rectangle_log_zone,
        test_rectangle_core_zone,
        test_wei2019_rectangle_equation,
        test_wei2019_all_24_published_points,
        test_wei2019_reject_wall_sensor,
        test_semicircle_log_zone,
        test_all_published_parameter_rows,
        test_reject_off_centerline,
        test_reject_unknown_parameter_set,
    ]

    for test in tests:
        test(executable)
        print(f"PASS {test.__name__}")

    print(f"All {len(tests)} model checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
