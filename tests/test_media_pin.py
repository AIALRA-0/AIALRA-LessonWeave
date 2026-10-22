"""用真实浏览器检查素材固定、自动解除和原有交互，不调用模型"""
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright

READER = Path(__file__).resolve().parents[1] / 'framework/reader'
RESOURCES = json.loads((READER.parent / 'examples/media/resources.json').read_text('utf8'))


@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1200, 'height': 850})
        page.set_default_timeout(4000)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        html = '''<!doctype html><meta charset="utf-8"><style>
          body{margin:0;background:#eee}.demo-explanation{position:absolute;inset:40px 150px 30px;overflow:auto;background:white}
          .pane-head{position:sticky;top:0;height:48px;background:white;z-index:5}
          article{padding:0 30px}.intro,.between{height:900px}figure{box-sizing:border-box}
        </style><link rel="stylesheet" href="/media-renderer.css">
        <main class="demo-explanation"><div class="pane-head">讲解</div><article>
        <div class="intro">开始阅读</div><div id="first"></div><div class="between">继续读正文</div>
        <div class="writing-block" data-media-kind="table" style="display:none">隐藏的系统信息</div>
        <div id="second" class="writing-block" data-media-kind="table"><table><tr><td>下一份素材</td></tr></table></div>
        <div class="between">最后的文字</div></article></main>
        <script src="/reading-icons.js"></script><script src="/media-renderer.js"></script>'''
        def route(request):
            path = READER / urlsplit(request.request.url).path.lstrip('/')
            if path.is_file():
                request.fulfill(path=str(path))
            else:
                request.fulfill(body=html, content_type='text/html')
        page.route('http://reader.test/**', route)
        page.goto('http://reader.test/')
        yield page
        assert errors == []
        browser.close()


def render(page, kind):
    resource = next(r for r in RESOURCES if r['kind'] == kind)
    page.evaluate('''resource=>{
      const image=()=>{const img=document.createElement('img');img.src='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="240"><rect width="400" height="240" fill="steelblue"/></svg>');return img};
      document.querySelector('#first').append(LessonMedia.render(resource,{image,path:()=> 'data:text/html,<button>Try</button>'}));
    }''', resource)
    page.locator('.lw-media-figure').scroll_into_view_if_needed()


@pytest.mark.parametrize('kind', ['image', 'table', 'formula', 'code', 'interactive'])
def test_pin_survives_text_then_releases_at_next_media(page, kind):
    render(page, kind)
    pin = page.locator('button[data-icon=pin]')
    pin.click()
    figure = page.locator('.lw-media-figure')
    assert pin.get_attribute('aria-pressed') == 'true'
    top = figure.bounding_box()['y']
    page.locator('.demo-explanation').evaluate('(node)=>node.scrollTop+=350')
    page.wait_for_timeout(50)
    assert abs(figure.bounding_box()['y'] - top) < 1
    assert pin.get_attribute('aria-pressed') == 'true'
    if kind == 'interactive':
        page.frame_locator('.lw-media iframe').get_by_role('button', name='Try').click()
    page.locator('.demo-explanation').evaluate('node=>{const next=document.querySelector("#second");node.scrollTop+=next.getBoundingClientRect().top-node.getBoundingClientRect().top-120}')
    page.wait_for_timeout(50)
    assert pin.get_attribute('aria-pressed') == 'false'
    assert page.locator('.lw-media-pin-placeholder').count() == 0


def test_manual_unpin_resize_expand_and_navigation_keep_content(page):
    render(page, 'code')
    original = page.locator('.lw-media-code-lines').text_content()
    pin = page.locator('button[data-icon=pin]')
    pin.click()
    page.set_viewport_size({'width': 1000, 'height': 850})
    page.wait_for_timeout(50)
    assert abs(page.locator('.lw-media-figure').bounding_box()['width'] - page.locator('.lw-media-pin-placeholder').bounding_box()['width']) < 1
    pin.click()
    assert pin.get_attribute('aria-pressed') == 'false'
    page.get_by_role('button', name='显示或隐藏行注').click()
    assert page.locator('.lw-hide-notes').count() == 1
    pin.click()
    page.get_by_role('button', name='放大素材', exact=True).click()
    assert page.locator('.is-pinned').count() == 0
    page.get_by_role('button', name='返回阅读', exact=True).click()
    assert page.locator('.lw-media-code-lines').text_content() == original
    pin.click()
    page.evaluate('document.dispatchEvent(new CustomEvent("reading:document-ready"))')
    assert pin.get_attribute('aria-pressed') == 'false'
    pin.click()
    page.evaluate('document.querySelector("#first").replaceChildren()')
    page.wait_for_timeout(50)
    assert page.locator('.is-pinned,.lw-media-pin-placeholder').count() == 0


def test_toolbar_uses_named_icons_and_pin_is_off_initially(page):
    render(page, 'image')
    buttons = page.locator('.lw-media-toolbar button')
    assert buttons.count() == 3
    for button in buttons.all():
        assert button.locator('svg').count() == 1
        assert button.get_attribute('aria-label') == button.get_attribute('data-tooltip')
        assert button.inner_text() == ''
    assert page.locator('.lw-media-figure').evaluate('node=>getComputedStyle(node).position') == 'sticky'


def test_media_toolbar_keeps_36px_buttons_20px_icons_and_8px_gaps_on_narrow_screen(page):
    page.set_viewport_size({'width': 320, 'height': 720})
    render(page, 'image')
    metrics = page.locator('.lw-media-toolbar').evaluate('''toolbar=>({
      gap:getComputedStyle(toolbar).columnGap,
      buttons:[...toolbar.querySelectorAll('.lw-media-action')].map(button=>{
        const rect=button.getBoundingClientRect();
        const icon=button.querySelector('svg');
        const style=icon&&getComputedStyle(icon);
        return {width:rect.width,height:rect.height,iconWidth:style?.width,iconHeight:style?.height,left:rect.left,right:rect.right};
      })
    })''')

    assert metrics['gap'] == '8px'
    assert len(metrics['buttons']) == 3
    assert all(
        button['width'] == 36 and button['height'] == 36
        and button['iconWidth'] == '20px' and button['iconHeight'] == '20px'
        for button in metrics['buttons']
    )
    assert all(
        right['left'] - left['right'] >= 8
        for left, right in zip(metrics['buttons'], metrics['buttons'][1:])
    )


@pytest.mark.parametrize('kind', ['image', 'formula'])
def test_media_stays_visible_inside_its_own_explanation_without_pressing_pin(page, kind):
    render(page, kind)
    page.wait_for_function("document.querySelector('.lw-media-figure').dataset.fitted === 'true'")
    page.locator('.lw-media').evaluate('node=>{const explanation=document.createElement("p");explanation.textContent="继续沿这份素材阅读";explanation.style.height="900px";node.append(explanation)}')
    figure = page.locator('.lw-media-figure')
    page.locator('.demo-explanation').evaluate('node=>node.scrollTop+=400')
    page.wait_for_timeout(50)
    before = figure.bounding_box()['y']
    page.locator('.demo-explanation').evaluate('node=>node.scrollTop+=200')
    page.wait_for_timeout(50)
    assert abs(figure.bounding_box()['y'] - before) < 1
    assert page.locator('button[data-icon=pin]').get_attribute('aria-pressed') == 'false'
    page.locator('.demo-explanation').evaluate('node=>{const next=document.querySelector("#second");node.scrollTop+=next.getBoundingClientRect().top-node.getBoundingClientRect().top-70}')
    page.wait_for_timeout(50)
    assert figure.bounding_box()['y'] < before
