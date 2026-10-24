#!/usr/bin/env python3
"""Small read-only GFS archive probe: index plus 16-byte GRIB header.

AI assistance: Codex, OpenAI, 2026-10-23; exact model ID unavailable.
No GRIB field decoding, regional extraction or forecast modelling is performed.
"""
import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', default='20260825')
    parser.add_argument('--cycle', default='18', choices=['00', '06', '12', '18'])
    parser.add_argument('--lead', default=9, type=int)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'audit/forecast_probe')
    args = parser.parse_args()
    origin = datetime.strptime(args.date + args.cycle, '%Y%m%d%H').replace(tzinfo=timezone.utc)
    valid = origin + timedelta(hours=args.lead)
    name = f'gfs.t{args.cycle}z.pgrb2.0p25.f{args.lead:03d}'
    base = f'https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{args.date}/{args.cycle}/atmos/{name}'
    args.output.mkdir(parents=True, exist_ok=True)
    result = {'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
              'index_url': base + '.idx', 'data_url': base,
              'provider_registry': 'https://registry.opendata.aws/noaa-gfs-bdp-pds/',
              'archive_listing': f'https://gdex.ucar.edu/datasets/d084001/filelist/{args.date}/',
              'reference_time_utc': origin.isoformat(), 'lead_hours': args.lead,
              'valid_time_utc': valid.isoformat(),
              'data_decoded': False, 'regional_data_extracted': False,
              'actual_operational_available_time': None,
              'limitations': ['One object/index success does not establish archive completeness.',
                             'Current access does not establish when this forecast was operationally available in August.',
                             'No weather forecast skill, local accuracy, or event forecast is assessed.',
                             'The valid time is after the catalog event onset; forecast reference time is earlier.']}
    try:
        with urlopen(base + '.idx', timeout=30) as response:
            raw = response.read(1024 * 1024 + 1)
            result['index_http_status'] = response.status
        if len(raw) > 1024 * 1024:
            raise ValueError('Index exceeded the metadata size limit.')
        text = raw.decode('utf-8')
        lines = text.splitlines()
        if not lines or any(not line.split(':', 1)[0].isdigit() for line in lines):
            raise ValueError('Response is not a GRIB index.')
        index_path = args.output / (args.date + '_' + name + '.idx')
        index_path.write_bytes(raw)
        result.update(index_bytes=len(raw), index_sha256=hashlib.sha256(raw).hexdigest(),
                      index_records=len(lines), index_file=index_path.name,
                      selected_variable_index_records=[line for line in lines if any(
                          token in line for token in [':TMP:2 m above ground:', ':RH:2 m above ground:',
                                                     ':APCP:surface:', ':UGRD:10 m above ground:',
                                                     ':VGRD:10 m above ground:'])])
        with urlopen(Request(base, headers={'Range': 'bytes=0-15'}), timeout=30) as response:
            header = response.read(16)
            result['header_http_status'] = response.status
            result['content_range'] = response.headers.get('Content-Range')
            result['etag'] = response.headers.get('ETag')
        result['grib_header_hex'] = header.hex()
        result['grib_signature_valid'] = len(header) == 16 and header[:4] == b'GRIB' and header[7] == 2
        result['first_message_bytes'] = int.from_bytes(header[8:16], 'big') if result['grib_signature_valid'] else None
        result['success'] = result['grib_signature_valid'] and result['header_http_status'] == 206
    except Exception as exc:
        result['success'] = False
        result['error'] = f'{type(exc).__name__}: {exc}'
    (args.output / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(not result['success'])


if __name__ == '__main__':
    raise SystemExit(main())
