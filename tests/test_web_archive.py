"""检查正式获取入口只执行一次抓取，并把归档文件与回放结果分开记录"""
from io import BytesIO
import json
from pathlib import Path
import sys
import threading
import urllib.error
import urllib.request
import zipfile

import fitz
from jsonschema import validate
from warcio.statusandheaders import StatusAndHeaders
from warcio.warcwriter import WARCWriter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'framework/00_source'))
import acquire
import web_archive
from lessonweave.server import Handler
from lessonweave.storage import Store
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
from PIL import Image


def test_pdf_keeps_original_bytes_without_creating_next_stage(tmp_path):
    original = tmp_path / 'input.pdf'
    with fitz.open() as document:
        document.new_page().insert_text((30, 30), 'Original PDF')
        document.save(original)
    root = tmp_path / 'project'
    result = acquire.acquire(root, {'kind': 'file', 'material': str(original)})
    assert result['integrity']['byte_for_byte_equal']
    assert (root / result['entry']).read_bytes() == original.read_bytes()
    assert not (root / '01_tree').exists()
    schema = Path(acquire.__file__).with_name('source.schema.json')
    validate(result, json.loads(schema.read_text('utf-8')))


def test_url_entry_uses_archive_adapter_and_does_not_rewrite_assets(tmp_path, monkeypatch):
    calls = []
    def capture(root, url, output):
        calls.append(url)
        (output / 'original.html').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding='utf-8')
        (output / 'original.wacz').write_bytes(b'archive')
        return {'web_archive': {'format': 'wacz'}}
    monkeypatch.setattr(web_archive, 'capture_web_archive', capture)
    root = tmp_path / 'project'
    result = acquire.acquire(root, {'kind': 'url', 'material': 'https://example.com/'})
    assert result['status'] == 'acquired' and calls == ['https://example.com/']
    assert not (root / result['entry']).with_name('offline.html').exists()
    assert not hasattr(acquire, 'complete_web_assets')
    assert not (root / '01_tree').exists()


def test_crawl_command_freezes_version_and_single_page_scope():
    command = web_archive.crawl_command('/tmp/crawls', 'one', 'https://example.com/')
    assert web_archive.IMAGE in command
    for name, value in [('--workers', '1'), ('--limit', '1'), ('--scopeType', 'page'), ('--behaviors', 'autoscroll,autofetch')]:
        assert command[command.index(name)+1] == value


def test_wacz_checks_http_failures_separately_from_file_integrity(tmp_path):
    stream = BytesIO()
    writer = WARCWriter(stream, gzip=True)
    for status in ('200 OK', '404 Not Found'):
        record = writer.create_warc_record('https://example.com/'+status[:3], 'response',
                    payload=BytesIO(b'original'), http_headers=StatusAndHeaders(status, [('Content-Type', 'text/html')], protocol='HTTP/1.1'))
        writer.write_record(record)
    target = tmp_path / 'original.wacz'
    with zipfile.ZipFile(target, 'w') as archive:
        archive.writestr('datapackage.json', json.dumps({'resources': [{'path': 'archive/page.warc.gz'}]}))
        archive.writestr('archive/page.warc.gz', stream.getvalue())
    result = web_archive.inspect_wacz(target)
    assert result['zip_crc_valid'] and result['manifest_members_present']
    assert len(result['http_failures']) == 1 and result['http_failures'][0]['status'] == 404


