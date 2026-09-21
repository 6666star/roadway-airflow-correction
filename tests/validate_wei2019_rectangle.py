#!/usr/bin/env python3
"""Validate the Wei et al. (2019) rectangle model against all 24 paper points."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = PROJECT_ROOT / "data" / "wei2019_rectangle_points.csv"


@dataclass(frozen=True)
class PointResult:
    point_id: str
    measured: float
    paper_calculated: float
    model_calculated: float
    point_error_pct: float
    inferred_mean: float
    inverse_error_pct: float


def run_model(
    executable: Path,
    width: float,
    height: float,
    x_from_left: float,
    y_from_top: float,
    measured: float,
    roughness: float,
) -> dict:
    completed = subprocess.run(
        [
            str(executable),
            "rectangle-wei2019",
            str(width),
            str(height),
            str(x_from_left),
            str(height - y_from_top),
            str(measured),
            str(roughness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"CLI did not return JSON: exit={completed.returncode}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        ) from error
    if completed.returncode != 0 or not payload.get("success"):
        raise RuntimeError(f"Model failed: {payload}")
    return payload


def validate(executable: Path, data_path: Path) -> tuple[list[PointResult], dict]:
    width = 4.94
    height = 3.43
    published_mean = 1.94
    roughness = 0.0055

    with data_path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))

    results: list[PointResult] = []
    for row in rows:
        measured = float(row["measured_velocity_mps"])
        payload = run_model(
            executable,
            width,
            height,
            float(row["x_from_left_m"]),
            float(row["y_from_top_m"]),
            measured,
            roughness,
        )
        phi = 1.0 / float(payload["correction_factor"])
        calculated = published_mean * phi
        inferred_mean = float(payload["mean_velocity_mps"])
        results.append(
            PointResult(
                point_id=row["point_id"],
                measured=measured,
                paper_calculated=float(row["paper_calculated_velocity_mps"]),
                model_calculated=calculated,
                point_error_pct=abs(calculated - measured) / measured * 100.0,
                inferred_mean=inferred_mean,
                inverse_error_pct=abs(inferred_mean - published_mean) / published_mean * 100.0,
            )
        )

    point_errors = [item.point_error_pct for item in results]
    inverse_errors = [item.inverse_error_pct for item in results]
    paper_differences = [
        abs(item.model_calculated - item.paper_calculated) for item in results
    ]
    summary = {
        "paper": "Wei et al. (2019), Thermal Science 23(3A), 1513-1519",
        "width_m": width,
        "height_m": height,
        "published_mean_velocity_mps": published_mean,
        "absolute_roughness_m": roughness,
        "point_count": len(results),
        "mean_absolute_point_error_pct": sum(point_errors) / len(point_errors),
        "maximum_point_error_pct": max(point_errors),
        "points_over_5_pct": sum(error > 5.0 for error in point_errors),
        "mean_absolute_inverse_error_pct": sum(inverse_errors) / len(inverse_errors),
        "maximum_inverse_error_pct": max(inverse_errors),
        "maximum_difference_from_rounded_paper_calculation_mps": max(paper_differences),
    }
    return results, summary


def markdown_report(results: list[PointResult], summary: dict, executable: Path) -> str:
    lines = [
        "# Wei 2019 矩形巷道点风速模型验证报告",
        "",
        "## 验证配置",
        "",
        f"- 可执行文件：`{executable}`",
        f"- 断面：{summary['width_m']} m × {summary['height_m']} m",
        f"- 论文断面平均风速：{summary['published_mean_velocity_mps']} m/s",
        f"- 绝对粗糙度：{summary['absolute_roughness_m']} m",
        f"- 测点数：{summary['point_count']}",
        "",
        "## 汇总结果",
        "",
        "| 指标 | 本次计算 |",
        "|---|---:|",
        f"| 点风速平均绝对误差 | {summary['mean_absolute_point_error_pct']:.4f}% |",
        f"| 点风速最大误差 | {summary['maximum_point_error_pct']:.4f}% |",
        f"| 点风速误差超过5%的点 | {summary['points_over_5_pct']} |",
        f"| 单点反演平均风速的平均绝对误差 | {summary['mean_absolute_inverse_error_pct']:.4f}% |",
        f"| 单点反演平均风速的最大误差 | {summary['maximum_inverse_error_pct']:.4f}% |",
        f"| 与论文表2舍入计算值的最大差 | {summary['maximum_difference_from_rounded_paper_calculation_mps']:.6f} m/s |",
        "",
        "## 逐点结果",
        "",
        "| 点号 | 实测风速 | 论文计算值 | 本模型计算值 | 点风速误差 | 反演平均风速 | 反演误差 |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in results:
        lines.append(
            f"| {item.point_id} | {item.measured:.2f} | {item.paper_calculated:.2f} | "
            f"{item.model_calculated:.4f} | {item.point_error_pct:.4f}% | "
            f"{item.inferred_mean:.4f} | {item.inverse_error_pct:.4f}% |"
        )

    lines.extend(
        [
            "",
            "## 结论",
            "",
            "本实现能够复现论文式(5)和式(6)对应的表2计算结果。按论文24个测点，",
            "多数点误差不超过5%，但仍存在超过5%的点，因此该模型适合作为规则、稳定",
            "矩形直巷的工程近似，不能声称任意点均达到5%以内。论文没有验证紧贴壁面",
            "以及其他尺寸矩形断面的准确性。",
            "",
            "这里的反演误差是把每个实测点单独用于反演断面平均风速，再与论文给出的",
            "1.94 m/s 断面平均风速比较得到的。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()

    executable = arguments.exe.resolve()
    if not executable.exists():
        parser.error(f"Executable does not exist: {executable}")

    results, summary = validate(executable, arguments.data.resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if arguments.report:
        report_path = arguments.report.resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            markdown_report(results, summary, executable),
            encoding="utf-8",
        )
        print(f"Report written to {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
