# Wei 多断面径向映射后端 V2

## 已实现内容

沿用 Wei 2019 式(5)的粗糙圆管速度公式，将几何等效距离替换为径向归一化映射。已支持矩形、直墙半圆拱、标准对称三心拱和等腰梯形的内部任意测点校正。

原有 Wei 矩形和 Zhang 中心线模型及其入口保留。新增模型没有套用原矩形模型的实测精度等级，独立论文算例验证属于下一阶段。

## 算法

给定面积 A、湿周 Pw、映射中心 C、测点 P：

- r0 = 2A/Pw：等效圆半径；水力半径本身为 A/Pw。
- rho = |P-C|。
- rho_b：射线 C+t(P-C)/rho 与实际边界的首个有效正交点距离。
- eta = rho/rho_b；测点与中心重合时 eta=0。
- delta = r0(1-eta)。
- phi = [ln(delta/epsilon)+3.4]/[ln(r0/epsilon)+1.9]。
- mean_velocity = measured_velocity/phi。
- airflow = A * mean_velocity。

仅改变几何映射，尚未引入新摩擦定律或拟合参数。粗糙度单位为米。映射中心默认使用 (W/2,H/2)，所有形状一致；支持显式指定内部中心。

未截断对数速度函数时，星形域内 mean(ln(1-eta))=-3/2，因此数学上的截面平均 phi=1。该性质不是实验精度证明。壁面及非正速度比测点拒绝计算，不对它们强行截断后返回风速。

## 坐标与几何输入

对外坐标沿用左下角原点，x 向右，y 向上。

| CLI 形状 | 几何参数顺序 | 说明 |
|---|---|---|
| rectangle-wei-radial | W H | 宽、高 |
| semicircle-wei-radial | W H | 总高 H>=W/2，墙高 H-W/2 |
| trapezoid-wei-radial | bottom top H | 等腰梯形，底边从 x=0 到 bottom；上底居中 |
| three-center-wei-radial | W wall rise R r | 宽、墙高、拱高、大圆半径、小圆半径 |

允许上底大于下底的等腰梯形，此时断面可能延伸到负 x，包围盒已处理。

三心拱要求 wall>=0、R>r>0、r<W/2、R>rise，且满足：

    hypot(W/2-r, R-rise) = R-r

相切误差容限为 1e-8*max(W,R,r)。若设计表中的半径仅保留少数小数，应先由一致的构造参数恢复精确几何，不能把明显不相切的圆弧拼起来。

例如 W=4、rise=1、r=0.5 时，R=3 精确满足相切关系。给定 W、rise、r 时，可按以下关系计算 R，再检查全部几何约束：

    R = [(W/2)^2 - W*r + rise^2] / [2*(rise-r)]

rise=r 不适用此式。单圆退化情形使用半圆拱入口。

## CLI 调用

在项目根目录执行，最后两个中心坐标可选：

~~~powershell
.\build-codex\airflow_cli.exe semicircle-wei-radial 4 3 1 2 2 0.0055
.\build-codex\airflow_cli.exe trapezoid-wei-radial 5 3 3 1 2 2 0.0055
.\build-codex\airflow_cli.exe three-center-wei-radial 4 1.5 1 3 0.5 1 2 2 0.0055
.\build-codex\airflow_cli.exe rectangle-wei-radial 4 3 1 2 2 0.0055
# 自定义中心 (2,1.4)
.\build-codex\airflow_cli.exe semicircle-wei-radial 4 3 1 2 2 0.0055 2 1.4
~~~

几何参数之后依次是：sensor_x、sensor_y、measured_velocity、roughness。

半圆拱示例实际输出：面积约 10.283185 m²，eta 约 0.647853，平均速度约 1.886982 m/s，风量约 19.404190 m³/s。这是软件计算示例，不是论文实测验证算例。

## gRPC

复用 CalculateCorrection，新增可选字段：

- absolute_roughness_m：不提供时 0.0055，显式提供 0 会拒绝。
- mapping_center_x_m / mapping_center_y_m：必须同时提供，或同时省略。

模型 ID：

- RECTANGLE_WEI_RADIAL
- SEMICIRCLE_ARCH_WEI_RADIAL
- TRAPEZOID_WEI_RADIAL
- THREE_CENTER_ARCH_WEI_RADIAL

dimensions_m 键：

- 矩形/半圆拱：width、height。
- 梯形：bottom_width、top_width、height。
- 三心拱：width、wall_height、arch_rise、crown_radius、side_radius。

梯形和三心拱 AUTO 自动选择径向模型。矩形和半圆拱保留旧 AUTO 行为；使用新算法时明确提供以上 model_id。旧前端暂不改动。

CorrectionResponse 新增：

- radial_eta
- equivalent_radius_m
- equivalent_wall_distance_m
- true_wall_distance_m

这些值用于核对映射；旧模型输出为默认零值，应结合 model_id 解读。

CalculateField 的网格传输仍为旧版未实现状态。本次完成任意内部测点校正，模型能力标记为 DIRECT_CORRECTION；该标记不代表必须位于中心线。批量测点可由调用端逐点调用，不会伪造完整无滑移壁面速度场。

## C++ 使用与文件

- include/airflow/radial.hpp：RadialGeometry、mapRadial、RadialWeiModel。
- src/radial.cpp：圆弧/线段、Green 面积积分、真实壁距、射线映射与校正。
- src/service.cpp：模型注册。
- src/main.cpp：新增 CLI 入口。
- proto/airflow_correction.proto：粗糙度、中心坐标和映射结果字段。
- grpc_adapter/server.py：新几何校验和模型路由。
- generated/：重新生成的 Python protobuf 文件。

调用 RadialWeiModel 时使用 RadialGeometry 工厂构造对应断面。现有 RectangleGeometry 等保留给旧算法使用。不要将旧几何对象直接传给新的径向模型。

## 已完成测试

2026-09-08 使用项目 .venv 与 build-codex 执行 CTest，4/4 通过：

1. radial_geometry_validation：6 种几何配置，8640 条射线的出口、边界距离、归一化位置、左右对称性；解析面积/湿周；极坐标面积与独立 Cartesian 网格面积/速度平均校验；错误三心拱和边界中心拒绝。
2. radial_rpc_validation：四类模型通过真实本地 gRPC 调用，检查几何面积、Wei 公式、对称性、参数错误。
3. python_model_validation：旧圆管、Zhang 和 Wei 论文数据回归。
4. grpc_end_to_end_validation：旧接口端到端回归。

~~~powershell
cmake -S . -B build-codex -DPython3_EXECUTABLE="$PWD/.venv/Scripts/python.exe"
cmake --build build-codex
ctest --test-dir build-codex --output-on-failure
~~~

以上测试确认软件几何与算法实现、原有功能兼容性。新断面的物理精度尚未借助独立论文大量算例测试，不将此任务混同于已完成的实现测试。
