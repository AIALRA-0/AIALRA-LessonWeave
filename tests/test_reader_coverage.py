import json
import re
from pathlib import Path
from lessonweave import legacy
import source_disposition
import writing_contract


def test_chapter_zero_numbers_keep_positive_inner_levels():
    schema=writing_contract.schema('demo')
    section=schema['properties']['section_number']['pattern']
    unit=schema['properties']['units']['items']['properties']['number']['pattern']
    assert re.fullmatch(section,'0.1')and re.fullmatch(unit,'0.1.1')
    assert re.fullmatch(section,'12.2')and re.fullmatch(unit,'12.2.3')
    assert not re.fullmatch(section,'0.0')and not re.fullmatch(unit,'0.1.0')


def test_render_mapping_expands_aliases_but_preserves_real_omissions(tmp_path,monkeypatch):
    def save(name,value):
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value),encoding='utf8')
    save('02_questions/questions.json',{'dispositions':[]})
    monkeypatch.setattr(source_disposition,'evaluate',lambda *_:{'nodes':[
        {'material_node':key,'role':'teach'if key!='m4'else'reference'}for key in ['m1','m2','m3','m4']],
        'summary':{'total':4,'percentage':100,'roles':{'teach':3,'reference':1}}})
    save('coverage.json',{'block_sources':{'real-paragraph':[{'source_id':'m1'}]}})
    save('sources.json',{'sources':[{'id':'m1','source_ids':['m1','m2']},{'id':'m3'}],
        'representation_links':[{'material_node':'m2','canonical_source':'m1'}]})
    material={'tree':{'id':'root','children':[{'id':key,'type':'text','text':key,'children':[]}for key in ['m1','m2','m3','m4']]}}
    result=legacy.mapped_materials(tmp_path,{'s':{'grounding':{'coverage_path':'coverage.json','source_pack_path':'sources.json'}}},material)
    assert result['covered_material_nodes']==2
    assert result['teaching_material_nodes']==3
    assert result['material_mapping_percentage']==66.6667
    report=json.loads((tmp_path/'05_writing/checks/material-render-mapping.json').read_text('utf8'))
    assert report['missing_teaching_material_nodes']==['m3']


def test_two_inline_code_fragments_on_one_line_keep_unique_ids():
    import document_sources
    rows=document_sources.sentences('m1','Use <code>Thing</code> with <pre>int x;</pre> here')
    assert len({row['id']for row in rows})==len(rows)
    assert ''.join(row['original']for row in rows)=='Use <code>Thing</code> with <pre>int x;</pre> here'


def test_old_same_line_fragments_keep_both_originals_for_location(tmp_path):
    from prepare_source_locations import collect_packs
    source={'id':'m1','source':{},'sentences':[
        {'id':'m1.L1-L1','original':'<code>A</code>','verbatim_code':True,'start_line':1,'end_line':1},
        {'id':'m1.L1-L1','original':'<code>B</code>','verbatim_code':True,'start_line':1,'end_line':1}]}
    path=tmp_path/'pack.json'
    path.write_text(json.dumps({'material_run':'v1','material_path':'tree.json','sources':[source]}),encoding='utf8')
    row=collect_packs([path])[0]['sources']['m1']['sentences']['m1.L1-L1']
    assert row['original_variants']==['<code>A</code>','<code>B</code>']
    assert not row['location_conflict']


def test_reusing_normalized_source_keeps_exact_and_ambiguous_coordinates():
    from prepare_source_locations import unique_span,normalized_map
    text='value = 123;\n另一行包含 Alpha 和 Alpha；next = 4.5;'
    prepared=normalized_map(text)
    for original in ['123','Alpha','4.5','另一行包含','not present','23']:
        assert unique_span(original,text,prepared)==unique_span(original,text)


def test_web_fragment_keeps_stable_source_markers_after_layout_changes(tmp_path):
    from prepare_source_locations import prepare_web_dom,collect_packs
    html=tmp_path/'original.html';html.write_text('<html><body><div></div><main><p>Example</p></main></body></html>',encoding='utf8')
    sources=[{'id':key,'source':{'kind':'html','path':'original.html','selector':'html > body > main > p'},'sentences':[]}for key in ['m1','m2']]
    pack=tmp_path/'pack.json';pack.write_text(json.dumps({'material_run':'v1','material_path':'tree.json','sources':sources}),encoding='utf8')
    group=collect_packs([pack])[0]
    assert group['sources']['m1']['source']['dom_path']=='html > body > main > p'
    target=prepare_web_dom(tmp_path,group,tmp_path,{'original':{'original':'https://example.test/'}})
    rendered=target.read_text('utf8')
    assert 'data-lw-source="m1 m2"'in rendered and 'Example'in rendered
