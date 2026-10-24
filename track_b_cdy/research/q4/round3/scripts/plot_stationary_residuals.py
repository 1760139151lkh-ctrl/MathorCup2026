#!/usr/bin/env python3
"""Show finite-time stationary residuals in existing registered native cases."""
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
from matplotlib.colors import LogNorm

ROOT = Path(__file__).resolve().parents[5]
R = ROOT/'track_b/research/q4/round3'
SELECTION = [
    ('copdem_120_single_ref__sf0', 'Reference: mu=0.15; zero entrainment'),
    ('copdem_120_single_entrain1m_P1buf250__sf0', 'Same friction; bounded 1m bed entrainment'),
    ('copdem_120_single_mu0p25__sf0', 'High friction: mu=0.25; zero entrainment')]


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    rows = {x['run_id']: x for x in csv.DictReader((R/'results/official_runs.csv').open())}
    fields = {x['run_id']: x for x in json.loads((R/'results/official_fields.json').read_text())['fields']}
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), layout='constrained')
    output = []
    for ax, (rid, label) in zip(axes, SELECTION):
        assert rows[rid]['status'] == 'completed'
        rec = fields[rid]
        p = Path(rec['path'])
        assert sha(p) == rec['sha256']
        with np.load(p) as d:
            h = d['depth_final'].astype(np.float64)
            speed = d['stationary_criterion_speed_final'].astype(np.float64)
            t = float(d['time_s'][-1])
            tr = Affine(*d['transform'][:6])
            h0 = d['depth_frames'][0]
        assert np.isfinite(h).all() and np.isfinite(speed).all()
        wet = h >= .1
        stationary = wet & (speed < .1)
        area = abs(tr.a*tr.e)
        volume = float(h[stationary].sum()*area)
        extent = [tr.c/1000, (tr.c+tr.a*h.shape[1])/1000, (tr.f+tr.e*h.shape[0])/1000, tr.f/1000]
        im = ax.imshow(np.ma.masked_where(~stationary, h), extent=extent,
                       cmap='magma', norm=LogNorm(.1, 100), origin='upper')
        ax.contour(h0 >= .1, levels=[.5], extent=extent, origin='upper', colors='grey', linewidths=.7)
        ax.plot(340.981540835, 3129.214004556, 'cx', ms=6)
        if not stationary.any():
            ax.text(.02, .97, 'No cells meet criterion', transform=ax.transAxes, va='top', fontsize=8)
        ax.set(xlabel='UTM45N easting (km)', ylabel='Northing (km)',
               title=f'{label}\nActual t={t:.1f}s; stationary volume={volume/1e6:.4f}Mm³')
        output.append({'run_id': rid, 'fields': rec, 'actual_end_time_s': t,
                       'stationary_residual_volume_m3': volume,
                       'stationary_residual_planar_area_m2': int(stationary.sum())*area,
                       'stationary_residual_max_depth_m': float(h[stationary].max()) if stationary.any() else 0.0,
                       'all_final_wet_volume_m3': float(h[wet].sum()*area)})
    fig.colorbar(im, ax=list(axes), label='Finite-time stationary depth (m)', shrink=.65)
    fig.suptitle('Criterion: total depth ≥0.1m and maximum horizontal speed of wet phases <0.1m/s\nGrey outline: initial source. Threshold diagnostic only; permanent deposition is not established.', fontsize=10)
    fig.savefig(R/'figures/comparison_stationary_residuals.png', dpi=160)
    plt.close(fig)
    (R/'results/stationary_residual_comparison.json').write_text(json.dumps({
        'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'runs': output,
        'stationary_criterion': 'final total h>=0.1m, max-phase horizontal speed<0.1m/s, each phase wet cutoff1e-6m',
        'scope': 'Existing registered case postprocessing, not a new experiment, permanent deposit observation or sediment mass validation.',
        'independent_local_event_validation_count': 0}, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'stationary_residual_volumes_m3': [x['stationary_residual_volume_m3'] for x in output]}))


if __name__ == '__main__':
    main()
