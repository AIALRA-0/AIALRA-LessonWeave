"""旧阅读链接读回共享改稿后，正文和表格继续使用统一公式渲染"""
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def test_standalone_entry_renders_saved_and_dynamically_updated_shared_math():
    html = '''<!doctype html><meta charset="utf-8"><article id="demo-content">原始快照</article><aside id="glossary-result"></aside><div id="source-cards"></div>
    <script src="/math-text.js"></script><script src="/reader-text.js"></script>
    <script>window.LESSONWEAVE={project_id:'fixture',readweave_shared:true};window.hydrated=[];
    window.ReaderSourceBridge={getState:()=>({doc:{section_id:'s1',glossary:[]},ready:true}),updateGlossary:()=>{},hydrateSharedMedia:()=>{},hydrateSharedText:async element=>{await ReaderText.renderIn(element);hydrated.push(element.id)}};</script>
    <script src="/shared-reader-entry.js"></script>'''
    article = {'articleId':'shared-fixture','key':'explanation:s1','kind':'explanation','title':'当前正文',
               'revision':2,'deleted':False,'body':r'<h2>共享改稿</h2><p>\(x_1=7\)</p><table><tr><td>\(v=8\)</td></tr></table>',
               'readweave':{'objects':[],'links':[]}}
    mutations,errors=[],[]
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch();page=browser.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        def route(item):
            request=item.request;path=urlsplit(request.url).path
            if request.method not in ('GET','HEAD','OPTIONS'):mutations.append(path);item.abort();return
            if path=='/':item.fulfill(body=html,content_type='text/html');return
            if path=='/api/readweave-projects/fixture':item.fulfill(json={'editionId':'e','section_articles':{'s1':'shared-fixture'}});return
            if path=='/api/shared/articles/shared-fixture':item.fulfill(json=article);return
            if path=='/api/shared/changes':item.fulfill(json={'changes':[{'kind':'article-updated'}]if article['revision']>2 else[],'nextCursor':article['revision']});return
            if path.startswith('/api/'):
                item.fulfill(json={'anchors':[],'entries':[],'jobs':[],'removedJobIds':[]});return
            file=ROOT/path.lstrip('/')
            if not file.is_file():file=ROOT/'framework/reader'/path.lstrip('/')
            if not file.is_file():file=ROOT/'web'/path.lstrip('/')
            if file.is_file():item.fulfill(path=str(file));return
            item.fulfill(status=404,body='')
        page.route('http://127.0.0.1:19877/**',route);page.goto('http://127.0.0.1:19877/')
        page.wait_for_function("document.querySelectorAll('#demo-content .katex').length===2")
        assert page.locator('#demo-content table .katex').count()==1
        assert page.evaluate("hydrated.includes('demo-content')")
        article.update(revision=3,body=r'<h2>读者再次保存</h2><p>\(y^2=9\)</p>')
        page.wait_for_function("document.querySelector('#demo-content [data-math-source]')?.dataset.mathSource==='y^2=9'")
        page.wait_for_function("document.querySelector('#demo-content .katex')!==null")
        assert page.evaluate("ReaderText.audit(document.querySelector('#demo-content')).errors")==[]
        assert '读者再次保存' in page.locator('#demo-content').inner_text()
        dialogs=[]
        page.on('dialog',lambda dialog:(dialogs.append(dialog.message),dialog.dismiss()))
        page.evaluate('window.getSelection().removeAllRanges()')
        page.locator('#demo-content h2').click(button='right')
        page.get_by_role('menuitem',name='移入回收站',exact=True).click()
        assert len(dialogs)==1 and '讲解“当前正文”' in dialogs[0]
        assert not errors and not mutations
        browser.close()