def test_archive_http_routes_support_ranges_and_keep_project_boundary(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'test.wacz').write_bytes(b'0123456789')
    store = Store(tmp_path / 'store')
    store.register('fixture', '归档测试', root)
    server = ThreadingHTTPServer(('127.0.0.1', 0), type('TestHandler', (Handler,), {'store': store}))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        request = urllib.request.Request(base+'/p/fixture/test.wacz', headers={'Range': 'bytes=2-5'})
        with urllib.request.urlopen(request) as response:
            assert response.status == 206 and response.read() == b'2345'
        with urllib.request.urlopen(base+'/p/fixture/archive.html?source=test.wacz&url=https://example.com/') as response:
            assert b'LESSONWEAVE_ARCHIVE' in response.read()
            assert 'Content-Security-Policy' not in response.headers
        with urllib.request.urlopen(base+'/archive/replay/sw.js') as response:
            assert response.status == 200
        # 正式发布包也必须带上公式排版器、样式和字体，不能只在开发目录中存在
        for asset in ['katex.min.js','katex.min.css','fonts/KaTeX_Main-Regular.woff2']:
            with urllib.request.urlopen(base+'/media-vendor/katex/dist/'+asset) as response:
                assert response.status == 200 and len(response.read()) > 100
        try:
            urllib.request.urlopen(base+'/p/fixture/archive.html?source=../outside.wacz')
        except urllib.error.HTTPError as error:
            assert error.code == 404
        else:
            raise AssertionError('项目外的归档路径不应公开')
    finally:
        server.shutdown()
        server.server_close()


def test_iframe_snapshot_keeps_middle_bottom_and_last_overlapping_tile(tmp_path):
    colors = [(10, 20, 30), (40, 50, 60), (70, 80, 90), (100, 110, 120), (130, 140, 150)]
    parts = ['<style>html,body{margin:0}section{height:120px}</style>',
             '<header style="position:fixed;top:0;left:0;width:100%;height:20px;background:rgb(255,0,0)">fixed</header>']
    for index, color in enumerate(colors):
        if index == 2:
            parts.append('<aside style="position:sticky;top:0;height:24px;background:#abcdef">sticky</aside>')
        parts.append(f'<section style="background:rgb{color}">part {index}</section>')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 320, 'height': 160}, device_scale_factor=1)
            page.set_content('<style>html,body{margin:0}iframe{border:0;width:320px;height:160px}</style><iframe></iframe>')
            frame = page.main_frame.child_frames[0]
            frame.set_content(''.join(parts))
            layout = web_archive.prepare_snapshot_layout(frame)
            result = web_archive.capture_frame_png(page, frame, tmp_path/'page.png')
        finally:
            browser.close()
    assert layout == {'fixed_elements': 1, 'sticky_elements': 1}
    assert result['complete'] and result['height'] == result['covered_height'] == 624
    assert result['tiles'][-1]['top'] == 464
    with Image.open(tmp_path/'page.png') as image:
        assert image.size == (320, 624)
        assert image.getpixel((310, 5)) == (255, 0, 0)
        assert image.getpixel((310, 250)) == (171, 205, 239)
        for y, color in zip([60, 180, 324, 444, 600], colors):
            assert image.getpixel((310, y)) == color


def test_locator_reads_registered_html_when_snapshot_display_is_a_replay_url(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'framework/05_writing'))
    from prepare_source_locations import prepare_web_dom
    (tmp_path/'original.html').write_text('<p data-iqa-source="p1">A complete source sentence.</p>', encoding='utf-8')
    group = {'sources': {'one': {'source': {'dom_path': '[data-iqa-source="p1"]'}}}}
    out = tmp_path/'locations'
    out.mkdir()
    tree = {'original': '/original.html', 'snapshot': {'html': '/archive.html?source=original.wacz'}}
    target = prepare_web_dom(tmp_path, group, out, tree)
    assert target is not None
    assert 'A complete source sentence.' in target.read_text('utf-8')


def test_replay_address_is_not_checked_as_a_local_snapshot_file(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'framework/01_tree'))
    from content_checks import check_objects
    (tmp_path/'original.html').write_text('<p data-iqa-source="p1">source</p>', encoding='utf-8')
    Image.new('RGB', (320, 160), 'white').save(tmp_path/'page.png')
    origin = {'kind': 'html', 'path': 'original.html', 'dom_path': '[data-iqa-source="p1"]', 'bbox': [0, 0, 100, 20]}
    document = {'tree': {'id': 'one', 'source': [origin], 'content': {'text': 'source'}, 'children': []},
                'pages': [], 'relations': [], 'original': '/original.html',
                'snapshot': {'image': '/page.png', 'html': '/original.html', 'offline_html': '/original.html',
                             'replay': '/archive.html?source=original.wacz', 'width': 320, 'height': 160}}
    assert check_objects(tmp_path, document, {})['errors'] == []
