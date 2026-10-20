"""逐项计算材料去处，问题字段与用途记录共同保留真实引用"""
from collections import Counter, defaultdict
import copy
from pathlib import Path
import re
import unicodedata
import posixpath


STRUCTURAL = {'webpage', 'body', 'main', 'section', 'p', 'header', 'footer', 'nav', 'ul', 'li',
              'tbody', 'tr', 'document', 'list', 'key_value_area', 'furniture', 'source_index',
              'repository', 'directory'}
ALWAYS_STRUCTURAL = {'repository', 'directory', 'document', 'body', 'furniture', 'source_index'}


def walk(node):
    yield node
    for child in node.get('children', []):
        yield from walk(child)


def text_of(node):
    content = node.get('content', {})
    return node.get('text') or content.get('text') or content.get('name') or ''


def source_of(node):
    source = node.get('source', {})
    return source[0] if isinstance(source, list) and source else source if isinstance(source, dict) else {}


def representation_links(material, root=None):
    """沿用解析器已确认的同内容关联，并补充可以直接解析的符号链接"""
    links = copy.deepcopy(material.get('representation_links', {}))
    nodes = list(walk(material['tree']))
    paths = {source_of(n).get('path'): n['id'] for n in nodes if n['type'] in {'file', 'directory', 'symlink'} and source_of(n).get('path')}

    def directories(node, parent=''):
        current = parent
        if node['type'] == 'directory':
            current = source_of(node).get('path') or posixpath.join(parent, text_of(node))
            paths.setdefault(current, node['id'])
        for child in node.get('children', []):
            directories(child, current)

    directories(material['tree'])
    for node in nodes:
        if node['type'] != 'symlink':
            continue
        source = source_of(node)
        target = source.get('symbol_target') or source.get('target')
        if target and target not in paths and source.get('path'):
            target = posixpath.normpath(posixpath.join(posixpath.dirname(source['path']), target))
        if target in paths and paths[target] != node['id']:
            links.setdefault(node['id'], {'targets': [paths[target]], 'method': 'resolved_symlink',
                                          'reason': '符号链接指向同一份已保存内容，入口与目标继续保留'})
    indexed = [n for n in nodes if n['type'] == 'source_text' and n['id'] not in links]
    if not indexed:
        return links
    heights = {}
    pages = material.get('pages', {})
    if isinstance(pages, dict):
        heights = {int(key): value.get('size', value).get('height') for key, value in pages.items() if isinstance(value, dict)}

    def pdf_path(value):
        if isinstance(value, dict):
            for child in value.values():
                found = pdf_path(child)
                if found:
                    return found
        elif isinstance(value, str) and value.lower().endswith('.pdf'):
            path = Path(value)
            if not path.is_absolute() and root:
                path = Path(root) / value.lstrip('/')
            if path.is_file():
                return path
        return None

    if not heights and (path := pdf_path(material.get('original', {}))):
        import pymupdf
        with pymupdf.open(path) as pdf:
            heights = {i + 1: page.rect.height for i, page in enumerate(pdf)}
    normal = lambda value: re.sub(r'\s+', '', unicodedata.normalize('NFKC', value or ''))
    by_page = defaultdict(list)
    for node in nodes:
        if node['type'] == 'source_text':
            continue
        source = source_of(node)
        for provenance in source.get('provenance', []):
            box, page = provenance.get('bbox'), provenance.get('page_no')
            if not isinstance(box, dict):
                continue
            if box.get('coord_origin') == 'BOTTOMLEFT':
                if not heights.get(page):
                    continue
                rect = box['l'], heights[page] - box['t'], box['r'], heights[page] - box['b']
            else:
                rect = box['l'], box['t'], box['r'], box['b']
            by_page[page].append((node['id'], rect, normal(text_of(node))))
    for node in indexed:
        source = source_of(node)
        box, page = source.get('bbox'), source.get('page')
        if not isinstance(box, list) or len(box) != 4:
            continue
        candidates = [item for item in by_page[page] if min(box[2], item[1][2]) > max(box[0], item[1][0])
                      and min(box[3], item[1][3]) > max(box[1], item[1][1])]
        text = normal(text_of(node))
        exact = [item[0] for item in candidates if text and text == item[2]]
        contained = [item[0] for item in candidates if text and text in item[2]]
        if exact:
            targets, method = exact, 'exact_text_and_position'
        elif contained:
            targets, method = contained, 'contained_text_and_position'
        elif text and text == ''.join(item[2] for item in candidates):
            targets, method = [item[0] for item in candidates], 'composite_text_and_position'
        else:
            targets, method = [item[0] for item in candidates], 'position_variant_preserved'
        if targets:
            links[node['id']] = {'targets': targets, 'method': method,
                                 'reason': '同一页面区域的不同原文表示，差异与原图继续保留' if method == 'position_variant_preserved' else '同页坐标与实际文字对应，原始表示继续保留'}
    return links


