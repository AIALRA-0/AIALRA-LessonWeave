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


def test_submit_is_idempotent_and_conflicts_fail(tmp_path):
    # 相同标识和内容只建立一个任务，变更内容时报告冲突
    store=Store(tmp_path)
    store.register('x','样例',tmp_path/'project')
    first=store.submit('x',{'a':1},'same')
    assert store.submit('x',{'a':1},'same')['id']==first['id']
    with pytest.raises(ValueError):
        store.submit('x',{'a':2},'same')


def test_restart_keeps_notes_and_marks_interrupted(tmp_path):
    # 服务重启后保留笔记，执行中的任务先进入待恢复状态
    store=Store(tmp_path)
    store.register('x','样例',tmp_path/'project')
    job=store.submit('x',{},'one')
    store.claim()
    store.note('x','unit','我理解了这个例子')
    restarted=Store(tmp_path,recover=True)
    assert restarted.job(job['id'])['status']=='interrupted'
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


def test_batch_repair_limit_survives_resume(tmp_path,monkeypatch):
    # 首稿加三轮修复统一计数，恢复已耗尽的任务时继续保留原结果
    from lessonweave import pipeline
    monkeypatch.setattr(pipeline,'prepare',lambda root:None)
    monkeypatch.setattr(pipeline.flow,'tree_stages',lambda *args:None)
    calls=[]
    def draft(root,backend):
        calls.append(read(root/'runtime/state.json')['round'])
        return {},False,['需要完善解释']
    monkeypatch.setattr(pipeline,'write_sections',draft)
    monkeypatch.setattr('lessonweave.package.export_package',lambda root:{})
    assert pipeline.run(tmp_path,3)['status']=='needs_review'
    assert calls==[0,1,2,3]
    pipeline.run(tmp_path,3)
    assert calls==[0,1,2,3]


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
