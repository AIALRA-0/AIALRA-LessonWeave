"""统一非文本素材的字段、写作要求与确定性检查，检查只返回问题列表"""
import copy
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator

VERSION = 'media-1.0'
HERE = Path(__file__).resolve().parent
KINDS = ('image', 'table', 'mermaid', 'formula', 'code', 'model', 'video', 'audio', 'interactive')


def obj(fields):
    return {'type': 'object', 'properties': fields, 'required': list(fields), 'additionalProperties': False}


TEXT = {'type': 'string', 'minLength': 1, 'pattern': r'\S'}
NULL_TEXT = {'anyOf': [TEXT, {'type': 'null'}]}


def array(items):
    return {'type': 'array', 'items': items}


def schema(name):
    return json.loads((HERE / (name + '.schema.json')).read_text(encoding='utf-8'))


def variants():
    common = {'id': TEXT, 'caption': TEXT, 'source_refs': {**array(TEXT), 'minItems': 1}}
    general = schema('media-guide')
    fields = {
        'image': {'asset': TEXT, 'alt': TEXT, 'source_id': TEXT, 'source_region': TEXT},
        'table': {'headers': array(TEXT), 'rows': array(array({'type': ['string', 'number', 'null']}))},
        'mermaid': {'text': TEXT}, 'formula': {'text': TEXT},
        'code': {'text': TEXT, 'language': TEXT, 'filename': NULL_TEXT,
                 'runs': array(obj({'inputs': TEXT, 'outputs': TEXT}))},
        'model': {'asset': NULL_TEXT, 'vertices': {**array({'type': 'array', 'items': {'type': 'number'}, 'minItems': 3, 'maxItems': 3}), 'minItems': 1},
                  'faces': {**array({'type': 'array', 'items': {'type': 'integer', 'minimum': 0}, 'minItems': 3}), 'minItems': 1}, 'unit': TEXT,
                  'parts': array(obj({'label': TEXT, 'face_indices': array({'type': 'integer', 'minimum': 0})}))},
        'video': {'asset': TEXT, 'poster': NULL_TEXT, 'cues': array(obj({'time': {'type': 'number', 'minimum': 0}, 'label': TEXT}))},
        'audio': {'asset': TEXT, 'cues': array(obj({'time': {'type': 'number', 'minimum': 0}, 'label': TEXT}))},
        'interactive': {'asset': TEXT},
    }
    return [obj({**copy.deepcopy(common), 'kind': {'const': kind}, **extra,
        'guide': schema('code-guide') if kind == 'code' else copy.deepcopy(general)}) for kind, extra in fields.items()]


def prompt_rules():
    return [
        '非文本资源在本次正文调用中共同生成 guide，保持 id、caption、source_refs 与实际素材本体，编号由渲染器按当前章节计算，源文件、原图和源码保持准确，同源素材可在不同位置再次展示，来源覆盖仍按来源去重',
        '图片、表格、Mermaid、公式、模型、视频、音频和交互内容使用 reading_guide、components、explanation、takeaway 四部分，先展示素材与编号题注，关键组分直接展开为 BP 释义列表，具体讲解用自然段，必要计算使用 formula，无需计算时为 null',
        '图片讲清区域、坐标、单位、趋势与对比；表格讲清行列、统计范围与比较条件；Mermaid 讲清节点、连线与整体功能；公式讲清变量单位、关系依据、代入与推导；模型讲清空间部件、关系和可观察结果；视频音频按实际片段与时间说明过程；交互说明输入、可操作动作、输出与参数实验',
        '代码使用专用 guide：line_annotations 每条保存行范围、role 和自然连贯的 sentence，不以空格拼接句子片段；overview 用 premise/action/result 三段综述功能与用法；segments 是同一代码块内的讲解分段，每段包含 overview、扁平 components 表、core_logic 功能逻辑与 takeaway，最后 summary 综合总结',
        '代码正文解释使用场景、如何提供输入、输出的含义、功能协作及业务理由，语句职责由行注承担；每段只保留综合讲解、关键组分、核心逻辑、理解结论四个固定部分，组分用 owner 表达所属类或函数，整体合成一张表，核心逻辑使用连续自然段，使用从属编号，完整代码只展示一份并随阅读高亮',
        '代码 guide 的全部行号以当前 text 的第一行为 1，保留空行参与计数，不把原文件行号混入局部展示；行注与分段覆盖声明、执行语句和关闭边界，components 与 core_logic 指向本段实际使用位置，原文件行号只保留在来源定位中',
        '代码 runs 只原样使用执行器已经提供的实际输入输出记录，缺少执行记录时填写空数组，写作任务不声称已经执行；素材 asset 使用已有本地资源，模型网格沿用真实 vertices、faces 与单位，交互使用已有本地 HTML，写作任务不编造文件路径或数值',
        '媒体讲解直接教清素材承载的关系、机制、实例与结果，保持明确主谓关系，不写原文概括或材料指出，不写内部来源编号，作者中文省略中文句号，每段接住前面已经讲清的内容；避免不是……而是……等绕行句式，事实所需的否定条件保持准确，原文、忠实译文、源码和公式保留准确形式',
    ]


