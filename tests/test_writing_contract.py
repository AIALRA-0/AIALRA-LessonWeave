"""检查正式写作字段、实际正文绑定、轻量语言提示和旧稿保护，不调用模型"""
import copy
import json
import pytest

from lessonweave import pipeline
from lessonweave.architecture import snapshot
from lessonweave.storage import Store, save
import writing_contract as contract
import information_points

def test_composition_joins_continuations_without_duplicate_punctuation():
    assert contract.compose(['事务是一种工作单元，','它把操作作为整体提交；','，操作失败时系统撤销整个事务'])=='事务是一种工作单元，它把操作作为整体提交，操作失败时系统撤销整个事务'
    assert contract.compose(['系统接收输入','系统返回输出'])=='系统接收输入；系统返回输出'


def unit():
    return {'question_id':'q.1', 'premise':'配置人员需要同时保留两组缓冲区，前缀应覆盖哪个地址范围',
            'explanation':[{'id':'q.1-e1', 'point_ids':['p1'], 'claim':'前缀从地址零连续覆盖目标范围',
                            'reasoning':'设备需要保留中间的地址，因此配置人员应按最远结束地址选择范围',
                            'grounding':'假设两组缓冲区分别占用 0–16 MB 与 32–40 MB，前缀应覆盖 40 MB',
                            'supplement':'配置人员还应按允许的容量步长向上取值',
                            'resources':[{'id':'q.1-image', 'kind':'image', 'asset':'/00_source/figure.png', 'source_id':'n000036', 'caption':'两组缓冲区在地址空间中的位置'}]}],
            'result':{'generalization':'资源选择受连续范围约束时，配置人员应计算完整覆盖范围', 'answer':'配置人员应先确定最远结束地址'},
            'bindings':[{'point_id':'p1', 'block_ids':['q.1-e1-reasoning','q.1-e1-grounding','q.1-image'], 'explanation':'推导与实例共同解释范围'}]}


def test_new_unit_keeps_actual_text_order_assets_and_coverage_positions():
    # 四个自然段使用实际写作字段，图与绑定位置在转换后继续存在，答案顺序不依赖 JSON 键顺序
    value=unit(); before=copy.deepcopy(value)
    rendered=contract.reader_unit(value)
    inventory={'points':[{'id':'p1','question_id':'q.1'}]}
    pipeline.flow.runtime.unit_errors(rendered,'q.1',inventory)
    assert [b['text'] for b in rendered['explanation'][:4]] == [value['explanation'][0][k] for k in ['claim','reasoning','grounding','supplement']]
    assert rendered['explanation'][4]['source_id']=='n000036'
    assert rendered['bindings']==value['bindings']
    assert rendered['synthesis']['text'].startswith(value['result']['answer'])
    assert value==before


def test_missing_reasoning_or_fake_binding_is_rejected():
    # 缺少推导段会留下具体格式问题，已有内容继续渲染，实际绑定检查继续报告缺口
    value=unit(); del value['explanation'][0]['reasoning']
    findings=[]
    contract.validate(value,'writing-unit',findings)
    assert any('reasoning' in item for item in findings)
    assert contract.reader_unit(value)['explanation'][1]['text']==''
    value=contract.reader_unit(unit());value['bindings'][0]['block_ids']=['missing']
    with pytest.raises(ValueError,match='正文位置'):
        pipeline.flow.runtime.unit_errors(value,'q.1',{'points':[{'id':'p1','question_id':'q.1'}]})


def test_legacy_unit_is_read_without_inventing_new_fields():
    # 旧稿的原有段落保持原值，转换不会伪造四段组或改动旧笔记键
    value={'question_id':'q.1','explanation':[{'id':'old-id','kind':'paragraph','text':'已有正文'}]}
    assert contract.reader_unit(value)==value
    assert 'result' not in contract.reader_unit(value)


def test_subject_hints_do_not_become_blocking_grammar_checks():
    # 合法共享主语与非及物表达可以继续发布，疑似压缩只留下提示，源码中的编号继续保留
    value={'text':'先确定地址，再计算范围，按步长调整容量，保留必要空间，然后计算预算',
           'resources':[{'kind':'code','text':'n000036 = 1'}], 'source_quotes':[{'quote':'n000036'}]}
    findings=contract.surface_findings(value)
    assert findings and all(f['severity']=='hint' for f in findings)
    assert not contract.surface_findings({'text':'配置人员读取地址并计算容量，系统保持空闲'})
    assert contract.POLICY['language_review']=='disabled'
    assert contract.POLICY['dependency_parser']=='disabled'
    assert contract.POLICY['coverage_review_unchanged'] is True


def test_internal_reference_in_author_prose_is_an_error():
    # 作者正文泄漏材料编号会拦截，忠实原文和代码不参与此项扫描
    findings=contract.surface_findings({'text':'n000036 的原句说明配置步长'})
    assert findings[0]['severity']=='error'
    assert not contract.surface_findings({'original':'n000036 的原句', 'translation':'n000036', 'kind':'code','text':'n000036'})


def test_internal_reference_in_rendered_table_is_an_error():
    # 正文表格同样面向读者，嵌套单元格中的内部材料编号也要拦截
    findings = contract.surface_findings({'kind': 'table', 'headers': ['原文'], 'rows': [['n000036']]})
    assert any(item['severity'] == 'error' and item['location'].endswith('.rows[0][0]') for item in findings)


