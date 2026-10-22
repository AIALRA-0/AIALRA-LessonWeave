"""在真实浏览器挂载原生面板，检查网站宿主中的选区、同步和删除恢复"""
from pathlib import Path
from urllib.parse import urlsplit
import json
import pytest
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def shared_page():
    article={'articleId':'shared_article','editionId':'edition','key':'explanation:s1','kind':'explanation','title':'带宽怎样计算','body':'<p>位宽告诉你一次能传多少个 bit，速率告诉你每秒传多少次</p><p>接下来把 bit 换成字节，再乘速率，就能得到带宽</p>','revision':1,'deleted':False,'readweave':{'objects':[],'links':[]}}
    html='''<!doctype html><meta charset="utf-8"><div id="host"></div><script type="module">
    import {mountSharedReader} from '/integrations/readweave/shared-reader.js';
    const shadow=document.querySelector('#host').attachShadow({mode:'open'});
    const root=document.createElement('main');root.className='lw-reader-root';root.innerHTML='<style>:host{display:block}main{font:16px/1.8 sans-serif;display:grid;grid-template-columns:650px 350px;gap:24px}#glossary-result{width:350px;grid-column:2;grid-row:1/4}article{padding:30px} .lw-readweave-host{height:650px}</style><div><article id="demo-content"><p>位宽告诉你一次能传多少个 bit，速率告诉你每秒传多少次</p><p>接下来把 bit 换成字节，再乘速率，就能得到带宽</p></article></div><aside id="glossary-result"><h2>术语表</h2><div id="glossary-list"></div></aside><div id="demo-original"></div>';
    shadow.append(root);window.shared=mountSharedReader(root,{bridge:()=>({doc:{section_id:'s1',glossary:[]}}),nativeUrl:id=>'/native/'+id,manifest:()=>fetch('/manifest').then(r=>r.json())});
    </script>'''
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={'width':1280,'height':900});errors=[];requests=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        def route(r):
            path=urlsplit(r.request.url).path
            if path=='/':r.fulfill(body=html,content_type='text/html');return
            if path.startswith('/native/'):r.fulfill(body='<p>Native article</p>',content_type='text/html');return
            if path=='/manifest':r.fulfill(json={'editionId':'edition','articles':[article],'section_articles':{'s1':article['articleId']}});return
            if path.startswith('/api/'):
                requests.append((r.request.method,path))
                payload=r.request.post_data_json if r.request.post_data else {}
                if path.endswith('/articles/shared_article'):
                    if r.request.method=='DELETE':article['deleted']=True;article['revision']+=1
                    if r.request.method=='PUT':article['body']=payload['body'];article['revision']+=1
                    r.fulfill(json=article);return
                if path.endswith('/restore'):article['deleted']=False;article['revision']+=1;r.fulfill(json=article);return
                if path.endswith('/edit-sessions')or'/edit-sessions/'in path:r.fulfill(json={'leaseId':'lease','token':'synthetic-test-token','fence':1});return
                if path.endswith('/anchors'):r.fulfill(json={'anchors':[]});return
                if '/anchors/'in path:r.fulfill(json={'entries':[]});return
                if path.endswith('/generation-jobs'):
                    r.fulfill(json={'jobs':[],'removedJobIds':[],'nextCursor':0});return
                if path.endswith('/changes'):r.fulfill(json={'changes':[],'nextCursor':0});return
                r.fulfill(json={'jobs':[],'removedJobIds':[],'nextCursor':0});return
            file=(ROOT/path.lstrip('/')).resolve()
            if file.is_file()and file.is_relative_to(ROOT):r.fulfill(path=str(file));return
            r.fulfill(status=404,body='Not found')
        page.context.route('http://127.0.0.1:19875/**',route);page.goto('http://127.0.0.1:19875/')
        page.locator('.lw-shared-state').filter(has_text='已同步').wait_for(timeout=15000)
        yield page,article,errors,requests
        browser.close()


