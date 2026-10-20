"""保存每个步骤的实际时间，汇总时区分并行经过时间与调用累计时间"""
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
import os
import time
import uuid
from .storage import read,save,WRITE_LOCK

LABELS={'acquire':'获取材料','parse':'解析材料','input_check':'检查输入','questions':'生成问题',
        'chapters':'规划章节','transitions':'规划承接','inventory':'清点材料','translation':'翻译材料',
        'writing':'生成讲解','extras':'生成练习与术语','overview':'汇总章节与全书',
        'glossary':'整理术语表','review':'独立审查','locations':'准备原文定位','package':'导出阅读包','library':'导入笔记库','qa':'阅读追问','other':'其他处理'}
LABELS['repair']='批量修复'


def stage(name):
    if name.startswith('02_questions-'):return 'questions'
    if name.startswith('03_chapters-'):return 'chapters'
    if name in {'02_questions','03_chapters','04_transitions'}:
        return {'02_questions':'questions','03_chapters':'chapters','04_transitions':'transitions'}[name]
    if name.startswith('c_repair-'):return 'repair'
    if name.startswith('c_translation'):return 'translation'
    if name.startswith('c_bridges'):return 'transitions'
    if name.startswith('c_terms'):return 'glossary'
    if '-c-' in name:return 'writing'
    if 'review' in name:return 'review'
    if 'inventory' in name:return 'inventory'
    if '06_glossary' in name:return 'glossary'
    if 'english' in name:return 'translation'
    if '05_unit' in name:return 'writing'
    if '05_extras' in name:return 'extras'
    if '05_overview' in name:return 'overview'
    if name.startswith('reader-qa-'):return 'qa'
    return 'other'


def start(root,stage_id,operation,**details):
    record={'id':uuid.uuid4().hex,'job_id':os.environ.get('LESSONWEAVE_JOB_ID'),
            'stage':stage_id,'operation':operation,'started_at':time.time(),'status':'running',**details}
    path=Path(root)/'runtime/timing.json'
    with WRITE_LOCK:
        data=read(path,{'profile':'lessonweave-timing-v1','records':[]})
        data['records'].append(record);save(path,data)
    return record['id']


def finish(root,key,status='completed',elapsed=None,**details):
    path=Path(root)/'runtime/timing.json'
    with WRITE_LOCK:
        data=read(path,{'profile':'lessonweave-timing-v1','records':[]})
        row=next((row for row in data['records'] if row['id']==key),None)
        if row and row['status']=='running':
            now=time.time()
            row.update(ended_at=now,elapsed_seconds=round(max(0,elapsed if elapsed is not None else now-row['started_at']),3),status=status,**details)
            save(path,data)


def annotate(root,key,**details):
    path=Path(root)/'runtime/timing.json'
    with WRITE_LOCK:
        data=read(path,{'records':[]})
        next(row for row in data['records'] if row['id']==key).update(details)
        save(path,data)


@contextmanager
def span(root,stage_id,operation,**details):
    key=start(root,stage_id,operation,**details);began=time.monotonic()
    try:
        yield key
    except BaseException as error:
        finish(root,key,'failed',time.monotonic()-began,error_type=type(error).__name__,failure_kind=getattr(error,'kind',None))
        raise
    else:finish(root,key,elapsed=time.monotonic()-began)


def timed(stage_id,operation):
    def decorate(function):
        @wraps(function)
        def wrapped(root,*args,**kwargs):
            with span(root,stage_id,operation) as key:
                result=function(root,*args,**kwargs)
                if isinstance(result,dict) and 'validation' in result:
                    annotate(root,key,validation_passed=bool(result['validation'].get('passed')))
                return result
        return wrapped
    return decorate


def close_job(root,job_id,status):
    # 工作进程被停止时，由监督进程记录观察到的结束时间
    for row in read(Path(root)/'runtime/timing.json',{'records':[]})['records']:
        if row.get('job_id')==job_id and row['status']=='running':
            finish(root,row['id'],status,measurement='supervisor_observed')


def union_seconds(rows,end=None):
    intervals=sorted((row['started_at'],row.get('ended_at',end or time.time())) for row in rows if row.get('started_at') is not None)
    total=0;left=right=None
    for a,b in intervals:
        b=max(a,b)
        if right is None:left,right=a,b
        elif a<=right:right=max(right,b)
        else:total+=right-left;left,right=a,b
    return round(total+(right-left if right is not None else 0),3)


