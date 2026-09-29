"""Small snapshot connectors. No vendor integration is implied."""
import csv
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from openpyxl import load_workbook


def _origin(url):
    u = urlsplit(url)
    return u.scheme, u.netloc


def read_api(url, token_env=None, max_pages=100):
    """Read a generic {items: [...], next: absolute URL|null} endpoint.

    Pagination is same-origin only. HTTP is allowed only for localhost demos.
    Redirects are deliberately not followed: never send credentials off-origin.
    """
    from urllib.request import HTTPRedirectHandler, build_opener

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    origin = _origin(url)
    if origin[0] != 'https' and urlsplit(url).hostname not in {'127.0.0.1', 'localhost'}:
        raise ValueError('API connections require HTTPS except localhost')
    headers = {'Accept': 'application/json'}
    if token_env:
        token = os.environ.get(token_env)
        if not token:
            raise ValueError(f'Missing token environment variable: {token_env}')
        headers['Authorization'] = f'Bearer {token}'
    opener = build_opener(NoRedirect())
    rows, visited = [], set()
    while url:
        if _origin(url) != origin or url in visited or len(visited) >= max_pages:
            raise ValueError('Unsafe or looping API pagination')
        visited.add(url)
        for attempt in range(3):
            try:
                with opener.open(Request(url, headers=headers), timeout=20) as response:
                    page = json.load(response)
                break
            except HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise
                time.sleep(0.25 * (2 ** attempt))
            except URLError:
                if attempt == 2:
                    raise
                time.sleep(0.25 * (2 ** attempt))
        if not isinstance(page, dict) or not isinstance(page.get('items'), list):
            raise ValueError('Expected API response with items list')
        rows.extend(page['items'])
        url = page.get('next')
    return rows


def read_source(source, project):
    kind = source['format']
    if kind == 'api':
        return read_api(source['url'], source.get('token_env'))
    path = (Path(project) / source['path']).resolve()
    if kind == 'csv':
        with path.open(encoding='utf-8-sig', newline='') as f:
            return list(csv.DictReader(f))
    if kind == 'json':
        content = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(content, list):
            raise ValueError('JSON snapshot must contain a list')
        return content
    if kind == 'xlsx':
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = workbook[source.get('sheet', 'Data')]
            values = iter(sheet.values)
            header = next(values)
            return [dict(zip(header, row)) for row in values if any(v is not None for v in row)]
        finally:
            workbook.close()
    raise ValueError(f'Unsupported format: {kind}')
