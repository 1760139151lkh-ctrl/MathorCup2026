#!/usr/bin/env python3
"""Offline negative tests for the pair client's hard body limit and stop rules."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pair_client', BASE / 'scripts/probe_pair.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class Response:
    def __init__(self, status, body, headers):
        self.status_code, self.headers = status, headers
        self.body, self.position, self.read_calls, self.closed = body, 0, 0, False
        self.raw = self

    def read(self, count, decode_content=False):
        self.read_calls += 1
        value = self.body[self.position:self.position + count]
        self.position += len(value)
        return value

    def close(self):
        self.closed = True


class Session:
    def __init__(self, response):
        self.response, self.trust_env = response, True

    def get(self, url, **kwargs):
        assert self.trust_env is False
        assert kwargs['stream'] is True and kwargs['allow_redirects'] is False
        assert kwargs['headers']['Range'] == 'bytes=0-16383'
        return self.response

    def close(self):
        pass


def main():
    (BASE / 'results').mkdir(parents=True, exist_ok=True)
    scenes = client.inventory()
    original_out, original_ledger = client.OUT, client.LEDGER
    checks = []
    with tempfile.TemporaryDirectory(prefix='budget-fixture-', dir=BASE / 'results') as folder:
        temp = Path(folder)

        def run_case(name, responses):
            case = temp / name
            client.OUT, client.LEDGER = case, case / 'network_budget.json'
            value = client.budget_load()
            for index, response in enumerate(responses):
                with patch('requests.Session', lambda: Session(response)):
                    client.probe(scenes[client.IDS[index]], 'pre' if index == 0 else 'post', value)
            return value

        response = Response(200, b'whole scene must not be consumed', {'Content-Length': '671193558'})
        value = run_case('range_200', [response])
        checks.append({'name': 'range_200_stops_before_body_read', 'passed': response.read_calls == 0 and response.closed and value['consumed_response_body_bytes_combined'] == 0})

        response = Response(206, b'oversized', {'Content-Range': 'bytes 0-19999/671193558'})
        value = run_case('oversize_range', [response])
        checks.append({'name': 'oversize_content_range_rejected_before_body', 'passed': response.read_calls == 0 and value['requests'][0]['outcome'] == 'invalid_content_range_body_not_read'})

        response = Response(206, b'II*\0' + b'\0' * 12, {'Content-Range': 'bytes 0-15/671193558', 'Content-Length': '16'})
        value = run_case('bounded_206', [response])
        checks.append({'name': 'valid_partial_tiff_header_only_no_pixel_claim', 'passed': value['consumed_response_body_bytes_combined'] == 16 and value['requests'][0]['tiff_header_verified'] and not value['requests'][0]['usable_pixels_obtained']})

        value = run_case('two_failures', [Response(401, b'x' * 96, {}), Response(401, b'y' * 96, {})])
        reloaded = client.budget_load()
        checks.append({'name': 'both_failed_scene_bodies_accumulate_and_persist', 'passed': reloaded['consumed_response_body_bytes_combined'] == 192 and len(reloaded['requests']) == 2})

        response = Response(401, b'x' * 100000, {})
        value = run_case('bounded_error', [response])
        checks.append({'name': 'error_body_capture_has_64k_bound', 'passed': response.position == 65536 and value['consumed_response_body_bytes_combined'] == 65536})

        client.OUT, client.LEDGER = temp / 'exhausted', temp / 'exhausted/network_budget.json'
        value = client.budget_load()
        value['consumed_response_body_bytes_combined'] = client.LIMIT - 100
        try:
            with patch('requests.Session', side_effect=AssertionError('Network must not start')):
                client.probe(scenes[client.IDS[0]], 'pre', value)
            rejected = False
        except RuntimeError:
            rejected = True
        checks.append({'name': 'remaining_budget_checked_before_request', 'passed': rejected})

        response = Response(302, b'login page should not be fetched', {'Location': 'https://example.invalid/login'})
        value = run_case('redirect', [response])
        checks.append({'name': 'redirect_not_followed_or_consumed', 'passed': response.read_calls == 0 and value['consumed_response_body_bytes_combined'] == 0})
    client.OUT, client.LEDGER = original_out, original_ledger
    result = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'offline': True,
              'real_network_requests': 0, 'passed': all(r['passed'] for r in checks), 'checks': checks,
              'scope': 'Synthetic HTTP fixtures validate client stop rules; not provider Range or pixel capability.'}
    client.save(BASE / 'results/network_guard_checks.json', result)
    print(json.dumps(result, ensure_ascii=False))
    assert result['passed']


if __name__ == '__main__':
    main()
