import mimetypes
import re
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from markdown_it import MarkdownIt
from tree_sitter_language_pack import get_parser


LANGUAGES = {'.sv':'systemverilog','.v':'systemverilog','.vh':'systemverilog','.vs':'systemverilog',
             '.tcl':'tcl','.py':'python','.c':'c','.h':'c','.cpp':'cpp','.hpp':'cpp','.js':'javascript','.ts':'typescript','.sh':'bash'}


def file_source(root, path):
    relative = path.relative_to(root).as_posix()
    return {'kind':'file','path':relative,'url':'/' + quote(relative)}


def code_source(root, path, raw, start, end):
    return {**file_source(root,path),'kind':'code','start_byte':start,'end_byte':end,
            'start_line':raw[:start].count(b'\n')+1,'end_line':raw[:max(start,end-1)].count(b'\n')+1}


def markdown_tree(builder, root, path, raw):
    text = raw.decode('utf-8')
    parser = MarkdownIt('commonmark').enable('table')
    tokens = parser.parse(text)
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1]+len(line.encode('utf-8')))
    result, stack, lists = [], [], []
    def append(node):
        (lists[-1]['children'] if lists else stack[-1][1]['children'] if stack else result).append(node)
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.map is not None:
            start, end = token.map
            source = [code_source(root,path,raw,offsets[start],offsets[end])]
        else:
            source = [file_source(root,path)]
        if token.type == 'heading_open':
            label = tokens[index+1].content
            level = int(token.tag[1:])
            while stack and stack[-1][0] >= level:
                stack.pop()
            section = builder.node('section',{'text':label},source)
            append(section)
            stack.append((level,section))
            index += 3
            continue
        if token.type in ('bullet_list_open','ordered_list_open','list_item_open'):
            node = builder.node('list_item' if token.type=='list_item_open' else 'list',{},source)
            append(node)
            lists.append(node)
        elif token.type in ('bullet_list_close','ordered_list_close','list_item_close'):
            lists.pop()
        elif token.type == 'paragraph_open':
            inline = tokens[index+1]
            contents = ''.join(child.content for child in inline.children or [] if child.type not in ('image','html_inline'))
            if contents.strip():
                append(builder.node('paragraph',{'text':contents},source))
            for image in inline.children or []:
                if image.type == 'image':
                    address = image.attrGet('src') or ''
                    if address.startswith(('https://','http://','data:')):
                        import sys
                        sys.path.insert(0,str(root/'00_source'))
                        from acquire import localize_asset
                        target=localize_asset(root,address)
                    else:target = (path.parent / __import__('urllib.parse',fromlist=['unquote']).unquote(address)).resolve()
                    content = {'text':image.content,'original_url':address}
                    if target.is_file() and target.is_relative_to(root):
                        content['asset'] = file_source(root,target)['url']
                    if 'asset' not in content:raise ValueError('Markdown 引用的图片没有找到本地内容：'+address)
                    append(builder.node('figure',{},source,[builder.node('image',content,source)]))
        elif token.type in ('fence','code_block'):
            append(builder.node('code_block',{'text':token.content or '\n','language':token.info or 'text'},source))
        elif token.type == 'table_open':
            append(builder.node('table',{'text':''.join(lines[start:end]),'html':parser.render(''.join(lines[start:end]))},source))
            depth=1
            while depth and index+1 < len(tokens):
                index+=1
                depth += (tokens[index].type=='table_open') - (tokens[index].type=='table_close')
        elif token.type == 'html_block' and token.content.strip():
            append(builder.node('code_block',{'text':token.content,'language':'html'},source))
        index+=1
    return result


def syntax_kind(node, raw):
    kind=node.type
    if kind=='ERROR' or node.is_missing:
        return 'unknown'
    if 'comment' in kind:
        return 'comment'
    if kind in ('module_declaration','interface_declaration','package_declaration','program_declaration'):
        return 'module'
    if kind in ('class_definition','class_declaration'):
        return 'class'
    if kind in ('function_definition','function_declaration','task_declaration','procedure'):
        return 'function'
    if 'import' in kind or kind in ('include_directive','package_import_declaration'):
        return 'import'
    if 'declaration' in kind or kind=='command':
        return 'declaration'
    return None


def syntax_tree(builder, root, path, raw, language, parsers):
    if language not in parsers:
        parsers[language]=get_parser(language)
    parser = parsers[language]
    tree = parser.parse(raw)
    def select(parent):
        items=[]
        for child in parent.children:
            if not child.is_named and not child.is_missing:
                continue
            if syntax_kind(child,raw):
                items.append(child)
            else:
                items.extend(select(child))
        return items
    def pieces(parent, start, end, parent_kind='file'):
        output=[]
        cursor=start
        for item in select(parent):
            if item.start_byte < start or item.end_byte > end:
                continue
            if item.start_byte > cursor and raw[cursor:item.start_byte].strip():
                output.append(builder.node('code_block',{'text':raw[cursor:item.start_byte].decode('utf-8',errors='replace'),'language':language},[code_source(root,path,raw,cursor,item.start_byte)]))
            kind=syntax_kind(item,raw)
            if kind=='function' and parent_kind=='class':
                kind='method'
            name_node=item.child_by_field_name('name')
            text=raw[item.start_byte:item.end_byte].decode('utf-8',errors='replace')
            content={'text':text or '\n','language':language,'syntax_type':item.type}
            if item.has_error and kind not in ('module','class','function','method','unknown'):
                content['intended_type']=kind
                kind='unknown'
            if name_node is not None:
                content['name']=raw[name_node.start_byte:name_node.end_byte].decode('utf-8',errors='replace')
            elif kind in ('module','class','function','method'):
                match=re.search(r'\b(?:module|interface|package|class|function|task|def)\s+(\w+)',text)
                content['name']=match.group(1) if match else text.splitlines()[0][:100]
            if kind=='module':
                content.update(ports=module_ports(item,root,path,raw),unresolved_references=[],has_syntax_errors=item.has_error)
            if kind=='unknown':
                content['reason']='当前语法规则未完整识别这段源码，可能涉及工具方言或源文件语法，原始字节与位置已保留'
            children=pieces(item,item.start_byte,item.end_byte,kind) if kind in ('module','class','function','method') else []
            output.append(builder.node(kind,content,[code_source(root,path,raw,item.start_byte,item.end_byte)],children))
            cursor=max(cursor,item.end_byte)
        if cursor < end and raw[cursor:end].strip():
            output.append(builder.node('code_block',{'text':raw[cursor:end].decode('utf-8',errors='replace'),'language':language},[code_source(root,path,raw,cursor,end)]))
        return output
    nodes=pieces(tree.root_node,0,len(raw))
    diagnostics=[]
    def inspect(node):
        if node.type=='ERROR' or node.is_missing:
            diagnostics.append({'syntax_type':node.type,'missing':node.is_missing,
                                **code_source(root,path,raw,node.start_byte,node.end_byte)})
            return
        for child in node.children:
            if child.has_error or child.is_missing:
                inspect(child)
    if tree.root_node.has_error:
        inspect(tree.root_node)
    return nodes,diagnostics



def module_ports(node,root,path,raw):
    ports=[]
    def visit(item):
        if item.type=='ansi_port_declaration':
            name=item.child_by_field_name('port_name')
            ports.append({'name':raw[name.start_byte:name.end_byte].decode('utf-8',errors='replace') if name else '',
                          'declaration':raw[item.start_byte:item.end_byte].decode('utf-8',errors='replace'),
                          'source':code_source(root,path,raw,item.start_byte,item.end_byte)})
            return
        for child in item.named_children:visit(child)
    visit(node)
    return ports
