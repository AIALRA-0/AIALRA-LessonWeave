"""用独立浏览器检查真实工作台、目录操作和源码范围，不调用生成模型"""
from pathlib import Path
import json
import os
import time
from playwright.sync_api import sync_playwright

BASE=os.environ.get('LESSONWEAVE_TEST_URL','http://127.0.0.1:8962')
OUT=Path(os.environ['LESSONWEAVE_EVIDENCE']);OUT.mkdir(parents=True,exist_ok=True)
results=[]
def check(name,passed,**details):
    results.append({'name':name,'passed':bool(passed),**details})

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,**({'executable_path':os.environ['LESSONWEAVE_BROWSER']} if os.environ.get('LESSONWEAVE_BROWSER') else {}))
    headers={}
    if os.environ.get('LESSONWEAVE_TEST_ENV_FILE'):
        settings=dict(line.split('=',1) for line in Path(os.environ['LESSONWEAVE_TEST_ENV_FILE']).read_text().splitlines() if '=' in line)
        headers={'X-Aialra-User':settings['LESSONWEAVE_OWNER']}
    page=browser.new_page(viewport={'width':1700,'height':1050},extra_http_headers=headers)
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    candidates=page.request.get(BASE+'/api/projects').json()
    chosen=os.environ.get('LESSONWEAVE_TEST_PROJECTS','').split(',')
    samples=[item for item in candidates if item['id'] in chosen] if chosen!=[''] else candidates
    sample=next((item for item in samples if item['ready'] and not item['legacy']),next(item for item in samples if item['ready']))
    page.goto(BASE+'/workspace?project='+sample['id'])
    page.wait_for_selector('.writing-unit',timeout=45000)
    check('工作台原生挂载读本',page.locator('#reader').evaluate('(host)=>!!host.shadowRoot && !host.querySelector("iframe")'))
    check('默认中性配色',page.evaluate('getComputedStyle(document.body).backgroundColor') in {'rgb(238, 238, 236)','rgb(20, 20, 20)'})
    page.screenshot(path=str(OUT/'workspace-desktop.png'))
    page.get_by_role('button',name='新建文件夹',exact=True).click()
    first_name='界面验证-'+str(time.time_ns())[-7:]
    page.locator('#action-name').fill(first_name)
    page.locator('#action-parent').select_option('root')
    with page.expect_response(lambda r:'/api/folders' in r.url and r.request.method=='POST') as response:
        page.locator('#action-confirm').click()
    first=response.value.json()
    page.wait_for_selector('.tree-row[data-id="'+first['id']+'"]')
    check('新建文件夹实际保存',first['name']==first_name)
    page.locator('#rename').click();page.locator('#action-name').fill('验证归档')
    page.locator('#action-confirm').click();page.wait_for_function("()=>!document.querySelector('#action-dialog').open")
    check('重命名实际保存',next(item for item in page.request.get(BASE+'/api/library').json()['folders'] if item['id']==first['id'])['name']=='验证归档')
    page.get_by_role('button',name='新建文件夹',exact=True).click();page.locator('#action-name').fill('验证上级');page.locator('#action-parent').select_option('root')
    with page.expect_response(lambda r:'/api/folders' in r.url and r.request.method=='POST') as response:
        page.locator('#action-confirm').click()
    parent=response.value.json()
    page.wait_for_selector('.tree-row[data-id="'+parent['id']+'"]')
    page.locator('.tree-row[data-id="'+first['id']+'"]').click();page.locator('#move').click();page.locator('#action-parent').select_option(parent['id']);page.locator('#action-confirm').click();page.wait_for_function("()=>!document.querySelector('#action-dialog').open")
    check('移动实际保存',next(item for item in page.request.get(BASE+'/api/library').json()['folders'] if item['id']==first['id'])['parent_id']==parent['id'])
    page.locator('#trash').click();page.locator('#action-confirm').click();page.wait_for_function("()=>!document.querySelector('#action-dialog').open")
    page.locator('#show-trash').click();page.locator('.trash-row').filter(has_text='验证归档').get_by_role('button',name='恢复',exact=True).click()
    page.wait_for_timeout(300)
    check('回收站恢复保留位置',not next(item for item in page.request.get(BASE+'/api/library').json()['folders'] if item['id']==first['id'])['deleted'])
    page.request.post(BASE+'/api/library/folder/'+parent['id']+'/trash',data={})
    page.goto(BASE+'/workspace?project='+sample['id']);page.wait_for_selector('.writing-unit')
    toggle=page.locator('.tree-row[data-kind="project"][data-id="'+sample['id']+'"] .tree-toggle');toggle.click()
    page.locator('.tree-row[data-id="'+sample['id']+':questions"]').click()
    page.wait_for_selector('#reader section details')
    page.wait_for_timeout(2500)
    check('阶段树在刷新后保持显示',page.locator('#reader section details').count()>0 and page.locator('.writing-unit').count()==0)
    page.locator('.tree-row[data-id="'+sample['id']+':reading"]').click();page.wait_for_selector('.writing-unit')
    page.locator('#new-project').click();page.locator('#generate-folder').select_option('root')
    check('生成窗口可以指定目标目录',page.locator('#generate-folder').input_value()=='root')
    page.get_by_role('button',name='关闭生成窗口',exact=True).click()
    page.locator('#theme').click();page.screenshot(path=str(OUT/'workspace-theme.png'))
    check('工作台主题切换',page.evaluate('getComputedStyle(document.body).backgroundColor') in {'rgb(238, 238, 236)','rgb(20, 20, 20)'})
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(200)
    if not page.locator('body').evaluate("el=>el.classList.contains('library-collapsed')"):
        page.locator('#toggle-library').click()
    page.screenshot(path=str(OUT/'workspace-mobile.png'))
    check('窄屏没有整体横向溢出',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    page.locator('#toggle-library').click();check('窄屏可以找回材料树',page.locator('#library').is_visible())
    page.set_viewport_size({'width':1700,'height':1050})
    code=next((item for item in candidates if item['id']=='original-code'),None)
    if code:
        page.goto(BASE+'/p/'+code['id']+'/book.html?preview=true')
        page.wait_for_selector('.writing-unit',timeout=45000)
        page.wait_for_function("()=>{const f=document.querySelector('#locator-dom');return f?.contentDocument?.querySelector('mark[data-locator-mark]')}",timeout=30000)
        for zoom in ['60','150','300']:
            page.locator('[data-locator-zoom-select]').first.select_option(zoom)
            page.wait_for_timeout(250)
            result=page.locator('#locator-dom').evaluate('''frame=>{const d=frame.contentDocument,marks=[...d.querySelectorAll('mark[data-locator-mark]')];return {marks:marks.length,text:marks.map(node=>node.textContent).join(''),wholeRows:d.querySelectorAll('.code-line.location-selected').length,aligned:marks.every(node=>{const range=d.createRange();range.selectNodeContents(node);const a=node.getBoundingClientRect(),b=range.getBoundingClientRect();return Math.abs(a.left-b.left)<1&&Math.abs(a.right-b.right)<1})}}''')
            check('源码 '+zoom+'% 按字符对齐',result['marks']>0 and result['wholeRows']==0 and result['aligned'],marks=result['marks'])
        page.screenshot(path=str(OUT/'code-location.png'))
    browser.close()
report={'checks':results,'page_errors':errors,'passed':all(row['passed'] for row in results) and not errors}
(OUT/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(report,ensure_ascii=False))
