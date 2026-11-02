"""Durable local experiment ledger and immutable JSON artifacts."""
import json,sqlite3,time,uuid
from pathlib import Path
from datetime import datetime,timezone
from .model import digest

def utc():return datetime.now(timezone.utc).isoformat()
class Store:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/'systematic.sqlite3'; (self.root/'artifacts').mkdir(exist_ok=True)
        with self.connect() as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, record TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY, created REAL, record TEXT NOT NULL)')
    def connect(self):return sqlite3.connect(self.db,timeout=15)
    def set(self,key,value):
        with self.connect() as c:c.execute('INSERT OR REPLACE INTO state VALUES(?,?)',(key,json.dumps(value,allow_nan=False)))
    def get(self,key,default=None):
        with self.connect() as c:r=c.execute('SELECT value FROM state WHERE key=?',(key,)).fetchone()
        return json.loads(r[0]) if r else default
    def artifact(self,value):
        key=digest(value);path=self.root/'artifacts'/f'{key}.json'
        if not path.exists():
            temp=path.with_suffix(f'.{uuid.uuid4().hex}.tmp');temp.write_text(json.dumps(value,sort_keys=True,allow_nan=False));temp.replace(path)
        return key
    def read_artifact(self,key):
        if len(key)!=64 or any(ch not in '0123456789abcdef' for ch in key):raise ValueError('invalid artifact hash')
        value=json.loads((self.root/'artifacts'/f'{key}.json').read_text())
        if digest(value)!=key:raise ValueError('artifact hash mismatch')
        return value
    def create_job(self,config):
        job=dict(config,id=str(uuid.uuid4()),config_hash=digest(config),status='queued',created_at=utc(),updated_at=utc(),runtime_seconds=None,metrics=None,error=None)
        with self.connect() as c:c.execute('INSERT INTO jobs VALUES(?,?)',(job['id'],json.dumps(job)))
        return job
    def update_job(self,id,**changes):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT record FROM jobs WHERE id=?',(id,)).fetchone()
            if not r:raise KeyError(id)
            job=json.loads(r[0]);job.update(changes,updated_at=utc());c.execute('UPDATE jobs SET record=? WHERE id=?',(json.dumps(job,allow_nan=False),id))
        return job
    def jobs(self):
        with self.connect() as c:rows=c.execute('SELECT record FROM jobs ORDER BY rowid DESC LIMIT 1000').fetchall()
        return [json.loads(r[0]) for r in rows]
    def job(self,id):
        with self.connect() as c:r=c.execute('SELECT record FROM jobs WHERE id=?',(id,)).fetchone()
        if not r:raise KeyError(id)
        return json.loads(r[0])
    def recover(self):
        for j in self.jobs():
            if j['status']=='running':self.update_job(j['id'],status='failed',error='interrupted by process restart; rerun with recorded config')
    def scan(self,value):
        self.set('snapshot',value)
        with self.connect() as c:
            c.execute('INSERT INTO scans(created,record) VALUES(?,?)',(time.time(),json.dumps(value,allow_nan=False)))
            c.execute('DELETE FROM scans WHERE created < ?',(time.time()-7*86400,))
    def history(self):
        with self.connect() as c:rows=c.execute('SELECT record FROM scans ORDER BY id DESC LIMIT 120').fetchall()
        return [json.loads(r[0]) for r in rows][::-1]
