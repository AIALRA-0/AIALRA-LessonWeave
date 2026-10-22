"""同一轮修复按执行容量分批，重复材料在请求内只传一份"""
import copy
import os
import lean_contract as contract
import media_contract


def format_document_terms(document, include_legacy=False):
    """先整理可确认的名称；拆解和来源问题继续交给既有统一修复记录。"""
    candidate = copy.deepcopy(document)
    appendix = candidate.get('appendix') if isinstance(candidate, dict) else None
    terms = appendix.get('terms') if isinstance(appendix, dict) else None
    if not isinstance(terms, list):
        return candidate, [], []

    import book_terminology
    selected = [index for index, term in enumerate(terms)
                if include_legacy or (isinstance(term, dict) and any(
                    field in term for field in book_terminology.CASE_FLAGS))]
    if not selected:
        return candidate, [], []
    formatted_terms = copy.deepcopy(terms)
    changes, errors = [], []
    for index in selected:
        term = terms[index]
        try:
            formatted, term_changes = book_terminology.format_term_metadata([term])
            formatted_terms[index] = formatted[0]
            changes.extend(dict(change, term_index=index) for change in term_changes)
            for finding in book_terminology.term_name_findings(formatted[0]):
                term_id = term.get('id') if isinstance(term, dict) else None
                errors.append(f"{term_id or 'term[' + str(index) + ']'}: {finding['field']}: {finding['message']}")
        except Exception as error:
            errors.append(str(error))
    appendix['terms'] = formatted_terms
    return candidate, changes, errors

def pack(tasks,rules):
    pool={};prepared=[]
    for task in tasks:
        item=copy.deepcopy(task);refs=[]
        for row in item.pop('materials',[]):
            material={k:v for k,v in row.items() if k!='question_ids'}
            key=material.get('id') or material.get('source_id','file')+'.file_role'
            base=key;index=1
            while key in pool and pool[key]!=material:index+=1;key=base+'#'+str(index)
            pool[key]=material;refs.append(key)
        if refs:item['material_refs']=list(dict.fromkeys(refs))
        prepared.append(item)
    needs_unit=any(t.get('schema_name')=='c-unit' or any(f['path'] in ['/explanation','/plan/items'] for f in t['fragments']) for t in tasks)
    schemas={'c-unit':contract.schema('c-unit')} if needs_unit else {}
    if not needs_unit and any('/resources' in f['path'] for t in tasks for f in t['fragments']):
        schemas['media-resource']=media_contract.schema('media-resource')
    if any(any(f['path'].startswith('/appendix/quiz') for f in t['fragments']) for t in tasks):
        schemas['quiz']=contract.schema('c-unit')['properties']['appendix']['properties']['quiz']
    if any(t['document'].endswith('bridges.json')for t in tasks):schemas['c-bridges']=contract.schema('c-bridges')
    return {'task':'批量修复脚本已经指出的具体问题，只返回受影响字段的改动','rules':rules,
        'schemas':schemas,'material_pool':pool,'tasks':prepared}


def split(tasks,rules,input_bytes=None,change_bytes=None):
    # 容量目标只决定请求怎样装包，完整任务和材料继续保留，同一文档只进入一个批次
    input_bytes=input_bytes or int(os.environ.get('LESSONWEAVE_REPAIR_BYTES','450000'))
    change_bytes=change_bytes or int(os.environ.get('LESSONWEAVE_REPAIR_CHANGE_BYTES','60000'))
    groups=[];current=[];changes=0
    for task in tasks:
        estimate=sum(len(contract.dumps(f.get('current')).encode('utf-8')) for f in task['fragments'])
        if task.get('schema_name')=='c-unit':estimate=max(estimate,change_bytes)
        candidate=current+[task]
        size=len(contract.dumps(pack(candidate,rules)).encode('utf-8'))
        if current and (size>input_bytes or changes+estimate>change_bytes):
            groups.append(current);current=[];changes=0
        current.append(task);changes+=estimate
    if current:groups.append(current)
    return groups
