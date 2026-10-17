"""保存可恢复的任务状态，运行资料始终放在代码仓库之外"""
from pathlib import Path
import json
import os
import sqlite3
import threading
import time
import uuid

WRITE_LOCK = threading.RLock()


def read(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with WRITE_LOCK:
        temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(temporary, path)


def data_root():
    return Path(os.environ.get('LESSONWEAVE_DATA', Path.home() / '.local/share/lessonweave')).resolve()


class Store:
    def __init__(self, root=None, recover=False):
        self.root = Path(root or data_root()).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,path TEXT NOT NULL,created REAL NOT NULL,legacy INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,idempotency_key TEXT UNIQUE NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,updated REAL NOT NULL,result TEXT);
                CREATE TABLE IF NOT EXISTS notes(project_id TEXT NOT NULL,note_key TEXT NOT NULL,value TEXT NOT NULL,updated REAL NOT NULL,PRIMARY KEY(project_id,note_key));
                CREATE TABLE IF NOT EXISTS folders(id TEXT PRIMARY KEY,parent_id TEXT NOT NULL,name TEXT NOT NULL,native_note_id TEXT,deleted INTEGER NOT NULL DEFAULT 0,trash_batch TEXT,created REAL NOT NULL);
            ''')
            for name,definition in [('folder_id',"TEXT NOT NULL DEFAULT 'root'"),('native_note_id','TEXT'),('deleted','INTEGER NOT NULL DEFAULT 0'),('trash_batch','TEXT')]:
                if name not in {row[1] for row in db.execute('PRAGMA table_info(projects)')}:
                    db.execute('ALTER TABLE projects ADD COLUMN '+name+' '+definition)
            db.execute("INSERT OR IGNORE INTO folders(id,parent_id,name,created) VALUES('root','','我的材料',?)",(time.time(),))
            if recover:
                db.execute("UPDATE jobs SET status=CASE WHEN status='cancelling' THEN 'cancelled' ELSE 'interrupted' END,updated=? WHERE status IN ('running','cancelling')", (time.time(),))

    def connect(self):
        connection = sqlite3.connect(self.root / 'lessonweave.sqlite', timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def projects(self, include_deleted=False):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM projects '+('' if include_deleted else 'WHERE deleted=0 ')+'ORDER BY created DESC')]

    def project(self, key):
        with self.connect() as db:
            row = db.execute('SELECT * FROM projects WHERE id=?', (key,)).fetchone()
            if row is None:
                raise KeyError('找不到这个项目')
            return dict(row)

    def register(self, key, name, path, legacy=False, folder_id='root', native_note_id=None):
        with self.connect() as db:
            self._folder(db,folder_id)
            db.execute('INSERT OR IGNORE INTO projects(id,name,path,created,legacy,folder_id,native_note_id) VALUES(?,?,?,?,?,?,?)', (key, name, str(Path(path).resolve()), time.time(), int(legacy),folder_id,native_note_id))
        return self.project(key)

    def submit(self, project, payload, key):
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        with self.connect() as db:
            existing = db.execute('SELECT * FROM jobs WHERE idempotency_key=?', (key,)).fetchone()
            if existing:
                if existing['payload'] != serialized or existing['project_id'] != project:
                    raise ValueError('同一个提交标识对应了不同的任务')
                return dict(existing)
            jid = uuid.uuid4().hex
            now = time.time()
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)', (jid, project, key, serialized, 'queued', now, now, None))
            from .metrics import start
            start(Path(self.project(project)['path']),'other','job_queue',job_id=jid)
        return self.job(jid)

    def job(self, key):
        with self.connect() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (key,)).fetchone()
            if row is None:
                raise KeyError('找不到这个任务')
            return dict(row)

    def jobs(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM jobs ORDER BY created DESC LIMIT 100')]

    def claim(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET status='running',updated=? WHERE id=?", (time.time(), row['id']))
            job=dict(row)
        from .metrics import finish,start
        root=Path(self.project(job['project_id'])['path'])
        for record in read(root/'runtime/timing.json',{'records':[]})['records']:
            if record.get('job_id')==job['id'] and record['operation']=='job_queue' and record['status']=='running':finish(root,record['id'])
        start(root,'other','job_run',job_id=job['id'])
        return job

    def finish(self, key, result):
        with self.connect() as db:
            current=db.execute('SELECT status FROM jobs WHERE id=?',(key,)).fetchone()
            if current and current['status'] in {'cancelling','cancelled'}:
                result=dict(result,status='cancelled')
            db.execute('UPDATE jobs SET status=?,updated=?,result=? WHERE id=?', (result['status'], time.time(), json.dumps(result, ensure_ascii=False), key))
        from .metrics import close_job
        close_job(Path(self.project(self.job(key)['project_id'])['path']),key,result['status'])

    def resume(self, key):
        with self.connect() as db:
            job=db.execute('SELECT project_id,status FROM jobs WHERE id=?',(key,)).fetchone()
            if not job or db.execute('SELECT deleted FROM projects WHERE id=?',(job['project_id'],)).fetchone()['deleted']:
                raise ValueError('先从回收站恢复项目，再继续任务')
            if job['status']=='needs_review':
                project=db.execute('SELECT path FROM projects WHERE id=?',(job['project_id'],)).fetchone()
                state=read(Path(project['path'])/'runtime/state.json',{})
                if state.get('round',0)>=state.get('maximum',3):
                    raise ValueError('本次已经达到返修上限，完整稿和检查问题已保留')
            if db.execute("SELECT 1 FROM jobs WHERE project_id=? AND id<>? AND status IN ('running','queued','cancelling')",(job['project_id'],key)).fetchone():
                raise ValueError('这个项目已有任务正在处理')
            changed=db.execute("UPDATE jobs SET status='queued',updated=? WHERE id=? AND status IN ('interrupted','needs_review','failed','cancelled')", (time.time(), key)).rowcount
            if changed:
                from .metrics import start
                start(Path(self.project(job['project_id'])['path']),'other','job_queue',job_id=key)

    def cancel(self,key):
        with self.connect() as db:
            row=db.execute('SELECT status FROM jobs WHERE id=?',(key,)).fetchone()
            if not row:
                raise KeyError('找不到这个任务')
            status='cancelled' if row['status']=='queued' else 'cancelling' if row['status']=='running' else row['status']
            db.execute('UPDATE jobs SET status=?,updated=? WHERE id=?',(status,time.time(),key))
        if status=='cancelled':
            from .metrics import close_job
            close_job(Path(self.project(self.job(key)['project_id'])['path']),key,status)
        return self.job(key)

    def folders(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM folders ORDER BY created')]

    @staticmethod
    def _folder(db,key):
        row=db.execute('SELECT * FROM folders WHERE id=? AND deleted=0',(key,)).fetchone()
        if not row:
            raise ValueError('目标文件夹已不存在，请选择其他位置')
        return dict(row)

    def create_folder(self,name,parent_id='root',native_note_id=None,key=None):
        name=self.clean_name(name)
        key=key or uuid.uuid4().hex
        with self.connect() as db:
            self._folder(db,parent_id)
            db.execute('INSERT INTO folders(id,parent_id,name,native_note_id,created) VALUES(?,?,?,?,?)',(key,parent_id,name,native_note_id,time.time()))
        return next(row for row in self.folders() if row['id']==key)

    @staticmethod
    def clean_name(name):
        if not isinstance(name,str) or not name.strip() or len(name)>150:
            raise ValueError('名称需要填写 1 到 150 个字符')
        return name.strip()

    def validate_library_change(self,kind,key,action,values):
        table='folders' if kind=='folder' else 'projects' if kind=='project' else None
        if table is None or action not in {'rename','move','trash','restore'}:
            raise ValueError('这个目录操作尚未支持')
        if key=='root':
            raise ValueError('根目录保持固定，请在下面创建文件夹')
        with self.connect() as db:
            row=db.execute('SELECT * FROM '+table+' WHERE id=?',(key,)).fetchone()
            if not row:
                raise KeyError('找不到选中的项目或文件夹')
            row=dict(row)
            if action=='rename':
                self.clean_name(values.get('name'))
            if action=='move':
                parent=values.get('parent_id','root')
                self._folder(db,parent)
                cursor=parent
                while cursor and kind=='folder':
                    if cursor==key:
                        raise ValueError('文件夹需要移动到自己的子目录之外')
                    found=db.execute('SELECT parent_id FROM folders WHERE id=?',(cursor,)).fetchone()
                    cursor=found['parent_id'] if found else ''
            if action=='trash':
                ids={key} if kind=='project' else {p['id'] for p in self.projects() if p['folder_id'] in self.descendants(key)}
                if any(job['project_id'] in ids and job['status'] in {'queued','running','cancelling'} for job in self.jobs()):
                    raise ValueError('先停止正在处理的任务，再把项目移入回收站')
            return row

    def descendants(self,key):
        rows=self.folders(); result={key}
        while True:
            new={row['id'] for row in rows if row['parent_id'] in result}
            if new<=result:
                return result
            result|=new

    def library_change(self,kind,key,action,values):
        row=self.validate_library_change(kind,key,action,values)
        table='folders' if kind=='folder' else 'projects'
        parent_field='parent_id' if kind=='folder' else 'folder_id'
        with self.connect() as db:
            if action=='rename':
                db.execute('UPDATE '+table+' SET name=? WHERE id=?',(self.clean_name(values['name']),key))
            elif action=='move':
                db.execute('UPDATE '+table+' SET '+parent_field+'=? WHERE id=?',(values['parent_id'],key))
            elif action=='trash':
                batch=uuid.uuid4().hex
                if kind=='folder':
                    for folder_id in self.descendants(key):
                        db.execute('UPDATE folders SET deleted=1,trash_batch=? WHERE id=? AND deleted=0',(batch,folder_id))
                        db.execute('UPDATE projects SET deleted=1,trash_batch=? WHERE folder_id=? AND deleted=0',(batch,folder_id))
                else:
                    db.execute('UPDATE projects SET deleted=1,trash_batch=? WHERE id=?',(batch,key))
            elif action=='restore':
                parent=db.execute('SELECT deleted FROM folders WHERE id=?',(row[parent_field],)).fetchone()
                if not parent or parent['deleted']:
                    db.execute('UPDATE '+table+' SET '+parent_field+"='root' WHERE id=?",(key,))
                for target in ['folders','projects']:
                    db.execute('UPDATE '+target+' SET deleted=0,trash_batch=NULL WHERE trash_batch=?',(row['trash_batch'],))
        return {'id':key,'action':action}

    def note(self, project, key, value=None):
        self.project(project)
        with self.connect() as db:
            if value is not None:
                db.execute('INSERT INTO notes VALUES(?,?,?,?) ON CONFLICT(project_id,note_key) DO UPDATE SET value=excluded.value,updated=excluded.updated', (project, key, value, time.time()))
            row = db.execute('SELECT value FROM notes WHERE project_id=? AND note_key=?', (project, key)).fetchone()
            return row['value'] if row else ''
