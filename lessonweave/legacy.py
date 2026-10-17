from __future__ import annotations
import copy
import json
from pathlib import Path
import re
import sys
import concurrent.futures as futures
import jsonschema
FRAME = Path(__file__).resolve().parents[1] / '04-framework'
for stage in ['00_source','01_tree','02_questions','03_chapters','04_transitions','05_writing']:
    sys.path.insert(0, str(FRAME / stage))
from acquire import acquire
from build_tree import build_tree
from build_questions import publish_questions
from build_chapters import publish_chapters
from build_transitions import publish_transitions
import book_generation as generation
import book_sources
import book_runtime as runtime
from build_demo import check_demo, terminology_inventory
from build_book import goal, check_book, grounded_book_report, material_audit_from_book, overview_snapshot
from teaching_coverage import evaluate, review_document, teaching_blocks
from review_contract import REVIEW_SCHEMA
from lessonweave.storage import read, save
from lessonweave.agents import Backend
def log(root, message):
    print(root.name + ' ' + message, flush=True)

def walk(node):
    yield node
    for child in node.get('children', []):
        yield from walk(child)


def clean_schema(schema, optional=()):
    schema = copy.deepcopy(schema)
    for key in optional:
        schema.get('properties', {}).pop(key, None)
    return schema

def author_format(value):
    """只转换作者文字的标点，原文、译文、源码与引文继续保留"""
    result = copy.deepcopy(value)
    changes = []
    prose = {'premise', 'question', 'title', 'goal', 'starting_point', 'range_description', 'focus',
             'closing_boundary', 'text', 'description', 'scope_note', 'definition', 'meaning',
             'lead_in', 'reference_answer', 'introduction', 'reason', 'explanation', 'answer'}
    arrays = {'items', 'checks', 'rubric', 'explanation'}
    preserve = {'original', 'translation', 'english', 'quote', 'source_quotes', 'code', 'raw_content'}
    def visit(node, trail=''):
        if isinstance(node, dict):
            if node.get('kind') in {'code', 'formula'}:
                return
            for key, child in node.items():
                path = trail + '/' + key
                if key in preserve:
                    continue
                if isinstance(child, str) and key in prose and '。' in child:
                    node[key] = child.replace('。', '；').rstrip('；')
                    changes.append(path)
                elif isinstance(child, list) and key in arrays:
                    for i, entry in enumerate(child):
                        if isinstance(entry, str) and '。' in entry:
                            child[i] = entry.replace('。', '；').rstrip('；')
                            changes.append(path + '/' + str(i))
                        else:
                            visit(entry, path + '/' + str(i))
                else:
                    visit(child, path)
        elif isinstance(node, list):
            for i, child in enumerate(node):
                visit(child, trail + '/' + str(i))
    visit(result)
    return result, changes

def remove_empty_extras(value, schema):
    allowed = set()
    def names(node):
        if isinstance(node, dict):
            allowed.update(node.get('properties', {}))
            for child in node.values():
                names(child)
        elif isinstance(node, list):
            for child in node:
                names(child)
    names(schema)
    changes = []
    def visit(node, trail=''):
        if isinstance(node, dict):
            for key in list(node):
                if key not in allowed and node[key] in [None, '', [], {}]:
                    changes.append(trail + '/' + key)
                    node.pop(key)
                else:
                    visit(node[key], trail + '/' + key)
        elif isinstance(node, list):
            for i, child in enumerate(node):
                visit(child, trail + '/' + str(i))
    visit(value)
    return changes

