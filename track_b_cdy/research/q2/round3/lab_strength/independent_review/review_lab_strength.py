#!/usr/bin/env python3
"""Read-only source/fit audit with independent OOXML and linear algebra.
Only writes under lab_strength/independent_review. Does not import model code.
"""
import argparse,csv,hashlib,io,json,math,sys,zipfile
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
from xml.etree import ElementTree as E
import numpy as np
ROOT=Path('/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2')
BASE=ROOT/'track_b/research/q2/round3/lab_strength'
OUT=BASE/'independent_review'
ARCHIVE=ROOT/'track_b/research/q2/round3/sources/strength/mamot2018_supplement.zip'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
MEMBERS=['Supplement/data_experiments.xlsx','Supplement/data_frictioncoeff_cohesion_Fig. 8.xlsx']
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def workbook(b):
    """Parse stored source XML, with no spreadsheet library/author code."""
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            for si in E.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',NS): strings.append(''.join(t.text or '' for t in si.findall('.//m:t',NS)))
        relroot=E.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        rels={r.attrib['Id']:r.attrib['Target'] for r in relroot}
        root=E.fromstring(z.read('xl/workbook.xml'));sheets=[]
        for ss in root.findall('m:sheets/m:sheet',NS):
            target=rels[ss.attrib['{'+NS['r']+'}id']]
            path=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            tree=E.fromstring(z.read(path));cells={};formulas=[]
            for c in tree.findall('.//m:sheetData/m:row/m:c',NS):
                ref=c.attrib['r'];typ=c.attrib.get('t','n');v=c.find('m:v',NS);f=c.find('m:f',NS)
                if f is not None:formulas.append({'cell':ref,'formula':f.text})
                if typ=='s':value=strings[int(v.text)] if v is not None else None
                elif typ=='inlineStr':value=''.join(t.text or '' for t in c.findall('.//m:t',NS))
                elif v is not None:
                    value=float(v.text) if typ in ('n','') else v.text
                else:value=None
                if value is not None:cells[ref]={'value':value,'source_type':typ}
            sheets.append({'name':ss.attrib['name'],'state':ss.attrib.get('state','visible'),'dimension':tree.find('m:dimension',NS).attrib.get('ref') if tree.find('m:dimension',NS) is not None else None,'cells':cells,'formulas':formulas})
        return sheets

def source_records():
    with zipfile.ZipFile(ARCHIVE) as z:
        inventory=[{'member':x.filename,'bytes':x.file_size,'crc32':x.CRC,'actual_data_read':x.filename in MEMBERS} for x in z.infolist()]
        books={name:{'bytes':len(z.read(name)),'sha256':sha(z.read(name)),'sheets':workbook(z.read(name))} for name in MEMBERS}
    cells=books[MEMBERS[0]]['sheets'][0]['cells'];records=[]
    columns=[chr(65+i) for i in range(16)]
    headers={c:cells[c+'1']['value'] for c in columns}
    numcols=['C','D','E','F','G','H','I','J','K','L','M','O','P'];numeric_strings=[]
    for r in range(2,143):
        row={c:cells[c+str(r)]['value'] for c in columns}
        for c in numcols:
            if isinstance(row[c],str):numeric_strings.append({'cell':c+str(r),'raw_value':row[c],'numeric_value':float(row[c])})
            row[c]=float(row[c])
        row['source_excel_row']=r;records.append(row)
    return records,books,inventory,headers,numeric_strings

