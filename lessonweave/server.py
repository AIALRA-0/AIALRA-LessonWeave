"""提供个人网站、持久任务和独立阅读演示，Codex 凭据只由执行端读取"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs
import json
import mimetypes
import os
import threading
import time
import uuid

from .storage import Store, read, save

REPO = Path(__file__).resolve().parents[1]
READER = REPO / '04-framework/reader'


def public_project(project):
    return {key: value for key, value in project.items() if key != 'path'}


def public_state(state):
    return {key:value for key,value in state.items() if key in {'status','stage','round','maximum','updated_at','elapsed_seconds'}}


def worker(store):
    from .jobs import execute
    while True:
        job = store.claim()
        if job is None:
            time.sleep(1)
            continue
        try:
            result=execute(store,job)
        except Exception as error:
            result = {'status': 'failed', 'issues': [str(error)]}
        store.finish(job['id'], result)


class Handler(SimpleHTTPRequestHandler):
    store = None

    def log_message(self, format, *args):
        return

    def json(self, value, status=200):
        content = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def allowed(self):
        if os.environ.get('LESSONWEAVE_AUTH_REQUIRED') == '1' and not self.headers.get('X-Aialra-User'):
            self.json({'error': '请先登录个人网站'}, 401)
            return False
        if os.environ.get('LESSONWEAVE_AUTH_REQUIRED') == '1' and os.environ.get('LESSONWEAVE_OWNER') and self.headers.get('X-Aialra-User') != os.environ['LESSONWEAVE_OWNER']:
            self.json({'error':'这个学习空间只向所有者开放'},403)
            return False
        return True

    def body(self):
        length = int(self.headers.get('Content-Length', '0'))
        if length > 110_000_000:
            raise ValueError('本次上传超过 100 MB，请缩小文件后继续')
        return self.rfile.read(length)

    def file(self, path, content=None, kind=None):
        if content is None:
            if not path.is_file():
                self.send_error(404)
                return
            content = path.read_bytes()
        mime = kind or mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
        self.send_response(200)
        self.send_header('Content-Type', mime + ('; charset=utf-8' if mime.startswith('text/') or mime == 'application/javascript' else ''))
        self.send_header('Content-Length', str(len(content)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store' if mime.endswith('json') else 'private, max-age=60')
        if mime in {'text/html','image/svg+xml'} and '/00_source/' in str(path).replace('\\','/'):
            self.send_header('Content-Security-Policy', "sandbox allow-same-origin; default-src 'self' data:; style-src 'self' 'unsafe-inline'; img-src 'self' data:")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if not self.allowed():
            return
        route = unquote(urlsplit(self.path).path)
        try:
            if route == '/api/health':
                self.json({'service': 'LessonWeave', 'version': '0.1.0', 'backend': os.environ.get('LESSONWEAVE_BACKEND', 'codex'), 'model': os.environ.get('LESSONWEAVE_MODEL', 'gpt-6.1-sol')})
            elif route == '/api/projects':
                result = []
                for project in self.store.projects():
                    root = Path(project['path'])
                    book = read(root/'05_writing/preview-book.json', read(root/'05_writing/book.json', {}))
                    result.append(dict(public_project(project), state=public_state(read(root/'runtime/state.json', {'status':'existing'})), title=book.get('title'), ready=bool(book) and (root/'05_writing/source-location/index.json').is_file(),readweave_available=bool(os.environ.get('LESSONWEAVE_TRILIUM_PUBLIC_URL') and project.get('native_note_id'))))
                self.json(result)
            elif route == '/api/library':
                from .trilium import configured
                self.json({'folders':self.store.folders(),'projects':[public_project(p) for p in self.store.projects(include_deleted=True)],'storage':'trilium' if configured() else 'local','native_root':os.environ.get('LESSONWEAVE_TRILIUM_ROOT')})
            elif route == '/api/jobs':
                from .progress import view
                self.json([dict({key:value for key,value in job.items() if key not in {'payload','result'}},progress=view(Path(self.store.project(job['project_id'])['path']),job)) for job in self.store.jobs()])
            elif route.startswith('/api/jobs/'):
                job = self.store.job(route.split('/')[3])
                job.pop('payload', None)
                from .progress import view
                job['progress']=view(Path(self.store.project(job['project_id'])['path']),job)
                self.json(job)
            elif route.startswith('/api/notes/'):
                parts = route.split('/')
                self.json({'value': self.store.note(parts[3], '/'.join(parts[4:]))})
            elif route.startswith('/api/artifacts/'):
                parts = route.split('/')
                root = Path(self.store.project(parts[3])['path'])
                self.json({name: read(root/path, {}) for name,path in {'material':'01_tree/tree.json','questions':'02_questions/questions.json','chapters':'03_chapters/chapters.json','transitions':'04_transitions/transitions.json','usage':'runtime/usage.json'}.items()})
            elif route.startswith('/p/'):
                parts = route.split('/')
                project = self.store.project(parts[2])
                root = Path(project['path']).resolve()
                name = '/'.join(parts[3:]) or 'book.html'
                if name=='open-readweave':
                    from .trilium import reading_link
                    section=parse_qs(urlsplit(self.path).query).get('section',[None])[0]
                    target=reading_link(project,root,section)
                    self.send_response(302)
                    self.send_header('Location',target)
                    self.send_header('Cache-Control','no-store')
                    self.end_headers()
                elif name in {'book.html', 'readweave.html'}:
                    html = (REPO/'integrations/readweave/demo.html' if name=='readweave.html' else READER/'book.html').read_text('utf-8')
                    config = {'project_id': parts[2], 'base': '/p/'+parts[2], 'readweave_demo': name=='readweave.html', 'legacy': bool(project['legacy'])}
                    html = html.replace('<head>', '<head><script>window.LESSONWEAVE='+json.dumps(config)+';</script><script src="/reader-mount.js"></script>')
                    if name=='book.html':
                        html = html.replace('</body>', '<script src="/reader-integration.js"></script></body>')
                    self.file(Path(name), html.encode('utf-8'), 'text/html')
                else:
                    path = (root/name).resolve()
                    if not path.is_relative_to(root) or path.suffix in {'.py','.pyc'} or name.startswith('runtime/calls/'):
                        self.send_error(404)
                        return
                    if path.suffix == '.html':
                        html = path.read_text('utf-8').replace('src="/00_', 'src="/p/'+parts[2]+'/00_').replace("src='/00_", "src='/p/"+parts[2]+"/00_")
                        self.file(path, html.encode(), 'text/html')
                    else:
                        self.file(path)
            elif route in {'/', '/index.html', '/app.js', '/app.css', '/reader-mount.js', '/reader-integration.js', '/inspect.html', '/inspect.js','/workspace','/workspace.html','/workspace.js','/workspace.css','/theme.css'}:
                self.file(REPO/'web'/('index.html' if route=='/' else 'workspace.html' if route=='/workspace' else route.lstrip('/')))
            elif route.startswith('/docs/assets/'):
                path = (REPO/route.lstrip('/')).resolve()
                if path.is_relative_to(REPO/'docs/assets'):
                    self.file(path)
                else:
                    self.send_error(404)
            elif route.startswith('/integrations/readweave/'):
                path=(REPO/route.lstrip('/')).resolve()
                if path.is_relative_to(REPO/'integrations/readweave') and path.suffix in {'.js','.css'}:
                    self.file(path)
                else:
                    self.send_error(404)
            elif (READER/route.lstrip('/')).is_file() and '/' not in route.lstrip('/'):
                self.file(READER/route.lstrip('/'))
            else:
                self.send_error(404)
        except (KeyError, ValueError, OSError) as error:
            self.json({'error': str(error)}, 400)

    def do_POST(self):
        if not self.allowed():
            return
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            self.json({'error': '提交来源与当前网站不同'}, 403)
            return
        route = unquote(urlsplit(self.path).path)
        try:
            if route == '/api/uploads':
                name = Path(self.headers.get('X-Filename', 'material.pdf')).name
                suffix = Path(name).suffix.lower()
                if suffix not in {'.pdf','.zip'}:
                    raise ValueError('请选择 PDF 或项目 ZIP 文件')
                key = uuid.uuid4().hex + suffix
                path = self.store.root/'uploads'/key
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(self.body())
                self.json({'upload_id': key, 'name': name})
                return
            payload = json.loads(self.body() or '{}')
            if route == '/api/folders':
                from .trilium import create_folder
                self.json(create_folder(self.store,self.store.clean_name(payload.get('name')),payload.get('parent_id','root')),201)
            elif route.startswith('/api/library/'):
                from .trilium import change
                parts=route.split('/')
                self.json(change(self.store,parts[3],parts[4],parts[5],payload))
            elif route == '/api/projects':
                from .pipeline import scaffold
                key = self.headers.get('Idempotency-Key')
                if not key or len(key) > 100:
                    raise ValueError('提交需要一个稳定的 Idempotency-Key')
                pid = str(uuid.uuid5(uuid.NAMESPACE_URL, 'lessonweave:'+key))
                try:
                    project = self.store.project(pid)
                except KeyError:
                    root = self.store.root/'projects'/pid
                    scaffold(root)
                    from .trilium import ensure_project
                    name=self.store.clean_name(payload.get('name','新的学习项目'))
                    folder_id=payload.get('folder_id','root')
                    native_note_id=ensure_project(self.store,pid,name,folder_id)
                    project = self.store.register(pid,name,root,folder_id=folder_id,native_note_id=native_note_id)
                kind = payload['kind']
                if kind == 'url':
                    from .network import validate_url
                    material = validate_url(payload['material'])
                else:
                    material = (self.store.root/'uploads'/payload['upload_id']).resolve()
                    if not material.is_relative_to(self.store.root/'uploads') or not material.is_file():
                        raise ValueError('上传文件已经失效')
                    material = str(material)
                input_value = {'kind': kind, 'material': material, 'mode': 'one_shot', 'system_prompt': payload.get('system_prompt') or '围绕完整原材料生成循序渐进的学习读本，保留来源、图表、术语、练习与逐项审查记录'}
                path = Path(project['path'])/'00_source/input.json'
                if not path.exists():
                    save(path, input_value)
                elif read(path)!=input_value:
                    raise ValueError('同一个提交标识对应了不同的输入')
                job = self.store.submit(pid, input_value, key)
                self.json({'project_id': pid, 'job_id': job['id']}, 201)
            elif route.startswith('/api/jobs/') and route.endswith('/resume'):
                key=route.split('/')[3]
                previous=self.store.job(key)
                from .progress import view
                root=Path(self.store.project(previous['project_id'])['path'])
                if view(root,previous).get('diagnosis',{}).get('failure_kind')=='output_limit':
                    raise ValueError('这次调用已超过输出上限，需要先拆小任务，已完成结果继续保留')
                if previous['status'] in {'interrupted','cancelled'}:
                    from .jobs import mark_cancelled
                    mark_cancelled(Path(self.store.project(previous['project_id'])['path']),reason='user_resumed_stopped_task')
                self.store.resume(key)
                self.json({'status':'queued'})
            elif route.startswith('/api/jobs/') and route.endswith('/cancel'):
                self.json(self.store.cancel(route.split('/')[3]))
            elif route.startswith('/api/notes/'):
                parts = route.split('/')
                self.json({'value': self.store.note(parts[3], '/'.join(parts[4:]), payload['value'])})
            elif route.startswith('/api/qa/'):
                project = route.split('/')[3]
                self.store.project(project)
                if not payload.get('question','').strip() or len(payload['question']) > 5000:
                    raise ValueError('请填写五千字以内的问题')
                job = self.store.submit(project, dict(payload, _type='qa'), self.headers.get('Idempotency-Key') or uuid.uuid4().hex)
                self.json({'job_id': job['id']}, 201)
            else:
                self.send_error(404)
        except (ValueError, KeyError, OSError) as error:
            self.json({'error': str(error)}, 400)


def serve(host='127.0.0.1', port=8960):
    if os.environ.get('LESSONWEAVE_AUTH_REQUIRED')=='1' and not os.environ.get('LESSONWEAVE_OWNER'):
        raise ValueError('个人网站启用登录时，需要配置 LESSONWEAVE_OWNER 指定所有者')
    # 升级时可让旧进程处理已有任务，新进程只领取尚未开始的任务
    store = Store(recover=os.environ.get('LESSONWEAVE_RECOVER_JOBS','1')!='0')
    Handler.store = store
    threading.Thread(target=worker, args=(store,), daemon=True).start()
    print('LessonWeave http://' + host + ':' + str(port), flush=True)
    server=ThreadingHTTPServer((host,port),Handler)
    try:
        server.serve_forever()
    finally:
        from .jobs import shutdown
        shutdown()
        server.server_close()
