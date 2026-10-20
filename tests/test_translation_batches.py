"""检查翻译分批完整保留原句与编号，测试不访问真实模型"""
import json
from lessonweave import legacy
import translation_batches as batching


def test_batches_keep_every_resource_once_and_copy_original_fields():
    # 三条材料分别请求一次，模型只填写译文，脚本把原句原样填回
    rows=[{'id':'r'+str(i),'original':'Original sentence '+str(i)} for i in range(3)];calls=[]
    class Backend:
        def _call_once(self,name,prompt,schema):
            selected=json.loads(prompt)['resources'];calls.extend(r['id'] for r in selected)
            return {'translations':[{'resource_id':r['id'],'translation':'中文译文'} for r in selected]}
    result=batching.generate(Backend(),rows,budget=1)
    assert sorted(calls)==['r0','r1','r2'] and result['calls']==3 and not result['errors']
    assert [r['english'] for r in result['translations']]==[r['original'] for r in rows]


def test_failed_translation_batch_keeps_other_results_and_does_not_retry():
    # 一批请求遇到执行问题时，其他译文保留，失败批次只记录一次并交给最后的集中检查
    rows=[{'id':key,'original':'Source '+key} for key in ['ok','issue']];calls=[]
    class Backend:
        def _call_once(self,name,prompt,schema):
            row=json.loads(prompt)['resources'][0];calls.append(row['id'])
            if row['id']=='issue':raise RuntimeError('记录执行问题')
            return {'translations':[{'resource_id':row['id'],'translation':'完整译文'}]}
    result=batching.generate(Backend(),rows,budget=1)
    assert sorted(calls)==['issue','ok'] and len(result['errors'])==1
    assert result['translations']==[{'resource_id':'ok','english':'Source ok','chinese':'完整译文'}]


def test_chinese_and_protected_only_inputs_use_no_model():
    class Backend:
        def _call_once(self,*args):raise AssertionError('这些原句不需要翻译请求')
    rows=[{'id':'cn','original':'中文包含 FIFO 与 16 MB'},{'id':'code','original':'`set enable=false` $C=R/S$ https://example.org'}]
    result=batching.generate(Backend(),rows)
    assert result['calls']==0 and result['translations'][0]['english']==''
    assert result['translations'][1]['chinese']==rows[1]['original']


def test_exact_paragraph_reuse_preserves_all_ids_and_source_spans():
    source='Call `cache.read(1)` and keep $x_i$ unchanged at https://example.org/docs';calls=[]
    class Backend:
        def _call_once(self,name,prompt,schema):
            rows=json.loads(prompt)['resources'];calls.extend(rows)
            return {'translations':[{'resource_id':r['id'],'translation':r['original'].replace('Call','调用').replace('and keep','并保留').replace('unchanged at','原样位于')}for r in rows]}
    result=batching.generate(Backend(),[{'id':'a','original':source},{'id':'b','original':source}])
    assert len(calls)==1 and result['reused_rows']==1 and len(result['translations'])==2
    assert all('`cache.read(1)`'in r['chinese'] and '$x_i$'in r['chinese'] and r['english']==source for r in result['translations'])
