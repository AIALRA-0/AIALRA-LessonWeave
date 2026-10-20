from lessonweave.storage import save
from lessonweave.progress import begin,tick,view
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
