"""按前置关系核对目录，让每个问题恰好归入一个标题"""
import argparse
import copy
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator


def walk(node):
    yield node
    for child in node['children']:
        yield from walk(child)


def generation_tree(node):
    """模型只负责标题含义和问题归属，脚本负责的字段不进入生成合同"""
    fields = ['id', 'kind', 'premise', 'question', 'focus', 'question_ids']
    return {**{key: copy.deepcopy(node[key]) for key in fields},
            'children': [generation_tree(child) for child in node['children']]}


def chapter_document(questions, response):
    """把模型的目录安排接回冻结问题版本，路径和运行信息由脚本填写"""
    tree = generation_tree(response['tree'])
    tree['id'] = 'book'
    return {'profile': 'chapter-outline-v1',
            'question_tree': f"02_questions/history/{questions['question_run']}/questions.json",
            **{key: questions[key] for key in ['question_run', 'material_tree', 'material_run']},
            'tree': tree}


def load_questions(document, root):
    root=Path(root).resolve()
    path=(root/document['question_tree']).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('目录没有对应的本地问题树')
    questions=json.loads(path.read_text(encoding='utf-8'))
    if questions.get('question_run')!=document['question_run']:
        from lessonweave.findings import record
        record(root, '03_chapters', '目录引用的问题版本需要核对')
    if any(document[k]!=questions[k] for k in ['material_tree','material_run']):
        raise ValueError('目录和问题树引用了不同的材料版本')
    spec=importlib.util.spec_from_file_location('outline_question_check',root/'02_questions/build_questions.py')
    checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
    errors=checker.check_questions(questions,root)
    from lessonweave.findings import record
    record(root, '02_questions', errors)
    return questions


def derive_plan(document, questions):
    qnodes={n['id']:n for n in walk(questions['tree'])}
    titles=list(walk(document['tree']))
    owners={key:[] for key in qnodes}
    allocations=[]
    for title in titles:
        for key in title['question_ids']:
            if key in owners:
                owners[key].append(title['id'])
                q=qnodes[key]
                allocations.append({'question_id':key,'title_id':title['id'],
                                    'use':'goal' if q['children'] else 'explain',
                                    'source_nodes':q['source_nodes'],'depends_on':q['depends_on']})
    missing=[key for key,places in owners.items() if not places]
    duplicates=[key for key,places in owners.items() if len(places)>1]
    order=[a['question_id'] for a in allocations if a['use']=='explain']
    positions={key:index for index,key in enumerate(order)}
    edges=[]
    conflicts=[]
    for key,q in qnodes.items():
        if q['children']:continue
        for before in q['depends_on']:
            edge={'before_question':before,'after_question':key,
                  'before_title':owners.get(before,[None])[0] if owners.get(before) else None,
                  'after_title':owners[key][0] if owners[key] else None}
            edges.append(edge)
            if before not in positions or key not in positions or positions[before]>=positions[key]:
                conflicts.append(edge)
    material_nodes={key for q in qnodes.values() if not q['children'] for key in q['source_nodes']}
    assigned_material={key for a in allocations if a['use']=='explain' for key in a['source_nodes']}
    summary={'question_nodes':len(qnodes),'assigned_questions':len(qnodes)-len(missing),
             'assignments':len(allocations),'percentage':round((len(qnodes)-len(missing))*100/len(qnodes),4),
             'assignment_percentage':round(len(allocations)*100/len(qnodes),4),
             'unassigned_questions':missing,'duplicated_questions':duplicates,
             'material_nodes':len(material_nodes),'covered_material_nodes':len(assigned_material&material_nodes),
             'material_percentage':round(len(assigned_material&material_nodes)*100/len(material_nodes),4),
             'dependency_edges':len(edges),'order_conflicts':len(conflicts)}
    sources={}
    requires={}
    for title in titles:
        sources[title['id']]=list(dict.fromkeys(key for qid in title['question_ids'] if qid in qnodes for key in qnodes[qid]['source_nodes']))
        subtree={n['id'] for n in walk(title)}
        requires[title['id']]=list(dict.fromkeys(e['before_title'] for e in edges
             if e['after_title'] in subtree and e['before_title'] not in subtree and e['before_title'] is not None))
    return {'summary':summary,'allocations':allocations,'dependencies':edges,
            'conflicts':conflicts,'learning_order':order,'source_nodes':sources,'requires':requires}


