from lessonweave.storage import save
from lessonweave.progress import begin,tick,view,stage_times
from lessonweave.system_info import snapshot
import time


def test_first_question_does_not_complete_writing_stage(tmp_path):
    save(tmp_path/'runtime/state.json',{'workflow':'lean-c-1.0','stage':'05_writing/c'})
    folder=tmp_path/'05_writing/work/sections/s1'
    save(folder/'context.json',{'units':[{'question_id':'q.1.1'},{'question_id':'q.1.2'}]})
    save(folder/'unit-q.1.1.json',{'result':{'answer':'已经写出的答案'}})
    job={'status':'running','created':time.time()-10,'updated':time.time()}
    value=view(tmp_path,job);rows={r['id']:r for r in value['stages']}
    assert rows['04']['status']=='running' and rows['04']['done']==1 and rows['04']['total']==2
    assert rows['05']['status']=='running'
    assert not value['output_ready']


def test_parallel_batches_keep_history_and_skipped_repair(tmp_path):
    begin(tmp_path,'写作',['s-c-q.1.1'])
    tick(tmp_path,'s-c-q.1.1','completed')
    tick(tmp_path,'c_translation-batch-001','running')
    begin(tmp_path,'承接',[])
    tick(tmp_path,'c_bridges-batch-001','completed')
    save(tmp_path/'05_writing/checks/batch-repair.json',{'model_calls':0})
    save(tmp_path/'runtime/state.json',{'workflow':'lean-c-1.0','stage':'05_writing/package'})
    value=view(tmp_path,{'status':'running','created':time.time()-5,'updated':time.time()})
    assert len(value['tasks'])==3
    assert next(r for r in value['stages'] if r['id']=='08')['status']=='skipped'
    assert next(r for r in value['stages'] if r['id']=='11')['status']=='running'


def test_system_info_never_returns_credentials_or_paths(tmp_path,monkeypatch):
    monkeypatch.setenv('AIALRA_DEEPSEEK_OFFICIAL_KEY','synthetic-private-value')
    value=snapshot(tmp_path)
    assert value['profile']['writing_calls']>=1 and value['capabilities']['flash']
    assert 'synthetic-private-value' not in str(value)
    assert str(tmp_path) not in str(value)


def test_library_progress_counts_saved_and_reused_attachments(tmp_path,monkeypatch):
    monkeypatch.setenv('LESSONWEAVE_TRILIUM_URL','http://localhost')
    save(tmp_path/'runtime/state.json',{'workflow':'lean-c-1.0','stage':'library/sync'})
    save(tmp_path/'runtime/progress.json',{'tasks':{'attachment:a':'completed','attachment:b':'reused','attachment:c':'running'}})
    save(tmp_path/'runtime/trilium/current.json',{'render_note_id':'previous-edition'})
    value=view(tmp_path,{'status':'running','created':time.time()-10,'updated':time.time()})
    row=next(r for r in value['stages'] if r['id']=='12')
    assert row['status']=='running' and row['done']==2 and row['total']==3


def test_stage_clocks_merge_nested_work_and_exclude_interruption_gaps(tmp_path):
    save(tmp_path/'runtime/timing.json',{'records':[
        {'job_id':'job','stage':'writing','operation':'model','started_at':0,'ended_at':10},
        {'job_id':'job','stage':'writing','operation':'format','started_at':2,'ended_at':8},
        {'job_id':'job','stage':'translation','operation':'model','started_at':5,'ended_at':15},
        {'job_id':'job','stage':'other','operation':'job_run','started_at':0,'ended_at':15},
        {'job_id':'job','stage':'other','operation':'job_run','started_at':100,'ended_at':105},
        {'job_id':'another','stage':'writing','operation':'model','started_at':0,'ended_at':200}]})
    rows=[{'id':'04','status':'done'},{'id':'05','status':'done'},{'id':'08','status':'skipped'}]
    result=stage_times(tmp_path,{'id':'job','status':'completed','updated':105},rows,{})
    assert [r['execution_seconds'] for r in rows]==[10,10,0]
    assert result=={'stage_execution_seconds':20,'execution_seconds':20}
