"""字层从原 PDF 的真实字符生成，坐标与原件保持一致"""
from hashlib import sha256
import json

import fitz
from lessonweave import legacy
from prepare_source_locations import prepare_pdf, backfill_pdf_text_layers


def test_pdf_page_exports_exact_glyph_text_and_keeps_original(tmp_path):
    pdf = tmp_path/'original.pdf'
    doc = fitz.open()
    page = doc.new_page(width=500, height=300)
    page.insert_text((30, 60), 'First exact PDF line')
    page.insert_text((30, 95), 'Second exact PDF line')
    doc.save(pdf)
    doc.close()
    before = sha256(pdf.read_bytes()).hexdigest()
    source = {'id': 'n1', 'source_refs': [], 'source': {'kind': 'pdf', 'path': 'original.pdf', 'page': 1}, 'sentences': {'s1': {'original': 'First exact PDF line'}}}
    manifest = {'pages': {}, 'sources': {'n1': {'page_ids': [], 'locations': [], 'sentences': {'s1': {'original': 'First exact PDF line'}}}}}
    prepare_pdf(tmp_path, {'sources': {'n1': source}}, tmp_path/'output', manifest)
    page = manifest['pages']['original.pdf:1']
    sidecar = json.loads((tmp_path/page['text_layer'].lstrip('/')).read_text('utf-8'))
    assert sidecar['profile'] == 'pdf-text-layer-v1'
    assert [line['text'] for line in sidecar['lines']] == ['First exact PDF line', 'Second exact PDF line']
    assert all(''.join(char['text'] for char in line['chars']) == line['text'] for line in sidecar['lines'])
    assert all(0 <= char['bbox'][0] < char['bbox'][2] <= 500 and 0 <= char['bbox'][1] < char['bbox'][3] <= 300 for line in sidecar['lines'] for char in line['chars'])
    assert sha256(pdf.read_bytes()).hexdigest() == before


def test_existing_page_gets_only_an_idempotent_text_sidecar(tmp_path):
    pdf = tmp_path/'source.pdf'
    document = fitz.open()
    page = document.new_page()
    page.insert_text((40, 70), 'Keep real hyphen one-')
    document.save(pdf)
    document.close()
    folder = tmp_path/'05_writing/source-location/version-0001'
    folder.mkdir(parents=True)
    image = folder/'page-0001.png'
    image.write_bytes(b'Existing original page image')
    manifest = {'pages': {'source.pdf:1': {'kind': 'pdf', 'number': 1, 'path': 'source.pdf',
                                         'image': '/05_writing/source-location/version-0001/page-0001.png'}},
                'sources': {'n1': {'locations': [{'bbox': [1, 2, 3, 4]}]}}}
    (folder/'manifest.json').write_text(json.dumps(manifest))
    (folder.parent/'index.json').write_text(json.dumps({'versions': [{'manifest': '/05_writing/source-location/version-0001/manifest.json'}]}))
    hashes = [sha256(path.read_bytes()).hexdigest() for path in (pdf, image)]
    assert backfill_pdf_text_layers(tmp_path) == {'pages': 1, 'manifests': 1}
    updated = json.loads((folder/'manifest.json').read_text())
    assert updated['sources'] == manifest['sources']
    assert updated['pages']['source.pdf:1']['text_layer'].endswith('.text.json')
    assert json.loads((folder/'page-0001.text.json').read_text())['lines'][0]['text'].endswith('one-')
    assert backfill_pdf_text_layers(tmp_path) == {'pages': 0, 'manifests': 0}
    assert [sha256(path.read_bytes()).hexdigest() for path in (pdf, image)] == hashes
