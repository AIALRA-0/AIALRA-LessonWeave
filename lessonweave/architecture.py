"""把当前框架和项目产物转换为只读的流程展示，查看页面时不执行生成任务"""
from functools import lru_cache
from pathlib import Path, PureWindowsPath
from urllib.parse import quote
import json
import re
import time

REPO = Path(__file__).resolve().parents[1]
FRAME = REPO / 'framework'
VIEW = FRAME / 'architecture'
EXAMPLE = FRAME / 'examples/minimal-web'
FILES = {
    'input': ('00_source/input.json', '00_source/input.schema.json'),
    'source': ('00_source/source.json', '00_source/source.schema.json'),
    'material': ('01_tree/tree.json', '01_tree/tree.schema.json'),
    'questions': ('02_questions/questions.json', '02_questions/questions.schema.json'),
    'chapters': ('03_chapters/chapters.json', '03_chapters/chapters.schema.json'),
    'transitions': ('04_transitions/transitions.json', '04_transitions/transitions.schema.json'),
    'independent_check': ('05_writing/checks/independent-before.json', None),
    'repair': ('05_writing/checks/batch-repair.json', None),
    'source_locations': ('05_writing/source-location/index.json', None),
    'package': ('05_writing/book.json', '05_writing/book.schema.json'),
    'library': ('runtime/trilium/current.json', None),
    'readweave': ('runtime/readweave/current.json', None),
}


@lru_cache(maxsize=64)
def _cached_json(path, modified, size):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def load(path):
    path = Path(path)
    if not path.is_file():
        return None
    try:
        stat = path.stat()
        return _cached_json(str(path), stat.st_mtime_ns, stat.st_size)
    except (ValueError, OSError):
        return None


def within(root, relative):
    path = (root / relative).resolve()
    return path if path.is_relative_to(root.resolve()) else None


def walk(node, prefix='tree'):
    if not isinstance(node, dict):
        return
    yield prefix, node
    for index, child in enumerate(node.get('children', [])):
        yield from walk(child, prefix + '.children[' + str(index) + ']')


def pick(document, predicate):
    return next(((prefix, node) for prefix, node in walk((document or {}).get('tree')) if predicate(node)), ('tree', {}))


def lookup(value, path):
    for part in re.findall(r'[^.\[\]]+', path):
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return None
    return value


def has_path(value, path):
    for part in re.findall(r'[^.\[\]]+', path):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return False
    return True


def schema_type(relative, path):
    schema = load(FRAME / relative) if relative else None
    node = schema
    for part in re.findall(r'[^.\[\]]+', path):
        if not isinstance(node, dict):
            return '按实际产物记录'
        while '$ref' in node and node['$ref'].startswith('#/'):
            node = lookup(schema, node['$ref'][2:].replace('/', '.'))
            if not isinstance(node, dict):
                return '按实际产物记录'
        node = node.get('items', {}) if part.isdigit() else node.get('properties', {}).get(part, {})
    if isinstance(node, dict):
        if '$ref' in node:
            node = lookup(schema, node['$ref'][2:].replace('/', '.')) or {}
        value = node.get('type')
        names = {'string': '字符串', 'array': '列表', 'object': '对象', 'boolean': '布尔值', 'integer': '整数', 'number': '数值', 'null': '空值'}
        if isinstance(value, list):
            return ' / '.join(names.get(item, item) for item in value)
        if value:
            return names.get(value, value)
    return '按实际产物记录'


