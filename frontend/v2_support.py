"""Frontend geometry validation and drawing only; velocities come from gRPC."""
from __future__ import annotations
import math
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'generated'))
import airflow_correction_pb2 as pb

SHAPES={'半圆拱（直墙＋半圆顶）':('semicircle',pb.GEOMETRY_TYPE_SEMICIRCLE_ARCH,'SEMICIRCLE_ARCH_WEI_RADIAL'),
        '矩形':('rectangle',pb.GEOMETRY_TYPE_RECTANGLE,'RECTANGLE_WEI_RADIAL'),
        '三心拱（对称相切）':('threecenter',pb.GEOMETRY_TYPE_THREE_CENTER_ARCH,'THREE_CENTER_ARCH_WEI_RADIAL'),
        '等腰梯形':('trapezoid',pb.GEOMETRY_TYPE_TRAPEZOID,'TRAPEZOID_WEI_RADIAL')}

def rise_from_radii(w,R,r):
    if not all(math.isfinite(v) and v>0 for v in [w,R,r]):
        raise ValueError('宽度和两个圆弧半径必须为有限正数。')
    if not (R>r and r<w/2):
        raise ValueError('三心拱要求大圆半径 R > 小圆半径 r，且 r < W/2。')
    q=(R-r)**2-(w/2-r)**2
    if q<=0:
        raise ValueError('这组宽度和半径无法构成当前标准相切三心拱；要求 R-r > W/2-r。')
    return R-math.sqrt(q)

def extent(shape,d):
    w=d.get('width',d.get('bottom_width'))
    h=d['wall_height']+d['arch_rise'] if shape=='threecenter' else d['height']
    return w,h

def validate_dimensions(shape,d):
    for name,v in d.items():
        if not math.isfinite(v) or (v<0 if name=='wall_height' else v<=0):
            raise ValueError('尺寸必须有限且为正；直墙高度允许为零。')
    w,h=extent(shape,d)
    if shape=='semicircle' and h<w/2:
        raise ValueError('半圆拱总高 H 必须不小于 W/2。')
    if shape=='threecenter':
        f=rise_from_radii(w,d['crown_radius'],d['side_radius'])
        if not math.isclose(f,d['arch_rise'],rel_tol=1e-8,abs_tol=1e-10):
            raise ValueError('三心拱拱高与圆弧相切条件不一致。')

def roof(shape,d,x):
    w,h=extent(shape,d); a=abs(x-w/2)
    if shape=='rectangle':return h
    if shape=='semicircle':return h-w/2+math.sqrt(max(0,(w/2)**2-a*a))
    R,r=d['crown_radius'],d['side_radius']; wall=d['wall_height']; f=d['arch_rise']
    join=R*(w/2-r)/(R-r)
    if a<=join:return wall+f-R+math.sqrt(max(0,R*R-a*a))
    return wall+math.sqrt(max(0,r*r-(a-(w/2-r))**2))

def inside(shape,d,p,strict=True):
    x,y=p; w,h=extent(shape,d); tol=1e-9 if strict else -1e-9
    if not all(math.isfinite(v) for v in p) or y<=tol or y>=h-tol:return False
    if shape=='trapezoid':
        half=(w+(d['top_width']-w)*y/h)/2
        return abs(x-w/2)<half-tol
    if x<=tol or x>=w-tol:return False
    return y<roof(shape,d,x)-tol

def validate_input(shape,d,p,center,velocity,eps):
    validate_dimensions(shape,d)
    if not math.isfinite(velocity) or velocity<=0:raise ValueError('请输入大于零的时间平均点风速。')
    if not math.isfinite(eps) or eps<=0:raise ValueError('粗糙度必须大于零。')
    if not inside(shape,d,p):raise ValueError('传感器必须严格位于实际断面内部，不能在壁面或断面外。')
    if not inside(shape,d,center):raise ValueError('映射中心必须严格位于断面内部。')

def request(typ,model,d,p,velocity,eps,custom_center=None):
    req=pb.CorrectionRequest(geometry=pb.GeometryRequest(type=typ,dimensions_m=d),
        sensor=pb.SensorMeasurement(x_m=p[0],y_m=p[1],measured_velocity_mps=velocity),
        model_id=model,absolute_roughness_m=eps)
    if custom_center is not None:
        req.mapping_center_x_m,req.mapping_center_y_m=custom_center
    return req

def sketch(shape,d,p,c):
    """Equal-scale SVG geometry preview, not a velocity contour plot."""
    w,h=extent(shape,d)
    extra=max(0,(d.get('top_width',w)-w)/2)
    lo,hi=-extra,w+extra
    scale=min(460/(hi-lo),310/h)
    def xy(q):return 62+(q[0]-lo)*scale,365-q[1]*scale
    if shape=='trapezoid':points=[(0,0),(w,0),((w+d['top_width'])/2,h),((w-d['top_width'])/2,h)]
    elif shape=='rectangle':points=[(0,0),(w,0),(w,h),(0,h)]
    else:points=[(0,0),(w,0)]+[(w*(1-j/160),roof(shape,d,w*(1-j/160))) for j in range(161)]
    coords=' '.join(f'{xy(q)[0]:.3f},{xy(q)[1]:.3f}' for q in points)
    valid=inside(shape,d,p) and inside(shape,d,c)
    extra_svg=''
    if valid and math.dist(p,c)>1e-10:
        dx,dy=p[0]-c[0],p[1]-c[1]; low,high=0.,1.
        while inside(shape,d,(c[0]+high*dx,c[1]+high*dy)):high*=2
        for _ in range(55):
            m=(low+high)/2
            if inside(shape,d,(c[0]+m*dx,c[1]+m*dy)):low=m
            else:high=m
        b=(c[0]+high*dx,c[1]+high*dy); bx,by=xy(b); cx,cy=xy(c)
        extra_svg=f'<line x1="{cx}" y1="{cy}" x2="{bx}" y2="{by}" stroke="#0d9488" stroke-width="2" stroke-dasharray="6 4"/><circle cx="{bx}" cy="{by}" r="4" fill="#0d9488"/><text x="{bx+8}" y="{by-8}">B</text>'
    markers=''
    for q,label,color in [(c,'C','#2563eb'),(p,'P','#ea580c')]:
        # Avoid unbounded viewBox expansion for invalid user coordinates.
        if lo<=q[0]<=hi and 0<=q[1]<=h:
            x,y=xy(q); markers+=f'<circle cx="{x}" cy="{y}" r="5" fill="{color}"/><text x="{x+9}" y="{y-9}">{label}</text>'
    ox,oy=xy((0,0))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 590 415" role="img" aria-label="断面、传感器和中心射线示意图"><rect width="590" height="415" rx="16" fill="#f8fafc"/><g font-family="sans-serif" font-size="14" fill="#334155"><polygon points="{coords}" fill="#e0f2fe" stroke="#334155" stroke-width="2"/>{extra_svg}{markers}<text x="{ox}" y="{oy+26}">O (0,0) · x →</text><text x="18" y="48">y ↑</text><text x="300" y="397">W = {w:.3f} m · H = {h:.3f} m</text></g></svg>'
