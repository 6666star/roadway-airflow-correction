#!/usr/bin/env python3
"""Preserved V1 Streamlit client; available through the V2 navigation."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import grpc
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = PROJECT_ROOT / "generated"
sys.path.insert(0, str(GENERATED_DIR))

import airflow_correction_pb2 as pb2  # noqa: E402
import airflow_correction_pb2_grpc as pb2_grpc  # noqa: E402


st.set_page_config(page_title="巷道风速校正", page_icon="🌬️", layout="wide")
st.title("单点风速校正与巷道风量估算")
st.caption("第一阶段：圆形完整场；矩形与半圆拱中央竖线直接校正")

with st.sidebar:
    st.header("服务连接")
    server_address = st.text_input(
        "gRPC 地址", value=os.environ.get("AIRFLOW_GRPC_ADDRESS", "127.0.0.1:51051")
    )
    timeout_seconds = st.number_input("超时时间（秒）", 1.0, 30.0, 5.0, 1.0)

shape_name = st.selectbox("断面类型", ["圆形", "矩形", "半圆拱"])

geometry_type: int
dimensions: dict[str, float]
inlet_velocity = 0.0

geometry_column, sensor_column = st.columns(2)

with geometry_column:
    st.subheader("断面与模型")
    if shape_name == "圆形":
        geometry_type = pb2.GEOMETRY_TYPE_CIRCLE
        radius = st.number_input("半径 R（m）", min_value=0.1, value=2.0, step=0.1)
        dimensions = {"radius": radius}
        st.info("采用经典 1/7 次幂律，可计算完整风场积分结果。")
    elif shape_name == "矩形":
        geometry_type = pb2.GEOMETRY_TYPE_RECTANGLE
        size_name = st.selectbox("论文断面尺寸（m）", ["4 × 3", "5 × 3.5", "6 × 4"])
        width, height = {
            "4 × 3": (4.0, 3.0),
            "5 × 3.5": (5.0, 3.5),
            "6 × 4": (6.0, 4.0),
        }[size_name]
        dimensions = {"width": width, "height": height}
        inlet_velocity = st.selectbox("论文入口风速（m/s）", [0.8, 2.0, 4.0, 6.0, 8.0], index=2)
        st.info("采用 Zhang 2022 中央竖线参数，只输出校正结果，不生成二维场。")
    else:
        geometry_type = pb2.GEOMETRY_TYPE_SEMICIRCLE_ARCH
        size_name = st.selectbox("论文断面尺寸（m）", ["4 × 3", "4.5 × 3.3"])
        width, height = {
            "4 × 3": (4.0, 3.0),
            "4.5 × 3.3": (4.5, 3.3),
        }[size_name]
        dimensions = {"width": width, "height": height}
        inlet_velocity = st.selectbox("论文入口风速（m/s）", [0.8, 2.0, 4.0, 6.0, 8.0], index=2)
        st.info("采用 Zhang 2022 中央竖线参数，只输出校正结果，不生成二维场。")

with sensor_column:
    st.subheader("传感器与实测数据")
    measured_velocity = st.number_input(
        "实测单点风速（m/s）", min_value=0.01, value=3.0, step=0.1
    )
    if shape_name == "圆形":
        sensor_x = st.number_input(
            "传感器 x（m，圆心为 0）", min_value=-radius, max_value=radius, value=0.0
        )
        y_limit = max((radius**2 - sensor_x**2) ** 0.5, 0.0)
        sensor_y = st.number_input(
            "传感器 y（m，圆心为 0）",
            min_value=-y_limit,
            max_value=y_limit,
            value=0.0,
        )
        mesh_resolution = st.slider("积分网格分辨率", 50, 600, 300, 50)
    else:
        sensor_x = width / 2.0
        st.number_input("传感器 x（m，固定为中央竖线）", value=sensor_x, disabled=True)
        if shape_name == "矩形":
            max_distance = height / 2.0
        else:
            max_distance = 1.50 if width == 4.0 else 1.65
        distance_from_roof = st.number_input(
            "距顶板距离 d（m）",
            min_value=0.05,
            max_value=float(max_distance),
            value=min(1.0, float(max_distance)),
            step=0.05,
        )
        sensor_y = height - distance_from_roof
        st.caption(f"换算坐标：x={sensor_x:.3f} m，y={sensor_y:.3f} m")
        mesh_resolution = 300

calculate = st.button("开始计算", type="primary", use_container_width=True)

if calculate:
    request = pb2.CorrectionRequest(
        geometry=pb2.GeometryRequest(type=geometry_type, dimensions_m=dimensions),
        sensor=pb2.SensorMeasurement(
            x_m=sensor_x,
            y_m=sensor_y,
            measured_velocity_mps=measured_velocity,
        ),
        inlet_velocity_mps=inlet_velocity,
        model_id="AUTO",
        mesh_resolution=mesh_resolution,
        centerline_tolerance_m=0.02,
    )

    try:
        with grpc.insecure_channel(server_address) as channel:
            stub = pb2_grpc.AirflowCorrectionServiceStub(channel)
            response = stub.CalculateCorrection(request, timeout=timeout_seconds)
    except grpc.RpcError as error:
        st.error(f"无法连接或调用 gRPC 服务：{error.code().name} — {error.details()}")
    else:
        if not response.success:
            st.error(f"计算失败：{response.error_code} — {response.message}")
        else:
            st.success("计算完成")
            result_columns = st.columns(4)
            result_columns[0].metric("断面面积", f"{response.section_area_m2:.4f} m²")
            result_columns[1].metric("校正系数", f"{response.correction_factor:.6f}")
            result_columns[2].metric("平均风速", f"{response.mean_velocity_mps:.4f} m/s")
            result_columns[3].metric("风量", f"{response.air_volume_m3ps:.4f} m³/s")

            st.subheader("模型与质量信息")
            st.write(f"模型：`{response.model.model_id}` — {response.model.name}")
            st.write(f"能力：`{response.model.capability}`")
            st.write(f"可信度：`{response.confidence_level}`")
            if response.parameter_set_id:
                st.write(f"论文参数集：`{response.parameter_set_id}`")
            if response.model.capability == "FULL_FIELD":
                st.write(
                    f"积分收敛：`{response.integration_converged}`，"
                    f"相对差异：`{response.integration_relative_error:.3e}`"
                )
            for warning in response.warnings:
                st.warning(warning)