def contexts(root):
    docs = {}
    for key, (relative, schema) in FILES.items():
        docs[key] = {'value': load(root / relative), 'file': relative, 'schema': schema, 'prefix': ''}
    selections = [
        ('material_group', 'material', lambda n: bool(n.get('children')) and n.get('type') in {'section', 'document', 'webpage', 'repository'}),
        ('material_node', 'material', lambda n: n.get('type') in {'paragraph', 'code', 'file'} and bool(n.get('content'))),
        ('question_node', 'questions', lambda n: not n.get('children') and bool(n.get('question'))),
        ('chapter_node', 'chapters', lambda n: n.get('kind') == 'section'),
        ('transition_node', 'transitions', lambda n: n.get('kind') == 'section'),
    ]
    for key, parent, predicate in selections:
        prefix, node = pick(docs[parent]['value'], predicate)
        docs[key] = dict(docs[parent], value=node, prefix=prefix)
    # 当前预览与已发布版本都读取保存的文件，较新的预览继续保留待审状态
    books = [root / '05_writing/book.json', root / '05_writing/preview-book.json']
    books = sorted((p for p in books if p.is_file()), key=lambda p: p.stat().st_mtime_ns, reverse=True)
    book_path = next((p for p in books if isinstance(load(p), dict)), None)
    book = load(book_path) if book_path else None
    docs['book'] = {'value': book, 'file': str(book_path.relative_to(root)).replace('\\', '/') if book_path else '05_writing/book.json', 'schema': '05_writing/book.schema.json', 'prefix': ''}
    section_ref = next((s.get('path') for c in (book or {}).get('chapters', []) for s in c.get('sections', []) if s.get('path')), None)
    section_path = within(root, section_ref) if section_ref else None
    section = load(section_path) if section_path else None
    # 仍在写作时，展示已有的候选单元，保留它的文件位置与检查状态
    work = root / '05_writing/work'
    if not section:
        candidate = next(iter(sorted(work.glob('sections/*/candidate.json'))), None)
        if candidate:
            section_path, section = candidate, load(candidate)
    section_file = str(section_path.relative_to(root)).replace('\\', '/') if section_path else '05_writing/work/sections/尚未生成/candidate.json'
    docs['section'] = {'value': section, 'file': section_file, 'schema': '05_writing/demo.schema.json', 'prefix': ''}
    units = (section or {}).get('units', [])
    docs['unit'] = dict(docs['section'], value=units[0] if units else {}, prefix='units[0]')
    section_id = (section or {}).get('section_id')
    evidence = work / 'sections' / section_id if section_id and '/' not in section_id and '\\' not in section_id else None
    inventory_path = evidence / 'inventory.json' if evidence else None
    coverage_path = evidence / 'coverage.json' if evidence else None
    grounding = (section or {}).get('grounding', {})
    if grounding.get('inventory_path'):
        inventory_path = within(root, grounding['inventory_path'])
    if grounding.get('coverage_path'):
        coverage_path = within(root, grounding['coverage_path'])
    # 老版本把覆盖记录放在小节旁，按实际文件保留该版本的来源
    if section_path:
        inventory_path = next((p for p in [inventory_path, evidence / 'coverage-inventory.json' if evidence else None, section_path.with_name(section_path.stem + '-inventory.json')] if p and p.is_file()), inventory_path)
        coverage_path = next((p for p in [coverage_path, section_path.with_name(section_path.stem + '-coverage.json')] if p and p.is_file()), coverage_path)
    if inventory_path is None or not inventory_path.is_file():
        inventory_path = next(iter(sorted(work.glob('sections/*/coverage-inventory.json'))), None)
    for key, path, schema in [('inventory', inventory_path, '05_writing/coverage-inventory.schema.json'), ('coverage', coverage_path, None)]:
        docs[key] = {'value': load(path) if path else None, 'file': str(path.relative_to(root)).replace('\\', '/') if path else '05_writing/work/sections/尚未生成/' + key + '.json', 'schema': schema, 'prefix': ''}
    if not docs['independent_check']['value'] and docs['coverage']['value']:
        docs['independent_check']=dict(docs['coverage'])
    registry_path = root / '01_tree/points.json'
    docs['registry'] = {'value': load(registry_path), 'file': '01_tree/points.json', 'schema': '01_tree/points.schema.json', 'prefix': ''}
    points = (docs['registry']['value'] or {}).get('points', [])
    docs['point'] = dict(docs['registry'], value=points[0] if points else {}, prefix='points[0]')
    folder = inventory_path.parent if inventory_path else None
    qid = units[0].get('question_id') if units else None
    safe_qid = qid if isinstance(qid, str) and '/' not in qid and '\\' not in qid else None
    authored_path = folder / ('unit-' + safe_qid + '.json') if folder and safe_qid else None
    # 新结构只读取当前小节明确采用的写作版本，旧段落不会被切成四段伪装成新稿
    authored = load(authored_path) if authored_path and (section or {}).get('writing_contract_version') else None
    for key, name, schema in [('bridge', 'bridge.json', '05_writing/bridge.schema.json'), ('glossary', 'glossary.json', '05_writing/glossary.schema.json')]:
        path = folder / name if folder else None
        docs[key] = {'value': load(path) if path and (section or {}).get('writing_contract_version') else None,
                     'file': str(path.relative_to(root)).replace('\\', '/') if path else '05_writing/work/sections/<section>/' + name,
                     'schema': schema, 'prefix': ''}
    docs['authored'] = {'value': authored, 'file': str(authored_path.relative_to(root)).replace('\\', '/') if authored_path else '05_writing/work/sections/<section>/unit-<question>.json', 'schema': '05_writing/writing-unit.schema.json', 'prefix': ''}
    docs['previous_authored'] = dict(docs['authored'], value=None, file='05_writing/work/sections/<previous>/unit-<question>.json')
    terms = (docs['glossary']['value'] or {}).get('terms', [])
    docs['term'] = dict(docs['glossary'], value=terms[0] if terms else {}, prefix='terms[0]')
    source_pack_path = within(root, grounding.get('source_pack_path', '')) if grounding.get('source_pack_path') else folder / 'source-pack.json' if folder else None
    source_pack = load(source_pack_path) if source_pack_path else None
    sentence = next((r for s in (source_pack or {}).get('sources', []) for r in s.get('sentences', [])), None)
    docs['sentence'] = {'value': sentence, 'file': str(source_pack_path.relative_to(root)).replace('\\', '/') if source_pack_path else '05_writing/work/sections/<section>/source-pack.json', 'schema': None, 'prefix': 'sources[0].sentences[0]'}
    points = (docs['inventory']['value'] or {}).get('points', [])
    docs['inventory_point'] = dict(docs['inventory'], value=points[0] if points else {}, prefix='points[0]')
    coverage = docs['coverage']['value'] or {}
    point = next(((i, p) for i, item in enumerate(coverage.get('items', [])) for p in item.get('points', [])), None)
    docs['coverage_point'] = dict(docs['coverage'], value=point[1] if point else {}, prefix='items[' + str(point[0]) + '].points[0]' if point else 'items[0].points[0]')
    return docs


