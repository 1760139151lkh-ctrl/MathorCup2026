#!/usr/bin/env python3
"""Historical registrations and explicit applicability decisions remain separate."""
from pathlib import Path
import json
P=Path(__file__).resolve().parents[1]
def registered_cases():
 out=[]
 for suite in ['copdem_v2','q2mapped_v2','q2fullmask_v2','composite','extended','composite_ablation','entrainment']:
  p=P/f'config/official_cases_{suite}.json'
  if p.exists():out+=json.loads(p.read_text())['cases']
 assert len({x['run_id'] for x in out})==len(out),'Duplicate registered run_id'
 return out
def applicability():
 p=P/'config/official_execution_applicability.json'
 return {x['run_id']:x for x in json.loads(p.read_text())['entries']} if p.exists() else {}
EXCLUDED={'quarantined_not_run','not_run_material_applicability_exclusion'}
PENDING={'pending_review_do_not_start'}
DIAGNOSTIC={'generic_material_proxy_diagnostic_only'}
