"""Summaries and figures from actually executed reduced model packets."""
from pathlib import Path
import csv,datetime,json,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reduced_solver import write_json,file_record

R=Path(__file__).resolve().parents[1]
def load():
    return sorted([json.loads(p.read_text()) for p in (R/'results').glob('reduced_[12]d_*.json')],key=lambda x:x['run_id'])

def export_path_vectors():
    """Preserve raw fields from the in-flight pre-export-fix driver if present."""
    for p in sorted((R/'results').glob('reduced_1d_*.json')):
        r=json.loads(p.read_text());d=np.load(r['fields']['path'])
        if 'u_path_final' in d.files:continue
        f={k:d[k] for k in d.files};along=f['u_east_final'].copy()
        tx=np.gradient(f['x'],f['station']);ty=np.gradient(f['y'],f['station']);norm=np.hypot(tx,ty);tx/=norm;ty/=norm
        f['u_path_final']=along;f['u_east_final']=along*tx[None,:];f['v_north_final']=along*ty[None,:]
        out=Path(r['fields']['path']).with_name('fields_vectors.npz');np.savez_compressed(out,**f)
        r['raw_solver_fields']=r['fields'];r['fields']=file_record(out,'derived 1D longitudinal velocity mapped to local UTM45N east/north tangents; raw scalar fields retained')
        r['velocity_export_postprocess']='No dynamics recomputation; u_path_final retained. Tangents follow candidate horizontal path.'
        write_json(p,r)

def terrain_diagnostics():
    for p in sorted((R/'results').glob('reduced_2d_*.json')):
        r=json.loads(p.read_text());res=r['parameters']['resolution_m'];d=np.load(R/f'results/spatial_inputs_{res}m.npz');z=d['z'];m=d['source_mask'].astype(bool);q=np.zeros_like(z)
        a=np.abs(np.diff(z,axis=0));q[:-1]=np.maximum(q[:-1],a);q[1:]=np.maximum(q[1:],a)
        a=np.abs(np.diff(z,axis=1));q[:,:-1]=np.maximum(q[:,:-1],a);q[:,1:]=np.maximum(q[:,1:],a)
        thickness=r['parameters']['thickness_m']*r['source_depth_scale']
        r['source_bedstep_diagnostic_definition']='legacy key: max absolute central row/col elevation difference, one-cell slope proxy; not maximum adjacent face jump'
        r['source_max_adjacent_face_jump_gt_initial_h_fraction']=float(np.mean(q[m]>thickness))
        r['source_max_adjacent_face_jump_definition']='maximum |z_neighbour-z_cell| over four direct neighbours, compared with actual initial thickness'
        write_json(p,r)

