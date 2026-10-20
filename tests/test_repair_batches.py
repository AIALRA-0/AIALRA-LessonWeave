"""检查同一轮修复的请求装包，不改变材料范围，也不调用真实模型"""
from lessonweave import legacy
import repair_batches as batching


def task(name):
    return {'document':name,'fragments':[{'path':'/result/answer','current':'需要调整的完整句子'}],
        'materials':[{'id':'r1','source_id':'n1','kind':'text','original':'原材料全文','question_ids':[name]}]}


def test_shared_materials_appear_once_and_tasks_keep_original_references():
    # 两份文档共用同一原句时，请求只存一份原句，每份任务继续指向相同的真实编号
    value=batching.pack([task('one'),task('two')],['保留事实'])
    assert len(value['material_pool'])==1
    assert [t['material_refs'] for t in value['tasks']]==[['r1'],['r1']]
    assert value['material_pool']['r1']['original']=='原材料全文'


def test_capacity_splits_whole_tasks_without_truncating_any_document():
    # 小容量只改变整份任务归入哪个批次，不丢字段、不拆开同一文档的改动
    values=[task('one'),task('two'),task('three')]
    groups=batching.split(values,[],input_bytes=1,change_bytes=1)
    assert [t for group in groups for t in group]==values and len(groups)==3


def test_media_field_repairs_receive_the_actual_media_schema():
    # 只返修媒体字段时，也要提供正式类型和字段约束，避免模型自行添加 file 类型
    value=task('media');value['fragments']=[{'path':'/explanation/0/resources/0','current':{}}]
    packed=batching.pack([value],[])
    kinds=[entry['properties']['kind']['const'] for entry in packed['schemas']['media-resource']['anyOf']]
    assert 'table' in kinds and 'file' not in kinds and 'c-unit' not in packed['schemas']


def test_sentence_repairs_do_not_receive_unrelated_media_schema():
    # 普通句式改写继续只携带局部文字，媒体规范不增加这类请求的输入量
    assert batching.pack([task('sentence')],[])['schemas']=={}
