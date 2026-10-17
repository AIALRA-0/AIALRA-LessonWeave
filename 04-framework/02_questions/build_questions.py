"""外层 agent 拟定问题，脚本检查全部材料的映射和学习顺序后发布"""
import argparse
import copy
import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator


def walk(node):
    yield node
    for child in node['children']:
        yield from walk(child)


def material_scope(document, root):
    root = Path(root).resolve()
    path = (root / document['material_tree']).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('问题树没有对应的本地材料树')
    material = json.loads(path.read_text(encoding='utf-8'))
    if material['run'] != document['material_run'] or not material['validation']['passed']:
        raise ValueError('问题树引用的材料版本尚未通过检查或运行编号不一致')
    nodes = {node['id']: node for node in walk(material['tree'])}
    roots = document['source_roots']
    if document['scope'] == 'full_material' and roots != [material['tree']['id']]:
        raise ValueError('全量问题树必须以整份材料为检查范围，不能缩小分母')
    if set(roots + document['context_nodes']) - nodes.keys():
        raise ValueError('问题树引用了不存在的材料分支')
    required = {n['id'] for key in roots for n in walk(nodes[key])}
    allowed = required | {n['id'] for key in document['context_nodes'] for n in walk(nodes[key])}
    return nodes, required, allowed


def mapping_report(document, root):
    nodes, required, _ = material_scope(document, root)
    reverse = {key: [] for key in nodes}
    leaves = [n for n in walk(document['tree']) if not n['children']]
    # 父问题只表示学习目标，覆盖率只计算真正会逐问讲解的叶子问题
    for question in leaves:
        for key in question['source_nodes']:
            if key in reverse:
                reverse[key].append(question['id'])
    missing = sorted(key for key in required if not reverse[key])
    total = len(required)
    links = sum(len(reverse[key]) for key in required)
    kinds = Counter(nodes[key]['type'] for key in required)
    covered = Counter(nodes[key]['type'] for key in required if reverse[key])
    summary = {
        'total': total, 'covered': total - len(missing),
        'percentage': round((total - len(missing)) * 100 / total, 4),
        'links': links, 'mapping_percentage': round(links * 100 / total, 4),
        'leaf_questions': len(leaves), 'unmapped': missing,
        'by_type': {kind: {'total': count, 'covered': covered[kind]} for kind, count in sorted(kinds.items())},
    }
    return {
        'material_tree': document['material_tree'], 'material_run': document['material_run'],
        'scope': document['scope'], 'summary': summary,
        'rule': '逐个列出材料范围内的节点，只计算叶子问题的直接引用，同一节点可以由多个问题共同讲解',
        'nodes': [{'material_node': key, 'type': nodes[key]['type'], 'questions': reverse[key]}
                  for key in nodes if key in required],
    }


def check_questions(document, root):
    root = Path(root).resolve()
    schema = json.loads((root / '02_questions/questions.schema.json').read_text(encoding='utf-8'))
    errors = [str(e.message) for e in Draft202012Validator(schema).iter_errors(document)]
    if errors:
        return errors
    try:
        _, _, allowed = material_scope(document, root)
    except (ValueError, KeyError) as error:
        return [str(error)]
    nodes = list(walk(document['tree']))
    ids = [n['id'] for n in nodes]
    if len(ids) != len(set(ids)):
        errors.append('问题 ID 不能重复')
    texts = [(n['premise'].strip() + n['question'].strip()) for n in nodes]
    if len(texts) != len(set(texts)):
        errors.append('问题树中出现了文字完全相同的问题')
    positions = {key: index for index, key in enumerate(ids)}
    leaves = [n['id'] for n in nodes if not n['children']]
    for node in nodes:
        if set(node['source_nodes']) - allowed:
            errors.append(node['id'] + ' 引用了材料范围之外的节点')
        for key in node['depends_on']:
            if key not in positions or positions[key] >= positions[node['id']]:
                errors.append(node['id'] + ' 的前置问题不存在，或排在当前问题之后')
            elif key not in leaves:
                errors.append(node['id'] + ' 必须依赖已经讲过的具体问题，不能把整体目标当作已学知识')
    if document['learning_order'] != leaves:
        errors.append('讲解顺序必须与叶子问题的实际排列一致')
    report = mapping_report(document, root)
    if report['summary']['unmapped']:
        errors.append('还有材料节点没有对应的叶子问题：' + ', '.join(report['summary']['unmapped']))
    if 'coverage' in document:
        actual = {k: v for k, v in document['coverage'].items() if k != 'report'}
        if actual != report['summary']:
            errors.append('保存的覆盖统计与逐项重新计算的结果不一致')
    return errors


def publish_questions(root, document):
    root = Path(root)
    document = copy.deepcopy(document)
    document.pop('coverage', None)
    document.pop('question_run', None)
    document['validation'] = {'passed': False, 'errors': []}
    errors = check_questions(document, root)
    if errors:
        raise ValueError('\n'.join(errors))
    report = mapping_report(document, root)
    stage = root / '02_questions'
    history = stage / 'history'
    numbers = [int(p.name[9:]) for p in history.glob('revision-*') if p.name[9:].isdigit()]
    revision = f'revision-{max(numbers, default=0)+1:04d}'
    destination = history / revision
    destination.mkdir(parents=True)
    # 使用冻结路径，旧问题始终能回到当时的材料和覆盖报告
    document['question_run'] = revision
    document['coverage'] = dict(report['summary'], report=f'02_questions/history/{revision}/coverage.json')
    document['validation'] = {'passed': True, 'errors': []}
    for name, data in [('coverage.json', report), ('questions.json', document)]:
        (destination / name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary = stage / 'questions.tmp'
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(stage / 'questions.json')
    return document


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='检查全量材料映射和前置顺序，通过后保存问题树')
    parser.add_argument('candidate', type=Path)
    args = parser.parse_args()
    result = publish_questions(Path(__file__).resolve().parent.parent,
                               json.loads(args.candidate.read_text(encoding='utf-8')))
    print(json.dumps(result['coverage'], ensure_ascii=False))