def additional_targets(runs):
    """All newly registered targets, using stored outputs without solver reruns."""
    path=R/'results/spatial_targets_v2.csv'
    if not path.exists():return
    targets=list(csv.DictReader(path.open()));rows=[]
    for r in runs:
        d=np.load(r['fields']['path']);times=d['times'];frames=d['snapshots']
        is1d=r['model_id'].startswith('independent_1d')
        if is1d:x,y=d['x'][None,:],d['y'][None,:]
        else:x,y=np.meshgrid(d['x'],d['y'])
        for target in targets:
            mask=np.hypot(x-float(target['x_m']),y-float(target['y_m']))<=100
            peak=np.array([float(a[mask].max()) if mask.any() else np.nan for a in frames]);hit=np.flatnonzero(peak>=.1)
            idx=int(hit[0]) if len(hit) else None
            upper=float(times[idx]) if idx is not None else None;lower=float(times[max(0,idx-1)]) if idx is not None else None
            state='arrived' if idx is not None else 'missing' if not mask.any() else 'numerical_failure' if r['summary']['execution_status']=='numerical_failure' else 'not_reached_within_horizon'
            rows.append({'run_id':r['run_id'],'scenario_id':r['scenario_id'],'model_id':r['model_id'],'target_id':target['target_id'],'target_kind':target['target_kind'],'geometry_version':target['geometry_version'],'source_geometry_version':r['geometry_version'],'parameter_version':r['parameter_version'],'travel_time_seconds':upper,'arrival_status':state,'arrival_lower_seconds':lower,'arrival_upper_seconds':upper,'target_cells':int(mask.sum()),'actual_horizon_seconds':float(times[-1]),'definition':'first saved 30s output h>=0.1m within 100m representative-centroid buffer; previous saved output below threshold; not solver-step precision','postprocess_without_rerun':True,'time_origin':'bulk release','initiation_to_release_delay_seconds':None,'evaluation_stratum':'conditional_scenario','include_in_arrival_envelope':False,'field_sha256':r['fields']['sha256']})
    with (R/'results/reduced_osm_target_arrivals_v2.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write_json(R/'results/reduced_osm_target_postprocess_v2.json',{'protocol':file_record(R/'config/additional_target_protocol_v2.json','prior registration for all five targets'),'target_input':file_record(path,'all five OSM representative centroids'),'rows':len(rows),'runs':len(runs),'targets_per_run':len(targets),'postprocess_is_not_solver_rerun':True,'primary_paper_target_unchanged':True,'count_arrived':sum(x['arrival_status']=='arrived' for x in rows),'status_counts':{k:sum(x['arrival_status']==k for x in rows) for k in sorted(set(x['arrival_status'] for x in rows))},'include_in_arrival_envelope':False,'reason':'reduced HR thin-flow numerical accuracy not qualified','missing_semantics':'Finite path/grid cell centres have no support inside the specified 100m object buffer; no nearest-cell substitution or extrapolation.'})

def main():
    export_path_vectors()
    terrain_diagnostics()
    runs=load();by={r['run_id']:r for r in runs};tables=[]
    additional_targets(runs)
    for r in runs:
        s=r['summary'];p=r['parameters'];arrival=s['target_arrivals']['paper_port_symbol'];fields=np.load(r['fields']['path'])
        row={k:r[k] for k in ['run_id','model_id','scenario_id','geometry_version','parameter_version','evaluation_stratum']}
        row.update({k:p[k] for k in ['thickness_m','mu','xi','resolution_m','cfl']});row.update({k:s[k] for k in ['execution_status','duration_actual_seconds','steps','wall_seconds','initial_volume_m3','final_domain_volume_m3','outflow_volume_m3','inflow_volume_m3','depth_clipping_added_volume_m3','relative_mass_balance_error','minimum_preclip_depth_m','max_depth_m','maximum_speed_any_wet_m_s','final_stationary_volume_v_lt_01_m3','footprint_area_hmax_ge_01_m2']})
        row.update(travel_time_seconds=arrival['travel_time_seconds'],arrival_status=arrival['arrival_status'],arrival_definition=arrival['definition'],target_id='paper_port_symbol',target_cells=arrival['target_cells'],time_origin='bulk release',initiation_to_release_delay_seconds=None)
        if r['model_id'].startswith('independent_1d'):
            mask=fields['maxdepth'][0]>=.1;row['runout_station_m']=float(fields['station'][mask].max()) if mask.any() else 0
        else:
            gx,gy=np.meshgrid(fields['x'],fields['y']);source=np.array([355410.,3130050.]);wet=fields['maxdepth']>=.1
            row['max_radial_distance_from_source_m']=float(np.hypot(gx-source[0],gy-source[1])[wet].max()) if wet.any() else 0
        tables.append(row)
    columns=list(dict.fromkeys(k for r in tables for k in r))
    with (R/'results/reduced_runs.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(tables)
    with (R/'results/reduced_target_arrivals.csv').open('w') as f:
        cols=['run_id','scenario_id','model_id','target_id','geometry_version','parameter_version','travel_time_seconds','arrival_status','arrival_definition','target_cells','time_origin','initiation_to_release_delay_seconds','evaluation_stratum'];w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(tables)
    # Reference process and spatial fields, in kilometre local coordinates.
    if '2d_ref_60m' in by:
        r=by['2d_ref_60m'];d=np.load(r['fields']['path']);extent=[d['x'][0]/1000,d['x'][-1]/1000,d['y'][-1]/1000,d['y'][0]/1000]
        fig,axes=plt.subplots(2,2,figsize=(12,7),constrained_layout=True)
        for ax,field,title,label in zip(axes.flat,['z','maxdepth','maxspeed','h_final'],['Copernicus DEM; conditional source','Maximum depth over 1800 s','Maximum speed over wet cells','Residual depth at 1800 s'],['m elevation','m depth','m/s; h > 1e-9 m','m residual; not all stationary']):
            a=d[field];plot=np.ma.masked_where(a<.1,a) if field in ['maxdepth','h_final'] else a
            im=ax.imshow(plot,extent=extent,origin='upper',cmap='terrain' if field=='z' else 'viridis');fig.colorbar(im,ax=ax,shrink=.75,label=label);ax.contour(d['x']/1000,d['y']/1000,d['source_mask'],levels=[.5],colors=['red'],linewidths=.6);ax.scatter([340.981541],[3129.214005],s=30,c='magenta',marker='x');ax.set_title(title,fontsize=10);ax.set_xlabel('UTM45N east (km)');ax.set_ylabel('UTM45N north (km)')
        fig.suptitle('Independent 2D FV baseline — h0=15 m, mu=.15, xi=1000; conditional scenario',fontsize=11);fig.savefig(R/'figures/reduced_2d_reference.png',dpi=180);plt.close(fig)
        fig,axes=plt.subplots(2,3,figsize=(13,6),constrained_layout=True)
        for ax,T in zip(axes.flat,[0,60,180,360,900,1800]):
            idx=int(np.argmin(np.abs(d['times']-T)));im=ax.imshow(np.ma.masked_less(d['snapshots'][idx],.1),extent=extent,origin='upper',vmin=.1,vmax=min(100,float(d['maxdepth'].max())),cmap='viridis');ax.set_title(f"t={d['times'][idx]:.0f} s");ax.scatter([340.981541],[3129.214005],c='magenta',marker='x',s=15);ax.set_xlabel('Easting (km)');ax.set_ylabel('Northing (km)')
        fig.colorbar(im,ax=list(axes.flat),label='Depth (m); <.1 masked',shrink=.8);fig.suptitle('2D reference snapshots; release-relative, no observed timing fit');fig.savefig(R/'figures/reduced_2d_snapshots.png',dpi=180);plt.close(fig)
    regional2=[x for x in tables if x['run_id'].startswith('2d_')]
    if regional2:
        fig,axes=plt.subplots(1,3,figsize=(14,5),constrained_layout=True)
        labels=[x['run_id'].replace('2d_','') for x in regional2]
        for ax,key,title,scale in zip(axes,['footprint_area_hmax_ge_01_m2','max_depth_m','outflow_volume_m3'],['Footprint hmax >= .1 m (km²)','Maximum depth (m)','Volume out of domain (Mm³)'],[1e6,1,1e6]):
            ax.barh(labels,[x[key]/scale for x in regional2]);ax.set_title(title,fontsize=10);ax.grid(axis='x',alpha=.25)
            if all(x[key]==0 for x in regional2):
                ax.set_xlim(0,1);ax.text(.5,.5,'All runs: 0 outflow',transform=ax.transAxes,ha='center',va='center',fontsize=11,color='dimgray')
        fig.suptitle('Executed 2D one-factor sensitivities; no probability weights');fig.savefig(R/'figures/reduced_2d_sensitivity.png',dpi=180);plt.close(fig)
    if all(f'1d_{p}_ref' in by for p in ['P1','P2','P3']):
        fig,axes=plt.subplots(3,1,figsize=(12,9),constrained_layout=True)
        for ax,p in zip(axes,['P1','P2','P3']):
            d=np.load(by[f'1d_{p}_ref']['fields']['path']);ax.plot(d['station']/1000,d['z'][0],color='saddlebrown',label='raw terrain-controlled path');ax.set_ylabel('Elevation (m)');ax.set_title(f'{p}: equivalent-width conservative 1D path flow');ax2=ax.twinx()
            for sc in ['ref','mu08','h136']:
                key=f'1d_{p}_{sc}'
                if key in by:
                    a=np.load(by[key]['fields']['path']);ax2.plot(a['station']/1000,a['maxdepth'][0],label=sc,alpha=.85)
            ax2.set_ylabel('Maximum depth (m)');ax2.legend(loc='upper right',fontsize=8);ax.set_xlabel('Horizontal path distance (km)');ax.grid(alpha=.2)
        fig.suptitle('1D profiles retain topographic barriers; mass transport, no lateral spreading');fig.savefig(R/'figures/reduced_1d_profiles.png',dpi=180);plt.close(fig)
    # Actual grid/CFL differences, not a declaration of asymptotic convergence.
    comparisons=[]
    if '2d_ref_60m' in by:
        ref=by['2d_ref_60m']
        for key in ['2d_ref_120m','2d_ref_60m_cflhalf']:
            if key in by:
                a=by[key];metrics={}
                for m in ['footprint_area_hmax_ge_01_m2','max_depth_m','maximum_speed_any_wet_m_s','outflow_volume_m3']:
                    v=ref['summary'][m];w=a['summary'][m];metrics[m]={'reference':v,'other':w,'relative_change':(w-v)/v if v else None}
                comparisons.append({'reference':ref['run_id'],'other':key,'metrics':metrics,'interpretation':'sensitivity only; no asymptotic grid-convergence assertion from two grids'})
    write_json(R/'results/reduced_comparisons.json',{'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runs_executed':len(runs),'one_d_runs':sum(x['run_id'].startswith('1d_') for x in runs),'two_d_runs':sum(x['run_id'].startswith('2d_') for x in runs),'status_counts':{k:sum(x['arrival_status']==k for x in tables) for k in sorted(set(x['arrival_status'] for x in tables))},'numerical_sensitivity':comparisons,'external_validation_events':0,'calibration_events':0,'all_runs_are_conditional_scenarios':True})
    benchmark_path=R/'results/reduced_numerical_validation.json'
    bench=json.loads(benchmark_path.read_text()) if benchmark_path.exists() else {}
    if bench:
        incline=next(x for x in bench['cases'] if x['case_id']=='uniform_incline_grid_response')['runs']
        relative=[x['absolute_error_m_s']/x['cartesian_graph_constant_depth_exact_m_s'] for x in incline]
        bench['regional_thin_flow_accuracy_qualified']=False
        bench['known_numerical_defects']={'uniform_incline_speed_relative_errors':relative,'uniform_incline_grid_m':[20,10,5],'regional_reference_source_central_gradient_one_cell_drop_gt_h_fraction':by.get('2d_ref_60m',{}).get('source_bedstep_gt_thickness_fraction'),'regional_reference_source_max_adjacent_face_jump_gt_h_fraction':by.get('2d_ref_60m',{}).get('source_max_adjacent_face_jump_gt_initial_h_fraction'),'interpretation':'HR bed steps and friction splitting strongly suppress thin flow; similar defect applies to 1D. Conservative and refinement checks are not regional accuracy qualification.'}
        write_json(benchmark_path,bench)
    for row in tables:
        row['include_in_arrival_envelope']=False
        row['accuracy_qualification']='not qualified for regional thin-flow timing; hydrostatic bed-step bias'
    # A separate delivery table adds the advisory exclusion without changing raw run records.
    cols=list(dict.fromkeys(k for x in tables for k in x))
    with (R/'results/reduced_delivery_metrics.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(tables)
    mass=max(abs(x['relative_mass_balance_error']) for x in tables) if tables else None
    r2=by.get('2d_ref_60m',{});ss=r2.get('summary',{})
    md='''# 独立一维与二维基线：实际计算与适用域\n\n这两条路线已经运行真实区域地形上的条件释放；它们是自写浅层流有限体积实现，均不是 r.avaflow、RAMMS 或 D-Claw。共同输入由空间组提供，候选源区／路径／口岸点未因此成为事件真值。\n\n## 方程、数值方法和共同条件\n\n求解 `∂t h+div(h u)=0`、`∂t(h u)+div(h u⊗u+g h² I/2)=−g h grad(z)−h a_f`，`a_f=[mu*g*cos(theta)+g*|u|²/(xi*h)] u/|u|`。这里 h 是 Cartesian 图地形上的垂直厚度、速度为水平投影；不包含曲率、主动／被动土压力、冰融化、相间交换、孔压、底床侵蚀或河水夹带。陡坡不是此实现已经验证的适用域。\n\n一阶 Rusanov 通量配合 Audusse 水静力重构及两侧压力修正。运输显式，CFL=.35；摩阻用速度标量隐式二次根收缩，不改变体积。干层只令动量归零，体积保留；任何负深截断的增加体积单列，低于−1e−8m即失败。开边界为零梯度透射，出流和可能的入流逐面计量。没有动能提前停止，均算至1800s。\n\n2D 60m源区257格、925200m²，15m体积13,878,000m³；120m源区67格、964800m²，厚度乘925200/964800保持体积。初速UTM45N东／北均0。5／15／30m及mu=.08/.15/.25、xi=500/1000/2000按OFAT比较；136m挑战来自外部作者重建，实际格网体积125,827,200m³，未强迫等于论文体积或拟合约8分钟。密度2000kg/m³仅为显式均质情景记账，不影响本方程的体积动力学。\n\n1D在P1/P2/P3真实候选折线上插值DEM高程，保留上坡障碍，不强制单调。站距为UTM水平折线长度；首个连续源区段均匀厚度释放，等效恒宽=925200m²/该段长度，使体积与2D完全相同。恒宽不是实测谷宽；1D不能描述横向分流、汇流展宽或脱离指定路径。\n\n## 计算结果\n\n'''
    md+=f"实际执行 {len(runs)} 个区域情景：{sum(x['run_id'].startswith('2d_') for x in tables)} 个2D、{sum(x['run_id'].startswith('1d_') for x in tables)} 个1D。区域质量账相对残差最大 `{mass}`。每个情景的完整记录、首达括号、体积账和缓存哈希分别见 `results/reduced_<run_id>.json`。\n\n"
    md+='| Run | V0 (Mm³) | hmax (m) | u_max any wet (m/s) | Target delay (s) | Status |\n|---|---:|---:|---:|---:|---|\n'
    for row in tables:
        travel='null' if row['travel_time_seconds'] is None else f"{row['travel_time_seconds']:.2f}"
        md+=f"| {row['run_id']} | {row['initial_volume_m3']/1e6:.3f} | {row['max_depth_m']:.2f} | {row['maximum_speed_any_wet_m_s']:.2f} | {travel} | {row['arrival_status']} |\n"
    md+='\n最大速度表格按任何h>1e−9m湿格统计，薄前缘可能影响该值；不将其当实测峰速。图中的hmax是全时最大流深；h_final只是1800s残余材料，只有另报速度<.1m/s体积才可称近静止残余。footprint为hmax>=.1m，并非泥石流真实影响范围。\n\n到达定义为代表口岸点100m内格心或1D路径格心第一次h>=.1m的求解器步；保留前后步括号，保存的过程图另以30s间隔。未达为1800s内未达，不能解释为永久不到达；数值失败、目标缺失、出域也保留。时间从条件成规模释放起算，`initiation_to_release_delay_seconds=null`；任何传播时延均不能替代源区首次机械启动时刻。\n\n## 数值反证及采用建议\n\n'
    if bench:
        md+=f"已执行6组数值基准（共13个细分运行）：静水含干边界、Ritter干床溃坝网格／步长、二维径向干前缘、开放边界体积账、常坡网格响应，以及独立刚体Voellmy解析ODE。静水最大速度约6e−15m/s；Ritter深度L1误差5→2.5→1.25m网格为0.00695→0.00484→0.00315m。全体`pass`只表示预登记守恒、对称、正性与误差下降性质，**不代表区域精度合格**。\n\n"
        md+=f"关键反证：10m薄层、tan(theta)=.2、t=5s，Cartesian定厚解析速度2.584m/s；20／10／5m格网仅0.633／1.610／2.097m/s，速度相对误差{relative[0]:.3f}/{relative[1]:.3f}/{relative[2]:.3f}。60m区域参考源区约{r2.get('source_bedstep_gt_thickness_fraction',0)*100:.2f}%的中心差分一格落差代理大于15m；以真实四邻面最大高差计算则为{r2.get('source_max_adjacent_face_jump_gt_initial_h_fraction',0)*100:.2f}%。故强烈数值阻滞并非小范围问题；1D使用同一重构，也受类似影响。`regional_thin_flow_accuracy_qualified=false`，本两条路线均`include_in_arrival_envelope=false`，仅保留为离散／参数敏感性和复杂模型比较的对照。\n\n"
    md+='两格网和减半CFL的实算差异见`reduced_comparisons.json`；两格网不构成渐近收敛证明。若官方复杂模型传播更远，须先区分其数值处理与物理新增项；不能把这个自写方法的缺陷直接算作多相／孔压收益。没有本地区域独立传播真值，校准数和独立事件验证数均为0；合成基准不计作事件。所有区域结果属于conditional_scenario，不产生概率、95%区间或覆盖率。\n\n## 文件与复跑\n\n'
    md+='`config/reduced_protocol.json`及amendment01在区域求解前登记；`config/reduced_environment.lock/json`固定局部Numba运行时，原44包venv未改。大型过程场在专有cache，run JSON逐文件bytes/hash绑定。源码为五个reduced_*.py（含交付检查与清单生成）。先建立并锁定局部环境、以pth桥接原科学包（原环境路径见环境JSON），随后从本worktree执行：\n\n```sh\nNUMBA_CACHE_DIR=/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/numba_cache /Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/venv/bin/python track_b/research/q4/round3/scripts/reduced_benchmarks.py\nNUMBA_CACHE_DIR=/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/numba_cache /Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/venv/bin/python track_b/research/q4/round3/scripts/reduced_region.py --mode all\n/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/venv/bin/python track_b/research/q4/round3/scripts/reduced_report.py\n```\n\n数值方法来源：[Audusse et al. 2004](https://epubs.siam.org/doi/abs/10.1137/S1064827503431090)、[水静力重构限制原文](https://arxiv.org/abs/1206.4986)；摩阻项参考[RAMMS官方方程说明](https://ramms.ch/ramms-avalanche/friction-parameters/)。参数范围由共同协议指定，未从RAMMS校准表迁移为本地区域真值。实际下载元数据／源字节哈希在reduced_protocol的sources登记；可读范围以该记录为准。\n'
    md+='\n新增OSM五个候选对象按预登记protocol_v2全量后处理，不挑选最快点：`results/reduced_osm_target_arrivals_v2.csv`保留每个模型×五个对象。使用已存30s场，不重算；首次达阈值与前一个未达输出构成括号，不能标成求解器步精度。原paper_port_symbol主目标和结果完全保留，设施／旧桥／临时桥对象身份不合并。\n'
    post=R/'results/reduced_osm_target_postprocess_v2.json'
    if post.exists():
        detail=json.loads(post.read_text());md+=f"\n新增对象共{detail['rows']}行，状态计数{detail['status_counts']}。1D路径有限终点及格心与新对象100m圈可能不相交，missing表示空间支持缺失；不能改写为未到达、外推或取最近格替代。\n"
    (R/'REDUCED_MODELS.md').write_text(md)
    if bench:
        fig,axes=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
        rr=next(x for x in bench['cases'] if x['case_id']=='ritter_dry_bed_grid_and_cfl')['runs'][:3]
        axes[0].loglog([x['dx_m'] for x in rr],[x['l1_depth_error_m'] for x in rr],'o-',label='Ritter dry bed');axes[0].set_xlabel('Grid spacing (m)');axes[0].set_ylabel('Mean L1 depth error (m)');axes[0].set_title('Refinement improves dam-break error');axes[0].grid(alpha=.3)
        rr=next(x for x in bench['cases'] if x['case_id']=='uniform_incline_grid_response')['runs']
        axes[1].plot([x['dx_m'] for x in rr],[x['actual_centre_speed_m_s'] for x in rr],'o-',label='FV computed');axes[1].axhline(rr[0]['cartesian_graph_constant_depth_exact_m_s'],color='black',linestyle='--',label='constant-depth exact');axes[1].set_xlabel('Grid spacing (m)');axes[1].set_ylabel('Speed at 5 s (m/s)');axes[1].set_title('Large thin-flow acceleration bias');axes[1].legend(fontsize=8);axes[1].grid(alpha=.3)
        fig.suptitle('Numerical benchmarks — not independent event validation');fig.savefig(R/'figures/reduced_numerical_checks.png',dpi=180);plt.close(fig)
    files=[file_record(p,'reduced model figure; awaiting actual visual inspection') for p in sorted((R/'figures').glob('reduced_*.png'))]
    write_json(R/'results/reduced_figure_index.json',{'figures':files,'visual_review_status':'pending actual open'})
    print(json.dumps({'runs':len(runs),'figures':len(files),'arrival_statuses':{k:sum(x['arrival_status']==k for x in tables) for k in sorted(set(x['arrival_status'] for x in tables))}}))

if __name__=='__main__':main()
