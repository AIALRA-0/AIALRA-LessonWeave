"""只用本地数据检查缺漏、忠实原句豁免和单轮批量改动，不调用真实模型"""
import copy
import json
from lessonweave import checks
from lessonweave.storage import save,read
import independent_checks as rules
import lean_contract as contract


def unit():
    return {'question_id':'q1','plan':{'items':[{'id':'p1','statement':'说明缓存保留数据的作用','resource_ids':['r1']}]},
        'premise':'程序反复访问数据时，缓存怎样供数？',
        'explanation':[{'id':'g1','title_premise':'程序复用数据','title_question':'缓存怎样供数？','claim':'缓存保留数据',
            'reasoning':'核心通过较近的路径取得数据','grounding':'程序再次加载已保留的数据','supplement':None,
            'resource_ids':['r1'],'plan_ids':['p1'],'resources':[]}],
        'result':{'answer':'缓存保留数据以供后续访问','generalization':'程序应结合复用情况选择容量'},
        'appendix':{'pitfalls':[],'quiz':[],'terms':[],'local_notations':[]}}


RESOURCES=[{'id':'r1','source_id':'n1','kind':'text','original':'Cache retains data','question_ids':['q1']}]


def test_original_punctuation_rule_still_applies_to_conversational_writing():
    from lessonweave.legacy import author_format
    value=unit();value['explanation'][0]['reasoning']='核心先查找缓存。找到数据后，就可以继续执行。'
    value['reader_title']='缓存能让程序少等多久？'
    assert any(f['rule']=='lint' for f in rules.unit_findings(value,RESOURCES,{},'q1'))
    result,_=author_format(value)
    assert result['explanation'][0]['reasoning']=='核心先查找缓存；找到数据后，就可以继续执行'
    assert result['reader_title']==value['reader_title']
    assert not [f for f in rules.unit_findings(result,RESOURCES,{},'q1')if f['rule']in {'schema','lint'}]


def test_script_detects_missing_actual_mapping_and_invalid_schema():
    # 删除映射或必填的因果展开字段时，检查器指出实际缺漏
    value=unit();value['explanation'][0]['resource_ids']=[]
    assert any(f['rule']=='material_coverage' for f in rules.unit_findings(value,RESOURCES,{'single_choice':0,'short_answer':0},'q1'))
    value=unit();del value['explanation'][0]['reasoning']
    assert any(f['rule']=='schema' for f in rules.unit_findings(value,RESOURCES,{},'q1'))


def test_translation_keeps_original_punctuation_and_negative_words():
    # 原句和忠实译文保留原有否定及标点，不进入作者句式检查
    resources=[dict(RESOURCES[0],original='This cannot be changed.')]
    value={'translations':[{'resource_id':'r1','english':'This cannot be changed.','chinese':'这不能更改。'}]}
    assert rules.translation_findings(value,resources)==[]


def test_no_findings_skips_model_repair(tmp_path,monkeypatch):
    # 没有检查问题时，修复模型调用次数为零
    report={'passed':True,'findings':[]}
    monkeypatch.setattr(checks,'scan',lambda root:report)
    class Backend:
        def _call_once(self,*args):raise AssertionError('无问题时不调用模型')
    result=checks.run(tmp_path,Backend())
    assert result['model_calls']==0 and result['rounds']==0


def test_multiple_findings_use_one_model_call_and_keep_unaffected_fields(tmp_path,monkeypatch):
    # 两处明确句式问题共用一次修复请求，其他正文和空字段保持原样
    path='05_writing/work/sections/s1/unit-q1.json';value=unit()
    value['explanation'][0]['claim']='这不是副本而是缓存';value['result']['answer']='这不是说明条件而是保留数据'
    save(tmp_path/path,value)
    def scan(root):
        current=read(root/path);findings=[dict(f,document=path) for f in rules.unit_findings(current,RESOURCES,{},'q1')]
        return {'passed':not findings,'findings':findings}
    monkeypatch.setattr(checks,'scan',scan);calls=[]
    class Backend:
        def _call_once(self,name,prompt,schema):
            calls.append(name)
            return {'changes':[{'document':path,'path':'/explanation/0/claim','value_json':json.dumps('缓存保留数据')},
                               {'document':path,'path':'/result/answer','value_json':json.dumps('缓存保留数据以供后续访问')}]}
    result=checks.run(tmp_path,Backend())
    assert result['passed'] and calls==['c_repair-batch']
    assert read(tmp_path/path)['explanation'][0]['reasoning']==value['explanation'][0]['reasoning']
    assert read(tmp_path/path)['explanation'][0]['supplement'] is None


