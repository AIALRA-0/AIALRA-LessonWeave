"""约束新版写作字段，再把同一份内容转换成阅读器已经支持的正文块"""
import copy
import media_contract
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

VERSION = '0.13'
HERE = Path(__file__).resolve().parent
SUBJECT_PROMPT = '写作前先在内部明确每个核心命题的主体、行为或状态、对象和成立条件，再写成自然语言；切换主体时写明新主体，同一主体可共享主语；操作步骤、因果解释与普遍规律分层分句；正文只引用材料内容，内部编号留在映射中；正常输出只保留既定字段和正文'
POLICY = {'language_check': 'prompt_and_batch_scripts', 'language_review': 'disabled',
          'per_sentence_extra_fields': False, 'repair_scope': 'obvious_findings_only',
          'ambiguous_findings': 'record_only', 'coverage_review_unchanged': True,
          'dependency_parser': 'disabled', 'surface_check_is_grammar_proof': False}


def schema(name):
    return json.loads((HERE / (name + '.schema.json')).read_text(encoding='utf-8'))


def validate(value, name, findings=None):
    errors = [f'{e.json_path}: {e.message}' for e in Draft202012Validator(schema(name)).iter_errors(value)]
    if name == 'writing-unit':
        for group in value.get('explanation', []):
            for resource in group.get('resources', []):
                if 'guide' in resource:
                    errors.extend(media_contract.check(resource))
    if findings is not None:
        findings.extend(errors)
    return value


def paragraph(key, text):
    return {'id': key, 'kind': 'paragraph', 'text': text}


def compose(values):
    # 各字段都是完整陈述，脚本只连接已有内容，不补写事实或伪造缺失段落
    result='';previous=''
    for value in values:
        if not value or not str(value).strip():continue
        raw=str(value).strip();part=raw.strip('，,；;。')
        if not part:continue
        join='，'if previous.endswith(('，',','))or raw.startswith(('，',','))else'；'
        result+=(join if result else'')+part;previous=raw
    return result


def reader_unit(value):
    """旧正文原样读取，新稿的四段组按固定编号转换，保留图片和来源对应"""
    if 'result' not in value:
        return copy.deepcopy(value)
    validate(value, 'writing-unit')
    qid = value['question_id']
    blocks = []
    for group in value['explanation']:
        blocks.extend(paragraph(group['id'] + '-' + role, group.get(role, ''))
                      for role in ('claim', 'reasoning', 'grounding', 'supplement') if role != 'supplement' or group.get(role))
        blocks.extend(copy.deepcopy(group['resources']))
    return {'question_id': qid, 'problem': paragraph(qid + '-problem', value['premise']),
            'explanation': blocks,
            'synthesis': paragraph(qid + '-synthesis', compose(value['result'][key] for key in ('answer', 'generalization'))),
            'summary': paragraph(qid + '-summary', value['result']['answer']),
            'bindings': copy.deepcopy(value['bindings'])}


def reader_term(value):
    """名称由三个字段组装，三个定义组各显示一段，旧词条继续沿用原数据"""
    if 'professional_definition' not in value:
        return copy.deepcopy(value)
    result = copy.deepcopy(value)
    abbreviation = (result['abbreviation'] or '').strip()
    normalize = lambda s: re.sub(r'\s+', '', s).casefold()
    if abbreviation and normalize(abbreviation) == normalize(result['english']):
        abbreviation = ''
        result['abbreviation'] = None
    result['display'] = (abbreviation + ' ' if abbreviation else '') + result['chinese'] + '（' + result['english'] + '）'
    definition = result.pop('professional_definition')
    result['definition'] = compose(definition[key] for key in ('genus', 'differentia', 'boundary', 'extension'))
    result['explanation'] = []
    for name, keys in [('intuitive_explanation', ('anchor', 'mapping', 'intuition', 'extension')),
                       ('typical_example', ('initial_conditions', 'mechanism', 'outcome', 'extension'))]:
        group = result.pop(name)
        result['explanation'].append(compose(group[key] for key in keys))
    return result


def writer_prompt(generation, context, pack, inventory, qid, prior=None, following=None):
    points = [p for p in inventory['points'] if p['question_id'] == qid]
    return generation.dumps({'任务': '用独立上下文讲透当前问题，再关联实际解释位置',
        '共同要求': generation.RULES + [SUBJECT_PROMPT], '全局背景': context,
        '当前问题': generation.next_item(context['core_questions'], qid),
        '前问职责': prior, '后问职责': following, '真实材料': pack, '负责信息点': points,
        '媒体规范': media_contract.prompt_rules(),
        '结构': [
            'premise 是展开后的问题段，给出直接引发问题的条件，让读者明确需要解决什么',
            'explanation 按推理关系重复四段组，每组依次写 claim 核心陈述、reasoning 条件与推导、grounding 真实证据或明确标记的构造例子、supplement 必要限制和补充；四个字段各是一段完整话，不靠最小字数凑长度',
            '每组 id 唯一，point_ids 指明当前组解释的信息点，resources 保存紧邻这一组的图表、代码或公式，保留实际来源和区域，允许同一图片在不同问题再次引用',
            'result 只写 answer 和 generalization，前者直接回答本问，后者在适用条件下提炼可迁移结论，两个字段显示为同一段，后续问题由单独的承接阶段负责',
            '所有数值、图表趋势、条件、代码机制和信息点 checks 都应在当前推理中讲清，一段可解释多个信息点，一个点也可由多个段共同解释',
            'bindings 每点恰好一项，只引用实际渲染的块 ID：question_id-problem、组id-claim、组id-reasoning、组id-grounding、组id-supplement、资源id、question_id-synthesis',
            'question_id 原样保留，原文编号和问题编号只放在映射中，正文直接讲材料内容，不把编号作为引用句式',
        ], '输出': '只返回 writing-unit.schema.json 约定的字段，不输出逐句语法分析或覆盖百分比'})


