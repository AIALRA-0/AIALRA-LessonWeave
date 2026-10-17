"""按阶段保存结果，集中检查后只批量修改受影响的单元"""
from __future__ import annotations
import concurrent.futures as futures
import copy
import json
import os
from pathlib import Path
import shutil
import threading
import time

from .storage import read, save, WRITE_LOCK
from .agents import Backend
from . import legacy as flow

FRAME = flow.FRAME
STAGES = ['00_source', '01_tree', '02_questions', '03_chapters', '04_transitions', '05_writing']
PARSE = threading.BoundedSemaphore(1)


def scaffold(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for stage in STAGES:
        folder = root / stage
        folder.mkdir(exist_ok=True)
        for path in (FRAME / stage).iterdir():
            if path.is_file() and (path.suffix in {'.py', '.md'} or path.name.endswith('.schema.json')):
                target = folder / path.name
                if not target.exists():
                    shutil.copyfile(path, target)
    if not (root / '05_writing/terminology.catalog.json').is_file():
        save(root / '05_writing/terminology.catalog.json', {'profile': 'terminology-catalog-v1', 'entries': []})


def update_state(root, **values):
    with WRITE_LOCK:
        path = root / 'runtime/state.json'
        state = read(path, {'round': 0, 'feedback': {}, 'issues': []})
        state.update(values, updated_at=time.time())
        save(path, state)
        return state


def feedback(root, name, details):
    with WRITE_LOCK:
        state = read(root / 'runtime/state.json', {'round': 0, 'feedback': {}})
        state.setdefault('feedback', {})[name] = details
        save(root / 'runtime/state.json', state)


def stage_call(backend, name, prompt, schema, validate, images=None):
    published = {'02_questions':'02_questions/questions.json','03_chapters':'03_chapters/chapters.json','04_transitions':'04_transitions/transitions.json'}.get(name)
    if published and (backend.root/published).is_file():
        return read(backend.root/published)
    candidate = None
    try:
        candidate = backend.call(name, prompt, schema, images)
        result = validate(candidate)
        save(backend.root / 'runtime/checks' / (name + '.json'), {'passed': True})
        return result
    except Exception as error:
        if isinstance(error, RuntimeError):
            raise
        details = {'errors': str(error).splitlines(), 'previous': candidate}
        feedback(backend.root, name, details)
        save(backend.root / 'runtime/checks' / (name + '.json'), dict(details, passed=False))
        raise


flow.stage_call = stage_call


def prepare(root):
    payload = read(root / '00_source/input.json')
    flow.jsonschema.Draft202012Validator(read(root / '00_source/input.schema.json')).validate(payload)
    update_state(root, stage='00_source')
    if not (root / '01_tree/tree.json').is_file():
        source = flow.acquire(root, payload)
        if source['status'] != 'acquired':
            raise ValueError('获取材料时遇到问题：' + source.get('reason', ''))
        update_state(root, stage='01_tree')
        with PARSE:
            tree = flow.build_tree(root, payload, source)
        if not tree['validation']['passed']:
            raise ValueError('\n'.join(tree['validation']['errors']))


def collect(pool, items, function):
    results, errors = [], []
    pending = {pool.submit(function, item): item for item in items}
    for future in futures.as_completed(pending):
        try:
            results.append(future.result())
        except Exception as error:
            errors.append(str(error))
    if errors:
        raise ValueError('\n'.join(errors))
    return results


def review_section(root, context, folder, pack, inventory, units, extras):
    doc, bindings, catalog = flow.runtime.build_doc(root, context, folder, pack, inventory, units, extras)
    structural = []
    for unit in units:
        try:
            flow.runtime.unit_errors(unit, unit['question_id'], inventory)
        except (ValueError, KeyError) as error:
            structural.extend(unit['question_id']+': '+line for line in str(error).splitlines())
    try:
        flow.runtime.inspect_without_review(doc, root, catalog)
    except (ValueError, KeyError) as error:
        structural.extend(str(error).splitlines())
    schema = copy.deepcopy(flow.REVIEW_SCHEMA)
    check = flow.generation.obj({'index': {'type': 'integer'}, 'passed': {'type': 'boolean'}, 'block_ids': flow.generation.STRINGS, 'reason': flow.generation.STRING})
    schema['properties']['points']['items']['properties']['checks'] = flow.generation.array(check)
    schema['properties']['points']['items']['required'].append('checks')
    prompt = '独立审查当前原材料与实际正文，作者绑定是待核对证据，逐项检查信息点下的每条 checks，index 从 0 开始，每条恰好返回一次，必须在实际正文中讲清才 passed=true，并指出正文块；总点通过由程序按子项重算，同时检查清单是否漏掉原材料、数值、图表、限制、翻译、易错点与练习，作者身份不提供\n'
    prompt += json.dumps({'source_pack': flow.runtime.source_view(pack), 'inventory': inventory, 'document': flow.review_document(doc), 'bindings': bindings, 'rules': flow.generation.RULES}, ensure_ascii=False)
    reviewer = Backend(root, role='independent_review')
    review = reviewer.call(context['section_id'] + '-05_review', prompt, schema, pack.get('images'))
    points = {point['id']: point for point in inventory['points']}
    known_blocks = {block['id'] for _, block in flow.teaching_blocks(doc)}
    bound_blocks = {row['point_id']:set(row['block_ids']) for row in bindings['points']}
    for point in review['points']:
        expected = points.get(point['point_id'], {})
        checks = point.get('checks', [])
        valid = len(checks) == len(expected.get('checks', [])) and {row['index'] for row in checks} == set(range(len(expected.get('checks', []))))
        point['passed'] = point['passed'] and valid and all(row['passed'] and row['block_ids'] and set(row['block_ids']) <= known_blocks & bound_blocks.get(point['point_id'],set()) for row in checks)
    review.update(section_id=context['section_id'], reviewed_inventory=copy.deepcopy(inventory), reviewed_source_pack=copy.deepcopy(pack),
                  reviewed_bindings=copy.deepcopy(bindings), reviewed_document=flow.review_document(doc),
                  block_snapshots={block['id']: copy.deepcopy(block) for _, block in flow.teaching_blocks(doc)})
    coverage = flow.evaluate(doc, inventory, bindings, review, pack)
    save(folder / 'review.json', review)
    save(folder / 'coverage.json', coverage)
    errors = list(dict.fromkeys(structural + flow.check_demo(doc, root)))
    doc['validation'] = {'passed': not errors and coverage['passed'], 'errors': errors}
    save(folder / 'candidate.json', doc)
    state = read(root / 'runtime/state.json')
    save(folder / 'rounds' / ('round-' + str(state['round']) + '.json'), {'document': doc, 'review': review, 'coverage': coverage, 'errors': errors})
    if not doc['validation']['passed']:
        brief = {key: value for key, value in review.items() if not key.startswith('reviewed_') and key != 'block_snapshots'}
        details = {'errors': errors, 'coverage_errors': coverage['errors'], 'review': brief}
        failed = {item['question_id'] for item in review['unit_reviews'] if not item['passed']}
        failed.update(points[row['point_id']]['question_id'] for row in review['points'] if not row['passed'] and row['point_id'] in points)
        if not review['coherence']['passed']:
            failed |= {unit['question_id'] for unit in units}
        for unit in units:
            if any(unit['question_id'] in error for error in errors):
                failed.add(unit['question_id'])
            if not review['writing_style']['passed'] and any(block['id'] in review['writing_style']['reason'] for block in [unit['problem'],*unit['explanation'],unit['synthesis']]):
                failed.add(unit['question_id'])
        for unit in units:
            if unit['question_id'] in failed:
                feedback(root, context['section_id'] + '-05_unit-' + unit['question_id'], dict(details, current=unit))
        if not review['inventory_complete']['passed']:
            feedback(root, context['section_id'] + '-05_inventory', dict(details, previous_inventory=inventory))
        if errors or any(not review[key]['passed'] for key in ['pitfalls', 'quiz', 'terminology', 'writing_style']):
            feedback(root, context['section_id'] + '-05_extras', dict(details, current=extras))
    return doc


def write_sections(root, backend):
    contexts, plan, chapters, questions = flow.runtime.contexts(root)
    work = root / '05_writing/work'
    work.mkdir(parents=True, exist_ok=True)
    update_state(root, stage='05_writing/materials')
    def plan_one(context):
        folder = work / 'sections' / context['section_id']
        folder.mkdir(parents=True, exist_ok=True)
        pack, inventory = flow.prepare_section(root, Backend(root, role='planning'), context, folder)
        return context, folder, pack, inventory
    with futures.ThreadPoolExecutor(max_workers=3) as pool:
        planned = collect(pool, contexts, plan_one)
    by_sid = {row[0]['section_id']: row for row in planned}
    planned = [by_sid[context['section_id']] for context in contexts]
    tasks = [(row, index) for row in planned for index in range(len(row[0]['units']))]
    update_state(root, stage='05_writing/units')
    def write_one(task):
        (context, folder, pack, inventory), index = task
        qid = context['units'][index]['question_id']
        prompt = flow.generation.writer_prompt(context, flow.runtime.source_view(pack), inventory, qid,
                 context['units'][index-1] if index else None, context['units'][index+1] if index+1 < len(context['units']) else context['next_title'])
        value = backend.call(context['section_id'] + '-05_unit-' + qid, prompt, flow.generation.UNIT_SCHEMA, pack.get('images'))
        save(folder / ('unit-' + qid + '.json'), value)
        return value
    with futures.ThreadPoolExecutor(max_workers=3) as pool:
        collect(pool, tasks, write_one)
    all_units = [read(folder / ('unit-' + item['question_id'] + '.json')) for context, folder, _, _ in planned for item in context['units']]
    overview_schema = flow.generation.obj({'introduction': flow.generation.STRING, 'answers': flow.generation.array(flow.generation.obj({'question_id': flow.generation.STRING, 'answer': flow.generation.STRING}))})
    parents = [question for question in questions.values() if question['children']]
    overview = backend.call('05_overview', '依据实际逐问总结回答全部父问题并写简短全书介绍，保持原材料中的条件和事实\n' + json.dumps({'chapters': chapters, 'parents': parents, 'summaries': [{'question_id': unit['question_id'], 'answer': unit['summary']['text']} for unit in all_units]}, ensure_ascii=False), overview_schema)
    save(work / 'overview.json', overview)
    update_state(root, stage='05_writing/review')
    def finish_one(row):
        context, folder, pack, inventory = row
        context = flow.runtime.patch_context(context, chapters, questions, overview)
        units = [read(folder / ('unit-' + item['question_id'] + '.json')) for item in context['units']]
        draft = {'units': units, 'core_questions': context['core_questions'], 'opening_title': context['opening_title'], 'context_goals': context['context_goals']}
        extras = backend.call(context['section_id'] + '-05_extras', flow.generation.extras_prompt(context, draft, inventory, {'entries': []}), flow.generation.EXTRAS_SCHEMA)
        save(folder / 'extras.json', extras)
        save(folder / 'units.json', units)
        return context['section_id'], review_section(root, context, folder, pack, inventory, units, extras)
    with futures.ThreadPoolExecutor(max_workers=3) as pool:
        sections = dict(collect(pool, planned, finish_one))
    save(work / 'sections.json', sections)
    book = flow.make_preview(root, sections, chapters, questions, {row['question_id']: row['answer'] for row in overview['answers']}, overview['introduction'])
    from prepare_source_locations import prepare_locations
    prepare_locations(root, list((work / 'sections').glob('*/source-pack.json')))
    errors = [error for doc in sections.values() for error in doc['validation']['errors']]
    if not book['validation']['passed']:
        errors.extend(book['validation']['errors'])
    overview_review = read(root / 'runtime/checks/book-checks.json', {}).get('overview_review', {})
    if overview_review and not overview_review.get('passed'):
        feedback(root, '05_overview', {'review': overview_review, 'current': overview})
    passed = all(doc['validation']['passed'] for doc in sections.values()) and book['validation']['passed']
    if passed:
        published = dict(book)
        for key in ('preview', 'preview_status', 'status'):
            published.pop(key, None)
        save(root / '05_writing/book.json', published)
    return sections, passed, list(dict.fromkeys(errors))


def usage(root):
    calls = [read(path) for path in (root / 'runtime/calls').glob('*/*/usage.json')]
    total = {'calls': len(calls), 'completed_calls': sum(c['status'] == 'completed' for c in calls), 'input_tokens': 0, 'output_tokens': 0, 'cached_input_tokens': 0, 'cache_measurement_missing_calls': 0, 'elapsed_call_seconds': 0}
    for call in calls:
        total['elapsed_call_seconds'] += call.get('elapsed_seconds', 0)
        for receipt in call.get('usage', []):
            total['input_tokens'] += receipt.get('input_tokens', receipt.get('prompt_tokens', 0))
            total['output_tokens'] += receipt.get('output_tokens', receipt.get('completion_tokens', 0))
            cached = receipt.get('cached_input_tokens', receipt.get('prompt_tokens_details', {}).get('cached_tokens'))
            if cached is None:
                total['cache_measurement_missing_calls'] += 1
            else:
                total['cached_input_tokens'] += cached
    save(root / 'runtime/usage.json', {'totals': total, 'calls': calls, 'billing': 'codex_subscription' if os.environ.get('LESSONWEAVE_BACKEND', 'codex') == 'codex' else 'provider_receipts'})
    return total


def run(root, maximum=3):
    root = Path(root).resolve()
    if root.name == '05-test' or '05-test' in root.parts:
        raise ValueError('05-test 由用户保留，本入口不执行该目录')
    scaffold(root)
    maximum = min(4, max(0, maximum))
    state = read(root / 'runtime/state.json', {'round': 0})
    if state.get('status') == 'completed':
        return state
    if state.get('status') == 'needs_review' and state.get('round',0) >= maximum:
        return state
    started = time.monotonic()
    for number in range(state.get('round', 0), maximum + 1):
        update_state(root, round=number, maximum=maximum, status='running')
        try:
            prepare(root)
            update_state(root, stage='02_questions–04_transitions')
            backend = Backend(root, role='planning')
            flow.tree_stages(root, backend)
            sections, passed, issues = write_sections(root, Backend(root, role='writing'))
            from .package import export_package
            export_package(root)
            if passed:
                return update_state(root, status='completed', issues=[], usage=usage(root), elapsed_seconds=round(time.monotonic()-started, 3))
            update_state(root, issues=issues)
        except Exception as error:
            update_state(root, issues=[str(error)])
            if isinstance(error, (NameError, ImportError, AttributeError, TypeError)):
                return update_state(root, status='failed', usage=usage(root))
            if isinstance(error, RuntimeError):
                return update_state(root, status='interrupted', usage=usage(root))
        current=read(root/'runtime/state.json')
        print(json.dumps({'project': root.name, 'round': number, 'stage':current.get('stage'), 'issues':current.get('issues',[])}, ensure_ascii=False), flush=True)
    return update_state(root, status='needs_review', usage=usage(root), elapsed_seconds=round(time.monotonic()-started, 3))