def evaluate(document, material):
    nodes = {n['id']: n for n in walk(material['tree'])}
    required = {n['id'] for sid in document['source_roots'] if sid in nodes for n in walk(nodes[sid])}
    questions = list(walk(document['tree']))
    leaves = {q['id']: q for q in questions if not q.get('children')}
    modern = document.get('planning_version') == 2
    preface = {qid for qid in leaves if qid.startswith('q.0.')}
    direct, owners = defaultdict(set), defaultdict(set)
    for qid, q in leaves.items():
        for sid in q['source_nodes']:
            if sid not in nodes:
                continue
            direct[sid].add(qid)
            for n in walk(nodes[sid]) if modern else [nodes[sid]]:
                owners[n['id']].add(qid)
    routes = {}
    for sid, node in nodes.items():
        if owners[sid]:
            role = 'preface' if owners[sid] & preface else 'teach'
            routes[sid] = {'role': role, 'question_ids': sorted(owners[sid]),
                           'destination': '第 0 章问题' if role == 'preface' else '正文具体问题',
                           'reason': '具体问题选择了这一来源，分支引用按实际后代展开' if modern else '历史问题直接引用了这一来源'}
        if modern and node['type'] in STRUCTURAL and (not text_of(node).strip() or node['type'] in ALWAYS_STRUCTURAL):
            routes[sid] = {'role': 'structure', 'question_ids': sorted(owners[sid]),
                           'destination': '材料层级与定位', 'reason': '解析器保留的材料容器，其下内容独立分配'}
    issues = []
    for entry in document.get('dispositions', []) if modern else []:
        unknown = set(entry['source_nodes']) - nodes.keys()
        allowed_questions = leaves.keys() if entry['role'] == 'reference' else {q['id'] for q in questions}
        invalid_questions = set(entry['question_ids']) - allowed_questions
        if unknown or invalid_questions:
            issues.append('用途记录引用了不存在的材料或具体问题：' + ', '.join(sorted(unknown | invalid_questions)))
        for sid in entry['source_nodes']:
            if sid not in nodes:
                continue
            for node in walk(nodes[sid]) if entry['extent'] == 'subtree' else [nodes[sid]]:
                nid = node['id']
                selected = owners[nid] | (set(entry['question_ids']) & leaves.keys())
                role = entry['role']
                if role == 'excluded' and direct[nid]:
                    issues.append('直接用于讲解的来源同时被排除：' + nid)
                if role == 'reference' and selected & preface:
                    role = 'preface'
                routes[nid] = {'role': role, 'question_ids': sorted(selected),
                               'destination': entry['destination'], 'reason': entry['reason']}
    links = document.get('representation_links', {}) if modern else {}
    resolved, unresolved = set(), []

    def link(sid, visiting):
        if sid in resolved:
            return routes.get(sid)
        if sid in visiting or sid not in nodes:
            return None
        relation = links.get(sid)
        if relation is None:
            return routes.get(sid)
        targets = relation.get('targets', [])
        target_routes = [link(target, visiting | {sid}) for target in targets]
        if not targets or not all(target_routes):
            unresolved.append(sid)
            return routes.get(sid)
        target_owners = {qid for target in targets for n in walk(nodes[target])
                         for qid in routes.get(n['id'], {}).get('question_ids', [])}
        # 问题字段中的引用继续保留，不让重复表示或旧用途遮住新增引用
        selected = owners[sid] | set(routes.get(sid, {}).get('question_ids', [])) | target_owners
        routes[sid] = {'role': 'variant' if relation.get('method') == 'position_variant_preserved' else 'duplicate',
                       'question_ids': sorted(selected), 'targets': targets, 'method': relation.get('method', ''),
                       'destination': '关联同一内容的来源表示', 'reason': relation['reason']}
        resolved.add(sid)
        return routes[sid]

    for sid in links:
        link(sid, set())
    missing = sorted(sid for sid in required if sid not in routes or
                     routes[sid]['role'] in {'teach', 'preface', 'reference'} and not routes[sid]['question_ids'])
    teaching = {sid for sid in required if routes.get(sid, {}).get('role') in {'teach', 'preface'}}
    teaching_missing = set(missing)
    denominator = len(teaching | teaching_missing)
    kinds = Counter(nodes[sid]['type'] for sid in required)
    covered = Counter(nodes[sid]['type'] for sid in required - set(missing))
    total = len(required)
    count = total - len(missing)
    edge_count = sum(len(routes.get(sid, {}).get('question_ids', [])) for sid in required)
    summary = {'total': total, 'covered': count, 'percentage': round(100 * count / total, 4) if total else 0,
               'links': edge_count, 'mapping_percentage': round(100 * edge_count / total, 4) if total else 0,
               'leaf_questions': len(leaves), 'unmapped': missing,
               'by_type': {kind: {'total': n, 'covered': covered[kind]} for kind, n in sorted(kinds.items())}}
    if modern:
        summary.update(disposition_percentage=summary['percentage'], teaching_nodes=denominator,
                       teaching_assigned=len(teaching), teaching_percentage=round(100 * len(teaching) / denominator, 4) if denominator else 100,
                       preface_required=document['metadata']['present'], preface_questions=len(preface),
                       preface_missing=bool(document['metadata']['present'] and not preface),
                       roles=dict(Counter(routes[sid]['role'] for sid in required if sid in routes)))
    return {'material_tree': document['material_tree'], 'material_run': document['material_run'],
            'scope': document['scope'], 'summary': summary,
            'rule': '脚本按完整材料范围核对用途和具体问题引用，未知用途继续列为缺项' if modern else '历史问题继续按原来的直接引用计算',
            'nodes': [{'material_node': sid, 'type': nodes[sid]['type'], **routes.get(sid, {'role': 'unassigned', 'question_ids': []})}
                      for sid in nodes if sid in required],
            'issues': issues, 'unresolved_links': sorted(set(unresolved))}


