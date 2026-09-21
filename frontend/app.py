#!/usr/bin/env python3
"""V2 Streamlit client: radial correction, geometry preview and auditable RPC."""
from __future__ import annotations
import hashlib
import os
import sys
from datetime import datetime,timezone
from pathlib import Path
import grpc
import streamlit as st
from google.protobuf.json_format import MessageToDict

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'frontend'),str(ROOT/'generated')]
import v2_support as ui
import airflow_correction_pb2_grpc as rpc

st.set_page_config(page_title='巷道风速校正 · V2',page_icon='🌬️',layout='wide')
st.title('巷道风速校正 · V2')
st.caption('几何输入 → 径向映射 → 单点反演均速与风量 ｜ 结果由 C++ 后端计算')

def number(label,*,value,key,**kwargs):
    # Initialize once so example callbacks do not conflict with widget defaults.
    if key not in st.session_state:st.session_state[key]=value
    result=st.number_input(label,value=None,key=key,**kwargs)
    if result is None:
        st.error(f'请填写：{label}'); st.stop()
    return result

if os.environ.get('AIRFLOW_MANAGED_BACKEND') == '1':
    address=os.environ['AIRFLOW_GRPC_ADDRESS']
    timeout=30.
else:
    with st.sidebar:
        st.subheader('后端连接')
        address=st.text_input('gRPC 地址',os.environ.get('AIRFLOW_GRPC_ADDRESS','127.0.0.1:51051'),key='endpoint')
        timeout=st.number_input('请求超时（秒）',min_value=1.,max_value=60.,value=10.)
        st.caption('请先启动本地计算后端，或使用 streamlit_app.py 自动启动。')

def preset(name):
    common=dict(roughness_mm=5.5,custom_center=False)
    data={
      '圆拱示例':dict(shape='半圆拱（直墙＋半圆顶）',width=4.,height=4.,sensor_x=2.,sensor_y=3.2,velocity=3.75),
      'Wei 点 111':dict(shape='矩形',width=4.94,height=3.43,sensor_x=.4,sensor_y=3.03,velocity=1.8),
      '三心拱示例':dict(shape='三心拱（对称相切）',threecenter_width=2.,wall=1.5,big_r=1.5,small_r=.5,sensor_x=1.,sensor_y=2.,velocity=2.),
      '梯形示例':dict(shape='等腰梯形',bottom=4.78,top=4.43,height=3.6,sensor_x=1.0875,sensor_y=1.8,velocity=2.)}
    st.session_state.update(common|data[name]); st.session_state.pop('v2_result',None)

with st.expander('快速填入示例（不会自动计算）'):
    cols=st.columns(4)
    for col,name in zip(cols,['圆拱示例','Wei 点 111','三心拱示例','梯形示例']):
        col.button(name,on_click=preset,args=(name,))
    st.caption('圆拱示例来自张浪2018；Wei点111来自Wei2019。三心拱是几何示例；梯形采用Luo2020尺寸，但此处速度2m/s为演示输入，不是验证点。')

shape_label=st.selectbox('断面类型',list(ui.SHAPES),key='shape')
shape,typ,model=ui.SHAPES[shape_label]
left,right=st.columns([1,1],gap='large')
errors=[]
with left:
    st.subheader('01 断面尺寸')
    if shape=='trapezoid':
        bottom=number('下底宽 B（m）',min_value=.01,value=4.78,step=.1,key='bottom')
        top=number('上底宽 T（m）',min_value=.01,value=4.43,step=.1,key='top')
        height=number('总高 H（m）',min_value=.01,value=3.6,step=.1,key='height')
        dims=dict(bottom_width=bottom,top_width=top,height=height)
        st.caption('上底相对下底居中；允许上宽下窄。原点为下底左端，上底较宽时部分x为负数。')
    else:
        width=number('净宽 W（m）',min_value=.01,value=2. if shape=='threecenter' else 4.,step=.1,key='threecenter_width' if shape=='threecenter' else 'width')
        if shape=='threecenter':
            wall=number('直墙高 h（m）',min_value=0.,value=1.5,step=.1,key='wall')
            R=number('顶部大圆半径 R（m）',min_value=.01,value=1.5,step=.1,key='big_r')
            r=number('两侧小圆半径 r（m）',min_value=.01,value=.5,step=.05,key='small_r')
            try:f=ui.rise_from_radii(width,R,r)
            except ValueError as exc:errors.append(str(exc)); f=0.
            dims=dict(width=width,wall_height=wall,arch_rise=f,crown_radius=R,side_radius=r)
            if not errors:st.info(f'相切条件自动推导：拱高 f = {f:.4f} m；总高 H = {wall+f:.4f} m')
            st.caption('f = R − √[(R−r)²−(W/2−r)²]。不把拱高和两个半径同时作为独立输入。')
        else:
            height=number('总高 H（m）',min_value=.01,value=4.,step=.1,key='height')
            dims=dict(width=width,height=height)
            if shape=='semicircle':st.caption(f'顶拱半径 W/2 = {width/2:.3f} m；直墙高 H−W/2 = {height-width/2:.3f} m。')
    w,h=ui.extent(shape,dims)
    roughness=number('等效绝对粗糙度 ε（mm）',min_value=.001,value=5.5,step=.5,format='%.3f',key='roughness_mm')/1000
    st.caption('粗糙度不是矿井摩擦阻力系数 α，也不是无量纲 Darcy 摩擦系数。')

