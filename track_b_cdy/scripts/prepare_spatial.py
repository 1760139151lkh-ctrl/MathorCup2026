#!/usr/bin/env python3
"""Formal GIS minimum loop, diagnostics only; no hazard model or event inference.

AI-assisted implementation: OpenAI Codex. Human review of source geography,
datum tolerances, product semantics and adoption is required. Originals are read
only. Run from any working directory with track_b/.venv/bin/python.
"""
from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyproj
from pyproj.transformer import TransformerGroup
import rasterio
from rasterio.features import geometry_mask, shapes
from rasterio.transform import Affine, array_bounds, from_origin
from rasterio.warp import Resampling, calculate_default_transform, reproject
from rasterio.windows import Window, from_bounds
import shapely
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union
import xarray as xr
import h5netcdf

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "04_B赛道"
TRACK = ROOT / "track_b"
OUT = TRACK / "data/processed/spatial"
POLICY_PATH = TRACK / "config/spatial_policy.json"
POLICY = json.loads(POLICY_PATH.read_text())
WORK_CRS = pyproj.CRS(POLICY["work_crs"])
OPERATIONS = {}
TRANSFORMERS = {}
SOURCES = {}


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(x) for x in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def dump(name, data):
    (OUT / name).write_text(json.dumps(clean(data), ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def register(path):
    key = str(path.relative_to(ROOT))
    SOURCES[key] = {"bytes": path.stat().st_size, "sha256": digest(path)}
    return key


def transformer(src, dst):
    src, dst = pyproj.CRS(src), pyproj.CRS(dst)
    key = f"{src.to_string()} -> {dst.to_string()}"
    if key in TRANSFORMERS:
        return TRANSFORMERS[key]
    group = TransformerGroup(src, dst, always_xy=True, allow_ballpark=True)
    if not group.transformers:
        raise RuntimeError(f"No coordinate operation: {key}")
    op = group.transformers[0]
    if key not in OPERATIONS:
        ballpark = any(x.has_ballpark_transformation for x in op.operations)
        strict = TransformerGroup(src, dst, always_xy=True, allow_ballpark=False)
        OPERATIONS[key] = {
            "source_wkt": src.to_wkt(), "target_wkt": dst.to_wkt(),
            "always_xy": True, "description": op.description,
            "definition": op.definition, "reported_accuracy_metres": op.accuracy,
            "contains_ballpark_transformation": ballpark,
            "best_available": group.best_available,
            "non_ballpark_operation_count": len(strict.transformers),
            "unavailable_operations": [{"name": x.name, "accuracy": x.accuracy,
                "grids": [{"short_name": g.short_name, "available": g.available} for g in x.grids]}
                for x in group.unavailable_operations],
            "interpretation": "-1 accuracy means unknown, not zero error. Ballpark operations cannot support survey-grade alignment. No vertical transform is requested."
        }
    TRANSFORMERS[key] = op
    return op


def project_geometry(geom, src, dst, densify=True):
    if geom is None or geom.is_empty:
        return geom
    geom = shapely.force_2d(geom)
    if densify and pyproj.CRS(src).is_geographic:
        geom = shapely.segmentize(geom, POLICY["geometry"]["geographic_edge_densification_max_degrees"])
    return shapely.transform(geom, transformer(src, dst).transform, interleaved=False)


def raster_meta(ds):
    return {"crs": ds.crs.to_string(), "crs_wkt": ds.crs.to_wkt(),
            "shape_yx": [ds.height, ds.width], "transform_affine_gdal": ds.transform.to_gdal(),
            "bounds_left_bottom_right_top": list(ds.bounds), "resolution_xy": ds.res,
            "dtype": ds.dtypes[0], "nodata": ds.nodata, "tags": ds.tags()}


def stats(arr, valid=None):
    a = np.asarray(arr)
    valid = np.isfinite(a) if valid is None else valid & np.isfinite(a)
    values = a[valid]
    return {"total_cells": a.size, "valid_cells": int(valid.sum()),
        "min": float(values.min()) if values.size else None,
        "max": float(values.max()) if values.size else None,
        "mean": float(values.mean()) if values.size else None}


def write_tif(name, arr, transform, crs, nodata, semantic, sources):
    path = OUT / name
    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0],
            count=1, dtype=arr.dtype, crs=crs, transform=transform, nodata=nodata,
            compress="DEFLATE") as dst:
        dst.write(arr, 1)
        dst.update_tags(semantic=semantic, sources=json.dumps(sources, ensure_ascii=False),
                        vertical_datum="unknown; no vertical transformation", policy=str(POLICY_PATH.relative_to(ROOT)))
    with rasterio.open(path) as ds:
        return raster_meta(ds)


