"""笔记继续使用原生接口，清空或原生删除后不会把旧备份重新显示"""
from pathlib import Path
from lessonweave import readweave as rw
from lessonweave.storage import save
import pytest


def test_note_create_update_clear_and_remote_delete(tmp_path,monkeypatch):
    mapping={'edition_id':'edition','sections':{'s1':'article'},'notes':{}}
    save(tmp_path/'runtime/readweave/current.json',mapping)
    project={'id':'synthetic','path':str(tmp_path)}
    calls=[];entries=[]
    class Store:
        def note(self,*args):return '旧备份'
    def proxy(method,path,payload=None):
        calls.append((method,path,payload))
        if '/anchors/'in path:return {'entries':entries.copy()}
        if method=='GET':return {'title':'在这个问题下怎样做笔记'}
        if method=='POST':
            assert payload['origin']=='manual' and payload['sourceExcerpt']
            entry=dict(payload,linkId='link',revision=1,linkRevision=1)
            entries.append(entry);return {'entry':entry}
        if method=='PATCH':assert payload['expectedLinkRevision']==1
        if method=='DELETE':assert path.endswith('?expectedLinkRevision=1')
        if method=='PATCH':entries[0]['body']=payload['body'];return {}
        if method=='DELETE':entries.clear();return {}
    monkeypatch.setattr(rw,'configured',lambda:True)
    monkeypatch.setattr(rw,'proxy',proxy)
    store=Store()
    assert rw.note(store,project,'s1:q1')=='旧备份'
    assert rw.note(store,project,'s1:q1','第一份笔记')=='第一份笔记'
    assert rw.note(store,project,'s1:q1')=='第一份笔记'
    rw.note(store,project,'s1:q1','改过的笔记')
    assert rw.note(store,project,'s1:q1')=='改过的笔记'
    rw.note(store,project,'s1:q1','')
    assert rw.note(store,project,'s1:q1')==''
    rw.note(store,project,'s1:q1','新的笔记')
    entries.clear()
    assert rw.note(store,project,'s1:q1')==''
    assert any(method=='DELETE'for method,_,_ in calls)


def test_import_batches_preserve_every_article_and_single_large_article():
    rows=[{'key':str(i),'body':'x'*size}for i,size in enumerate([10,10,10000,10,10])]
    groups=list(rw.import_batches(rows,target_bytes=100))
    assert [row for group in groups for row in group]==rows
    assert any(len(group)==1 and group[0]['key']=='2'for group in groups)
    assert max(len(group)for group in rw.import_batches([{'key':str(i)}for i in range(20)]))==8
    assert max(len(group)for group in rw.import_batches([{'key':str(i),'kind':'source'}for i in range(130)]))==64


def test_stale_note_revision_keeps_newer_native_note(tmp_path,monkeypatch):
    save(tmp_path/'runtime/readweave/current.json',{'sections':{'s1':'article'}})
    monkeypatch.setattr(rw,'configured',lambda:True)
    def proxy(method,path,payload=None):
        assert method=='GET'
        return {'entries':[{'linkId':'link','contentType':'note','revision':2,'linkRevision':1,'body':'另一处的新笔记'}]}
    monkeypatch.setattr(rw,'proxy',proxy)
    with pytest.raises(rw.UpstreamError)as error:rw.note(None,{'id':'cas','path':str(tmp_path)},'s1:q1','旧输入',expected_revision=1,expected_link_revision=1)
    assert error.value.status==409
