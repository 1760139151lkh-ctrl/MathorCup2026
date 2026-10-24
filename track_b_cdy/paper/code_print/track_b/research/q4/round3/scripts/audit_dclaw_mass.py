#!/usr/bin/env python3
"""Read-only audit of completed fixed D-Claw outputs; never invokes a solver.

Output is confined to this audit's two new JSON files. Native data and the
official postprocessor are inputs. No numerical-source accounting is inferred
from coarse saved frames.
"""
from pathlib import Path
import datetime
import hashlib
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path('<LOCAL_HOME>/Documents/MathorCup/research_cache/round3/q4/official/runs')
SOURCE = Path('<LOCAL_HOME>/Documents/MathorCup/research_cache/round3/runtime/sources/dclaw-1.0.0')
RUNS = ['dclaw_ref_extended120', 'copdem_120_dclaw_permeable', 'copdem_120_dclaw_ref']
SOURCE_SCOPE = {
    'docs/src/theory.md': {'read_lines': [[1, 175]], 'purpose': 'State semantics, core equations, density and dilation source terms'},
    'src/2d/dig/digclaw_module.f90': {'read_lines': [[70, 105], [267, 465]], 'purpose': 'State indices, ordinary qfix, constant-mass qfix_cmass, actual permeability law'},
    'src/2d/dig/src2.f90': {'read_lines': [[1, 300]], 'purpose': 'Complete source integrator; rhoh before qfix, source method 2, dry cycle, entrainment switch'},
    'src/2d/dig/mp_update.f90': {'read_lines': [[1, 165]], 'keyword_scan_only_elsewhere': ['rhoh', 'qfix', 'dry_tolerance', 'subroutine', 'h =', 'hm =', 'm =', 'mass'], 'purpose': 'Method descriptions, actual method-2 coefficients and constant-mass calls; not a complete branch-by-branch proof'},
    'src/2d/dig/b4step2.f90': {'read_lines': [[1, 80]], 'purpose': 'Pre-step qfix calls for interior and ghost cells'},
    'src/2d/dig/rpn2_dclaw.f': {'read_lines': [[1, 392]], 'purpose': 'Normal Riemann qfix, wet-dry wall handling, zero-speed fluctuation branch'},
    'src/2d/dig/riemannsolvers_dclaw.f': {'read_lines': [[1, 508]], 'purpose': 'Flux wave identities including hm flux; not replayed as a solver'},
    'src/2d/dig/flux2fw.f': {'read_lines': [[1, 240]], 'purpose': 'First-order flux-difference assembly; active first-order run avoids second-order limiter claims'},
    'src/2d/dig/valout.f90': {'read_lines': [[1, 565]], 'purpose': 'Native binary layout: seven states and eta, ghost cells, tiny-value output rounding'},
}


def record(path, scope=None):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            digest.update(block)
    row = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}
    if scope is not None:
        row['actual_read_scope'] = scope
    return row


def parse_data(path):
    """Read generated named scalar controls; not a setrun reconstruction."""
    values = {}
    for line in path.read_text().splitlines():
        if '=:' in line:
            before, after = line.split('=:', 1)
            values[after.split()[0]] = before.strip()
    return values


