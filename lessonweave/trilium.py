"""使用 Trilium 的笔记、分支和附件保存学习项目，账号和数据库由宿主管理"""
from pathlib import Path
import hashlib
import html
import json
import mimetypes
import os
import re
from urllib.parse import urljoin,urlsplit
import requests
from .storage import read,save


def configured():
    return bool(os.environ.get('LESSONWEAVE_TRILIUM_URL') and os.environ.get('LESSONWEAVE_TRILIUM_TOKEN') and os.environ.get('LESSONWEAVE_TRILIUM_ROOT'))


def public_note_url(client,note_id,public_url):
    parsed=urlsplit(public_url)
    if parsed.scheme not in {'https','http'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('ReadWeave 的网页入口需要填写完整 HTTP 或 HTTPS 地址')
    path=[];cursor=note_id
    while cursor:
        if cursor in path or len(path)>=64 or not re.fullmatch(r'[A-Za-z0-9_]+',cursor):
            raise ValueError('对应笔记的目录关系需要重新核对')
        path.insert(0,cursor)
        if cursor=='root':
            return public_url.rstrip('/')+'/#'+'/'.join(path)
        note=client.call('GET','notes/'+cursor)
        if not note.get('parentNoteIds'):
            break
        cursor=note['parentNoteIds'][0]
    raise ValueError('对应笔记尚未连接到 ReadWeave 根目录')


def reading_link(project,root,section=None):
    public_url=os.environ.get('LESSONWEAVE_TRILIUM_PUBLIC_URL')
    if not public_url or not configured():
        raise ValueError('正式 ReadWeave 尚未关联，导入完成后可直达对应笔记')
    mapping=read(Path(root)/'runtime/trilium/current.json',{})
    from .readweave import current,configured as shared_configured
    shared=current(root) if shared_configured()else{}
    if section and shared.get('sections',{}).get(section):
        return public_note_url(Client(),shared['sections'][section],public_url)
    target=mapping.get('sections',{}).get(section) if section else project.get('native_note_id') or mapping.get('project_note_id')
    if not target:
        raise ValueError('当前小节尚未导入 ReadWeave，已保留生成结果')
    return public_note_url(Client(),target,public_url)


class Client:
    def __init__(self):
        self.url=os.environ['LESSONWEAVE_TRILIUM_URL'].rstrip('/')
        self.root=os.environ['LESSONWEAVE_TRILIUM_ROOT']
        self.trash=os.environ['LESSONWEAVE_TRILIUM_TRASH']
        self.session=requests.Session()
        self.session.headers['Authorization']=os.environ['LESSONWEAVE_TRILIUM_TOKEN']

    def call(self,method,path,payload=None,content=None,mime=None):
        headers={'Content-Type':mime} if mime else {}
        if isinstance(content,bytes):
            headers['Content-Transfer-Encoding']='binary'
        response=self.session.request(method,self.url+'/etapi/'+path,json=payload,data=content,headers=headers,timeout=90)
        if response.status_code>=400:
            raise ValueError('Trilium '+method+' '+path.split('?')[0]+' 返回 '+str(response.status_code))
        return response.json() if response.content and 'json' in response.headers.get('Content-Type','') else response.content

    def identity(self,key):
        return 'lw'+hashlib.sha256((self.root+':'+key).encode()).hexdigest()[:24]

    def note(self,key,parent,title,kind='book',content='',mime=None):
        nid=self.identity(key)
        response=self.session.get(self.url+'/etapi/notes/'+nid,timeout=30)
        if response.status_code==404:
            payload={'noteId':nid,'parentNoteId':parent,'title':title,'type':kind,'content':content}
            if mime:
                payload['mime']=mime
            return self.call('POST','create-note',payload)['note']
        if not response.ok:
            raise ValueError('读取 Trilium 笔记时返回 '+str(response.status_code))
        note=response.json()
        if parent not in note.get('parentNoteIds',[]):
            raise ValueError('已有 Trilium 笔记位于其他位置，保留它并核对导入记录')
        return note

    def move(self,nid,previous,parent):
        note=self.call('GET','notes/'+nid)
        if parent not in note['parentNoteIds']:
            self.call('POST','branches',{'noteId':nid,'parentNoteId':parent})
        # 先创建目标分支，再删除原分支，笔记 ID 和其他克隆位置继续保留
        for branch_id in note['parentBranchIds']:
            branch=self.call('GET','branches/'+branch_id)
            if branch['parentNoteId']==previous and previous!=parent:
                self.call('DELETE','branches/'+branch_id)

    def attribute(self,note,name,value,kind='label'):
        existing=next((item for item in note.get('attributes',[]) if item['name']==name and item['type']==kind),None)
        if existing and existing['value']==value:
            return
        if existing:
            self.call('PATCH','attributes/'+existing['attributeId'],{'value':value})
        else:
            self.call('POST','attributes',{'noteId':note['noteId'],'type':kind,'name':name,'value':value})

    def attachment(self,owner,title,content,mime=None,attachment_id=None):
        mime=mime or mimetypes.guess_type(title)[0] or 'application/octet-stream'
        aid=attachment_id
        if not aid:
            aid=self.call('POST','attachments',{'ownerId':owner,'role':'file','mime':mime,'title':title})['attachmentId']
        if content is not None:
            if mime!=(mimetypes.guess_type(title)[0] or 'application/octet-stream'):
                self.call('PATCH','attachments/'+aid,{'mime':mime})
            # ETAPI 的二进制正文使用 octet-stream 传输，阅读时的 MIME 由附件元数据保留
            self.call('PUT','attachments/'+aid+'/content',content=content,mime='application/octet-stream')
        return aid


def native_parent(store,key):
    if key=='root':
        return os.environ['LESSONWEAVE_TRILIUM_ROOT']
    folder=next((row for row in store.folders() if row['id']==key and not row['deleted']),None)
    if not folder or not folder.get('native_note_id'):
        raise ValueError('这个文件夹还没有对应的 Trilium 笔记')
    return folder['native_note_id']


def ensure_project(store,key,name,folder_id):
    if not configured():
        return None
    return Client().note('project:'+key,native_parent(store,folder_id),name)['noteId']


def create_folder(store,name,parent):
    import uuid
    key=uuid.uuid4().hex
    nid=Client().note('folder:'+key,native_parent(store,parent),name)['noteId'] if configured() else None
    return store.create_folder(name,parent,native_note_id=nid,key=key)


def change(store,kind,key,action,values):
    row=store.validate_library_change(kind,key,action,values)
    if kind=='project' and action=='trash':
        from .readweave import library_action
        library_action(row,action)
    if configured() and row.get('native_note_id'):
        client=Client();nid=row['native_note_id']
        previous_key=row['parent_id' if kind=='folder' else 'folder_id']
        previous=native_parent(store,previous_key) if not row['deleted'] else client.trash
        if action=='rename':
            # 网站文件名和原生文章名分别保存，身份、正文与笔记继续共享
            pass
        elif action=='move':
            client.move(nid,previous,native_parent(store,values['parent_id']))
        elif action=='trash':
            client.move(nid,previous,client.trash)
        elif action=='restore':
            parent=next((f for f in store.folders() if f['id']==previous_key and not f['deleted']),None)
            client.move(nid,client.trash,native_parent(store,parent['id'] if parent else 'root'))
    if kind=='project' and action=='restore':
        from .readweave import library_action
        library_action(row,action)
    return store.library_change(kind,key,action,values)


def plain(value):
    if isinstance(value,str):
        return value
    if isinstance(value,dict):
        return plain(value.get('text',value.get('code','')))
    if isinstance(value,list):
        return ' '.join(plain(item) for item in value)
    return str(value) if value is not None else ''


def block_html(block):
    if isinstance(block,str):
        return '<p>'+html.escape(block)+'</p>'
    kind=block.get('kind')
    if kind=='image':
        return '<figure><img data-resource="'+html.escape(block.get('asset',''))+'"><figcaption>'+html.escape(block.get('caption',''))+'</figcaption></figure>'
    if kind=='list':
        return '<ul>'+''.join('<li>'+html.escape(str(item))+'</li>' for item in block.get('items',[]))+'</ul>'
    if kind=='table':
        return '<table>'+''.join('<tr>'+''.join('<td>'+html.escape(str(cell))+'</td>' for cell in row)+'</tr>' for row in block.get('rows',[]))+'</table>'
    if kind=='code':
        return '<pre><code>'+html.escape(block.get('code',block.get('text','')))+'</code></pre>'
    return '<p data-lw-block="'+html.escape(block.get('id',''))+'">'+html.escape(block.get('text',''))+'</p>'


def svg_preview(content):
    # SVG 原件按文本保存，宿主中的图片使用静态预览，避免材料脚本取得笔记页面权限
    import fitz
    with fitz.open(stream=content,filetype='svg') as document:
        page=document[0]
        scale=min(2,2400/max(page.rect.width,page.rect.height,1))
        return page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=True).tobytes('png')