def authored_texts(value, path='$'):
    """只取作者讲解，原始代码、公式、表格数据和源文件路径保持原样"""
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {'line_start', 'line_end', 'id', 'role', 'owner', 'name', 'kind', 'type', 'default', 'label', 'math_label', 'formula'}:
                continue
            if isinstance(child, str):
                yield path + '.' + key, child
            elif isinstance(child, (dict, list)):
                yield from authored_texts(child, path + '.' + key)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from authored_texts(child, path + '[' + str(i) + ']')


def required_code_lines(text, language=None):
    """只要求实际代码行具备行注和讲解归属，纯注释不增加强制讲解负担"""
    lines=text.splitlines();console=any(line.lstrip().startswith('>>> ')for line in lines)
    fallback={i for i,line in enumerate(lines,1)if line.strip()
              and not(console and line.strip()in {'>>>','...'})
              and not(line.lstrip().startswith(('#','//'))and not re.search(r'[A-Za-z0-9\u4e00-\u9fff]',line))}
    if not language:return fallback
    try:
        from pygments.lexers import get_lexer_by_name
        from pygments.token import Comment
        from pygments.util import ClassNotFound
    except ImportError:return fallback
    try:lexer=get_lexer_by_name(language.casefold(),stripnl=False,ensurenl=False)
    except ClassNotFound:return fallback
    required=set();line=1
    for kind,fragment in lexer.get_tokens(text):
        comment=kind in Comment and kind not in Comment.Preproc and kind not in Comment.PreprocFile
        for piece in fragment.splitlines(keepends=True):
            if not comment and piece.strip():required.add(line)
            line+=piece.count('\n')
    return required


def guide_findings(value, kind, text=None, language=None):
    expected = schema('code-guide' if kind == 'code' else 'media-guide')
    issues = [e.json_path + ': ' + e.message for e in Draft202012Validator(expected).iter_errors(value)]
    if issues:
        return issues
    from positive_writing import FORBIDDEN
    for location, sentence in authored_texts(value):
        if re.search(FORBIDDEN.pattern+r'|。|原文概括|材料指出|\bn\d{6}\b', sentence):
            issues.append(location + ': 作者文字需要按当前写作规则调整')
    if kind != 'code' or text is None:
        return issues
    lines = text.splitlines()
    nonempty = required_code_lines(text,language)
    annotated, assigned, duplicate, ids = set(), set(), set(), set()
    for entry in value['line_annotations']:
        if not 1 <= entry['line_start'] <= entry['line_end'] <= len(lines):
            issues.append('代码行注的范围超出实际源码')
        annotated.update(range(entry['line_start'], entry['line_end'] + 1))
    for segment in value['segments']:
        if segment['id'] in ids:
            issues.append('代码讲解分段 ID 重复')
        ids.add(segment['id'])
        if not 1 <= segment['line_start'] <= segment['line_end'] <= len(lines):
            issues.append('代码讲解分段的范围超出实际源码')
        covered = set(range(segment['line_start'], segment['line_end'] + 1)) & nonempty
        duplicate |= covered & assigned
        assigned |= covered
        for entry in segment['components'] + segment['core_logic']:
            if not segment['line_start'] <= entry['line_start'] <= entry['line_end'] <= segment['line_end']:
                issues.append(segment['id'] + ': 组分或功能说明的行号超出当前分段')
    if nonempty - annotated:
        issues.append('代码缺少行注：' + ', '.join(map(str, sorted(nonempty - annotated))))
    if nonempty - assigned:
        issues.append('代码缺少讲解归属：' + ', '.join(map(str, sorted(nonempty - assigned))))
    if duplicate:
        issues.append('代码行重复归属讲解分段：' + ', '.join(map(str, sorted(duplicate))))
    return issues


def check(resource, root=None, source_ids=None):
    """检查字段、引用、资源存在及代码行覆盖，不把格式检查当成语义理解证明"""
    issues = [e.json_path + ': ' + e.message for e in Draft202012Validator(schema('media-resource')).iter_errors(resource)]
    if issues:
        return issues
    issues += guide_findings(resource['guide'], resource['kind'], resource.get('text'), resource.get('language'))
    if source_ids is not None:
        for key in set(resource['source_refs']) - set(source_ids):
            issues.append('媒体引用的来源不存在：' + key)
    if root is not None:
        root = Path(root).resolve()
        for field in ('asset', 'poster'):
            name = resource.get(field)
            if not name:
                continue
            path = (root / name.lstrip('/')).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                issues.append('媒体本地资源不存在：' + name)
    if resource['kind'] == 'table' and any(len(row) != len(resource['headers']) for row in resource['rows']):
        issues.append('表格每一行需要与表头具有相同列数')
    if resource['kind'] == 'model':
        vertices = resource['vertices']
        if any(len(point) != 3 for point in vertices) or any(i >= len(vertices) for face in resource['faces'] for i in face):
            issues.append('三维模型的顶点或面索引与实际网格不一致')
        if any(i >= len(resource['faces']) for part in resource['parts'] for i in part['face_indices']):
            issues.append('模型部件引用的面超出实际网格')
    return issues
