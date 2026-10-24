"""Executed numerical checks, independent of any regional event validation."""
from pathlib import Path
import json, datetime, csv
import numpy as np
from reduced_solver import run, write_json,advance,timestep

R=Path(__file__).resolve().parents[1]

def main():
    results={'evaluation_stratum':'numerical_benchmark','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cases':[]}
    # Still water with genuinely dry high terrain.
    x,y=np.meshgrid(np.arange(100)*10,np.arange(80)*10)
    z=.8*np.exp(-((x-500)**2+(y-400)**2)/(200**2))+.03*np.sin(x/200)
    h=np.maximum(.5-z,0)
    s,f,_=run(h,z,10,10,300,mu=0,xi=0,closed=True,interval=300)
    case={'case_id':'lake_at_rest_wet_dry','summary':s,'max_h_change_m':float(np.abs(f['h_final']-h).max()),'max_speed_m_s':float(f['maxspeed'].max()),'tolerance_h_m':1e-6,'tolerance_speed_m_s':1e-7}
    case['pass']=case['max_h_change_m']<case['tolerance_h_m'] and case['max_speed_m_s']<case['tolerance_speed_m_s'];results['cases'].append(case)
    # Analytic Ritter dam-break (flat, initially dry downstream, no friction).
    ritter=[]
    for dx,cfl in [(5.,.35),(2.5,.35),(1.25,.35),(2.5,.175)]:
        xx=np.arange(-500+dx/2,500,dx);h=(xx<0).astype(float)[None,:];z=np.zeros_like(h)
        s,f,_=run(h,z,dx,1,20,mu=0,xi=0,cfl=cfl,one_d=True,closed=True,interval=20)
        c=np.sqrt(9.81);exact=np.where(xx<=-20*c,1.,np.where(xx<40*c,4/(9*9.81)*(c-xx/(40))**2,0.))
        err=float(np.mean(np.abs(f['h_final'][0]-exact)))
        ritter.append({'dx_m':dx,'cfl':cfl,'l1_depth_error_m':err,'summary':s})
    refinement=[x['l1_depth_error_m'] for x in ritter[:3]]
    results['cases'].append({'case_id':'ritter_dry_bed_grid_and_cfl','runs':ritter,'grid_error_strictly_decreases':bool(refinement[2]<refinement[1]<refinement[0]),'cfl_halving_depth_l1_difference_m':float(abs(ritter[1]['l1_depth_error_m']-ritter[3]['l1_depth_error_m'])),'pass':bool(refinement[2]<refinement[1]<refinement[0])})
    # Radial release tests cross-direction symmetry and dry fronts.
    x,y=np.meshgrid((np.arange(100)+.5)*5,(np.arange(100)+.5)*5)
    h=(((x-250)**2+(y-250)**2)<50**2).astype(float);z=np.zeros_like(h)
    s,f,_=run(h,z,5,5,30,mu=0,xi=0,closed=True,interval=30)
    sym=float(np.max(np.abs(f['h_final']-f['h_final'].T)))
    results['cases'].append({'case_id':'radial_dry_front','summary':s,'transpose_symmetry_max_h_m':sym,'pass':abs(s['relative_mass_balance_error'])<1e-11 and s['minimum_preclip_depth_m']>=-1e-8 and sym<1e-6})
    # A moving finite plug crosses an open right boundary; actual signed flux is booked.
    xx=np.arange(.5,600,1.);h=((xx>200)&(xx<400)).astype(float)[None,:];z=np.zeros_like(h)
    s,f,_=run(h,z,1,1,70,mu=0,xi=0,one_d=True,initial_mx=h*10,interval=70)
    results['cases'].append({'case_id':'open_boundary_volume_ledger','summary':s,'pass':s['outflow_volume_m3']>0 and abs(s['relative_mass_balance_error'])<1e-10})
    # A uniform incline demonstrates both consistency and steep-cell limitations.
    incline=[]
    for dx in [20.,10.,5.]:
        xx=(np.arange(400)+.5)*dx;h=np.ones((1,400))*10;z=(-.2*xx)[None,:]
        s,f,_=run(h,z,dx,1,5,mu=.15,xi=1000,one_d=True,interval=5)
        actual=float(np.mean(f['u_east_final'][0,180:220]));A=9.81*(.2-.15/np.sqrt(1+.2**2));B=9.81/(1000*10);exact=np.sqrt(A/B)*np.tanh(np.sqrt(A*B)*5)
        incline.append({'dx_m':dx,'actual_centre_speed_m_s':actual,'cartesian_graph_constant_depth_exact_m_s':float(exact),'absolute_error_m_s':float(abs(actual-exact)),'bed_step_over_depth':.2*dx/10,'summary':s})
    results['cases'].append({'case_id':'uniform_incline_grid_response','runs':incline,'pass':bool(incline[2]['absolute_error_m_s']<incline[0]['absolute_error_m_s']),'interpretation':'Cartesian graph acceleration g*tan(theta), vertical depth. This is not terrain-normal avalanche momentum.'})
    # Separately declared constant-depth rigid parcel equation, using actual surface station.
    theta=np.arctan(.2);h=15.;mu=.15;xi=1000.;A=9.81*(np.sin(theta)-mu*np.cos(theta));B=9.81/(xi*h);T=120.
    analytic_v=float(np.sqrt(A/B)*np.tanh(np.sqrt(A*B)*T));analytic_s=float(np.log(np.cosh(np.sqrt(A*B)*T))/B)
    def parcel(dt):
        v=s=0.
        for _ in range(round(T/dt)):
            # RK4 v, with s integrated by the same stages.
            k1=A-B*v*v;k2=A-B*(v+dt*k1/2)**2;k3=A-B*(v+dt*k2/2)**2;k4=A-B*(v+dt*k3)**2
            s+=dt*(v+2*(v+dt*k1/2)+2*(v+dt*k2/2)+(v+dt*k3))/6;v+=dt*(k1+2*k2+2*k3+k4)/6
        return v,s
    rigid=[]
    for dt in [1.,.5,.25]:
        v,s=parcel(dt);rigid.append({'dt_seconds':dt,'v_m_s':v,'s_m':s,'v_absolute_error':abs(v-analytic_v),'s_absolute_error':abs(s-analytic_s)})
    results['cases'].append({'case_id':'rigid_constant_slope_voellmy_analytic','analytic_v_m_s':analytic_v,'analytic_s_m':analytic_s,'runs':rigid,'pass':rigid[-1]['s_absolute_error']<1e-4,'interpretation':'additional ODE benchmark only; no volume transport and not an event prediction nor the 1D FV model'})
    results['all_declared_checks_pass']=all(c['pass'] for c in results['cases'])
    results['pass_scope']='Declared algebraic properties and direction of grid response only; not a quantitative regional accuracy acceptance or event validation.'
    results['regional_event_accuracy_accepted']=False
    results['incline_accuracy_warning']='At h10m, slope.2, dx20m, the centre speed error is about 75%; refinement reduces this but 60/120m regional grids are not demonstrated accurate.'
    results['jit_evidence']={'advance_compiled_signatures':[str(x) for x in getattr(advance,'signatures',[])],'timestep_compiled_signatures':[str(x) for x in getattr(timestep,'signatures',[])],'all_jit_functions_have_signatures':bool(getattr(advance,'signatures',[]) and getattr(timestep,'signatures',[]))}
    write_json(R/'results/reduced_numerical_validation.json',results)
    print(json.dumps({'all_pass':bool(results['all_declared_checks_pass']),'cases':[(c['case_id'],bool(c['pass'])) for c in results['cases']]}),flush=True)

if __name__=='__main__':main()