def test_factual_negative_does_not_trigger_rephrasing():
    value=unit();value['result']['answer']='当前测试无法确定队列容量，读取没有命中时不能直接得到缓存数据，机会成本按最佳替代的400元计算，而不是按两个替代相加的650元计算'
    assert not [f for f in rules.unit_findings(value,RESOURCES,{},'q1') if f['rule']=='lint']


def test_compact_output_rule_keeps_detailed_fields_and_nulls():
    # 紧凑输出只改变排版要求，三段细字段与可空拓展字段继续保留
    text=' '.join(contract.glossary_rules())
    assert '紧凑 JSON' in text and '空字段' in text and 'differentia' in text and 'initial_conditions' in text


def test_independent_unit_ids_do_not_collide_after_script_assembly(tmp_path):
    # 两个独立写作任务都返回 g1 时，装配脚本仍为它们保留独立块 ID 与来源对应
    first=unit();second=unit();second['question_id']='q2'
    save(tmp_path/'05_writing/work/sections/s1/unit-q1.json',first)
    save(tmp_path/'05_writing/work/sections/s1/unit-q2.json',second)
    changed=checks.namespace_blocks(tmp_path)
    a=read(tmp_path/'05_writing/work/sections/s1/unit-q1.json');b=read(tmp_path/'05_writing/work/sections/s1/unit-q2.json')
    assert a['explanation'][0]['id']=='q1-g1' and b['explanation'][0]['id']=='q2-g1'
    assert a['explanation'][0]['claim']==first['explanation'][0]['claim'] and len(changed)==2
    assert checks.namespace_blocks(tmp_path)==[]


def test_missing_translation_is_appended_and_original_is_copied_without_regeneration(tmp_path,monkeypatch):
    # 漏译只交给翻译模型，脚本复制英文原句，内容修复模型不重复生成译文
    rid='n000001.s1';resource=dict(RESOURCES[0],id=rid)
    path='05_writing/translations.json';save(tmp_path/path,{'translations':[]})
    save(tmp_path/'05_writing/translation-originals.json',{rid:resource['original']})
    save(tmp_path/'05_writing/work/sections/s1/resources.json',[resource])
    def scan(root):
        findings=[dict(f,document=path) for f in rules.translation_findings(read(root/path),[resource])]
        return {'passed':not findings,'findings':findings}
    monkeypatch.setattr(checks,'scan',scan);calls=[]
    from lessonweave import agents
    class TranslationBackend:
        def __init__(self,root,role):
            assert role=='lean_translation_repair'
        def _call_once(self,name,prompt,schema):
            calls.append(name)
            return {'translations':[{'resource_id':rid,'translation':'缓存保留数据'}]}
    monkeypatch.setattr(agents,'Backend',TranslationBackend)
    class Backend:
        def _call_once(self,*args,**kwargs):
            raise AssertionError('漏译无需调用内容修复模型')
    result=checks.run(tmp_path,Backend())
    assert result['passed'] and calls==['c_repair-translation']
    assert result['translation_calls']==1 and result['content_calls']==0
    assert read(tmp_path/path)['translations'][0]['english']==resource['original']


def test_mermaid_syntax_newlines_survive_formatting_and_old_output_assembly(tmp_path):
    # 流程图保留语法换行，旧格式转换压掉的换行只从实际模型原稿恢复，讲解文字保持原样
    from lessonweave.legacy import author_format
    graph={'id':'chart','kind':'mermaid','text':'flowchart TD\nA --> B\nB --> C'}
    assert author_format(graph)[0]['text']==graph['text']
    raw=unit();raw['explanation'][0]['resources']=[graph]
    value=copy.deepcopy(raw);value['explanation'][0]['resources'][0]['text']=graph['text'].replace('\n',' ')
    path=tmp_path/'05_writing/work/sections/s1/unit-q1.json';save(path,value)
    save(tmp_path/'runtime/calls/s1-c-q1/request/response.json',raw)
    changes=checks.namespace_blocks(tmp_path)
    assert read(path)['explanation'][0]['resources'][0]['text']==graph['text']
    assert read(path)['explanation'][0]['claim']==raw['explanation'][0]['claim']
    assert changes[0]['syntax'] and checks.namespace_blocks(tmp_path)==[]


