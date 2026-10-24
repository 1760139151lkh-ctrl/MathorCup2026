"""Regional conditional scenarios with immutable common spatial inputs."""
from __future__ import annotations
from pathlib import Path
import argparse,csv,datetime,json,platform,sys,hashlib
import numpy as np
from reduced_solver import run,write_json,file_record

R=Path(__file__).resolve().parents[1]
C=Path('<LOCAL_HOME>/Documents/MathorCup/research_cache/round3/q4/reduced')
TARGET=np.array([340981.541,3129214.005])

def scenarios():
    rows=[('ref',15,.15,1000),('h5',5,.15,1000),('h30',30,.15,1000),('mu08',15,.08,1000),('mu25',15,.25,1000),('xi500',15,.15,500),('xi2000',15,.15,2000),('h136',136,.15,1000)]
    return [dict(name=n,thickness_m=h,mu=mu,xi=xi) for n,h,mu,xi in rows]

def terrain(res):
    p=R/f'results/spatial_inputs_{res}m.npz';d=np.load(p)
    return {k:d[k] for k in d.files},file_record(p,'frozen common terrain and source binary mask')

def path_data(path_id,dx=60):
    rows=[r for r in csv.DictReader((R/'results/spatial_paths.csv').open()) if r['path_id']==path_id]
    station=np.array([float(r['distance_m']) for r in rows]);xx=np.array([float(r['x_m']) for r in rows]);yy=np.array([float(r['y_m']) for r in rows]);zz=np.array([float(r['elevation_m']) for r in rows])
    n=int(np.ceil(station[-1]/dx));dx=station[-1]/n;ss=(np.arange(n)+.5)*dx
    x=np.interp(ss,station,xx);y=np.interp(ss,station,yy);z=np.interp(ss,station,zz)
    d,_=terrain(60);transform=d['transform'];rr=np.floor((transform[5]-y)/60).astype(int);cc=np.floor((x-transform[2])/60).astype(int)
    in_source=d['source_mask'][np.clip(rr,0,d['z'].shape[0]-1),np.clip(cc,0,d['z'].shape[1]-1)].astype(bool)
    # Only the contiguous source reach beginning at the source representative point.
    first_dry=np.flatnonzero(~in_source)
    end=int(first_dry[0]) if len(first_dry) else len(in_source)
    if end<1:raise ValueError('path does not begin in the common binary source mask')
    release=np.arange(n)<end
    source_area=float(d['source_mask'].sum()*60**2);width=source_area/(release.sum()*dx)
    return {'s':ss,'x':x,'y':y,'z':z[None,:],'release':release[None,:],'dx':dx,'width':width,'source_area':source_area,'target':(np.hypot(x-TARGET[0],y-TARGET[1])<=100)[None,:],'source_reach_length_m':end*dx,'path_length_m':station[-1]}