def audit():
    rows,books,inventory,headers,strings=source_records()
    counts=Counter((r['D'],r['F']) for r in rows);spec=Counter(r['B'] for r in rows)
    subsets={'lowfull':[r for r in rows if r['F']<=400], 'eqdomain':[r for r in rows if r['F']<=400 and -8<=r['D']<=-.5], 'warmlow':[r for r in rows if r['F']<=400 and -4<=r['D']<=-.5], 'warmall':[r for r in rows if -4<=r['D']<=-.5]}
    review={'version':'q2r3-lab-strength-independent-raw-v1','generated_at_utc':datetime.now(timezone.utc).isoformat(),'archive_path':str(ARCHIVE.relative_to(ROOT)),'archive_sha256':sha(ARCHIVE.read_bytes()),'member_inventory':inventory,'actual_read_scope':MEMBERS,'workbooks':[{'member':name,'bytes':b['bytes'],'sha256':b['sha256'],'sheets':[{'name':s['name'],'state':s['state'],'dimension':s['dimension'],'nonempty_cells':len(s['cells']),'nonempty_rows':len(set(''.join(filter(str.isdigit,c)) for c in s['cells'])),'formula_count':len(s['formulas'])} for s in b['sheets']]} for name,b in books.items()],'headers':headers,'numeric_text_coercions':strings,'observation_n':len(rows),'unique_experiment_specimen_ids':len(set((r['A'],r['B']) for r in rows)),'specimen_label_counts':dict(sorted(spec.items())),'design_cell_counts':[{'temperature_class_c':t,'stress_class_kpa':stress,'n':n} for (t,stress),n in sorted(counts.items())],'subset_counts':{name:len(rr) for name,rr in subsets.items()},'actual_sigma_range_in_400_class_kpa':[min(r['G'] for r in rows if r['F']==400),max(r['G'] for r in rows if r['F']==400)],'actual_temperature_range_in_minus0p5_class_c':[min(r['E'] for r in rows if r['D']==-.5),max(r['E'] for r in rows if r['D']==-.5)],'actual_stress_le400_would_exclude_400_target_n':sum(r['F']==400 and r['G']>400 for r in rows),'outcome_material':'Laboratory ice-filled limestone-joint peak shear; external transfer only. Figure8 is derived from same tests; not extra observations.','grouping_recommendation':{'primary_grouped_evaluation':['temperature class','normal stress class'],'correlation_sensitivity':'Treat specimen label across experiment cells as a possibly reused physical-pair cluster, conservatively, with leave-label-out and cluster-resample sensitivity. Manuscript2.3 retains specimen-pair arrangement and orientation, but explicit label-to-physical-pair map unavailable; not proof of8 independent physical specimens.','cluster_count':len(spec),'uncertainty_limit':'Only8 label clusters; small-cluster bootstrap quantiles do not establish95% coverage, and row-level covariance/stratified bootstrap omit possible pair dependence.'},'exclusions':['Do not pool Figure8 derived coefficients with141 raw specimens as extra training points.','Do not subset stress-class400 using actual sigma<=400.','Do not use floating measured temperature as a grouping ID; all nominal-class repeats stay in held-out group.','No local event/time/scenario targets used for fitting/model selection.','Failure type, rupture time and AE onset are post-failure responses: diagnostic strata only, not predictor features.'],'independent_local_events':0,'data_role':'external_lab_source_audit'}
    dump(OUT/'raw_inventory_audit.json',review)
    return rows,review

MODELS=['author_eq6','mc_linear','mc_temperature_quadratic','mc_stress_quadratic','mc_stress_hinge_400']
def design(rows,model):
    t=np.array([r['E'] for r in rows]);s=np.array([r['G'] for r in rows])/1000.
    columns=[np.ones(len(rows)),t,s,t*s]
    if model=='mc_temperature_quadratic':columns.extend([t*t,s*t*t])
    if model=='mc_stress_quadratic':columns.extend([s*s,s*s*t])
    if model=='mc_stress_hinge_400':
        h=np.maximum(s-.4,0);columns.extend([h,h*t])
    return np.column_stack(columns)
def fit(rows,model,weights=None):
    y=np.array([r['L'] for r in rows]);X=design(rows,model)
    if model=='author_eq6':return {'model':model,'coefficient':np.array([53.3,-73.5,420.,-210.]),'rank':0,'p':0,'fixed_reference':True}
    w=np.ones(len(rows)) if weights is None else np.asarray(weights)
    xw=X*np.sqrt(w[:,None]);yw=y*np.sqrt(w)
    coef,_,rank,sv=np.linalg.lstsq(xw,yw,rcond=None)
    output={'model':model,'coefficient':coef,'rank':int(rank),'p':X.shape[1],'condition':float(sv.max()/sv.min()) if sv.min()>0 else None,'fixed_reference':False}
    if rank<X.shape[1]:return output
    residual=yw-xw@coef;bread=np.linalg.inv(xw.T@xw);h=np.sum((xw@bread)*xw,axis=1)
    scores=xw*(residual/(1-h))[:,None]
    hc3=bread@scores.T@scores@bread
    labels=np.array([r['B'] for r in rows]);clusters=sorted(set(labels));meat=np.zeros((X.shape[1],X.shape[1]))
    for label in clusters:
        score=xw[labels==label].T@residual[labels==label];meat+=np.outer(score,score)
    cr1=len(clusters)/(len(clusters)-1)*(len(rows)-1)/(len(rows)-X.shape[1])*bread@meat@bread
    output.update({'hc3_covariance':hc3,'cluster_cr1_covariance':cr1,'cluster_n':len(clusters)})
    return output