def test_native_five_selection_actions_in_shadow_host(shared_page):
    page,article,errors,requests=shared_page
    paragraph=page.locator('#demo-content p').first
    box=paragraph.bounding_box()
    page.mouse.move(box['x']+2,box['y']+box['height']/2)
    page.mouse.down();page.mouse.move(box['x']+min(360,box['width']-3),box['y']+box['height']/2,steps=18);page.mouse.up()
    bubble=page.locator('.readweave-selection-actions');bubble.wait_for(timeout=8000)
    text=bubble.inner_text()
    for action in ['提问','定义','注解','总结','笔记']:assert action in text
    page.wait_for_function("""() => document.fonts.check('16px boxicons') && [...document.fonts].some(face => face.family.replace(/[\"']/g,'') === 'boxicons' && face.status === 'loaded')""",timeout=10000)
    icon=bubble.locator('i.bx').first
    icon.wait_for()
    icon_style=icon.evaluate("""el => ({family:getComputedStyle(el,'::before').fontFamily,content:getComputedStyle(el,'::before').content})""")
    assert 'boxicons' in icon_style['family'].lower(),icon_style
    assert icon_style['content'] not in ('none','normal','""'),icon_style
    font_requests=page.evaluate("""() => performance.getEntriesByType('resource').filter(entry => /\\.woff2(?:[?#]|$)/i.test(entry.name) && entry.responseEnd > 0).map(entry => entry.name)""")
    assert any('boxicons' in url.lower() for url in font_requests),font_requests
    assert errors==[]


def test_context_recycle_cancel_is_read_only_and_edit_opens_native(shared_page):
    page,article,errors,requests=shared_page
    page.locator('#demo-content p').first.click(button='right')
    menu=page.get_by_role('menu')
    menu.wait_for()
    before=list(requests)
    confirmations=[]
    page.once('dialog',lambda dialog:(confirmations.append(dialog.message),dialog.dismiss()))
    menu.get_by_role('menuitem',name='移入回收站').click()
    assert confirmations==['将讲解“带宽怎样计算”移入回收站？原始生成快照会保留，可以恢复']
    assert requests==before
    assert not article['deleted']
    assert page.locator('[contenteditable=true]').count()==0
    assert page.locator('[data-shared=delete]').count()==0
    assert page.locator('[data-shared=edit] svg').count()==1
    assert page.locator('[data-shared=open] svg').count()==1
    with page.expect_popup() as popup:
        page.get_by_role('link',name='在 ReadWeave 编辑当前文章',exact=True).click()
    popup.value.wait_for_load_state()
    assert popup.value.url.endswith('/native/shared_article')
    popup.value.close()
    assert not any('/generate'in path for method,path in requests if method=='POST')
    assert errors==[]


def test_real_cross_paragraph_drag_and_right_click_keep_five_actions(shared_page):
    page,article,errors,requests=shared_page
    first=page.locator('#demo-content p').nth(0).bounding_box();last=page.locator('#demo-content p').nth(1).bounding_box()
    page.mouse.move(first['x']+2,first['y']+8);page.mouse.down()
    page.mouse.move(last['x']+min(200,last['width']-3),last['y']+12,steps=24);page.mouse.up()
    bubble=page.locator('.readweave-selection-actions');bubble.wait_for(timeout=8000)
    selected=page.evaluate("document.querySelector('#host').shadowRoot.getSelection().toString()")
    assert '接下来'in selected
    page.mouse.click(last['x']+100,last['y']+12,button='right')
    bubble.wait_for()
    assert bubble.get_by_role('button').count()==5
    bubble.get_by_role('button',name='提问',exact=True).click()
    page.locator('.readweave-selection').wait_for()
    assert not any(method=='POST'and'/generation-jobs'in path for method,path in requests)
    assert errors==[]