def framework_contexts():
    docs = {key: {'value': None, 'file': relative, 'schema': schema, 'prefix': ''} for key, (relative, schema) in FILES.items()}
    for key, parent in [('material_node', 'material'), ('material_group', 'material'), ('question_node', 'questions'), ('chapter_node', 'chapters'), ('transition_node', 'transitions')]:
        docs[key] = dict(docs[parent], prefix='tree')
    for key, relative, schema in [('book', '05_writing/book.json', '05_writing/book.schema.json'), ('section', '05_writing/sections/section.json', '05_writing/demo.schema.json'), ('inventory', '05_writing/work/sections/section/inventory.json', '05_writing/coverage-inventory.schema.json'), ('coverage', '05_writing/work/sections/section/coverage.json', None)]:
        docs[key] = {'value': None, 'file': relative, 'schema': schema, 'prefix': ''}
    for key, parent, prefix in [('unit', 'section', 'units[0]'), ('inventory_point', 'inventory', 'points[0]'), ('coverage_point', 'coverage', 'items[0].points[0]')]:
        docs[key] = dict(docs[parent], prefix=prefix)
    for key, file, schema, prefix in [
        ('registry', '01_tree/points.json', '01_tree/points.schema.json', ''),
        ('authored', '05_writing/work/sections/<section>/unit-<question>.json', '05_writing/writing-unit.schema.json', ''),
        ('bridge', '05_writing/work/sections/<section>/bridge.json', '05_writing/bridge.schema.json', ''),
        ('glossary', '05_writing/work/sections/<section>/glossary.json', '05_writing/glossary.schema.json', ''),
        ('sentence', '05_writing/work/sections/<section>/source-pack.json', None, 'sources[0].sentences[0]'),
    ]:
        docs[key] = {'value': None, 'file': file, 'schema': schema, 'prefix': prefix}
    docs['point'] = dict(docs['registry'], prefix='points[0]')
    docs['previous_authored'] = dict(docs['authored'], file='05_writing/work/sections/<previous>/unit-<question>.json')
    docs['term'] = dict(docs['glossary'], prefix='terms[0]')
    return docs


