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
from .agents import Backend,AgentCallFailure
from .progress import begin
from . import legacy as flow
import writing_contract as authoring
from .metrics import span,timed,start,finish,stage
from .findings import record

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
        if values.get('status') in {'running','completed'}:
            state.pop('failure_kind',None)
        state.update(values, updated_at=time.time())
        save(path, state)
        return state


def feedback(root, name, details):
    with WRITE_LOCK:
        state = read(root / 'runtime/state.json', {'round': 0, 'feedback': {}})
        state.setdefault('feedback', {})[name] = details
        save(root / 'runtime/state.json', state)


def stage_call(backend, name, prompt, schema, validate, images=None):
    published = {'04_transitions':'04_transitions/transitions.json'}.get(name)
    if published and (backend.root/published).is_file():
        with span(backend.root,stage(name),'reuse',task=name):
            return read(backend.root/published)
    candidate = None
    try:
        candidate = backend.call(name, prompt, schema, images)
        with span(backend.root,stage(name),'check',task=name):
            result = validate(candidate)
        save(backend.root / 'runtime/checks' / (name + '.json'), {'passed': True})
        return result
    except Exception as error:
        details = {'errors': str(error).splitlines(), 'previous': candidate}
        feedback(backend.root, name, details)
        save(backend.root / 'runtime/checks' / (name + '.json'), dict(details, passed=False))
        record(backend.root, name, details['errors'])
        if candidate is not None:
            # 候选结果继续流转，确定的转换由脚本处理，语义问题统一进入批量修复
            return candidate
        return backend.call(name, prompt, schema, images)


flow.stage_call = stage_call


def prepare(root):
    payload = read(root / '00_source/input.json')
    with span(root,'input_check','check'):
        record(root, '00_input', [e.json_path + ': ' + e.message for e in flow.jsonschema.Draft202012Validator(read(root / '00_source/input.schema.json')).iter_errors(payload)])
    update_state(root, stage='00_source')
    if not (root / '01_tree/tree.json').is_file():
        with span(root,'acquire','phase'):
            source = flow.acquire(root, payload)
        if source['status'] != 'acquired':
            raise ValueError('获取材料时遇到问题：' + source.get('reason', ''))
        update_state(root, stage='01_tree')
        with PARSE:
            with span(root,'parse','phase'):
                tree = flow.build_tree(root, payload, source)
        record(root, '01_tree', tree['validation']['errors'])
    else:
        tree=read(root/'01_tree/tree.json')
        if tree.get('format')=='html' and tree.get('coverage',{}).get('inventory') and not tree.get('validation',{}).get('passed'):
            # 恢复时只重算旧诊断，树的内容、节点编号和模型响应继续复用
            from content_checks import source_inventory
            from tree_model import save_result
            inventory_path=root/tree['coverage']['inventory']
            source=read(inventory_path.parent/'source.json')
            save(inventory_path,source_inventory(root,tree,source))
            tree=save_result(root,tree,inventory_path.parent)
            record(root,'01_tree',tree['validation']['errors'])
        for sid in ['acquire','parse']:
            with span(root,sid,'reuse'):pass


def collect(pool, items, function, root=None):
    results = []
    pending = {pool.submit(function, item): item for item in items}
    while pending:
        completed, _ = futures.wait(pending, return_when=futures.FIRST_COMPLETED)
        for future in completed:
            item = pending.pop(future)
            try:
                results.append(future.result())
            except Exception as issue:
                if root is not None:
                    record(root, function.__name__, str(issue), 'repair')
                time.sleep(1)
                pending[pool.submit(function, item)] = item
    return results


def recover(root, task, function):
    """运行异常在当前任务内恢复，已完成的其他任务和真实检查结论继续保留"""
    while True:
        try:
            return function()
        except Exception as issue:
            record(root, task, str(issue), 'repair')
            update_state(root, status='running', behavior='repair', recovery_task=task)
            time.sleep(2)


def assemble_draft(root, context, folder, pack, inventory, units, extras):
    """正文按真实数据直接预览，检查问题随结果保留，后续集中审查和批量修复"""
    from teaching_coverage import build_block_sources
    doc, bindings, catalog = flow.runtime.build_doc(root, context, folder, pack, inventory, units, extras)
    doc['writing_contract_version'] = authoring.VERSION
    block_sources, issues = build_block_sources(inventory, bindings, pack)
    record(root, context['section_id'], issues)
    doc['validation'] = {'passed': False, 'errors': issues}
    save(folder / 'coverage.json', {'section_id': context['section_id'], 'passed': False,
         'review_status': 'not_reviewed', 'errors': issues, 'block_sources': block_sources,
         'items': [], 'percentage': None})
    save(folder / 'candidate.json', doc)
    return doc