def check_chapters(document, root):
    root=Path(root)
    schema=json.loads((root/'03_chapters/chapters.schema.json').read_text(encoding='utf-8'))
    errors=[str(e.message) for e in Draft202012Validator(schema).iter_errors(document)]
    if errors:return errors
    try: questions=load_questions(document,root)
    except (ValueError,KeyError,OSError) as error:return [str(error)]
    qnodes={n['id']:n for n in walk(questions['tree'])}
    if questions.get('planning_version') == 2:
        zero = [c for c in document['tree']['children'] if any(qid == 'q.0' or qid.startswith('q.0.') for t in walk(c) for qid in t['question_ids'])]
        if any(qid.startswith('q.0.') for qid in qnodes):
            if len(zero) != 1 or zero[0] is not document['tree']['children'][0]:
                errors.append('第 0 章问题需要共同归入目录最前面的独立一章')
            if any(not qid.startswith('q.0') for c in zero for t in walk(c) for qid in t['question_ids']):
                errors.append('第 0 章不混入正文问题')
    nodes=list(walk(document['tree']))
    ids=[n['id'] for n in nodes]
    if len(ids)!=len(set(ids)):errors.append('标题 ID 不能重复')
    titles=[n['title'] for n in nodes]
    if len(titles)!=len(set(titles)):errors.append('标题不能完全重复')
    def hierarchy(node,level):
        expected=['book','chapter','section'][min(level,2)]
        if level>2 or node['kind']!=expected:errors.append(node['id']+' 的书、章、节层级不正确')
        if level<2 and not node['children']:errors.append(node['id']+' 缺少下一级标题')
        if level==2 and not any(key in qnodes and not qnodes[key]['children'] for key in node['question_ids']):
            errors.append(node['id']+' 没有分配具体讲解问题')
        for child in node['children']:hierarchy(child,level+1)
    hierarchy(document['tree'],0)
    for n in nodes:
        plain = re.sub(r'^\d+(?:\.\d+)*\.\s+', '', n['title']) if document.get('title_format_version') else n['title']
        if plain!=n['premise']+n['question']:
            errors.append(n['id']+' 的标题必须由前提与问句直接拼成')
        if document.get('title_format_version') and n['kind'] != 'book' and not re.match(r'^\d+(?:\.\d+)*\. [^\r\n]+？$', n['title']):
            errors.append(n['id'] + ' 的标题需要使用 1. 或 1.1. 加单行问句')
        if set(n['question_ids'])-qnodes.keys():errors.append(n['id']+' 引用了不存在的问题')
    plan=derive_plan(document,questions)
    if plan['summary']['unassigned_questions']:errors.append('还有问题未分配：'+', '.join(plan['summary']['unassigned_questions']))
    if plan['summary']['duplicated_questions']:errors.append('问题被重复分配：'+', '.join(plan['summary']['duplicated_questions']))
    if plan['conflicts']:errors.append('章节顺序违反了问题的前置关系')
    if document['learning_order']!=plan['learning_order']:errors.append('保存的学习顺序与章节实际分配不一致')
    # 父问题所在的标题必须统领所有子问题，让章级目标与下面的内容对应
    owner={a['question_id']:a['title_id'] for a in plan['allocations']}
    descendants={n['id']:{x['id'] for x in walk(n)} for n in nodes}
    for q in qnodes.values():
        if q['id'] not in owner:continue
        if any(c['id'] in owner and owner[c['id']] not in descendants[owner[q['id']]] for c in q['children']):
            errors.append(q['id']+' 的子问题落在其目标标题之外')
    for n in nodes:
        if n['source_nodes']!=plan['source_nodes'][n['id']]:errors.append(n['id']+' 的材料引用与分配的问题不一致')
        if n['requires']!=plan['requires'][n['id']]:errors.append(n['id']+' 的前置标题与问题依赖不一致')
    if 'coverage' in document and {k:v for k,v in document['coverage'].items() if k!='report'}!=plan['summary']:
        errors.append('目录覆盖统计与逐项计算的结果不一致')
    return errors


