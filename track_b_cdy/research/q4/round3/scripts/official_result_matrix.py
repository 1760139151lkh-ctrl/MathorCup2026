#!/usr/bin/env python3
"""Summarize closed, registered runs without qualifying their numerical accuracy."""
from pathlib import Path
import csv, datetime, hashlib, json
import numpy as np
from official_catalogue import registered_cases, applicability, EXCLUDED, DIAGNOSTIC

P = Path(__file__).resolve().parents[1]
R = P / 'results'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    metrics_path = R / 'official_metrics.csv'
    arrivals_path = R / 'official_arrivals.csv'
    validation_path = R / 'official_validation.json'
    metrics = {x['run_id']: x for x in csv.DictReader(metrics_path.open())}
    arrivals = {}
    for row in csv.DictReader(arrivals_path.open()):
        arrivals.setdefault(row['run_id'], {})[row['target']] = row
    checks = {x['run_id']: x for x in json.loads(validation_path.read_text())['checks']}
    decisions = applicability()
    rows, phase_ledgers = [], []
    for item in registered_cases():
        rid = item['run_id']
        decision = decisions.get(rid, {}).get('decision', 'required')
        c = json.loads(Path(item['case']).read_text())
        row = {'run_id': rid, 'scenario_id': c.get('scenario_id'),
               'model': c['model'], 'resolution_m': c['resolution_m'],
               'applicability_decision': decision, 'case_sha256': sha(item['case']),
               'requested_release_volume_m3': c.get('release_grid_volume_m3'),
               'requested_horizon_seconds': c.get('end_seconds'),
               'mu_basal': c.get('mu_basal'), 'xi': c.get('xi'),
               'release_thickness_m': c.get('release_thickness_m'),
               'numerical_accuracy_qualified': False,
               'local_event_validation_count': 0}
        if decision in EXCLUDED:
            row['execution_state'] = decision
            rows.append(row)
            continue
        m, check = metrics.get(rid), checks.get(rid)
        if not m or not check:
            row['execution_state'] = 'not_yet_in_closed_postprocessed_cohort'
            rows.append(row)
            continue
        path = Path(m['source_fields_path'])
        assert sha(path) == m['source_fields_sha256'] == check['source_fields_sha256']
        fields = np.load(path)
        area = abs(float(fields['transform'][0]) * float(fields['transform'][4]))
        h = fields['depth_final'].astype(float)
        v = fields['stationary_criterion_speed_final'].astype(float)
        wet = h >= .1
        stationary = wet & np.isfinite(v) & (v < .1)
        row.update({
            'execution_state': m['status'],
            'actual_end_seconds': float(fields['time_s'][-1]),
            'source_fields_path': str(path),
            'source_fields_sha256': m['source_fields_sha256'],
            'parser_sha256_at_start': m['parser_sha256_at_start'],
            'execution_sha256': m['execution_sha256'],
            'log_sha256': m['log_sha256'],
            'solver_build': m['solver_build'],
            'actual_binary_sha256': m['actual_binary_sha256'],
            'execution_image_id': m['execution_image_id'],
            'stationary_residual_volume_m3': float(np.sum(h[stationary]) * area),
            'stationary_residual_cells': int(stationary.sum()),
            'final_wet_min_horizontal_speed_m_s': float(np.min(v[wet])) if wet.any() else None,
            'initial_domain_volume_m3': float(fields['volume_m3'][0]),
            'final_domain_volume_m3': float(fields['volume_m3'][-1]),
            'initial_domain_mass_kg': float(fields['mass_kg'][0]),
            'final_domain_mass_kg': float(fields['mass_kg'][-1]),
        })
        for key in ['max_depth_over_saved_outputs_m',
                    'max_horizontal_speed_over_saved_outputs_m_s',
                    'native_cumulative_max_depth_m',
                    'native_cumulative_max_speed_m_s', 'impact_area_m2',
                    'native_mass_budget_relative_residual',
                    'native_internal_summary_mass_budget_relative_residual',
                    'estimated_boundary_adjusted_mass_residual_fraction',
                    'mass_change_fraction']:
            row[key] = float(m[key]) if m.get(key) else None
        for target in ['paper_port_symbol', 'paper_junction']:
            a = arrivals.get(rid, {}).get(target, {})
            if a:
                assert a['source_fields_sha256'] == m['source_fields_sha256']
                assert float(a['evaluation_end_time_seconds']) == row['actual_end_seconds']
            for key in ['status', 'arrival_seconds', 'previous_below_threshold_time_seconds',
                        'first_boundary_threshold_time_seconds', 'domain_affected_before_arrival']:
                row[target + '_' + key] = a.get(key) or None
        ledger = {'run_id': rid, 'model': c['model'], 'source_fields_sha256': m['source_fields_sha256'],
                  'phase_volume_initial_m3': fields['phase_volume_m3'][0].tolist(),
                  'phase_volume_final_m3': fields['phase_volume_m3'][-1].tolist(),
                  'phase_material_names': fields['phase_material_names'].tolist(),
                  'initial_total_mass_kg': row['initial_domain_mass_kg'],
                  'final_total_mass_kg': row['final_domain_mass_kg'],
                  'native_edge_store_phase_volumes_m3': check.get('native_edge_store_outflow_phase_volumes_m3'),
                  'native_signed_entrainment_phase_volumes_m3': check.get('native_signed_entrainment_phase_volumes_m3'),
                  'native_added_entrainment_mass_kg': check.get('native_entrained_added_mass_kg'),
                  'estimated_boundary_mass_out_kg': check.get('estimated_boundary_mass_out_kg'),
                  'native_boundary_phase_budget_available': c['model'] != 'dclaw',
                  'native_conservation_qualified': False,
                  'empty_phase_max_abs_depth_m': check.get('prescribed_empty_phase_max_abs_depth_m'),
                  'empty_phase_max_abs_volume_m3': check.get('prescribed_empty_phase_max_abs_volume_m3')}
        phase_ledgers.append(ledger)
        rows.append(row)
    columns = list(dict.fromkeys(k for row in rows for k in row))
    with (R / 'official_result_matrix.csv').open('w') as f:
        w = csv.DictWriter(f, fieldnames=columns); w.writeheader(); w.writerows(rows)
    excluded = sum(x['applicability_decision'] in EXCLUDED for x in rows)
    closed = sum(x['execution_state'] not in EXCLUDED | {'not_yet_in_closed_postprocessed_cohort'} for x in rows)
    output = {'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'registered_count': len(rows), 'material_excluded_not_run_count': excluded,
              'closed_postprocessed_count': closed,
              'all_applicable_and_diagnostic_closed': closed + excluded == len(rows),
              'sources': [{'path': str(p), 'sha256': sha(p)} for p in [metrics_path, arrivals_path, validation_path]],
              'stationary_residual_definition': 'last actual saved output: h>=0.1m and max horizontal speed over wet native phases (phase h>=1e-6m)<0.1m/s; finite v only; not permanent deposition',
              'phase_budget_definition': 'saved-output domain phase volumes; DClaw solid/fluid from h*m and h*(1-m), ravaflow active native phases; no melt inference',
              'dclaw_boundary_budget_limitation': 'boundary mass estimate is trapezoidal integration of saved output, not native conservative phase flux; no qualification from this estimate',
              'accuracy_or_conservation_qualification': False, 'local_event_validation_count': 0,
              'phase_ledgers': phase_ledgers}
    (R / 'official_final_diagnostics.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({k: output[k] for k in ['registered_count', 'closed_postprocessed_count', 'material_excluded_not_run_count', 'all_applicable_and_diagnostic_closed']}))

if __name__ == '__main__':
    main()
