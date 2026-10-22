"""把已经保存的读本补登记到共享库，沿用稳定身份，不重新生成或覆盖改稿"""
from pathlib import Path
import argparse
import json
import time

from . import readweave
from .storage import Store, read, save


def needs_shared_registration(root):
    root = Path(root)
    book = read(root/'05_writing/book.json', {})
    if not book:
        return False
    mapping = readweave.current(root)
    sections = {section['id'] for chapter in book.get('chapters', []) for section in chapter.get('sections', [])}
    if not mapping.get('edition_id') or sections - set(mapping.get('sections', {})):
        return True
    index = read(root/'05_writing/source-location/index.json', {})
    for version in index.get('versions', []):
        location = read(root/str(version.get('manifest', '')).lstrip('/'), {})
        for page_id, page in location.get('pages', {}).items():
            identity = '\n'.join([str(location.get('material_run', '')), str(location.get('material_path', '')), page_id])
            if (page.get('text_layer') or page.get('dom')) and identity not in mapping.get('pages', {}):
                return True
    return False


def backfill(store):
    started = time.monotonic()
    report = {'models_called': 0, 'registered': 0, 'already_shared': 0, 'running': 0, 'preserved_test_directories': 0, 'pdf_text_pages': 0, 'issues': []}
    if not readweave.configured():
        return dict(report, configured=False)
    running = {job['project_id'] for job in store.jobs() if job['status'] in {'queued', 'running', 'cancelling'}}
    for project in store.projects(include_deleted=True):
        if project.get('deleted'):
            continue
        root = Path(project['path'])
        if '05-test' in root.parts:
            report['preserved_test_directories'] += 1
            continue
        if project['id'] in running:
            report['running'] += 1
            continue
        try:
            from . import legacy
            from prepare_source_locations import backfill_pdf_text_layers
            report['pdf_text_pages'] += backfill_pdf_text_layers(root)['pages']
        except Exception as error:
            report['issues'].append({'project_id': project['id'], 'reason': '原页字层尚未补齐，保留原件继续登记：' + str(error)})
        if not needs_shared_registration(root):
            report['already_shared'] += 1
            continue
        legacy_mapping = read(root/'runtime/trilium/current.json', {})
        try:
            readweave.publish_project(store, project, root, legacy_mapping)
            report['registered'] += 1
        except Exception as error:
            report['issues'].append({'project_id': project['id'], 'reason': str(error)})
    report['seconds'] = round(time.monotonic()-started, 3)
    save(store.root/'readweave-backfill.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path)
    args = parser.parse_args()
    print(json.dumps(backfill(Store(args.data)), ensure_ascii=False))


if __name__ == '__main__':
    main()
