"""用实际定位脚本和鼠标拖选核对 PDF 字层与离线 iframe，不调用生成模型"""
import base64
import json
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
FIRST = "First source line explains the input"
SECOND = "Second source line explains the result"


@pytest.mark.parametrize("kind", ["pdf", "iframe"])
def test_real_source_drag_opens_native_five_actions(kind):
    template = BeautifulSoup((ROOT/'framework/reader/book.html').read_text('utf-8'), 'html.parser')
    source = template.select_one('#demo-original')
    source.attrs.pop('hidden', None)
    dialog = template.select_one('#locator-dialog')
    source_html = str(source)+str(dialog)
    page_id = 'source.pdf:1' if kind == 'pdf' else 'offline-page'
    identity = 'r1\ntree.json\n'+page_id
    articles = {
        'explanation': {'articleId': 'explanation', 'kind': 'explanation', 'key': 'explanation:s1', 'title': '说明', 'body': '<p>说明</p>', 'revision': 1, 'deleted': False, 'readweave': {'objects': [], 'links': []}},
        'original': {'articleId': 'original', 'kind': 'original', 'title': '原文', 'body': '<p>Section original</p>', 'revision': 1, 'deleted': False},
        'page': {'articleId': 'page', 'kind': 'original', 'title': '原页全文', 'body': f'<p>{FIRST}</p>\n<p>{SECOND}</p>', 'revision': 1, 'deleted': False},
    }
    pack = {'material_run': 'r1', 'material_path': 'tree.json', 'sources': [{'id': 'source', 'type': 'text', 'source': {'kind': 'pdf' if kind == 'pdf' else 'html', 'path': 'source.pdf' if kind == 'pdf' else 'offline.html', 'dom_path': 'p'}, 'sentences': [{'id': 's1', 'original': FIRST}]}]}
    manifest = {'editionId': 'edition', 'section_articles': {'s1': 'explanation'}, 'original_articles': {'s1': 'original'}, 'page_articles': {identity: 'page'}}
    locations = {'material_run': 'r1', 'material_path': 'tree.json', 'pages': {page_id: {'kind': 'pdf' if kind == 'pdf' else 'html', 'width': 600, 'height': 240, 'number': 1, 'image': '/page.png', **({'text_layer': '/page.text.json'} if kind == 'pdf' else {})}}, 'files': {}, 'sources': {'source': {'page_ids': [page_id], 'file_ids': [], 'locations': [{'page_id': page_id, 'bbox': [30, 40, 520, 120]}], 'sentences': {'s1': {'original': FIRST, 'status': 'exact', 'rects': [{'page_id': page_id, 'bbox': [30, 40, 520, 60]}]}}}}}
    if kind == 'iframe':
        locations['web'] = {'dom': '/offline.html'}
    lines = []
    for row, text in enumerate((FIRST, SECOND)):
        top = 40+row*45
        lines.append({'text': text, 'bbox': [30, top, 30+len(text)*9, top+22], 'chars': [{'text': char, 'bbox': [30+i*9, top, 39+i*9, top+22]} for i, char in enumerate(text)]})
    seed = json.dumps({'pack': pack, 'manifest': manifest}, ensure_ascii=False)
    reader_html = '''<style>
    body{margin:0}#root{display:grid;grid-template-columns:700px 360px;font:16px/1.8 sans-serif;gap:20px}#demo-original{grid-column:1}#glossary-result{grid-column:2;grid-row:1/5;height:750px}.pane-content{overflow:auto}#source-text-scroll{height:90px;overflow:auto}.locator-surface{height:400px;position:relative}.locator-viewport{height:400px;overflow:auto;position:relative}.locator-page{position:relative}#locator-image{width:100%;display:block}#locator-highlights{pointer-events:none;position:absolute;inset:0}#locator-dom{width:100%;height:400px;border:0}#demo-content{grid-column:1}#locator-status{margin:0}[hidden]{display:none!important}
    </style><article id="demo-content"><p>说明</p></article><aside id="glossary-result" class="demo-terms"><h2>术语表</h2><div class="pane-content"><div id="glossary-list">术语</div></div></aside>'''+source_html
    html = '''<!doctype html><meta charset="utf-8"><div id="host"></div><script>window.__seed='''+seed+''';</script><script type="module">
    import {mountSharedReader} from '/integrations/readweave/shared-reader.js';
    const shadow=document.querySelector('#host').attachShadow({mode:'open'}),root=document.createElement('main');root.id='root';root.className='lw-reader-root';root.innerHTML='''+json.dumps(reader_html, ensure_ascii=False)+''';shadow.append(root);window.readerRoot=root;
    const state={doc:{section_id:'s1',glossary:[]},sourcePack:window.__seed.pack};
    window.shared=mountSharedReader(root,{bridge:()=>state,manifest:()=>Promise.resolve(window.__seed.manifest),nativeUrl:id=>'/native/'+id});
    window.ReaderSourceBridge={getState:()=>({ready:true,sourcePack:state.sourcePack,selection:{refs:[{source_id:'source'}]}})};
    const documentProxy=new Proxy(document,{get(target,key){if(key==='getElementById')return id=>root.querySelector('#'+CSS.escape(id));if(key==='querySelector'||key==='querySelectorAll'||key==='addEventListener'||key==='removeEventListener'||key==='dispatchEvent')return root[key].bind(root);const value=target[key];return typeof value==='function'?value.bind(target):value;}});
    new Function('document',await fetch('/framework/reader/source-locator.js').then(response=>response.text()))(documentProxy);window.ready=true;
    </script>'''
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width': 1280, 'height': 1000})
        page.set_default_timeout(6000)
        errors, calls = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def route(request):
            path = urlsplit(request.request.url).path
            if path == '/': request.fulfill(body=html, content_type='text/html'); return
            if path == '/offline.html': request.fulfill(body=f'''<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><style>body{{font:20px/1.7 sans-serif;padding:20px}}p{{margin:0 0 24px}}</style><p>{FIRST}</p><p>{SECOND}</p>''', content_type='text/html'); return
            if path == '/page.png': request.fulfill(body=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg=='), content_type='image/png'); return
            if path == '/page.text.json': request.fulfill(json={'page_id': page_id, 'lines': lines}); return
            if path == '/05_writing/source-location/index.json': request.fulfill(json={'versions': [{'material_run': 'r1', 'material_path': 'tree.json', 'manifest': '/locations.json'}]}); return
            if path == '/locations.json': request.fulfill(json=locations); return
            if path.startswith('/api/'):
                calls.append((request.request.method, path))
                if path.startswith('/api/shared/articles/'): request.fulfill(json=articles[path.rsplit('/', 1)[-1]]); return
                if path.endswith('/anchors'): request.fulfill(json={'anchors': []}); return
                if '/anchors/' in path: request.fulfill(json={'entries': []}); return
                if path.endswith('/generation-jobs'): request.fulfill(json={'jobs': [], 'removedJobIds': [], 'nextCursor': 0}); return
                request.fulfill(json={'changes': [], 'nextCursor': 0}); return
            file = (ROOT/path.lstrip('/')).resolve()
            if file.is_relative_to(ROOT) and file.is_file(): request.fulfill(path=str(file)); return
            request.fulfill(status=404, body='Not found')

        page.context.route('http://127.0.0.1:19877/**', route)
        page.goto('http://127.0.0.1:19877/')
        try:
            page.wait_for_function('window.ready===true', timeout=6000)
        except Exception as error:
            raise AssertionError(errors) from error
        page.locator('.lw-shared-state').filter(has_text='已同步').wait_for()
        glossary=page.locator('#glossary-result > .pane-content').bounding_box()
        questions=page.locator('#glossary-result > .lw-readweave-host').bounding_box()
        assert glossary['height']>180 and abs(glossary['height']-questions['height'])<2
        if kind == 'iframe':
            page.locator('#locator-view-select').select_option('dom')
            first = page.frame_locator('#locator-dom').locator('p').nth(0)
            second = page.frame_locator('#locator-dom').locator('p').nth(1)
            first.wait_for()
            page.wait_for_function("window.readerRoot.querySelector('#locator-dom').contentDocument.body.dataset.readweaveArticleId==='page'")
        else:
            first = page.locator('.locator-selectable-text p').nth(0)
            second = page.locator('.locator-selectable-text p').nth(1)
            first.wait_for()
            page.wait_for_function("window.readerRoot.querySelector('.locator-selectable-text').dataset.readweaveArticleId==='page'")
        first_box, second_box = first.bounding_box(), second.bounding_box()
        input_session=page.context.new_cdp_session(page)
        input_session.send('Input.dispatchMouseEvent',{'type':'mouseMoved','x':first_box['x']+2,'y':first_box['y']+first_box['height']/2})
        input_session.send('Input.dispatchMouseEvent',{'type':'mousePressed','x':first_box['x']+2,'y':first_box['y']+first_box['height']/2,'button':'left','buttons':1,'clickCount':1})
        input_session.send('Input.dispatchMouseEvent',{'type':'mouseMoved','x':second_box['x']+220,'y':second_box['y']+second_box['height']/2,'button':'left','buttons':1})
        input_session.send('Input.dispatchMouseEvent',{'type':'mouseReleased','x':second_box['x']+220,'y':second_box['y']+second_box['height']/2,'button':'left','buttons':0,'clickCount':1})
        scope = page.frame_locator('#locator-dom') if kind == 'iframe' else page
        bubble = scope.locator('.readweave-selection-actions')
        bubble.wait_for(timeout=8000)
        assert bubble.get_by_role('button').count() == 5
        assert bubble.evaluate("element=>getComputedStyle(element).position")=='fixed'
        selected = page.evaluate("window.readerRoot.querySelector('#locator-dom').contentWindow.getSelection().toString()" if kind == 'iframe' else "document.querySelector('#host').shadowRoot.getSelection().toString()")
        assert 'Second source' in selected, (kind, selected, errors)
        page.mouse.click(second_box['x']+110, second_box['y']+second_box['height']/2, button='right')
        bubble.wait_for()
        assert page.locator('[data-shared="edit"]').get_attribute('href').endswith('/native/page')
        ask=bubble.get_by_role('button', name='提问', exact=True)
        if kind == 'iframe':
            try:
                page.wait_for_function("readerRoot.querySelector('#locator-dom').contentDocument.fonts.check('16px boxicons') && [...readerRoot.querySelector('#locator-dom').contentDocument.fonts].some(font=>font.family.replace(/[\"']/g,'')==='boxicons'&&font.status==='loaded')")
            except Exception as error:
                raise AssertionError(page.evaluate("({frame:[...readerRoot.querySelector('#locator-dom').contentDocument.fonts].map(font=>({family:font.family,status:font.status})),parent:[...document.fonts].map(font=>({family:font.family,status:font.status})),errors:readerRoot.querySelector('.lw-readweave-host').textContent.slice(-100)})")) from error
            page.evaluate("async()=>{const bubble=readerRoot.querySelector('#locator-dom').contentDocument.querySelector('.readweave-selection-actions');await Promise.all(bubble.getAnimations({subtree:true}).map(animation=>animation.finished.catch(()=>{})));}")
            samples=page.evaluate("""async()=>{const result=[];for(let index=0;index<5;index++){await new Promise(requestAnimationFrame);const rect=readerRoot.querySelector('#locator-dom').contentDocument.querySelector('.readweave-selection-actions button').getBoundingClientRect();result.push({x:rect.x,y:rect.y,width:rect.width,height:rect.height});}return result;}""")
            for field in ('x','y','width','height'):
                assert max(sample[field] for sample in samples)-min(sample[field] for sample in samples)<1, samples
            box=ask.bounding_box()
            x,y=box['x']+box['width']/2,box['y']+box['height']/2
            input_session.send('Input.dispatchMouseEvent',{'type':'mouseMoved','x':x,'y':y})
            input_session.send('Input.dispatchMouseEvent',{'type':'mousePressed','x':x,'y':y,'button':'left','buttons':1,'clickCount':1})
            input_session.send('Input.dispatchMouseEvent',{'type':'mouseReleased','x':x,'y':y,'button':'left','buttons':0,'clickCount':1})
        else:
            ask.click()
        page.locator('.readweave-selection').wait_for()
        page.wait_for_function("!readerRoot.querySelector('.lw-readweave-host').textContent.includes('待确认的文字选区')")
        content=page.frame_locator('#locator-dom').locator('body') if kind=='iframe' else page.locator('.locator-selectable-text')
        assert content.locator(':scope > p').count()==2
        assert content.locator('[data-readweave-runtime-only="1"]').count()>=2
        assert not any(method == 'POST' and '/generation-jobs' in path for method, path in calls)
        assert errors == []
        browser.close()
