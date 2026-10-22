"""在真实浏览器延迟请求，检查轮询和保存后的读取是否按实际动作执行"""
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:19877"


@pytest.fixture(params=[False, True], ids=["default-request", "custom-request"])
def shared_request_page(request):
    pending, errors, mutations = [], [], []
    custom = "request:(path,init)=>fetch('/custom/'+path,init).then(async response=>{const value=await response.json();if(!response.ok)throw Error(value.error);return value;})," if request.param else ""
    html = '''<!doctype html><div id="root"><article id="demo-content"></article><aside id="glossary-result"></aside></div>
    <script type="module">import {mountSharedReader} from '/integrations/readweave/shared-reader.js';
    window.reader=mountSharedReader(document.querySelector('#root'),{''' + custom + '''bridge:()=>({ready:false}),manifest:async()=>({})});
    </script>'''
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        def route(route):
            path = urlsplit(route.request.url).path
            if path == "/":
                route.fulfill(body=html, content_type="text/html")
            elif path == "/integrations/readweave/native-panel.js":
                route.fulfill(body="export const sanitizeArticle=value=>value;export function mountReadWeave(root,options){window.panelRequest=options.request;return{update(){},unmount(){}}}", content_type="text/javascript")
            elif path.endswith("/readweave/generation-jobs"):
                if route.request.method == "GET":
                    pending.append(route)
                elif urlsplit(route.request.url).query == "delay=1":
                    mutations.append(route)
                else:
                    route.fulfill(json={"saved": True})
            else:
                file = ROOT / path.lstrip("/")
                if file.is_file():
                    route.fulfill(path=str(file))
                else:
                    route.fulfill(status=404)

        page.route(BASE + "/**", route)
        page.goto(BASE)
        page.wait_for_function("typeof window.panelRequest==='function'")
        yield page, pending, errors, mutations
        page.evaluate("window.reader.unmount()")
        browser.close()


def _start_get(page, name):
    page.evaluate("name=>{window[name]=window.panelRequest('readweave/generation-jobs').then(value=>{window[name+'Result']=value;},error=>{window[name+'Error']=error.message;});}", name)


def test_panel_shares_only_current_get_and_releases_after_completion(shared_request_page):
    page, pending, errors, _ = shared_request_page
    _start_get(page, "first")
    _start_get(page, "second")
    page.wait_for_timeout(120)
    assert len(pending) == 1
    pending.pop().fulfill(json={"revision": 1})
    page.wait_for_function("window.firstResult?.revision===1 && window.secondResult?.revision===1")
    _start_get(page, "third")
    page.wait_for_timeout(120)
    assert len(pending) == 1
    pending.pop().fulfill(json={"revision": 2})
    page.wait_for_function("window.thirdResult?.revision===2")
    assert errors == []


def test_mutation_starts_fresh_get_and_old_completion_keeps_new_get(shared_request_page):
    page, pending, errors, _ = shared_request_page
    _start_get(page, "beforeSave")
    page.wait_for_timeout(100)
    assert len(pending) == 1
    old = pending.pop()
    page.evaluate("window.panelRequest('readweave/generation-jobs',{method:'POST',body:'{}'})")
    _start_get(page, "afterSave")
    page.wait_for_timeout(100)
    assert len(pending) == 1
    old.fulfill(json={"revision": 1})
    page.wait_for_function("window.beforeSaveResult?.revision===1")
    _start_get(page, "sameNewRead")
    page.wait_for_timeout(100)
    assert len(pending) == 1
    pending.pop().fulfill(json={"revision": 2})
    page.wait_for_function("window.afterSaveResult?.revision===2 && window.sameNewReadResult?.revision===2")
    assert errors == []


