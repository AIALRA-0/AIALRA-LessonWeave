"""检查架构页面读取真实产物、保留待审状态并限制私人文件访问"""
from functools import partial
from http.server import ThreadingHTTPServer
from threading import Thread
import json
import urllib.error
import urllib.request

from lessonweave.architecture import FRAME, VIEW, load, snapshot
from lessonweave.storage import Store, save
from lessonweave.server import Handler


def test_framework_fields_follow_current_schemas_and_rule_files(tmp_path):
    # 没有选择项目时仍显示真实字段类型，每个规则入口都指向存在的实现
    result = snapshot(Store(tmp_path))
    assert len(result['stages']) == 8 and result['project'] is None
    assert result['stages'][0]['fields'][0]['type'] == '字符串'
    for stage in result['stages']:
        assert (FRAME / stage['rules_file']).is_file()
        assert all(field['value'] is None for field in stage['fields'])
    assert (VIEW / 'vendor/LICENSE-mermaid.txt').is_file()


def test_preview_version_and_failed_checks_remain_read_only(tmp_path):
    # 当前预览保留失败状态，数字按产物显示，查询后正文与笔记原样保留
    root = tmp_path / 'book'; store = Store(tmp_path / 'store')
    store.register('book', '当前项目', root)
    save(root / '00_source/input.json', {'kind':'file', 'material':'C:/private/original.pdf'})
    save(root / '00_source/source.json', {'status':'acquired', 'entry':'00_source/materials/original.pdf'})
    save(root / '01_tree/tree.json', {'run':'run-9', 'tree':{'id':'n1', 'type':'paragraph', 'content':{'text':'材料原文'}, 'source':[]}, 'coverage':{'content':{'covered':2,'expected':3},'objects':{'available':1,'expected':2}}})
    section = '05_writing/sections/current.json'
    save(root / section, {'section_id':'s1', 'units':[{'problem':{'text':'当前问题'},'explanation':[{'text':'实际解释'}],'synthesis':{'text':'回答'}}], 'validation':{'passed':False}})
    save(root / '05_writing/preview-book.json', {'preview':True,'writing_run':'revision-9','title':'真实预览','chapters':[{'sections':[{'path':section}]}], 'validation':{'passed':False,'status':'preview_not_published'}})
    store.note('book', 'unit', '保留我的理解')
    before = {p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
    result = snapshot(store, 'book')
    assert result['version'] == 'revision-9' and result['preview']
    assert result['stages'][7]['status'] == '预览待审'
    assert result['stages'][1]['coverage'][0]['percentage'] == 66.67
    assert result['stages'][0]['fields'][1]['value'] == 'original.pdf'
    field = result['stages'][5]['fields'][1]
    assert field['path'] == 'units[0].problem.text' and field['value'] == '当前问题'
    assert all(p.read_bytes() == content for p,content in before.items())
    assert store.note('book','unit') == '保留我的理解'


def test_section_reference_cannot_read_outside_project(tmp_path):
    # 产物中的小节路径越出项目目录时，架构页面不读取该文件
    root=tmp_path/'book';store=Store(tmp_path/'store');store.register('book','项目',root)
    save(tmp_path/'secret.json',{'title':'PRIVATE-FIXTURE'})
    save(root/'05_writing/book.json',{'chapters':[{'sections':[{'path':'../secret.json'}]}]})
    result=snapshot(store,'book')
    assert 'PRIVATE-FIXTURE' not in json.dumps(result)


def test_coverage_uses_current_section_grounding_and_keeps_review_failure(tmp_path):
    # 当前小节声明的覆盖路径优先于其他工作目录，数字齐全时仍保留审查失败
    root=tmp_path/'book';store=Store(tmp_path/'store');store.register('book','项目',root)
    section='05_writing/draft/sections/s1.json'
    evidence='05_writing/draft/sections/s1/'
    save(root/'05_writing/preview-book.json',{'preview':True,'chapters':[{'sections':[{'path':section}]}]})
    save(root/section,{'section_id':'s1','grounding':{'inventory_path':evidence+'inventory.json','coverage_path':evidence+'coverage.json'}})
    save(root/(evidence+'inventory.json'),{'points':[{'description':'实际细节','checks':['说明条件']}]})
    save(root/(evidence+'coverage.json'),{'passed':False,'total_points':1,'explained_points':1,'items':[{'points':[{'explained':True,'block_ids':['b1']}]}]})
    value=snapshot(store,'book')['stages'][6]
    assert value['status']=='检查未通过' and value['coverage'][0]['percentage']==100
    assert value['fields'][0]['value']=='实际细节'
    assert value['fields'][2]['path']=='items[0].points[0].explained'


def test_architecture_routes_require_owner_and_restrict_static_files(tmp_path,monkeypatch):
    # 页面、数据和规则均受所有者保护，静态路径与规则查询只开放指定文件
    store=Store(tmp_path)
    server=ThreadingHTTPServer(('127.0.0.1',0),type('TestHandler',(Handler,),{'store':store}))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    monkeypatch.setenv('LESSONWEAVE_AUTH_REQUIRED','1');monkeypatch.setenv('LESSONWEAVE_OWNER','fixture-owner')
    base='http://127.0.0.1:'+str(server.server_port)
    def status(path,owner=None):
        request=urllib.request.Request(base+path,headers={'X-Aialra-User':owner} if owner else {})
        try:
            with urllib.request.urlopen(request) as response:return response.status,response.read()
        except urllib.error.HTTPError as error:return error.code,error.read()
    try:
        for path in ['/architecture','/api/architecture','/api/architecture/rule?stage=01']:
            assert status(path)[0]==401
            assert status(path,'other')[0]==403
            assert status(path,'fixture-owner')[0]==200
        assert status('/architecture/../00_source/acquire.py','fixture-owner')[0]==404
        assert status('/api/architecture/rule?stage=../storage','fixture-owner')[0]==404
    finally:
        server.shutdown();server.server_close();thread.join()
