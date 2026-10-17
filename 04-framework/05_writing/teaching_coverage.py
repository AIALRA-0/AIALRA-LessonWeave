"""把独立审查过的正文位置对应到材料信息点，重新计算已讲解标记"""
import copy
import json
import re
from pathlib import Path
from jsonschema import Draft202012Validator


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def teaching_blocks(doc):
    """只把实际教学正文计入覆盖，不能拿标题、翻译或术语替代讲解"""
    for unit in doc['units']:
        for block in [unit['problem'], *unit['explanation'], unit['synthesis']]:
            yield unit['question_id'], block


def review_document(doc):
    """正文改动后要求重新审查，路径和发布编号变化不影响已审查的文字"""
    keys = ['section_id', 'section_number', 'title', 'opening_title', 'opening',
            'core_questions', 'units', 'summary', 'pitfalls', 'quiz', 'glossary']
    result = {key: copy.deepcopy(doc[key]) for key in keys}
    if 'opening_forward' in doc:
        result['opening_forward'] = copy.deepcopy(doc['opening_forward'])
    if 'writing_rules_version' in doc:
        result['writing_rules_version'] = doc['writing_rules_version']
    if 'local_notations' in doc:
        result['local_notations'] = copy.deepcopy(doc['local_notations'])
    return result


def build_block_sources(inventory, bindings, source_pack, explained_ids=None):
    """按已审查的信息点找出原句和图区域，正文块只获得实际解释的引用"""
    sources = {source['id']: source for source in source_pack['sources']}
    bound = {row['point_id']: row['block_ids'] for row in bindings['points']}
    index = {}
    errors = []
    normalize = lambda text: re.sub(r'\s+', ' ', text).strip().casefold()
    for point in inventory['points']:
        if explained_ids is not None and point['id'] not in explained_ids:
            continue
        refs = {}
        for quote in point['source_quotes']:
            source = sources.get(quote['source_id'])
            if not source:
                errors.append(point['id'] + '的原文条目不存在')
                continue
            matches = [row for row in source['sentences'] if normalize(quote['quote']) in normalize(row['original'])]
            if quote.get('sentence_ids'):
                requested = set(quote['sentence_ids'])
                matches = [row for row in matches if row['id'] in requested]
                if {row['id'] for row in matches} != requested:
                    errors.append(point['id'] + '指定的原句位置与引文不一致')
                    continue
            elif len(matches) > 1:
                errors.append(point['id'] + '的引文出现在多个位置，需要用 sentence_ids 明确指定：' + quote['quote'])
                continue
            if not matches:
                errors.append(point['id'] + '的引文找不到对应原句：' + quote['quote'])
                continue
            ref = refs.setdefault(source['id'], {'source_id': source['id'], 'sentence_ids': [], 'region_ids': []})
            for row in matches:
                if row['id'] not in ref['sentence_ids']:
                    ref['sentence_ids'].append(row['id'])
                if row.get('region') and row['region'] not in ref['region_ids']:
                    ref['region_ids'].append(row['region'])
        for block_id in bound.get(point['id'], []):
            block_refs = index.setdefault(block_id, {})
            for source_id, ref in refs.items():
                merged = block_refs.setdefault(source_id, {'source_id': source_id, 'sentence_ids': [], 'region_ids': []})
                for field in ['sentence_ids', 'region_ids']:
                    merged[field] = list(dict.fromkeys([*merged[field], *ref[field]]))
    return {key: list(refs.values()) for key, refs in index.items()}, errors