def raw_frame(folder, suffix):
    """Independent binary64 decoder from valout's Fortran stream layout."""
    t_path, q_path, b_path = [folder / (prefix + suffix) for prefix in ['fort.t', 'fort.q', 'fort.b']]
    tokens = [line.split()[0] for line in t_path.read_text().splitlines() if line.strip()]
    time, nq, ngrids, ghost, fmt = float(tokens[0]), int(tokens[1]), int(tokens[2]), int(tokens[5]), tokens[6]
    if (nq, ngrids, fmt.lower()) != (8, 1, 'binary64'):
        raise ValueError(f'Unsupported audit layout in {t_path}: {tokens}')
    head = [line.split()[0] for line in q_path.read_text().splitlines() if line.strip()]
    if len(head) != 8 or int(head[1]) != 1:
        raise ValueError('Expected one level-1 header, no AMR overlap')
    nx, ny = int(head[2]), int(head[3])
    dx, dy = float(head[6]), float(head[7])
    raw = np.fromfile(b_path, dtype='<f8')
    expected = nq * (nx + 2 * ghost) * (ny + 2 * ghost)
    if raw.size != expected:
        raise ValueError(f'Byte count does not match native header: {b_path}')
    full = raw.reshape(ny + 2 * ghost, nx + 2 * ghost, nq)
    q = full[ghost:ghost + ny, ghost:ghost + nx, :]
    # The native array is south-to-north. Integrals need no vertical flip.
    return time, q, dx, dy, [t_path, q_path, b_path]


def source_rate_at_state(q, controls, dry):
    """Instantaneous mathematical rates, not the actual substep ledger."""
    rs, rf = float(controls['rho_s']), float(controls['rho_f'])
    mu, kref, mref = float(controls['mu']), float(controls['kref']), float(controls['mref'])
    h, hm, p = q[:, :, 0], q[:, :, 3], q[:, :, 4]
    wet = h > dry
    m = np.divide(hm, h, out=np.zeros_like(h), where=wet)
    rho = rf + (rs - rf) * m
    k = kref * np.exp(-(m - mref) / .04)  # Actual setvars, not the sign in a prose formula.
    excess = p - rf * 9.81 * h
    dilation = np.divide(-2 * k * excess, mu * h, out=np.zeros_like(h), where=wet)
    phi1 = np.where(wet, (rho - rf) / rho * dilation, 0.)
    phi4 = np.where(wet, -dilation * m * rf / rho, 0.)
    return phi1, phi4