def resolve_resource_html(text,resources):
    def replace(match):
        name=html.unescape(match.group(1)).lstrip('/')
        target=resources.get(name)
        return 'src="'+html.escape(target,quote=True)+'"' if target else match.group(0)
    return re.sub(r'data-resource="([^"]*)"',replace,text)


def section_html(doc,resources):
    questions={row['question_id']:row['text'] for row in doc['core_questions']}
    text='<h2>承上启下</h2>'
    for key in ['opening_title','opening','opening_forward']:
        value=doc.get(key,'')
        text+=block_html(value) if isinstance(value,dict) else '<p>'+html.escape(value)+'</p>'
    text+='<h2>核心问题</h2><ul>'+''.join('<li>'+html.escape(row['text'])+'</li>' for row in doc['core_questions'])+'</ul><h2>内容讲解</h2>'
    for unit in doc['units']:
        text+='<h3>'+html.escape(unit['title'])+'</h3>'
        text+=''.join(block_html(block) for block in [unit['problem'],*unit['explanation'],unit['synthesis']])
    text+='<h2>内容总结</h2>'+''.join('<p>'+html.escape(questions[row['question_id']])+'</p>'+block_html(row['answer']) for row in doc['summary'])
    text+='<h2>易错点</h2>'
    for pitfall in doc.get('pitfalls',[]):
        text+='<h3>'+html.escape(pitfall['premise']+pitfall['question'])+'</h3>'
        body=pitfall.get('body',[])
        text+=''.join(block_html(block) for block in (body if isinstance(body,list) else [body]))
    text+='<h2>问答</h2>'
    for quiz in doc.get('quiz',[]):
        text+='<h3>'+html.escape(plain(quiz['prompt']))+'</h3>'
        if quiz.get('options'):
            text+='<ol>'+''.join('<li>'+html.escape(plain(option))+'</li>' for option in quiz['options'])+'</ol>'
        answer=quiz.get('reference_answer') or (quiz.get('options') or [''])[quiz.get('answer',0)]
        text+='<details><summary>核对答案</summary><p>'+html.escape(str(answer))+'</p>'+block_html(quiz['explanation'])+'</details>'
    text+='<h2>术语表</h2>'
    for term in doc.get('glossary',[]):
        text+='<h3>'+html.escape(term['display'])+'</h3><p>'+html.escape(term['definition'])+'</p>'+''.join('<p>'+html.escape(item)+'</p>' for item in term.get('explanation',[]))
    return resolve_resource_html(text,resources)


