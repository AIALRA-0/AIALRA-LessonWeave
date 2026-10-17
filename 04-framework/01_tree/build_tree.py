import copy
import json
from pathlib import Path

import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'00_source'))
from acquire import complete_web_assets
from content_checks import source_inventory,attach_missing_content,append_docling_units
from architecture import parse_architecture
from reading import build_relations,normalize_lists
from tree_code import LANGUAGES,file_source,markdown_tree,syntax_tree
from tree_document import parse_document
from tree_model import TreeBuilder,save_result,walk
from tree_web import parse_webpage


def next_output(root):
    history=root/'01_tree/history';history.mkdir(exist_ok=True)
    numbers=[int(path.name.split('-')[1]) for path in history.glob('run-*') if path.is_dir()]
    output=history/f'run-{max(numbers,default=0)+1:04}';output.mkdir();return output

def build_tree(root,payload,source):
    root=Path(root).resolve();output=next_output(root)
    if source['status']!='acquired':raise ValueError('原材料尚未取得，请先完成 00_source')
    (output/'input.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'source.json').write_text(json.dumps(source,ensure_ascii=False,indent=2),encoding='utf-8')
    kind=payload['kind'];builder=TreeBuilder()
    result={'kind':kind,'material':payload['material'],'format':{'file':'pdf','url':'html','repository':'code'}[kind],
        'run':output.name,'status':'parsed','original':file_source(root,root/source['entry'])['url'],'relations':[]}
    if kind=='url':
        source=complete_web_assets(root,source)
        (output/'source.json').write_text(json.dumps(source,ensure_ascii=False,indent=2),encoding='utf-8')
    inventory=source_inventory(root,result,source)
    if kind=='file':result.update(parse_document(builder,root,root/source['entry'],output))
    elif kind=='url':result.update(parse_webpage(builder,root,source,output))
    else:result.update(parse_architecture(builder,root,source))
    append_docling_units(root,result,inventory,output)
    attach_missing_content(root,result,inventory,builder)
    inventory_path=output/'content-inventory.json'
    inventory_path.write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
    result['coverage']={'profile':'content-tree-v1','inventory':inventory_path.relative_to(root).as_posix(),
                        'report':(output/'coverage.json').relative_to(root).as_posix()}
    fixes=normalize_lists(result['tree'],builder)
    if kind!='repository':result['relations']=build_relations(result['tree'])
    result['reading_policy']={'unit':'context_group','classification':'hint','source_review':['figure','table','equation','unknown'],
        'description':'读取完整段落组与关联图表，节点分类作为定位线索，关键数值、公式和识别疑点回查原材料'}
    result['adaptations'].append({'rule':'numbered-list-context','reason':'合并相邻且编号连续的段落与列表项，保留原编号、完整文字和每项来源','count':fixes})
    result['summary']['relations']=len(result['relations'])
    return save_result(root,result,output)

def expand_file(root,document,node_id):
    root=Path(root);document=copy.deepcopy(document);nodes=list(walk(document['tree']))
    file=next((node for node in nodes if node['id']==node_id and node['type']=='file'),None)
    if not file or file['content']['role'] not in ('source','document'):raise ValueError('这个节点不是可展开的源码或文档文件')
    if file['content'].get('detail_state')=='expanded':return document
    builder=TreeBuilder();builder.count=max(int(node['id'][1:]) for node in nodes)
    path=root/file['source'][0]['path'];raw=path.read_bytes();suffix=path.suffix.lower()
    if suffix in LANGUAGES:
        file['children'],diagnostics=syntax_tree(builder,root,path,raw,LANGUAGES[suffix],{})
        if diagnostics:file['content']['syntax_diagnostics']=diagnostics
    elif suffix=='.md':file['children']=markdown_tree(builder,root,path,raw)
    else:
        from tree_code import code_source
        file['children']=[builder.node('code_block',{'text':raw.decode('utf-8',errors='replace'),'language':'text'},[code_source(root,path,raw,0,len(raw))])]
    for node in walk(file):
        if node['type']=='module':
            node['content'].update(file_ref=file['id'],path=file['content']['path'])
            previous=next((other for other in nodes if other is not node and other['type']=='module' and other['content'].get('name')==node['content'].get('name') and other['content'].get('path')==file['content']['path']),None)
            if previous:node['content']['unresolved_references']=previous['content'].get('unresolved_references',[])
    file['content']['detail_state']='expanded';file['content']['description']='已经按需展开，完整原文件继续保留'
    document['summary']['expanded_files']=sum(node['type']=='file' and node['content'].get('detail_state')=='expanded' for node in walk(document['tree']))
    output=next_output(root);document['run']=output.name
    for name in ('input.json','source.json'):
        (output/name).write_bytes((root/'00_source'/name).read_bytes())
    previous=root/document['coverage']['inventory']
    target=output/'content-inventory.json';target.write_bytes(previous.read_bytes())
    document['coverage']={**document['coverage'],'inventory':target.relative_to(root).as_posix(),
                          'report':(output/'coverage.json').relative_to(root).as_posix()}
    return save_result(root,document,output)