def display(value, limit=1200):
    if value is None:
        return None
    if not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return value if len(value) <= limit else value[:limit] + '\n…'


def ratio(label, numerator, denominator, target='100%'):
    return {'label': label, 'numerator': numerator, 'denominator': denominator, 'target': target,
            'percentage': round(numerator / denominator * 100, 2) if isinstance(numerator, (int, float)) and isinstance(denominator, (int, float)) and denominator else None}


def coverage_rows(sid, docs):
    value = lambda key: docs.get(key, {}).get('value') or {}
    if sid == '00':
        return [ratio('材料已保存', int(value('source').get('status') == 'acquired') if value('input') else None, 1 if value('input') else None)]
    if sid == '01.1':
        cov = value('material').get('coverage', {})
        content, objects = cov.get('content', {}), cov.get('objects', {})
        return [ratio('本地材料内容已提取', content.get('covered'), content.get('expected')), ratio('引用对象可读取', objects.get('available'), objects.get('expected'))]
    if sid == '02':
        cov = value('questions').get('coverage', {})
        if 'teaching_nodes' in cov:
            return [ratio('材料去向明确', cov.get('covered'), cov.get('total')), ratio('应讲解内容已有具体问题负责', cov.get('teaching_assigned'), cov.get('teaching_nodes'))]
        return [ratio('历史材料已有问题承接', cov.get('covered'), cov.get('total'))]
    if sid == '03':
        cov = value('chapters').get('coverage', {})
        return [ratio('问题已有章节归属', cov.get('assigned_questions'), cov.get('question_nodes')), ratio('问题分配次数', cov.get('assignments'), cov.get('question_nodes'), '恰好 100%')]
    if sid == '07':
        cov = value('coverage')
        if cov.get('semantic_review') == 'not_run':
            return [ratio('材料引用覆盖', cov.get('covered'), cov.get('expected'))]
        return [ratio('当前小节已讲清信息点', cov.get('explained_points'), cov.get('total_points'))]
    return []


