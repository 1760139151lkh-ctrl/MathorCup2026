"""Hash-bound Q4 candidate geometry / Q2 release coupling; immutable v2.

Only reads the advisor-delivered bundle's top-level file mapping, own Q2 v1,
and explicitly listed immutable DEM cache paths. No network or other worktree.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import Affine

HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
ROOT = HERE.parents[4]
EXPECTED_ROOT = Path("/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2")
GEOMETRY_BUNDLE = PACKET / "inputs/q4/bundle_q4-r3-spatial-copdem-v1-frozen-export/bundle.json"
GEOMETRY_SHA = "8eb6cbc1b85e60fe8a82906f4f025ec22b3bcf96d5c59bd0535ffbe0ccf8a0c5"
BASE_BUNDLE = PACKET / "exports/release_bundle.json"
V2_BUNDLE = PACKET / "exports/release_bundle_v2.json"
VERSION = "q2-r3-release-v2-spatial-copdem-v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return path.relative_to(ROOT).as_posix()


def resolve(path):
    candidate = Path(path)
    candidate = candidate if candidate.is_absolute() else ROOT / candidate
    candidate = candidate.resolve()
    allowed_cache = Path("/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/spatial")
    if not candidate.is_relative_to(PACKET) and not candidate.is_relative_to(allowed_cache):
        raise ValueError(f"unapproved input path: {candidate}")
    return candidate


def record(path, role, scope):
    return dict(path=str(path) if not path.is_relative_to(ROOT) else relative(path),
                bytes=path.stat().st_size, sha256=sha(path), role=role, actual_read_scope=scope)


def check_bundle(path, expected_sha=None):
    if expected_sha is not None and sha(path) != expected_sha:
        raise ValueError(f"bundle hash mismatch: {path}")
    data = json.loads(path.read_text())
    mapping = {}
    for item in data["files"]:
        target = resolve(item["path"])
        if target.stat().st_size != item["bytes"] or sha(target) != item["sha256"]:
            raise ValueError(f"bundle member mismatch: {target}")
        if item["role"] in mapping:
            raise ValueError(f"duplicate role: {item['role']}")
        mapping[item["role"]] = target
    return data, mapping


def emit(path, payload):
    """Never silently replace a previously released version."""
    path = path.resolve()
    if not path.is_relative_to(PACKET):
        raise ValueError("write outside own packet")
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f"immutable v2 output differs; use a new version: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def emit_json(path, value):
    emit(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def emit_csv(path, rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    emit(path, buffer.getvalue())


def raster_bytes(array, transform, volume, parameter_id, resolution):
    with MemoryFile() as memory:
        with memory.open(driver="GTiff", height=array.shape[0], width=array.shape[1],
                         count=1, dtype="float64", crs="EPSG:32645", transform=transform,
                         compress="deflate", nodata=None) as ds:
            ds.write(array.astype("float64"), 1)
            ds.update_tags(units="m", thickness_definition="vertical thickness above horizontal cell footprint",
                           evaluation_stratum="conditional_scenario", parameter_set_id=parameter_id,
                           release_volume_m3=f"{volume:.17g}", geometry_version="q4-r3-spatial-copdem-v1",
                           resolution_m=str(resolution), outside_mask="zero actual thickness; no nodata")
        return memory.read()


def main():
    if ROOT != EXPECTED_ROOT or Path.cwd().resolve() != ROOT:
        raise SystemExit("run from the assigned Q2 worktree only")
    geom, supplied = check_bundle(GEOMETRY_BUNDLE, GEOMETRY_SHA)
    base, parent = check_bundle(BASE_BUNDLE)
    release_path = parent["results/release_states.csv"]
    parameter_path = parent["results/parameter_ensemble.csv"]
    base_rows = list(csv.DictReader(io.StringIO(release_path.read_text())))
    parameter_rows = {r["scenario_id"]: r for r in csv.DictReader(io.StringIO(parameter_path.read_text()))}
    parameter_ids = list(dict.fromkeys(parameter_rows[r["scenario_id"]]["parameter_set_id"] for r in base_rows))
    assert len(base_rows) == 32 and len(parameter_ids) == 8
    assert len({r["scenario_id"] for r in base_rows}) == 32
    assert {r["mechanism_id"] for r in base_rows} == {"S", "S_T", "S_H", "S_T_H"}
    selected = parameter_ids[:2]
    terrain_bundle = json.loads(supplied["terrain_bundle"].read_text())
    grids, terrain_rows, inputs = {}, [], []
    for item in geom["files"]:
        inputs.append({**item, "actual_read_scope": "full bytes for hash; numerical content read for DEM/NPZ; terrain metadata read; geometry/path/figure content not used in calculations"})
    inputs += [record(GEOMETRY_BUNDLE, "advisor_delivered_geometry_bundle", "all JSON"),
               record(BASE_BUNDLE, "parent_release_v1_bundle", "all JSON and every member hash"),
               record(release_path, "parent_release_states", "all 32 scenarios"),
               record(parameter_path, "parent_parameter_grid", "all rows indexed; 32 release scenarios used")]
    for resolution in (60, 120):
        array_path = supplied[f"model_arrays_{resolution}m"]
        dem_path = supplied[f"primary_dem_{resolution}m"]
        with np.load(array_path, allow_pickle=False) as data:
            z = data["z"].astype(float)
            mask = data["source_mask"].astype(bool)
            assert set(np.unique(data["source_mask"])) <= {0, 1}
            dx = float(data["dx"])
            affine = Affine(*data["transform"][:6])
            x, y = data["x"], data["y"]
            assert str(data["geometry_version"]) == geom["geometry_version"]
        with rasterio.open(dem_path) as dem:
            assert dem.crs.to_string() == "EPSG:32645" and dem.transform == affine
            assert dem.shape == z.shape and np.array_equal(dem.read(1), z)
        assert dx == resolution and np.all(np.isfinite(z)) and mask.sum() > 0
        assert np.allclose(np.diff(x), dx) and np.allclose(np.diff(y), -dx)
        cell_area = abs(affine.a * affine.e - affine.b * affine.d)
        area = int(mask.sum()) * cell_area
        assert area == geom["grids"][str(resolution)]["source_raster_area_m2"]
        # Differentiate full valid DEM before masking, never the mask's cliff.
        gradient_y, gradient_x = np.gradient(z, y, x, edge_order=2)
        slope = np.degrees(np.arctan(np.hypot(gradient_x, gradient_y)))[mask]
        quantiles = np.quantile(slope, [0, .05, .25, .5, .75, .95, 1.])
        terrain_rows.append(dict(geometry_version=geom["geometry_version"], grid_resolution_m=resolution,
                                 source_cells=int(mask.sum()), source_plan_area_m2=area,
                                 elevation_min_m=float(z[mask].min()), elevation_max_m=float(z[mask].max()),
                                 slope_min_deg=float(quantiles[0]), slope_p05_deg=float(quantiles[1]),
                                 slope_p25_deg=float(quantiles[2]), slope_median_deg=float(quantiles[3]),
                                 slope_p75_deg=float(quantiles[4]), slope_p95_deg=float(quantiles[5]),
                                 slope_max_deg=float(quantiles[6]), slope_mean_deg=float(slope.mean()),
                                 slope_definition="arctan(norm(gradient DSM height)); cell-centred DEM surface, not structural sliding plane",
                                 evaluation_stratum="conditional_scenario"))
        grids[resolution] = dict(mask=mask, affine=affine, area=area, cell_area=cell_area,
                                 array_path=array_path, array_sha256=sha(array_path), shape=z.shape)
    emit_csv(PACKET / "results/geometry_integration_terrain.csv", terrain_rows)

    rows, checks, raster_paths = [], [], {}
    for original in base_rows:
        p = parameter_rows[original["scenario_id"]]
        parameter_id = p["parameter_set_id"]
        normal = float(p["thickness_normal_m"])
        theta = float(p["theta_deg"])
        rho = float(original["density"])
        vertical_60 = normal / np.cos(np.deg2rad(theta))
        assert np.isclose(vertical_60, float(original["release_thickness_vertical_m"]), rtol=1e-13)
        volume = grids[60]["area"] * vertical_60
        fractions = json.loads(original["phase_fractions"])
        assert original["phase_fraction_basis"] == "volume"
        assert all(value >= 0 for value in fractions.values()) and abs(sum(fractions.values()) - 1) < 1e-14
        velocity = json.loads(original["initial_velocity"])
        assert [velocity[axis] for axis in ("x", "y", "z")] == [0, 0, 0]
        assert "EPSG:32645" in velocity["crs"]
        assert np.isclose(rho, 2700 * fractions["rock"] + 917 * fractions["ice"], rtol=1e-13)
        phase_volumes = {key: volume * value for key, value in fractions.items()}
        phase_masses = {key: phase_volumes[key] * {"rock": 2700., "ice": 917., "free_water": 1000.}[key]
                        for key in fractions}
        for resolution, grid in grids.items():
            vertical = volume / grid["area"]
            raster = vertical * grid["mask"].astype(float)
            integrated_volume = float(raster.sum(dtype=float) * grid["cell_area"])
            mass = integrated_volume * rho
            assert abs(integrated_volume - volume) <= 1e-12 * volume
            assert abs(sum(phase_masses.values()) - mass) <= 1e-12 * mass
            raster_path = None
            if parameter_id in selected:
                raster_path = PACKET / f"results/release_thickness_{parameter_id}_{resolution}m_v2.tif"
                if raster_path not in raster_paths:
                    emit(raster_path, raster_bytes(raster, grid["affine"], volume, parameter_id, resolution))
                    with rasterio.open(raster_path) as ds:
                        assert ds.transform == grid["affine"] and ds.crs.to_string() == "EPSG:32645"
                        reread = ds.read(1)
                        assert np.array_equal(reread, raster)
                        assert abs(reread.sum() * grid["cell_area"] - volume) <= 1e-12 * volume
                    raster_paths[raster_path] = dict(parameter_set_id=parameter_id, resolution_m=resolution)
            spec = dict(mask_path=relative(grid["array_path"]), mask_array="source_mask",
                        mask_sha256=grid["array_sha256"],
                        release_thickness_raster_path=relative(raster_path) if raster_path else None,
                        constant_vertical_thickness_m=vertical, crs="EPSG:32645")
            rows.append(dict(scenario_id=f"{original['scenario_id']}__geomv2_{resolution}m",
                             base_scenario_id=original["scenario_id"], parameter_set_id=parameter_id,
                             model_id=original["model_id"], mechanism_id=original["mechanism_id"],
                             geometry_version=geom["geometry_version"], release_mapping_version=VERSION,
                             parameter_version=original["parameter_version"], grid_resolution_m=resolution,
                             source_polygon_or_release_raster=json.dumps(spec, separators=(",", ":")),
                             release_thickness_or_volume=json.dumps(dict(kind="constant_vertical_thickness_on_candidate_source_mask",
                                                                         vertical_thickness_m=vertical, volume_m3=volume), separators=(",", ":")),
                             source_mask_path=relative(grid["array_path"]), source_mask_array="source_mask",
                             release_raster_path=relative(raster_path) if raster_path else "",
                             plan_area_m2=grid["area"], mechanism_thickness_normal_m=normal,
                             mechanism_plane_theta_deg=theta,
                             release_thickness_vertical_m=vertical,
                             release_thickness_normal_equivalent_m=vertical*np.cos(np.deg2rad(theta)),
                             release_volume_m3=volume, integrated_volume_m3=integrated_volume,
                             density=rho, density_unit="kg m-3", release_mass_kg=mass,
                             phase_fraction_basis="volume", phase_fractions=json.dumps(fractions, separators=(",", ":")),
                             phase_volumes_m3=json.dumps(phase_volumes, separators=(",", ":")),
                             phase_masses_kg=json.dumps(phase_masses, separators=(",", ":")),
                             initial_velocity=original["initial_velocity"], onset_status=original["onset_status"],
                             data_role="scenario", evaluation_stratum="conditional_scenario",
                             provenance_and_assumptions="Q4 candidate mask, not observed release; V=A60*h_mechanism/cos(theta_mechanism), vertical thickness=V/Agrid. Preserve parent unit-area mechanism theta and thickness; 120m raster normalization is not a mechanism re-fit. Zero initial speed; free-water release fraction remains parent scenario zero; no reservoir-to-release-water inference. Propagation requires conditional release even for no-onset/left-censored parent states."))
            checks.append(dict(scenario_id=rows[-1]["scenario_id"], resolution_m=resolution,
                               volume_abs_error_m3=abs(integrated_volume-volume),
                               volume_relative_error=abs(integrated_volume-volume)/volume,
                               phase_mass_sum_relative_error=abs(sum(phase_masses.values())-mass)/mass))
    assert len(rows) == 64 and len(raster_paths) == 4
    for base_id in {row["base_scenario_id"] for row in rows}:
        pair = [row for row in rows if row["base_scenario_id"] == base_id]
        assert len(pair) == 2 and pair[0]["release_volume_m3"] == pair[1]["release_volume_m3"]
        assert np.isclose(pair[0]["release_mass_kg"], pair[1]["release_mass_kg"], rtol=1e-13)
    release_v2 = PACKET / "results/release_states_geometry_v2.csv"
    emit_csv(release_v2, rows)
    summary = dict(integration_version=VERSION, evaluation_stratum="conditional_scenario",
                   input_version=geom["input_version"], geometry_version=geom["geometry_version"],
                   geometry_bundle_sha256=GEOMETRY_SHA, parent_release_bundle_sha256=sha(BASE_BUNDLE),
                   parent_release_states_sha256=sha(release_path), inputs=inputs,
                   terrain_diagnostics=terrain_rows, release_rows=len(rows), base_release_rows=len(base_rows),
                   parameter_sets=parameter_ids, rasterized_parameter_sets=selected, rasters_written=len(raster_paths),
                   min_volume_m3=min(r["release_volume_m3"] for r in rows),
                   max_volume_m3=max(r["release_volume_m3"] for r in rows),
                   min_mass_kg=min(r["release_mass_kg"] for r in rows),
                   max_mass_kg=max(r["release_mass_kg"] for r in rows),
                   max_volume_relative_error=max(r["volume_relative_error"] for r in checks),
                   max_phase_mass_sum_relative_error=max(r["phase_mass_sum_relative_error"] for r in checks),
                   grid_volume_mass_checks=checks,
                   two_grid_volume_equality_passed=True, two_grid_mass_equality_passed=True,
                   preserved_parent_mechanism_parameters=True,
                   vertical_datum=terrain_bundle["vertical_datum"], observation_epoch=terrain_bundle["observation_epoch"],
                   scientific_adoption="pending_team_review", independent_events=0,
                   reproduction_command="track_b/.venv/bin/python track_b/research/q2/round3/scripts/integrate_geometry.py")
    summary_path = PACKET / "results/geometry_integration_summary.json"
    emit_json(summary_path, summary)
    doc_path = PACKET / "GEOMETRY_INTEGRATION.md"
    text = f"""# Q2—Q4 条件几何耦合 v2

