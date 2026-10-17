import os
import json
import re
import shutil
import zipfile
from pathlib import Path,PurePosixPath
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def read_json(path):return json.loads(path.read_text(encoding='utf-8'))
def write_json(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def extract_repository(archive_path,destination,root):
    destination.mkdir(parents=True,exist_ok=True)
    mappings={};occupied={};files=[]
    with zipfile.ZipFile(archive_path) as archive:
        entries=[entry for entry in archive.infolist() if not entry.is_dir()]
        if len(entries)>20000 or sum(entry.file_size for entry in entries)>512_000_000:
            raise ValueError('仓库解压后超过当前站点的文件数量或容量上限')
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
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True, **({'executable_path': os.environ['LESSONWEAVE_BROWSER']} if os.environ.get('LESSONWEAVE_BROWSER') else {}))
        page=browser.new_page(viewport={'width':1280,'height':900},device_scale_factor=1)
        if os.environ.get('LESSONWEAVE_ALLOW_LOCAL_FETCH')!='1':
            from lessonweave.network import validate_url
            def guard(route):
                try:
                    if route.request.url.startswith(('http://','https://')):validate_url(route.request.url)
                    route.continue_()
                except ValueError:route.abort()
            page.route('**/*',guard)
        page.goto(url,wait_until='domcontentloaded',timeout=60000)
        page.locator('body').wait_for(timeout=30000)
        page.evaluate("document.querySelectorAll('img').forEach(img=>img.loading='eager')")
        page.wait_for_timeout(1500)
        positions=page.evaluate('''()=>{const positions={};let index=0;for(const element of document.querySelectorAll('body *')){const r=element.getBoundingClientRect(),id='s'+(++index);element.setAttribute('data-iqa-source',id);positions[id]={bbox:[Math.max(0,r.left+scrollX),Math.max(0,r.top+scrollY),Math.max(0,r.right+scrollX),Math.max(0,r.bottom+scrollY)],src:element.currentSrc||element.src||null};}return positions;}''')
        height=page.evaluate('Math.max(document.body.scrollHeight,document.documentElement.scrollHeight)')
        page.screenshot(path=str(output/'original.png'),full_page=True)
        html=page.content();browser.close()
    (output/'original.html').write_text(html,encoding='utf-8');write_json(output/'dom.json',positions)
    soup=BeautifulSoup(html,'html.parser');body=soup.select_one('.body.markup') or soup.find('article') or soup.find('main') or soup.body
    images=[];seen=set();(output/'assets').mkdir()
    for image in body.find_all('img'):
        address=positions[image['data-iqa-source']]['src'] or urljoin(url,image.get('src',''))
        if address in seen:continue
        seen.add(address);response=guarded_get(address,timeout=30);response.raise_for_status()
        mime=response.headers.get('Content-Type','').split(';')[0]
        suffix={'image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp','image/svg+xml':'.svg','image/gif':'.gif','image/avif':'.avif'}.get(mime)
        if not suffix:raise ValueError(f'图像资源返回了 {mime}')
        path=output/'assets'/f'image-{len(images)+1:03}{suffix}';path.write_bytes(response.content)
        images.append({'url':address,'path':path.relative_to(root).as_posix()})
    prefix='/'+output.relative_to(root).as_posix()
    return {'snapshot':{'image':prefix+'/original.png','html':prefix+'/original.html','width':1280,'height':height},'positions':(output/'dom.json').relative_to(root).as_posix(),'images':images}


def acquire(root,payload,force=False):
    root=Path(root).resolve();stage=root/'00_source';current=stage/'source.json'
    if current.is_file() and not force:
        old=read_json(current)
        if old['status']=='acquired' and old['kind']==payload['kind'] and old['material']==payload['material'] and (root/old['entry']).is_file() and all((root/item['path']).is_file() for item in old['files']):return old
    materials=stage/'materials';materials.mkdir(exist_ok=True)
    numbers=[int(p.name.split('-')[1]) for p in materials.glob('source-*') if p.is_dir()]
    output=materials/f'source-{max(numbers,default=0)+1:04}';output.mkdir()
    kind=payload['kind'];result={'kind':kind,'material':payload['material'],'status':'acquired','entry':'','files':[]}
    try:
        if kind=='url':
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
        result['entry']=entry.relative_to(root).as_posix()
        if kind!='repository':result['files']=[{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size} for p in output.rglob('*') if p.is_file()]
    except Exception as error:result.update(status='unavailable',reason=str(error))
    if result['status']=='acquired' and kind=='url':result=complete_web_assets(root,result)
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


