"""检查去重、恢复、资料保护、轮次上限和真实模型配置，不发起模型请求"""
import json
from pathlib import Path
import zipfile

import jsonschema
import pytest

from lessonweave.storage import Store, save, read
from lessonweave.agents import Backend, register_backend
from lessonweave.pipeline import scaffold, run
from lessonweave.package import import_package


def test_saved_book_still_resumes_unfinished_location_and_export_steps(tmp_path, monkeypatch):
    from lessonweave import jobs, pipeline, trilium
    store = Store(tmp_path/'data')
    project = tmp_path/'project'
    store.register('x', '样例', project)
    job = store.submit('x', {}, 'one')
    save(project/'05_writing/book.json', {'validation': {'passed': True}})
    save(project/'runtime/state.json', {'status': 'cancelled', 'stage': '05_writing/locations'})
    called = []
    def finish(root, maximum):
        called.append((root, maximum))
        return {'status': 'completed'}
    monkeypatch.setattr(pipeline, 'run', finish)
    monkeypatch.setattr(trilium, 'configured', lambda: False)
    monkeypatch.setattr(jobs.sys, 'argv', ['jobs', str(tmp_path/'data'), job['id']])
    jobs.main()
    assert called == [(project, 1)]
    assert read(project/'runtime/jobs'/job['id']/'result.json')['status'] == 'completed'


def test_submit_is_idempotent_and_conflicts_fail(tmp_path):
    # 相同标识和内容只建立一个任务，变更内容时报告冲突
    store=Store(tmp_path)
    store.register('x','样例',tmp_path/'project')
    first=store.submit('x',{'a':1},'same')
    assert store.submit('x',{'a':1},'same')['id']==first['id']
    with pytest.raises(ValueError):
        store.submit('x',{'a':2},'same')


def test_restart_keeps_notes_and_automatically_requeues(tmp_path):
    # 服务重启后保留笔记，执行中的任务自动回到队列并复用已有结果
    store=Store(tmp_path)
    store.register('x','样例',tmp_path/'project')
    job=store.submit('x',{},'one')
    store.claim()
    store.note('x','unit','我理解了这个例子')
    restarted=Store(tmp_path,recover=True)
    assert restarted.job(job['id'])['status']=='queued'
    assert restarted.note('x','unit')=='我理解了这个例子'


@pytest.mark.parametrize('field',['kind','material','mode','system_prompt'])
def test_input_requires_nonblank_values(tmp_path,field):
    # 四个输入字段各自使用空白内容时，Schema 都会拒绝
    scaffold(tmp_path)
    payload={'kind':'url','material':'https://example.com','mode':'one_shot','system_prompt':'解释材料'}
    payload[field]=' '
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload,read(tmp_path/'00_source/input.schema.json'))


def test_arbitrary_project_name_has_all_stages(tmp_path):
    # 新项目使用任意名称，仍然得到与框架相同的步骤和输入 Schema
    root=tmp_path/'a-new-topic'
    scaffold(root)
    assert (root/'00_source/input.schema.json').is_file()
    assert (root/'05_writing/demo.schema.json').is_file()


def test_model_schema_includes_every_property_without_changing_disk_contract():
    # API 的严格输出 Schema 要求全部属性进入 required，旧产物的可选字段继续按原磁盘规则读取
    from lessonweave.agents import wire_schema
    schema={'type':'object','properties':{'title':{'type':'string'},'title_format_version':{'const':2}},'required':['title'],
            '$defs':{'question':{'type':'object','properties':{'id':{'type':'string'},'point_ids':{'type':'array','items':{'type':'string'}}},'required':['id']}}}
    result=wire_schema(schema)
    assert set(result['required'])==set(result['properties'])
    assert set(result['$defs']['question']['required'])=={'id','point_ids'}
    assert schema['required']==['title'] and result['properties']['title_format_version']=={'const':2,'type':'integer'}


def test_wire_constants_declare_types_for_media_and_shared_terms():
    from lessonweave import pipeline
    from lessonweave.agents import wire_schema
    import lean_contract,glossary_reuse
    schema=wire_schema(lean_contract.writer_schema({'single_choice':1,'short_answer':0}))
    def check(node):
        if isinstance(node,dict):
            if 'const'in node or node.get('enum'):assert 'type'in node
            for value in node.values():check(value)
        elif isinstance(node,list):
            for value in node:check(value)
    check(schema)
    assert wire_schema({'enum':['first','second']})['type']=='string'
    assert wire_schema({'const':False})['type']=='boolean'
    assert wire_schema({'enum':[None,'value']})['type']==['null','string']


