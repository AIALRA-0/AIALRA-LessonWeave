"""保留完整资料，同时避免父容器把已分给其他问题的正文再次归给当前问题"""
from lessonweave import pipeline,lean
catalog=lean.catalog
import book_sources

def test_list_context_does_not_take_other_questions_children():
    a={'id':'a','type':'paragraph','children':[]};b={'id':'b','type':'paragraph','children':[]}
    parent={'id':'list','type':'list','children':[a,b]};nodes={n['id']:n for n in [parent,a,b]}
    q1={'id':'q1','source_nodes':['list','a'],'children':[]};q2={'id':'q2','source_nodes':['b'],'children':[]}
    owned=book_sources.question_owners([q1],nodes,{'q1':q1,'q2':q2})
    assert owned['a']==['q1'] and owned['b']==[]
    pack={'sources':[{'id':'a','question_ids':owned['a'],'sentences':[{'id':'a.s1','original':'A'}]}, {'id':'b','question_ids':owned['b'],'sentences':[{'id':'b.s1','original':'B'}]}]}
    assert [r['id']for r in catalog(pack)]==['a.s1']
    assert len(pack['sources'])==2 and pack['sources'][1]['sentences'][0]['original']=='B'

def test_complete_object_inherits_unassigned_children_without_losing_material():
    image={'id':'image','type':'image','children':[]};figure={'id':'figure','type':'figure','children':[image]};q={'id':'q','source_nodes':['figure'],'children':[]}
    owned=book_sources.question_owners([q],{'figure':figure,'image':image},{'q':q})
    assert owned['image']==['q']


def test_printable_pdf_bytes_are_not_taught_as_source_text():
    pdf=b'%PDF-1.4\n'+b'printable encoded binary stream '*100
    assert book_sources._decode(pdf)==(None,None)
    assert book_sources._decode(b'#!/bin/sh\necho hello\n')[0]=='#!/bin/sh\necho hello\n'

def test_opaque_file_is_kept_as_attachment_even_when_old_role_said_source():
    pack={'sources':[{'id':'f','question_ids':['q'],'sentences':[],'file_fragments':[{'source':{'path':'data.pdf'},'role':'source','read_policy':'original_attachment'}]}]}
    assert catalog(pack)[0]['kind']=='file'
