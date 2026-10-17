import mimetypes
import re
from collections import Counter,defaultdict
from importlib.metadata import version
from pathlib import Path,PurePosixPath

from tree_sitter_language_pack import get_parser
from markdown_it import MarkdownIt

from tree_code import LANGUAGES,code_source,file_source,module_ports


def ast_nodes(node):
    yield node
    for child in node.named_children:yield from ast_nodes(child)

def symbol_name(node,raw):
    named=node.child_by_field_name('name')
    if named is not None:return raw[named.start_byte:named.end_byte].decode('utf-8',errors='replace')
    header=node.named_children[0] if node.named_children else node
    text=raw[header.start_byte:header.end_byte].decode('utf-8',errors='replace')
    match=re.search(r'\b(?:module|interface|package|program)\s+(?:(?:automatic|static)\s+)?(\w+)',text)
    return match[1] if match else text.splitlines()[0][:80]

def readme_description(root,file):
    path=root/file['source'][0]['path'];raw=path.read_bytes();text=raw.decode('utf-8',errors='replace')
    tokens=MarkdownIt('commonmark').parse(text);lines=text.splitlines(keepends=True);offsets=[0]
    for line in lines:offsets.append(offsets[-1]+len(line.encode('utf-8')))
    parts=[];sources=[]
    for index,token in enumerate(tokens):
        if token.type!='paragraph_open' or token.level!=0:continue
        inline=tokens[index+1];value=''.join(child.content for child in inline.children or [] if child.type not in ('image','html_inline'))
        if len(value.strip())<15 or value.lstrip().startswith(('http://','https://')):continue
        parts.append(value.strip());start,end=token.map;sources.append(code_source(root,path,raw,offsets[start],offsets[end]))
        if len(parts)>=2:break
    return '\n\n'.join(parts)[:900],sources


