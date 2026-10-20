"""复用应保留完整定义，并允许同名特殊词义继续使用自己的解释"""
import copy,json
from lessonweave import pipeline
import glossary_reuse as reuse
import lean_contract as contract

def test_shared_term_expands_without_rewriting_three_paragraphs():
    term={'id':'old','chinese':'缓存','english':'Cache','abbreviation':None,'aliases':['cache'],'professional_definition':{'genus':'缓存保存数据','differentia':'缓存提供较近访问路径','boundary':'缓存不保证持续有效'},'intuitive_explanation':{'anchor':'工具托盘'},'typical_example':{'mechanism':'程序再次读取'}}
    entry={'key':'storage-cache-v1','term':term}
    prompt=contract.dumps({'question':{'title':'缓存怎样供数'},'materials':[],'glossary_rules':[]})
    prompt,schema,selected=reuse.prepare(prompt,contract.writer_schema({'single_choice':0,'short_answer':0}),[entry])
    value={'appendix':{'terms':[{'common_key':entry['key'],'id':'current','aliases':['资料缓存']},{'id':'special','chinese':'缓存','professional_definition':{'boundary':'特殊场景'}}]}}
    restored,hits=reuse.expand(value,selected)
    assert restored['appendix']['terms'][0]['professional_definition']==term['professional_definition']
    assert restored['appendix']['terms'][0]['typical_example']==term['typical_example']
    assert restored['appendix']['terms'][1]==value['appendix']['terms'][1]
    assert len(hits)==1 and value['appendix']['terms'][0].get('common_key')
    assert json.loads(prompt)['common_terms'][0]['boundary']==term['professional_definition']['boundary']

def test_library_does_not_match_short_english_names_inside_other_words():
    entry={'key':'ram','term':{'chinese':'随机存取存储器','english':'RAM','aliases':[],'professional_definition':{}}}
    prompt=contract.dumps({'question':{'title':'program grammar'},'materials':[],'glossary_rules':[]});schema=contract.writer_schema({})
    assert reuse.prepare(prompt,schema,[entry])==(prompt,schema,{})
