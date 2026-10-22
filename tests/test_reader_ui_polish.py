"""验证阅读器首屏、目录重建和窄屏控制的关键行为。"""
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def test_shared_body_outline_rebuilds_from_current_headings_without_rewriting_content():
    source = (ROOT / "framework/reader/writing-demo.js").read_text(encoding="utf-8")
    start = source.index("  function renderOutline() {")
    end = source.index("\n  async function loadGrounding() {", start)
    outline = source[start:end]
    html = """<!doctype html><meta charset="utf-8">
    <aside id="demo-directory"><nav id="demo-outline"><button>旧章节</button></nav></aside>
    <main><article id="demo-content" class="lw-shared-body">
      <h2 id="saved-heading" data-plain="共享标题"><span class="reader-math"><span class="katex"><span class="katex-mathml">共享标题</span><span class="katex-html">共享标题 x</span></span></span></h2>
      <h3 data-plain="子标题"><span class="reader-math"><span class="katex"><span class="katex-mathml">子标题</span><span class="katex-html">子标题 y</span></span></span></h3>
    </article></main>"""
    helpers = """const data={units:[]};const get=id=>document.getElementById(id);
    const make=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
    const openPane=()=>{};
    window.ReaderText={plain:node=>node.dataset.plain||node.textContent};
    """ + outline + "\nwindow.runOutline=renderOutline;"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html)
        page.add_script_tag(content=helpers)
        result = page.evaluate("""() => {
          const body=document.querySelector('.lw-shared-body');
          const before=[...body.querySelectorAll('.reader-math')].map(node=>node.outerHTML);
          runOutline();
          const first=[...document.querySelectorAll('#demo-outline button')].map(node=>node.textContent);
          const assigned=document.querySelector('.lw-shared-body h3').id;
          const clicked=[];
          const original=Element.prototype.scrollIntoView;
          Element.prototype.scrollIntoView=function(){clicked.push(this.id);};
          const entries=[...document.querySelectorAll('#demo-outline button')];
          entries[0].click();entries[1].click();
          Element.prototype.scrollIntoView=original;
          runOutline();
          const headings=[...body.querySelectorAll('h2,h3,h4,h5,h6')];
          return {
            first,
            second:[...document.querySelectorAll('#demo-outline button')].map(node=>node.textContent),
            count:document.querySelectorAll('#demo-outline button').length,
            targetIdsExist:headings.every(node=>!!node.id),
            clickTargets:clicked,
            clickTargetsExist:clicked.every(id=>headings.some(node=>node.id===id)),
            headingId:document.querySelector('.lw-shared-body h2').id,
            assigned,
            before,
            after:[...body.querySelectorAll('.reader-math')].map(node=>node.outerHTML),
            hasPrefix:document.querySelector('.lw-shared-body h3').dataset.readerPrefix
          };
        }""")
        browser.close()

    assert result["first"] == ["1. 共享标题", "1.1. 子标题"]
    assert result["second"] == result["first"]
    assert result["count"] == 2
    assert result["targetIdsExist"]
    assert result["clickTargets"] == ["saved-heading", "shared-heading-002"]
    assert result["clickTargetsExist"]
    assert result["headingId"] == "saved-heading"
    assert result["assigned"] == "shared-heading-002"
    assert result["hasPrefix"] == "1.1"
    assert result["after"] == result["before"]


