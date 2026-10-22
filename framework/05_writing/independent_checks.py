"""独立读取字段和映射检查完成情况，不调用模型评判讲解质量"""
import re
from collections import Counter
from pathlib import Path
from jsonschema import Draft202012Validator
import lean_contract as contract
import media_contract
import book_terminology as term_names
from positive_writing import FORBIDDEN

LINT=re.compile(FORBIDDEN.pattern+r'|。|原文概括|\bn\d{6}(?:\.[\w-]+)*\b')


def pointer(parts):
    return '/'+ '/'.join(str(p).replace('~','~0').replace('/','~1') for p in parts)


def issue(rule,path,message,target=None,**details):
    return {'rule':rule,'path':path,'message':message,'target':target if target is not None else path,**details}


def strings(value,parts=()):
    if isinstance(value,str):yield parts,value
    elif isinstance(value,list):
        for i,item in enumerate(value):yield from strings(item,parts+(i,))
    elif isinstance(value,dict):
        for key,item in value.items():yield from strings(item,parts+(key,))


def prose(value):
    """检查作者新写的说明，源码、公式本体、原文、译文和机器标识保持原样"""
    for parts,text in strings(value):
        last=parts[-1] if parts else ''
        if parts and parts[0]=='premise':yield parts,text;continue
        if parts and parts[0]=='explanation':
            if len(parts)==3 and last in {'title_premise','title_question','claim','body','reasoning','grounding','supplement'}:
                if text:yield parts,text
            elif 'resources' in parts and ('guide' in parts or last=='caption'):
                if last not in {'id','type','language','math_label','formula','label','owner','name'}:yield parts,text
        elif parts and parts[0]=='result':yield parts,text
        elif parts and parts[0]=='appendix':
            if parts[1]=='terms' and len(parts)>4 and parts[3] in {'professional_definition','intuitive_explanation','typical_example'}:
                if text:yield parts,text
            elif parts[1]=='pitfalls' and (last in {'premise','question','text'}):yield parts,text
            elif parts[1]=='quiz' and (last in {'text','reference_answer'} or 'options' in parts or 'rubric' in parts):yield parts,text


