"""检查逐问生成的调用次数、去重、复用与默认入口，测试只使用本地桩数据"""
import copy
import json
from lessonweave import pipeline, lean
from lessonweave.storage import read,save
import lean_contract as contract
import bridge_batches


def test_default_entry_uses_lean_once_and_does_not_start_legacy_rounds(tmp_path,monkeypatch):
    # 正式入口默认转交轻量流程，调用方传入旧修复轮数也不会启动内容返修
    calls=[]
    monkeypatch.setattr(lean,'run',lambda root,maximum:calls.append((root,maximum)) or {'status':'completed'})
    assert pipeline.run(tmp_path,3)['status']=='completed'
    assert calls==[(tmp_path,3)]


def test_quiz_quota_preserves_four_choices_and_one_short_answer():
    # 每节在写作前分配题数，问题数量变化时仍保持四道单选和一道简答
    for count in [1,2,4,7]:
        quotas=[lean.quota(i,count) for i in range(count)]
        assert sum(q['single_choice'] for q in quotas)==4
        assert sum(q['short_answer'] for q in quotas)==1


def test_translation_deduplicates_and_reuses_only_matching_originals(tmp_path):
    # 两节共用同一原句时只翻译一次，原句改变后重新翻译，旧 ID 本身不代表文本仍相同
    calls=[]
    class Backend:
        def _call_once(self,name,prompt,schema):
            rows=json.loads(prompt)['resources'];calls.append(rows)
            return {'translations':[{'resource_id':r['id'],'translation':'中文译文'} for r in rows]}
    row={'id':'r1','kind':'text','original':'One source'}
    lean.translate(tmp_path,Backend(),[row,copy.deepcopy(row)],[])
    lean.translate(tmp_path,Backend(),[row],[])
    row['original']='Changed source'
    lean.translate(tmp_path,Backend(),[row],[])
    assert len(calls)==2 and all(len(rows)==1 for rows in calls)
    lean.translate(tmp_path,Backend(),[row],[{'material_run':'run2','material_path':'01_tree/tree.json','sources':[]}])
    assert len(calls)==3


def test_unit_mapping_keeps_actual_resources_and_does_not_claim_semantic_review():
    # 删除正文的材料对应会降低覆盖，格式检查继续如实保存语义审查未执行
    value={'plan':{'items':[{'id':'p1','resource_ids':['r1','r2']}]},
           'explanation':[{'resource_ids':['r1'],'plan_ids':['p1']}]}
    result=contract.mappings(value,['r1','r2'])
    assert result['percentage']==50 and result['errors'] and result['semantic_review']=='not_run'


def test_term_merge_reuses_definition_and_retains_raw_conflict():
    # 名称去重沿用已经输出的定义，不再调用模型重写全部术语
    a={'id':'cpu','chinese':'中央处理器','english':'Central Processing Unit','definition':'定义'}
    terms,conflicts=contract.merge_terms([a,dict(a,id='cpu2')])
    assert terms==[a] and len(conflicts)==1


