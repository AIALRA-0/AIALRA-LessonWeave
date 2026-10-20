from pathlib import Path
import urllib.request,urllib.error
import pytest
from lessonweave import pipeline
from lessonweave.storage import save,read
from web_archive import offline_view
from tree_model import TreeBuilder,walk
from content_checks import attach_missing_content,coverage_report
import fitz


def test_private_archive_replay_is_local_without_public_authentication(tmp_path,monkeypatch):
    monkeypatch.setenv('LESSONWEAVE_AUTH_REQUIRED','1')
    monkeypatch.setenv('LESSONWEAVE_OWNER','synthetic-owner')
    (tmp_path/'example.wacz').write_bytes(b'archive-fixture')
    with offline_view(tmp_path)as(base,proxy,outbound):
        address=base+'/p/capture/archive.html?source=example.wacz&url=https://example.com/'
        assert base.startswith('http://127.0.0.1:')
        with urllib.request.urlopen(address)as response:assert b'LESSONWEAVE_ARCHIVE'in response.read()


def test_native_pdf_object_gets_its_own_source_and_page_crop(tmp_path):
    source=tmp_path/'original.pdf'
    with fitz.open()as pdf:
        page=pdf.new_page();page.insert_text((30,40),'Original table content');pdf.save(source)
    origin={'kind':'pdf','path':'original.pdf','page':1,'bbox':[20,20,250,80],'engine_ref':'#/tables/0'}
    builder=TreeBuilder();document={'format':'pdf','run':'run-0001','pages':[],'summary':{},'tree':builder.node('document',{'name':'材料'},[{'kind':'file','path':'original.pdf'}])}
    inventory={'scope':'原生对象','units':[{'id':'native-table','kind':'parser_object','native_text':'Actual cell','source':origin}]}
    attach_missing_content(tmp_path,document,inventory,builder)
    node=next(n for n in walk(document['tree'])if n['type']=='unknown')
    assert node['source']==[origin] and node['content']['text']=='Actual cell'
    assert (tmp_path/node['content']['asset'].lstrip('/')).is_file()
    assert coverage_report(tmp_path,document,inventory)['ratio']==1