def publish_chapters(root, candidate):
    root=Path(root)
    document=copy.deepcopy(candidate)
    document['title_format_version'] = 2
    # 书、章、节的完整标题都由同一规则组装，不依赖模型重复填写
    for title in walk(document['tree']):
        title['title'] = title['premise'] + title['question']
    body_number = 0
    for chapter in document['tree']['children']:
        is_preface = any(qid == 'q.0' or qid.startswith('q.0.') for title in walk(chapter) for qid in title['question_ids'])
        if is_preface:
            number = 0
        else:
            body_number += 1
            number = body_number
        chapter['title'] = f"{number}. " + chapter['premise'] + chapter['question']
        for si, section in enumerate(chapter['children'], 1):
            section['title'] = f"{number}.{si}. " + section['premise'] + section['question']
    document.pop('coverage',None);document.pop('chapter_run',None)
    document['validation']={'passed':False,'errors':[]}
    questions=load_questions(document,root)
    plan=derive_plan(document,questions)
    document['learning_order']=plan['learning_order']
    for n in walk(document['tree']):
        n['source_nodes']=plan['source_nodes'][n['id']]
        n['requires']=plan['requires'][n['id']]
    errors=check_chapters(document,root)
    from lessonweave.findings import record
    record(root, '03_chapters', errors)
    stage=root/'03_chapters'
    numbers=[int(p.name[9:]) for p in (stage/'history').glob('revision-*') if p.name[9:].isdigit()]
    revision=f'revision-{max(numbers,default=0)+1:04d}'
    destination=stage/'history'/revision;destination.mkdir(parents=True)
    document['chapter_run']=revision
    document['coverage']=dict(plan['summary'],report=f'03_chapters/history/{revision}/coverage.json')
    document['validation']={'passed':not errors,'errors':errors}
    report={'question_tree':document['question_tree'],'question_run':document['question_run'],
            'material_tree':document['material_tree'],'material_run':document['material_run'],
            'summary':plan['summary'],'allocations':plan['allocations'],'dependencies':plan['dependencies']}
    for name,data in [('chapters.json',document),('coverage.json',report)]:
        (destination/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary=stage/'chapters.tmp'
    temporary.write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(stage/'chapters.json')
    return document


def apply_chapter_patch(document, patch):
    """只调整标题和问题归属，原问题树及其材料引用继续保留"""
    result = copy.deepcopy(document)
    titles = {n['id']: n for n in walk(result['tree'])}
    for update in patch.get('title_updates', []):
        if update['id'] in titles:
            titles[update['id']].update({k: copy.deepcopy(v) for k, v in update.items() if k != 'children'})
    for entry in patch.get('new_titles', []):
        parent = titles.get(entry['parent_title_id'])
        title = copy.deepcopy(entry['title'])
        if parent is None or title['id'] in titles:
            continue
        children = parent.setdefault('children', [])
        position = 0 if not entry['after_title_id'] else next((i + 1 for i, child in enumerate(children) if child['id'] == entry['after_title_id']), len(children))
        children.insert(position, title)
        titles.update({n['id']: n for n in walk(title)})
    for assignment in patch.get('question_assignments', []):
        destination = titles.get(assignment['title_id'])
        if destination is None:
            continue
        qid = assignment['question_id']
        for title in titles.values():
            title['question_ids'] = [key for key in title['question_ids'] if key != qid]
        destination['question_ids'].append(qid)
    for entry in patch.get('child_orders', []):
        parent = titles.get(entry['parent_title_id'])
        if parent is None:
            continue
        children = {n['id']: n for n in parent['children']}
        if set(entry['child_title_ids']) == set(children) and len(entry['child_title_ids']) == len(children):
            parent['children'] = [children[key] for key in entry['child_title_ids']]
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='检查每问恰好归属一个标题且学习顺序符合前置关系，通过后保存目录')
    parser.add_argument('candidate',type=Path)
    args=parser.parse_args()
    result=publish_chapters(Path(__file__).resolve().parent.parent,json.loads(args.candidate.read_text(encoding='utf-8')))
    print(json.dumps(result['coverage'],ensure_ascii=False))
