import os
import json
import re
import shutil
import zipfile
import time
from pathlib import Path,PurePosixPath
from urllib.parse import urljoin

import requests


def read_json(path):return json.loads(path.read_text(encoding='utf-8'))
def write_json(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def extract_repository(archive_path,destination,root):
    destination.mkdir(parents=True,exist_ok=True)
    mappings={};occupied={};files=[]
    with zipfile.ZipFile(archive_path) as archive:
        entries=[entry for entry in archive.infolist() if not entry.is_dir()]
        heads={PurePosixPath(entry.filename).parts[0] for entry in entries}
        strip=len(heads)==1 and all(len(PurePosixPath(entry.filename).parts)>1 for entry in entries)
        for entry in entries:
            parts=PurePosixPath(entry.filename).parts[1:] if strip else PurePosixPath(entry.filename).parts
            if any(part in ('..','.') for part in parts):raise ValueError('归档成员包含越界路径')
            for depth in range(1,len(parts)+1):
                original='/'.join(parts[:depth])
                if original in mappings:continue
                leaf=re.sub(r'[<>:"|?*\x00-\x1f]','_',parts[depth-1]).rstrip(' .') or '_'
                if leaf.split('.')[0].upper() in ('CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]):leaf='_'+leaf
                parent=mappings.get('/'.join(parts[:depth-1]),'');safe=(PurePosixPath(parent)/leaf).as_posix();index=1
                while safe.casefold() in occupied and occupied[safe.casefold()]!=original:
                    safe=(PurePosixPath(parent)/(leaf+f'_{index}')).as_posix();index+=1
                mappings[original]=safe;occupied[safe.casefold()]=original
            original='/'.join(parts);target=(destination/mappings[original]).resolve()
            if not target.is_relative_to(destination.resolve()):raise ValueError('归档成员超出了仓库目录')
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(entry))
            files.append({'path':target.relative_to(root).as_posix(),'original_path':original,'archive_member':entry.filename,'bytes':target.stat().st_size})
        revision=archive.comment.decode('ascii',errors='replace')
    return files,revision


def capture_web(root,url,output):
    from web_archive import capture_web_archive
    return capture_web_archive(root,url,output)


def acquire(root,payload,force=False):
    root=Path(root).resolve();stage=root/'00_source';current=stage/'source.json'
    stage.mkdir(parents=True,exist_ok=True)
    if current.is_file() and not force:
        old=read_json(current)
        if old['status']=='acquired' and old['kind']==payload['kind'] and old['material']==payload['material'] and (root/old['entry']).is_file() and all((root/item['path']).is_file() for item in old['files']):return old
    materials=stage/'materials';materials.mkdir(exist_ok=True)
    numbers=[int(p.name.split('-')[1]) for p in materials.glob('source-*') if p.is_dir()]
    output=materials/f'source-{max(numbers,default=0)+1:04}';output.mkdir()
    kind=payload['kind'];result={'kind':kind,'material':payload['material'],'status':'acquired','entry':'','files':[]};begin=time.perf_counter()
    try:
        if kind=='url':
            # 派生截图失败时继续使用已经抓完的归档，不重新访问原站
            if not force and current.is_file() and old.get('kind')==kind and old.get('material')==payload['material']:
                saved=next((p for p in sorted(materials.glob('source-*/original.wacz'),reverse=True) if p.parent!=output and (p.parent/'capture.json').is_file()),None)
                if saved:
                    shutil.copyfile(saved,output/'original.wacz')
                    shutil.copyfile(saved.parent/'capture.json',output/'capture.json')
            result.update(capture_web(root,payload['material'],output));entry=output/'original.html'
        else:
            entry=output/('original.pdf' if kind=='file' else 'original.zip');path=Path(payload['material'])
            if path.is_file():shutil.copyfile(path,entry)
            elif kind=='repository':
                match=re.fullmatch(r'https://github.com/([^/]+)/([^/#?]+?)(?:\.git)?/?',payload['material'])
                if not match:raise ValueError('请提供 GitHub 仓库首页或本机 ZIP')
                response=guarded_get(f'https://codeload.github.com/{match[1]}/{match[2]}/zip/HEAD',timeout=60);response.raise_for_status();entry.write_bytes(response.content)
            else:raise ValueError('本机 PDF 文件不存在')
            if kind=='repository':
                result['files'],result['revision']=extract_repository(entry,output/'repository',root)
                result['repository']=(output/'repository').relative_to(root).as_posix()
            else:
                import fitz
                with fitz.open(entry) as document:result['pages']=len(document)
                result['integrity']={'original_bytes':path.stat().st_size,'saved_bytes':entry.stat().st_size,'byte_for_byte_equal':path.read_bytes()==entry.read_bytes()}
        result['entry']=entry.relative_to(root).as_posix()
        if kind!='repository':result['files']=[{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size} for p in output.rglob('*') if p.is_file()]
    except Exception as error:result.update(status='unavailable',reason=str(error))
    result.setdefault('acquisition',{'attempts':1,'model_calls':0,'api_cost_rmb':0})
    result['acquisition']['total_seconds']=time.perf_counter()-begin
    write_json(current,result);return result


def localize_asset(root, address):
    """把材料真正使用的网络资源保存到本地，原链接只用来记录出处"""
    import base64
    import mimetypes
    from urllib.parse import urlsplit
    folder=root/'00_source/materials/linked-assets';folder.mkdir(parents=True,exist_ok=True)
    index=folder/'links.json';links=read_json(index) if index.is_file() else {}
    if address in links and (root/links[address]).is_file():return root/links[address]
    if address.startswith('data:'):
        header,body=address.split(',',1);mime=header[5:].split(';')[0]
        data=base64.b64decode(body) if ';base64' in header else __import__('urllib.parse',fromlist=['unquote_to_bytes']).unquote_to_bytes(body)
    else:
        response=guarded_get(address,timeout=45);response.raise_for_status();data=response.content
        mime=response.headers.get('Content-Type','').split(';')[0]
    if not data:raise ValueError('网络资源为空：'+address)
    suffix=mimetypes.guess_extension(mime) or Path(urlsplit(address).path).suffix or '.bin'
    target=folder/f'asset-{len(links)+1:04}{suffix}';target.write_bytes(data)
    links[address]=target.relative_to(root).as_posix();write_json(index,links)
    return target





def guarded_get(address, **kwargs):
    """每次跳转都核对公开地址，保护下载器与浏览器之外的资源路径"""
    from lessonweave.network import validate_url
    for _ in range(6):
        if os.environ.get('LESSONWEAVE_ALLOW_LOCAL_FETCH')!='1':
            validate_url(address)
        response=requests.get(address,allow_redirects=False,**kwargs)
        if response.status_code in {301,302,303,307,308}:
            address=urljoin(address,response.headers['Location'])
            response.close()
            continue
        return response
    raise ValueError('资源发生了过多次跳转')
