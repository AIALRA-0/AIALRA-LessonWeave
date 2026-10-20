"""用 Browsertrix 保存原页，再从本地 WACZ 读取供解析器使用的 DOM 与定位信息"""
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from io import BytesIO
import mimetypes
import os
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import threading
import time
from urllib.parse import urlencode
import uuid
import zipfile

from playwright.sync_api import sync_playwright

IMAGE = 'webrecorder/browsertrix-crawler:1.15.0'


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def crawl_command(folder, collection, url):
    return ['docker', 'run', '--rm', '--shm-size=1g', '-v', str(folder) + ':/crawls',
            IMAGE, 'crawl', '--url', url, '--scopeType', 'page', '--limit', '1',
            '--workers', '1', '--collection', collection, '--generateWACZ', '--text', 'to-warc',
            '--screenshot', 'view', '--pageLoadTimeout', '30', '--postLoadDelay', '1',
            '--behaviorTimeout', '20', '--pageExtraDelay', '1', '--behaviors', 'autoscroll,autofetch']


def capture_once(url, output):
    """配置在启动前固定，每次只执行一条抓取命令，不回退到旧下载器"""
    collection = 'page-' + uuid.uuid4().hex
    host = os.environ.get('LESSONWEAVE_ARCHIVE_SSH', '')
    if host:
        folder = str(PurePosixPath(os.environ.get('LESSONWEAVE_ARCHIVE_WORKDIR', '/tmp/lessonweave-archives')) / collection)
        subprocess.run(['ssh', '-o', 'BatchMode=yes', host, shlex.join(['mkdir', '-p', folder])], check=True, capture_output=True)
    else:
        folder = str((output / 'crawl').resolve())
        Path(folder).mkdir()
    command = crawl_command(folder, collection, url)
    invocation = ['ssh', '-o', 'BatchMode=yes', host, shlex.join(command)] if host else command
    receipt = {'engine': 'Browsertrix Crawler', 'version': '1.15.0', 'image': IMAGE,
               'url': url, 'collection': collection, 'command': command, 'runtime': 'ssh' if host else 'local',
               'started_at': datetime.now(timezone.utc).isoformat(), 'attempts': 1,
               'manual_repairs': 0, 'model_calls': 0, 'api_cost_rmb': 0}
    begin = time.perf_counter()
    with (output / 'capture.log').open('wb') as log:
        process = subprocess.run(invocation, stdout=log, stderr=subprocess.STDOUT)
    receipt.update(exit_code=process.returncode, crawl_seconds=time.perf_counter() - begin,
                   ended_at=datetime.now(timezone.utc).isoformat())
    save(output / 'capture.json', receipt)
    archive = output / 'original.wacz'
    relative = f'collections/{collection}/{collection}.wacz'
    begin = time.perf_counter()
    if host:
        transfer = subprocess.run(['scp', '-q', '-o', 'BatchMode=yes', f'{host}:{folder}/{relative}', str(archive)], capture_output=True)
        receipt['transfer_exit_code'] = transfer.returncode
        if transfer.returncode:
            receipt['transfer_error'] = transfer.stderr.decode('utf-8', errors='replace')
    else:
        saved = Path(folder) / relative
        if saved.is_file():
            import shutil
            shutil.copyfile(saved, archive)
    receipt['transfer_seconds'] = time.perf_counter() - begin
    save(output / 'capture.json', receipt)
    if not archive.is_file():
        raise ValueError('Browsertrix 没有生成可保存的 WACZ，原始日志保存在 capture.log')
    return archive, receipt


def inspect_wacz(path):
    """检查 ZIP 实体与 WACZ 的资源清单，资源失败继续按原记录交付"""
    from warcio.archiveiterator import ArchiveIterator
    resources = []
    page_info = []
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        package = json.loads(archive.read('datapackage.json'))
        missing = [r['path'] for r in package.get('resources', []) if r['path'] not in archive.namelist()]
        for name in archive.namelist():
            if not name.endswith('.warc.gz'):
                continue
            with archive.open(name) as stream:
                for record in ArchiveIterator(stream):
                    target = record.rec_headers.get_header('WARC-Target-URI') or ''
                    if record.rec_type == 'response' and record.http_headers:
                        resources.append({'url': target, 'status': int(record.http_headers.get_statuscode()),
                                          'mime': record.http_headers.get_header('Content-Type') or ''})
                    if record.rec_type in {'resource', 'metadata'} and ('pageinfo' in target or 'page-info' in target):
                        try:
                            page_info.append(json.loads(record.content_stream().read()))
                        except (ValueError, UnicodeError):
                            pass
    return {'zip_crc_valid': bad is None, 'zip_bad_member': bad,
            'manifest_members_present': not missing, 'missing_members': missing,
            'http_responses': len(resources), 'http_failures': [r for r in resources if r['status'] >= 400],
            'page_info': page_info}