def tree_stages(root, backend):
    if (root / '04_transitions/transitions.json').is_file():
        from build_questions import check_questions
        from build_chapters import check_chapters
        from build_transitions import check_transitions
        errors = check_questions(read(root / '02_questions/questions.json'), root)
        errors += check_chapters(read(root / '03_chapters/chapters.json'), root)
        errors += check_transitions(read(root / '04_transitions/transitions.json'), root)
        if errors:
            raise ValueError('\n'.join(errors))
        return
    tree = read(root / '01_tree/tree.json')
    schema = clean_schema(read(root / '02_questions/questions.schema.json'), ['question_run', 'coverage'])
    metadata = {'profile': 'learning-questions-v1', 'scope': 'full_material',
                'material_tree': f'01_tree/history/{tree["run"]}/tree.json', 'material_run': tree['run'],
                'source_roots': [tree['tree']['id']], 'context_nodes': [], 'validation': {'passed': False, 'errors': []}}
    originals = []
    for source_node in walk(tree['tree']):
        if source_node['type'] == 'file' and source_node['content'].get('role') in {'source', 'document'}:
            locator = source_node['source'][0]
            actual = (root / locator['path']).resolve()
            if not actual.is_relative_to(root.resolve()):
                raise ValueError('原件路径越过当前项目目录')
            originals.append({'source_id': source_node['id'], 'path': locator['path'], 'text': actual.read_text(encoding='utf-8'), 'start_line': 1})
    prompt = (root / '02_questions/generation.md').read_text(encoding='utf-8')
    prompt += '\n完整输入\n' + json.dumps({'input': read(root / '00_source/input.json'), 'material': tree, 'actual_source_files': originals, 'fixed_fields': metadata}, ensure_ascii=False)
    prompt += '\n依据材料规模安排有递进关系的问题和小节，材料较小时可以只用二至三个问题，较大时按理解职责分组，根问题统领全书，每个材料节点都要由叶子直接引用，保留元信息来源但正文围绕材料事实展开，ID 使用 q.root、q.1 等稳定格式，learning_order 只列叶子，所有问题使用同一行 premise 加 question 的完整问句，来源、容器和未知节点均保留映射'
    def questions(candidate):
        candidate.update(metadata)
        by_id = {node['id']: node for node in walk(tree['tree'])}
        changes = []
        for question in walk(candidate['tree']):
            if question['children']:
                continue
            original = set(question['source_nodes'])
            for source in by_id.values():
                if source['children'] and any(node['id'] in original for child in source['children'] for node in walk(child)):
                    if source['id'] not in question['source_nodes']:
                        question['source_nodes'].append(source['id'])
                        changes.append({'question_id': question['id'], 'source_id': source['id'], 'reason': '该容器的实际子项已经归入当前问题，脚本沿材料树补全容器对应'})
        save(root / 'runtime/checks/container-mapping-conversion.json', changes)
        return publish_questions(root, candidate)
    qdoc = stage_call(backend, '02_questions', prompt, schema, questions)
    schema = clean_schema(read(root / '03_chapters/chapters.schema.json'), ['chapter_run', 'coverage'])
    metadata = {'profile': 'chapter-outline-v1', 'question_tree': f'02_questions/history/{qdoc["question_run"]}/questions.json',
                'question_run': qdoc['question_run'], 'material_tree': qdoc['material_tree'], 'material_run': qdoc['material_run'],
                'validation': {'passed': False, 'errors': []}}
    prompt = (root / '03_chapters/generation.md').read_text(encoding='utf-8') + '\n' + json.dumps({'questions': qdoc, 'fixed_fields': metadata}, ensure_ascii=False)
    prompt += '\n根据材料规模安排章节，小型材料可以安排一章一节，书根ID固定为book，书标题分配根问题，章节可以用空 question_ids，具体叶子各恰好分给一节，source_nodes 和 requires 暂填空数组，由框架按实际分配计算，标题必须是 premise 加 question 的同一行完整问句'
    def chapters(candidate):
        candidate.update(metadata)
        candidate['tree']['id'] = 'book'
        return publish_chapters(root, candidate)
    cdoc = stage_call(backend, '03_chapters', prompt, schema, chapters)
    schema = clean_schema(read(root / '04_transitions/transitions.schema.json'), ['transition_run', 'coverage'])
    metadata = {key: cdoc[key] for key in ['question_tree', 'question_run', 'material_tree', 'material_run']}
    metadata.update(profile='transition-plan-v1', status='preview', chapters_path=f'03_chapters/history/{cdoc["chapter_run"]}/chapters.json',
                    chapter_run=cdoc['chapter_run'], validation={'passed': False, 'errors': []})
    prompt = (root / '04_transitions/generation.md').read_text(encoding='utf-8')
    prompt += '\n本任务直接执行已确认的 04 阶段，无需等待用户，按下面当前输入生成承接树\n' + json.dumps({'chapters': cdoc, 'questions': qdoc, 'fixed_fields': metadata}, ensure_ascii=False)
    prompt += '\n承接树逐项对应书、章、节标题，title_id 保持相同，text 为承上启下：加 premise 加 question，不添加其他内容，关系字段由框架重新推导，最后一个单元 next_question_id 和 next_section_id 为 null'
    def transitions(candidate):
        candidate.update(metadata)
        return publish_transitions(root, candidate)
    stage_call(backend, '04_transitions', prompt, schema, transitions)

