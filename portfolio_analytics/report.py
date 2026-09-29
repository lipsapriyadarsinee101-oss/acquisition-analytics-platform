"""Offline dashboard: embedded data, no external scripts or network requests."""
import json
from pathlib import Path


def render(report, output):
    template = (Path(__file__).resolve().parents[1]/'templates/dashboard.html').read_text(encoding='utf-8')
    payload = json.dumps(report, default=str, allow_nan=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
    Path(output).write_text(template.replace('__REPORT_DATA__',payload),encoding='utf-8')
