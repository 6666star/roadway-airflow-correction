import json, math, statistics, subprocess, hashlib
from pathlib import Path
from datetime import datetime,timezone
O=Path(__file__).resolve().parent
P=Path('C:/Users/staro/Desktop/Cluade/Project_1_v2')
EXE=P/'build-codex/airflow_cli.exe'
def read(n):return json.loads((O/n).read_text(encoding='utf-8'))
field=read('field_retest_20260920.json')
contour=read('results.json')
round2=read('field_round2_results.json')
expanded=read('expanded_validation_20260910.json')
manifest=read('source_manifest.json')
audit=read('execution_audit.json')
new=[]
# Wang 2015 printed p95 Table 3, rectangle rows, visually checked 2026-09-20.
# Heights 3.5,3,2.5; widths 3.5,4,4.5,5. These are position references, not velocities.
tables={'anchor_mesh':[[.382,.388,.389,.393],[.340,.345,.346,.352],[.297,.299,.305,.312]],'shotcrete':[[.371,.377,.380,.388],[.325,.330,.333,.340],[.287,.288,.295,.301]]}
for support,table in tables.items():
 for h,values in zip([3.5,3,2.5],table):
  for w,d in zip([3.5,4,4.5,5],values):
   cmd=[str(EXE),'rectangle-wei-radial',str(w),str(h),str(w/2),str(h-d),'1','.0055']
   result=json.loads(subprocess.check_output(cmd,text=True,encoding='utf-8'))
   assert result['success']
   eta=result['radial_eta']; eta_star=1-math.exp(-1.5)
   pred=(1-eta_star)/(1-eta)*d
   target=cmd.copy();target[5]=str(h-pred)
   check=json.loads(subprocess.check_output(target,text=True,encoding='utf-8'))
   assert abs(check['correction_factor']-1)<1e-10
   new.append(dict(source='Wang2015_Table3_rectangle',source_pdf_page=4,printed_page=95,support=support,width=w,height=h,reference_gap_m=d,predicted_gap_m=pred,position_error_pct=100*(pred/d-1),position_error_m=pred-d,command=cmd,output=result,self_check=check))
new_summary=dict(n=len(new),mape=statistics.mean(abs(r['position_error_pct']) for r in new),max_abs_pct=max(abs(r['position_error_pct']) for r in new))
wei=[r for r in field['records'] if r['source']=='Wei2019' and r['epsilon']==.0055]
groups={}
for r in wei:groups.setdefault(round(r['output']['radial_eta'],12),[]).append(r)
diagnostics=[]
for eta,rs in groups.items():
 if len(rs)<2:continue
 lo=min(r['input_velocity'] for r in rs);hi=max(r['input_velocity'] for r in rs)
 diagnostics.append(dict(eta=eta,cases=[r['case'] for r in rs],observed_speeds=[r['input_velocity'] for r in rs],shared_K=rs[0]['output']['correction_factor'],minimum_possible_max_relative_error_pct=100*(hi-lo)/(hi+lo)))
worst=max(diagnostics,key=lambda r:r['minimum_possible_max_relative_error_pct'])
# Table 1 values manually verified against PDF p3; ensure fixture did not drift.
velocities={'111':1.80,'121':2.08,'131':2.03,'141':2.07,'151':2.17,'161':2.19,'112':2.19,'122':2.12,'132':2.15,'142':2.32,'152':2.26,'162':2.34,'113':2.26,'123':2.31,'133':2.19,'143':2.23,'153':2.21,'163':2.20,'114':2.21,'124':2.27,'134':2.35,'144':2.11,'154':2.23,'164':2.27}
assert {str(r['case']):r['input_velocity'] for r in wei}==velocities
source_map={}
for m in manifest:
 name=Path(m['path']).name
 key=next((k for k in ['Wei','Zhou','Song','Luo','Ding'] if name.startswith(k)),name.split('_')[0])
 if key!='Ding' or '2017' in name:source_map[key]=m['path']