def sync_project(store,project,root,package_manifest=None):
    """在原生笔记树中追加版本，原有版本与用户笔记继续保留"""
    from .package import export_package
    from .progress import begin,tick
    client=Client();pid=project['id']
    project_nid=project.get('native_note_id') or ensure_project(store,pid,project['name'],project.get('folder_id','root'))
    with store.connect() as db:
        db.execute('UPDATE projects SET native_note_id=? WHERE id=?',(project_nid,pid))
    manifest=package_manifest if package_manifest is not None else export_package(root)
    version=manifest['version']
    owner=client.note('edition:'+pid+':'+version,project_nid,'版本 '+version)['noteId']
    mapping_path=root/'runtime/trilium'/version/'mapping.json'
    mapping=read(mapping_path,{'project_note_id':project_nid,'edition_note_id':owner,'version':version,'attachments':{},'uploaded':[],'sections':{}})
    save(mapping_path,mapping)
    paths=manifest['files']
    begin(root,'保存到 Trilium 笔记树',['attachment:'+path for path in paths],reused=['attachment:'+path for path in mapping['uploaded']])
    for path in paths:
        if path not in mapping['attachments']:
            mapping['attachments'][path]=client.attachment(owner,path,None)
            save(mapping_path,mapping)
    resources={path:'/api/attachments/'+aid+'/open' for path,aid in mapping['attachments'].items()}
    previews=mapping.setdefault('previews',{})
    for path in paths:
        if Path(path).suffix.lower()=='.svg':
            client.call('PATCH','attachments/'+mapping['attachments'][path],{'mime':'text/plain'})
            if path not in previews:
                previews[path]=client.attachment(owner,'.lessonweave-preview/'+path+'.png',svg_preview((root/path).read_bytes()),'image/png')
                save(mapping_path,mapping)
            resources[path]='/api/attachments/'+previews[path]+'/open'
    for path in paths:
        if path in mapping['uploaded']:
            continue
        tick(root,'attachment:'+path,'running')
        content=(root/path).read_bytes()
        mime=mimetypes.guess_type(path)[0] or 'application/octet-stream'
        if Path(path).suffix.lower()=='.svg':
            mime='text/plain'
        if Path(path).suffix.lower() in {'.html','.htm'}:
            parent=Path(path).parent
            def replace(match):
                raw=match.group(2)
                target=raw.lstrip('/') if raw.startswith('/') else (parent/raw).as_posix()
                return match.group(1)+resources.get(target,raw)+match.group(3)
            content=re.sub(r'''((?:src|href)=["'])([^"']+)(["'])''',replace,content.decode('utf-8')).encode()
            if path.startswith('05_writing/source-location/'):
                policy='<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'none\'; img-src \'self\' data:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
                content=content.replace(b'<head>',('<head>'+policy).encode(),1)
            else:
                # 原始网页的字节继续保存在阅读包中，附件入口按文本查看，避免执行材料中的脚本
                mime='text/plain'
        client.attachment(owner,path,content,mime=mime,attachment_id=mapping['attachments'][path])
        mapping['uploaded'].append(path);save(mapping_path,mapping);tick(root,'attachment:'+path,'completed')
    book=read(root/'05_writing/preview-book.json',read(root/'05_writing/book.json'))
    for stage,label,filename in [('01_tree','01 材料树','tree.json'),('02_questions','02 问题树','questions.json'),('03_chapters','03 标题树','chapters.json'),('04_transitions','04 承上启下','transitions.json')]:
        client.note(pid+':'+version+':'+stage,owner,label,'code',(root/stage/filename).read_text('utf-8'),'application/json')
    for chapter in book['chapters']:
        chapter_nid=client.note(pid+':'+version+':'+chapter['id'],owner,chapter['title'])['noteId']
        for section in chapter['sections']:
            doc=read(root/section['path'])
            note=client.note(pid+':'+version+':'+section['id'],chapter_nid,section['number']+' '+section['title'],'text',section_html(doc,resources),'text/html')
            mapping['sections'][section['id']]=note['noteId']
            client.attribute(note,'readOnly','')
            client.attribute(note,'lessonweaveSectionId',section['id'])
    notes=client.note('user-notes:'+pid,project_nid,'我的学习笔记')['noteId']
    module_path=Path(__file__).resolve().parents[1]/'integrations/readweave/reader-component.js'
    script_template=(module_path.parent/'trilium-render.js').read_text('utf-8')
    ui_version=hashlib.sha256(module_path.read_bytes()+script_template.encode()).hexdigest()[:16]
    module=mapping.get('module_attachment') if mapping.get('ui_version')==ui_version else None
    module=module or client.attachment(owner,'lessonweave-reader-'+ui_version+'.js',module_path.read_bytes(),'application/javascript')
    mapping.update(resources=resources,notes_note_id=notes,reader_module='/api/attachments/'+module+'/open',module_attachment=module,ui_version=ui_version,validated=book['validation']['passed'])
    source=script_template.replace('/*LESSONWEAVE_CONFIG*/null',json.dumps({'projectId':pid,'base':'/__lessonweave/'+pid,'moduleTitle':'lessonweave-reader-'+ui_version+'.js','preview':not (root/'05_writing/book.json').is_file()},ensure_ascii=False))
    script=client.note(pid+':'+version+':renderer-script:'+ui_version,owner,'LessonWeave 阅读组件','code',source,'application/javascript;env=frontend')
    client.attribute(script,'lessonweaveEdition',owner,'relation')
    client.attribute(script,'lessonweaveUserNotes',notes,'relation')
    render=client.note(pid+':'+version+':renderer:'+ui_version,owner,'对照原材料阅读','render','')
    if not any(a['name']=='renderNote' for a in render.get('attributes',[])):
        client.call('POST','attributes',{'noteId':render['noteId'],'type':'relation','name':'renderNote','value':script['noteId']})
    mapping['render_note_id']=render['noteId']
    save(mapping_path,mapping)
    save(root/'runtime/trilium/current.json',mapping)
    from .readweave import publish_project
    publish_project(store,project,root,mapping)
    return mapping
