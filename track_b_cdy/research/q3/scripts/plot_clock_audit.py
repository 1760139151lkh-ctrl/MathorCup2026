#!/usr/bin/env python3
"""Plot forecast windows and separate retrospective candidate event clocks.

AI assistance: OpenAI Codex, 2026-10-24. This is an evidence diagram, not a
prediction, calibrated interval, accepted event chronology or event simulation.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as dates
import matplotlib.pyplot as plt

Q = Path(__file__).resolve().parents[1]
ROOT = Q.parents[2]


def time(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def main():
    forecast = json.loads((ROOT / 'track_b/data/processed/forecast_sample/summary.json').read_text())
    ledger = json.loads((ROOT / 'track_b/data/external/event_remote/event_evidence_ledger.json').read_text())
    config = json.loads((Q / 'config/replay.json').read_text())
    reference, valid = map(time, [forecast['forecast_reference_time_utc'], forecast['valid_time_utc']])
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(11.8, 8.8), gridspec_kw={'height_ratios': [1, 1.25]})
    fig.subplots_adjust(top=.88, bottom=.16, left=.29, right=.97, hspace=.50)
    fig.suptitle('Q3 clock audit: forecasts, decisions and candidate event phases', x=.04, ha='left', fontsize=14, fontweight='bold')
    fig.text(.04, .915, 'All clocks in UTC, 25-26 Aug 2026. Historical first availability remains unverified.', color='#555555')
    for y, start, label in [(2, reference, 'Rain accumulation: f000-f009'), (1, reference + timedelta(hours=6), 'Rain accumulation: f006-f009')]:
        top.plot([start, valid], [y, y], lw=11, solid_capstyle='butt', color='#6c91ac')
        top.scatter([start, valid], [y, y], s=20, color='#284c67', zorder=3)
    top.scatter([valid], [0], s=65, marker='D', color='#284c67')
    top.set_yticks([2, 1, 0], ['Rain: 0-9 h', 'Rain: 6-9 h', 'Instant fields: f009'])
    for issue in config['issue_times_utc']:
        top.axvline(time(issue), color='#966748', linestyle=':', lw=1.4)
    top.set_ylim(-.6, 2.6)
    top.set_xlim(reference - timedelta(minutes=15), valid + timedelta(minutes=15))
    top.xaxis.set_major_locator(dates.HourLocator(byhour=[18, 21, 0, 3], tz=timezone.utc))
    top.xaxis.set_major_formatter(dates.DateFormatter('%d Aug %H:%M', tz=timezone.utc))
    top.set_title('Forecast target windows overlap; dotted lines are technical demonstration issue times', loc='left', fontsize=10)
    top.grid(axis='x', alpha=.2)
    lookup = {r['evidence_id']: r for r in ledger['records']}
    labels = [
        ('problem_1030', 'Task reference: phase unverified', '#9a7357'),
        ('jms_initiation', 'JMS onset reconstruction: approximate', '#5a7774'),
        ('yin_main_onset_extract', 'Yin onset: search extract only', '#9a7357'),
        ('usgs_current_reviewed_origin', 'USGS signal proxy: not mechanical onset', '#4d6e8c'),
        ('jms_first_impact', 'JMS first impact reconstruction', '#5a7774'),
        ('jms_confluence_impact', 'JMS confluence impact reconstruction', '#5a7774'),
        ('jms_port_arrival', 'JMS port arrival reconstruction', '#5a7774'),
        ('yin_port_arrival_extract', 'Yin port arrival: search extract only', '#9a7357')]
    for i, (key, label, colour) in enumerate(labels):
        moment = time(lookup[key]['event_time_utc'])
        y = len(labels) - 1 - i
        bottom.scatter(moment, y, s=46, color=colour)
        bottom.annotate(moment.strftime('%H:%M:%S'), (moment, y), xytext=(8, 0), textcoords='offset points', va='center', fontsize=9)
    bottom.set_yticks(range(len(labels)), [row[1] for row in labels][::-1], fontsize=9)
    bottom.set_ylim(-.7, len(labels) - .3)
    bottom.set_xlim(time('2026-08-26T02:20:00Z'), time('2026-08-26T03:09:00Z'))
    bottom.xaxis.set_major_locator(dates.MinuteLocator(byminute=[20, 30, 40, 50, 0], tz=timezone.utc))
    bottom.xaxis.set_major_formatter(dates.DateFormatter('%H:%M', tz=timezone.utc))
    bottom.set_title('Different sources and phases of one hazard chain; none is accepted validation truth', loc='left', fontsize=10)
    bottom.set_xlabel('26 Aug 2026 (UTC)')
    bottom.grid(axis='x', alpha=.2)
    fig.text(.04, .025, 'Sources: saved GFS GRIB/summary, task statement, USGS QuakeML and retrospective publisher evidence.\nNo uncertainty band is invented from differences between source clocks.', color='#555555', fontsize=9)
    folder = Q / 'figures'
    folder.mkdir(exist_ok=True)
    fig.savefig(folder / 'clock_audit.png', dpi=170)
    plt.close(fig)


if __name__ == '__main__':
    main()
