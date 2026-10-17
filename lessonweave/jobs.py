"""把每个任务放入独立进程组，停止时一并结束它启动的模型和解析进程"""
from pathlib import Path
import json
import os
import signal
import subprocess
import sys
import time
import atexit
import threading
from .storage import Store,read,save

ACTIVE=set()
ACTIVE_LOCK=threading.Lock()


def shutdown():
    with ACTIVE_LOCK:
        processes=list(ACTIVE)
    for process in processes:
        try:
            terminate(process)
        except (OSError,subprocess.SubprocessError):
            pass


atexit.register(shutdown)


def terminate(process):
    if process.poll() is not None:
        return
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        os.killpg(process.pid,signal.SIGTERM)
        try:
            process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL)
    process.wait(timeout=10)


def execute(store,job):
    root=Path(store.project(job['project_id'])['path'])
    work=root/'runtime/jobs'/job['id']
    work.mkdir(parents=True,exist_ok=True)
    args=[sys.executable,'-X','utf8','-B','-m','lessonweave.jobs',str(store.root),job['id']]
    options={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
    with (work/'worker.log').open('ab') as log:
        process=subprocess.Popen(args,cwd=Path(__file__).resolve().parents[1],stdout=log,stderr=log,**options)
        with ACTIVE_LOCK:
            ACTIVE.add(process)
        save(work/'process.json',{'pid':process.pid,'job_id':job['id'],'started':time.time()})
        while process.poll() is None:
            if store.job(job['id'])['status']=='cancelling':
                terminate(process)
                mark_cancelled(root)
                result=read(root/'runtime/state.json',{})
                result.update(status='cancelled')
                save(root/'runtime/state.json',result)
                with ACTIVE_LOCK:
                    ACTIVE.discard(process)
                return result
            time.sleep(.25)
    with ACTIVE_LOCK:
        ACTIVE.discard(process)
    if store.job(job['id'])['status']=='cancelling':
        mark_cancelled(root)
        result=read(root/'runtime/state.json',{})
        result['status']='cancelled';save(root/'runtime/state.json',result)
        return result
    result=read(work/'result.json')
    return result or {'status':'interrupted','issues':['执行进程已退出，已完成的阶段与调用记录继续保留']}


def mark_cancelled(root,reason='user_cancelled'):
    for path in (root/'runtime/calls').glob('*/*/usage.json'):
        receipt=read(path)
        if receipt.get('status') in {'started','uncertain'}:
            receipt.update(status='cancelled',cancelled_at=time.time(),stop_reason=reason,usage_measurement='partial_or_unavailable')
            events=path.parent/'events.jsonl'
            if events.exists():
                usage=[]
                for line in events.read_text('utf-8',errors='replace').splitlines():
                    try:
                        event=json.loads(line)
                        if event.get('type')=='turn.completed':
                            usage.append(event.get('usage',{}))
                    except ValueError:
                        continue
                receipt['usage']=usage
            save(path,receipt)


def main():
    store=Store(sys.argv[1]);job=store.job(sys.argv[2]);project=store.project(job['project_id'])
    os.environ['LESSONWEAVE_JOB_ID']=job['id']
    root=Path(project['path'])
    payload=json.loads(job['payload'])
    try:
        if payload.get('_type')=='qa':
            from .qa import answer
            result=answer(root,payload)
        else:
            from .pipeline import run
            published=read(root/'05_writing/book.json',{})
            if published.get('validation',{}).get('passed'):
                result=dict(read(root/'runtime/state.json',{}),status='completed',issues=[])
            else:
                result=run(root)
            from .trilium import sync_project,configured
            if configured() and (root/'05_writing/preview-book.json').is_file():
                try:
                    from .metrics import span
                    with span(root,'library','phase'):
                        sync_project(store,project,root)
                    result.update(library_sync='completed')
                except Exception as error:
                    result.update(status='interrupted',library_sync='failed',library_issue=str(error),issues=result.get('issues',[])+['书稿已经保存，笔记树保存遇到问题：'+str(error)])
            save(root/'runtime/state.json',result)
    except Exception as error:
        result={'status':'failed','issues':[str(error)]}
    save(root/'runtime/jobs'/job['id']/'result.json',result)


if __name__=='__main__':
    main()
