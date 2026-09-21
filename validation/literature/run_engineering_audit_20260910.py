"""Re-run frozen field cases; add the explicitly reported Zhou A6 center point.
No model changes, no calibration, no simulated observations. Standard library only.
"""
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from run_validation import cli

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXE = ROOT / 'build-codex/airflow_cli.exe'
FIXTURE = HERE / 'user_articles_results.json'
PREFIX = HERE / 'engineering_audit_20260910'

def main():
    old = json.loads(FIXTURE.read_text(encoding='utf-8'))
    cases = []
    for r in old['records']:
        if r['epsilon'] != .0055:
            continue
        if r['source'] == 'Wei2019' and r['mode'] == 'rectangle-wei-radial':
            group = 'Wei2019_24_points'
        elif r['source'] == 'Wang2015_field':
            group = 'Wang2015_' + ('arch' if r['mode'].startswith('semicircle') else 'rectangle')
        elif r['source'] == 'Zhang2018' and r['case'] == 'no_person':
            group = 'Zhang2018_no_person'
        elif r['source'] == 'Zhou2017' and r.get('roof_gap') == .3048:
            group = 'Zhou2017_21_roof_points'
        else:
            continue
        cases.append(dict(group=group, source=r['source'], case=r['case'], mode=r['mode'],
            geometry=r['geometry'], point=r['point'], input_velocity=r['input_velocity'],
            reference=r['reference'], kind=r['kind'], previous_case=True))
    assert len(cases) == 50
    # Section 3.2 gives centerline correction factor 0.59; Table 1 gives 5 x 7 ft.
    # This is a new tested point at an OLD station, not a new independent mine.
    cases.append(dict(group='Zhou2017_A6_center_new_point', source='Zhou2017', case='A6_center',
        mode='rectangle-wei-radial', geometry=[5*.3048,7*.3048], point=[2.5*.3048,3.5*.3048],
        input_velocity=1., reference=.59, kind='normalized_measured_K', previous_case=False,
        source_location='Section 3.2 and Table 1',
        source_url='https://doi.org/10.1007/s40789-017-0184-z'))
    rows = []
    for c in cases:
        for eps in [.001,.0055,.01]:
            o = cli(EXE,c['mode'],c['geometry'],*c['point'],c['input_velocity'],eps)
            assert o['success'] and o['correction_factor'] > 0
            expected = 1/(1+(math.log1p(-o['radial_eta'])+1.5)/(math.log(o['equivalent_radius_m']/eps)+1.9))
            assert math.isclose(expected,o['correction_factor'],rel_tol=1e-11)
            err = 100*(o['mean_velocity_mps']/c['reference']-1)
            raw = 100*(c['input_velocity']/c['reference']-1)
            rows.append(c | dict(epsilon=eps, output=o, error_pct=err, uncorrected_error_pct=raw,
                improved=abs(err)<abs(raw)))
    summary=[]
    for group in dict.fromkeys(c['group'] for c in cases):
        rr=[r for r in rows if r['group']==group and r['epsilon']==.0055]
        summary.append(dict(group=group,n=len(rr),mape=statistics.mean(abs(r['error_pct']) for r in rr),
            raw_mape=statistics.mean(abs(r['uncorrected_error_pct']) for r in rr),
            max_abs_error=max(abs(r['error_pct']) for r in rr),
            within5=sum(abs(r['error_pct'])<=5 for r in rr),
            within10=sum(abs(r['error_pct'])<=10 for r in rr), improved=sum(r['improved'] for r in rr)))
    out=dict(generated_at=datetime.now(timezone.utc).isoformat(),
        executable=str(EXE),exe_sha256=hashlib.sha256(EXE.read_bytes()).hexdigest(),
        fixture=str(FIXTURE),fixture_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        main_epsilon_m=.0055,records=rows,summary=summary)
    PREFIX.with_suffix('.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# V2 真实工程算例复算与新增中心点检验（2026-09-10）','',
        '本轮测试当前已实现的 V2 径向算法，未实现或测试上一轮讨论的复合速度分布候选模型。',
        '共51组输入位置（50组已有案例复算、1组旧测站新增中心点），3种假设粗糙度，共153次真实C++调用。不是51个独立工程或新增论文。',
        '固定主参数 ε=0.0055 m，另做0.001和0.01 m敏感性；不按参考答案选参数。不混入CFD、均速线位置误差或无独立均速的梯形剖面。','',
        '## 数据与误差口径','',
        '- 原始数据夹具及来源审计：user_articles_report.md、field_round2_report.md；本次重新运行CLI，不把旧输出当新结果。',
        '- Wei2019：同一矩形断面的24个测点，并非24条巷道。',
        '- Wang2015：王坡煤矿副斜井、辅助进风大巷、轨道大巷、集中回风巷，表4；使用表中已舍入的平均值。测点本来接近均速位置，必须比较不校正基线。',
        '- Zhang2018：白坪煤矿无人员工况；人工参考3.45 m/s并非逐工况同步参考，因此只纳入无人员一个工况。',
        '- Zhou2017：SRCM研究矿井21个断面，按文中宽高作矩形近似；扰动风场压力测试。原文参考均速是两种遍历测风结果的平均，两种方法在部分站点存在明显分歧。',
        '- Zhou的输入1 m/s只是归一化，输出数值等于K，不是虚构实测点速；误差按100(K预测/K参考−1)计算。其他案例按100(均速预测/参考均速−1)。',
        '- 新增A6中心点：原文第3.2节直接给K=0.59；表1宽5 ft、高7 ft，按矩形几何中心建模。它是有意选取的极端压力测试，不能作为随机抽样或新增独立矿井。',
        '- 参考K保留两位小数，有舍入不确定性，5%边界附近不宜解释为严格验收结论。','',
        '## 分组结果（主粗糙度）','',
        '|组别|点数|未校正MAPE/%|V2 MAPE/%|最大绝对误差/%|≤5%|≤10%|较未校正改善|',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for s in summary:
        lines.append(f"|{s['group']}|{s['n']}|{s['raw_mape']:.3f}|{s['mape']:.3f}|{s['max_abs_error']:.3f}|{s['within5']}|{s['within10']}|{s['improved']}|")
    lines += ['', '## 全部主参数逐点结果','',
        'Zhou的参考列为K；其余为m/s。JSON保存全部几何、测点、输出和敏感性。','',
        '|来源|点位|宽高/几何 m|坐标 m|点速输入*|参考|K预测|未校正误差/%|V2误差/%|',
        '|---|---|---|---|---:|---:|---:|---:|---:|']
    for r in rows:
        if r['epsilon']!=.0055: continue
        lines.append(f"|{r['source']}|{r['case']}|{r['geometry']}|{r['point']}|{r['input_velocity']:.4f}|{r['reference']:.4f}|{r['output']['correction_factor']:.6f}|{r['uncorrected_error_pct']:+.3f}|{r['error_pct']:+.3f}|")
    lines += ['', '## 新增A6中心点敏感性','', '|ε/m|K预测|参考K|误差/%|','|---:|---:|---:|---:|']
    for r in rows:
        if r['case']=='A6_center':lines.append(f"|{r['epsilon']}|{r['output']['correction_factor']:.6f}|0.59|{r['error_pct']:+.3f}|")
    lines += ['', '## 新资料筛选与缺口','',
        '- Yang等2026，doi:10.1038/s41598-026-53628-8：均速线定位资料；本轮未取得能无歧义配对的完整测点坐标、局部变形几何与独立均速，未把论文报告的5%当成本算法误差。',
        '- 《金属矿三心拱巷道风速传感器最佳安装位置研究》(2025)：检索到书目信息，未取得可复算原文，不纳入。',
        '- Zhang等2022，doi:10.1002/ese3.1277：本轮出版方全文获取失败，不能将摘要误差直接移植到V2。',
        '- 三心拱仍没有本轮新增的充分实测验证；梯形已有Luo2020相对剖面，但缺独立均速，不能计入本表。',
        '- 本次未找到并纳入全新的独立论文数据集，不声称新增多个矿井验证。','',
        '## 来源入口','',
        '- Wei2019：https://doi.org/10.2298/TSCI180707218W',
        '- Zhou2017：https://doi.org/10.1007/s40789-017-0184-z',
        '- Zhang2018：https://mtkxjs.com.cn/cn/article/pdf/preview/1fada46d-1463-46ca-9116-e98221933877.pdf',
        '- Wang2015：项目sources/wang2015.pdf，《基于Fluent巷道断面平均风速点定位监测模拟研究》，表4。','',
        '## 复现','', '```powershell', '.\\.venv\\Scripts\\python.exe validation/literature/run_engineering_audit_20260910.py','```','',
        '结论：按组报告准确性和不校正基线，不能用若干低误差案例证明任意断面任意点可靠。候选新速度模型能否改善尚未测试。']
    PREFIX.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('A6 center:',[(r['epsilon'],r['output']['correction_factor'],r['error_pct']) for r in rows if r['case']=='A6_center'])
    print('PASS: 153 CLI calls; analytic K checks; 51 cases, including one newly evaluated point at an existing station.')

if __name__ == '__main__':
    main()