def snapshot(store, project_id=None):
    definition = load(VIEW / 'stages.json')
    project = store.project(project_id) if project_id else None
    root = Path(project['path']).resolve() if project else None
    using_example = not project and any((EXAMPLE / ('05_writing/' + name)).is_file() for name in ['book.json','preview-book.json'])
    if using_example:
        root = EXAMPLE
    docs = contexts(root) if root else framework_contexts()
    jobs = [j for j in store.jobs() if project and j['project_id'] == project_id and json.loads(j['payload']).get('_type') != 'qa']
    job = jobs[0] if jobs else None
    metrics = load(root / 'runtime/metrics-final.json') if using_example else None
    if job:
        from .metrics import report
        metrics = report(root, job)
    state = load(root / 'runtime/state.json') if root else None
    base = '/p/' + quote(project_id, safe='') + '/' if project else '/framework-example/' if using_example else ''
    stages = []
    for spec in definition['stages']:
        rows = []
        for field_spec in spec['fields']:
            doc_key, field = field_spec['doc'], field_spec['field']
            explanation, rule = field_spec['description'], field_spec['rule']
            context = docs.get(doc_key, {})
            prefix = context.get('prefix', '')
            path = (prefix + '.' if prefix else '') + field
            raw = lookup(context.get('value'), field)
            present = has_path(context.get('value'), field)
            if field_spec.get('combine'):
                components = [lookup(context.get('value'), key) for key in field_spec['combine']]
                raw = ''.join(components) if all(isinstance(item, str) for item in components) else None
                present = all(has_path(context.get('value'), key) for key in field_spec['combine'])
                path = ' + '.join((prefix + '.' if prefix else '') + key for key in field_spec['combine'])
            # 上传文件显示文件名，磁盘绝对路径留在私人运行目录中
            if doc_key == 'input' and field == 'material' and isinstance(raw, str) and not raw.startswith(('https://', 'http://')):
                raw = PureWindowsPath(raw).name
            rows.append({'key': field_spec['key'], 'path': path, 'description': explanation, 'rule': rule,
                         'side': field_spec['side'], 'label': field_spec['label'],
                         'type': schema_type(context.get('schema'), path) if schema_type(context.get('schema'), path) != '按实际产物记录' else field_spec['type'], 'value': 'null' if raw is None and present else display(raw),
                         'file': ('framework/examples/minimal-web/' + context['file']) if using_example and context.get('file') else context.get('file'), 'schema': context.get('schema'),
                         'url': base + context['file'] if root and context.get('file') and context.get('value') is not None else None})
        cov = coverage_rows(spec['id'], docs)
        artifact_key = spec['artifact']
        artifact = docs.get(artifact_key, {}).get('value')
        validation = (artifact or {}).get('validation', {})
        status = '未选择项目' if not root else '尚未生成' if not artifact else '已有结果'
        if artifact and validation.get('passed') is False:
            status = '预览待审' if (artifact.get('preview') or validation.get('status') == 'preview_not_published') else '检查未通过'
        elif artifact and validation.get('passed') is True:
            status = '检查通过'
        if spec['id'] == '07' and artifact:
            status = '检查通过' if artifact.get('passed') is True else '检查未通过' if artifact.get('passed') is False else '已有覆盖记录，待审'
        if spec['id']=='08' and artifact:
            status='已完成，无需执行' if not artifact.get('model_calls') else '已完成一轮批量修复'
        if spec['id']=='11' and root:
            status='已导出阅读包' if (root/'05_writing/reading-package.zip').is_file() else '尚未导出'
        if spec['id'] == '00' and artifact:
            status = {'acquired': '材料已保存', 'unavailable': '获取失败'}.get(artifact.get('status'), '已有结果')
        related = [m for m in (metrics or {}).get('stages', []) if m['stage'] in spec['metrics']]
        if project and not artifact and spec['id'] in {'04', '05', '06'} and docs['section'].get('value'):
            status = '保留旧稿，本阶段新版产物尚未生成'
        if artifact and spec['id'] == '03' and not artifact.get('title_format_version'):
            status = '旧版检查通过，新版标题格式尚未生成' if validation.get('passed') else status
        if using_example:
            status = '框架真实案例 · ' + status
        stages.append(dict(spec, fields=rows, coverage=cov, status=status, metrics=related))
    image = None
    if root:
        tree = docs['material']['value'] or {}
        preview = next((p.get('preview') for p in tree.get('pages', []) if p.get('preview')), None)
        if not preview:
            preview = next((n.get('content', {}).get('asset') for _, n in walk(tree.get('tree')) if n.get('content', {}).get('asset')), None)
        path = within(root, preview.lstrip('/')) if preview else None
        if path and path.is_file():
            image = base + quote(preview.lstrip('/'), safe='/')
    book = docs.get('book', {}).get('value') or {}
    return {'profile': definition['profile'], 'template_version': definition['template_version'], 'generated_at': time.time(),
            'framework_release': REPO.name, 'project': {'id': project['id'], 'name': project['name']} if project else None,
            'state': {k: v for k, v in (state or {}).items() if k in {'status', 'stage', 'round', 'maximum', 'updated_at'}},
            'active': bool(job and job['status'] in {'running', 'queued', 'cancelling'}),
            'job': {'id': job['id'], 'status': job['status']} if job else None,
            'version': book.get('writing_run') or (docs.get('material', {}).get('value') or {}).get('run'),
            'preview': bool(book.get('preview')), 'stages': stages, 'material_image': image, 'using_example': using_example,
            'writing_contract_version': (docs['section']['value'] or {}).get('writing_contract_version', 'legacy'),
            'legacy_unit': docs['unit'].get('value') if not (docs['section']['value'] or {}).get('writing_contract_version') else None,
            'reader_url': base + 'book.html' + ('?preview=true' if book.get('preview') else '') if book else None,
            'metrics_url': '/api/jobs/' + job['id'] + '/metrics' if job else None}
