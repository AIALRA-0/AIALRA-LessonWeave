"""验证规划同步只使用现有讲解关系，不改正文、不减少应讲材料"""
import copy
from lessonweave import legacy
import plan_sync

RESOURCES=[{'id':'n1.s1','source_id':'n1','question_ids':['q1']},{'id':'n1.s2','source_id':'n1','question_ids':['q1']}]


def example():
    return {'question_id':'q1','plan':{'items':[{'id':'p1','statement':'解释既有材料','resource_ids':['n1.s1','n1.s3']}]},
        'explanation':[{'id':'g1','plan_ids':['p1'],'resource_ids':['n1.s1','n1.s2'],'claim':'正文保持这句话'}]}


def test_completed_body_can_fill_its_explicit_plan_references():
    # 正文完整引用了两条真实资料，规划按同一 plan_ids 关系引用它们，正文保持原样
    value=example();before=copy.deepcopy(value['explanation']);changes=plan_sync.align(value,RESOURCES)
    assert changes and value['plan']['items'][0]['resource_ids']==['n1.s1','n1.s2']
    assert value['explanation']==before and plan_sync.align(value,RESOURCES)==[]


def test_missing_body_material_stays_missing():
    # 正文少讲任何已分配材料时，脚本不通过改规划来抹去缺漏
    value=example();value['explanation'][0]['resource_ids']=['n1.s1'];before=copy.deepcopy(value)
    assert plan_sync.align(value,RESOURCES)==[] and value==before


def test_unknown_foreign_source_stays_visible_to_checker():
    # 其他来源的未知引用继续保留，检查器仍能指出这处问题
    value=example();value['plan']['items'][0]['resource_ids'].append('n999.s1')
    plan_sync.align(value,RESOURCES)
    assert 'n999.s1' in value['plan']['items'][0]['resource_ids']


def test_valid_many_to_many_plan_stays_unchanged():
    # 多个规划共同由一个讲解组展开时，已有映射完整就保持原样，避免无谓扩张规划引用
    value=example();value['plan']['items']=[{'id':'p1','resource_ids':['n1.s1']},{'id':'p2','resource_ids':['n1.s2']}]
    value['explanation'][0]['plan_ids']=['p1','p2'];before=copy.deepcopy(value)
    assert plan_sync.align(value,RESOURCES)==[] and value==before
