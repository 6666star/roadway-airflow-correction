"""Single-command entrypoint for local use and Streamlit Community Cloud."""
import os
import runpy
from pathlib import Path
import streamlit as st
from cloud_runtime import start_backend

ROOT = Path(__file__).resolve().parent
try:
    with st.spinner("正在准备计算服务，首次启动需要编译…"):
        backend = start_backend()
except Exception:
    import logging
    logging.exception("Cloud backend initialization failed")
    st.error("计算服务启动失败，请管理员检查应用日志后重启。")
    st.stop()
os.environ["AIRFLOW_MANAGED_BACKEND"] = "1"
os.environ["AIRFLOW_GRPC_ADDRESS"] = backend.address
runpy.run_path(str(ROOT / "frontend" / "app.py"), run_name="__main__")
