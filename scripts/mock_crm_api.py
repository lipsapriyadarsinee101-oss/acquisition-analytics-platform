"""Run a mock generic CRM API for exercising the HTTP connector locally."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

parser=argparse.ArgumentParser()
parser.add_argument('--file',default='data/alp_crm.json')
parser.add_argument('--port',type=int,default=8766)
args=parser.parse_args()
rows=json.loads(Path(args.file).read_text(encoding='utf-8'))
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed=urlparse(self.path)
        if parsed.path!='/deals':
            self.send_error(404);return
        try:
            page=max(1,int(parse_qs(parsed.query).get('page',['1'])[0]))
        except ValueError:
            self.send_error(400);return
        start=(page-1)*10
        result={'items':rows[start:start+10], 'next':f'http://127.0.0.1:{args.port}/deals?page={page+1}' if start+10<len(rows) else None}
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(result).encode())
print(f'Mock CRM API: http://127.0.0.1:{args.port}/deals (synthetic data only)')
HTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
