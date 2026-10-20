"""检查脚本修正真实对应关系，保留未确认的译文和附件内容状态"""
import copy
from jsonschema import Draft202012Validator
from lessonweave import pipeline,lean
import lean_contract as contract
from reader_repairs import bilingual,attachment,file_role

def test_language_keeps_chinese_labels_and_translates_english_with_chinese_names():
    from reader_repairs import is_chinese
    assert is_chinese('系统使用 `read_data` 和 FIFO 保存数据')
    assert is_chinese('Interface spec 与 `chk_integrity`](#1-interface-spec-与-chk_integrity)')
    assert not is_chinese('The text quotes 中国 as a name; its numerical value remains 16 MB.')

def test_translation_reuses_exact_original_and_holds_stale_target():
    originals={'a':'The cache holds data','b':'The cache holds data','c':'中文原句','d':'Untranslated English'}
    rows=[{'resource_id':'a','english':originals['a'],'chinese':'缓存保留数据'},
          {'resource_id':'b','english':'Different source','chinese':'错位的旧译文'},
          {'resource_id':'c','english':'Unrelated old translation','chinese':'另一个原句'}]
    fixed,stats=bilingual(originals,rows)
    assert fixed['b']['row']['chinese']=='缓存保留数据'
    assert fixed['b']['reused_from']==['a']
    assert fixed['c']['row']=={'resource_id':'c','chinese':'中文原句','english':''}
    assert fixed['c']['previous']['english']=='Unrelated old translation'
    assert fixed['d']['needs_review']
    assert stats=={'reused_exact_source':1,'english_on_demand':1,'chinese_needs_review':1}

def test_attachment_resolves_preserved_repo_path_without_claiming_pdf_explained(tmp_path):
    p=tmp_path/'00_source/materials/arbitrary-source/repository/docs/manual.pdf';p.parent.mkdir(parents=True);p.write_bytes(b'%PDF-1.7\n')
    value={'id':'m','kind':'file','file':{'local_path':'docs/manual.pdf'},'caption':'保留手册','source_refs':['source.file'],'guide':{}}
    original=copy.deepcopy(value);fixed=attachment(value,tmp_path)
    assert fixed['asset']=='/00_source/materials/arbitrary-source/repository/docs/manual.pdf'
    assert fixed['projection']['rows'][0][1]=='application/pdf'
    assert not fixed['content_explained'] and value==original
    assert file_role('folder/Thumbs.db')=='system_metadata'
    assert file_role('__MACOSX/anything')=='system_metadata'
    assert file_role('archive.unknown')=='attachment_inventory'

def test_quiz_task_schema_gives_each_kind_its_own_required_slot():
    from lessonweave.agents import wire_schema
    for quota in [{'single_choice':4,'short_answer':1},{'single_choice':0,'short_answer':0},{'single_choice':1,'short_answer':0}]:
        slots=wire_schema(contract.writer_schema(quota))['properties']['appendix']['properties']['quiz']
        assert len(slots['required'])==sum(quota.values())
        for name,field in slots['properties'].items():assert field['properties']['kind']['const']==name.rsplit('_',1)[0]
        assert list(Draft202012Validator(slots).iter_errors({})) if sum(quota.values()) else not list(Draft202012Validator(slots).iter_errors({}))