def test_user_test_directory_is_protected(tmp_path):
    # 调度器在建立产物之前拒绝用户的 05-test 目录
    root=tmp_path/'05-test'
    with pytest.raises(ValueError):
        run(root)
    assert not root.exists()


def test_provider_reuses_identical_request_and_keeps_contexts_separate(tmp_path,monkeypatch):
    # 相同角色和输入复用结果，独立审查使用另一份实际请求
    from lessonweave import agents
    class Fake:
        capabilities={'images':True}
        count=0
        def execute(self,task,folder):
            Fake.count+=1
            return {'answer':'完成'}, {'usage':[{'input_tokens':5,'output_tokens':2,'cached_input_tokens':3}], 'session_id':str(Fake.count)}
    register_backend('fixture',Fake)
    monkeypatch.setenv('LESSONWEAVE_BACKEND','fixture')
    schema={'type':'object','properties':{'answer':{'type':'string'}},'required':['answer'],'additionalProperties':False}
    writer=Backend(tmp_path,role='writing')
    writer.call('unit','当前任务',schema)
    writer.call('unit','当前任务',schema)
    Backend(tmp_path,role='independent_review').call('unit','当前任务',schema)
    assert Fake.count==2
    records=list((tmp_path/'runtime/calls').glob('*/*/usage.json'))
    assert {read(p)['role'] for p in records}=={'writing','independent_review'}


def test_scaffold_keeps_project_rules_independent(tmp_path,monkeypatch):
    # 更新公共规则后，已经创建的项目继续保留创建时的规则内容
    from lessonweave import pipeline
    frame=tmp_path/'frame'
    for stage in pipeline.STAGES:
        (frame/stage).mkdir(parents=True)
    source=frame/'00_source/input.schema.json'
    source.write_text('{"version":1}')
    monkeypatch.setattr(pipeline,'FRAME',frame)
    project=tmp_path/'project'
    pipeline.scaffold(project)
    source.write_text('{"version":2}')
    assert (project/'00_source/input.schema.json').read_text()=='{"version":1}'


def test_private_site_requires_owner(monkeypatch):
    # 启用个人登录时必须先指定所有者，避免无意开放给其他已登录账户
    from lessonweave.server import serve
    monkeypatch.setenv('LESSONWEAVE_AUTH_REQUIRED','1')
    monkeypatch.delenv('LESSONWEAVE_OWNER',raising=False)
    with pytest.raises(ValueError,match='LESSONWEAVE_OWNER'):
        serve()




def test_configured_four_round_limit_allows_resume_without_resetting_history(tmp_path,monkeypatch):
    # 网站采用允许的四轮上限时，第三轮暂停的任务可以继续，历史轮次仍保持原值
    monkeypatch.setenv('LESSONWEAVE_MAX_REPAIRS','4')
    store=Store(tmp_path/'store');root=tmp_path/'project'
    store.register('book','最小案例',root);job=store.submit('book',{},'limit')
    save(root/'runtime/state.json',{'round':3,'maximum':3})
    store.finish(job['id'],{'status':'needs_review'})
    store.resume(job['id'])
    assert store.job(job['id'])['status']=='queued'
    assert read(root/'runtime/state.json')['round']==3


def test_reading_import_preserves_source_code_and_rejects_escape(tmp_path):
    # 源码是可阅读材料，导入后按原字节保存，越界文件始终拒绝
    archive=tmp_path/'book.zip'
    name='00_source/materials/project/main.py'
    manifest={'profile':'lessonweave-reading-package-v1','schema_version':1,'project_id':'sample','version':'v1','title':'示例','book_path':'05_writing/book.json','validation':{},'coverage':{},'source_location_path':'05_writing/source-location/index.json','files':[name],'user_data_included':False}
    with zipfile.ZipFile(archive,'w') as output:
        output.writestr('manifest.json',json.dumps(manifest))
        output.writestr(name,'print("sample")')
    import_package(archive,tmp_path/'reader')
    assert (tmp_path/'reader'/name).read_text()=='print("sample")'
    with zipfile.ZipFile(archive,'w') as output:
        manifest['files']=['../escape']
        output.writestr('manifest.json',json.dumps(manifest))
        output.writestr('../escape','bad')
    with pytest.raises(ValueError):
        import_package(archive,tmp_path/'other')
