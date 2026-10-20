"""按实际阶段和已完成任务显示进度，耗时未知的模型调用保持运行状态"""
from pathlib import Path
import time
import os
from .storage import read,save,WRITE_LOCK

STAGE_GROUPS={'00':{'input_check','acquire'},'01':{'parse'},'02':{'questions'},'03':{'chapters'},'04':{'writing'},'05':{'translation'},'06':{'transitions'},'07':{'review'},'08':{'repair'},'09':{'assembly'},'10':{'locations'},'11':{'package'},'12':{'library'}}


def stage_times(root,job,rows,state):
    """每阶段合并重叠记录，恢复前后的空档不计入实际执行时间"""
    from .metrics import union_seconds
    end=time.time() if job['status'] in {'queued','running','cancelling'} else job['updated']
    records=[r for r in read(root/'runtime/timing.json',{'records':[]})['records'] if r.get('job_id')==job.get('id')]
    groups=STAGE_GROUPS
    for row in rows:
        spans=[r for r in records if r['stage'] in groups[row['id']] and r['operation'] not in {'job_queue','job_run','slot_queue'}]
        seconds=union_seconds(spans,end) if spans else 0 if row['status']=='skipped' else None
        if row['id']=='09':
            saved=[read(root/('runtime/'+name+'.json'),{}) for name in ['section-assembly','reader-assembly']]
            durations=[v['seconds'] for v in saved if isinstance(v.get('seconds'),(int,float))]
            if durations:seconds=round(sum(durations),3)
            elif row['status']=='running' and state.get('updated_at'):
                seconds=round(max(0,end-state['updated_at']),3)
        row['execution_seconds']=seconds
    elapsed=[r for r in records if r['operation']=='job_run']
    return {'stage_execution_seconds':round(sum(r['execution_seconds'] or 0 for r in rows),3),
            'execution_seconds':union_seconds(elapsed,end) if elapsed else None}

def begin(root,label,names):
    with WRITE_LOCK:
        value=read(root/'runtime/progress.json',{})
        history=value.setdefault('all_tasks',{})
        history.update(value.get('tasks',{}))
        tasks={name:history.get(name,'waiting') for name in names}
        history.update(tasks)
        value.update(label=label,tasks=tasks,updated=time.time())
        save(root/'runtime/progress.json',value)


def tick(root,name,status):
    with WRITE_LOCK:
        value=read(root/'runtime/progress.json',{'label':'正在处理当前阶段','tasks':{}})
        value.setdefault('all_tasks',{}).update(value.get('tasks',{}))
        value['all_tasks'][name]=status
        value.setdefault('tasks',{})[name]=status
        times=value.setdefault('task_times',{}).setdefault(name,{})
        if status=='running':times.setdefault('started',time.time())
        if status in {'completed','reused','failed'}:times['ended']=time.time()
        value.update(last_task=name,last_status=status,updated=time.time())
        save(root/'runtime/progress.json',value)


def view(root,job):
    root=Path(root)
    state=read(root/'runtime/state.json',{})
    if state.get('workflow') == 'lean-c-1.0':
        return lean_view(root,job,state)
    # 旧项目只展示已有产物，继续执行时仍使用当前的逐问生成流程
    return {'stages':[],'completed_stages':0,'stage_total':0,'phase':'历史任务，原有产物与笔记继续保留','done':0,'total':0,'active':0,'round':state.get('round',0),'maximum':0,'elapsed_seconds':round(max(0,job['updated']-job['created'])),'updated':job['updated'],'issues':state.get('issues',[]),'output_ready':(root/'05_writing/book.json').is_file() or (root/'05_writing/preview-book.json').is_file(),'workflow':'legacy_read_only'}


def lean_view(root,job,state):
    return detailed_view(root,job,state)


