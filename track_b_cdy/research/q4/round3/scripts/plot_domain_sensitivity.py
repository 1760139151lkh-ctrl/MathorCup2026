#!/usr/bin/env python3
"""Postprocess frozen D-Claw v1 domain/parameter diagnostics; no solver run."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import numpy as np
from affine import Affine
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

ROOT = Path(__file__).resolve().parents[5]
R = ROOT/'track_b/research/q4/round3'


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def load_fields(bundle, run_id):
    rec = next(f for f in bundle['files'] if f.get('run_id') == run_id and f['path'].endswith('.npz'))
    path = Path(rec['path'])
    assert sha(path) == rec['sha256']
    with np.load(path) as arrays:
        return {k: arrays[k] for k in arrays.files}, rec


def main():
    p = R/'exports/propagation_v1/bundle.json'
    assert sha(p) == 'aeafa98159440c675eaae00b2cbd7afec21b31b92a2511f8cb3ed988594ad9e7'
    bundle = json.loads(p.read_text())
    old, old_rec = load_fields(bundle, 'copdem_120_dclaw_ref')
    expanded, ext_rec = load_fields(bundle, 'dclaw_ref_extended120')
    permeable, perm_rec = load_fields(bundle, 'copdem_120_dclaw_permeable')
    tr0, tr1 = Affine(*old['transform'][:6]), Affine(*expanded['transform'][:6])
    row0, col0 = int(round((tr1.f-tr0.f)/120)), int(round((tr0.c-tr1.c)/120))
    assert (row0, col0) == (84, 84)
    h0, h1 = old['depth_frames'].max(0), expanded['depth_frames'].max(0)
    crop = h1[row0:row0+h0.shape[0], col0:col0+h0.shape[1]]
    assert crop.shape == h0.shape and np.array_equal(old['time_s'], expanded['time_s'])
    wet0, wet1 = h0 >= .1, h1 >= .1
    core_wet = crop >= .1
    intersection, union = int((wet0 & core_wet).sum()), int((wet0 | core_wet).sum())
    metrics = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'inputs': [old_rec, ext_rec, perm_rec],
               'scope': 'Frozenv1 conditional diagnostics; no new simulation, no observational validation',
               'same_grid_core_offset_rc': [row0, col0], 'original_domain_shape': list(h0.shape),
               'expanded_domain_shape': list(h1.shape), 'depth_threshold_m': .1,
               'footprint_original_m2': int(wet0.sum())*14400,
               'footprint_expanded_full_m2': int(wet1.sum())*14400,
               'footprint_expanded_within_original_domain_m2': int(core_wet.sum())*14400,
               'common_domain_footprint_iou': intersection/union,
               'common_domain_maxdepth_field_mae_m': float(np.abs(crop-h0).mean()),
               'arrival_brackets_unchanged_at_saved_resolution': True,
               'arrival_claim_scope': 'See independently rechecked v1 target table, paper (160,180]s; does not imply continuous-time equality',
               'mass_budget_qualified': False, 'independent_local_event_validation_count': 0}
    (R/'results/domain_sensitivity_comparison.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2)+'\n')
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout='constrained')
    for ax, depth, tr, title in zip(axes, [h0, h1], [tr0, tr1], ['Original domain', 'Expanded domain; same original core']):
        extent = [tr.c/1000, (tr.c+tr.a*depth.shape[1])/1000, (tr.f+tr.e*depth.shape[0])/1000, tr.f/1000]
        im = ax.imshow(np.ma.masked_less(depth, .1), extent=extent, origin='upper', cmap='magma', norm=LogNorm(.1, 100))
        ax.plot(340.981540835, 3129.214004556, 'cx', ms=7, mew=2)
        ax.set(xlabel='UTM45N easting (km)', ylabel='UTM45N northing (km)', title=title)
        ax.plot(np.array([tr0.c, tr0.c+tr0.a*h0.shape[1], tr0.c+tr0.a*h0.shape[1], tr0.c, tr0.c])/1000,
                np.array([tr0.f, tr0.f, tr0.f+tr0.e*h0.shape[0], tr0.f+tr0.e*h0.shape[0], tr0.f])/1000,
                '--', color='deepskyblue', lw=.8, label='Original domain boundary')
        ax.legend(fontsize=7, loc='upper left')
    fig.colorbar(im, ax=list(axes), label='Max stored depth (m); <0.1 masked', shrink=.8)
    fig.suptitle('D-Claw prescribed release: equal arrival brackets do not imply equal final footprint', fontsize=11)
    fig.savefig(R/'figures/comparison_domain_sensitivity.png', dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), layout='constrained')
    for name, data in [('Original reference', old), ('Expanded reference', expanded), ('Original high permeability', permeable)]:
        t = data['time_s']
        pct = 100*(data['mass_kg']/data['mass_kg'][0]-1)
        for ax in axes:
            ax.plot(t, pct, label=name)
            ax.axhline(0, color='black', lw=.5)
            ax.set(xlabel='Seconds after bulk release', ylabel='Domain total mass change (%)')
            ax.grid(alpha=.2)
        early = t <= 200
        axes[1].plot(t[early], pct[early], 'o', ms=3, color=axes[1].lines[-2].get_color())
    axes[0].set(xlim=(0, 1800), title='Complete saved histories; boundary loss not corrected')
    axes[1].set(xlim=(0, 200), ylim=(-5, 14), title='Native saved samples; not a volume-dilation metric')
    axes[1].axvline(80, color='gray', ls='--', lw=.8, label='Original-domain first wet boundary')
    axes[0].legend(fontsize=8)
    axes[1].legend(fontsize=7, loc='lower left')
    fig.suptitle('Raw-verified total mass = 2700*solid volume + 1000*fluid volume; budget unresolved', fontsize=10)
    fig.savefig(R/'figures/comparison_mass_budget.png', dpi=160)
    plt.close(fig)
    print(json.dumps({k: metrics[k] for k in ['footprint_original_m2', 'footprint_expanded_full_m2', 'footprint_expanded_within_original_domain_m2', 'common_domain_footprint_iou']}))


if __name__ == '__main__':
    main()
