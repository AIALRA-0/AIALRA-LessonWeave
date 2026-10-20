"""验证任务删除、自动恢复和动态媒体编号，所有测试都不调用模型"""
import json
import sys
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright
from lessonweave.storage import Store,save
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'framework/00_source'))
import acquire
import web_archive
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'framework/01_tree'))
from tree_web import image_asset
from tree_web import parse_webpage
from tree_model import TreeBuilder,walk


def test_record_delete_keeps_idempotence_content_and_notes(tmp_path):
    store=Store(tmp_path/'store');root=tmp_path/'book'
    store.register('book','读本',root);save(root/'05_writing/book.json',{'title':'保留正文'})
    store.note('book','one','保留我的笔记')
    job=store.submit('book',{},'same')
    with pytest.raises(ValueError):store.archive_job(job['id'])
    store.finish(job['id'],{'status':'completed'});store.archive_job(job['id'])
    assert store.jobs()==[]
    assert store.submit('book',{},'same')['id']==job['id']
    assert store.note('book','one')=='保留我的笔记'
    assert json.loads((root/'05_writing/book.json').read_text('utf8'))['title']=='保留正文'


def test_restart_does_not_resume_user_cancelled_job(tmp_path):
    store=Store(tmp_path);store.register('book','读本',tmp_path/'book')
    job=store.submit('book',{},'first');store.claim();store.cancel(job['id'])
    assert Store(tmp_path,recover=True).job(job['id'])['status']=='cancelled'


def test_dynamic_svg_canvas_and_frames_receive_stable_unique_anchors():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page();page.set_content('<div data-iqa-source="s1">已保存</div>')
        page.evaluate("()=>document.body.insertAdjacentHTML('beforeend','<svg xmlns=\"http://www.w3.org/2000/svg\"></svg><canvas></canvas><iframe></iframe><video></video>')")
        first=page.evaluate(web_archive.resource_snapshot_script())
        second=page.evaluate(web_archive.resource_snapshot_script())
        assert len(first)==4 and first==second
        assert len({r['anchor'] for r in first})==4 and all(r['anchor']!='s1' for r in first)
        assert all(page.locator('[data-iqa-source="'+r['anchor']+'"]').count()==1 for r in first)
        browser.close()


def test_failed_snapshot_reuses_saved_archive_without_recrawling(tmp_path,monkeypatch):
    root=tmp_path/'book';old=root/'00_source/materials/source-0001';old.mkdir(parents=True)
    (old/'original.wacz').write_bytes(b'previously-acquired')
    (old/'capture.json').write_text('{}')
    payload={'kind':'url','material':'https://example.com/'}
    save(root/'00_source/source.json',dict(payload,status='unavailable'))
    calls=[]
    def recover(root,url,output):
        assert (output/'original.wacz').read_bytes()==b'previously-acquired'
        assert output!=old
        calls.append(url);(output/'original.html').write_text('<p>Recovered</p>')
        return {}
    monkeypatch.setattr(acquire,'capture_web',recover)
    assert acquire.acquire(root,payload)['status']=='acquired'
    assert calls==[payload['material']] and (old/'original.wacz').read_bytes()==b'previously-acquired'


def test_picture_routes_use_anchor_then_original_src_and_keep_variants_distinct():
    original='https://example.com/picture?format=auto'
    replay='http://127.0.0.1:8000/archive/replay/w/capture/hash/20261020193221oe_/'+original
    changed='https://example.com/picture?format=webp'
    record={'images':[{'url':original,'path':'assets/original.png'}]}
    assert image_asset(record,'s1',changed,replay)=='assets/original.png'
    assert image_asset(record,'s1',changed) is None
    record['images'][0]['anchor']='s1'
    assert image_asset(record,'s1',changed)=='assets/original.png'


def test_missing_remote_image_keeps_actual_page_region_instead_of_aborting(tmp_path):
    from PIL import Image
    (tmp_path/'original.html').write_text('<article><img data-iqa-source="s1" src="missing.png" alt="实际图表"></article>')
    save(tmp_path/'dom.json',{'s1':{'bbox':[10,10,80,50],'src':'https://example.com/missing.png'}})
    Image.new('RGB',(100,70),'red').save(tmp_path/'original.png')
    output=tmp_path/'parsed';output.mkdir()
    record={'entry':'original.html','material':'https://example.com/','positions':'dom.json','images':[],'snapshot':{'image':'/original.png'}}
    result=parse_webpage(TreeBuilder(),tmp_path,record,output)
    node=next(n for n in walk(result['tree']) if n['type']=='image')
    assert node['content']['representation']=='original_page_region'
    with Image.open(tmp_path/node['content']['asset'].lstrip('/'))as image:assert image.size==(70,40)
    assert len(result['summary']['image_issues'])==1
