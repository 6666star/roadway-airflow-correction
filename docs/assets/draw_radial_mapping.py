"""Generate an exact geometric diagram, not a simulated velocity field."""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont

HERE=Path(__file__).resolve().parent
im=Image.new("RGB",(1800,820),"white")
d=ImageDraw.Draw(im)
font=lambda size:ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc",size)
ink="#203448"; accent="#c95729"; pale="#bdc9d2"
C=(2,1.5); P=(1,2)
lam=(-1+math.sqrt(76))/5
eta=1/lam
B=(2-lam,1.5+.5*lam)
e=(-1/math.sqrt(1.25),.5/math.sqrt(1.25))
left=lambda p:(450+140*(p[0]-2),425-140*(p[1]-1.5))
right=lambda p:(1330+230*p[0],425-230*p[1])
outline=[(0,0),(4,0),(4,1)]
outline += [(2+2*math.cos(math.pi*i/240),1+2*math.sin(math.pi*i/240)) for i in range(241)]
outline += [(0,0)]
circle=[(math.cos(2*math.pi*i/360),math.sin(2*math.pi*i/360)) for i in range(361)]
def path(points,transform,color,width=3,dashed=False):
    pts=[transform(p) for p in points]
    if not dashed:
        d.line(pts,fill=color,width=width)
    else:
        # Resample long line segments, so dashed boundaries remain complete.
        phase=0.
        for a,b in zip(pts,pts[1:]):
            length=math.dist(a,b); n=max(1,math.ceil(length/2))
            for j in range(n):
                t=j/n; u=(j+1)/n
                if int(phase/10)%2==0:
                    d.line([(a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])),
                            (a[0]+u*(b[0]-a[0]),a[1]+u*(b[1]-a[1]))],fill=color,width=width)
                phase+=length/n
def label(x,y,text,size=26,color=ink):
    d.text((x,y),text,font=font(size),fill=color,anchor="mm")
path(outline,left,ink,4)
path(circle,right,ink,4)
path([(C[0]+eta*(p[0]-C[0]),C[1]+eta*(p[1]-C[1])) for p in outline],left,accent,3,True)
path([(eta*p[0],eta*p[1]) for p in circle],right,accent,3,True)
for b in [(4,1),(4,0),(0,1),(2,3)]:
    dist=math.dist(C,b); v=((b[0]-C[0])/dist,(b[1]-C[1])/dist)
    path([C,b],left,pale,2);path([(0,0),v],right,pale,2)
for trans,c,p,b,names in [(left,C,P,B,("C","P","B")),
                         (right,(0,0),(eta*e[0],eta*e[1]),e,("O","P1","B1"))]:
    path([c,b],trans,accent,5)
    for pt,name,off,color in [(c,names[0],(19,30),ink),(p,names[1],(24,-27),accent),(b,names[2],(-28,-25),ink)]:
        x,y=trans(pt);d.ellipse((x-7,y-7,x+7,y+7),fill=color)
        label(x+off[0],y+off[1],name,28,color)
label(450,80,"真实断面",34)
label(450,129,"各方向的中心到边界距离不同",25)
label(1330,80,"单位圆",34)
label(1330,129,"各方向的中心到边界距离均为 1",25)
label(900,390,"→",65)
label(900,452,"按方向归一化",24)
label(450,685,"CP / CB = η ≈ 0.648",28)
label(1330,685,"OP1 / OB1 = η ≈ 0.648",28)
label(900,750,"虚线：相同 η 的点集；缩小的断面轮廓对应单位圆中的同心圆。",26)
label(900,793,"下一步：将单位圆所有长度乘以 r0，得到参考圆，相对位置 η 不变。",25)
assert abs(math.dist(B,(2,1))-2)<1e-12
assert abs(math.dist(C,P)/math.dist(C,B)-eta)<1e-12
im.save(HERE/"radial_mapping_explainer.png")
print(f"Geometric checks passed: eta={eta:.12f}")
