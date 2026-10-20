"""按冻结原句分批清点大材料，合并后仍以完整材料包严格核对"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import json
from pathlib import Path
import traceback

from jsonschema import Draft202012Validator


MAX_BATCH_CHARACTERS = 18_000
MAX_BATCH_SENTENCES = 24
MAX_BATCH_SOURCES = 16
MAX_PARALLEL_BATCHES = 3
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.bmp'}


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def needs_batched_planning(raw):
    """原句或来源较多时提前分批，已发生输出截断的小节可直接调用分批清点"""
    rows = [row for source in raw['sources'] for row in source.get('sentences', [])]
    return len(rows) > 48 or sum(len(row['original']) for row in rows) > 36_000 or len(raw['sources']) > 24


def _limits():
    return {'characters': MAX_BATCH_CHARACTERS, 'sentences': MAX_BATCH_SENTENCES,
            'sources': MAX_BATCH_SOURCES, 'parallel_batches': MAX_PARALLEL_BATCHES}


def _fits(rows, source_ids):
    return (len(rows) <= MAX_BATCH_SENTENCES and len(source_ids) <= MAX_BATCH_SOURCES
            and sum(len(row['original']) for _, row in rows) <= MAX_BATCH_CHARACTERS)


def _make_batches(raw):
    sources = {source['id']: source for source in raw['sources']}
    if len(sources) != len(raw['sources']):
        raise ValueError('分批清点要求材料节点 ID 唯一')
    parents = {source_id: source_id for source_id in sources}

    def find(key):
        while parents[key] != key:
            key = parents[key]
        return key

    def union(left, right):
        parents[find(right)] = find(left)

    assets = {}
    expected = []
    for source_id, source in sources.items():
        for related in source.get('source_ids', []):
            if related not in sources:
                raise ValueError('共享来源缺少实际材料记录：' + related)
            union(source_id, related)
        asset = source.get('asset')
        if asset and Path(asset).suffix.lower() in IMAGE_SUFFIXES:
            if asset in assets:
                union(assets[asset], source_id)
            assets[asset] = source_id
        ids = [row['id'] for row in source.get('sentences', [])]
        if len(ids) != len(set(ids)):
            raise ValueError('同一材料内的原句 ID 重复：' + source_id)
        for row in source.get('sentences', []):
            if len(row['original']) > MAX_BATCH_CHARACTERS:
                raise ValueError('单条原句超过批次字符上限，需要保留原句后由外层另行安排：' + source_id + ' ' + row['id'])
            expected.append((source_id, row['id']))
    unknown = set(raw.get('required_source_ids', [])) - set(sources)
    if unknown:
        raise ValueError('要求清点的材料节点没有实际原文记录：' + ', '.join(sorted(unknown)))
    groups = {}
    for source_id in sources:
        groups.setdefault(find(source_id), []).append(source_id)
    units = []
    for group in groups.values():
        rows = [(source_id, row) for source_id in group for row in sources[source_id].get('sentences', [])]
        if _fits(rows, group):
            units.append((set(group), rows))
            continue
        # 超大的图组按原句拆分，每批继续带上实际图像对象，完整关系仍留在冻结原包
        companions = {source_id for source_id in group if sources[source_id].get('asset')
                      and Path(sources[source_id]['asset']).suffix.lower() in IMAGE_SUFFIXES}
        if len(companions) >= MAX_BATCH_SOURCES:
            companions = set(sorted(companions, key=list(sources).index)[:1])
        current_rows, current_ids = [], set(companions)
        for source_id, row in rows:
            wanted_ids = current_ids | {source_id}
            if current_rows and not _fits([*current_rows, (source_id, row)], wanted_ids):
                units.append((current_ids, current_rows))
                current_rows, current_ids = [], set(companions)
            current_rows.append((source_id, row))
            current_ids.add(source_id)
        if current_rows:
            units.append((current_ids, current_rows))
        present = {source_id for ids, _ in units for source_id in ids}
        empty = [source_id for source_id in group if source_id not in present]
        for index in range(0, len(empty), MAX_BATCH_SOURCES):
            units.append((set(empty[index:index + MAX_BATCH_SOURCES]), []))
    packed, active_ids, active_rows = [], set(), []
    for ids, rows in units:
        if active_ids and not _fits([*active_rows, *rows], active_ids | ids):
            packed.append((active_ids, active_rows))
            active_ids, active_rows = set(), []
        active_ids.update(ids)
        active_rows.extend(rows)
    if active_ids:
        packed.append((active_ids, active_rows))
    result = []
    for index, (ids, rows) in enumerate(packed, 1):
        if not _fits(rows, ids):
            raise ValueError('图组的实际来源数超过批次上限，需要外层保留完整图组后安排清点')
        result.append({'id': f'batch-{index:04d}',
                       'call_prefix': raw['section_id'] + f'-plan-batch-{index:04d}',
                       'sources': [{'source_id': source_id,
                                    'sentence_ids': [row['id'] for sid, row in rows if sid == source_id]}
                                   for source_id in sources if source_id in ids],
                       'characters': sum(len(row['original']) for _, row in rows), 'sentence_count': len(rows)})
    actual = [(source['source_id'], sentence_id) for batch in result for source in batch['sources']
              for sentence_id in source['sentence_ids']]
    if Counter(actual) != Counter(expected) or {s['source_id'] for b in result for s in b['sources']} != set(sources):
        raise ValueError('分批结果没有逐项保留全部材料和原句')
    if not result:
        raise ValueError('分批清点需要实际材料')
    return result


def _batch_raw(root, raw, batch):
    selected = {row['source_id']: set(row['sentence_ids']) for row in batch['sources']}
    result = copy.deepcopy(raw)
    result['sources'] = []
    for original in raw['sources']:
        source_id = original['id']
        if source_id not in selected:
            continue
        source = copy.deepcopy(original)
        source['sentences'] = [row for row in source.get('sentences', []) if row['id'] in selected[source_id]]
        if 'source_ids' in source:
            source['source_ids'] = [key for key in source['source_ids'] if key in selected]
        result['sources'].append(source)
    result['required_source_ids'] = list(selected)
    result['visual_assets'] = [copy.deepcopy(row) for row in raw.get('visual_assets', []) if row['source_id'] in selected]
    possible = {str(Path(row['model_path']).resolve()) for row in result['visual_assets']}
    for source in result['sources']:
        if source.get('image_preview', {}).get('path'):
            possible.add(str(Path(source['image_preview']['path']).resolve()))
        if source.get('asset'):
            possible.add(str((Path(root) / source['asset'].lstrip('/')).resolve()))
    result['images'] = [path for path in raw.get('images', []) if str(Path(path).resolve()) in possible]
    if 'image_regions' in result:
        result['image_regions'] = {key: value for key, value in result['image_regions'].items() if key in selected}
    row_order = {row['source_id']: row['sentence_ids'] for row in batch['sources']}
    result['material_manifest'] = [dict(copy.deepcopy(row), sentence_ids=copy.deepcopy(row_order[row['id']]))
                                   for row in raw.get('material_manifest', []) if row['id'] in selected]
    metadata = result.setdefault('metadata', {})
    for key in ('deferred_fragments', 'unresolved_required_fragments'):
        if key in metadata:
            metadata[key] = [row for row in metadata[key] if row['source_id'] in selected]
    metadata['planning_batch'] = {'id': batch['id'], 'full_source_count': len(raw['sources']),
                                  'full_sentence_count': sum(len(s.get('sentences', [])) for s in raw['sources']),
                                  'scope': '本批只清点列出的真实来源和原句，完整材料仍作为最后合并与独立审查的依据'}
    return result


def _normalized_plan(raw, pack, inventory):
    originals = {source['id']: source for source in raw['sources']}
    translated, labels = [], []
    for source in pack['sources']:
        baseline = originals[source['id']]
        ids = {row['id'] for row in baseline.get('sentences', [])}
        for row in source.get('sentences', []):
            if row['id'] not in ids:
                labels.append({'source_id': source['id'], **{key: copy.deepcopy(row[key]) for key in
                              ('id', 'original', 'translation', 'region')}})
            elif not baseline.get('verbatim_code') and not row.get('verbatim_code') and row.get('evidence_kind') != 'material_index':
                translated.append({'source_id': source['id'], 'sentence_id': row['id'], 'translation': row['translation']})
    return {'translated_sentences': translated, 'image_labels': labels,
            'points': copy.deepcopy(inventory['points']),
            'source_assignments': [{'source_id': row['id'], 'role': row['role'], 'scope_note': row['scope_note']}
                                   for row in inventory['sources']]}


def _merge(raw, batches, plans):
    translated, labels, assignments, points = {}, {}, {}, []
    priority = {'container': 0, 'context': 1, 'primary': 2}
    for index, batch in enumerate(batches, 1):
        plan = plans[batch['id']]
        for row in plan['translated_sentences']:
            key = row['source_id'], row['sentence_id']
            if key in translated and translated[key] != row:
                raise ValueError('不同批次给同一原句返回了冲突译文：' + ' '.join(key))
            translated.setdefault(key, copy.deepcopy(row))
        for row in plan['image_labels']:
            key = row['source_id'], row['id']
            if key in labels and any(labels[key][field] != row[field] for field in ('original', 'region')):
                raise ValueError('不同批次把同一原图位置 ID 对应到不同文字或区域：' + ' '.join(key))
            # 同一原文与区域出现多份忠实译文时，沿冻结批次顺序保留第一份供独立审查
            labels.setdefault(key, copy.deepcopy(row))
        for row in plan['source_assignments']:
            key = row['source_id']
            if key not in assignments:
                assignments[key] = {'source_id': key, 'role': row['role'], 'notes': []}
            target = assignments[key]
            if priority[row['role']] > priority[target['role']]:
                target['role'] = row['role']
            if row['scope_note'] not in target['notes']:
                target['notes'].append(row['scope_note'])
        for ordinal, point in enumerate(plan['points'], 1):
            point = copy.deepcopy(point)
            point['id'] = raw['section_id'] + f'.b{index:04d}.p{ordinal:04d}'
            points.append(point)
    return {'translated_sentences': list(translated.values()), 'image_labels': list(labels.values()), 'points': points,
            'source_assignments': [{'source_id': key, 'role': value['role'], 'scope_note': '\n'.join(value['notes'])}
                                   for key, value in assignments.items()]}


def plan_materials(runtime, root, context, raw, work):
    """返回合并计划、完整材料与清单、各批实际计量，成功批次恢复时直接复核缓存"""
    root, work = Path(root).resolve(), Path(work).resolve()
    if context['section_id'] != raw['section_id']:
        raise ValueError('分批清点的固定问题背景与原材料需要对应同一小节')
    batches = _make_batches(raw)
    provided_images = {str(Path(path).resolve()) for batch in batches
                       for path in _batch_raw(root, raw, batch)['images']}
    if provided_images != {str(Path(path).resolve()) for path in raw.get('images', [])}:
        raise ValueError('有原图视觉输入尚未对应到具体批次，完整材料保持原样等待外层修复')
    folder = work / 'planning-batches'
    frozen = {'profile': 'bounded-material-planning-v1', 'context': context, 'raw': raw, 'limits': _limits()}
    manifest = {'profile': frozen['profile'], 'section_id': raw['section_id'], 'material_run': raw['material_run'],
                'material_path': raw['material_path'], 'limits': _limits(), 'batches': batches}
    if (folder / 'inputs.json').is_file():
        if _read(folder / 'inputs.json') != frozen or _read(folder / 'manifest.json') != manifest:
            raise ValueError('分批清点的原材料、问题背景或边界已变化，需要保留旧批次并建立新版本')
    else:
        _save(folder / 'inputs.json', frozen)
        _save(folder / 'manifest.json', manifest)
    state_path = folder / 'state.json'
    state = _read(state_path) if state_path.is_file() else {'pending_batches': [b['id'] for b in batches]}
    state['phase'] = 'planning'
    _save(state_path, state)
    validator = Draft202012Validator(runtime.generation.PLAN_SCHEMA)
    registry_work = runtime.work_root(root)

    def one(batch):
        batch_raw = _batch_raw(root, raw, batch)

        def validate(value):
            validator.validate(value)
            return runtime.validate_plan(batch_raw, copy.deepcopy(value), registry_work)

        cache = folder / batch['id']
        if (cache / 'accepted-plan.json').is_file() and (cache / 'usage.json').is_file():
            plan = _read(cache / 'accepted-plan.json')
            pack, inventory = validate(plan)
            return _normalized_plan(batch_raw, pack, inventory), _read(cache / 'usage.json')
        prompt = runtime.generation.plan_prompt(runtime.source_view(batch_raw), copy.deepcopy(context))
        prompt += '\n本次只清点 manifest 中列出的本批来源与原句，原句 ID 和具体问题 ID 保持原样，其他批次负责其余真实材料，完整小节会在合并后独立审查，不生成省略占位文本，也不把文件索引当作已读源码\n'
        prompt += json.dumps({'batch': batch, 'batch_count': len(batches),
                              'full_source_count': len(raw['sources'])}, ensure_ascii=False)
        response, (pack, inventory), meter = runtime.retry_call(root, batch['call_prefix'], prompt,
                                                               runtime.generation.PLAN_SCHEMA, validate,
                                                               images=batch_raw['images'])
        plan = _normalized_plan(batch_raw, pack, inventory)
        _save(cache / 'response.json', response)
        _save(cache / 'accepted-plan.json', plan)
        _save(cache / 'usage.json', meter)
        return plan, meter

    plans, meters, failures = {}, {}, []
    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_BATCHES, len(batches))) as pool:
        futures = {pool.submit(one, batch): batch['id'] for batch in batches}
        for future in as_completed(futures):
            batch_id = futures[future]
            try:
                plans[batch_id], meters[batch_id] = future.result()
            except BaseException as error:
                failures.append(error)
                if batch_id not in state['pending_batches']:
                    state['pending_batches'].append(batch_id)
                state.setdefault('failures', []).append({'batch_id': batch_id, 'error_type': type(error).__name__,
                    'message': str(error), 'traceback': ''.join(traceback.format_exception(type(error), error, error.__traceback__))})
            else:
                if batch_id in state['pending_batches']:
                    state['pending_batches'].remove(batch_id)
            _save(state_path, state)
    if failures:
        if len(failures) == 1:
            raise failures[0]
        raise BaseExceptionGroup('分批材料清点失败，其他已完成批次已保存', failures)
    try:
        merged = _merge(raw, batches, plans)
        validator.validate(merged)
        pack, inventory = runtime.validate_plan(raw, copy.deepcopy(merged), registry_work)
        merged = _normalized_plan(raw, pack, inventory)
    except BaseException as error:
        state['phase'] = 'merge_failed'
        state.setdefault('merge_failures', []).append({'error_type': type(error).__name__, 'message': str(error),
            'traceback': ''.join(traceback.format_exception(type(error), error, error.__traceback__))})
        _save(state_path, state)
        raise
    actual_meters = {'profile': 'batched-plan-usage-v1',
                     'batches': [{'batch_id': batch['id'], 'call_prefix': batch['call_prefix'], 'record': meters[batch['id']]}
                                 for batch in batches],
                     'usage': [copy.deepcopy(row) for batch in batches for row in meters[batch['id']].get('usage', [])]}
    _save(folder / 'merged-plan.json', merged)
    _save(folder / 'usage.json', actual_meters)
    state['phase'] = 'completed'
    _save(state_path, state)
    return merged, (pack, inventory), actual_meters
