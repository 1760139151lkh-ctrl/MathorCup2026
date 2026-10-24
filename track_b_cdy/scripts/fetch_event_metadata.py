#!/usr/bin/env python3
"""Capture selected fields of the USGS event; no event-time inference.

AI assistance: Codex, OpenAI, 2026-10-23; exact model ID unavailable.
Team review required before adoption. Network access is read-only.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'audit/event_metadata.json')
    args = parser.parse_args()
    url = 'https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us7000tbwb&format=geojson'
    with urlopen(url, timeout=30) as response:
        data = json.load(response)
    if data.get('id') != 'us7000tbwb':
        raise ValueError('Unexpected event response; no snapshot written.')
    prop = data['properties']
    origin = datetime.fromtimestamp(prop['time'] / 1000, timezone.utc)
    result = {
        'source_url': url,
        'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
        'selected_fields_only': True,
        'event_id': data['id'],
        'event_type': prop.get('type'),
        'origin_time_epoch_ms': prop['time'],
        'origin_time_utc': origin.isoformat(),
        'origin_time_china': origin.astimezone(timezone(timedelta(hours=8))).isoformat(),
        'origin_time_nepal': origin.astimezone(timezone(timedelta(hours=5, minutes=45))).isoformat(),
        'coordinates_lon_lat_depth_km': data['geometry']['coordinates'],
        'place': prop.get('place'),
        'status': prop.get('status'),
        'event_page': prop.get('url'),
        'source_updated_epoch_ms': prop.get('updated'),
        'limitations': [
            'Catalog origin time is a reference, not proof of the first mechanical failure or debris-flow conversion time.',
            'No verified port-arrival time is included.',
            'The problem statement time is retained separately; the discrepancy is unresolved.',
            'Current reviewed metadata may contain post-event revisions unavailable at a simulated forecast issue time.'
        ]
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
