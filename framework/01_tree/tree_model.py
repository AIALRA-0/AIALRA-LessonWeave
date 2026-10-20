import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator


class TreeBuilder:
    def __init__(self):
        self.count = 0

    def node(self, kind, content, source, children=None):
        self.count += 1
        return {'id': f'n{self.count:06}', 'type': kind, 'content': content,
                'source': source, 'children': children or []}


def walk(node):
    yield node
    for child in node['children']:
        yield from walk(child)


def check_tree(document, schema, root, evaluation=None):
    """逐项检查节点、原文内容和本地对象，返回实际失败原因"""
    if document.get('format') == 'full-material-tree':
        errors=[];seen=set();pending=[document.get('tree')]
        if document.get('kind') not in {'web','pdf','code'} or not document.get('run'):
            errors.append('原生材料树缺少已识别的材料类型或运行编号')
        while pending:
            node=pending.pop()
            if not isinstance(node,dict) or not isinstance(node.get('children'),list):
                errors.append('原生材料节点缺少节点对象或 children 数组');continue
            nid=node.get('id')
            if not isinstance(nid,str) or not nid or nid in seen:
                errors.append('原生材料节点缺少唯一编号：'+str(nid))
            seen.add(nid)
            if not isinstance(node.get('type'),str) or not node['type']:
                errors.append(str(nid)+' 缺少节点类型')
            if 'text' in node and not isinstance(node['text'],str):
                errors.append(str(nid)+' 的原生文本应为字符串')
            if 'source' in node and not isinstance(node['source'],(dict,list)):
                errors.append(str(nid)+' 的原生来源字段格式不正确')
            pending.extend(node['children'])
        return errors
    from content_checks import evaluate_content
    errors = [f"{'/'.join(map(str, error.absolute_path))}: {error.message}"
              for error in Draft202012Validator(schema).iter_errors(document)]
    if errors:
        return errors
    nodes = list(walk(document['tree']))
    ids = [node['id'] for node in nodes]
    if len(ids) != len(set(ids)):
        errors.append('树中存在重复的节点 ID')
    for relation in document['relations']:
        if relation['from'] not in ids or relation['to'] not in ids:
            errors.append('引用关系指向了树中不存在的节点')
    for node in nodes:
        if node['type'] == 'unknown' and document['status'] == 'parsed':
            errors.append('存在未处理节点时，结果不能标为全部解析完成')
        if node['type']=='file' and node['content'].get('syntax_diagnostics'):
            if not any(child['type']=='unknown' for child in walk(node)):
                errors.append(node['id']+' 有语法疑点，但没有保留待核对节点')
    try:
        content,objects = evaluation if evaluation is not None else evaluate_content(Path(root),document)
        errors.extend(objects['errors'])
        errors.extend('原材料内容没有完整保留：'+unit for unit in content['missing'])
    except (OSError,ValueError,KeyError) as error:
        errors.append('内容覆盖检查没有完成：'+str(error))
    return errors


def summarize(tree):
    counts = Counter(node['type'] for node in walk(tree))
    return {'nodes': sum(counts.values()), 'types': dict(counts), 'files': counts['file'],
            'unknown': counts['unknown']}


def save_result(root, document, output):
    root = Path(root)
    schema = json.loads((root / '01_tree/tree.schema.json').read_text(encoding='utf-8'))
    document['summary'] = {**document.get('summary', {}), **summarize(document['tree'])}
    if document['summary']['unknown'] and document['status'] == 'parsed':
        document['status'] = 'needs_review'
    from content_checks import normalize_content,evaluate_content
    normalize_content(document['tree'])
    content,objects=evaluate_content(root,document)
    document['coverage']['content']={k:v for k,v in content.items() if k!='entries'}
    document['coverage']['objects']=objects
    document['coverage']['profile']='content-tree-v1'
    document['validation'] = {'passed': False, 'errors': []}
    errors = check_tree(document, schema, root,(content,objects))
    report={'content':content,'objects':objects,'passed':not errors,'errors':errors}
    (output/'coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    document['validation'] = {'passed': not errors, 'errors': errors}
    if errors:
        document['status'] = 'needs_review'
    encoded = json.dumps(document, ensure_ascii=False, indent=2) + '\n'
    (output / 'tree.json').write_text(encoded, encoding='utf-8')
    # 当前树保留全部原文与真实诊断，后续阶段可以读取，不把格式诊断变成无材料可读的门禁
    current = root / '01_tree/tree.json'
    temporary = current.with_suffix('.tmp')
    temporary.write_text(encoded, encoding='utf-8')
    temporary.replace(current)
    return document
