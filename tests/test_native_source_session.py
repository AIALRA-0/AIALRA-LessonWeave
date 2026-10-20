"""核对原生取材保留真实字节、节点对应和查阅用途，不调用模型"""
import json
from pathlib import Path
from lessonweave import pipeline,legacy
from lessonweave.storage import save,read
from tree_model import check_tree
import book_sources
import source_disposition


def native_fixture(root,tmp_path,monkeypatch):
    pipeline.scaffold(root)
    repo=tmp_path/'original';repo.mkdir()
    (repo/'sample.py').write_bytes(b'a=1\nb=2\n')
    nodes=[{'id':'file','type':'file','text':'sample.py','source':{'path':'sample.py'},'children':[]},
           {'id':'statement','type':'function_definition','text':'a','source':{'path':'sample.py','start_byte':0,'end_byte':4},'children':[]}]
    material={'format':'full-material-tree','kind':'code','run':'r1','repository':str(repo),
              'tree':{'id':'root','type':'repository','text':'sample','children':nodes}}
    save(root/'01_tree/tree.json',material)
    q={'tree':{'id':'q.root','children':[{'id':'q.1','children':[]}]}}
    save(root/'02_questions/questions.json',q)
    save(root/'03_chapters/chapters.json',{'tree':{'id':'book','kind':'book','children':[{'id':'section','kind':'section','question_ids':['q.1'],'children':[]}]}})
    save(root/'04_transitions/transitions.json',{'question_tree':'02_questions/questions.json',
         'chapters_path':'03_chapters/chapters.json','material_tree':'01_tree/tree.json','material_run':'r1'})
    monkeypatch.setattr(source_disposition,'evaluate',lambda q,m:{'nodes':[
        {'material_node':'file','role':'teach','question_ids':['q.1']},
        {'material_node':'statement','role':'teach','question_ids':['q.1']}]})
    return material


def test_overlapping_native_ranges_are_read_once_with_all_node_links(tmp_path,monkeypatch):
    root=tmp_path/'project';material=native_fixture(root,tmp_path,monkeypatch)
    session=book_sources.prepare_session(root)
    pack=book_sources.prepare_sources(root,'section',root/'work',session=session)
    assert len(pack['sources'])==1
    source=pack['sources'][0]
    assert set(source['source_ids'])=={'file','statement'} and source['id']=='file'
    assert source['original_texts']['file']=='a=1\nb=2\n'
    assert ''.join(s['original']for s in source['sentences'])=='a=1\nb=2\n'
    assert len(pack['representation_links'])==2
    assert read(root/'01_tree/tree.json')==material


def test_reference_material_keeps_location_without_becoming_body_input(tmp_path,monkeypatch):
    root=tmp_path/'project';native_fixture(root,tmp_path,monkeypatch)
    monkeypatch.setattr(source_disposition,'evaluate',lambda q,m:{'nodes':[
        {'material_node':'file','role':'reference','question_ids':['q.1']}]})
    session=book_sources.prepare_session(root)
    pack=session.pack('section',root/'work')
    from lessonweave.lean import catalog
    assert pack['sources'][0]['reading_role']=='reference'
    assert catalog(pack)==[]


def test_native_tree_checker_detects_duplicate_ids_and_broken_children(tmp_path):
    doc={'format':'full-material-tree','kind':'web','run':'r','tree':{'id':'x','type':'webpage','children':[
        {'id':'x','type':'text','text':'original','children':[]}]}}
    assert any('唯一编号'in e for e in check_tree(doc,{},tmp_path))
    doc['tree']['children']=['broken']
    assert any('children'in e for e in check_tree(doc,{},tmp_path))
