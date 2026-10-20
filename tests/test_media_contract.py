"""检查九类素材字段、来源、真实资源与代码行覆盖，全部使用本地数据"""
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from lessonweave import pipeline
import media_contract
import writing_contract

ROOT = pipeline.FRAME / 'examples/media'
RESOURCES = json.loads((ROOT / 'resources.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('resource', RESOURCES, ids=lambda value: value['kind'])
def test_each_approved_media_kind_has_valid_fields_assets_and_refs(resource):
    # 九类真实样例都应通过字段、来源 ID、本地文件和代码行号检查
    assert media_contract.check(resource, ROOT, {r['source_refs'][0] for r in RESOURCES}) == []


def test_code_annotations_and_segment_ownership_report_missing_or_wrong_lines():
    # 删除行注、越界归属与重复分段都会给出具体问题，检查器保留原始数据
    code = copy.deepcopy(next(r for r in RESOURCES if r['kind'] == 'code'))
    code['guide']['line_annotations'].pop(0)
    assert any('缺少行注' in item for item in media_contract.check(code))
    code['guide']['segments'].append(copy.deepcopy(code['guide']['segments'][0]))
    assert any('重复' in item for item in media_contract.check(code))
    code['guide']['segments'][0]['line_end'] = len(code['text'].splitlines()) + 1
    assert any('超出' in item for item in media_contract.check(code))


def test_console_prompts_and_decorative_comments_do_not_create_repair_tasks():
    assert media_contract.required_code_lines('>>> value=1\n...\n>>>\n#\n# ▓▓▓\n# description\nprint(value)')=={1,6,7}
    assert media_contract.required_code_lines('...\npass')=={1,2}


def test_resource_lookup_and_shape_check_use_actual_source_data(tmp_path):
    # 来源 ID、资源路径、表格列数和模型索引分别检查，正文长度与这些结果无关
    image = copy.deepcopy(RESOURCES[0])
    assert any('来源不存在' in item for item in media_contract.check(image, source_ids=set()))
    assert any('本地资源不存在' in item for item in media_contract.check(image, tmp_path))
    table = copy.deepcopy(next(r for r in RESOURCES if r['kind'] == 'table'))
    table['rows'][0].pop()
    assert any('相同列数' in item for item in media_contract.check(table))
    model = copy.deepcopy(next(r for r in RESOURCES if r['kind'] == 'model'))
    model['parts'][0]['face_indices'] = [len(model['faces'])]
    assert any('超出实际网格' in item for item in media_contract.check(model))


def test_authored_guide_rules_preserve_raw_code_and_formulas():
    # 源码保持准确，作者讲解中的内部编号、绕行句式和中文句号留下明确检查项
    code = copy.deepcopy(next(r for r in RESOURCES if r['kind'] == 'code'))
    code['text'] += '\n# n000036 不是正文。\n'
    last = len(code['text'].splitlines())
    code['guide']['line_annotations'].append({'line_start':last, 'line_end':last, 'role':'源码注释', 'sentence':'注释保留源文件的原有内容'})
    code['guide']['segments'][-1]['line_end'] = last
    assert not media_contract.check(code)
    code['guide']['overview']['premise'] = 'n000036 不是正文。'
    assert any('作者文字' in item for item in media_contract.check(code))


def test_new_resources_pass_actual_generation_schema_and_conversion():
    # 新媒体经过正式写作转换后仍保留完整 guide、资源 ID 和来源映射，必要补充可以为空
    value = {'question_id':'q', 'premise':'使用者需要核对多种素材，系统怎样保留实际来源',
             'explanation':[{'id':'q-g1','point_ids':['p1'],'claim':'系统在各素材附近展示独立解释',
                 'reasoning':'每项素材具有自己的字段，阅读器据此选择相应展示方式',
                 'grounding':'下面九项教学素材分别保留实际内容与讲解字段', 'supplement':None, 'resources':RESOURCES}],
             'result':{'answer':'系统保存原始内容与结构化解释','generalization':'结构化字段可以让不同宿主复用同一份素材'},
             'bindings':[{'point_id':'p1','block_ids':['q-g1-claim'],'explanation':'陈述说明展示方法'}]}
    findings = []
    writing_contract.validate(value, 'writing-unit', findings)
    assert findings == []
    result = writing_contract.reader_unit(value)
    assert result['explanation'][3:] == RESOURCES
    assert result['bindings'] == value['bindings']
    from book_generation import BLOCK
    for resource in RESOURCES:
        assert not list(Draft202012Validator(BLOCK).iter_errors(resource))


def test_legacy_resources_still_validate_and_guides_have_no_demo_size_limit():
    # 旧图片块继续有效，代码行号上限由实际源码决定，规范中保留功能说明与独立讲解要求
    old = {'id':'old','kind':'image','asset':'/00_source/image.png','source_id':'source','caption':'原图'}
    choices = writing_contract.schema('writing-unit')['properties']['explanation']['items']['properties']['resources']['items']
    assert not list(Draft202012Validator(choices).iter_errors(old))
    rule_text = ' '.join(media_contract.prompt_rules())
    assert '功能逻辑' in rule_text and 'reading_guide' in rule_text and '已经提供的实际输入输出' in rule_text
    assert 'maximum' not in writing_contract.schema('code-guide')['properties']['line_annotations']['items']['properties']['line_end']


def test_native_media_seeking_uses_real_byte_ranges():
    # 浏览器可以请求起始片段、后续片段或尾部，越界与多范围请求回落到完整文件读取
    from lessonweave.server import Handler
    assert Handler.media_byte_range('bytes=0-', 120) == (0,119)
    assert Handler.media_byte_range('bytes=50-79', 120) == (50,79)
    assert Handler.media_byte_range('bytes=-20', 120) == (100,119)
    assert Handler.media_byte_range('bytes=120-', 120) is None
    assert Handler.media_byte_range('bytes=0-9,20-29', 120) is None
