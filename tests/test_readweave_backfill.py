"""共享登记复用已保存正文，整页文本只登记一次，原图和用户改稿继续保留"""
from hashlib import sha256
from pathlib import Path

import pytest

from lessonweave import readweave as rw, trilium
from lessonweave.readweave_backfill import backfill, needs_shared_registration
from lessonweave.storage import Store, read, save


@pytest.mark.parametrize('has_legacy_mapping', [True, False])
def test_old_completed_book_appends_shared_articles_and_page_text_once(tmp_path, monkeypatch, has_legacy_mapping):
    store = Store(tmp_path/'data')
    root = tmp_path/'book'
    store.register('book', '保存过的读本', root)
    doc = {'section_id': 's1', 'glossary': []}
    save(root/'05_writing/doc.json', doc)
    save(root/'05_writing/book.json', {'title': '读本', 'chapters': [{'sections': [{'id': 's1', 'number': '1.1', 'title': '问题', 'path': '05_writing/doc.json'}]}]})
    if has_legacy_mapping:
        save(root/'runtime/trilium/current.json', {'version': 'v1', 'edition_note_id': 'old-edition'})
    save(root/'05_writing/source-location/index.json', {'versions': [{'manifest': '/05_writing/source-location/v1/manifest.json'}]})
    save(root/'05_writing/source-location/v1/manifest.json', {'material_run': 'r1', 'material_path': 'tree.json', 'pages': {'paper.pdf:1': {'kind': 'pdf', 'number': 1, 'path': 'paper.pdf', 'text_layer': '/05_writing/source-location/v1/page.text.json'}}})
    save(root/'05_writing/source-location/v1/page.text.json', {'lines': [{'text': 'First exact PDF line'}, {'text': 'Second exact PDF line'}]})
    before = sha256((root/'05_writing/doc.json').read_bytes()).hexdigest()
    monkeypatch.setattr(rw, 'configured', lambda: True)
    monkeypatch.setattr('lessonweave.shared_html.article_html', lambda doc, resources: '<p>Saved body</p>')
    registered, batches = {}, []

    class Client:
        def call(self, method, path, payload=None):
            if method == 'POST':
                batches.append(payload)
                for row in payload['articles']:
                    registered.setdefault(row['key'], dict(row, articleId='native_'+str(len(registered))))
            return {'editionId': 'shared-edition', 'articles': list(registered.values())}

    monkeypatch.setattr(rw, 'Client', Client)
    assert needs_shared_registration(root)
    assert backfill(store)['registered'] == 1
    assert not needs_shared_registration(root)
    assert backfill(store)['registered'] == 0
    assert len(batches) == 1
    assert bool(batches[0].get('parentNoteId')) == has_legacy_mapping
    page = next(row for row in registered.values() if row['key'].startswith('original-page:'))
    assert page['body'] == '<p>First exact PDF line</p>\n<p>Second exact PDF line</p>'
    assert 'lines' not in page['source'] and 'chars' not in page['source']
    assert read(root/'runtime/readweave/current.json')['pages']['r1\ntree.json\npaper.pdf:1'] == page['articleId']
    assert sha256((root/'05_writing/doc.json').read_bytes()).hexdigest() == before


def test_native_article_jump_checks_membership_and_deleted_state(tmp_path, monkeypatch):
    save(tmp_path/'runtime/readweave/current.json', {'edition_id': 'edition', 'sections': {'s1': 'article'}})
    monkeypatch.setenv('LESSONWEAVE_TRILIUM_PUBLIC_URL', 'https://read.example')
    monkeypatch.setattr(trilium, 'configured', lambda: True)
    monkeypatch.setattr(rw, 'configured', lambda: True)
    monkeypatch.setattr(trilium, 'Client', lambda: object())
    monkeypatch.setattr(trilium, 'public_note_url', lambda client, article, base: base+'/#'+article)
    monkeypatch.setattr(rw, 'proxy', lambda *args: {'deleted': False, 'articles': [{'articleId': 'article', 'deleted': False}, {'articleId': 'gone', 'deleted': True}]})
    assert trilium.reading_link({}, tmp_path, article='article') == 'https://read.example/#article'
    for article in ['foreign', 'gone', '../article']:
        with pytest.raises(ValueError):
            trilium.reading_link({}, tmp_path, article=article)
