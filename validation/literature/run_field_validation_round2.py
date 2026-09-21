"""Round 2: published mine measurements and physical-gallery data; no fitting.
Run from any directory. Calls the unchanged V2 executable through run_validation.cli.
Luo Figure 2 data are approximate manual digitization, NOT original raw records.
"""
import hashlib
import json
import math
import statistics
from pathlib import Path
from run_validation import cli

HERE = Path(__file__).resolve().parent
EXE = HERE.parents[1] / 'build-codex/airflow_cli.exe'
EPS = [.001, .0055, .01]

def main():
    output = {'executable_sha256': hashlib.sha256(EXE.read_bytes()).hexdigest(),
              'no_parameter_fitting': True, 'circle_mine': [], 'circle_gallery': [],
              'trapezoid_profile': [], 'trapezoid_summary': []}
    # Zhang 2018, section 1.3 and Table 2. One shared manual reference,
    # not five separately synchronized section-mean measurements.
    for label, measured in [('no_person',3.75), ('center_facing',3.98),
                            ('center_sideways',3.85), ('left_facing',3.94),
                            ('left_sideways',3.72)]:
        for eps in EPS:
            r = cli(EXE, 'semicircle-wei-radial', [4,4], 2,3.2,measured,eps)
            output['circle_mine'].append(dict(case=label, epsilon_m=eps,
                measured_mps=measured, reference_mps=3.45,
                reference_caveat='shared paper-reported manual roadway velocity; not per-condition synchronized mean',
                corrected_mps=r['mean_velocity_mps'],
                raw_error_pct=100*(measured/3.45-1),
                corrected_error_pct=100*(r['mean_velocity_mps']/3.45-1), cli=r))
    # Zhang et al 2022 Table 11: mean distances of measured mean-speed line.
    # Not four new mines; not four measured point-speed/mean pairs.
    pred = 2.82/2 * math.exp(-1.5)
    contour_check = cli(EXE,'semicircle-wei-radial',[2.89,2.82],2.89/2,2.82-pred,1,.0055)
    assert abs(contour_check['correction_factor']-1) < 1e-8
    output['circle_gallery_cli_contour_check'] = contour_check
    for nominal, d in zip([1.3,2,2.6,3.5],[.3298,.3274,.3256,.3244]):
        output['circle_gallery'].append(dict(nominal_condition_mps=nominal,
            measured_mean_line_roof_gap_m=d, predicted_gap_m=pred,
            gap_error_pct=100*(pred/d-1),
            caveat='published mean contour-to-roof distance treated as central-axis proxy; contour not fully digitized'))
    # Luo & Zhao 2020 Fig 1: Wb=4.780, Wt=4.430, H=3.600.
    # Fig 2 rendered using pdftoppm -scale-to 1600 -jpeg (1134 x 1600).
    # Axis calibration: d=0 at px298; d=200cm at px893;
    # u=0 at py1052; u=2.5m/s at py591. Black markers only.
    pixels = [(333,879),(417,735),(446,686),(487,666),(535,673),
              (606,677),(654,679),(725,666),(773,661),(892,658)]
    output['digitization'] = dict(source='Luo2020 Figure2 printed p258',
        render='sources/luo2020_verify-04.jpg', pixels=pixels,
        axes_pixels={'x0':298,'x200cm':893,'y0':1052,'y2_5':591},
        estimated_reading_uncertainty_mps=.03, estimated_distance_uncertainty_m=.01,
        caveat='selected visible markers spanning profile, not exhaustive data or statistical sample')
    for eps in EPS:
        center = cli(EXE,'trapezoid-wei-radial',[4.78,4.43,3.6],2.39,1.8,2.14,eps)
        for px, py in pixels:
            d = (px-298)/595*2
            observed = (1052-py)/461*2.5
            x = (4.78-4.43)/4+d
            r = cli(EXE,'trapezoid-wei-radial',[4.78,4.43,3.6],x,1.8,1,eps)
            predicted = center['mean_velocity_mps']/r['correction_factor']
            output['trapezoid_profile'].append(dict(epsilon_m=eps,
                horizontal_wall_gap_m=d, point_m=[x,1.8], digitized_mps=observed,
                predicted_mps=predicted, profile_error_pct=100*(predicted/observed-1),
                absolute_speed_error_mps=abs(predicted-observed),
                center_anchor_mps=2.14, center_inferred_mean_mps=center['mean_velocity_mps'],
                caveat='center-anchored normalized profile test; NOT measured mean-speed validation',cli=r))
        rows = [r for r in output['trapezoid_profile'] if r['epsilon_m']==eps]
        for name, subset in [('all_selected',rows),
            ('wall_gap_ge_1m',[r for r in rows if r['horizontal_wall_gap_m']>=1])]:
            output['trapezoid_summary'].append(dict(epsilon_m=eps,group=name,n=len(subset),
                mape_pct=statistics.mean(abs(r['profile_error_pct']) for r in subset),
                max_abs_error_pct=max(abs(r['profile_error_pct']) for r in subset)))
    (HERE/'field_round2_results.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 第二轮实测验证数值结果','', '由 run_field_validation_round2.py 生成；解释与限制见 field_round2_report.md。','',
           '## 圆拱矿井：共享 3.45 m/s 参考风速','',
           '|工况|ε/m|测点风速|校正均速|未校正误差/%|校正误差/%|',
           '|---|---:|---:|---:|---:|---:|']
    for r in output['circle_mine']:
        lines.append(f"|{r['case']}|{r['epsilon_m']}|{r['measured_mps']:.3f}|{r['corrected_mps']:.4f}|{r['raw_error_pct']:.3f}|{r['corrected_error_pct']:.3f}|")
    lines += ['', '## 圆拱物理试验巷道：均速线距离','', '|工况/m/s|实测距离/m|预测/m|位置误差/%|','|---:|---:|---:|---:|']
    for r in output['circle_gallery']:
        lines.append(f"|{r['nominal_condition_mps']}|{r['measured_mean_line_roof_gap_m']:.4f}|{r['predicted_gap_m']:.6f}|{r['gap_error_pct']:.3f}|")
    lines += ['', '## 梯形矿井：中心风速锚定的剖面检验，ε=0.0055 m','',
        '|距侧壁/m|读图实测/m/s|预测/m/s|剖面误差/%|','|---:|---:|---:|---:|']
    for r in output['trapezoid_profile']:
        if r['epsilon_m']==.0055:
            lines.append(f"|{r['horizontal_wall_gap_m']:.3f}|{r['digitized_mps']:.3f}|{r['predicted_mps']:.3f}|{r['profile_error_pct']:.2f}|")
    lines += ['', '## 梯形粗糙度敏感性','', '|ε/m|测点组|n|MAPE/%|最大绝对误差/%|','|---:|---|---:|---:|---:|']
    for r in output['trapezoid_summary']:
        lines.append(f"|{r['epsilon_m']}|{r['group']}|{r['n']}|{r['mape_pct']:.2f}|{r['max_abs_error_pct']:.2f}|")
    (HERE/'field_round2_results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__ == '__main__':
    main()