def test_catalog_uses_real_images_and_existing_model_previews():
    # 附件路径不等于图片，真实图片继续使用底层解析器已经生成的模型预览
    from lessonweave.lean import catalog
    pack={'sources':[{'id':'metadata','asset':'/00_source/.DS_Store'},
                     {'id':'figure','asset':'/00_source/chart.svg','question_ids':['q1']}],
          'visual_assets':[{'source_id':'figure','model_path':'F:/preview/chart.png'}]}
    rows=catalog(pack)
    assert len(rows)==1 and rows[0]['id']=='figure.image'
    assert rows[0]['model_asset']=='F:/preview/chart.png'


def test_resource_files_keep_declared_file_scope_instead_of_loading_all_glyph_data(tmp_path):
    # 材料树只登记资源文件时，模型收到文件用途及全部引用编号，字体内部数据继续保存在原文件
    from lessonweave.lean import catalog
    pack={'sources':[{'id':'font','sentences':[],'file_fragments':[{'role':'resource','source':{'path':'font.flf'},
          'file_bytes':6000000,'read_policy':'indexed_complete','text_storage':{'path':'not-opened.json'}}]}]}
    rows=catalog(pack)
    assert rows[0]['kind']=='file' and rows[0]['scope']=='file_role'
    save(tmp_path/'01_tree/tree.json',{'tree':{'id':'root','children':[{'id':'font','content':{'role':'resource','name':'font.flf','bytes':6000000}}]}})
    old=[{'id':'font.chunk1','source_id':'font','kind':'code','original':'glyph data'},
         {'id':'font.chunk2','source_id':'font','kind':'code','original':'more glyph data'}]
    adapted=checks.file_role_context(tmp_path,old)
    assert adapted[0]['resource_ids']==['font.chunk1','font.chunk2']
    assert adapted[0]['file']['bytes']==6000000 and 'glyph data' not in json.dumps(adapted)


def test_source_line_ranges_resolve_to_complete_existing_chunks_without_model_repair(tmp_path):
    # 合并行范围只有在完整覆盖已有连续片段时才展开，缺少实际来源的范围继续留给检查器
    value=unit();value['explanation'][0]['resources']=[{'id':'flow','kind':'mermaid','text':'flowchart TD\nA --> B',
        'source_refs':['n1.L1-L40','n1.L1-L60']}]
    folder=tmp_path/'05_writing/work/sections/s1';save(folder/'unit-q1.json',value)
    save(folder/'resources.json',[{'id':'n1.L1-L20','source_id':'n1'},{'id':'n1.L21-L40','source_id':'n1'}])
    checks.namespace_blocks(tmp_path)
    refs=read(folder/'unit-q1.json')['explanation'][0]['resources'][0]['source_refs']
    assert refs==['n1.L1-L20','n1.L21-L40','n1.L1-L60']


def test_reader_projection_keeps_nullable_term_fields():
    # 阅读投影与生成合同保留相同的可空元数据，不把 null 变成缺少字段
    from book_generation import normalize_term
    from jsonschema import Draft202012Validator
    import writing_contract
    term={'id':'t1','kind':'official_name','official_spelling':None,'case_source':None}
    assert normalize_term(term)==term
    for name in ['official_spelling','case_source']:
        Draft202012Validator(writing_contract.schema('demo')['$defs']['term']['properties'][name]).validate(None)


def test_verbatim_source_sentences_stay_out_of_natural_language_translation():
    # 解析器标记的源码行继续原样展示，不把整段源码送去翻译
    from lessonweave.lean import catalog
    value=catalog({'sources':[{'id':'n1','sentences':[{'id':'n1.L1-L2','original':'return value','verbatim_code':True}]}]})
    assert value[0]['kind']=='code'
