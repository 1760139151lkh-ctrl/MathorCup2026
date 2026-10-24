"""Closed-form source reconstruction probe; never edits canonical audit or fits.

Read-only original XLSX XML verifies values/headers against the canonical audit.
Coefficient source '_error' stays untyped, even when numerically matching OLS SE.
"""
from pathlib import Path
import hashlib
import io
import json
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
LAB=HERE.parent
BASE=LAB.parent
ROOT=BASE.parents[3]
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def cells_from_xlsx(blob,index):
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        ss=ET.fromstring(z.read('xl/sharedStrings.xml'))
        strings=[''.join(t.text or '' for t in si.findall('.//s:t',NS)) for si in ss.findall('s:si',NS)]
        sheet=ET.fromstring(z.read(f'xl/worksheets/sheet{index}.xml'))
        cells={}
        for c in sheet.findall('.//s:sheetData/s:row/s:c',NS):
            v=c.find('s:v',NS)
            if v is None:continue
            cells[c.attrib['r']]=strings[int(v.text)] if c.attrib.get('t')=='s' else v.text
        return cells


def number(value):
    return float(str(value).strip().replace(',','.').replace('−','-'))


def closed_fit(x,y,w=None):
    x,y=np.asarray(x,float),np.asarray(y,float)
    w=np.ones(len(x)) if w is None else np.asarray(w,float)
    xb=np.sum(w*x)/np.sum(w);yb=np.sum(w*y)/np.sum(w)
    sxx=np.sum(w*(x-xb)**2)
    slope=np.sum(w*(x-xb)*(y-yb))/sxx;intercept=yb-slope*xb
    sigma2=np.sum(w*(y-intercept-slope*x)**2)/(len(x)-2)
    return dict(intercept=float(intercept),slope=float(slope),
                intercept_ols_se=float(np.sqrt(sigma2*(1/np.sum(w)+xb*xb/sxx))),
                slope_ols_se=float(np.sqrt(sigma2/sxx)),n_points=len(x))


