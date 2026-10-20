"""把已经完成的正文组装成独立预览，保留原稿、真实检查结果和辅助内容来源"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re


CORE_FIELDS = ('question_id', 'problem', 'explanation', 'synthesis', 'summary')
SUPPORT_FIELDS = ('opening', 'summary', 'pitfalls', 'quiz')


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _relative(path, root):
    return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()


def _units(value):
    return value if isinstance(value, list) else value['units']


def _signature(value):
    return [{key: row.get(key) for key in CORE_FIELDS} for row in _units(value)]


def _responses(folder, work, prefix, stage):
    paths = []
    staged = folder / stage / 'response.json'
    if staged.is_file():
        paths.append(staged)
    paths.extend(sorted((work / 'calls').glob(prefix + '-' + stage + '-[0-9][0-9].json')))
    return [(path, _read(path)) for path in paths]


def _same_identity(left, right):
    return all(left.get(key) == right.get(key) for key in ('id', 'chinese', 'english', 'abbreviation'))


def _term_body(row):
    return (isinstance(row, dict) and isinstance(row.get('definition'), str)
            and bool(row['definition'].strip()) and isinstance(row.get('explanation'), list)
            and len(row['explanation']) == 2
            and all(isinstance(text, str) and text.strip() for text in row['explanation']))


def _support_ok(value, qids):
    return (isinstance(value, dict) and all(key in value for key in SUPPORT_FIELDS)
            and isinstance(value['opening'], dict) and isinstance(value['opening'].get('text'), str)
            and isinstance(value['summary'], list)
            and [row.get('question_id') for row in value['summary']] == qids
            and isinstance(value['pitfalls'], list) and isinstance(value['quiz'], list)
            and all(set(row.get('question_ids', [])) <= set(qids) for row in value['quiz']))


def _auxiliary(root, work, section, current, old, old_path):
    """只复用同一冻结小节的真实响应，原模型输出保持原样"""
    sid = section.name
    qids = [row['question_id'] for row in old['core_questions']]
    support = copy.deepcopy(old)
    support_path = old_path
    support_current = False
    current_terms = {}
    current_term_paths = {}
    latest_metadata = None
    latest_metadata_path = None
    for folder in sorted((section / 'extras-batches').glob('r[0-9]*/v[0-9]*')):
        inputs_path = folder / 'inputs.json'
        if not inputs_path.is_file():
            continue
        inputs = _read(inputs_path)
        if _signature(inputs.get('draft', {'units': []})) != _signature(current):
            continue
        prefix = sid + '-extras-' + folder.parent.name + '-' + folder.name
        complete = _responses(folder, work, prefix, 'complete-response')
        for name in ('merged-extras.json', 'complete-extras.json'):
            if (folder / name).is_file():
                complete.append((folder / name, _read(folder / name)))
        for path, value in complete:
            if _support_ok(value, qids):
                support, support_path, support_current = copy.deepcopy(value), path, True
            full_terms = value.get('terms', []) if isinstance(value, dict) else []
            if full_terms:
                current_terms, current_term_paths = {}, {}
                latest_metadata, latest_metadata_path = None, None
            for term in full_terms:
                if _term_body(term) and term.get('id'):
                    current_terms[term['id']] = copy.deepcopy(term)
                    current_term_paths[term['id']] = path
        for path, value in _responses(folder, work, prefix, 'support'):
            if _support_ok(value, qids):
                support, support_path, support_current = copy.deepcopy(value), path, True
        metadata_path = folder / 'frozen-term-metadata.json'
        if metadata_path.is_file():
            metas = _read(metadata_path)
            bodies = {}
            body_paths = {}
            stage_names = {path.name for path in folder.glob('terms-[0-9]*') if path.is_dir()}
            stage_names.update(re.findall(r'-(terms-\d{4})-\d{2}\.json$', path.name)[0]
                               for path in (work / 'calls').glob(prefix + '-terms-[0-9]*-[0-9][0-9].json')
                               if re.findall(r'-(terms-\d{4})-\d{2}\.json$', path.name))
            for stage in sorted(stage_names):
                for path, value in _responses(folder, work, prefix, stage):
                    for row in value.get('terms', []) if isinstance(value, dict) else []:
                        if _term_body(row):
                            bodies[row['id']] = row
                            body_paths[row['id']] = path
            latest_metadata, latest_metadata_path = metas, metadata_path
            for meta in metas:
                if meta['id'] in bodies:
                    current_terms[meta['id']] = {**copy.deepcopy(meta), **copy.deepcopy(bodies[meta['id']])}
                    current_term_paths[meta['id']] = body_paths[meta['id']]
    old_terms = {row['id']: row for row in old.get('glossary', [])}
    terms, term_provenance, missing = [], [], []
    selected = latest_metadata if latest_metadata is not None else list(current_terms.values())
    if not selected:
        selected = list(old_terms.values())
    for meta in selected:
        tid = meta['id']
        actual, source, current_body = None, None, False
        if tid in current_terms and _same_identity(meta, current_terms[tid]):
            actual, source, current_body = current_terms[tid], current_term_paths[tid], True
        elif tid in old_terms and _same_identity(meta, old_terms[tid]) and _term_body(old_terms[tid]):
            actual, source = old_terms[tid], old_path
        if actual is None:
            missing.append({'term_id': tid, 'metadata': copy.deepcopy(meta),
                            'metadata_path': _relative(latest_metadata_path, root) if latest_metadata_path else None,
                            'reason': '该术语已有名称登记，当前没有可复用的完整解释'})
            continue
        terms.append(copy.deepcopy(actual))
        term_provenance.append({'term_id': tid, 'path': _relative(source, root),
                                'current_unit_context': current_body})
    return support, terms, {
        'support': {'path': _relative(support_path, root), 'current_unit_context': support_current,
                    'independent_review_state': 'pending'},
        'terms': term_provenance,
        'missing_term_explanations': missing,
        'glossary_empty': not terms,
    }


def _coverage_helpers():
    spec = importlib.util.spec_from_file_location('preview_teaching_coverage', Path(__file__).with_name('teaching_coverage.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _preview_links(inventory, bindings, pack, units):
    live_blocks = {block['id'] for unit in units
                   for block in [unit['problem'], *unit['explanation'], unit['synthesis']]}
    links, errors = _coverage_helpers().build_block_sources(inventory, bindings, pack)
    unknown = sorted(set(links) - live_blocks)
    errors.extend('正文对应位置当前不存在：' + value for value in unknown)
    return {key: value for key, value in links.items() if key in live_blocks}, errors


def _pending_coverage(inventory, bindings):
    bound = {row['point_id']: row.get('block_ids', []) for row in bindings['points']}
    return {'profile': 'current-draft-unreviewed-coverage-v1', 'section_id': inventory['section_id'],
            'material_run': inventory.get('material_run'), 'total_points': len(inventory['points']),
            'explained_points': None, 'percentage': None, 'total_items': len(inventory['sources']),
            'explained_items': None, 'block_sources': {}, 'items': [
                {'source_id': source['source_id'] if 'source_id' in source else source['id'],
                 'role': source.get('role'), 'scope_note': source.get('scope_note', ''), 'explained': None,
                 'points': [{'id': point['id'], 'description': point['description'],
                             'question_id': point['question_id'], 'explained': None,
                             'block_ids': copy.deepcopy(bound.get(point['id'], [])), 'reasons': []}
                            for point in inventory['points']
                            if (source.get('source_id', source.get('id')) in point['source_ids'])]}
                for source in inventory['sources']]}


def _section(root, work, section, old, old_path):
    context = _read(section / 'context.json')
    units = _units(_read(section / 'units.json'))
    qids = [row['question_id'] for row in context['units']]
    if [row['question_id'] for row in units] != qids or [row['question_id'] for row in old['units']] != qids:
        raise ValueError('当前正文、冻结章节和旧书的问题归属需要一致：' + section.name)
    pack = _read(section / 'source-pack.json')
    inventory = _read(section / 'coverage-inventory.json')
    support, terms, provenance = _auxiliary(root, work, section, units, old, old_path)
    doc = {key: copy.deepcopy(value) for key, value in old.items()
           if key not in ('grounding', 'coverage', 'validation', 'glossary', 'local_notations')}
    for key in ('section_id', 'section_number', 'title', 'opening_title', 'core_questions',
                'transitions_path', 'transition_run', 'next_section_id', 'next_title'):
        if key in context:
            doc[key] = copy.deepcopy(context[key])
    doc.update(preview=True, status='current_draft_preview', glossary=terms)
    doc['units'] = []
    doc['preview_note_aliases'] = []
    for spec, result, previous in zip(context['units'], units, old['units']):
        actual = copy.deepcopy(result)
        actual.update(number=spec['number'], title=spec['title'], source_nodes=copy.deepcopy(spec['source_nodes']),
                      note_block_id=spec.get('note_block_id', previous['synthesis']['id']))
        doc['units'].append(actual)
        doc['preview_note_aliases'].append({'question_id': result['question_id'],
            'current_block_id': result['synthesis']['id'], 'previous_block_id': previous['synthesis']['id']})
    for key in SUPPORT_FIELDS:
        doc[key] = copy.deepcopy(support[key])
    if support.get('opening_forward'):
        doc['opening_forward'] = copy.deepcopy(support['opening_forward'])
    # 总结使用作者已经完成的逐问回答，保留章节总结原有位置和笔记编号
    answers = {row['question_id']: row['summary'] for row in units}
    aliases = {}
    summary_provenance = []
    overview_path = work / 'overview.json'
    overview = _read(overview_path) if overview_path.is_file() else {}
    overview_answers = {row['question_id']: row['answer'] for row in overview.get('answers', [])}
    for goal in doc.get('context_goals', []):
        if goal.get('question_id') in overview_answers:
            goal['answer'] = overview_answers[goal['question_id']]
    if doc.get('book_introduction') and overview.get('introduction'):
        doc['book_introduction'] = overview['introduction']
    for row in doc['summary']:
        qid = row['question_id']
        if qid in answers:
            original = answers[qid]
            row['answer']['text'] = original['text']
            aliases[original['id']] = row['answer']['id']
            source = section / 'units.json'
        elif qid in overview_answers:
            row['answer']['text'] = overview_answers[qid]
            source = overview_path
        else:
            source = old_path
        summary_provenance.append({'question_id': qid, 'path': _relative(source, root)})
    doc['local_notations'] = copy.deepcopy(support.get('local_notations', [])) if provenance['support']['current_unit_context'] else []
    for notation in doc['local_notations']:
        notation['definition_block_id'] = aliases.get(notation['definition_block_id'], notation['definition_block_id'])
        notation['scope_block_ids'] = list(dict.fromkeys(aliases.get(key, key) for key in notation['scope_block_ids']))
    bindings = {'section_id': section.name, 'points': [copy.deepcopy(row) for unit in units for row in unit['bindings']]}
    links, link_errors = _preview_links(inventory, bindings, pack, units)
    doc['preview_source_links'] = links
    coverage_path = section / 'coverage.json'
    coverage = _read(coverage_path) if coverage_path.is_file() else _pending_coverage(inventory, bindings)
    review_path = section / 'review.json'
    review = _read(review_path) if review_path.is_file() else None
    doc['validation'] = {'passed': False, 'errors': [], 'status': 'preview_not_published'}
    doc['coverage'] = copy.deepcopy(coverage)
    doc['preview_status'] = {'state': 'review_pending', 'unit_count': len(units),
                             'source_link_errors': link_errors, 'new_model_calls': 0}
    doc['preview_provenance'] = {'current_units_path': _relative(section / 'units.json', root),
        'current_context_path': _relative(section / 'context.json', root),
        'published_section_path': _relative(old_path, root), 'published_validation': old.get('validation'),
        'published_coverage': old.get('coverage'), 'auxiliary': provenance,
        'coverage_path': _relative(coverage_path, root) if coverage_path.is_file() else None,
        'review_path': _relative(review_path, root) if review_path.is_file() else None,
        'review_applies_to_current_preview': False,
        'summary_sources': summary_provenance, 'source_links_state': 'association_pending_review'}
    return doc, pack, inventory, bindings, coverage, review


def _prepare(root, work):
    book = _read(root / '05_writing/book.json')
    result = []
    for chapter in book['chapters']:
        for row in chapter['sections']:
            old_path = root / row['path']
            result.append((row, _section(root, work, work / 'sections' / row['id'], _read(old_path), old_path)))
    sections = [item[1][0] for item in result]
    report = {'case': root.name, 'sections': len(sections), 'units': sum(len(doc['units']) for doc in sections),
        'current_support_sections': sum(doc['preview_provenance']['auxiliary']['support']['current_unit_context'] for doc in sections),
        'reused_published_support_sections': sum(not doc['preview_provenance']['auxiliary']['support']['current_unit_context'] for doc in sections),
        'missing_term_explanations': [{'section_id': doc['section_id'], **copy.deepcopy(item)} for doc in sections
            for item in doc['preview_provenance']['auxiliary']['missing_term_explanations']],
        'empty_glossary_sections': [doc['section_id'] for doc in sections if not doc['glossary']],
        'source_link_errors': [{'section_id': doc['section_id'], 'errors': doc['preview_status']['source_link_errors']}
            for doc in sections if doc['preview_status']['source_link_errors']],
        'note_keys_match_published': all(
            unit['note_block_id'] == alias['previous_block_id']
            for doc in sections for unit, alias in zip(doc['units'], doc['preview_note_aliases'])),
        'note_key_checks': [{'section_id': doc['section_id'], 'question_id': unit['question_id'],
             'preview_note_block_id': unit['note_block_id'], 'published_note_block_id': alias['previous_block_id'],
             'actual_synthesis_block_id': unit['synthesis']['id'],
             'matches': unit['note_block_id'] == alias['previous_block_id']}
            for doc in sections for unit, alias in zip(doc['units'], doc['preview_note_aliases'])],
        'new_model_calls': 0, 'independent_review_state': 'pending'}
    return book, result, report


def inspect_current_preview(root, work=None):
    root = Path(root).resolve()
    work = Path(work).resolve() if work else root / '05_writing/full-work/run-0002'
    return _prepare(root, work)[2]


def export_current_preview(root, work=None, version=None):
    """一次写出当前稿的新快照，旧正式书、工作材料与真实调用记录保持原样"""
    root = Path(root).resolve()
    work = Path(work).resolve() if work else root / '05_writing/full-work/run-0002'
    version = version or datetime.now(timezone.utc).strftime('draft-%Y%m%d-%H%M%S')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', version):
        raise ValueError('预览版本只能包含字母、数字、连字符和下划线')
    book, sections, report = _prepare(root, work)
    target = root / '05_writing/current-draft-preview' / version
    if target.exists():
        raise FileExistsError('该预览快照已经存在，原快照保留：' + str(target))
    target.mkdir(parents=True)
    manifest = copy.deepcopy(book)
    manifest.update(preview=True, status='current_draft_preview', writing_run=version,
                    validation={'passed': False, 'errors': [], 'status': 'preview_not_published'},
                    coverage={'state': 'review_pending', 'percentage': None})
    manifest['preview_provenance'] = {'published_book_path': '05_writing/book.json',
        'published_validation': copy.deepcopy(book.get('validation')),
        'published_coverage': copy.deepcopy(book.get('coverage')), 'work_path': _relative(work, root)}
    overview_path = work / 'overview.json'
    if overview_path.is_file():
        overview = _read(overview_path)
        answers = {row['question_id']: row['answer'] for row in overview.get('answers', [])}
        if overview.get('introduction'):
            manifest['introduction'] = overview['introduction']
        for goal in manifest.get('goals', []):
            if goal['question_id'] in answers:
                goal['answer'] = answers[goal['question_id']]
        manifest['preview_provenance']['overview_path'] = _relative(overview_path, root)
        _save(target / 'overview.json', overview)
    paths = {}
    for row, (doc, pack, inventory, bindings, coverage, review) in sections:
        sid = doc['section_id']
        part = target / 'sections' / sid
        artifacts = {'source-pack.json': pack, 'coverage-inventory.json': inventory,
                     'coverage-bindings.json': bindings, 'coverage.json': coverage}
        if review is not None:
            artifacts['review.json'] = review
        for filename, value in artifacts.items():
            _save(part / filename, value)
        doc['grounding'] = {name + '_path': _relative(part / filename, root)
            for name, filename in [('source_pack', 'source-pack.json'), ('inventory', 'coverage-inventory.json'),
                                   ('bindings', 'coverage-bindings.json'), ('coverage', 'coverage.json')]}
        if review is not None:
            doc['grounding']['review_path'] = _relative(part / 'review.json', root)
        doc['writing_run'] = version
        path = target / 'sections' / (sid + '.json')
        _save(path, doc)
        paths[sid] = _relative(path, root)
    for chapter in manifest['chapters']:
        for row in chapter['sections']:
            row['path'] = paths[row['id']]
    manifest['preview_status'] = copy.deepcopy(report)
    report['version'] = version
    report['manifest_path'] = '05_writing/preview-book.json'
    report['snapshot_path'] = _relative(target, root)
    _save(target / 'delivery-report.json', report)
    # 本脚本只组装本地文件，模型消耗为零，外层代理用量没有可核对数据时保留未知
    _save(target / 'delivery-usage.json', {'profile': 'current-draft-export-usage-v1', 'model_calls': [],
        'actual_new_model_call_count': 0, 'input_tokens': 0, 'output_tokens': 0,
        'cached_input_tokens': None, 'outer_agent_tokens': None,
        'cache_state': 'no_new_model_calls', 'outer_agent_usage_state': 'unknown',
        'existing_generation_usage_path': _relative(work / 'book-usage.json', root) if (work / 'book-usage.json').is_file() else None})
    _save(target / 'book.json', manifest)
    temporary = root / '05_writing/preview-book.json.tmp'
    _save(temporary, manifest)
    temporary.replace(root / '05_writing/preview-book.json')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='把当前已完成正文导出为独立阅读预览')
    parser.add_argument('root')
    parser.add_argument('--work')
    parser.add_argument('--version')
    parser.add_argument('--inspect', action='store_true')
    args = parser.parse_args()
    result = inspect_current_preview(args.root, args.work) if args.inspect else export_current_preview(args.root, args.work, args.version)
    print(json.dumps(result, ensure_ascii=False, indent=2))
