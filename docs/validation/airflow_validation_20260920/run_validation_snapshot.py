"""Published-case checks of the existing V2 CLI; no fitting and no backend edits.
Run with the project's Python. Only Python standard library is required.
Contour samples are evaluations of published correlations, NOT independent experiments.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ETA_STAR = 1 - math.exp(-1.5)

def cli(exe, mode, geometry, x, y, measured, epsilon):
    args = [str(exe), mode, *map(str, geometry), str(x), str(y), str(measured), str(epsilon)]
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", check=True)
    result = json.loads(p.stdout)
    if not result.get("success"):
        raise RuntimeError(result)
    return result

def stat(rows, key):
    vals = [abs(r[key]) for r in rows]
    return {"n_evaluations": len(vals), "mean_absolute": statistics.mean(vals),
            "min_absolute": min(vals), "max_absolute": max(vals)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=ROOT / "build-codex/airflow_cli.exe")
    args = parser.parse_args()
    records, fields = [], []

    def contour(source, case, mode, geom, point, center, epsilon, metadata):
        x, y = point
        # The reference point is on the paper's u/Umean=1 contour.
        # Unit speed is a normalization, not a fabricated measurement.
        r = cli(args.exe, mode, geom, x, y, 1.0, epsilon)
        eta = r["radial_eta"]
        rho = math.dist(point, center)
        rho_b = rho / eta
        pred = [center[j] + ETA_STAR / eta * (point[j] - center[j]) for j in (0, 1)]
        delta_percent = ((1 - ETA_STAR) / (1 - eta) - 1) * 100
        rec = {"source": source, "case": case, "mode": mode, "geometry_m": geom,
               "reference_point_m": point, "default_center_m": center,
               "reference_type": "published_mean_velocity_contour",
               "epsilon_m_assumed": epsilon, "predicted_same_ray_contour_point_m": pred,
               "radial_position_error_m": abs(eta - ETA_STAR) * rho_b,
               "radial_wall_gap_error_pct": delta_percent,
               "conditional_speed_bias_pct": (r["mean_velocity_mps"] - 1) * 100,
               "cli_output": r, **metadata}
        records.append(rec)
        # Independently check CLI's mapping and contour property.
        q = cli(args.exe, mode, geom, *pred, 1.0, epsilon)
        assert abs(q["correction_factor"] - 1) < 1e-8
        assert abs(q["radial_eta"] - ETA_STAR) < 1e-8

    # Wang 2015, Table 3, printed p95. Rows H=3.5,3.0,2.5;
    # columns W=3.5,4.0,4.5,5.0. Distances are from ROOF.
    tables = {
        "masonry": [[.557,.546,.535,.528],[.484,.471,.458,.455],[.408,.394,.375,.372]],
        "shotcrete": [[.571,.560,.550,.543],[.488,.481,.474,.471],[.412,.401,.392,.386]]
    }
    for support, matrix in tables.items():
        for h, values in zip([3.5,3.0,2.5], matrix):
            for w, d in zip([3.5,4.0,4.5,5.0], values):
                contour("Wang2015_Table3", f"{support}_W{w}_H{h}",
                        "semicircle-wei-radial", [w,h], [w/2,h-d], [w/2,h/2], .0055,
                        {"paper_wall_distance_m": d, "wall": "roof", "support": support,
                         "predicted_wall_distance_m": h/2*math.exp(-1.5)})

    # Table 4 uses the printed averages, not a recalculated average of rounded repeats.
    for name, w, h, d, measured, ref in [
        ("auxiliary_inclined_shaft",4.2,3.4,.491,5.20,5.18),
        ("auxiliary_intake_main",4.0,3.5,.546,2.24,2.23)
    ]:
        for eps in [.001,.0055,.01]:
            r = cli(args.exe, "semicircle-wei-radial", [w,h], w/2, h-d, measured, eps)
            fields.append({"source":"Wang2015_Table4","case":name,
                "geometry_m":[w,h],"point_m":[w/2,h-d],"epsilon_m_assumed":eps,
                "reference_mean_mps":ref,"measured_mps":measured,
                "raw_error_pct":(measured/ref-1)*100,
                "corrected_error_pct":(r["mean_velocity_mps"]/ref-1)*100,"cli_output":r})

    # Yang et al. 2026, Table 5, accepted manuscript PDF p19.
    # Floor column only: no guessed side sampling elevation.
    # Table 4 fit roots disagree with Table 5; keep this a flagged secondary check.
    ys = [.523,.509,.513,.518,.525]
    fits = [(.09224,.53031),(.19342,1.07224),(.55556,3.19546),
            (.90016,5.30006),(1.40293,8.44058)]
    audits = []
    for speed, d, (slope, intercept) in zip([.5,1,3,5,8], ys, fits):
        contour("Yang2026_Table5_FLAGGED", f"inlet_{speed}", "semicircle-wei-radial",
                [5,4.5], [2.5,d], [2.5,2.25], .0055,
                {"paper_wall_distance_m":d,"wall":"floor","inlet_mps":speed,
                 "predicted_wall_distance_m":2.25*math.exp(-1.5)})
        audits.append({"inlet_mps":speed,"table5_floor_distance_m":d,
                       "table4_velocity_at_table5_point_mps":slope*math.log(d)+intercept,
                       "table4_root_for_inlet_mean_m":math.exp((speed-intercept)/slope)})

    # Ding 2016 conference Tables 1,2; same geometry/equations in Ding 2017.
    # These two publications are ONE data family.
    # 5 floor samples + 3 on each vertical side, per scale. No curve corners/roof
    # included: this is a partial 2D contour test, not full-field validation.
    for k in range(1,6):
        w, wall, big, small = .260*k, .113*k, .183*k, .066*k
        rise = big - math.sqrt((big-small)**2-(w/2-small)**2)
        h = wall+rise
        geom = [w,wall,rise,big,small]
        # Relative roughness is a declared sensitivity assumption, not paper input.
        seed = cli(args.exe,"three-center-wei-radial",geom,w/2,h/2,1,.00001)
        eps = .001*seed["equivalent_radius_m"]
        left, right = .2338*w+.0364, .7662*w-.0364
        for j in range(5):
            contour("Ding2016_2017_floor",f"scale{k}_floor{j}",
                    "three-center-wei-radial",geom,
                    [left+(right-left)*j/4,.085*w-.0034],[w/2,h/2],eps,
                    {"scale":k,"wall":"floor","sample_index":j,
                     "paper_wall_distance_m":.085*w-.0034,
                     "predicted_wall_distance_m":h/2*math.exp(-1.5)})
        ymin, ymax = .5053*wall+.0096, .9932*wall-.0087
        for side in ["left","right"]:
            dx = .2219*wall-.0014
            for j in range(3):
                contour("Ding2016_2017_side",f"scale{k}_{side}{j}",
                        "three-center-wei-radial",geom,
                        [dx if side=="left" else w-dx,ymin+(ymax-ymin)*j/2],
                        [w/2,h/2],eps,{"scale":k,"wall":side,"sample_index":j})

    summary = {}
    for source in sorted({r["source"] for r in records}):
        subset = [r for r in records if r["source"]==source]
        summary[source] = {
            "radial_wall_gap_error_pct":stat(subset,"radial_wall_gap_error_pct"),
            "radial_position_error_m":stat(subset,"radial_position_error_m"),
            "conditional_speed_bias_pct":stat(subset,"conditional_speed_bias_pct")}
    result = {"schema_version":1,"exe":str(args.exe),
              "exe_sha256":hashlib.sha256(args.exe.read_bytes()).hexdigest(),
              "eta_mean_contour":ETA_STAR,"no_parameter_fitting":True,
              "warning":"Contour errors are not velocity errors. Roughness values are assumptions.",
              "counts":{"contour_evaluations":len(records),"field_cases":2,
                        "field_sensitivity_evaluations":len(fields),"trapezoid_verified_cases":0},
              "summary":summary,"field_cases":fields,"source_consistency_audit":audits,
              "contour_cases":records}
    (HERE/"results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    lines = ["# V2 文献算例数值结果", "",
             "自动生成；解释、来源和局限见 validation_report.md。位置误差不是风速误差。",
             "未拟合参数。粗糙度均为声明的假设。三心拱采样点不是独立实验次数。","",
             "| 数据组 | 点数 | 径向距壁位置平均绝对相对误差 | 位置最大绝对偏差/m |",
             "|---|---:|---:|---:|"]
    for source,s in summary.items():
        lines.append(f"| {source} | {s['radial_wall_gap_error_pct']['n_evaluations']} | "
                     f"{s['radial_wall_gap_error_pct']['mean_absolute']:.3f}% | "
                     f"{s['radial_position_error_m']['max_absolute']:.6f} |")
    lines += ["","## 圆拱现场点风速校正：粗糙度敏感性","","| 工况 | 假设 ε/mm | 实测点风速 | 参考平均风速 | V2平均风速 | 未校正误差 | 校正误差 |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for r in fields:
        lines.append(f"| {r['case']} | {r['epsilon_m_assumed']*1000:g} | {r['measured_mps']:.2f} | "
                     f"{r['reference_mean_mps']:.2f} | {r['cli_output']['mean_velocity_mps']:.5f} | "
                     f"{r['raw_error_pct']:+.3f}% | {r['corrected_error_pct']:+.3f}% |")
    (HERE/"results.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"summary":summary,"fields":fields,"counts":result["counts"]},
                     ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()