def prepare_section(root, backend, context, folder):
    sid = context['section_id']
    raw = book_sources.prepare_sources(root, sid, folder)
    save(folder / 'raw-sources.json', raw)
    def validate_plan(candidate):
        candidate = copy.deepcopy(candidate)
        sources_by_id = {source['id']: source for source in raw['sources']}
        aliases, retained, duplicate_labels = {}, [], []
        for label in candidate['image_labels']:
            source = sources_by_id.get(label['source_id'], {})
            matching = [row for row in source.get('sentences', []) if ' '.join(row['original'].split()) == ' '.join(label['original'].split())]
            if len(matching) == 1:
                aliases[(label['source_id'], label['id'])] = matching[0]['id']
                duplicate_labels.append({'source_id': label['source_id'], 'label_id': label['id'], 'actual_sentence_id': matching[0]['id'], 'reason': '同一文字已经作为真实原句提取，按实际来源去重，继续保留原文'})
            else:
                retained.append(label)
        candidate['image_labels'] = retained
        for point in candidate['points']:
            for quote in point['source_quotes']:
                quote['sentence_ids'] = list(dict.fromkeys(aliases.get((quote['source_id'], sid), sid) for sid in quote['sentence_ids']))
        save(folder / 'duplicate-label-conversions.json', duplicate_labels)
        existing = {(row['source_id'], row['sentence_id']) for row in candidate['translated_sentences']}
        labels = {'原始文件与附件': 'Original files and attachments', '页眉与页脚': 'Headers and footers'}
        conversions = []
        for source in raw['sources']:
            for row in source['sentences']:
                if (source['id'], row['id']) in existing:
                    continue
                if source.get('evidence_kind') == 'material_index' or row.get('evidence_kind') == 'material_index':
                    translated = row['original']
                elif row['original'] in labels:
                    translated = labels[row['original']]
                else:
                    continue
                candidate['translated_sentences'].append({'source_id': source['id'], 'sentence_id': row['id'], 'translation': translated})
                conversions.append({'source_id': source['id'], 'sentence_id': row['id'], 'reason': '索引保持原始数据，固定系统标签按公共字典显示，材料正文继续由模型翻译'})
        save(folder / 'index-translation-conversions.json', conversions)
        material_nodes = {node['id']: node for node in walk(read(root / '01_tree/tree.json')['tree'])}
        container_refs = []
        for point in candidate['points']:
            original = set(point['source_ids'])
            for source in raw['sources']:
                node = material_nodes.get(source['id'])
                if node and node['children'] and any(child['id'] in original for c in node['children'] for child in walk(c)):
                    if source['id'] not in point['source_ids']:
                        point['source_ids'].append(source['id'])
                        container_refs.append({'point_id': point['id'], 'source_id': source['id'], 'reason': '当前信息点已经解释该容器中的实际子项，脚本补上树中真实存在的父子对应'})
        save(folder / 'container-point-conversions.json', container_refs)
        return runtime.validate_plan(raw, candidate)
    previous_inventory = read(folder / 'coverage-inventory.json') if (folder / 'coverage-inventory.json').is_file() else None
    pack, inventory = stage_call(backend, sid + '-05_inventory', generation.plan_prompt(runtime.source_view(raw), context),
                                 generation.PLAN_SCHEMA, validate_plan, raw.get('images'))
    if previous_inventory:
        old = {point['id']:point for point in previous_inventory['points']}
        new = {point['id']:point for point in inventory['points']}
        if set(old)-set(new) or any(not set(point['checks']) <= set(new[key]['checks']) or point['question_id'] != new[key]['question_id'] for key,point in old.items() if key in new):
            raise ValueError('清点修订需要保留已登记的信息点、检查要求与问题职责')
    import book_languages
    chinese = []
    for source in pack['sources']:
        for row in source.get('sentences', []):
            if source.get('verbatim_code') or row.get('verbatim_code') or source.get('evidence_kind') == 'material_index':
                continue
            if re.search(r'[\u3400-\u9fff]', row['original']):
                chinese.append({'source_id': source['id'], 'sentence_id': row['id'], 'original': row['original']})
            else:
                row['english'] = row['original']
    if chinese:
        translated = backend.call(sid + '-05_english', '逐句忠实翻译为英文，保持数字、代码与原句ID\n' + json.dumps(chinese, ensure_ascii=False), book_languages.ENGLISH_SCHEMA)
        by_key = {(r['source_id'], r['sentence_id']): r['english'] for r in translated['translations']}
        for source in pack['sources']:
            for row in source.get('sentences', []):
                if (source['id'], row['id']) in by_key:
                    row['english'] = book_languages._validate_english(row['original'], by_key[(source['id'], row['id'])])
    save(folder / 'source-pack.json', pack)
    save(folder / 'coverage-inventory.json', inventory)
    return pack, inventory

