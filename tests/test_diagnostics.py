import concurrent.futures
import json
import time
import pytest
from lessonweave import agents,pipeline
from lessonweave.agents import AgentCallFailure,CodexAdapter
from lessonweave.storage import read,save
from lessonweave.progress import view
from lessonweave.trilium import public_note_url,reading_link


def test_output_limit_receipt_preserves_known_cause(tmp_path,monkeypatch):
    # CLI 明确返回输出超限时保存真实失败类型，测试进程不会启动模型
    class FailedProcess:
        pid=1234
        returncode=1
        def __init__(self,args,**options):self.output=options['stdout']
        def communicate(self,prompt,timeout=None):
            self.output.write(json.dumps({'type':'turn.failed','error':{'message':'Incomplete response returned, reason: max_output_tokens'}})+'\n')
            self.output.flush()
    monkeypatch.setattr(agents,'codex_executable',lambda:'test-fixture')
    monkeypatch.setattr(agents.subprocess,'Popen',FailedProcess)
    with pytest.raises(AgentCallFailure) as result:
        CodexAdapter().execute({'schema':{},'model':'fixture','effort':'high','images':[],'prompt':'fixture'},tmp_path)
    assert result.value.kind=='output_limit'
    receipt=read(tmp_path/'receipt.json')
    assert receipt['failure_kind']=='output_limit' and receipt['exit_code']==1
    assert receipt['usage_measurement']=='unavailable'


def test_parallel_collection_preserves_interrupted_calls():
    # 某个请求需要恢复时，其他任务照常完成，恢复后收齐全部真实结果
    done=[]
    attempts=[]
    def task(value):
        if value==1 and not attempts:
            attempts.append(value)
            raise AgentCallFailure('output_limit','任务超过输出上限')
        done.append(value);return value
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pipeline.collect(pool,[1,2,3],task))==[1,2,3]
    assert sorted(done)==[1,2,3]




def test_readweave_jump_uses_actual_native_note_path():
    # 跳转使用当前实例的真实父子笔记关系，保留宿主的登录入口
    class Native:
        def call(self,method,path):
            return {'parentNoteIds':{'notes/section':['chapter'],'notes/chapter':['book'],'notes/book':['root']}[path]}
    assert public_note_url(Native(),'section','https://notes.example.com')=='https://notes.example.com/#root/book/chapter/section'
    with pytest.raises(ValueError):public_note_url(Native(),'section','javascript:fixture')


def test_readweave_jump_waits_for_the_matching_instance(tmp_path,monkeypatch):
    # 未配置实际宿主时保留未关联状态，演示笔记不会指向另一个正式实例
    monkeypatch.delenv('LESSONWEAVE_TRILIUM_PUBLIC_URL',raising=False)
    with pytest.raises(ValueError,match='尚未关联'):reading_link({'native_note_id':'demo'},tmp_path)


def test_readweave_jump_opens_the_current_section(tmp_path,monkeypatch):
    # 当前小节使用版本回执中的实际笔记，缺失回执时显示未导入
    from lessonweave import trilium
    for key,value in {'URL':'http://localhost:8080','TOKEN':'fixture','ROOT':'book','PUBLIC_URL':'https://notes.example.com'}.items():
        monkeypatch.setenv('LESSONWEAVE_TRILIUM_'+key,value)
    save(tmp_path/'runtime/trilium/current.json',{'sections':{'s1':'native_section'}})
    class Native:
        def call(self,method,path):return {'parentNoteIds':['root']}
    monkeypatch.setattr(trilium,'Client',Native)
    assert reading_link({'native_note_id':'book'},tmp_path,'s1')=='https://notes.example.com/#root/native_section'
    with pytest.raises(ValueError,match='尚未导入'):reading_link({'native_note_id':'book'},tmp_path,'s2')


