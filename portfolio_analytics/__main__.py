import argparse
import json
import sys
from pathlib import Path
from .demo import seed
from .pipeline import run, ROOT


def main():
    parser=argparse.ArgumentParser(description='Acquisition analytics: synthetic local demo')
    parser.add_argument('command',choices=['seed','run','demo','status'])
    parser.add_argument('--project',type=Path,default=ROOT)
    parser.add_argument('--as-of',default='2026-09-30',help='Snapshot cutoff, YYYY-MM-DD')
    args=parser.parse_args()
    try:
        if args.command in {'seed','demo'}:
            seed(args.project)
        if args.command in {'run','demo'}:
            folder=run(args.project,args.as_of)
            print('SUCCESS: '+str(folder/'dashboard.html'))
        if args.command=='status':
            manifests=sorted((args.project/'lakehouse/runs').glob('*/manifest.json'), key=lambda p: p.stat().st_mtime_ns)
            if not manifests:
                print('No runs yet');return 1
            latest=json.loads(manifests[-1].read_text(encoding='utf-8'))
            print(json.dumps(latest,indent=2))
            return 0 if latest['status']=='success' else 1
        return 0
    except Exception as exc:
        print(f'FAILED: {exc}',file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
