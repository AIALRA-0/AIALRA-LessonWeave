"""将外层 agent 已写好的逐问内容组织成完整教材，保留冻结版本与逐项映射"""
import argparse
import copy
import importlib.util
import json
import re
from book_sources import generated_pdf_container_sentence
from pathlib import Path

from jsonschema import Draft202012Validator

STAGE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('book_writing',STAGE/'build_demo.py')
writing=importlib.util.module_from_spec(spec);spec.loader.exec_module(writing)

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,obj):Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def paragraph(key,text):return {'id':key,'kind':'paragraph','text':text}

def goal(node,questions,answers):
    return [{'question_id':key,'text':questions[key]['premise']+questions[key]['question'],
             'answer':answers[key],'source_nodes':questions[key]['source_nodes']} for key in node['question_ids']]

def make_section(section,bridge,plan,chapters,questions,drafts,answers):
    key=section['id'];number=writing.section_number(chapters['tree'],key)
    ids=section['question_ids'];leaves=[q for q in ids if not questions[q]['children']]
    units=[]
    for index,qid in enumerate(leaves,1):
        scene,teaching,answer,handoff,wrong1,wrong2=drafts[qid]
        stem=f'{key}-u{index}'
        units.append({'question_id':qid,'number':f'{number}.{index}',
            'title':questions[qid]['premise']+questions[qid]['question'],
            'source_nodes':questions[qid]['source_nodes'],
            'problem':paragraph(stem+'-problem',scene+'，'+questions[qid]['question']),
            'explanation':[paragraph(stem+f'-explain-{i}',p) for i,p in enumerate(teaching.split('\n\n'),1)],
            'synthesis':paragraph(stem+'-synthesis',answer+('；'+handoff if handoff else ''))})
    summary=[{'question_id':q,'answer':paragraph(key+'-summary-'+str(i),answers[q])} for i,q in enumerate(ids,1)]
    # 首尾两问各检查一次选择，其余练习要求读者自己解释机制、纠正误解并串起全节
    quiz=[]
    for index,qid in enumerate([leaves[0],leaves[-1]],1):
        record=drafts[qid];options=[record[2],record[4],record[5]];shift=(index+int(number.split('.')[0]))%3
        options=options[shift:]+options[:shift]
        prompt=questions[qid]['premise']+questions[qid]['question']
        if index==2 and len(leaves)==1:prompt='面对“'+record[4]+'”这一判断，以下哪项能够正确说明原因？'
        quiz.append({'id':key+f'-quiz-{index}','kind':'single_choice','question_ids':[qid],
            'prompt':paragraph(key+f'-quiz-{index}-prompt',prompt),'options':options,'answer':options.index(record[2]),
            'explanation':paragraph(key+f'-quiz-{index}-explanation',record[1].split('\n\n')[0])})
    targets=[leaves[len(leaves)//2],leaves[0],None]
    for index,qid in enumerate(targets,3):
        if qid is None:
            prompt=section['title'];reference='；'.join(answers[q] for q in leaves);qids=leaves
            rubric=[answers[q] for q in leaves]
        else:
            record=drafts[qid];qids=[qid]
            prompt=(questions[qid]['premise']+questions[qid]['question']) if index==3 else '如果把“'+record[4]+'”当成结论，错在什么条件或推理，应该怎样纠正？'
            reference=record[2];rubric=[record[1].split('\n\n')[0],record[2]]
        quiz.append({'id':key+f'-quiz-{index}','kind':'short_answer','question_ids':qids,
            'prompt':paragraph(key+f'-quiz-{index}-prompt',prompt),'reference_answer':reference,'rubric':rubric,
            'explanation':paragraph(key+f'-quiz-{index}-explanation','回答时把具体条件、作用过程与结论接起来，避免只重复术语，'+reference)})
    pitfalls=[]
    for index,qid in enumerate(dict.fromkeys([leaves[0],leaves[-1]]),1):
        record=drafts[qid]
        pitfalls.append({'id':key+f'-pitfall-{index}','premise':'如果认为“'+record[4]+'”，',
            'question':'会忽略哪些条件并怎样影响判断？',
            'body':paragraph(key+f'-pitfall-{index}-body',record[2]+'；'+record[1].split('\n\n')[-1])})
    next_id=bridge['next_section_id']
    next_title=next((n['title'] for n in writing.walk(chapters['tree']) if n['id']==next_id),'')
    opening_text=bridge['premise']+bridge['question']
    return {'profile':'writing-demo-v1','scope':'book_section','status':'first_edition',
        'transitions_path':f"04_transitions/history/{plan['transition_run']}/transitions.json",'transition_run':plan['transition_run'],
        'section_id':key,'section_number':number,'title':section['title'],'opening_title':opening_text,
        'opening':paragraph(key+'-opening',bridge['premise']+'具体来看，'+drafts[leaves[0]][0]+'，'+bridge['question']),
        'core_questions':[{'question_id':q,'text':questions[q]['premise']+questions[q]['question']} for q in ids],
        'units':units,'summary':summary,'pitfalls':pitfalls,'quiz':quiz,'next_section_id':next_id,'next_title':next_title,
        'catalog_path':'05_writing/terminology.catalog.json','glossary':[],'validation':{'passed':False,'errors':[]}}

def check_book(book,root):
    root=Path(root);errors=[]
    schema=read(root/'05_writing/book.schema.json')
    errors.extend(e.message for e in Draft202012Validator(schema).iter_errors(book))
    if errors:return errors
    plan=read(root/book['transitions_path'])
    context={'transitions_path':book['transitions_path'],'transition_run':book['transition_run'],
             'section_id':plan['section_order'][0]}
    _,chapters,qdoc,_,_=writing.load_context(context,root)
    qnodes={n['id']:n for n in writing.walk(qdoc['tree'])}
    material=read(root/plan['material_tree']);material_ids={n['id'] for n in writing.walk(material['tree'])}
    expected_sections=[n for n in writing.walk(chapters['tree']) if n['kind']=='section']
    actual_sections=[s for c in book['chapters'] for s in c['sections']]
    if [s['id'] for s in actual_sections]!=[s['id'] for s in expected_sections]:errors.append('全书小节必须与冻结章节逐项同序对应')
    if [c['id'] for c in book['chapters']]!=[c['id'] for c in chapters['tree']['children']]:errors.append('全书章必须与冻结目录一致')
    ownership=[];taught=[];sources=set();terms=set();quiz_count=0
    for entry in [book]+book['chapters']:
        owner=next(n for n in writing.walk(chapters['tree']) if n['id']==entry['id'])
        if entry['title']!=owner['title']:errors.append('书或章标题被改动')
        if [g['question_id'] for g in entry['goals']]!=owner['question_ids']:errors.append('书或章目标的问题归属不一致')
        for g in entry['goals']:
            ownership.append(g['question_id'])
            original=qnodes.get(g['question_id'])
            if not original or g['text']!=original['premise']+original['question'] or g['source_nodes']!=original['source_nodes']:errors.append('整体问题的文字或材料映射被改动')
            if not g['answer'].strip() or '。' in g['answer']:errors.append('书或章问题需要有符合约定的实际回答')
    for entry in actual_sections:
        path=(root/entry['path']).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():errors.append('正文小节文件不存在');continue
        doc=read(path)
        if doc['section_id']!=entry['id'] or doc['title']!=entry['title']:errors.append('正文与目录入口不一致')
        if book.get('writing_rules_version') == 2:
            chapter = next(c for c in book['chapters'] if entry in c['sections'])
            expected_goals = []
            if entry == chapter['sections'][0]:
                if chapter == book['chapters'][0]:
                    expected_goals.extend(book['goals'])
                    if doc.get('book_introduction') != book['introduction']:
                        errors.append('全书介绍与第一节保存的介绍不一致')
                expected_goals.extend(chapter['goals'])
            if doc.get('context_goals', []) != expected_goals:
                errors.append('整体问题回答与各节保留的父问题回答不一致')
        errors.extend(entry['id']+' '+e for e in writing.check_demo(doc,root))
        ownership.extend(q['question_id'] for q in doc['core_questions'])
        for u in doc['units']:
            taught.append(u['question_id']);sources.update(u['source_nodes'])
            if u['source_nodes']!=qnodes[u['question_id']]['source_nodes']:errors.append('讲解单元的材料映射被改动')
        terms.update(t['id'] for t in doc['glossary']);quiz_count+=len(doc['quiz'])
    leaf_ids={k for k,n in qnodes.items() if not n['children']}
    if set(ownership)!=set(qnodes) or len(ownership)!=len(set(ownership)):errors.append('问题树每个节点必须恰好归属并回答一次')
    if set(taught)!=leaf_ids or len(taught)!=len(set(taught)):errors.append('具体问题必须恰好有一个完整讲解单元')
    if sources!=material_ids:errors.append('正文讲解的材料映射没有覆盖完整冻结材料树')
    expected={'sections':len(expected_sections),'question_nodes':len(qnodes),'answered_questions':len(ownership),
        'teaching_units':len(taught),'material_nodes':len(material_ids),'covered_material_nodes':len(sources),
        'quiz':quiz_count,'unique_terms':len(terms),'question_percentage':100.0,'material_mapping_percentage':100.0}
    if book['coverage']!=expected:errors.append('全书覆盖数字与逐项检查不一致')
    if book.get('writing_rules_version') == 2:
        try:
            report = grounded_book_report(book, root)
            report_path = project_file(root, book['grounding_report_path'])
            if read(report_path) != report:
                errors.append('全书信息点覆盖记录与逐节重新检查的结果不一致')
            if not report['passed']:
                errors.extend(report['errors'])
            audit, audit_errors = material_audit_from_book(book, root)
            if read(report_path.with_name('material-audit.json')) != audit:
                errors.append('全书材料核对记录与实际原句及讲解职责不一致')
            errors.extend(audit_errors)
            if not audit['passed']:
                errors.append('全书还有材料节点或原句没有通过实际讲解检查')
            errors.extend(check_overview_review(book, root, report_path.with_name('overview-review.json')))
        except (KeyError, ValueError, OSError) as error:
            errors.append('全书讲解覆盖记录需要修复：' + str(error))
    return errors


def project_file(root, value):
    """只读取当前案例里的实际文件，发布时保留它们各自的冻结副本"""
    root = Path(root).resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('案例文件不存在：' + str(value))
    return path


def grounded_book_report(book, root):
    """从每节已审查的正文重算信息点，材料映射比例单独保留"""
    root = Path(root)
    sections = []
    duties = []
    source_ids = set()
    errors = []
    for entry in [s for chapter in book['chapters'] for s in chapter['sections']]:
        doc = read(project_file(root, entry['path']))
        if doc.get('writing_rules_version') != 2 or 'grounding' not in doc:
            errors.append(entry['id'] + '缺少按当前规则审查的讲解依据')
            continue
        artifacts = writing._coverage_module.load_artifacts(doc, root)
        report = writing._coverage_module.evaluate(
            doc, artifacts['inventory'], artifacts['bindings'], artifacts['review'], artifacts['source_pack'])
        if artifacts['coverage'] != report:
            errors.append(entry['id'] + '的覆盖标记与实际正文不一致')
        if not report['passed'] or report['percentage'] != 100:
            errors.append(entry['id'] + '还有信息点需要讲清楚')
            errors.extend(entry['id'] + ' ' + error for error in report['errors'])
        points = {point['id']: point for point in artifacts['inventory']['points']}
        checked = {point['id']: point for item in report['items'] for point in item['points']}
        for point_id, point in points.items():
            actual = checked.get(point_id, {})
            duties.append({'section_id': entry['id'], 'point_id': point_id,
                'question_id': point['question_id'], 'source_ids': point['source_ids'],
                'block_ids': actual.get('block_ids', []), 'explained': actual.get('explained', False)})
            source_ids.update(point['source_ids'])
        sections.append({'section_id': entry['id'], 'coverage_path': doc['grounding']['coverage_path'],
            'total_points': report['total_points'], 'explained_points': report['explained_points'],
            'total_items': report['total_items'], 'explained_items': report['explained_items'],
            'passed': report['passed']})
    completed = sum(point['explained'] for point in duties)
    return {'profile': 'verified-book-teaching-coverage-v1', 'writing_rules_version': 2,
        'total_sections': len(sections), 'total_points': len(duties), 'explained_points': completed,
        'percentage': round(100 * completed / len(duties), 2) if duties else 0,
        'source_ids': sorted(source_ids), 'sections': sections, 'duties': duties,
        'scope': '按每节负责的信息点和已审查的实际正文计算，同一材料可承担多个不同问题的讲解职责',
        'passed': not errors and bool(duties) and completed == len(duties), 'errors': errors}


def material_audit_from_book(book, root):
    """逐节合并真实原句和已讲解位置，复核每个材料节点与原句的职责"""
    root = Path(root)
    plan = read(project_file(root, book['transitions_path']))
    material = read(project_file(root, plan['material_tree']))
    required = {node['id'] for node in writing.walk(material['tree'])}
    covered = set()
    sentences = {}
    metadata_sentences = []
    assigned = set()
    sections = []
    errors = []
    for entry in [s for chapter in book['chapters'] for s in chapter['sections']]:
        doc = read(project_file(root, entry['path']))
        artifacts = writing._coverage_module.load_artifacts(doc, root)
        inventory, pack = artifacts['inventory'], artifacts['source_pack']
        for label, data in [('材料清单', inventory), ('原文包', pack)]:
            if data.get('material_path') != plan['material_tree'] or data.get('material_run') != plan['material_run']:
                errors.append(entry['id'] + '的' + label + '没有引用同一份冻结材料')
        report = writing._coverage_module.evaluate(
            doc, inventory, artifacts['bindings'], artifacts['review'], pack)
        actual_sources = {source['id'] for source in inventory['sources']}
        covered.update(actual_sources)
        for source in pack['sources']:
            generated=generated_pdf_container_sentence(root,source)
            if generated:
                metadata_sentences.append(generated)
                continue
            for sentence in source.get('sentences', []):
                if sentence.get('evidence_kind') == 'material_index':
                    continue
                key = (source['id'], sentence['id'])
                if key in sentences and sentences[key] != sentence['original']:
                    errors.append(source['id'] + '的同一原句在不同小节中发生变化：' + sentence['id'])
                sentences[key] = sentence['original']
        # evaluate 只为实际审查通过的信息点生成精确来源，重复展示原图不会增加分母
        for refs in report.get('block_sources', {}).values():
            for reference in refs:
                assigned.update((reference['source_id'], sentence_id) for sentence_id in reference['sentence_ids'])
        sections.append({'section_id': entry['id'], 'source_ids': sorted(actual_sources),
            'point_ids': [point['id'] for point in inventory['points']],
            'review_passed': report['passed'] and artifacts['coverage'] == report})
    missing_sources = sorted(required - covered)
    missing_sentences = [{'source_id': source_id, 'sentence_id': sentence_id}
                         for source_id, sentence_id in sorted(set(sentences) - assigned)]
    if covered - required:
        errors.append('全书清单包含冻结材料树之外的来源：' + ', '.join(sorted(covered - required)))
    audit = {'material_path': plan['material_tree'], 'material_run': plan['material_run'],
        'total_nodes': len(required), 'covered_nodes': len(covered & required),
        'missing_source_ids': missing_sources, 'total_sentences': len(sentences),
        'assigned_sentences': len(set(sentences) & assigned), 'missing_sentences': missing_sentences,
        'generated_metadata_sentences': metadata_sentences,
        'sections': sections, 'passed': not errors and not missing_sources and not missing_sentences
            and all(section['review_passed'] for section in sections)}
    return audit, errors


def overview_snapshot(book, root):
    """把书与章的回答和最终各节结论读回来，核对独立审查使用的实际内容"""
    answers = {row['question_id']: row['answer']
               for owner in [book, *book['chapters']] for row in owner['goals']}
    summaries = []
    for entry in [s for chapter in book['chapters'] for s in chapter['sections']]:
        doc = read(project_file(root, entry['path']))
        rows = {row['question_id']: row['answer'] for row in doc['summary']}
        summaries.append({'section': doc['title'], 'questions': [
            {'question_id': unit['question_id'], 'answer': rows[unit['question_id']]['text']
             if rows[unit['question_id']]['kind'] == 'paragraph' else writing.block_text(rows[unit['question_id']]).strip()}
            for unit in doc['units']]})
    return {'reviewed_answers': answers, 'reviewed_introduction': book['introduction'],
            'reviewed_summaries': summaries}


def check_overview_review(book, root, review_path):
    review = read(review_path)
    errors = []
    if review.get('passed') is not True or not review.get('reason', '').strip():
        errors.append('书与章的整体回答还没有通过独立审查')
    snapshot = overview_snapshot(book, root)
    for key, value in snapshot.items():
        if review.get(key) != value:
            errors.append('整体回答审查使用的内容已发生变化：' + key)
    return errors


def publish_grounded_book(root, sections, overview_answers, introduction, work):
    """全部小节通过实际讲解检查后再更新当前书，任何失败都保留上一次已发布结果"""
    root = Path(root).resolve()
    stage = root / '05_writing'
    work = Path(work).resolve()
    if not work.is_relative_to(root) or not work.is_dir():
        raise ValueError('全书工作目录需要位于当前案例中')
    if not sections:
        raise ValueError('全书还没有完成的小节')
    docs = copy.deepcopy(sections)
    first = next(iter(docs.values()))
    plan, chapters, qdoc, _, _ = writing.load_context(first, root)
    expected_sections = [node for node in writing.walk(chapters['tree']) if node['kind'] == 'section']
    if set(docs) != {node['id'] for node in expected_sections}:
        raise ValueError('完成的小节与冻结章节需要逐项对应')
    questions = {node['id']: node for node in writing.walk(qdoc['tree'])}
    parent_ids = set(chapters['tree']['question_ids']) | {
        key for chapter in chapters['tree']['children'] for key in chapter['question_ids']}
    if set(overview_answers) != parent_ids:
        raise ValueError('书与章的父问题需要逐项提供实际回答')
    answers = dict(overview_answers)
    for section in expected_sections:
        doc = docs[section['id']]
        if doc.get('scope') != 'book_section' or doc.get('writing_rules_version') != 2 or 'grounding' not in doc:
            raise ValueError(section['id'] + '需要按当前整节规则完成正文和独立审查')
        if doc['transitions_path'] != first['transitions_path'] or doc['transition_run'] != first['transition_run']:
            raise ValueError('各节需要使用同一份冻结的承接计划')
        for row in doc['summary']:
            key = row['question_id']
            answers[key] = writing.block_text(row['answer']).strip()
        errors = writing.check_demo(doc, root)
        if errors:
            raise ValueError(section['id'] + '\n' + '\n'.join(errors))
    if set(answers) != set(questions):
        raise ValueError('全书仍有问题缺少实际回答')
    for chapter_index, chapter in enumerate(chapters['tree']['children']):
        for section_index, section in enumerate(chapter['children']):
            expected_goals = []
            if section_index == 0:
                if chapter_index == 0:
                    expected_goals.extend(goal(chapters['tree'], questions, answers))
                expected_goals.extend(goal(chapter, questions, answers))
            doc = docs[section['id']]
            if doc.get('context_goals', []) != expected_goals:
                raise ValueError(section['id'] + '的父问题回答需要与全书已审查回答一致')
            if chapter_index == section_index == 0 and doc.get('book_introduction') != introduction:
                raise ValueError('全书介绍需要与第一节已检查的内容一致')
    revisions = [int(path.name[9:]) for path in (stage / 'books').glob('revision-*') if path.name[9:].isdigit()]
    revision = f'revision-{max(revisions, default=0) + 1:04d}'
    dest = stage / 'books' / revision
    dest.mkdir(parents=True)
    (dest / 'sections').mkdir()
    book = {'profile': 'learning-book-v1', 'id': 'book', 'title': chapters['tree']['title'],
        'introduction': introduction, 'transitions_path': first['transitions_path'],
        'transition_run': first['transition_run'], 'writing_run': revision, 'writing_rules_version': 2,
        'goals': goal(chapters['tree'], questions, answers), 'chapters': [], 'coverage': {},
        'grounding_report_path': (dest / 'grounding-report.json').relative_to(root).as_posix(),
        'validation': {'passed': False, 'errors': []}}
    terms = set()
    material_ids = set()
    quiz_total = 0
    for chapter_index, chapter in enumerate(chapters['tree']['children'], 1):
        chapter_entry = {'id': chapter['id'], 'number': str(chapter_index), 'title': chapter['title'],
            'goals': goal(chapter, questions, answers), 'sections': []}
        for section in chapter['children']:
            doc = docs[section['id']]
            frozen = dest / 'sections' / section['id']
            frozen.mkdir()
            for key, path in list(doc['grounding'].items()):
                target = frozen / (key.removesuffix('_path').replace('_', '-') + '.json')
                target.write_bytes(project_file(root, path).read_bytes())
                doc['grounding'][key] = target.relative_to(root).as_posix()
            catalog = read(project_file(root, doc['catalog_path']))
            save(frozen / 'terminology.catalog.json', catalog)
            doc['catalog_path'] = (frozen / 'terminology.catalog.json').relative_to(root).as_posix()
            inventory = writing.terminology_inventory(doc, catalog)
            required = {row['term_id'] for row in inventory['terms']}
            selected = [entry for entry in catalog['entries'] if entry['id'] in required]
            if selected != doc['glossary']:
                raise ValueError(section['id'] + '的正文术语与已审查的术语清单内容不一致')
            term_report = frozen / 'term-inventory.json'
            save(term_report, inventory)
            doc['writing_run'] = revision
            doc['coverage'] = {'questions': len(doc['core_questions']), 'units': len(doc['units']),
                'answered': len(doc['summary']), 'quiz': len(doc['quiz']), 'terms': len(required),
                'covered_terms': len(doc['glossary']), 'term_percentage': 100.0,
                'report': term_report.relative_to(root).as_posix()}
            errors = writing.check_demo(doc, root)
            if errors:
                save(dest / 'failure.json', {'section': section['id'], 'errors': errors})
                raise ValueError(section['id'] + '\n' + '\n'.join(errors))
            doc['validation'] = {'passed': True, 'errors': []}
            path = dest / 'sections' / (section['id'] + '.json')
            save(path, doc)
            chapter_entry['sections'].append({'id': section['id'], 'number': doc['section_number'],
                'title': doc['title'], 'path': path.relative_to(root).as_posix()})
            terms.update(required)
            quiz_total += len(doc['quiz'])
            for unit in doc['units']:
                material_ids.update(unit['source_nodes'])
        book['chapters'].append(chapter_entry)
    material = read(project_file(root, plan['material_tree']))
    book['coverage'] = {'sections': len(expected_sections), 'question_nodes': len(questions),
        'answered_questions': len(answers), 'teaching_units': sum(not node['children'] for node in questions.values()),
        'material_nodes': len(list(writing.walk(material['tree']))), 'covered_material_nodes': len(material_ids),
        'quiz': quiz_total, 'unique_terms': len(terms), 'question_percentage': 100.0,
        'material_mapping_percentage': 100.0}
    report = grounded_book_report(book, root)
    save(root / book['grounding_report_path'], report)
    material_audit, audit_errors = material_audit_from_book(book, root)
    save(dest / 'material-audit.json', material_audit)
    if audit_errors or not material_audit['passed']:
        save(dest / 'failure.json', {'errors': audit_errors, 'material_audit': material_audit})
        raise ValueError('全书还有材料节点或原句需要实际讲解\n' + '\n'.join(audit_errors))
    if (work / 'material-audit.json').is_file():
        (dest / 'material-audit-preparation.json').write_bytes((work / 'material-audit.json').read_bytes())
    if not (work / 'overview-review.json').is_file():
        raise ValueError('全书还缺少独立检查记录：overview-review.json')
    (dest / 'overview-review.json').write_bytes((work / 'overview-review.json').read_bytes())
    for name in ['usage.json']:
        if (work / name).is_file():
            (dest / name).write_bytes((work / name).read_bytes())
    errors = check_book(book, root)
    if errors:
        save(dest / 'failure.json', {'errors': errors})
        raise ValueError('\n'.join(errors))
    book['validation'] = {'passed': True, 'errors': []}
    save(dest / 'book.json', book)
    temporary = stage / 'book.tmp'
    save(temporary, book)
    temporary.replace(stage / 'book.json')
    return book

def publish_book(root,drafts,overview_answers,introduction,section_overrides=None):
    root=Path(root);stage=root/'05_writing';plan=read(root/'04_transitions/transitions.json')
    seed={'transitions_path':f"04_transitions/history/{plan['transition_run']}/transitions.json",'transition_run':plan['transition_run'],'section_id':plan['section_order'][0]}
    _,chapters,qdoc,_,_=writing.load_context(seed,root);qnodes={n['id']:n for n in writing.walk(qdoc['tree'])}
    concrete={key for key,n in qnodes.items() if not n['children']}
    if set(drafts)!=concrete:raise ValueError('逐问内容与具体问题不一致 '+str(sorted(concrete-set(drafts)))+' '+str(sorted(set(drafts)-concrete)))
    answers={key:value[2] for key,value in drafts.items()};answers.update(overview_answers)
    if set(answers)!=set(qnodes):raise ValueError('还缺少父问题的实际回答 '+str(sorted(set(qnodes)-set(answers))))
    revisions=[int(p.name[9:]) for p in (stage/'books').glob('revision-*') if p.name[9:].isdigit()]
    revision=f'revision-{max(revisions,default=0)+1:04d}';dest=stage/'books'/revision;dest.mkdir(parents=True)
    catalog=read(stage/'terminology.catalog.json');save(dest/'terminology.catalog.json',catalog)
    (dest/'sections').mkdir();bridges={n['title_id']:n for n in writing.walk(plan['tree'])}
    book={'profile':'learning-book-v1','id':'book','title':chapters['tree']['title'],'introduction':introduction,
        **seed,'writing_run':revision,'goals':goal(chapters['tree'],qnodes,answers),'chapters':[],
        'coverage':{},'validation':{'passed':False,'errors':[]}}
    book.pop('section_id')
    used_terms=set();sources=set();quiz_total=0;section_total=0
    for index,chapter in enumerate(chapters['tree']['children'],1):
        item={'id':chapter['id'],'number':str(index),'title':chapter['title'],'goals':goal(chapter,qnodes,answers),'sections':[]}
        for section in chapter['children']:
            doc=make_section(section,bridges[section['id']],plan,chapters,qnodes,drafts,answers)
            if section['id']==chapter['children'][0]['id']:
                doc['context_goals']=copy.deepcopy(item['goals'])
                if index==1:
                    doc['context_goals']=copy.deepcopy(book['goals'])+doc['context_goals']
                    doc['book_introduction']=introduction
            override=(section_overrides or {}).get(section['id'],{})
            for field in ['opening','units','summary','pitfalls','quiz']:
                if field in override:doc[field]=copy.deepcopy(override[field])
            for unit in doc['units']:unit['source_nodes']=qnodes[unit['question_id']]['source_nodes']
            inventory=writing.terminology_inventory(doc,catalog);required={t['term_id'] for t in inventory['terms']}
            doc['glossary']=[copy.deepcopy(t) for t in catalog['entries'] if t['id'] in required]
            doc['catalog_path']=(dest/'terminology.catalog.json').relative_to(root).as_posix()
            doc['writing_run']=revision
            report=(dest/'sections'/(section['id']+'-terms.json')).relative_to(root).as_posix()
            doc['coverage']={'questions':len(doc['core_questions']),'units':len(doc['units']),'answered':len(doc['summary']),
                'quiz':len(doc['quiz']),'terms':len(required),'covered_terms':len(required),'term_percentage':100.0,'report':report}
            errors=writing.check_demo(doc,root)
            if errors:
                save(dest/'failure.json',{'section':section['id'],'errors':errors})
                raise ValueError(section['id']+'\n'+'\n'.join(errors))
            doc['validation']={'passed':True,'errors':[]}
            path=dest/'sections'/(section['id']+'.json');save(path,doc);save(root/report,inventory)
            item['sections'].append({'id':section['id'],'number':doc['section_number'],'title':doc['title'],'path':path.relative_to(root).as_posix()})
            used_terms.update(required);section_total+=1;quiz_total+=len(doc['quiz'])
            for unit in doc['units']:sources.update(unit['source_nodes'])
        book['chapters'].append(item)
    material=read(root/plan['material_tree']);material_count=len(list(writing.walk(material['tree'])))
    book['coverage']={'sections':section_total,'question_nodes':len(qnodes),'answered_questions':len(answers),
        'teaching_units':len(concrete),'material_nodes':material_count,'covered_material_nodes':len(sources),
        'quiz':quiz_total,'unique_terms':len(used_terms),'question_percentage':100.0,'material_mapping_percentage':100.0}
    errors=check_book(book,root)
    if errors:save(dest/'failure.json',{'errors':errors});raise ValueError('\n'.join(errors))
    book['validation']={'passed':True,'errors':[]};save(dest/'book.json',book)
    temp=stage/'book.tmp';save(temp,book);temp.replace(stage/'book.json')
    return book

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='将已经完成的逐问内容组织成教材并检查全量问题与材料映射')
    parser.add_argument('draft',type=Path);args=parser.parse_args();data=read(args.draft)
    result=publish_book(STAGE.parent,data['units'],data['answers'],data['introduction'],data.get('section_overrides'))
    print(json.dumps(result['coverage'],ensure_ascii=False))
