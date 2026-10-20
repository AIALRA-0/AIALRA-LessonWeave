"""检查每个标题的承接问题，以及逐问讲解结束后接到哪里"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path

from jsonschema import Draft202012Validator


def walk(node):
    yield node
    for child in node['children']:yield from walk(child)


def load_chapters(document, root):
    root=Path(root).resolve();path=(root/document['chapters_path']).resolve()
    if not path.is_relative_to(root) or not path.is_file():raise ValueError('承接计划没有对应的本地章节快照')
    chapters=json.loads(path.read_text(encoding='utf-8'))
    if chapters.get('chapter_run')!=document['chapter_run']:
        from lessonweave.findings import record
        record(root, '04_transitions', '承接计划引用的章节版本需要核对')
    spec=importlib.util.spec_from_file_location('transition_chapters',root/'03_chapters/build_chapters.py')
    checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
    errors=checker.check_chapters(chapters,root)
    from lessonweave.findings import record
    record(root, '03_chapters', errors)
    questions=checker.load_questions(chapters,root)
    for key in ['question_tree','question_run','material_tree','material_run']:
        if document[key]!=chapters[key]:raise ValueError('承接计划与章节引用了不同的'+key)
    return chapters,questions


def derive_context(chapters,questions):
    titles=list(walk(chapters['tree']));qnodes={n['id']:n for n in walk(questions['tree'])}
    sections=[n for n in titles if n['kind']=='section'];section_ids=[n['id'] for n in sections]
    owners={qid:n['id'] for n in sections for qid in n['question_ids'] if not qnodes[qid]['children']}
    order=chapters['learning_order'];positions={key:i for i,key in enumerate(order)}
    contexts={}
    for node in titles:
        contained=[n['id'] for n in walk(node) if n['kind']=='section']
        first=section_ids.index(contained[0]);last=section_ids.index(contained[-1])
        previous=sections[first-1] if first else None
        following=sections[last+1] if last+1<len(sections) else None
        review=[key for key in previous['question_ids'] if not qnodes[key]['children']] if previous else []
        units=[]
        for key in node['question_ids']:
            if qnodes[key]['children']:continue
            index=positions[key];next_key=order[index+1] if index+1<len(order) else None
            units.append({'question_id':key,'next_question_id':next_key,'next_section_id':owners.get(next_key)})
        sources=list(dict.fromkeys(key for qid in review+node['question_ids'] for key in qnodes[qid]['source_nodes']))
        contexts[node['id']]={'kind':node['kind'],'core_question_ids':node['question_ids'],
                             'previous_section_id':previous['id'] if previous else None,
                             'next_section_id':following['id'] if following else None,
                             'review_question_ids':review,'units':units,'source_nodes':sources}
    return contexts


def context_plan(root, chapters):
    """写作前只计算章节位置，真正承接文字在正文完成后另行生成"""
    document = {key: chapters[key] for key in ['question_tree', 'question_run', 'material_tree', 'material_run', 'chapter_run']}
    document.update(profile='transition-plan-v1', status='preview',
                    chapters_path=f"03_chapters/history/{chapters['chapter_run']}/chapters.json",
                    purpose='context_only', validation={'passed': False, 'errors': []})
    def node(title):
        return {'title_id': title['id'], 'premise': title['premise'], 'question': title['question'],
                'text': '承上启下：' + title['premise'] + title['question'],
                'closing_boundary': '当前部分覆盖该标题分配的全部问题，下一部分继续展开后续问题',
                'children': [node(child) for child in title['children']]}
    document['tree'] = node(chapters['tree'])
    return publish_transitions(root, document)


def check_transitions(document, root):
    root=Path(root)
    schema=json.loads((root/'04_transitions/transitions.schema.json').read_text(encoding='utf-8'))
    errors=[str(e.message) for e in Draft202012Validator(schema).iter_errors(document)]
    if errors:return errors
    try:chapters,questions=load_chapters(document,root)
    except (ValueError,KeyError,OSError) as e:return [str(e)]
    context=derive_context(chapters,questions)
    ns=list(walk(document['tree']));ids=[n['title_id'] for n in ns]
    if len(ids)!=len(set(ids)):errors.append('一个标题只能有一条承上启下计划')
    if set(ids)!=set(context):errors.append('承上启下计划必须覆盖全部且仅覆盖已有标题')
    titles={n['id']:n for n in walk(chapters['tree'])}
    if document['section_order']!=[n['id'] for n in titles.values() if n['kind']=='section']:
        errors.append('承接顺序与章节的阅读顺序不一致')
    sentences=[]
    for n in ns:
        key=n['title_id']
        if key not in context:continue
        if n['text']!='承上启下：'+n['premise']+n['question']:errors.append(key+' 的承接问题没有按两个字段直接拼接')
        sentences.append(n['premise']+n['question'])
        if [c['title_id'] for c in n['children']]!=[c['id'] for c in titles[key]['children']]:errors.append(key+' 的层级或子标题顺序发生变化')
        for field,expected in context[key].items():
            if n[field]!=expected:errors.append(key+' 的'+field+' 与章节或问题依赖不一致')
    if len(sentences)!=len(set(sentences)):errors.append('不同位置不能使用完全相同的承接问题')
    total_q=sum(len(n['core_question_ids']) for n in ns)
    expected_q=len(list(walk(questions['tree'])))
    if total_q!=expected_q:errors.append('原有问题的唯一分配没有完整保留')
    summary={'titles':len(context),'covered_titles':len(set(ids)&context.keys()),
             'sections':len(document['section_order']),'core_question_nodes':expected_q,
             'teaching_units':len(chapters['learning_order']),'percentage':round(len(set(ids)&context.keys())*100/len(context),4)}
    if 'coverage' in document and {k:v for k,v in document['coverage'].items() if k!='report'}!=summary:
        errors.append('承接计划的覆盖统计与实际结果不一致')
    return errors


def publish_transitions(root,candidate):
    root=Path(root);doc=copy.deepcopy(candidate)
    doc.pop('coverage',None);doc.pop('transition_run',None);doc['validation']={'passed':False,'errors':[]}
    chapters,questions=load_chapters(doc,root);context=derive_context(chapters,questions)
    for n in walk(doc['tree']):
        if n['title_id'] in context:n.update(context[n['title_id']])
    doc['section_order']=[n['id'] for n in walk(chapters['tree']) if n['kind']=='section']
    errors=check_transitions(doc,root)
    from lessonweave.findings import record
    record(root, '04_transitions', errors)
    stage=root/'04_transitions';nums=[int(p.name[9:]) for p in (stage/'history').glob('revision-*') if p.name[9:].isdigit()]
    revision=f'revision-{max(nums,default=0)+1:04d}';dest=stage/'history'/revision;dest.mkdir(parents=True)
    doc['transition_run']=revision
    summary={'titles':len(context),'covered_titles':len(context),'sections':len(doc['section_order']),
             'core_question_nodes':len(list(walk(questions['tree']))),'teaching_units':len(chapters['learning_order']),'percentage':100.0}
    doc['coverage']=dict(summary,report=f'04_transitions/history/{revision}/coverage.json')
    doc['validation']={'passed':not errors,'errors':errors}
    report={'chapters_path':doc['chapters_path'],'chapter_run':doc['chapter_run'],'summary':summary,
            'nodes':[dict(title_id=n['title_id'],previous_section_id=n['previous_section_id'],next_section_id=n['next_section_id'],review_question_ids=n['review_question_ids'],core_question_ids=n['core_question_ids'],units=n['units']) for n in walk(doc['tree'])]}
    for name,obj in [('transitions.json',doc),('coverage.json',report)]:
        (dest/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp=stage/'transitions.tmp';temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(stage/'transitions.json')
    return doc


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='检查并保存承上启下问题树，正文扩写在确认后另行生成')
    parser.add_argument('candidate',type=Path);args=parser.parse_args()
    result=publish_transitions(Path(__file__).resolve().parent.parent,json.loads(args.candidate.read_text(encoding='utf-8')))
    print(json.dumps(result['coverage'],ensure_ascii=False))