def audit_run(name):
    folder = CACHE / name
    case_path = folder / 'case.json'
    case = json.loads(case_path.read_text())
    controls = parse_data(folder / 'dclaw.data')
    geo = parse_data(folder / 'geoclaw.data')
    dry = float(geo['dry_tolerance'])
    rs, rf = float(controls['rho_s']), float(controls['rho_f'])
    summaries = sorted(folder.glob('summary_fields_db13be185e93.npz'))
    if len(summaries) != 1:
        raise ValueError('Exact audited summary version missing')
    summary_path = summaries[0]
    files = [record(folder / f, 'Complete named control/JSON read' if f in ['case.json', 'dclaw.data', 'geoclaw.data'] else 'Identity hash only within audit script; associated controls reviewed separately') for f in [
        'case.json', 'dclaw.data', 'geoclaw.data', 'claw.data', 'amr.data',
        'execution.json', 'timing.txt']]
    files.append(record(summary_path, 'All named arrays relevant to depth, m, phase volumes, mass, time and boundary flux; no rewrite'))
    rows, raw_files = [], []
    comparisons = {key: 0. for key in ['mass_max_abs_difference_kg', 'mass_max_relative_difference',
        'phase_volume_max_abs_difference_m3', 'depth_float32_max_abs_difference_m',
        'wet_m_float32_max_abs_difference', 'boundary_mass_rate_max_abs_difference_kg_s']}
    with np.load(summary_path) as summary:
        stored_t = summary['time_s']
        stored_mass = summary['mass_kg']
        stored_phases = summary['phase_volume_m3']
        stored_depth = summary['depth_frames']
        stored_m = summary['solid_fraction_frames']
        stored_boundary = summary['boundary_mass_flux_kg_s']
        if len(stored_t) != 91 or stored_t[0] != 0 or stored_t[-1] != 1800:
            raise ValueError('Unexpected completed horizon')
        footprint = None
        for index, tf in enumerate(sorted(folder.glob('fort.t[0-9][0-9][0-9][0-9]'))):
            time, q, dx, dy, paths = raw_frame(folder, tf.name[-4:])
            if time != stored_t[index]:
                raise ValueError('Native time disagrees with summary')
            if not np.isfinite(q).all():
                raise ValueError(f'Nonfinite native state in {name}, t={time}')
            raw_files.extend(record(path, 'Complete header or all binary64 interior state values decoded; ghosts excluded from integrals') for path in paths)
            h, hm, hu, hv = q[:, :, 0], q[:, :, 3], q[:, :, 1], q[:, :, 2]
            area = dx * dy
            volume = float(h.sum() * area)
            solid_volume = float(hm.sum() * area)
            fluid_volume = float((h - hm).sum() * area)
            # Never apply the 0.1 m impact threshold to total or phase mass.
            cell_mass = rf * h + (rs - rf) * hm
            mass = float(cell_mass.sum() * area)
            density = rf + (rs - rf) * np.divide(hm, h, out=np.zeros_like(h), where=h > 1e-12)
            edge_h = np.concatenate((h[0], h[-1], h[1:-1, 0], h[1:-1, -1]))
            edge_momentum = np.concatenate((q[0, :, 1:3].ravel(), q[-1, :, 1:3].ravel(),
                                           q[1:-1, 0, 1:3].ravel(), q[1:-1, -1, 1:3].ravel()))
            # E/N signs evaluated in native south-to-north coordinates.
            boundary_rate = float(dy * (np.sum(density[:, -1] * hu[:, -1]) - np.sum(density[:, 0] * hu[:, 0]))
                                + dx * (np.sum(density[-1] * hv[-1]) - np.sum(density[0] * hv[0])))
            next_h = np.where(h <= dry, 0., h)
            next_hm = np.where(h <= dry, 0., np.clip(hm, 0., h))
            qfix_delta = (rf * next_h + (rs - rf) * next_hm - cell_mass) * area
            thin = (h > 0) & (h <= dry)
            footprint = h > dry if footprint is None else footprint | (h > dry)
            row = {
                'time_s': time, 'volume_m3': volume, 'solid_volume_hm_m3': solid_volume,
                'fluid_volume_h_minus_hm_m3': fluid_volume, 'mass_kg': mass,
                'h_min_m': float(h.min()), 'hm_min_m': float(hm.min()),
                'hm_negative_cells': int(np.count_nonzero(hm < 0)),
                'hm_gt_h_cells': int(np.count_nonzero(hm > h)),
                'thin_positive_cells_h_le_dry': int(thin.sum()),
                'thin_positive_mass_kg': float(cell_mass[thin].sum() * area),
                'hypothetical_one_qfix_mass_loss_kg': float(-qfix_delta[qfix_delta < 0].sum()),
                'hypothetical_one_qfix_mass_gain_kg': float(qfix_delta[qfix_delta > 0].sum()),
                'boundary_h_max_m': float(edge_h.max()),
                'boundary_abs_hu_hv_max_m2_s': float(np.abs(edge_momentum).max()),
                'saved_boundary_mass_rate_kg_s': boundary_rate,
                'wet_cells_h_gt_dry': int((h > dry).sum()),
                'erosion_bdif_max_abs_m': float(np.abs(q[:, :, 6]).max()),
            }
            if index == 0:
                phi1, phi4 = source_rate_at_state(q, controls, dry)
                row['instantaneous_source_integrals_t0'] = {
                    'phi1_volume_rate_m3_s': float(phi1.sum() * area),
                    'phi4_solid_volume_rate_m3_s': float(phi4.sum() * area),
                    'combined_total_mass_rate_kg_s': float((rf * phi1 + (rs - rf) * phi4).sum() * area),
                    'combined_absolute_pointwise_residual_kg_s': float(np.abs(rf * phi1 + (rs - rf) * phi4).sum() * area),
                    'scope': 't=0 instantaneous theoretical rates integrated over cells, actual native substep source history unavailable',
                }
            mass_diff = abs(mass - float(stored_mass[index]))
            comparisons['mass_max_abs_difference_kg'] = max(comparisons['mass_max_abs_difference_kg'], mass_diff)
            comparisons['mass_max_relative_difference'] = max(comparisons['mass_max_relative_difference'], mass_diff / abs(mass))
            comparisons['phase_volume_max_abs_difference_m3'] = max(comparisons['phase_volume_max_abs_difference_m3'],
                float(np.max(np.abs(stored_phases[index] - [solid_volume, fluid_volume]))))
            comparisons['depth_float32_max_abs_difference_m'] = max(comparisons['depth_float32_max_abs_difference_m'],
                float(np.max(np.abs(stored_depth[index] - h[::-1]))))
            # The summary stores m only above its 0.1 m display/impact threshold.
            shown = h[::-1] > .1
            primitive_m = np.divide(hm, h, out=np.zeros_like(h), where=h != 0)[::-1]
            if shown.any():
                comparisons['wet_m_float32_max_abs_difference'] = max(comparisons['wet_m_float32_max_abs_difference'],
                    float(np.max(np.abs(stored_m[index][shown] - primitive_m[shown]))))
            comparisons['boundary_mass_rate_max_abs_difference_kg_s'] = max(comparisons['boundary_mass_rate_max_abs_difference_kg_s'],
                abs(boundary_rate - float(stored_boundary[index])))
            rows.append(row)
        m0, v0, s0 = [rows[0][key] for key in ['mass_kg', 'volume_m3', 'solid_volume_hm_m3']]
        for row in rows:
            row['mass_change_fraction'] = row['mass_kg'] / m0 - 1
            row['volume_change_fraction'] = row['volume_m3'] / v0 - 1
            row['solid_volume_change_fraction'] = row['solid_volume_hm_m3'] / s0 - 1
        rates = np.array([row['saved_boundary_mass_rate_kg_s'] for row in rows])
        times = np.array([row['time_s'] for row in rows])
        integrated = float(np.trapezoid(rates, times))
        first_threshold = next((row['time_s'] for row in rows if row['boundary_h_max_m'] >= .1), None)
        final_loss = m0 - rows[-1]['mass_kg']
        max_thin = max(row['thin_positive_mass_kg'] for row in rows)
        result = {
            'run_id': name, 'solver_binary_sha256': record(folder / 'xdclaw')['sha256'],
            'native_single_patch_shape_y_x': list(q.shape[:2]), 'native_frames': len(rows),
            'all_eight_output_components_finite_at_all_saved_interior_cells': True,
            'rho_s_kg_m3': rs, 'rho_f_kg_m3': rf, 'dry_tolerance_m': dry,
            'source_method': int(controls['src2method']), 'entrainment': int(controls['entrainment']),
            'mass_formula': 'rho_f*h + (rho_s-rho_f)*hm; integrate all interior cells without wet threshold',
            'decoder_comparison': comparisons,
            'first_saved_boundary_h_ge_0_1_seconds': first_threshold,
            'all_saved_boundary_h_exactly_zero': all(row['boundary_h_max_m'] == 0 for row in rows),
            'all_saved_boundary_hu_hv_exactly_zero': all(row['boundary_abs_hu_hv_max_m2_s'] == 0 for row in rows),
            'estimated_saved_boundary_mass_out_kg': integrated,
            'estimated_boundary_adjusted_final_residual_fraction': (rows[-1]['mass_kg'] + integrated - m0) / m0,
            'max_saved_thin_positive_mass_kg': max_thin,
            'max_saved_thin_positive_mass_fraction_of_initial': max_thin / m0,
            'max_saved_thin_mass_fraction_of_final_mass_deficit': max_thin / final_loss if final_loss > 0 else None,
            'saved_ever_wet_cells_h_gt_dry': int(footprint.sum()),
            'hypothetical_one_cleanup_all_cells_upper_bound_kg': float(q.shape[0] * q.shape[1] * dx * dy * dry * rs),
            'dry_budget_limit': 'Snapshot thin mass and hypothetical single-call bounds are not cumulative deletion; intermediate qfix calls/states are not recorded',
            'qualification': 'conditional_diagnostic; no independent validation and no native conservative mass ledger',
            'rows': rows,
        }
    return result, files + raw_files