def predict(rows,fitted):return design(rows,fitted['model'])@fitted['coefficient']
def subsets_of(rows):
    return {'lowfull':[r for r in rows if r['F']<=400], 'eqdomain':[r for r in rows if r['F']<=400 and -8<=r['D']<=-.5], 'warmlow':[r for r in rows if r['F']<=400 and -4<=r['D']<=-.5], 'warmall':[r for r in rows if -4<=r['D']<=-.5]}
def numeric_json(x):
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,dict):return {k:numeric_json(v) for k,v in x.items()}
    if isinstance(x,list):return [numeric_json(v) for v in x]
    return x
def references(rows):
    fits=[];folds=[]
    for subset,rr in subsets_of(rows).items():
        for model in MODELS:
            f=fit(rr,model);y=np.array([r['L'] for r in rr]);yh=predict(rr,f)
            fits.append(numeric_json({'subset':subset,'n':len(rr),'train_rmse_kpa':float(np.sqrt(np.mean((yh-y)**2))),'train_mae_kpa':float(np.mean(abs(yh-y))),**f,'source_rows':[r['source_excel_row'] for r in rr],'predictions':yh,'coefficient_units':'intercept kPa; T degreeC; sigma scaled toMPa; hinge breakpoint0.4MPa'}))
            if model=='author_eq6':continue # Reuses original paper data: calibration reference only, not a held-out model.
            for grouping,key in [('temperature','D'),('stress','F'),('specimen','B')]:
                for group in sorted(set(r[key] for r in rr)):
                    train=[r for r in rr if r[key]!=group];test=[r for r in rr if r[key]==group]
                    ff=fit(train,model);fullrank=ff['fixed_reference'] or ff['rank']==ff['p']
                    yy=np.array([r['L'] for r in test]);pred=predict(test,ff) if fullrank else None
                    folds.append({'subset':subset,'model':model,'grouping':grouping,'group':group,'train_n':len(train),'test_n':len(test),'rank':ff['rank'],'p':ff['p'],'identifiable_algebraically':fullrank,'test_source_rows':[r['source_excel_row'] for r in test],'train_source_rows':[r['source_excel_row'] for r in train],'prediction':None if pred is None else pred.tolist(),'rmse_kpa':None if pred is None else float(np.sqrt(np.mean((pred-yy)**2))),'mae_kpa':None if pred is None else float(np.mean(abs(pred-yy))),'bias_kpa':None if pred is None else float(np.mean(pred-yy))})
    result={'version':'q2-lab-independent-linear-algebra-reference-v1','data_role':'external_lab_internal_validation','independent_local_events':0,'fit_method':'Independent uncentered-in-T design with sigma inMPa; np.linalg.lstsq; no parent model import. HC3 direct leverage/sandwich; clusterCR1 on full specimen labels.','fits':fits,'folds':folds}
    dump(OUT/'independent_fit_reference.json',result);return result