def test_chapter_switch_does_not_keep_previous_article_while_manifest_waits():
    first='First paragraph belongs to the old chapter'
    second='Second paragraph belongs only to the new chapter'
    html='''<!doctype html><meta charset="utf-8"><div id="host"></div><script type="module">
    import {mountSharedReader} from '/integrations/readweave/shared-reader.js';
    const shadow=document.querySelector('#host').attachShadow({mode:'open'}),root=document.createElement('main');
    root.className='lw-reader-root';root.innerHTML='<style>main{display:grid;grid-template-columns:650px 350px;font:17px/1.8 sans-serif}#demo-content{padding:25px}#glossary-result{height:700px}</style><article id="demo-content"><p>'''+first+'''</p></article><aside id="glossary-result"><div id="glossary-list"></div></aside><div id="source-cards"></div><div id="external-source"><p>Old original paragraph</p></div>';
    shadow.append(root);window.state={doc:{section_id:'s1',glossary:[]}};window.root=root;
    window.shared=mountSharedReader(root,{bridge:()=>state,nativeUrl:id=>'/native/'+id,manifest:()=>state.doc.section_id==='s1'?Promise.resolve({editionId:'e',section_articles:{s1:'old',s2:'new'},source_articles:{'old.txt':'old'}}):new Promise(resolve=>window.finishManifest=()=>resolve({editionId:'e',section_articles:{s1:'old',s2:'new'}}))});
    </script>'''
    calls=[]
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={'width':1280,'height':1000})
        def route(r):
            path=urlsplit(r.request.url).path
            if path=='/':r.fulfill(body=html,content_type='text/html');return
            if path.startswith('/api/'):
                calls.append((r.request.method,path))
                if path.startswith('/api/shared/articles/'):
                    id=path.rsplit('/',1)[-1];r.fulfill(json={'articleId':id,'editionId':'e','key':'explanation:'+('s1'if id=='old'else's2'),'kind':'explanation','title':id,'body':'<p>'+ (first if id=='old'else second)+'</p>','revision':1,'deleted':False,'readweave':{'objects':[],'links':[]}});return
                if path.endswith('/anchors'):r.fulfill(json={'anchors':[]});return
                if '/anchors/'in path:r.fulfill(json={'entries':[]});return
                r.fulfill(json={'jobs':[],'removedJobIds':[],'changes':[],'nextCursor':0});return
            file=(ROOT/path.lstrip('/')).resolve()
            if file.is_relative_to(ROOT)and file.is_file():r.fulfill(path=str(file));return
            r.fulfill(status=404,body='Not found')
        page.context.route('http://127.0.0.1:19876/**',route);page.goto('http://127.0.0.1:19876/')
        page.locator('[data-shared=edit]').filter(has_text='').wait_for()
        page.wait_for_function("root.querySelector('[data-shared=edit]').getAttribute('href')==='/native/old'")
        page.evaluate("()=>{for(const name of ['original','translation']){const node=document.createElement('div');node.dataset.readweaveArticleId='old-'+name;node.dataset.readweaveContentRoot='readonly';root.querySelector('#source-cards').append(node);}const element=root.querySelector('#external-source');root.dispatchEvent(new CustomEvent('reading:source-surface',{detail:{element,filePath:'old.txt'}}));}")
        page.wait_for_function("root.querySelector('#external-source').dataset.readweaveArticleId==='old'")
        page.evaluate("text=>{root.dispatchEvent(new CustomEvent('reading:document-changing'));state.doc={section_id:'s2',glossary:[]};root.querySelector('#demo-content').innerHTML='<p>'+text+'</p>';}",second)
        assert page.locator('#demo-content').get_attribute('data-readweave-article-id')is None
        assert page.locator('[data-readweave-article-id]').count()==0
        page.locator('#external-source').click()
        assert page.locator('#external-source').get_attribute('data-readweave-article-id')is None
        assert page.locator('[data-shared=edit]').get_attribute('href')is None
        assert page.locator('[data-shared=open]').get_attribute('href')is None
        paragraph=page.locator('#demo-content p');box=paragraph.bounding_box()
        page.mouse.move(box['x']+2,box['y']+10);page.mouse.down();page.mouse.move(box['x']+230,box['y']+10,steps=20);page.mouse.up()
        selected=page.evaluate("document.querySelector('#host').shadowRoot.getSelection().toString()")
        assert selected
        page.evaluate("root.dispatchEvent(new CustomEvent('reading:document-ready'))")
        assert page.locator('[data-shared=edit]').get_attribute('href')is None
        page.evaluate('finishManifest()')
        page.wait_for_function("root.querySelector('[data-shared=edit]').getAttribute('href')==='/native/new'")
        bubble=page.locator('.readweave-selection-actions');bubble.wait_for(timeout=8000)
        assert bubble.get_by_role('button').count()==5
        assert page.evaluate("document.querySelector('#host').shadowRoot.getSelection().toString()") == selected
        bubble.get_by_role('button',name='提问',exact=True).click()
        page.locator('.readweave-selection').wait_for()
        assert page.locator('[data-shared=edit]').get_attribute('href')=='/native/new'
        assert not any(method not in('GET','HEAD')for method,path in calls)
        browser.close()


