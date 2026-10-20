"""读取历史信息点字段，当前规划不再提供逐事实清点执行器"""
import copy
import re


def walk(node):
    yield node
    for child in node.get('children', []):
        yield from walk(child)


def records(tree):
    """材料树已决定解析范围，这里保留实际内容与定位，不执行仓库中的代码"""
    return [{'source_id': node['id'], 'type': node['type'], 'content': node['content'],
             'source': node['source'],
             'evidence_kind': 'material_index' if node.get('children') and node['type'] in {'document','webpage','repository','directory','section','list','list_item'} else 'content',
             'child_source_ids': [child['id'] for child in walk(node) if child is not node]}
            for node in walk(tree['tree']) if node.get('content')]


def validate(candidate, rows, conversions=None, findings=None):
    findings = findings if findings is not None else []
    allowed = {row['source_id']: row for row in rows}
    ids = set()
    linked = set()
    for point in candidate['points']:
        if point['id'] in ids or not point['description'].strip() or not point['checks']:
            findings.append('信息点需要唯一编号、实际内容与具体检查项：' + point['id'])
        ids.add(point['id'])
        if not point['source_ids'] or set(point['source_ids']) - allowed.keys():
            findings.append('信息点需要对应当前批次的真实材料：' + point['id'])
        if not point['source_refs']:
            findings.append('信息点需要原句或原图区域：' + point['id'])
        ref_sources = set()
        for ref in point['source_refs']:
            source = allowed.get(ref['source_id'])
            if not source or ref['source_id'] not in point['source_ids']:
                findings.append('信息点引文需要来自它实际引用的材料：' + point['id'])
                continue
            def texts(node):
                if isinstance(node, str):
                    yield node
                elif isinstance(node, dict):
                    for child in node.values():
                        yield from texts(child)
                elif isinstance(node, list):
                    for child in node:
                        yield from texts(child)
            def locate(text):
                if not ref['quote'].strip():return None
                pattern=r'\s+'.join(re.escape(word) for word in re.split(r'\s+',ref['quote'].strip()))
                return re.search(pattern,text)
            matches=[text[match.start():match.end()] for text in texts(source['content']) if (match:=locate(text))]
            if not matches and source.get('child_source_ids'):
                children=[(key,text[match.start():match.end()])
                          for key in source.get('child_source_ids',[]) if key in allowed
                          for text in texts(allowed[key]['content']) if (match:=locate(text))]
                if len(set(children))==1:
                    child,actual=children[0]
                    if conversions is not None:
                        conversions.append({'point_id':point['id'],'container_id':ref['source_id'],'actual_source_id':child,'reason':'引文逐字存在于唯一实际子项，脚本保留容器对应并把原句定位到子项'})
                    ref['source_id']=child
                    locators=allowed[child].get('source',[])
                    if allowed[child].get('type') not in {'image','figure'} and locators and locators[0].get('dom_path'):
                        ref['region']=locators[0]['dom_path']
                    if child not in point['source_ids']:point['source_ids'].append(child)
                    matches=[actual]
            if not matches:
                findings.append('信息点 '+point['id']+' 在 '+ref['source_id']+' 的引文缺少实际对应：'+repr(ref['quote'][:100]))
                continue
            if ref['quote']!=matches[0] and conversions is not None:
                conversions.append({'point_id':point['id'],'actual_source_id':ref['source_id'],'reason':'仅按原材料恢复引文中的实际空白与换行'})
            ref['quote']=matches[0]
            ref_sources.add(ref['source_id'])
        inherited = {key for key in point['source_ids']
                     if key in allowed and allowed[key].get('child_source_ids')
                     and set(allowed[key].get('child_source_ids', [])) & ref_sources}
        if set(point['source_ids']) - ref_sources - inherited:
            findings.append(point['id'] + ' 的部分引用来源尚缺实际引文或区域记录')
        linked.update(point['source_ids'])
    if set(allowed) - linked:
        findings.append('仍有材料没有对应的信息点：' + ', '.join(sorted(set(allowed) - linked)))
    return candidate