def read_csv(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
DOMAIN_MAP={'low_full':'lowfull','low_eq6_temperature':'eqdomain','warm_low':'warmlow','warm_all':'warmall'}
def scale_to_parent(model):
    base=[1.,.2,2.5,.5]
    if model=='mc_temperature_quadratic':base.extend([.04,.1])
    if model=='mc_stress_quadratic':base.extend([6.25,1.25])
    if model=='mc_stress_hinge_400':base.extend([2.5,.5])
    return np.array(base)
def review(rows):
    """Independent re-fit and resampling; never import parent competition code."""
    checks=[]
    def ck(name,value,**kw):
        checks.append({'check':name,'passed':bool(value),**kw})
        if not value:raise AssertionError(name+': '+str(kw))
    canonical_path=BASE/'audit/results/observations.csv';canonical=read_csv(canonical_path)
    schema=json.loads((BASE/'audit/results/schema.json').read_text())
    expected_by_row={r['source_excel_row']:r for r in rows};max_source_error=0.
    for r in canonical:
        raw=expected_by_row[int(r['source_row'])]
        for key,meta in schema['observations']['raw_column_map'].items():
            v=raw[meta['column']]
            if isinstance(v,str):ck_value=r[key]==v
            else:
                e=abs(float(r[key])-v);max_source_error=max(max_source_error,e);ck_value=e<1e-10
            if not ck_value:raise AssertionError('canonical source mismatch '+str((r['observation_id'],key,v,r[key])))
    ck('all141_canonical_rows_times16_fields_match_independent_source_XML',len(canonical)==141,max_numeric_abs_error=max_source_error)
    ids=[r['observation_id'] for r in canonical]
    ck('source_observation_id_unique_and_ordered',ids==[f"mamot2018-test-r{r['source_excel_row']:03d}" for r in rows] and len(set(ids))==141)
    _,books,*_=source_records();cells=books[MEMBERS[1]]['sheets'][0]['cells'];coeff=read_csv(BASE/'audit/results/coefficient_strata.csv');nc=0
    for r in coeff:
        for field,cell in json.loads(r['field_cells_json']).items():
            v=cells[cell]['value'];assert abs(float(r[field])-float(v))<1e-10;nc+=1
    ck('all14_derived_coefficient_strata_match_XML_cells',len(coeff)==14,source_numeric_fields_checked=nc)
    ck('canonical_all_external_laboratory_no_local_event_count',all(r['evaluation_stratum']=='external_transfer' and r['independent_landslide_events']=='0' for r in canonical))
    model_dir=BASE/'model';res=model_dir/'results'
    config=json.loads((res/'run_config.json').read_text());config_hash=sha((res/'run_config.json').read_bytes())
    ck('fit_input_and_protocol_hashes_match',config['data_sha256']==sha(canonical_path.read_bytes()) and config['protocol_sha256']==sha((BASE/'PROTOCOL.md').read_bytes()) and config['protocol_amendment_sha256']==sha((BASE/'PROTOCOL_AMENDMENT.md').read_bytes()))
    ck('all_predeclared_models_and_domains_retained',set(config['models'])==set(MODELS[1:]) and config['independent_local_events']==0)
    sets={domain:subsets_of(rows)[key] for domain,key in DOMAIN_MAP.items()}
    allfits={};calibration=read_csv(res/'calibration_residuals.csv');bycal={(r['domain'],r['model'],r['weight'],r['observation_id']):r for r in calibration}
    max_fit_error=0.;max_cov_relative=0.;n_prediction=0;rank_total=0
    covs=json.loads((res/'covariances.json').read_text())
    cov_lookup={(r['domain'],r['model'],r['weight'],r['method']):np.array(r['matrix_kpa_squared']) for r in covs}
    for domain,rr in sets.items():
        for model in MODELS:
            policies=['fixed_published_reference'] if model=='author_eq6' else ['row_ols','cell_equal']
            for policy in policies:
                counts=Counter((r['D'],r['F']) for r in rr)
                w=np.array([1/counts[(r['D'],r['F'])] for r in rr]);w=w/w.mean()
                f=fit(rr,model,w if policy=='cell_equal' else None);allfits[(domain,model,policy)]=f
                expected=predict(rr,f)
                for row,yp in zip(rr,expected):
                    oid=f"mamot2018-test-r{row['source_excel_row']:03d}";out=bycal[(domain,model,policy,oid)]
                    max_fit_error=max(max_fit_error,abs(float(out['predicted_kpa'])-yp));n_prediction+=1
                if model=='author_eq6':continue
                factor=scale_to_parent(model)
                for own,parent in [('hc3_covariance','hc3'),('cluster_cr1_covariance','label_cr1')]:
                    expected_cov=f[own]/factor[:,None]/factor[None,:]
                    published=cov_lookup[(domain,model,policy,parent)]
                    relative=float(np.max(abs(published-expected_cov))/max(float(np.max(abs(expected_cov))),1.))
                    max_cov_relative=max(max_cov_relative,relative)
    ck('all_OLS_and_cell_equal_calibration_predictions_recomputed',max_fit_error<2e-7,max_abs_error_kpa=max_fit_error,predictions_checked=n_prediction,fit_groups=len(allfits))
    ck('all_HC3_and_label_CR1_covariance_matrices_recomputed',max_cov_relative<2e-8,max_matrix_relative_error=max_cov_relative,matrix_n=len(covs),basis_transform='parentX=ownX*diag(1,.2,2.5,.5,...); parentCov=ownCov/(scale_i*scale_j)')
    folds=read_csv(res/'holdout_folds.csv');preds=read_csv(res/'holdout_predictions.csv');pmap={(r['domain'],r['model'],r['weight'],r['holdout_scheme'],r['heldout_group'],r['observation_id']):r for r in preds}
    ck('fixed_published_author_reference_excluded_from_CV',not any(r['model']=='author_eq6' for r in folds+preds))
    max_cv_error=0.;max_metric_error=0.;rank_deficient=0;pred_count=0;group_keys={'temperature':'D','normal_stress':'F','specimen_label_assumed':'B'}
    fold_by_group=defaultdict(list)
    for fold in folds:
        domain,model,policy,scheme=fold['domain'],fold['model'],fold['weight'],fold['holdout_scheme'];key=group_keys[scheme]
        held=fold['heldout_group'] if key=='B' else float(fold['heldout_group']);rr=sets[domain]
        tr=[r for r in rr if r[key]!=held];te=[r for r in rr if r[key]==held]
        counts=Counter((r['D'],r['F']) for r in tr);w=np.array([1/counts[(r['D'],r['F'])] for r in tr]);w/=w.mean()
        ff=fit(tr,model,w if policy=='cell_equal' else None)
        ck_shape=len(tr)==int(fold['training_n']) and len(te)==int(fold['test_n']) and ff['rank']==int(fold['rank'])
        if not ck_shape:raise AssertionError('fold train/test/rank mismatch '+str((domain,model,policy,scheme,held)))
        testids=[f"mamot2018-test-r{r['source_excel_row']:03d}" for r in te]
        assert sha('\n'.join(testids).encode())==fold['test_ids_sha256']
        assert set(r['source_excel_row'] for r in tr).isdisjoint(r['source_excel_row'] for r in te)
        outkey=(domain,model,policy,scheme,fold['heldout_group'])
        if ff['rank']<ff['p']:
            rank_deficient+=1;assert fold['status']=='rank_deficient_no_prediction'
            assert not any((*outkey,oid) in pmap for oid in testids);continue
        assert fold['status']=='full_rank'
        yp=predict(te,ff);yy=np.array([r['L'] for r in te]);error=yp-yy
        for oid,expected in zip(testids,yp):
            out=pmap[(*outkey,oid)];max_cv_error=max(max_cv_error,abs(float(out['predicted_kpa'])-expected));pred_count+=1
        values={'rmse_kpa':float(np.sqrt(np.mean(error**2))),'mae_kpa':float(np.mean(abs(error))),'bias_kpa':float(np.mean(error))}
        for k,v in values.items():max_metric_error=max(max_metric_error,abs(float(fold[k])-v))
        fold_by_group[(domain,model,policy,scheme)].append(values)
    ck('every_group_holdout_refit_uses_disjoint_class_or_label_sets',len(folds)==576,fold_n=len(folds),prediction_n=pred_count,rank_deficient_no_prediction_n=rank_deficient)
    ck('all_group_holdout_predictions_and_metrics_recomputed',max_cv_error<2e-6 and max_metric_error<2e-6 and pred_count==len(preds),max_abs_prediction_error_kpa=max_cv_error,max_abs_metric_error_kpa=max_metric_error,all_exported_predictions_accounted=(pred_count==len(preds)))
    summary=read_csv(res/'holdout_summary.csv');macroerr=0.
    for r in summary:
        key=(r['domain'],r['model'],r['weight'],r['holdout_scheme']);ff=fold_by_group[key]
        macro=math.sqrt(sum(v['rmse_kpa']**2 for v in ff)/len(ff));macroerr=max(macroerr,abs(macro-float(r['group_macro_rmse_kpa'])))
    ck('equal_group_RMSE_is_root_mean_fold_MSE',macroerr<2e-6,max_abs_error_kpa=macroerr,meaning='sqrt(mean(fold_RMSE**2)), not arithmetic mean of fold RMSE; both are different valid summaries and this one must be named explicitly')
    # Exact RNG replay, but an independently parsed source and differently scaled basis.
    rng=np.random.default_rng(config['seed']);stored=np.load(res/'bootstrap_coefficient_draws.npz');boot_summary=json.loads((res/'bootstrap_summary.json').read_text())
    bsum={(r['domain'],r['model'],r['scheme']):r for r in boot_summary};max_draw_relative=0.;max_quantile_relative=0.;attempts=0;failures=0
    for domain,rr in sets.items():
        labels=np.array([r['B'] for r in rr]);unique=np.array(sorted(set(labels)));cells=defaultdict(list)
        for i,row in enumerate(rr):cells[(row['D'],row['F'])].append(i)
        for model in MODELS[1:]:
            x=design(rr,model);y=np.array([r['L'] for r in rr]);factor=scale_to_parent(model)
            for scheme in ['within_cell_independent_tests','specimen_label_blocks_assumed']:
                draws=[];failed=0
                for repeat in range(config['bootstrap_repetitions']):
                    attempts+=1
                    if scheme=='within_cell_independent_tests':
                        indices=np.concatenate([rng.choice(np.array(cells[k]),len(cells[k]),replace=True) for k in sorted(cells)])
                    else:
                        selected=rng.choice(unique,len(unique),replace=True)
                        indices=np.concatenate([np.flatnonzero(labels==label) for label in selected])
                    beta,_,rank,_=np.linalg.lstsq(x[indices],y[indices],rcond=1e-12)
                    if rank<x.shape[1] or not np.isfinite(beta).all():failed+=1
                    else:draws.append(beta/factor)
                draws=np.array(draws);published=stored[domain+'__'+model+'__'+scheme];info=bsum[(domain,model,scheme)]
                assert len(draws)==len(published)==info['usable_draws'] and failed==info['rank_deficient_or_nonfinite_draws']
                relative=float(np.max(abs(draws-published))/max(1.,float(np.max(abs(published)))))
                max_draw_relative=max(max_draw_relative,relative);failures+=failed
                q=np.quantile(draws,[.025,.5,.975],axis=0);expected=np.array(info['coefficient_percentiles_2p5_50_97p5_kpa'])
                max_quantile_relative=max(max_quantile_relative,float(np.max(abs(q-expected))/max(1.,float(np.max(abs(expected))))))
    ck('all_32000_bootstrap_draws_and_failed_draw_accounting_recomputed',attempts==32000 and max_draw_relative<2e-7,attempts=attempts,failed_rank_or_nonfinite=failures,max_coefficient_array_relative_error=max_draw_relative,scope='Same declared RNG stream; independent source XML, alternate basis, explicit cluster row duplication rather than parent multiplicity weights.')
    ck('all_conditional_bootstrap_parameter_percentiles_recomputed',max_quantile_relative<2e-7,max_relative_error=max_quantile_relative,statistical_limit='Percentile sensitivity under either conditionally independent-test or assumed-label-block resampling. No coverage certification or local-event probability.')
    ck('final_config_binds_actual_model_code_bytes',config['code_sha256']==sha((model_dir/'competition.py').read_bytes()))
    # Strict domain count was a review finding; check final repaired output rather than assume it.
    domains=json.loads((res/'domains.json').read_text());strict_errors=[];tolerance_errors=[];domain_counts=[]
    for d in domains:
        n=sum(not(-8<=r['E']<=-.5 and 100<=r['G']<=400) for r in sets[d['domain']])
        tolerant=sum(not(-8.1<=r['E']<=-.4 and 100<=r['G']<=400) for r in sets[d['domain']])
        if d['actual_outside_original_eq6_strict_continuous_domain']!=n:strict_errors.append((d['domain'],n,d['actual_outside_original_eq6_strict_continuous_domain']))
        if d['actual_outside_eq6_with_explicit_temperature_tolerance_0p1c']!=tolerant:tolerance_errors.append(d['domain'])
        domain_counts.append({'domain':d['domain'],'n':len(sets[d['domain']]),'strict_actual_outside_n':n,'explicit_temperature_tolerance_0p1c_outside_n':tolerant})
    ck('strict_original_continuous_domain_counts_match_raw_values',not strict_errors,mismatches=strict_errors,counts=domain_counts)
    ck('explicit_point1c_temperature_tolerance_diagnostic_separately_named_and_recomputed',not tolerance_errors,mismatches=tolerance_errors,scope='Temperature sensitivity only; normal stress domain remains100..400kPa; never changes fit/class membership.')
    report={'version':'q2r3-lab-strength-independent-review-v1','generated_at_utc':datetime.now(timezone.utc).isoformat(),'outcome':'pass','checks':checks,'independent_source_parser':'stdlib ZIP/XML, no openpyxl or canonical/model code imported','model_calculation_reference':'Different T/sigma basis and independent least-squares/covariance/explicit bootstrap loops; no parent function calls.','code_review_scope':'Full competition.py read; fixed source DATA is canonical external laboratory only. No event/model-outcome/time-target data read. Author Eq6 reuse excluded from CV.','mathematical_and_statistical_limits':['Seven prepared rock-pairs stated by manuscript but eight source labels including single spec8; physical UID map unresolved. Label blocks are a conservative correlation sensitivity, not proof of eight independent physical specimens.','HC3 assumes working row independence; labelCR1/label bootstrap assume cross-condition repeated labels are meaningful correlation blocks. Small clusters and singletons limit uncertainty interpretation.','No independent local landslide events; fitting and held-out internal laboratory tests cannot validate local causality/forecast coverage.','Class-based subset membership and continuous measured predictor domain separated. High-stress extrapolation flagged even when jitter yields full algebraic rank.'],'findings_resolved':[{'issue':'Parent initial domain diagnostic silently widened temperature interval to[-8.1,-.4].','resolution':'Reported before final publication; parent repairs strict[-8,-.5] count and separately labels any explicit tolerance sensitivity. Fit/cross-validation memberships and fitted predictions unaffected.'}],'independent_local_events':0,'data_role':'external_lab_internal_numerical_review','bindings':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in [ARCHIVE,ROOT/'track_b/research/q2/round3/sources/strength/mamot2018_article_extracted.txt',canonical_path,BASE/'PROTOCOL.md',BASE/'PROTOCOL_AMENDMENT.md',model_dir/'competition.py',res/'run_config.json',res/'run_summary.json',res/'fits.csv',res/'calibration_residuals.csv',res/'covariances.json',res/'holdout_folds.csv',res/'holdout_predictions.csv',res/'bootstrap_summary.json',res/'bootstrap_coefficient_draws.npz',res/'domains.json']],'command':'track_b/.venv/bin/python track_b/research/q2/round3/lab_strength/independent_review/review_lab_strength.py --review','writes':'own independent_review directory only'}
    dump(OUT/'review.json',report);print(json.dumps({'checks':len(checks),'max_fit_error_kpa':max_fit_error,'max_cv_error_kpa':max_cv_error,'bootstrap_attempts':attempts,'bootstrap_failed':failures,'max_bootstrap_relative_error':max_draw_relative},indent=2))

def main():
    if Path.cwd().resolve()!=ROOT:raise RuntimeError('explicit root required')
    OUT.mkdir(parents=True,exist_ok=True)
    ap=argparse.ArgumentParser();ap.add_argument('--audit',action='store_true');ap.add_argument('--reference',action='store_true');ap.add_argument('--review',action='store_true');args=ap.parse_args()
    rows,r=audit();print(json.dumps({'source_n':len(rows),'subsets':r['subset_counts'],'specimen_labels':r['specimen_label_counts'],'numeric_text':r['numeric_text_coercions'],'wrong_stress_filter_excluded':r['actual_stress_le400_would_exclude_400_target_n']},indent=2))
    if args.reference:
        result=references(rows);print('independent_fits',len(result['fits']),'group_heldout_folds',len(result['folds']))
    if args.review:
        references(rows);review(rows)
if __name__=='__main__':main()
