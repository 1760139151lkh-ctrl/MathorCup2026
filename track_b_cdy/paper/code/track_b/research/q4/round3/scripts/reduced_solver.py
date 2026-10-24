"""Independent conservative shallow-water baseline. Not r.avaflow or D-Claw.

Array row velocity points south; exported north velocity has the opposite sign.
Volume is conserved in transport. Bed pressure sources are side-specific Audusse
hydrostatic reconstruction; Coulomb/Voellmy friction contracts momentum only.
"""
from __future__ import annotations
import hashlib, json, time, sys
from pathlib import Path
import numpy as np
try:
    from numba import njit
except ImportError:
    def njit(*a, **kw):
        def deco(f): return f
        return deco

G = 9.81
DRY = 1e-9

@njit(cache=True)
def face_flux(hl, ul, vl, zl, hr, ur, vr, zr, gravity):
    zface = max(zl, zr)
    left = max(0.0, hl + zl - zface)
    right = max(0.0, hr + zr - zface)
    speed = max(abs(ul) + np.sqrt(gravity * left), abs(ur) + np.sqrt(gravity * right))
    f0 = .5 * (left * ul + right * ur - speed * (right-left))
    f1 = .5 * (left*ul*ul + .5*gravity*left*left + right*ur*ur + .5*gravity*right*right - speed*(right*ur-left*ul))
    f2 = .5 * (left*ul*vl + right*ur*vr - speed*(right*vr-left*vl))
    return f0, f1, f2, .5*gravity*(hl*hl-left*left), .5*gravity*(hr*hr-right*right)

@njit(cache=True)
def speeds(h, mx, my):
    ny,nx = h.shape
    ux=np.zeros_like(h);uy=np.zeros_like(h)
    for i in range(ny):
        for j in range(nx):
            if h[i,j]>DRY:
                ux[i,j]=mx[i,j]/h[i,j];uy[i,j]=my[i,j]/h[i,j]
    return ux,uy

@njit(cache=True)
def timestep(h, mx, my, dx, dy, cfl, gravity, one_d):
    ny,nx=h.shape
    max_rate=0.0
    for i in range(ny):
        for j in range(nx):
            if h[i,j]>DRY:
                u=abs(mx[i,j]/h[i,j]);v=abs(my[i,j]/h[i,j]);c=np.sqrt(gravity*h[i,j])
                rate=(u+c)/dx
                if not one_d: rate+=(v+c)/dy
                max_rate=max(max_rate,rate)
    return cfl/max_rate if max_rate>0 else 30.0

