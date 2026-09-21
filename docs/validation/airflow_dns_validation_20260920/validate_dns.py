from pathlib import Path
import numpy as np,struct,json,math,subprocess,hashlib
P=Path(__file__).resolve().parent
EXE=Path(r'C:\Users\staro\Desktop\Cluade\Project_1_v2\build-codex\airflow_cli.exe')
ETA=1-math.exp(-1.5)

def interp(g,u,x,y):
 x,y=np.broadcast_arrays(x,y); ix=np.clip(np.searchsorted(g,x)-1,0,len(g)-2);iy=np.clip(np.searchsorted(g,y)-1,0,len(g)-2)
 a=(x-g[ix])/(g[ix+1]-g[ix]);b=(y-g[iy])/(g[iy+1]-g[iy])
 return (1-a)*(1-b)*u[ix,iy]+a*(1-b)*u[ix+1,iy]+(1-a)*b*u[ix,iy+1]+a*b*u[ix+1,iy+1]

def load(f):
 if f.suffix=='.bin':
  b=f.read_bytes();n,m,ub,ut,nu,ts=struct.unpack('<ii4d',b[:40]);a=np.frombuffer(b,offset=40,dtype='<f8');g=a[:n];z=a[n:n+m];assert np.allclose(g,z)
  u=a[n+m:n+m+n*m].reshape((n,m),order='F')/ub
  assert len(b)==40+8*(n+m+9*n*m)
  sym=sum([u,u[::-1],u[:,::-1],u[::-1,::-1],u.T,u.T[::-1],u.T[:,::-1],u.T[::-1,::-1]])/8
  k=n//2;g=g[k:];g[0] if False else None;u=sym[k:,k:];meta=dict(source='Pinelli_KIT',Re_b_halfwidth=ub/nu,Re_tau=ut/nu,bulk_velocity_header=ub)
 else:
  lines=f.read_text().splitlines();start=next(i for i,l in enumerate(lines) if 'DT=(' in l)+1;a=np.loadtxt(lines[start:]);g=np.unique(a[:,0]);n=len(g);assert len(a)==n*n
  # Explicit coordinate ordering, rather than assuming Tecplot indexing.
  u=np.zeros((n,n));u[np.searchsorted(g,a[:,0]),np.searchsorted(g,a[:,1])]=a[:,2]
  ratio=float(np.median(a[:,2]/a[:,3]));g=-g[::-1];u=u[::-1,::-1];u=(u+u.T)/2
  # Symmetry at centre and no-slip at wall; boundaries absent from cell-centred source.
  u=np.pad(u,((1,1),(1,1)),mode='edge');u[-1,:]=0;u[:,-1]=0;g=np.r_[0,g,1]
  meta=dict(source='Rome_author_database',Re_tau_filename=int(f.stem.split('Retau')[1]),utau_over_ub=ratio)
 assert np.all(np.diff(g)>0)
 integral=float(np.trapezoid(np.trapezoid(u,g,axis=1),g))
 assert abs(integral-1)<.003,(f.name,integral)
 return g,u,dict(meta,file=f.name,integrated_u_over_ub=integral,shape=list(u.shape))

def cli(x,y,v):
 args=[str(EXE),'rectangle-wei-radial','4','4',str(2+2*x),str(2+2*y),str(v),'.0055'];r=json.loads(subprocess.check_output(args,text=True,encoding='utf-8'));assert r['success'];return r

def metrics(e):
 a=np.abs(e)*100;return dict(n=int(a.size),mape_pct=float(a.mean()),max_abs_pct=float(a.max()),within_5_pct=float((a<=5).mean()*100),within_10_pct=float((a<=10).mean()*100))

results=[];audit=[]
for f in sorted(P.glob('statistics_*.bin'))+sorted(P.glob('plotyz_Retau*.dat')):
 g,u,meta=load(f);s=np.linspace(0,1,41)
 v=interp(g,u,np.full(s.shape,ETA),ETA*s)
 contour=[]
 for q,val in zip(s,v):
  low,high=0.,1.
  for _ in range(45):
   mid=(low+high)/2
   if interp(g,u,mid,mid*q)>1:low=mid
   else:high=mid
  t=(low+high)/2
  contour.append(dict(side_fraction=float(q),eta_model=ETA,eta_dns=t,point_u_over_ub=float(val),mean_inversion_error_pct=float((val-1)*100),gap_error_pct=100*((1-ETA)/(1-t)-1)))
 for q in [0,.5,1]:
  val=float(interp(g,u,ETA,ETA*q));r=cli(ETA,ETA*q,val);assert abs(r['correction_factor']-1)<1e-9;assert abs(r['mean_velocity_mps']-val)<1e-9
  audit.append(dict(case=f.name,kind='mean_contour',s=q,input_ratio=val,output=r))
 rings=[]
 for eta in [.25,.5,.75,.9,.95]:
  vv=interp(g,u,np.full(s.shape,eta),eta*s);lo=float(vv.min());hi=float(vv.max())
  rings.append(dict(eta=eta,axis=float(vv[0]),diagonal=float(vv[-1]),min_ratio=lo,max_ratio=hi,unavoidable_max_mean_inversion_error_pct=100*(hi-lo)/(hi+lo)))
 sens=[];convergence=[]
 for n in [200,400]:
  a=(np.arange(n)+.5)/n;x,y=np.meshgrid(a,a,indexing='ij');eta=np.maximum(x,y);ref=interp(g,u,x,y)
  for er in ([.00275] if n==200 else [1e-5,1e-4,.001,.00275,.01]):
   phi=1+(np.log1p(-eta)+1.5)/(math.log(1/er)+1.9);valid=phi>0
   for limit in [.8,.9,.95,1.]:
    mask=(eta<=limit)&valid;mm=metrics(ref[mask]/phi[mask]-1);row=dict(grid=n,epsilon_over_r0=er,eta_limit=limit,area_fraction_analyzed=float(mask.mean()),invalid_area_fraction=float(((eta<=limit)&~valid).mean()),**mm)
    if n==400:sens.append(row)
    else:convergence.append(row)
  if n==400:np.savez_compressed(P/(f.stem+'_normalized.npz'),coordinates=g,velocity_ratio=u)
 # Fixed-default model consistency checks away from its mean contour.
 for xx,yy in [(.2,.1),(.6,.3),(.9,.8)]:
  val=float(interp(g,u,xx,yy));r=cli(xx,yy,val);ph=1+(math.log1p(-max(xx,yy))+1.5)/(math.log(1/.00275)+1.9);assert abs(r['mean_velocity_mps']-val/ph)<1e-9;audit.append(dict(case=f.name,kind='field_formula_check',output=r))
 row=dict(**meta,contour_summary=metrics(v-1),contour=contour,rings=rings,sensitivity=sens,coarse_grid_check=convergence)
 results.append(row); print(f.name,'bulk',round(meta['integrated_u_over_ub'],6),'contour',row['contour_summary'],'ring .9',rings[3],flush=True)
(P/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8');(P/'cli_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print('DONE',len(results),'cases',len(audit),'CLI checks')