def evaluate(doc, inventory, bindings, review, source_pack):
    errors = []
    for label, artifact in [('材料清单', inventory), ('正文对应表', bindings),
                            ('独立审查', review), ('原文包', source_pack)]:
        if artifact.get('section_id') != doc['section_id']:
            errors.append(label + '对应了其他小节')
    if inventory.get('material_run') != source_pack.get('material_run'):
        errors.append('材料清单与原文包的冻结版本不一致')
    source_ids = {s['id'] for s in inventory['sources']}
    pack_ids = {key for s in source_pack['sources'] for key in [s['id'], *s.get('source_ids', [])]}
    if source_ids != pack_ids:
        errors.append('材料清单与原文包的来源条目不一致')
    for requirement in inventory.get('retention_checks', []):
        originals = '\n'.join(row['original'] for source in source_pack['sources']
                              if requirement['source_id'] in [source['id'], *source.get('source_ids', [])]
                              for row in source.get('sentences', []))
        if any(text not in originals for text in requirement['required_originals']):
            errors.append('原材料文字或原图标签没有完整保留：' + requirement['source_id'])
    units = {u['question_id']: u for u in doc['units']}
    all_blocks = list(teaching_blocks(doc))
    block_index = {b['id']: (qid, b) for qid, b in all_blocks}
    if len(block_index) != len(all_blocks):
        errors.append('正文块 ID 重复')
    points = inventory['points']
    point_ids = {p['id'] for p in points}
    if not points or len(points) != len(point_ids):
        errors.append('材料信息点必须存在且不能重复')
    binding_rows = bindings['points']
    binding_index = {p['point_id']: p for p in binding_rows}
    if len(binding_index) != len(binding_rows) or set(binding_index) != point_ids:
        errors.append('正文对应表不能删除、增加或重复冻结信息点')
    judgments = {p['point_id']: p for p in review.get('points', [])}
    if set(judgments) != point_ids or len(judgments) != len(review.get('points', [])):
        errors.append('独立审查没有逐项核对冻结信息点')
    if review.get('reviewed_inventory') != inventory:
        errors.append('材料清单变化后需要重新审查，不能缩小检查分母')
    if review.get('reviewed_source_pack') != source_pack:
        errors.append('原文包变化后需要重新审查')
    if review.get('reviewed_bindings') != bindings:
        errors.append('正文对应表变化后需要重新审查')
    if review.get('reviewed_document') != review_document(doc):
        errors.append('正文变化后需要重新进行内容与连贯性审查')
    review_names = ['inventory_complete', 'coherence', 'pitfalls', 'quiz', 'terminology']
    if doc.get('writing_rules_version',1)>=2:
        review_names.append('writing_style')
    for name in review_names:
        verdict = review.get(name, {})
        if verdict.get('passed') is not True or not verdict.get('reason', '').strip():
            errors.append('独立审查未通过：' + name)
    unit_reviews = {u['question_id']: u for u in review.get('unit_reviews', [])}
    if set(unit_reviews) != set(units):
        errors.append('独立审查没有核对全部讲解单元')
    for qid, result in unit_reviews.items():
        if result.get('passed') is not True:
            errors.append(qid + '尚未讲清问题或衔接不顺')
    snapshots = review.get('block_snapshots', {})
    checked = {}
    for point in points:
        key = point['id']
        binding = binding_index.get(key, {})
        judgment = judgments.get(key, {})
        block_ids = binding.get('block_ids', [])
        reasons = []
        if point['question_id'] not in units:
            reasons.append('负责的问题不存在')
        if not point['source_ids'] or set(point['source_ids']) - source_ids:
            reasons.append('原材料位置不存在')
        if not block_ids or len(set(block_ids)) != len(block_ids):
            reasons.append('缺少实际讲解位置或位置重复')
        for block_id in block_ids:
            current = block_index.get(block_id)
            if current is None:
                reasons.append('讲解位置已删除：' + block_id)
            elif current[0] != point['question_id']:
                reasons.append('讲解位置属于其他问题：' + block_id)
            elif snapshots.get(block_id) != current[1]:
                reasons.append('讲解位置已经修改，需要重新审查：' + block_id)
        if judgment.get('passed') is not True or not judgment.get('reason', '').strip():
            reasons.append('独立审查尚未确认讲清楚')
        if judgment.get('block_ids') != block_ids:
            reasons.append('审查位置与提交位置不一致')
        if review.get('reviewed_inventory') != inventory or review.get('reviewed_source_pack') != source_pack:
            reasons.append('审查使用的材料与当前清单不一致')
        checked[key] = {
            'id': key, 'description': point['description'], 'question_id': point['question_id'],
            'explained': not reasons, 'block_ids': block_ids, 'reasons': reasons,
        }
    for source in inventory['sources']:
        expected = {p['id'] for p in points if source['id'] in p['source_ids']}
        if not expected or set(source['point_ids']) != expected:
            errors.append(source['id'] + '的信息点不能遗漏或与清单不一致')
    completed = sum(p['explained'] for p in checked.values())
    items = [{
        'source_id': source['id'], 'title': source.get('title', source['id']), 'role': source['role'],
        'scope_note': source['scope_note'],
        'explained': bool(source['point_ids']) and all(checked.get(key, {}).get('explained', False) for key in source['point_ids']),
        'points': [checked[key] for key in source['point_ids'] if key in checked],
    } for source in inventory['sources']]
    result = {
        'profile': 'verified-teaching-coverage-v1', 'section_id': doc['section_id'],
        'material_run': inventory['material_run'], 'total_points': len(points),
        'explained_points': completed, 'percentage': round(100 * completed / len(points), 2) if points else 0,
        'total_items': len(items), 'explained_items': sum(i['explained'] for i in items),
        'scope': '本小节负责讲解的信息点，背景材料保留完整原文并明确本节职责',
        'items': items, 'passed': not errors and completed == len(points), 'errors': errors,
    }
    if doc.get('writing_rules_version', 1) >= 2:
        result['block_sources'], reference_errors = build_block_sources(
            inventory, bindings, source_pack, {key for key, value in checked.items() if value['explained']})
        errors.extend(reference_errors)
        result['passed'] = not errors and completed == len(points)
    return result