@njit(cache=True)
def advance(h,mx,my,z,cosine,dx,dy,dt,mu,xi,gravity,closed,one_d):
    ny,nx=h.shape
    ux,uy=speeds(h,mx,my)
    fx=np.zeros((3,ny,nx+1));fy=np.zeros((3,ny+1,nx))
    cxL=np.zeros((ny,nx+1));cxR=np.zeros((ny,nx+1))
    cyL=np.zeros((ny+1,nx));cyR=np.zeros((ny+1,nx))
    for i in range(ny):
        for j in range(nx+1):
            il=max(0,j-1);ir=min(nx-1,j)
            ul=ux[i,il];ur=ux[i,ir]
            if closed and j==0: ul=-ur
            if closed and j==nx: ur=-ul
            a,b,c,dl,dr=face_flux(h[i,il],ul,uy[i,il],z[i,il],h[i,ir],ur,uy[i,ir],z[i,ir],gravity)
            fx[0,i,j]=a;fx[1,i,j]=b;fx[2,i,j]=c;cxL[i,j]=dl;cxR[i,j]=dr
    if not one_d:
        for i in range(ny+1):
            for j in range(nx):
                il=max(0,i-1);ir=min(ny-1,i)
                ul=uy[il,j];ur=uy[ir,j]
                if closed and i==0: ul=-ur
                if closed and i==ny: ur=-ul
                a,b,c,dl,dr=face_flux(h[il,j],ul,ux[il,j],z[il,j],h[ir,j],ur,ux[ir,j],z[ir,j],gravity)
                fy[0,i,j]=a;fy[1,i,j]=c;fy[2,i,j]=b;cyL[i,j]=dl;cyR[i,j]=dr
    hn=np.empty_like(h);xn=np.empty_like(h);yn=np.empty_like(h)
    clipping=0.0;minimum=1e99
    for i in range(ny):
        for j in range(nx):
            depth=h[i,j]-dt/dx*(fx[0,i,j+1]-fx[0,i,j])
            xmom=mx[i,j]-dt/dx*(fx[1,i,j+1]+cxL[i,j+1]-fx[1,i,j]-cxR[i,j])
            ymom=my[i,j]-dt/dx*(fx[2,i,j+1]-fx[2,i,j])
            if not one_d:
                depth-=dt/dy*(fy[0,i+1,j]-fy[0,i,j])
                xmom-=dt/dy*(fy[1,i+1,j]-fy[1,i,j])
                ymom-=dt/dy*(fy[2,i+1,j]+cyL[i+1,j]-fy[2,i,j]-cyR[i,j])
            minimum=min(minimum,depth)
            if depth<0:
                clipping-=depth*dx*dy
                depth=0
            if depth>DRY:
                speed=np.sqrt(xmom*xmom+ymom*ymom)/depth
                rhs=max(0.0,speed-dt*mu*gravity*cosine[i,j])
                a=dt*gravity/(xi*depth) if xi>0 else 0.0
                new_speed=2*rhs/(1+np.sqrt(1+4*a*rhs))
                factor=new_speed/speed if speed>0 else 0.0
                xmom*=factor;ymom*=factor
            else: xmom=0.0;ymom=0.0
            hn[i,j]=depth;xn[i,j]=xmom;yn[i,j]=ymom
    outward=0.0;inward=0.0
    for i in range(ny):
        for v in (-fx[0,i,0]*dy*dt,fx[0,i,nx]*dy*dt):
            if v>=0: outward+=v
            else: inward-=v
    if not one_d:
        for j in range(nx):
            for v in (-fy[0,0,j]*dx*dt,fy[0,ny,j]*dx*dt):
                if v>=0: outward+=v
                else: inward-=v
    return hn,xn,yn,outward,inward,clipping,minimum

