#!/usr/bin/env python3
"""Read-only, reproducible audit of Track B spatial inputs (directories 03--08).

AI assistance: Codex, OpenAI, 2026-10-23; exact model/version not exposed.
Generated audit code and charts require team review; see track_b/AI_USAGE.md.
No installation, reprojection, interpolation, modeling or source-file mutation.
Recommended existing interpreter: /usr/local/anaconda3/bin/python
Metadata and pixel statistics cover every TIFF; exceptions remain explicit.
Vector coverage counts use record bounding boxes / supplied representative points,
not exact polygon intersections. UTM inverse is for approximate audit bounds only.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from zoneinfo import ZoneInfo

import numpy as np
import tifffile


def clean(v):
    """Convert library scalars/metadata to strict JSON (no NaN/Infinity)."""
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if isinstance(v, np.ndarray):
        if v.dtype.hasobject or v.dtype.fields:
            return str(v)
        return clean(v.tolist())
    if isinstance(v, np.generic):
        return clean(v.item())
    if isinstance(v, bytes):
        return v.decode('utf-8', errors='replace')
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    return str(v)


def write_json(path, obj):
    path.write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2,
                               allow_nan=False) + '\n', encoding='utf-8')


def write_csv(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(clean(v), ensure_ascii=False) if isinstance(v, (dict, list, tuple))
                        else clean(v) for k, v in row.items()})


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def pixels(path):
    """Pillow/libtiff is a fallback for LZW when imagecodecs is absent."""
    try:
        return tifffile.imread(path), 'tifffile', None
    except Exception as e:
        first = f'{type(e).__name__}: {e}'
        try:
            from PIL import Image
            with Image.open(path) as im:
                return np.asarray(im), 'Pillow/libtiff', first
        except Exception as second:
            raise RuntimeError(first + '; Pillow: ' + str(second)) from second


def array_stats(a, nodata=None):
    a = np.asarray(a)
    finite = np.isfinite(a)
    nodata_mask = np.zeros(a.shape, dtype=bool)
    if nodata is not None and math.isfinite(float(nodata)):
        nodata_mask = a == nodata
    valid = finite & ~nodata_mask
    values = a[valid]
    out = {'cells': a.size, 'nonfinite_cells': int((~finite).sum()),
           'nodata_cells': int(nodata_mask.sum()), 'valid_cells': int(valid.sum()),
           'valid_fraction': float(valid.mean()), 'scan': 'all cells'}
    if values.size:
        out.update(min=float(values.min()), max=float(values.max()))
        if a.dtype != np.uint8:
            out.update(mean=float(values.astype(np.float64).mean()),
                       quantiles_p0_p25_p50_p75_p100=np.quantile(values, [0, .25, .5, .75, 1]).tolist())
        else:
            out['numeric_code_warning'] = 'Categorical codes: arithmetic mean/quantiles are intentionally omitted.'
    if a.dtype == np.uint8 or values.size < 2:
        vals, counts = np.unique(a, return_counts=True)
        out['value_counts_including_nodata'] = {str(x): int(c) for x, c in zip(vals, counts)}
    return out


def raster_info(path, root):
    with tifffile.TiffFile(path) as f:
        p = f.pages[0]
        geo = p.geotiff_tags or {}
        epsg = geo.get('ProjectedCSTypeGeoKey') or geo.get('GeographicTypeGeoKey')
        scale = geo.get('ModelPixelScale')
        tie = geo.get('ModelTiepoint')
        box = None
        if scale and tie:
            left = tie[3] - tie[0] * scale[0]
            top = tie[4] + tie[1] * scale[1]
            box = [left, top - p.imagelength * scale[1],
                   left + p.imagewidth * scale[0], top]
        nd = p.tags.get('GDAL_NODATA')
        nd = float(nd.value) if nd else None
        out = {'path': str(path.relative_to(root)), 'bytes': path.stat().st_size,
               'pages': len(f.pages), 'height': p.imagelength, 'width': p.imagewidth,
               'dtype': str(p.dtype), 'epsg': int(epsg) if epsg else None,
               'pixel_size_xy': scale[:2] if scale else None,
               'coordinate_unit': 'metre' if geo.get('GTModelTypeGeoKey') == 1 else 'degree',
               'bounds_left_bottom_right_top': box, 'nodata': nd,
               'compression': p.compression.name, 'geotiff_tags': clean(geo),
               'metadata_scan': 'all TIFFs, first image directory; page count recorded'}
        name = path.name
        if '_dhdt' in name:
            match = re.match(r'(N\d{2}E\d{3})_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})_', name)
            if match:
                out.update(tile=match[1], period_start=match[2], period_end=match[3])
            out['variant'] = 'error_UTM' if '_err' in name else 'dhdt_GCS' if '_GCS' in name else 'dhdt_UTM'
            out['measurement_semantics'] = 'period-average surface elevation change rate / its uncertainty; not event-time data'
        try:
            a, reader, fallback = pixels(path)
            out['pixel_reader'] = reader
            if fallback:
                out['primary_reader_exception'] = fallback
            out['pixel_statistics'] = array_stats(a, nd)
        except Exception as e:
            out['pixel_read_error'] = str(e)
        return out


def decode_str(raw, encoding):
    return raw.rstrip(b'\x00 ').decode(encoding, errors='replace').strip()


def dbf_info(path, root):
    b = path.read_bytes()
    n = struct.unpack_from('<I', b, 4)[0]
    header_len, record_len = struct.unpack_from('<HH', b, 8)
    cpg = path.with_suffix('.cpg')
    cpg_text = cpg.read_text(encoding='ascii').strip() if cpg.exists() else None
    encoding = 'utf-8' if cpg_text and cpg_text.upper() in {'UTF-8', '65001', 'UTF8'} else 'gb18030'
    fields = []
    for pos in range(32, header_len - 1, 32):
        part = b[pos:pos + 32]
        if part[0] == 13:
            break
        fields.append({'name': decode_str(part[:11].split(b'\0')[0], encoding),
                       'type': chr(part[11]), 'width': part[16], 'decimals': part[17]})
    records, deleted = [], 0
    for i in range(n):
        raw = b[header_len + i * record_len:header_len + (i + 1) * record_len]
        if len(raw) != record_len:
            raise ValueError(f'truncated DBF record {i}')
        if raw[0] == 42:
            deleted += 1
            continue
        row, offset = {'_record_index': i}, 1
        for fld in fields:
            row[fld['name']] = decode_str(raw[offset:offset + fld['width']], encoding)
            offset += fld['width']
        records.append(row)
    summaries = []
    for fld in fields:
        vals = [r[fld['name']] for r in records]
        counts = Counter(vals)
        s = {**fld, 'empty_records': counts.get('', 0), 'distinct_count': len(counts),
             'examples': list(counts)[:5]}
        if len(counts) <= 40 or fld['type'] == 'D' or 'date' in fld['name'].lower():
            s['value_counts'] = dict(sorted(counts.items()))
        if fld['type'] in {'N', 'F'}:
            numbers = []
            for v in vals:
                try:
                    numbers.append(float(v))
                except ValueError:
                    pass
            s['parsed_numbers'] = len(numbers)
            if numbers:
                s.update(min=min(numbers), max=max(numbers))
        summaries.append(s)
    return {'path': str(path.relative_to(root)), 'record_count_header': n,
            'active_records': len(records), 'deleted_records': deleted,
            'record_length': record_len, 'header_length': header_len,
            'codepage_byte_hex': hex(b[29]), 'cpg': cpg_text, 'used_encoding': encoding,
            'fields': summaries, 'sample_records_first3': records[:3],
            'scan': 'all records, all fields'}, records


def shp_info(path, root):
    b = path.read_bytes()
    length = struct.unpack_from('>I', b, 24)[0] * 2
    shp_type = struct.unpack_from('<I', b, 32)[0]
    box = list(struct.unpack_from('<4d', b, 36))
    records = []
    cursor = 100
    while cursor < len(b):
        record_no, content_words = struct.unpack_from('>2I', b, cursor)
        content = b[cursor + 8:cursor + 8 + content_words * 2]
        st = struct.unpack_from('<I', content)[0]
        r = {'record_number': record_no, 'shape_type': st}
        if st in {3, 5, 13, 15, 23, 25, 31}:
            r['bounds'] = list(struct.unpack_from('<4d', content, 4))
            r['part_count'], r['point_count'] = struct.unpack_from('<2I', content, 36)
        elif st in {1, 11, 21}:
            x, y = struct.unpack_from('<2d', content, 4)
            r['bounds'] = [x, y, x, y]
            r['point_count'] = 1
        elif st != 0:
            r['unhandled_type'] = True
        records.append(r)
        cursor += 8 + content_words * 2
    prj = path.with_suffix('.prj')
    wkt = prj.read_text() if prj.exists() else None
    epsg = 4490 if wkt and 'China_Geodetic' in wkt else 4326 if wkt and 'WGS_1984' in wkt else None
    return {'path': str(path.relative_to(root)), 'shape_type': shp_type,
            'shape_type_name': {1: 'Point', 3: 'PolyLine', 5: 'Polygon', 15: 'PolygonZ'}.get(shp_type, 'other'),
            'record_count': len(records), 'bytes': len(b), 'header_declared_bytes': length,
            'header_length_matches': length == len(b),
            'bounds_left_bottom_right_top': box, 'crs_wkt': wkt,
            'epsg_inferred_from_wkt_name': epsg,
            'record_shape_types': dict(Counter(str(r['shape_type']) for r in records)),
            'total_vertices': sum(r.get('point_count', 0) for r in records),
            'scan': 'all binary record headers, part/vertex counts and record envelopes'}, records


def utm45_inverse(x, y):
    """WGS84 UTM45N inverse series for approximate coverage diagnostics only."""
    a, e2, k0 = 6378137., 0.0066943799901413165, .9996
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    ep2 = e2 / (1 - e2)
    mu = (y / k0) / (a * (1 - e2/4 - 3*e2**2/64 - 5*e2**3/256))
    fp = (mu + (3*e1/2 - 27*e1**3/32)*math.sin(2*mu)
          + (21*e1**2/16 - 55*e1**4/32)*math.sin(4*mu)
          + (151*e1**3/96)*math.sin(6*mu) + (1097*e1**4/512)*math.sin(8*mu))
    c, t = ep2*math.cos(fp)**2, math.tan(fp)**2
    n = a/math.sqrt(1-e2*math.sin(fp)**2)
    r = a*(1-e2)/(1-e2*math.sin(fp)**2)**1.5
    d = (x-500000)/(n*k0)
    lat = fp-(n*math.tan(fp)/r)*(d*d/2-(5+3*t+10*c-4*c*c-9*ep2)*d**4/24
                              +(61+90*t+298*c+45*t*t-252*ep2-3*c*c)*d**6/720)
    lon = math.radians(87)+(d-(1+2*t+c)*d**3/6
                             +(5-2*c+28*t-3*c*c+8*ep2+24*t*t)*d**5/120)/math.cos(fp)
    return math.degrees(lon), math.degrees(lat)


def approximate_geo_box(utm_box):
    l, b, r, t = utm_box
    pts = [utm45_inverse(x, y) for x in (l, (l+r)/2, r) for y in (b, (b+t)/2, t)]
    return [min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts)]


def nc_info(path, root):
    out = {'path': str(path.relative_to(root)), 'bytes': path.stat().st_size,
           'magic_hex': path.read_bytes()[:8].hex()}
    try:
        import xarray as xr
        with xr.open_dataset(path) as ds:
            out['xarray'] = {'opened': True, 'dimensions': dict(ds.sizes)}
    except Exception as e:
        out['xarray'] = {'opened': False, 'exception': f'{type(e).__name__}: {e}'}
    try:
        import h5py
        with h5py.File(path) as f:
            out['h5py_opened'] = True
            out['global_attributes'] = clean(dict(f.attrs))
            variables = []
            for name, d in f.items():
                dims = []
                if d.shape:
                    for dim in d.dims:
                        dims.append([v.name for v in dim.values()])
                attrs = {k: v for k, v in d.attrs.items() if k not in {'DIMENSION_LIST', 'REFERENCE_LIST'}}
                v = {'name': name, 'shape': list(d.shape), 'dtype': str(d.dtype),
                     'dimensions': dims, 'attributes': clean(attrs),
                     'statistics': array_stats(d[()], d.attrs.get('_FillValue'))}
                variables.append(v)
            out['variables'] = variables
            x, y = f['x'][()], f['y'][()]
            dx, dy = float(np.median(np.diff(x))), float(np.median(np.diff(y)))
            box = [float(x.min()-abs(dx)/2), float(y.min()-abs(dy)/2),
                   float(x.max()+abs(dx)/2), float(y.max()+abs(dy)/2)]
            auth = re.findall(r'AUTHORITY\["EPSG","(\d+)"\]', str(f['spatial_ref'].attrs['crs_wkt']))
            epsg = int(auth[-1]) if auth else None
            out.update(grid_shape_yx=[len(y), len(x)], pixel_size_xy_metres=[abs(dx), abs(dy)],
                       epsg=epsg, bounds_UTM_left_bottom_right_top=box,
                       approximate_bounds_WGS84=approximate_geo_box(box),
                       no_time_dimension=not any(name.lower() in {'time', 'date', 'datetime'} for name in f),
                       temporal_semantics='Velocity metadata: 2014-2024 climatology with 2018-01-01 intercept; no event-time series',
                       scan='all datasets, all numeric cells, all non-internal attributes')
            out['mask'] = array_stats(f['glacier_mask'][()])
            mask = np.isfinite(f['glacier_mask'][()]) & (f['glacier_mask'][()] > 0)
            out['on_positive_mask'] = {name: {'mask_cells': int(mask.sum()),
                                            'finite_cells': int((np.isfinite(f[name][()]) & mask).sum())}
                                       for name in ['dem', 'slope', 'thickness', 'v', 'vx', 'vy']}
    except Exception as e:
        out['h5py_exception'] = f'{type(e).__name__}: {e}'
    return out


def intersects(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def contains(box, x, y):
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def plot_coverage(output, rasters, coverage, historical_rows, station):
    """Static diagnostic, no basemap or claim of exact datum transformation."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False})
    dem = coverage['dem_bounds_WGS84']
    land = coverage['landcover_bounds_WGS84']
    nc = coverage['netcdf'][0]['approximate_bounds_WGS84']
    points = [(float(r['x_coord']), float(r['y_coord'])) for r in historical_rows]
    inside = [(x, y) for x, y in points if contains(dem, x, y)]
    outside = [(x, y) for x, y in points if not contains(dem, x, y)]
    fig, axes = plt.subplots(1, 2, figsize=(13.4, 7.5), gridspec_kw={'width_ratios': [1.15, 1]})
    colors = {'land': '#7a9e8b', 'dem': '#205f85', 'nc': '#b27936', 'inside': '#1d7b8a', 'outside': '#ba634b'}
    def box(ax, bounds, color, label, fill=False, linestyle='-'):
        l, b, r, t = bounds
        ax.add_patch(Rectangle((l,b), r-l, t-b, edgecolor=color,
                               facecolor=color if fill else 'none', alpha=.10 if fill else 1,
                               linewidth=1.8, linestyle=linestyle, label=label))
        if fill:
            ax.add_patch(Rectangle((l,b), r-l, t-b, edgecolor=color, facecolor='none', linewidth=1.8))
    for ax in axes:
        box(ax, land, colors['land'], 'Land-cover extent (2020-2023)', linestyle='--')
        box(ax, dem, colors['dem'], 'DEM extent; all cells valid', fill=True)
        box(ax, nc, colors['nc'], 'NC grid extent (approx. inverse UTM)', fill=True)
        ax.scatter(*zip(*outside), s=24, facecolors='none', edgecolors=colors['outside'],
                   linewidths=1.1, label=f'Historical representative points: outside DEM ({len(outside)})', zorder=4)
        ax.scatter(*zip(*inside), s=24, color=colors['inside'], edgecolor='white', linewidth=.35,
                   label=f'Historical representative points: inside DEM ({len(inside)})', zorder=5)
        ax.scatter([station[0]], [station[1]], marker='*', s=165, color='#493c72',
                   edgecolor='white', linewidth=.5, label='Station metadata: 85.29 E, 28.86 N', zorder=6)
        ax.set_xlabel('Longitude (degrees E)')
        ax.set_ylabel('Latitude (degrees N)')
        ax.grid(color='#dce1e4', linewidth=.6, zorder=0)
        ax.set_aspect(1/math.cos(math.radians(28.6)))
        ax.tick_params(axis='x', rotation=30)
    axes[0].set_xlim(84.40, 86.22)
    axes[0].set_ylim(28.19, 29.39)
    axes[0].set_title('A  County-scale coverage', loc='left', fontweight='bold', pad=12)
    axes[0].annotate('Station metadata location', xy=station, xytext=(85.48, 29.06),
                     arrowprops={'arrowstyle': '-', 'color': '#493c72'}, color='#493c72')
    axes[1].set_xlim(84.97, 85.75)
    axes[1].set_ylim(28.20, 29.06)
    axes[1].set_title('B  Historical inventory vs local DEM', loc='left', fontweight='bold', pad=12)
    axes[1].annotate('NC: 145 x 138 cells, 30 m\nNo time dimension\nLand cover: all NoData*', xy=((nc[0]+nc[2])/2, (nc[1]+nc[3])/2),
                     xytext=(85.35, 28.68), arrowprops={'arrowstyle':'-', 'color':colors['nc']},
                     color='#845d2b')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower left', bbox_to_anchor=(.045, .058), frameon=False,
               ncol=2, fontsize=9.5, columnspacing=2)
    fig.suptitle('Track B spatial data audit', x=.055, y=.98, ha='left', fontsize=18, fontweight='bold')
    fig.text(.055, .937, 'Source coverage is uneven: 22 / 84 supplied historical representative points fall inside the DEM extent.',
             ha='left', fontsize=11, color='#3e4b56')
    fig.text(.055, .023,
             'Diagnostic only: representative points are not polygon intersections. CGCS2000 vs WGS84 compared numerically; no datum transform.\n'
             '*7,152/7,152 NC-mask centers sample as land-cover NoData in all 4 years. Rectangles are envelopes; external station metadata not verified against CSV.',
             fontsize=9, color='#46515a', va='bottom')
    fig.subplots_adjust(left=.055, right=.975, bottom=.27, top=.87, wspace=.20)
    fig.savefig(output / 'spatial_coverage_diagnostic.png', dpi=180, facecolor='white')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, default=None)
    args = parser.parse_args()
    repo = args.repo.resolve()
    root = repo / '04_B赛道'
    output = args.output or repo / 'track_b/audit/spatial'
    output.mkdir(parents=True, exist_ok=True)
    dirs = sorted(d for d in root.iterdir() if d.is_dir() and d.name[:2] in {'03', '04', '05', '06', '07', '08'})
    files = sorted(p for d in dirs for p in d.rglob('*') if p.is_file())
    inventory = [{'path': str(p.relative_to(root)), 'directory': p.parent.name,
                  'suffix': p.suffix.lower(), 'bytes': p.stat().st_size,
                  'sha256': sha256(p)} for p in files]
    write_csv(output / 'file_inventory.csv', inventory)
    rasters = [raster_info(p, root) for p in files if p.suffix.lower() == '.tif']
    write_json(output / 'rasters.json', rasters)
    raster_rows = [{k: v for k, v in r.items() if k != 'geotiff_tags'} for r in rasters]
    write_csv(output / 'rasters.csv', raster_rows)
    vectors, dbfs, dbf_rows_by_stem, shp_rows_by_stem = [], [], {}, {}
    for p in files:
        if p.suffix.lower() == '.shp':
            info, rows = shp_info(p, root)
            vectors.append(info)
            shp_rows_by_stem[p.stem] = rows
            write_csv(output / (p.stem + '_geometry_envelopes.csv'), rows)
        elif p.suffix.lower() == '.dbf':
            info, rows = dbf_info(p, root)
            dbfs.append(info)
            dbf_rows_by_stem[p.stem] = rows
            write_csv(output / (p.stem + '_attributes.csv'), rows)
    write_json(output / 'vectors.json', vectors)
    write_json(output / 'vector_attributes.json', dbfs)
    netcdfs = [nc_info(p, root) for p in files if p.suffix.lower() == '.nc']
    write_json(output / 'netcdf.json', netcdfs)
    documents = []
    for p in files:
        if p.suffix.lower() == '.docx':
            with zipfile.ZipFile(p) as z:
                el = ET.fromstring(z.read('word/document.xml'))
                paragraphs = [''.join(t.text or '' for t in para.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
                              for para in el.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')]
                documents.append({'path': str(p.relative_to(root)), 'paragraphs': paragraphs,
                                  'scan': 'all word/document.xml paragraphs'})
        elif p.name.endswith('.xml'):
            el = ET.parse(p).getroot()
            selected = [{'tag': e.tag, 'text': e.text.strip(), 'attributes': dict(e.attrib)}
                        for e in el.iter() if e.text and e.text.strip()
                        and e.tag in {'Process', 'CreaDate', 'ModDate', 'SyncDate', 'source', 'srcdate', 'mdDateSt'}]
            documents.append({'path': str(p.relative_to(root)), 'selected_metadata_elements': selected,
                              'scan': 'all XML elements; selected process/date elements exported'})
    write_json(output / 'source_documentation.json', documents)
    groups = defaultdict(list)
    for r in rasters:
        if 'tile' in r:
            groups[(r['tile'], r['period_start'], r['period_end'])].append(r)
    pairs = []
    for key, rs in sorted(groups.items()):
        pairs.append({'tile': key[0], 'period_start': key[1], 'period_end': key[2],
                      'variant_counts': dict(Counter(r['variant'] for r in rs)),
                      'paths': [r['path'] for r in rs],
                      'interpretation': 'GCS and UTM are reprojection variants of the same signal; error is uncertainty, not an extra observation'})
    write_json(output / 'dhdt_source_groups.json', pairs)
    dem = next(r for r in rasters if r['path'].startswith('07_'))
    dem_box = dem['bounds_left_bottom_right_top']
    land = next(r for r in rasters if r['path'].startswith('05_'))
    land_box = land['bounds_left_bottom_right_top']
    coverage = {'dem_bounds_WGS84': dem_box,
                'landcover_bounds_WGS84': land_box,
                'method': 'Full set of vector record envelopes; no exact polygon clipping. Historical CGCS2000 degrees are compared numerically to WGS84 for coarse diagnostics only; no datum transformation performed.',
                'vectors': []}
    dem_array, _, _ = pixels(root / dem['path'])
    land_rasters = [r for r in rasters if r['path'].startswith('05_')]
    land_arrays = {r['path']: pixels(root/r['path'])[0] for r in land_rasters}
    for info in vectors:
        stem = Path(info['path']).stem
        rows, attrs = shp_rows_by_stem[stem], dbf_rows_by_stem.get(stem, [])
        matching = [r for r in rows if r.get('bounds') and intersects(r['bounds'], dem_box)]
        fully = [r for r in rows if r.get('bounds') and contains(dem_box, r['bounds'][0], r['bounds'][1])
                 and contains(dem_box, r['bounds'][2], r['bounds'][3])]
        v = {'path': info['path'], 'total_geometry_records': len(rows),
             'record_envelopes_intersecting_DEM': len(matching),
             'record_envelopes_fully_inside_DEM': len(fully),
             'record_envelopes_intersecting_landcover': sum(bool(r.get('bounds')) and intersects(r['bounds'], land_box) for r in rows)}
        representatives = []
        for row in attrs:
            x = row.get('x_coord') or row.get('cenlon') or row.get('CenLon') or row.get('Longitude')
            y = row.get('y_coord') or row.get('cenlat') or row.get('CenLat') or row.get('Latitude')
            try:
                x, y = float(x), float(y)
            except (ValueError, TypeError):
                continue
            inside = contains(dem_box, x, y)
            rr = {'record_index': row['_record_index'], 'x': x, 'y': y, 'inside_DEM_extent': inside}
            if inside:
                col = min(int((x-dem_box[0])/dem['pixel_size_xy'][0]), dem['width']-1)
                rn = min(int((dem_box[3]-y)/dem['pixel_size_xy'][1]), dem['height']-1)
                elev = float(dem_array[rn, col])
                rr['DEM_nearest_cell_valid'] = math.isfinite(elev) and elev != dem['nodata']
            for lr in land_rasters:
                year = Path(lr['path']).stem[-4:]
                lb = lr['bounds_left_bottom_right_top']
                rr[f'landcover_{year}_cell_valid'] = False
                if contains(lb, x, y):
                    lc = min(int((x-lb[0])/lr['pixel_size_xy'][0]), lr['width']-1)
                    ln = min(int((lb[3]-y)/lr['pixel_size_xy'][1]), lr['height']-1)
                    code = int(land_arrays[lr['path']][ln, lc])
                    rr[f'landcover_{year}_value'] = code
                    rr[f'landcover_{year}_cell_valid'] = code != lr['nodata']
            representatives.append(rr)
        if representatives:
            v.update(supplied_representative_points=len(representatives),
                     supplied_points_inside_DEM_extent=sum(r['inside_DEM_extent'] for r in representatives),
                     supplied_points_on_valid_DEM_cell=sum(r.get('DEM_nearest_cell_valid', False) for r in representatives))
            for lr in land_rasters:
                year = Path(lr['path']).stem[-4:]
                v[f'supplied_points_on_valid_landcover_{year}_cell'] = sum(r.get(f'landcover_{year}_cell_valid', False) for r in representatives)
            write_csv(output / (stem + '_representative_point_coverage.csv'), representatives)
        coverage['vectors'].append(v)
    coverage['netcdf'] = [{'path': n['path'], 'approximate_bounds_WGS84': n.get('approximate_bounds_WGS84'),
                           'approximate_extent_inside_DEM': bool(n.get('approximate_bounds_WGS84')) and
                           all(contains(dem_box, n['approximate_bounds_WGS84'][i], n['approximate_bounds_WGS84'][i+1]) for i in (0,2)),
                           'note': 'UTM inverse series applied to 3x3 edge/interior points for coarse bound check, not final geospatial preprocessing.'}
                          for n in netcdfs]
    nc_ids = ['RGI60-15.04172', 'RGI60-15.04173', 'RGI60-15.04174', 'RGI60-15.04175']
    source_glaciers = [r for r in dbf_rows_by_stem['RGI_V6_JilongFlood_Buffer_200km'] if r['RGIId'] in nc_ids]
    coverage['netcdf_glacier_mask_reference_crosscheck'] = {
        'referenced_RGI6_ids': nc_ids,
        'all_ids_found_in_supplied_RGI6': len(source_glaciers) == len(nc_ids),
        'RGI6_attribute_area_sum_km2': sum(float(r['Area']) for r in source_glaciers),
        'RGI6_attribute_records': source_glaciers,
        'NC_positive_mask_nominal_area_km2': netcdfs[0].get('on_positive_mask', {}).get('dem', {}).get('mask_cells', 0) * .0009,
        'interpretation': 'Attribute-ID and nominal-area checks only; not exact polygon-raster intersection or proof of DEM/velocity acquisition date.'}
    coverage['external_station_metadata'] = {
        'longitude': 85.29, 'latitude': 28.86,
        'catalog_mirror_url': 'https://gwfnet.net/Metadata/Index/T-2026-08-28-p1f3e5qIqTEyibfPAp3smBeA',
        'original_dataset_url': 'https://www.tpdc.ac.cn/zh-hans/data/5b09afd1-d11b-4150-a291-50f0484dddf1',
        'doi': '10.11888/Atmos.tpdc.303600',
        'local_CSV_version_hash_matched_to_external_dataset': False,
        'evidence_note': 'External station metadata supplied by the main audit; local CSV alone does not establish station location.'}
    if netcdfs and netcdfs[0].get('h5py_opened'):
        import h5py
        with h5py.File(root/netcdfs[0]['path']) as f:
            mask = f['glacier_mask'][()]
            xx, yy = f['x'][()], f['y'][()]
            indices = np.argwhere(np.isfinite(mask) & (mask > 0))
            centers = [utm45_inverse(float(xx[col]), float(yy[row])) for row, col in indices]
        samples = []
        for lr in land_rasters:
            lb = lr['bounds_left_bottom_right_top']
            codes = []
            outside = 0
            for x, y in centers:
                if contains(lb, x, y):
                    lc = min(int((x-lb[0])/lr['pixel_size_xy'][0]), lr['width']-1)
                    ln = min(int((lb[3]-y)/lr['pixel_size_xy'][1]), lr['height']-1)
                    codes.append(int(land_arrays[lr['path']][ln, lc]))
                else:
                    outside += 1
            samples.append({'landcover_path': lr['path'], 'mask_center_count': len(centers),
                            'outside_raster_extent': outside,
                            'valid_class_samples': sum(c != lr['nodata'] for c in codes),
                            'sample_code_counts': dict(Counter(str(c) for c in codes))})
        coverage['NC_positive_mask_to_landcover_sampling'] = {
            'method': 'All positive-mask UTM cell centers transformed with audit-only inverse series, sampled at containing land-cover cell; not exact polygon overlay or formal datum processing.',
            'results': samples}
    write_json(output / 'coverage.json', coverage)
    historical_stem = next(k for k in dbf_rows_by_stem if '历史灾点' in k)
    try:
        plot_coverage(output, rasters, coverage, dbf_rows_by_stem[historical_stem], (85.29, 28.86))
        coverage['diagnostic_figure'] = 'spatial_coverage_diagnostic.png'
    except Exception as e:
        coverage['diagnostic_figure_error'] = f'{type(e).__name__}: {e}'
    write_json(output / 'coverage.json', coverage)
    duplicates = defaultdict(list)
    for row in inventory:
        duplicates[row['sha256']].append(row['path'])
    summary = {'run_at_America_New_York': datetime.now(ZoneInfo('America/New_York')).isoformat(),
               'user_planning_date': '2026-10-23',
               'python': sys.executable, 'python_version': platform.python_version(),
               'scope': 'All regular files in Track B directories 03--08, excluding directory metadata',
               'source_files_modified': False,
               'file_count': len(files), 'bytes': sum(r['bytes'] for r in inventory),
               'directories': [{'directory': d.name, 'files': sum(p.parent == d for p in files),
                                'bytes': sum(p.stat().st_size for p in files if p.parent == d)} for d in dirs],
               'suffix_counts': dict(Counter(p.suffix.lower() for p in files)),
               'raster_count': len(rasters),
               'raster_all_cell_read_successes': sum('pixel_statistics' in r for r in rasters),
               'raster_all_cell_read_failures': [r['path'] for r in rasters if 'pixel_statistics' not in r],
               'raster_epsg_counts': dict(Counter(str(r['epsg']) for r in rasters)),
               'dhdt_groups': len(pairs), 'dhdt_variants': dict(Counter(r.get('variant') for r in rasters if 'variant' in r)),
               'dhdt_variant_incomplete_groups': [p for p in pairs if set(p['variant_counts']) != {'dhdt_UTM', 'dhdt_GCS', 'error_UTM'}],
               'dhdt_filename_anomalies': [r['path'] for r in rasters if '_dhdt5_' in r['path']],
               'byte_identical_file_groups': [v for v in duplicates.values() if len(v) > 1],
               'notes': ['Byte identity is not scientific independence; reprojections can differ in bytes and still be one source.',
                         'Directory and file creation dates do not establish acquisition or measurement dates.',
                         'Land-cover class names are not provided in the audited files; report numeric values pending official legend.',
                         'Historical image/interpretation dates cannot substitute for event occurrence timestamps.',
                         'County population is not village/building/grid exposure; two population-like fields require a dictionary.']}
    summary['source_sha256_recheck_mismatches'] = [r['path'] for r in inventory
                                                 if sha256(root/r['path']) != r['sha256']]
    write_json(output / 'summary.json', summary)
    print(json.dumps({'files': len(files), 'rasters': len(rasters),
                      'all_cell_reads': summary['raster_all_cell_read_successes'],
                      'vector_layers': len(vectors), 'netcdf_files': len(netcdfs),
                      'dhdt_groups': len(pairs), 'output': str(output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
