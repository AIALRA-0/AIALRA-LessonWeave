import os
import time
from lessonweave import metrics,agents
from lessonweave.storage import Store,save,read


def test_parallel_time_uses_union_and_keeps_cumulative_time():
    # 两个重叠调用共经过 15 秒，累计调用时间仍为 20 秒
    rows=[{'started_at':100,'ended_at':110},{'started_at':105,'ended_at':115}]
    assert metrics.union_seconds(rows)==15
    assert sum(row['ended_at']-row['started_at'] for row in rows)==20


def test_new_calls_distinguish_initial_repair_and_reuse(tmp_path,monkeypatch):
    # 使用本地替身完成初稿、复用和返修，复用不会增加实际模型调用或 token
    from lessonweave.agents import Backend
    class Fixture:
        capabilities={'images':False}
        def execute(self,task,folder):
            return {'text':'材料中的条件决定实际结果'},{'usage':[{'input_tokens':10,'output_tokens':5,'cached_input_tokens':0}]}
    monkeypatch.setitem(agents.ADAPTERS,'fixture',Fixture)
    monkeypatch.setenv('LESSONWEAVE_BACKEND','fixture')
    monkeypatch.setenv('LESSONWEAVE_JOB_ID','job')
    began=time.time()
    schema={'type':'object','properties':{'text':{'type':'string'}},'required':['text']}
    backend=Backend(tmp_path,role='writing')
    first=backend.call('s-05_unit-q1','fixture',schema)
    assert backend.call('s-05_unit-q1','fixture',schema)==first
    save(tmp_path/'runtime/state.json',{'round':1,'feedback':{'s-05_unit-q1':{'errors':['补齐条件']}}})
    backend.call('s-05_unit-q1','fixture',schema)
    report=metrics.report(tmp_path,{'id':'job','status':'completed','created':began,'updated':time.time()})
    assert report['summary']['calls']==2
    assert report['summary']['repair_calls']==1 and report['summary']['reuse_events']==1
    assert report['summary']['input_tokens']==20 and report['summary']['output_tokens']==10
    assert report['summary']['cached_input_tokens']==0
    assert all(row['queue_seconds'] is not None and row['measurement']=='recorded' for row in report['calls'])
    # 新的阅读追问有独立任务，沿用项目修复轮次也不会被算成内容返修
    monkeypatch.setenv('LESSONWEAVE_JOB_ID','qa-job')
    began=time.time()
    Backend(tmp_path,role='reader_qa').call('reader-qa-fixture','fixture',schema)
    qa=metrics.report(tmp_path,{'id':'qa-job','status':'completed','created':began,'updated':time.time()})
    assert qa['summary']['calls']==1 and qa['summary']['repair_calls']==0
    assert qa['calls'][0]['round']==0 and qa['calls'][0]['kind']=='initial'


def test_historical_missing_usage_stays_unknown_and_files_are_preserved(tmp_path):
    # 历史结束时间按文件推算，未报告用量与排队时间保持缺失，历史文件原样保留
    now=time.time();folder=tmp_path/'runtime/calls/s-05_inventory/request'
    save(folder/'process.json',{'started':now-40})
    save(folder/'usage.json',{'task':'s-05_inventory','status':'uncertain','round':2,'elapsed_seconds':90})
    os.utime(folder/'usage.json',(now,now))
    before=(folder/'usage.json').read_bytes()
    value=metrics.report(tmp_path,{'id':'old','status':'needs_review','created':now-100,'updated':now})
    call=value['calls'][0]
    assert call['measurement']=='historical_file_times' and call['queue_seconds'] is None
    assert call['elapsed_seconds']==40 and call['input_tokens'] is None
    assert value['summary']['unknown_usage_calls']==1 and value['summary']['repair_rounds_entered'] is None
    assert (folder/'usage.json').read_bytes()==before
    assert next(row for row in value['stages'] if row['stage']=='parse')['wall_seconds'] is None


def test_job_stop_closes_queued_and_running_timers(tmp_path,monkeypatch):
    # 排队停止和运行停止都保存结束时间，迟到的完成结果仍保留停止状态
    store=Store(tmp_path/'store');root=tmp_path/'book';store.register('book','读本',root)
    job=store.submit('book',{},'first');store.cancel(job['id'])
    value=metrics.report(root,store.job(job['id']))
    assert value['summary']['job_queue_seconds'] is not None and value['summary']['calls']==0
    store.resume(job['id']);store.claim()
    monkeypatch.setenv('LESSONWEAVE_JOB_ID',job['id'])
    key=metrics.start(root,'writing','model')
    store.cancel(job['id']);store.finish(job['id'],{'status':'completed'})
    row=next(r for r in read(root/'runtime/timing.json')['records'] if r['id']==key)
    assert row['status']=='cancelled' and row['measurement']=='supervisor_observed' and 'ended_at' in row


def test_new_job_report_excludes_other_jobs_and_reports_rounds(tmp_path,monkeypatch):
    # 同一项目的追问与旧任务分开统计，实际进入的修复批次单独计数
    now=time.time();monkeypatch.setenv('LESSONWEAVE_JOB_ID','other')
    with metrics.span(tmp_path,'writing','model'):pass
    monkeypatch.setenv('LESSONWEAVE_JOB_ID','current')
    with metrics.span(tmp_path,'other','repair_round',round=1):pass
    value=metrics.report(tmp_path,{'id':'current','status':'completed','created':now,'updated':time.time()})
    assert len(value['steps'])==1 and value['summary']['repair_rounds_entered']==1


def test_first_task_call_is_initial_even_after_an_earlier_stage_repair(tmp_path,monkeypatch):
    # 材料清点触发全局修复后，正文任务的首次实际调用仍按初稿计量
    class Fixture:
        capabilities={'images':False}
        def execute(self,task,folder):return {'text':'完整讲解'},{'usage':[{'input_tokens':10,'output_tokens':3,'cached_input_tokens':0}]}
    monkeypatch.setitem(agents.ADAPTERS,'fixture',Fixture)
    monkeypatch.setenv('LESSONWEAVE_BACKEND','fixture');monkeypatch.setenv('LESSONWEAVE_JOB_ID','job')
    save(tmp_path/'runtime/state.json',{'round':2})
    began=time.time();schema={'type':'object','properties':{'text':{'type':'string'}},'required':['text']}
    agents.Backend(tmp_path,role='writing').call('s-05_unit-q1','正文任务',schema)
    value=metrics.report(tmp_path,{'id':'job','status':'completed','created':began,'updated':time.time()})
    assert value['calls'][0]['kind']=='initial' and value['summary']['repair_calls']==0


def test_first_batch_repair_keeps_its_explicit_recorded_kind(tmp_path):
    # 批量修复有独立任务名，首次调用仍是修复，不能误记为初稿
    now=time.time();folder=tmp_path/'runtime/calls/c_repair-batch/request'
    save(folder/'usage.json',{'task':'c_repair-batch','job_id':'job','status':'completed',
        'attempt_kind':'repair','round':0,'started_at':now-2,
        'usage':[{'input_tokens':10,'output_tokens':3,'cached_input_tokens':0}]})
    value=metrics.report(tmp_path,{'id':'job','status':'completed','created':now-10,'updated':now})
    assert value['calls'][0]['kind']=='repair'
    assert value['summary']['repair_calls']==1 and value['summary']['initial_generation_seconds']==0
