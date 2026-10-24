"""Rebuild manually verified external evidence tables without network access.

The PDF and HTML snapshots are data, never executable inputs. Values below were
transcribed against the saved article and actually viewed PDF pages.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
BASE = ROOT / "track_b/research/q2/round3/sources/strength"
OUT = ROOT / "track_b/research/q2/round3/results/strength_evidence.csv"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    reg_path = BASE / "source_register.json"
    reg = json.loads(reg_path.read_text())
    by_name = {Path(row["path"]).name: row for row in reg["sources"]}
    for name, row in by_name.items():
        path = ROOT / row["path"]
        assert path.stat().st_size == row["bytes"] and digest(path) == row["sha256"], name

    mamot = by_name["mamot2018_article.pdf"]
    thermal = by_name["thermal_diffusivity2025.html"]
    hydro = by_name["waterflow2026.html"]
    supp = by_name["mamot2018_supplement.zip"]
    rows = []

    def add(key, mechanism, value, units, domain, locator, source, uncertainty="", use="external_transfer", limit=""):
        rows.append({"parameter_id": key, "mechanism_group": mechanism,
                     "value_or_relationship": value, "units": units,
                     "published_domain": domain, "uncertainty_semantics": uncertainty,
                     "evaluation_stratum": use, "local_measurement_status": "not locally measured",
                     "source_locator": locator, "canonical_url_or_product_id": source["canonical_url_or_product_id"],
                     "source_snapshot_path": source["path"], "source_sha256": source["sha256"],
                     "retrieved_at_utc": source["retrieved_at_utc"], "permitted_use_and_limit": limit})

    d = "ice-filled limestone joint; T=-8 to -0.5 degC; applied normal stress 100 to 400 kPa; fast brittle shear"
    add("joint_cohesion", "T;S_T;S_T_H", "c_joint(T)=53.3-73.5*T", "kPa; T in degC", d,
        "Eq4, printed3341/PDF9; Eq6, printed3342/PDF10", mamot,
        "Eq6 intercept SE20.6 kPa; slope SE8.8 kPa/degC; coefficient covariance not reported",
        limit="External constitutive transfer; not a pure-ice or site-calibrated law; retain out-of-domain flags")
    add("joint_friction_coefficient", "T;S_T;S_T_H", "mu_joint(T)=0.42-0.21*T", "1; T in degC", d,
        "Eq5, printed3341/PDF9; Eq6, printed3342/PDF10", mamot,
        "Eq6 intercept SE0.15; slope SE0.06/degC; joint probability distribution not specified",
        limit="External constitutive transfer; do not assign independent normal priors from SE alone")
    add("joint_friction_angle", "T;S_T;S_T_H", "phi=atan(mu_joint)", "radian; multiply 180/pi for deg", d,
        "Sect2.4; text below Eq6", mamot, limit="mu is tan(phi), not phi in degrees")
    add("strength_criterion", "S;S_T;S_H;S_T_H", "tau_failure=sigma*mu_joint(T)+c_joint(T)", "kPa", d,
        "Eq3 and Eq6", mamot, limit="Published sigma is applied laboratory normal stress; water-pressure substitution is extra modeling assumption")
    add("temperature_fitted_domain", "T;S_T;S_T_H", "[-8,-0.5]", "degC", d,
        "Eq4-Eq6; Sect3.3", mamot, "endpoint specimen temperature spreads reported +/-0.1 degC",
        limit="Tests also included -10 degC, but Eq6 was not calibrated for -10; any clip is a separate boundary scenario")
    add("normal_stress_fitted_domain", "S;S_T;S_H;S_T_H", "[100,400]", "kPa", d,
        "Eq6; Sect3.3; Fig9", mamot, limit="800 kPa tests were held out; replacing sigma with effective sigma must still flag sigma_eff outside range")
    add("shear_displacement_rate", "S;S_T;S_H;S_T_H", "0.7 +/- 0.1", "mm/min", d,
        "Sect2.3, printed3338/PDF6", mamot, "reported mean +/- spread; not a rate-independent calibration",
        limit="Do not apply as slow-creep law or convert background glacier speed to this shear-zone strain rate")
    add("shear_strain_rate", "S;S_T;S_H;S_T_H", "mean4.8e-3 +/-1.4e-3; reported minimum1.58e-3", "1/s", d,
        "Sect2.3, printed3338/PDF6", mamot, limit="Brittle failure experiments; long-term creep/transition requires other law; source minimum reproduced as reported")
    add("ice_layer_thickness", "S;S_T;S_H;S_T_H", "3 +/- 1", "mm", d,
        "Sect2.2, printed3337/PDF5", mamot, limit="Laboratory specimen geometry, not field release thickness")
    add("joint_surface_roughness", "S;S_T;S_H;S_T_H", "0.185", "mm amplitude", d,
        "Sect2.2, printed3337/PDF5", mamot, limit="Controlled ground surface; natural fracture roughness and stress redistribution unmeasured")
    add("tested_material", "S;S_T;S_H;S_T_H", "Wetterstein limestone; porosity approx4.4%; tap-water ice", "material description", d,
        "Sect2.2; Sect4.1", mamot, limit="Authors hypothesize transfer to other rocks, but explicitly call for cross-lithology tests; do not claim local granite calibration")
    add("experiment_count", "S;S_T;S_H;S_T_H", "141", "laboratory tests", d,
        "Sect2.3; Supplement TableS1", mamot, limit="Not independent landslide events; no contribution to Q3 event count")
    add("coefficient_error_type", "T;S_T;S_T_H", "regression coefficient standard errors", "as above", d,
        "Sect2.4, printed3339/PDF7; Fig7; Eq6", mamot,
        "Fig7 c-slopeSE8.7; Fig9 equation8.75; Eq6 rounds8.8; choose Eq6 for canonical implementation",
        limit="No parameter covariance or local posterior supplied; sensitivity corners are scenarios, not calibrated confidence limits")
    add("warm_thawed_branch", "T;S_T;S_T_H", "not tested above -0.5 degC", "domain exclusion", "T>-0.5 degC",
        "Sect3.3 text before Eq6, printed3341/PDF9", mamot,
        limit="Melting/squeezing out changes to rock-rock shear; positive c intercept at T=0 is not a supported thawed strength; use explicitly separate branch")
    add("published_model_holdout_error", "S_T;S_T_H", "held-out temperature strata MAD97.5-252.3; CV15.0-43.5", "kPa; percent", "same laboratory; 100-400 kPa; includes -10 degC extrapolation",
        "Sect4.2; Supplement TableS2, supplement PDF10", supp,
        limit="Temperature-stratum holdout only; not independent field validation or site predictive coverage")
    add("effective_stress_extension", "S_H;S_T_H", "sigma_eff=max(sigma_n-u,0)", "kPa", "hydraulic pressure, connected area and contact regime require specification",
        "Modeling extension to Eq3/Eq6; not tested in Mamot2018", mamot, use="conditional_scenario",
        limit="Mamot did not control hydraulic pore pressure; sigma_eff<=0 requires opening/uplift flag; pressure-to-area mapping remains assumed")
    add("area_mix_damage_extension", "S;S_T;S_H;S_T_H", "area-fraction rock-bridge/joint mixture; damage scaling", "dimensionless fractions and stress", "field geometry/damage unknown",
        "No calibrated mixture or damage law in Mamot2018", mamot, use="conditional_scenario",
        limit="Cannot source bridge fraction/bridge cohesion/damage evolution from this article; identify and vary explicitly")
    td = "Swiss mountain permafrost below active layer; 29 PERMOS boreholes, landform subsets/exclusions; conduction-dominant estimate"
    add("thermal_diffusivity_bedrock", "T;S_T;S_T_H", "median1.5e-6; MAD0.6e-6", "m2/s", td,
        "Weber2025 Sect3.4 and Sect5; DOI10.5194/tc-19-6727-2025", thermal,
        "median +/- median absolute deviation; not SE, confidence interval or local parameter distribution",
        limit="0.9/1.5/2.1e-6 may be deliberately selected sensitivity grid; transfer to local fractured ice-rock unvalidated")
    add("thermal_diffusivity_talus", "T;S_T;S_T_H", "median1.1e-6; MAD0.2e-6", "m2/s", td,
        "Weber2025 Sect3.4 and Sect5", thermal, "median and MAD",
        limit="Landform dependence is external; no local composition identified")
    add("thermal_diffusivity_rockglacier", "T;S_T;S_T_H", "median1.3e-6; MAD0.3e-6", "m2/s", td,
        "Weber2025 Sect3.4 and Sect5", thermal, "median and MAD",
        limit="Not equivalent to glacier ice diffusivity or site bedrock calibration")
    add("conduction_domain_caveat", "T;S_T;S_T_H", "active-layer latent/advection effects and lateral heat flow violate simple 1D conduction", "model limitation", td,
        "Weber2025 Sect3.3-3.4; Sect4; Fig6 exclusions", thermal,
        limit="Near-melt apparent diffusivity can vary; conduction benchmark does not include latent heat/advective bypass")
    hd = "Aiguille du Midi granite fractures; man-made tunnel outlet; observed 2022-2023; open unsaturated paths approx12-20 m"
    add("flow_lag_air_temperature", "H;S_H;S_T_H", "3-9", "h", hd,
        "Ben-Asher2026 Sect3.5.2, Sect4.1, Sect6", hydro,
        "moving 24h daily cross-correlation; 1h smoothing; days maxflow>6L/h; observational lag not drainage coefficient",
        limit="Supports possible hour-scale paths; cannot estimate local tau or hydraulic head")
    add("flow_lag_ground_surface_temperature", "H;S_H;S_T_H", "abstract/conclusion0-3; Results4.1 text0-6", "h", hd,
        "Ben-Asher2026 Abstract, Sect4.1, Sect6", hydro,
        "Internal reporting discrepancy retained; exact numerical bound not adopted",
        limit="Do not silently select one bound or use as local drainage tau")
    add("water_path_thermal_advection", "S_T_H", "fracture flow can transport heat; outlet flow is not pore pressure", "process constraint", hd,
        "Ben-Asher2026 Sect5.1-5.4 and Sect6", hydro,
        limit="T/H are not independent causal observations; pure conduction plus mechanical pressure omits heat advection; tunnel shortcut and anthropogenic heat limit transfer")
    add("drainage_parameter_local", "S_H;S_T_H", "unknown; explicit sensitivity scenario needed", "h; conductance/storage as model defines", "local network/opening/storage/head unobserved",
        "External case has heterogeneous neighboring paths and nonlinear seasonal recessions, Sect3.5.1 and5.3", hydro, use="conditional_scenario",
        limit="Do not equate correlation lag, transit time, reservoir recession constant and pore-pressure response time")
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    coeff = {
        "parameter_version": "mamot2018-eq6-transcription-v1",
        "source": mamot,
        "evaluation_stratum": "external_transfer",
        "temperature_unit": "degC",
        "stress_unit": "kPa",
        "c_intercept": 53.3, "c_slope": -73.5,
        "mu_intercept": 0.42, "mu_slope": -0.21,
        "coefficient_standard_errors": {"c_intercept":20.6,"c_slope":8.8,"mu_intercept":0.15,"mu_slope":0.06},
        "coefficient_covariance": None,
        "temperature_domain_degC": [-8.0,-0.5],
        "applied_normal_stress_domain_kPa": [100.0,400.0],
        "mean_strain_rate_per_s": 0.0048,
        "mean_strain_rate_reported_spread_per_s": 0.0014,
        "adoption_status": "pending_team_review",
        "local_validation": False,
        "critical_extensions": ["effective stress substitution not pressure-calibrated", "bridge/damage area mixture assumed", "slow creep outside rate regime", "thawed branch requires independent law", "no calibrated joint probability distribution"]
    }
    (BASE/"mamot2018_coefficients.json").write_text(json.dumps(coeff,indent=2)+"\n")
    values = [(-0.5,0.1,40.0,19.9,"calibration"),(-1.1,0.2,97.5,43.5,"temperature_holdout"),
              (-2.2,0.2,99.3,24.6,"calibration"),(-3.1,0.2,137.8,30.5,"temperature_holdout"),
              (-4.2,0.2,145.7,19.8,"calibration"),(-4.9,0.2,136.4,17.9,"calibration"),
              (-6.1,0.2,206.6,24.6,"temperature_holdout"),(-8.0,0.1,110.4,8.8,"calibration"),
              (-10.0,0.4,252.3,15.0,"temperature_holdout_outside_fitted_temperature_domain")]
    with (BASE/"mamot2018_table_s2_transcribed.csv").open("w",newline="") as f:
        w=csv.writer(f);w.writerow(["mean_temperature_degC","reported_temperature_spread_degC","MAD_kPa","CV_percent","published_role"]);w.writerows(values)
    print(json.dumps({"evidence_rows":len(rows),"evidence_sha256":digest(OUT),"coefficients_sha256":digest(BASE/"mamot2018_coefficients.json"),"table_s2_rows":len(values)}))


if __name__ == "__main__":
    main()