def test_legacy_shared_heading_keeps_its_text_number_and_anchors_in_the_outline():
    source = (ROOT / "framework/reader/writing-demo.js").read_text(encoding="utf-8")
    start = source.index("  function renderOutline() {")
    outline = source[start:source.index("\n  async function loadGrounding() {", start)]
    html = '''<aside id="demo-directory"><nav id="demo-outline"></nav></aside>
    <article id="demo-content" class="lw-shared-body"><h2>内容讲解</h2>
    <p id="kept-anchor" data-lw-block="saved-heading">1.1.1.2. <em>当前讲解标题</em></p>
    <p data-lw-block="edited-heading">读者已改成自己的文字</p>
    <p data-lw-block="ordinary">1.2. 这仍然是正文</p></article>'''
    helpers = '''const data={units:[{explanation:[{id:'saved-heading',kind:'heading',text:'1.1.1.2. 当前讲解标题'},
      {id:'edited-heading',kind:'heading',text:'原来的标题'},{id:'ordinary',kind:'paragraph',text:'1.2. 这仍然是正文'}]}]};
    const get=id=>document.getElementById(id),openPane=()=>{};
    const make=(tag,text,cls)=>{const node=document.createElement(tag);node.textContent=text;node.className=cls;return node;};
    ''' + outline + '\nwindow.runOutline=renderOutline;'
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page()
        page.set_content(html)
        page.add_script_tag(content=helpers)
        result = page.evaluate('''()=>{
          const body=document.querySelector('#demo-content'),before=body.textContent,em=body.querySelector('em');
          runOutline();runOutline();
          const entry=[...document.querySelectorAll('#demo-outline button')].find(n=>n.textContent==='1.1.1.2. 当前讲解标题');
          let clicked;Element.prototype.scrollIntoView=function(){clicked=this.id;};entry?.click();
          return {sameText:before===body.textContent,sameEm:em===body.querySelector('em'),tag:document.querySelector('#kept-anchor').tagName,
            clicked,entries:[...document.querySelectorAll('#demo-outline button')].map(n=>n.textContent),
            protectedParagraphs:body.querySelectorAll('p').length};
        }''')
        browser.close()
    assert result['sameText'] and result['sameEm']
    assert result['tag'] == 'H4' and result['clicked'] == 'kept-anchor'
    assert result['entries'].count('1.1.1.2. 当前讲解标题') == 1
    assert result['protectedParagraphs'] == 2


def test_new_shared_heading_is_serialized_as_a_heading_without_changing_text():
    from lessonweave.trilium import block_html
    from bs4 import BeautifulSoup
    value = {'kind':'heading','id':'shared-heading','text':'1.1.1.2. 保留 x < y 的条件'}
    heading = BeautifulSoup(block_html(value), 'html.parser').find('h4')
    assert heading is not None and heading['data-lw-block'] == value['id']
    assert heading.get_text() == value['text']


def test_reader_startup_theme_toolbar_and_glossary_controls_have_one_clear_state():
    book = (ROOT / "framework/reader/book.html").read_text(encoding="utf-8")
    reader_css = (ROOT / "framework/reader/reading-ui.css").read_text(encoding="utf-8")
    workspace = (ROOT / "web/workspace.html").read_text(encoding="utf-8")
    architecture_css = (ROOT / "framework/architecture/compact.css").read_text(encoding="utf-8")

    assert book.index('src="/math-text.js"') < book.index('src="/reader-text.js')
    assert 'id="reader-startup"' in book and "data-reader-loading" in book
    first_view = book.split("</header>", 1)[0]
    assert first_view.count("<svg ") >= 7
    assert 'data-icon="directory" aria-label="隐藏目录" data-tooltip="显示或隐藏目录" aria-pressed="true"><svg' in first_view
    assert 'id="glossary-preview-caption"' not in book
    assert 'aria-label="返回全部术语" data-tooltip="返回全部术语"' in book
    assert "#focus-reading{display:none}" not in reader_css
    assert ".demo-header-actions{gap:0}" not in reader_css
    assert ".control-group{gap:0}" not in reader_css
    assert 'data-app-loading' in workspace and 'id="initial-loader"' in workspace
    assert "light-dark(" not in architecture_css
    assert ":root[data-theme=dark]" in architecture_css