def missing_index(document, material, report):
    pending = set(report['summary']['unmapped'])
    roles = {row['material_node']: row['role'] for row in report['nodes']}
    sizes = {}
    def count(node):
        children = [count(child) for child in node.get('children', [])]
        missing = int(node['id'] in pending) + sum(pair[0] for pair in children)
        eligible = int(node['id'] in pending or roles.get(node['id']) not in {'structure', 'duplicate', 'variant'}) + sum(pair[1] for pair in children)
        sizes[node['id']] = missing, eligible
        return missing, eligible
    count(material['tree'])
    rows = []
    def visit(node, parent=None):
        missing, eligible = sizes[node['id']]
        if not missing:
            return
        if missing == eligible or node['id'] in pending:
            source = source_of(node)
            rows.append({'id': node['id'], 'type': node['type'], 'parent': parent,
                         'path_or_page': source.get('path') or source.get('page'),
                         'text': text_of(node), 'pending_in_subtree': missing})
        if missing != eligible:
            for child in node.get('children', []):
                visit(child, node['id'])
    visit(material['tree'])
    return {'coverage': report['summary'], 'format_errors': document.get('validation', {}).get('errors', []), 'rows': rows}


def apply_patch(document, patch):
    result = copy.deepcopy(document)
    lookup = {q['id']: q for q in walk(result['tree'])}
    for q in patch.get('question_updates', []):
        if q['id'] in lookup:
            lookup[q['id']].update({k: copy.deepcopy(v) for k, v in q.items() if k != 'children'})
    for entry in patch.get('new_questions', []):
        q = copy.deepcopy(entry['question'])
        parent = lookup.get(entry['parent_question_id'])
        if parent is None or q['id'] in lookup:
            continue
        siblings = parent.setdefault('children', [])
        after = entry['after_question_id']
        position = 0 if q['id'] == 'q.0' else next((i + 1 for i, sibling in enumerate(siblings) if sibling['id'] == after), len(siblings))
        siblings.insert(position, q)
        lookup.update({item['id']: item for item in walk(q)})
        added = [item['id'] for item in walk(q) if not item.get('children')]
        order = result['learning_order']
        position = 0 if q['id'] == 'q.0' else order.index(after) + 1 if after in order else len(order)
        order[position:position] = added
    for entry in patch.get('source_additions', []):
        q = lookup.get(entry['question_id'])
        if q is not None and not q.get('children'):
            q['source_nodes'] = list(dict.fromkeys(q['source_nodes'] + entry['source_nodes']))
            if entry['use'] == 'reference':
                result['dispositions'].append({'source_nodes': entry['source_nodes'], 'extent': 'subtree',
                                               'role': 'reference', 'question_ids': [q['id']],
                                               'destination': '具体问题的查阅来源', 'reason': entry['reason']})
    result['dispositions'].extend(copy.deepcopy(patch.get('dispositions', [])))
    if patch.get('learning_order'):
        result['learning_order'] = patch['learning_order']
    return result