@timed('review','phase')
def review_section(root, context, folder, pack, inventory, units, extras):
    doc, bindings, catalog = flow.runtime.build_doc(root, context, folder, pack, inventory, units, extras)
    if context.get('writing_contract_version'):
        doc['writing_contract_version'] = context['writing_contract_version']
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
    language = authoring.surface_findings(doc)
    save(folder / 'writing-hints.json', {'policy': authoring.POLICY, 'findings': language})
    structural.extend(item['location'] + ': ' + item['code'] for item in language if item['severity'] == 'error')
    schema = copy.deepcopy(flow.REVIEW_SCHEMA)
    check = flow.generation.obj({'index': {'type': 'integer'}, 'passed': {'type': 'boolean'}, 'block_ids': flow.generation.STRINGS, 'reason': flow.generation.STRING})
    schema['properties']['points']['items']['properties']['checks'] = flow.generation.array(check)
    schema['properties']['points']['items']['required'].append('checks')
    prompt = '独立审查当前原材料与实际正文，作者绑定是待核对证据，逐项检查信息点下的每条 checks，index 从 0 开始，每条恰好返回一次，必须在实际正文中讲清才 passed=true，并指出正文块；总点通过由程序按子项重算，同时检查清单是否漏掉原材料、数值、图表、限制、翻译、易错点与练习，作者身份不提供\n'
    prompt += json.dumps({'source_pack': flow.runtime.source_view(pack), 'inventory': inventory,
                          'global_information_points': context.get('frozen_points', []),
                          'document': flow.review_document(doc), 'bindings': bindings, 'rules': flow.generation.RULES}, ensure_ascii=False)
    reviewer = Backend(root, role='independent_review')
    review = reviewer.call(context['section_id'] + '-05_review', prompt, schema, pack.get('images'))
    points = {point['id']: point for point in inventory['points']}
    known_blocks = {block['id'] for _, block in flow.teaching_blocks(doc)}
    owned_blocks = {unit['question_id']: {block['id'] for block in [unit['problem'], *unit['explanation'], unit['synthesis']]} for unit in units}
    for point in review['points']:
        expected = points.get(point['point_id'], {})
        checks = point.get('checks', [])
        valid = len(checks) == len(expected.get('checks', [])) and {row['index'] for row in checks} == set(range(len(expected.get('checks', []))))
        allowed = owned_blocks.get(expected.get('question_id'), set())
        point['passed'] = point['passed'] and valid and all(row['passed'] and row['block_ids'] and set(row['block_ids']) <= known_blocks & allowed for row in checks)
        if point['passed']:
            point['block_ids'] = list(dict.fromkeys(key for row in checks for key in row['block_ids']))
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
                current = read(folder / ('unit-' + unit['question_id'] + '.json'), unit)
                feedback(root, context['section_id'] + '-05_unit-' + unit['question_id'], dict(details, current=current))
        if not review['inventory_complete']['passed']:
            feedback(root, context['section_id'] + '-05_inventory', dict(details, previous_inventory=inventory))
        if errors or any(not review[key]['passed'] for key in ['pitfalls', 'quiz', 'terminology', 'writing_style']):
            feedback(root, context['section_id'] + '-05_extras', dict(details, current=extras))
        if not review['terminology']['passed'] or any(any(word in error for word in ['术语','glossary','缩写','专业英文','局部符号']) for error in errors):
            feedback(root, context['section_id'] + '-06_glossary', dict(details, current=read(folder/'glossary.json',{})))
    return doc




def usage(root):
    calls = [read(path) for path in (root / 'runtime/calls').glob('*/*/usage.json')]
    calls += [read(path) for path in (root/'runtime/cancelled-calls').glob('*/*/usage.json')]
    calls += [read(path) for path in (root/'runtime/recovery-calls').glob('*/*/usage.json')]
    total = {'calls': len(calls), 'completed_calls': sum(c['status'] == 'completed' for c in calls), 'input_tokens': 0, 'output_tokens': 0, 'cached_input_tokens': 0, 'cache_measurement_missing_calls': 0, 'usage_measurement_missing_calls': 0, 'elapsed_call_seconds': 0}
    for call in calls:
        total['elapsed_call_seconds'] += call.get('elapsed_seconds', 0)
        if not call.get('usage'):total['usage_measurement_missing_calls']+=1
        for receipt in call.get('usage', []):
            total['input_tokens'] += receipt.get('input_tokens', receipt.get('prompt_tokens', 0))
            total['output_tokens'] += receipt.get('output_tokens', receipt.get('completion_tokens', 0))
            cached = receipt.get('cached_input_tokens', receipt.get('prompt_cache_hit_tokens', receipt.get('prompt_tokens_details', {}).get('cached_tokens')))
            if cached is None:
                total['cache_measurement_missing_calls'] += 1
            else:
                total['cached_input_tokens'] += cached
    save(root / 'runtime/usage.json', {'totals': total, 'calls': calls, 'billing': 'codex_subscription' if os.environ.get('LESSONWEAVE_BACKEND', 'codex') == 'codex' else 'provider_receipts'})
    return total




def write_sections(root, backend, **options):
    from .lean import write_sections as execute
    return execute(Path(root), backend)


def run(root, maximum=0):
    from .lean import run as execute
    return execute(root, maximum)
