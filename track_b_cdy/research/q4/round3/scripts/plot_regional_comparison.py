#!/usr/bin/env python3
"""Geographic process panels from executed runs with explicit qualification limits."""
from pathlib import Path
import csv
import json
import hashlib
from datetime import datetime, timezone
import numpy as np
from affine import Affine
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

ROOT = Path(__file__).resolve().parents[5]
R = ROOT/'track_b/research/q4/round3'
TARGET = (340.981540835, 3129.214004556)


def sha(p):
    digest = hashlib.sha256()
    with Path(p).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def bound_load(rec):
    assert sha(rec['path']) == rec['sha256'], rec['path']
    return np.load(rec['path'])


def main():
    rows = {r['run_id']: r for r in csv.DictReader((R/'results/official_runs.csv').open())}
    index = json.loads((R/'results/official_fields.json').read_text())['fields']
    fields = {f['run_id']: f for f in index}
    selected = []
    reduced = json.loads((R/'results/reduced_2d_ref_60m.json').read_text())
    used_inputs = [reduced['fields']]
    d = bound_load(reduced['fields'])
    tr = Affine(60, 0, d['x'][0]-30, 0, -60, d['y'][0]+30)
    selected.append({'label': 'Custom 2D HR: diagnostic only', 'run': reduced['run_id'],
                     'depth': d['snapshots'].max(0), 'transform': tr, 'interval': '30 s saved outputs'})
    for model in ['ravaflow_single', 'dclaw']:
        candidates = [run for run, row in rows.items() if row['model'] == model and row['status'] == 'completed'
                      and row.get('role') == 'conditional_scenario' and '120' in run and 'ref' in run
                      and 'extended' not in run and run in fields]
        candidates.sort(key=lambda name: ('__sf0' not in name, len(name)))
        if candidates:
            run = candidates[0]
            used_inputs.append(fields[run])
            q = bound_load(fields[run])
            selected.append({'label': {'ravaflow_single': 'r.avaflow homogeneous', 'ravaflow_multi': 'r.avaflow multiphase proxy',
                                       'dclaw': 'D-Claw pore pressure'}[model],
                             'run': run, 'depth': q['depth_frames'].max(0),
                             'transform': Affine(*q['transform'][:6]), 'interval': 'native saved outputs; actual times'})
    composite = 'composite_RI_water_120__sf0'
    if composite in rows and rows[composite]['status'] == 'completed' and composite in fields:
        used_inputs.append(fields[composite])
        q = bound_load(fields[composite])
        selected.insert(-1, {'label': 'r.avaflow composite rock-ice solid + water', 'run': composite,
                            'depth': q['depth_frames'].max(0), 'transform': Affine(*q['transform'][:6]),
                            'interval': 'native saved outputs; actual times'})
    fig, axes = plt.subplots(len(selected), 1, figsize=(10, 3.6*len(selected)), layout='constrained')
    axes = np.atleast_1d(axes)
    for axis, item in zip(axes, selected):
        h, tr = item['depth'], item['transform']
        extent = [tr.c/1000, (tr.c+tr.a*h.shape[1])/1000, (tr.f+tr.e*h.shape[0])/1000, tr.f/1000]
        im = axis.imshow(np.ma.masked_less(h, .1), extent=extent, origin='upper',
                         cmap='magma', norm=LogNorm(.1, 100))
        axis.plot(*TARGET, 'cx', ms=8, mew=2, label='Paper target candidate')
        axis.set(xlabel='UTM45N easting (km)', ylabel='UTM45N northing (km)',
                 title=f"{item['label']} — {item['run']}")
        axis.legend(loc='upper left', fontsize=8)
        axis.grid(alpha=.12)
        fig.colorbar(im, ax=axis, label='Max over stored depth outputs (m); scale 0.1–100')
    fig.suptitle('Common Copernicus DEM and release volume; native mapping and boundary differences retained', fontsize=11)
    fig.savefig(R/'figures/comparison_regional_fields.png', dpi=160)
    plt.close(fig)

    if 'copdem_120_dclaw_ref' in fields:
        data = bound_load(fields['copdem_120_dclaw_ref'])
        times, frames = data['time_s'], data['depth_frames']
        tr = Affine(*data['transform'][:6])
        extent = [tr.c/1000, (tr.c+tr.a*frames.shape[2])/1000,
                  (tr.f+tr.e*frames.shape[1])/1000, tr.f/1000]
        fig, axes = plt.subplots(2, 3, figsize=(14, 7), layout='constrained')
        for axis, desired in zip(axes.flat, [0, 40, 80, 180, 360, 1800]):
            k = int(np.argmin(np.abs(times-desired)))
            im = axis.imshow(np.ma.masked_less(frames[k], .1), extent=extent, origin='upper',
                             norm=LogNorm(.1, 100), cmap='magma')
            axis.plot(*TARGET, 'cx', ms=6, mew=1.5)
            axis.set(xlabel='Easting (km)', ylabel='Northing (km)', title=f'Actual t={times[k]:.1f} s')
        fig.colorbar(im, ax=list(axes.flat), label='Depth (m); <0.1 masked', shrink=.8)
        fig.suptitle('D-Claw reference: conditional release; boundary wet by 80 s; target candidate at 180 s', fontsize=11)
        fig.savefig(R/'figures/comparison_dclaw_process.png', dpi=160)
        plt.close(fig)

        if data['pressure_frames'].size:
            fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout='constrained')
            k = int(np.argmin(np.abs(times-80)))
            wet = frames[k] >= .1
            im = axes[0].imshow(np.ma.masked_where(~wet, data['pressure_frames'][k]/1000),
                                extent=extent, origin='upper', cmap='viridis')
            fig.colorbar(im, ax=axes[0], label='Basal pressure (kPa)')
            im = axes[1].imshow(np.ma.masked_where(~wet, data['solid_fraction_frames'][k]),
                                extent=extent, origin='upper', vmin=.5, vmax=.8, cmap='cividis')
            fig.colorbar(im, ax=axes[1], label='Solid volume fraction')
            for axis in axes:
                axis.set(xlabel='Easting (km)', ylabel='Northing (km)')
            axes[0].set_title(f'Actual native pressure, t={times[k]:.1f} s')
            axes[1].set_title(f'Native solid fraction, t={times[k]:.1f} s')
            fig.suptitle('D-Claw conditional process fields; source pressure is prescribed, not measured', fontsize=11)
            fig.savefig(R/'figures/comparison_dclaw_pressure.png', dpi=160)
            plt.close(fig)
    report = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'selected_run_ids': [x['run'] for x in selected],
              'hash_bound_input_arrays': used_inputs,
              'scope': 'Saved-output conditional process illustrations; no common effective discretisation, scientific acceptance or independent event-validation claim.',
              'independent_local_event_validation_count': 0}
    (R/'results/regional_visual_inputs.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'completed_reference_panels': len(selected), 'note': 'All input array hashes verified; review regenerated figures before final freeze.'}))


if __name__ == '__main__':
    main()