def output_run(identifier,model,params,summary,fields,series,inputs,extra):
    out=C/identifier;out.mkdir(parents=True,exist_ok=True)
    arrays=out/'fields.npz';np.savez_compressed(arrays,**fields)
    record={'run_id':identifier,'model_id':model,'mechanism_id':'homogeneous_coulomb_voellmy','experiment_id':'regional_ofat','scenario_id':f"q4-r3-release-h{params['thickness_m']}-v0",'geometry_version':'q4-r3-spatial-copdem-v1','parameter_version':'q4-r3-reduced-v1','evaluation_stratum':'conditional_scenario','parameters':params,'density_kg_m3':2000,'density_role':'scenario bulk density, not observed; no role in volume dynamics','initial_velocity':{'east_m_s':0,'north_m_s':0,'crs':'EPSG:32645'},'time_origin':'bulk release','initiation_to_release_delay_seconds':None,'inputs':inputs,'summary':summary,'fields':file_record(arrays,'full gridded maxdepth/maxspeed/final state and 30s process snapshots'), 'execution':{'python':sys.version,'platform':platform.platform()},**extra}
    record['summary']['initial_mass_kg']=summary['initial_volume_m3']*2000;record['summary']['final_mass_kg']=summary['final_domain_volume_m3']*2000
    write_json(R/f'results/reduced_{identifier}.json',record)
    p=R/f'results/reduced_{identifier}_timeseries.csv'
    with p.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(series[0]));w.writeheader();w.writerows(series)
    print(json.dumps({'finished':identifier,'status':summary['execution_status'],'wall_seconds':summary['wall_seconds'],'maxdepth':summary['max_depth_m'],'arrivals':summary['target_arrivals'],'mass_error':summary['relative_mass_balance_error']}),flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['2d','1d','all'],default='all');parser.add_argument('--select',default='all');args=parser.parse_args()
    selected=lambda name:args.select=='all' or name in args.select.split(',')
    params=scenarios()
    if args.mode in ['2d','all']:
        jobs=[(s,60,.35) for s in params]+[(params[0],120,.35),(params[0],60,.175)]
        for par,res,cfl in jobs:
            name=f"2d_{par['name']}_{res}m"+('_cflhalf' if cfl<.35 else '')
            if not selected(name):continue
            d,irec=terrain(res);dx=float(d['dx']);mask=d['source_mask'].astype(bool);source60,_=terrain(60);area=float(source60['source_mask'].sum()*60**2);scale=area/(mask.sum()*dx**2)
            h=mask.astype(float)*par['thickness_m']*scale
            x,y=np.meshgrid(d['x'],d['y']);target=(np.hypot(x-TARGET[0],y-TARGET[1])<=100)
            # Diagnostic receiving river, without implying source-to-river proof.
            channel=(d['channel_distance_m']<=100)&~mask
            s,f,t=run(h,d['z'],dx,dx,1800,mu=par['mu'],xi=par['xi'],cfl=cfl,targets={'paper_port_symbol':target,'candidate_channel':channel},progress=True)
            f.update(x=d['x'],y=d['y'],z=d['z'],source_mask=mask,target_mask=target)
            bedstep=np.maximum(np.abs(np.gradient(d['z'],axis=0)),np.abs(np.gradient(d['z'],axis=1)))
            extra={'raster_shape':list(h.shape),'resolution_m':dx,'source_area_m2_common':area,'native_source_area_m2':int(mask.sum())*dx**2,'source_depth_scale':scale,'source_initial_volume_integral_m3':float(h.sum()*dx**2),'target_definition':'cell centres within 100 m of paper_port_symbol; h>=0.1m at solver step','source_bedstep_gt_thickness_fraction':float((bedstep[mask]>h[mask]).mean()),'no_entrainment':True,'deposition_interpretation':'h_final is residual material, not all stationary deposit'}
            extra['source_bedstep_diagnostic_definition']='legacy key: max absolute central row/col elevation difference (one-cell slope proxy); not maximum adjacent face jump'
            output_run(name,'independent_2d_hydrostatic_fv',{**par,'resolution_m':res,'cfl':cfl},s,f,t,[irec],extra)
    if args.mode in ['1d','all']:
        for path_id in ['P1','P2','P3']:
            for par in params:
                name=f"1d_{path_id}_{par['name']}"
                if not selected(name):continue
                d=path_data(path_id);h=d['release'].astype(float)*par['thickness_m']
                s,f,t=run(h,d['z'],d['dx'],d['width'],1800,mu=par['mu'],xi=par['xi'],one_d=True,targets={'paper_port_symbol':d['target']},progress=False)
                # Longitudinal momentum is mapped onto local UTM tangents for export.
                along=f['u_east_final'].copy();tx=np.gradient(d['x'],d['s']);ty=np.gradient(d['y'],d['s']);norm=np.hypot(tx,ty);tx/=norm;ty/=norm
                f['u_path_final']=along;f['u_east_final']=along*tx[None,:];f['v_north_final']=along*ty[None,:]
                f.update(station=d['s'],x=d['x'],y=d['y'],z=d['z'],target_mask=d['target'])
                extra={k:d[k] for k in ['source_area','source_reach_length_m','path_length_m','width']};extra.update(path_id=path_id,effective_width_role='constant equivalent width chosen from common raster source area / contiguous path source length; not measured valley width',distance_definition='horizontal UTM45N centreline station, raw DEM elevations interpolated; no monotonic forcing',target_definition='path cell centre within 100 m of paper_port_symbol with h>=0.1 m',lateral_spreading='not represented',no_entrainment=True)
                output_run(name,'independent_1d_path_fv',{**par,'resolution_m':d['dx'],'cfl':.35},s,f,t,[file_record(R/'results/spatial_paths.csv','common terrain-controlled path ensemble'),file_record(R/'results/spatial_inputs_60m.npz','common source area for mass matching')],extra)

if __name__=='__main__':main()
