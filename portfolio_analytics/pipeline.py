"""Snapshot orchestration with immutable bronze, strict quality gates and atomic publication."""
import hashlib
import json
import re
import shutil
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import duckdb
from .connectors import read_source

ROOT = Path(__file__).resolve().parents[1]


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding='utf-8')


def number(value):
    try:
        d = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('Invalid numeric value') from exc
    if not d.is_finite():
        raise ValueError('Non-finite numeric value')
    return d


def cents(value, rate=1):
    return int((number(value) * number(rate) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def validate_config(config):
    companies = config['companies']
    ids = [c['id'] for c in companies]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Company IDs must be unique and nonempty')
    for c in companies:
        date.fromisoformat(c['acquired_on'])
    if config['reporting_currency'] != 'EUR':
        raise ValueError('This release supports EUR reporting only')
    source_ids = [s['id'] for s in config['sources']]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError('Duplicate source IDs')
    required = {'ledger', 'crm', 'time', 'budget'}
    for cid in ids:
        if {s['kind'] for s in config['sources'] if s['company'] == cid} != required:
            raise ValueError(f'{cid} requires ledger, crm, time and budget sources')
    for s in config['sources']:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', s['id']) or s['company'] not in ids or s['kind'] not in required:
            raise ValueError('Invalid source configuration')
    for rates in config['fx'].values():
        if number(rates.get('EUR', 0)) != 1 or any(number(v) <= 0 for v in rates.values()):
            raise ValueError('FX rates must be positive and EUR rate must equal one')
    for p in config['stage_probabilities'].values():
        if not 0 <= number(p) <= 1:
            raise ValueError('Stage probability must be between zero and one')
    if any(number(config['stage_probabilities'].get(s, -1)) != 0 for s in ['won', 'lost']):
        raise ValueError('Closed stages must have zero open-pipeline weight')


def normalize(row, source, config, as_of):
    row = {k: row.get(v) for k, v in source['columns'].items()} if source.get('columns') else row
    company = source['company']
    kind = source['kind']
    companies = {c['id']: c for c in config['companies']}
    when = str(row['period']) + '-01' if kind == 'budget' else str(row['date'])[:10]
    dt = date.fromisoformat(when)
    if dt > as_of:
        raise ValueError('Record date is later than report as-of date')
    period = when[:7]
    key = str(row['deal_id'] if kind == 'crm' else row['period'] if kind == 'budget' else row['entry_id']).strip()
    if not key or key == 'None':
        raise ValueError('Missing business key')
    base = {'company': company, 'record_id': key, 'period': period, 'source_id': source['id']}
    if kind in {'ledger', 'crm'}:
        rate = config['fx'].get(period, {}).get(str(row['currency']).upper())
        if rate is None:
            raise ValueError('Missing monthly FX rate')
        amount = cents(row['amount'], rate)
        if kind == 'ledger':
            category = config['accounts'].get(company, {}).get(str(row['account']))
            if category not in {'revenue', 'cogs', 'opex'}:
                raise ValueError('Unmapped or unsupported account')
            cp = str(row.get('counterparty') or 'EXTERNAL')
            if cp != 'EXTERNAL' and cp not in companies:
                raise ValueError('Unknown group counterparty')
            if cp == company:
                raise ValueError('Self-referencing intercompany record')
            ic = cp in companies and dt >= date.fromisoformat(companies[cp]['acquired_on'])
            base.update(category=category, amount_eur_cents=amount, intercompany=ic)
        else:
            stage = str(row['stage']).lower()
            if stage not in config['stage_probabilities'] or amount < 0:
                raise ValueError('Invalid deal stage or negative deal amount')
            weighted = int((Decimal(amount) * number(config['stage_probabilities'][stage])).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            base.update(stage=stage, amount_eur_cents=amount, weighted_eur_cents=weighted)
    elif kind == 'time':
        hours, billable = number(row['hours']), number(row['billable_hours'])
        if not 0 <= billable <= hours <= 744:
            raise ValueError('Monthly logged/billable hours are out of bounds')
        base.update(minutes=int((hours*60).quantize(Decimal('1'))), billable_minutes=int((billable*60).quantize(Decimal('1'))))
    else:
        amount = cents(row['revenue_eur'])
        if amount < 0:
            raise ValueError('Negative revenue budget')
        base.update(revenue_eur_cents=amount)
    # Monthly budget includes acquisition month; daily actuals start on acquisition date.
    acquired = date.fromisoformat(companies[company]['acquired_on'])
    eligible = period >= str(acquired)[:7] if kind == 'budget' else dt >= acquired
    return base, eligible


SCHEMAS = {
    'ledger': 'company VARCHAR, record_id VARCHAR, period VARCHAR, source_id VARCHAR, category VARCHAR, amount_eur_cents BIGINT, intercompany BOOLEAN',
    'crm': 'company VARCHAR, record_id VARCHAR, period VARCHAR, source_id VARCHAR, stage VARCHAR, amount_eur_cents BIGINT, weighted_eur_cents BIGINT',
    'time': 'company VARCHAR, record_id VARCHAR, period VARCHAR, source_id VARCHAR, minutes BIGINT, billable_minutes BIGINT',
    'budget': 'company VARCHAR, record_id VARCHAR, period VARCHAR, source_id VARCHAR, revenue_eur_cents BIGINT',
}
TABLES = {'ledger': 'ledger', 'crm': 'crm', 'time': 'time_entries', 'budget': 'budget'}


def query_dicts(con, sql):
    result = con.execute(sql)
    names = [d[0] for d in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]


def run(project, as_of='2026-09-30'):
    project = Path(project).resolve()
    as_of_date = date.fromisoformat(as_of)
    config = json.loads((project/'config/portfolio.json').read_text(encoding='utf-8'))
    validate_config(config)
    root = project/'lakehouse'
    root.mkdir(exist_ok=True)
    # Lock protects local concurrent writers; a crash leaves a documented recoverable lock.
    lock = root/'pipeline.lock'
    handle = lock.open('x')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
    folder = root/'runs'/run_id
    folder.mkdir(parents=True)
    manifest = {'run_id': run_id, 'status': 'running', 'synthetic_demo': True, 'as_of': as_of,
                'started_at': datetime.now(timezone.utc).isoformat(), 'sources': [], 'alerts': [],
                'contract_version': '1.0.0', 'config_sha256': hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()}
    dump(folder/'config_snapshot.json', config)
    shutil.copyfile(ROOT/'sql/gold.sql', folder/'gold.sql')
    manifest['sql_sha256'] = hashlib.sha256((folder/'gold.sql').read_bytes()).hexdigest()
    data = {kind: [] for kind in SCHEMAS}
    rejected, seen = [], {}
    try:
        bronze = folder/'bronze'; bronze.mkdir()
        for source in config['sources']:
            age = (as_of_date-date.fromisoformat(source['snapshot_as_of'])).days
            if age < 0 or age > source.get('max_age_days', 7):
                raise ValueError(f"Stale or future snapshot: {source['id']}")
            # Copy local input before parsing, so bronze exactly matches what was processed.
            if source['format'] != 'api':
                source_path = project/source['path']
                snapshot = bronze/(source['id'] + source_path.suffix)
                shutil.copyfile(source_path, snapshot)
                rows = read_source({**source,'path':str(snapshot)}, project)
            else:
                rows = read_source(source, project)
                snapshot = bronze/(source['id']+'.json')
                dump(snapshot, rows)
            count = {'id': source['id'], 'company': source['company'], 'kind': source['kind'],
                     'input_rows': len(rows), 'accepted': 0, 'duplicates': 0, 'pre_acquisition': 0,
                     'rejected': 0, 'snapshot_as_of': source['snapshot_as_of'],
                     'sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest()}
            manifest['sources'].append(count)
            if len(rows) < source.get('min_rows', 1):
                raise ValueError(f"Unexpected empty or short snapshot: {source['id']}")
            for index, row in enumerate(rows, start=1):
                try:
                    normal, eligible = normalize(row,source,config,as_of_date)
                    key = (source['kind'],normal['company'],normal['record_id'])
                    # Cross-source business key uniqueness prevents double-counting overlapping exports.
                    compare = {k:v for k,v in normal.items() if k != 'source_id'}
                    if key in seen:
                        if seen[key] != compare:
                            raise ValueError('Conflicting duplicate business key')
                        count['duplicates'] += 1
                        continue
                    seen[key] = compare
                    if not eligible:
                        count['pre_acquisition'] += 1
                        continue
                    data[source['kind']].append(normal)
                    count['accepted'] += 1
                except (ValueError,KeyError,TypeError,OverflowError) as exc:
                    count['rejected'] += 1
                    rejected.append({'source':source['id'],'row_number':index,'reason':str(exc),'record':row})
            if count['duplicates']:
                manifest['alerts'].append({'level':'warning','source':source['id'],'message':f"Deduplicated {count['duplicates']} identical records"})
        dump(folder/'quarantine.json', rejected)
        if rejected:
            raise ValueError(f'{len(rejected)} invalid records; publication blocked. See quarantine.json.')
        with duckdb.connect(str(folder/'warehouse.duckdb')) as con:
            con.execute('CREATE SCHEMA silver; CREATE SCHEMA gold;')
            for kind, schema in SCHEMAS.items():
                table = TABLES[kind]
                con.execute(f'CREATE TABLE silver.{table} ({schema})')
                if data[kind]:
                    placeholders = ','.join('?' for _ in data[kind][0])
                    con.executemany(f'INSERT INTO silver.{table} VALUES ({placeholders})',[list(r.values()) for r in data[kind]])
            balances = con.execute("SELECT period, SUM(CASE WHEN category='revenue' THEN amount_eur_cents ELSE -amount_eur_cents END) FROM silver.ledger WHERE intercompany GROUP BY period").fetchall()
            if any(abs(balance)>1 for _,balance in balances):
                raise ValueError('Intercompany revenue/expense does not balance by month')
            con.execute((folder/'gold.sql').read_text(encoding='utf-8'))
            # Reconciliation independently ties consolidated revenue to validated external ledger rows.
            ledger_total = sum(r['amount_eur_cents'] for r in data['ledger'] if r['category']=='revenue' and not r['intercompany'])
            reported = con.execute('SELECT COALESCE(SUM(revenue_cents),0) FROM gold.group_monthly').fetchone()[0]
            if ledger_total != reported:
                raise ValueError('Gold-to-ledger reconciliation failed')
            manifest['reconciliation'] = {'external_ledger_revenue_cents':ledger_total,'reported_revenue_cents':reported,'passed':True}
            for layer,tables in [('silver',list(TABLES.values())),('gold',['finance_monthly','group_monthly'])]:
                target = folder/layer; target.mkdir()
                for table in tables:
                    path = str(target/(table+'.parquet')).replace("'","''")
                    con.execute(f"COPY {layer}.{table} TO '{path}' (FORMAT PARQUET)")
            report = {'company_monthly':query_dicts(con,'SELECT * FROM gold.finance_monthly ORDER BY period,company'),
                      'group_monthly':query_dicts(con,'SELECT * FROM gold.group_monthly ORDER BY period'),
                      'companies':config['companies']}
        manifest['status']='success'
        manifest['finished_at']=datetime.now(timezone.utc).isoformat()
        dump(folder/'manifest.json',manifest)
        report['manifest']=manifest
        dump(folder/'report.json',report)
        # AI-ready factual context uses the SAME gold results; no autonomous advice or LLM claims.
        dump(folder/'ai_context.json',{'synthetic':True,'as_of':as_of,'run_id':run_id,'currency':'EUR',
             'metric_contract':'docs/metrics.md','group_monthly':report['group_monthly']})
        from .report import render
        render(report,folder/'dashboard.html')
        temporary = root/'latest.tmp'
        dump(temporary,{'run_id':run_id,'dashboard':f'runs/{run_id}/dashboard.html','report':f'runs/{run_id}/report.json'})
        temporary.replace(root/'latest.json')
        return folder
    except Exception as exc:
        manifest['status']='failed';manifest['finished_at']=datetime.now(timezone.utc).isoformat()
        manifest['alerts'].append({'level':'critical','message':str(exc)})
        dump(folder/'manifest.json',manifest)
        raise
    finally:
        handle.close()
        lock.unlink(missing_ok=True)
