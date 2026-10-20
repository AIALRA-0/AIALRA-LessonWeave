"""核对显示换行可恢复且不会覆盖已经改写的内容，所有测试均不调用模型"""
import json
from lessonweave.legacy import author_format

def test_code_guide_formatting_keeps_source_bytes_and_formats_nested_question_titles():
    value={'kind':'code','text':'# 保留原句。\nprint(1)','guide':{'overview':{'premise':'程序需要输入。','action':'函数处理输入。','result':'程序取得输出。'},'segments':[{'title_question':'函数怎样使用输入','line_annotations':[{'sentence':'注释说明输入。'}]}]}}
    result,_=author_format(value)
    assert result['text']==value['text']
    assert result['guide']['segments'][0]['title_question']=='函数怎样使用输入？'
    assert result['guide']['overview']['action']=='函数处理输入'
import reader_whitespace


def test_repeated_official_name_is_not_shown_as_its_own_abbreviation():
    term={'kind':'official_name','english':'DCOH','abbreviation':'DCOH','chinese':'设备侧协调部件','definition':'设备负责协调'}
    result,changes=author_format(term)
    assert result['abbreviation']is None and result['english']=='DCOH'
    assert changes==['/abbreviation'] and term['abbreviation']=='DCOH'


def test_ambiguous_initialism_is_left_for_existing_name_checker():
    term={'kind':'initialism','english':'DCOH','abbreviation':'DCOH'}
    assert author_format(term)[0]==term


def test_author_format_keeps_prose_breaks_and_original_assets():
    # 新生成的自然段保留换行，源码、公式、图描述和原句保持原值
    original={'reasoning':'配置人员读取地址\n系统计算容量。','resources':[{'kind':'code','text':'a\nb'}, {'kind':'formula','text':'x\ny'},{'kind':'mermaid','text':'A-->B\nB-->C'}], 'original':'原句。\n原句'}
    result,_=author_format(original)
    assert result['reasoning']=='配置人员读取地址\n系统计算容量'
    assert result['resources']==original['resources']
    assert result['original']==original['original']


def test_restore_only_matches_original_flattening_and_keeps_repaired_words(tmp_path):
    # 显示记录只恢复完全一致的原换行，返修后改变的句子及素材代码不会被旧回执覆盖
    call=tmp_path/'runtime/calls/q-c-1/first';call.mkdir(parents=True)
    (call/'response.json').write_text(json.dumps({'reasoning':'第一段\n第二段','grounding':'原先\n证据','resources':[{'kind':'code','text':'code\ncode'}]}),encoding='utf-8')
    preview=tmp_path/'05_writing/preview';preview.mkdir(parents=True)
    document={'text':'第一段 第二段','other':'已经返修改写的证据','code':'code code'}
    path=preview/'section.json';before=json.dumps(document);path.write_text(before,encoding='utf-8')
    result=reader_whitespace.build(tmp_path)
    overlay=json.loads((tmp_path/'05_writing/reader-whitespace.json').read_text(encoding='utf-8'))
    assert result['restored_distinct_fields']==1
    assert overlay['replacements']=={'第一段 第二段':'第一段\n第二段'}
    assert path.read_text(encoding='utf-8')==before
