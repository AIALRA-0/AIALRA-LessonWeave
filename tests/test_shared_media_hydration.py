"""浏览器读取共享改稿后，只补媒体工具，不把旧 JSON 内容写回去"""
import copy
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright

READER = Path(__file__).resolve().parents[1] / 'framework/reader'
RESOURCES = json.loads((READER.parent / 'examples/media/resources.json').read_text('utf-8'))


@pytest.fixture
def shared_media_page():
    blocks = [copy.deepcopy(next(row for row in RESOURCES if row['kind'] == kind))
              for kind in ('table', 'formula', 'mermaid', 'image', 'code')]
    for row in blocks:
        row['id'] = row['kind']
        row['caption'] = '旧的图注'
    source = (READER / 'writing-demo.js').read_text('utf-8')
    hydration = source[source.index('  function hydrateSharedMedia(element)'):source.index('  function updateGlossary(terms)')]
    html = '''<!doctype html><meta charset="utf-8"><main id="shared"></main>
      <script src="/reading-icons.js"></script><script src="/math-text.js"></script>
      <script src="/reader-text.js"></script><script src="/media-renderer.js"></script>
      <script>
      (function(window){
      const data={units:[{explanation:BLOCKS}]};
      const make=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node};
      const mediaPlacement=()=>({prefix:'2.1',index:1}),projectPath=value=>value,imageRegion=()=>null;
      const sourceImage=(asset,alt)=>{const img=document.createElement('img');img.src=asset;img.alt=alt;return img};
      HYDRATION
      globalThis.hydrate=async()=>{hydrateSharedMedia(document.querySelector('#shared'));await ReaderText.renderIn(document.querySelector('#shared'));};
      })({LessonMedia:globalThis.LessonMedia,ReaderText:globalThis.ReaderText});
      delete globalThis.LessonMedia;
      </script>'''.replace('BLOCKS', json.dumps(blocks, ensure_ascii=False)).replace('HYDRATION', hydration)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={'width': 1200, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        def route(request):
            name = urlsplit(request.request.url).path
            if name == '/':request.fulfill(body=html, content_type='text/html');return
            path = READER / name.lstrip('/')
            if path.is_file():request.fulfill(path=str(path));return
            request.fulfill(status=404, body='')
        page.route('http://reader.test/**', route)
        page.goto('http://reader.test/')
        yield page
        assert errors == []
        browser.close()


def test_shared_table_keeps_current_cells_format_math_and_caption(shared_media_page):
    page = shared_media_page
    result = page.evaluate(r'''async()=>{
      const root=document.querySelector('#shared');root.innerHTML='<div data-shared-media="table">当前旁注<table><tbody><tr><td><strong>读者刚改的值</strong> \\(v_2=7\\)</td></tr></tbody></table><p>读者的新图注 <em>格式也保留</em></p></div>';
      const original=root.querySelector('table');await hydrate();
      return {sameTable:root.querySelector('table')===original,value:root.querySelector('td').textContent,strong:root.querySelector('td strong')?.textContent,caption:root.querySelector('figcaption')?.textContent,captionEm:root.querySelector('figcaption em')?.textContent,katex:root.querySelectorAll('td .katex').length,audit:ReaderText.audit(root),toolbar:root.querySelectorAll('.lw-media-toolbar').length,note:root.textContent.includes('当前旁注')};
    }''')
    assert result['sameTable']
    assert result['strong'] == '读者刚改的值'
    assert '读者的新图注' in result['caption'] and result['captionEm'] == '格式也保留'
    assert result['katex'] == 1 and result['audit']['errors'] == []
    assert result['toolbar'] == 1
    assert result['note']


def test_shared_formula_diagram_image_and_deleted_visual_use_current_content(shared_media_page):
    page = shared_media_page
    result = page.evaluate(r'''async()=>{
      const root=document.querySelector('#shared');root.innerHTML='<div data-shared-media="formula"><div class="math-tex" data-lw-formula="true">x^2+3</div><p>新的公式图注</p></div><div data-shared-media="mermaid"><pre>graph TD; A[当前起点]-->B[当前终点]</pre><p>新的图表图注</p></div><div data-shared-media="image"><img alt="读者的新替代文字" src="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2220%22 height=%2220%22/%3E"><p>新的图片图注</p></div><div data-shared-media="code"><pre><code>print("current")</code></pre><p>新的代码图注</p></div><div data-shared-media="table" id="deleted"><p>用户已删表，只保留这句话</p></div>';
      await hydrate();
      const diagram=root.querySelector('[data-shared-media="mermaid"] .lw-media-mermaid');if(diagram?.mediaReady)await diagram.mediaReady;
      const firstFigure=root.querySelector('.lw-media-figure');await hydrate();
      return {formula:root.querySelector('[data-shared-media="formula"] [data-math-source]')?.dataset.mathSource,formulaCaption:root.querySelector('[data-shared-media="formula"] figcaption')?.textContent,diagram:diagram?.textContent,diagramCaption:root.querySelector('[data-shared-media="mermaid"] figcaption')?.textContent,imageAlt:root.querySelector('img')?.alt,imageCaption:root.querySelector('[data-shared-media="image"] figcaption')?.textContent,code:[...root.querySelectorAll('[data-shared-media="code"] .lw-media-code-row code')].map(node=>node.textContent).join('\n'),codeCaption:root.querySelector('[data-shared-media="code"] figcaption')?.textContent,deleted:document.querySelector('#deleted').innerHTML,sameFigure:firstFigure===root.querySelector('.lw-media-figure'),figures:root.querySelectorAll('.lw-media-figure').length,audit:ReaderText.audit(root)};
    }''')
    assert result['formula'] == 'x^2+3'
    assert '新的公式图注' in result['formulaCaption']
    assert '当前起点' in result['diagram'] and '当前终点' in result['diagram']
    assert '新的图表图注' in result['diagramCaption']
    assert result['imageAlt'] == '读者的新替代文字' and '新的图片图注' in result['imageCaption']
    assert result['code'] == 'print("current")' and '新的代码图注' in result['codeCaption']
    assert result['deleted'] == '<p>用户已删表，只保留这句话</p>'
    assert result['sameFigure'] and result['figures'] == 4
    assert result['audit']['errors'] == []


def test_removing_shared_visual_or_caption_does_not_restore_old_content(shared_media_page):
    page = shared_media_page
    result = page.evaluate(r'''async()=>{
      const root=document.querySelector('#shared');
      root.innerHTML=['table','formula','mermaid','image','code'].map(kind=>'<div data-shared-media="'+kind+'"><p>保留读者这句话</p></div>').join('')+'<div data-shared-media="formula" id="no-caption"><div class="math-tex">y+5</div></div>';
      await hydrate();
      return {deleted:[...root.querySelectorAll('[data-shared-media]')].slice(0,5).map(node=>node.innerHTML),caption:root.querySelector('#no-caption figcaption'),formula:root.querySelector('#no-caption [data-math-source]')?.dataset.mathSource};
    }''')
    assert result['deleted'] == ['<p>保留读者这句话</p>'] * 5
    assert result['caption'] is None and result['formula'] == 'y+5'


def test_legacy_formula_pre_renders_current_tex_instead_of_old_json(shared_media_page):
    result = shared_media_page.evaluate(r'''async tex=>{
      const root=document.querySelector('#shared');root.innerHTML='<div data-shared-media="formula"><pre data-lw-block="legacy-formula"></pre><p>旧库里刚改的公式</p></div>';
      root.querySelector('pre').textContent=tex;await hydrate();
      return {source:root.querySelector('[data-math-source]')?.dataset.mathSource,pre:root.querySelectorAll('pre').length,block:root.querySelector('[data-lw-block="legacy-formula"]')?.tagName,katex:root.querySelectorAll('.katex').length,audit:ReaderText.audit(root)};
    }''', r'\frac{7}{2}+x')
    assert result['source'] == r'\frac{7}{2}+x'
    assert result['pre'] == 0 and result['block'] == 'DIV' and result['katex'] == 1
    assert result['audit']['errors'] == []


@pytest.mark.parametrize('kind,caption,visual', [
    ('table', '表 3.2-7. 读者保留的编号', '<table><tr><td>当前值</td></tr></table>'),
    ('formula', '式3.2-8. 读者保留的编号', '<div class="math-tex">x+1</div>'),
    ('image', '图 3.2-9. 读者保留的编号', '<img alt="当前图片" src="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2220%22 height=%2220%22/%3E">'),
])
def test_shared_caption_keeps_existing_number_without_another_prefix(shared_media_page, kind, caption, visual):
    result = shared_media_page.evaluate(r'''async value=>{
      const root=document.querySelector('#shared');root.innerHTML='<div data-shared-media="'+value.kind+'">'+value.visual+'<p></p></div>';
      root.querySelector('p').textContent=value.caption;await hydrate();return root.querySelector('figcaption').textContent;
    }''', {'kind': kind, 'caption': caption, 'visual': visual})
    assert result == caption
