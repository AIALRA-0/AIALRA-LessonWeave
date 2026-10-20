"""模型规划问题，脚本检查材料去处和学习顺序后保存"""
import argparse
import copy
import json
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
    if material['run'] != document['material_run']:
        raise ValueError('问题树与材料树的运行编号不一致')
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
    material_scope(document, root)
    from source_disposition import evaluate
    material = json.loads((Path(root) / document['material_tree']).read_text(encoding='utf-8'))
    return evaluate(document, material)


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
    positions = {key: index for index, key in enumerate(document['learning_order'])}
    leaves = [n['id'] for n in nodes if not n['children']]
    for node in nodes:
        if set(node['source_nodes']) - allowed:
            errors.append(node['id'] + ' 引用了材料范围之外的节点')
        for key in node['depends_on']:
            if key not in positions or positions[key] >= positions.get(node['id'], len(positions)):
                errors.append(node['id'] + ' 的前置问题不存在，或排在当前问题之后')
            elif key not in leaves:
                errors.append(node['id'] + ' 必须依赖已经讲过的具体问题，不能把整体目标当作已学知识')
    if set(document['learning_order']) != set(leaves) or len(document['learning_order']) != len(leaves):
        errors.append('学习顺序需要恰好包含全部具体问题')
    report = mapping_report(document, root)
    errors.extend(report.get('issues', []))
    if document.get('planning_version') == 2:
        import re
        for node in nodes:
            if not re.fullmatch(r'q\.(root|\d+(?:\.\d+)*)', node['id']):
                errors.append(node['id'] + ' 需要使用 q.root 或 q.0.1 这样的统一编号')
            if not node['children'] and document['source_roots'][0] in node['source_nodes']:
                errors.append(node['id'] + ' 不能用整棵材料根节点代替具体来源')
        if report['summary']['preface_missing']:
            errors.append('材料有可用元数据，需要在同一问题树中补齐 q.0 的具体问题')
    if report['summary']['unmapped']:
        errors.append('还有 ' + str(len(report['summary']['unmapped'])) + ' 个材料节点没有明确去处，具体来源见 missing-index.json')
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
    from lessonweave.findings import record
    record(root, '02_questions', errors)
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
    document['validation'] = {'passed': not errors, 'errors': errors}
    for name, data in [('coverage.json', report), ('questions.json', document)]:
        (destination / name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    if document.get('planning_version') == 2:
        from source_disposition import missing_index
        material = json.loads((root / document['material_tree']).read_text(encoding='utf-8'))
        (stage / 'missing-index.json').write_text(json.dumps(missing_index(document, material, report), ensure_ascii=False, indent=2), encoding='utf-8')
    temporary = stage / 'questions.tmp'
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(stage / 'questions.json')
    return document


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='检查材料去处和前置顺序，保存问题树与真实差集')
    parser.add_argument('candidate', type=Path)
    args = parser.parse_args()
    result = publish_questions(Path(__file__).resolve().parent.parent,
                               json.loads(args.candidate.read_text(encoding='utf-8')))
    print(json.dumps(result['coverage'], ensure_ascii=False))