def test_reader_toolbar_keeps_equal_buttons_and_eight_pixel_gaps_on_a_narrow_screen():
    css = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in (
        "framework/reader/reading-ui.css",
        "framework/reader/reader-polish.css",
    ))
    controls = """<header class="demo-masthead">
      <div class="document-heading"><h1>读本标题</h1></div>
      <div class="demo-header-actions">
        <div class="control-group"><button class="icon-button"><svg></svg></button><button class="icon-button"><svg></svg></button><button class="icon-button"><svg></svg></button></div>
        <div class="control-group"><button class="icon-button"><svg></svg></button><button class="icon-button"><svg></svg></button><button class="icon-button"><svg></svg></button></div>
      </div>
    </header>"""

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 320, "height": 720})
        page.set_content('<style>' + css + '</style><body class="reader-ui">' + controls + '</body>')
        mouse = page.evaluate("""() => ({
          boxes:[...document.querySelectorAll('.icon-button')].map(button=>{const r=button.getBoundingClientRect();return [r.width,r.height]}),
          icon:[...document.querySelectorAll('.icon-button svg')].map(svg=>[getComputedStyle(svg).width,getComputedStyle(svg).height]),
          gaps:[...document.querySelectorAll('.control-group')].map(group=>getComputedStyle(group).columnGap),
          groupGap:getComputedStyle(document.querySelector('.demo-header-actions')).columnGap,
          focusVisible:getComputedStyle(document.querySelectorAll('.icon-button')[3]).display
        })""")
        touch = browser.new_page(viewport={"width": 320, "height": 720}, has_touch=True)
        touch.set_content('<style>' + css + '</style><body class="reader-ui">' + controls + '</body>')
        touch_sizes = touch.locator(".icon-button").evaluate_all("nodes=>nodes.map(node=>{const r=node.getBoundingClientRect();return [r.width,r.height]})")
        browser.close()

    assert mouse["boxes"] == [[36, 36]] * 6
    assert mouse["icon"] == [["20px", "20px"]] * 6
    assert mouse["gaps"] == ["8px", "8px"]
    assert mouse["groupGap"] == "8px"
    assert mouse["focusVisible"] != "none"
    assert all(width == height and width >= 36 for width, height in touch_sizes)


def test_source_locator_tool_groups_keep_8px_gaps_and_36px_icon_buttons_on_a_narrow_screen():
    css = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in (
        "framework/reader/reading-ui.css",
        "framework/reader/reader-polish.css",
    ))
    controls = """<main id="demo-original">
      <header class="locator-heading">
        <select id="locator-view-select"><option>页面</option></select>
        <div class="locator-sentence-navigation">
          <button class="icon-button"><svg></svg></button><select id="locator-sentence-select"><option>1</option></select><button class="icon-button"><svg></svg></button>
        </div>
        <div class="locator-head-actions">
          <div class="locator-zoom-controls">
            <button class="icon-button"><svg></svg></button><select class="locator-zoom-select"><option>100%</option></select><button class="zoom-reset">适配</button><button class="icon-button"><svg></svg></button>
          </div>
          <button class="icon-button"><svg></svg></button><button class="icon-button"><svg></svg></button>
        </div>
      </header>
      <div class="material-heading"><h2>原件</h2><div class="source-view-actions"><button class="icon-button"><svg></svg></button><button class="icon-button"><svg></svg></button></div></div>
    </main>"""

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 320, "height": 720})
        page.set_content('<style>' + css + '</style><body class="reader-ui">' + controls + '</body>')
        metrics = page.evaluate("""() => {
          const measure=selector=>getComputedStyle(document.querySelector(selector)).columnGap;
          const buttons=[...document.querySelectorAll('#demo-original .locator-heading .icon-button, #demo-original .source-view-actions .icon-button')];
          return {
            gaps:['.locator-sentence-navigation','.locator-head-actions','.locator-zoom-controls','.source-view-actions'].map(measure),
            buttons:buttons.map(button=>{const rect=button.getBoundingClientRect();const icon=button.querySelector('svg');return [rect.width,rect.height,getComputedStyle(icon).width,getComputedStyle(icon).height]}),
            wrapped:getComputedStyle(document.querySelector('.locator-heading')).flexWrap
          };
        }""")
        browser.close()

    assert metrics["gaps"] == ["8px"] * 4
    assert metrics["buttons"] == [[36, 36, "20px", "20px"]] * 8
    assert metrics["wrapped"] == "wrap"
