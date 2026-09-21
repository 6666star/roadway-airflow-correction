"""Additional published cases. Frozen V2 CLI; no fitting or backend changes."""
import hashlib
import json
import math
from pathlib import Path
import statistics
from run_validation import cli

HERE = Path(__file__).resolve().parent
EXE = HERE.parents[1] / "build-codex/airflow_cli.exe"
EPS = [.0055, .0001, .00001, .000001]
SONG_URL = "https://francis-press.com/uploads/papers/WNqdFilm9irV8Ikpca17YuKs4RAZSZs7iPWhPZVT.pdf"
ZHANG_URL = "https://scijournals.onlinelibrary.wiley.com/doi/abs/10.1002/ese3.1277"

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def stats(values):
    a = [abs(v) for v in values]
    return dict(n=len(a), mape_pct=statistics.mean(a), max_abs_pct=max(a),
                within_5=sum(v<=5 for v in a), within_10=sum(v<=10 for v in a))

def main():
    positions, profiles, checks = [], [], []
    def evaluate(group, case, mode, geometry, y, ratio, metadata):
        w,h = geometry
        rows=[]
        for eps in EPS:
            r=cli(EXE,mode,geometry,w/2,y,ratio,eps)
            eta=abs(y-h/2)/(h/2)
            phi=1+(math.log(1-eta)+1.5)/(math.log(r["equivalent_radius_m"]/eps)+1.9)
            assert abs(r["correction_factor"]-1/phi)<1e-10
            rows.append(dict(epsilon_m_assumed=eps, corrected_mean_ratio=r["mean_velocity_mps"],
                             error_pct=100*(r["mean_velocity_mps"]-1),cli_output=r))
        return dict(group=group,case=case,geometry_m=geometry,point_m=[w/2,y],
                    reference_point_to_mean_ratio=ratio,raw_error_pct=100*(ratio-1),
                    normalized_reference_mean=1,results=rows,**metadata)
    def position(group,case,mode,geometry,d,side,metadata):
        w,h=geometry
        predicted=h/2*math.exp(-1.5)
        y=d if side=="floor" else h-d
        row=evaluate(group,case,mode,geometry,y,1,metadata)
        row.update(reference_gap_m=d,predicted_gap_m=predicted,
                   position_error_pct=100*(predicted/d-1),position_error_m=predicted-d,side=side)
        positions.append(row)
        q=cli(EXE,mode,geometry,w/2,predicted if side=="floor" else h-predicted,1,.0055)
        assert abs(q["correction_factor"]-1)<1e-10
        checks.append(q)

    # Song & Shi 2022, printed p53 Tables 1/2; W=H=.2 m (p49 Figure 2).
    # z+ = a+b exp(c v+) below; z+ = a-b exp(c v+) above.
    # These are fitted LDA profiles, NOT original point samples.
    experiments=[
        (1.68,23000,.1665,.1689,(-.0822,.01342,2.9195),(1.04414,.0094,3.1207)),
        (2.52,35000,.1535,.1540,(-.13498,.02004,2.6667),(1.02934,.00632,3.3676)),
        (3.29,46000,.1467,.1484,(-.10844,.01047,3.1933),(1.04757,.00514,3.6407)),
        (4.10,57000,.1146,.1056,(-.04579,.00464,3.5427),(1.03539,.00323,3.7763)),
        (4.67,65000,.0826,.0634,(-.01802,.00136,4.3037),(.9824,.000091,6.2216)),
    ]
    for u,re,lo,up,lower,upper in experiments:
        meta=dict(source_url=SONG_URL,source_location="p53 Tables 1/2; p49-50 geometry",
                  evidence="physical_LDA_fit",condition_id=f"Song_Re{re}",reported_mean_mps=u,
                  fully_developed_confirmed=False,roughness_measured=False)
        for side,fraction,coef in [("floor",lo,lower),("roof",up,upper)]:
            a,b,c=coef
            fitted_gap=a+b*math.exp(c) if side=="floor" else 1-a+b*math.exp(c)
            position("Song2022_LDA_contour",f"Re{re}_{side}","rectangle-wei-radial",
                     [.2,.2],fraction*.2,side,dict(**meta,table1_gap_fraction=fitted_gap,
                     table2_gap_fraction=fraction,table_rounding_difference=fitted_gap-fraction))
        for z in [.05,.1,.2,.35,.65,.8,.9,.95]:
            a,b,c=lower if z<.5 else upper
            ratio=math.log(((z-a) if z<.5 else (a-z))/b)/c
            assert ratio>0
            profiles.append(evaluate("Song2022_LDA_fitted_profile",f"Re{re}_z{z}",
                            "rectangle-wei-radial",[.2,.2],z*.2,ratio,
                            dict(**meta,z_fraction=z,fit_parameters=[a,b,c])))

    # Zhang et al. 2022 Table 6: two complete geometry blocks available
    # in publisher full-text index. W4 H3 block excluded from this script.
    for w,h,ds in [(5,3.5,[.3860,.3808,.3841,.3862,.3849]),
                   (6,4,[.4409,.4363,.4379,.4385,.4364])]:
        for u,d in zip([.8,2,4,6,8],ds):
            position("Zhang2022_CFD_rectangle",f"W{w}_H{h}_U{u}",
                     "rectangle-wei-radial",[w,h],d,"roof",
                     dict(source_url=ZHANG_URL,source_location="Table 6",
                          evidence="CFD_mean_contour",reported_mean_mps=u))
    for w,h,ds in [(4,3,[.3228,.3286,.3305,.3266,.3257]),
                   (4.5,3.3,[.3671,.3621,.3628,.3628,.3625])]:
        for u,d in zip([.8,2,4,6,8],ds):
            position("Zhang2022_CFD_semiarch",f"W{w}_H{h}_U{u}",
                     "semicircle-wei-radial",[w,h],d,"roof",
                     dict(source_url=ZHANG_URL,source_location="Table 7",
                          evidence="CFD_mean_contour",reported_mean_mps=u))
    for i,(w,h,u,d) in enumerate([(4.8,3.4,.56,.3946),(4.8,3.4,2.6,.3952),
                                  (5,3,2.8,.3437),(4.5,2.8,4.8,.3176)]):
        position("Zhang2022_Sima_field_proxy",f"Sima_{i+1}","rectangle-wei-radial",
                 [w,h],d,"roof",dict(source_url=ZHANG_URL,source_location="Table 12 and Figure 21",
                 evidence="field_mean_contour_average_distance_proxy",reported_mean_mps=u,
                 caveat="Published distance is averaged along contour, NOT a measured center-axis point.",
                 speed_discrepancy="Case 1: Figure21=.65, Table12=.56 m/s; position result unaffected." if i==0 else None))
    groups={}
    for g in sorted({r["group"] for r in positions+profiles}):
        rows=[r for r in positions+profiles if r["group"]==g]
        item=dict(evaluations=len(rows),raw=stats([r["raw_error_pct"] for r in rows]),
                  conditional_speed_by_epsilon={str(e):stats([r["results"][j]["error_pct"] for r in rows])
                                                for j,e in enumerate(EPS)})
        if "position_error_pct" in rows[0]:
            item["position"]=stats([r["position_error_pct"] for r in rows])
        groups[g]=item
    source_pdf=HERE/"sources/song2022_lda.pdf"
    out=dict(exe=str(EXE),exe_sha256=digest(EXE),script_sha256=digest(Path(__file__)),
             song_pdf_sha256=digest(source_pdf) if source_pdf.exists() else None,
             no_fitting=True,epsilon_policy="Frozen .0055 primary; .0001/.00001/.000001 sensitivity only. None measured; .0055 is not physically matched to smooth .2m model.",
             new_data_policy="Song new paper; Zhang existing paper, previously unused cases. 5 LDA conditions produce 10 contour and 40 fitted profile evaluations.",
             counts=dict(position_evaluations=len(positions),fit_profile_evaluations=len(profiles),
                         cli_calls=(len(positions)+len(profiles))*len(EPS)+len(checks)),
             groups=groups,positions=positions,profiles=profiles)
    (HERE/"expanded_validation_20260910.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# 扩展文献验证：数值结果（2026-09-10）","",
           "后端未改、未拟合。位置误差不等于均速误差。详细适用条件见 expanded_validation_20260910_report.md。","",
           "| 数据组 | 评价数 | 距壁位置 MAPE | 条件均速 MAPE，ε=5.5mm | 条件均速最大误差 |",
           "|---|---:|---:|---:|---:|"]
    for g,s in groups.items():
        p=f'{s["position"]["mape_pct"]:.3f}%' if "position" in s else "不适用"
        t=s["conditional_speed_by_epsilon"]["0.0055"]
        lines.append(f'| {g} | {s["evaluations"]} | {p} | {t["mape_pct"]:.3f}% | {t["max_abs_pct"]:.3f}% |')
    lines+=["","## 粗糙度敏感性：条件均速误差","",
            "| 组 | 假设 ε/m | MAPE | 最大绝对误差 | ≤10%数量 |","|---|---:|---:|---:|---:|"]
    for g,s in groups.items():
        for e,t in s["conditional_speed_by_epsilon"].items():
            lines.append(f'| {g} | {e} | {t["mape_pct"]:.3f}% | {t["max_abs_pct"]:.3f}% | {t["within_10"]}/{t["n"]} |')
    lines+=["","## 位置逐项结果","",
            "| 组/工况 | 参考距壁/m | 预测/m | 位置误差 |","|---|---:|---:|---:|"]
    for r in positions:
        lines.append(f'| {r["group"]}/{r["case"]} | {r["reference_gap_m"]:.6f} | {r["predicted_gap_m"]:.6f} | {r["position_error_pct"]:+.3f}% |')
    (HERE/"expanded_validation_20260910.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps(dict(counts=out["counts"],groups=groups),ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
