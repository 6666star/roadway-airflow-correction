"""Frozen CLI checks of user-supplied literature. No fitted parameters."""
import csv, hashlib, json, statistics, math
from pathlib import Path
from run_validation import cli
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
EXE=ROOT/'build-codex/airflow_cli.exe'
EPS=[.001,.0055,.01]
def metric(rs,key='error_pct'):
    v=[abs(r[key]) for r in rs]
    return dict(n=len(v),mape=statistics.mean(v),max_error=max(v),within5=sum(x<=5 for x in v),within10=sum(x<=10 for x in v))
def main():
    rows=[]
    def add(src,name,mode,g,p,u,ref,eps,kind='point_to_mean',**kw):
        out=cli(EXE,mode,g,*p,u,eps)
        if mode=='rectangle-wei-radial':
            w,h=g
            eta=max(abs(p[0]-w/2)/(w/2),abs(p[1]-h/2)/(h/2))
            radius=w*h/(w+h)
            factor=1/(1+(math.log1p(-eta)+1.5)/(math.log(radius/eps)+1.9))
            assert abs(out['radial_eta']-eta)<1e-10
            assert abs(out['correction_factor']-factor)<1e-10
        r=dict(source=src,case=name,mode=mode,geometry=g,point=p,input_velocity=u,reference=ref,epsilon=eps,kind=kind,cli=out,error_pct=100*(out['mean_velocity_mps']/ref-1),**kw)
        rows.append(r); return r
    with (ROOT/'data/wei2019_rectangle_points.csv').open(encoding='utf-8',newline='') as f:
        for p in csv.DictReader(f):
            for e in EPS:
                for mode in ['rectangle-wei2019','rectangle-wei-radial']:
                    add('Wei2019',p['point_id'],mode,[4.94,3.43],[float(p['x_from_left_m']),3.43-float(p['y_from_top_m'])],float(p['measured_velocity_mps']),1.94,e)
    stations=[('A2',11,6,1.60),('A3',12,6,1.05),('A4',9,6,.97),('A5',9,7,1.29),('A6',5,7,1.06),('A7',4,7,1.41),('A13',14,6,1.01),('A15',12,6,1.13),('A16',13,7,1.20),('A17',16,6,.92),('A18',17,6,.93),('A19',17,6,1.02),('A20',16,6,1.10),('A21',12,7,1.),('A22',12,5,1.),('A23',12,5,1.10),('A24',14,6,.95),('A25',11,5,1.05),('A26',11,6,.98),('A27',11,6,.94),('A28',10,7,1.17)]
    for name,wf,hf,k in stations:
        w,h=wf*.3048,hf*.3048
        for e in EPS:
            for d in [.3048,.3]:
                add('Zhou2017',name,'rectangle-wei-radial',[w,h],[w/2,h-d],1,k,e,'normalized_measured_K',roof_gap=d,raw_error_pct=100*(1/k-1),note='Unit speed normalization, not a measured speed. Rectangular approximation; disturbed-flow stress test; rounded empirical K.')
    for name,w,h,d,u,ref,mode in [('inclined',4.2,3.4,.491,5.2,5.18,'semicircle-wei-radial'),('intake',4,3.5,.546,2.24,2.23,'semicircle-wei-radial'),('rail',4.7,3.1,.353,2.67,2.66,'rectangle-wei-radial'),('return',4.05,3.2,.336,1.83,1.81,'rectangle-wei-radial')]:
        for e in EPS:add('Wang2015_field',name,mode,[w,h],[w/2,h-d],u,ref,e)
    old=json.loads((HERE/'results.json').read_text(encoding='utf-8'))
    for r in old['contour_cases']:
        if r['source'].startswith('Ding') or r['source']=='Wang2015_Table3':
            n=add(r['source'],r['case'],r['mode'],r['geometry_m'],r['reference_point_m'],1,1,r['epsilon_m_assumed'],'conditional_mean_contour',position_error_pct=r['radial_wall_gap_error_pct'])
            assert abs(n['cli']['radial_eta']-r['cli_output']['radial_eta'])<1e-10
    second=json.loads((HERE/'field_round2_results.json').read_text(encoding='utf-8'))
    for r in second['circle_mine']:
        add('Zhang2018',r['case'],'semicircle-wei-radial',[4,4],[2,3.2],r['measured_mps'],3.45,r['epsilon_m'],'shared_manual_reference',note=r['reference_caveat'])
    for r in second['trapezoid_profile']:
        e=r['epsilon_m']; g=[4.78,4.43,3.6]
        c=cli(EXE,'trapezoid-wei-radial',g,2.39,1.8,2.14,e)
        p=cli(EXE,'trapezoid-wei-radial',g,*r['point_m'],1,e)
        pred=c['mean_velocity_mps']/p['correction_factor']
        rows.append(dict(source='Luo2020',case=str(r['horizontal_wall_gap_m']),mode='trapezoid-wei-radial',epsilon=e,kind='center_anchored_profile',observed=r['digitized_mps'],predicted=pred,error_pct=100*(pred/r['digitized_mps']-1),cli=p,note='Symmetric trapezoid assumption; digitized markers; not mean-speed validation'))
    summary={}
    for src,mode in sorted({(r['source'],r['mode']) for r in rows if r['kind']!='conditional_mean_contour'}):
        for e in EPS:
            rs=[r for r in rows if r['source']==src and r['mode']==mode and r['epsilon']==e and r.get('roof_gap',.3048)==.3048]
            summary[f'{src}/{mode}/eps{e}']=metric(rs)
    sources=Path('C:/Users/staro/Desktop/文章')
    out=dict(exe_sha256=hashlib.sha256(EXE.read_bytes()).hexdigest(),source_files=[dict(name=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sources.glob('*.pdf')],records=rows,summary=summary,digitization=second['digitization'],excluded={'半.pdf':'Conveyor obstacles and inconsistent reported u,Q,A; no unambiguous reference.'})
    (HERE/'user_articles_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 用户文章目录验证结果','','主值 ε=0.0055 m；不能混合不同误差指标。','','|来源/模型|n|MAPE/%|最大/%|≤5%|≤10%|','|---|---:|---:|---:|---:|---:|']
    for k,s in summary.items():
        if k.endswith('eps0.0055'):lines.append(f"|{k}|{s['n']}|{s['mape']:.3f}|{s['max_error']:.3f}|{s['within5']}|{s['within10']}|")
    lines+=['','## 逐点结果','','|来源|点|模型|误差/%|','|---|---|---|---:|']
    for r in rows:
        if r['epsilon']==.0055 and r.get('roof_gap',.3048)==.3048:lines.append(f"|{r['source']}|{r['case']}|{r['mode']}|{r['error_pct']:+.3f}|")
    lines+=['','## 全部粗糙度场景','','```json',json.dumps(summary,ensure_ascii=False,indent=2),'```']
    (HERE/'user_articles_results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
