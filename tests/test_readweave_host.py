"""在真实浏览器挂载原生面板，检查网站宿主中的选区、同步和删除恢复"""
from pathlib import Path
from urllib.parse import urlsplit
import json
import pytest
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def shared_page():
    article={'articleId':'shared_article','editionId':'edition','key':'explanation:s1','kind':'explanation','title':'带宽怎样计算','body':'<p>位宽告诉你一次能传多少个 bit，速率告诉你每秒传多少次</p>','revision':1,'deleted':False,'readweave':{'objects':[],'links':[]}}
    html='''<!doctype html><meta charset="utf-8"><div id="host"></div><script type="module">
    import {mountSharedReader} from '/integrations/readweave/shared-reader.js';
    const shadow=document.querySelector('#host').attachShadow({mode:'open'});
    const root=document.createElement('main');root.className='lw-reader-root';root.innerHTML='<style>:host{display:block}main{font:16px/1.8 sans-serif;display:grid;grid-template-columns:650px 350px;gap:24px}#glossary-result{width:350px;grid-column:2;grid-row:1/4}article{padding:30px} .lw-readweave-host{height:650px}</style><div><article id="demo-content"><p>位宽告诉你一次能传多少个 bit，速率告诉你每秒传多少次</p></article></div><aside id="glossary-result"><h2>术语表</h2><div id="glossary-list"></div></aside><div id="demo-original"></div>';
    shadow.append(root);window.shared=mountSharedReader(root,{bridge:()=>({doc:{section_id:'s1',glossary:[]}}),manifest:()=>fetch('/manifest').then(r=>r.json())});
    </script>'''
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={'width':1280,'height':900});errors=[];requests=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        def route(r):
            path=urlsplit(r.request.url).path
            if path=='/':r.fulfill(body=html,content_type='text/html');return
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
        page.route('http://127.0.0.1:19875/**',route);page.goto('http://127.0.0.1:19875/')
        page.locator('.lw-shared-state').filter(has_text='已同步').wait_for(timeout=15000)
        yield page,article,errors,requests
        browser.close()


def test_native_five_selection_actions_in_shadow_host(shared_page):
    page,article,errors,requests=shared_page
    page.locator('#demo-content p').evaluate('''p=>{const range=document.createRange();range.selectNodeContents(p);const selection=p.getRootNode().getSelection();selection.removeAllRanges();selection.addRange(range);document.dispatchEvent(new Event('selectionchange'));p.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,composed:true}));}''')
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


def test_shared_delete_restore_and_edit_do_not_call_models(shared_page):
    page,article,errors,requests=shared_page
    page.get_by_role('button',name='移入回收站',exact=True).click()
    page.get_by_role('button',name='恢复文章').wait_for()
    assert article['deleted']
    page.get_by_role('button',name='恢复文章').click()
    page.get_by_role('button',name='编辑当前文章').click()
    page.get_by_role('textbox',name='编辑共享文章',exact=True).fill('改过的正文仍保留单位 bit')
    page.get_by_role('button',name='保存并同步').click()
    page.locator('#demo-content').filter(has_text='改过的正文仍保留单位 bit').wait_for()
    assert article['revision']==4
    assert not any('/generate'in path for method,path in requests if method=='POST')
    assert errors==[]