def make_preview(root, sections, chapters, questions, answers, introduction):
    stage = root / '05_writing'
    book = {'profile': 'learning-book-v1', 'id': 'book', 'title': chapters['tree']['title'], 'introduction': introduction,
            'transitions_path': next(iter(sections.values()))['transitions_path'], 'transition_run': next(iter(sections.values()))['transition_run'],
            'writing_run': 'run-current', 'writing_rules_version': 2, 'goals': goal(chapters['tree'], questions, answers),
            'chapters': [], 'preview': True, 'status': 'current_draft_preview', 'preview_status': '当前完整稿，检查状态按实际记录', 'coverage': {}, 'validation': {'passed': False, 'errors': []}}
    for ci, chapter in enumerate(chapters['tree']['children'], 1):
        item = {'id': chapter['id'], 'number': str(ci), 'title': chapter['title'], 'goals': goal(chapter, questions, answers), 'sections': []}
        for section in chapter['children']:
            doc = sections[section['id']]
            path = stage / 'preview' / (section['id'] + '.json')
            save(path, doc)
            item['sections'].append({'id': section['id'], 'number': doc['section_number'], 'title': doc['title'], 'path': path.relative_to(root).as_posix()})
        book['chapters'].append(item)
    material_ids = {n['id'] for n in walk(read(root / chapters['material_tree'])['tree'])}
    covered_ids = {key for doc in sections.values() for unit in doc['units'] for key in unit['source_nodes']}
    answered = {row['question_id'] for doc in sections.values() for row in doc['summary']} | set(answers)
    book['coverage'] = {'sections': len(sections), 'question_nodes': len(questions), 'answered_questions': len(answered),
                        'teaching_units': sum(len(doc['units']) for doc in sections.values()), 'material_nodes': len(material_ids),
                        'covered_material_nodes': len(covered_ids & material_ids), 'quiz': sum(len(doc['quiz']) for doc in sections.values()),
                        'unique_terms': len({term['id'] for doc in sections.values() for term in doc['glossary']}),
                        'question_percentage': round(100 * len(answered & questions.keys()) / len(questions), 4),
                        'material_mapping_percentage': round(100 * len(covered_ids & material_ids) / len(material_ids), 4)}
    save(stage / 'preview-book.json', book)
    formal = {key: value for key, value in book.items() if key not in {'preview', 'status', 'preview_status'}}
    artifacts = stage / 'preview/book-checks'
    artifacts.mkdir(parents=True, exist_ok=True)
    formal['grounding_report_path'] = (artifacts / 'grounding-report.json').relative_to(root).as_posix()
    save(artifacts / 'grounding-report.json', grounded_book_report(formal, root))
    audit, audit_errors = material_audit_from_book(formal, root)
    save(artifacts / 'material-audit.json', audit)
    snapshot = overview_snapshot(formal, root)
    prompt = '你是独立审查者，根据实际材料和各节已经完成的讲解结论，检查书与章的父问题回答和介绍是否准确概括，是否遗漏核心事实或引入材料未支持的结论，发现问题照实返回 passed=false 并写明依据\n'
    prompt += json.dumps({'questions': [q for q in questions.values() if q['children']],
                          'snapshot': snapshot, 'sections': [{'title': doc['title'], 'units': doc['units']} for doc in sections.values()]}, ensure_ascii=False)
    verdict = Backend(root, 'codex-sol', role='independent_review').call('05_overview_review', prompt, generation.obj({'passed': {'type': 'boolean'}, 'reason': generation.STRING}))
    save(artifacts / 'overview-review.json', dict(verdict, **snapshot))
    try:
        errors = check_book(formal, root)
    except StopIteration:
        errors = ['章节中的书根 ID 为 ' + chapters['tree']['id'] + '，发布清单按 Schema 使用 book，当前框架尚未把两个阶段的 ID 约定统一']
    formal['validation'] = {'passed': not errors, 'errors': errors}
    book.update(grounding_report_path=formal['grounding_report_path'], validation=formal['validation'])
    save(stage / 'preview-book.json', book)
    save(root / 'runtime/checks/book-checks.json', {'passed': not errors, 'errors': errors, 'material_audit': audit, 'overview_review': verdict})
    return book

