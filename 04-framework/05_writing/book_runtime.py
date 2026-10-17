import copy
import json
from pathlib import Path
import re
from jsonschema import Draft202012Validator
import book_generation as generation
import book_sources
from build_demo import check_demo, terminology_inventory, check_terminology, chunks
from positive_writing import check_positive_writing
from teaching_coverage import read, save, build_block_sources
STAGE = Path(__file__).resolve().parent
def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))

def walk(node):
    yield node
    for child in node.get('children', []):
        yield from walk(child)

def contexts(root):
    plan = read(root / '04_transitions/transitions.json')
    chapters = read(root / plan['chapters_path'])
    qdoc = read(root / plan['question_tree'])
    questions = {q['id']: q for q in walk(qdoc['tree'])}
    previous_book = read(root / '05_writing/book.json') if (root / '05_writing/book.json').is_file() else None
    note_ids = {}
    if previous_book:
        for chapter in previous_book['chapters']:
            for section in chapter['sections']:
                for unit in read(root / section['path'])['units']:
                    note_ids[unit['question_id']] = unit['synthesis']['id']
    bridges = {b['title_id']: b for b in walk(plan['tree'])}
    result = []
    for ci, chapter in enumerate(chapters['tree']['children'], 1):
        for si, section in enumerate(chapter['children'], 1):
            bridge = bridges[section['id']]
            leaves = [questions[qid] for qid in section['question_ids'] if not questions[qid]['children']]
            next_section = next((s for c in chapters['tree']['children'] for s in c['children'] if s['id'] == bridge['next_section_id']), None)
            number = f'{ci}.{si}'
            item = {
                'case_name': root.name, 'section_id': section['id'], 'section_number': number,
                'title': section['title'], 'opening_title': bridge['premise'] + bridge['question'],
                'transitions_path': f"04_transitions/history/{plan['transition_run']}/transitions.json",
                'transition_run': plan['transition_run'], 'material_run': plan['material_run'],
                'material_path': plan['material_tree'],
                'core_questions': [{'question_id': qid, 'text': questions[qid]['premise'] + questions[qid]['question']} for qid in section['question_ids']],
                'questions': [copy.deepcopy(q) for q in leaves],
                'units': [{'question_id': q['id'], 'number': f'{number}.{i}', 'title': q['premise'] + q['question'], 'source_nodes': q['source_nodes'], 'note_block_id': note_ids.get(q['id'], f"{section['id']}-u{i}-synthesis")} for i, q in enumerate(leaves, 1)],
                'next_section_id': bridge['next_section_id'], 'next_title': next_section['title'] if next_section else '',
                'context_goals': [], 'book_introduction': '',
                'chapter_id': chapter['id'], 'first_in_chapter': si == 1, 'first_in_book': ci == 1 and si == 1,
                'outline': [{'id': c['id'], 'title': c['title'], 'sections': [{'id': s['id'], 'title': s['title']} for s in c['children']]} for c in chapters['tree']['children']],
                'global_questions': [{'question_id': q['id'], 'text': q['premise'] + q['question'], 'source_nodes': q['source_nodes']} for q in questions.values()],
            }
            result.append(item)
    return result, plan, chapters, questions

def source_view(raw):
    view = copy.deepcopy(raw)
    view.setdefault('questions', [])
    view.setdefault('required_source_ids', [s['id'] for s in raw['sources']])
    return book_sources.model_context(view) if hasattr(book_sources, 'model_context') else view

def validate_plan(raw, result, registry_work=None):
    from book_material_registry import resolve_plan_quotes, canonicalize_plan_labels
    result = resolve_plan_quotes(raw, result)
    if registry_work is not None:
        result = canonicalize_plan_labels(registry_work, raw, result)
    # 新识别的图标签已有实际文字时，脚本可以唯一定位它的 ID，含糊匹配仍交回清点任务
    rows = {s['id']: [*s.get('sentences', [])] for s in raw['sources']}
    for label in result['image_labels']:
        rows.setdefault(label['source_id'], []).append(label)
    normalize = lambda text: re.sub(r'\s+', ' ', text).strip().casefold()
    for point in result['points']:
        for quote in point['source_quotes']:
            matches = [row['id'] for row in rows.get(quote['source_id'], []) if normalize(quote['quote']) in normalize(row['original'])]
            if len(matches) == 1 and quote['sentence_ids'] != matches:
                quote['sentence_ids'] = matches
    pack, inventory = generation.materialize_plan(raw, result)
    errors = [e.message for e in Draft202012Validator(read(STAGE / 'coverage-inventory.schema.json')).iter_errors(inventory)]
    _, refs = build_block_sources(inventory, {'points': [{'point_id': p['id'], 'block_ids': ['draft']} for p in inventory['points']]}, pack)
    errors += refs
    if errors:
        raise ValueError('\n'.join(errors))
    return pack, inventory

