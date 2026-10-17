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
            ''')
            if recover:
                db.execute("UPDATE jobs SET status='interrupted',updated=? WHERE status='running'", (time.time(),))

    def connect(self):
        connection = sqlite3.connect(self.root / 'lessonweave.sqlite', timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def projects(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM projects ORDER BY created DESC')]

    def project(self, key):
        with self.connect() as db:
            row = db.execute('SELECT * FROM projects WHERE id=?', (key,)).fetchone()
            if row is None:
                raise KeyError('找不到这个项目')
            return dict(row)

    def register(self, key, name, path, legacy=False):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO projects VALUES(?,?,?,?,?)', (key, name, str(Path(path).resolve()), time.time(), int(legacy)))
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
            return dict(row)

    def finish(self, key, result):
        with self.connect() as db:
            db.execute('UPDATE jobs SET status=?,updated=?,result=? WHERE id=?', (result['status'], time.time(), json.dumps(result, ensure_ascii=False), key))

    def resume(self, key):
        with self.connect() as db:
            db.execute("UPDATE jobs SET status='queued',updated=? WHERE id=? AND status IN ('interrupted','needs_review','failed')", (time.time(), key))

    def note(self, project, key, value=None):
        self.project(project)
        with self.connect() as db:
            if value is not None:
                db.execute('INSERT INTO notes VALUES(?,?,?,?) ON CONFLICT(project_id,note_key) DO UPDATE SET value=excluded.value,updated=excluded.updated', (project, key, value, time.time()))
            row = db.execute('SELECT value FROM notes WHERE project_id=? AND note_key=?', (project, key)).fetchone()
            return row['value'] if row else ''