def complete_web_assets(root,source):
    """核对正文使用的资源，并额外生成不依赖网络图片的正文快照"""
    from content_checks import material_body,in_material
    from PIL import Image
    original=root/source['entry'];soup=BeautifulSoup(original.read_text(encoding='utf-8'),'html.parser')
    body=material_body(soup)
    if body is None:raise ValueError('没有找到网页内容')
    positions=read_json(root/source['positions']);images={item['url']:item['path'] for item in source.get('images',[])}
    resources={item['anchor']:item for item in source.get('resources',[])}
    assets=original.parent/'assets';assets.mkdir(exist_ok=True)
    for image in body.find_all('img'):
        if not in_material(image):continue
        anchor=image.get('data-iqa-source');address=positions.get(anchor,{}).get('src') or urljoin(source['material'],image.get('src',''))
        if address not in images or not (root/images[address]).is_file():
            path=localize_asset(root,address);images[address]=path.relative_to(root).as_posix()
    for element in body.find_all(['svg','canvas','video','audio','iframe','object','embed']):
        if not in_material(element):continue
        anchor=element.get('data-iqa-source')
        if not anchor:raise ValueError('媒体没有冻结的 DOM 定位')
        if anchor in resources and (root/resources[anchor]['path']).is_file():continue
        if element.name=='svg':
            path=assets/(anchor+'.svg');path.write_text(str(element),encoding='utf-8')
        elif element.name=='canvas':
            box=positions.get(anchor,{}).get('bbox')
            if not box or box[2]<=box[0] or box[3]<=box[1]:raise ValueError('画布没有可保留的图像范围')
            path=assets/(anchor+'.png')
            with Image.open(root/source['snapshot']['image'].lstrip('/')) as image:image.crop(tuple(map(int,box))).save(path)
        else:
            address=element.get('src') or element.get('data') or (element.find('source') or {}).get('src')
            if not address:raise ValueError('媒体没有可保存的内容地址')
            path=localize_asset(root,urljoin(source['material'],address))
        resources[anchor]={'anchor':anchor,'kind':element.name,'path':path.relative_to(root).as_posix()}
    source['images']=[{'url':url,'path':path} for url,path in images.items()]
    source['resources']=list(resources.values())
    offline=BeautifulSoup(str(body),'html.parser')
    for element in offline.find_all(['script','style','noscript','template','button','form']):element.decompose()
    for element in offline.select('picture source'):element.decompose()
    for image in offline.find_all('img'):
        anchor=image.get('data-iqa-source');address=positions.get(anchor,{}).get('src') or urljoin(source['material'],image.get('src',''))
        image['src']='/'+images[address]
        for key in ('srcset','sizes','loading'):image.attrs.pop(key,None)
    for element in offline.find_all(['svg','canvas','video','audio','iframe','object','embed']):
        item=resources.get(element.get('data-iqa-source'))
        if not item:continue
        replacement=offline.new_tag('img' if item['kind'] in ('svg','canvas') else 'a')
        replacement['src' if replacement.name=='img' else 'href']='/'+item['path']
        if replacement.name=='a':replacement.string='打开已保存的媒体文件'
        element.replace_with(replacement)
    path=original.parent/'offline.html'
    path.write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>已保留的网页正文</title><style>body{max-width:850px;margin:40px auto;padding:0 20px;font:18px/1.8 system-ui}img{max-width:100%}pre{white-space:pre-wrap}</style>'+str(offline),encoding='utf-8')
    source['snapshot']['offline_html']='/'+path.relative_to(root).as_posix()
    existing={item['path']:item for item in source['files']}
    for path in [path,*[root/item['path'] for item in source['images']],*[root/item['path'] for item in source['resources']]]:
        existing[path.relative_to(root).as_posix()]={'path':path.relative_to(root).as_posix(),'bytes':path.stat().st_size}
    source['files']=list(existing.values())
    if (root/'00_source/source.json').is_file():write_json(root/'00_source/source.json',source)
    return source



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
        if len(response.content)>100_000_000:
            raise ValueError('下载的单个资源超过当前容量上限')
        return response
    raise ValueError('资源发生了过多次跳转')
