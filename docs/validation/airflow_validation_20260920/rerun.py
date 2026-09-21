from pathlib import Path
import sys, importlib.util, json, hashlib, contextlib, time
from datetime import datetime, timezone
PROJECT=Path("C:/Users/staro/Desktop/Cluade/Project_1_v2")
OUT=Path(__file__).resolve().parent
LIB=PROJECT/"validation/literature"
sys.path.insert(0,str(LIB))
import run_validation
EXE=PROJECT/"build-codex/airflow_cli.exe"
original_cli=run_validation.cli
calls=[]
def audited_cli(*args):
    result=original_cli(*args)
    calls.append(dict(arguments=[str(v) for v in args],result=result))
    return result
run_validation.cli=audited_cli
names=["run_validation","run_field_validation_round2","run_user_articles","run_engineering_audit_20260910","run_expanded_validation_20260910"]
for name in names:
    module=__import__(name)
    source=LIB/(name+".py")
    (OUT/(name+"_snapshot.py")).write_bytes(source.read_bytes())
    module.HERE=OUT
    module.ROOT=PROJECT
    module.EXE=EXE
    module.cli=audited_cli
    if name=="run_engineering_audit_20260910":
        module.FIXTURE=OUT/"user_articles_results.json"
        module.PREFIX=OUT/"field_retest_20260920"
    sys.argv=[name,"--exe",str(EXE)] if name=="run_validation" else [name]
    with (OUT/(name+".log")).open("w",encoding="utf-8") as log, contextlib.redirect_stdout(log):
        module.main()
    print("Completed",name, "cumulative CLI calls",len(calls),flush=True)
audit=dict(generated_at=datetime.now(timezone.utc).isoformat(),exe=str(EXE),exe_sha256=hashlib.sha256(EXE.read_bytes()).hexdigest(),calls=len(calls),no_model_changes=True,no_fitting=True,records=calls,source_files={str(p.relative_to(PROJECT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in list((PROJECT/"src").glob("*.cpp"))+list((PROJECT/"include/airflow").glob("*.hpp"))})
(OUT/"execution_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
print("ALL DONE",len(calls),flush=True)