@pytest.mark.parametrize('new_section_state', ['pending', 'ready'])
def test_old_poll_cannot_outlive_chapter_scope(new_section_state):
    html='''<!doctype html><meta charset="utf-8"><button id="next">下一节</button><div id="host"></div><script type="module">
    import {mountSharedReader} from '/integrations/readweave/shared-reader.js';
    const shadow=document.querySelector('#host').attachShadow({mode:'open'}),root=document.createElement('main');
    root.className='lw-reader-root';root.innerHTML='<article id="demo-content"><p>旧章节正文</p></article><aside id="glossary-result"><div id="glossary-list"></div></aside><div id="source-cards"></div>';shadow.append(root);
    window.state={doc:{section_id:'s1',glossary:[]}};window.root=root;window.sharedEvents=[];window.statuses=[];
    window.addEventListener('readweave:shared-change',event=>sharedEvents.push(event.detail));
    const request=async(path,init={})=>{const url=path.startsWith('lessonweave/')?'/api/shared/'+path.slice(12):'/api/'+path;const response=await fetch(url,init),value=await response.json();if(path==='lessonweave/articles/old'&&value.revision===2)window.oldResponseReturned=true;return value};
    mountSharedReader(root,{bridge:()=>state,nativeUrl:id=>'/native/'+id,request,manifest:()=>fetch('/manifest?section='+state.doc.section_id).then(response=>response.json())});
    new MutationObserver(()=>statuses.push(root.querySelector('.lw-shared-state').textContent)).observe(root.querySelector('.lw-shared-state'),{childList:true,subtree:true});
    document.querySelector('#next').onclick=()=>{root.dispatchEvent(new CustomEvent('reading:document-changing'));state.doc={section_id:'s2',glossary:[]};root.querySelector('#demo-content').innerHTML='<p>新章节正文</p>';root.dispatchEvent(new CustomEvent('reading:document-ready'));};
    </script>'''
    manifest={'editionId':'e','section_articles':{'s1':'old','s2':'new'},'original_articles':{'s1':'old-source','s2':'new-source'}}
    delayed_old,delayed_manifest,calls,errors=[],[],[],[]
    armed={'value':False,'feed':False}
    def article(id,revision=1):
        source=id.endswith('-source')
        return {'articleId':id,'editionId':'e','key':('original:'if source else'explanation:')+('s1'if id.startswith('old')else's2'),'kind':'original'if source else'explanation','title':id,'body':'<p>'+id+'</p>','revision':revision,'deleted':False,'readweave':{'objects':[],'links':[]}}
    with sync_playwright()as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        def route(r):
            path=urlsplit(r.request.url).path;calls.append((r.request.method,path))
            if path=='/':r.fulfill(body=html,content_type='text/html');return
            if path=='/manifest':
                if armed['value']:delayed_manifest.append(r)
                else:r.fulfill(json=manifest)
                return
            if path.startswith('/api/shared/articles/'):
                id=path.rsplit('/',1)[-1]
                if id=='old'and armed['value']:delayed_old.append(r)
                else:r.fulfill(json=article(id))
                return
            if path=='/api/shared/changes':
                changed=armed['value']and not armed['feed'];armed['feed']|=changed
                r.fulfill(json={'changes':[{'kind':'article-updated','articleId':'old'}]if changed else[],'nextCursor':1 if changed else 0});return
            if path.startswith('/api/'):
                r.fulfill(json={'anchors':[],'entries':[],'jobs':[],'removedJobIds':[]});return
            file=(ROOT/path.lstrip('/')).resolve()
            if file.is_relative_to(ROOT)and file.is_file():r.fulfill(path=str(file));return
            r.fulfill(status=404,body='Not found')
        page.route('http://127.0.0.1:19876/**',route);page.goto('http://127.0.0.1:19876/')
        page.wait_for_function("root.querySelector('[data-shared=edit]').getAttribute('href')==='/native/old'")
        armed['value']=True
        for _ in range(100):
            if delayed_old:break
            page.wait_for_timeout(25)
        assert delayed_old
        page.get_by_role('button',name='下一节',exact=True).click()
        for _ in range(100):
            if delayed_manifest:break
            page.wait_for_timeout(25)
        assert delayed_manifest
        if new_section_state=='ready':
            delayed_manifest.pop().fulfill(json=manifest)
            page.wait_for_function("root.querySelector('[data-shared=edit]').getAttribute('href')==='/native/new'")
        delayed_old.pop().fulfill(json=article('old',2))
        page.wait_for_function('window.oldResponseReturned===true');page.wait_for_timeout(100)
        assert not any('Cannot read' in text for text in page.evaluate('statuses'))
        assert not any('old'in event.get('articleIds',[])or'old-source'in event.get('articleIds',[])for event in page.evaluate('sharedEvents'))
        if new_section_state=='pending':
            assert page.locator('[data-shared=edit]').get_attribute('href')is None
            delayed_manifest.pop().fulfill(json=manifest)
            page.wait_for_function("root.querySelector('[data-shared=edit]').getAttribute('href')==='/native/new'")
        assert page.locator('#demo-content').get_attribute('data-readweave-article-id')=='new'
        assert page.locator('[data-shared=edit]').get_attribute('href')=='/native/new'
        assert not any(method not in('GET','HEAD')for method,path in calls)
        assert errors==[]
        browser.close()