@contextmanager
def offline_view(root):
    """回放只读取本地归档，外部连接由独立代理拒绝，并保留请求记录"""
    from lessonweave.server import Handler

    attempts = []

    class DenyExternal(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_CONNECT(self):
            attempts.append({'method': self.command, 'target': self.path})
            self.send_error(403, 'Offline archive replay')

        do_GET = do_CONNECT
        do_POST = do_CONNECT

    class RootStore:
        def project(self, key):
            if key != 'capture':
                raise KeyError(key)
            return {'path': str(root), 'legacy': False}

    # 临时渲染器只绑定本机回环，Service Worker 的内部请求不经过官网认证中间件
    handler = type('ArchiveHandler', (Handler,), {'store': RootStore(), 'allowed': lambda self: self.client_address[0]=='127.0.0.1'})
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    proxy = ThreadingHTTPServer(('127.0.0.1', 0), DenyExternal)
    for item in (server, proxy):
        threading.Thread(target=item.serve_forever, daemon=True).start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', f'http://127.0.0.1:{proxy.server_port}', attempts
    finally:
        for item in (server, proxy):
            item.shutdown()
            item.server_close()


def replay_frame(page):
    for _ in range(150):
        found = [f for f in page.frames if '/archive/replay/w/' in f.url and 'mp_/' in f.url
                 and f.parent_frame and '/archive/replay/w/' not in f.parent_frame.url and f.locator('body').count()]
        if found:
            return found[-1]
        page.wait_for_timeout(200)
    raise ValueError('没有读到 WACZ 回放中的原页面')


def prepare_snapshot_layout(frame):
    """把悬浮元素固定在快照中的一次位置，逐屏截图时不再重复遮住正文"""
    return frame.evaluate('''()=>{
      window.scrollTo({top:0,left:0,behavior:'instant'});
      const style=document.createElement('style');
      style.textContent='*{animation-play-state:paused!important;transition:none!important;scroll-behavior:auto!important}';
      document.head.append(style);
      let fixed=0,sticky=0;
      for(const e of document.querySelectorAll('html,body,body *')){
        const s=getComputedStyle(e),position=s.position;
        if(position==='sticky'){
          for(const [key,value] of Object.entries({position:'relative',top:'auto',bottom:'auto'}))e.style.setProperty(key,value,'important');
          sticky++;
        }else if(position==='fixed'){
          const b=e.getBoundingClientRect();if(!b.width||!b.height)continue;
          const width=s.width,height=s.height;
          for(const [key,value] of Object.entries({position:'absolute',left:'0px',top:'0px',right:'auto',bottom:'auto',width,height}))e.style.setProperty(key,value,'important');
          const now=e.getBoundingClientRect();
          e.style.setProperty('left',(b.left-now.left)+'px','important');
          e.style.setProperty('top',(b.top-now.top)+'px','important');
          fixed++;
        }
      }
      return {fixed_elements:fixed,sticky_elements:sticky};
    }''')


def capture_frame_png(page, frame, target):
    """截取 iframe 实际可见的每一屏，再按真实滚动坐标拼成整页，避免 iframe 裁切"""
    from PIL import Image
    begin = time.perf_counter()
    size = frame.evaluate('''()=>({width:innerWidth,height:Math.max(document.body.scrollHeight,document.documentElement.scrollHeight),viewport_height:innerHeight})''')
    box = frame.frame_element().bounding_box()
    border = frame.frame_element().evaluate('(e)=>({left:e.clientLeft,top:e.clientTop})')
    clip = {'x': box['x']+border['left'], 'y': box['y']+border['top'],
            'width': size['width'], 'height': size['viewport_height']}
    picture = Image.new('RGB', (size['width'], size['height']), 'white')
    tiles = []
    covered = 0
    while covered < size['height']:
        top = round(frame.evaluate('''y=>{window.scrollTo({top:y,left:0,behavior:'instant'});return scrollY}''', covered))
        frame.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        raw = page.screenshot(clip=clip, animations='disabled')
        with Image.open(BytesIO(raw)) as tile:
            height = min(tile.height, size['height']-top)
            picture.paste(tile.convert('RGB').crop((0, 0, tile.width, height)), (0, top))
        tiles.append({'top': top, 'height': height})
        end = top+height
        if top > covered or end <= covered:
            break
        covered = end
    picture.save(target)
    frame.evaluate("window.scrollTo({top:0,left:0,behavior:'instant'})")
    return {'method': 'iframe-scroll-stitch-v1', 'width': size['width'], 'height': size['height'],
            'covered_height': covered, 'complete': covered == size['height'], 'tiles': tiles,
            'elapsed_seconds': time.perf_counter()-begin}


def snapshot_from_archive(root, url, archive, output):
    """供解析器使用的 HTML、图片和定位只从本地回放读取，WACZ 保持原样"""
    images, resources, issues = [], [], []
    assets = output / 'assets'
    assets.mkdir(exist_ok=True)
    relative = archive.relative_to(root).as_posix()
    query = urlencode({'source': relative, 'url': url})
    with offline_view(root) as (base, proxy, outbound), sync_playwright() as p:
        options = {'headless': True, 'args': ['--proxy-server='+proxy, '--proxy-bypass-list=127.0.0.1;localhost;[::1]', '--disable-quic']}
        if os.environ.get('LESSONWEAVE_BROWSER'):
            options['executable_path'] = os.environ['LESSONWEAVE_BROWSER']
        browser = p.chromium.launch(**options)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 900}, device_scale_factor=1)
            page.goto(base + '/p/capture/archive.html?' + query, wait_until='domcontentloaded', timeout=45000)
            frame = replay_frame(page)
            frame.wait_for_timeout(1200)
            begin = time.perf_counter()
            bottom = False
            while time.perf_counter() - begin < 20:
                bottom = frame.evaluate('''()=>{const h=Math.max(document.body.scrollHeight,document.documentElement.scrollHeight);const y=window.scrollY;window.scrollTo({top:y+700,behavior:'instant'});return y+innerHeight>=h-2}''')
                frame.wait_for_timeout(60)
                if bottom:
                    break
            frame.evaluate('''()=>{document.querySelectorAll('img').forEach(i=>i.loading='eager');window.scrollTo({top:0,behavior:'instant'})}''')
            frame.evaluate('''()=>Promise.race([Promise.allSettled([...document.images].map(i=>i.decode())),new Promise(r=>setTimeout(r,4000))])''')
            layout = prepare_snapshot_layout(frame)
            state = frame.evaluate('''()=>{const positions={};let index=0;for(const e of document.querySelectorAll('html,body,body *')){const id='s'+(++index),b=e.getBoundingClientRect();e.setAttribute('data-iqa-source',id);positions[id]={bbox:[Math.max(0,b.left+scrollX),Math.max(0,b.top+scrollY),Math.max(0,b.right+scrollX),Math.max(0,b.bottom+scrollY)],src:e.currentSrc||e.src||null}}return {positions,html:document.documentElement.outerHTML,height:Math.max(document.body.scrollHeight,document.documentElement.scrollHeight),title:document.title,text:document.body.innerText,tex:[...document.querySelectorAll('math annotation')].map(e=>e.textContent),svg:[...document.querySelectorAll('svg')].map(e=>({namespace:e.namespaceURI,viewBox:e.getAttribute('viewBox')})),images:[...document.images].map(e=>({anchor:e.getAttribute('data-iqa-source'),url:e.currentSrc||e.src,loaded:e.complete&&e.naturalWidth>0}))}}''')
            (output / 'original.html').write_text('<!doctype html>\n' + state.pop('html'), encoding='utf-8')
            save(output / 'dom.json', state.pop('positions'))
            screenshot = capture_frame_png(page, frame, output / 'original.png')
            if not screenshot['complete']:
                issues.append({'kind': 'screenshot', 'reason': '逐屏截图尚未覆盖完整页面', 'covered_height': screenshot['covered_height'], 'height': screenshot['height']})
            for image in state['images']:
                address = image['url']
                if not address or any(i['url'] == address for i in images):
                    continue
                data = frame.evaluate('''async url=>{try{const r=await fetch(url);if(!r.ok)return {error:'HTTP '+r.status};const b=await r.blob();return await new Promise(resolve=>{const f=new FileReader();f.onload=()=>resolve({mime:b.type,data:f.result.split(',')[1]});f.onerror=()=>resolve({error:'图片响应无法读取'});f.readAsDataURL(b)})}catch(e){return {error:String(e)}}}''', address)
                if data.get('error'):
                    issues.append({'kind': 'image', 'url': address, 'reason': data['error']})
                    continue
                suffix = mimetypes.guess_extension(data['mime'].split(';')[0]) or '.bin'
                path = assets / f'image-{len(images)+1:03}{suffix}'
                path.write_bytes(base64.b64decode(data['data']))
                images.append({'url': address, 'anchor': image.get('anchor'), 'path': path.relative_to(root).as_posix()})
            for item in frame.evaluate(resource_snapshot_script()):
                path = archive
                if item.get('svg'):
                    path = assets / (item['anchor'] + '.svg')
                    path.write_text(item['svg'], encoding='utf-8')
                elif item.get('canvas'):
                    path = assets / (item['anchor'] + '.png')
                    path.write_bytes(base64.b64decode(item['canvas']))
                resources.append({'anchor': item['anchor'], 'kind': item['kind'], 'path': path.relative_to(root).as_posix(),
                                  'url': item.get('url'), 'representation': 'archive' if path == archive else 'snapshot'})
                if item.get('error'):
                    issues.append({'kind': item['kind'], 'anchor': item['anchor'], 'reason': item['error']})
            # 动态 SVG、Canvas 可能在图片解码或截图期间出现，最终 HTML 与定位共用最新编号
            final = frame.evaluate('''()=>{const positions={};for(const e of document.querySelectorAll('[data-iqa-source]')){const b=e.getBoundingClientRect();positions[e.getAttribute('data-iqa-source')]={bbox:[Math.max(0,b.left+scrollX),Math.max(0,b.top+scrollY),Math.max(0,b.right+scrollX),Math.max(0,b.bottom+scrollY)],src:e.currentSrc||e.src||null}}return {positions,html:document.documentElement.outerHTML}}''')
            save(output/'dom.json',final['positions'])
            (output/'original.html').write_text('<!doctype html>\n'+final['html'],encoding='utf8')
            state.update(scroll_reached_bottom=bottom, outbound_attempts=list(outbound), issues=issues,
                         screenshot=screenshot, snapshot_layout=layout)
            save(output / 'replay-check.json', state)
        finally:
            browser.close()
    prefix = '/' + output.relative_to(root).as_posix()
    return {'snapshot': {'image': prefix + '/original.png', 'html': prefix + '/original.html',
                         'offline_html': prefix + '/original.html', 'replay': '/archive.html?' + query,
                         'width': 1280, 'height': state['height']},
            'positions': (output / 'dom.json').relative_to(root).as_posix(), 'images': images, 'resources': resources}, state


