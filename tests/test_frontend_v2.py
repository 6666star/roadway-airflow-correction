"""Headless Streamlit widget tests against a real gRPC server and C++ CLI."""
import math
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'frontend'),str(ROOT/'generated')]
from streamlit.testing.v1 import AppTest
from grpc_adapter.server import create_server
import v2_support as ui

def button(app,label):return next(b for b in app.button if b.label==label)
def healthy(app):assert not app.exception,[e.message for e in app.exception]
def calculate(app):
    button(app,'计算校正结果').click().run(timeout=30)
    healthy(app)
    assert not app.error,[e.value for e in app.error]
    return app.session_state['v2_result']

def main():
    assert math.isclose(ui.rise_from_radii(4,3,.5),1)
    assert not ui.inside('semicircle',dict(width=4,height=3),(0.1,2.9))
    assert ui.inside('trapezoid',dict(bottom_width=3,top_width=5,height=3),(-.3,2.5))
    for dims in [(4,1,.5),(4,3,2),(4,float('nan'),.5)]:
        try:ui.rise_from_radii(*dims)
        except ValueError:pass
        else:raise AssertionError('Invalid three-center accepted')
    service=create_server(ROOT/'build-codex/airflow_cli.exe')
    port=service.add_insecure_port('127.0.0.1:0'); service.start()
    old=os.environ.get('AIRFLOW_GRPC_ADDRESS')
    os.environ['AIRFLOW_GRPC_ADDRESS']=f'127.0.0.1:{port}'
    try:
        app=AppTest.from_file(str(ROOT/'frontend/app.py'),default_timeout=20).run()
        healthy(app)
        r=calculate(app)
        assert r['result']['model']['model_id']=='SEMICIRCLE_ARCH_WEI_RADIAL'
        assert math.isclose(r['result']['mean_velocity_mps'],3.48878933468352,rel_tol=1e-10)
        assert r['request']['absolute_roughness_m']==.0055
        assert 'mapping_center_x_m' not in r['request']
        assert [m.label for m in app.metric]==['校正系数 K','估算截面均速','估算风量','断面面积']
        assert not any(e.label in ['模型信息与后端提示','现有验证证据与限制'] for e in app.expander)
        assert not app.get('download_button')
        # Compact preview must not stretch across the full page.
        assert "width=460" in (ROOT/'frontend/app.py').read_text(encoding='utf-8')
        # Changed inputs must never display the previous numeric result.
        app.number_input(key='velocity').set_value(4).run(); healthy(app)
        assert not app.metric and any('旧结果' in i.value for i in app.info)
        app.number_input(key='sensor_x').set_value(0).run()
        assert app.error and button(app,'计算校正结果').disabled
        for name,model in [('Wei 点 111','RECTANGLE_WEI_RADIAL'),('三心拱示例','THREE_CENTER_ARCH_WEI_RADIAL'),('梯形示例','TRAPEZOID_WEI_RADIAL')]:
            button(app,name).click().run(); healthy(app)
            r=calculate(app); assert r['result']['model']['model_id']==model
        # Three-center tangency is derived, not guessed.
        button(app,'三心拱示例').click().run()
        app.number_input(key='big_r').set_value(1).run(); healthy(app)
        assert app.error and button(app,'计算校正结果').disabled
        # Rectangle always uses radial mapping, including custom centers.
        button(app,'Wei 点 111').click().run()
        assert [v.label for v in app.selectbox]==['断面类型']
        assert [v.label for v in app.checkbox]==['自定义映射中心']
        r=calculate(app)
        assert r['result']['model']['model_id']=='RECTANGLE_WEI_RADIAL'
        app.checkbox(key='custom_center').check().run()
        app.number_input(key='center_x').set_value(2.1).run()
        r=calculate(app); assert r['request']['mapping_center_x_m']==2.1
        assert 'mapping_center_y_m' in r['request']
        # Bad endpoint clears old results and reports failure without traceback.
        app.text_input(key='endpoint').set_value('127.0.0.1:1').run()
        button(app,'计算校正结果').click().run(timeout=30); healthy(app)
        assert app.error and not app.metric
        assert not app.radio
        assert not any('V2 径向映射为工程近似模型' in c.value for c in app.caption)
        print('PASS: four radial shapes, real RPC, unit conversion, tangency, invalid points, custom center, stale results, network failure, simplified UI')
    finally:
        service.stop(0).wait()
        if old is None:os.environ.pop('AIRFLOW_GRPC_ADDRESS',None)
        else:os.environ['AIRFLOW_GRPC_ADDRESS']=old

if __name__=='__main__':main()
