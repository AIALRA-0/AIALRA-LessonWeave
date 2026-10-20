"""逐问生成的输入、输出与脚本装配，讲解规划和正文同次生成"""
import copy
import json
import re
from pathlib import Path
from jsonschema import Draft202012Validator
import media_contract
import writing_contract

HERE = Path(__file__).resolve().parent
VERSION = 'lean-c-1.0'
TEXT = {'type':'string','minLength':1}
STRINGS = {'type':'array','items':TEXT}


def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


def schema(name):
    return json.loads((HERE / (name+'.schema.json')).read_text(encoding='utf-8'))


def definitions():
    extras, glossary = writing_contract.schema('writing-extras'), writing_contract.schema('glossary')
    appendix = obj({k:copy.deepcopy(extras['properties'][k]) for k in ['pitfalls','quiz']} |
                   {k:copy.deepcopy(glossary['properties'][k]) for k in ['terms','local_notations']})
    completion = obj({**copy.deepcopy(appendix['properties']), 'bridge':copy.deepcopy(extras['properties']['bridge'])})
    group = obj({'id':TEXT,'title_premise':TEXT,'title_question':TEXT,'claim':TEXT,'reasoning':TEXT,'grounding':TEXT,
                 'supplement':{'type':['string','null']},'resource_ids':STRINGS,'plan_ids':STRINGS,
                 'resources':{'type':'array','items':{'anyOf':media_contract.variants()}}})
    unit = obj({'question_id':TEXT,'plan':obj({'items':{'type':'array','minItems':1,'items':obj({'id':TEXT,'statement':TEXT,'resource_ids':STRINGS})}}),
                'premise':TEXT,'explanation':{'type':'array','minItems':1,'items':group},
                'result':obj({'answer':TEXT,'generalization':TEXT}),'appendix':appendix})
    translation = obj({'translations':{'type':'array','items':obj({'resource_id':TEXT,'chinese':TEXT,'english':{'type':'string'}})}})
    bridges = obj({'bridges':{'type':'array','items':obj({'section_id':TEXT,**extras['properties']['bridge']['properties']})}})
    return {'c-unit':unit,'c-completion':completion,'c-translation':translation,'c-bridges':bridges}


GLOBAL_RULES = [writing_contract.SUBJECT_PROMPT,
    '作者中文保持清楚连贯，省略中文句号，正文只引用材料内容，来源编号保留在映射字段',
    '直接说明条件、事实、过程与结果，避免不是……而是……等绕行句式，保留事实所需的否定条件，不把讲解变成原文概括',
    '只执行本次任务，一次返回约定 JSON，不审查或返修其他任务，也不声称已经独立验证语义覆盖']


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(',',':'))


def glossary_rules():
    return ['本次直接输出全部实际使用的专业术语及完整三段解释，不另开术语清点请求，常见专业缩写与媒体中出现的名称也应登记',
        '输出采用紧凑 JSON，JSON 结构不添加缩进、换行和冒号后的排版空格，字符串中的正常空格和段落内容保持准确；字段名称、层级、空字段以及三段内部的细字段全部保留，不通过缩短解释来压缩输出',
        '名称由 abbreviation、chinese、english 构成，缩写可为空且与英文全称不同，英文全称按专业规范书写，保留官方大小写与必要连接词',
        'professional_definition 用 genus、differentia、boundary、可空 extension 写完整定义；intuitive_explanation 用 anchor、mapping、intuition、可空 extension 写直观解释；typical_example 用 initial_conditions、mechanism、outcome、可空 extension 写典型实例，各组成一段完整话',
        '定义只说明概念是什么、必要特征与边界，生活类比使用读者熟悉的物体或活动，实例只呈现一件小事的初始条件、过程和结果；各段开头接住前一段已经建立的认识，结尾收束本段，不重复其他段落的职责',
        '每段细字段合成后应是一段主谓关系清楚的完整话，允许必要的主语共享，禁止用空格串联名词短语；类比的对象身份、动作方向和因果关系应与定义一致；默认使用简短通用实例，材料有特殊边界时再补材料实例，不为每份材料强行定制',
        '先准确解释术语本身，再联系当前材料，不把术语表写成正文的重复综述，单字母变量放入 local_notations 并指向实际定义位置']


def completion_prompt(document, questions):
    return dumps({'task':'现有正文保持原样，只一次补齐当前样章的承接、易错点、练习和完整术语定义',
        'questions':questions,'completed_document':document,
        'rules':['bridge.carryover 根据本样章的真实起点写承上，只有先前问题的规划，没有先前成稿时应以材料情境起笔，不声称前文已经讲清',
        'bridge.premise 与 question 组成直接相连的启下段，标题由页面固定为承上启下',
        'pitfalls 简短回答容易混淆的问题核心，标题为直接相关的 premise 加 question，默认四道单选和一道简答，围绕四个问题分配，数值与条件沿用现有正文',
        'summary 由脚本复用各问 result.answer，本任务不再次生成总结，不改写正文'],
        'glossary_rules':glossary_rules()})