def test_get_during_save_is_not_reused_after_save_finishes(shared_request_page):
    page, pending, errors, mutations = shared_request_page
    page.evaluate("() => {window.save=window.panelRequest('readweave/generation-jobs?delay=1',{method:'POST',body:'{}'}).then(()=>{window.saved=true;});}")
    page.wait_for_timeout(100)
    assert len(mutations) == 1
    _start_get(page, "duringSave")
    page.wait_for_timeout(100)
    assert len(pending) == 1
    old = pending.pop()
    mutations.pop().fulfill(json={"saved": True})
    page.wait_for_function("window.saved===true")
    _start_get(page, "afterSaveFinishes")
    page.wait_for_timeout(100)
    assert len(pending) == 1
    old.fulfill(json={"revision": 1})
    page.wait_for_function("window.duringSaveResult?.revision===1")
    _start_get(page, "anotherSavedRead")
    page.wait_for_timeout(100)
    assert len(pending) == 1
    pending.pop().fulfill(json={"revision": 2})
    page.wait_for_function("window.afterSaveFinishesResult?.revision===2 && window.anotherSavedReadResult?.revision===2")
    assert errors == []


def test_failed_get_is_not_reused_on_the_next_read(shared_request_page):
    page, pending, errors, _ = shared_request_page
    _start_get(page, "failedRead")
    page.wait_for_timeout(100)
    pending.pop().fulfill(status=503, json={"error": "test unavailable"})
    page.wait_for_function("window.failedReadError==='test unavailable'")
    _start_get(page, "nextRead")
    page.wait_for_timeout(100)
    assert len(pending) == 1
    pending.pop().fulfill(json={"revision": 3})
    page.wait_for_function("window.nextReadResult?.revision===3")
    assert errors == []


def test_timer_waits_for_refresh_but_manual_action_starts_its_own_refresh():
    pending, errors, counts = [], [], {"jobs": 0}
    library = {"folders": [{"id": "root", "name": "文件", "parent_id": None}], "projects": []}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.clock.install()
        page.on("pageerror", lambda error: errors.append(str(error)))

        def route(route):
            path = urlsplit(route.request.url).path
            if path == "/workspace":
                route.fulfill(path=str(ROOT / "web/workspace.html"))
            elif path == "/api/jobs":
                counts["jobs"] += 1
                if counts["jobs"] == 1:
                    route.fulfill(json=[], content_type="application/json")
                else:
                    pending.append(route)
            elif path == "/api/library":
                route.fulfill(json=library)
            elif path == "/api/projects":
                route.fulfill(json=[], content_type="application/json")
            elif path == "/api/folders":
                row = {"id": "created", "name": "手动创建", "parent_id": "root"}
                library["folders"].append(row)
                route.fulfill(json=row)
            elif path == "/api/system":
                route.fulfill(json={}, content_type="application/json")
            elif path.endswith("/reader-component.js"):
                route.fulfill(body="export const mountReader=()=>({});", content_type="text/javascript")
            elif path.endswith("/artifact-tree.js"):
                route.fulfill(body="export const mountArtifactTree=()=>({});", content_type="text/javascript")
            else:
                file = ROOT / "web" / path.lstrip("/")
                if file.is_file():
                    route.fulfill(path=str(file))
                else:
                    route.fulfill(status=404)

        page.route(BASE + "/**", route)
        page.goto(BASE + "/workspace")
        page.wait_for_function("!document.documentElement.hasAttribute('data-app-loading')")
        page.clock.run_for(2000)
        page.wait_for_timeout(100)
        assert counts["jobs"] == 2, (counts, errors, page.locator("#work-status").inner_text())
        page.clock.run_for(4000)
        page.wait_for_timeout(100)
        assert counts["jobs"] == 2, (counts, errors, page.locator("#work-status").inner_text())
        page.locator("#new-folder").click()
        page.locator("#action-name").fill("手动创建")
        page.locator("#action-confirm").click()
        page.wait_for_timeout(100)
        assert counts["jobs"] == 3
        pending.pop(0).fulfill(json=[], content_type="application/json")
        page.clock.run_for(2000)
        page.wait_for_timeout(100)
        assert counts["jobs"] == 3
        pending.pop(0).fulfill(json=[], content_type="application/json")
        page.wait_for_function("document.querySelector('[data-id=created]')!==null")
        page.clock.run_for(2000)
        page.wait_for_timeout(100)
        assert counts["jobs"] == 4
        pending.pop(0).fulfill(status=503, json={"error": "test unavailable"})
        page.wait_for_function("document.querySelector('#work-status').textContent==='test unavailable'")
        page.clock.run_for(2000)
        page.wait_for_timeout(100)
        assert counts["jobs"] == 5
        pending.pop(0).fulfill(json=[], content_type="application/json")
        assert errors == []
        browser.close()
