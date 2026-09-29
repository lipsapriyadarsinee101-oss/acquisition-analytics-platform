import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import duckdb
from portfolio_analytics.demo import seed
from portfolio_analytics.pipeline import run, cents, normalize, validate_config
from portfolio_analytics.connectors import read_api


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        seed(self.root)
        self.config=json.loads((self.root/'config/portfolio.json').read_text())

    def tearDown(self):
        self.temp.cleanup()

    def config_save(self):
        (self.root/'config/portfolio.json').write_text(json.dumps(self.config))

    def test_full_pipeline_reconciles_and_excludes_pre_acquisition(self):
        folder=run(self.root)
        report=json.loads((folder/'report.json').read_text())
        self.assertEqual(len(report['group_monthly']),6)
        self.assertEqual(len(report['company_monthly']),15)
        self.assertTrue(all(r['period']>='2026-07' for r in report['company_monthly'] if r['company']=='CED'))
        with duckdb.connect(str(folder/'warehouse.duckdb'),read_only=True) as con:
            september=con.execute("SELECT revenue_cents,operating_earnings_cents FROM gold.group_monthly WHERE period='2026-09'").fetchone()
            # Independently hand-derived from the three source revenues and FX rates.
            self.assertEqual(september[0],10250000+11884275+13185900)
            self.assertEqual(september[1],3075000+3565283+3955770)
            company_total=con.execute("SELECT SUM(revenue_cents) FROM gold.finance_monthly WHERE period='2026-09'").fetchone()[0]
            self.assertEqual(company_total-september[0],80000)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM read_parquet(?)",[str(folder/'gold/finance_monthly.parquet')]).fetchone()[0],15)
        self.assertEqual(sum(s['duplicates'] for s in report['manifest']['sources']),1)

    def test_reruns_are_idempotent_and_raw_preserved(self):
        first=run(self.root);second=run(self.root)
        a=json.loads((first/'report.json').read_text());b=json.loads((second/'report.json').read_text())
        self.assertEqual(a['group_monthly'],b['group_monthly'])
        self.assertEqual((first/'bronze/alp_ledger.csv').read_bytes(),(self.root/'data/alp_ledger.csv').read_bytes())
        self.assertEqual(json.loads((self.root/'lakehouse/latest.json').read_text())['run_id'],second.name)

    def test_bad_account_preserves_last_good_publication(self):
        first=run(self.root)
        file=self.root/'data/alp_ledger.csv';file.write_text(file.read_text().replace(',4000,',',UNKNOWN,',1))
        with self.assertRaisesRegex(ValueError,'invalid records'):
            run(self.root)
        self.assertEqual(json.loads((self.root/'lakehouse/latest.json').read_text())['run_id'],first.name)
        failed=[p for p in (self.root/'lakehouse/runs').iterdir() if p!=first][0]
        self.assertEqual(json.loads((failed/'manifest.json').read_text())['status'],'failed')
        self.assertIn('Unmapped',json.loads((failed/'quarantine.json').read_text())[0]['reason'])

    def test_stale_source_blocks_publication(self):
        self.config['sources'][0]['snapshot_as_of']='2026-08-01';self.config_save()
        with self.assertRaisesRegex(ValueError,'Stale'):
            run(self.root)
        self.assertFalse((self.root/'lakehouse/latest.json').exists())

    def test_conflicting_duplicate_is_not_silently_dropped(self):
        file=self.root/'data/alp_ledger.csv';text=file.read_text();lines=text.splitlines()
        lines[-1]=lines[-1].replace('80000','90000');file.write_text('\n'.join(lines)+'\n')
        with self.assertRaisesRegex(ValueError,'invalid records'):
            run(self.root)

    def test_unbalanced_intercompany_blocks_publication(self):
        file=self.root/'data/alp_ledger.csv';file.write_text(file.read_text().replace(',800,EUR,BRI',',900,EUR,BRI'))
        with self.assertRaisesRegex(ValueError,'Intercompany'):
            run(self.root)

    def test_full_snapshot_replacement_handles_deletion(self):
        run(self.root)
        file=self.root/'data/alp_crm.json';rows=json.loads(file.read_text());deleted=rows.pop(0);file.write_text(json.dumps(rows))
        latest=run(self.root)
        with duckdb.connect(str(latest/'warehouse.duckdb'),read_only=True) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM silver.crm WHERE record_id=?',[deleted['deal_id']]).fetchone()[0],0)

    def test_money_rounding_and_nonfinite_values(self):
        self.assertEqual(cents('1.005'),101)
        self.assertEqual(cents('100','1.17'),11700)
        for value in ['NaN','Infinity','not a number']:
            with self.assertRaises(ValueError):cents(value)

    def test_invalid_hours_and_missing_fx(self):
        from datetime import date
        source=next(s for s in self.config['sources'] if s['id']=='alp_time')
        with self.assertRaisesRegex(ValueError,'hours'):
            normalize({'entry_id':'x','date':'2026-09-01','hours':5,'billable_hours':6},source,self.config,date(2026,9,30))
        source=next(s for s in self.config['sources'] if s['id']=='alp_crm')
        with self.assertRaisesRegex(ValueError,'FX'):
            normalize({'deal_id':'x','date':'2026-09-01','amount':100,'currency':'USD','stage':'won'},source,self.config,date(2026,9,30))

    def test_zero_denominator_returns_null(self):
        file=self.root/'data/alp_time.csv';lines=file.read_text().splitlines();header=lines[0]
        file.write_text(header+'\n'+'\n'.join(','.join(row.split(',')[:2]+['0','0']) for row in lines[1:])+'\n')
        folder=run(self.root)
        with duckdb.connect(str(folder/'warehouse.duckdb'),read_only=True) as con:
            self.assertTrue(all(r[0] is None for r in con.execute("SELECT billable_share FROM gold.finance_monthly WHERE company='ALP'").fetchall()))

    def test_concurrent_writer_lock(self):
        (self.root/'lakehouse').mkdir();(self.root/'lakehouse/pipeline.lock').touch()
        with self.assertRaises(FileExistsError):run(self.root)

    def test_invalid_config(self):
        self.config['fx']['2026-04']['GBP']=0
        with self.assertRaises(ValueError):validate_config(self.config)


class ApiTests(unittest.TestCase):
    def test_paginated_http_connector(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                page={'items':[{'id':1}],'next':f'http://127.0.0.1:{self.server.server_port}/page2'} if self.path=='/' else {'items':[{'id':2}],'next':None}
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(page).encode())
            def log_message(self,*args):pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:self.assertEqual(read_api(f'http://127.0.0.1:{server.server_port}/'),[{'id':1},{'id':2}])
        finally:server.shutdown();server.server_close();thread.join()

    def test_nonsecure_remote_api_rejected(self):
        with self.assertRaisesRegex(ValueError,'HTTPS'):read_api('http://example.com/api')

if __name__=='__main__':unittest.main()