def unit_findings(value,resources,quota,question_id,root=None):
    findings=[]
    for error in Draft202012Validator(contract.schema('c-unit')).iter_errors(value):
        parts=list(error.path)
        if error.validator=='required':
            match=re.match(r"'([^']+)' is a required property",error.message)
            if match:parts.append(match[1])
        findings.append(issue('schema',pointer(parts),error.message))
    if findings:return findings
    if value['question_id']!=question_id:
        findings.append(issue('question_owner','/question_id','讲解所属问题与分配的问题不同'))
    if value.get('reader_title') and not value['reader_title'].rstrip().endswith('？'):
        findings.append(issue('question_title','/reader_title','阅读标题需要以中文问号结束'))
    known={r['id'] for r in resources};expected={r['id'] for r in resources if question_id in r.get('question_ids',[])}
    mapped=contract.mappings(value,expected)
    missing=expected-{r for g in value['explanation'] for r in g['resource_ids']}
    planned=expected-{r for item in value['plan']['items'] for r in item['resource_ids']}
    if missing or planned:
        findings.append(issue('material_coverage','/explanation','本问材料需要同时进入规划和实际讲解：'+', '.join(sorted(missing|planned)),'/explanation',resource_ids=sorted(missing|planned)))
    unknown={rid for g in value['explanation'] for rid in g['resource_ids']}|{rid for p in value['plan']['items'] for rid in p['resource_ids']}
    if unknown-known:findings.append(issue('source_exists','/explanation','材料引用不存在：'+', '.join(sorted(unknown-known)),resource_ids=sorted(unknown-known)))
    plan_ids=[item['id'] for item in value['plan']['items']]
    used={pid for g in value['explanation'] for pid in g['plan_ids']}
    if set(plan_ids)!=used:findings.append(issue('plan_coverage','/explanation','讲解组需要覆盖本问全部规划，且只引用实际存在的规划'))
    for field,ids in [('plan/items',plan_ids),('explanation',[g['id'] for g in value['explanation']])]:
        if len(ids)!=len(set(ids)):findings.append(issue('unique_id','/'+field,'同一问题内部的条目 ID 重复'))
    for i,g in enumerate(value['explanation']):
        if not g['title_question'].rstrip().endswith(('？','?')):
            findings.append(issue('question_title',f'/explanation/{i}/title_question','讲解标题需要以问号结束'))
        for j,media in enumerate(g['resources']):
            if media['kind']=='image' and Path(media['asset']).suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.gif','.svg','.bmp'}:
                findings.append(issue('media_contract',f'/explanation/{i}/resources/{j}','图片字段指向了非图片文件，需要按文件元数据或真实素材类型展示'))
            for message in media_contract.check(media,root,known|{r['source_id'] for r in resources}):
                findings.append(issue('media_contract',f'/explanation/{i}/resources/{j}',message))
    quiz=value['appendix']['quiz']
    for kind,expected_count in quota.items():
        if sum(q['kind']==kind for q in quiz)!=expected_count:
            findings.append(issue('quiz_quota','/appendix/quiz',f'{kind} 应生成 {expected_count} 题'))
    for i,q in enumerate(quiz):
        if q['kind']=='single_choice' and not 0<=q['answer']<len(q['options']):
            findings.append(issue('quiz_answer',f'/appendix/quiz/{i}/answer','答案索引超出实际选项'))
    for i,term in enumerate(value['appendix']['terms']):
        # 旧读本没有例外位时继续按旧数据读取；新写作响应带位后，名称问题进入现有统一修复
        if any(field in term for field in term_names.CASE_FLAGS):
            for finding in term_names.term_name_findings(term):
                path=pointer(('appendix','terms',i,*finding['field'].split('.')))
                findings.append(issue('term_name',path,finding['message']))
        a=(term['abbreviation'] or '').strip();english=term['english']
        normalize=lambda s:re.sub(r'\s+','',s).casefold()
        if a and normalize(a)==normalize(english):
            findings.append(issue('term_name',f'/appendix/terms/{i}/abbreviation','缩写需要与英文全称不同'))
    identifiers=known|{r['source_id']for r in resources}
    identifiers={rid for rid in identifiers if len(rid)>=6}
    token=re.compile(r'(?<![A-Za-z0-9_.:/-])[A-Za-z0-9_-]+(?:[.:/][A-Za-z0-9_-]+)*(?![A-Za-z0-9_.:/-])')
    special=[rid for rid in identifiers if not re.fullmatch(r'[A-Za-z0-9_-]+(?:[.:/][A-Za-z0-9_-]+)*',rid)]
    special_pattern=re.compile('|'.join(re.escape(rid)for rid in sorted(special,key=len,reverse=True)))if special else None
    for parts,text in prose(value):
        leaked=set(token.findall(text))&identifiers
        if special_pattern:leaked.update(special_pattern.findall(text))
        if leaked:findings.append(issue('source_id_prose',pointer(parts),'作者说明需要引用材料内容，不直接展示内部来源编号：'+', '.join(sorted(leaked)),resource_ids=sorted(leaked)))
        if not text.strip():findings.append(issue('nonempty',pointer(parts),'作者说明为空'))
        for match in LINT.finditer(text):
            findings.append(issue('lint',pointer(parts),'需要调整作者句式或内部编号：'+match.group(),pointer(parts)))
    return findings


def translation_findings(value,resources):
    shape=[issue('schema',pointer(e.path),e.message) for e in Draft202012Validator(contract.schema('c-translation')).iter_errors(value)]
    if shape:return shape
    rows=value.get('translations',[]);by_id={r['resource_id']:r for r in rows}
    expected={r['id']:r for r in resources if r['kind']=='text'};result=[]
    for rid,r in expected.items():
        row=by_id.get(rid)
        from reader_repairs import is_chinese
        if not row or not str(row.get('chinese','')).strip() or (not is_chinese(r['original']) and not str(row.get('english','')).strip()):
            result.append(issue('translation_complete','/translations','缺少译文：'+rid,resource_ids=[rid]));continue
        if r['original'] not in {row['chinese'],row['english']}:
            result.append(issue('translation_original','/translations','原句发生变化：'+rid,resource_ids=[rid]))
    duplicates=[k for k,c in Counter(r['resource_id'] for r in rows).items() if c>1]
    if duplicates:result.append(issue('translation_unique','/translations','译文 ID 重复：'+', '.join(duplicates),resource_ids=duplicates))
    if set(by_id)-set(expected):result.append(issue('translation_source','/translations','译文引用了未登记的原句：'+', '.join(sorted(set(by_id)-set(expected))),resource_ids=sorted(set(by_id)-set(expected))))
    return result
