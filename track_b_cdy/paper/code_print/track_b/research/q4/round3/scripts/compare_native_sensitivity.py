#!/usr/bin/env python3
"""Compare registered single-phase native runs; no solver executions or fitting."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[5]
R = ROOT/'track_b/research/q4/round3'
CACHE = Path('<LOCAL_HOME>/Documents/MathorCup/research_cache/round3/q4/official/runs')
CONFIGS = [
    ('copdem_120_single_ref__sf0', 'Reference 120m', 'reference'),
    ('copdem_120_single_cfl025__sf0', 'CFL 0.25', 'numerical'),
    ('copdem_60_single_ref__sf0', 'Reference 60m', 'numerical'),
    ('copdem_120_single_h5__sf0', 'Thickness 5m', 'physical'),
    ('copdem_120_single_h30__sf0', 'Thickness 30m', 'physical'),
    ('copdem_120_single_h136__sf0', 'Thickness 136m', 'physical'),
    ('copdem_120_single_mu0p08__sf0', 'Friction mu=0.08', 'physical'),
    ('copdem_120_single_mu0p25__sf0', 'Friction mu=0.25', 'physical'),
    ('copdem_120_single_xi500__sf0', 'Drag xi=500', 'physical'),
    ('copdem_120_single_xi2000__sf0', 'Drag xi=2000', 'physical'),
]


def sha(p):
    digest = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def rows(name):
    return list(csv.DictReader((R/'results'/name).open()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    runs = {r['run_id']: r for r in rows('official_runs.csv')}
    metrics = {r['run_id']: r for r in rows('official_metrics.csv')}
    fields = {r['run_id']: r for r in json.loads((R/'results/official_fields.json').read_text())['fields']}
    arrivals = rows('official_arrivals.csv')
    expected = [r[0] for r in CONFIGS]
    missing = [rid for rid in expected if rid not in runs or runs[rid]['status'] != 'completed']
    if args.require_complete:
        assert not missing, missing
    loaded, output = {}, []
    for rid, label, kind in CONFIGS:
        if rid in missing:
            continue
        rec = fields[rid]
        path = Path(rec['path'])
        assert sha(path) == rec['sha256']
        cp = CACHE/rid/'case.json'
        assert sha(cp) == rec['case_sha256']
        case = json.loads(cp.read_text())
        with np.load(path) as d:
            loaded[rid] = {k: d[k] for k in d.files}
        d = loaded[rid]
        t, h = d['time_s'], d['depth_frames']
        assert np.isfinite(t).all() and np.all(np.diff(t) > 0) and t[-1] >= case['end_seconds']
        m = metrics[rid]
        def number(key):
            return float(m[key]) if m.get(key) not in [None, ''] else None
        output.append({'run_id': rid, 'label': label, 'comparison_role': kind,
                       'fields': rec, 'actual_end_time_s': float(t[-1]),
                       'depth_max_saved_m': number('max_depth_over_saved_outputs_m'),
                       'horizontal_speed_max_saved_m_s': number('max_horizontal_speed_over_saved_outputs_m_s'),
                       'native_cumulative_speed_scalar_m_s': number('native_global_cumulative_speed_scalar_m_s'),
                       'saved_cumulative_footprint_area_m2': number('impact_area_m2'),
                       'native_internal_summary_budget_relative_residual': number('native_internal_summary_mass_budget_relative_residual'),
                       'ASCII_integral_budget_relative_residual': number('native_mass_budget_relative_residual'),
                       'paper_target_records': [a for a in arrivals if a['run_id'] == rid],
                       'case': case})
    reference = output[0]
    for row in output:
        row['relative_to_reference'] = {
            key: row[key]/reference[key]-1 for key in [
                'depth_max_saved_m', 'horizontal_speed_max_saved_m_s', 'saved_cumulative_footprint_area_m2']}
    # A strict registration-level contrast; saved actual native controls are indexed separately.
    cflid = CONFIGS[1][0]
    cfl_check = None
    if cflid in loaded:
        a, b = [next(r['case'] for r in output if r['run_id'] == rid).copy() for rid in [expected[0], cflid]]
        for case in (a, b):
            for k in ['run_id', 'parent_configuration_run_id', 'extras']:
                case.pop(k, None)
        assert a == b
        assert next(r['case'] for r in output if r['run_id'] == cflid)['extras'] == {'cfl': .25}
        cfl_check = {'registration_other_fields_identical': True,
                     'reference_native_default_CFL': .5, 'challenge_CFL': .25,
                     'execution_control_provenance': 'results/official_native_control_index.json; registration equality alone is not proof of executed control equality'}
        cross_path = R/'results/official_cfl_control_crosscheck.json'
        cross = json.loads(cross_path.read_text())
        for rec in cross['native_parameter_files']:
            assert sha(Path(rec['path'])) == rec['sha256']
        cfl_check['actual_native_control_crosscheck'] = {
            'path': str(cross_path.relative_to(ROOT)), 'bytes': cross_path.stat().st_size,
            'sha256': sha(cross_path), 'only_numeric_control_difference': 'CFL criterion 0.50 to 0.25',
            'actual_binary_sha256': cross['actual_binary_sha256']}
    doc = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
           'status': 'complete_registered_single_comparison' if not missing else 'provisional_completed_subset',
           'required_ids': expected, 'pending_ids': missing, 'runs': output, 'CFL_pair': cfl_check,
           'interpretation': 'Numerical and physical variations are separated. Two spatial grids or two CFL values do not establish asymptotic convergence. Peaks from saved fields can depend on temporal sampling; native cumulative scalar is a different quantity. The native cumulative speed also changes under the CFL-only contrast, so stored-output sampling cannot explain the whole difference.',
           'independent_local_event_validation_count': 0, 'predictive_qualification': False}
    (R/'results/native_sensitivity_comparison.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    fig, axes = plt.subplots(2, 3, figsize=(15, 9), layout='constrained')
    for rid, label, kind in CONFIGS[:3]:
        if rid not in loaded:
            continue
        d = loaded[rid]
        t, h = d['time_s'], d['depth_frames']
        cellarea = abs(float(d['transform'][0]*d['transform'][4]))
        speed = np.where(h >= .1, d['horizontal_speed_frames'], 0).reshape(len(t), -1).max(1)
        for ax, values in zip(axes[0], [d['volume_m3']/1e6, speed, (h >= .1).sum((1, 2))*cellarea/1e6]):
            ax.plot(t, values, label=label, lw=1.3)
    for ax, label in zip(axes[0], ['Saved domain volume (Mm³)', 'Wet horizontal speed peak (m/s)', 'Instantaneous wet area (km²)']):
        ax.set(xlabel='Actual seconds after bulk release', ylabel=label)
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    colors = {'reference': '#676767', 'numerical': '#c47b20', 'physical': '#3d76a2'}
    for ax, key, label in zip(axes[1],
                             ['depth_max_saved_m', 'horizontal_speed_max_saved_m_s', 'saved_cumulative_footprint_area_m2'],
                             ['Saved depth peak', 'Saved horizontal speed peak', 'Cumulative wet footprint']):
        values = [100*row['relative_to_reference'][key] for row in output]
        ax.barh([r['label'] for r in output], values, color=[colors[r['comparison_role']] for r in output])
        ax.invert_yaxis()
        ax.axvline(0, color='black', lw=.6)
        ax.set(xlabel='Change from 120m reference (%)', title=label)
        ax.grid(axis='x', alpha=.2)
    scope = 'All ten registered comparisons' if not missing else 'Completed subset only'
    fig.suptitle('Registered single-phase sensitivity: orange numerical settings; blue conditional physical inputs\n'+scope+'; no convergence or independently validated prediction claim', fontsize=11)
    fig.savefig(R/'figures/comparison_single_sensitivity.png', dpi=160)
    plt.close(fig)
    print(json.dumps({'completed_single': len(output), 'pending_single': missing, 'registration_CFL_contrast_verified': bool(cfl_check)}))


if __name__ == '__main__':
    main()
