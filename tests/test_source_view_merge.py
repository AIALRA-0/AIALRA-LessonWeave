"""合并来源时保留原顺序和文字，大批独立节点不再两两扫描"""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture
def merge_page():
    source = (Path(__file__).resolve().parents[1] / 'framework/reader/writing-demo.js').read_text('utf-8')
    functions = source[source.index('  function sourceIds(source)'):source.index('  function hasReadingMaterial(')]
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page()
        page.add_script_tag(content=functions+';window.merge=mergeSourceViews;')
        yield page
        browser.close()


def test_transitive_source_aliases_keep_order_fields_and_original_records(merge_page):
    sources = [
        {'id':'a','source_ids':['alias-a'],'type':'text','asset':'first.png','caption':'首份图注',
         'scope_note':'先读第一份','sentences':[{'id':'s1','original':'第一句'}],'original_texts':{'a':'原字'}},
        {'id':'b','type':'text','sentences':[{'id':'sb','original':'独立材料'}]},
        {'id':'c','source_ids':['alias-c'],'type':'text','asset':'later.png','scope_note':'再读第三份',
         'sentences':[{'id':'s2','original':'第二句'}],'original_texts':{'c':'第三份原字'}},
        {'id':'bridge','source_ids':['alias-c','alias-a'],'type':'figure','scope_note':'接在一起',
         'sentences':[{'id':'s2','original':'重复句不能覆盖'},{'id':'s3','original':'新增第三句'}]},
    ]
    result = merge_page.evaluate('''sources=>{const before=JSON.stringify(sources);return {groups:merge(sources),unchanged:before===JSON.stringify(sources)}}''', sources)
    assert result['unchanged']
    first, second = result['groups']
    assert first['id'] == 'bridge' and first['type'] == 'figure' and second['id'] == 'b'
    assert first['source_ids'] == ['a','alias-a','c','alias-c','bridge']
    assert first['asset'] == 'first.png' and first['caption'] == '首份图注'
    assert first['scope_notes'] == ['先读第一份','再读第三份','接在一起']
    assert first['original_texts'] == {'a':'原字','c':'第三份原字'}
    assert first['sentences'] == [{'id':'s1','original':'第一句'},{'id':'s2','original':'第二句'},{'id':'s3','original':'新增第三句'}]


def test_large_independent_source_pack_uses_id_index(merge_page):
    result = merge_page.evaluate('''()=>{
      let reads=0;const sources=Array.from({length:8000},(_,i)=>({id:'node-'+i,get source_ids(){reads++;return ['alias-'+i]},sentences:[{id:'sentence-'+i,original:'材料保持完整'}]}));
      const start=performance.now(),groups=merge(sources);return {count:groups.length,reads,last:groups.at(-1),milliseconds:performance.now()-start};
    }''')
    assert result['count'] == 8000
    assert result['reads'] <= 24000
    assert result['last']['source_ids'] == ['node-7999','alias-7999']
    assert result['last']['sentences'] == [{'id':'sentence-7999','original':'材料保持完整'}]
    assert result['milliseconds'] < 5000