def load_artifacts(doc, root):
    root = Path(root).resolve()
    result = {}
    for key in ['source_pack', 'inventory', 'bindings', 'review', 'coverage']:
        path = (root / doc['grounding'][key + '_path']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('讲解依据文件不存在：' + key)
        result[key] = read(path)
    return result


def check_grounding(doc, root):
    try:
        data = load_artifacts(doc, root)
        schema = read(Path(root) / '05_writing/coverage-inventory.schema.json')
        schema_errors = [e.message for e in Draft202012Validator(schema).iter_errors(data['inventory'])]
        if schema_errors:
            return ['材料信息点清单格式错误：' + e for e in schema_errors]
        report = evaluate(doc, data['inventory'], data['bindings'], data['review'], data['source_pack'])
        errors = list(report['errors'])
        if report['percentage'] != 100 or not report['passed']:
            errors.append('还有材料信息点没有通过讲解审查')
        if data['coverage'] != report:
            errors.append('覆盖标记与实际正文重新核对的结果不一致')
        # 抽取原文时保留的完整节点还要与冻结树核对，翻译不能替换原文
        material_path = (Path(root) / data['inventory']['material_path']).resolve()
        if not material_path.is_relative_to(Path(root).resolve()):
            raise ValueError('材料树不在当前案例中')
        material = read(material_path)
        if data['source_pack'].get('profile') == 'teaching-source-pack-v1':
            import importlib.util
            spec = importlib.util.spec_from_file_location('verified_book_sources', Path(root) / '05_writing/book_sources.py')
            adapter = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(adapter)
            errors.extend(adapter.verify_source_pack(root, data['source_pack'], material,
                                                     require_readable_resources=doc.get('writing_rules_version') == 2))
        def walk(node):
            yield node
            for child in node.get('children', []):
                yield from walk(child)
        nodes = {n['id']: n for n in walk(material['tree'])}
        for source in data['source_pack']['sources']:
            if source['id'] not in nodes:
                errors.append('原文节点不在冻结材料树中')
            originals = source.get('original_texts', {}) if data['source_pack'].get('profile') != 'teaching-source-pack-v1' else {}
            for node_id, text in originals.items():
                if nodes.get(node_id, {}).get('content', {}).get('text', '') != text:
                    errors.append(node_id + '的原文已偏离冻结材料')
            if any(not row.get('original', '').strip() or not row.get('translation', '').strip() for row in source.get('sentences', [])):
                errors.append(source['id'] + '存在原句或译句缺漏')
            if source['type'] in ['paragraph', 'caption'] and data['source_pack'].get('profile') != 'teaching-source-pack-v1':
                import re
                joined = ''.join(row['original'] for row in source['sentences'])
                original = source.get('original_texts', {}).get(source['id'], '')
                if re.sub(r'\s+', '', joined) != re.sub(r'\s+', '', original):
                    errors.append(source['id'] + '的逐句原文没有完整覆盖冻结原段落')
            if source.get('asset') and not (Path(root) / source['asset'].lstrip('/')).is_file():
                errors.append('原图文件不存在')
        if doc.get('writing_rules_version', 1) >= 2:
            regions = data['source_pack'].get('image_regions', {})
            packed_sources = {row['id']: row for row in data['source_pack']['sources']}
            for _, block in teaching_blocks(doc):
                if block['kind'] != 'image':
                    continue
                source = nodes.get(block.get('source_id'))
                actual_asset = (packed_sources.get(block.get('source_id'), {}).get('asset')
                                if data['source_pack'].get('profile') == 'teaching-source-pack-v1'
                                else source.get('content', {}).get('asset') if source else None)
                if not source or actual_asset != block['asset']:
                    errors.append(block['id'] + '没有对应同一份原图')
                if block.get('source_region'):
                    region = regions.get(block.get('source_id'), {}).get(block['source_region'])
                    if not region:
                        errors.append(block['id'] + '的原图区域不存在')
                    else:
                        x, y, width, height = region['bbox']
                        image_width, image_height = region['image_size']
                        if min(x, y) < 0 or min(width, height) <= 0 or x + width > image_width or y + height > image_height:
                            errors.append(block['id'] + '的原图区域超出图像范围')
        return errors
    except (KeyError, ValueError, TypeError, OSError) as error:
        return ['讲解覆盖记录需要修复：' + str(error)]
