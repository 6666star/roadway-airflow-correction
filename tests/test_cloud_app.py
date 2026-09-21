"""Cloud entrypoint smoke test using the real compiled backend."""
import math
from pathlib import Path
from streamlit.testing.v1 import AppTest
ROOT=Path(__file__).resolve().parents[1]
app=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=240).run()
def healthy():
    assert not app.exception, [x.message for x in app.exception]
    assert not app.error, [x.value for x in app.error]
healthy()
assert not app.text_input, 'Cloud app must not expose the backend address'
for name, expected in [('圆拱示例','SEMICIRCLE_ARCH_WEI_RADIAL'),('Wei 点 111','RECTANGLE_WEI_RADIAL'),('三心拱示例','THREE_CENTER_ARCH_WEI_RADIAL'),('梯形示例','TRAPEZOID_WEI_RADIAL')]:
    next(b for b in app.button if b.label==name).click().run()
    next(b for b in app.button if b.label=='计算校正结果').click().run()
    healthy()
    result=app.session_state['v2_result']['result']
    assert result['model']['model_id']==expected
    assert result['mean_velocity_mps']>0
    if name=='圆拱示例':
        assert math.isclose(result['mean_velocity_mps'],3.48878933468352,rel_tol=1e-10)
    print('PASS',name,result['mean_velocity_mps'])
app.number_input(key='velocity').set_value(4.1).run()
healthy()
assert not app.metric, 'Stale results visible'
print('PASS: cloud startup, four shapes, real C++ results, hidden backend settings, stale-result guard')
