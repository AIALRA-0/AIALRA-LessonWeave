import time
import pytest
from lessonweave.pricing import estimate,usage_totals
from lessonweave.metrics import report
from lessonweave.progress import view
from lessonweave.storage import save


def test_cached_input_is_not_billed_twice_and_long_context_uses_its_rates():
    call={'model':'gpt-6.1-sol','input_tokens':100000,'cached_input_tokens':80000,'output_tokens':1000}
    assert estimate(call)['USD']['minimum']==pytest.approx(.058)
    call.update(input_tokens=1000000,cached_input_tokens=750000,output_tokens=10000)
    assert estimate(call)['USD']['minimum']==pytest.approx(1.3)


def test_flash_keeps_currency_and_peak_price_range():
    call={'model':'deepseek-v4.1-flash','input_tokens':1000,'cached_input_tokens':400,'output_tokens':500}
    result=usage_totals([call])
    assert result['estimated_costs']['CNY']['minimum']==pytest.approx(.002608)
    assert result['estimated_costs']['CNY']['maximum']==pytest.approx(.005216)
    call['cached_input_tokens']=None
    assert usage_totals([call])['unpriced_calls']==1
    assert usage_totals([])['input_tokens']==0


def test_stage_usage_counts_actual_receipts_but_not_reuse_events(tmp_path):
    now=time.time()
    save(tmp_path/'runtime/state.json',{'workflow':'lean-c-1.0','stage':'05_writing/package'})
    save(tmp_path/'runtime/calls/section-c-q.1.1/request/usage.json',{
        'job_id':'job','task':'section-c-q.1.1','status':'completed','started_at':now-2,
        'model':'gpt-6.1-sol','usage':[{'input_tokens':100,'output_tokens':10,'cached_input_tokens':80}]})
    save(tmp_path/'runtime/timing.json',{'records':[
        {'job_id':'job','stage':'writing','operation':'reuse','status':'completed','started_at':now-1,'ended_at':now},
    ]})
    job={'id':'job','status':'completed','created':now-5,'updated':now}
    metrics=report(tmp_path,job)
    assert metrics['summary']['estimated_costs']['USD']['minimum']==pytest.approx(.000148)
    progress=view(tmp_path,job)
    writing=next(row for row in progress['stages']if row['id']=='04')
    assert writing['usage']['input_tokens']==100 and writing['reuse_count']==1
    assert writing['usage']['estimated_costs']==metrics['summary']['estimated_costs']
    assert next(row for row in progress['stages']if row['id']=='11')['usage']['calls']==0
