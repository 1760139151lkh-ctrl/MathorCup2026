#!/usr/bin/env python3
"""Bounded native entrainment and operational stationary-residual comparison."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import csv
import numpy as np
from affine import Affine
import rasterio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

ROOT = Path(__file__).resolve().parents[5]
R = ROOT/'track_b/research/q4/round3'
CASE_ROOT = Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official/runs')
IDS = ['copdem_120_single_ref__sf0', 'copdem_120_single_entrain1m_P1buf250__sf0']


def sha(p):
    digest = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    records = {x['run_id']: x for x in json.loads((R/'results/official_fields.json').read_text())['fields']}
    checks = {x['run_id']: x for x in json.loads((R/'results/official_validation.json').read_text())['checks']}
    runs = {x['run_id']: x for x in csv.DictReader((R/'results/official_runs.csv').open())}
    arrays, outputs = {}, []
    for rid in IDS:
        assert runs[rid]['status'] == 'completed'
        p = Path(records[rid]['path'])
        assert sha(p) == records[rid]['sha256']
        with np.load(p) as d:
            arrays[rid] = {k: d[k] for k in d.files}
        d = arrays[rid]
        h, speed = np.asarray(d['depth_final'], dtype=float), np.asarray(d['stationary_criterion_speed_final'], dtype=float)
        assert np.isfinite(speed).all()
        wet = h >= .1
        stationary = wet & (speed < .1)
        outputs.append({'run_id': rid, 'fields': records[rid], 'actual_end_time_s': float(d['time_s'][-1]),
                        'final_total_domain_volume_m3': float(h.sum()*14400),
                        'final_volume_in_h_ge_01m_m3': float(h[wet].sum()*14400),
                        'stationary_residual_volume_m3': float(h[stationary].sum()*14400),
                        'stationary_residual_area_m2': int(stationary.sum())*14400,
                        'final_wet_horizontal_speed_min_m_s': float(speed[wet].min()) if wet.any() else None,
                        'final_wet_horizontal_speed_median_m_s': float(np.median(speed[wet])) if wet.any() else None,
                        'stationary_mask_definition': 'final h>=0.1m and horizontal speed<0.1m/s; native criterion considers each phase h>=1e-6m',
                        'not_permanent_deposit_or_observed_accumulation': True})
    d = arrays[IDS[1]]
    case = json.loads((CASE_ROOT/IDS[1]/'case.json').read_text())
    bed_path = Path(case['erodible_bed'])
    assert sha(bed_path) == case['erodible_bed_sha256']
    with rasterio.open(bed_path) as ds:
        bed = ds.read(1)
        assert ds.nodata == -9999 and int(ds.read_masks(1).min()) == 255
    erosion = -np.asarray(d['base_change_final_m'], dtype=float)
    assert np.all(erosion >= -1e-6) and np.all(erosion <= bed+1e-5)
    report = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'runs': outputs,
              'erodible_bed': {'path': str(bed_path), 'sha256': sha(bed_path), 'volume_capacity_m3': float(bed.sum()*14400)},
              'native_added_volume_m3': checks[IDS[1]]['native_entrained_added_volume_m3'],
              'native_added_mass_kg': checks[IDS[1]]['native_entrained_added_mass_kg'],
              'saved_erosion_integral_m3': float(erosion.sum()*14400),
              'native_source_adjusted_internal_budget_relative_residual': checks[IDS[1]]['native_internal_summary_mass_budget_relative_residual'],
              'scenario_not_observed_bed': True, 'independent_local_event_validation_count': 0}
    (R/'results/entrainment_residual_comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    tr = Affine(*d['transform'][:6])
    extent = [tr.c/1000, (tr.c+tr.a*bed.shape[1])/1000, (tr.f+tr.e*bed.shape[0])/1000, tr.f/1000]
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), layout='constrained')
    for ax, rid, row in zip(axes[0], IDS, outputs):
        a = arrays[rid]
        h, speed = a['depth_final'], a['stationary_criterion_speed_final']
        masked = np.ma.masked_where(h < .1, h)
        im = ax.imshow(masked, extent=extent, origin='upper', cmap='magma', norm=LogNorm(.1, 100))
        stationary = (h >= .1) & (speed < .1)
        if stationary.any():
            ax.contour(stationary, levels=[.5], extent=extent, origin='upper', colors=['cyan'], linewidths=.6)
        else:
            ax.text(.02, .94, 'No cells meet stationary criterion', transform=ax.transAxes, va='top', fontsize=8,
                    bbox={'facecolor': 'white', 'alpha': .9, 'edgecolor': 'none'})
        ax.set_title(('Zero entrainment' if rid == IDS[0] else 'Bounded 1m bed entrainment')+
                     f'\nFinal flow depth; stationary volume {row["stationary_residual_volume_m3"]/1e6:.3f} Mm³ at {row["actual_end_time_s"]:.1f} s', fontsize=10)
    fig.colorbar(im, ax=list(axes[0]), label='Final flow depth (m)', shrink=.8)
    for ax, layer, title in zip(axes[1], [bed, erosion], ['Specified erodible layer; valid zero elsewhere', 'Actual cumulative erosion; no larger than prescribed layer']):
        im = ax.imshow(np.ma.masked_less_equal(layer, 0), extent=extent, origin='upper', cmap='viridis', vmin=0, vmax=1)
        ax.set_title(title, fontsize=10)
    fig.colorbar(im, ax=list(axes[1]), label='Bed thickness (m; scenario)', shrink=.8)
    for ax in axes.flat:
        ax.plot(340.981540835, 3129.214004556, 'cx', ms=6, mew=1.5)
        ax.set(xlabel='UTM45N easting (km)', ylabel='Northing (km)')
    fig.suptitle('Same release/friction; stationary criterion h>=0.1m, horizontal speed<0.1m/s; no permanent-deposit claim', fontsize=10)
    fig.savefig(R/'figures/comparison_entrainment_residuals.png', dpi=160)
    plt.close(fig)
    print(json.dumps({'native_added_volume_m3': report['native_added_volume_m3'],
                      'stationary_residual_volumes_m3': [row['stationary_residual_volume_m3'] for row in outputs]}))


if __name__ == '__main__':
    main()
