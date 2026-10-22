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
    helpers = """const get=id=>document.getElementById(id);
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
