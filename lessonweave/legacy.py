from __future__ import annotations
import copy
import json
from pathlib import Path
import re
import sys
import concurrent.futures as futures
import jsonschema
FRAME = Path(__file__).resolve().parents[1] / 'framework'
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
    """转换作者文字的确定格式，原文、译文、源码与引文继续保留"""
    result = copy.deepcopy(value)
    changes = []
    prose = {'premise', 'question', 'title', 'goal', 'starting_point', 'range_description', 'focus',
             'closing_boundary', 'text', 'description', 'scope_note', 'definition', 'meaning',
             'lead_in', 'reference_answer', 'introduction', 'reason', 'explanation', 'answer'}
    prose.update({'carryover','claim','reasoning','grounding','supplement','generalization',
                  'genus','differentia','boundary','extension','anchor','mapping','intuition',
                  'initial_conditions','mechanism','outcome','reading_guide','takeaway','purpose','sentence',
                  'conclusion','relation_to_whole','collaboration','action','result','title_premise','title_question','caption'})
    arrays = {'items', 'checks', 'rubric', 'explanation'}
    preserve = {'original', 'translation', 'english', 'quote', 'source_quotes', 'code', 'raw_content'}
    def visit(node, trail=''):
        if isinstance(node, dict):
            if node.get('kind') in {'concept','official_name','unit'} and node.get('abbreviation') and isinstance(node.get('english'),str) and node['abbreviation'].strip().casefold()==node['english'].strip().casefold():
                node['abbreviation']=None
                changes.append(trail+'/abbreviation')
            if node.get('kind') in {'code', 'formula'}:
                if isinstance(node.get('guide'),dict):visit(node['guide'],trail+'/guide')
                return
            for key, child in node.items():
                path = trail + '/' + key
                if key == 'text' and node.get('kind') == 'mermaid':
                    continue
                if key in preserve:
                    continue
                if isinstance(child, str) and key in prose:
                    normalized = re.sub(r'\r\n?|[\u2028\u2029]', '\n', child).replace('。', '；').rstrip('；')
                    if key=='title_question' and normalized.strip():normalized=normalized.rstrip('？? ')+'？'
                    if normalized != child:
                        node[key] = normalized
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
    # 旧调用入口只转交公共执行器，不再保留另一套问题规划
    from .planning import run_planning
    return run_planning(root, backend)


def prepare_section(root, backend, context, folder):
    sid = context['section_id']
    raw = book_sources.prepare_sources(root, sid, folder)
    save(folder / 'raw-sources.json', raw)
    def validate_plan(candidate):
        candidate = copy.deepcopy(candidate)
        frozen = context.get('frozen_points', [])
        for expected in frozen:
            owned = [point for point in candidate['points']
                     if expected['id'] in point.get('global_point_ids', []) and point['question_id'] == expected['question_id']]
            checks = {check for point in owned for check in point['checks']}
            if not owned or not set(expected['checks']) <= checks:
                from .findings import record
                record(root, sid + '-inventory', '本节清点需要补齐全局信息点的检查责任：' + expected['id'])
        allowed_global = {point['id'] for point in frozen}
        if {key for point in candidate['points'] for key in point.get('global_point_ids', [])} - allowed_global:
            from .findings import record
            record(root, sid + '-inventory', '本节清点引用了未分配给当前小节的全局信息点')
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
        return runtime.validate_plan(raw, candidate, root=root)
    previous_inventory = read(folder / 'coverage-inventory.json') if (folder / 'coverage-inventory.json').is_file() else None
    pack, inventory = stage_call(backend, sid + '-05_inventory', generation.plan_prompt(runtime.source_view(raw), context),
                                 generation.PLAN_SCHEMA, validate_plan, raw.get('images'))
    if previous_inventory:
        old = {point['id']:point for point in previous_inventory['points']}
        new = {point['id']:point for point in inventory['points']}
        if set(old)-set(new) or any(not set(point['checks']) <= set(new[key]['checks']) or point['question_id'] != new[key]['question_id'] for key,point in old.items() if key in new):
            from .findings import record
            record(root, sid + '-inventory', '清点修订需要保留已登记的信息点、检查要求与问题职责')
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