def main():
    when = datetime.datetime.now(datetime.timezone.utc).isoformat()
    results, all_inputs = [], []
    for name in RUNS:
        result, inputs = audit_run(name)
        results.append(result)
        all_inputs.extend(inputs)
    output = {
        'audit_version': 'q4-r3-dclaw-mass-audit-v1', 'created_utc': when,
        'baseline_commit': '904d7257b899b9f71d1ac9e0eab7479e459eab52',
        'baseline_manifest_sha256': 'fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53',
        'execution': {'argv': sys.argv, 'python': sys.executable, 'numpy': np.__version__,
                      'native_solver_invoked': False, 'inputs_modified': False},
        'state_semantics': {'q1': 'h', 'q2': 'hu', 'q3': 'hv', 'q4': 'hm', 'q5': 'pb',
                            'q6': 'hchi', 'q7': 'bdif', 'q8_output_only': 'eta'},
        'theoretical_identity': 'rho_f*phi1+(rho_s-rho_f)*phi4 = 0, since rho-rho_f=(rho_s-rho_f)*m',
        'solid_phase_scope': 'hm has nonzero phi4 source in the stated model; its integral is audited separately and cannot be presumed invariant without source and boundary ledgers',
        'causal_attribution': 'unresolved: stored states reproduce deficits/gains, but no native per-step flux/source/qfix ledger exists',
        'runs': results,
    }
    output_path = ROOT / 'results/dclaw_mass_audit.json'
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    source_records = []
    for path, scope in SOURCE_SCOPE.items():
        # Hash complete files; the cited scope is the actual human/model review,
        # not a claim that hashing constituted a complete scientific reading.
        nlines = len((SOURCE / path).read_text().splitlines())
        scope = dict(scope)
        scope['read_lines'] = [[first, min(last, nlines)] for first, last in scope['read_lines']]
        source_records.append(record(SOURCE / path, scope))
    source_audit = {
        'created_utc': when, 'audit_version': output['audit_version'],
        'source_version': 'D-Claw 1.0.0; fixed local runtime source snapshot',
        'source_review': source_records,
        'postprocessor_review': record(ROOT / 'scripts/official_analyse.py', 'Full source read, independent decoder does not import or execute it'),
        'runtime_identity_snapshot': record(ROOT / 'sources/official_source_identity.json', 'Full structured read; inherited binary/source checks, not recompiled in this audit'),
        'native_and_summary_inputs': all_inputs,
        'raw_hash_scope': 'All fort.t/fort.q headers and fort.b binary streams of all 91 frames for each of the three listed runs; no output mutation',
        'audit_script': record(Path(__file__), 'Executed read-only audit'),
        'audit_result': record(output_path, 'New audit result'),
        'read_limitations': ['No native timestep mass flux ledger exists in these outputs',
                             'No per-call qfix before/after states exist',
                             'No native source-integrator substep history exists',
                             'No solver rerun, recompilation or patching undertaken'],
    }
    (ROOT / 'sources/dclaw_mass_source_audit.json').write_text(json.dumps(source_audit, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'result': str(output_path), 'runs': [
        {'run_id': row['run_id'], 'mass_change_at_20s': row['rows'][1]['mass_change_fraction'],
         'mass_change_at_180s': row['rows'][9]['mass_change_fraction'],
         'mass_change_at_1800s': row['rows'][-1]['mass_change_fraction'],
         'mass_decode_max_abs_difference_kg': row['decoder_comparison']['mass_max_abs_difference_kg']}
        for row in results]}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