def unit_errors(result, qid, inventory):
    errors = []
    if result['question_id'] != qid:
        errors.append('当前问题 ID 被改动')
    expected = {p['id'] for p in inventory['points'] if p['question_id'] == qid}
    rows = result['bindings']
    if {b['point_id'] for b in rows} != expected or len(rows) != len(expected):
        errors.append('本问的每个信息点需要恰好一个实际正文对应记录')
    block_ids = {b['id'] for b in [result['problem'], *result['explanation'], result['synthesis']]}
    if len(block_ids) != len(result['explanation']) + 2:
        errors.append('正文块 ID 重复')
    for row in rows:
        if not row['block_ids'] or set(row['block_ids']) - block_ids:
            errors.append(row['point_id'] + ' 缺少有效实际正文位置')
    fake = {'writing_rules_version': 2, 'opening': {'id': 'empty', 'kind': 'paragraph', 'text': ''},
            'units': [result], 'summary': [], 'pitfalls': [], 'quiz': [], 'glossary': []}
    errors.extend(check_positive_writing(fake))
    for block in [result['problem'], *result['explanation'], result['synthesis'], result['summary']]:
        if block['kind'] == 'paragraph' and '。' in block['text']:
            errors.append(block['id'] + ' 使用了中文句号')
        if block['kind'] == 'image' and Path(block['asset']).suffix.lower() not in ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.bmp']:
            errors.append(block['id'] + ' 需要引用实际原图，其他附件在原材料栏通过原文件链接读取')
    if errors:
        raise ValueError('\n'.join(errors))
    return result

def patch_context(context, chapters, questions, overview_result):
    context = copy.deepcopy(context)
    answers = {r['question_id']: r['answer'] for r in overview_result['answers']}
    ids = []
    if context['first_in_chapter']:
        if context['first_in_book']:
            ids.extend(chapters['tree']['question_ids'])
        chapter = next(c for c in chapters['tree']['children'] if c['id'] == context['chapter_id'])
        ids.extend(chapter['question_ids'])
    context['context_goals'] = [{'question_id': qid, 'text': questions[qid]['premise'] + questions[qid]['question'], 'answer': answers[qid], 'source_nodes': questions[qid]['source_nodes']} for qid in ids]
    context['book_introduction'] = overview_result['introduction'] if context['first_in_book'] else ''
    return context

def build_doc(root, context, work, pack, inventory, units, extras):
    from book_terminology import normalize_known_terms, format_term_metadata
    prepared = copy.deepcopy(extras)
    formatted, changes = format_term_metadata(extras['terms'])
    prepared['terms'] = normalize_known_terms(formatted, read(root / '05_writing/terminology.catalog.json'))
    save(work / 'term-format-changes.json', {'scope': '这里只按确定格式规范名称，原始模型响应保持原样，实际含义继续交给独立审查', 'changes': changes})
    doc, bindings, catalog = generation.assemble_section(context, pack, inventory, units, prepared)
    answers = {unit['question_id']: unit['summary']['text'] for unit in units}
    for answer in doc['summary']:
        if answer['question_id'] in answers:
            answer['answer']['text'] = answers[answer['question_id']]
    doc['grounding'] = {name + '_path': (work / filename).relative_to(root).as_posix() for name, filename in [('source_pack', 'source-pack.json'), ('inventory', 'coverage-inventory.json'), ('bindings', 'coverage-bindings.json'), ('review', 'review.json'), ('coverage', 'coverage.json')]}
    doc['catalog_path'] = (work / 'terminology.catalog.json').relative_to(root).as_posix()
    save(work / 'coverage-bindings.json', bindings)
    save(work / 'terminology.catalog.json', catalog)
    return doc, bindings, catalog

def inspect_without_review(doc, root, catalog):
    schema = read(STAGE / 'demo.schema.json')
    errors = [e.message for e in Draft202012Validator(schema).iter_errors(doc)]
    terms = terminology_inventory(doc, catalog)
    required = {t['term_id'] for t in terms['terms']}
    # 先按真实阅读内容选择词条，额外生成但没有使用的词条留在原始响应中，不进入正文与格式检查
    doc['glossary'] = [t for t in doc['glossary'] if t['id'] in required]
    errors.extend(check_positive_writing(doc))
    for location, text in chunks(doc):
        if '。' in text:
            errors.append(location + ' 使用了中文句号')
    if len(doc['quiz']) != 5 or sum(q['kind'] == 'short_answer' for q in doc['quiz']) != 1:
        errors.append('默认四道单选和一道简答')
    for term in doc['glossary']:
        errors.extend(check_terminology(term))
    errors.extend(terms['local_notations']['errors'])
    if terms['unknown_tokens']:
        errors.append('专业英文或缩写需要登记术语，局部符号需要实际定义和明确范围：' + compact(terms['unknown_tokens']))
    if errors:
        raise ValueError('\n'.join(errors))
    return doc