out=dict(generated_at=datetime.now(timezone.utc).isoformat(),executable=str(EXE),exe_sha256=audit['exe_sha256'],main_epsilon_m=.0055,no_fitting=True,source_manifest=manifest,field_summary=field['summary'],field_records=field['records'],new_rectangle_contour=new,new_rectangle_summary=new_summary,same_eta_diagnostics=diagnostics,main_scope='Only papers physically present in the user folder. Zhang2022 outputs from legacy rerun are excluded.',calls_total=audit['calls']+2*len(new),call_count_note='Includes sensitivities, repeated legacy regressions, old Wei baseline and Zhang2022 supplementary regression; not independent observations.')
(O/'verified_results_20260920.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
labels={'Wei2019_24_points':'Wei 2019：矩形24点','Zhou2017_21_roof_points':'Zhou 2017：21个近顶测站','Wang2015_arch':'王翰锋2015：半圆拱现场','Wang2015_rectangle':'王翰锋2015：矩形现场','Zhang2018_no_person':'张浪2018：圆拱无人员','Zhou2017_A6_center_new_point':'Zhou A6中心：单列压力测试'}
L=['# 当前径向映射模型：用户论文目录准确性复测','', '日期：2026-09-20。没有修改算法、没有标定粗糙度、没有覆盖项目旧报告。', '',
'## 结论','',
'当前模型在部分规则断面数据中改善了单点读数，但收益依赖测点和流场。不能据此宣布任意点满足5%或10%误差。矩形映射相同eta点的实测速率存在明显差别，显示仅修改统一径向速度函数不能解决全部残差。','',
'## 范围与复现','',
f'- 本轮真实调用现有C++可执行文件 {out["calls_total"]} 次，含敏感性、恒等式自检和重复回归；绝不等同于独立测点数量。',
'- 11份分类PDF，含Ding同源版本、补充及存疑文献；根目录7份为重复文件。主结论只纳入本次指定目录实际存在的论文。',
'- 复用现有论文录入脚本，重新计算所有输出；目视核验Wei表1/2、Zhou表1及参考定义、王翰锋表3/4、张浪几何和表2、Song表1/2、Ding尺寸及关联式、Luo几何与实测散点图。Luo沿用旧读图坐标，未声称重新提取原始数据。',
'- 本轮额外录入王翰锋表3的24个矩形均速位置，属于已有论文的新评价条目，不是新实验。',
'- 实际点到均速主表51条：Wei24点、Zhou21个顶部测站、王翰锋4个现场工况、张浪1个无人员工况、Zhou A6中心1点（后者单列，非新增独立测站）。',
'- 主粗糙度固定0.0055m；现场敏感性为0.001、0.0055、0.01m。除Wei推荐值外，不冒充现场实测粗糙度。默认中心保持不变。',
'- 使用现有build-codex二进制，未重新编译；已保存二进制、核心源码、原文PDF的SHA256。','',
'复现：先执行 `rerun.py`，再执行 `compile_report.py`。需当前项目路径及其已有可执行文件。两者只在本报告目录写结果。','',
'## 1. 单点校正：必须与不校正比较','',
'误差 E=100×(预测均速/参考均速−1)，MAPE=平均|E|。Zhou按100×(预测K/参考K−1)计算，输入1只是归一化。≤5%/≤10%是描述性阈值，未纳入测量不确定度。','',
'|数据|n|不校正MAPE %|径向MAPE %|最大绝对误差 %|≤5%|≤10%|改善点数|','|---|---:|---:|---:|---:|---:|---:|---:|']
for s in field['summary']:L.append(f"|{labels[s['group']]}|{s['n']}|{s['raw_mape']:.3f}|{s['mape']:.3f}|{s['max_abs_error']:.3f}|{s['within5']}/{s['n']}|{s['within10']}/{s['n']}|{s['improved']}/{s['n']}|")
L+=['','Wei是一个断面24点，不能当作24条巷道。Zhou按矩形近似，真实风场有扰动；参考系数经过舍入，参考均速来自两种遍历结果的平均。张浪使用共享人工参考3.45m/s，缺逐工况同步独立均速，主表只保留无人员工况。王翰锋的传感器本来接近均速位置，不校正基线很强。不同来源不合并为总体成功率。','',
'## 2. 几何映射诊断：相同eta的实测速率并不相同','',
f"Wei测点 {', '.join(worst['cases'])} 在当前默认中心下 eta={worst['eta']:.9f}，共享K={worst['shared_K']:.6f}，实测速率为 {worst['observed_speeds']} m/s，参考均速均为1.94m/s。",
'', '只要保留同一映射中心、统一粗糙度及只依赖eta的速度函数，这些点就共享同一个K。对速度最小值a、最大值b，共同K可达到的最小最大相对均速误差为 (b−a)/(b+a)：', '',
f"**本组下界为 {worst['minimum_possible_max_relative_error_pct']:.3f}%。因此，单靠更换统一的圆管径向速度公式，无法让这组报告值全部落入10%以内。**",'',
'该结论针对论文报告值和固定模型结构；测量误差、时间波动也可能贡献点间差异，不能仅凭此证明真实等速度线形状。它足以提示应检查方向性、映射中心及等eta假设。','',
'## 3. 均速线位置检验：不是均速误差','',
'|来源|评价数|指标|平均绝对相对误差 %|最大绝对相对误差 %|','|---|---:|---|---:|---:|',
f"|王翰锋2015 矩形（本轮新录入）|24|中心轴距顶位置|{new_summary['mape']:.3f}|{new_summary['max_abs_pct']:.3f}|"]
for key,label in [('Wang2015_Table3','王翰锋2015 半圆拱'),('Ding2016_2017_floor','Ding三心拱 底部'),('Ding2016_2017_side','Ding三心拱 侧壁')]:
 s=contour['summary'][key]['radial_wall_gap_error_pct'];L.append(f"|{label}|{s['n_evaluations']}|同射线距壁位置|{s['mean_absolute']:.3f}|{s['max_absolute']:.3f}|")
s=expanded['groups']['Song2022_LDA_contour']['position'];L.append(f"|Song矩形LDA|10|中心轴距顶/底位置|{s['mape_pct']:.3f}|{s['max_abs_pct']:.3f}|")
L+=['','Ding为5种缩尺几何的55个关联式评价点，不是55次独立实验；仅覆盖底部和侧壁，未证明拱肩/顶部准确。','',
'模型均速位置eta*=1−exp(−1.5)，默认中心轴距顶/底为0.111565H，与粗糙度无关。圆拱位置偏差、三心拱方向差异、Song随工况变化的均速位置说明固定归一化分布存在约束；这些结果不能单独区分映射和速度公式各自的贡献。','',
'## 4. 梯形相对剖面与LDA拟合剖面','',
'- Luo梯形：中心速度2.14m/s锚定、10个可辨认实测散点，剖面MAPE 9.871%，最大55.202%；距壁≥1m的5点MAPE 2.567%。完整10点均保留，远壁子集仅用于诊断。没有独立截面均速，不能称为梯形单点反演准确率。读图估计不确定度约±0.03m/s、位置约±0.01m，未将其转换成统计置信区间。',
'- Song矩形：5个工况的拟合函数按预设位置生成40个评价点，默认粗糙度条件下均速MAPE由14.222%降至5.261%，最大13.387%，36/40≤10%。这些是关联的拟合评价点，不是40个原始独立测点。',
'- Song模型宽高仅0.2m、光滑有机玻璃，默认5.5mm粗糙度只是迁移压力测试，不具备已证实的物理匹配。粗糙度0.1/0.01/0.001mm下同40点MAPE为7.227%/8.398%/9.245%；不能选择误差最低值就称完成标定。','',
'## 5. 粗糙度敏感性（现场）','', '|数据|ε=1mm MAPE %|ε=5.5mm MAPE %|ε=10mm MAPE %|','|---|---:|---:|---:|']
for g,label in labels.items():
 vals=[statistics.mean(abs(r['error_pct']) for r in field['records'] if r['group']==g and r['epsilon']==e) for e in [.001,.0055,.01]]
 L.append('|'+label+'|'+'|'.join(f'{v:.3f}' for v in vals)+'|')
L+=['','## 6. 不纳入主结论的资料','',
'- Yang2026：原表均速位置与对数拟合式在以入口速度作均速基准时存在不一致；5个位置算例保留在原始复测JSON中但不作主准确性证据。',
'- 时创新2026：相关系数/均速位置与Yang资料重合，不重复计数。',
'- 王佳伟2026：存在胶带输送机障碍，当前模型未表达障碍；首组正文速度1.67m/s、风量1603m³/min与表中面积18.12m²不直接一致（Q/(60A)约1.474m/s），不能自行挑选基准拼成准确性验证。',
'- Zhang2022完整原文不在该目录，旧脚本顺带复算的CFD与位置代理结果不纳入本报告主表；旧Wei原模型回归也不属于当前径向模型的准确性结果。','',
'## 7. 主参数逐点结果','', '|来源|点|坐标m|点速或归一化输入|参考均速或K|K预测|不校正误差 %|校正误差 %|','|---|---|---|---:|---:|---:|---:|---:|']
for r in field['records']:
 if r['epsilon']==.0055:L.append(f"|{r['source']}|{r['case']}|{r['point']}|{r['input_velocity']:.4f}|{r['reference']:.4f}|{r['output']['correction_factor']:.6f}|{r['uncorrected_error_pct']:+.3f}|{r['error_pct']:+.3f}|")
L+=['','## 8. 来源与审计文件','',f"C++ SHA256：`{audit['exe_sha256']}`",'',
'- `verified_results_20260920.json`：本轮主表、逐点结果、新增24个位置和等eta诊断。',
'- `execution_audit.json`：前1147次真实CLI调用及输出；额外48次见verified_results中的新位置与自检输出。',
'- `source_manifest.json`：11份分类PDF完整路径、页数和SHA256。',
'- `*_snapshot.py`：本轮使用的原验证脚本快照。旧脚本输出文件名或文本中的旧日期仅是继承命名，本次运行时间以审计JSON及本报告为准。','']
for key in ['Wei','Zhou','王翰锋','张浪','Song','Ding','Luo']:
 path=source_map[key].replace('\\','/');L.append(f'- [{key} 原文](<{path}>)')
(O/'模型准确性复测报告_20260920.md').write_text('\n'.join(L)+'\n',encoding='utf-8')
print(json.dumps(dict(new_rectangle_summary=new_summary,same_eta_worst=worst,calls_total=out['calls_total']),ensure_ascii=False,indent=2))
print('Report created; all fresh CLI self-checks passed.')
