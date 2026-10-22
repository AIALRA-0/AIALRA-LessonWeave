"""让网站读写正式 ReadWeave，生成快照和用户改稿分别保留"""
from pathlib import Path
from urllib.parse import quote,urlsplit
import hashlib,html,json,os,re,threading,time,uuid
import requests
from .storage import read,save

_project_locks={}
_lock=threading.Lock()
_library_poll={}


def configured():
    return os.environ.get('LESSONWEAVE_READWEAVE_BRIDGE')=='1' and bool(os.environ.get('LESSONWEAVE_READWEAVE_URL') or os.environ.get('LESSONWEAVE_TRILIUM_URL'))


class UpstreamError(ValueError):
    def __init__(self,status,payload):
        self.status=status;self.payload=payload
        super().__init__(payload.get('message') or payload.get('error') or '共享内容暂时没有读回来，请保留当前输入后重试')


class Client:
    def __init__(self):
        self.url=(os.environ.get('LESSONWEAVE_READWEAVE_URL') or os.environ['LESSONWEAVE_TRILIUM_URL']).rstrip('/')
        self.session=requests.Session()
        self.session.headers['Authorization']=os.environ.get('LESSONWEAVE_READWEAVE_TOKEN') or os.environ['LESSONWEAVE_TRILIUM_TOKEN']

    def call(self,method,path,payload=None):
        if not re.match(r'^(?:lessonweave|readweave)/',path) or '..' in urlsplit(path).path.split('/'):
            raise ValueError('共享接口路径不正确')
        body=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8')if payload is not None else None
        attempts=3 if method=='GET'or path=='lessonweave/publications/import'or isinstance(payload,dict)and payload.get('operationId')else 1
        for attempt in range(attempts):
            try:
                response=self.session.request(method,self.url+'/api/'+path,data=body,headers={'Content-Type':'application/json'}if body is not None else None,timeout=(60,120))
                break
            except requests.RequestException as error:
                if attempt+1==attempts:raise UpstreamError(503,{'error':'共享笔记库暂时无法连接，当前草稿和已生成内容仍然保留'}) from error
                time.sleep(0.5*(attempt+1))
        try:data=response.json()
        except ValueError:data={'error':'ReadWeave 返回的内容暂时无法读取'}
        if not response.ok:raise UpstreamError(response.status_code,data if isinstance(data,dict) else {'error':'共享请求没有完成'})
        return data


def proxy(method,path,payload=None):
    if not configured():raise UpstreamError(503,{'error':'共享笔记库尚未配置，已有正文和笔记仍然保留'})
    return Client().call(method,path,payload)


def current(root):
    return read(Path(root)/'runtime/readweave/current.json',{})


def publication(store,project,root):
    mapping=current(root)
    if not mapping:raise UpstreamError(404,{'error':'这份读本还没有导入共享笔记库'})
    value=proxy('GET','lessonweave/publications/'+quote(mapping['edition_id'],safe=''))
    return dict(value,section_articles=mapping.get('sections',{}),translation_articles=mapping.get('translations',{}),original_articles=mapping.get('originals',{}),project_id=project['id'])


def library_action(project,action):
    mapping=current(project['path'])
    if not configured()or not mapping.get('edition_id')or action not in {'trash','restore'}:return
    path='lessonweave/publications/'+quote(mapping['edition_id'],safe='')
    proxy('DELETE'if action=='trash'else'POST',path+('/restore'if action=='restore'else''),{'operationId':uuid.uuid4().hex})


def reconcile_library(store):
    """回读共享库的删除状态，网站不会用旧快照重新创建已删文章"""
    if not configured():return
    key=str(store.root);now=time.monotonic()
    with _lock:
        if now-_library_poll.get(key,0)<2:return
        _library_poll[key]=now
    checkpoint=read(store.root/'readweave-library-cursor.json',{'cursor':0})
    try:response=proxy('GET','lessonweave/changes?after='+str(checkpoint['cursor']))
    except UpstreamError:return
    decisions={}
    for change in response.get('changes',[]):
        if change['kind']in {'publication-deleted','publication-restored'}:decisions[change['editionId']]=change['kind']=='publication-deleted'
    if decisions:
        with store.connect()as db:
            for project in store.projects(include_deleted=True):
                edition=current(project['path']).get('edition_id')
                if edition in decisions:db.execute('UPDATE projects SET deleted=?,trash_batch=? WHERE id=?',(int(decisions[edition]),'readweave'if decisions[edition]else None,project['id']))
    save(store.root/'readweave-library-cursor.json',{'cursor':response.get('nextCursor',checkpoint['cursor'])})