使用主参谋批准分发的 `{geom['bundle_version']}`，入口 SHA256 `{GEOMETRY_SHA}`。所有8个顶层成员已逐文件核验；只读取本树副本和明确列出的只读地形缓存，不读取Q4活动工作树。保留v1发布文件原字节；本文件与独立`exports/release_bundle_v2.json`组成新增版本。

## 实际计算

- 60 m源mask：{terrain_rows[0]['source_cells']}格，水平面积{grids[60]['area']:.0f} m²；120 m：{terrain_rows[1]['source_cells']}格，面积{grids[120]['area']:.0f} m²，相差{(grids[120]['area']/grids[60]['area']-1)*100:.4f}%。这是同一候选几何栅格化差异。
- 两网格地形像元与交付NPZ逐值相等。完整DSM先计算`atan(norm(gradient(z)))`，再选mask；60/120 m源区地表坡度中位数分别为{terrain_rows[0]['slope_median_deg']:.4f}°/{terrain_rows[1]['slope_median_deg']:.4f}°，P05–P95分别{terrain_rows[0]['slope_p05_deg']:.4f}–{terrain_rows[0]['slope_p95_deg']:.4f}°/{terrain_rows[1]['slope_p05_deg']:.4f}–{terrain_rows[1]['slope_p95_deg']:.4f}°。地表坡度不是结构面倾角，没有替换或重新拟合父机制theta。
- 父接口8个预定参数×4机制=32个情景，扩展为64行。共同体积`V=A60*h_mechanism/cos(theta_mechanism)`，两个网格的垂直厚度分别`V/Agrid`。体积范围{summary['min_volume_m3']:.6f}–{summary['max_volume_m3']:.6f} m³；总体质量范围{summary['min_mass_kg']:.6f}–{summary['max_mass_kg']:.6f} kg。
- 全64行实际构造厚度数组并积分。最大体积相对误差{summary['max_volume_relative_error']:.3g}；组分质量和相对误差{summary['max_phase_mass_sum_relative_error']:.3g}。32对网格体积与质量一致。前2个预定参数`{selected[0]}`、`{selected[1]}`保存4张float64厚度GeoTIFF；各机制共享同参数初值栅格，其余情景明确给出mask路径、数组名和常数垂直厚度，可原样重建。
- 组分沿用父接口的体积分数，和为1；岩/冰相密度2700/917 kg m⁻³，体积加权总体密度与父参数一致。自由水相比例为父情景的0，**没有把H储水状态推算为释放自由水量**。全部初速度为EPSG:32645坐标下的零向量，方向无意义。

