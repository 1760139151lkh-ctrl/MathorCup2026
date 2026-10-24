#!/usr/bin/env python3
"""Plot completed, hash-bound composite-solid/water experiments only."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import csv
import numpy as np
from affine import Affine
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[5]
R = ROOT/'track_b/research/q4/round3'
IDS = ['composite_RI_water_120__sf0', 'composite_RI_water_nodragvm_120__sf0', 'composite_rock_water_120__sf0']


def sha(p):
    digest = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    rows = {r['run_id']: r for r in csv.DictReader((R/'results/official_runs.csv').open())}
    fields = {r['run_id']: r for r in json.loads((R/'results/official_fields.json').read_text())['fields']}
    data, report = {}, []
    for rid in IDS:
        assert rid in rows and rows[rid]['status'] == 'completed', f'Wait for completed native run: {rid}'
        rec = fields[rid]
        p = Path(rec['path'])
        assert sha(p) == rec['sha256']
        with np.load(p) as d:
            data[rid] = {k: d[k] for k in d.files}
        d = data[rid]
        phase = d['phase_depth_frames']
        assert phase.shape[:2] == (len(d['time_s']), 3)
        assert np.isfinite(phase).all()
        assert float(np.min(phase)) >= -1e-7
        assert float(np.max(np.abs(phase[:, 1]))) == 0, 'Registered empty phase2 unexpectedly populated'
        fraction_checks = []
        for k in [0, len(d['time_s'])-1]:
            total = phase[k].astype(np.float64).sum(0)
            wet = d['depth_frames'][k] >= .1
            fraction = np.divide(phase[k, 2], total, out=np.zeros_like(total), where=total > 0)
            weights = total[wet]
            mean = float(np.average(fraction[wet], weights=weights)) if wet.any() else None
            fraction_checks.append({'actual_time_s': float(d['time_s'][k]),
                                    'wet_total_depth_threshold_m': .1,
                                    'minimum': float(fraction[wet].min()) if wet.any() else None,
                                    'maximum': float(fraction[wet].max()) if wet.any() else None,
                                    'mixture_volume_weighted_mean': mean,
                                    'mixture_volume_weighted_spatial_stddev': float(np.sqrt(np.average((fraction[wet]-mean)**2, weights=weights))) if wet.any() else None})
        report.append({'run_id': rid, 'fields': rec, 'empty_phase2_max_abs_depth_m': float(np.max(np.abs(phase[:, 1]))),
                       'max_abs_phase_sum_minus_mixture_depth_m': float(np.max(np.abs(phase.sum(1)-d['depth_frames']))),
                       'initial_phase_volumes_m3': d['phase_volume_m3'][0].tolist(),
                       'final_phase_volumes_m3': d['phase_volume_m3'][-1].tolist(),
                       'initial_mass_kg': float(d['mass_kg'][0]), 'final_domain_mass_kg': float(d['mass_kg'][-1]),
                       'actual_end_time_s': float(d['time_s'][-1]),
                       'descriptive_water_fraction_statistics': fraction_checks})
    ref, ablation = data[IDS[0]], data[IDS[1]]
    assert np.array_equal(ref['phase_depth_frames'][0], ablation['phase_depth_frames'][0])
    assert abs(ref['mass_kg'][0]/ablation['mass_kg'][0]-1) < 1e-10
    rock = data[IDS[2]]
    assert np.array_equal(ref['phase_depth_frames'][0], rock['phase_depth_frames'][0])
    assert rock['mass_kg'][0] > ref['mass_kg'][0]
    output = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'runs': report,
              'comparison': 'Same composite-solid/water initial phases and mass; only drag and virtual-mass terms disabled. Other buoyancy/pressure coupling remains.',
              'material_limit': 'Ice only changes composite-solid density. No separate rock/ice velocity, thermal state or melting is solved.',
              'all_rock_pair': 'Same phase volumes, different solid density and total mass; not fixed-mass pure-ice intervention.',
              'initial_all_rock_phase_depths_equal_to_RI': True,
              'water_fraction_statistic_scope': 'Descriptive native spatial composition, not a preregistered score, observed phase segregation, thermal phase change or calibrated physical attribution. Domain losses and mass drift remain separate.',
              'independent_local_event_validation_count': 0}
    (R/'results/composite_phase_comparison.json').write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    fig, axes = plt.subplots(2, 3, figsize=(14, 7), layout='constrained')
    for row, rid, label in zip(axes, IDS[:2], ['Native coupled reference', 'Drag and virtual mass disabled']):
        d = data[rid]
        tr = Affine(*d['transform'][:6])
        h = d['depth_frames']
        extent = [tr.c/1000, (tr.c+tr.a*h.shape[2])/1000, (tr.f+tr.e*h.shape[1])/1000, tr.f/1000]
        for ax, wanted in zip(row, [0, 180, float(d['time_s'][-1])]):
            k = int(np.argmin(np.abs(d['time_s']-wanted)))
            phases = d['phase_depth_frames'][k]
            total = phases.sum(0)
            fraction = np.divide(phases[2], total, out=np.zeros_like(total), where=total > 0)
            im = ax.imshow(np.ma.masked_where(h[k] < .1, fraction), extent=extent, origin='upper', cmap='Blues', vmin=0, vmax=1)
            ax.plot(340.981540835, 3129.214004556, 'mx', ms=5)
            ax.set(xlabel='UTM45N easting (km)', ylabel='Northing (km)', title=f'{label}\nActual t={d["time_s"][k]:.1f} s')
    fig.colorbar(im, ax=list(axes.flat), label='Water volume fraction in moving/residual mixture; h<0.1 masked', shrink=.8)
    fig.suptitle('Composite rock-ice solid + water: conditional phase distributions; no ice-melt process', fontsize=11)
    fig.savefig(R/'figures/comparison_composite_phases.png', dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
    names = ['Composite R/I + water', 'Same material, drag/VM disabled', 'All-rock solid + water']
    for rid, label in zip(IDS, names):
        d = data[rid]
        axes[0].plot(d['time_s'], d['phase_volume_m3'][:, 0]/1e6, label=label)
        axes[1].plot(d['time_s'], d['phase_volume_m3'][:, 2]/1e6, label=label)
    for ax, title in zip(axes, ['Solid-composite phase', 'Water phase']):
        ax.set(xlabel='Actual seconds after bulk release', ylabel='Saved-output domain volume (Mm³)', title=title)
        ax.grid(alpha=.2)
        ax.legend(fontsize=7)
    fig.suptitle('Domain phase volumes; changes include outflow and numerical effects, not phase transformation', fontsize=10)
    fig.savefig(R/'figures/comparison_composite_phase_volumes.png', dpi=160)
    plt.close(fig)
    print(json.dumps({'completed_cases': 3, 'initial_drag_VM_ablation_state_equal': True, 'no_melting_claim': True}))


if __name__ == '__main__':
    main()