with right:
    st.subheader('02 传感器位置与点速')
    st.caption('x 从底板左端向右，y 从底板向上；均以米计。弧形断面也使用同一坐标，不固定在中心线上。')
    sx=number('传感器 x（m）',value=2.,step=.05,key='sensor_x')
    sy=number('传感器 y（m）',value=3.2,step=.05,key='sensor_y')
    velocity=number('时间平均实测点风速（m/s）',min_value=.001,value=3.75,step=.1,key='velocity')
    custom=st.checkbox('自定义映射中心',key='custom_center')
    if custom:
        cx=number('中心 x（m）',value=w/2,step=.05,key='center_x')
        cy=number('中心 y（m）',value=h/2,step=.05,key='center_y')
    else:cx,cy=w/2,h/2
    st.caption(f'当前中心 C=({cx:.3f}, {cy:.3f}) m；默认是包围框中心，不代表实测最大风速位置。')

try:ui.validate_input(shape,dims,(sx,sy),(cx,cy),velocity,roughness)
except ValueError as exc:
    if str(exc) not in errors:errors.append(str(exc))
if errors:
    for error in errors:st.error(error)
else:
    with st.expander('断面与测点示意图',expanded=True):
        st.image(ui.sketch(shape,dims,(sx,sy),(cx,cy)),width=460)
        st.caption('C：映射中心；P：传感器；B：射线与边界交点。等比例几何示意，不是实测风场。')

req=ui.request(typ,model,dims,(sx,sy),velocity,roughness,(cx,cy) if custom else None)
signature=hashlib.sha256(req.SerializeToString(deterministic=True)+address.encode()).hexdigest()
if st.button('计算校正结果',type='primary',disabled=bool(errors),width='stretch'):
    st.session_state.pop('v2_result',None)
    try:
        with st.spinner('正在调用 V2 后端…'),grpc.insecure_channel(address) as channel:
            stub=rpc.AirflowCorrectionServiceStub(channel)
            response=stub.CalculateCorrection(req,timeout=timeout)
            if not response.success:raise ValueError(f'{response.error_code}：{response.message}')
            if response.model.model_id!=model:raise ValueError('服务返回模型与请求不一致，请确认连接的是 V2 后端。')
            st.session_state.v2_result=dict(signature=signature,request=MessageToDict(req,preserving_proto_field_name=True),
                result=MessageToDict(response,preserving_proto_field_name=True),
                response=response.SerializeToString(),generated_at=datetime.now(timezone.utc).isoformat(),server=address)
    except grpc.RpcError as exc:
        st.error(f'后端调用失败：{exc.code().name} — {exc.details()}。请确认 V2 后端已启动、地址正确。')
    except ValueError as exc:st.error(str(exc))

saved=st.session_state.get('v2_result')
if saved and saved['signature']!=signature:
    st.info('输入或服务地址已变化，旧结果已隐藏。请重新计算。')
elif saved and not errors:
    response=ui.pb.CorrectionResponse.FromString(saved['response'])
    st.subheader('03 校正结果')
    st.success('计算完成。以下为模型估算值，不是独立实测均速。')
    cols=st.columns(4)
    for col,label,value in zip(cols,['校正系数 K','估算截面均速','估算风量','断面面积'],
      [f'{response.correction_factor:.5f}',f'{response.mean_velocity_mps:.4f} m/s',f'{response.air_volume_m3ps:.3f} m³/s',f'{response.section_area_m2:.3f} m²']):col.metric(label,value)
    st.caption(f'均速 = 点速 × K；风量 = 面积 × 均速。风量折合 {response.air_volume_m3ps*60:.2f} m³/min。')