def resource_snapshot_script():
    return '''()=>{const used=new Set(),owners=new Map();for(const e of document.querySelectorAll('[data-iqa-source]')){const a=e.getAttribute('data-iqa-source');used.add(a);if(!owners.has(a))owners.set(a,e)}let index=0;return [...document.querySelectorAll('svg,canvas,video,audio,iframe,object,embed')].map(e=>{let anchor=e.getAttribute('data-iqa-source');if(!anchor||!/^s[0-9]+$/.test(anchor)||owners.get(anchor)!==e){do{anchor='s'+(++index)}while(used.has(anchor));used.add(anchor);owners.set(anchor,e);e.setAttribute('data-iqa-source',anchor)}const r={anchor,kind:e.localName,url:e.src||e.data||null};if(e.localName==='svg')r.svg=new XMLSerializer().serializeToString(e);if(e.localName==='canvas'){try{r.canvas=e.toDataURL('image/png').split(',')[1]}catch(error){r.error=String(error)}}return r})}'''


def capture_web_archive(root, url, output):
    from lessonweave.network import validate_url
    if os.environ.get('LESSONWEAVE_ALLOW_LOCAL_FETCH') != '1':
        validate_url(url)
    begin = time.perf_counter()
    archive=output/'original.wacz'
    if archive.is_file():
        receipt=json.loads((output/'capture.json').read_text('utf8'))
        receipt=dict(receipt,reused_archive=True,crawl_seconds=0,transfer_seconds=0)
    else:
        archive, receipt = capture_once(url, output)
    inspect_begin = time.perf_counter()
    integrity = inspect_wacz(archive)
    save(output / 'archive-check.json', integrity)
    inspect_seconds = time.perf_counter() - inspect_begin
    snapshot_begin = time.perf_counter()
    result, replay = snapshot_from_archive(root, url, archive, output)
    timing = {'crawl_seconds': receipt['crawl_seconds'], 'transfer_seconds': receipt['transfer_seconds'],
              'archive_check_seconds': inspect_seconds, 'offline_snapshot_seconds': time.perf_counter() - snapshot_begin,
              'total_seconds': time.perf_counter() - begin}
    result.update(web_archive={'engine': 'Browsertrix Crawler', 'version': '1.15.0', 'format': 'wacz',
                              'path': archive.relative_to(root).as_posix(), 'url': url, 'replay_version': '2.5.3',
                              'capture_receipt': (output / 'capture.json').relative_to(root).as_posix(),
                              'archive_check': (output / 'archive-check.json').relative_to(root).as_posix(),
                              'replay_check': (output / 'replay-check.json').relative_to(root).as_posix()},
                  integrity={'archive_valid': integrity['zip_crc_valid'] and integrity['manifest_members_present'],
                             'http_failure_count': len(integrity['http_failures']),
                             'snapshot_issue_count': len(replay['issues']),
                             'scope': '原始网络响应保存在 WACZ，DOM 与图片副本只从本地回放读取；视频完整播放另行记录'},
                  acquisition={'attempts': 1, 'model_calls': 0, 'api_cost_rmb': 0, **timing})
    return result