def extras_prompt(generation, context, doc, inventory, previous):
    return generation.dumps({'任务': '正文已完成，现在补写两段承接、总结、易错点与练习',
        '共同要求': generation.RULES + [SUBJECT_PROMPT], '当前章节': context,
        '当前实际正文': doc, '前节实际正文与答案': previous, '信息点': inventory,
        '结构': [
            'bridge.carryover 依据前节实际正文写一段承上，首节依据真实材料情景起笔，标题本身不作为前节已经讲清的证据',
            'bridge.premise 给出直接导致当前问题的条件，bridge.question 引出本节问题，脚本把 premise 与 question 合成第二段启下，标题固定为承上启下',
            'summary 按 core_questions 原顺序逐问直接回答，pitfalls 用 premise 加 question 提问，body 直接回答易错点的核心并说明条件',
            'quiz 默认四道单选和一道简答，允许三至五道单选，简答恰好一道；每题保留 question_ids，单选恰好一个正确选项，简答带具体 rubric',
            '本任务先完成全部阅读内容，完整术语表由下一独立请求读取这些最终内容后生成',
        ], '输出': '只返回 writing-extras.schema.json，不在本轮生成术语定义'})


def glossary_prompt(generation, context, doc, catalog):
    legacy = json.loads(generation.extras_prompt(context, doc, {'points': []}, catalog))
    rules = [r for r in legacy['术语怎样清点与解释']
             if not r.startswith(('每个词条有一句', 'display 严格', '专业术语依照'))]
    return generation.dumps({'任务': '全部正文、承接、总结和练习完成后，独立清点并整理完整术语表及局部符号',
        '共同要求': generation.RULES + [SUBJECT_PROMPT], '完整阅读内容': doc,
        '既有名称': catalog, '术语规则': rules,
        '定义结构': [
            '名称只填写 abbreviation、chinese、english，abbreviation 可为空且与英文全称不同，显示名称由脚本组装',
            'professional_definition 用 genus 上位类别、differentia 必要特征、boundary 适用边界、extension 补充内容组成一段完整专业定义',
            'intuitive_explanation 用 anchor 熟悉事物、mapping 关系映射、intuition 核心直觉、extension 补充内容组成一段完整直观解释',
            'typical_example 用 initial_conditions 初始环境与对象、mechanism 触发过程、outcome 结果及所体现特征、extension 补充内容组成一段完整案例',
            '每组前三项必填，extension 字段保留，可为 null 或空字符串，三个组各显示一段，段内没有小标题，定义先解释概念本身，再联系本节材料',
        ], '输出': '只返回 glossary.schema.json，专业定义与局部符号使用各自字段'})


def surface_findings(value):
    """明显内部编号进入正文时拦截，可能省略主语的句子只记录提示"""
    findings = []
    prose_fields = {'premise', 'carryover', 'question', 'claim', 'reasoning', 'grounding', 'supplement',
                    'answer', 'generalization', 'text', 'description', 'definition', 'explanation',
                    'genus', 'differentia', 'boundary', 'extension', 'anchor', 'mapping', 'intuition',
                    'initial_conditions', 'mechanism', 'outcome', 'reference_answer', 'meaning', 'caption'}
    preserve = {'source_quotes', 'bindings', 'point_ids', 'question_ids', 'source_ids', 'source_nodes',
                'original', 'translation', 'english', 'code', 'raw_content', 'definition_quote'}
    def inspect(text, location):
        for pattern, code in [(r'\bn\d{6}\b', 'internal-reference'),
                               (r'(?:原文|材料)(?:中|的)?第[\d一二三四五六七八九十]+[句段]', 'numbered-source-prose')]:
            for match in re.finditer(pattern, text):
                findings.append({'location': location, 'code': code, 'severity': 'error', 'excerpt': match.group()})
        if re.match(r'^(?:先|再|应当|应该|需要|必须|可以)', text) or any(len(re.findall('[，,]', part)) >= 4 for part in text.split('；')):
            findings.append({'location': location, 'code': 'subject-or-density', 'severity': 'hint',
                             'excerpt': text[:100], 'reason': '结合前后文确认主体与分句，脚本只提示，保留合法的共享主语'})
    def visit(node, path='$', parent=''):
        if isinstance(node, dict):
            if node.get('kind') in {'code', 'formula'}:
                return
            for key, child in node.items():
                if key in preserve:
                    continue
                if isinstance(child, str) and key in prose_fields:
                    inspect(child, path + '.' + key)
                elif isinstance(child, (dict, list)):
                    visit(child, path + '.' + key, key)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                if isinstance(child, str) and parent in {'explanation', 'options', 'rubric', 'items', 'headers', 'rows'}:
                    inspect(child, path + f'[{index}]')
                else:
                    visit(child, path + f'[{index}]', parent)
    visit(value)
    return findings
