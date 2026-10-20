"""脚本在独立显示记录中纠正附件类型与双语对应，正文及历史检查保持原样"""
import collections,copy,json,mimetypes,re
from pathlib import Path

SYSTEM_NAMES={'.ds_store','thumbs.db','desktop.ini','.localized'}
def file_role(path):
    p=Path(str(path).replace('\\','/'))
    if p.name.casefold() in SYSTEM_NAMES or '__MACOSX' in p.parts or p.name.startswith('._'):return 'system_metadata'
    mime=mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
    if mime.startswith('image/'):return 'image'
    if mime.startswith(('audio/','video/')):return mime.split('/')[0]
    return 'attachment_inventory'

def is_chinese(text):
    # 先排除代码、公式和链接，英文正文中偶尔出现中文专名时仍需要翻译正文
    visible=re.sub(r'```[\s\S]*?```|`[^`\n]+`|\$[^$\n]+\$|https?://\S+|\(#[^)]+\)','',text)
    chinese=len(re.findall('[\u4e00-\u9fff]',visible))
    words=len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*",visible))
    return chinese>0 and (chinese>=words or words<3)

def bilingual(originals,rows):
    by_id={r['resource_id']:r for r in rows};candidates=collections.defaultdict(list)
    for rid,original in originals.items():
        row=by_id.get(rid,{})
        if original in (row.get('chinese'),row.get('english')):candidates[original].append(row)
    repairs={};stats=collections.Counter()
    for rid,original in originals.items():
        old=by_id.get(rid,{})
        if old.get('chinese') and old.get('english') and original in (old['chinese'],old['english']):continue
        chinese=is_chinese(original);target='english' if chinese else 'chinese'
        usable=[r for r in candidates[original] if r.get(target) and r.get(target)!=original]
        options={r[target] for r in usable}
        if len(options)==1:
            row=copy.deepcopy(usable[0]);row['resource_id']=rid
            status='reused_exact_source';stats['reused_exact_source']+=1
        else:
            row={'resource_id':rid,'chinese':original if chinese else '', 'english':'' if chinese else original}
            status='english_on_demand' if chinese else 'chinese_needs_review';stats[status]+=1
        # 始终由脚本填写不可变原句，候选复用保持来源可追溯
        row['chinese' if chinese else 'english']=original
        repairs[rid]={'original':original,'row':row,'status':status,'reused_from':[r['resource_id']for r in usable] if len(options)==1 else [],'previous':old,'previous_translation_status':'needs_review' if old and status!='reused_exact_source' else None,'needs_review':status=='chinese_needs_review','semantic_review':'not_run'}
    return repairs,dict(stats)

def attachment(value,root):
    raw=value.get('asset') or value.get('file',{}).get('local_path') or value.get('file',{}).get('path')
    if not raw:return None
    raw=str(raw).replace('\\','/');relative=raw.lstrip('/');actual=root/relative
    if not actual.is_file():
        # 先按来源保留的完整相对后缀定位，只有唯一文件时才修正路径
        choices=[p for p in (root/'00_source').rglob(Path(relative).name) if p.is_file() and p.as_posix().endswith('/'+relative)]
        if len(choices)!=1:return {'status':'path_needs_review','original_asset':raw}
        actual=choices[0]
    asset='/'+actual.relative_to(root).as_posix();role=file_role(actual)
    with actual.open('rb') as f:head=f.read(12)
    mime='application/pdf' if head.startswith(b'%PDF-') else 'application/zip' if head.startswith(b'PK\x03\x04') else mimetypes.guess_type(actual.name)[0]or'application/octet-stream'
    projected={k:copy.deepcopy(value[k])for k in ['id','caption','source_refs','guide']if k in value}
    projected.update(kind='table',headers=['文件','类型','大小（字节）'],rows=[[actual.name,mime,actual.stat().st_size]])
    return {'status':'resolved','role':role,'asset':asset,'original_asset':raw,'projection':projected,'content_explained':False,'file_exists':True}

def build(root):
    root=Path(root);writing=root/'05_writing';load=lambda p,default:json.loads(p.read_text('utf8'))if p.is_file()else default
    originals=load(writing/'translation-originals.json',{})
    rows=load(writing/'translations.json',{'translations':[]})['translations']
    # 上次已经按同一原句补好的译文可继续复用，旧的未核对候选不会覆盖新结果
    prior=load(writing/'reader-repairs.json',{}).get('translations',{})
    repairs,stats=bilingual(originals,rows)
    for rid,item in prior.items():
        if item.get('original')==originals.get(rid) and item.get('status') in {'translated_chinese','reused_exact_source'} and item.get('row',{}).get('chinese'):
            if rid in repairs:repairs[rid]=copy.deepcopy(item)
    stats=dict(collections.Counter(item['status']for item in repairs.values()))
    attachments={}
    def visit(value):
        if isinstance(value,list):
            for item in value:visit(item)
        elif isinstance(value,dict):
            if value.get('kind')=='file':
                fixed=attachment(value,root)
                if fixed:attachments[value['id']]=fixed
            for item in value.values():
                if isinstance(item,(dict,list)):visit(item)
    for path in (writing/'work/sections').glob('*/unit-*.json'):visit(load(path,{}))
    result={'version':1,'translations':repairs,'attachments':attachments,'stats':{'translations':stats,'attachments':dict(collections.Counter(r.get('role',r['status'])for r in attachments.values()))},'model_calls':0,'content_files_changed':False}
    output=writing/'reader-repairs.json';output.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    pointer=writing/'reader-whitespace.json';overlay=load(pointer,{'replacements':{}});overlay['reader_repairs_path']='/05_writing/reader-repairs.json';pointer.write_text(json.dumps(overlay,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    return result
