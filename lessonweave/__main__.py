import argparse
import json
from pathlib import Path
import uuid
from .storage import Store, read, save


def main():
    parser = argparse.ArgumentParser(prog='lessonweave')
    sub = parser.add_subparsers(dest='command', required=True)
    serve = sub.add_parser('serve')
    serve.add_argument('--host', default='127.0.0.1')
    serve.add_argument('--port', type=int, default=8960)
    run = sub.add_parser('run')
    run.add_argument('--input', type=Path, required=True)
    run.add_argument('--name', default='新的学习项目')
    run.add_argument('--project', default=None)
    run.add_argument('--repairs', type=int, default=3)
    add = sub.add_parser('register')
    add.add_argument('path', type=Path)
    add.add_argument('--id', required=True)
    add.add_argument('--name', required=True)
    export = sub.add_parser('export')
    export.add_argument('path', type=Path)
    native = sub.add_parser('sync-trilium')
    native.add_argument('project')
    args = parser.parse_args()
    if args.command == 'serve':
        from .server import serve as start
        start(args.host, args.port)
    elif args.command == 'register':
        print(json.dumps(Store().register(args.id, args.name, args.path, legacy=True), ensure_ascii=False))
    elif args.command == 'export':
        from .package import export_package
        print(json.dumps(export_package(args.path), ensure_ascii=False))
    elif args.command == 'sync-trilium':
        from .trilium import sync_project
        store=Store();project=store.project(args.project)
        mapping=sync_project(store,project,Path(project['path']))
        print(json.dumps({key:mapping[key] for key in ['project_note_id','render_note_id','version','validated']},ensure_ascii=False))
    elif args.command == 'run':
        from .pipeline import scaffold, run as execute
        store = Store()
        key = args.project or uuid.uuid4().hex[:12]
        try:
            root = Path(store.project(key)['path'])
        except KeyError:
            root = store.root / 'projects' / key
            scaffold(root)
            payload = read(args.input)
            material = Path(payload['material'])
            if payload['kind'] != 'url' and not material.is_absolute():
                payload['material'] = str((args.input.resolve().parent / material).resolve())
            save(root / '00_source/input.json', payload)
            store.register(key, args.name, root)
        result = execute(root, args.repairs)
        print(json.dumps({'project_id': key, **result}, ensure_ascii=False))
        raise SystemExit(0 if result['status'] == 'completed' else 2)


if __name__ == '__main__':
    main()
