#!/usr/bin/env python3
"""Publish a separate immutable phase-evidence candidate, never a truth update."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];ROOT=R.parents[3]
def main():
    output=R/'exports/phase_evidence_bundle_v3.json'
    if output.exists():raise FileExistsError('Immutable export already exists; verify it instead of replacing')
    named=[('WAVEFORM_EVIDENCE.md','waveform_methods_results_limits'),('inputs/waveform/protocol.json','waveform_registered_protocol'),
       ('results/waveform_sources.json','waveform_source_products'),('results/waveform/phase_review.json','station_phase_evidence_only'),
       ('results/waveform/threshold_summary.csv','all_nine_band_threshold_combinations'),('results/waveform/candidate_episodes.csv','all_candidate_episodes_not_independent_events'),
       ('results/waveform/validation.json','waveform_qc'),('results/waveform/station_inventory.json','station_channel_response_metadata'),
       ('results/waveform/mustang_summary.json','daily_quality_metric_not_first_availability'),('results/waveform/waveform_bands.png','station_signal_figure'),
       ('results/waveform/waveform_spectra.png','retrospective_spectrum_figure'),('results/phase_evidence/phase_review.json','USGS_fixed_origin_pick_arrival_review'),
       ('sources/us7000tbwb_phase_1792791413040.xml','USGS_raw_quakeml')]
    files=[]
    for name,role in named:
        p=R/name;files.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),role=role))
    b=dict(bundle_version='q3-r3-phase-evidence-v3',producer_question='q3',created_at_utc=datetime.now(timezone.utc).isoformat(),
       input_version={'baseline_commit':'904d7257b899b9f71d1ac9e0eab7479e459eab52','baseline_manifest_sha256':'fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53'},
       files=files,evaluation_stratum='retrospective_phase_evidence',approved_first_mechanical_truth=False,independent_truth_events_added=0,
       limitations=['Single station candidate signals are arrivals and phase proxies, not source first mechanical motion',
          'All nine threshold/frequency combinations retained, including early high-frequency candidates',
          'Station/source clock, propagation, radiation phase, response and causal filter delays do not define an accepted onset interval',
          'Product acquisition and MUSTANG metric update time are not historical first availability',
          'USGS90% origin uncertainty is conditional on catalogue model, not mechanical-phase proxy bias',
          'Original event v1 and external event v2 are immutable; this bundle proposes evidence only'])
    output.write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(path=str(output.relative_to(ROOT)),sha256=hashlib.sha256(output.read_bytes()).hexdigest(),files=len(files))))
if __name__=='__main__':main()
