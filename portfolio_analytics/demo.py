"""Reproducible synthetic portfolio. No actual companies or financial data."""
import csv
import json
from pathlib import Path
from openpyxl import Workbook


def seed(project):
    project = Path(project)
    config_path = project / 'config' / 'portfolio.json'
    if config_path.exists():
        raise FileExistsError('Demo already exists; use a new --project folder to preserve edits.')
    (project / 'data').mkdir(parents=True, exist_ok=True)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    companies = [
        {'id': 'ALP', 'name': 'Alpine Services', 'country': 'Germany', 'currency': 'EUR', 'acquired_on': '2026-01-01'},
        {'id': 'BRI', 'name': 'Bridge Advisory', 'country': 'United Kingdom', 'currency': 'GBP', 'acquired_on': '2026-01-01'},
        {'id': 'CED', 'name': 'Cedar Operations', 'country': 'Poland', 'currency': 'PLN', 'acquired_on': '2026-07-01'},
    ]
    accounts = {'ALP': {'4000': 'revenue', '5000': 'cogs', '6000': 'opex'},
                'BRI': {'SALES': 'revenue', 'DIRECT': 'cogs', 'ADMIN': 'opex'},
                'CED': {'700': 'revenue', '401': 'cogs', '402': 'opex'}}
    sources = []
    for n, company in enumerate(companies):
        cid, currency = company['id'], company['currency']
        ledger, crm, times, budgets = [], [], [], []
        scale = [1, 0.85, 4.2][n]
        for month in range(4, 10):
            dt = f'2026-{month:02d}-15'
            revenue = round((80000 + n * 17000 + (month - 4) * 4500) * scale, 2)
            for cat, amount in [('revenue', revenue), ('cogs', round(revenue * .43, 2)), ('opex', round(revenue * .27, 2))]:
                code = next(k for k, v in accounts[cid].items() if v == cat)
                ledger.append({'entry_id': f'{cid}-{month}-{cat}', 'date': dt, 'account': code,
                               'amount': amount, 'currency': currency, 'counterparty': 'EXTERNAL'})
            for j, stage in enumerate(['qualified', 'proposal', 'negotiation', 'won', 'lost']):
                crm.append({'deal_id': f'{cid}-{month}-D{j}', 'date': dt, 'stage': stage,
                            'amount': round((15000 + 3000 * j + month * 100) * scale, 2), 'currency': currency})
            for j in range(12):
                times.append({'entry_id': f'{cid}-{month}-T{j}', 'date': dt,
                              'hours': 120 + j, 'billable_hours': 85 + month + j})
            budgets.append({'period': dt[:7], 'revenue_eur': 90000 + n * 15000 + (month - 4) * 3000})
        # Matching EUR intercompany pair: removed once at the consolidated level.
        if cid in {'ALP', 'BRI'}:
            category = 'revenue' if cid == 'ALP' else 'opex'
            ledger.append({'entry_id': f'{cid}-IC-09', 'date': '2026-09-15',
                           'account': next(k for k,v in accounts[cid].items() if v == category),
                           'amount': 800, 'currency': 'EUR', 'counterparty': 'BRI' if cid == 'ALP' else 'ALP'})
        # Exact duplicate illustrates safe deduplication with an audit warning.
        if cid == 'ALP':
            ledger.append(dict(ledger[0]))
        for kind, rows, fmt in [('ledger', ledger, 'xlsx' if cid == 'CED' else 'csv'),
                                ('crm', crm, 'json'), ('time', times, 'csv'), ('budget', budgets, 'xlsx')]:
            filename = f'data/{cid.lower()}_{kind}.{fmt}'
            path = project / filename
            if fmt == 'json':
                path.write_text(json.dumps(rows, indent=2), encoding='utf-8')
            elif fmt == 'xlsx':
                wb = Workbook(); ws = wb.active; ws.title = 'Data'
                ws.append(list(rows[0])); [ws.append(list(r.values())) for r in rows]
                wb.save(path); wb.close()
            else:
                with path.open('w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
            sources.append({'id': f'{cid.lower()}_{kind}', 'company': cid, 'kind': kind,
                            'format': fmt, 'path': filename, 'snapshot_as_of': '2026-09-30',
                            'max_age_days': 7, 'min_rows': 1})
    config = {'reporting_currency': 'EUR', 'companies': companies, 'accounts': accounts,
              'fx': {f'2026-{m:02d}': {'EUR': 1, 'GBP': 1.17, 'PLN': .23} for m in range(4, 10)},
              'stage_probabilities': {'qualified': .25, 'proposal': .6, 'negotiation': .9, 'won': 0, 'lost': 0},
              'sources': sources}
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    return config_path