def mapped_materials(root,sections,material):
    """沿实际讲解引用展开已有合并来源，正文覆盖率使用应讲解材料作分母"""
    qdoc=read(root/'02_questions/questions.json')
    if 'dispositions'not in qdoc:return {}
    from source_disposition import evaluate
    routes=evaluate(qdoc,material)
    expected={row['material_node']for row in routes['nodes']if row['role']in {'teach','preface'}}
    nodes={node['id']:node for node in walk(material['tree'])}
    empty={key for key in expected if nodes[key].get('type')=='file'and nodes[key].get('source',{}).get('bytes')==0}
    expected-=empty
    represented=set()
    for doc in sections.values():
        grounding=doc.get('grounding',{})
        coverage=read(root/grounding['coverage_path'])
        used={ref['source_id']for refs in coverage['block_sources'].values()for ref in refs}
        pack=read(root/grounding['source_pack_path'])
        for source in pack['sources']:
            if source['id']in used:
                represented.add(source['id']);represented.update(source.get('source_ids',[]))
        for link in pack.get('representation_links',[]):
            if link['canonical_source']in used:represented.add(link['material_node'])
    # 没有独立文字的容器沿原有父子关系关联到已经讲解的实际子项
    for node in reversed(list(walk(material['tree']))):
        children=node.get('children',[])
        descendants={child['id']for item in children for child in walk(item)}&expected
        if node['id']in expected and not node.get('text','').strip()and descendants and descendants<=represented:
            represented.add(node['id'])
    covered=expected&represented;missing=sorted(expected-covered)
    report={'material_nodes':routes['summary']['total'],'disposition_percentage':routes['summary']['percentage'],
        'teaching_material_nodes':len(expected),'covered_teaching_material_nodes':len(covered),
        'material_mapping_percentage':round(100*len(covered)/len(expected),4)if expected else 100,
        'missing_teaching_material_nodes':missing,'roles':routes['summary'].get('roles',{}),
        'empty_files_retained_as_context':[{'material_node':key,'path':nodes[key]['source']['path'],'bytes':0,
            'reason':'原文件为空，没有正文可讲解；文件名、路径和所属问题继续保留'}for key in sorted(empty)],
        'basis':'按实际讲解组的来源引用与已有合并来源关联计算，结构、重复表示、定位和已说明原因的排除项保留各自去处',
        'semantic_quality_review':'not_run'}
    save(root/'05_writing/checks/material-render-mapping.json',report)
    return {'covered_material_nodes':len(covered),'teaching_material_nodes':len(expected),
        'material_disposition_percentage':report['disposition_percentage'],
        'material_mapping_percentage':report['material_mapping_percentage']}


def make_preview(root, sections, chapters, questions, answers, introduction, review=False):
    stage = root / '05_writing'
    book = {'profile': 'learning-book-v1', 'id': 'book', 'title': chapters['tree']['title'], 'introduction': introduction,
            'transitions_path': next(iter(sections.values()))['transitions_path'], 'transition_run': next(iter(sections.values()))['transition_run'],
            'writing_run': 'run-current', 'writing_rules_version': 2, 'goals': goal(chapters['tree'], questions, answers),
            'chapters': [], 'preview': True, 'status': 'current_draft_preview', 'preview_status': '当前完整稿，检查状态按实际记录', 'coverage': {}, 'validation': {'passed': False, 'errors': []}}
    for ci, chapter in enumerate(chapters['tree']['children'], 1):
        declared=re.match(r'^(\d+)\. ',chapter['title'])
        item = {'id': chapter['id'], 'number': declared.group(1)if declared else str(ci), 'title': chapter['title'], 'goals': goal(chapter, questions, answers), 'sections': []}
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
    modern=mapped_materials(root,sections,read(root/chapters['material_tree']))
    if modern:
        book['coverage'].update(modern)
        book['grounding_report_path']='05_writing/checks/material-render-mapping.json'
    save(stage / 'preview-book.json', book)
    if not review:
        book['validation'] = {'passed': all(doc.get('validation', {}).get('passed') for doc in sections.values()),
                              'errors': [error for doc in sections.values() for error in doc.get('validation', {}).get('errors', [])]}
        save(stage / 'preview-book.json', book)
        return book
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

