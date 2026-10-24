#!/usr/bin/env python3
"""Replot frozen Q4 process fields for the paper; never run a physical model."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource, LogNorm, SymLogNorm
from matplotlib import font_manager
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = ROOT / 'track_b/research/q4/round3'
PAPER = ROOT / 'track_b/paper'
OUT = PAPER / 'figures/q4'
PRIMARY = 'q2full_q2r3_p0036_S_T_linear__geomv2_120m__sf0'
FINE = 'q2full_q2r3_p0036_S_T_linear__geomv2_60m__sf0'
PRESSURE = 'dclaw_ref_extended120'
PHASE = 'composite_RI_water_120__sf0'
USED = []


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def record(path, role):
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'sha256': sha(path), 'bytes': path.stat().st_size, 'role': role}


def load_fields(run_id):
    index = RESEARCH / 'results/official_fields.json'
    row = next(x for x in json.loads(index.read_text())['fields'] if x['run_id'] == run_id)
    path = Path(row['path'])
    assert sha(path) == row['sha256'] and path.stat().st_size == row['bytes']
    USED.append({**record(path, 'frozen native saved process fields'), 'run_id': run_id,
                 'bound_by_repo_index': record(index, 'native field index')})
    with np.load(path) as data:
        return {key: data[key].copy() for key in data.files}


def extent(data):
    tr = data['transform']; ny, nx = data['depth_frames'].shape[1:]
    return [tr[2]/1000, (tr[2]+tr[0]*nx)/1000,
            (tr[5]+tr[4]*ny)/1000, tr[5]/1000]


def setup():
    path = font_manager.findfont(font_manager.FontProperties(family='Arial Unicode MS', weight='normal'))
    font_manager.fontManager.addfont(path)
    plt.rcParams.update({'font.family': 'Arial Unicode MS', 'font.size': 8.0,
        'axes.titlesize': 9, 'axes.labelsize': 8, 'xtick.labelsize': 7,
        'ytick.labelsize': 7, 'axes.unicode_minus': False, 'pdf.fonttype': 42,
        'ps.fonttype': 42, 'mathtext.fontset': 'stix', 'axes.linewidth': .6})
    return path


def decorate(ax, title, targets, background, ex):
    ax.imshow(background, extent=ex, origin='upper', cmap='gray', vmin=0, vmax=1,
              interpolation='nearest', rasterized=True)
    ax.set(xlim=(339.48, 357.48), ylim=(3127.68, 3136.92), title=title,
           xlabel='东坐标 E（km）', ylabel='北坐标 N（km）')
    ax.set_xticks([340, 345, 350, 355]); ax.set_yticks([3128, 3132, 3136])
    ax.tick_params(length=2, pad=2)
    if ax.get_subplotspec().is_last_col():
        ax.set_ylabel('')
    ax.set_aspect('equal')
    for key, marker in [('J', 'o'), ('P', '^')]:
        x, y = targets[key]
        ax.plot(x, y, marker, ms=3.5, mfc='white', mec='#20242a', mew=.7, zorder=6)
        ax.annotate(key, (x, y), xytext=(4, 4), textcoords='offset points',
                    fontsize=7.5, weight='bold', color='#1b2027', zorder=7)


def save(fig, name):
    pdf = OUT / f'{name}.pdf'; png = OUT / f'{name}.png'
    fig.savefig(pdf, dpi=300, bbox_inches='tight', pad_inches=.03, metadata={'Creator': 'Q4 frozen-field paper plot',
                                      'CreationDate': None, 'ModDate': None})
    fig.savefig(png, dpi=300, bbox_inches='tight', pad_inches=.03)
    plt.close(fig)
    return [record(pdf, 'paper figure PDF'), record(png, '300dpi visual review image')]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    font_path = setup()
    primary, fine, pressure, phase = [load_fields(rid) for rid in [PRIMARY, FINE, PRESSURE, PHASE]]
    grid = RESEARCH/'results/spatial_inputs_120m.npz'
    USED.append(record(grid, 'registered common terrain grid'))
    with np.load(grid) as data:
        terrain = data['z'].copy()
    background = LightSource(azdeg=315, altdeg=45).hillshade(terrain, vert_exag=1, dx=120, dy=120)
    ex = extent(primary)
    geo_path = RESEARCH/'results/computational_geometries.geojson'
    geoms = json.loads(geo_path.read_text())['features']; USED.append(record(geo_path, 'candidate target geometry'))
    transform = Transformer.from_crs(4326, 32645, always_xy=True)
    targets = {}
    for key, sid in [('J', 'paper_junction'), ('P', 'paper_port_symbol')]:
        obj = next(g for g in geoms if g['properties'].get('space_id') == sid)
        x, y = transform.transform(*obj['geometry']['coordinates']); targets[key] = [x/1000, y/1000]
    norm = LogNorm(.1, 100)
    fig, axes = plt.subplots(2, 2, figsize=(6.65, 3.9))
    fig.subplots_adjust(left=.08, right=.89, bottom=.11, top=.94, wspace=.22, hspace=.47)
    frames = []
    for letter, ax, target in zip('abcd', axes.flat, [0, 180, 600, 1800]):
        k = int(np.argmin(np.abs(primary['time_s']-target)))
        tau = float(primary['time_s'][k]); h = primary['depth_frames'][k]
        decorate(ax, f'（{letter}）τ = {tau:.1f} s', targets, background, ex)
        im = ax.imshow(np.ma.masked_less(h, .1), extent=ex, origin='upper', cmap='viridis',
                       norm=norm, interpolation='nearest', rasterized=True, zorder=2)
        frames.append({'requested_time_s': target, 'actual_time_s': tau,
                       'max_saved_depth_m': float(h.max()), 'wet_planar_area_km2': float((h>=.1).sum()*120**2/1e6)})
    cb = fig.colorbar(im, cax=fig.add_axes([.915, .18, .015, .67]), ticks=[.1, 1, 10, 100])
    cb.set_label('流深 h（m）', labelpad=3); cb.ax.tick_params(labelsize=7)
    outputs = save(fig, 'process_fullmask_st120')

    fig, axes = plt.subplots(2, 2, figsize=(6.65, 4.25))
    fig.subplots_adjust(left=.08, right=.94, bottom=.10, top=.94, wspace=.35, hspace=.48)
    diagnostics = []
    for ax, data, title in [(axes[0,0], primary, '（a）ST 全源面：120 m'),
                            (axes[0,1], fine, '（b）ST 全源面：60 m')]:
        keep = data['time_s'] <= 1800
        hmax = data['depth_frames'][keep].max(axis=0)
        decorate(ax, title, targets, background, ex)
        im = ax.imshow(np.ma.masked_less(hmax, .1), extent=extent(data), origin='upper',
                       cmap='viridis', norm=norm, interpolation='nearest', rasterized=True, zorder=2)
        cb = fig.colorbar(im, ax=ax, pad=.015, fraction=.035, ticks=[.1, 1, 10, 100])
        cb.ax.tick_params(labelsize=6.5); cb.set_label('最大流深（m）', fontsize=7, labelpad=2)
        diagnostics.append({'panel': title, 'field': 'max saved total depth for actual times <=1800s',
                            'last_selected_time_s': float(data['time_s'][keep][-1]),
                            'threshold_footprint_km2': float((hmax>=.1).sum()*data['transform'][0]**2/1e6)})
    k = int(np.argmin(np.abs(pressure['time_s']-180)))
    h = pressure['depth_frames'][k]; p = pressure['pressure_frames'][k]/1000
    ax = axes[1,0]; decorate(ax, f'（c）D-Claw：τ = {pressure["time_s"][k]:.0f} s', targets, background, ex)
    p = np.ma.masked_where((h < .1) | ~np.isfinite(p), p)
    im = ax.imshow(p, extent=extent(pressure), origin='upper', cmap='magma', norm=SymLogNorm(linthresh=1, vmin=0, vmax=600),
                   interpolation='nearest', rasterized=True, zorder=2)
    cb = fig.colorbar(im, ax=ax, pad=.015, fraction=.035, ticks=[0,1,10,100,600]); cb.set_label('基底压力（kPa）', fontsize=7, labelpad=2)
    cb.ax.tick_params(labelsize=6.5)
    k = int(np.argmin(np.abs(phase['time_s']-180)))
    h = phase['depth_frames'][k]; depths = phase['phase_depth_frames'][k]
    assert depths.shape[0] == 3 and np.max(np.abs(depths[1])) == 0
    water = np.divide(depths[2], depths.sum(axis=0), out=np.zeros_like(h), where=depths.sum(axis=0)>0)
    ax = axes[1,1]; decorate(ax, f'（d）复合固水：τ = {phase["time_s"][k]:.1f} s', targets, background, ex)
    im = ax.imshow(np.ma.masked_where(h<.1, water), extent=extent(phase), origin='upper',
                   cmap='Blues', vmin=0, vmax=1, interpolation='nearest', rasterized=True, zorder=2)
    cb = fig.colorbar(im, ax=ax, pad=.015, fraction=.035, ticks=[0, .5, 1]); cb.set_label('水相厚度份额', fontsize=7, labelpad=2)
    cb.ax.tick_params(labelsize=6.5)
    outputs += save(fig, 'model_comparison')
    report = {'schema_version':'q4-paper-plot-manifest-v1', 'command':'track_b/.venv/bin/python track_b/paper/scripts/q4_plot_results.py',
        'source_files':USED, 'outputs':outputs, 'main_process_frames':frames,
        'comparison_panels':diagnostics, 'target_markers_utm_km':targets,
        'font_file':font_path, 'comparison_horizon_seconds':1800,
        'scope':'Frozen conditional flow fields. ST panels use V31.184139Mm3; pressure/composite panels use distinct baseline V13.878Mm3. Geographic panel limits show common core; expanded pressure run solved larger domain.',
        'threshold_depth_m':.1, 'target_buffer_radius_m':100,
        'pressure_color_scale':'SymLogNorm: linear0-1kPa, logarithmic1-600kPa',
        'pressure_actual_time_s':180.0, 'water_fraction_actual_time_s':180.5, 'time_origin':'given bulk release',
        'initiation_to_release_delay_seconds':None, 'independent_local_event_validation_count':0,
        'physical_model_runs_added':0}
    (PAPER/'evidence/q4_plot_manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'process_frames':frames,'comparison_panels':diagnostics,'outputs':[x['path'] for x in outputs]},ensure_ascii=False))


if __name__ == '__main__':
    main()