def main():
    assert str(ROOT)=='/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2' and Path.cwd().resolve()==ROOT
    obs_path=LAB/'audit/results/observations.csv';summary_path=LAB/'audit/results/coefficient_strata.csv'
    obs=pd.read_csv(obs_path);summary=pd.read_csv(summary_path)
    archive=BASE/'sources/strength/mamot2018_supplement.zip'
    with zipfile.ZipFile(archive) as z:
        raw=z.read('Supplement/data_experiments.xlsx');coef=z.read('Supplement/data_frictioncoeff_cohesion_Fig. 8.xlsx')
    rc=cells_from_xlsx(raw,1);coeffcells={f'Sheet{i}':cells_from_xlsx(coef,i) for i in [1,2]}
    fields={'temperature_target_c':'D','temperature_at_failure_c':'E','normal_stress_target_kpa':'F',
            'normal_stress_at_failure_kpa':'G','peak_shear_kpa':'L'}
    max_raw_delta=0.
    for _,row in obs.iterrows():
        for field,col in fields.items():
            delta=abs(number(rc[f'{col}{int(row.source_row)}'])-float(row[field]))
            assert delta<1e-10
            max_raw_delta=max(max_raw_delta,delta)
    for _,row in summary.iterrows():
        for field,cell in json.loads(row.field_cells_json).items():
            assert abs(number(coeffcells[row.sheet][cell])-float(row[field]))<1e-10
    records=[]
    for _,source in summary.iterrows():
        upper=source.normal_stress_target_max_kpa
        g=obs[(obs.normal_stress_target_kpa<=upper)&(obs.temperature_target_c==source.temperature_target_c)]
        cell=g.groupby('normal_stress_target_kpa')[['normal_stress_at_failure_kpa','peak_shear_kpa']].mean()
        variance=g.groupby('normal_stress_target_kpa').normal_stress_at_failure_kpa.var(ddof=1)
        for method in ['individual_tests_ols','stress_cell_means_ols','stress_cell_means_inverse_sigma_variance_wls']:
            row=dict(block=source.nominal_stress_group,temperature_target_c=float(source.temperature_target_c),method=method,n_tests=len(g))
            if method.endswith('_wls') and (variance.isna().any() or (variance<=0).any()):
                row.update(status='unavailable_singleton_or_zero_sigma_variance')
                records.append(row);continue
            if method=='individual_tests_ols':
                fit=closed_fit(g.normal_stress_at_failure_kpa,g.peak_shear_kpa)
            else:
                fit=closed_fit(cell.normal_stress_at_failure_kpa,cell.peak_shear_kpa,
                               1/variance.to_numpy() if method.endswith('_wls') else None)
            dc=fit['intercept']-source.cohesion_kpa;dm=fit['slope']-source.friction_coefficient_mu
            row.update(status='computed',**fit,source_cohesion_kpa=source.cohesion_kpa,source_mu=source.friction_coefficient_mu,
                       cohesion_delta_kpa=float(dc),mu_delta=float(dm),coefficients_match=bool(abs(dc)<1e-9 and abs(dm)<1e-11),
                       source_c_error_untyped=source.cohesion_error_kpa,source_mu_error_untyped=source.friction_coefficient_error,
                       c_ols_se_minus_source_error=fit['intercept_ols_se']-source.cohesion_error_kpa,
                       mu_ols_se_minus_source_error=fit['slope_ols_se']-source.friction_coefficient_error,
                       raw_temperature_sample_sd_c=float(g.temperature_at_failure_c.std(ddof=1)),
                       source_temperature_error_untyped_c=float(source.friction_temperature_error_c))
            records.append(row)
    frame=pd.DataFrame(records)
    frame.to_csv(HERE/'stage1_weight_probe.csv',index=False,lineterminator='\n')
    summaries=[]
    for method,g in frame.groupby('method',sort=False):
        good=g[g.status=='computed']
        summaries.append(dict(method=method,computed=len(good),unavailable=len(g)-len(good),
                              matching_author_coefficient_layers=int(good.coefficients_match.astype(bool).sum()),
                              max_abs_cohesion_delta_kpa=float(good.cohesion_delta_kpa.abs().max()),
                              max_abs_mu_delta=float(good.mu_delta.abs().max())))
    axis=[]
    for block,selected in [('nominal_100_400',[-8,-5,-4,-2,-.5]),('nominal_100_400',[-4,-2,-.5]),('nominal_100_800',[-4,-2,-1,-.5])]:
        g=summary[(summary.nominal_stress_group==block)&summary.temperature_target_c.isin(selected)]
        for response,ycol,errcol,tcol in [('c','cohesion_kpa','cohesion_error_kpa','cohesion_temperature_mean_c'),
                                         ('mu','friction_coefficient_mu','friction_coefficient_error','friction_temperature_mean_c')]:
            for input_axis in ['nominal','measured_mean']:
                fit=closed_fit(g.temperature_target_c if input_axis=='nominal' else g[tcol],g[ycol],1/g[errcol].to_numpy()**2)
                axis.append(dict(block=block,selected_layers=selected,response=response,temperature_axis=input_axis,
                                 weight='inverse_literal_response_error_squared;not_assuming_header_semantics',**fit))
    report=dict(probe_version='source-stage1-closedform-v1',evaluation_stratum='external_source_reconstruction',
                formula='mu=sum(w*(sigma-sigma_bar)*(tau-tau_bar))/sum(w*(sigma-sigma_bar)^2);c=tau_bar-mu*sigma_bar',
                raw_zip_sha256=sha(archive),raw_workbook_member_sha256=hashlib.sha256(raw).hexdigest(),
                coefficient_workbook_member_sha256=hashlib.sha256(coef).hexdigest(),
                canonical_observations_sha256=sha(obs_path),canonical_summaries_sha256=sha(summary_path),
                raw_value_checks=141*len(fields),max_canonical_vs_original_numeric_delta=max_raw_delta,
                actual_read_scope='Original experiments Sheet1 numericD/E/F/G/L for141rows plus relevant headers; coefficient Sheet1 two nominal-stress-domain blocks,14summary columns and literalerrorheaders; Sheet2 parsed empty and unused; no workbook changes.',
                original_header_examples={k:rc[k] for k in ['D1','E1','F1','G1','L1']},
                coefficient_original_header_examples={k:coeffcells['Sheet1'].get(k) for k in ['A5','A6','A7','A8','A12','A13','A14','A15']},
                candidate_summary=summaries,source_axis_weight_probe=axis,
                interpretation='Individual-testOLS reproduces12of14 coefficientlayers including reportederrornumbers;this is numerical evidence of algorithm/SE correspondence,not a sourceheader redefinition. Both-.5Clayers remain unreproduced. No rows removed or filled.',
                scope='42stage1 reconstructions and12source-summary axis/weight checks;no new competition/model selection or local event fitting',
                source_error_type_preserved='literal_error_untyped;OLSstandarderrors explicitly computed separately',
                local_stress_used_for_tuning=False,local_event_time_used_for_tuning=False,source_rows_deleted=0,
                independent_local_events=0,canonical_audit_modified=False)
    (HERE/'stage1_weight_probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summaries))
    print(json.dumps([v for v in axis if v['block']=='nominal_100_400' and v['selected_layers']==[-4,-2,-.5] and v['response']=='c']))


if __name__=='__main__':main()