def test_two_sections_use_c_units_one_translation_and_compact_bridge_batch(tmp_path,monkeypatch):
    # 两节各一次 C 写作、一次去重翻译和一次承接批次，没有信息点清点、AI 审查、术语二次请求或内容返修
    contexts=[]
    for i in [1,2]:
        contexts.append({'section_id':'s'+str(i),'section_number':'1.'+str(i),'title':'缓存怎样供数？',
            'opening_title':'','context_goals':[],'transitions_path':'04_transitions/transitions.json','transition_run':'run1',
            'core_questions':[{'question_id':'q'+str(i),'text':'缓存怎样供数？'}],
            'units':[{'question_id':'q'+str(i),'number':'1.'+str(i)+'.1','title':'缓存怎样供数？','source_nodes':['n1']}],
            'next_section_id':'','next_title':''})
    chapters={'tree':{'children':[]}}
    monkeypatch.setattr(pipeline.flow.runtime,'contexts',lambda root:(contexts,{},chapters,{}))
    def sources(root,sid,folder):
        qid='q'+sid[1:]
        return {'sources':[{'id':'n1','question_ids':[qid],'sentences':[{'id':'n1.s1','original':'Cache retains data'}]}]}
    monkeypatch.setattr(lean.book_sources,'prepare_sources',sources)
    monkeypatch.setattr(pipeline.flow,'make_preview',lambda *args,**kwargs:{'validation':{'passed':True,'errors':[]}})
    monkeypatch.setattr('prepare_source_locations.prepare_locations',lambda *args:None)
    calls=[]
    class Fake:
        def __init__(self,*args,**kwargs):pass
        def _call_once(self,name,prompt,schema,images=None):
            data=json.loads(prompt);calls.append((name,data))
            if name=='c_translation':
                return {'translations':[{'resource_id':'n1.s1','translation':'缓存保留数据'}]}
            if name=='c_bridges':
                assert 'explanation' not in prompt
                assert data['boundaries'][0]['prior_actual_results'] is None
                assert data['boundaries'][0]['is_first_main_body'] is True
                assert any('首个正文节' in rule for rule in data['rules'])
                assert data['boundaries'][1]['prior_actual_results']['answers']==['缓存保留常用数据']
                return {'bridges':[{'section_id':c['section_id'],'carryover':'程序需要取得数据','premise':'缓存保留常用数据，','question':'加载怎样利用它？'} for c in contexts]}
            assert '-c-' in name
            qid=data['question']['question_id']
            p=lambda key,text:{'id':key,'kind':'paragraph','text':text}
            quiz=[{'id':qid+'choice'+str(i),'kind':'single_choice','question_ids':[qid],'prompt':p(qid+'p'+str(i),'缓存怎样供数'),
                'options':['保留常用数据','丢弃全部数据'],'answer':0,'explanation':p(qid+'a'+str(i),'缓存保留常用数据')} for i in range(4)]
            quiz.append({'id':qid+'short','kind':'short_answer','question_ids':[qid],'prompt':p(qid+'short-p','请说明缓存的作用'),
                'reference_answer':'缓存保留常用数据','rubric':['说明保留作用'],'explanation':p(qid+'short-a','缓存保留常用数据')})
            return {'question_id':qid,'plan':{'items':[{'id':qid+'plan','statement':'解释保留作用','resource_ids':['n1.s1']}]},
                'premise':'程序反复取得数据时，缓存怎样供数？','explanation':[{'id':qid+'g','title_premise':'程序复用数据','title_question':'缓存怎样减少等待？',
                    'claim':'缓存保留数据','reasoning':'较近的缓存缩短路径','grounding':'再次加载时可以命中','supplement':None,
                    'resource_ids':['n1.s1'],'plan_ids':[qid+'plan'],'resources':[]}],
                'result':{'answer':'缓存保留常用数据','generalization':'使用者应结合复用情况考虑容量'},
                'appendix':{'pitfalls':[{'id':qid+'pitfall','premise':'程序会重复读取，','question':'缓存保留了哪些数据？','body':p(qid+'pitfall-body','缓存保留常用数据')}],
                    'quiz':quiz,'terms':[],'local_notations':[]}}
    monkeypatch.setattr(lean,'Backend',Fake)
    sections,passed,errors=lean.write_sections(tmp_path,Fake())
    assert passed and not errors and len(sections)==2
    assert len(calls)==4
    before=len(calls)
    lean.write_sections(tmp_path,Fake())
    assert len(calls)==before
    assert read(tmp_path/'05_writing/work/sections/s1/checks.json')['semantic_review']=='not_run'


def test_first_main_body_uses_book_context_and_later_body_uses_previous_body_result():
    contexts = [
        {'section_id': 'ch0-s3', 'chapter_id': 'ch0', 'section_number': '0.3',
         'title': '导读', 'core_questions': [{'question_id': 'q0', 'text': '导读问题？'}]},
        {'section_id': 'ch1-s1', 'chapter_id': 'ch1', 'section_number': '1.1',
         'title': '首个正文问题', 'core_questions': [{'question_id': 'q1', 'text': '正文先问什么？'}]},
        {'section_id': 'ch1-s2', 'chapter_id': 'ch1', 'section_number': '1.2',
         'title': '后续正文问题', 'core_questions': [{'question_id': 'q2', 'text': '下一步问什么？'}]},
    ]
    values = [
        [{'result': {'answer': '导读提出的旧承接'}}],
        [{'result': {'answer': '首个正文得到的结果'}}],
        [{'result': {'answer': '后续正文得到的结果'}}],
    ]
    chapters = {'tree': {'title': '全书标题', 'question_ids': ['root-q']}}
    questions = {'root-q': {'premise': '研究者要解决的问题是', 'question': '怎样确认核心条件？'}}

    boundaries = lean.build_bridge_boundaries(list(zip(contexts, values)), chapters, questions)

    assert boundaries[0]['is_preface'] is True
    first_body = boundaries[1]
    assert first_body['prior_actual_results'] is None
    assert first_body['project_background'] == {
        'title': '全书标题',
        'root_questions': [{'question_id': 'root-q', 'text': '研究者要解决的问题是怎样确认核心条件？'}],
    }
    assert first_body['current']['questions'] == contexts[1]['core_questions']
    assert boundaries[2]['prior_actual_results']['answers'] == ['首个正文得到的结果']
    assert 'project_background' not in boundaries[2]


def test_targeted_opening_tool_calls_only_first_main_body_and_returns_proposal(monkeypatch):
    boundaries = [
        {'section_id': 'ch0-s3', 'is_preface': True},
        {'section_id': 'ch1-s1', 'is_first_main_body': True, 'project_background': {'root_questions': []}},
        {'section_id': 'ch1-s2'},
    ]
    calls = []

    def generate(backend, selected):
        calls.append(selected)
        return {'bridges': [{'section_id': 'ch1-s1', 'carryover': '承接候选',
                             'premise': '引出前提', 'question': '继续问什么？'}],
                'records': [{'status': 'completed'}]}

    monkeypatch.setattr(bridge_batches, 'generate', generate)
    result = lean.generate_first_opening_candidate(object(), boundaries)

    assert len(calls) == 1 and [row['section_id'] for row in calls[0]] == ['ch1-s1']
    assert result == {
        'status': 'proposed_only',
        'candidate': {'section_id': 'ch1-s1', 'carryover': '承接候选',
                      'premise': '引出前提', 'question': '继续问什么？'},
        'records': [{'status': 'completed'}],
    }