def detailed_view(root,job,state):
    """完成数来自全部预期任务与落盘结果，正文和翻译可以同时处于运行中"""
    root=Path(root);folder=root/'05_writing/work/sections'
    work=read(root/'runtime/progress.json',{});tasks={**work.get('all_tasks',{}),**work.get('tasks',{})}
    times=work.get('task_times',{});active=job['status'] in {'running','cancelling'}
    stage=state.get('stage','00_source');now=time.time()
    end=now if job['status'] in {'queued','running','cancelling'} else job['updated']
    contexts=[read(p,{}) for p in folder.glob('*/context.json')]
    expected=[(p.parent/('unit-'+u['question_id']+'.json'),u['question_id']) for p in folder.glob('*/context.json') for u in read(p,{}).get('units',[])]
    finished=sum(p.is_file() for p,_ in expected)
    source=read(root/'00_source/source.json',{})
    questions=read(root/'02_questions/questions.json',{})
    chapter=read(root/'03_chapters/chapters.json',{})
    qcoverage=questions.get('coverage',{})
    check=read(root/'05_writing/checks/independent-before.json',{})
    repair=read(root/'05_writing/checks/batch-repair.json',{})
    rows=[]
    def add(key,label,done=False,total=None,count=0,detail='',running=False,skipped=False):
        status='skipped' if skipped else 'done' if done else 'running' if active and running else 'waiting'
        rows.append(dict(id=key,label=label,status=status,done=count,total=total,detail=detail))
    add('00','保存原件与资源',source.get('status')=='acquired',detail='原件、资源与归档继续保存在项目中',running=stage=='00_source')
    add('01','解析材料树',(root/'01_tree/tree.json').is_file(),detail='完整保留材料，非主体内容只标记用途',running=stage=='01_tree')
    add('02','规划第 0 章与正文问题',bool(questions.get('validation',{}).get('passed')),detail='有缺项才补齐，来源分配结果可在材料树中查看',running=stage.startswith('02'))
    add('03','编排章节',bool(chapter.get('validation',{}).get('passed')),detail='使用带编号的问题树规划目录和问题归属',running=stage.startswith(('02','03')) and bool(questions.get('validation',{}).get('passed')))
    writing_done=bool(expected) and finished==len(expected)
    add('04','生成正文、媒体、练习与术语',writing_done,len(expected) or None,finished,'每问同次规划并写作，已有术语完整复用',stage.startswith('05_writing') and not writing_done and not stage.endswith(('locations','package')))
    translation_done=(root/'runtime/translation-stage.json').is_file()
    tr=read(root/'runtime/translation-live.json',{})
    add('05','并行生成中文译文',translation_done,tr.get('total'),tr.get('completed',0),'与正文并行；源码、公式和链接保持原样；复用 '+str(tr.get('reused',0))+' 条',bool(expected) and not translation_done and stage.startswith('05_writing'))
    bridge=read(root/'05_writing/work/bridges.json',{})
    add('06','根据实际答案生成两段承接',bool(bridge),len(contexts) or None,len(bridge.get('bridges',[])), '承上段与启下段使用已经写出的答案',stage=='05_writing/bridges')
    add('07','脚本检查字段、格式与引用',bool(check),detail='不调用 AI 评价内容质量',running=stage=='05_writing/independent-check' and not check)
    add('08','按具体问题做一轮批量修复',bool(repair),detail=('无需修复，已跳过模型调用' if repair and not repair.get('model_calls') else '只发送需要修改的字段，修复后由脚本复核'),running=stage=='05_writing/independent-check' and bool(check) and not repair,skipped=bool(repair) and not repair.get('model_calls'))
    add('09','装配阅读页面',(root/'05_writing/book.json').is_file(),detail='总结、笔记框和目录由脚本装配',running=stage=='05_writing/assembly')
    add('10','准备原文定位',(root/'05_writing/source-location/index.json').is_file(),detail='保留精确、歧义和未定位的实际统计',running=stage=='05_writing/locations')
    add('11','导出完整阅读包',(root/'05_writing/reading-package.zip').is_file(),detail='读本、原件与来源映射一起打包',running=stage=='05_writing/package')
    if os.environ.get('LESSONWEAVE_TRILIUM_URL'):
        attachments={name:status for name,status in work.get('tasks',{}).items() if name.startswith('attachment:')}
        library_done=bool(read(root/'runtime/trilium/current.json',{}).get('render_note_id')) and not (active and stage=='library/sync')
        add('12','保存到笔记库',library_done,len(attachments) or None,sum(v in {'completed','reused'} for v in attachments.values()),detail='沿用已配置的笔记库和原有笔记位置',running=stage=='library/sync')
    if active and not any(r['status']=='running' for r in rows):
        pending=next((r for r in rows if r['status']=='waiting'),None)
        if pending:pending['status']='running'
    if job['status'] in {'failed','interrupted','cancelled'}:
        pending=next((r for r in rows if r['status']=='waiting'),None)
        if pending:pending['status']='failed' if job['status']=='failed' else 'interrupted'
    detail=[]
    from .metrics import stage as task_stage,report
    from .pricing import usage_totals,PRICING
    metered=report(root,job) if job.get('id') else {'calls':[],'steps':[]}
    for row in rows:
        row['usage']=usage_totals([call for call in metered['calls'] if call['stage'] in STAGE_GROUPS[row['id']]])
        row['reuse_count']=sum(step['operation']=='reuse' and step['stage'] in STAGE_GROUPS[row['id']] for step in metered['steps'])
        row['groups']=sorted(STAGE_GROUPS[row['id']])
    for name,status in tasks.items():
        t=times.get(name,{})
        detail.append({'name':name,'stage':'library' if name.startswith('attachment:') else task_stage(name),'status':status,'elapsed_seconds':round(max(0,t.get('ended',now)-t.get('started',now))),**t})
    current=[r['label'] for r in rows if r['status']=='running']
    result=job.get('result') or {}
    if isinstance(result,str):
        import json
        try:result=json.loads(result)
        except ValueError:result={}
    timing=stage_times(root,job,rows,state)
    return {'stages':rows,'completed_stages':sum(r['status'] in {'done','skipped'} for r in rows),'stage_total':len(rows),
        'phase':'已完成并保存' if job['status']=='completed' else '；'.join(current) or work.get('label','等待执行'),
        'done':finished if expected else sum(v in {'completed','reused'} for v in tasks.values()),'total':len(expected) or len(tasks),'active':sum(v=='running' for v in tasks.values()),'round':int(bool(repair.get('model_calls'))),'maximum':1,
        'elapsed_seconds':round(max(0,end-job['created'])),'updated':work.get('updated',state.get('updated_at',job['updated'])),
        'observed_at':now,'tasks':detail,'coverage':qcoverage,'pricing':PRICING,'issues':state.get('issues',[]) or (result.get('issues',[]) if not active else []),
        'output_ready':(root/'05_writing/book.json').is_file() and (root/'05_writing/source-location/index.json').is_file(),
        'diagnosis':{},'workflow':'lean-c-1.0',**timing}