def run(h,z,dx,dy,duration,mu=0.15,xi=1000,cfl=.35,closed=False,
        targets=None,interval=30,one_d=False,initial_mx=None,initial_my=None,
        save_snapshots=True,progress=False):
    """Conservative transport to requested horizon; no kinetic early stopping."""
    h=np.array(h,dtype=np.float64,copy=True);z=np.asarray(z,dtype=np.float64)
    mx=np.zeros_like(h) if initial_mx is None else np.array(initial_mx,copy=True)
    my=np.zeros_like(h) if initial_my is None else np.array(initial_my,copy=True)
    if one_d: gradx=np.gradient(z[0],dx)[None,:];grady=np.zeros_like(z)
    else: grady,gradx=np.gradient(z,dy,dx)
    cosine=1/np.sqrt(1+gradx**2+grady**2)
    initial=float(h.sum()*dx*dy);outflow=inflow=clipping=0.0
    maxh=h.copy();maxv=np.zeros_like(h);time_now=0.0;steps=0
    min_raw=float(h.min());last_output=0.0;next_output=interval
    times=[0.0];snapshots=[h.astype('float32')] if save_snapshots else []
    records=[];targets=targets or {};arrivals={k:None for k in targets}
    last_target_dry={k:0.0 for k in targets};brackets={k:None for k in targets}
    wallclock=time.perf_counter();status='completed';reason=None
    records.append({'elapsed_seconds':0.,'domain_volume_m3':initial,'outflow_m3':0.,'inflow_m3':0.,'maxdepth_m':float(h.max()),'maxspeed_m_s':0.})
    while time_now<duration-1e-9:
        dt=min(timestep(h,mx,my,dx,dy,cfl,G,one_d),duration-time_now,next_output-time_now)
        if dt<=1e-12:
            next_output=min(duration,next_output+interval);continue
        previous_time=time_now
        h,mx,my,out,inc,clip,minimum=advance(h,mx,my,z,cosine,dx,dy,dt,mu,xi,G,closed,one_d)
        time_now+=dt;steps+=1;outflow+=out;inflow+=inc;clipping+=clip;min_raw=min(min_raw,float(minimum))
        if minimum< -1e-8 or not np.isfinite(h).all() or not np.isfinite(mx).all() or not np.isfinite(my).all():
            status='numerical_failure';reason='nonfinite state or negative raw depth below -1e-8';break
        u,v=speeds(h,mx,my);speed=np.hypot(u,v)
        maxh=np.maximum(maxh,h);maxv=np.maximum(maxv,speed)
        for k,mask in targets.items():
            if arrivals[k] is None:
                if mask.any() and float(h[mask].max())>=.1:
                    arrivals[k]=time_now;brackets[k]=[previous_time,time_now]
                else:last_target_dry[k]=time_now
        if time_now>=next_output-1e-8 or time_now>=duration-1e-8:
            times.append(time_now)
            if save_snapshots:snapshots.append(h.astype('float32'))
            records.append({'elapsed_seconds':time_now,'domain_volume_m3':float(h.sum()*dx*dy),'outflow_m3':outflow,'inflow_m3':inflow,'maxdepth_m':float(h.max()),'maxspeed_m_s':float(speed[h>=.1].max()) if np.any(h>=.1) else 0.})
            next_output=min(duration,next_output+interval)
            if progress and len(records)%10==0: print(json.dumps({'t':time_now,'step':steps,'maxh':float(h.max()),'outflow':outflow}),flush=True)
        if steps>300000: status='numerical_failure';reason='300000 step safety limit';break
    u,v=speeds(h,mx,my);speed=np.hypot(u,v)
    final=float(h.sum()*dx*dy)
    summary={'execution_status':status,'failure_reason':reason,'duration_requested_seconds':duration,'duration_actual_seconds':time_now,'steps':steps,'wall_seconds':time.perf_counter()-wallclock,
      'initial_volume_m3':initial,'final_domain_volume_m3':final,'outflow_volume_m3':outflow,'inflow_volume_m3':inflow,'depth_clipping_added_volume_m3':clipping,
      'mass_balance_residual_m3':final+outflow-inflow-clipping-initial,'relative_mass_balance_error':(final+outflow-inflow-clipping-initial)/initial if initial else 0.,
      'minimum_preclip_depth_m':min_raw,'minimum_final_depth_m':float(h.min()),'max_depth_m':float(maxh.max()),'maximum_speed_any_wet_m_s':float(maxv.max()),
      'max_speed_final_h_ge_01_m_s':float(speed[h>=.1].max()) if np.any(h>=.1) else 0.,'final_stationary_volume_v_lt_01_m3':float(h[(speed<.1)].sum()*dx*dy),'footprint_area_hmax_ge_01_m2':int((maxh>=.1).sum())*dx*dy,
      'target_arrivals':{k:{'travel_time_seconds':arrivals[k],'arrival_status':('numerical_failure' if status=='numerical_failure' else 'arrived' if arrivals[k] is not None else 'missing' if not mask.any() else 'out_of_domain' if outflow>initial*.999 else 'not_reached_within_horizon'), 'arrival_time_bracket_seconds':brackets[k],'target_cells':int(mask.sum()),'definition':'first solver step with h >= 0.1 m in raster target mask; previous step below threshold','time_origin':'seconds after scenario bulk release','initiation_to_release_delay_seconds':None} for k,mask in targets.items()}}
    fields={'h_final':h.astype('float32'),'maxdepth':maxh.astype('float32'),'maxspeed':maxv.astype('float32'),'u_east_final':u.astype('float32'),'v_north_final':(-v).astype('float32'),'times':np.array(times),'snapshots':np.stack(snapshots) if snapshots else np.empty((0,))}
    return summary,fields,records

def file_record(path,role):
    p=Path(path);return {'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'role':role}

def write_json(path,obj):
    def scalar(value):
        if isinstance(value,np.generic):return value.item()
        if isinstance(value,np.ndarray):return value.tolist()
        raise TypeError(type(value).__name__)
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False,default=scalar)+'\n')