def meter(value):
    receipts=value.get('usage',[])
    if not receipts:return {'input_tokens':None,'output_tokens':None,'cached_input_tokens':None}
    def summed(*names):
        values=[]
        for receipt in receipts:
            found=next((receipt[name] for name in names if name in receipt),None)
            values.append(found)
        return sum(values) if all(v is not None for v in values) else None
    cached=[r.get('cached_input_tokens',r.get('prompt_cache_hit_tokens',r.get('prompt_tokens_details',{}).get('cached_tokens'))) for r in receipts]
    return {'input_tokens':summed('input_tokens','prompt_tokens'),'output_tokens':summed('output_tokens','completion_tokens'),
            'cached_input_tokens':sum(cached) if all(v is not None for v in cached) else None}


def report(root,job):
    root=Path(root);active=job['status'] in {'running','queued','cancelling'}
    end=time.time() if active else job['updated']
    saved=read(root/'runtime/timing.json',{'records':[]})['records']
    records=[dict(row) for row in saved if row.get('job_id')==job['id']]
    for row in records:
        if row['status']=='running':
            row['elapsed_seconds']=round(max(0,end-row['started_at']),3)
            if not active:row.update(status='interrupted',measurement='end_not_recorded')
    calls=[];diagnosis=read(root/'runtime/diagnosis.json',{})
    for parent in ['calls','cancelled-calls']:
        for file in (root/'runtime'/parent).glob('*/*/usage.json'):
            value=read(file);process=read(file.parent/'process.json',{})
            began=value.get('started_at',process.get('started'))
            if value.get('job_id') and value['job_id']!=job['id']:continue
            if not value.get('job_id') and (began is None or not job['created']<=began<=end):continue
            name=value.get('task',file.parent.parent.name)
            model=next((row for row in records if row['operation']=='model' and row.get('request_id')==file.parent.name),None)
            row={'task':name,'request_id':file.parent.name,'stage':stage(name),'round':value.get('round',0),
                 'model':value.get('model'),'reasoning_effort':value.get('reasoning_effort'),'status':value.get('status'),
                 'failure_kind':value.get('failure_kind'),'kind':value.get('attempt_kind','repair' if value.get('round',0)>0 else 'initial'),**meter(value)}
            row['classification_source']='recorded' if value.get('attempt_kind') else 'historical_round'
            if not row['failure_kind'] and name in diagnosis.get('affected_tasks',[]):row['failure_kind']=diagnosis.get('failure_kind')
            if model:
                row.update({key:model[key] for key in ['started_at','ended_at','elapsed_seconds','status','measurement'] if key in model})
                queued=next((q for q in records if q['operation']=='slot_queue' and q.get('request_id')==file.parent.name),None)
                row['queue_seconds']=queued.get('elapsed_seconds') if queued else None
                row.setdefault('measurement','recorded')
            else:
                stopped=None if value.get('status')=='started' and active else min(file.stat().st_mtime,end)
                row.update(started_at=began,elapsed_seconds=round(max(0,(stopped or end)-began),3) if began else None,
                           queue_seconds=None,measurement='historical_file_times')
                if stopped is not None:row['ended_at']=stopped
            calls.append(row)
    # 全局修复轮次可能由前一步触发，后续任务的第一次实际调用仍属于初稿
    seen_tasks=set()
    for row in sorted(calls,key=lambda item:item.get('started_at') or float('inf')):
        if row['classification_source']=='historical_round' and row['kind']=='repair' and row['task'] not in seen_tasks and row.get('started_at') is not None:
            row['recorded_kind']=row['kind'];row['kind']='initial';row['classification_source']='first_task_call'
        seen_tasks.add(row['task'])
    # 完整记录只统计本次任务，历史调用按时间范围归属并明确标为推算
    groups=[]
    for sid,label in LABELS.items():
        work=[row for row in records if row['stage']==sid and row['operation'] not in {'job_queue','job_run','repair_round','reuse','slot_queue'}]
        group_calls=[row for row in calls if row['stage']==sid]
        historical=[row for row in group_calls if row['measurement']=='historical_file_times']
        groups.append({'stage':sid,'label':label,'wall_seconds':union_seconds(work+historical,end) if work or historical else None,
                       'started_at':min((row['started_at'] for row in work+historical),default=None),
                       'ended_at':max((row.get('ended_at',end) for row in work+historical),default=None),
                       'model_seconds':round(sum(row['elapsed_seconds'] or 0 for row in group_calls),3),
                       'calls':len(group_calls),'repair_calls':sum(row['kind']=='repair' for row in group_calls),
                       'retry_calls':sum(row['kind']=='retry' for row in group_calls),
                       'failed_calls':sum(row['status'] in {'failed','uncertain','invalid','cancelled'} for row in group_calls),
                       'failed_checks':sum(row['status']=='failed' and row['operation'] in {'check','format'} for row in work) if records else None,
                       'reuse_count':sum(row['stage']==sid and row['operation']=='reuse' for row in records) if records else None,
                       'historical_estimate':bool(historical)})
    initial=[row for row in calls if row['stage'] not in {'review','qa'} and row['kind']=='initial']
    repair=[row for row in calls if row['stage'] not in {'review','qa'} and row['kind']=='repair']
    reviews=[row for row in calls if row['stage']=='review']
    retries=[row for row in calls if row['kind']=='retry']
    queue=[row for row in records if row['operation']=='job_queue']
    rounds=[row for row in records if row['operation']=='repair_round']
    scripts=[row for row in records if row['operation'] in {'check','format'}]
    summary={'elapsed_seconds':round(max(0,end-job['created']),3),'job_queue_seconds':union_seconds(queue,end) if queue else None,
             'execution_seconds':union_seconds([row for row in records if row['operation']=='job_run'],end) if records else None,
             'initial_generation_seconds':union_seconds(initial,end),'repair_generation_seconds':union_seconds(repair,end),
             'review_seconds':union_seconds(reviews,end),'retry_seconds':union_seconds(retries,end),
             'model_cumulative_seconds':round(sum(row['elapsed_seconds'] or 0 for row in calls),3),
             'calls':len(calls),'repair_calls':len(repair),'review_calls':len(reviews),
             'review_rechecks':sum(row['kind']=='repair' for row in reviews),'retry_calls':len(retries),
             'reuse_events':sum(row['operation']=='reuse' for row in records),
             'script_seconds':union_seconds(scripts,end) if scripts else None,
             'format_operations':sum(row['operation']=='format' for row in records),
             'converted_items':sum(row.get('converted_items',0) for row in records),
             'slot_queue_cumulative_seconds':round(sum(row.get('elapsed_seconds',0) for row in records if row['operation']=='slot_queue'),3) if records else None,
             'repair_rounds_entered':len(rounds) if rounds else None,
             'repair_batch_seconds':union_seconds(rounds,end) if rounds else None,
             'review_failed_sections':sum(row['stage']=='review' and row.get('validation_passed') is False for row in records),
             'repair_rounds_with_model_calls':len({row['round'] for row in calls if row['round']>0}),
             'unknown_usage_calls':sum(row['input_tokens'] is None or row['output_tokens'] is None for row in calls),
             'historical_estimate_calls':sum(row['measurement']=='historical_file_times' for row in calls)}
    if not records:
        for field in ['reuse_events','format_operations','converted_items','review_failed_sections']:summary[field]=None
    if any(row['classification_source']=='historical_round' for row in calls):
        summary['retry_calls']=None;summary['retry_seconds']=None
    for field in ['input_tokens','output_tokens','cached_input_tokens']:
        known=[row[field] for row in calls if row[field] is not None]
        summary[field]=sum(known) if known else None
        summary[field+'_missing_calls']=sum(row[field] is None for row in calls)
    result={'profile':'lessonweave-metrics-v1','job_id':job['id'],'status':job['status'],'generated_at':time.time(),
            'summary':summary,'stages':groups,'calls':sorted(calls,key=lambda row:row.get('started_at') or 0),'steps':records,
            'notes':['实际用时合并并行区间，累计调用时间逐次相加，各阶段可能重叠，合计以任务实际时间为准',
                     '首次生成、内容返修、失败重试、独立审查和结果复用分别统计，审查复核单列次数',
                     '历史调用起点取进程记录，终点按文件时间推算，旧任务未记录的解析与格式时间保持缺失',
                     '旧调用按原有轮次归类，失败重试与复用次数没有单独记录时显示未记录',
                     'token 只合计实际回执，缺失用量与缓存数据分别列出']}
    return result
