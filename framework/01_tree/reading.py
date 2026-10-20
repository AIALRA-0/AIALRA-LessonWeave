import re

from tree_model import walk

NUMBER=re.compile(r'^\s*\((\d+)\)\s+(.+)',re.S)

def item_number(node):
    if node['type']=='list' and len(node['children'])==1:return item_number(node['children'][0])
    if node['type']=='list_item' and node['children']:return item_number(node['children'][0])
    if node['type']!='paragraph':return None
    return NUMBER.match(node['content'].get('raw_text',node['content'].get('text','')))

def normalize_lists(node,builder):
    changes=0
    for child in node['children']:changes+=normalize_lists(child,builder)
    children=node['children'];result=[];index=0
    while index<len(children):
        first=item_number(children[index]);end=index+1
        if first:
            while end<len(children):
                match=item_number(children[end])
                if not match or int(match[1])!=int(first[1])+end-index:break
                a=children[index]['source'][0];b=children[end]['source'][0]
                if a['kind']=='pdf' and b['kind']=='pdf' and a.get('page')==b.get('page') and abs(a['bbox'][0]-b['bbox'][0])>15:break
                end+=1
        if first and end-index>=2:
            items=[]
            for child in children[index:end]:
                match=item_number(child);number=int(match[1])
                if child['type']=='list':child=child['children'][0]
                if child['type']=='list_item':item=child;paragraph=item['children'][0]
                else:
                    paragraph=child;item=builder.node('list_item',{},child['source'],[paragraph])
                paragraph['content'].setdefault('raw_text',paragraph['content']['text']);paragraph['content']['text']=match[2]
                item['content'].update(marker=f'({number})',ordinal=number)
                items.append(item)
            result.append(builder.node('list',{'ordered':True,'start':int(first[1]),'items':len(items)},[source for item in items for source in item['source']],items))
            changes+=1;index=end
        else:result.append(children[index]);index+=1
    node['children']=result
    return changes

def build_relations(tree):
    nodes=list(walk(tree));targets={}
    for node in nodes:
        if node['type'] in ('figure','table'):
            name=node['content'].get('name','')
            match=re.match(r'^((?:Extended Data\s+)?(?:Fig(?:ure)?\.?|Table)\s*\d+)',name,re.I)
            if match:targets[re.sub(r'[.\s]','',match[1]).lower()]=node['id']
    relations=[]
    for node in nodes:
        if node['type']!='paragraph':continue
        for match in re.finditer(r'\b(?:Extended Data\s+)?(?:Fig(?:ure)?\.?|Table)\s*\d+',node['content'].get('text',''),re.I):
            target=targets.get(re.sub(r'[.\s]','',match[0]).lower())
            if target:relations.append({'from':node['id'],'to':target,'type':'refers_to','source':node['source']})
    return relations

def reading_context(document,node_id):
    nodes={node['id']:node for node in walk(document['tree'])}
    if node_id not in nodes:raise ValueError('树中没有这个节点')
    parents={child['id']:parent for parent in nodes.values() for child in parent['children']}
    anchor=nodes[node_id]
    while anchor['id'] in parents and parents[anchor['id']]['type'] in ('list_item','list','figure','table'):
        anchor=parents[anchor['id']]
    parent=parents.get(anchor['id']);chosen=[]
    if document['format']=='code' and anchor['type'] in ('repository','subsystem'):
        chosen=[anchor]
        for child in anchor['children']:
            if child['content'].get('view')=='files':continue
            chosen.append(child)
            if child['type']=='section':chosen.extend(child['children'])
    elif parent and parent['type'] in ('section','document','webpage'):
        siblings=parent['children'];index=siblings.index(anchor)
        # 编号识别有波动时，也把相邻的完整段落组交给后续分析
        start=max(0,index-4);end=min(len(siblings),index+5)
        for sibling in siblings[start:end]:
            if sibling['type'] not in ('section','directory'):chosen.extend(walk(sibling))
    else:chosen.extend(walk(anchor))
    related=[]
    ids={node['id'] for node in chosen}
    for edge in document.get('relations',[]):
        if edge['from'] in ids and edge['to'] in nodes:related.extend(walk(nodes[edge['to']]))
    unique={node['id']:node for node in chosen+related}
    required=[]
    for node in unique.values():
        if node['type']=='list' and node['content'].get('ordered'):
            required.append({'type':'list_items','node_id':node['id'],'count':len(node['children']),'markers':[child['content'].get('marker') for child in node['children']]})
    numbered={int(match[1]):node['id'] for node in unique.values() if node['type']=='paragraph' and (match:=item_number(node))}
    numbers=sorted(numbered)
    if len(numbers)>=2 and numbers==list(range(1,numbers[-1]+1)) and not any(rule['count']>=len(numbers) for rule in required):
        required=[rule for rule in required if rule['count']>=len(numbers)]
        required.append({'type':'list_items','node_ids':[numbered[number] for number in numbers],'count':len(numbers),'markers':[f'({number})' for number in numbers],'evidence':'numbered_context'})
    fragments=[]
    for node in unique.values():
        content=dict(node['content'])
        if node['type'] in ('module','class','function','method') and node['children']:content.pop('text',None)
        fragments.append({**node,'content':content,'children':[]})
    return {'selected':node_id,'anchor':anchor['id'],'nodes':fragments,
            'structure':{node['id']:[child['id'] for child in node['children'] if child['id'] in unique] for node in unique.values()},'requirements':required,
            'description':'完整读取这些段落、列表与关联图表，节点片段已去重，层级关系见 structure，涉及公式、图像或识别疑点时按来源回查原材料'}
