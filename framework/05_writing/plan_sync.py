"""实际讲解已经覆盖材料后，脚本把明确的执行对应关系填回本问规划"""


def align(value,resources):
    by_id={r['id']:r['source_id'] for r in resources};known=set(by_id)
    expected={r['id'] for r in resources if value.get('question_id') in r.get('question_ids',[])}
    groups=value.get('explanation',[]);actual={rid for g in groups for rid in g.get('resource_ids',[])}
    # 正文缺少任何应讲材料或仍引用未知材料时，保留问题，不能用改规划来隐藏正文缺漏
    if not expected<=actual or not actual<=known:return []
    planned={rid for item in value.get('plan',{}).get('items',[]) for rid in item['resource_ids']}
    missing=expected-planned
    if not missing and planned<=known:return []
    changes=[]
    for item in value.get('plan',{}).get('items',[]):
        linked=list(dict.fromkeys(rid for g in groups if item['id'] in g.get('plan_ids',[]) for rid in g['resource_ids']))
        if not linked:continue
        sources={by_id[rid] for rid in linked};old=item['resource_ids']
        invalid=[rid for rid in old if rid not in known and rid.split('.',1)[0] in sources]
        updated=list(dict.fromkeys([rid for rid in old if rid not in invalid]+[rid for rid in linked if rid in missing]))
        if updated!=old:
            item['resource_ids']=updated
            changes.append({'plan':item['id'],'action':'按已关联讲解组同步规划引用','removed_invalid':invalid,
                'added_from_actual_groups':[rid for rid in updated if rid not in old]})
    return changes
