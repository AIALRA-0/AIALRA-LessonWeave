"""共享文章保留代码讲解里的实际文字，结构字段不会被打印成字典"""
from lessonweave.shared_html import article_html


def test_code_guide_keeps_overview_steps_examples_and_components():
    block={'id':'code-1','kind':'code','text':'result = value + 1','language':'python','caption':'代码题注','runs':[],
           'guide':{'overview':{'premise':'输入前提','action':'执行动作','result':'得到结果'},
                    'segments':[{'title_premise':'检查当前输入','title_question':'下一步怎样做',
                       'overview':{'premise':'分段前提','action':'分段动作','result':'分段结果'},
                       'components':[{'owner':'所属函数','name':'参数名称','kind':'参数种类','type':'类型名','default':'默认值','purpose':'参数用途'}],
                       'core_logic':[{'explanation':'机制解释','example':'具体算例'}],
                       'takeaway':{'conclusion':'分段结论','relation_to_whole':'与整体的关系'}}],
                    'summary':{'answer':'完整回答','collaboration':'如何协作'},
                    'line_annotations':[{'line_start':1,'sentence':'这一行的说明'}]}}
    doc={'core_questions':[{'question_id':'q1','text':'当前问题'}],
         'units':[{'title':'当前标题','problem':{'text':'问题段'},'explanation':[block],'synthesis':{'text':'结论段'}}],
         'summary':[],'glossary':[{'display':'默认定义','definition':'单独登记到ReadWeave的定义','explanation':[]}],
         'local_notations':[{'symbol':'x','definition':'局部符号含义'}]}
    value=article_html(doc,{})
    for expected in ['输入前提','执行动作','得到结果','分段前提','分段动作','分段结果','所属函数','参数名称','参数种类','类型名','默认值','参数用途','机制解释','具体算例','分段结论','与整体的关系','完整回答','如何协作','这一行的说明','局部符号含义']:
        assert expected in value
    assert value.count('result = value + 1')==1
    assert "'premise':"not in value and "'action':"not in value
    assert 'data-shared-media="code-1"'in value
    assert '单独登记到ReadWeave的定义'not in value