def parse_architecture(builder,root,source):
    archive=root/source['entry'];repository=root/source['repository'];records=source['files']
    heads={PurePosixPath(record['archive_member']).parts[0] for record in records}
    name=next(iter(heads)).removesuffix('-main').removesuffix('-master') if len(heads)==1 else Path(source['material']).stem
    project=builder.node('repository',{'name':name,'revision':source.get('revision',''),
        'description':'先读项目概览、子系统与模块关系，需要看实现时再展开原文件'},[file_source(root,archive)])
    inventory=builder.node('section',{'text':'原始文件与附件','view':'files'},[file_source(root,archive)])
    folders={repository:inventory};files={};raws={};syntax={};counts=Counter();parsers={}
    for record in sorted(records,key=lambda item:(item['original_path'].casefold(),item['original_path'])):
        path=root/record['path'];original=record['original_path'];suffix=path.suffix.lower();role='source' if suffix in LANGUAGES else 'document' if suffix in ('.md','.txt') else 'attachment' if suffix in ('.pdf','.zip') else 'resource'
        parents=[];parent=path.parent
        while parent not in folders:parents.append(parent);parent=parent.parent
        for directory in reversed(parents):
            folder=builder.node('directory',{'name':directory.name},[file_source(root,archive)]);folders[directory.parent]['children'].append(folder);folders[directory]=folder
        content={'name':PurePosixPath(original).name,'path':original,'archive_member':record['archive_member'],'local_path':path.relative_to(repository).as_posix(),'bytes':record['bytes'],'mime':mimetypes.guess_type(path.name)[0] or 'application/octet-stream','role':role,'detail_state':'deferred' if role in ('source','document') else 'retained'}
        content['description']='需要看实现时点击展开语法结构' if role=='source' else '需要阅读时点击展开文档章节' if role=='document' else '保留完整原文件，当前没有展开内部正文'
        file=builder.node('file',content,[file_source(root,path)]);folders[path.parent]['children'].append(file);files[original]=file;counts[role]+=1
        if role=='source':
            raw=path.read_bytes();language=LANGUAGES[suffix]
            if language not in parsers:parsers[language]=get_parser(language)
            tree=parsers[language].parse(raw);syntax[original]=(tree,language);raws[original]=raw
            if tree.root_node.has_error:
                diagnostics=[]
                def inspect(node):
                    if node.type=='ERROR' or node.is_missing:
                        diagnostics.append(code_source(root,path,raw,node.start_byte,node.end_byte));return
                    for child in node.children:
                        if child.has_error or child.is_missing:inspect(child)
                inspect(tree.root_node)
                file['content']['syntax_diagnostics']=diagnostics;counts['syntax_error_files']+=1
                file['children'].append(builder.node('unknown',{'reason':'语法库在这些位置未完整识别源码，架构扫描与按需展开仍保留原文件'},diagnostics or file['source']))
    readme=next((name for name in files if name.lower()=='readme.md'),None)
    if readme:
        path=root/files[readme]['source'][0]['path'];raw=path.read_bytes();end=min(len(raw),6000)
        text=raw.decode('utf-8',errors='replace');headings=re.findall(r'^#{1,4}\s+(.+)$',text,re.M)[:12]
        overview_text='README 列出的主要入口：\n'+'\n'.join('• '+heading for heading in headings)
        overview=builder.node('section',{'text':'这个项目怎样组织'},[code_source(root,path,raw,0,end)],
            [builder.node('paragraph',{'text':overview_text},[code_source(root,path,raw,0,end)])])
        project['children'].append(overview)
    subsystem_names=sorted({name.split('/')[0] for name in files if '/rtl/' in name.lower()})
    subsystems={};design_groups={};run_groups={}
    for name in subsystem_names:
        evidence=next((files[p] for p in files if p.startswith(name+'/') and p.lower().endswith('readme.md')),None)
        location=evidence['source'] if evidence else next(file['source'] for p,file in files.items() if p.startswith(name+'/'))
        description='';description_sources=[]
        if evidence:
            description,description_sources=readme_description(root,evidence)
        if description_sources:location=description_sources
        subsystem=builder.node('subsystem',{'name':name,'description':description or '从本目录中的设计模块、验证脚本和说明文件逐层阅读','evidence_file':evidence['id'] if evidence else None},location)
        design=builder.node('section',{'text':'有哪些模块，接口怎样连接'},location);runs=builder.node('section',{'text':'验证和执行从哪些文件开始'},location)
        subsystem['children']=[design,runs];project['children'].append(subsystem);subsystems[name]=subsystem;design_groups[name]=design;run_groups[name]=runs
    symbols=[];pending=[];relations=[]
    for original,(tree,language) in syntax.items():
        file=files[original];raw=raws[original];path=root/file['source'][0]['path'];subsystem=original.split('/')[0]
        if subsystem not in subsystems:continue
        if language=='tcl':
            actions=[]
            for node in tree.root_node.named_children:
                if node.type=='command':
                    text=raw[node.start_byte:node.end_byte].decode('utf-8',errors='replace')
                    if re.match(r'\s*(?:analyze|elaborate|clock|reset|prove|check|source|set_top|read_hdl)\b',text):actions.append({'text':text,'source':code_source(root,path,raw,node.start_byte,node.end_byte)})
            if actions:
                entry=builder.node('entrypoint',{'name':original,'file_ref':file['id'],'actions':actions,'description':'按脚本中实际出现的读入、顶层设置、时钟复位与验证命令列出入口'},file['source']);run_groups[subsystem]['children'].append(entry)
                relations.append({'from':entry['id'],'to':file['id'],'type':'implemented_by','source':file['source']})
            continue
        for node in ast_nodes(tree.root_node):
            if node.type not in ('module_declaration','interface_declaration','package_declaration','program_declaration'):continue
            name=symbol_name(node,raw);ports=module_ports(node,root,path,raw)
            module=builder.node('module',{'name':name,'file_ref':file['id'],'path':original,'ports':ports,'has_syntax_errors':tree.root_node.has_error,'description':'接口与实例关系来自语法树，实现内容可通过对应文件按需展开'},[code_source(root,path,raw,node.start_byte,node.end_byte)])
            design_groups[subsystem]['children'].append(module);symbols.append((name,subsystem,original,module))
            relations.append({'from':module['id'],'to':file['id'],'type':'implemented_by','source':module['source']})
            for child in ast_nodes(node):
                if child.type=='module_instantiation' and child.named_children:
                    target_node=child.named_children[0];target=raw[target_node.start_byte:target_node.end_byte].decode('utf-8',errors='replace')
                    pending.append((module,target,subsystem,original,code_source(root,path,raw,child.start_byte,child.end_byte)))
    unresolved=0
    for module,target,subsystem,original,location in pending:
        matches=[item for item in symbols if item[0]==target and item[1]==subsystem and item[2]==original]
        if not matches:matches=[item for item in symbols if item[0]==target and item[1]==subsystem]
        if len(matches)==1:relations.append({'from':module['id'],'to':matches[0][3]['id'],'type':'instantiates','source':[location]})
        else:
            module['content'].setdefault('unresolved_references',[]).append({'name':target,'reason':'没有找到唯一的同子系统定义，保留名称与位置供后续回查','source':location});unresolved+=1
    project['content']['description']=f'仓库中识别到 {len(subsystems)} 个包含 RTL 实现的子系统，先阅读子系统、模块接口和验证入口，需要具体实现时再打开原文件'
    project['children'].append(inventory)
    return {'tree':project,'title':project['content']['name'],'pages':[],'relations':relations,
        'summary':{'files':len(files),**dict(counts),'subsystems':len(subsystems),'architecture_modules':len(symbols),'unresolved_references':unresolved,'expanded_files':0},
        'notes':['架构入口按设计目录、README、模块接口和实例关系组织，全部原文件仍可在文件清单中查找','首次只扫描架构，不生成每条声明和注释，点击具体文件后才展开语法或文档结构','附件与资源保留原文件，未展开的文件会明确显示状态'],
        'adaptations':[{'rule':'architecture-first','reason':'先显示项目概览、子系统、模块协作和验证入口，源码与文档按需展开'},{'rule':'scoped-references','reason':'优先匹配同文件及同子系统中的模块定义，重复定义与外部依赖保留为未解析引用'}],
        'engine':{'name':'Tree-sitter','version':version('tree-sitter-language-pack'),'profile':'architecture-first-v2'}}
