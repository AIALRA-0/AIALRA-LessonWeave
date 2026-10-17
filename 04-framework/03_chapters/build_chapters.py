"""按前置关系核对目录，让每个问题恰好归入一个标题"""
import argparse
import copy
import importlib.util
import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator


def walk(node):
    yield node
    for child in node['children']:
        yield from walk(child)


def load_questions(document, root):
    root=Path(root).resolve()
    path=(root/document['question_tree']).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('目录没有对应的本地问题树')
    questions=json.loads(path.read_text(encoding='utf-8'))
    if questions.get('question_run')!=document['question_run'] or not questions['validation']['passed']:
        raise ValueError('目录引用的问题版本不一致或尚未通过检查')
    if any(document[k]!=questions[k] for k in ['material_tree','material_run']):
        raise ValueError('目录和问题树引用了不同的材料版本')
    spec=importlib.util.spec_from_file_location('outline_question_check',root/'02_questions/build_questions.py')
    checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
    errors=checker.check_questions(questions,root)
    if errors:
        raise ValueError('问题树需要先修复：'+'；'.join(errors))
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
        if n['title']!=n['premise']+n['question']:
            errors.append(n['id']+' 的标题必须由前提与问句直接拼成')
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
    document.pop('coverage',None);document.pop('chapter_run',None)
    document['validation']={'passed':False,'errors':[]}
    questions=load_questions(document,root)
    plan=derive_plan(document,questions)
    document['learning_order']=plan['learning_order']
    for n in walk(document['tree']):
        n['source_nodes']=plan['source_nodes'][n['id']]
        n['requires']=plan['requires'][n['id']]
    errors=check_chapters(document,root)
    if errors:raise ValueError('\n'.join(errors))
    stage=root/'03_chapters'
    numbers=[int(p.name[9:]) for p in (stage/'history').glob('revision-*') if p.name[9:].isdigit()]
    revision=f'revision-{max(numbers,default=0)+1:04d}'
    destination=stage/'history'/revision;destination.mkdir(parents=True)
    document['chapter_run']=revision
    document['coverage']=dict(plan['summary'],report=f'03_chapters/history/{revision}/coverage.json')
    document['validation']={'passed':True,'errors':[]}
    report={'question_tree':document['question_tree'],'question_run':document['question_run'],
            'material_tree':document['material_tree'],'material_run':document['material_run'],
            'summary':plan['summary'],'allocations':plan['allocations'],'dependencies':plan['dependencies']}
    for name,data in [('chapters.json',document),('coverage.json',report)]:
        (destination/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary=stage/'chapters.tmp'
    temporary.write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(stage/'chapters.json')
    return document


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='检查每问恰好归属一个标题且学习顺序符合前置关系，通过后保存目录')
    parser.add_argument('candidate',type=Path)
    args=parser.parse_args()
    result=publish_chapters(Path(__file__).resolve().parent.parent,json.loads(args.candidate.read_text(encoding='utf-8')))
    print(json.dumps(result['coverage'],ensure_ascii=False))
