"""把实际阅读依赖打包，让接收端保留正文版本与来源定位"""
from pathlib import Path
import json
import zipfile
import hashlib
import jsonschema
from .storage import read, save


def safe_local(root, name):
    value = str(name).split('#', 1)[0].split('?', 1)[0].lstrip('/')
    for prefix in (str(root)+os_separator(),root.as_posix()+'/'):
        if str(name).startswith(prefix):
            value=str(name)[len(prefix):].replace('\\','/')
            break
    if not value.startswith(('00_source/','01_tree/','02_questions/','03_chapters/','04_transitions/','05_writing/')):
        return None
    target = (root / value).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        return None
    return target


def os_separator():
    import os
    return os.sep


def export_package(root, output=None):
    root = Path(root).resolve()
    output=Path(output).resolve() if output else root/'05_writing'
    output.mkdir(parents=True,exist_ok=True)
    book = read(root / '05_writing/preview-book.json', read(root / '05_writing/book.json'))
    if not book:
        raise ValueError('当前项目尚未形成可导出的书稿')
    paths = set()
    pending = [root / ('05_writing/preview-book.json' if (root / '05_writing/preview-book.json').exists() else '05_writing/book.json')]
    pending += [root/'05_writing'/name for name in ('book.json','preview-book.json','note-aliases.json') if (root/'05_writing'/name).is_file()]
    pending += [p for folder in ['00_source/materials','01_tree/history','02_questions/history','03_chapters/history','04_transitions/history','05_writing/source-location'] for p in (root/folder).rglob('*') if p.is_file() and (p.suffix not in {'.py','.pyc'} or p.is_relative_to(root/'00_source/materials'))]
    pending += [root / stage / name for stage, name in [('00_source','source.json'),('01_tree','tree.json'),('02_questions','questions.json'),('03_chapters','chapters.json'),('04_transitions','transitions.json')]]
    def visit(value):
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            path = safe_local(root, value)
            if path and path not in paths and (path.suffix not in {'.py','.pyc'} or path.is_relative_to(root/'00_source/materials')):
                pending.append(path)
    while pending:
        path = pending.pop()
        if path in paths or not path.is_file():
            continue
        paths.add(path)
        if path.suffix == '.json':
            visit(read(path))
        elif path.suffix in {'.html', '.css'}:
            import re
            for item in re.findall(r'''(?:src|href)=["']([^"']+)["']''', path.read_text('utf-8', errors='replace')):
                found = safe_local(root, item) if item.startswith('/') else safe_local(root, (path.parent / item).relative_to(root))
                if found:
                    pending.append(found)
    identity=hashlib.sha256(json.dumps(book,sort_keys=True,ensure_ascii=False).encode())
    for chapter in book['chapters']:
        for section in chapter['sections']:
            identity.update((root/section['path']).read_bytes())
    version = book['writing_run']+'-'+identity.hexdigest()[:12]
    manifest = {'profile': 'lessonweave-reading-package-v1', 'schema_version': 1,
                'project_id': root.name, 'version': version, 'title': book['title'],
                'book_path': '05_writing/preview-book.json' if book.get('preview') else '05_writing/book.json',
                'validation': book['validation'], 'coverage': book['coverage'],
                'source_location_path': '05_writing/source-location/index.json',
                'files': sorted(p.relative_to(root).as_posix() for p in paths),
                'user_data_included': False}
    save(output / 'reading-package.json', manifest)
    schema=read(Path(__file__).resolve().parents[1]/'framework/05_writing/reading-package.schema.json')
    jsonschema.validate(manifest,schema)
    destination = output / 'reading-package.zip'
    def portable(value):
        if isinstance(value,dict):
            return {key:portable(child) for key,child in value.items()}
        if isinstance(value,list):
            return [portable(child) for child in value]
        if isinstance(value,str) and (value.startswith(str(root)) or value.startswith(root.as_posix())):
            path=Path(value)
            if path.is_relative_to(root):
                return path.relative_to(root).as_posix()
        return value
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        for path in paths:
            if path.suffix=='.json':
                archive.writestr(path.relative_to(root).as_posix(),json.dumps(portable(read(path)),ensure_ascii=False))
            else:
                archive.write(path, path.relative_to(root).as_posix())
    return manifest


def import_package(archive_path, destination):
    destination = Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('导入目标必须为空，已有正文和笔记继续保留')
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('profile') != 'lessonweave-reading-package-v1':
            raise ValueError('阅读包版本尚未支持')
        schema=read(Path(__file__).resolve().parents[1]/'framework/05_writing/reading-package.schema.json')
        jsonschema.validate(manifest,schema)
        allowed = set(manifest['files']) | {'manifest.json'}
        if len(archive.infolist())>25000 or sum(item.file_size for item in archive.infolist())>1_500_000_000:
            raise ValueError('阅读包超过本次导入的资源上限')
        if set(archive.namelist()) != allowed:
            raise ValueError('阅读包中的实际文件与清单不同')
        for entry in archive.infolist():
            target = (destination / entry.filename).resolve()
            if not target.is_relative_to(destination) or entry.filename.startswith(('/', '\\')) or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('阅读包包含目标之外的路径或符号链接')
            if entry.file_size > 200_000_000:
                raise ValueError('阅读包中有超出单文件上限的内容')
        archive.extractall(destination)
    return manifest
