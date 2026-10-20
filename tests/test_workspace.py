"""检查目录恢复、任务终止和实际进度，所有模型调用都使用本地替身"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import pytest
from lessonweave.storage import Store,save,read
from lessonweave.jobs import terminate
from lessonweave.progress import begin,tick,view
from lessonweave.trilium import section_html,svg_preview


def test_native_svg_keeps_original_and_uses_static_preview():
    # 原始 SVG 字节保持原样，宿主使用有尺寸上限的 PNG，材料中的脚本不参与预览
    content=b'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40"><script>throw Error("fixture")</script><rect width="80" height="40" fill="red"/></svg>'
    from PIL import Image
    from io import BytesIO
    image=Image.open(BytesIO(svg_preview(content)))
    assert image.format=='PNG' and image.size==(160,80)
    assert image.getpixel((20,20))[:3]==(255,0,0)
    assert b'<script>' in content


def test_folder_move_trash_restore_preserves_notes_and_previous_trash(tmp_path):
    # 文件夹不移入自己的后代，恢复一批删除时继续保留之前单独放入回收站的项目
    store=Store(tmp_path)
    first=store.create_folder('资料')
    child=store.create_folder('论文',first['id'])
    store.register('book','读本',tmp_path/'book',folder_id=child['id'])
    store.register('old','旧读本',tmp_path/'old',folder_id=child['id'])
    store.note('book','unit-1','自己的理解')
    with pytest.raises(ValueError):
        store.library_change('folder',first['id'],'move',{'parent_id':child['id']})
    store.library_change('project','old','trash',{})
    store.library_change('folder',first['id'],'trash',{})
    assert not store.projects()
    store.library_change('folder',first['id'],'restore',{})
    assert [p['id'] for p in store.projects()]==['book']
    assert store.note('book','unit-1')=='自己的理解'
    store.library_change('project','book','rename',{'name':'新的名称'})
    store.library_change('project','book','move',{'parent_id':'root'})
    assert store.project('book')['name']=='新的名称'
    assert store.project('book')['folder_id']=='root'


def test_cancel_queued_and_late_completion_cannot_overwrite_stop(tmp_path):
    # 排队任务直接停止，执行任务先进入正在停止，迟到的成功结果仍保留停止状态
    store=Store(tmp_path)
    store.register('book','读本',tmp_path/'book')
    queued=store.submit('book',{},'one')
    assert store.cancel(queued['id'])['status']=='cancelled'
    assert store.claim() is None
    store.resume(queued['id'])
    running=store.claim()
    assert store.cancel(running['id'])['status']=='cancelling'
    store.finish(running['id'],{'status':'completed'})
    assert store.job(running['id'])['status']=='cancelled'


def test_active_project_stays_outside_trash(tmp_path):
    # 项目正在排队时保留材料位置，停止后才允许移入回收站
    store=Store(tmp_path)
    store.register('book','读本',tmp_path/'book')
    job=store.submit('book',{},'one')
    with pytest.raises(ValueError):
        store.library_change('project','book','trash',{})
    store.cancel(job['id'])
    store.library_change('project','book','trash',{})
    with pytest.raises(ValueError):
        store.resume(job['id'])


def test_progress_counts_actual_completed_tasks(tmp_path,monkeypatch):
    # 当前步骤的完成数来自实际响应或复用，未通过整书检查时保留待完成阶段
    monkeypatch.delenv('LESSONWEAVE_TRILIUM_URL',raising=False)
    save(tmp_path/'runtime/state.json',{'workflow':'lean-c-1.0','stage':'05_writing/c'})
    begin(tmp_path,'逐问生成',['first','second','third'])
    tick(tmp_path,'first','completed')
    tick(tmp_path,'second','reused')
    tick(tmp_path,'third','running')
    state=view(tmp_path,{'status':'running','created':time.time()-5,'updated':time.time()})
    assert state['done']==2 and state['total']==3 and state['active']==1
    assert state['completed_stages']==0


def test_terminate_stops_descendant_process(tmp_path):
    # 实际创建父子进程，停止进程组以后，子进程也停止写入心跳
    heartbeat=tmp_path/'heartbeat'
    child=tmp_path/'child.py'
    child.write_text('from pathlib import Path\nimport time\np=Path('+repr(str(heartbeat))+')\nwhile True:\n p.write_text(str(time.time()))\n time.sleep(.1)\n')
    parent=tmp_path/'parent.py'
    parent.write_text('import subprocess,sys,time\nsubprocess.Popen([sys.executable,'+repr(str(child))+'])\ntime.sleep(90)\n')
    options={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
    process=subprocess.Popen([sys.executable,str(parent)],**options)
    try:
        deadline=time.time()+10
        while not heartbeat.exists() and time.time()<deadline:
            time.sleep(.1)
        assert heartbeat.exists()
        terminate(process)
        previous=heartbeat.read_text()
        time.sleep(.35)
        assert heartbeat.read_text()==previous
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            terminate(process)


def test_native_note_keeps_structured_paragraphs_and_escapes_material():
    # 原生笔记接收正文块形式的承接和题干，保留核心内容并转义来源中的 HTML
    paragraph=lambda text:{'id':'p','kind':'paragraph','text':text}
    doc={'opening_title':'起点是什么？','opening':paragraph('承接已有理解'),'opening_forward':paragraph('引出新问题'),
         'core_questions':[{'question_id':'q','text':'怎样解释变化？'}],
         'units':[{'title':'怎样解释变化？','problem':paragraph('<script>material</script>'),'explanation':[paragraph('因为条件发生变化')],'synthesis':paragraph('所以结果随之变化')}],
         'summary':[{'question_id':'q','answer':paragraph('条件带来结果')}],
         'pitfalls':[{'premise':'已知条件相同，','question':'还能怎样比较？','body':paragraph('保持相同的比较范围')}],
         'quiz':[{'prompt':paragraph('结果依赖什么？'),'options':['条件','标题'],'answer':0,'explanation':paragraph('材料明确列出条件')}],
         'glossary':[{'display':'条件（Condition）','definition':'结果成立时需要满足的情况','explanation':['先核对条件，再解释结果']}]}
    result=section_html(doc,{})
    assert all(text in result for text in ['承接已有理解','引出新问题','结果依赖什么','条件带来结果','保持相同的比较范围','条件（Condition）'])
    assert '<script>material</script>' not in result
    assert '&lt;script&gt;material&lt;/script&gt;' in result
