"""确认同次生成的骨架、正文和附属内容都进入原来的阅读流程"""
import copy
import pytest
from jsonschema import Draft202012Validator
from lessonweave import pipeline, lean
from lessonweave.legacy import author_format
import lean_contract as contract


def wire():
    return {'p':{'t':'程序重复读数据，缓存怎样减少等待？','r':'先看复用，再看命中',
                 's':[{'i':'g1','t':'程序再次读取','q':'缓存怎样供数？','c':'缓存保留常用数据',
                       's':[{'k':'机制','d':'第一次保存，再次命中','a':['n1.s1']}],'n':None}]},
            'premise':'同一个数据读两遍，会发生什么？',
            'explanation':[{'i':'g1','b':'第一次读完，缓存留下数据。\n再次读取时，程序直接取得副本。',
                            'x':None,'resources':[]}],
            'result':{'answer':'再次读取可以命中缓存','generalization':'结合实际复用距离判断'},
            'appendix':{'pitfalls':[],'quiz':{},'terms':[],'local_notations':[]}}


def test_same_call_retains_continuous_body_and_source_bindings():
    raw=wire()
    Draft202012Validator(contract.writer_schema({})).validate(raw)
    normalized=contract.reader_quiz(raw,'q.1.1')
    assert not contract.findings(normalized,'c-unit')
    assert normalized['explanation'][0]['body']==raw['explanation'][0]['b']
    assert normalized['plan']['items'][0]['explain']['steps'][0]['resource_ids']==['n1.s1']
    formatted,_=author_format(normalized)
    assert '。' not in formatted['explanation'][0]['body']
    rendered=lean.reader_unit(formatted)
    assert any(b['id']=='q.1.1-e1-body' for b in rendered['explanation'])
    report,links=lean.coverage([formatted],[{'id':'n1.s1','source_id':'n1','kind':'text','question_ids':['q.1.1']}])
    assert report['percentage']==100 and links['q.1.1-e1-body'][0]['sentence_ids']==['n1.s1']
    assert raw['explanation'][0]['b'].endswith('副本。')


def test_missing_or_duplicate_body_is_not_silently_discarded():
    value=wire();value['explanation']=[]
    with pytest.raises(ValueError,match='逐一对应'):contract.reader_quiz(value,'q.1.1')
    value=wire();value['explanation']*=2
    with pytest.raises(ValueError,match='逐一对应'):contract.reader_quiz(value,'q.1.1')


def test_generation_schema_keeps_media_and_fixed_appendix_slots():
    schema=contract.writer_schema({'single_choice':4,'short_answer':1})
    assert len(schema['properties']['appendix']['properties']['quiz']['required'])==5
    assert set(schema['properties']['appendix']['required'])=={'pitfalls','quiz','terms','local_notations'}
    assert schema['properties']['explanation']['items']['properties']['resources']['items']['anyOf']
    assert 'question_id' not in schema['properties']
    assert len(contract.WRITING_RULES)==9


def test_reader_title_is_formatted_before_assembly():
    value=contract.reader_quiz(wire(),'q.1.1');value['reader_title']='程序再次读取，缓存怎样供数'
    formatted,changes=author_format(value)
    assert formatted['reader_title']=='程序再次读取，缓存怎样供数？'
    assert '/reader_title' in changes


def test_unparsed_attachment_keeps_file_metadata_without_fabricating_content(tmp_path):
    (tmp_path/'sample.bin').write_bytes(b'\x00\x01')
    source={'id':'n1','asset':'/sample.bin','question_ids':['q.0.1'],
            'sentences':[{'id':'n1.index','evidence_kind':'material_index','original':'index'}]}
    rows=lean.catalog({'sources':[source]},tmp_path)
    assert rows[0]['kind']=='file' and '"bytes":2' in rows[0]['original']
    source['raw_content']={'reading_role':'hidden_control'}
    assert lean.catalog({'sources':[source]},tmp_path)==[]
