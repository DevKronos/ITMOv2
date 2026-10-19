"""python -m app.cli import-snapshots | sync | notify | preview."""
import argparse
import json
from app import storage
from app.source import collect_snapshots
from app.service import synchronize,generate_notifications,preview_notifications


def main():
    parser=argparse.ArgumentParser(description='Сервис уведомлений об акциях')
    sub=parser.add_subparsers(dest='command',required=True)
    imp=sub.add_parser('import-snapshots',help='Импорт сохранённых реальных страниц без сети')
    imp.add_argument('directory',nargs='?',default='research/snapshots')
    sync=sub.add_parser('sync');sync.add_argument('--snapshots')
    sub.add_parser('notify');sub.add_parser('preview')
    args=parser.parse_args()
    if args.command=='import-snapshots':
        collected=collect_snapshots(args.directory)
        result={**storage.import_promotions(collected['promotions'],complete=collected['complete']), 'errors':collected['errors'],'mode':'snapshots'}
    elif args.command=='sync': result=synchronize(args.snapshots)
    elif args.command=='notify': result={'created':generate_notifications()}
    else: result=preview_notifications()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result.get('status') in ('error','partial') or result.get('errors'): raise SystemExit(1)


if __name__=='__main__': main()