## 接口解释与限制

`base_scenario_id`精确指回父32条记录；新`scenario_id`添加`__geomv2_60m/120m`，`geometry_version={geom['geometry_version']}`。`mechanism_thickness_normal_m`与`mechanism_plane_theta_deg`保留父模型定义；`release_thickness_vertical_m`是用于栅格积分的厚度，`release_thickness_normal_equivalent_m`只表示按该假设倾角换算的等效量。120 m保持体积的厚度缩放不重新计算父单位面积稳定裕度。CSV中的`source_polygon_or_release_raster`为带mask和可选TIFF的JSON规格；未保存TIFF的情景仍有完整常数厚度定义。

mask是Q4按题图重建的条件源区候选，不能称为实测失稳面或反演体积。COPDEM是2011–2015主要获取、2021编辑发布的背景地形，垂直基准EGM2008，不能声称2026事件地形。此实验只证明几何、厚度、体积和组分质量的接口一致性，没有验证真实源区、体积、结构面、材料或启动时刻；不增加独立事件数，也不赋参数网格概率。保留父`onset_status`；从未越阈情景若用于传播，只表示外加假设释放，并不代表模型预测启动。

实际复跑命令（离线；输出版本已存在时只允许字节相同）：

```sh
track_b/.venv/bin/python track_b/research/q2/round3/scripts/integrate_geometry.py
```

