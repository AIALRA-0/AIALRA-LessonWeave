"""同一轮修复按执行容量分批，重复材料在请求内只传一份"""
import copy
import os
import lean_contract as contract
import media_contract


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