def test_term_name_and_three_paragraphs_follow_structure():
    # 定义组组成三段，重复的缩写按确定格式清空，完整定义继续渲染
    group=lambda *keys:{k:k+' 完整陈述' for k in keys}
    value={'id':'dram','abbreviation':'DRAM','chinese':'动态随机存取存储器','english':'Dynamic Random Access Memory',
           'professional_definition':group('boundary','genus','extension','differentia'),
           'intuitive_explanation':group('intuition','mapping','anchor','extension'),
           'typical_example':group('outcome','mechanism','initial_conditions','extension')}
    result=contract.reader_term(value)
    assert result['display']=='DRAM 动态随机存取存储器（Dynamic Random Access Memory）'
    assert result['definition'].startswith('genus 完整陈述；differentia')
    assert len(result['explanation'])==2 and result['explanation'][0].startswith('anchor')
    value['abbreviation']=' dynamic random access memory '
    assert contract.reader_term(value)['abbreviation'] is None


def test_information_point_coverage_rejects_missing_material_and_false_quotes():
    # 丢掉材料映射或替换成不存在的引文都会失败，多信息点可以共享真实来源
    rows=[{'source_id':'n1','content':{'text':'设备按 16 MB 步长配置容量'}}]
    point={'id':'p1','description':'配置步长','checks':['说明 16 MB'], 'source_ids':['n1'],
           'source_refs':[{'source_id':'n1','quote':'16 MB','region':'text'}]}
    assert information_points.validate({'points':[point]},rows)
    findings=[]
    information_points.validate({'points':[]},rows,findings=findings)
    assert any('没有对应' in item for item in findings)
    point['source_refs'][0]['quote']='32 MB'
    findings=[]
    information_points.validate({'points':[point]},rows,findings=findings)
    assert any('32 MB' in item for item in findings)


def test_structural_container_uses_actual_child_quote_without_invented_text():
    # 列表容器通过真实子项追溯，独立正文节点仍须提供自己的引文
    rows=[{'source_id':'list','content':{'ordered':False},'evidence_kind':'material_index','child_source_ids':['child']},
          {'source_id':'child','content':{'text':'保留域名用于文档示例'}}]
    point={'id':'p1','description':'文档示例用途','checks':['解释文档用途'],'source_ids':['list','child'],
           'source_refs':[{'source_id':'child','quote':'用于文档示例','region':'text'}]}
    assert information_points.validate({'points':[point]},rows)
    rows[0]['child_source_ids']=['unrelated']
    findings=[]
    information_points.validate({'points':[point]},rows,findings=findings)
    assert any('实际引文' in item for item in findings)


def test_container_alias_and_line_break_are_resolved_by_script():
    # 引文挂在容器下时，脚本找到唯一真实子项并恢复原换行，事实与容器对应继续保留
    rows=[{'source_id':'list','content':{'ordered':False},'evidence_kind':'material_index','child_source_ids':['child']},
          {'source_id':'child','content':{'text':'文档作者可以使用\n示例域名'},'source':[{'dom_path':'[data-iqa-source="child"]'}]}]
    point={'id':'p1','description':'示例域名用途','checks':['解释用途'],'source_ids':['list'],
           'source_refs':[{'source_id':'list','quote':'使用 示例域名','region':'list'}]}
    conversions=[]
    information_points.validate({'points':[point]},rows,conversions)
    assert point['source_ids']==['list','child']
    assert point['source_refs'][0]['source_id']=='child'
    assert point['source_refs'][0]['quote']=='使用\n示例域名'
    assert point['source_refs'][0]['region']=='[data-iqa-source="child"]'
    assert conversions


def test_context_index_contains_all_fields_not_derived_from_chapter_links(monkeypatch):
    # 写作前的关系索引由脚本生成，旧兼容 Schema 要求的字段必须全部保留
    import build_transitions
    from lessonweave.storage import read
    monkeypatch.setattr(build_transitions,'publish_transitions',lambda root,candidate:candidate)
    title={'id':'book','premise':'已经明确用途，','question':'该怎样理解服务范围？','children':[]}
    chapters={key:'version' for key in ['question_tree','question_run','material_tree','material_run','chapter_run']}
    chapters['tree']=title
    result=build_transitions.context_plan(None,chapters)
    schema=read(pipeline.FRAME/'04_transitions/transitions.schema.json')
    derived={'kind','core_question_ids','review_question_ids','previous_section_id','next_section_id','source_nodes','units'}
    assert set(schema['$defs']['node']['required'])-derived<=set(result['tree'])
    assert result['tree']['closing_boundary']


def test_every_generation_schema_uses_supported_wire_shapes_and_keeps_local_rules():
    # 一次检查所有新生成任务的接口结构，完整的复合约束仍留在本地 Schema 中执行
    from lessonweave.agents import wire_schema
    def check(node):
        if isinstance(node,dict):
            assert not {'allOf','not','uniqueItems'} & node.keys()
            if 'properties' in node:assert set(node['required'])==set(node['properties'])
            for child in node.values():check(child)
        elif isinstance(node,list):
            for child in node:check(child)
    for name in ['writing-unit','writing-extras','bridge','glossary']:
        check(wire_schema(contract.schema(name)))
    local=contract.schema('writing-unit')
    assert 'allOf' in local['properties']['premise']
    value=unit();value['premise']='第一段\n第二段'
    findings=[]
    contract.validate(value,'writing-unit',findings)
    assert findings


def test_all_diagram_nodes_have_table_fields_and_vertical_direction(tmp_path):
    # 每个竖向图节点都能找到字段行，图中使用通用描述，实际案例从项目文件读取
    result=snapshot(Store(tmp_path))
    assert result['template_version']=='0.14'
    for stage in result['stages']:
        assert stage['diagram'].startswith('flowchart TB')
        keys={f['key'] for f in stage['fields']}
        assert all(node['field_keys'] and set(node['field_keys'])<=keys for node in stage['nodes'])
        assert all(f['side'] in {'输入','输出'} and f['file'] for f in stage['fields'])


