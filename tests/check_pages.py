"""在独立的无头浏览器中验证正式页面，截图与检查记录保存到指定证据目录"""
from pathlib import Path
import json
import os
from playwright.sync_api import sync_playwright

BASE=os.environ.get('LESSONWEAVE_TEST_URL','http://127.0.0.1:8960')
OUT=Path(os.environ['LESSONWEAVE_EVIDENCE'])
OUT.mkdir(parents=True,exist_ok=True)
records=[]


def record(name,passed,**details):
    records.append({'name':name,'passed':bool(passed),**details})


with sync_playwright() as playwright:
    browser=playwright.chromium.launch(headless=True,**({'executable_path':os.environ['LESSONWEAVE_BROWSER']} if os.environ.get('LESSONWEAVE_BROWSER') else {}))
    headers={}
    if os.environ.get('LESSONWEAVE_TEST_ENV_FILE'):
        settings=dict(line.split('=',1) for line in Path(os.environ['LESSONWEAVE_TEST_ENV_FILE']).read_text().splitlines() if '=' in line)
        headers={'X-Aialra-User':settings['LESSONWEAVE_OWNER']}
    page=browser.new_page(viewport={'width':1600,'height':1050},device_scale_factor=1,extra_http_headers=headers)
    page.route('**/*',lambda route:route.continue_() if route.request.url.startswith((BASE,'data:','blob:')) else route.abort())
    failures=[]
    page.on('pageerror',lambda error:failures.append(str(error)))
    page.goto(BASE+'/?demo=1')
    page.wait_for_selector('.project-card')
    record('workbench',page.locator('h1').inner_text().startswith('把手边的材料'))
    page.screenshot(path=str(OUT/'workbench-light.png'),full_page=True)
    page.get_by_role('button',name='切换明暗主题').click()
    page.screenshot(path=str(OUT/'workbench-dark.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(OUT/'workbench-mobile.png'),full_page=True)
    record('workbench-mobile',page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
    page.set_viewport_size({'width':1600,'height':1050})
    projects=page.request.get(BASE+'/api/projects').json()
    ready=[project for project in projects if project['ready'] and not project['legacy']]
    if os.environ.get('LESSONWEAVE_TEST_PROJECTS'):
        ids=os.environ['LESSONWEAVE_TEST_PROJECTS'].split(',')
        ready=[project for project in projects if project['ready'] and project['id'] in ids]
    if not ready:
        ready=[project for project in projects if project['ready']]
    for project in ready:
        for view in ['book.html','readweave.html']:
            before=len(failures)
            page.goto(BASE+'/p/'+project['id']+'/'+view+'?preview=true')
            try:
                page.wait_for_selector('.writing-unit',timeout=45000)
                units=page.locator('.writing-unit').count()
                record(project['id']+'-'+view,units>0 and len(failures)==before,units=units,errors=failures[before:])
                if not project['legacy']:
                    page.screenshot(path=str(OUT/(project['id']+'-'+view+'.png')))
                if view=='readweave.html':
                    record(project['id']+'-native-component',page.locator('#reader').evaluate('(host)=>!!host.shadowRoot && !host.shadowRoot.querySelector("iframe.reader-frame")'))
                toggle=page.get_by_role('button',name='切换深色主题')
                if toggle.count():
                    toggle.click()
                    record(project['id']+'-theme',True)
                source=page.locator('#locator-sentence-select')
                try:
                    source.locator('option').first.wait_for(state='attached',timeout=15000)
                except Exception:
                    pass
                record(project['id']+'-source-sentences',source.locator('option').count()>0)
                zoom=page.locator('[data-locator-zoom-select]').first
                zoom.select_option('150')
                record(project['id']+'-zoom',zoom.input_value()=='150')
                debug=page.locator('#show-debug')
                record(project['id']+'-debug-default',not debug.is_checked())
                if not project['legacy']:
                    prefix=project['id']+'-'+view
                    term=page.locator('#demo-content .inline-term').first
                    term_id=term.get_attribute('data-term-id')
                    term.hover()
                    target=page.locator('.glossary-entry[data-term-id="'+term_id+'"]')
                    target.wait_for(state='visible')
                    page.wait_for_timeout(250)
                    record(prefix+'-term-hover',target.evaluate('(item)=>item.open') and page.locator('.glossary-entry:visible').count()==1)
                    page.mouse.move(3,3)
                    page.wait_for_timeout(450)
                    record(prefix+'-term-restore',page.locator('.glossary-entry:visible').count()>1)
                    marker=page.locator('.source-marker:not(.debug-only)').first
                    marker.click()
                    page.wait_for_timeout(500)
                    record(prefix+'-source-link',marker.get_attribute('aria-pressed')=='true')
                    source.locator('option').first.wait_for(state='attached')
                    if source.locator('option').count()>1:
                        source.select_option(index=1)
                    page.wait_for_timeout(500)
                    record(prefix+'-translation-highlight',page.locator('.source-sentence-pair.is-locator-selected').count()>0)
                    splitter=page.locator('#source-splitter')
                    prior=splitter.get_attribute('aria-valuenow')
                    splitter.focus()
                    splitter.press('ArrowDown')
                    page.wait_for_timeout(120)
                    record(prefix+'-vertical-split',prior!=splitter.get_attribute('aria-valuenow'))
                    handle=page.locator('[data-resize-pane="source"]')
                    if handle.count():
                        before=page.locator('#demo-original').bounding_box()['width']
                        handle.focus()
                        handle.press('ArrowRight')
                        page.wait_for_timeout(120)
                        record(prefix+'-column-resize',before!=page.locator('#demo-original').bounding_box()['width'])
                    quiz=page.locator('.quiz-card').first
                    quiz.locator('input[type="radio"]').first.check()
                    quiz.get_by_role('button',name='核对答案',exact=True).click()
                    record(prefix+'-quiz',quiz.locator('.quiz-answer').is_visible())
                    note=page.locator('.writing-note').first
                    field=note.locator('textarea')
                    previous=field.input_value()
                    field.fill('我会沿着原材料核对这一步的条件与结果')
                    with page.expect_response(lambda response:'/api/notes/' in response.url and response.request.method=='POST') as saved:
                        note.get_by_role('button',name='保存笔记').click()
                    record(prefix+'-note-save',saved.value.ok)
                    page.reload()
                    page.wait_for_selector('.writing-unit')
                    field=page.locator('.writing-note textarea').first
                    page.wait_for_function('()=>{const h=document.querySelector("#reader");const d=h?.shadowRoot||document;return d.querySelector(".writing-note textarea")?.value==="我会沿着原材料核对这一步的条件与结果"}')
                    record(prefix+'-note-restore',True)
                    field.fill(previous)
                    with page.expect_response(lambda response:'/api/notes/' in response.url and response.request.method=='POST'):
                        page.locator('.writing-note').first.get_by_role('button',name='保存笔记').click()
                page.set_viewport_size({'width':390,'height':844})
                page.screenshot(path=str(OUT/(project['id']+'-'+view+'-mobile.png')))
                record(project['id']+'-mobile',page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'))
                page.set_viewport_size({'width':1600,'height':1050})
            except Exception as error:
                record(project['id']+'-'+view,False,error=str(error),errors=failures[before:])
                page.screenshot(path=str(OUT/(project['id']+'-'+view+'-error.png')))
    browser.close()
result={'checks':records,'page_errors':failures,'passed':all(row['passed'] for row in records)}
(OUT/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(result,ensure_ascii=False))
