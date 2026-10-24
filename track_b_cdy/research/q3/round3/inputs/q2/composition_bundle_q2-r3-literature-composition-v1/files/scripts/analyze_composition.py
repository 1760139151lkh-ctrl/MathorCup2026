"""Independent, paired extension of the immutable thermal125v2 composition domain.

First run --prepare to register the protocol and source/mapping record; --run
then performs 8 fixed representatives x2 compositions x4 mechanisms x2 laws.
Published v1/v2 outputs, bundles, figures and manifests are read-only. There is
no event-time selection or fitting and no assigned probability weights.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import time
from datetime import datetime, UTC

sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

from mechanism_engine import G, MARGIN_DEFINITION, classify_trajectory, resistance, simulate, stresses, thermal_transfer

ROOT = Path(__file__).resolve().parents[5]
BASE = ROOT / "track_b/research/q2/round3"
OUT = BASE / "results/composition_sensitivity"
V2 = BASE / "results/refined_v2"
REPS = [0, 36, 72, 109, 145, 182, 218, 255]
FRACTIONS = [0.85, 0.90]
ENGINE_SHA = "bb6636d2d3f463c894cdc6bc1df9c7fd0f93f9b7a6f9aa6e8233113630afe14e"
EXPERIMENT = "q2r3-composition-domain-extension-v1"
PARAMETER_VERSION = "q2r3-design-v1-composition-extension-v1"
ADVISOR_EXCERPT = "当前rock体积分数0.2–0.8未覆盖他已读JMS源区103.35Mm3中ice12.6/rock90.75(ice12.2%)、另一原摘要ice10–15%。都是事后文献候选不是实测定值。"


def digest(path, role):
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "role": role}


def emit(path, raw):
    allowed = path.resolve().is_relative_to(OUT.resolve()) or path == BASE / "COMPOSITION_SENSITIVITY.md"
    if not allowed:
        raise ValueError("outside independent composition package")
    raw = raw.encode() if isinstance(raw, str) else raw
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f"existing composition output differs; preserve and version separately: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def json_emit(path, value):
    emit(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def csv_emit(path, frame):
    emit(path, frame.to_csv(index=False, lineterminator="\n"))


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"): self.skip = True
    def handle_endtag(self, tag):
        if tag in ("script", "style"): self.skip = False
    def handle_data(self, text):
        if not self.skip and text.strip(): self.parts.append(text.strip())


def input_files():
    return [(BASE / "scripts/mechanism_engine.py", "unchanged_model_engine"),
            (Path(__file__), "independent_composition_script"),
            (V2 / "config.json", "thermal125v2_frozen_config"),
            (V2 / "forcing_hourly_v2.csv", "same_frozen_hourly_forcing"),
            (V2 / "parameter_ensemble.csv", "same_v2_design_and_original_composition"),
            (V2 / "scenario_outcomes.csv", "existing_64_paired_baseline_outcomes_from_2048"),
            (V2 / "state_trajectories.parquet", "existing_64_representative_baseline_state_paths"),
            (ROOT / "track_b/research/q2/sources/jms_abstract.html", "frozen_round1_JMS_abstract_snapshot"),
            (ROOT / "track_b/research/q2/sources/yin_abstract.html", "frozen_round1_Yin_abstract_snapshot"),
            (ROOT / "track_b/research/q2/sources/mechanism_reading.json", "frozen_round1_source_acquisition_record"),
            (BASE / "inputs/q3/event_bundle_q3-r3-event-v1-local/files/exports/event_v1/label_mapping.csv", "advisor_delivered_Q3_candidate_reference_URLs")]


def prepare():
    assert Path.cwd().resolve() == ROOT
    assert digest(BASE / "scripts/mechanism_engine.py", "engine")["sha256"] == ENGINE_SHA
    protocol_path = OUT / "protocol.json"
    registered = json.loads(protocol_path.read_text())["registered_at_utc"] if protocol_path.exists() else datetime.now(UTC).isoformat()
    read_record = json.loads((ROOT / "track_b/research/q2/sources/mechanism_reading.json").read_text())
    sources = []
    for name, expected, needles, interpretation in [
        ("jms_abstract", "6cf316f8d40fee7d48ab40f9a62699a867cf632ef5ca17bcfe56a5df7ca04b41",
         ["~103", "~12.6"], "local frozen abstract supports rounded total~103Mm3 and ice~12.6Mm3 (~12%); exact103.35/90.75 not verified in abstract"),
        ("yin_abstract", "7e7312b13c0c7acd39d68810fdbe78863ea8c836837d38aaac34a5f5879da56c",
         ["10%～15%", "10%–15%"], "local frozen Chinese and English abstracts state ice content10%-15%; not a locally measured fraction")]:
        path = ROOT / f"track_b/research/q2/sources/{name}.html"
        record = next(r for r in read_record["records"] if r["source_id"] == name)
        item = digest(path, "retrospective_literature_candidate")
        assert item["sha256"] == expected == record["sha256"]
        html = PlainHTML(); html.feed(path.read_text()); text = " ".join(html.parts)
        assert all(needle in text for needle in needles)
        excerpts = []
        for needle in needles:
            at = text.index(needle)
            excerpts.append(text[max(0, at-45):at+len(needle)+65])
        sources.append({**item, "canonical_url_or_product_id": record["url"],
                        "product_version": "round1 frozen publisher abstract HTML; full article not reread",
                        "retrieved_at_utc": record["retrieved_at_utc"],
                        "actual_read_scope": "this subexperiment: relevant complete abstract locally parsed and read, no new download or full-paper reading",
                        "small_local_locator_contexts": excerpts,
                        "interpretation": interpretation, "data_role": "scenario",
                        "available_time_or_unknown": "retrospective paper candidate; not accepted as antecedent operational input"})
    protocol = {
        "protocol_version": EXPERIMENT + "-preregistered", "registered_at_utc": registered,
        "baseline_commit": "904d7257b899b9f71d1ac9e0eab7479e459eab52",
        "selection_rule": "8 original predeclared index representatives, not selected by outcomes or reconstructed event time",
        "representative_parameter_indices": REPS, "rock_volume_fractions": FRACTIONS,
        "mechanisms": ["S", "S_T", "S_H", "S_T_H"],
        "strength_policies": ["linear_extension", "thawed_rock_contact"],
        "new_full_state_integrations": 128, "existing_paired_baseline_paths": 64,
        "baseline_reintegrations_planned": 0, "dt_hours": 1.0, "dz_m": 0.125,
        "thermal_bottom_m": 40.0, "same_forcing": True,
        "density_mapping": "rho=917*(1-rock_volume_fraction)+2700*rock_volume_fraction kg/m3; same two-solid no-void/no-liquid mixture as v2",
        "composition_to_structure_mapping": "release-scale total rock/ice fraction is conditionally homogenized into plane-slab density; not evidence of the actual sliding interface",
        "bridge_fraction_mapping": "unchanged independently sampled load-bearing area fraction; never equated to total rock volume fraction",
        "paired_invariants": "all parameters except rock_volume_fraction and its deterministic density transform; alpha/thermal depth/water/bridge/damage parameters unchanged",
        "omitted_composition_couplings": "thermal diffusivity, latent heat, roughness, bridge area and drainage are not automatically changed by this one-factor density experiment",
        "advisor_provided_candidate": {"instruction_excerpt": ADVISOR_EXCERPT,
            "instruction_excerpt_sha256": hashlib.sha256(ADVISOR_EXCERPT.encode()).hexdigest(),
            "total_Mm3": 103.35, "ice_Mm3": 12.6, "rock_Mm3": 90.75,
            "derived_ice_volume_fraction": 12.6/103.35, "derived_rock_volume_fraction": 90.75/103.35,
            "provenance_status": "exact volumes supplied by main advisor dispatch; not verified against full paper in this subexperiment"},
        "source_records": sources,
        "source_use": "retrospective composition candidates motivate domain extension only; not measured constants, calibration labels or validation events",
        "time_window": "same v2 2026-06-01T00:00Z..2026-08-27T00:00Z; evaluation start2026-08-19T00:00Z",
        "output_metrics": ["rho", "normal/driving/effective stresses", "all/evaluation/initial/final margin", "critical-head values and domain/root-status", "all onset categories including no-start/left-censor", "temperature/effective-stress joint-domain fractions", "paired changes"],
        "evaluation_stratum": "conditional_scenario", "comparison_stratum": "numerical_benchmark",
        "data_role": "scenario", "forecast_input_mode": "ideal_weather", "independent_events": 0,
        "probabilities_assigned": False, "weights": None, "event_time_fitting": False,
        "validation": "verify published v2 baseline states algebraically without reintegration; unchanged engine/input hashes; paired invariants; full128 count; finite states and mass balance; preserve null roots and no-start/left-censor",
        "inputs": [digest(p, role) for p, role in input_files()],
    }
    json_emit(protocol_path, protocol)
    print(json.dumps({"registered_protocol": str(protocol_path.relative_to(ROOT)), "sha256": digest(protocol_path,"protocol")["sha256"], "new_integrations_planned":128}), flush=True)


def finite_stat(values, which):
    x = np.asarray(values, float); x = x[np.isfinite(x)]
    return float(getattr(np, which)(x)) if len(x) else None


def metrics(sid, base_sid, pid, mechanism, policy, parameters, ti, damage, pressure, margin, critical, domain, forcing, ev, group):
    onset = classify_trajectory(margin)
    late = classify_trajectory(margin[ev:])
    state = resistance(parameters, damage, ti, pressure, policy)
    normal, drive = stresses(parameters)
    eff = np.asarray(state["effective_kpa"])
    root = np.asarray(state["critical_head_status"])
    return dict(scenario_id=sid, baseline_scenario_id=base_sid, parameter_set_id=pid,
        mechanism_id=mechanism, law_policy=policy, composition_group=group,
        experiment_id=EXPERIMENT, geometry_version="conditional_plane_slab_v1",
        parameter_version=PARAMETER_VERSION if group != "v2_original_paired_subset" else "q2r3-design-v1",
        density_kg_m3=float(parameters["density_kg_m3"]), rock_volume_fraction=float(parameters["rock_volume_fraction"]),
        bridge_fraction=float(parameters["bridge_fraction"]), normal_kpa=float(normal), driving_kpa=float(drive),
        initial_effective_kpa=float(eff[0]), min_effective_kpa=float(eff.min()), max_effective_kpa=float(eff.max()),
        initial_margin=float(margin[0]), min_margin_all=float(margin.min()),
        min_margin_evaluation=float(margin[ev:].min()), final_margin=float(margin[-1]),
        final_interface_temp_c=float(ti[-1]), final_damage=float(damage[-1]),
        peak_pressure_kpa=float(pressure.max()), min_critical_head_m=finite_stat(critical,"min"),
        max_critical_head_m=finite_stat(critical,"max"),
        initial_critical_head_m=float(critical[0]) if np.isfinite(critical[0]) else None,
        final_critical_head_m=float(critical[-1]) if np.isfinite(critical[-1]) else None,
        finite_critical_head_fraction=float(np.isfinite(critical).mean()),
        initial_critical_head_status=str(root[0]), final_critical_head_status=str(root[-1]),
        strength_domain_fraction=float(np.asarray(domain).mean()),
        temperature_in_lab_domain_fraction=float(((ti>=-8)&(ti<=-.5)).mean()),
        effective_stress_in_lab_domain_fraction=float(((eff>=100)&(eff<=400)).mean()),
        effective_stress_below100_fraction=float((eff<100).mean()), effective_stress_above400_fraction=float((eff>400).mean()),
        contact_valid_fraction=float((eff>0).mean()), evaluation_onset_status=late["onset_status"],
        crossing_time_utc=(forcing.time_utc.iloc[0]+pd.Timedelta(hours=onset["onset_elapsed_hours"])).isoformat() if onset["onset_elapsed_hours"] is not None else None,
        **onset, evaluation_stratum="conditional_scenario", data_role="scenario", forecast_input_mode="ideal_weather", independent_events=0)


def run():
    started=time.perf_counter()
    protocol=json.loads((OUT/"protocol.json").read_text())
    for row in protocol["inputs"]:
        path=ROOT/row["path"]
        assert path.stat().st_size==row["bytes"] and digest(path,row["role"])["sha256"]==row["sha256"], row["path"]
    cfg=json.loads((V2/"config.json").read_text())
    assert cfg["dz_m"]==.125 and cfg["dt_hours"]==1.0
    forcing=pd.read_csv(V2/"forcing_hourly_v2.csv",parse_dates=["time_utc"])
    assert len(forcing)==2089 and (forcing.time_utc.diff().dropna()==pd.Timedelta(hours=1)).all()
    ev=int(np.flatnonzero(forcing.time_utc>=cfg["evaluation_start_utc"])[0])
    allparams=pd.read_csv(V2/"parameter_ensemble.csv")
    params=allparams[(allparams.mechanism_id=="S")&(allparams.law_policy=="linear_extension")].copy()
    pids=[f"q2r3-p{i:04d}" for i in REPS]
    params=params.set_index("parameter_set_id").loc[pids]
    names=list(cfg["ranges"])+["density_kg_m3"]
    original={name:params[name].to_numpy() for name in names}
    baseline_outcomes=pd.read_csv(V2/"scenario_outcomes.csv")
    baseline_outcomes=baseline_outcomes[baseline_outcomes.parameter_set_id.isin(pids)].copy()
    assert len(baseline_outcomes)==64
    tracks=pd.read_parquet(V2/"state_trajectories.parquet")
    baseline_records=[]; max_baseline_algebra_error=0.
    for row in baseline_outcomes.to_dict("records"):
        j=pids.index(row["parameter_set_id"])
        one={k:float(v[j]) for k,v in original.items()}
        path=tracks[tracks.scenario_id==row["scenario_id"]].sort_values("elapsed_hours")
        assert len(path)==len(forcing)
        state=resistance(one,path.damage.to_numpy(),path.interface_temp_c.to_numpy(),path.pressure_kpa.to_numpy(),row["law_policy"])
        error=float(np.abs(state["failure_margin"]-path.failure_margin.to_numpy()).max())
        max_baseline_algebra_error=max(max_baseline_algebra_error,error)
        assert error<1e-10
        record=metrics(row["scenario_id"],row["scenario_id"],row["parameter_set_id"],row["mechanism_id"],row["law_policy"],one,
            path.interface_temp_c.to_numpy(),path.damage.to_numpy(),path.pressure_kpa.to_numpy(),path.failure_margin.to_numpy(),
            path.critical_head_m.to_numpy(),path.strength_in_lab_domain.to_numpy(),forcing,ev,"v2_original_paired_subset")
        assert record["onset_status"]==row["onset_status"]
        for key in ["initial_margin","min_margin_all","min_margin_evaluation","final_margin","strength_domain_fraction"]:
            assert abs(record[key]-row[key])<1e-10
        baseline_records.append(record)
    baseline=pd.DataFrame(baseline_records)
    csv_emit(OUT/"baseline_outcomes_64.csv",baseline)

    newp={name:np.tile(v,2) for name,v in original.items()}
    newp["rock_volume_fraction"]=np.repeat(FRACTIONS,len(REPS))
    newp["density_kg_m3"]=917*(1-newp["rock_volume_fraction"])+2700*newp["rock_volume_fraction"]
    for name in names:
        if name not in ["rock_volume_fraction","density_kg_m3"]:
            np.testing.assert_array_equal(newp[name],np.tile(original[name],2))
    air=forcing.station_air_temp_c.to_numpy(); rain=forcing.precip_assumed_mm_h.to_numpy()
    thermal=thermal_transfer(air,newp,1.,.125,40.)
    rows=[]; parameter_rows=[]; newtracks=[]; max_water_error=0.; max_temp_difference=0.
    for policy in protocol["strength_policies"]:
        for mechanism in protocol["mechanisms"]:
            result=simulate(air,rain,newp,mechanism,policy,thermal=thermal)
            assert np.isfinite(result["failure_margin"]).all()
            max_water_error=max(max_water_error,float(result["water_budget_max_abs_m"].max()))
            for j in range(16):
                idx=j%8; pid=pids[idx]; frac=FRACTIONS[j//8]; label=f"composition{int(round(frac*100)):03d}"
                old=baseline[(baseline.parameter_set_id==pid)&(baseline.mechanism_id==mechanism)&(baseline.law_policy==policy)].iloc[0]
                sid=f"{old.scenario_id}__{label}"; one={k:float(v[j]) for k,v in newp.items()}
                oldtrack=tracks[tracks.scenario_id==old.scenario_id].sort_values("elapsed_hours")
                temp_error=float(np.abs(result["interface_temp_c"][:,j]-oldtrack.interface_temp_c.to_numpy()).max())
                max_temp_difference=max(max_temp_difference,temp_error);assert temp_error<1e-10
                rec=metrics(sid,old.scenario_id,pid,mechanism,policy,one,
                    result["interface_temp_c"][:,j],result["damage"][:,j],result["pressure_kpa"][:,j],
                    result["failure_margin"][:,j],result["critical_head_m"][:,j],result["strength_domain"][:,j],forcing,ev,label)
                rows.append(rec)
                parameter_rows.append(dict(scenario_id=sid,baseline_scenario_id=old.scenario_id,parameter_set_id=pid,
                    mechanism_id=mechanism,law_policy=policy,parameter_version=PARAMETER_VERSION,composition_group=label,
                    original_rock_volume_fraction=float(original["rock_volume_fraction"][idx]),
                    original_density_kg_m3=float(original["density_kg_m3"][idx]),prior_weight=None,
                    design_role="paired_domain_extension_not_probability",evaluation_stratum="conditional_scenario",**one))
                state=resistance(one,result["damage"][:,j],result["interface_temp_c"][:,j],result["pressure_kpa"][:,j],policy)
                newtracks.append(pd.DataFrame(dict(scenario_id=sid,baseline_scenario_id=old.scenario_id,parameter_set_id=pid,
                    mechanism_id=mechanism,law_policy=policy,composition_group=label,time_utc=forcing.time_utc,
                    elapsed_hours=forcing.elapsed_hours,failure_margin=result["failure_margin"][:,j],margin_definition=MARGIN_DEFINITION,
                    interface_temp_c=result["interface_temp_c"][:,j],damage=result["damage"][:,j],storage_m=result["storage_m"][:,j],
                    pressure_kpa=result["pressure_kpa"][:,j],normal_kpa=state["normal_kpa"],driving_kpa=state["driving_kpa"],
                    effective_kpa=state["effective_kpa"],critical_head_m=result["critical_head_m"][:,j],
                    critical_head_status=state["critical_head_status"],strength_in_lab_domain=result["strength_domain"][:,j],
                    contact_valid=state["contact_valid"],onset_status_whole_run=rec["onset_status"],
                    evaluation_stratum="conditional_scenario",data_role="scenario",forecast_input_mode="ideal_weather")))
            print(f"Composition complete: {policy} {mechanism},16 new paths",flush=True)
    outcomes=pd.DataFrame(rows); parameters=pd.DataFrame(parameter_rows)
    assert len(outcomes)==128 and outcomes.scenario_id.is_unique
    csv_emit(OUT/"parameter_ensemble_128.csv",parameters)
    csv_emit(OUT/"scenario_outcomes_128.csv",outcomes)
    import io
    buf=io.BytesIO();pd.concat(newtracks,ignore_index=True).to_parquet(buf,index=False,compression="zstd")
    emit(OUT/"state_trajectories_128.parquet",buf.getvalue())
    paired=outcomes.merge(baseline,left_on="baseline_scenario_id",right_on="scenario_id",suffixes=("_new","_baseline"),validate="many_to_one")
    deltas=paired[["scenario_id_new","baseline_scenario_id_new","parameter_set_id_new","mechanism_id_new","law_policy_new","composition_group_new"]].copy()
    metrics_list=["rock_volume_fraction","density_kg_m3","bridge_fraction","normal_kpa","driving_kpa","min_effective_kpa","max_effective_kpa",
        "initial_margin","min_margin_all","min_margin_evaluation","final_margin","peak_pressure_kpa","final_damage",
        "initial_critical_head_m","final_critical_head_m","finite_critical_head_fraction","strength_domain_fraction",
        "effective_stress_in_lab_domain_fraction","effective_stress_above400_fraction"]
    for key in metrics_list:
        deltas[key+"_baseline"]=paired[key+"_baseline"]
        deltas[key+"_new"]=paired[key+"_new"]
        deltas[key+"_delta_new_minus_baseline"]=paired[key+"_new"]-paired[key+"_baseline"]
    for key in ["onset_status","evaluation_onset_status","initial_critical_head_status","final_critical_head_status","onset_elapsed_hours"]:
        deltas[key+"_baseline"]=paired[key+"_baseline"]
        deltas[key+"_new"]=paired[key+"_new"]
    deltas["onset_category_changed"]=paired.onset_status_new!=paired.onset_status_baseline
    deltas["onset_elapsed_hours_delta"]=paired.onset_elapsed_hours_new-paired.onset_elapsed_hours_baseline
    deltas["evaluation_stratum"]="numerical_benchmark";deltas["independent_events"]=0
    csv_emit(OUT/"paired_changes_128.csv",deltas)
    combined=pd.concat([baseline,outcomes],ignore_index=True)
    comparisons=[]
    for (group,mechanism,policy), subset in combined.groupby(["composition_group","mechanism_id","law_policy"],sort=False):
        comparisons.append(dict(composition_group=group,mechanism_id=mechanism,law_policy=policy,n_scenarios=len(subset),
            interval_crossing_n=int((subset.onset_status=="interval_crossing").sum()),
            left_censored_n=int(subset.onset_status.str.startswith("left_censored").sum()),
            never_crossed_n=int((subset.onset_status=="never_crossed").sum()),
            missing_n=int(subset.onset_status.str.contains("missing").sum()),
            median_min_margin_evaluation=float(subset.min_margin_evaluation.median()),
            mean_lab_domain_fraction=float(subset.strength_domain_fraction.mean()),
            wholly_lab_domain_n=int((subset.strength_domain_fraction==1).sum()),
            evaluation_stratum="conditional_scenario",independent_events=0,probabilities_assigned=False))
    csv_emit(OUT/"comparison_by_mechanism.csv",pd.DataFrame(comparisons))
    bycomposition=[]
    for group, subset in outcomes.groupby("composition_group",sort=False):
        d=deltas[deltas.composition_group_new==group]
        bycomposition.append(dict(composition_group=group,n_integrations=len(subset),
            onset_counts=subset.onset_status.value_counts().to_dict(),
            onset_category_changed_n=int(d.onset_category_changed.sum()),
            median_delta_min_margin_evaluation=float(d.min_margin_evaluation_delta_new_minus_baseline.median()),
            min_delta_min_margin_evaluation=float(d.min_margin_evaluation_delta_new_minus_baseline.min()),
            max_delta_min_margin_evaluation=float(d.min_margin_evaluation_delta_new_minus_baseline.max()),
            mean_delta_lab_domain_fraction=float(d.strength_domain_fraction_delta_new_minus_baseline.mean()),
            mean_new_lab_domain_fraction=float(subset.strength_domain_fraction.mean()),
            wholly_lab_domain_n=int((subset.strength_domain_fraction==1).sum())))
    summary=dict(experiment_id=EXPERIMENT,new_integrations=128,existing_baseline_paths=64,baseline_reintegrations=0,
        new_state_rows=len(forcing)*128,representative_indices=REPS,rock_volume_fractions=FRACTIONS,
        density_kg_m3=[917*(1-r)+2700*r for r in FRACTIONS],dt_hours=1.,dz_m=.125,
        by_composition=bycomposition,onset_category_changed_total=int(deltas.onset_category_changed.sum()),
        max_baseline_state_algebra_margin_error=max_baseline_algebra_error,
        max_new_vs_baseline_interface_temperature_difference_c=max_temp_difference,
        max_water_balance_residual_m=max_water_error,
        all_noncomposition_parameters_pairwise_unchanged=True,bridge_area_fraction_unchanged=True,
        protocol_sha256=digest(OUT/"protocol.json","protocol")["sha256"],engine_sha256=ENGINE_SHA,
        independent_events=0,probabilities_assigned=False,event_time_fitting=False,
        evaluation_stratum="conditional_scenario",comparison_stratum="numerical_benchmark",
        commands=["track_b/.venv/bin/python track_b/research/q2/round3/scripts/analyze_composition.py --prepare",
                  "track_b/.venv/bin/python track_b/research/q2/round3/scripts/analyze_composition.py --run"],
        limitations=["retrospective literature candidate composition; exact103.35/90.75 advisor-provided only, no full-paper reread",
                    "bulk source material conditionally homogenized into plane slab; total rock volume is not bridge area",
                    "density-only composition intervention; no automatic thermal/hydraulic/strength composition remapping",
                    "8 fixed paired representatives, not rerun2048; no inferred probabilities or event-time calibration",
                    "increasing density can move effective stress beyond Mamot100-400kPa domain; domain fractions retained"])
    assert max_water_error<1e-10
    for row in protocol["inputs"]:
        assert digest(ROOT/row["path"],row["role"])["sha256"]==row["sha256"],"published input changed during subexperiment"
    summary["all_consumed_published_inputs_unchanged"]=True
    json_emit(OUT/"summary.json",summary)
    lines=["# 组成参数域扩展的配对敏感性实验", "",
        "独立补充包；不替换已发布v1/v2接口、图表和manifest。先登记protocol.json再计算，128条新完整状态轨迹均已实际积分；原v2预定8索引×4机制×2策略的64条轨迹只读作配对基线，未重跑全部2048。", "",
        "固定代表索引为[0,36,72,109,145,182,218,255]；岩石整体体积分数分别改为0.85和0.90，密度按原两固相无孔隙映射为2432.55和2521.7kg/m³。岩桥面积分数fb及其他参数逐项保持不变；两者不是同一物理量。热网格dz=0.125m、小时步长、2089时刻和气象映射均与v2一致。", "",
        "## 来源与物理映射", "",
        "本轮重新读取的是本树冻结R1两篇中英摘要和获批Q3标签映射中的URL：", "",
        "- [JMS论文](https://jms.imde.ac.cn/en/article/doi/10.1007/s11629-026-1482-y)摘要支持约103Mm³总量、冰约12.6Mm³（约12%）；103.35/90.75Mm³精细值来自主参谋派单，本子实验未核全文，不能称本轮原文复核。",
        "- [殷等论文](https://zgdzzhyfzxb.com/article/doi/10.16031/j.cghc.202610008?viewType=HTML)冻结中英摘要写冰10%–15%。来源快照哈希、原获取UTC和实际读取范围见protocol.json。", "",
        "这些都是事后重建候选，未采用为实测组成或先验权重。将整块源区组成均匀化到平面板密度，是额外物理映射假设；没有由此改变界面冰充填、岩桥比例、扩散率、潜热或排水。", "",
        "## 实际结果", "",
        "|组成|积分数|首次区间越阈|初始已不稳定|始终未越阈|改变启动类别数/64|评估期最小裕度变化中位数|平均实验室域覆盖比例|",
        "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for item in bycomposition:
        c=item["onset_counts"]
        lines.append(f"|{item['composition_group']}|64|{c.get('interval_crossing',0)}|{c.get('left_censored_already_unstable',0)}|{c.get('never_crossed',0)}|{item['onset_category_changed_n']}|{item['median_delta_min_margin_evaluation']:.6f}|{item['mean_new_lab_domain_fraction']:.6f}|")
    lines += ["", "所有未启动、左删失和不存在压力单独启动根的情景均保留；详细64条基线、128条新结局、配对变化、临界水头及完整267392行状态轨迹分别落盘。失稳时刻只为条件模型诊断，未按题面或论文时刻选优；表中计数不是概率。",
        "", f"校验：基线状态代数重算的最大裕度误差{max_baseline_algebra_error:.3g}；新旧界面温度最大差{max_temp_difference:.3g}°C；水量守恒最大残差{max_water_error:.3g}m；输入哈希全部保持一致。",
        "", "密度增加同时改变法向和驱动应力；黏聚相对于自重的贡献、损伤速率、受法向应力约束的水头容量及有效应力域可随之改变。强度外域按逐时标记保留，不能因为组成更接近事后文献就提升为当地验证或机制证实。",
        "", "## 复跑", "", "```bash", *summary["commands"], "```", "",
        "脚本先检查并登记输入哈希，输出同字节时复跑安全；若协议或已存子包内容改变则拒绝覆盖，需另建版本。全部为conditional_scenario，配对差为numerical_benchmark，独立事件数0，未赋概率权重。"]
    emit(BASE/"COMPOSITION_SENSITIVITY.md","\n".join(lines)+"\n")
    files=[digest(p,"independent_composition_result") for p in sorted(OUT.iterdir()) if p.is_file() and p.name!="output_index.json"]
    files.append(digest(BASE/"COMPOSITION_SENSITIVITY.md","human_readable_composition_report"))
    json_emit(OUT/"output_index.json",dict(experiment_id=EXPERIMENT,files=files,self_entry=False))
    print(json.dumps({"new_integrations":128,"onset_category_changed_total":summary["onset_category_changed_total"],"by_composition":bycomposition,"runtime_seconds":round(time.perf_counter()-started,2)},ensure_ascii=False),flush=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare",action="store_true");group.add_argument("--run",action="store_true")
    args=parser.parse_args()
    prepare() if args.prepare else run()