逐情景误差、输入哈希见`results/geometry_integration_summary.json`；坡度分布见`results/geometry_integration_terrain.csv`。最终科学采用待队员联合审视。
"""
    emit(doc_path, text)
    files = [record(release_v2, "release_states_geometry_v2", "all 64 rows"),
             record(summary_path, "geometry_integration_checks", "all JSON"),
             record(PACKET / "results/geometry_integration_terrain.csv", "source_surface_slope_diagnostics", "two grids"),
             record(doc_path, "geometry_integration_methods_and_limits", "all text"),
             record(Path(__file__).resolve(), "geometry_integration_reproduction_script", "all code")]
    for path, properties in raster_paths.items():
        files.append(record(path, f"release_thickness_{properties['parameter_set_id']}_{properties['resolution_m']}m", "all raster pixels"))
    for resolution in grids:
        files.append(record(grids[resolution]["array_path"], f"source_mask_model_arrays_{resolution}m", "source_mask/grid/z arrays"))
    emit_json(V2_BUNDLE, dict(bundle_version=VERSION, producer_question="q2",
                             input_version=geom["input_version"], evaluation_stratum="conditional_scenario",
                             geometry_version=geom["geometry_version"], geometry_bundle_sha256=GEOMETRY_SHA,
                             parent_release_bundle_version=base["bundle_version"], parent_release_bundle_sha256=sha(BASE_BUNDLE),
                             files=[{key: value for key, value in f.items() if key != "actual_read_scope"} for f in files],
                             limitations=["All geometry/thickness/composition/release states are conditional scenarios, not measured source initial conditions.",
                                          "Surface slope is distinct from assumed structural plane angle; no mechanism parameters refitted.",
                                          "Two grids share fixed volume; 120m constant vertical thickness normalized by its source-mask horizontal area.",
                                          "Zero initial velocity and zero free-water release fraction are explicit inherited scenarios, not inferred from background velocity or reservoir state.",
                                          "No-start/left-censored parent trajectories retained; propagation from them requires additional conditional release, not predicted onset.",
                                          "No parameter probabilities; no independent observed events; human scientific adoption pending."]))
    print(json.dumps(dict(bundle=relative(V2_BUNDLE), bundle_sha256=sha(V2_BUNDLE), rows=len(rows), rasters=len(raster_paths),
                          source_slope_median_deg=[r["slope_median_deg"] for r in terrain_rows],
                          max_volume_relative_error=summary["max_volume_relative_error"])))


if __name__ == "__main__":
    main()