def writer_prompt(context, question, resources, quota):
    return dumps({'task':'同一次调用内，先规划当前问题内部的多条讲解，再依次写正文与独立媒体讲解，末尾补齐分配的练习、易错点与术语',
        'background':{k:context.get(k) for k in ['title','outline','context_goals']},'question':question,
        'materials':resources,'quiz_quota':quota,
        'rules':['plan.items 每条是一整句，说明使用哪些材料解释什么、怎样解释，以及读者最后应理解什么，resource_ids 至少共同覆盖本问全部材料',
                 '每个问题拥有自己的 premise、多组 explanation 和 result，每组使用直接相关的 title_premise 与 title_question，同一条规划可展开多组讲解；笔记输入框由前端自动提供，本任务不生成笔记组、记笔记方法或提示用户写理解的额外文字',
                 'claim 提出明确命题，reasoning 展开原因与条件，grounding 落到实例或证据，supplement 按需为 null，result.answer 回答本问，generalization 提炼适用规律',
                 '各组 resource_ids 与 plan_ids 指向实际材料与本问规划，保留全文、数值、条件和图中关系，正文只展示内容，材料只在 materials 出现一次',
                 'kind=file 的材料只登记文件用途、格式、大小和本地位置，使用已有 table 媒体结构展示元数据，不当成图片；文件仍未解析时只解释其在项目中的职责，不编造 PDF 页内内容；系统元数据不生成教学段落',
                 'appendix 根据已经写出的内容完成，quiz 按给定 Schema 的固定题位填写，每个题位分别负责一道题，禁止留空或重复题目；汇总答案由脚本复用 result.answer，承接交给完成后的紧凑边界请求',
                 '在本次生成结束前，内部核对 materials 中每个实际条目是否已经进入 plan 和讲解组；标题、图注与目录材料可以连同对应内容解释其作用；遗漏内容应接回相关推理过程，再关联真实讲清它的组，禁止只添加引用编号凑覆盖；这个核对在本次调用中完成，不额外输出审查报告'],
        'media_rules':media_contract.prompt_rules(),'glossary_rules':glossary_rules()})


def writer_schema(quota):
    """模型按固定题位生成练习，脚本只把题位装回已有数组"""
    value=copy.deepcopy(schema('c-unit'))
    variants=value['properties']['appendix']['properties']['quiz']['items']['anyOf']
    kinds={v['properties']['kind']['const']:v for v in variants}
    slots={kind+'_'+str(i+1):copy.deepcopy(kinds[kind]) for kind,count in quota.items() for i in range(count)}
    value['properties']['appendix']['properties']['quiz']=obj(slots)
    return value


def reader_quiz(value):
    value=copy.deepcopy(value)
    quiz=value['appendix']['quiz']
    if isinstance(quiz,dict):value['appendix']['quiz']=list(quiz.values())
    return value


def translation_prompt(resources):
    return dumps({'task':'逐条忠实提供中文与英文显示文本，原始资源只出现一次，保持数字、单位、公式、代码和资源 ID',
        'resources':[{k:r[k] for k in ['id','original'] if k in r} for r in resources],
        'rules':['英文原句原样填写 english 并翻译 chinese，中文原句原样填写 chinese 并翻译 english，源码保持原样',
                 '这是翻译任务，忠实保留原文语气、否定和标点，不加入讲解或省略信息']})


def merge_terms(terms):
    """同一名称只展示一份定义，不生成第二份语义改写，异义词条保留其原始记录"""
    result, seen, conflicts = [], {}, []
    for term in terms:
        key = re.sub(r'\s+','',term.get('english','')).casefold(), term.get('chinese','')
        if key in seen:
            if term != seen[key]:
                conflicts.append({'kept':seen[key]['id'],'other':term['id'],'reason':'同一名称保留首个完整解释，其他原稿继续留在逐问文件'})
            continue
        seen[key] = term
        result.append(copy.deepcopy(term))
    return result, conflicts


def findings(value, name):
    return [error.json_path+': '+error.message for error in Draft202012Validator(schema(name)).iter_errors(value)]


def mappings(unit, known):
    """只检查实际引用与使用关系，覆盖率由脚本计算，语义审查状态另存"""
    planned = {r for item in unit.get('plan',{}).get('items',[]) for r in item['resource_ids']}
    used = {r for item in unit.get('explanation',[]) for r in item['resource_ids']}
    expected = set(known)
    missing, unknown = sorted(expected-used), sorted((planned|used)-expected)
    errors = (['正文缺少材料映射：'+', '.join(missing)] if missing else [])
    errors += (['材料引用不存在：'+', '.join(unknown)] if unknown else [])
    errors += (['规划缺少材料映射：'+', '.join(sorted(expected-planned))] if expected-planned else [])
    ids = {i['id'] for i in unit.get('plan',{}).get('items',[])}
    referenced = {r for item in unit.get('explanation',[]) for r in item['plan_ids']}
    if ids != referenced:
        errors.append('讲解组与本问规划的实际对应需要检查')
    return {'expected':len(expected),'covered':len(expected&used),'percentage':100*len(expected&used)/len(expected) if expected else 100,
            'missing':missing,'unknown':unknown,'errors':errors,'semantic_review':'not_run'}