def samples(ds, x, y, src_crs):
    px, py = transformer(src_crs, ds.crs).transform(x, y)
    rows, cols = rasterio.transform.rowcol(ds.transform, px, py)
    rows, cols = np.asarray(rows), np.asarray(cols)
    inside = (rows >= 0) & (rows < ds.height) & (cols >= 0) & (cols < ds.width)
    data = ds.read(1)
    valid = np.zeros(len(px), dtype=bool)
    values = np.full(len(px), np.nan)
    values[inside] = data[rows[inside], cols[inside]]
    valid[inside] = ds.read_masks(1)[rows[inside], cols[inside]] > 0
    valid &= np.isfinite(values)
    return values, valid, inside


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("[spatial] imports ready; reading five vector datasets", flush=True)
    register(POLICY_PATH)
    register(Path(__file__).resolve())
    report = {"purpose": "stage3 formal GIS minimum processing loop and coverage diagnostics; not a validated hazard domain",
        "software": {"python": platform.python_version(), "rasterio": rasterio.__version__,
                     "gdal": rasterio.__gdal_version__, "pyproj": pyproj.__version__,
                     "proj": pyproj.proj_version_str, "geopandas": gpd.__version__,
                     "shapely": shapely.__version__, "xarray": xr.__version__, "h5netcdf": h5netcdf.__version__},
        "policy": POLICY, "vectors": [], "rasters": {}, "warnings": []}

    # 1. Read all vector features formally; planar copies deliberately drop Z.
    transformer("EPSG:4490", "EPSG:4326")  # Explicit datum-only capability probe.
    vectors = {}
    for path in sorted(BASE.rglob("*.shp")):
        for sidecar in sorted(path.parent.glob(path.stem + ".*")):
            if sidecar.suffix.lower() in {".shp", ".shx", ".dbf", ".prj", ".cpg"}:
                register(sidecar)
        gdf = gpd.read_file(path, engine="pyogrio")
        invalid = ~gdf.geometry.is_valid
        derived = gdf.copy()
        derived["source_record_index"] = np.arange(len(gdf))
        derived["source_geometry_valid"] = ~invalid
        derived.geometry = derived.geometry.map(lambda x: shapely.force_2d(shapely.make_valid(x)) if not x.is_valid else shapely.force_2d(x))
        src_crs = gdf.crs
        derived.geometry = derived.geometry.map(lambda x: project_geometry(x, src_crs, WORK_CRS))
        derived = derived.set_crs(WORK_CRS, allow_override=True)
        projected_invalid = ~derived.geometry.is_valid
        before_repair_areas = derived.geometry.area.copy()
        projected_invalid_records = [{"source_record_index": int(i), "reason": shapely.is_valid_reason(derived.geometry.iloc[i])}
                                     for i in np.flatnonzero(projected_invalid.to_numpy())]
        derived.loc[projected_invalid, "geometry"] = derived.loc[projected_invalid, "geometry"].map(shapely.make_valid)
        key = "history" if "历史灾点" in str(path) else "population" if "人口普查" in str(path) else "rgi_v6" if "V6" in path.stem else "rgi_v7" if "V7" in path.stem else "buffer_200km"
        vectors[key] = derived
        report["vectors"].append({"key": key, "source": str(path.relative_to(ROOT)), "records": len(gdf),
            "source_crs": src_crs.to_string(), "source_geometry_types": gdf.geom_type.value_counts().to_dict(),
            "source_geometry_with_z": int(gdf.geometry.has_z.sum()), "source_invalid_geometry_count": int(invalid.sum()),
            "source_invalid_records": [{"source_record_index": int(i), "reason": shapely.is_valid_reason(gdf.geometry.iloc[i])}
                for i in np.flatnonzero(invalid.to_numpy())],
            "projected_invalid_before_repair": int(projected_invalid.sum()),
            "projected_invalid_records_before_repair": projected_invalid_records,
            "post_projection_repair_max_absolute_area_change_m2": float((derived.geometry.area - before_repair_areas).abs().max()),
            "derived_invalid_geometry_count": int((~derived.geometry.is_valid).sum()),
            "null_empty_count": int((derived.geometry.isna() | derived.geometry.is_empty).sum()),
            "projected_bounds": derived.total_bounds.tolist()})
    assert len(vectors) == 5
    print("[spatial] vectors read and projected; processing DEM", flush=True)

    # 2. Read native DEM with raster masks; derive valid footprint independently.
    dem_path = next(p for p in BASE.rglob("DEM.tif"))
    for path in sorted(dem_path.parent.glob(dem_path.stem + ".*")):
        register(path)
    with rasterio.open(dem_path) as src:
        dem = src.read(1)
        dem_valid = (src.read_masks(1) > 0) & np.isfinite(dem)
        dem_crs, dem_tf, dem_bounds = src.crs, src.transform, src.bounds
        report["rasters"]["native_dem"] = {"source": str(dem_path.relative_to(ROOT)), **raster_meta(src), **stats(dem, dem_valid)}
        native_footprint = box(*src.bounds)
        valid_shapes = [shape(g) for g, v in shapes(dem_valid.astype("uint8"), mask=dem_valid, transform=src.transform) if v == 1]
        native_valid_footprint = unary_union(valid_shapes)
        dem_footprint = project_geometry(native_footprint, src.crs, WORK_CRS)
        dem_valid_footprint = project_geometry(native_valid_footprint, src.crs, WORK_CRS)
        dem_dest_tf, dem_width, dem_height = calculate_default_transform(src.crs, WORK_CRS,
            src.width, src.height, *src.bounds, resolution=POLICY["dem"]["output_grid_metres"])
        dem_dest = np.full((dem_height, dem_width), POLICY["dem"]["output_nodata"], dtype="float32")
        reproject(source=dem, destination=dem_dest, src_transform=src.transform, src_crs=src.crs,
            src_nodata=src.nodata, dst_transform=dem_dest_tf, dst_crs=WORK_CRS,
            dst_nodata=POLICY["dem"]["output_nodata"], resampling=Resampling.bilinear)
    report["rasters"]["dem_utm45_30m"] = write_tif("dem_utm45_30m.tif", dem_dest, dem_dest_tf, WORK_CRS,
        POLICY["dem"]["output_nodata"], "continuous elevation; bilinear target sampling 30m; unknown vertical datum", [str(dem_path.relative_to(ROOT))])
    report["rasters"]["dem_utm45_30m"].update(stats(dem_dest, dem_dest != POLICY["dem"]["output_nodata"]))

    # 3. Exact planar intersections, area and native centre/touched pixel support.
    hist = vectors["history"]
    rows = []
    for idx, row in hist.iterrows():
        geom = row.geometry
        intersect = geom.intersection(dem_footprint)
        valid_intersect = geom.intersection(dem_valid_footprint)
        # This raster count is intentionally separate from polygon intersection area.
        native_geom = project_geometry(geom, WORK_CRS, dem_crs)
        center = geometry_mask([mapping(native_geom)], out_shape=dem.shape, transform=dem_tf, invert=True, all_touched=False)
        touched = geometry_mask([mapping(native_geom)], out_shape=dem.shape, transform=dem_tf, invert=True, all_touched=True)
        rr = {"source_record_index": int(row.source_record_index), "Code": row.get("Code"),
            "polygon_area_m2": geom.area, "dem_footprint_intersection_area_m2": intersect.area,
            "dem_valid_footprint_intersection_area_m2": valid_intersect.area,
            "dem_footprint_intersects": geom.intersects(dem_footprint),
            "dem_positive_area_overlap": intersect.area > 0,
            "dem_footprint_covers_polygon": dem_footprint.covers(geom),
            "fraction_polygon_area_on_dem": valid_intersect.area / geom.area if geom.area else None,
            "native_grid_center_selected_cells": int(center.sum()),
            "native_grid_center_selected_valid_cells": int((center & dem_valid).sum()),
            "native_grid_all_touched_cells": int(touched.sum()),
            "native_grid_all_touched_valid_cells": int((touched & dem_valid).sum())}
        rows.append(rr)
    coverage = pd.DataFrame(rows)
    coverage.to_csv(OUT / "history_dem_coverage.csv", index=False)
    print("[spatial] historical polygon intersection and raster-support counts ready", flush=True)
    # Keep original attributes in the GeoPackage and append only diagnostic columns.
    hist = hist.merge(coverage.drop(columns="Code"), on="source_record_index", validate="one_to_one")
    report["historical_inventory_coverage"] = {"records": len(hist),
        "footprint_intersects": int(coverage.dem_footprint_intersects.sum()),
        "positive_area_overlap": int(coverage.dem_positive_area_overlap.sum()),
        "fully_covered_by_dem_footprint": int(coverage.dem_footprint_covers_polygon.sum()),
        "with_native_valid_center_cells": int((coverage.native_grid_center_selected_valid_cells > 0).sum()),
        "with_native_valid_all_touched_cells": int((coverage.native_grid_all_touched_valid_cells > 0).sum()),
        "sum_inventory_polygon_area_m2": coverage.polygon_area_m2.sum(),
        "sum_intersection_area_m2": coverage.dem_valid_footprint_intersection_area_m2.sum(),
        "inventory_union_area_m2": hist.geometry.union_all().area,
        "inventory_union_on_dem_area_m2": hist.geometry.union_all().intersection(dem_valid_footprint).area,
        "warning": "Per-polygon area sums can double-count overlaps. These are spatial inventory diagnostics, not event-time training labels. Centre and all-touched counts are raster support, not exact polygon area."}

    # 4. CF decoding and georeferenced export of supplied NC, with explicit orientation.
    nc_path = next(BASE.rglob("*.nc"))
    register(nc_path)
    with xr.open_dataset(nc_path, engine="h5netcdf", decode_cf=False, mask_and_scale=False) as raw_ds:
        raw = raw_ds.load()
    with xr.open_dataset(nc_path, engine="h5netcdf", decode_cf=True, mask_and_scale=True, decode_coords="all") as decoded_ds:
        nc = decoded_ds.load()
    nc = nc.sortby("x", ascending=True).sortby("y", ascending=False)
    x, y = nc.x.values, nc.y.values
    dx, dy = float(np.diff(x)[0]), float(-np.diff(y)[0])
    assert np.allclose(np.diff(x), dx) and np.allclose(-np.diff(y), dy)
    nc_tf = from_origin(float(x[0] - dx / 2), float(y[0] + dy / 2), dx, dy)
    nc_crs = pyproj.CRS.from_wkt(nc.spatial_ref.attrs.get("crs_wkt", nc.spatial_ref.attrs.get("spatial_ref")))
    assert nc_crs == WORK_CRS
    nc_dem = nc.dem.transpose("y", "x").values.astype("float32")
    nc_mask = np.isfinite(nc.glacier_mask.values) & (nc.glacier_mask.values > 0)
    mask_rows, mask_cols = np.where(nc_mask)
    mask_x, mask_y = x[mask_cols], y[mask_rows]
    nc_footprint = box(*array_bounds(len(y), len(x), nc_tf))
    nc_mask_geom = unary_union([shape(g) for g, v in shapes(nc_mask.astype("uint8"), mask=nc_mask, transform=nc_tf) if v == 1])
    report["netcdf"] = {"source": str(nc_path.relative_to(ROOT)), "engine": "h5netcdf", "decode_cf": True,
        "decode_coords": "all", "mask_and_scale": True, "dimensions": dict(nc.sizes),
        "coordinates": list(nc.coords), "no_time_dimension": "time" not in nc.dims,
        "global_attributes": dict(nc.attrs), "crs": nc_crs.to_string(), "transform_affine_gdal": nc_tf.to_gdal(),
        "bounds_left_bottom_right_top": list(nc_footprint.bounds), "resolution_metres_xy": [dx, dy],
        "native_x_order": "increasing" if np.diff(raw.x.values).mean() > 0 else "decreasing",
        "native_y_order": "increasing" if np.diff(raw.y.values).mean() > 0 else "decreasing",
        "export_order": "x increasing / y decreasing; arrays sorted with coordinates",
        "positive_mask_cells": int(nc_mask.sum()), "positive_mask_area_m2": nc_mask_geom.area,
        "mask_covered_by_native_dem_valid_footprint": dem_valid_footprint.covers(nc_mask_geom),
        "mask_area_on_native_dem_m2": nc_mask_geom.intersection(dem_valid_footprint).area,
        "full_nc_grid_covered_by_native_dem_valid_footprint": dem_valid_footprint.covers(nc_footprint),
        "variable_decode_checks": {}}
    for name in nc.data_vars:
        if nc[name].ndim != 2:
            continue
        v = nc[name].values
        r = raw[name].sortby("x", ascending=True).sortby("y", ascending=False).values
        report["netcdf"]["variable_decode_checks"][name] = {"attrs_after_decoding": nc[name].attrs,
            "raw_fill_value": raw[name].attrs.get("_FillValue"),
            "raw_scale_factor": raw[name].attrs.get("scale_factor"), "raw_add_offset": raw[name].attrs.get("add_offset"),
            "raw_and_decoded_equal_nan": bool(np.array_equal(r, v, equal_nan=True)),
            "decoded_statistics": stats(v), "finite_on_positive_mask": int(np.isfinite(v[nc_mask]).sum())}
    report["rasters"]["nc_dem_native_grid"] = write_tif("nc_dem_native_grid.tif", nc_dem, nc_tf, nc_crs, np.nan,
        "continuous elevation exported without resampling; vertical datum unverified", [str(nc_path.relative_to(ROOT))])
    report["rasters"]["nc_glacier_mask"] = write_tif("nc_glacier_mask.tif", nc_mask.astype("uint8"), nc_tf, nc_crs, 0,
        "categorical positive mask exported without resampling; not confirmed event failure boundary", [str(nc_path.relative_to(ROOT))])
    dem_on_nc = np.full(nc_dem.shape, -9999, dtype="float32")
    with rasterio.open(dem_path) as src:
        reproject(source=rasterio.band(src, 1), destination=dem_on_nc, src_transform=src.transform,
            src_crs=src.crs, src_nodata=src.nodata, dst_transform=nc_tf, dst_crs=nc_crs,
            dst_nodata=-9999, resampling=Resampling.bilinear)
        dv, valid, inside = samples(src, mask_x, mask_y, nc_crs)
    report["rasters"]["dem_on_nc_grid"] = write_tif("dem_on_nc_grid.tif", dem_on_nc, nc_tf, nc_crs, -9999,
        "continuous native DEM bilinear to supplied NC parameter grid", [str(dem_path.relative_to(ROOT)), str(nc_path.relative_to(ROOT))])
    difference = dem_on_nc - nc_dem
    comparison_valid = (dem_on_nc != -9999) & np.isfinite(nc_dem)
    report["netcdf"]["dem_comparison"] = {"positive_mask_native_dem_inside_cells": int(inside.sum()),
        "positive_mask_native_dem_valid_cells": int(valid.sum()), "whole_nc_grid_valid_dem_cells": int(comparison_valid.sum()),
        "whole_grid_local_dem_minus_nc_dem_m": stats(difference, comparison_valid),
        "mask_local_dem_minus_nc_dem_m": stats(difference, comparison_valid & nc_mask),
        "interpretation": "Differences combine unknown product, date, vertical datum, resolution and interpolation effects; not an accuracy or co-registration validation."}
    print("[spatial] CF NetCDF decoding and DEM-to-NC grid complete", flush=True)

    # 5. Formal all-mask-cell native class sampling, plus nearest-neighbour export.
    landcover_reports = []
    for path in sorted(BASE.glob("05*/*.tif")):
        register(path)
        arr = np.zeros(nc_dem.shape, dtype="uint8")
        with rasterio.open(path) as src:
            values, valid, inside = samples(src, mask_x, mask_y, nc_crs)
            reproject(source=rasterio.band(src, 1), destination=arr, src_transform=src.transform,
                src_crs=src.crs, src_nodata=src.nodata, dst_transform=nc_tf, dst_crs=nc_crs,
                dst_nodata=0, resampling=Resampling.nearest)
            item = {"source": str(path.relative_to(ROOT)), "metadata": raster_meta(src),
                "positive_nc_mask_centres": len(mask_x), "inside_native_extent": int(inside.sum()),
                "native_valid_class_samples": int(valid.sum()),
                "sample_numeric_code_counts": {str(int(c)): int(n) for c, n in zip(*np.unique(values[inside], return_counts=True))},
                "nearest_nc_grid_valid_on_positive_mask": int(((arr > 0) & nc_mask).sum())}
        name = f"{path.stem}_nc_grid_nearest.tif"
        report["rasters"][path.stem] = write_tif(name, arr, nc_tf, nc_crs, 0,
            "categorical codes; nearest resampling only; 0=NoData; class legend unverified", [str(path.relative_to(ROOT))])
        landcover_reports.append(item)
    report["landcover_source_grid_coverage"] = landcover_reports
    print("[spatial] four categorical nearest-neighbour samples complete", flush=True)

    # 6. GeoPackage keeps only source vicinity RGI, plus whole historical inventory.
    gpkg = OUT / "spatial_diagnostic.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    hist.to_file(gpkg, layer="historical_inventory_diagnostic", driver="GPKG", engine="pyogrio")
    vectors["population"].to_file(gpkg, layer="population_boundary", driver="GPKG", engine="pyogrio")
    rgi_local = vectors["rgi_v6"][vectors["rgi_v6"].intersects(nc_footprint.buffer(1000))].copy()
    rgi_local.to_file(gpkg, layer="rgi6_near_nc_grid", driver="GPKG", engine="pyogrio")
    gpd.GeoDataFrame({"kind": ["dem_outer_footprint", "dem_valid_pixel_footprint", "nc_grid_footprint", "nc_positive_glacier_mask"]},
        geometry=[dem_footprint, dem_valid_footprint, nc_footprint, nc_mask_geom], crs=WORK_CRS).to_file(
        gpkg, layer="coverage_footprints", driver="GPKG", engine="pyogrio")
    report["geopackage"] = {"layers": {"historical_inventory_diagnostic": len(hist), "population_boundary": 1,
            "rgi6_near_nc_grid": len(rgi_local), "coverage_footprints": 4},
        "planar_geometry": "source Z dropped only in derived copies; all layers EPSG:32645"}

    # 7. Source-grid neighborhood validity is not a source-to-port routing test.
    report["terrain_continuity"] = {"native_dem_valid_pixels": int(dem_valid.sum()),
        "native_dem_total_pixels": dem_valid.size, "native_dem_internal_invalid_pixels": int((~dem_valid).sum()),
        "full_nc_parameter_grid_covered": dem_valid_footprint.covers(nc_footprint),
        "nc_positive_mask_covered": dem_valid_footprint.covers(nc_mask_geom),
        "verified_port_protection_point": None, "verified_channel_centreline": None,
        "source_to_port_continuity_verified": False,
        "reason": "No traceable port target coordinate or verified river path is available to this work package. Full rectangular DEM validity establishes local grid support only, not downstream route coverage or hydrologic correctness.",
        "required_next_inputs": ["Port protection point with source and positional uncertainty", "Event failure polygon independent of RGI parameter mask", "Source-to-port river centreline and required corridor buffer", "DEM product/date/vertical reference and hydrologic conditioning review"]}
    report["warnings"] = [
        "CGCS2000 to WGS84 is ballpark in this PROJ environment; reported operation accuracy is unknown and no non-ballpark operation is available.",
        "Local NC grid is supported by valid DEM cells, but confirmed event failure polygon, port target and full propagation channel remain unavailable.",
        "Every positive NC glacier-mask centre is NoData in all four supplied land-cover rasters; reprojection cannot create coverage.",
        "The separate DEM and NC DEM disagree materially; their product, date and vertical reference remain unverified and they must not be silently merged.",
        "Two source RGI6 geometries and 16 post-projection RGI7 geometries needed make_valid on derived 2D copies; repair details are recorded."
    ]

    # 8. Static QA plot: layout explicitly distinguishes regional and local views.
    fig, axes = plt.subplots(1, 3, figsize=(17, 6), constrained_layout=True)
    ax = axes[0]
    hist.plot(ax=ax, facecolor="#d87459", edgecolor="#a64e39", linewidth=0.35, alpha=.65)
    gpd.GeoSeries([dem_footprint], crs=WORK_CRS).boundary.plot(ax=ax, color="#204e73", linewidth=1.5)
    gpd.GeoSeries([nc_footprint], crs=WORK_CRS).boundary.plot(ax=ax, color="#192024", linewidth=1.5)
    ax.set_title("Historical polygons and DEM footprint\n84 inventory polygons; no event-time labels")
    ax.set_xlabel("Easting (m)"); ax.set_ylabel("Northing (m)")
    ax.text(.02,.02,"Blue: DEM | Black: NC grid", transform=ax.transAxes, fontsize=9)
    ax = axes[1]
    valid_dem_dest = np.ma.masked_equal(dem_dest, -9999)
    bounds = array_bounds(dem_height, dem_width, dem_dest_tf)
    im = ax.imshow(valid_dem_dest, extent=[bounds[0],bounds[2],bounds[1],bounds[3]], cmap="terrain", origin="upper")
    gpd.GeoSeries([nc_mask_geom], crs=WORK_CRS).boundary.plot(ax=ax, color="#b9204b", linewidth=1)
    hist[hist.intersects(dem_footprint)].boundary.plot(ax=ax, color="#242f3c", linewidth=.5)
    ax.set_title("DEM reprojected to UTM 45N / 30 m\nBilinear; vertical datum unknown")
    ax.set_xlabel("Easting (m)"); ax.set_ylabel("Northing (m)")
    fig.colorbar(im, ax=ax, shrink=.7, label="Elevation (source metres)")
    ax = axes[2]
    b = nc_footprint.bounds
    im = ax.imshow(nc_dem, extent=[b[0],b[2],b[1],b[3]], cmap="terrain", origin="upper")
    gpd.GeoSeries([nc_mask_geom], crs=WORK_CRS).boundary.plot(ax=ax, color="#b9204b", linewidth=1)
    ax.set_title("Supplied NC source-parameter grid\n7,152 mask cells; LC valid: 0 in each year")
    ax.set_xlabel("Easting (m)"); ax.set_ylabel("Northing (m)")
    fig.colorbar(im, ax=ax, shrink=.7, label="NC DEM (m; datum unverified)")
    for ax in axes:
        ax.ticklabel_format(style="plain", useOffset=False)
        ax.tick_params(axis="x", labelrotation=30)
        ax.grid(alpha=.16)
    fig.suptitle("Formal GIS minimum loop — coverage diagnostics, not confirmed event source or flow path", fontsize=15)
    fig.savefig(OUT / "spatial_pipeline_qa.png", dpi=160, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)

    # Re-open every written spatial artifact and record checked properties.
    verified = []
    for path in sorted(OUT.glob("*.tif")):
        with rasterio.open(path) as ds:
            arr = ds.read(1)
            assert ds.crs == rasterio.crs.CRS.from_epsg(32645)
            if path.name == "nc_dem_native_grid.tif":
                assert np.array_equal(arr, nc_dem, equal_nan=True)
                assert np.allclose(ds.xy(0, 0), (x[0], y[0]))
            if path.name == "nc_glacier_mask.tif":
                assert np.array_equal(arr, nc_mask.astype("uint8"))
            verified.append({"file": path.name, "readback_ok": True, **raster_meta(ds),
                "valid_mask_cells": int((ds.read_masks(1) > 0).sum())})
    layer_readback = {}
    for layer, count in report["geopackage"]["layers"].items():
        gdf = gpd.read_file(gpkg, layer=layer, engine="pyogrio")
        assert len(gdf) == count and gdf.crs.to_epsg() == 32645
        layer_readback[layer] = {"records": len(gdf), "valid_geometry_count": int(gdf.is_valid.sum())}
    report["verification"] = {"raster_readbacks": verified, "geopackage_readbacks": layer_readback,
        "figure_visual_inspection": "Generation alone is not visual verification. See separate visual_review.json when present, and require its recorded figure hash to match the current figure."}
    dump("coordinate_operations.json", OPERATIONS)
    report["coordinate_operations_file"] = "coordinate_operations.json"
    report["source_integrity_after_run"] = {k: digest(ROOT / k) == v["sha256"] for k, v in SOURCES.items()}
    assert all(report["source_integrity_after_run"].values())
    dump("source_manifest.json", SOURCES)
    dump("pipeline_report.json", report)
    manifest = {p.name: {"bytes": p.stat().st_size, "sha256": digest(p)} for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "output_manifest.json"}
    dump("output_manifest.json", manifest)
    print(json.dumps(clean({"outputs": str(OUT), "vectors": len(vectors),
        "history": report["historical_inventory_coverage"], "nc_mask": report["netcdf"]["positive_mask_cells"],
        "landcover_valid": [i["native_valid_class_samples"] for i in landcover_reports],
        "native_source_hashes_unchanged": all(report["source_integrity_after_run"].values())}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
