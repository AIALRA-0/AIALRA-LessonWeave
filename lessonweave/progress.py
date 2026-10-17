"""按实际阶段和已完成任务显示进度，耗时未知的模型调用保持运行状态"""
from pathlib import Path
import time
import os
from .storage import read,save,WRITE_LOCK

STEPS=[('00_source','保存材料','00_source/source.json'),('01_tree','解析材料','01_tree/tree.json'),('02_questions','组织问题','02_questions/questions.json'),('03_chapters','安排章节','03_chapters/chapters.json'),('04_transitions','规划承接','04_transitions/transitions.json'),('05_writing','写作与检查','05_writing/book.json')]


def begin(root,label,names):
    with WRITE_LOCK:
        value=read(root/'runtime/progress.json',{})
        value.update(label=label,tasks={name:'waiting' for name in names},updated=time.time())
        save(root/'runtime/progress.json',value)


def tick(root,name,status):
    with WRITE_LOCK:
        value=read(root/'runtime/progress.json',{'label':'正在处理当前阶段','tasks':{}})
        if name in value.get('tasks',{}):
            value['tasks'][name]=status
        value.update(last_task=name,last_status=status,updated=time.time())
        save(root/'runtime/progress.json',value)


def view(root,job):
    root=Path(root)
    state=read(root/'runtime/state.json',{})
    diagnosis=read(root/'runtime/diagnosis.json',{})
    if diagnosis.get('state_updated_at')!=state.get('updated_at') or job['status'] in {'running','queued','cancelling','completed'}:
        diagnosis={}
    if not diagnosis and state.get('failure_kind')=='output_limit' and job['status'] not in {'running','queued','cancelling','completed'}:
        diagnosis={'failure_kind':'output_limit','message':'当前任务超过模型输出上限，需要拆小任务后继续，已完成内容保留'}
    rows=[]
    steps=STEPS+[('06_library','保存到笔记树','runtime/trilium/current.json')] if os.environ.get('LESSONWEAVE_TRILIUM_URL') else STEPS
    for key,label,path in steps:
        value=read(root/path,{})
        done=bool(value) and (value.get('status')=='acquired' if key=='00_source' else bool(value.get('render_note_id')) if key=='06_library' else value.get('validation',{}).get('passed',False))
        rows.append({'id':key,'label':label,'status':'done' if done else 'waiting'})
    current=next((row for row in rows if row['status']!='done'),rows[-1])
    if state.get('stage')=='05_writing/materials':
        current['label']='清点各节原材料'
    if job['status'] in {'running','cancelling'}:
        current['status']='running'
    elif job['status'] not in {'completed','queued'}:
        current['status']=job['status']
    work=read(root/'runtime/progress.json',{})
    tasks=work.get('tasks',{})
    completed=sum(status in {'completed','reused'} for status in tasks.values())
    end=time.time() if job['status'] in {'queued','running','cancelling'} else job['updated']
    return {'stages':rows,'completed_stages':sum(row['status']=='done' for row in rows),'stage_total':len(rows),'phase':'已完成并保存' if job['status']=='completed' else current['label'] if state.get('stage')=='05_writing/materials' else work.get('label',current['label']),'done':completed,'total':len(tasks),'active':sum(status=='running' for status in tasks.values()),'round':state.get('round',0),'maximum':state.get('maximum',3),'elapsed_seconds':round(end-job['created']),'updated':work.get('updated',state.get('updated_at',job['updated'])),'issues':state.get('issues',[]) if job['status'] not in {'queued','running'} else [],'output_ready':(root/'05_writing/preview-book.json').is_file() or (root/'05_writing/book.json').is_file(),'diagnosis':{key:diagnosis[key] for key in ['failure_kind','message','affected_tasks'] if key in diagnosis}}
