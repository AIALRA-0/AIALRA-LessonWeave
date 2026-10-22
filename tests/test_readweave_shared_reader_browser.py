"""这个测试在真实浏览器挂载共享阅读器，并检查原文、译文和术语能否按小节回读。"""
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def _term_anchor(term_id):
    return "lwdef_" + sha256(term_id.encode()).hexdigest()[:24]


@pytest.fixture
def shared_source_page():
    glossary = [
        {"id": "term-a", "display": "术语甲", "definition": "本地定义甲", "explanation": []},
        {"id": "term-b", "display": "术语乙", "definition": "本地定义乙", "explanation": []},
    ]
    definition_objects = [
        {"objectId": "object-a", "contentType": "definition", "displayTitle": "术语甲", "displayBody": "远端定义甲"},
        {"objectId": "object-b", "contentType": "definition", "displayTitle": "术语乙", "displayBody": "远端定义乙"},
    ]
    articles = {
        "explanation": {
            "articleId": "explanation", "editionId": "edition", "key": "explanation:s1", "kind": "explanation",
            "title": "讲解", "body": "<p>讲解正文</p>", "revision": 1, "deleted": False,
            "source": {"section_id": "s1"},
            "readweave": {"objects": definition_objects, "links": [
                {"objectId": "object-a", "articleId": "explanation", "anchorId": _term_anchor("term-a"), "contentType": "definition", "displayTitle": "术语甲", "displayBody": "远端定义甲"},
            ]},
        },
        "original": {
            "articleId": "original", "editionId": "edition", "key": "original:s1", "kind": "original",
            "title": "原文", "body": '<p data-lw-sentence="s1">共享原文改稿一</p><p data-lw-sentence="s2">共享原文改稿二</p><p>自由增加的原文</p><pre><code>原文代码片段</code></pre><h4>原文小标题</h4><table><tbody><tr><td>原文表格内容</td></tr></tbody></table>',
            "revision": 2, "deleted": False,
        },
        "translation": {
            "articleId": "translation", "editionId": "edition", "key": "translation:s1", "kind": "translation",
            "title": "译文", "body": '<p data-lw-sentence="s1">共享译文一</p><p data-lw-sentence="s2">共享译文改稿二</p><p>自由增加的译文</p>',
            "revision": 2, "deleted": False,
        },
    }
    manifest = {
        "editionId": "edition", "section_articles": {"s1": "explanation"},
        "original_articles": {"s1": "original"}, "translation_articles": {"s1": "translation"},
    }
    source_pack = {"sources": [{"id": "source", "sentences": [
        {"id": "s1", "original": "中文原文一", "english": "英文译文一", "translation": "中文译文一"},
        {"id": "s2", "original": "英文原文二", "translation": "中文译文二"},
    ]}]}
    seed = json.dumps({"glossary": glossary, "sourcePack": source_pack}, ensure_ascii=False)
    html = f'''<!doctype html><meta charset="utf-8"><div id="host"></div>
    <script>window.__seed={seed};</script>
    <script type="module">
      import {{mountSharedReader}} from '/integrations/readweave/shared-reader.js';
          const shadow=document.querySelector('#host').attachShadow({{mode:'open'}}),root=document.createElement('main');root.className='lw-reader-root';
      root.innerHTML='<article id="demo-content"><p>讲解正文快照</p></article><aside id="glossary-result"><div id="glossary-list"></div></aside>'+
        '<aside id="demo-original"><div class="pane-head">原页与译文</div><div id="source-text-scroll"><div id="source-cards">'+
        '<section class="demo-source-card"><div class="source-sentence-pair" data-sentence-id="s1"><div class="source-translation"><p>中文原文一</p></div><div class="source-original"><p>英文译文一</p></div></div>'+
        '<div class="source-sentence-pair" data-sentence-id="s2"><div class="source-translation"><p>中文译文二</p></div><div class="source-original"><p>英文原文二</p></div></div></section></div></div>'+
        '<section id="source-locator"><div id="locator-viewport"><div id="locator-page">原件定位界面</div></div></section></aside>';
          shadow.append(root);
      const state={{doc:{{section_id:'s1',glossary:window.__seed.glossary}},sourcePack:window.__seed.sourcePack}};
      window.__readerState=state;
      window.glossaryUpdates=[];
      window.shared=mountSharedReader(root,{{bridge:()=>state,manifest:()=>Promise.resolve(window.__manifest),
        updateGlossary:terms=>{{state.doc.glossary=terms;window.glossaryUpdates.push(terms);}},
        request:async(path,init={{}})=>{{const response=await fetch('/api/'+path,init);const value=await response.json();if(!response.ok)throw Error(value.error||'request failed');return value;}}
      }});
      window.__readerRoot=root;
    </script>'''
    errors, requests, change_feed = [], [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("pageerror", lambda error: errors.append(str(error)))

        def route(request):
            path = urlsplit(request.request.url).path
            if path == "/":
                request.fulfill(body=html, content_type="text/html")
                return
            if path == "/manifest-seed":
                request.fulfill(json=manifest)
                return
            if path.startswith("/api/lessonweave/articles/"):
                parts = path.split("/")
                if parts[-1] == "restore" and request.request.method == "POST":
                    article_id = parts[-2]
                    article = articles[article_id]
                    article["deleted"] = False
                    article["revision"] += 1
                    requests.append(("POST-restore", article_id))
                    request.fulfill(json={"articleId": article_id})
                    return
                article_id = parts[-1]
                requests.append((request.request.method, article_id))
                article = articles.get(article_id)
                if not article:
                    request.fulfill(status=404, json={"error": "missing"})
                    return
                if request.request.method == "PUT":
                    article["body"] = request.request.post_data_json["body"]
                    article["revision"] += 1
                if request.request.method == "DELETE":
                    article["deleted"] = True
                    article["revision"] += 1
                request.fulfill(json=article)
                return
            if path.endswith("/edit-sessions") and request.request.method == "POST":
                request.fulfill(json={"leaseId": "lease", "token": "browser-test-token", "fence": 1})
                return
            if "/edit-sessions/" in path:
                request.fulfill(json={})
                return
            if path.endswith("/changes"):
                batch = list(change_feed)
                change_feed.clear()
                request.fulfill(json={"changes": batch, "nextCursor": 1 if batch else 0})
                return
            file = (ROOT / path.lstrip("/")).resolve()
            if file.is_file() and file.is_relative_to(ROOT):
                request.fulfill(path=str(file))
                return
            request.fulfill(status=404, body="Not found")

        page.route("http://127.0.0.1:19876/**", route)
        page.add_init_script(f"window.__manifest={json.dumps(manifest)}")
        page.goto("http://127.0.0.1:19876/")
        try:
            page.locator(".lw-shared-state").wait_for(timeout=15000)
        except Exception as error:
            raise AssertionError(f"共享阅读器未挂载；浏览器错误={errors}；页面内容={page.locator('body').inner_text()}") from error
        page.locator(".lw-shared-source-additions").filter(has_text="自由增加的原文").wait_for(timeout=15000)
        yield page, articles, errors, requests, change_feed
        browser.close()


def test_source_projection_keeps_locator_and_selects_the_matching_article(shared_source_page):
    page, articles, errors, requests, _ = shared_source_page
    page.get_by_text("共享原文改稿一", exact=True).wait_for()
    page.get_by_text("共享原文改稿二", exact=True).wait_for()
    page.get_by_text("共享译文改稿二", exact=True).wait_for()
    page.get_by_text("自由增加的译文", exact=True).wait_for()
    page.get_by_text("原文代码片段", exact=True).wait_for()
    page.get_by_text("原文小标题", exact=True).wait_for()
    page.get_by_text("原文表格内容", exact=True).wait_for()
    assert page.locator(".source-translation p").nth(0).inner_text() == "共享原文改稿一"
    assert page.locator(".source-original p").nth(0).inner_text() == "英文译文一"
    assert page.locator(".source-original p").nth(1).inner_text() == "共享原文改稿二"
    assert page.locator(".source-translation p").nth(1).inner_text() == "共享译文改稿二"
    assert page.locator("#locator-page").inner_text() == "原件定位界面"

    page.locator(".source-original p").nth(1).click()
    page.locator('[data-shared="edit"]').click()
    original_editor = page.get_by_role("textbox", name="编辑共享文章")
    original_editor.wait_for()
    assert "共享原文改稿二" in original_editor.inner_text()
    original_editor.evaluate("""node=>{node.innerHTML='<p data-lw-sentence="s1">原文新版本一</p><p data-lw-sentence="s2">原文新版本二</p><p>新版自由原文</p>';node.dispatchEvent(new Event('input',{bubbles:true}));}""")
    page.get_by_role("button", name="保存并同步").click()
    page.locator(".source-translation p").nth(0).filter(has_text="原文新版本一").wait_for()
    assert page.locator(".source-translation p").nth(0).inner_text() == "原文新版本一"
    assert page.locator(".source-original p").nth(1).inner_text() == "原文新版本二"
    assert page.get_by_text("新版自由原文", exact=True).count() == 1
    assert page.locator("#locator-page").inner_text() == "原件定位界面"
    assert articles["original"]["revision"] == 3

    page.locator(".source-translation p").nth(1).click()
    page.locator('[data-shared="edit"]').click()
    translation_editor = page.get_by_role("textbox", name="编辑共享文章")
    translation_editor.wait_for()
    assert "共享译文改稿二" in translation_editor.inner_text()
    page.get_by_role("button", name="退出编辑").click()
    page.locator(".source-original p").nth(1).click()
    page.locator('[data-shared="delete"]').click()
    page.get_by_role("button", name="恢复共享原文").wait_for()
    assert page.locator(".source-original p").nth(1).is_hidden()
    assert page.locator("#locator-page").inner_text() == "原件定位界面"
    page.get_by_role("button", name="恢复共享原文").click()
    page.locator(".source-original p").nth(1).filter(has_text="原文新版本二").wait_for()
    assert not page.locator(".source-original p").nth(1).is_hidden()
    assert articles["original"]["revision"] == 5
    assert ("GET", "original") in requests and ("GET", "translation") in requests
    assert ("POST-restore", "original") in requests
    assert errors == []


def test_deleted_glossary_definition_returns_after_restore(shared_source_page):
    page, articles, errors, requests, _ = shared_source_page
    page.wait_for_function("window.glossaryUpdates.length > 0")
    assert [term["id"] for term in page.evaluate("window.glossaryUpdates.at(-1)")] == ["term-a"]
    articles["explanation"]["readweave"]["links"].append({
        "objectId": "object-b", "articleId": "explanation", "anchorId": _term_anchor("term-b"),
        "contentType": "definition", "displayTitle": "术语乙", "displayBody": "恢复后的定义乙",
    })
    page.evaluate("window.__readerRoot.dispatchEvent(new CustomEvent('reading:document-ready'))")
    page.wait_for_function("window.glossaryUpdates.length > 1 && window.glossaryUpdates.at(-1).some(term => term.id === 'term-b')")
    restored = page.evaluate("window.glossaryUpdates.at(-1)")
    assert [term["id"] for term in restored] == ["term-a", "term-b"]
    assert restored[1]["definition"] == "恢复后的定义乙"
    assert errors == []


def test_poll_refreshes_other_articles_without_changing_the_active_source(shared_source_page):
    page, articles, errors, requests, change_feed = shared_source_page
    page.locator(".source-original p").nth(1).click()
    page.wait_for_function("window.glossaryUpdates.length > 0")
    page.evaluate("""() => {window.sharedChanges=[];window.addEventListener('readweave:shared-change',event=>window.sharedChanges.push(event.detail));}""")
    before = len(requests)
    articles["explanation"]["readweave"]["links"].append({
        "objectId": "object-b", "articleId": "explanation", "anchorId": _term_anchor("term-b"),
        "contentType": "definition", "displayTitle": "术语乙", "displayBody": "另一端刚刚更新的定义",
    })
    articles["explanation"]["revision"] += 1
    change_feed.append({"articleId": "explanation", "kind": "article-updated"})
    page.wait_for_function("window.glossaryUpdates.at(-1).some(term => term.id === 'term-b' && term.definition === '另一端刚刚更新的定义')", timeout=10000)
    page.wait_for_function("window.sharedChanges.some(change => change.articleIds.includes('explanation') && change.articleIds.includes('original') && change.articleIds.includes('translation'))", timeout=10000)
    refreshed = requests[before:]
    for article_id in ("explanation", "original", "translation"):
        assert ("GET", article_id) in refreshed
    page.locator('[data-shared="edit"]').click()
    editor = page.get_by_role("textbox", name="编辑共享文章")
    editor.wait_for()
    assert "共享原文改稿二" in editor.inner_text()
    page.get_by_role("button", name="退出编辑").click()
    assert errors == []


def test_switching_section_keeps_draft_and_does_not_insert_the_previous_body(shared_source_page):
    page,articles,errors,requests,_=shared_source_page
    articles['explanation']['revision']=2
    articles['explanation']['body']='<p>上一节保存过的正文</p>'
    articles['next']={'articleId':'next','editionId':'edition','key':'explanation:s2','kind':'explanation','title':'下一节','body':'<p>下一节自己的正文</p>','revision':1,'deleted':False,'readweave':{'objects':[],'links':[]}}
    page.locator('[data-shared="edit"]').click()
    field=page.get_by_role('textbox',name='编辑共享文章')
    field.fill('上一节尚未保存的草稿')
    page.evaluate("""() => {window.__manifest.section_articles.s2='next';window.__readerState.doc={section_id:'s2',glossary:[]};window.__readerState.sourcePack={sources:[]};window.__readerRoot.querySelector('#demo-content').innerHTML='<p>下一节自己的正文</p>';window.__readerRoot.dispatchEvent(new CustomEvent('reading:document-ready'));}""")
    page.wait_for_function("window.__readerRoot.querySelector('#demo-content').dataset.readweaveArticleId==='next'")
    assert page.get_by_role('textbox',name='编辑共享文章').count()==0
    assert page.locator('#demo-content').inner_text()=='下一节自己的正文'
    assert '尚未保存的草稿'in page.evaluate("localStorage.getItem('lessonweave:shared-draft:explanation')")
    assert articles['explanation']['body']=='<p>上一节保存过的正文</p>'
    assert errors==[]