def _term(term):
    body=term.get('definition','')+'\n\n'+'\n\n'.join(term.get('explanation',[]))
    return {'key':term.get('id') or term['display'],'title':term['display'],'body':body,
            'termIdentity':{'abbreviation':term.get('abbreviation') or None,'chineseName':term.get('chinese_full_name') or term.get('chinese') or None,'englishName':term.get('english_full_name') or term.get('english') or None},
            'sourceExcerpt':term.get('display','')}


def import_batches(rows,target_bytes=8*1024*1024):
    """按传输大小分批，不截断单篇，也不限制材料总量"""
    batch=[];size=0
    for row in rows:
        amount=len(json.dumps(row,ensure_ascii=False,separators=(',',':')).encode('utf-8'))
        source_only=row.get('kind')=='source'and not row.get('definitions')and all(item.get('kind')=='source'and not item.get('definitions')for item in batch)
        if batch and(size+amount>target_bytes or len(batch)>=(64 if source_only else 8)):
            yield batch;batch=[];size=0
        batch.append(row);size+=amount
    if batch:yield batch


def publish_project(store,project,root,trilium_mapping):
    """按稳定身份追加所有文本，重试只补没导入的内容，不覆盖改稿或恢复删除项"""
    if not configured():return {}
    from .shared_html import article_html
    root=Path(root);version=trilium_mapping['version'];client=Client()
    import_key=project['id']+':'+version
    mapping=current(root)
    if mapping.get('import_key')!=import_key:
        mapping={'import_key':import_key,'version':version,'sections':{},'translations':{},'originals':{},'source_articles':{},'notes':{},'imported':[]}
    book=read(root/'05_writing/preview-book.json',read(root/'05_writing/book.json',{}))
    rows=[];section_keys={};translation_keys={};original_keys={};sources={}
    resources=trilium_mapping.get('resources',{})
    for chapter in book.get('chapters',[]):
        for section in chapter['sections']:
            sid=section['id'];doc=read(root/section['path'])
            key='explanation:'+sid;section_keys[key]=sid
            rows.append({'key':key,'title':section['number']+' '+section['title'],'kind':'explanation',
                         'body':article_html(doc,resources),'definitions':[_term(t)for t in doc.get('glossary',[])],
                         'source':{'section_id':sid,'path':section['path'],'document':doc}})
            pack_path=doc.get('grounding',{}).get('source_pack_path')
            if pack_path:
                pack=read(root/pack_path.lstrip('/'),{})
                paragraphs=[];originals=[]
                for source in pack.get('sources',[]):
                    for sentence in source.get('sentences',[]):
                        original=sentence.get('original') or sentence.get('english')
                        if original:originals.append('<p data-lw-sentence="'+html.escape(sentence['id'])+'">'+html.escape(str(original))+'</p>')
                        translated=sentence.get('translation') or sentence.get('zh')
                        if translated:
                            paragraphs.append('<p data-lw-sentence="'+html.escape(sentence['id'])+'">'+html.escape(str(translated))+'</p>')
                    if not source.get('sentences'):
                        for fragment in source.get('file_fragments',[]):
                            text=fragment.get('text',fragment.get('content',''))
                            if text:originals.append('<pre><code>'+html.escape(text)+'</code></pre>')
                        for text in source.get('original_texts',[]):
                            if isinstance(text,str) and text:originals.append('<p>'+html.escape(text)+'</p>')
                if originals:
                    key='original:'+sid;original_keys[key]=sid
                    rows.append({'key':key,'title':section['number']+' 原文','kind':'original','body':'\n'.join(originals),'source':{'section_id':sid,'path':pack_path,'source_pack':pack}})
                if paragraphs:
                    key='translation:'+sid;translation_keys[key]=sid
                    rows.append({'key':key,'title':section['number']+' 中文译文','kind':'translation','body':'\n'.join(paragraphs),'source':{'section_id':sid,'path':pack_path,'source_pack':pack}})
    # 原文文件与说明、译文分别登记，二进制原件继续使用附件，不把二进制猜成文本
    manifest=read(root/'05_writing/reading-package.json',{})
    for name in manifest.get('files',[]):
        if not name.startswith('00_source/materials/'):continue
        path=root/name
        try:
            content=path.read_text('utf-8-sig')
        except (UnicodeError,OSError):continue
        if '\x00'in content:continue
        key='source:'+name;sources[key]=name
        body='<pre><code>'+html.escape(content)+'</code></pre>'
        rows.append({'key':key,'title':path.name,'kind':'source','body':body,'source':{'path':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}})
    from .progress import begin,tick
    begin(root,'把正文、原文、译文和术语同步到 ReadWeave',['shared:'+r['key']for r in rows],reused=['shared:'+key for key in mapping['imported']])
    pending=[r for r in rows if r['key']not in mapping['imported']]
    receipts=read(root/'runtime/readweave/import-receipts.json',{'batches':[]})
    for batch in import_batches(pending):
        for row in batch:tick(root,'shared:'+row['key'],'running')
        payload={'importKey':import_key,'title':book.get('title',project['name']),'parentNoteId':trilium_mapping['edition_note_id'],'articles':batch}
        if mapping.get('edition_id'):payload['editionId']=mapping['edition_id']
        started=time.monotonic()
        result=client.call('POST','lessonweave/publications/import',payload)
        receipts['batches'].append({'articles':len(batch),'definitions':sum(len(row.get('definitions',[]))for row in batch),'bytes':len(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8')),'seconds':round(time.monotonic()-started,3),'importStats':result.get('importStats',{})})
        save(root/'runtime/readweave/import-receipts.json',receipts)
        mapping['edition_id']=result['editionId']
        for row in result.get('articles',[]):
            key=row['key']
            if key in section_keys:mapping['sections'][section_keys[key]]=row['articleId']
            if key in translation_keys:mapping['translations'][translation_keys[key]]=row['articleId']
            if key in original_keys:mapping.setdefault('originals',{})[original_keys[key]]=row['articleId']
            if key in sources:mapping['source_articles'][sources[key]]=row['articleId']
        mapping['imported']=list(dict.fromkeys([*mapping['imported'],*(r['key']for r in batch)]))
        save(root/'runtime/readweave/current.json',mapping)
        for row in batch:tick(root,'shared:'+row['key'],'completed')
    # 第一次没有待导入项时，也按正式库读回，避免把本地记录当作成功回执
    if mapping.get('edition_id'):client.call('GET','lessonweave/publications/'+quote(mapping['edition_id'],safe=''))
    return mapping


def note(store,project,key,value=None,*,details=False,expected_revision=None,expected_link_revision=None):
    """旧笔记先保留，已迁入的笔记每次直接读正式库，不复制回生成正文"""
    root=Path(project['path'])
    with _lock:guard=_project_locks.setdefault(project['id'],threading.RLock())
    with guard:
        mapping=current(root);sid=key.split(':',1)[0];article=mapping.get('sections',{}).get(sid)
        def result(text,entry=None):
            return {'value':text,'revision':entry['revision']if entry else 0,'linkRevision':entry.get('linkRevision',1)if entry else 0}if details else text
        if not configured() or not article:return result(store.note(project['id'],key,value))
        anchor='lwn'+hashlib.sha256(key.encode()).hexdigest()[:24]
        entries=proxy('GET','readweave/articles/'+quote(article,safe='')+'/anchors/'+anchor).get('entries',[])
        entry=next((item for item in entries if item.get('contentType')=='note'),None)
        if value is None:
            if entry:return result(entry.get('displayBody') if entry.get('displayBody') is not None else entry.get('body',''),entry)
            # 已迁入后被原生删除的笔记返回空，不把旧备份再次导入
            return result('' if key in mapping.get('notes',{}) else store.note(project['id'],key))
        if expected_revision is not None and expected_revision!=(entry['revision']if entry else 0)or expected_link_revision is not None and expected_link_revision!=(entry.get('linkRevision',1)if entry else 0):
            raise UpstreamError(409,{'error':'这份笔记已在另一处修改，当前输入已保留，请先对照最新内容'})
        if entry:
            if value:
                entry=proxy('PATCH','readweave/links/'+entry['linkId'],{'articleId':article,'mode':'global','title':entry['title'],'body':value,'expectedRevision':entry['revision'],'expectedLinkRevision':entry.get('linkRevision',1)}).get('entry',entry)
            else:
                proxy('DELETE','readweave/links/'+entry['linkId']+'?expectedLinkRevision='+str(entry.get('linkRevision',1)))
        elif value:
            article_row=proxy('GET','lessonweave/articles/'+quote(article,safe=''))
            entry=proxy('POST','readweave/entries',{'articleId':article,'anchorId':anchor,'anchorType':'paragraph','kind':'question','contentType':'note','origin':'manual','sourceExcerpt':article_row['title'],'title':'学习笔记','body':value})['entry']
        if entry:mapping.setdefault('notes',{})[key]=entry['linkId'];save(root/'runtime/readweave/current.json',mapping)
        return result(value,entry if value else None)
